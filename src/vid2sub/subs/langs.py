"""The languages vid2sub knows, and the name every tool uses for each (spec §2.2, §9.2, §11).

One table, so a language is added in one place. Codes are vid2sub's own: ISO 639-1 where one
exists, else ISO 639-3 (`yue`, Cantonese, which Whisper also calls `yue`). whisper.cpp's
verbose_json names languages in full ("cantonese"); Qwen3-ASR wants capitalised English names
("Cantonese"); media files tag tracks with ISO 639-2 (`jpn`, `chi`).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Lang:
    code: str
    name: str
    whisper_full: str
    qwen: str
    cjk: bool
    media_tags: tuple[str, ...]


LANGS: dict[str, Lang] = {
    lang.code: lang
    for lang in (
        Lang("en", "English", "english", "English", False, ("eng", "en")),
        Lang("ja", "Japanese", "japanese", "Japanese", True, ("jpn", "ja")),
        Lang("zh", "Mandarin", "chinese", "Chinese", True, ("chi", "zho", "cmn", "zh")),
        Lang("yue", "Cantonese", "cantonese", "Cantonese", True, ("yue",)),
        Lang("ko", "Korean", "korean", "Korean", True, ("kor", "ko")),
    )
}


class UnknownLanguage(ValueError):
    pass


def get(code: str) -> Lang:
    try:
        return LANGS[code]
    except KeyError:
        raise UnknownLanguage(
            f"unknown language {code!r}; known: {', '.join(LANGS)}") from None


def from_whisper_full(name: str) -> str | None:
    name = name.strip().lower()
    return next((lang.code for lang in LANGS.values() if lang.whisper_full == name), None)


def from_qwen(name: str) -> str | None:
    name = name.strip().lower()
    return next((lang.code for lang in LANGS.values() if lang.qwen.lower() == name), None)


def from_media_tag(tag: str | None) -> str | None:
    if not tag:
        return None
    tag = tag.strip().lower()
    return next((lang.code for lang in LANGS.values() if tag in lang.media_tags), None)
