"""YouTube videos through yt-dlp, audio only unless asked (spec §8.1, §6.7).

yt-dlp runs as `python -m yt_dlp` from vid2sub's own environment, locked down: no config files
(which can set --exec), no plugins, the YouTube extractor only (so a URL can't reach the generic
extractor and the LAN), one video, output named by id inside the job's scratch folder, and the URL
after `--` (ids can start with `-`). The file is then moved into the YouTube folder under a safe
name, `<title> [<id>].<ext>`, and an existing download of the same id is reused. YouTube needs
deno (yt-dlp's only default JavaScript runtime). This is the first real YouTube source in Dan's
projects; recordings' Stage 5 can copy it (spec §26.2).
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from vid2sub.media.tools import ToolFailed, Tools, run_tool
from vid2sub.security import safe_component

YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com",
                 "youtu.be"}
_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
UPGRADE_HINT = "upgrade yt-dlp: uv tool upgrade vid2sub --upgrade-package yt-dlp"


class NotYouTube(ValueError):
    pass


class YouTubeError(RuntimeError):
    def __init__(self, kind: str, message: str, hint: str = ""):
        self.kind, self.hint = kind, hint
        super().__init__(message)


@dataclass(frozen=True)
class Fetched:
    path: Path
    video_id: str
    title: str
    published: str | None


def is_url(value: str) -> bool:
    return value.startswith(("http://", "https://"))


def video_id(url: str) -> str:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.scheme not in ("http", "https") or host not in YOUTUBE_HOSTS:
        raise NotYouTube("only YouTube links are supported")
    segments = [s for s in parts.path.split("/") if s]
    if host == "youtu.be":
        vid = segments[0] if segments else ""
    elif parts.path == "/watch":
        vid = (parse_qs(parts.query).get("v") or [""])[0]
    elif len(segments) >= 2 and segments[0] in ("shorts", "live", "embed"):
        vid = segments[1]
    else:
        vid = ""
    if not _ID.fullmatch(vid):
        raise NotYouTube("that link doesn't name one YouTube video")
    return vid


def canonical_url(vid: str) -> str:
    return f"https://www.youtube.com/watch?v={vid}"


def find_existing(out_dir: Path, vid: str) -> Path | None:
    if not out_dir.is_dir():
        return None
    suffix = f"[{vid}]"
    return next((p for p in sorted(out_dir.iterdir()) if p.is_file() and p.stem.endswith(suffix)),
                None)


def download(url: str, *, out_dir: Path, scratch: Path, keep_video: bool, tools: Tools,
             runner: Callable = run_tool, timeout: float = 3600) -> Fetched:
    vid = video_id(url)
    existing = find_existing(out_dir, vid)
    if existing is not None:
        return Fetched(existing, vid, existing.stem.rsplit(" [", 1)[0], None)
    tools.need("deno")
    args = [sys.executable, "-m", "yt_dlp", "--ignore-config", "--no-plugin-dirs",
            "--use-extractors", "youtube", "--no-playlist", "--no-progress",
            "--no-js-runtimes", "--js-runtimes", f"deno:{tools.deno}",
            "-f", "bv*+ba/b" if keep_video else "bestaudio/best",
            "-P", str(scratch), "-o", "%(id)s.%(ext)s",
            "--print", "after_move:%(.{id,title,upload_date,filepath})j"]
    if tools.ffmpeg:
        args += ["--ffmpeg-location", tools.ffmpeg]
    args += ["--", canonical_url(vid)]
    try:
        proc = runner(args, cwd=scratch, timeout=timeout)
    except ToolFailed as err:
        text = err.stderr.lower()
        if "not a bot" in text or "sign in" in text:
            raise YouTubeError("bot_check", "YouTube asked to confirm this isn't a bot",
                               UPGRADE_HINT) from None
        raise YouTubeError("failed", "yt-dlp couldn't download that video", UPGRADE_HINT) \
            from None
    info = json.loads(proc.stdout.decode("utf-8").strip().splitlines()[-1])
    src = Path(info["filepath"])
    if src.parent.resolve() != scratch.resolve():
        raise YouTubeError("failed", "yt-dlp wrote outside the scratch folder")
    title = str(info.get("title") or vid)
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"{safe_component(title)} [{vid}]{src.suffix}"
    if dest.exists():
        raise YouTubeError("failed", f"{dest.name} appeared while downloading; try again")
    shutil.move(src, dest)
    return Fetched(dest, vid, title, info.get("upload_date"))
