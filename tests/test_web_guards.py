"""The engine answers only to its own names, refuses websockets and writes from other sites, and
sends the security headers on every response (spec §6.2, §6.3; S24, S25).

The HostGuard and WriteGuard tests are copied from recordings (packages/ui/tests/test_hosts.py
and test_writeguard.py at 8deb039, spec §4.4); the CSP and /media/ header tests are new.
"""

from contextlib import asynccontextmanager

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse, PlainTextResponse, Response
from starlette.routing import Route, WebSocketRoute
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from vid2sub.web.guards import CSP, LOCAL_HOSTS, MEDIA_HEADERS, HostGuard, WriteGuard

# Spec §6.3, verbatim, so loosening guards.CSP fails here too.
SPEC_CSP = (
    "default-src 'self'; script-src 'self'; connect-src 'self'; object-src 'none'; "
    "base-uri 'none'; frame-ancestors 'none'; img-src 'self' data: blob:; media-src 'self' blob:"
)
EVERY_RESPONSE = {
    "cross-origin-resource-policy": "same-origin",
    "cross-origin-opener-policy": "same-origin",
    "x-frame-options": "DENY",
    "referrer-policy": "same-origin",
}
PAGE = {**EVERY_RESPONSE, "content-security-policy": SPEC_CSP}
MEDIA = {
    **EVERY_RESPONSE,
    "content-security-policy": "sandbox",
    "x-content-type-options": "nosniff",
    "cache-control": "no-store",
}
JSON = {"Content-Type": "application/json"}


async def _hello(request):
    return PlainTextResponse("hi")


async def _echo(websocket):
    await websocket.accept()
    await websocket.send_text("hello")
    await websocket.close()


async def _thing(request):
    return JSONResponse({"ok": True})


async def _weak(request):
    # A route that sets weaker headers of its own: the guard's must win, and be sent once.
    return PlainTextResponse(
        "weak",
        headers={"Content-Security-Policy": "script-src *", "X-Frame-Options": "SAMEORIGIN"},
    )


async def _media(request):
    # As Task 10's route answers: its own nosniff, and a CSP that the sandbox must replace.
    return Response(
        b"\x00" * 16,
        media_type="audio/mpeg",
        headers={"Content-Security-Policy": "default-src *", "X-Content-Type-Options": "nosniff"},
    )


def _inner(lifespan=None) -> Starlette:
    return Starlette(
        routes=[
            Route("/", _hello),
            WebSocketRoute("/ws", _echo),
            Route("/api/thing", _thing, methods=["GET", "POST", "DELETE"]),
            Route("/weak", _weak),
            Route("/media/{token}", _media),
            Route("/mediafile", _hello),
        ],
        lifespan=lifespan,
    )


def guarded(allowed=LOCAL_HOSTS, lifespan=None) -> TestClient:
    return TestClient(HostGuard(_inner(lifespan), frozenset(allowed)), base_url="http://localhost")


@pytest.fixture
def client():
    with TestClient(WriteGuard(_inner(), LOCAL_HOSTS), base_url="http://localhost:8000") as c:
        yield c


def _policy(response, names) -> dict:
    return {k: response.headers.get(k) for k in names}


# ---- HostGuard ---------------------------------------------------------------------------


def test_the_unknown_host_answer_carries_the_security_headers_too():
    # "Every response" carries the policy (spec §6.2), the 400 included.
    r = guarded().get("/", headers={"Host": "attacker.example"})
    assert r.status_code == 400
    assert _policy(r, PAGE) == PAGE


@pytest.mark.parametrize(
    "host",
    [
        "attacker.example",
        "attacker.example:8000",
        "localhost.attacker.example",
        "evil-localhost",
        "[::2]:8000",
        "",
    ],
)
def test_an_unknown_host_is_400(host):
    # DNS rebinding: a website's own name pointed at 127.0.0.1 still arrives in Host.
    r = guarded().get("/", headers={"Host": host})
    assert r.status_code == 400 and r.text == "unknown host"


@pytest.mark.parametrize(
    "host",
    [
        "localhost",
        "localhost:8000",
        "127.0.0.1:8000",
        "[::1]:8000",
        "[::1]",
        "LOCALHOST:8000",
        "LocalHost",
    ],
)
def test_allowed_host_variants_pass(host):
    r = guarded().get("/", headers={"Host": host})
    assert r.status_code == 200 and r.text == "hi"


def test_allowed_names_are_compared_lowercased():
    client = guarded(allowed={"My-Laptop"})
    assert client.get("/", headers={"Host": "my-laptop:8000"}).status_code == 200
    assert client.get("/", headers={"Host": "localhost"}).status_code == 400  # only what it's given


def _refused(client, url, headers) -> int:
    with pytest.raises(WebSocketDisconnect) as exc, client.websocket_connect(url, headers=headers):
        pass
    return exc.value.code


@pytest.mark.parametrize(
    "origin", ["http://evil.example", "https://localhost.evil.example", "null", "http://[::1"]
)
def test_a_websocket_from_a_foreign_origin_is_refused(origin):
    assert _refused(guarded(), "ws://localhost/ws", {"Origin": origin}) == 1008


def test_a_websocket_to_an_unknown_host_is_refused():
    assert (
        _refused(guarded(), "ws://attacker.example/ws", {"Origin": "http://attacker.example"})
        == 1008
    )


@pytest.mark.parametrize(
    "url, origin",
    [
        ("ws://localhost:8000/ws", "http://localhost:8000"),
        ("ws://127.0.0.1:8000/ws", "http://127.0.0.1:8000"),
        ("ws://[::1]:8000/ws", "http://[::1]:8000"),
        ("ws://localhost/ws", "HTTP://LOCALHOST"),
    ],
)
def test_a_websocket_from_its_own_origin_is_accepted(url, origin):
    # The page's own origin: the scheme, host name and port of the Host it connects to.
    with guarded().websocket_connect(url, headers={"Origin": origin}) as ws:
        assert ws.receive_text() == "hello"


@pytest.mark.parametrize(
    "origin", ["http://localhost:9999", "https://localhost:8000", "http://127.0.0.1:8000"]
)
def test_a_websocket_from_another_port_scheme_or_name_of_this_host_is_refused(origin):
    # An origin is a scheme, a host name and a port (RFC 6454). A page at http://localhost:9999
    # is another program, though its host name is allowed (S24).
    assert _refused(guarded(), "ws://localhost:8000/ws", {"Origin": origin}) == 1008


@pytest.mark.parametrize("site", ["cross-site", "same-site"])
def test_a_websocket_the_browser_marks_as_another_sites_is_refused(site):
    assert (
        _refused(
            guarded(),
            "ws://localhost:8000/ws",
            {"Origin": "http://localhost:8000", "Sec-Fetch-Site": site},
        )
        == 1008
    )


def test_a_websocket_without_an_origin_is_accepted():
    # Browsers always send Origin on a websocket; a client without one is not a web page.
    with guarded().websocket_connect("ws://localhost/ws") as ws:
        assert ws.receive_text() == "hello"


def test_lifespan_passes_straight_through():
    started = []

    @asynccontextmanager
    async def lifespan(app):
        started.append(True)
        yield

    with guarded(lifespan=lifespan):
        assert started == [True]


# ---- WriteGuard --------------------------------------------------------------------------


def test_a_same_origin_json_write_passes(client):
    assert (
        client.post(
            "/api/thing",
            json={},
            headers={"Origin": "http://localhost:8000", "Sec-Fetch-Site": "same-origin"},
        ).status_code
        == 200
    )


def test_a_write_from_no_browser_passes(client):
    # No Origin and no Sec-Fetch-Site: curl or a script, not a web page. TokenGuard (Task 9)
    # still asks it for the launch cookie.
    assert client.post("/api/thing", content=b"{}", headers=JSON).status_code == 200


@pytest.mark.parametrize(
    "headers",
    [
        {"Sec-Fetch-Site": "cross-site"},
        {"Sec-Fetch-Site": "same-site"},  # another port of this host is the same site
        {"Origin": "https://evil.example"},
        {"Origin": "null"},
        {"Origin": "http://localhost:9999"},  # the same name at another port: another program
        {"Origin": "https://localhost:8000"},  # another scheme
        {"Origin": "http://127.0.0.1:8000"},  # an allowed name, but not the page's own origin
        {"Origin": "http://localhost:8000", "Sec-Fetch-Site": "cross-site"},
    ],
    ids=[
        "cross-site",
        "same-site",
        "foreign-origin",
        "null-origin",
        "other-port",
        "other-scheme",
        "other-allowed-name",
        "mixed",
    ],
)
def test_a_cross_site_write_is_refused(client, headers):
    # S25: a page on another site, or another port of this host, can post to the engine's name.
    response = client.post("/api/thing", content=b"{}", headers={**JSON, **headers})
    assert response.status_code == 403


def test_a_write_to_an_unknown_host_is_refused_even_from_that_origin(client):
    # DNS rebinding: Host and Origin both name the attacker's site, so they agree.
    response = client.post(
        "/api/thing",
        content=b"{}",
        headers={**JSON, "Host": "evil.example", "Origin": "http://evil.example"},
    )
    assert response.status_code == 403


@pytest.mark.parametrize(
    "ctype",
    [
        "text/plain",
        "application/x-www-form-urlencoded",
        "multipart/form-data; boundary=x",
        "application/json; charset=utf-8",
        "",
    ],
)
def test_anything_but_exactly_json_is_refused(client, ctype):
    # A browser sends text/plain or a form cross-site without a CORS preflight (S25).
    headers = {"Content-Type": ctype} if ctype else {}
    refused = client.post("/api/thing", content=b"{}", headers=headers)
    assert refused.status_code == 415
    assert "exactly application/json" in refused.text  # says why a charset is refused too
    assert client.delete("/api/thing", headers=headers).status_code == 415


def test_reads_are_not_affected(client):
    assert client.get("/api/thing", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 200


# ---- the headers -------------------------------------------------------------------------


def test_the_csp_is_the_specs_verbatim_and_never_allows_eval():
    assert SPEC_CSP == CSP
    assert "unsafe-eval" not in CSP and "frame-ancestors 'none'" in CSP


def test_every_response_carries_the_security_headers_and_the_csp(client):
    # Spec §6.2, §6.3. Without CORP, another site could embed /media/ in an <audio> tag, or load
    # the engine's answers with a no-cors request. A framed engine is this origin, so its own
    # websocket passes every check: no page may frame it. The CSP stops any script but the
    # engine's own files. Refusals carry them too.
    forbidden = client.post(
        "/api/thing", content=b"{}", headers={**JSON, "Sec-Fetch-Site": "cross-site"}
    )
    unsupported = client.post("/api/thing", content=b"{}", headers={"Content-Type": "text/plain"})
    assert (forbidden.status_code, unsupported.status_code) == (403, 415)
    for response in (client.get("/api/thing"), client.get("/"), forbidden, unsupported):
        assert _policy(response, PAGE) == PAGE


def test_a_media_response_is_sandboxed_unsniffed_and_never_stored(client):
    # Spec §6.3: a user's file is never run as a page, never sniffed into another type, and
    # never left in the browser's disk cache.
    r = client.get("/media/abc")
    assert r.status_code == 200
    assert _policy(r, MEDIA) == MEDIA
    assert {k: r.headers[k] for k in MEDIA_HEADERS} == MEDIA_HEADERS


def test_only_media_is_kept_out_of_the_cache(client):
    for path in ("/", "/api/thing", "/mediafile"):
        assert "cache-control" not in client.get(path).headers


def test_a_path_that_only_starts_like_media_gets_the_page_csp(client):
    assert client.get("/mediafile").headers["content-security-policy"] == SPEC_CSP


def test_the_guards_headers_replace_weaker_ones_the_app_set(client):
    r = client.get("/weak")
    assert r.headers.get_list("content-security-policy") == [SPEC_CSP]
    assert r.headers.get_list("x-frame-options") == ["DENY"]


def test_on_media_the_sandbox_replaces_any_csp_the_route_set(client):
    r = client.get("/media/abc")
    assert r.headers.get_list("content-security-policy") == ["sandbox"]
    assert r.headers.get_list("x-content-type-options") == ["nosniff"]
