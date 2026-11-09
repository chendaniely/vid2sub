"""The editor's episode, and the shapes the Shiny server, its views and the backends share (spec
§3.3, §19.1, §21).

Pure, so the server and its views import only what the Pages bundle has: spec §21 bundles
`vid2sub.subs`, `vid2sub.catalog`, `vid2sub.parse` and `web/server.py` with `BrowserBackend`, and
Pyodide has no ffmpeg, network client or threads (the Phase 2 plan's Global Constraints, Task 14
round 14a). `LocalBackend` (`web.backend`) makes and changes these values and re-exports them, so
its callers' imports stay as they were. An `Episode` is never changed in place: every backend call
returns a new one, so a reactive value that holds it sees each change. Stale follows spec §13.4
as M1 decides it (`pipeline._translate_targets`): a translation is stale when its source text
changed, and every cue of it when the glossary's hash or the translation model differs from the
ones its head was made with (Decision 9).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from vid2sub.subs.edit import Tracks
from vid2sub.subs.glossary import Glossary
from vid2sub.subs.model import Word
from vid2sub.subs.sidecar import Header, Sidecar


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


# One undo or redo step: the tracks, the glossary adds and `made_with` as they were.
Snapshot = tuple[Tracks, dict[str, str], dict[str, tuple[str, str | None]]]


@dataclass(frozen=True)
class Streams:
    """What the browser is asked about before it plays the video (spec §8.2): ffprobe's names for
    the container, the video's codec and the codec of the audio track the editor plays."""

    container: str = ""  # ffprobe's format_name, such as "mov,mp4,m4a,3gp,3g2,mj2"
    video_codec: str | None = None  # None: no picture (or only cover art)
    audio_codec: str = ""


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
    undo: list[Snapshot] = field(default_factory=list)
    redo: list[Snapshot] = field(default_factory=list)
    taken: set[str] = field(default_factory=set)
    glossary_adds: dict[str, str] = field(default_factory=dict)
    made_with: dict[str, tuple[str, str | None]] = field(default_factory=dict)  # since a redo-all
    streams: Streams = Streams()  # from the probe at open

    @property
    def dirty(self) -> bool:
        return self.tracks != self.base or bool(self.glossary_adds)


def glossary_with(glossary: Glossary, adds: dict[str, str]) -> Glossary:
    """The glossary as it will read once Save has added `adds`: a term it has keeps its own."""
    have = dict(glossary.terms)
    return Glossary(glossary.description, glossary.terms + tuple(
        (term, translation) for term, translation in adds.items() if term not in have))


def track_setup(ep: Episode, track: str) -> tuple[str, str | None]:
    """The glossary hash ("" for none) and the model the track's cues were made with: those of a
    retranslation that redid every unedited cue, while none of the cues it replaced is back (an
    undo), else its head's."""
    made = ep.made_with.get(track)
    if made is not None:
        before = {c.id for c in ep.base.translations.get(track, ())}
        if not any(c.id in before for c in ep.tracks.translations.get(track, ())
                   if "edited" not in c.flags):
            return made
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
