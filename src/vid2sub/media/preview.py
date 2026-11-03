"""The playback audio: an episode's audio as AAC stereo, for a browser that can't play it (§8.8).

A browser plays neither AC-3, E-AC-3, DTS nor TrueHD, and silent playback is worse than none
(§8.2), so the editor plays this `.m4a` instead, made on demand into the cache (§8.9) the first
time an episode needs it and reused after that (Dan, 2026-10-14; Q&A item 13 brought it into
Phase 2, S43). Only the chosen audio track is kept, with no video, subtitles, data, metadata or
chapters, so the show's title never reaches the file, as with chunks (§7.3); `+faststart` puts
the index first so playback starts before the whole file is read. ffmpeg writes to a temporary
name in the entry's folder and the result is renamed into place, so a half-made file is never
served; the entry just made is kept by the eviction that follows it, though an entry another
call is still making isn't protected yet (the Phase-end list).
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from vid2sub.cache import Cache
from vid2sub.media.tools import Tools, input_args, run_tool


def playback_audio(video: Path, *, key: str, audio_index: int, tools: Tools, cache: Cache,
                   timeout: float) -> Path:
    """`audio_index` counts audio tracks only (ffmpeg's `a:N`, `probe.AudioTrack.index`)."""
    if isinstance(audio_index, bool) or not isinstance(audio_index, int) or audio_index < 0:
        raise ValueError("an audio track is a number from 0")
    folder = cache.folder(key)
    out = folder / f"playback-a{audio_index}.m4a"
    if out.is_file():
        return out
    tmp = folder / f".playback-a{audio_index}-{secrets.token_hex(4)}.part"
    try:
        run_tool([tools.need("ffmpeg"), "-nostdin", "-hide_banner", "-loglevel", "error",
                  *input_args(video), "-map", f"0:a:{audio_index}", "-vn", "-sn", "-dn",
                  "-ac", "2", "-c:a", "aac", "-b:a", "160k", "-map_metadata", "-1",
                  "-map_chapters", "-1", "-fflags", "+bitexact", "-movflags", "+faststart",
                  "-f", "mp4", str(tmp)], cwd=folder, timeout=timeout)
        os.replace(tmp, out)
    finally:
        tmp.unlink(missing_ok=True)
    cache.evict(keep=key)
    return out
