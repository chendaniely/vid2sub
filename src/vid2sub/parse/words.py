"""Helpers shared by the parsers: tokens into words, untimed words, and punctuation (spec §9.2).

whisper.cpp's "words" are BPE tokens, so they're merged into words on the leading space; a CJK
token is a word of its own. Aligners (Qwen's, OpenAI's word list) return units without the
text's spaces and punctuation, so `attach_punctuation` maps them back: closing punctuation joins
the word before it, a space and any opening punctuation join the word after. A word with no time
sits at the previous word's end and is marked untimed (recordings' rule).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from vid2sub.subs.model import Word
from vid2sub.subs.text import NO_LINE_END, is_cjk

RawToken = tuple[str, int | None, int | None, float | None]


def ms(seconds: Any) -> int | None:
    if seconds is None:
        return None
    try:
        value = float(seconds)
    except (TypeError, ValueError):
        return None
    return None if value < 0 else round(value * 1000)


def fill_untimed(raw: Sequence[Sequence[Any]], start_ms: int = 0) -> list[Word]:
    words: list[Word] = []
    prev_end = start_ms
    for text, start, end, prob in raw:
        if start is None or end is None or end < start:
            words.append(Word(text=text, start_ms=prev_end, end_ms=prev_end, prob=prob,
                              timed=False))
        else:
            words.append(Word(text=text, start_ms=start, end_ms=end, prob=prob))
            prev_end = end
    return words


def tokens_to_words(tokens: Sequence[RawToken], *, start_ms: int = 0) -> list[Word]:
    merged: list[list[Any]] = []
    for text, start, end, prob in tokens:
        if not text or not text.strip():
            continue
        head = text.lstrip()
        last = merged[-1][0].rstrip() if merged else ""
        starts_word = (not merged or text[0].isspace() or is_cjk(head[0])
                       or (bool(last) and is_cjk(last[-1])))
        if starts_word:
            merged.append([text, start, end, prob])
            continue
        current = merged[-1]
        current[0] += text
        if end is not None:
            current[2] = end
        if prob is not None:
            current[3] = prob if current[3] is None else min(current[3], prob)
    return fill_untimed(merged, start_ms)


def attach_punctuation(text: str, units: Sequence[tuple[str, int | None, int | None]], *,
                       start_ms: int = 0) -> list[Word] | None:
    lowered = text.lower()
    haystack = lowered if len(lowered) == len(text) else text
    raw: list[list[Any]] = []
    pos = 0
    for utext, start, end in units:
        needle = utext.strip()
        if not needle:
            continue
        found = haystack.find(needle.lower() if haystack is lowered else needle, pos)
        if found < 0:
            return None
        gap = text[pos:found]
        lead = ""
        if gap:
            space = next((i for i, ch in enumerate(gap) if ch.isspace()), None)
            if space is not None:
                closing, lead = gap[:space], " " + gap[space:].strip()
            else:
                k = len(gap)
                while k > 0 and gap[k - 1] in NO_LINE_END:
                    k -= 1
                closing, lead = gap[:k], gap[k:]
            if closing:
                if raw:
                    raw[-1][0] += closing
                else:
                    lead = closing + lead
        raw.append([lead + text[found:found + len(needle)], start, end, None])
        pos = found + len(needle)
    if not raw:
        return None
    raw[-1][0] += text[pos:].rstrip()
    return fill_untimed(raw, start_ms)
