"""The app shell: `/healthz`, `/auth` and `/media/` come before the Shiny app mounted at "/", the
whole engine sits inside HostGuard, WriteGuard and TokenGuard, FastAPI's own pages are off, and
stopping the engine closes the job queue (spec §19.1, §6.1, §6.2, §17.1; S23, S24, S25)."""

import asyncio
import builtins
import io
import json
import os
import re
import socket
import subprocess

import pytest
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route, WebSocketRoute
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from vid2sub import cache as caching
from vid2sub.cache import Cache
from vid2sub.config import Config
from vid2sub.engines.clients import KeyRing
from vid2sub.jobs import Queue
from vid2sub.media.tools import Tools
from vid2sub.web import auth, runtime
from vid2sub.web.app import create_app
from vid2sub.web.backend import LocalBackend
from vid2sub.web.guards import CSP, LOCAL_HOSTS, HostGuard, WriteGuard
from vid2sub.web.media import MediaTokens

PORT = 8765
TOKEN = "t" * 43  # as long as a real token, and plainly not one (the leak scan agrees)
BASE = f"http://127.0.0.1:{PORT}"
# In full: the test client joins a bare path onto ws://testserver, which gets no cookie.
WS = f"ws://127.0.0.1:{PORT}/websocket/"
JSON = {"Content-Type": "application/json"}
PAGE = {"Origin": BASE, "Sec-Fetch-Site": "same-origin"}  # what the engine's own page sends


async def _page(request):
    return PlainTextResponse("shiny")


async def _echo(websocket):
    await websocket.accept()
    await websocket.send_text("hello")
    await websocket.close()


def _shiny() -> Starlette:
    """Stands in for the Shiny app: it answers every path, as an app mounted at "/" does."""
    return Starlette(routes=[WebSocketRoute("/websocket/", _echo), Route("/{rest:path}", _page)])


@pytest.fixture
def rt(tmp_path):
    made = runtime.build(Config(), tools=Tools(None, None, None), keys=KeyRing(environ={}),
                         cache=Cache(tmp_path / "cache", max_bytes=0))
    yield made
    made.queue.close()


@pytest.fixture
def client(rt):
    with TestClient(create_app(rt, token=TOKEN, port=PORT, shiny_app=_shiny()),
                    base_url=BASE) as c:
        yield c


def _sign_in(client):
    r = client.post("/auth", content=json.dumps({"token": TOKEN}), headers={**JSON, **PAGE})
    assert r.status_code == 204
    return r


def test_healthz_answers_ok_and_nothing_more_without_the_cookie(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    assert r.headers["content-security-policy"] == CSP


@pytest.mark.parametrize("path", ["/", "/editor", "/media/x", "/docs", "/openapi.json",
                                  "/healthz/", "/auth/x", "/lib/shiny-1.8.0/shiny.js"])
def test_every_other_path_needs_the_launch_cookie(client, path):
    r = client.get(path)
    assert r.status_code == 401
    assert r.text == auth.SIGN_IN_AGAIN
    expected = "sandbox" if path.startswith("/media/") else CSP  # MEDIA_HEADERS there
    assert r.headers["content-security-policy"] == expected


def test_the_websocket_needs_the_launch_cookie(client):
    with pytest.raises(WebSocketDisconnect) as refused, client.websocket_connect(
            WS, headers={"Origin": BASE}):
        pass
    assert refused.value.code == 1008


def test_a_signed_in_browser_reaches_the_shiny_app_and_its_websocket(client):
    _sign_in(client)
    assert client.get("/").text == "shiny"
    assert client.get("/editor").text == "shiny"
    with client.websocket_connect(WS, headers={"Origin": BASE}) as ws:
        assert ws.receive_text() == "hello"


@pytest.mark.parametrize("path", ["/docs", "/docs/oauth2-redirect", "/redoc", "/openapi.json"])
def test_fastapis_own_pages_are_off(client, path):
    # Swagger UI and ReDoc load scripts from a CDN, which the CSP and spec §6.3 forbid.
    _sign_in(client)
    assert client.get(path).text == "shiny"


def test_the_shells_routes_come_before_the_shiny_app(client, rt, tmp_path):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"0123456789")
    token = rt.media.issue(clip, owner="e1")
    _sign_in(client)
    r = client.get(f"/media/{token}")
    assert r.status_code == 200 and r.content == b"0123456789"
    assert r.headers["content-security-policy"] == "sandbox"
    assert client.get("/healthz").json() == {"ok": True}
    assert "<script src=\"/auth.js\"></script>" in client.get("/auth").text
    assert client.get("/media/unknown").status_code == 404  # the route, not the Shiny app


def test_the_guards_wrap_the_whole_engine(client):
    # HostGuard: a name the engine isn't called by, as DNS rebinding sends it. Only 127.0.0.1,
    # which the engine binds and its link names, is allowed.
    assert client.get("/healthz", headers={"Host": "evil.example"}).status_code == 400
    assert client.get("/healthz", headers={"Host": f"localhost:{PORT}"}).status_code == 400
    # WriteGuard: a sign-in sent from a page on another local port, and one that isn't JSON.
    other = client.post("/auth", content=json.dumps({"token": TOKEN}),
                        headers={**JSON, "Origin": "http://127.0.0.1:9999",
                                 "Sec-Fetch-Site": "same-site"})
    assert other.status_code == 403 and "set-cookie" not in other.headers
    charset = client.post("/auth", content=json.dumps({"token": TOKEN}),
                          headers={"Content-Type": "application/json; charset=utf-8", **PAGE})
    assert charset.status_code == 415
    _sign_in(client)
    # HostGuard: the cookie doesn't let another origin's page open the websocket.
    with pytest.raises(WebSocketDisconnect) as refused, client.websocket_connect(
            WS, headers={"Origin": "http://127.0.0.1:9999"}):
        pass
    assert refused.value.code == 1008


def test_stopping_the_engine_closes_the_job_queue(rt):
    with TestClient(create_app(rt, token=TOKEN, port=PORT, shiny_app=_shiny()), base_url=BASE):
        rt.queue.jobs()  # open while the engine runs
    with pytest.raises(RuntimeError, match="closed"):
        rt.queue.submit(["/videos/a.mkv"])


def test_the_lifespan_closes_the_job_queue_off_the_event_loop(rt):
    # Queue.close() runs the queue's listeners, so where one runs is where close() ran.
    on_the_loop: list[bool] = []

    def listener():
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            on_the_loop.append(False)
        else:
            on_the_loop.append(True)

    rt.queue.on_change(listener)
    with TestClient(create_app(rt, token=TOKEN, port=PORT, shiny_app=_shiny()), base_url=BASE):
        assert on_the_loop == []
    assert on_the_loop == [False]


# ---- the runtime ------------------------------------------------------------------------------


def test_current_needs_configure_first():
    runtime.configure(None)
    with pytest.raises(RuntimeError, match="configure"):
        runtime.current()


def test_configure_sets_what_current_returns(rt):
    runtime.configure(rt)
    try:
        assert runtime.current() is rt
    finally:
        runtime.configure(None)


def test_build_puts_one_backend_queue_and_token_store_together(tmp_path):
    config, keys = Config(), KeyRing(environ={})
    cache = Cache(tmp_path / "cache", max_bytes=0)
    rt = runtime.build(config, tools=Tools(None, None, None), keys=keys, cache=cache)
    try:
        assert isinstance(rt.backend, LocalBackend)
        assert (rt.backend.config, rt.backend.keys, rt.backend.cache) == (config, keys, cache)
        assert isinstance(rt.queue, Queue) and isinstance(rt.media, MediaTokens)
        assert (rt.config, rt.keys) == (config, keys)
    finally:
        rt.queue.close()


def test_the_cache_follows_cache_max_gb_from_vid2sub_toml(tmp_path, monkeypatch):
    monkeypatch.setattr(caching, "default_root", lambda: tmp_path / "cache")
    config = Config.model_validate({"defaults": {"cache_max_gb": 3}})
    rt = runtime.build(config, tools=Tools(None, None, None), keys=KeyRing(environ={}))
    try:
        assert rt.backend.cache.root == tmp_path / "cache"
        assert rt.backend.cache.max_bytes == 3 * caching.GB
    finally:
        rt.queue.close()


# ---- S25: a GET never writes anything or starts a process -----------------------------------


def _api(app):
    """The FastAPI app inside the guards: each guard keeps the app it wraps in `.app`."""
    while not hasattr(app, "routes"):
        app = app.app
    return app


def get_paths(app) -> list[str]:
    """Every path the built app answers to GET or HEAD, read from its routes at run time, so a
    route a later task adds is covered too. A mount has no methods and answers everything."""
    paths = {
        re.sub(r"\{[^}]+\}", "x", route.path or "/")
        for route in _api(app).routes
        if getattr(route, "methods", None) is None or {"GET", "HEAD"} & route.methods
    }
    return sorted(paths | {"/no/such/page"})


def read_only_violations(client, monkeypatch, tmp_path, extra=()) -> list[str]:
    """What a GET or HEAD to each of the app's paths did that a read must not: opened a file for
    writing, made, moved or removed one, started a process, or opened a connection."""
    seen: list[str] = []
    real_open = builtins.open

    def trip(what):
        def tripped(*args, **kwargs):
            seen.append(what)
            raise OSError(f"{what} during a GET")

        return tripped

    def guarded_open(file, mode="r", *args, **kwargs):
        if set(mode) & set("wax+"):
            return trip(f"open(..., {mode!r})")()
        return real_open(file, mode, *args, **kwargs)

    for owner, name in [
        (subprocess, "Popen"), (os, "system"), (os, "mkdir"), (os, "makedirs"), (os, "remove"),
        (os, "unlink"), (os, "rename"), (os, "replace"), (os, "rmdir"),
        (socket.socket, "connect"), (socket, "create_connection"),
    ]:
        monkeypatch.setattr(owner, name, trip(f"{owner.__name__}.{name}"))
    monkeypatch.setattr(builtins, "open", guarded_open)
    monkeypatch.setattr(io, "open", guarded_open)
    before = sorted(str(p) for p in tmp_path.rglob("*"))
    for method in ("get", "head"):
        for path in [*get_paths(client.app), *extra]:
            try:
                getattr(client, method)(path)
            except OSError as error:  # the trip raises it; a route that fails on it is a violation
                seen.append(f"{method.upper()} {path}: {error}")
    after = sorted(str(p) for p in tmp_path.rglob("*"))
    return [*seen, *(["files changed"] if before != after else [])]


def test_no_get_or_head_route_writes_a_file_or_starts_a_process(client, rt, tmp_path, monkeypatch):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"0123456789")
    live = rt.media.issue(clip, owner="e1")
    _sign_in(client)
    assert read_only_violations(client, monkeypatch, tmp_path, extra=[f"/media/{live}"]) == []


def test_the_enumeration_finds_the_shells_own_routes_and_the_mount(client):
    paths = get_paths(client.app)
    assert "/healthz" in paths and "/media/x" in paths and "/" in paths


def _wrapped(route) -> TestClient:
    """A guarded app with one GET route that does something a read must not."""
    inner = Starlette(routes=[Route("/boom", route)])
    return TestClient(HostGuard(WriteGuard(inner, LOCAL_HOSTS), LOCAL_HOSTS), base_url=BASE)


async def _writes(request):
    with open(request.app.state.target, "w") as f:  # noqa: ASYNC230 - the point of the test
        f.write("x")
    return PlainTextResponse("ok")


def _launches(request):  # sync: Starlette runs it in a thread, and ruff bars Popen in async
    subprocess.Popen(["true"])
    return PlainTextResponse("ok")


async def _connects(request):
    socket.create_connection(("127.0.0.1", 9))
    return PlainTextResponse("ok")


@pytest.mark.parametrize("route", [_writes, _launches, _connects],
                         ids=["writes a file", "starts a process", "opens a connection"])
def test_the_check_notices_a_get_route_that_does_one_of_them(route, tmp_path, monkeypatch):
    client = _wrapped(route)
    _api(client.app).state.target = str(tmp_path / "out.txt")
    found = read_only_violations(client, monkeypatch, tmp_path, extra=["/boom"])
    # Tripped by the check itself, not merely failed: port 9 refusing the connection would also
    # end the request in an error.
    assert any("/boom" in line and "during a GET" in line for line in found)
