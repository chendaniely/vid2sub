"""whisper.cpp v1.9.4 server `verbose_json` → a ParsedChunk (spec §9.2).

Its words are BPE tokens (merged here); its top-level `language` is a full name, while
`language_probabilities` is keyed by ISO code; `t_dtw` is in raw 10 ms units and, when the server
runs with DTW (local-ai item 5), is better than the token's own start/end, so it wins. A token
with U+FFFD (a CJK character split across tokens, whisper.cpp issue #399) makes the segment
unaligned rather than wrong.
"""

from __future__ import annotations

import itertools
import math
from typing import Any

from vid2sub.parse import ParsedChunk, ParseError
from vid2sub.parse.words import ms, tokens_to_words
from vid2sub.subs import langs
from vid2sub.subs.model import Segment


def _dtw_is_usable(raw: list[dict[str, Any]], s_start: int, s_end: int) -> bool:
    starts = []
    for w in raw:
        t = w.get("t_dtw")
        if isinstance(t, bool) or not isinstance(t, (int, float)) or not math.isfinite(t) or t < 0:
            return False
        starts.append(round(t * 10))
    if any(later < earlier for earlier, later in itertools.pairwise(starts)):
        return False
    return all(s_start <= start <= s_end for start in starts)


def parse_whispercpp(data: Any) -> ParsedChunk:
    if not isinstance(data, dict) or not isinstance(data.get("segments"), list):
        raise ParseError("not a whisper.cpp verbose_json response")
    raw_probs = data.get("language_probabilities") or {}
    if not isinstance(raw_probs, dict):
        raise ParseError("language_probabilities is not an object")
    try:
        probs = {str(k): float(v) for k, v in raw_probs.items()}
    except (TypeError, ValueError):
        raise ParseError("language_probabilities holds a value that is not a number") from None
    language = langs.from_whisper_full(str(data.get("language") or ""))
    if language is None and probs:
        language = max(probs, key=probs.__getitem__)
    segments = []
    for seg in data["segments"]:
        if not isinstance(seg, dict):
            raise ParseError("a whisper.cpp segment is not an object")
        s_start = ms(seg.get("start")) or 0
        s_end = ms(seg.get("end"))
        s_end = s_start if s_end is None or s_end < s_start else s_end
        raw = [w for w in seg.get("words") or [] if isinstance(w, dict)]
        dtw = [w.get("t_dtw") for w in raw]
        use_dtw = bool(raw) and _dtw_is_usable(raw, s_start, s_end)
        tokens = []
        for k, w in enumerate(raw):
            if use_dtw:
                start = round(dtw[k] * 10)
                end = round(dtw[k + 1] * 10) if k + 1 < len(raw) else s_end
            else:
                start, end = ms(w.get("start")), ms(w.get("end"))
            tokens.append((str(w.get("word", "")), start, end, w.get("probability")))
        words = tokens_to_words(tokens, start_ms=s_start)
        if any("�" in w.text for w in words):
            words = []
        text = "".join(w.text for w in words) if words else str(seg.get("text", ""))
        segments.append(Segment(text=text, start_ms=s_start, end_ms=s_end, words=tuple(words),
                                avg_logprob=seg.get("avg_logprob"),
                                no_speech_prob=seg.get("no_speech_prob"),
                                compression_ratio=seg.get("compression_ratio")))
    return ParsedChunk(tuple(segments), language, probs)
