"""Tracks, their file codes, and the names of the files next to a video (spec §15.1, §14.1).

A track is keyed by BCP-47 (`yue-Hant`); its file code is what Plex and Jellyfin recognise.
Jellyfin doesn't know `yue` and Plex documents ISO 639-1/2, so Cantonese files are `.zh-HK`
(council, 2026-10-14); `yue` stays in the sidecar. Cantonese is Traditional only in v1 (plan
decision 7).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePath

GLOSSARY_NAME = "vid2sub.glossary.toml"
SIDECAR_SUFFIX = ".vid2sub.jsonl"


@dataclass(frozen=True)
class TrackInfo:
    key: str
    lang: str
    script: str | None
    file_code: str


TRACKS: dict[str, TrackInfo] = {
    t.key: t
    for t in (
        TrackInfo("en", "en", None, "en"),
        TrackInfo("ja", "ja", None, "ja"),
        TrackInfo("ko", "ko", None, "ko"),
        TrackInfo("zh-Hans", "zh", "Hans", "zh-CN"),
        TrackInfo("zh-Hant", "zh", "Hant", "zh-TW"),
        TrackInfo("yue-Hant", "yue", "Hant", "zh-HK"),
    )
}
_ALIASES = {"zh": "zh-Hans", "yue": "yue-Hant", "eng": "en", "jpn": "ja", "kor": "ko",
            "chi": "zh-Hans", "zho": "zh-Hans"}


class UnknownTrack(ValueError):
    pass


def track(key: str) -> TrackInfo:
    try:
        return TRACKS[key]
    except KeyError:
        raise UnknownTrack(f"unknown track {key!r}; known: {', '.join(TRACKS)}") from None


def source_track(lang: str, script: str | None) -> str:
    if lang == "zh":
        return "zh-Hant" if script == "hant" else "zh-Hans"
    if lang == "yue":
        if script == "hans":
            raise UnknownTrack("Cantonese subtitles are Traditional only in this version")
        return "yue-Hant"
    return track(lang).key


def target_track(value: str) -> str:
    lowered = value.strip().lower()
    for key in TRACKS:
        if key.lower() == lowered:
            return key
    if lowered in _ALIASES:
        return _ALIASES[lowered]
    raise UnknownTrack(f"unknown target {value!r}; known: {', '.join(TRACKS)}")


def stem(video_name: str) -> str:
    return PurePath(video_name).stem


def subtitle_name(video_name: str, track_key: str, fmt: str, *,
                  sdh: bool = False, forced: bool = False) -> str:
    parts = [stem(video_name), track(track_key).file_code]
    if sdh:
        parts.append("sdh")
    if forced:
        parts.append("forced")
    return ".".join(parts) + f".{fmt}"


def sidecar_name(video_name: str) -> str:
    return stem(video_name) + SIDECAR_SUFFIX


def track_from_subtitle_name(video_name: str, sub_name: str) -> str | None:
    base = stem(video_name) + "."
    sub_stem = PurePath(sub_name).stem
    if not sub_stem.startswith(base):
        return None
    code = sub_stem[len(base):].split(".")[0].lower()
    for info in TRACKS.values():
        if info.file_code.lower() == code or info.key.lower() == code:
            return info.key
    return _ALIASES.get(code)
