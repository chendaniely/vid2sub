"""Media tokens and `/media/{token}`: the browser plays a video, or its playback audio, by an
unguessable token, never by its path (spec §6.3, §6.5).

A token is `secrets.token_urlsafe(32)`, bound to the engine's launch rather than a Shiny session,
because a `/media/` request carries only the launch cookie (plan Decision 1). Tokens live in
memory, so they die with the engine, and closing an episode revokes its own (`revoke_owner`).
Only an absolute path to a regular audio or video file is issued one, as recordings' media route
allowed only audio and video: never a page or an SVG served from the engine's origin. Each token
records the file's (device, inode, size), so a file replaced or rewritten since is never served.
Paths reach no URL, header, error message or log (spec §6.8). A token is looked up in a dict:
its hash reveals nothing usable about 256 random bits, so no constant-time compare is needed.

Starlette's FileResponse answers Range with 206 and a range past the end with 416. It opens the
file by path just after the check, so a swap in that instant isn't caught; whoever can do that
can already write the user's files. WriteGuard adds /media/'s headers (spec §6.3).
"""

from __future__ import annotations

import os
import secrets
import stat
import threading
from dataclasses import dataclass
from pathlib import Path

from starlette.requests import Request
from starlette.responses import FileResponse, PlainTextResponse, Response
from starlette.routing import BaseRoute, Route
from starlette.types import Receive, Scope, Send

# One fixed table, never the OS's: Python's mimetypes reads the host's own files (and, on Windows,
# the registry), so a type came and went with the machine. The keys are exactly the suffixes the
# pipeline accepts (pipeline.MEDIA_SUFFIXES; a test pins it). Each type is the IANA registry's
# (https://www.iana.org/assignments/media-types/) where it has one, else CPython 3.14's built-in
# `mimetypes` defaults; `.mkv` and `.m4a` are fixed by the plan.
_TYPES = {
    ".mkv": "video/x-matroska",  # plan (the registry has video/matroska, CPython the same)
    ".mp4": "video/mp4",  # IANA
    ".m4v": "video/x-m4v",  # CPython's built-in table; not in IANA
    ".mov": "video/quicktime",  # IANA
    ".webm": "video/webm",  # CPython's built-in table; not in IANA
    ".avi": "video/vnd.avi",  # CPython's built-in table; not in IANA
    ".ts": "video/MP2T",  # IANA (CPython's built-in table has none)
    ".m2ts": "video/MP2T",  # IANA (CPython's built-in table has none)
    ".wmv": "video/x-ms-wmv",  # CPython's built-in table; not in IANA
    ".mp3": "audio/mpeg",  # IANA
    ".m4a": "audio/mp4",  # plan (IANA: audio/mp4)
    ".aac": "audio/aac",  # IANA
    ".flac": "audio/flac",  # IANA
    ".wav": "audio/vnd.wave",  # CPython's built-in table; not in IANA's audio list
    ".ogg": "audio/ogg",  # IANA
    ".opus": "audio/opus",  # IANA
}


def media_type(path: Path) -> str | None:
    """The type `/media/` serves `path` as, from its plain suffix: audio/* or video/*, else None.
    A name is never parsed as a URL, and a compressed name (`.mp4.gz`) is None: the browser would
    get the archive's bytes."""
    return _TYPES.get(path.suffix.lower())


def _identity(st: os.stat_result) -> tuple[int, int, int]:
    return (st.st_dev, st.st_ino, st.st_size)


@dataclass(frozen=True)
class _Issued:
    path: Path
    owner: str
    media_type: str
    identity: tuple[int, int, int]  # (st_dev, st_ino, st_size) when issued


class MediaTokens:
    """The media tokens this launch has issued. Thread-safe: the editor's session issues and
    revokes them while the route resolves them in a worker thread."""

    def __init__(self) -> None:
        self._issued: dict[str, _Issued] = {}
        self._lock = threading.Lock()

    def issue(self, path: Path, *, owner: str) -> str:
        """A new token for `path`, revoked with `owner` (the episode's id). `path` must be an
        absolute path to a regular audio or video file; otherwise ValueError, naming no path."""
        if not path.is_absolute():
            raise ValueError("a media path must be absolute")
        kind = media_type(path)
        if kind is None:
            raise ValueError("not an audio or video file")
        try:
            st = os.stat(path)  # follows a symlink: the identity is the file it points at
        except (OSError, ValueError):  # missing, unreadable, or a NUL in the name
            raise ValueError("the media file can't be read") from None
        if not stat.S_ISREG(st.st_mode):
            raise ValueError("not a regular file")
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._issued[token] = _Issued(path, owner, kind, _identity(st))
        return token

    def resolve(self, token: str) -> Path | None:
        """The file `token` serves, or None when it is unknown, revoked, or the file was replaced,
        resized or removed since it was issued."""
        live = self._live(token)
        return live[0].path if live else None

    def revoke_owner(self, owner: str) -> None:
        """Revoke every token issued for `owner`."""
        with self._lock:
            self._issued = {t: i for t, i in self._issued.items() if i.owner != owner}

    def _live(self, token: str) -> tuple[_Issued, os.stat_result] | None:
        with self._lock:
            issued = self._issued.get(token)
        if issued is None:
            return None
        try:
            st = os.stat(issued.path)  # outside the lock: a network share can be slow
        except (OSError, ValueError):
            return None
        if not stat.S_ISREG(st.st_mode) or _identity(st) != issued.identity:
            return None
        return issued, st


class MediaUnreadable(Exception):
    """The file couldn't be read once the response had started. Carries no path (spec §6.8)."""


class _PathFreeFileResponse(FileResponse):
    """A FileResponse whose failures name no file. Starlette opens the file by path after the
    route's check, and its OSError or "shorter than expected" RuntimeError carries that path into
    the server's error log. The headers are already sent by then, so the connection just ends."""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        failed = False
        try:
            await super().__call__(scope, receive, send)
        except (OSError, RuntimeError):
            failed = True
        if failed:  # raised outside the except block: no chained exception can carry the path
            raise MediaUnreadable("the media file could not be read")


def route(tokens: MediaTokens) -> BaseRoute:
    """`GET /media/{token}` (HEAD too): the file inline, with Range; 404 for a token that isn't
    live. A plain function, so Starlette runs it in a worker thread and the stat never blocks the
    event loop."""

    def serve(request: Request) -> Response:
        live = tokens._live(request.path_params["token"])
        if live is None:
            return PlainTextResponse("not found", status_code=404)
        issued, st = live
        # FileResponse writes Content-Disposition only with a filename, which would put the
        # video's title in a header; `inline` alone names nothing. The checked stat is passed
        # on, so Content-Length is the size that was checked.
        return _PathFreeFileResponse(
            issued.path,
            media_type=issued.media_type,
            stat_result=st,
            headers={"Content-Disposition": "inline"},
        )

    return Route("/media/{token}", serve, methods=["GET"])
