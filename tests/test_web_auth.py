"""Only the browser vid2sub opened, with the cookie it got from the launch token, reaches the
engine; the token itself never reaches a response, a log or the command line (spec §6.1; S23,
S24; Review Focus 5)."""

import asyncio
import json
import logging
import re
import stat
import sys
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Route, WebSocketRoute
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from vid2sub.web import auth
from vid2sub.web.guards import LOCAL_HOSTS, HostGuard, WriteGuard

PORT = 8765
# 43 URL-safe characters, as new_token makes, and plainly not a secret (the leak scan agrees).
TOKEN = "testtokentesttokentesttokentesttokentesttok"
BASE = f"http://127.0.0.1:{PORT}"
# In full: the test client joins a bare path onto ws://testserver, which gets no cookie.
WS = f"ws://127.0.0.1:{PORT}/websocket/"
JSON = {"Content-Type": "application/json"}
SIGN_IN_AGAIN = "open the link vid2sub printed when it started"


async def _home(request):
    return PlainTextResponse("home")


async def _healthz(request):
    return JSONResponse({"ok": True})


async def _write(request):
    return JSONResponse({"written": True})


async def _echo(websocket):
    await websocket.accept()
    await websocket.send_text("hello")
    await websocket.close()


def _app(token=TOKEN, port=PORT, lifespan=None):
    inner = Starlette(
        routes=[
            *auth.routes(token, port),
            Route("/healthz", _healthz),
            Route("/", _home),
            Route("/api/write", _write, methods=["POST"]),
            Route("/media/{token}", _home),
            WebSocketRoute("/websocket/", _echo),
        ],
        lifespan=lifespan,
    )
    return auth.TokenGuard(inner, token=token, port=port)


@pytest.fixture
def client():
    with TestClient(_app(), base_url=BASE) as c:
        yield c


def _sign_in(client, token=TOKEN):
    return client.post("/auth", content=json.dumps({"token": token}), headers=JSON)


def _cookie_value(token=TOKEN, port=PORT) -> str:
    # What a signed-in browser holds: whatever POST /auth set.
    with TestClient(_app(token, port), base_url=f"http://127.0.0.1:{port}") as c:
        r = _sign_in(c, token)
        assert r.status_code == 204
        return c.cookies[auth.cookie_name(port)]


# ---- the token, the cookie's name, the sign-in link and the redirect file ------------------


def test_a_token_is_256_random_bits_in_url_safe_characters():
    tokens = {auth.new_token() for _ in range(50)}
    assert len(tokens) == 50
    assert all(re.fullmatch(r"[A-Za-z0-9_-]{43}", t) for t in tokens)


def test_the_cookie_is_named_for_the_port():
    assert auth.cookie_name(8765) == "vid2sub-8765"
    assert auth.cookie_name(9000) == "vid2sub-9000"


def test_the_sign_in_link_carries_the_token_only_in_the_fragment():
    # The fragment never reaches a request line, so never the server's logs (spec §6.1).
    url = auth.auth_url(PORT, TOKEN)
    assert url == f"http://127.0.0.1:{PORT}/auth#t={TOKEN}"
    parts = urlsplit(url)
    assert (parts.path, parts.query, parts.fragment) == ("/auth", "", f"t={TOKEN}")


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes")
def test_the_redirect_file_is_private_and_its_path_never_names_the_token():
    # `ps` shows the browser's arguments: the file's path, never the token (S23).
    page = auth.write_redirect(auth.auth_url(PORT, TOKEN))
    try:
        assert stat.S_IMODE(page.stat().st_mode) == 0o600
        assert stat.S_IMODE(page.parent.stat().st_mode) == 0o700
        assert TOKEN not in str(page)
    finally:
        page.unlink()
        page.parent.rmdir()


def test_the_redirect_file_sends_the_browser_on_without_any_script():
    url = auth.auth_url(PORT, TOKEN)
    page = auth.write_redirect(url)
    try:
        text = page.read_text(encoding="utf-8")
        assert f'<meta http-equiv="refresh" content="0;url={url}">' in text
        assert f'<a href="{url}">' in text  # for a browser that ignores the refresh
        assert "<script" not in text.lower()
    finally:
        page.unlink()
        page.parent.rmdir()


def test_the_redirect_file_escapes_what_it_is_given():
    page = auth.write_redirect('http://127.0.0.1:1/auth#t="><script>alert(1)</script>')
    try:
        text = page.read_text(encoding="utf-8")
        assert "<script" not in text and "&quot;&gt;&lt;script&gt;" in text
    finally:
        page.unlink()
        page.parent.rmdir()


# ---- /auth and its script --------------------------------------------------------------------


def test_the_auth_page_loads_its_script_from_a_file_and_has_none_inline(client):
    # The CSP allows only the engine's own files (spec §6.3): an inline script wouldn't run.
    page = client.get("/auth")
    assert page.status_code == 200
    assert page.headers["content-type"] == "text/html; charset=utf-8"
    scripts = re.findall(
        r"<script\b([^>]*)>(.*?)</script>", page.text, flags=re.DOTALL | re.IGNORECASE
    )
    assert scripts == [(' src="/auth.js"', "")]
    assert not re.search(r"\son[a-z]+\s*=|\sstyle\s*=|<style", page.text, flags=re.IGNORECASE)
    script = client.get("/auth.js")
    assert script.status_code == 200
    assert script.headers["content-type"] == "application/javascript"


def test_the_auth_script_posts_exactly_json_and_shows_text_only():
    # WriteGuard refuses `application/json; charset=…`, and the message is set as text.
    js = (auth.STATIC / "auth.js").read_text(encoding="utf-8")
    assert 'headers: { "Content-Type": "application/json" },' in js
    assert 'credentials: "same-origin"' in js
    assert 'location.replace("/")' in js and "location.hash" in js
    assert "This link is out of date: open the URL vid2sub printed when it started." in js
    assert "textContent" in js and "innerHTML" not in js and "eval" not in js


# ---- POST /auth ------------------------------------------------------------------------------


def test_the_right_token_sets_an_httponly_strict_cookie_for_the_whole_site(client):
    r = _sign_in(client)
    assert r.status_code == 204 and r.content == b""
    cookie = r.headers["set-cookie"]
    name, _, rest = cookie.partition("=")
    attributes = {a.strip().split("=")[0].lower(): a.strip() for a in rest.split(";")[1:]}
    assert name == "vid2sub-8765"
    assert attributes["httponly"] == "HttpOnly"
    assert attributes["samesite"] == "SameSite=strict"
    assert attributes["path"] == "Path=/"
    # Plain http on 127.0.0.1, so no Secure; a session cookie, so it dies with the browser.
    assert not {"secure", "max-age", "expires", "domain"} & set(attributes)


@pytest.mark.parametrize(
    "body",
    [
        {"token": "wrong"},
        {"token": ""},
        {"token": TOKEN + "x"},
        {"token": TOKEN[:-1]},
        {"token": "é" * 43},  # not ASCII: compared as bytes, never a TypeError
        {},
    ],
    ids=["wrong", "empty", "longer", "shorter", "non-ascii", "missing"],
)
def test_a_wrong_or_missing_token_is_403_and_sets_no_cookie(client, body):
    r = client.post("/auth", content=json.dumps(body), headers=JSON)
    assert r.status_code == 403
    assert "set-cookie" not in r.headers and not client.cookies


@pytest.mark.parametrize(
    "content",
    [b"", b"not json", b"[]", b'"token"', b'{"token": 5}', b'{"token": null}', b"\xff\xfe",
     b"[" * 500 + b"]" * 500],
    ids=["empty", "not-json", "list", "string", "number", "null", "bad-bytes", "deep"],
)
def test_a_malformed_body_is_400_and_sets_no_cookie(client, content):
    r = client.post("/auth", content=content, headers=JSON)
    assert r.status_code == 400
    assert "set-cookie" not in r.headers


def test_a_body_too_large_for_a_token_is_refused(client):
    r = client.post("/auth", content=json.dumps({"token": "x" * 2000}), headers=JSON)
    assert r.status_code == 413 and "set-cookie" not in r.headers


# ---- TokenGuard ------------------------------------------------------------------------------


def test_without_the_cookie_every_route_but_the_open_three_is_401(client):
    for method, path in [("GET", "/"), ("GET", "/media/abc"), ("POST", "/api/write"),
                         ("GET", "/no-such-page"), ("HEAD", "/")]:
        r = client.request(method, path, headers=JSON)
        assert r.status_code == 401, path
        assert r.headers["content-type"] == "text/plain; charset=utf-8"
        if method != "HEAD":
            assert r.text == SIGN_IN_AGAIN
    for path in ("/auth", "/auth.js", "/healthz"):
        assert client.get(path).status_code == 200, path


def test_after_signing_in_every_route_answers(client):
    assert _sign_in(client).status_code == 204
    assert client.get("/").text == "home"
    assert client.get("/media/abc").status_code == 200
    assert client.post("/api/write", content=b"{}", headers=JSON).json() == {"written": True}


def _status(app, path: str, cookie: str | None = None, method: str = "GET") -> int:
    """Call `app` with exactly this `scope["path"]`, as uvicorn passes it (an HTTP client would
    normalise `..` away first), and return the status it answers."""
    headers = [(b"host", f"127.0.0.1:{PORT}".encode())]
    if cookie is not None:
        headers.append((b"cookie", cookie.encode("latin-1")))
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method,
             "scheme": "http", "path": path, "raw_path": path.encode("latin-1"),
             "query_string": b"", "root_path": "", "headers": headers,
             "server": ("127.0.0.1", PORT), "client": ("127.0.0.1", 50000)}
    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    asyncio.run(app(scope, receive, send))
    return sent[0]["status"]


@pytest.fixture
def recorded():
    """A TokenGuard around an app that records each path it is reached with."""
    reached: list[str] = []

    async def inner(scope, receive, send):
        reached.append(scope["path"])
        await PlainTextResponse("inner")(scope, receive, send)

    return auth.TokenGuard(inner, token=TOKEN, port=PORT), reached


@pytest.mark.parametrize(
    "path",
    ["/auth/", "/auth/x", "/auth.js/", "/auth.jsx", "/authx", "/healthz/", "/healthz/../",
     "/healthz/..", "/healthz/../media/x", "/auth/../", "//healthz", "/HEALTHZ", "/Auth",
     "/auth\x00", "/auth;x", "/healthz ", " /healthz", "/./healthz", "", "/"],
)
def test_a_path_that_only_looks_open_needs_the_cookie(recorded, path):
    guard, reached = recorded
    assert _status(guard, path) == 401 and reached == []


OPEN_PAIRS = [("GET", "/auth"), ("HEAD", "/auth"), ("POST", "/auth"),
              ("GET", "/auth.js"), ("HEAD", "/auth.js"), ("GET", "/healthz")]


def test_the_open_routes_are_matched_exactly_and_reach_the_app(recorded):
    guard, reached = recorded
    assert [_status(guard, p, method=m) for m, p in OPEN_PAIRS] == [200] * len(OPEN_PAIRS)
    assert reached == [p for _, p in OPEN_PAIRS]


@pytest.mark.parametrize(
    ("method", "path"),
    [("PUT", "/auth"), ("DELETE", "/auth"), ("PATCH", "/auth"), ("OPTIONS", "/auth"),
     ("POST", "/auth.js"), ("PUT", "/auth.js"), ("POST", "/healthz"), ("OPTIONS", "/healthz"),
     ("HEAD", "/healthz")],
)
def test_a_method_an_open_route_doesnt_answer_needs_the_cookie(recorded, method, path):
    # Else it would fall through to whatever is mounted at / (spec §6.1 opens only these routes).
    guard, reached = recorded
    assert _status(guard, path, method=method) == 401 and reached == []


@pytest.mark.parametrize(
    "cookie",
    [
        "vid2sub-8765=wrong",
        f"vid2sub-8765={TOKEN}",  # the token itself is not the cookie
        "vid2sub-8765=",
        "vid2sub-8765",
        "vid2sub-9999={value}",  # the right value under another port's name
        "other={value}",
        "vid2sub-8765={value}x",
        "vid2sub-8765=x{value}",
    ],
)
def test_a_cookie_that_isnt_this_launchs_is_401(recorded, cookie):
    guard, reached = recorded
    assert _status(guard, "/", cookie.replace("{value}", _cookie_value())) == 401
    assert reached == []


def test_the_cookie_is_found_among_others_and_beside_a_planted_one(recorded):
    # A page on another port of 127.0.0.1 can set cookies for this host (cookies ignore ports),
    # but can't read or remove the HttpOnly one: a planted cookie of the same name is ignored.
    guard, reached = recorded
    value = _cookie_value()
    assert _status(guard, "/", f"theme=dark; vid2sub-8765=planted; vid2sub-8765={value}") == 200
    assert _status(guard, "/", f"vid2sub-8765={value}; vid2sub-8765=planted") == 200
    assert _status(guard, "/", f'vid2sub-8765={value}; other="x"') == 200
    assert reached == ["/", "/", "/"]


def test_a_restarted_engine_refuses_the_old_cookie():
    # Review Focus 5: a tab left open across a restart is told to open the new link.
    old = _cookie_value(TOKEN)
    with TestClient(_app(token=auth.new_token()), base_url=BASE) as c:
        c.cookies.set(auth.cookie_name(PORT), old, domain="127.0.0.1")
        r = c.get("/")
        assert r.request.headers["cookie"] == f"vid2sub-8765={old}"  # it was sent, and refused
        assert r.status_code == 401 and r.text == SIGN_IN_AGAIN
        with pytest.raises(WebSocketDisconnect) as exc, c.websocket_connect(WS):
            pass
        assert exc.value.code == 1008


def test_a_websocket_without_the_cookie_is_closed_before_accept(client):
    # S24: a websocket opened without this launch's cookie gets nothing.
    with pytest.raises(WebSocketDisconnect) as exc, client.websocket_connect(WS):
        pass
    assert exc.value.code == 1008


def test_a_websocket_with_the_cookie_is_accepted(client):
    _sign_in(client)
    with client.websocket_connect(WS) as ws:
        assert ws.receive_text() == "hello"


def test_lifespan_passes_straight_through():
    started = []

    @asynccontextmanager
    async def lifespan(app):
        started.append(True)
        yield

    with TestClient(_app(lifespan=lifespan), base_url=BASE):
        assert started == [True]


def test_only_lifespan_besides_http_and_websocket_reaches_the_app():
    # Fail closed, as HostGuard and WriteGuard do since Task 8: any other scope type is not
    # something this guard checked, so it never reaches the app.
    seen = []

    async def inner(scope, receive, send):
        seen.append(scope["type"])

    async def never(*_):
        raise AssertionError("the guard answered a scope it should only drop")

    guard = auth.TokenGuard(inner, token=TOKEN, port=PORT)
    for kind in ("custom", "lifespan"):
        asyncio.run(guard({"type": kind, "headers": []}, never, never))
    assert seen == ["lifespan"]


# ---- the token goes nowhere --------------------------------------------------------------


def test_the_token_is_in_no_response_and_no_log_record(caplog):
    # S23. It is in the redirect file, by design, and nowhere else.
    caplog.set_level(logging.DEBUG)
    page = auth.write_redirect(auth.auth_url(PORT, TOKEN))
    try:
        assert TOKEN in page.read_text(encoding="utf-8")  # so the checks below aren't vacuous
    finally:
        page.unlink()
        page.parent.rmdir()
    responses = []
    with TestClient(_app(), base_url=BASE) as c:
        responses += [c.get("/"), c.get("/auth"), c.get("/auth.js"), c.get("/healthz")]
        responses += [c.post("/auth", content=b"{}", headers=JSON),
                      c.post("/auth", content=b"nope", headers=JSON),
                      _sign_in(c, "wrong"), _sign_in(c)]
        responses += [c.get("/"), c.post("/api/write", content=b"{}", headers=JSON)]
    for r in responses:
        assert TOKEN.encode() not in r.content
        assert all(TOKEN.encode() not in k + v for k, v in r.headers.raw)
    assert caplog.records  # httpx logs each request
    for record in caplog.records:
        assert TOKEN not in record.getMessage() and TOKEN not in repr(record.args)


def test_the_whole_stack_signs_a_browser_in():
    # As Task 11 wraps it: HostGuard(WriteGuard(TokenGuard(app))), with a browser's headers.
    app = HostGuard(WriteGuard(_app(), LOCAL_HOSTS), LOCAL_HOSTS)
    page = {"Origin": BASE, "Sec-Fetch-Site": "same-origin"}
    with TestClient(app, base_url=BASE) as c:
        assert c.get("/").status_code == 401
        refused = c.post("/auth", content=json.dumps({"token": TOKEN}),
                         headers={**JSON, "Origin": "http://127.0.0.1:9999",
                                  "Sec-Fetch-Site": "same-site"})
        assert refused.status_code == 403 and "set-cookie" not in refused.headers
        charset = c.post("/auth", content=json.dumps({"token": TOKEN}),
                         headers={"Content-Type": "application/json; charset=utf-8", **page})
        assert charset.status_code == 415
        r = c.post("/auth", content=json.dumps({"token": TOKEN}), headers={**JSON, **page})
        assert r.status_code == 204
        assert c.get("/").text == "home"
        with c.websocket_connect(WS, headers={"Origin": BASE}) as ws:
            assert ws.receive_text() == "hello"
