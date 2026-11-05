# Copied from recordings, packages/ui/src/recordings_ui/hosts.py at 8deb039, and relicensed under
# this repo's MIT licence (Dan owns both; spec §4.4). Changed here: the headers every response
# carries (the spec's whole CSP, and /media/'s own set), which now replace any the app set; the
# docstrings; recordings' notes on TLS proxies and its upload exemption are left out.
"""The engine answers only to its own names, takes writes only from its own pages, and sends the
security headers on every response (spec §6.2, §6.3).

The engine is a local server that reads files and holds API keys, and every website open in the
browser can reach 127.0.0.1. Other ports on this machine count as the same site, so cookies alone
don't keep them out (the council's red team, spec §27). The guards are copied from `recordings`,
which has the same threat model:

- **DNS rebinding:** a website points its own name at 127.0.0.1, then reads the engine as "same
  origin". The request still carries the website's name in `Host`: HostGuard answers 400.
- **Cross-site websockets:** browsers let any page open a websocket to any address, and send that
  page's `Origin`. HostGuard closes the handshake (1008) before accepting it unless `Origin` is
  exactly the engine's own (scheme, name and port) and the browser doesn't mark it as sent by
  another site.
- **Cross-site writes:** WriteGuard refuses every method but GET, HEAD and OPTIONS unless it is
  from this origin (or from no browser) and carries exactly `Content-Type: application/json`,
  which no page can send to another origin without a CORS preflight the engine never answers.

Every response, refusals included, carries the CSP below, `X-Frame-Options: DENY`,
`Cross-Origin-Resource-Policy`, `Cross-Origin-Opener-Policy` and `Referrer-Policy`. A response
under `/media/` carries `MEDIA_HEADERS` instead of the page CSP. These replace any header of the
same name the app set, so no route can weaken them. The engine binds 127.0.0.1 only (§6.1), behind
no proxy.
"""

from __future__ import annotations

from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
POLICY_VIOLATION = 1008  # RFC 6455 close code

# Spec §6.3, verbatim. One constant, so a style rule Shiny turns out to need (§6.3 leaves them to
# §29) is a one-line change; script-src never changes without Dan. Never 'unsafe-eval'.
CSP = (
    "default-src 'self'; script-src 'self'; connect-src 'self'; object-src 'none'; "
    "base-uri 'none'; frame-ancestors 'none'; img-src 'self' data: blob:; media-src 'self' blob:"
)
# Spec §6.3: what /media/ serves is a user's file, never a page. Sandboxed if a browser renders it
# anyway, never sniffed into another type, and never left in the disk cache (Range still seeks).
MEDIA_HEADERS = {
    "content-security-policy": "sandbox",
    "x-content-type-options": "nosniff",
    "cache-control": "no-store",
}
# Spec §6.2, on every response. CORP: another site can't embed /media/ in an <audio> tag, or load
# the engine's answers with a no-cors request. X-Frame-Options, as frame-ancestors does for newer
# browsers: a framed engine is this origin, so its own websocket would pass every check above, and
# a decoy page could steer the user's clicks. COOP: a page that opens the engine doesn't share its
# browsing context group. Referrer-Policy: a link out doesn't send the engine's address.
_EVERY_RESPONSE = {
    "cross-origin-resource-policy": "same-origin",
    "cross-origin-opener-policy": "same-origin",
    "x-frame-options": "DENY",
    "referrer-policy": "same-origin",
}


def host_name(host: str) -> str:
    """The name in a `Host` header, lowercased, without the port or IPv6 brackets."""
    host = host.strip().lower()
    if host.startswith("["):  # [::1]:8000
        end = host.find("]")
        return host[1:end] if end > 0 else ""
    return host.partition(":")[0]


def same_origin(scope: Scope, origin: str) -> bool:
    """Whether `origin` is exactly this request's own: its scheme, then its Host header as sent.

    An origin is a scheme, a host name and a port (RFC 6454). A page at http://localhost:9999 is
    another origin than the engine at http://localhost:8765, and may be another program, though
    its host name is allowed. Browsers leave a default port out of both headers, so those match.
    """
    host = (_header(scope, b"host") or "").strip().lower()
    scheme = scope.get("scheme", "http")
    scheme = {"ws": "http", "wss": "https"}.get(scheme, scheme)
    return bool(host) and origin.strip().lower() == f"{scheme}://{host}"


def sent_by_this_site(scope: Scope) -> bool:
    """False when the browser says another site sent the request: `Sec-Fetch-Site` is anything
    but `same-origin` or `none` (a typed address). `same-site` is refused too: another port of
    this host is the same site. With no header, Origin decides."""
    site = (_header(scope, b"sec-fetch-site") or "").strip().lower()
    return site in ("", "same-origin", "none")


def _header(scope: Scope, name: bytes) -> str | None:
    for key, value in scope["headers"]:
        if key == name:
            return value.decode("latin-1")
    return None


def _policy(path: str) -> list[tuple[bytes, bytes]]:
    """The security headers for a response to `path`: /media/'s set there, the page CSP
    elsewhere, and the others on both."""
    own = MEDIA_HEADERS if path.startswith("/media/") else {"content-security-policy": CSP}
    headers = {**_EVERY_RESPONSE, **own}
    return [(k.encode("latin-1"), v.encode("latin-1")) for k, v in headers.items()]


def _with_policy(scope: Scope, send: Send) -> Send:
    """`send`, with the security headers replacing any header of the same name the app set: a
    route can't weaken them, and none is sent twice."""
    extra = _policy(scope["path"])
    names = {k for k, _ in extra}

    async def wrapped(message: Message) -> None:
        if message["type"] == "http.response.start":
            kept = [(k, v) for k, v in message.get("headers", []) if bytes(k).lower() not in names]
            message = {**message, "headers": [*kept, *extra]}
        await send(message)

    return wrapped


class HostGuard:
    """Pure ASGI middleware: refuse requests addressed to a name not in `allowed`, and websockets
    from any origin but the engine's own."""

    def __init__(self, app: ASGIApp, allowed: frozenset[str]) -> None:
        self.app = app
        self.allowed = frozenset(h.lower() for h in allowed)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            await self.app(scope, receive, send)
            return
        if scope["type"] not in ("http", "websocket"):  # a type no guard knows: fail closed
            return
        host_ok = host_name(_header(scope, b"host") or "") in self.allowed
        if scope["type"] == "http":
            if not host_ok:
                await PlainTextResponse("unknown host", status_code=400)(
                    scope, receive, _with_policy(scope, send)
                )
                return
        else:
            # A browser always sends Origin on a websocket. It must be the engine's own, exactly,
            # and the handshake not marked as sent by another site. No Origin means no browser
            # sent it, so no website is behind it.
            origin = _header(scope, b"origin")
            origin_ok = (origin is None or same_origin(scope, origin)) and sent_by_this_site(scope)
            if not (host_ok and origin_ok):
                # Refuse the handshake without accepting (the server answers 403).
                if (await receive())["type"] == "websocket.connect":
                    await send({"type": "websocket.close", "code": POLICY_VIOLATION})
                return
        await self.app(scope, receive, send)


SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


class WriteGuard:
    """Every request that could change data comes from this engine's own page, or from no browser
    at all, and is exactly JSON (spec §6.2). Every response carries the security headers (above).

    - **Who sent it.** A browser names the sending page in `Origin`, and marks a request another
      site sent with `Sec-Fetch-Site: cross-site` or `same-site`. Either refuses it, and so does
      an `Origin` that isn't exactly the engine's own (same_origin). Without both headers, no
      browser sent it, so no website is behind it; TokenGuard still asks it for the cookie.
    - **What it carries.** `Content-Type: application/json` can't be sent to another origin
      without a CORS preflight, which the engine never answers. Exactly that: a charset parameter
      is refused too, so there is one spelling to check.
    """

    def __init__(self, app: ASGIApp, allowed: frozenset[str]) -> None:
        self.app = app
        self.allowed = frozenset(h.lower() for h in allowed)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("lifespan", "websocket"):  # websockets are HostGuard's to check
            await self.app(scope, receive, send)
            return
        if scope["type"] != "http":  # a type no guard knows: fail closed
            return
        send = _with_policy(scope, send)
        if scope["method"] in SAFE_METHODS:
            await self.app(scope, receive, send)
            return
        origin = _header(scope, b"origin")
        own = origin is None or (
            same_origin(scope, origin) and host_name(_header(scope, b"host") or "") in self.allowed
        )
        if not (own and sent_by_this_site(scope)):
            await PlainTextResponse("cross-site request refused", status_code=403)(
                scope, receive, send
            )
            return
        if (_header(scope, b"content-type") or "").strip().lower() != "application/json":
            await PlainTextResponse("send Content-Type exactly application/json", status_code=415)(
                scope, receive, send
            )
            return
        await self.app(scope, receive, send)
