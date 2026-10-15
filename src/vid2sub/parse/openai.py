"""OpenAI `whisper-1` `verbose_json` → a ParsedChunk (spec §9.2).

OpenAI returns words at the top level, without spaces or punctuation, so each word is assigned
to the segment containing its midpoint (or the nearest one, for words between segments or before
the first) and the segment's text supplies the punctuation. A segment whose words don't spell its
text is unaligned rather than wrong, because joining a segment's words must give its text.
"""

from __future__ import annotations

from typing import Any

from vid2sub.parse import ParsedChunk, ParseError
from vid2sub.parse.words import attach_punctuation, ms
from vid2sub.subs import langs
from vid2sub.subs.model import Segment


def _segment_for(mid: int, spans: list[tuple[int, int]]) -> int:
    best, best_gap = 0, None
    for i, (start, end) in enumerate(spans):
        if start <= mid < end:
            return i
        gap = start - mid if mid < start else mid - end
        if best_gap is None or gap < best_gap:
            best, best_gap = i, gap
    return best


def parse_openai(data: Any) -> ParsedChunk:
    if not isinstance(data, dict) or not isinstance(data.get("segments"), list):
        raise ParseError("not an OpenAI verbose_json response")
    raw_lang = str(data.get("language") or "")
    language = langs.from_whisper_full(raw_lang) or (raw_lang if raw_lang in langs.LANGS else None)
    words = [w for w in data.get("words") or [] if isinstance(w, dict)]
    segs = data["segments"]
    for seg in segs:
        if not isinstance(seg, dict):
            raise ParseError("an OpenAI segment is not an object")
    spans = []
    for seg in segs:
        s_start = ms(seg.get("start")) or 0
        spans.append((s_start, max(ms(seg.get("end")) or s_start, s_start)))
    mine: list[list[tuple[str, int, int]]] = [[] for _ in segs]
    if segs:
        for w in words:
            ws, we = ms(w.get("start")), ms(w.get("end"))
            if ws is None or we is None:
                continue
            mine[_segment_for((ws + we) // 2, spans)].append((str(w.get("word", "")), ws, we))
    segments = []
    for seg, (s_start, s_end), units in zip(segs, spans, mine, strict=True):
        text = str(seg.get("text", ""))
        aligned = attach_punctuation(text, units, start_ms=s_start) if units else None
        if aligned and "".join(w.text for w in aligned) == text.rstrip():
            text, words_out = "".join(w.text for w in aligned), tuple(aligned)
        else:
            words_out = ()
        segments.append(Segment(
            text=text, start_ms=s_start, end_ms=s_end, words=words_out,
            avg_logprob=seg.get("avg_logprob"), no_speech_prob=seg.get("no_speech_prob"),
            compression_ratio=seg.get("compression_ratio")))
    # The engine reports only the language, not a distribution: 1.0 means "the engine said so",
    # not a measured probability.
    return ParsedChunk(tuple(segments), language, {language: 1.0} if language else {})
