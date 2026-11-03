"""The sidecar and the subtitle files next to a video (spec §14.5, §14.6, §15).

Appends use compare-and-swap: read the sidecar, add records, write them to a temporary file,
re-read the sidecar just before the rename, and start over if another writer got there first;
records are immutable with ids, so the merge is a union and nothing is lost. Within one process
every append and projection holds the sidecar's lock (`write_lock`), so the editor's Save and a
job's write never overlap; between processes only the moment between that re-read and the rename
is unguarded (spec §14.6, §18.3; the Phase 2 plan's Decision 30, Dan's answer to the kickoff
council). A sidecar vid2sub can't read is never overwritten. A subtitle file is
vid2sub's only if the sidecar has a projection record for it; anyone else's (Bazarr, a fansub) is
never overwritten without `overwrite_foreign`. The projection record is written before the file.
A projected file that changed on disk is parsed and compared at its format's precision (an ASS
file's `Default` events only): real changes come back as an `external` version (ids recovered by
time and text), and a change that was only bytes or styling just updates the record, after which
the file counts as the current version's projection and isn't rewritten, so a restyle survives
(final review). An automatic version never replaces a head a person set (spec §14.4). A file of
ours edited since vid2sub wrote it is never overwritten until the edit has been recorded as a
version (controller ruling, Task 28). That version replaces the one its file was written from, not
whatever head is current, so an edit to a file the head has moved on from diverges from the head,
a conflict the person resolves (spec §14.4); and a write that fails puts back the file's previous
projection record, so the file still counts as the version it holds. The external version keeps
the glossary hash and model of the version its file was written from, since a text edit changes
neither (§13.4), and every line the person changed or added is `edited`, so it is never replaced
automatically (Phase 2, Task 6).
"""

from __future__ import annotations

import os
import threading
import unicodedata
import weakref
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path

from vid2sub.media.identity import VideoIdentity
from vid2sub.security import WriteRefused, safe_write
from vid2sub.subs import naming
from vid2sub.subs.formats import (
    PRECISION_MS,
    ParsedCue,
    SubtitleError,
    parse_subtitles,
    same_cues,
    sha256_hex,
    to_ass,
    to_srt,
)
from vid2sub.subs.model import Cue, new_cue_id
from vid2sub.subs.rendition import body_track_language, cues_body, cues_from_body
from vid2sub.subs.sidecar import (
    Conflict,
    Header,
    HeadRecord,
    ProjectionRecord,
    RenditionRecord,
    Sidecar,
    SidecarError,
    VideoInfo,
    make_rendition,
    parse_sidecar,
    serialize,
)


class StoreError(RuntimeError):
    pass


class _Raced(Exception):
    """Another writer replaced the sidecar after it was read: read it again and merge."""


class ForeignFile(StoreError):
    def __init__(self, name: str):
        self.name = name
        super().__init__(f"{name} wasn't written by vid2sub, so it isn't overwritten "
                         "(--overwrite-foreign to replace it)")


class EditedOnDisk(ForeignFile):
    def __init__(self, name: str):
        self.name = name
        StoreError.__init__(
            self, f"{name} changed since vid2sub wrote it, so it isn't overwritten; "
                  "run again to keep the edit as a version")


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def sidecar_path(video: Path) -> Path:
    return video.with_name(naming.sidecar_name(video.name))


def subtitle_path(video: Path, track: str, fmt: str) -> Path:
    return video.with_name(naming.subtitle_name(video.name, track, fmt))


def header_for(video: Path, identity: VideoIdentity, duration_ms: int) -> Header:
    return Header(video=VideoInfo(name=video.name, size=identity.size,
                                  quick_sha256=identity.quick_sha256, duration_ms=duration_ms))


def _decode(data: bytes, name: str) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        raise SidecarError(f"{name} isn't UTF-8; refusing to write over it") from None


_LOCKS: weakref.WeakValueDictionary[tuple, threading.RLock] = weakref.WeakValueDictionary()
_LOCKS_GUARD = threading.Lock()


def write_lock(video: Path) -> threading.RLock:
    """This process's one lock for `video`'s sidecar, held by every append and projection.

    Keyed by the sidecar's folder as the file system knows it (device and inode) and its name
    folded for case and Unicode form, so two spellings of one file (a linked folder, another case
    on a case-insensitive volume) share it; folding a name on a case-sensitive volume only makes
    two files take turns. Reentrant, so the editor's Save holds it around all its writes. Kept
    only while someone holds it, so the engine doesn't gather one per video it ever saw."""
    path = sidecar_path(video)
    try:
        folder = os.stat(path.parent)
        key: tuple = (folder.st_dev, folder.st_ino,
                      unicodedata.normalize("NFC", path.name).casefold())
    except OSError:  # the folder is gone, and the write will say so
        key = (os.path.normcase(os.path.realpath(path)),)
    with _LOCKS_GUARD:
        lock = _LOCKS.get(key)
        if lock is None:
            lock = _LOCKS[key] = threading.RLock()
        return lock


def load(video: Path) -> tuple[Sidecar | None, list[str]]:
    path = sidecar_path(video)
    if not path.exists():
        return None, []
    return parse_sidecar(_decode(path.read_bytes(), path.name))


def append(video: Path, header: Header, records: Sequence) -> Sidecar:
    """Adds `records` to the sidecar, merging with any other writer's; returns what was written.

    It always writes with `overwrite=True`: that is safe because every write is a union merge,
    re-checked just before the rename, and a sidecar made meanwhile is merged, not replaced."""
    path = sidecar_path(video)
    with write_lock(video):
        for _ in range(5):
            before = path.read_bytes() if path.exists() else None
            current = (parse_sidecar(_decode(before, path.name))[0] if before is not None
                       else Sidecar(header))
            data = serialize(current.add(*records)).encode("utf-8")

            def unchanged(before: bytes | None = before) -> None:  # just before the rename
                try:
                    latest = path.read_bytes()
                except FileNotFoundError:
                    latest = None
                if latest != before:
                    raise _Raced

            try:  # a sidecar made meanwhile is caught by `unchanged`, then merged
                safe_write(path, data, overwrite=True, check=unchanged)
            except _Raced:
                continue
            return parse_sidecar(data.decode("utf-8"))[0]
    raise StoreError("the sidecar kept changing while vid2sub saved it; try again")


def head_record(sidecar: Sidecar, track: str, rendition_id: str, by: str, *,
                replace_person: bool = False) -> HeadRecord | None:
    """None when nothing should change; a track in Conflict is resolved in the editor."""
    current = sidecar.head(track)
    if isinstance(current, Conflict):
        return None
    if current is not None:
        if current.rendition == rendition_id:
            return None
        if by == "auto" and current.by != "auto" and not replace_person:
            return None
    return HeadRecord(track=track, rendition=rendition_id,
                      replaces=current.rendition if current is not None else None,
                      by=by, at=now())


def current_cues(sidecar: Sidecar, track: str) -> tuple[RenditionRecord, list[Cue]]:
    head = sidecar.head(track)
    if head is None:
        raise StoreError(f"there are no {track} subtitles yet")
    if isinstance(head, Conflict):
        raise StoreError(f"the {track} track has two diverging versions; pick one in the editor")
    rec = sidecar.renditions()[head.rendition]
    return rec, cues_from_body(rec.body)


def source_track(sidecar: Sidecar) -> str | None:
    renditions = sidecar.renditions()
    for track in sidecar.tracks():
        head = sidecar.head(track)
        if isinstance(head, HeadRecord):
            body = renditions[head.rendition].body
            if body.get("meta", {}).get("role") == "source":
                return track
    return None


def projected_digests(sidecar: Sidecar, name: str) -> set[str]:
    """Every hash vid2sub has ever recorded for the file `name`, not only the latest.

    The record is appended before the file is written, so a write cut short (Ctrl-C, a full
    disk, Windows' "file in use") leaves bytes whose hash is an earlier record's: vid2sub's own
    unfinished write, never a person's edit (final review).
    """
    return {r.sha256 for r in sidecar.records
            if isinstance(r, ProjectionRecord) and r.path == name}


def project(video: Path, header: Header, sidecar: Sidecar, track: str, fmt: str, *,
            overwrite_foreign: bool) -> tuple[Sidecar, Path, bool]:
    """EditedOnDisk assumes the caller ran `check_external` first; that makes the edit a version.

    A file holding an earlier projection's bytes (an interrupted write) is overwritten. The
    sidecar's write lock is held throughout, so a record and the file it describes go in together,
    and the sidecar is read again inside it: the caller's may be from before another writer's
    Save, whose file would otherwise look like an outside edit.
    """
    with write_lock(video):
        return _project(video, header, load(video)[0] or sidecar, track, fmt,
                        overwrite_foreign=overwrite_foreign)


def _project(video: Path, header: Header, sidecar: Sidecar, track: str, fmt: str, *,
             overwrite_foreign: bool) -> tuple[Sidecar, Path, bool]:
    rec, cues = current_cues(sidecar, track)
    path = subtitle_path(video, track, fmt)
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise WriteRefused(f"{path.name} exists and isn't a regular file")
    existing = path.read_bytes() if path.is_file() else None
    previous = sidecar.projections().get(path.name)
    if existing is not None and previous is None and not overwrite_foreign:
        raise ForeignFile(path.name)
    if (existing is not None and previous is not None and previous.rendition == rec.id
            and sha256_hex(existing) == previous.sha256):
        # vid2sub's own projection of the current version, perhaps restyled since (an Aegisub
        # \an8 that check_external recorded): nothing to rewrite, and rewriting would undo it
        return sidecar, path, False
    if (existing is not None and previous is not None and sha256_hex(existing) != previous.sha256
            and sha256_hex(existing) not in projected_digests(sidecar, path.name)):
        raise EditedOnDisk(path.name)
    ours = existing if (existing is not None and previous is not None) else None
    data = to_srt(cues) if fmt == "srt" else to_ass(cues, existing=ours)
    digest = sha256_hex(data)
    if (existing is not None and previous is not None and previous.rendition == rec.id
            and sha256_hex(existing) == digest):
        return sidecar, path, False
    record = ProjectionRecord(path=path.name, format=fmt, track=track, rendition=rec.id,
                              sha256=digest, at=now())
    sidecar = append(video, header, [record])
    try:
        safe_write(path, data, overwrite=existing is not None)
    except (OSError, WriteRefused):
        if previous is not None:  # the file still holds the version `previous` recorded
            # a finer time than now()'s seconds, so it never merges into the record it copies
            at = datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
            append(video, header, [previous.model_copy(update={"at": at})])
        raise
    return sidecar, path, True


def normalise_track(cues: Sequence[Cue]) -> list[Cue]:
    out: list[Cue] = []
    for c in sorted(cues, key=lambda c: (c.start_ms, c.end_ms)):
        if out and c.start_ms < out[-1].end_ms:
            out[-1] = out[-1].model_copy(update={"end_ms": c.start_ms})
        out.append(c)
    return [c for c in out if c.end_ms > c.start_ms and c.text.strip()]


def align_ids(parsed: Sequence[ParsedCue], projected: Sequence[Cue], *,
              tolerance_ms: int = 1000) -> list[Cue]:
    taken = {c.id for c in projected}
    used: set[str] = set()
    out: list[Cue] = []
    for p in parsed:
        match = next((c for c in projected if c.id not in used and c.text == p.text
                      and abs(c.start_ms - p.start_ms) <= tolerance_ms), None)
        if match is None:
            match = next((c for c in projected if c.id not in used
                          and abs(c.start_ms - p.start_ms) <= 100
                          and abs(c.end_ms - p.end_ms) <= 100), None)
        if match is None:  # a line the person added, or reworded and retimed: theirs
            out.append(Cue(id=new_cue_id(taken), start_ms=p.start_ms, end_ms=p.end_ms,
                           text=p.text, flags=("edited",)))
            continue
        used.add(match.id)
        flags = match.flags
        if match.text != p.text and "edited" not in flags:
            flags = flags + ("edited",)
        out.append(match.model_copy(update={"start_ms": p.start_ms, "end_ms": p.end_ms,
                                            "text": p.text, "flags": flags}))
    return normalise_track(out)


def check_external(video: Path, header: Header, sidecar: Sidecar, *,
                   on_unreadable: Callable[[str], None] | None = None,
                   ) -> tuple[Sidecar, list[str]]:
    """Record edits made outside vid2sub as versions; a file that won't parse is only reported.

    An unreadable or emptied file is neither adopted nor touched, so `project` later refuses it
    as `EditedOnDisk`. The new version's head replaces the version the file was written from, so
    if the head has moved on since, the two diverge (spec §14.4); so do edits to files written
    from different versions of one track (Decision 10); two edited files of one version chain
    their heads rather than diverge. Like `project`, it holds the sidecar's write lock and
    reads the sidecar again inside it, so another writer's Save is never taken for an outside edit.
    """
    with write_lock(video):
        return _check_external(video, header, load(video)[0] or sidecar,
                               on_unreadable=on_unreadable)


def _check_external(video: Path, header: Header, sidecar: Sidecar, *,
                    on_unreadable: Callable[[str], None] | None,
                    ) -> tuple[Sidecar, list[str]]:
    renditions = sidecar.renditions()
    latest: dict[tuple[str, str], str] = {}  # (track, version a file was written from) -> newest
    records: list = []
    changed: list[str] = []
    for name, proj in sidecar.projections().items():
        path = video.with_name(name)
        if not path.is_file() or path.is_symlink():
            continue
        data = path.read_bytes()
        digest = sha256_hex(data)
        if digest == proj.sha256 or digest in projected_digests(sidecar, name):
            continue  # unchanged, or vid2sub's own write that was cut short: never adopted
        projected_body = renditions[proj.rendition].body
        projected = cues_from_body(projected_body)
        try:  # an ASS file's other styles are a person's signs, not vid2sub's cues
            parsed = parse_subtitles(data, proj.format, default_style_only=proj.format == "ass")
        except SubtitleError:
            parsed = []
        if not parsed:
            if on_unreadable is not None:
                on_unreadable(name)
            continue
        if same_cues(parsed, projected, precision_ms=PRECISION_MS[proj.format]):
            records.append(proj.model_copy(update={"sha256": digest, "at": now()}))
            continue
        language, script = body_track_language(projected_body)
        body = cues_body(align_ids(parsed, projected), language=language, script=script,
                         engine="external", model=projected_body.get("model"),
                         version=f"external@{digest[:12]}", created_at=now(),
                         inputs={"file_sha256": digest},
                         meta={"file": name, "role": projected_body.get("meta", {}).get("role")},
                         glossary_sha=projected_body.get("payload", {}).get("glossary_sha"))
        rec = make_rendition([proj.rendition], proj.track, body)
        key = (proj.track, proj.rendition)
        latest.setdefault(key, proj.rendition)
        records += [rec,
                    HeadRecord(track=proj.track, rendition=rec.id,
                               replaces=latest[key], by="external", at=now()),
                    ProjectionRecord(path=name, format=proj.format, track=proj.track,
                                     rendition=rec.id, sha256=digest, at=now())]
        latest[key] = rec.id
        changed.append(proj.track)
    if records:
        sidecar = append(video, header, records)
    return sidecar, changed


def import_subtitles(video: Path, header: Header, sub_path: Path, track: str, *,
                     role: str) -> Sidecar:
    """A person's explicit action, so it may replace a person's head (spec §14.4 binds only auto)."""
    data = sub_path.read_bytes()
    fmt = sub_path.suffix.lower().lstrip(".")
    parsed = parse_subtitles(data, fmt if fmt in ("srt", "ass", "ssa", "vtt") else None)
    taken: set[str] = set()
    cues = normalise_track([Cue(id=new_cue_id(taken), start_ms=p.start_ms, end_ms=p.end_ms,
                                text=p.text) for p in parsed])
    info = naming.track(track)
    digest = sha256_hex(data)
    body = cues_body(cues, language=info.lang, script=info.script, engine="import", model=None,
                     version=f"import@{digest[:12]}", created_at=now(),
                     inputs={"file_sha256": digest}, meta={"file": sub_path.name, "role": role})
    existing, _ = load(video)
    sidecar = existing or Sidecar(header)
    rec = make_rendition([], track, body)
    head = sidecar.head(track)
    records: list = [rec, HeadRecord(track=track, rendition=rec.id,
                                     replaces=head.rendition if isinstance(head, HeadRecord)
                                     else None, by="import", at=now())]
    if fmt in ("srt", "ass") and sub_path.resolve() == subtitle_path(video, track, fmt).resolve():
        records.append(ProjectionRecord(path=sub_path.name, format=fmt, track=track,
                                        rendition=rec.id, sha256=digest, at=now()))
    return append(video, header, records)
