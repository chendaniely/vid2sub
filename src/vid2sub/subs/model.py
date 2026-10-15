"""The subtitle data model: words, segments, transcripts and cues (spec §9.2, §12.1, §14.3).

Times are integer milliseconds everywhere. Words follow Whisper's convention, whatever engine
produced them: a leading space marks a word boundary, so joining a segment's words gives its text,
and CJK words carry no spaces. A word whose time the engine didn't give is `timed=False` and sits
at the previous word's end (recordings' rule). Cue ids are random, unique per track and never
reused; SRT numbers are only for display.
"""

from __future__ import annotations

import secrets
from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Word(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    text: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    prob: float | None = None
    timed: bool = True


class Segment(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    text: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    words: tuple[Word, ...] = ()
    avg_logprob: float | None = None
    no_speech_prob: float | None = None
    compression_ratio: float | None = None

    @property
    def aligned(self) -> bool:
        return bool(self.words)


class Transcript(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    language: str
    segments: tuple[Segment, ...]
    language_probs: dict[str, float] = Field(default_factory=dict)

    def words(self) -> list[Word]:
        return [word for seg in self.segments for word in seg.words]


class Cue(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)
    id: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    text: str
    w: tuple[int, int] | None = None  # word index range [i, j) in the transcript
    src: tuple[str, ...] | None = None  # translation: the source cue ids it covers
    src_sha: str | None = None
    from_: tuple[str, ...] | None = Field(default=None, alias="from")
    detached: bool = False
    flags: tuple[str, ...] = ()

    def dump(self) -> dict[str, Any]:
        return self.model_dump(mode="json", by_alias=True, exclude_defaults=True)


def shift_segment(seg: Segment, offset_ms: int) -> Segment:
    return seg.model_copy(update={
        "start_ms": seg.start_ms + offset_ms,
        "end_ms": seg.end_ms + offset_ms,
        "words": tuple(w.model_copy(update={"start_ms": w.start_ms + offset_ms,
                                            "end_ms": w.end_ms + offset_ms})
                       for w in seg.words),
    })


def new_cue_id(taken: set[str]) -> str:
    while True:
        cid = "c" + secrets.token_hex(4)
        if cid not in taken:
            taken.add(cid)
            return cid


class TrackError(ValueError):
    pass


def check_track(cues: Sequence[Cue]) -> None:
    """The invariants every stored track keeps (spec §12.1)."""
    seen: set[str] = set()
    prev: Cue | None = None
    for c in cues:
        if c.id in seen:
            raise TrackError(f"duplicate id {c.id}")
        seen.add(c.id)
        if c.start_ms >= c.end_ms:
            raise TrackError(f"cue {c.id} starts at or after its end")
        if not c.text.strip():
            raise TrackError(f"cue {c.id} is empty")
        if any(not line.strip() for line in c.text.split("\n")):
            raise TrackError(f"cue {c.id} has a blank line")
        if prev is not None:
            if c.start_ms < prev.start_ms:
                raise TrackError(f"cue {c.id} is out of order")
            if c.start_ms < prev.end_ms:
                raise TrackError(f"cue {c.id} overlaps {prev.id}")
        prev = c
