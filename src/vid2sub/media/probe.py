"""Probing a video and picking its audio track (spec §8.2, §8.4, §8.5).

ffprobe gives the duration, the video codec and every audio stream with its language tag,
default flag and start time. Cover art (an attached picture) isn't the video. If the chosen audio
starts later than the earliest stream (an MKV audio delay, an MPEG-TS start time), the difference
is the timeline offset added to every word, so cues match what the player shows.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vid2sub.media.tools import Tools, input_args, run_tool
from vid2sub.subs import langs


class ProbeError(RuntimeError):
    pass


@dataclass(frozen=True)
class AudioTrack:
    index: int  # among audio streams: ffmpeg's a:N
    stream_index: int
    codec: str
    channels: int | None
    language: str | None
    tag: str | None
    default: bool
    start_ms: int


@dataclass(frozen=True)
class Probe:
    duration_ms: int
    container: str
    video_codec: str | None
    audio: tuple[AudioTrack, ...]
    min_start_ms: int


def _ms(value: Any) -> int | None:
    try:
        return round(float(value) * 1000)
    except (TypeError, ValueError):
        return None


def parse_probe(data: dict) -> Probe:
    fmt = data.get("format") or {}
    duration = _ms(fmt.get("duration"))
    starts: list[int] = []
    video: str | None = None
    audio: list[AudioTrack] = []
    for s in data.get("streams") or []:
        kind = s.get("codec_type")
        disposition = s.get("disposition") or {}
        start = _ms(s.get("start_time"))
        if kind == "video" and not disposition.get("attached_pic"):
            video = video or s.get("codec_name")
            if start is not None:
                starts.append(start)
        elif kind == "audio":
            tag = (s.get("tags") or {}).get("language")
            audio.append(AudioTrack(
                index=len(audio), stream_index=int(s["index"]),
                codec=str(s.get("codec_name", "")), channels=s.get("channels"),
                language=langs.from_media_tag(tag), tag=tag,
                default=bool(disposition.get("default")), start_ms=start or 0))
            if start is not None:
                starts.append(start)
    if duration is None:
        raise ProbeError("couldn't read this file's duration")
    if not audio:
        raise ProbeError("this file has no audio track")
    return Probe(duration, str(fmt.get("format_name", "")), video, tuple(audio),
                 min(starts) if starts else 0)


def probe(path: Path, tools: Tools, *, scratch: Path) -> Probe:
    proc = run_tool([tools.need("ffprobe"), "-v", "error", *input_args(path), "-show_format",
                     "-show_streams", "-of", "json"], cwd=scratch, timeout=120)
    try:
        data = json.loads(proc.stdout)
    except ValueError:
        raise ProbeError("ffprobe's answer wasn't JSON") from None
    return parse_probe(data)


def pick_track(p: Probe, lang: str | None, override: int | str | None = None) -> AudioTrack:
    if isinstance(override, int):
        if not 0 <= override < len(p.audio):
            raise ProbeError(f"there's no audio track {override}; this file has {len(p.audio)}")
        return p.audio[override]
    wanted = override if isinstance(override, str) else lang
    if wanted:
        for track in p.audio:
            if track.language == wanted:
                return track
        if isinstance(override, str):
            raise ProbeError(f"no audio track is tagged {override}")
    return next((t for t in p.audio if t.default), p.audio[0])


def timeline_offset_ms(p: Probe, track: AudioTrack) -> int:
    return max(0, track.start_ms - p.min_start_ms)
