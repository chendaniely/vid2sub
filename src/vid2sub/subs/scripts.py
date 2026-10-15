"""Traditional and Simplified Chinese, converted with OpenCC (spec §11.3).

Whisper writes Chinese in either script, so source tracks are converted to the track's script
after cues are built: on cue text, never on words, because conversion can change text length.
opencc-purepy is pure Python (it runs in Pyodide); it sits behind this module so it can be
swapped (council, 2026-10-14: it has one maintainer).
"""

from __future__ import annotations

from collections.abc import Sequence
from functools import cache

from opencc_purepy import OpenCC

from vid2sub.subs.model import Cue

CONFIG_FOR_TRACK: dict[str, str] = {"zh-Hans": "t2s", "zh-Hant": "s2tw", "yue-Hant": "s2hk"}


@cache
def _converter(config: str) -> OpenCC:
    return OpenCC(config)


def config_for(track_key: str) -> str | None:
    return CONFIG_FOR_TRACK.get(track_key)


def convert(text: str, config: str) -> str:
    return _converter(config).convert(text)


def convert_cues(cues: Sequence[Cue], config: str) -> list[Cue]:
    return [c.model_copy(update={"text": convert(c.text, config)}) for c in cues]
