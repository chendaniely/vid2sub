"""OpenAI `whisper-1` `verbose_json` → a ParsedChunk (spec §9.2).

OpenAI returns words at the top level, without spaces or punctuation, so each word is assigned
to the segment containing its midpoint and the segment's text supplies the punctuation.
"""

from __future__ import annotations

from typing import Any

from vid2sub.parse import ParsedChunk, ParseError
from vid2sub.parse.words import attach_punctuation, ms
from vid2sub.subs import langs
from vid2sub.subs.model import Segment


def parse_openai(data: Any) -> ParsedChunk:
    if not isinstance(data, dict) or not isinstance(data.get("segments"), list):
        raise ParseError("not an OpenAI verbose_json response")
    raw_lang = str(data.get("language") or "")
    language = langs.from_whisper_full(raw_lang) or (raw_lang if raw_lang in langs.LANGS else None)
    words = [w for w in data.get("words") or [] if isinstance(w, dict)]
    segs = data["segments"]
    segments = []
    for i, seg in enumerate(segs):
        if not isinstance(seg, dict):
            raise ParseError("an OpenAI segment is not an object")
        s_start = ms(seg.get("start")) or 0
        s_end = max(ms(seg.get("end")) or s_start, s_start)
        last = i == len(segs) - 1
        mine = []
        for w in words:
            ws, we = ms(w.get("start")), ms(w.get("end"))
            if ws is None or we is None:
                continue
            mid = (ws + we) // 2
            if s_start <= mid < s_end or (last and mid >= s_start):
                mine.append((str(w.get("word", "")), ws, we))
        text = str(seg.get("text", ""))
        aligned = attach_punctuation(text, mine, start_ms=s_start) if mine else None
        segments.append(Segment(
            text="".join(w.text for w in aligned) if aligned else text,
            start_ms=s_start, end_ms=s_end, words=tuple(aligned or ()),
            avg_logprob=seg.get("avg_logprob"), no_speech_prob=seg.get("no_speech_prob"),
            compression_ratio=seg.get("compression_ratio")))
    return ParsedChunk(tuple(segments), language, {language: 1.0} if language else {})
