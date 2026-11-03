"""The cache of playback audio and preview copies, one folder per video (spec §8.9).

Everything in it can be made again from the video, so it is disposable: capped by
`defaults.cache_max_gb`, least recently used first, and emptied by `vid2sub cache clear` (S46).
An entry is a folder named by the video's 64-hex `quick_sha256` (§8.3), made 0700 like a job's
scratch folder because it holds the user's audio; using an entry touches its folder, so the
folder's mtime is its last use. Eviction and `clear()` remove only folders with such names and
never follow a symlink, so a cache folder that is shared with, or points into, anything else
loses nothing but vid2sub's own entries (the playback audio moved here from M3: Dan, Q&A item 13).
"""

from __future__ import annotations

import os
import re
import shutil
import stat
from pathlib import Path

import platformdirs

from vid2sub.config import Config

GB = 1_000_000_000
_KEY = re.compile(r"[0-9a-f]{64}")


def default_root() -> Path:
    """`~/Library/Caches/vid2sub`, `%LOCALAPPDATA%\\vid2sub\\Cache` or `~/.cache/vid2sub`
    (spec §8.9); `$XDG_CACHE_HOME` wins where platformdirs honours it."""
    return Path(platformdirs.user_cache_dir("vid2sub", appauthor=False))


def from_config(config: Config, root: Path | None = None) -> Cache:
    return Cache(root or default_root(), max_bytes=int(config.defaults.cache_max_gb * GB))


class Cache:
    def __init__(self, root: Path, *, max_bytes: int):
        self.root = root
        self.max_bytes = max_bytes

    def folder(self, key: str) -> Path:
        """The entry for one video, made 0700 if it's new, and marked used."""
        if not _KEY.fullmatch(key):
            raise ValueError("a cache key is a video's 64-hex quick_sha256")
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = self.root / key
        if path.is_symlink():
            path.unlink()
        path.mkdir(mode=0o700, exist_ok=True)
        os.utime(path)
        return path

    def size(self) -> int:
        return sum(_bytes(p) for p in self._entries())

    def evict(self, *, keep: str | None = None) -> int:
        """Removes the least recently used entries, never `keep`, until the cache fits its cap;
        returns the bytes freed."""
        entries = sorted(self._entries(), key=lambda p: (p.lstat().st_mtime_ns, p.name))
        total = sum(_bytes(p) for p in entries)
        freed = 0
        for p in entries:
            if total - freed <= self.max_bytes:
                break
            if p.name != keep:
                freed += _remove(p)
        return freed

    def clear(self) -> int:
        """Removes every entry and nothing else; returns the bytes freed."""
        return sum(_remove(p) for p in self._entries())

    def _entries(self) -> list[Path]:
        try:
            found = list(self.root.iterdir())
        except OSError:  # no cache yet, or one this user can't read
            return []
        return [p for p in found if _KEY.fullmatch(p.name) and _is_real_dir(p)]


def _is_real_dir(path: Path) -> bool:
    try:
        return stat.S_ISDIR(path.lstat().st_mode)
    except OSError:
        return False


def _bytes(folder: Path) -> int:
    """The regular files under `folder`, never following a symlink."""
    total = 0
    for dirpath, _, names in os.walk(folder):
        for name in names:
            try:
                st = os.lstat(os.path.join(dirpath, name))
            except OSError:
                continue
            if stat.S_ISREG(st.st_mode):
                total += st.st_size
    return total


def _remove(folder: Path) -> int:
    """Removes one entry folder; shutil.rmtree unlinks symlinks inside it, never their targets."""
    before = _bytes(folder)
    shutil.rmtree(folder, ignore_errors=True)
    return before - (_bytes(folder) if folder.exists() else 0)
