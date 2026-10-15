"""Lint flags and known hallucinations (spec §12.4, §12.5).

Lint flags are recomputed whenever they're shown, never stored as truth. Hallucination phrases are
the lines Whisper-family models invent over silence and music, per language; English ones are
checked in every language because they turn up everywhere. A flagged cue is shown, never deleted.
"""

from __future__ import annotations

from collections.abc import Sequence

from vid2sub.subs.model import Cue
from vid2sub.subs.rules import CueRules, cps
from vid2sub.subs.text import unwrap, width

HALLUCINATION_PHRASES: dict[str, tuple[str, ...]] = {
    "en": ("thank you for watching", "thanks for watching", "please subscribe",
           "subtitles by the amara.org community"),
    "ja": ("ご視聴ありがとうございました", "チャンネル登録をお願いします"),
    "zh": ("字幕由amara.org社区提供", "请不吝点赞", "谢谢观看", "感谢观看"),
    "yue": ("字幕由amara.org社區提供", "多謝收睇", "多謝收看"),
    "ko": ("시청해 주셔서 감사합니다",),
}


def looks_hallucinated(text: str, lang: str) -> bool:
    norm = unwrap(text).lower()
    phrases = HALLUCINATION_PHRASES.get(lang, ()) + HALLUCINATION_PHRASES["en"]
    return any(phrase in norm for phrase in phrases)


def lint(cues: Sequence[Cue], rules: CueRules) -> dict[str, tuple[str, ...]]:
    out: dict[str, tuple[str, ...]] = {}
    for c in cues:
        flags: list[str] = []
        lines = c.text.split("\n")
        if len(lines) > rules.max_lines or any(width(line) > rules.max_width for line in lines):
            flags.append("width")
        duration = c.end_ms - c.start_ms
        if duration < rules.min_ms or duration > rules.max_ms:
            flags.append("duration")
        if cps(c.text, duration) > rules.cps:
            flags.append("cps")
        if flags:
            out[c.id] = tuple(flags)
    return out
