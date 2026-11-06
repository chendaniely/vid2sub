"""The app shell: `/healthz`, `/auth` and `/media/` come before the Shiny app mounted at "/", the
whole engine sits inside HostGuard, WriteGuard and TokenGuard, FastAPI's own pages are off, and
stopping the engine closes the job queue (spec §19.1, §6.1, §6.2, §17.1; S23, S24, S25)."""

import json

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
from vid2sub.web.guards import CSP
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
    # HostGuard: a name the engine isn't called by, as DNS rebinding sends it.
    assert client.get("/healthz", headers={"Host": "evil.example"}).status_code == 400
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
