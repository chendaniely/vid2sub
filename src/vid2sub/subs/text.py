"""Text rules for subtitle lines (spec §12.2, §12.3, §15.2).

Width is in East Asian Width units: a wide or full-width character counts 2, anything else 1, so
one limit table covers English (42) and Japanese (26, i.e. 13 full-width characters), as
Netflix's timed-text guides count them. Lines break at spaces, or between two characters where
either is CJK; never inside a run of Latin letters or digits, and never against kinsoku: no line
starts with closing punctuation or small kana, and none ends with an opening bracket.
"""

from __future__ import annotations

import re
import unicodedata

NO_LINE_START = frozenset(
    "、。，．・：；？！ー…‥）」』】〕〉》〙〗〟’”｠»ゝゞヽヾぁぃぅぇぉっゃゅょゎゕゖ"
    "ァィゥェォッャュョヮヵヶ々〻,.!?;:)]}%％"
)
NO_LINE_END = frozenset("（「『【〔〈《〘〖〝‘“｟«([{")
SENTENCE_END = frozenset(".!?。！？…")
CLAUSE_END = frozenset(",;:、，；：")
_SPACES = re.compile(r"[ \t]+")


def char_width(ch: str) -> int:
    if unicodedata.combining(ch):
        return 0
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


def width(text: str) -> int:
    return sum(char_width(ch) for ch in text)


def is_cjk(ch: str) -> bool:
    return unicodedata.east_asian_width(ch) in ("W", "F")


def canonical(text: str) -> str:
    """`\\n` line breaks, single spaces, no blank or padded lines (spec §15.2).

    `{`, `}` and `\\` are stored full-width: ASS reads them as markup, so what's written is
    exactly what's read back."""
    text = text.replace("{", "｛").replace("}", "｝").replace("\\", "＼")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = (_SPACES.sub(" ", line).strip() for line in text.split("\n"))
    return "\n".join(line for line in lines if line)


def unwrap(text: str) -> str:
    """Join lines into one: a space between Latin text, nothing between CJK."""
    parts = canonical(text).split("\n")
    out = parts[0]
    for part in parts[1:]:
        joiner = "" if out and is_cjk(out[-1]) and is_cjk(part[0]) else " "
        out += joiner + part
    return out


def _breaks(text: str) -> list[tuple[int, int]]:
    """Where `text` may break: (end of line 1, start of line 2)."""
    points: list[tuple[int, int]] = []
    for i in range(1, len(text)):
        prev, cur = text[i - 1], text[i]
        if cur == " ":
            continue
        if prev == " ":
            j = i - 1
            while j > 0 and text[j - 1] == " ":
                j -= 1
            if j > 0:
                points.append((j, i))
            continue
        if not (is_cjk(prev) or is_cjk(cur)):
            continue
        if cur in NO_LINE_START or prev in NO_LINE_END:
            continue
        points.append((i, i))
    return points


def wrap(text: str, max_width: int, max_lines: int = 2) -> list[str] | None:
    """At most two lines no wider than `max_width`, as balanced as possible; None if impossible.

    Ties prefer a shorter first line, and a break after punctuation wins over a slightly more
    even one."""
    text = unwrap(text)
    if not text:
        return []
    if width(text) <= max_width:
        return [text]
    if max_lines < 2:
        return None
    best: tuple[float, list[str]] | None = None
    for end1, start2 in _breaks(text):
        first, second = text[:end1].rstrip(), text[start2:].lstrip()
        if not first or not second:
            continue
        w1, w2 = width(first), width(second)
        if w1 > max_width or w2 > max_width:
            continue
        score = abs(w1 - w2) + (0.5 if w1 > w2 else 0.0)
        if first[-1] in SENTENCE_END or first[-1] in CLAUSE_END:
            score -= 4
        if best is None or score < best[0]:
            best = (score, [first, second])
    return best[1] if best else None


def strip_line_ends(lines: list[str], chars: str = "，。") -> list[str]:
    """Chinese subtitle lines don't end with a comma or full stop (spec §12.3)."""
    return [line.rstrip(chars) or line for line in lines]
