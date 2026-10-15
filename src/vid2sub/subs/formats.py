"""SRT and ASS: bytes out, cues in, and the comparisons that decide external edits (spec §15).

vid2sub serialises with pysubs2 but writes the bytes itself: LF line endings and UTF-8 (BOM
optional), so a projection's hash is the same on every OS (pysubs2's own save() writes CRLF on
Windows). Canonical text keeps `\\n` breaks and `<i>` as the only markup; braces become full-width
so text can never turn into ASS override tags. An existing ASS file keeps its Script Info, Styles
and every event outside vid2sub's `Default` style (plan decision 6), and outside-edit checks read
only its `Default` events, so a person's signs never become dialogue. Imports read UTF-8 with or
without a BOM, then fall back to charset-normalizer, because GBK, Big5 and Shift-JIS files are
common. ASS stores centiseconds, so comparisons allow the format's precision (spec §15.3).
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

import pysubs2
from charset_normalizer import from_bytes

from vid2sub.subs.model import Cue
from vid2sub.subs.text import canonical

PRECISION_MS = {"srt": 1, "ass": 10}
_ASS_TAG = re.compile(r"\{[^}]*\}")
_HTML_TAG = re.compile(r"</?(?!i>)[a-zA-Z][^>]*>")


class SubtitleError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedCue:
    start_ms: int
    end_ms: int
    text: str


class _Timed(Protocol):
    start_ms: int
    end_ms: int
    text: str


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_to_ass(text: str) -> str:
    text = text.replace("{", "｛").replace("}", "｝").replace("\\", "＼")
    text = text.replace("<i>", r"{\i1}").replace("</i>", r"{\i0}")
    return text.replace("\n", r"\N")


def _italic_effect(match: re.Match[str]) -> str:
    block = match.group(0)
    if r"\i1" in block:
        return "<i>"
    if r"\i0" in block or re.search(r"\\i(?!\d)", block):
        return "</i>"
    return ""


def _balance_italics(text: str) -> str:
    out, depth = [], 0
    for part in re.split(r"(</?i>)", text):
        if part == "<i>":
            if depth:
                continue
            depth = 1
        elif part == "</i>":
            if not depth:
                continue
            depth = 0
        out.append(part)
    return "".join(out) + ("</i>" if depth else "")


def ass_to_canonical(text: str) -> str:
    text = text.replace(r"\N", "\n").replace(r"\n", "\n").replace(r"\h", " ")
    text = _ASS_TAG.sub(_italic_effect, text)
    text = _balance_italics(text)
    text = _HTML_TAG.sub("", text)
    return canonical(text)


def decode_text(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass
    best = from_bytes(data).best()
    if best is None:
        raise SubtitleError("couldn't work out this file's text encoding")
    return str(best)


def _ssafile(cues: Sequence[Cue]) -> pysubs2.SSAFile:
    subs = pysubs2.SSAFile()
    for c in cues:
        subs.append(pysubs2.SSAEvent(start=c.start_ms, end=c.end_ms, text=canonical_to_ass(c.text)))
    return subs


def _encode(text: str, bom: bool) -> bytes:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not text.endswith("\n"):
        text += "\n"
    return (b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8")


def to_srt(cues: Sequence[Cue], *, bom: bool = False) -> bytes:
    return _encode(_ssafile(cues).to_string("srt"), bom)


def _default_style() -> pysubs2.SSAStyle:
    return pysubs2.SSAStyle(
        fontname="Noto Sans CJK SC", fontsize=52,
        primarycolor=pysubs2.Color(255, 255, 255, 0), outlinecolor=pysubs2.Color(0, 0, 0, 0),
        backcolor=pysubs2.Color(0, 0, 0, 128), outline=3, shadow=0,
        alignment=pysubs2.Alignment.BOTTOM_CENTER, marginv=40)


def to_ass(cues: Sequence[Cue], *, existing: bytes | None = None, bom: bool = False) -> bytes:
    subs = _ssafile(cues)
    subs.info.update({"PlayResX": "1920", "PlayResY": "1080", "WrapStyle": "2",
                      "ScaledBorderAndShadow": "yes"})
    subs.styles["Default"] = _default_style()
    if existing is not None:
        old = pysubs2.SSAFile.from_string(decode_text(existing), format_="ass")
        subs.info = dict(old.info)
        subs.styles = dict(old.styles)
        subs.styles.setdefault("Default", _default_style())
        kept = [e for e in old.events if e.style != "Default"]
        subs.events = sorted(list(subs.events) + kept, key=lambda e: (e.start, e.end))
    return _encode(subs.to_string("ass"), bom)


def parse_subtitles(data: bytes, fmt: str | None = None, *,
                    default_style_only: bool = False) -> list[ParsedCue]:
    """The cues in a subtitle file, sorted by time.

    `default_style_only` reads only an ASS or SSA file's `Default` events, the ones vid2sub
    writes: signs and karaoke a person added in other styles aren't vid2sub's cues, so comparing
    them would turn them into dialogue (plan decision 6; final review). Imports keep every event.
    """
    text = decode_text(data)
    try:
        subs = pysubs2.SSAFile.from_string(text, format_=fmt)
    except Exception as err:  # noqa: BLE001 - pysubs2 raises several unrelated types
        raise SubtitleError(f"not a subtitle file vid2sub can read ({type(err).__name__})") from None
    only_default = default_style_only and subs.format in ("ass", "ssa")
    out = []
    for ev in subs.events:
        if ev.is_comment or (only_default and ev.style != "Default"):
            continue
        body = ass_to_canonical(ev.text)
        if body and ev.end > ev.start:
            out.append(ParsedCue(int(ev.start), int(ev.end), body))
    if not out and text.strip():
        raise SubtitleError("no subtitles found in this file")
    out.sort(key=lambda c: (c.start_ms, c.end_ms))
    return out


def same_cues(a: Sequence[_Timed], b: Sequence[_Timed], *, precision_ms: int) -> bool:
    if len(a) != len(b):
        return False
    return all(abs(x.start_ms - y.start_ms) < precision_ms
               and abs(x.end_ms - y.end_ms) < precision_ms
               and x.text == y.text for x, y in zip(a, b))
