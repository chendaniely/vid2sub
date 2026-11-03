"""M1-shaped episodes for the editor's tests: a short video, its sidecar and its subtitle files.

Built with store's own functions in the shape M1's pipeline writes (pipeline._transcribe and
_translate_targets): a transcript, a source track whose cues point into its words, a
translation per target whose cues record src and src_sha, auto heads, and each track's SRT
projected next to the video. Ids are fixed (`sid(i)`, `tid(i)`) so tests can name cues; they
have new_cue_id's shape, as the editor's edits require.
"""

from __future__ import annotations

import tempfile
from collections.abc import Sequence
from pathlib import Path

from helpers import make_clip

from vid2sub import store
from vid2sub.media.identity import identify
from vid2sub.media.probe import probe
from vid2sub.media.tools import Tools
from vid2sub.subs.model import Cue, Segment, Transcript, Word
from vid2sub.subs.rendition import cues_body, transcript_body
from vid2sub.subs.sidecar import Header, HeadRecord, RenditionRecord, Sidecar, make_rendition
from vid2sub.subs.translate_shape import src_sha

LINES = ("おはよう", "元気ですか", "はい、元気です")
ENGLISH = ("Good morning", "How are you?", "Yes, I'm fine")
STEP_MS, LENGTH_MS = 3600, 3000  # cue i runs from i × 3.6 s for 3 s


def sid(i: int) -> str:
    return f"ca{i:07x}"


def tid(i: int) -> str:
    return f"cb{i:07x}"


def source_cues(n: int) -> list[Cue]:
    texts = LINES if n == len(LINES) else [f"台詞{i}" for i in range(n)]
    return [Cue(id=sid(i), start_ms=i * STEP_MS, end_ms=i * STEP_MS + LENGTH_MS, text=texts[i],
                w=(2 * i, 2 * i + 2)) for i in range(n)]


def translation_cues(source: Sequence[Cue]) -> list[Cue]:
    texts = ENGLISH if len(source) == len(ENGLISH) else [f"Line {i}" for i in range(len(source))]
    return [Cue(id=tid(i), start_ms=c.start_ms, end_ms=c.end_ms, text=texts[i], src=(c.id,),
                src_sha=src_sha([c.text])) for i, c in enumerate(source)]


def transcript_for(source: Sequence[Cue], *, audio_track: int, quick: str) -> dict:
    """Two words per cue, so cue i's words are 2i and 2i+1 (its `w`)."""
    segments = []
    for c in source:
        mid = (c.start_ms + c.end_ms) // 2
        half = len(c.text) // 2 or 1
        words = (Word(text=c.text[:half], start_ms=c.start_ms, end_ms=mid),
                 Word(text=c.text[half:] or "。", start_ms=mid, end_ms=c.end_ms))
        segments.append(Segment(text=c.text, start_ms=c.start_ms, end_ms=c.end_ms, words=words))
    return transcript_body(
        Transcript(language="ja", segments=tuple(segments)), engine="whisper.cpp",
        model="fake", version="fake@test", created_at=store.now(),
        inputs={"audio_sha256": "0" * 64, "video_quick_sha256": quick,
                "audio_track": audio_track, "timeline_offset_ms": 0},
        meta={})


def header_of(video: Path) -> Header:
    with tempfile.TemporaryDirectory() as scratch:
        duration = probe(video, Tools.find(), scratch=Path(scratch)).duration_ms
    return store.header_for(video, identify(video), duration)


def track_body(cues: Sequence[Cue], track: str, *, role: str, engine: str = "vid2sub",
               model: str | None = None) -> dict:
    lang = "ja" if track == "ja" else track.split("-")[0]
    return cues_body(cues, language=lang, script=None, engine=engine, model=model,
                     version="test", created_at=store.now(), inputs={}, meta={"role": role})


def write_track(video: Path, track: str, cues: Sequence[Cue], *, role: str,
                parents: Sequence[str] = (), by: str = "auto",
                replaces: str | None = None) -> RenditionRecord:
    """Appends a rendition of `track`, and a head for it that replaces `replaces`, to the
    episode's existing sidecar, as another writer (a CLI run, another tab) would."""
    engine, model = ("vid2sub", None) if role == "source" else ("translate:gemma", "gemma")
    rec = make_rendition(list(parents), track, track_body(cues, track, role=role, engine=engine,
                                                          model=model))
    header = store.load(video)[0].header
    store.append(video, header, [rec, HeadRecord(track=track, rendition=rec.id,
                                                 replaces=replaces, by=by, at=store.now())])
    return rec


def make_episode(folder: Path, name: str = "Show - S01E01.mkv", *, n: int = len(LINES),
                 targets: Sequence[str] = ("en",), audio_langs: Sequence[str] = ("jpn",),
                 audio_codec: str = "aac", audio_track: int = 0,
                 project: Sequence[str] = ("ja", "en")) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    video = make_clip(folder, name, seconds=2.0, audio_langs=tuple(audio_langs),
                      audio_codec=audio_codec)
    header = header_of(video)
    source = source_cues(n)
    transcript = make_rendition([], None, transcript_for(
        source, audio_track=audio_track, quick=header.video.quick_sha256))
    src = make_rendition([transcript.id], "ja", track_body(source, "ja", role="source"))
    records: list = [transcript, src,
                     HeadRecord(track="ja", rendition=src.id, by="auto", at=store.now())]
    for target in targets:
        rec = make_rendition([src.id], target, track_body(
            translation_cues(source), target, role="translation", engine="translate:gemma",
            model="gemma"))
        records += [rec, HeadRecord(track=target, rendition=rec.id, by="auto", at=store.now())]
    side: Sidecar = store.append(video, header, records)
    for track in project:
        side, _, _ = store.project(video, header, side, track, "srt", overwrite_foreign=False)
    return video
