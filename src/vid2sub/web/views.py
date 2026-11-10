"""The editor's view of an episode: plain JSON for the React frontend (spec §19.1, §20, §12.5).

A pure function of the `Episode`, so the shinyreact server only sends what it returns, and every
flag the cue list shows is computed here once. One row per source cue, in order, with each
translation track's cues in the row of the first source cue they cover; a translation whose
source cues are all gone sits in the row at its time, so nothing is hidden. Flags are the stored
ones (`est`, `halluc`, `edited`) with the lint flags recomputed each time, never stored as truth
(§12.5): reading speed, width and duration by each track's own language rules; `stale` from the
source text a translation was made from, and on every cue of a track made with another glossary
or model (§13.4, `episode.all_stale`); `untranslated` for a source cue no translation in a track
covers; an imported line (no `src`) is never stale and covers the source cues it overlaps in time
(Q&A item 45). The view never holds a path, only the video's bare file name (§6.8), and the
probe's container and codec names, which the browser's canPlayType is asked about (§8.2). It
names each track's head rendition, by which the tab keys its crash-recovery draft (§14.5, S34),
and the formats Save writes: ASS too where one was written before (§15.2). A track in conflict
lists its versions, and the cues where they differ, so the person can tell which holds what
(§14.4, S32). The server runs in Pages too (§21), so this module imports only pure packages and
`web.episode` at its top; the status views' config and keys are the local engine's, imported only
where they are used (Task 14 round 14a).
"""

from __future__ import annotations

import dataclasses
from bisect import bisect_right
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from vid2sub.subs import langs, naming
from vid2sub.subs.lint import lint
from vid2sub.subs.model import Cue
from vid2sub.subs.rendition import cues_from_body
from vid2sub.subs.rules import rules_for
from vid2sub.subs.sidecar import HeadRecord
from vid2sub.subs.translate_shape import stale_linked_ids, uncovered_ids
from vid2sub.web.episode import Capabilities, Episode, all_stale

if TYPE_CHECKING:  # local only: the Pages bundle has neither (spec §21)
    from vid2sub.config import Config
    from vid2sub.engines.clients import KeyRing

_SCRIPTS = {"Hant": " (Traditional)", "Hans": " (Simplified)"}
DIFFERENCES_SHOWN = 50  # cues where a conflicted track's versions differ, before "and N more"


def episode_view(ep: Episode, *, video_url: str | None, audio_url: str | None) -> dict[str, Any]:
    return {
        "id": ep.id,
        "video": {"name": ep.video.name, "duration_ms": ep.header.video.duration_ms,
                  "url": video_url, "audio_url": audio_url, "playable_audio": ep.playable_audio,
                  "container": ep.streams.container, "video_codec": ep.streams.video_codec,
                  "audio_codec": ep.streams.audio_codec},
        "source": ep.source_key,
        "tracks": _tracks(ep),
        "rows": _rows(ep),
        "words": [{"start_ms": w.start_ms, "end_ms": w.end_ms, "text": w.text}
                  for w in ep.words],
        "dirty": ep.dirty,
        "can_undo": bool(ep.undo),
        "can_redo": bool(ep.redo),
        "notes": list(ep.notes),
        "conflicts": _conflicts(ep),
        "differences": _differences(ep),
        "glossary_adds": dict(ep.glossary_adds),
        "heads": dict(ep.heads),
        "formats": _formats(ep),
    }


def capabilities_view(caps: Capabilities) -> dict[str, Any]:
    return dataclasses.asdict(caps)


def local_endpoints(config: Config) -> list[str]:
    """The endpoints that serve a local model, the only ones the engine contacts unasked."""
    from vid2sub.config import is_local  # here: the Pages bundle has no vid2sub.config

    return [name for name in config.endpoints
            if any(m.endpoint == name and is_local(m, config) for m in config.models.values())]


def status_view(config: Config, keys: KeyRing, reachable: Mapping[str, bool], *,
                ffmpeg: bool) -> dict[str, Any]:
    """`reachable`: what the last check found for each local endpoint; one not in it is `None`
    (not checked yet), as is every cloud endpoint (never contacted)."""
    local = set(local_endpoints(config))
    endpoints = []
    for name, ep in config.endpoints.items():
        needs_key = bool(ep.key_env) or ep.allow_typed_key
        key = ("present" if keys.key_for(name, ep) else "missing") if needs_key else "none"
        endpoints.append({"name": name, "local": name in local, "key": key,
                          "reachable": reachable.get(name) if name in local else None})
    return {"endpoints": endpoints, "ffmpeg": ffmpeg}


def _rows(ep: Episode) -> list[dict[str, Any]]:
    source = ep.tracks.source
    linted = lint(source, rules_for(_lang(ep.source_key)))
    rows = [{"id": c.id, "n": n, "start_ms": c.start_ms, "end_ms": c.end_ms, "text": c.text,
             "w": list(c.w) if c.w else None, "flags": _flags(c.flags, linted.get(c.id, ())),
             "tr": {}} for n, c in enumerate(source, 1)]
    if not rows:
        return rows
    by_id = {c.id: c for c in source}
    index = {c.id: k for k, c in enumerate(source)}
    starts = [c.start_ms for c in source]
    for track, cues in ep.tracks.translations.items():
        linted = lint(cues, rules_for(_lang(track)))
        stale = ({c.id for c in cues if c.src} if all_stale(ep, track)
                 else stale_linked_ids(cues, by_id))
        cells: list[dict[str, list]] = [{"cues": [], "flags": []} for _ in rows]
        for c in cues:
            extra = ("stale",) if c.id in stale else ()
            cells[_row_of(c, index, starts)]["cues"].append({
                "id": c.id, "start_ms": c.start_ms, "end_ms": c.end_ms, "text": c.text,
                "src": list(c.src or ()), "detached": c.detached,
                "flags": _flags(c.flags, linted.get(c.id, ()) + extra)})
        for cid in uncovered_ids(source, cues):
            cells[index[cid]]["flags"] = ["untranslated"]
        for row, cell in zip(rows, cells, strict=True):
            row["tr"][track] = cell
    return rows


def _row_of(c: Cue, index: dict[str, int], starts: list[int]) -> int:
    """The row of the first source cue it covers; else the row at its time."""
    covered = [index[i] for i in c.src or () if i in index]
    if covered:
        return min(covered)
    return max(bisect_right(starts, c.start_ms) - 1, 0)


def _tracks(ep: Episode) -> list[dict[str, Any]]:
    keys = [ep.source_key] + [t for t in ep.sidecar.tracks() if t != ep.source_key
                              and (t in ep.tracks.translations or t in ep.conflicts)]
    out = []
    for key in keys:
        head = ep.sidecar.head(key)
        out.append({"key": key, "label": _label(key),
                    "role": "source" if key == ep.source_key else "translation",
                    "head_by": head.by if isinstance(head, HeadRecord) else None,
                    "in_conflict": key in ep.conflicts,
                    "all_stale": key in ep.tracks.translations and all_stale(ep, key)})
    return out


def _conflicts(ep: Episode) -> dict[str, list[dict[str, Any]]]:
    renditions = ep.sidecar.renditions()
    out: dict[str, list[dict[str, Any]]] = {}
    for track, leaves in ep.conflicts.items():
        heads = {h.rendition: h for h in ep.sidecar.heads(track)}  # the latest for each
        out[track] = []
        for rid in leaves:
            head, rec = heads.get(rid), renditions.get(rid)
            out[track].append({
                "rendition": rid, "by": head.by if head else None, "at": head.at if head else None,
                "cue_count": len(rec.body.get("payload", {}).get("cues", [])) if rec else 0})
    return out


def _differences(ep: Episode) -> dict[str, dict[str, Any]]:
    """For each track in conflict, the cues where its versions differ (spec §14.4, S32): each
    cue's time (from the first version that has it) and its text in each version, in the order
    `_conflicts` lists them, or None where a version lacks it; cues are matched by id, which a
    text or time edit keeps. At most DIFFERENCES_SHOWN, in time order, with a count of the rest.
    Worked out once per view, from the versions' cues."""
    renditions = ep.sidecar.renditions()
    out: dict[str, dict[str, Any]] = {}
    for track, leaves in ep.conflicts.items():
        versions = [{c.id: c for c in cues_from_body(renditions[rid].body)}
                    if rid in renditions else {} for rid in leaves]
        found = []
        for cid in dict.fromkeys(cid for v in versions for cid in v):
            cues = [v.get(cid) for v in versions]
            if None not in cues and len({(c.start_ms, c.end_ms, c.text) for c in cues}) == 1:
                continue
            first = next(c for c in cues if c is not None)
            found.append({"start_ms": first.start_ms, "end_ms": first.end_ms,
                          "texts": [c.text if c is not None else None for c in cues]})
        found.sort(key=lambda d: (d["start_ms"], d["end_ms"]))
        out[track] = {"cues": found[:DIFFERENCES_SHOWN],
                      "more": max(0, len(found) - DIFFERENCES_SHOWN)}
    return out


def _formats(ep: Episode) -> list[str]:
    """SRT, and ASS where vid2sub has written an ASS for this video before (spec §15.2)."""
    written = {p.format for p in ep.sidecar.projections().values()}
    return ["srt", "ass"] if "ass" in written else ["srt"]


def _flags(stored: tuple[str, ...], computed: tuple[str, ...]) -> list[str]:
    return sorted(set(stored) | set(computed))


def _lang(track: str) -> str:
    info = naming.TRACKS.get(track)
    return info.lang if info else track.split("-")[0]


def _label(track: str) -> str:
    info = naming.TRACKS.get(track)
    if info is None:
        return track
    name = langs.LANGS[info.lang].name if info.lang in langs.LANGS else info.lang
    return name + _SCRIPTS.get(info.script or "", "")
