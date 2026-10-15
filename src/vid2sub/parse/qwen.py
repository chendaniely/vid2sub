"""mlx-qwen3-asr's result → a ParsedChunk (spec §9.2, §9.4).

Qwen3-ASR gives the text; its forced aligner gives word or character units with times. Whether
the units carry punctuation isn't documented (spec §29), so the text's punctuation is attached to
them either way. If the units can't be found in the text, or none of them has a time, the chunk
becomes one unaligned segment rather than wrong timings.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from vid2sub.parse import ParsedChunk
from vid2sub.parse.words import attach_punctuation, ms
from vid2sub.subs import langs
from vid2sub.subs.model import Segment


def parse_qwen(result: Mapping[str, Any], *, duration_ms: int) -> ParsedChunk:
    text = str(result.get("text") or "")
    language = langs.from_qwen(str(result.get("language") or ""))
    # The engine reports only the language, not a distribution: 1.0 means "the engine said so",
    # not a measured probability.
    probs = {language: 1.0} if language else {}
    units = [(str(u.get("text", "")), ms(u.get("start")), ms(u.get("end")))
             for u in result.get("segments") or [] if isinstance(u, Mapping)]
    timed = [start for _, start, end in units if start is not None and end is not None
             and end >= start]
    words = (attach_punctuation(text, units, start_ms=timed[0] if timed else 0)
             if units and text.strip() else None)
    if words and any(w.timed for w in words):
        seg = Segment(text="".join(w.text for w in words), start_ms=words[0].start_ms,
                      end_ms=max(w.end_ms for w in words), words=tuple(words))
    elif text.strip():
        seg = Segment(text=text, start_ms=0, end_ms=duration_ms)
    else:
        return ParsedChunk((), language, probs)
    return ParsedChunk((seg,), language, probs)
