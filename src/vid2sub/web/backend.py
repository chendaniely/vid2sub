"""The editor's backend: opening an episode M1 made, and editing it (spec §19.1, §20, §15.3).

The web app's server calls this, never the store directly, so the CLI and the editor share one
core (spec §18.3); `capabilities()` tells the frontend which controls exist (`BrowserBackend`, in
Pages, is Phase 4's). Phase 2's editor opens only episodes that already have a sidecar: making
subtitles is `vid2sub run` or the Jobs page. Opening folds in edits made outside vid2sub, as
every M1 command does (§15.3, S31), and says so in notes that name files only by their bare name
(§6.8). A track whose heads diverged is in conflict (§14.4): it isn't loaded, and its versions
are listed for the person to pick; when that is the source, every edit waits for the pick, since
translations hang off source cues. The spoken words come from the transcript the source was
built from, following rendition parents, so word highlighting matches the cues' `w` ranges. Audio
in AC-3, E-AC-3, DTS or TrueHD can't be played by a browser (§8.2), so the editor then plays the
playback audio instead (the Phase 2 plan's Decision 2). An `Episode` is never changed in place:
every call returns a new one, so a reactive value that holds it sees each change. A translation
is stale, as spec §13.4 says and M1 decides (pipeline._translate_targets), when its source text
changed, and every cue of it is when the glossary's hash or the translation model differs from
the ones its head was made with; so the episode holds the glossary beside the video and the model
Retranslate would use with none named, picked offline from the catalog route as M1 picks it but
taking every configured local server to answer (no request is made at open). Edits run
through the pure `subs.edit` rules, so they exist once (§20); each one that changes something
pushes the tracks and the pending glossary adds onto the undo stack (the last 200 steps) and
clears redo. A track in conflict can't be edited, and nothing but a glossary add can while the
source is, until a person picks a version.
"""

from __future__ import annotations

import os
import secrets
import tempfile
import threading
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Literal

from vid2sub import detect as detecting
from vid2sub import store
from vid2sub.cache import Cache
from vid2sub.catalog import suggest
from vid2sub.config import Config
from vid2sub.engines.clients import KeyRing
from vid2sub.media.identity import identify
from vid2sub.media.probe import Probe, ProbeError, pick_track, probe
from vid2sub.media.tools import ToolFailed, ToolMissing, Tools
from vid2sub.pipeline import MEDIA_SUFFIXES, video_change
from vid2sub.security import InputRefused, WriteRefused, resolve_input
from vid2sub.subs import edit, naming
from vid2sub.subs.edit import SOURCE, EditError, Tracks
from vid2sub.subs.glossary import EMPTY_GLOSSARY, Glossary, GlossaryError, parse_glossary
from vid2sub.subs.model import Word
from vid2sub.subs.rendition import cues_from_body, transcript_from_body
from vid2sub.subs.sidecar import (
    Conflict,
    Header,
    HeadRecord,
    RenditionRecord,
    Sidecar,
    SidecarError,
)
from vid2sub.web import ops

UNPLAYABLE_AUDIO = frozenset({"ac3", "eac3", "dts", "truehd"})  # ffprobe's codec names (§8.2)
NO_SUBTITLES = "no subtitles yet: make them with vid2sub run or the Jobs page first"
UNDO_STEPS = 200


class OpenError(Exception):
    """An episode that can't be opened; the reason is fit to show."""


@dataclass(frozen=True)
class Capabilities:
    engine: Literal["local", "browser"]
    generate: bool
    save: Literal["disk", "download"]
    path_input: bool


@dataclass(frozen=True)
class Episode:
    id: str
    video: Path
    header: Header  # the video as it is now, from the probe at open
    source_key: str
    tracks: Tracks
    heads: dict[str, str]  # track → the head rendition its cues came from
    conflicts: dict[str, tuple[str, ...]]  # track → its diverged versions (rendition ids)
    words: tuple[Word, ...]
    notes: list[str]
    playable_audio: bool
    audio_index: int  # among audio tracks: ffmpeg's a:N, as preview.playback_audio takes
    sidecar: Sidecar  # as of the open or the last Save
    base: Tracks  # the tracks as of the open or the last Save
    glossary: Glossary | None  # beside the video at open; None if it couldn't be read
    translate_model: str | None  # the model Retranslate would use with none named (offline)
    undo: list[tuple[Tracks, dict[str, str]]] = field(default_factory=list)
    redo: list[tuple[Tracks, dict[str, str]]] = field(default_factory=list)
    taken: set[str] = field(default_factory=set)
    glossary_adds: dict[str, str] = field(default_factory=dict)

    @property
    def dirty(self) -> bool:
        return self.tracks != self.base or bool(self.glossary_adds)


class LocalBackend:
    def __init__(self, config: Config, tools: Tools, keys: KeyRing, cache: Cache):
        self.config = config
        self.tools = tools
        self.keys = keys
        self.cache = cache
        self._open: dict[str, Path] = {}
        self._lock = threading.Lock()

    def capabilities(self) -> Capabilities:
        return Capabilities(engine="local", generate=True, save="disk", path_input=True)

    def open(self, path: str) -> Episode:
        """Probes the video and reads its sidecar, recording outside edits first (§15.3)."""
        video = _video(path)
        try:
            side, warnings = store.load(video)
        except SidecarError as err:
            raise OpenError(str(err)) from None
        except OSError as err:
            raise _files_error(err) from None
        if side is None:
            raise OpenError(NO_SUBTITLES)
        p = self._probe(video)
        try:
            header = store.header_for(video, identify(video), p.duration_ms)
        except OSError as err:
            raise _files_error(err) from None
        notes = list(warnings)
        change = video_change(side.header.video, header.video)
        if change:
            notes.append(f"this video changed since its subtitles were made ({change}); its "
                         "transcript may no longer line up")

        def unreadable(name: str) -> None:
            notes.append(f"left {name} alone: it isn't a readable subtitle file")

        try:
            side, changed = store.check_external(video, header, side, on_unreadable=unreadable)
        except (SidecarError, store.StoreError, WriteRefused) as err:
            raise OpenError(str(err)) from None
        except OSError as err:
            raise _files_error(err) from None
        notes += [f"kept your outside edit to {t}" for t in changed]
        source_key, tracks, heads, conflicts = load_tracks(side)
        transcript = _transcript(side, heads.get(source_key))
        track = _audio_track(p, transcript, naming.TRACKS.get(source_key))
        try:
            glossary: Glossary | None = read_glossary(video)
        except GlossaryError as err:
            glossary = None
            notes.append(f"couldn't read {naming.GLOSSARY_NAME}: {err}")
        except OSError as err:  # never err.filename: a full path
            glossary = None
            notes.append(f"couldn't read {naming.GLOSSARY_NAME}"
                         + (f" ({err.strerror})" if err.strerror else ""))
        ep = Episode(
            id="e" + secrets.token_hex(8), video=video, header=header, source_key=source_key,
            tracks=tracks, heads=heads, conflicts=conflicts,
            words=tuple(transcript_from_body(transcript.body).words()) if transcript else (),
            notes=notes, playable_audio=track.codec not in UNPLAYABLE_AUDIO,
            audio_index=track.index, sidecar=side, base=tracks, taken=cue_ids(side),
            glossary=glossary, translate_model=self._route_model(_lang(source_key)))
        with self._lock:
            self._open[ep.id] = video
        return ep

    def is_open(self, episode_id: str) -> bool:
        with self._lock:
            return episode_id in self._open

    def close(self, episode_id: str) -> None:
        """Forgets the episode; unsaved edits in it are dropped (the tab keeps a draft, §14.5)."""
        with self._lock:
            self._open.pop(episode_id, None)

    def apply(self, ep: Episode, op: ops.EditOp) -> Episode:
        """One edit; EditError (fit to show) if the rules refuse it. An edit that changes
        nothing returns `ep` itself, with no undo step."""
        self._check_open(ep)
        taken = set(ep.taken)
        tracks, adds = _edit(ep, op, taken)
        if tracks == ep.tracks and adds == ep.glossary_adds:
            return ep
        return replace(ep, tracks=tracks, glossary_adds=adds, taken=taken, redo=[],
                       undo=[*ep.undo, (ep.tracks, ep.glossary_adds)][-UNDO_STEPS:])

    def undo(self, ep: Episode) -> Episode:
        self._check_open(ep)
        if not ep.undo:
            return ep
        tracks, adds = ep.undo[-1]
        return replace(ep, tracks=tracks, glossary_adds=adds, undo=ep.undo[:-1],
                       redo=[*ep.redo, (ep.tracks, ep.glossary_adds)])

    def redo(self, ep: Episode) -> Episode:
        self._check_open(ep)
        if not ep.redo:
            return ep
        tracks, adds = ep.redo[-1]
        return replace(ep, tracks=tracks, glossary_adds=adds, redo=ep.redo[:-1],
                       undo=[*ep.undo, (ep.tracks, ep.glossary_adds)][-UNDO_STEPS:])

    def _check_open(self, ep: Episode) -> None:
        if not self.is_open(ep.id):
            raise OpenError("this episode was closed: open it again")

    def _route_model(self, lang: str) -> str | None:
        """The model Retranslate would use with none named and no cloud: M1's catalog route over
        the configured models, each local server taken to answer (`probe_endpoints=False`)."""
        cands = detecting.candidates(self.config, self.keys, probe_endpoints=False)
        name = suggest(lang, cands, "translate", allow_cloud=False).model
        return self.config.models[name].model if name else None

    def _probe(self, video: Path) -> Probe:
        try:
            with tempfile.TemporaryDirectory(prefix="vid2sub-") as scratch:
                return probe(video, self.tools, scratch=Path(scratch))
        except (ProbeError, ToolMissing) as err:
            raise OpenError(str(err)) from None
        except ToolFailed:
            raise OpenError("ffprobe couldn't read this file: check that it plays in a media "
                            "player") from None


def _files_error(err: OSError) -> OpenError:
    """The files next to the video couldn't be read or written; never err.filename: a full path."""
    return OpenError("couldn't read or write the files next to the video"
                     + (f" ({err.strerror})" if err.strerror else ""))


def _edit(ep: Episode, op: ops.EditOp, taken: set[str]) -> tuple[Tracks, dict[str, str]]:
    """The tracks and glossary adds after `op`; new cue ids are added to `taken`."""
    if isinstance(op, ops.GlossaryAdd):
        return ep.tracks, {**ep.glossary_adds, op.term.strip(): op.translation.strip()}
    t = ep.tracks
    match op:
        case ops.SetText():
            _editable(ep, ep.source_key)
            return edit.set_text(t, op.cue, op.text), ep.glossary_adds
        case ops.SetTranslationText():
            _editable(ep, op.track)
            return edit.set_translation_text(t, op.track, op.cue, op.text), ep.glossary_adds
        case ops.SetTimes():
            _editable(ep, ep.source_key)
            return (edit.set_times(t, op.cue, start_ms=op.start_ms, end_ms=op.end_ms),
                    ep.glossary_adds)
        case ops.Nudge():
            _editable(ep, ep.source_key)
            return edit.nudge(t, op.cue, op.delta_ms, edge=op.edge), ep.glossary_adds
        case ops.Split():
            _editable(ep, ep.source_key)
            return (edit.split(t, op.cue, at_char=op.at_char, at_ms=op.at_ms,
                               ids=(op.ids[0], op.ids[1]), taken=taken)[0], ep.glossary_adds)
        case ops.MergeNext():
            _editable(ep, ep.source_key)
            return (edit.merge_next(t, op.cue, new_id=op.id, joined_ids=op.joined,
                                    taken=taken)[0], ep.glossary_adds)
        case ops.Insert():
            _editable(ep, ep.source_key)
            return (edit.insert(t, start_ms=op.start_ms, end_ms=op.end_ms, text=op.text,
                                new_id=op.id, taken=taken)[0], ep.glossary_adds)
        case ops.Delete():
            _editable(ep, ep.source_key)
            return edit.delete(t, op.cue), ep.glossary_adds
        case ops.Detach():
            _editable(ep, op.track)
            return edit.detach(t, op.track, op.cue, op.detached), ep.glossary_adds
        case ops.ReplaceAll():
            _editable(ep, *(ep.source_key if name == SOURCE else name for name in op.tracks))
            return edit.replace_all(t, op.find, op.replace, tracks=op.tracks)[0], ep.glossary_adds
    raise EditError("that isn't an edit the editor knows")


def _editable(ep: Episode, *tracks: str) -> None:
    """A track in conflict waits for a person to pick a version (spec §14.4); while the source
    is, so does every track, since translations hang off source cues."""
    for name in (ep.source_key, *tracks):
        if name in ep.conflicts:
            raise EditError(f"the {name} track has two versions: pick one before editing")


def _video(path: str) -> Path:
    """A typed path must be fully qualified (spec §6.5): the server's folder means nothing to
    the person typing."""
    try:
        if not os.path.isabs(os.path.expanduser(path)):
            raise OpenError("give the video's full path")
        video = resolve_input(path)
    except InputRefused as err:
        raise OpenError(str(err)) from None
    if not video.is_file():
        raise OpenError("there's no video at that path")
    try:
        twins = [p for p in video.parent.iterdir() if p != video
                 and p.stem.casefold() == video.stem.casefold()
                 and p.suffix.lower() in MEDIA_SUFFIXES]
    except OSError as err:
        raise _files_error(err) from None
    if twins:
        raise OpenError("another video in this folder has the same name, so their subtitles "
                        "would collide: rename one of them")
    return video


def load_tracks(side: Sidecar) -> tuple[str, Tracks, dict[str, str], dict[str, tuple[str, ...]]]:
    """The source track's key, every track's cues at its head, the heads, and the tracks in
    conflict (not loaded: a person picks a version first, §14.4)."""
    source_key = store.source_track(side) or _forked_source(side)
    if source_key is None:
        raise OpenError(NO_SUBTITLES)
    renditions = side.renditions()
    heads: dict[str, str] = {}
    conflicts: dict[str, tuple[str, ...]] = {}
    loaded: dict[str, tuple] = {}
    for track in side.tracks():
        head = side.head(track)
        if isinstance(head, Conflict):
            conflicts[track] = head.leaves
        elif isinstance(head, HeadRecord):
            heads[track] = head.rendition
            loaded[track] = tuple(cues_from_body(renditions[head.rendition].body))
    source = loaded.pop(source_key, ())
    return source_key, Tracks(source, loaded), heads, conflicts


def cue_ids(side: Sidecar) -> set[str]:
    """Every cue id any version of any track has used: ids are never reused (spec §14.3)."""
    return {c["id"] for r in side.renditions().values() if r.body.get("kind") == "cues"
            for c in r.body["payload"]["cues"]}


def _forked_source(side: Sidecar) -> str | None:
    """A source track in conflict: one of its versions says it is the source."""
    renditions = side.renditions()
    for track in side.tracks():
        head = side.head(track)
        if isinstance(head, Conflict) and any(
                renditions[i].body.get("meta", {}).get("role") == "source"
                for i in head.leaves if i in renditions):
            return track
    return None


def _transcript(side: Sidecar, source_head: str | None) -> RenditionRecord | None:
    """The transcript the source's head was built from, else the newest one."""
    renditions = side.renditions()
    seen: set[str] = set()
    todo = [source_head] if source_head else []
    while todo:
        rid = todo.pop(0)
        if rid in seen or rid not in renditions:
            continue
        seen.add(rid)
        rec = renditions[rid]
        if rec.body.get("kind") == "transcript":
            return rec
        todo += rec.parents
    found = side.transcripts()
    return found[-1] if found else None


def _audio_track(p: Probe, transcript: RenditionRecord | None, info: naming.TrackInfo | None):
    """The track the transcript was made from (its `inputs.audio_track`), else §8.4's pick."""
    if transcript is not None:
        value = str(transcript.body.get("inputs", {}).get("audio_track", ""))
        if value.isdigit() and int(value) < len(p.audio):
            return p.audio[int(value)]
    return pick_track(p, info.lang if info else None)


def read_glossary(video: Path) -> Glossary:
    """The glossary beside the video, read as M1 reads it; EMPTY_GLOSSARY when there's none."""
    path = video.with_name(naming.GLOSSARY_NAME)
    if not path.is_file():
        return EMPTY_GLOSSARY
    try:
        return parse_glossary(path.read_text(encoding="utf-8-sig"))
    except UnicodeDecodeError:
        raise GlossaryError("the glossary isn't UTF-8; save it as UTF-8") from None


def glossary_with(glossary: Glossary, adds: dict[str, str]) -> Glossary:
    """The glossary as it will read once Save has added `adds`: a term it has keeps its own."""
    have = dict(glossary.terms)
    return Glossary(glossary.description, glossary.terms + tuple(
        (term, translation) for term, translation in adds.items() if term not in have))


def track_setup(ep: Episode, track: str) -> tuple[str, str | None]:
    """The glossary hash ("" for none) and the model the track's cues were made with."""
    body = ep.sidecar.renditions()[ep.heads[track]].body
    return body.get("payload", {}).get("glossary_sha") or "", body.get("model")


def setup_changed(setup: tuple[str, str | None], glossary_sha: str | None,
                  model: str | None) -> bool:
    """Spec §13.4's other two legs, as M1 decides them: the glossary's hash, or the model, isn't
    the one the cues were made with. A leg whose current value is unknown (None) is left out, and
    both are when the version has no model: no translator made it (an import, or an editor's or
    an outside version of one), and M1 never retranslates what it didn't make."""
    made_sha, made_model = setup
    if made_model is None:
        return False
    return ((glossary_sha is not None and made_sha != glossary_sha)
            or (model is not None and made_model != model))


def all_stale(ep: Episode, track: str) -> bool:
    """Every cue of a loaded translation track is stale: against the glossary beside the video
    with the terms waiting for Save, and the model Retranslate would use with none named."""
    sha = None if ep.glossary is None else glossary_with(ep.glossary, ep.glossary_adds).sha()
    return setup_changed(track_setup(ep, track), sha, ep.translate_model)


def _lang(track: str) -> str:
    info = naming.TRACKS.get(track)
    return info.lang if info else track.split("-")[0]
