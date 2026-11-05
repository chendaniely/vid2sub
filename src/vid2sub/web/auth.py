"""The launch token: only the browser vid2sub opened, holding the cookie it got for the token,
reaches the engine (spec §6.1).

As Jupyter does (the council's red team, spec §27). Each launch makes a token and opens the
browser through a redirect file (mode 0600, in a 0700 folder) that goes to `/auth#t=<token>`.
The token is in the fragment, which a browser never sends, so it reaches no request line, no
server log and no command line (`ps` shows only the file's path). The `/auth` page's script, a
file because the CSP allows no inline script, posts it back and gets an `HttpOnly`,
`SameSite=Strict` cookie named for the port, so launches on two ports don't clobber each other.
The cookie's value is an HMAC of the token, so the token itself is in no response either.

TokenGuard asks every other request and every websocket handshake for that cookie. A restart
makes a new token, so a tab left open is refused and told to open the new link (Review Focus 5).
No `Secure` flag: the engine is plain http on 127.0.0.1. Cookies ignore ports, so the cookie
alone doesn't keep out a page on another port of this machine; HostGuard and WriteGuard do
(spec §6.2).
"""

from __future__ import annotations

import hashlib
import hmac
import html
import json
import os
import secrets
import tempfile
from pathlib import Path

from starlette.requests import Request
from starlette.responses import FileResponse, PlainTextResponse, Response
from starlette.routing import BaseRoute, Route
from starlette.types import ASGIApp, Receive, Scope, Send

STATIC = Path(__file__).parent / "static"
# Method and path pairs, matched exactly, never as prefixes: /auth/x or /healthz/../ needs the
# cookie like any path, and so does a method these routes don't answer, which would fall through
# to whatever is mounted at / (spec §6.1). HEAD rides on GET for Starlette's routes; /healthz is
# the app's own, which answers GET only.
OPEN_ROUTES = frozenset({
    ("GET", "/auth"), ("HEAD", "/auth"), ("POST", "/auth"),
    ("GET", "/auth.js"), ("HEAD", "/auth.js"),
    ("GET", "/healthz"),
})
POLICY_VIOLATION = 1008  # RFC 6455 close code
SIGN_IN_AGAIN = "open the link vid2sub printed when it started"
MAX_BODY = 1024  # bytes; {"token": "<43 characters>"} is 56
_MALFORMED = 'send {"token": "<the token>"} as JSON'


def new_token() -> str:
    """A fresh launch token: 256 random bits in 43 URL-safe characters."""
    return secrets.token_urlsafe(32)


def cookie_name(port: int) -> str:
    """The launch cookie's name, which names the port."""
    return f"vid2sub-{port}"


def auth_url(port: int, token: str) -> str:
    """The link that signs a browser in, with the token only in the fragment."""
    return f"http://127.0.0.1:{port}/auth#t={token}"


def _cookie_value(token: str) -> str:
    return hmac.new(token.encode(), b"vid2sub launch cookie", hashlib.sha256).hexdigest()


def write_redirect(url: str) -> Path:
    """Write a page that sends the browser to `url`, in a new private folder, and return its path.

    It is opened as a file, where no CSP applies, so it has no script: a meta refresh, and a link
    for a browser that ignores it. The folder is the caller's to remove when the engine exits.
    """
    folder = Path(tempfile.mkdtemp(prefix="vid2sub-"))  # mode 0700 (the tempfile docs)
    page = folder / "open.html"
    href = html.escape(url, quote=True)
    text = (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        f'<meta http-equiv="refresh" content="0;url={href}">\n'
        "<title>vid2sub</title>\n</head>\n"
        f'<body><p><a href="{href}">Open vid2sub</a></p></body>\n</html>\n'
    )
    fd = os.open(page, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    return page


def routes(token: str, port: int) -> list[BaseRoute]:
    """`GET /auth` (the page), `GET /auth.js` (its script) and `POST /auth` (the token for the
    cookie), to register before anything mounted at `/`."""
    expected = token.encode()
    name = cookie_name(port)
    value = _cookie_value(token)

    def page(request: Request) -> Response:
        return FileResponse(STATIC / "auth.html", media_type="text/html")

    def script(request: Request) -> Response:
        return FileResponse(STATIC / "auth.js", media_type="application/javascript")

    async def sign_in(request: Request) -> Response:
        try:
            data = json.loads(await request.body())
        except ValueError:  # not JSON, or not UTF-8; MAX_BODY keeps nesting far from the limit
            return PlainTextResponse(_MALFORMED, status_code=400)
        given = data.get("token", "") if isinstance(data, dict) else None  # missing: no match
        if not isinstance(given, str):
            return PlainTextResponse(_MALFORMED, status_code=400)
        if not secrets.compare_digest(
            given.encode("utf-8", "surrogatepass"), expected  # bytes: any text compares
        ):
            return PlainTextResponse("this link is out of date", status_code=403)
        response = Response(status_code=204)
        response.set_cookie(name, value, path="/", httponly=True, samesite="strict")
        return response

    return [
        Route("/auth", page, methods=["GET"]),
        Route("/auth", sign_in, methods=["POST"], max_body_size=MAX_BODY),
        Route("/auth.js", script, methods=["GET"]),
    ]


class TokenGuard:
    """Pure ASGI middleware: every HTTP request and websocket handshake needs this launch's
    cookie, except HTTP requests for the open paths, matched exactly. Lifespan passes through."""

    def __init__(self, app: ASGIApp, *, token: str, port: int) -> None:
        self.app = app
        self._name = cookie_name(port)
        self._value = _cookie_value(token).encode()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            await self.app(scope, receive, send)
            return
        if scope["type"] not in ("http", "websocket"):  # a type no guard knows: fail closed
            return
        if (
            scope["type"] == "http" and (scope["method"], scope["path"]) in OPEN_ROUTES
        ) or self._signed_in(scope):
            await self.app(scope, receive, send)
            return
        if scope["type"] == "http":
            await PlainTextResponse(SIGN_IN_AGAIN, status_code=401)(scope, receive, send)
        elif (await receive())["type"] == "websocket.connect":
            # Refuse the handshake without accepting (the server answers 403), as HostGuard does.
            await send({"type": "websocket.close", "code": POLICY_VIOLATION})

    def _signed_in(self, scope: Scope) -> bool:
        """Whether any cookie of this launch's name holds its value. Every one is checked: a page
        on another port can plant a cookie of the same name beside the real one."""
        found = False
        for key, raw in scope["headers"]:
            if key != b"cookie":
                continue
            for pair in raw.decode("latin-1").split(";"):
                name, sep, value = pair.strip().partition("=")
                if sep and name == self._name:
                    found |= secrets.compare_digest(value.strip().encode("latin-1"), self._value)
        return found
