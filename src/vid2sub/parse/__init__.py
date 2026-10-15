"""Engine responses → vid2sub's one word shape (spec §9.2). Pure: no I/O, runs in Pyodide later.

Every engine's response becomes a ParsedChunk: segments of words in Whisper's convention (a
leading space marks a word boundary; joining a segment's words gives its text), with times in
milliseconds relative to the chunk.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from vid2sub.subs.model import Segment


class ParseError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedChunk:
    segments: tuple[Segment, ...]
    language: str | None
    language_probs: dict[str, float] = field(default_factory=dict)
