"""Cue rules per language (spec §12.2), defaulting to Netflix's timed-text style guides.

Width is in East Asian Width units (Task 3): English 42; Japanese 26 (13 full-width); Chinese and
Cantonese 32 (16). Reading speed (characters per second) only extends cues into gaps and lints;
it never splits or merges (spec §12.2), because verbatim Japanese can't meet 4 cps. The rules'
hash goes into cue versions, so changing a rule mints a new version.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class CueRules:
    max_width: int
    cps: float
    max_lines: int = 2
    min_ms: int = 833
    max_ms: int = 7000
    min_gap_ms: int = 84  # two frames at 23.976 fps
    close_gap_ms: int = 500
    pause_ms: int = 700  # a longer silence ends a phrase

    def sha(self) -> str:
        blob = json.dumps(asdict(self), sort_keys=True).encode()
        return hashlib.sha256(blob).hexdigest()[:8]


RULES: dict[str, CueRules] = {
    "en": CueRules(max_width=42, cps=20.0),
    "ja": CueRules(max_width=26, cps=4.0),
    "zh": CueRules(max_width=32, cps=9.0),
    "yue": CueRules(max_width=32, cps=9.0),
    "ko": CueRules(max_width=32, cps=12.0),
}


def rules_for(lang: str) -> CueRules:
    return RULES.get(lang, RULES["en"])


def reading_chars(text: str) -> int:
    return len(text.replace("\n", ""))


def cps(text: str, duration_ms: int) -> float:
    return reading_chars(text) * 1000 / max(duration_ms, 1)


def width_chars(rules: CueRules, cjk: bool) -> int:
    """Characters per line: half the width for full-width text."""
    return rules.max_width // 2 if cjk else rules.max_width
