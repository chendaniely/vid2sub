"""Finding and running ffmpeg, ffprobe and deno (spec §6.7, §4.2).

Every child process runs through `run_tool`: an absolute executable (never found in the current
directory, which Windows would otherwise search first), an argument list with no shell, `cwd` set
to the job's scratch folder, an allowlisted environment so it never inherits a key, and a
timeout. ffmpeg and ffprobe read input only through the `file` protocol and a demuxer allowlist,
so a playlist disguised as `.mp4` can neither fetch URLs nor read other files. Homebrew's folders
are a fallback because launchd's PATH doesn't include them (an audio-router lesson).
"""

from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from vid2sub.security import child_env

FALLBACK_DIRS = ("/opt/homebrew/bin", "/usr/local/bin", "/usr/bin")
FORMAT_WHITELIST = ("matroska,webm,mov,mp4,m4a,3gp,3g2,mj2,avi,mpegts,flv,ogg,wav,flac,mp3,aac,"
                    "asf,aiff,w64,caf")
_HINTS = {
    "ffmpeg": "install ffmpeg 6 or later (macOS: brew install ffmpeg; Windows: winget install "
              "Gyan.FFmpeg; Linux: your package manager)",
    "ffprobe": "ffprobe comes with ffmpeg: install ffmpeg 6 or later",
    "deno": "install deno 2.3 or later (https://deno.com): yt-dlp needs it for YouTube",
}


class ToolMissing(RuntimeError):
    def __init__(self, name: str):
        self.name = name
        self.hint = _HINTS.get(name, f"install {name}")
        super().__init__(f"{name} isn't installed: {self.hint}")


class ToolFailed(RuntimeError):
    def __init__(self, tool: str, returncode: int, stderr: str):
        self.tool, self.returncode, self.stderr = tool, returncode, stderr
        super().__init__(f"{tool} failed (exit {returncode})")


def which(name: str, path: str | None = None) -> str | None:
    search = os.environ.get("PATH", "") if path is None else path
    dirs = [d for d in search.split(os.pathsep) if d and os.path.isabs(d)]
    if os.name != "nt":
        dirs += [d for d in FALLBACK_DIRS if d not in dirs]
    exts = os.environ.get("PATHEXT", ".EXE;.BAT;.CMD").split(";") if os.name == "nt" else [""]
    for d in dirs:
        for ext in exts:
            candidate = os.path.join(d, name + ext)
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate
    return None


@dataclass(frozen=True)
class Tools:
    ffmpeg: str | None
    ffprobe: str | None
    deno: str | None

    @classmethod
    def find(cls) -> Tools:
        return cls(which("ffmpeg"), which("ffprobe"), which("deno"))

    def need(self, name: str) -> str:
        exe = getattr(self, name)
        if not exe:
            raise ToolMissing(name)
        return exe


def run_tool(args: Sequence[str], *, cwd: Path, timeout: float, stdin: bytes | None = None,
             check: bool = True) -> subprocess.CompletedProcess[bytes]:
    if not os.path.isabs(args[0]):
        raise ValueError("run_tool needs an absolute executable path")
    name = Path(args[0]).name
    try:
        proc = subprocess.run(list(args), check=False, cwd=cwd, env=child_env(), input=stdin,
                              capture_output=True, timeout=timeout, shell=False)
    except subprocess.TimeoutExpired:
        raise ToolFailed(name, -1, f"timed out after {timeout:.0f} s") from None
    if check and proc.returncode != 0:
        raise ToolFailed(name, proc.returncode,
                         proc.stderr[-4000:].decode("utf-8", errors="replace"))
    return proc


def input_args(path: Path) -> list[str]:
    return ["-protocol_whitelist", "file", "-format_whitelist", FORMAT_WHITELIST,
            "-i", f"file:{path}"]


def version(exe: str) -> tuple[int, ...] | None:
    """ffmpeg answers `-version`; deno answers `--version`."""
    for flag in ("-version", "--version"):
        try:
            proc = subprocess.run([exe, flag], check=False, capture_output=True, timeout=30,
                                  env=child_env())
        except (OSError, subprocess.TimeoutExpired):
            return None
        if proc.returncode == 0:
            first = proc.stdout.decode("utf-8", errors="replace").splitlines()[:1]
            match = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", first[0]) if first else None
            return tuple(int(g) for g in match.groups() if g is not None) if match else None
    return None
