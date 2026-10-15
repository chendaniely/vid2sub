"""whisper.cpp v1.9.4 server `verbose_json` → a ParsedChunk (spec §9.2).

Its words are BPE tokens (merged here); its top-level `language` is a full name, while
`language_probabilities` is keyed by ISO code; `t_dtw` is in raw 10 ms units and, when the server
runs with DTW (local-ai item 5), is better than the token's own start/end, so it wins. A token
with U+FFFD (a CJK character split across tokens, whisper.cpp issue #399) makes the segment
unaligned rather than wrong.
"""

from __future__ import annotations

from typing import Any

from vid2sub.parse import ParsedChunk, ParseError
from vid2sub.parse.words import ms, tokens_to_words
from vid2sub.subs import langs
from vid2sub.subs.model import Segment


def parse_whispercpp(data: Any) -> ParsedChunk:
    if not isinstance(data, dict) or not isinstance(data.get("segments"), list):
        raise ParseError("not a whisper.cpp verbose_json response")
    probs = {str(k): float(v) for k, v in (data.get("language_probabilities") or {}).items()}
    language = langs.from_whisper_full(str(data.get("language") or ""))
    if language is None and probs:
        language = max(probs, key=probs.__getitem__)
    segments = []
    for seg in data["segments"]:
        s_start = ms(seg.get("start")) or 0
        s_end = ms(seg.get("end"))
        s_end = s_start if s_end is None or s_end < s_start else s_end
        raw = [w for w in seg.get("words") or [] if isinstance(w, dict)]
        dtw = [w.get("t_dtw") for w in raw]
        use_dtw = bool(raw) and all(isinstance(t, (int, float)) and t >= 0 for t in dtw)
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
