"""One input, end to end (spec §17.2).

resolve (a path, or a YouTube download) → probe → glossary → the source track: reused from the
sidecar, or made now: the language (given, inherited from earlier files in the folder, or
detected), decode, find speech, chunk, transcribe with retries, place words, add the timeline
offset, build cues, convert the Chinese script → translate each target (only what's new or stale)
→ write the files → record the full hash. Connection errors and Spark refusals wait with backoff
up to a limit, then raise Paused so the CLI exits 75 and a re-run resumes; finished chunks are
cached for the life of the process. Any other error fails only this input, with the fix. Events
carry stages and counts, never titles or paths (spec §6.8). A dry run writes and downloads
nothing: a link not downloaded yet is planned by its video id (final review).
"""

from __future__ import annotations

import hashlib
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Literal

import platformdirs

from vid2sub import detect as detecting
from vid2sub import store
from vid2sub.catalog import Suggestion, suggest
from vid2sub.config import Config, ConfigError
from vid2sub.engines.base import Chunk, ChunkResult, Engine, EngineError
from vid2sub.engines.clients import KeyRing, RunPolicy
from vid2sub.engines.registry import make_engine
from vid2sub.media import youtube
from vid2sub.media.chunk import chunk_samples, place, plan_chunks
from vid2sub.media.decode import SAMPLES_PER_MS, decode_to_wav, encode_flac, read_wav, to_float
from vid2sub.media.identity import full_sha256, identify
from vid2sub.media.probe import Probe, ProbeError, pick_track, probe, timeline_offset_ms
from vid2sub.media.tools import ToolFailed, ToolMissing, Tools
from vid2sub.media.vad import VAD_ID, speech_regions
from vid2sub.security import InputRefused, WriteRefused, resolve_input
from vid2sub.subs import langs, naming, scripts
from vid2sub.subs.build import build_cues
from vid2sub.subs.formats import SubtitleError
from vid2sub.subs.glossary import (
    EMPTY_GLOSSARY,
    Glossary,
    GlossaryError,
    chunk_prompt,
    parse_glossary,
    prompt_sha,
    vocabulary_prompt,
)
from vid2sub.subs.model import Segment, Transcript, shift_segment
from vid2sub.subs.rendition import cues_body, transcript_body
from vid2sub.subs.rules import rules_for
from vid2sub.subs.sidecar import (
    Conflict,
    HeadRecord,
    IdentityRecord,
    Sidecar,
    SidecarError,
    make_rendition,
)
from vid2sub.subs.translate_shape import stale_ids
from vid2sub.translate.run import PROMPT_VERSION, TranslationFailed, make_ask, translate_cues

MEDIA_SUFFIXES = frozenset({".mkv", ".mp4", ".m4v", ".mov", ".webm", ".avi", ".ts", ".m2ts",
                            ".wmv", ".mp3", ".m4a", ".aac", ".flac", ".wav", ".ogg", ".opus"})
CHUNKER_VERSION = "c1"
PROMPT_POLICY = "p1"
PIPELINE = hashlib.sha256(f"{VAD_ID}|{CHUNKER_VERSION}|{PROMPT_POLICY}".encode()).hexdigest()[:8]
SUSPECT_COMPRESSION = 2.4
Event = Callable[[str, dict[str, Any]], None]


class Paused(RuntimeError):
    def __init__(self, error: EngineError):
        super().__init__(str(error))
        self.error = error


class StopRun(RuntimeError):
    pass


class InputError(RuntimeError):
    def __init__(self, message: str, hint: str = ""):
        super().__init__(message)
        self.hint = hint


@dataclass
class RunOptions:
    source_lang: str | None = None
    targets: list[str] = field(default_factory=lambda: ["en"])
    formats: list[str] = field(default_factory=lambda: ["srt"])
    model: str | None = None
    translate_model: str | None = None
    script: str | None = None
    glossary: Path | None = None
    audio_track: int | str | None = None
    keep_video: bool = False
    skip_existing: bool = False
    overwrite_foreign: bool = False
    allow_cloud: bool = False
    dry_run: bool = False
    on_uncertain: Literal["proceed", "skip", "stop"] = "skip"
    wait_on_connection_s: float = 600.0
    replace_edited: bool = False


@dataclass
class InputResult:
    input: str
    status: Literal["done", "skipped", "failed", "uncertain", "planned"] = "failed"
    title: str = ""
    reason: str = ""  # for people: may name a file, so never put in --json output
    hint: str = ""
    kind: str = ""  # for scripts: an error kind or exception name, safe for --json
    notes: list[str] = field(default_factory=list)
    written: list[str] = field(default_factory=list)
    foreign: list[str] = field(default_factory=list)
    kept: list[str] = field(default_factory=list)
    plan: dict[str, Any] = field(default_factory=dict)


def _no_event(kind: str, fields: dict[str, Any]) -> None:
    return None


@dataclass
class RunContext:
    config: Config
    tools: Tools
    keys: KeyRing
    options: RunOptions
    events: Event = _no_event
    sleep: Callable[[float], None] = time.sleep
    engines: dict[str, Engine] = field(default_factory=dict)
    chunk_cache: dict[tuple, ChunkResult] = field(default_factory=dict)
    folder_votes: dict[Path, list[str]] = field(default_factory=dict)
    candidates: list | None = None

    @property
    def policy(self) -> RunPolicy:
        return RunPolicy(self.options.allow_cloud)

    def engine(self, name: str) -> Engine:
        if name not in self.engines:
            self.engines[name] = make_engine(name, self.config, self.policy, self.keys)
        return self.engines[name]

    def get_candidates(self) -> list:
        if self.candidates is None:
            self.candidates = detecting.candidates(self.config, self.keys)
        return self.candidates

    def close(self) -> None:
        for engine in self.engines.values():
            engine.close()


def _guarded(result: InputResult, work: Callable[[Path], None]) -> InputResult:
    """Run one input's work in a scratch folder; any ordinary error fails only this input."""
    with tempfile.TemporaryDirectory(prefix="vid2sub-") as tmp:
        try:
            work(Path(tmp))
        except (Paused, StopRun):
            raise
        except (EngineError, ToolMissing, youtube.YouTubeError, InputError) as err:
            _fail(result, str(err), getattr(err, "hint", ""),
                  getattr(err, "kind", type(err).__name__))
        except OSError as err:  # never err.filename: reasons may reach a --json consumer's log
            _fail(result, "couldn't read or write a file here"
                  + (f" ({err.strerror})" if err.strerror else ""),
                  "check the folder's permissions and free space", type(err).__name__)
        except ToolFailed as err:
            _fail(result, f"{err.tool} couldn't process this file",
                  "check that it plays in a media player", "ToolFailed")
        except (youtube.NotYouTube, ProbeError, InputRefused, SubtitleError, GlossaryError,
                ConfigError, SidecarError, store.StoreError, WriteRefused, TranslationFailed,
                naming.UnknownTrack, langs.UnknownLanguage) as err:
            _fail(result, str(err), kind=type(err).__name__)
    return result


def run_one(source: str, ctx: RunContext) -> InputResult:
    result = InputResult(input=source)
    return _guarded(result, lambda scratch: _run(source, ctx, scratch, result))


def _check_external(video: Path, header, sidecar: Sidecar, result: InputResult) -> Sidecar:
    """Fold in outside edits to the subtitle files, with notes that name no file (spec §6.8)."""
    def unreadable(name: str) -> None:
        track = naming.track_from_subtitle_name(video.name, name) or "subtitle"
        result.notes.append(
            f"left your {track} {Path(name).suffix} file alone: it isn't a readable "
            "subtitle file; delete it to have vid2sub write it again")
    sidecar, changed = store.check_external(video, header, sidecar, on_unreadable=unreadable)
    result.notes += [f"kept your outside edit to {t}" for t in changed]
    return sidecar


def _fail(result: InputResult, reason: str, hint: str = "", kind: str = "") -> None:
    result.status, result.reason, result.hint, result.kind = "failed", reason, hint, kind


def _planned_source(opts: RunOptions, src_track: str | None = None) -> str:
    if src_track:
        return src_track
    return naming.source_track(opts.source_lang, opts.script) if opts.source_lang else "detect"


def _run(source: str, ctx: RunContext, scratch: Path, result: InputResult) -> None:
    opts = ctx.options
    video = _resolve(source, ctx, scratch, result)
    if video is None:  # a dry run of a link not downloaded yet: named by its id, never a title
        result.status = "planned"
        result.plan = {
            "download": f"YouTube video {youtube.video_id(source)} (not downloaded yet)",
            "source": _planned_source(opts),
            "transcribe": opts.model or "suggested",
            "targets": [naming.target_track(t) for t in opts.targets],
        }
        return
    is_url = youtube.is_url(source)
    ctx.events("stage", {"stage": "probe"})
    p = probe(video, ctx.tools, scratch=scratch)
    header = store.header_for(video, identify(video), p.duration_ms)
    sidecar, _ = store.load(video)
    if sidecar is not None and not opts.dry_run:  # a dry run writes nothing, not even versions
        sidecar = _check_external(video, header, sidecar, result)
    glossary = _glossary(video, opts)
    targets = [naming.target_track(t) for t in opts.targets]
    src_track = store.source_track(sidecar) if sidecar is not None else None
    if opts.skip_existing and _all_exist(video, targets, opts.formats, src_track):
        result.status, result.reason = "skipped", "its subtitle files already exist"
        return
    if opts.dry_run:
        result.status = "planned"
        result.plan = {
            "source": _planned_source(opts, src_track),
            "transcribe": "reuse the sidecar" if src_track else (opts.model or "suggested"),
            "targets": targets,
            "files": [store.subtitle_path(video, t, f).name
                      for t in ([src_track] if src_track else []) + targets
                      for f in opts.formats],
        }
        return
    if src_track is None:
        if sidecar is not None:
            forked = _forked_source(sidecar)
            if forked:
                raise store.StoreError(f"the {forked} track has two versions; pick one in the "
                                       "editor")
        sidecar, src_track = _transcribe(video, p, header, sidecar, glossary, ctx, scratch,
                                         result, is_url=is_url)
        if src_track is None:
            return
    elif opts.source_lang and naming.track(src_track).lang != opts.source_lang:
        result.notes.append(f"kept the existing {src_track} transcript; --from "
                            f"{opts.source_lang} applies only to new transcripts")
    sidecar = _translate_targets(video, header, sidecar, src_track, targets, glossary, ctx,
                                 result)
    tracks = [src_track] + [t for t in targets if t != src_track]
    sidecar = _write(video, header, sidecar, tracks, ctx, result)
    if sidecar.identity() is None:
        ctx.events("stage", {"stage": "hash"})
        store.append(video, header, [IdentityRecord(sha256=full_sha256(video), at=store.now())])
    result.status = "done"


def _resolve(source: str, ctx: RunContext, scratch: Path, result: InputResult) -> Path | None:
    """The video to work on; None only for a dry run of a link that isn't downloaded yet."""
    if youtube.is_url(source):
        configured = ctx.config.defaults.youtube_dir
        out_dir = (Path(configured).expanduser() if configured
                   else Path(platformdirs.user_videos_dir()) / "vid2sub")
        if ctx.options.dry_run:  # a dry run never downloads (final review)
            found = youtube.find_existing(out_dir, youtube.video_id(source))
            if found is not None:
                result.title = found.stem.rsplit(" [", 1)[0]
            return found
        ctx.events("stage", {"stage": "download"})
        fetched = youtube.download(source, out_dir=out_dir, scratch=scratch,
                                   keep_video=ctx.options.keep_video, tools=ctx.tools)
        result.title = fetched.title
        return fetched.path
    path = resolve_input(source)
    if not path.is_file():
        raise InputError("there's no file at that path")
    result.title = path.name
    twins = [p for p in path.parent.iterdir() if p != path and p.stem.casefold() == path.stem.casefold()
             and p.suffix.lower() in MEDIA_SUFFIXES]
    if twins:
        raise InputError("another video in this folder has the same name, so their subtitles "
                         "would collide (spec §8.3)", "rename one of them")
    return path


def _glossary(video: Path, opts: RunOptions) -> Glossary:
    path = opts.glossary or video.parent / naming.GLOSSARY_NAME
    if not path.is_file():
        if opts.glossary is not None:
            raise InputError("that glossary file doesn't exist")
        return EMPTY_GLOSSARY
    try:
        return parse_glossary(path.read_text(encoding="utf-8-sig"))
    except UnicodeDecodeError:
        raise GlossaryError("the glossary isn't UTF-8; save it as UTF-8") from None


def _all_exist(video: Path, targets: list[str], formats: list[str],
               src_track: str | None) -> bool:
    tracks = list(targets) + ([src_track] if src_track else [])
    return bool(tracks) and all(store.subtitle_path(video, t, f).exists()
                                for t in tracks for f in formats)


def _forked_source(sidecar: Sidecar) -> str | None:
    """A source track that is in Conflict, so it can't be reused and mustn't be redone."""
    renditions = sidecar.renditions()
    for track in sidecar.tracks():
        head = sidecar.head(track)
        if isinstance(head, Conflict) and any(
                renditions[i].body.get("meta", {}).get("role") == "source"
                for i in head.leaves if i in renditions):
            return track
    return None


class _PatientDetector:
    """An engine whose language detection waits and pauses like transcription (spec §17.2)."""

    def __init__(self, inner: Engine, ctx: RunContext):
        self._inner, self._ctx = inner, ctx

    def detect_language(self, chunk: Chunk):
        return _retrying(lambda: self._inner.detect_language(chunk), self._ctx)

    def __getattr__(self, name: str):
        return getattr(self._inner, name)


def _waits_for(cands: list, pick: Callable[[list], str | None]) -> bool:
    """Whether the route's pick, were every server answering, is one that isn't answering now."""
    hoped = pick([replace(c, available=True, reason="") if c.unreachable else c for c in cands])
    return any(c.name == hoped and c.unreachable for c in cands)


def _candidates_that_work(ctx: RunContext, pick: Callable[[list], str | None]) -> list:
    """The candidates, looked at again while the model the route prefers might still come back.

    `pick` is the route: candidates in, the chosen model's name (or None) out. It is asked twice,
    once as if every server answered and once with the real list; when the first answer is a
    server that didn't answer, this waits and probes again, then pauses, rather than taking the
    next model down the route or the cloud (spec §7.2, §17.3, §17.4; final review). A server the
    route wouldn't pick anyway causes no waiting.
    """
    cands = ctx.get_candidates()
    if not _waits_for(cands, pick):
        return cands

    def look() -> list:
        fresh = detecting.candidates(ctx.config, ctx.keys)
        ctx.candidates = fresh
        if _waits_for(fresh, pick):
            raise EngineError("connection", "the model server isn't reachable",
                              hint="is it running? For the Spark: is `make tunnel` running?")
        return fresh

    return _retrying(look, ctx)


def _choose(video: Path, samples, speech, encode, ctx: RunContext, result: InputResult, *,
            is_url: bool = False) -> tuple[str | None, str | None, dict]:
    opts = ctx.options
    lang, meta = opts.source_lang, {}
    if lang is None:
        votes = [] if is_url else ctx.folder_votes.get(video.parent, [])
        if len(votes) >= 2 and len(set(votes)) == 1:
            lang, meta = votes[0], {"inherited_from_folder": True}
            result.notes.append(f"used {lang} like the other videos in this folder")
        else:
            def detector_for(c: list) -> str | None:
                return detecting.choose_detector(c, allow_cloud=opts.allow_cloud)

            detector = detector_for(_candidates_that_work(ctx, detector_for))
            if detector is None:
                raise InputError("no model is available to detect the language",
                                 "pass --from LANG, or check `vid2sub models`")
            ctx.events("stage", {"stage": "detect"})
            found = detecting.detect(_PatientDetector(ctx.engine(detector), ctx), samples, speech,
                                     len(samples) // SAMPLES_PER_MS, encode=encode)
            meta = {"detector": found.detector, "votes": list(found.votes),
                    "confidence": found.confidence}
            if found.uncertain:
                if opts.on_uncertain == "stop":
                    raise StopRun(found.reason())
                if opts.on_uncertain == "skip" or found.language is None:
                    result.status, result.reason = "uncertain", found.reason()
                    result.hint = "run it again with --from LANG (for example --from yue)"
                    return None, None, meta
            lang = found.language
            if found.uncertain:
                result.notes.append(f"went ahead with {lang} although {found.reason()}")
            elif not is_url:  # only a confident detection votes, and a download has no folder
                ctx.folder_votes.setdefault(video.parent, []).append(lang)
    model = opts.model
    if model is None:
        def suggestion(cands: list):
            return suggest(lang, cands, "transcribe", allow_cloud=opts.allow_cloud)

        s = suggestion(_candidates_that_work(ctx, lambda c: suggestion(c).model))
        if s.model is None:
            raise InputError(f"no usable transcription model for {langs.get(lang).name}",
                             "; ".join(f"{n}: {r}" for n, r in s.considered)
                             or "add one to vid2sub.toml (`vid2sub config init`)")
        if s.warning:
            result.notes.append(s.warning)
        model = s.model
    return lang, model, meta


def _retrying(fn: Callable[[], Any], ctx: RunContext) -> Any:
    """Run one model call under the shared retry policy (spec §17.2).

    A server error is retried twice with a short pause. A dropped connection or a refusal waits
    with backoff until `wait_on_connection_s` is spent, then raises Paused. Anything else is
    raised as it came. Transcription and translation both go through here, so a Spark drop in
    either pauses the run rather than failing the input (controller ruling 1).
    """
    waited, server_tries = 0.0, 0
    while True:
        try:
            return fn()
        except EngineError as err:
            if err.kind == "server" and server_tries < 2:
                server_tries += 1
                ctx.sleep(2.0 ** server_tries)
                continue
            if err.kind in ("connection", "refused"):
                delay = err.retry_after or min(30.0, 5.0 + waited / 4)
                if waited + delay > ctx.options.wait_on_connection_s:
                    raise Paused(err) from None
                ctx.events("waiting", {"kind": err.kind, "seconds": round(delay)})
                ctx.sleep(delay)
                waited += delay
                continue
            raise


def _with_retries(engine: Engine, chunk: Chunk, *, language: str, prompt: str,
                  ctx: RunContext) -> ChunkResult:
    return _retrying(lambda: engine.transcribe(chunk, language=language, prompt=prompt), ctx)


def _transcribe(video: Path, p: Probe, header, sidecar: Sidecar | None, glossary: Glossary,
                ctx: RunContext, scratch: Path, result: InputResult, *,
                is_url: bool = False) -> tuple[Sidecar | None, str | None]:
    opts = ctx.options
    track = pick_track(p, opts.source_lang, opts.audio_track)
    offset = timeline_offset_ms(p, track)
    ctx.events("stage", {"stage": "decode"})
    wav = scratch / "audio.wav"
    decode_to_wav(video, track, wav, ctx.tools, scratch=scratch, duration_ms=p.duration_ms)
    samples = read_wav(wav)
    ctx.events("stage", {"stage": "speech"})
    speech = speech_regions(to_float(samples))

    def encode(s):
        return encode_flac(s, ctx.tools, scratch=scratch)

    lang, model_name, detection = _choose(video, samples, speech, encode, ctx, result,
                                         is_url=is_url)
    if lang is None:
        return sidecar, None
    engine = ctx.engine(model_name)
    duration = len(samples) // SAMPLES_PER_MS
    plans = plan_chunks(speech, duration, engine.max_chunk_s)
    cjk = langs.get(lang).cjk
    vocab = prompt_sha(vocabulary_prompt(glossary.source_terms())) if engine.supports_prompt \
        else ""
    segments: list[Segment] = []
    tail, answered = "", None
    for plan in plans:
        ctx.events("chunk", {"index": plan.index + 1, "of": len(plans)})
        key = (header.video.quick_sha256, track.stream_index, model_name, lang, plan.plan_hash(),
               vocab)
        if key not in ctx.chunk_cache:
            chunk = Chunk(plan.index, chunk_samples(samples, plan, speech), encode)
            prompt = chunk_prompt(glossary, tail, cjk=cjk) if engine.supports_prompt else ""
            ctx.chunk_cache[key] = _with_retries(engine, chunk, language=lang, prompt=prompt,
                                                 ctx=ctx)
        res = ctx.chunk_cache[key]
        answered = res.answered_model or answered
        placed = place(plan, res.parsed.segments)
        segments += placed
        suspect = any((s.compression_ratio or 0) > SUSPECT_COMPRESSION for s in placed)
        tail = "" if suspect else "".join(s.text for s in placed)[-200:]
    transcript = Transcript(language=lang,
                            segments=tuple(shift_segment(s, offset) for s in segments))
    stamp = engine.stamp()
    now = store.now()
    t_body = transcript_body(
        transcript, engine=stamp.engine, model=stamp.model,
        version=f"{stamp.label}+v{vocab or '0'}+p{PIPELINE}", created_at=now,
        inputs={"audio_sha256": full_sha256(wav), "video_quick_sha256": header.video.quick_sha256,
                "audio_track": track.index, "timeline_offset_ms": offset},
        meta={"vad": VAD_ID, "chunker": CHUNKER_VERSION, "prompt_policy": PROMPT_POLICY,
              "speech": [list(r) for r in speech], "chunks": len(plans),
              "answered_model": answered, "detection": detection})
    t_rec = make_rendition([], None, t_body)
    rules = rules_for(lang)
    cues = build_cues(transcript, rules,
                      speech=[(s + offset, e + offset) for s, e in speech])
    src_track = naming.source_track(lang, opts.script)
    info = naming.track(src_track)
    c_rec = make_rendition([t_rec.id], src_track, cues_body(
        cues, language=lang, script=info.script, engine="vid2sub", model=None,
        version=f"cues@{rules.sha()}", created_at=now, inputs={"transcript": t_rec.id},
        meta={"role": "source"}))
    records: list = [t_rec, c_rec]
    head_target = c_rec
    config = scripts.config_for(src_track)
    if config:
        head_target = make_rendition([c_rec.id], src_track, cues_body(
            scripts.convert_cues(cues, config), language=lang, script=info.script,
            engine=f"opencc:{config}", model=None, version=f"opencc@{config}", created_at=now,
            inputs={"cues": c_rec.id}, meta={"role": "source"}))
        records.append(head_target)
    base = sidecar or Sidecar(header)
    head = store.head_record(base, src_track, head_target.id, "auto",
                             replace_person=opts.replace_edited)
    if head is None and base.head(src_track) is not None:
        result.kept.append(src_track)
    sidecar = store.append(video, header, records + ([head] if head else []))
    return sidecar, src_track


def _translator(src_lang: str, ctx: RunContext) -> str:
    if ctx.options.translate_model:
        return ctx.options.translate_model

    def suggestion(cands: list):
        return suggest(src_lang, cands, "translate", allow_cloud=ctx.options.allow_cloud)

    s = suggestion(_candidates_that_work(ctx, lambda c: suggestion(c).model))
    if s.model is None:
        raise InputError("no usable translation model",
                         "; ".join(f"{n}: {r}" for n, r in s.considered)
                         or "add one to vid2sub.toml (`vid2sub config init`)")
    return s.model


def _translate_targets(video: Path, header, sidecar: Sidecar, src_track: str,
                       targets: list[str], glossary: Glossary, ctx: RunContext,
                       result: InputResult, *, fresh: bool = False) -> Sidecar:
    opts = ctx.options
    src_rec, source = store.current_cues(sidecar, src_track)
    src_lang = naming.track(src_track).lang
    by_id = {c.id: c for c in source}
    for target in targets:
        if target == src_track:
            continue
        if opts.skip_existing and all(store.subtitle_path(video, target, f).exists()
                                      for f in opts.formats):
            continue
        model_name = _translator(src_lang, ctx)
        entry = ctx.config.models.get(model_name)
        if entry is None or entry.task != "translate":
            raise ConfigError(f"{model_name} isn't a translation model in vid2sub.toml")
        existing = sidecar.head(target)
        if isinstance(existing, Conflict):
            result.notes.append(f"the {target} track has two versions; pick one in the editor")
            continue
        if isinstance(existing, HeadRecord) and existing.by != "auto" \
                and not opts.replace_edited:
            result.kept.append(target)
            result.notes.append(f"kept your {target} subtitles; --replace-edited would redo them")
            continue
        parents, keep, todo = [src_rec.id], [], list(by_id)
        if isinstance(existing, HeadRecord):
            old_rec, old = store.current_cues(sidecar, target)
            parents.append(old_rec.id)
            same = (old_rec.body["payload"].get("glossary_sha", "") == (glossary.sha() or "")
                    and old_rec.body.get("model") == entry.model)
            stale = stale_ids(old, by_id) if (same and not fresh) else {c.id for c in old}
            keep = [c for c in old if c.id not in stale or "edited" in c.flags]
            covered = {i for c in keep for i in (c.src or ())}
            todo = [i for i in by_id if i not in covered]
            if not todo:
                continue
        ctx.events("stage", {"stage": "translate"})
        raw_ask = make_ask(model_name, entry, ctx.config, ctx.policy, ctx.keys)

        def ask(system, prompt, model, _raw=raw_ask):
            return _retrying(lambda: _raw(system, prompt, model), ctx)

        new = translate_cues(source, source_lang=src_lang, target_track=target,
                             glossary=glossary, ask=ask, only=todo if keep else None,
                             taken={c.id for c in keep},
                             on_batch=lambda n, total: ctx.events("batch",
                                                                  {"index": n, "of": total}))
        info = naming.track(target)
        rec = make_rendition(parents, target, cues_body(
            store.normalise_track(keep + new), language=info.lang, script=info.script,
            engine=f"translate:{model_name}", model=entry.model,
            version=f"{entry.model}@unknown+g{glossary.sha() or '0'}+{PROMPT_VERSION}",
            created_at=store.now(), inputs={"source": src_rec.id}, meta={"role": "translation"},
            glossary_sha=glossary.sha() or None))
        head = store.head_record(sidecar, target, rec.id, "auto",
                                 replace_person=opts.replace_edited)
        if head is None and isinstance(existing, HeadRecord):
            result.kept.append(target)
        sidecar = store.append(video, header, [rec] + ([head] if head else []))
    return sidecar


def _write(video: Path, header, sidecar: Sidecar, tracks: list[str], ctx: RunContext,
           result: InputResult) -> Sidecar:
    opts = ctx.options
    for track in tracks:
        if not isinstance(sidecar.head(track), HeadRecord):
            continue
        for fmt in opts.formats:
            try:
                sidecar, path, written = store.project(video, header, sidecar, track, fmt,
                                                       overwrite_foreign=opts.overwrite_foreign)
            except store.ForeignFile as err:
                result.foreign.append(err.name)
                continue
            if written:
                result.written.append(path.name)
    return sidecar


@dataclass
class DetectReport:
    input: str
    title: str = ""
    duration_ms: int = 0
    tracks: list[str] = field(default_factory=list)
    detection: detecting.Detection | None = None
    transcribe: Suggestion | None = None
    translate: Suggestion | None = None
    error: str = ""
    kind: str = ""
    hint: str = ""


def detect_one(source: str, ctx: RunContext) -> DetectReport:
    """What `run` would do for one file, without transcribing it (spec §18.1).

    Detection waits and pauses like a run's does: a dropped tunnel raises Paused (§17.2, §17.3).
    """
    report = DetectReport(input=source)
    if youtube.is_url(source):
        report.error, report.kind = "detect works on files, not links", "NotAFile"
        report.hint = "download it first with `vid2sub run URL --to none`"
        return report
    opts = ctx.options
    with tempfile.TemporaryDirectory(prefix="vid2sub-") as tmp:
        scratch = Path(tmp)
        try:
            path = resolve_input(source)
            if not path.is_file():
                raise InputError("there's no file at that path")
            report.title = path.name
            p = probe(path, ctx.tools, scratch=scratch)
            report.duration_ms = p.duration_ms
            report.tracks = [f"{t.index}: {t.language or t.tag or '?'} {t.codec}"
                             f"{' (default)' if t.default else ''}" for t in p.audio]
            lang = opts.source_lang
            if lang is None:
                track = pick_track(p, None, opts.audio_track)
                wav = scratch / "audio.wav"
                decode_to_wav(path, track, wav, ctx.tools, scratch=scratch,
                              duration_ms=p.duration_ms)
                samples = read_wav(wav)

                def detector_for(c: list) -> str | None:
                    return detecting.choose_detector(c, allow_cloud=opts.allow_cloud)

                detector = detector_for(_candidates_that_work(ctx, detector_for))
                if detector is None:
                    raise InputError("no model is available to detect the language",
                                     "check `vid2sub models`")
                report.detection = detecting.detect(
                    _PatientDetector(ctx.engine(detector), ctx), samples,
                    speech_regions(to_float(samples)), len(samples) // SAMPLES_PER_MS,
                    encode=lambda s: encode_flac(s, ctx.tools, scratch=scratch))
                lang = report.detection.language
            if lang:
                def suggestion(c: list, task: str) -> Suggestion:
                    return suggest(lang, c, task, allow_cloud=opts.allow_cloud)

                def routed(task: str) -> Suggestion:
                    return suggestion(_candidates_that_work(
                        ctx, lambda c: suggestion(c, task).model), task)

                report.transcribe = routed("transcribe")
                report.translate = routed("translate")
        except (Paused, StopRun):
            raise
        except (EngineError, ToolMissing, InputError) as err:
            report.error, report.hint = str(err), getattr(err, "hint", "")
            report.kind = getattr(err, "kind", type(err).__name__)
        except OSError as err:  # never err.filename (spec §6.8)
            report.error = ("couldn't read a file here"
                            + (f" ({err.strerror})" if err.strerror else ""))
            report.kind = type(err).__name__
        except (ToolFailed, ProbeError, InputRefused, ConfigError) as err:
            report.error, report.kind = str(err), type(err).__name__
    return report


def _existing(source: str, ctx: RunContext, scratch: Path, result: InputResult):
    video = resolve_input(source)
    if not video.is_file():
        raise InputError("there's no file at that path")
    result.title = video.name
    p = probe(video, ctx.tools, scratch=scratch)
    header = store.header_for(video, identify(video), p.duration_ms)
    sidecar, _ = store.load(video)
    if sidecar is None:
        raise InputError("this video has no vid2sub sidecar yet",
                         "run `vid2sub run` (or `vid2sub import`) on it first")
    return video, header, _check_external(video, header, sidecar, result)


def translate_one(source: str, ctx: RunContext, *, fresh: bool) -> InputResult:
    result = InputResult(input=source)

    def work(scratch: Path) -> None:
        video, header, sidecar = _existing(source, ctx, scratch, result)
        src_track = store.source_track(sidecar)
        if src_track is None:
            raise InputError("the sidecar has no source subtitles",
                             "run `vid2sub run` or `vid2sub import` first")
        targets = [naming.target_track(t) for t in ctx.options.targets]
        sidecar = _translate_targets(video, header, sidecar, src_track, targets,
                                     _glossary(video, ctx.options), ctx, result, fresh=fresh)
        _write(video, header, sidecar, targets, ctx, result)
        result.status = "done"

    return _guarded(result, work)


def write_one(source: str, ctx: RunContext) -> InputResult:
    result = InputResult(input=source)

    def work(scratch: Path) -> None:
        video, header, sidecar = _existing(source, ctx, scratch, result)
        _write(video, header, sidecar, sidecar.tracks(), ctx, result)
        result.status = "done"

    return _guarded(result, work)


def import_one(sub_path: str, video_path: str, track: str | None,
               ctx: RunContext) -> InputResult:
    result = InputResult(input=sub_path)

    def work(scratch: Path) -> None:
        sub = resolve_input(sub_path)
        video = resolve_input(video_path)
        if not sub.is_file() or not video.is_file():
            raise InputError("both the subtitle file and the video must exist")
        result.title = video.name
        key = naming.target_track(track) if track else naming.track_from_subtitle_name(
            video.name, sub.name)
        if key is None:
            raise InputError("can't tell the subtitle's language from its name",
                             "pass --lang (for example --lang ja)")
        p = probe(video, ctx.tools, scratch=scratch)
        header = store.header_for(video, identify(video), p.duration_ms)
        existing, _ = store.load(video)
        current = store.source_track(existing) if existing else None
        role = "source" if current in (None, key) else "translation"
        sidecar = store.import_subtitles(video, header, sub, key, role=role)
        _, cues = store.current_cues(sidecar, key)
        result.notes.append(f"imported {len(cues)} cues as the {key} {role} track")
        result.status = "done"

    return _guarded(result, work)
