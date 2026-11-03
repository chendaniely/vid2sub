"""The editor's backend: opening, editing, retranslating and saving an episode (spec §19.1, §20).

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

Save (spec §14.5, §14.6) first records any outside edit to a subtitle file as M1 does, so an
edit made in another program since the open is a version too, never something a later open puts
over the editor's. Then it appends one `editor` version per changed track, whose parent is the
head the editor's cues came from, and a head that replaces that same head: never the head on disk
now, so a CLI run, another tab or that outside edit leaves two heads, a conflict both versions
survive, rather than one silently replacing the other (Review Focus 2 and 4). A track whose head
on disk already holds exactly these cues (the same Save sent twice) gets nothing. The records go
in one `store.append`, compare-and-swap with a union merge, so no other writer's records are
lost. Only then are the files written, through `store.project` with `overwrite_foreign` off:
someone else's file is left alone and reported (§6.6, §15.3), and a track in conflict isn't
written until a person picks a version with `resolve`, the only thing that moves a head on a
conflicted track. Once the versions are in the sidecar nothing raises: a file that can't be
written is a note, and the episode moves to the new heads either way. Saves and picks hold the
sidecar's write lock (`store.write_lock`, keyed by the folder's device and inode and the name, NFC and casefolded), which every other append and
projection in this engine takes too, so two picks at once can't replace each other in a cycle and
a job's write never lands inside a Save (Decision 30).
Glossary terms are written at Save (the plan's Decision 5), appended to the file beside the video
so its comments survive, and the file is read back: a term just added makes every translation
made without it stale (§13.4), as M1 decides it too, and that is intended. A Save, like a pick,
starts the undo history again, because the tracks are read back from the sidecar. While a
translation is in conflict, no source cue can be split, merged, deleted or retimed: the unloaded
version's cues would keep pointing at ids that are gone or at old times. A pick first records
outside edits as a version, and supersedes only the versions the person was shown: one that
arrived since keeps the track in conflict, so the person picks again.

Retranslate (spec §13.4, §20) redoes the stale and untranslated cues, or the cues a person names,
as one undoable edit. The model is the one named, else the one M1's catalog route picks; a cloud
model only when this call allows it (§7.2), checked before anything is sent, and a route whose
model's server is down is never passed over for the next one or the cloud (§17.4). Retranslating
stale never replaces a translation a person edited (§13.4); naming a cue does, since that is the
person asking. Translations are replaced in whole groups: every source cue a replaced translation
covers is translated with it, and a translation whose time overlaps the cues being translated is
replaced too (a cue inserted inside a translation that spans two cues), so the track never
overlaps; where that would replace an edited translation, those cues are left as they are.
"""

from __future__ import annotations

import codecs
import os
import secrets
import tempfile
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Literal

from vid2sub import __version__, store
from vid2sub import detect as detecting
from vid2sub.cache import Cache
from vid2sub.catalog import suggest
from vid2sub.config import Config
from vid2sub.engines.base import EngineError
from vid2sub.engines.clients import KeyRing, RunPolicy, check_allowed
from vid2sub.media.identity import identify
from vid2sub.media.probe import Probe, ProbeError, pick_track, probe
from vid2sub.media.tools import ToolFailed, ToolMissing, Tools
from vid2sub.pipeline import MEDIA_SUFFIXES, video_change
from vid2sub.security import InputRefused, WriteRefused, resolve_input, safe_write
from vid2sub.subs import edit, naming
from vid2sub.subs.edit import SOURCE, EditError, Tracks
from vid2sub.subs.glossary import (
    EMPTY_GLOSSARY,
    Glossary,
    GlossaryError,
    add_terms,
    parse_glossary,
)
from vid2sub.subs.model import Cue, TrackError, Word, check_track
from vid2sub.subs.rendition import cues_body, cues_from_body, transcript_from_body
from vid2sub.subs.sidecar import (
    Conflict,
    Header,
    HeadRecord,
    RenditionRecord,
    Sidecar,
    SidecarError,
    make_rendition,
)
from vid2sub.subs.translate_shape import stale_ids, untranslated
from vid2sub.translate.run import make_ask, translate_cues
from vid2sub.web import ops

UNPLAYABLE_AUDIO = frozenset({"ac3", "eac3", "dts", "truehd"})  # ffprobe's codec names (§8.2)
NO_SUBTITLES = "no subtitles yet: make them with vid2sub run or the Jobs page first"
UNDO_STEPS = 200
FORMATS = ("srt", "ass")
GONE = "the sidecar next to the video is gone, so nothing was saved: open the episode again"


class OpenError(Exception):
    """An episode that can't be opened; the reason is fit to show."""


class SaveError(Exception):
    """Nothing was saved; the reason is fit to show."""


@dataclass(frozen=True)
class SaveResult:
    written: tuple[str, ...]  # file names written
    foreign: tuple[str, ...]  # file names left alone: someone else's, or changed outside since
    conflicts: tuple[str, ...]  # tracks in conflict, so not written until a version is picked
    notes: tuple[str, ...]


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
            tracks=tracks, heads=heads, conflicts=conflicts, words=_words(transcript), notes=notes,
            playable_audio=track.codec not in UNPLAYABLE_AUDIO,
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

    def save(self, ep: Episode, *, formats: Sequence[Literal["srt", "ass"]]
             ) -> tuple[Episode, SaveResult]:
        """SRT is always written, ASS when asked for (spec §15.2). SaveError means nothing was
        saved; once the versions are in the sidecar, every later problem is a note."""
        self._check_open(ep)
        fmts = _formats(formats)
        notes: list[str] = []
        with store.write_lock(ep.video):
            try:
                side, changed = store.check_external(ep.video, ep.header, _reload(ep.video),
                                                     on_unreadable=_unreadable(notes))
                notes += [f"kept your outside edit to {t}" for t in changed]
                records = _versions(ep, side)
                if records:
                    side = store.append(ep.video, ep.header, records)
            except (SidecarError, store.StoreError, WriteRefused) as err:
                raise SaveError(str(err)) from None
            except OSError as err:  # never err.filename: a full path
                raise SaveError(_failed("couldn't save next to the video", err)) from None
            side, written, foreign, conflicts, more = _project(ep.video, ep.header, side,
                                                               side.tracks(), fmts)
            notes += more
            adds, glossary_notes = _write_glossary(ep.video, ep.glossary_adds)
            try:  # read back, so a term just added makes translations stale (§13.4), as at open
                glossary: Glossary | None = read_glossary(ep.video)
            except (GlossaryError, OSError):
                glossary = None
        source_key, tracks, heads, in_conflict = load_tracks(side)
        saved = replace(ep, sidecar=side, source_key=source_key, tracks=tracks, base=tracks,
                        heads=heads, conflicts=in_conflict, undo=[], redo=[],
                        taken=ep.taken | cue_ids(side), glossary_adds=adds, glossary=glossary)
        return saved, SaveResult(tuple(written), tuple(foreign), tuple(conflicts),
                                 tuple(notes + glossary_notes))

    def resolve(self, ep: Episode, track: str, rendition: str) -> tuple[Episode, SaveResult]:
        """A person's pick of one of a conflicted track's versions (spec §14.4): it replaces
        every version it was shown, by "user", and the track is loaded and written; a version
        that arrived since (an outside edit, another Save) stays, and the track stays in
        conflict. Unsaved edits on other tracks are kept."""
        self._check_open(ep)
        if track not in naming.TRACKS:  # it comes from the browser: never echoed unchecked
            raise SaveError("there's no such track")
        if track not in ep.conflicts:  # a stale request must never reload a track being edited
            raise SaveError(f"the {track} track has only one version: there's nothing to pick")
        shown = ep.conflicts[track]
        if rendition not in shown:  # only a version the person was shown can be picked
            raise SaveError(f"that isn't one of the {track} track's versions")
        notes: list[str] = []
        with store.write_lock(ep.video):
            try:
                side, changed = store.check_external(ep.video, ep.header, _reload(ep.video),
                                                     on_unreadable=_unreadable(notes))
                notes += [f"kept your outside edit to {t}" for t in changed]
                head = side.head(track)
                if isinstance(head, Conflict):
                    if rendition in head.leaves:  # supersede only what the person was shown
                        now = store.now()
                        records = [HeadRecord(track=track, rendition=rendition, replaces=other,
                                              by="user", at=now)
                                   for other in shown if other != rendition and other in head.leaves]
                        if records:
                            side = store.append(ep.video, ep.header, records)
                    if isinstance(side.head(track), Conflict):  # a version the person never saw
                        notes.append(f"another version of the {track} track arrived: pick again")
                        return (_with_track(ep, side, track),
                                SaveResult((), (), (track,), tuple(notes)))
                else:
                    notes.append(f"the {track} track's version was already picked elsewhere: "
                                 "showing it")
            except (SidecarError, store.StoreError, WriteRefused) as err:
                raise SaveError(str(err)) from None
            except OSError as err:
                raise SaveError(_failed("couldn't save next to the video", err)) from None
            has_ass = any(p.track == track and p.format == "ass"
                          for p in side.projections().values())
            side, written, foreign, conflicts, more = _project(
                ep.video, ep.header, side, [track], ["srt", "ass"] if has_ass else ["srt"])
        return _with_track(ep, side, track), SaveResult(tuple(written), tuple(foreign),
                                                        tuple(conflicts), tuple(notes + more))

    def retranslate(self, ep: Episode, track: str, *, ids: Sequence[str] | None,
                    model: str | None = None, allow_cloud: bool = False,
                    on_batch: Callable[[int, int], None] | None = None) -> Episode:
        """`ids=None`: every stale or untranslated source cue, never replacing an edited
        translation; else those source cues, whatever their translation. One undo step; `ep`
        itself when there's nothing to translate. Blocks on the model's server. Raises EditError
        (a track in conflict, an unknown track or cue), EngineError (no usable model, a cloud
        model this call doesn't allow, the server down or refusing: `.hint` names the fix),
        TranslationFailed, or GlossaryError (a glossary beside the video vid2sub can't read);
        nothing changes then."""
        self._check_open(ep)
        if track not in naming.TRACKS:  # it comes from the browser: never echoed unchecked
            raise EditError("there's no such track")
        _editable(ep, track)
        if track not in ep.tracks.translations:
            raise EditError(f"there is no {track} track")
        source, cues = ep.tracks.source, ep.tracks.translations[track]
        wanted, replaced = retranslation(source, cues, ids)
        if not wanted:
            return ep
        lang = _lang(ep.source_key)
        name = self._translator(lang, model, allow_cloud)
        entry = self.config.models[name]
        policy = RunPolicy(allow_cloud)
        check_allowed(name, entry, self.config, policy)
        ask = make_ask(name, entry, self.config, policy, self.keys)
        taken = set(ep.taken)
        new = translate_cues(source, source_lang=lang, target_track=track,
                             glossary=glossary_with(read_glossary(ep.video), ep.glossary_adds),
                             ask=ask, only=wanted, taken=taken, on_batch=on_batch)
        result = tuple(sorted([c for c in cues if c.id not in replaced] + new,
                              key=lambda c: (c.start_ms, c.end_ms)))
        try:
            check_track(result)
        except TrackError as err:
            raise EditError(f"the {track} track would break: {err}") from None
        tracks = Tracks(source, {**ep.tracks.translations, track: result})
        return replace(ep, tracks=tracks, taken=taken, redo=[],
                       undo=[*ep.undo, (ep.tracks, ep.glossary_adds)][-UNDO_STEPS:])

    def _translator(self, lang: str, model: str | None, allow_cloud: bool) -> str:
        """The named model, else the catalog route's pick, as M1's pipeline picks (§11.2). A route
        whose model's server isn't answering stops here rather than taking the next model."""
        if model is not None:
            entry = self.config.models.get(model)
            if entry is None or entry.task != "translate":
                raise EngineError("unavailable", "that isn't a translation model in vid2sub.toml",
                                  hint="`vid2sub models` lists them")
            return model
        cands = detecting.candidates(self.config, self.keys)

        def pick(c: list) -> str | None:
            return suggest(lang, c, "translate", allow_cloud=allow_cloud).model

        hoped = pick([replace(c, available=True, reason="") if c.unreachable else c
                      for c in cands])
        if any(c.name == hoped and c.unreachable for c in cands):
            raise EngineError("connection", "the translation model's server isn't reachable",
                              hint="is it running? For the Spark: is `make tunnel` running?")
        s = suggest(lang, cands, "translate", allow_cloud=allow_cloud)
        if s.model is None:
            raise EngineError("unavailable", "no usable translation model",
                              hint="; ".join(f"{n}: {r}" for n, r in s.considered)
                              or "add one to vid2sub.toml (`vid2sub config init`)")
        return s.model

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


def retranslation(source: Sequence[Cue], cues: Sequence[Cue], ids: Sequence[str] | None
                  ) -> tuple[list[str], set[str]]:
    """The source cue ids to translate, in order, and the translation cue ids they replace.

    Whole groups, so the new cues never overlap the kept ones: a replaced translation brings
    every source cue it covers, and a translation that covers a cue being translated, or whose
    time overlaps a run of them, is replaced too. With `ids=None` an edited translation is never
    replaced; the cues it would have brought in are left out instead."""
    order = {c.id: k for k, c in enumerate(source)}
    by_id = {c.id: c for c in source}
    if ids is None:
        stale = stale_ids(cues, by_id)
        wanted = {i for c in cues if c.id in stale and "edited" not in c.flags
                  for i in c.src or () if i in by_id}
        wanted |= set(untranslated(list(order), cues))
    else:
        if any(i not in by_id for i in ids):
            raise EditError("one of those cues isn't in the source track")
        wanted = set(ids)
    blocked: set[str] = set()
    while True:
        chosen = sorted(wanted - blocked, key=order.__getitem__)
        runs = _runs(chosen, order, by_id)
        replaced: set[str] = set()
        grow: set[str] = set()
        block: set[str] = set()
        for c in cues:
            covers = {i for i in c.src or () if i in by_id}
            hits = [ids_ for start, end, ids_ in runs
                    if covers & ids_ or (c.start_ms < end and start < c.end_ms)]
            if not hits:
                continue
            if (ids is not None or "edited" not in c.flags) and not covers & blocked:
                replaced.add(c.id)
                grow |= covers
            else:
                block |= covers.union(*hits)
        if block - blocked:
            blocked |= block
        elif grow - wanted:
            wanted |= grow
        else:
            return chosen, replaced


def _runs(chosen: Sequence[str], order: dict[str, int], by_id: dict[str, Cue]
          ) -> list[tuple[int, int, set[str]]]:
    """Each run of adjacent source cues: its start, its end and its ids."""
    runs: list[tuple[int, int, set[str]]] = []
    last = -2
    for cid in chosen:
        c = by_id[cid]
        if order[cid] == last + 1:
            start, _, members = runs[-1]
            runs[-1] = (start, c.end_ms, members | {cid})
        else:
            runs.append((c.start_ms, c.end_ms, {cid}))
        last = order[cid]
    return runs


def _formats(formats: Sequence[str]) -> list[str]:
    if any(f not in FORMATS for f in formats):
        raise ValueError("the formats are srt and ass")
    return ["srt"] + (["ass"] if "ass" in formats else [])


def _reload(video: Path) -> Sidecar:
    side, _ = store.load(video)
    if side is None:
        raise SaveError(GONE)
    return side


def _failed(what: str, err: OSError) -> str:
    return what + (f" ({err.strerror})" if err.strerror else "")


def _cues(t: Tracks, track: str, source_key: str) -> tuple[Cue, ...] | None:
    return t.source if track == source_key else t.translations.get(track)


def _versions(ep: Episode, side: Sidecar) -> list:
    """An editor version and a head for each track whose cues differ from its head's; the head
    replaces the one the cues came from, never the head on disk now (spec §14.4). A track whose
    head on disk, or one of whose diverged versions, already holds these cues gets nothing."""
    renditions = side.renditions()
    now = store.now()
    records: list = []
    source_rid = ep.heads.get(ep.source_key)
    for track in [ep.source_key, *ep.tracks.translations]:
        cues = _cues(ep.tracks, track, ep.source_key)
        if track not in ep.heads or cues is None or cues == _cues(ep.base, track, ep.source_key):
            continue
        is_source = track == ep.source_key
        same = _holding(side, track, cues)
        if same is not None:
            if is_source:
                source_rid = same
            continue
        parent = ep.heads[track]
        if parent not in renditions:  # the sidecar was replaced; nothing here can build on it
            raise SaveError("the subtitles' history was replaced since this episode was opened: "
                            "reopen it")
        body = _editor_body(renditions[parent].body, cues, is_source=is_source, created_at=now,
                            inputs={} if is_source or not source_rid else {"source": source_rid})
        rec = make_rendition([parent], track, body)
        if is_source:
            source_rid = rec.id
        records += [rec, HeadRecord(track=track, rendition=rec.id, replaces=parent, by="editor",
                                    at=now)]
    return records


def _holding(side: Sidecar, track: str, cues: tuple[Cue, ...]) -> str | None:
    """The rendition at the track's head on disk (or among its diverged versions) whose cues are
    exactly `cues`, if there is one."""
    head = side.head(track)
    current = (head.leaves if isinstance(head, Conflict)
               else (head.rendition,) if isinstance(head, HeadRecord) else ())
    renditions = side.renditions()
    for rid in current:
        if rid in renditions and tuple(cues_from_body(renditions[rid].body)) == cues:
            return rid
    return None


def _unreadable(notes: list[str]) -> Callable[[str], None]:
    def note(name: str) -> None:
        notes.append(f"left {name} alone: it isn't a readable subtitle file")
    return note


def _words(transcript: RenditionRecord | None) -> tuple[Word, ...]:
    return tuple(transcript_from_body(transcript.body).words()) if transcript else ()


def _editor_body(head: dict, cues: Sequence[Cue], *, is_source: bool, created_at: str,
                 inputs: dict[str, str]) -> dict:
    """The head's language, script and glossary hash; its model too, since the cues the person
    didn't touch are still that model's, and M1 reads a changed model as every cue stale."""
    payload = head.get("payload", {})
    return cues_body(cues, language=payload["language"], script=payload.get("script"),
                     engine="editor", model=head.get("model"), version=f"editor@{__version__}",
                     created_at=created_at, inputs=inputs,
                     meta={"role": "source" if is_source else "translation"},
                     glossary_sha=payload.get("glossary_sha"))


def _project(video: Path, header: Header, side: Sidecar, tracks: Sequence[str],
             fmts: Sequence[str]) -> tuple[Sidecar, list[str], list[str], list[str], list[str]]:
    """Writes each track's files; never raises, since the versions are already saved."""
    written: list[str] = []
    foreign: list[str] = []
    conflicts: list[str] = []
    notes: list[str] = []
    for track in tracks:
        head = side.head(track)
        if isinstance(head, Conflict):
            conflicts.append(track)
            continue
        if not isinstance(head, HeadRecord):
            continue
        for fmt in fmts:
            try:
                name = store.subtitle_path(video, track, fmt).name
            except naming.UnknownTrack:
                notes.append(f"couldn't write the {track} track: vid2sub has no file name for it")
                break
            try:
                side, _, did = store.project(video, header, side, track, fmt,
                                             overwrite_foreign=False)
            except store.ForeignFile:  # someone else's file, or edited outside since
                foreign.append(name)
                continue
            except WriteRefused as err:  # a link, or a file held open: not someone else's
                notes.append(f"couldn't write {name}: {err}")
                continue
            except (SidecarError, store.StoreError) as err:
                notes.append(f"couldn't write {name}: {err}")
                continue
            except OSError as err:
                notes.append(_failed(f"couldn't write {name}", err))
                continue
            except Exception as err:  # noqa: BLE001 - the versions are saved; this is one file
                notes.append(f"couldn't write {name} ({type(err).__name__})")
                continue
            if did:
                written.append(name)
    return side, written, foreign, conflicts, notes


def _with_track(ep: Episode, side: Sidecar, track: str) -> Episode:
    """The episode with one track read again from the sidecar; the others as they were."""
    heads, conflicts = dict(ep.heads), dict(ep.conflicts)
    tracks, base, words = ep.tracks, ep.base, ep.words
    head = side.head(track)
    if isinstance(head, HeadRecord):
        cues = tuple(cues_from_body(side.renditions()[head.rendition].body))
        heads[track] = head.rendition
        conflicts.pop(track, None)
        tracks, base = (_put(t, track, cues, ep.source_key) for t in (tracks, base))
        if track == ep.source_key:
            words = _words(_transcript(side, head.rendition))
    elif isinstance(head, Conflict):
        conflicts[track] = head.leaves
        heads.pop(track, None)
    return replace(ep, sidecar=side, heads=heads, conflicts=conflicts, tracks=tracks, base=base,
                   words=words, undo=[], redo=[], taken=ep.taken | cue_ids(side))


def _put(t: Tracks, track: str, cues: tuple[Cue, ...], source_key: str) -> Tracks:
    if track == source_key:
        return Tracks(cues, t.translations)
    return Tracks(t.source, {**t.translations, track: cues})


def _write_glossary(video: Path, adds: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    """Appends the terms to the glossary beside the video, compare-and-swap like the sidecar;
    returns the terms still waiting (all of them if it couldn't) and the notes."""
    if not adds:
        return {}, []
    path = video.with_name(naming.GLOSSARY_NAME)
    name = path.name
    if path.is_symlink():  # never read or write through a link planted in the folder (§6.6)
        return dict(adds), [f"couldn't add to {name}: it isn't a regular file"]
    try:
        for _ in range(3):
            existed = path.is_file()
            data = path.read_bytes() if existed else b""
            text = data.decode("utf-8-sig")
            out, kept = add_terms(text, adds)
            if out == text:
                break
            latest = path.read_bytes() if path.is_file() else b""
            if latest != data:
                continue
            bom = codecs.BOM_UTF8 if data.startswith(codecs.BOM_UTF8) else b""
            safe_write(path, bom + out.encode("utf-8"), overwrite=existed)
            break
        else:
            return dict(adds), [f"couldn't add to {name}: it kept changing; save again"]
    except UnicodeDecodeError:
        return dict(adds), [f"couldn't add to {name}: it isn't UTF-8"]
    except (GlossaryError, WriteRefused) as err:
        return dict(adds), [f"couldn't add to {name}: {err}"]
    except OSError as err:
        return dict(adds), [_failed(f"couldn't add to {name}", err)]
    had = dict(parse_glossary(text).terms) if text.strip() else {}
    new = sum(1 for term in adds if term not in had)
    notes = [f"added {new} term{'' if new == 1 else 's'} to {name}"] if new else []
    notes += [f"{name} already has {term} with another translation: kept that one"
              for term in kept]
    return {}, notes


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
            _editable(ep, ep.source_key, *ep.conflicts)
            return (edit.set_times(t, op.cue, start_ms=op.start_ms, end_ms=op.end_ms),
                    ep.glossary_adds)
        case ops.Nudge():
            _editable(ep, ep.source_key, *ep.conflicts)
            return edit.nudge(t, op.cue, op.delta_ms, edge=op.edge), ep.glossary_adds
        case ops.Split():
            _editable(ep, ep.source_key, *ep.conflicts)
            return (edit.split(t, op.cue, at_char=op.at_char, at_ms=op.at_ms,
                               ids=(op.ids[0], op.ids[1]), taken=taken)[0], ep.glossary_adds)
        case ops.MergeNext():
            _editable(ep, ep.source_key, *ep.conflicts)
            return (edit.merge_next(t, op.cue, new_id=op.id, joined_ids=op.joined,
                                    taken=taken)[0], ep.glossary_adds)
        case ops.Insert():
            _editable(ep, ep.source_key)
            return (edit.insert(t, start_ms=op.start_ms, end_ms=op.end_ms, text=op.text,
                                new_id=op.id, taken=taken)[0], ep.glossary_adds)
        case ops.Delete():
            _editable(ep, ep.source_key, *ep.conflicts)
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
