"""A video's identity: size plus a quick hash of its ends (spec §8.3).

Hashing a multi-GB file over SMB on every open is impractical, so a video is known by its size
and a SHA-256 of its size, first MiB and last MiB. The full SHA-256 is computed by streaming
during a job and appended to the sidecar.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

MIB = 1 << 20


@dataclass(frozen=True)
class VideoIdentity:
    size: int
    quick_sha256: str


def quick_sha256(path: Path) -> str:
    size = path.stat().st_size
    h = hashlib.sha256(size.to_bytes(8, "big"))
    with path.open("rb") as f:
        h.update(f.read(MIB))
        if size > MIB:
            f.seek(max(MIB, size - MIB))
            h.update(f.read(MIB))
    return h.hexdigest()


def full_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(MIB):
            h.update(chunk)
    return h.hexdigest()


def identify(path: Path) -> VideoIdentity:
    return VideoIdentity(size=path.stat().st_size, quick_sha256=quick_sha256(path))
