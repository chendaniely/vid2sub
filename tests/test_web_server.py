"""The Shiny server for the React frontend: its page runs no inline script or style, so the spec's
CSP allows all of it; `capabilities` and `status` are JSON outputs, with keys by presence only;
`notice` is a shinyreact message (spec §19.1, §19.2, §6.3; S26); and the editor's `open` and
`playback` inputs and `episode` and `busy` outputs, with their media tokens and the queue that
runs them, are here too (spec §19.1, §20, §8.2, §8.8)."""

import asyncio
import contextlib
import dataclasses
import json
import logging
import re
import threading
import time

import pytest
from episodes import ENGLISH, LINES, make_episode
from starlette.testclient import TestClient
from test_web_app import get_paths, read_only_violations

from vid2sub.cache import Cache
from vid2sub.config import Config, ModelEntry
from vid2sub.engines import clients
from vid2sub.engines.base import EngineError
from vid2sub.engines.clients import KeyRing
from vid2sub.media.tools import Tools
from vid2sub.translate.run import TranslationFailed
from vid2sub.web import runtime, server, views
from vid2sub.web.app import create_app
from vid2sub.web.backend import LocalBackend
from vid2sub.web.episode import SaveError
from vid2sub.web.guards import CSP

PORT = 8765
TOKEN = "t" * 43  # as long as a real token, and plainly not one (the leak scan agrees)
BASE = f"http://127.0.0.1:{PORT}"
WS = f"ws://127.0.0.1:{PORT}/websocket/"
JSON = {"Content-Type": "application/json"}
PAGE = {"Origin": BASE, "Sec-Fetch-Site": "same-origin"}
KEY = "v" * 24  # a key's value, which must reach no output
CONFIG = {
    "endpoints": {
        "spark": {"base_url": "http://127.0.0.1:9/v1", "key_env": "SPARK_TEST_KEY"},
        "openai": {"base_url": "https://api.openai.com/v1", "key_env": "OPENAI_TEST_KEY"},
        "lan": {"base_url": "http://127.0.0.1:10/v1"},
    },
    "models": {
        "spark-turbo": {"endpoint": "spark", "model": "w", "parser": "whisper.cpp", "local": True},
        "lan-gemma": {"endpoint": "lan", "model": "g", "task": "translate", "local": True},
        "cloud": {"endpoint": "openai", "model": "whisper-1", "parser": "openai"},
    },
}


@pytest.fixture(autouse=True)
def fresh_reactive_lock():
    """shiny's reactive lock is one asyncio.Lock per process, bound to the first event loop it is
    contended on, and each TestClient runs its own loop: dropping it makes a new one (recordings'
    packages/ui/tests/conftest.py)."""
    from shiny.reactive import _core

    _core._reactive_environment._lock = None
    yield
    _core._reactive_environment._lock = None


@pytest.fixture
def probed(monkeypatch):
    """No endpoint is contacted for real: the spark answers, the LAN one is down. `on_loop` holds,
    for each call, whether it ran on an event loop's thread."""

    class Calls(list):
        on_loop: list[bool]

    calls = Calls()
    calls.on_loop = []

    def list_models(name, endpoint, keys, *, timeout=5.0):
        calls.append(name)
        try:
            asyncio.get_running_loop()
            calls.on_loop.append(True)
        except RuntimeError:
            calls.on_loop.append(False)
        if name == "lan":
            raise EngineError("connection", "the server isn't reachable")
        return ["w"]

    monkeypatch.setattr(clients, "list_models", list_models)
    return calls


@pytest.fixture
def rt(tmp_path):
    made = runtime.build(Config.model_validate(CONFIG), tools=Tools(None, None, None),
                         keys=KeyRing(environ={"SPARK_TEST_KEY": KEY}),
                         cache=Cache(tmp_path / "cache", max_bytes=0))
    runtime.configure(made)
    yield made
    runtime.configure(None)
    made.queue.close()


@pytest.fixture
def client(rt):
    with TestClient(create_app(rt, token=TOKEN, port=PORT, shiny_app=server.app),
                    base_url=BASE) as c:
        r = c.post("/auth", content=json.dumps({"token": TOKEN}), headers={**JSON, **PAGE})
        assert r.status_code == 204
        yield c


def _session(client, outputs: set[str], until) -> list[dict]:
    """Every message the server sends a new session until `until(messages)` holds (20 s at
    most). Shiny runs the server function after the client's `init`, and sends an output only
    once the client says it isn't hidden (recordings' test_demo_guard.py)."""
    messages: list[dict] = []
    with client.websocket_connect(WS, headers={"Origin": BASE}) as ws:
        init = {f".clientdata_output_{name}_hidden": False for name in outputs}
        ws.send_text(json.dumps({"method": "init", "data": init}))

        def read() -> None:
            while not until(messages):
                messages.append(json.loads(ws.receive_text()))

        reader = threading.Thread(target=read, daemon=True)
        reader.start()
        reader.join(20)  # receive_text has no timeout: a missing output must not hang
    assert until(messages), f"the session sent only {messages}"
    return messages


def _values(messages: list[dict]) -> dict:
    out: dict = {}
    for m in messages:
        out.update(m.get("values", {}))
    return out


def test_the_page_runs_no_inline_script_or_style(client):
    # The CSP's script-src 'self' blocks inline scripts, and with no style-src, default-src
    # 'self' blocks inline styles (spec §6.3). Shiny 1.8.0's own page has one inline script,
    # the busy indicators; server.py serves it as a file instead.
    r = client.get("/")
    assert r.status_code == 200 and r.headers["content-security-policy"] == CSP
    for attrs, body in re.findall(r"<script\b([^>]*)>(.*?)</script>", r.text, re.DOTALL):
        if "src=" in attrs:
            assert body.strip() == ""
            continue
        kind = re.search(r'type="([^"]+)"', attrs)
        assert kind and kind.group(1) in ("application/json", "application/html-dependencies"), (
            f"an inline script the CSP would block: <script{attrs}>{body[:80]}")
    assert "<style" not in r.text and " style=" not in r.text
    assert not re.search(r"\son\w+\s*=", r.text)  # no inline event handler (onclick=...)
    assert "javascript:" not in r.text


def test_the_busy_indicators_still_switch_on_from_a_file(client):
    page = client.get("/").text
    srcs = re.findall(r'<script src="([^"]*busy-indicators\.js)"', page)
    assert len(srcs) == 1
    script = client.get("/" + srcs[0].lstrip("/"))
    assert script.status_code == 200
    assert "document.documentElement.dataset.shinyBusySpinners = true;" in script.text
    assert "document.documentElement.dataset.shinyBusyPulse = true;" in script.text
    assert re.search(r'href="[^"]*busy-indicators\.css"', page)  # Shiny's stylesheet stays


def test_the_page_loads_the_frontend_and_its_fonts_from_the_engine(client):
    page = client.get("/").text
    assert "<title>vid2sub</title>" in page
    assert client.get("/fonts/AtkinsonHyperlegible-Regular.woff2").status_code == 200
    assert "http://" not in page.replace(BASE, "") and "https://" not in page  # nothing third-party


def test_capabilities_says_this_is_the_local_engine(client, probed):
    values = _values(_session(client, {"capabilities"}, lambda m: "capabilities" in _values(m)))
    assert values["capabilities"] == {"engine": "local", "generate": True, "save": "disk",
                                      "path_input": True}


def test_status_names_each_endpoint_its_reach_and_its_key_by_presence_only(client, probed):
    def probed_all(messages):
        status = _values(messages).get("status")
        return bool(status) and all(e["reachable"] is not None or not e["local"]
                                    for e in status["endpoints"])

    messages = _session(client, {"status"}, probed_all)
    assert _values(messages)["status"] == {
        "ffmpeg": False,
        "endpoints": [
            {"name": "spark", "local": True, "key": "present", "reachable": True},
            {"name": "openai", "local": False, "key": "missing", "reachable": None},
            {"name": "lan", "local": True, "key": "none", "reachable": False},
        ],
    }
    assert sorted(probed) == ["lan", "spark"]  # a cloud endpoint is never contacted
    assert probed.on_loop == [False, False]  # off the event loop, which would freeze every tab
    assert KEY not in json.dumps(messages)


def test_the_status_is_checked_again_every_sixty_seconds(client, probed, monkeypatch):
    from shiny import reactive

    waits: list[float] = []
    real = reactive.invalidate_later

    def invalidate_later(delay, **kwargs):
        waits.append(delay)
        return real(delay, **kwargs)

    monkeypatch.setattr(reactive, "invalidate_later", invalidate_later)
    _session(client, {"status"}, lambda m: bool(_values(m).get("status")) and bool(probed))
    assert server.STATUS_EVERY == 60 and waits == [server.STATUS_EVERY]


def test_a_notice_reaches_the_browser_as_a_shinyreact_message():
    class Session:
        def __init__(self):
            self.sent = []

        async def send_custom_message(self, kind, message):
            self.sent.append((kind, message))

    session = Session()
    asyncio.run(server.notice(session, "error", "couldn't save Show.en.srt"))
    assert session.sent == [("shinyReactMessage", {"id": "notice", "data": {
        "kind": "error", "text": "couldn't save Show.en.srt"}})]


# ---- the views -------------------------------------------------------------------------------


def test_a_typed_key_counts_as_present_and_is_never_shown():
    config = Config.model_validate({"endpoints": {"openai": {
        "base_url": "https://api.openai.com/v1", "allow_typed_key": True}}})
    keys = KeyRing(typed={"openai": KEY}, environ={})
    status = views.status_view(config, keys, {}, ffmpeg=True)
    assert status["endpoints"] == [
        {"name": "openai", "local": False, "key": "present", "reachable": None}]
    assert KEY not in json.dumps(status)


def test_an_endpoint_not_checked_yet_or_in_the_cloud_is_neither_reachable_nor_not():
    config = Config.model_validate(CONFIG)
    found = {"spark": True, "openai": True}  # a cloud endpoint is never shown as checked
    status = views.status_view(config, KeyRing(environ={}), found, ffmpeg=True)
    assert [(e["name"], e["reachable"]) for e in status["endpoints"]] == [
        ("spark", True), ("openai", None), ("lan", None)]


def test_capabilities_view_is_the_backends_capabilities_as_json(rt):
    assert views.capabilities_view(rt.backend.capabilities()) == {
        "engine": "local", "generate": True, "save": "disk", "path_input": True}


# ---- what a session may leave behind ---------------------------------------------------------


def test_shinys_bookmark_store_is_disabled_so_no_session_state_reaches_the_disk():
    # shiny 1.8.0 keeps it on the app: App.bookmark_store (shiny/_app.py), set from the
    # constructor's bookmark_store= by App._init_bookmarking; "server" would save state to disk.
    assert server.app.bookmark_store == "disable"


def test_no_get_or_head_route_of_the_real_shiny_app_writes_a_file_or_starts_a_process(
        client, tmp_path, monkeypatch):
    # Shiny's session routes (/session/{id}/{action}/{subpath}) are reached with a made-up id,
    # so only as far as their 404; a task that adds a download or dynamic route adds a
    # live-session case to `extra`.
    paths = get_paths(client.app)
    assert any(p.startswith("/session/") for p in paths), f"no session route among {paths}"
    # The page's own scripts and stylesheets, so the static mounts are reached at real files and
    # not only at their bare paths (a 404): the sweep reads them from the page, as a browser does.
    page = client.get("/").text
    files = ["/" + url.split("?")[0].lstrip("/")
             for url in re.findall(r'(?:src|href)="(lib/[^"]+)"', page)]
    assert any(url.endswith("/shiny.js") for url in files), f"no real static file in {files}"
    assert read_only_violations(client, monkeypatch, tmp_path, extra=files) == []


def test_an_endpoint_answering_junk_is_unreachable_and_the_others_are_still_checked(tmp_path):
    import http.server

    class Junk(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):  # a web page where the model list should be
            body = b"<html>not a model server</html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Junk)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    config = Config.model_validate({
        "endpoints": {"webui": {"base_url": f"http://127.0.0.1:{httpd.server_address[1]}/v1"},
                      "spark": {"base_url": "http://127.0.0.1:9/v1"}},
        "models": {"a": {"endpoint": "webui", "model": "w", "parser": "whisper.cpp",
                         "local": True},
                   "b": {"endpoint": "spark", "model": "w", "parser": "whisper.cpp",
                         "local": True}}})
    calls = []
    real = clients.list_models

    def list_models(name, endpoint, keys, *, timeout=5.0):
        calls.append(name)
        if name == "spark":
            return ["w"]  # the healthy one, without a real server
        return real(name, endpoint, keys, timeout=timeout)

    made = runtime.build(config, tools=Tools(None, None, None), keys=KeyRing(environ={}),
                         cache=Cache(tmp_path / "cache", max_bytes=0))
    try:
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(clients, "list_models", list_models)
            found = made.reachable()
    finally:
        httpd.shutdown()
        made.queue.close()
    assert found == {"webui": False, "spark": True} and calls == ["webui", "spark"]


def test_an_output_that_fails_sends_the_browser_no_text_of_the_error(client, probed, monkeypatch):
    # shiny 1.8.0, session/_session.py: an output that raises sends str(e) to the browser unless
    # app.sanitize_errors is set (and the exception isn't a SafeException); server.py sets it
    # (spec §6.8: no keys or paths in what leaves the engine).
    assert server.app.sanitize_errors is True

    def fails(caps):
        raise RuntimeError(f"the endpoint refused key {KEY}")

    monkeypatch.setattr(views, "capabilities_view", fails)
    messages = _session(client, {"capabilities"},
                        lambda m: any("capabilities" in x.get("errors", {}) for x in m))
    assert KEY not in json.dumps(messages)


# ---- the editor: opening an episode (Task 14) -------------------------------------------------


class Tab:
    """One browser tab's websocket to the Shiny server, driven by hand: inputs go in as
    shinyreact sends them (`<id>:shinyreact.default`), and a reader thread keeps every message."""

    def __init__(self, ws):
        self.ws = ws
        self.messages: list[dict] = []
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self) -> None:
        with contextlib.suppress(Exception):  # until the socket closes
            while True:
                self.messages.append(json.loads(self.ws.receive_text()))

    def send(self, method: str, data: dict) -> None:
        self.ws.send_text(json.dumps({"method": method, "data": data}))

    def set(self, **inputs) -> None:
        self.send("update", {f"{name}:shinyreact.default": v for name, v in inputs.items()})

    def until(self, check, timeout: float = 20.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            found = check(self)
            if found:
                return found
            time.sleep(0.02)
        raise AssertionError(f"timed out; the tab saw {self.messages[-5:]}")

    def value(self, name: str):
        """The output's latest value; KeyError while it has none."""
        for m in reversed(self.messages):
            if name in m.get("values", {}):
                return m["values"][name]
        raise KeyError(name)

    def has(self, name: str) -> bool:
        try:
            self.value(name)
        except KeyError:
            return False
        return True

    def notices(self) -> list[dict]:
        return [m["custom"]["shinyReactMessage"]["data"] for m in self.messages
                if m.get("custom", {}).get("shinyReactMessage", {}).get("id") == "notice"]


EDITOR_OUTPUTS = {"episode", "busy"}


@contextlib.contextmanager
def tab(client, outputs=EDITOR_OUTPUTS):
    with client.websocket_connect(WS, headers={"Origin": BASE}) as ws:
        t = Tab(ws)
        t.send("init", {f".clientdata_output_{name}_hidden": False for name in outputs})
        yield t


@pytest.fixture
def media_rt(tmp_path):
    """A runtime with the real ffmpeg and ffprobe, for opening episodes."""
    made = runtime.build(Config(), tools=Tools.find(), keys=KeyRing(environ={}),
                         cache=Cache(tmp_path / "cache", max_bytes=10**9))
    runtime.configure(made)
    yield made
    runtime.configure(None)
    made.queue.close()


@pytest.fixture
def media_client(media_rt):
    with TestClient(create_app(media_rt, token=TOKEN, port=PORT, shiny_app=server.app),
                    base_url=BASE) as c:
        r = c.post("/auth", content=json.dumps({"token": TOKEN}), headers={**JSON, **PAGE})
        assert r.status_code == 204
        yield c


def opened(t: Tab):
    return t.has("episode") and t.value("episode")


def has_sound_only(t: Tab):
    """The open episode, once its playback audio is there (it is shown first, without)."""
    ep = opened(t)
    return ep and ep["video"]["audio_url"] and ep


def test_with_no_episode_open_the_episode_output_is_null_and_nothing_is_busy(client):
    with tab(client) as t:
        t.until(lambda t: t.has("episode") and t.has("busy"))
        assert t.value("episode") is None and t.value("busy") is None


@pytest.mark.media
def test_opening_an_episode_sends_its_view_with_the_video_by_a_media_token(
        media_client, media_rt, tmp_path):
    video = make_episode(tmp_path / "Secret Show")
    with tab(media_client) as t:
        t.until(lambda t: t.has("episode"))
        t.set(open={"path": str(video), "n": 1})
        ep = t.until(opened)
        assert [r["text"] for r in ep["rows"]] == list(LINES)
        assert [c["text"] for r in ep["rows"] for c in r["tr"]["en"]["cues"]] == list(ENGLISH)
        url = ep["video"]["url"]
        assert re.fullmatch(r"/media/[A-Za-z0-9_-]{43}", url) and ep["video"]["audio_url"] is None
        assert media_rt.media.resolve(url.removeprefix("/media/")) == video
        assert media_rt.backend.is_open(ep["id"])
        everything = json.dumps(t.messages)
        assert "Secret Show" not in everything and str(tmp_path) not in everything
        assert t.value("busy") is None


@pytest.mark.media
def test_a_video_whose_audio_the_browser_cant_play_gets_the_playback_audio_instead(
        media_client, media_rt, tmp_path):
    # Decision 2: AC-3 can't be played by a browser, so the player gets the playback audio and no
    # picture; the audio is made into the cache, keyed by the video's quick hash (§8.8, §8.9).
    video = make_episode(tmp_path / "ac3", audio_codec="ac3")
    with tab(media_client) as t:
        t.until(lambda t: t.has("episode"))
        t.set(open={"path": str(video), "n": 1})
        ep = t.until(has_sound_only)
        assert ep["video"]["url"] is None and ep["video"]["playable_audio"] is False
        audio = media_rt.media.resolve(ep["video"]["audio_url"].removeprefix("/media/"))
        assert audio is not None and audio.name == "playback-a0.m4a"
        assert audio.parent.parent == tmp_path / "cache"
        token = ep["video"]["audio_url"].removeprefix("/media/")
    # the audio's token is the episode's too: it goes with the tab
    assert wait(lambda: media_rt.media.resolve(token) is None)


@pytest.mark.media
def test_an_episode_that_cant_be_opened_is_a_notice_and_the_editor_stays_empty(
        media_client, tmp_path):
    with tab(media_client) as t:
        t.until(lambda t: t.has("episode"))
        t.set(open={"path": "Show.mkv", "n": 1})
        notice = t.until(lambda t: t.notices())[0]
        assert notice == {"kind": "error", "text": "give the video's full path"}
        assert t.value("episode") is None


def test_an_open_request_that_isnt_a_path_is_refused_without_echoing_it(client):
    with tab(client) as t:
        t.until(lambda t: t.has("episode"))
        for bad in ({"path": 7, "n": 1}, {"n": 2}, "<img src=x>", {"path": "x" * 5000, "n": 3}):
            t.set(open=bad)
        t.until(lambda t: len(t.notices()) == 4)
        assert {n["text"] for n in t.notices()} == {"type the video's full path to open it"}
        assert "<img" not in json.dumps(t.messages)


@pytest.mark.media
def test_closing_the_tab_closes_its_episode_and_revokes_its_media(media_client, media_rt,
                                                                 tmp_path):
    first, second = make_episode(tmp_path / "one"), make_episode(tmp_path / "two")
    with tab(media_client) as t:
        t.until(lambda t: t.has("episode"))
        t.set(open={"path": str(first), "n": 1})
        one = t.until(opened)
        t.set(open={"path": str(second), "n": 2})
        two = t.until(lambda t: opened(t) and opened(t)["id"] != one["id"] and opened(t))
        # opening another episode closes the first, and its token stops working
        assert not media_rt.backend.is_open(one["id"])
        assert media_rt.media.resolve(one["video"]["url"].removeprefix("/media/")) is None
        token = two["video"]["url"].removeprefix("/media/")
        assert media_rt.media.resolve(token) == second
    deadline = time.monotonic() + 10
    while media_rt.backend.is_open(two["id"]) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not media_rt.backend.is_open(two["id"])
    assert media_rt.media.resolve(token) is None


# ---- the editor: what the browser can play (Task 14, round 14d) ------------------------------


@pytest.mark.media
def test_the_view_names_the_container_and_codecs_the_browser_is_asked_about(media_client,
                                                                           tmp_path):
    video = make_episode(tmp_path / "ep")  # tests/helpers.make_clip: MPEG-4 Part 2 and AAC in MKV
    with tab(media_client) as t:
        t.until(lambda t: t.has("episode"))
        t.set(open={"path": str(video), "n": 1})
        ep = t.until(opened)
        assert {k: ep["video"][k] for k in ("container", "video_codec", "audio_codec")} == {
            "container": "matroska,webm", "video_codec": "mpeg4", "audio_codec": "aac"}


@pytest.mark.media
def test_a_tab_whose_browser_cant_play_the_video_gets_the_playback_audio_and_its_token_goes(
        media_client, media_rt, tmp_path):
    # Spec §8.2, §8.8: the UI reports what canPlayType and the <video> say; the editor then plays
    # the playback audio with no picture, and the video's own token stops working.
    video = make_episode(tmp_path / "ep")
    with tab(media_client) as t:
        t.until(lambda t: t.has("episode"))
        t.set(open={"path": str(video), "n": 1})
        ep = t.until(opened)
        token = ep["video"]["url"].removeprefix("/media/")
        assert media_rt.media.resolve(token) == video
        # A request for an episode the tab has moved on from changes nothing: the queue runs it
        # before the bad open that follows, whose notice says it has been through.
        t.set(playback={"episode": "e" + "0" * 16, "n": 1})
        t.set(open={"n": 2})
        t.until(lambda t: t.notices())
        assert media_rt.media.resolve(token) == video and opened(t)["video"]["url"] is not None
        t.set(playback={"episode": ep["id"], "n": 2})
        audio = t.until(lambda t: opened(t)["video"]["audio_url"] and opened(t))["video"]
        assert audio["url"] is None
        played = media_rt.media.resolve(audio["audio_url"].removeprefix("/media/"))
        assert played is not None and played.name == "playback-a0.m4a"
        assert media_rt.media.resolve(token) is None
        busy = [m["values"]["busy"] for m in t.messages if "busy" in m.get("values", {})]
        assert "playback" in busy and t.value("busy") is None
        # Asked again, nothing happens: a bad open after it says it has been through.
        sent = len(t.messages)
        t.set(playback={"episode": ep["id"], "n": 3})
        t.set(open={"n": 4})
        t.until(lambda t: len(t.notices()) == 2)
        assert not any("episode" in m.get("values", {}) for m in t.messages[sent:])


@pytest.mark.media
def test_a_video_whose_chosen_audio_track_isnt_its_first_plays_that_tracks_sound_alone(
        media_client, media_rt, tmp_path):
    # Q&A item 48: the browser would play the first track under captions made from the second.
    second = make_episode(tmp_path / "second", audio_langs=("eng", "jpn"), audio_track=1)
    first = make_episode(tmp_path / "first", audio_langs=("jpn", "eng"), audio_track=0)
    with tab(media_client) as t:
        t.until(lambda t: t.has("episode"))
        t.set(open={"path": str(second), "n": 1})
        ep = t.until(has_sound_only)
        assert ep["video"]["url"] is None and ep["video"]["playable_audio"] is False
        audio = media_rt.media.resolve(ep["video"]["audio_url"].removeprefix("/media/"))
        assert audio is not None and audio.name == "playback-a1.m4a"
        t.set(open={"path": str(first), "n": 2})
        ep = t.until(lambda t: opened(t) and opened(t)["id"] != ep["id"] and opened(t))
        assert ep["video"]["url"] and ep["video"]["audio_url"] is None


# ---- the editor's queue: what it promises (Task 14, round 14e) -------------------------------


def wait(check, timeout: float = 15.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return True
        time.sleep(0.02)
    return False


class Slow:
    """Wraps a blocking callable: it records its calls in order and waits for `release`."""

    def __init__(self, real):
        self.real, self.started, self.release = real, threading.Event(), threading.Event()
        self.calls: list = []
        self.results: list = []

    def __call__(self, *args, **kwargs):
        self.calls.append(args)
        self.started.set()
        assert self.release.wait(30)
        out = self.real(*args, **kwargs)
        self.results.append(out)
        return out


def slow_media_for(rt_) -> Slow:
    slow = Slow(rt_.media_for)
    object.__setattr__(rt_, "media_for", slow)  # the runtime is frozen; this shadows the method
    return slow


def live_tokens(rt_) -> dict:
    return dict(rt_.media._issued)


def reactive_lock_held() -> bool:
    from shiny.reactive import _core

    lock = _core._reactive_environment._lock
    return lock is not None and lock.locked()


@pytest.mark.media
def test_a_tab_closing_while_the_backend_opens_leaves_no_episode_and_no_token(
        media_client, media_rt, tmp_path):
    video = make_episode(tmp_path / "one")
    slow = Slow(media_rt.backend.open)
    media_rt.backend.open = slow
    with tab(media_client) as t:
        t.until(lambda t: t.has("episode"))
        t.set(open={"path": str(video), "n": 1})
        assert slow.started.wait(10)
    slow.release.set()  # the websocket is closed; the running open goes on
    assert wait(lambda: slow.results)
    assert wait(lambda: not media_rt.backend.is_open(slow.results[0].id))
    assert wait(lambda: not live_tokens(media_rt))


@pytest.mark.media
def test_a_tab_closing_while_the_media_is_made_leaves_no_episode_and_no_token(
        media_client, media_rt, tmp_path):
    video = make_episode(tmp_path / "one", audio_codec="ac3")
    slow = slow_media_for(media_rt)
    with tab(media_client) as t:
        t.until(lambda t: t.has("episode"))
        t.set(open={"path": str(video), "n": 1})
        assert slow.started.wait(10)
    slow.release.set()
    assert wait(lambda: slow.results)
    assert wait(lambda: not media_rt.backend.is_open(slow.calls[0][0].id))
    assert wait(lambda: not live_tokens(media_rt))


@pytest.mark.media
def test_a_slow_open_holds_no_reactive_lock_and_another_tab_is_served(
        media_client, media_rt, tmp_path):
    video = make_episode(tmp_path / "one")
    slow = Slow(media_rt.backend.open)
    media_rt.backend.open = slow
    with tab(media_client) as t:
        t.until(lambda t: t.has("episode"))
        t.set(open={"path": str(video), "n": 1})
        assert slow.started.wait(10)
        t.until(lambda t: t.has("busy") and t.value("busy") == "opening")
        assert not reactive_lock_held()
        with tab(media_client) as other:  # a second tab starts and is served meanwhile
            other.until(lambda o: o.has("episode") and o.has("busy"), timeout=5)
            other.set(open="not a dict")
            other.until(lambda o: o.notices(), timeout=5)
        assert t.value("busy") == "opening"
        slow.release.set()
        t.until(opened)


@pytest.mark.media
def test_quick_opens_run_one_at_a_time_in_the_order_sent_and_leave_one_episode(
        media_client, media_rt, tmp_path):
    videos = [make_episode(tmp_path / name) for name in "abc"]
    slow = Slow(media_rt.backend.open)
    media_rt.backend.open = slow
    running = [0, 0]  # now, most at once
    real = slow.real

    def counted(path):
        running[0] += 1
        running[1] = max(running)
        try:
            return real(path)
        finally:
            running[0] -= 1

    slow.real = counted
    with tab(media_client) as t:
        t.until(lambda t: t.has("episode"))
        for n, video in enumerate(videos, 1):
            t.set(open={"path": str(video), "n": n})
        assert slow.started.wait(10)
        time.sleep(0.3)  # the others have arrived and wait
        slow.release.set()
        assert wait(lambda: len(slow.results) == 3)
        last = slow.results[-1].id
        t.until(lambda t: opened(t) and opened(t)["id"] == last)
        assert [c[0] for c in slow.calls] == [str(v) for v in videos]
        assert running[1] == 1
        assert [e.id for e in slow.results if media_rt.backend.is_open(e.id)] == [last]
        assert len(live_tokens(media_rt)) == 1


@pytest.mark.media
def test_a_failure_in_the_queue_logs_its_type_tells_the_tab_in_fixed_words_and_the_next_runs(
        media_client, media_rt, tmp_path, caplog):
    secret = str(tmp_path / "Secret Show" / "x.mkv")
    good = make_episode(tmp_path / "good")
    real = media_rt.backend.open
    failed = []

    def fails_once(path):
        if not failed:
            failed.append(path)
            raise PermissionError(13, "denied", secret)
        return real(path)

    media_rt.backend.open = fails_once
    with caplog.at_level(logging.DEBUG), tab(media_client) as t:
        t.until(lambda t: t.has("episode"))
        t.set(open={"path": str(good), "n": 1})
        t.until(lambda t: t.notices() and t.has("busy") and t.value("busy") is None)
        assert t.notices() == [{"kind": "error",
                                "text": "something went wrong (open); see the log"}]
        assert t.value("episode") is None  # the failed request left nothing open or shown
        t.set(open={"path": str(good), "n": 2})  # and the queue goes on
        assert t.until(opened)
        assert t.value("busy") is None
    assert "Secret Show" not in caplog.text
    assert "the editor's open failed: PermissionError" in caplog.text


@pytest.mark.media
def test_the_shown_episodes_token_goes_with_the_tab_though_another_open_is_still_running(
        media_client, media_rt, tmp_path):
    first, second = make_episode(tmp_path / "one"), make_episode(tmp_path / "two")
    with tab(media_client) as t:
        t.until(lambda t: t.has("episode"))
        t.set(open={"path": str(first), "n": 1})
        token = t.until(opened)["video"]["url"].removeprefix("/media/")
        slow = Slow(media_rt.backend.open)
        media_rt.backend.open = slow
        t.set(open={"path": str(second), "n": 2})
        assert slow.started.wait(10)
    # the tab is gone, the open is not: the first episode's token must not wait for it
    assert wait(lambda: media_rt.media.resolve(token) is None, timeout=5)
    slow.release.set()
    assert wait(lambda: slow.results)
    assert wait(lambda: not live_tokens(media_rt))


@pytest.mark.media
def test_an_ac3_episode_is_shown_at_once_while_its_playback_audio_is_made(
        media_client, media_rt, tmp_path):
    video = make_episode(tmp_path / "ac3", audio_codec="ac3")
    slow = slow_media_for(media_rt)
    with tab(media_client) as t:
        t.until(lambda t: t.has("episode"))
        t.set(open={"path": str(video), "n": 1})
        assert slow.started.wait(10)
        ep = t.until(opened)  # the cue list arrives before ffmpeg is done
        assert ep["video"]["url"] is None and ep["video"]["audio_url"] is None
        assert [r["text"] for r in ep["rows"]] == list(LINES)
        assert t.value("busy") == "playback"
        slow.release.set()
        ep = t.until(lambda t: opened(t) and opened(t)["video"]["audio_url"] and opened(t))
        assert media_rt.media.resolve(ep["video"]["audio_url"].removeprefix("/media/"))
        t.until(lambda t: t.value("busy") is None)


@pytest.mark.media
@pytest.mark.parametrize("how", ["no-ffmpeg", "ffmpeg-fails"])
def test_a_playback_audio_that_cant_be_made_is_a_notice_after_the_episode_opens(
        media_client, media_rt, tmp_path, monkeypatch, how):
    from vid2sub.media import preview
    from vid2sub.media.tools import ToolFailed

    video = make_episode(tmp_path / "ac3", audio_codec="ac3")
    real_open = media_rt.backend.open

    def open_then_lose_ffmpeg(path):
        ep = real_open(path)
        if how == "no-ffmpeg":
            media_rt.backend.tools = Tools(None, None, None)
        return ep

    def fails(*args, **kwargs):
        raise ToolFailed("ffmpeg", 1, f"cannot read {video}")

    media_rt.backend.open = open_then_lose_ffmpeg
    if how == "ffmpeg-fails":
        monkeypatch.setattr(preview, "playback_audio", fails)
    with tab(media_client) as t:
        t.until(lambda t: t.has("episode"))
        t.set(open={"path": str(video), "n": 1})
        ep = t.until(opened)
        note = t.until(lambda t: t.notices())[0]
        assert ep["video"]["url"] is None and ep["video"]["audio_url"] is None
        assert note["kind"] == "error"
        assert note["text"].startswith("the browser can't play this video's audio, and ")
        assert str(tmp_path) not in json.dumps(t.messages) and "cannot read" not in note["text"]
        assert t.value("busy") is None


@pytest.mark.media
def test_a_tab_closing_drops_the_requests_still_waiting_in_its_queue(
        media_client, media_rt, tmp_path):
    first, second = make_episode(tmp_path / "one"), make_episode(tmp_path / "two")
    slow = Slow(media_rt.backend.open)
    media_rt.backend.open = slow
    with tab(media_client) as t:
        t.until(lambda t: t.has("episode"))
        t.set(open={"path": str(first), "n": 1})
        assert slow.started.wait(10)
        t.set(open={"path": str(second), "n": 2})  # waits behind the first
        time.sleep(0.3)
    slow.release.set()
    assert wait(lambda: slow.results)
    assert wait(lambda: not live_tokens(media_rt) and not media_rt.backend.is_open(
        slow.results[0].id))
    time.sleep(0.5)  # long enough for a second open to have started
    assert [c[0] for c in slow.calls] == [str(first)]


@pytest.mark.media
def test_an_open_whose_media_fails_leaves_the_new_episode_no_media_of_the_old_one(
        media_client, media_rt, tmp_path):
    # With the new episode set and the old one's media still on the editor, the next request
    # would treat the new episode as playing the old one's (revoked) video URL.
    first, second = make_episode(tmp_path / "one"), make_episode(tmp_path / "two")
    real_open, real_media = media_rt.backend.open, media_rt.media_for
    opened_eps, calls = [], []

    def recording_open(path):
        opened_eps.append(real_open(path))
        return opened_eps[-1]

    def fails_for_the_second(ep, **kwargs):
        calls.append(ep.video)
        if ep.video == second:
            raise KeyError("not one media_for expects")
        return real_media(ep, **kwargs)

    media_rt.backend.open = recording_open
    object.__setattr__(media_rt, "media_for", fails_for_the_second)
    with tab(media_client) as t:
        t.until(lambda t: t.has("episode"))
        t.set(open={"path": str(first), "n": 1})
        t.until(opened)
        t.set(open={"path": str(second), "n": 2})
        t.until(lambda t: t.notices())
        assert t.notices()[0]["text"] == "something went wrong (open); see the log"
        # A page that asks for the playback audio of the new episode has no video to swap out:
        # ffmpeg is not asked again, and nothing is published for it.
        sent = len(t.messages)
        t.set(playback={"episode": opened_eps[1].id, "n": 3})
        t.set(open={"n": 4})
        t.until(lambda t: len(t.notices()) == 2)
        assert not any(m.get("values", {}).get("busy") == "playback" for m in t.messages[sent:])
        assert calls == [first, second]


# ---- the editor: edits, undo and redo (Task 15) -----------------------------------------------


def opened_in(t: Tab, video) -> dict:
    t.until(lambda t: t.has("episode"))
    t.set(open={"path": str(video), "n": 1})
    return t.until(opened)


def latest(t: Tab, check):
    """The episode output once `check(episode)` holds."""
    return t.until(lambda t: opened(t) and check(t.value("episode")) and t.value("episode"))


@pytest.mark.media
def test_edits_undo_and_redo_reach_the_episode_one_at_a_time_in_the_order_sent(
        media_client, tmp_path):
    video = make_episode(tmp_path / "ep")
    with tab(media_client) as t:
        ep = opened_in(t, video)
        first = ep["rows"][0]
        ask = {"episode": ep["id"]}
        # sent back to back, each in its own message, as the frontend's pacer sends them
        t.set(edit={**ask, "n": 1, "op": {"op": "set_text", "cue": first["id"], "text": "やあ"}})
        t.set(edit={**ask, "n": 2, "op": {"op": "nudge", "cue": first["id"], "delta_ms": 100}})
        t.set(undo={**ask, "n": 3})
        t.set(redo={**ask, "n": 4})
        t.set(undo={**ask, "n": 5})
        done = latest(t, lambda e: e["rows"][0]["text"] == "やあ" and e["can_redo"])
        assert done["rows"][0]["start_ms"] == first["start_ms"]  # the nudge is undone again
        assert done["dirty"] and done["can_undo"]
        # the translation re-points nowhere new, but its source text changed: it is stale
        assert "stale" in done["rows"][0]["tr"]["en"]["cues"][0]["flags"]
        t.set(undo={**ask, "n": 6})
        clean = latest(t, lambda e: not e["dirty"])
        assert clean["rows"][0]["text"] == first["text"] and not clean["can_undo"]


@pytest.mark.media
def test_a_bad_edit_is_a_notice_naming_the_field_and_never_what_was_sent(media_client,
                                                                        tmp_path):
    video = make_episode(tmp_path / "ep")
    with tab(media_client) as t:
        ep = opened_in(t, video)
        cue = ep["rows"][0]["id"]
        for n, op in enumerate([
            {"op": "set_text", "cue": cue, "text": "x", "<img src=x>": 1},  # an unknown field
            {"op": "set_text", "cue": "<script>", "text": "x"},  # not a cue id's shape
            {"op": "nudge", "cue": cue, "delta_ms": "100"},  # a string is never a number
            {"op": "merge_next", "cue": ep["rows"][-1]["id"], "id": "cd0000001",
             "joined": {}},  # the rules refuse it
            # a new cue's id, drawn by the page (Decision 31): its shape, then that it is free
            {"op": "insert", "start_ms": 3100, "end_ms": 3500, "text": "x", "id": "<b>"},
            {"op": "insert", "start_ms": 3100, "end_ms": 3500, "text": "x", "id": cue},
        ]):
            t.set(edit={"episode": ep["id"], "n": n, "op": op})
        t.until(lambda t: len(t.notices()) == 6)
        assert [n["text"] for n in t.notices()] == [
            "this edit can't be made: it has a field no edit has",
            "this edit can't be made: cue isn't valid",
            "this edit can't be made: delta_ms has the wrong type",
            "the last cue has no next cue to merge with",
            "this edit can't be made: id isn't valid",
            "a new cue's id is already in use; try again",
        ]
        assert "<img" not in json.dumps(t.messages) and "<script>" not in json.dumps(t.messages)
        assert "<b>" not in json.dumps(t.messages)
        assert not t.value("episode")["dirty"]


@pytest.mark.media
def test_an_edit_for_an_episode_the_tab_has_moved_on_from_is_dropped(media_client, tmp_path):
    first, second = make_episode(tmp_path / "one"), make_episode(tmp_path / "two")
    with tab(media_client) as t:
        one = opened_in(t, first)
        t.set(open={"path": str(second), "n": 2})
        two = t.until(lambda t: opened(t) and opened(t)["id"] != one["id"] and opened(t))
        t.set(edit={"episode": one["id"], "n": 3,
                    "op": {"op": "delete", "cue": one["rows"][0]["id"]}})
        t.set(edit={"episode": two["id"], "n": 4,
                    "op": {"op": "set_text", "cue": two["rows"][1]["id"], "text": "二"}})
        done = latest(t, lambda e: e["rows"][1]["text"] == "二")
        assert len(done["rows"]) == len(LINES) and t.notices() == []


@pytest.mark.media
def test_an_edit_holding_a_list_is_read_as_json_has_it_though_shiny_makes_lists_tuples(
        media_client, tmp_path):
    # Shiny 1.8.0 decodes every JSON array in a message as a tuple (_utils.lists_to_tuples),
    # and ops.parse_op is strict: a tuple is not a list.
    video = make_episode(tmp_path / "ep")
    with tab(media_client) as t:
        ep = opened_in(t, video)
        t.set(edit={"episode": ep["id"], "n": 1, "op": {
            "op": "replace_all", "find": "元気", "replace": "げんき",
            "tracks": ["source", "en"]}})
        done = latest(t, lambda e: e["rows"][1]["text"] == "げんきですか")
        assert done["rows"][2]["text"] == "はい、げんきです" and t.notices() == []


# ---- fix round 15d: found by Task 15's Spec review ----------------------------------------------


def episodes_published(t: Tab) -> int:
    return sum(1 for m in t.messages if (m.get("values") or {}).get("episode") is not None)


@pytest.mark.media
def test_edits_sent_while_the_sound_is_made_wait_for_it_and_land_in_the_order_sent(
        media_client, media_rt, tmp_path):
    # the queue's promise: an edit never runs ahead of the open it was sent behind
    video = make_episode(tmp_path / "ep", audio_codec="ac3")
    slow = slow_media_for(media_rt)
    with tab(media_client) as t:
        t.until(lambda t: t.has("episode"))
        t.set(open={"path": str(video), "n": 1})
        assert slow.started.wait(10)
        ep = t.until(lambda t: t.has("busy") and t.value("busy") == "playback"
                     and t.value("episode"))
        cue = ep["rows"][0]["id"]
        for n, text in enumerate(["first", "second"], start=2):
            t.set(edit={"episode": ep["id"], "n": n,
                        "op": {"op": "set_text", "cue": cue, "text": text}})
        time.sleep(0.5)  # long enough for an edit that ran ahead to have been published
        assert t.value("episode")["rows"][0]["text"] == ep["rows"][0]["text"]
        assert not t.value("episode")["dirty"]
        slow.release.set()
        done = latest(t, lambda e: e["rows"][0]["text"] == "second")
        assert done["dirty"] and done["can_undo"]
        t.set(undo={"episode": ep["id"], "n": 4})
        back = latest(t, lambda e: e["rows"][0]["text"] == "first")
        assert back["can_undo"]  # two steps were made, in order, not one over the other


@pytest.mark.media
def test_an_undo_naming_an_episode_the_tab_has_moved_on_from_changes_nothing(
        media_client, tmp_path):
    first, second = make_episode(tmp_path / "one"), make_episode(tmp_path / "two")
    with tab(media_client) as t:
        one = opened_in(t, first)
        t.set(open={"path": str(second), "n": 2})
        two = t.until(lambda t: opened(t) and opened(t)["id"] != one["id"] and opened(t))
        t.set(edit={"episode": two["id"], "n": 3,
                    "op": {"op": "set_text", "cue": two["rows"][0]["id"], "text": "二"}})
        latest(t, lambda e: e["rows"][0]["text"] == "二")
        seen = episodes_published(t)
        t.set(undo={"episode": one["id"], "n": 4})
        t.set(redo={"episode": one["id"], "n": 5})
        time.sleep(0.5)
        assert episodes_published(t) == seen
        now = t.value("episode")
        assert now["rows"][0]["text"] == "二" and now["dirty"] and t.notices() == []


@pytest.mark.media
def test_an_undo_with_nothing_to_undo_publishes_nothing(media_client, tmp_path):
    video = make_episode(tmp_path / "ep")
    with tab(media_client) as t:
        ep = opened_in(t, video)
        cue = ep["rows"][0]["id"]
        for n, text in enumerate(["a", "b", "c"], start=1):
            t.set(edit={"episode": ep["id"], "n": n,
                        "op": {"op": "set_text", "cue": cue, "text": text}})
        latest(t, lambda e: e["rows"][0]["text"] == "c")
        seen = episodes_published(t)
        for n in range(4, 8):  # four undos of three steps
            t.set(undo={"episode": ep["id"], "n": n})
        latest(t, lambda e: not e["can_undo"])
        time.sleep(0.5)
        assert episodes_published(t) - seen == 3


def test_as_json_turns_tuples_into_lists_and_changes_nothing_else():
    got = server.as_json({"a": True, "b": (False, 1, "1", (2.5, None)), "c": {"d": ("e",)}})
    assert got == {"a": True, "b": [False, 1, "1", [2.5, None]], "c": {"d": ["e"]}}
    assert json.dumps(got) == '{"a": true, "b": [false, 1, "1", [2.5, null]], "c": {"d": ["e"]}}'
    assert got["a"] is True and got["b"][0] is False  # a bool never becomes 1 or 0


# ---- the editor: Save and picking a version (Task 16) ------------------------------------------


def results(t: Tab) -> list[dict]:
    return [m["custom"]["shinyReactMessage"]["data"] for m in t.messages
            if m.get("custom", {}).get("shinyReactMessage", {}).get("id") == "save_result"]


def busy_seen(t: Tab) -> list:
    return [m["values"]["busy"] for m in t.messages if "busy" in m.get("values", {})]


@pytest.mark.media
def test_save_writes_a_version_then_the_files_and_says_what_it_wrote(media_client, tmp_path):
    # S29, spec §14.5.
    video = make_episode(tmp_path / "ep")
    srt = video.with_name("Show - S01E01.ja.srt")
    with tab(media_client) as t:
        ep = opened_in(t, video)
        ask = {"episode": ep["id"]}
        t.set(edit={**ask, "n": 1, "op": {"op": "set_text", "cue": ep["rows"][0]["id"],
                                          "text": "おはようございます"}})
        latest(t, lambda e: e["dirty"])
        t.set(save={**ask, "n": 2, "formats": ["srt"]})
        result = t.until(lambda t: results(t) and results(t)[0])
        assert result == {"episode": ep["id"], "kind": "save", "written": [srt.name],
                          "foreign": [], "conflicts": [], "notes": []}
        saved = latest(t, lambda e: not e["dirty"])
        assert saved["rows"][0]["text"] == "おはようございます" and not saved["can_undo"]
        assert saved["heads"]["ja"] != ep["heads"]["ja"]
        assert saved["heads"]["en"] == ep["heads"]["en"]
        assert "saving" in busy_seen(t) and t.value("busy") is None
        assert "おはようございます" in srt.read_text(encoding="utf-8")


@pytest.mark.media
def test_two_tabs_saving_one_episode_end_in_a_conflict_the_second_sees_and_a_pick_resolves(
        media_client, tmp_path):
    # Review Focus 4, S32: each Save is compare-and-swap on the version its tab opened.
    video = make_episode(tmp_path / "ep")
    with tab(media_client) as a, tab(media_client) as b:
        ep_a, ep_b = opened_in(a, video), opened_in(b, video)
        cue = ep_a["rows"][1]["id"]
        for t, ep, text in ((a, ep_a, "げんき？"), (b, ep_b, "元気？")):
            t.set(edit={"episode": ep["id"], "n": 1,
                        "op": {"op": "set_text", "cue": cue, "text": text}})
            latest(t, lambda e: e["dirty"])
            t.set(save={"episode": ep["id"], "n": 2, "formats": ["srt"]})
            t.until(lambda t: results(t))
        assert results(a)[0]["conflicts"] == [] and results(b)[0]["conflicts"] == ["ja"]
        assert results(b)[0]["written"] == []  # a track in conflict is never written
        torn = latest(b, lambda e: e["conflicts"])
        assert [t["in_conflict"] for t in torn["tracks"] if t["key"] == "ja"] == [True]
        versions = torn["conflicts"]["ja"]
        assert len(versions) == 2 and {v["by"] for v in versions} == {"editor"}
        # keep the second tab's own version: the file still holds the first's, so it is written
        theirs = latest(a, lambda e: not e["dirty"])["heads"]["ja"]
        mine = next(v["rendition"] for v in versions if v["rendition"] != theirs)
        b.set(resolve={"episode": torn["id"], "n": 3, "track": "ja", "rendition": mine})
        picked = b.until(lambda t: len(results(t)) == 2 and results(t)[1])
        assert picked["kind"] == "pick" and picked["written"] == ["Show - S01E01.ja.srt"]
        whole = latest(b, lambda e: not e["conflicts"])
        assert whole["rows"][1]["text"] == "元気？"
        assert "元気？" in video.with_name("Show - S01E01.ja.srt").read_text(encoding="utf-8")
        assert "picking" in busy_seen(b)


@pytest.mark.media
def test_a_save_or_pick_that_isnt_well_formed_is_refused_without_echoing_it(media_client,
                                                                            tmp_path):
    video = make_episode(tmp_path / "ep")
    with tab(media_client) as t:
        ep = opened_in(t, video)
        ask = {"episode": ep["id"]}
        t.set(save={**ask, "n": 1, "formats": ["<mp4>"]})
        t.set(save={**ask, "n": 2, "formats": "srt"})
        t.set(save={**ask, "n": 6, "formats": ["ass"]})  # exactly srt, or srt and ass
        t.set(save={**ask, "n": 7, "formats": ["srt", "srt"]})
        t.set(resolve={**ask, "n": 3, "track": "ja", "rendition": "<script>"})
        t.set(resolve={**ask, "n": 4, "track": "<b>", "rendition": "r_" + "0" * 16})
        t.set(resolve={**ask, "n": 5, "track": "ja", "rendition": "r_" + "0" * 16})
        t.until(lambda t: len(t.notices()) == 7)
        assert [n["text"] for n in t.notices()] == [
            "Save writes srt, and ass when asked for: nothing was saved",
            "Save writes srt, and ass when asked for: nothing was saved",
            "Save writes srt, and ass when asked for: nothing was saved",
            "Save writes srt, and ass when asked for: nothing was saved",
            "pick one of the track's versions",
            "there's no such track",
            "the ja track has only one version: there's nothing to pick",
        ]
        assert results(t) == [] and "<" not in json.dumps(t.notices())


def applied(t: Tab) -> list[dict]:
    return [m["custom"]["shinyReactMessage"]["data"] for m in t.messages
            if m.get("custom", {}).get("shinyReactMessage", {}).get("id") == "applied"]


@pytest.mark.media
def test_each_edit_undo_and_redo_is_answered_with_whether_it_was_made(media_client, tmp_path):
    # The crash draft keeps only what the server did, and a Restore counts what it refused
    # (Decision 31).
    video = make_episode(tmp_path / "ep")
    with tab(media_client) as t:
        ep = opened_in(t, video)
        ask, rows = {"episode": ep["id"]}, ep["rows"]
        t.set(edit={**ask, "n": 1,
                    "op": {"op": "set_text", "cue": rows[0]["id"], "text": "やあ"}})
        t.set(edit={**ask, "n": 2, "op": {"op": "merge_next", "cue": rows[-1]["id"],
                                          "id": "cd0000001", "joined": {}}})  # the rules refuse it
        t.set(undo={**ask, "n": 3})
        t.set(redo={**ask, "n": 4})
        t.set(edit={**ask, "n": 5, "op": {"op": "set_text", "cue": "<b>", "text": "x"}})
        t.set(undo={**ask, "n": "6"})  # a count that isn't a number is never sent back
        t.set(undo={**ask, "n": 7})  # answered after 6 was done: the queue keeps their order
        t.until(lambda t: len(applied(t)) == 6)
        assert applied(t) == [
            {"episode": ep["id"], "n": n, "ok": ok, "changed": changed} for n, ok, changed in
            ((1, True, True), (2, False, False), (3, True, True), (4, True, True),
             (5, False, False), (7, True, False))]  # 7: nothing left to undo


@pytest.mark.media
def test_an_edit_undo_or_redo_that_changes_nothing_is_answered_as_made_but_unchanged(
        media_client, tmp_path):
    # Restore follows the server's undo history, so the draft keeps only the steps that moved it
    # (Task 17's review: an edit that changed nothing pushes no undo step).
    video = make_episode(tmp_path / "ep")
    with tab(media_client) as t:
        ep = opened_in(t, video)
        ask, first = {"episode": ep["id"]}, ep["rows"][0]
        t.set(edit={**ask, "n": 1, "op": {"op": "set_text", "cue": first["id"],
                                          "text": first["text"]}})  # the text it has
        t.set(redo={**ask, "n": 2})  # nothing to redo
        t.set(edit={**ask, "n": 3, "op": {"op": "set_text", "cue": first["id"], "text": "やあ"}})
        t.set(undo={**ask, "n": 4})
        t.set(redo={**ask, "n": 5})
        t.until(lambda t: len(applied(t)) == 5)
        assert [(a["n"], a["ok"], a["changed"]) for a in applied(t)] == [
            (1, True, False), (2, True, False), (3, True, True), (4, True, True),
            (5, True, True)]


def index_of(t: Tab, check) -> int:
    """Where in what the tab received the first message satisfying `check` came."""
    return next(i for i, m in enumerate(t.messages) if check(m))


def custom_id(m: dict) -> str | None:
    return m.get("custom", {}).get("shinyReactMessage", {}).get("id")


@pytest.mark.media
def test_save_result_comes_after_the_saved_episode_and_applied_after_the_edit_is_shown(
        media_client, tmp_path):
    # Brief: `save_result` is "sent after the new episode is published"; the same goes for
    # `applied`, so a tab hearing either finds the episode it speaks of already there.
    video = make_episode(tmp_path / "ep")
    with tab(media_client) as t:
        ep = opened_in(t, video)
        ask = {"episode": ep["id"]}
        t.set(edit={**ask, "n": 1, "op": {"op": "set_text", "cue": ep["rows"][0]["id"],
                                          "text": "おはよう！"}})
        t.until(lambda t: applied(t))
        shown = index_of(t, lambda m: (e := m.get("values", {}).get("episode"))
                         and e["rows"][0]["text"] == "おはよう！")
        assert shown < index_of(t, lambda m: custom_id(m) == "applied")
        t.set(save={**ask, "n": 2, "formats": ["srt"]})
        t.until(lambda t: results(t))
        saved = index_of(t, lambda m: (e := m.get("values", {}).get("episode"))
                         and e["heads"]["ja"] != ep["heads"]["ja"])
        assert saved < index_of(t, lambda m: custom_id(m) == "save_result")


@pytest.mark.media
def test_a_refused_save_or_pick_leaves_nothing_busy(media_client, tmp_path, monkeypatch):
    # A busy that stayed "saving" or "picking" would keep Save disabled for good.
    video = make_episode(tmp_path / "ep")

    def refuse(self, ep, *, formats):
        raise SaveError("nothing was saved: the disk said no")

    monkeypatch.setattr(LocalBackend, "save", refuse)
    with tab(media_client) as t:
        ep = opened_in(t, video)
        ask = {"episode": ep["id"]}
        t.set(save={**ask, "n": 1, "formats": ["srt"]})
        t.until(lambda t: len(t.notices()) == 1)
        t.until(lambda t: t.value("busy") is None)  # the Save's own, before the pick is sent
        t.set(resolve={**ask, "n": 2, "track": "ja", "rendition": "r_" + "0" * 16})
        t.until(lambda t: len(t.notices()) == 2)
        t.until(lambda t: t.value("busy") is None)
        assert {"saving", "picking"} <= set(busy_seen(t))
        assert t.notices()[0]["text"] == "nothing was saved: the disk said no"


@pytest.mark.media
def test_an_edit_sent_during_a_slow_save_waits_for_it_and_lands_on_the_saved_episode(
        media_client, tmp_path, monkeypatch):
    # Review Focus 4: "no edit is lost to a Save running at the same time". The Save is held open
    # in the backend (the thread blocking on the disk); the edit behind it must not run until it
    # ends, and then lands on the episode the Save returned.
    video = make_episode(tmp_path / "ep")
    started, release = threading.Event(), threading.Event()
    real = LocalBackend.save

    def slow(self, ep, *, formats):
        started.set()
        assert release.wait(20)
        return real(self, ep, formats=formats)

    monkeypatch.setattr(LocalBackend, "save", slow)
    with tab(media_client) as t:
        ep = opened_in(t, video)
        ask, rows = {"episode": ep["id"]}, ep["rows"]
        t.set(edit={**ask, "n": 1, "op": {"op": "set_text", "cue": rows[0]["id"],
                                          "text": "おはよう！"}})
        latest(t, lambda e: e["dirty"])
        t.set(save={**ask, "n": 2, "formats": ["srt"]})
        assert started.wait(20)
        t.set(edit={**ask, "n": 3, "op": {"op": "set_text", "cue": rows[1]["id"],
                                          "text": "元気？"}})
        time.sleep(0.5)  # long enough for a Save that didn't hold the queue to be passed
        assert [a["n"] for a in applied(t)] == [1] and t.value("busy") == "saving"
        release.set()
        t.until(lambda t: len(applied(t)) == 2)
        final = latest(t, lambda e: e["rows"][1]["text"] == "元気？")
        assert final["dirty"] and final["rows"][0]["text"] == "おはよう！"
        third = index_of(t, lambda m: custom_id(m) == "applied"
                         and m["custom"]["shinyReactMessage"]["data"]["n"] == 3)
        assert index_of(t, lambda m: custom_id(m) == "save_result") < third
        srt = video.with_name("Show - S01E01.ja.srt")
        assert "元気？" not in srt.read_text(encoding="utf-8")  # the Save wrote without it


# ---- the editor: retranslating (Task 17) -------------------------------------------------------


class Translating(LocalBackend):
    """The backend with a model that answers "EN <id>" for each cue it is asked, keeping each
    batch and each call's cloud policy; `gate`, once set, holds every batch until it opens, and
    `fail` is raised where the model would be picked."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.batches: list[list[str]] = []
        self.policies: list = []
        self.gate: threading.Event | None = None
        self.fail: Exception | None = None
        self.on_batch = None  # the last retranslation's, to call late

    def retranslate(self, ep, track, *, ids, model=None, allow_cloud=False, on_batch=None):
        self.on_batch = on_batch
        return super().retranslate(ep, track, ids=ids, model=model, allow_cloud=allow_cloud,
                                   on_batch=on_batch)

    def _translator(self, lang, model, allow_cloud):
        if self.fail is not None:
            raise self.fail
        return "gemma", ModelEntry(endpoint="spark", model="gemma", task="translate", local=True)

    def _ask(self, name, entry, policy):
        self.policies.append(policy)

        def ask(system, prompt, data_model):
            if self.gate is not None:
                assert self.gate.wait(20)
            ids = re.findall(r"^\[(\S+)\] \(max", prompt, flags=re.MULTILINE)
            self.batches.append(ids)
            return data_model.model_validate(
                {"items": [{"src": [i], "text": f"EN {i}"} for i in ids]})

        return ask


@pytest.fixture
def tr_rt(tmp_path):
    made = runtime.build(Config(), tools=Tools.find(), keys=KeyRing(environ={}),
                         cache=Cache(tmp_path / "cache", max_bytes=10**9))
    made = dataclasses.replace(made, backend=Translating(made.config, made.backend.tools,
                                                         made.keys, made.backend.cache))
    runtime.configure(made)
    yield made
    runtime.configure(None)
    made.queue.close()


@pytest.fixture
def tr_client(tr_rt):
    with TestClient(create_app(tr_rt, token=TOKEN, port=PORT, shiny_app=server.app),
                    base_url=BASE) as c:
        r = c.post("/auth", content=json.dumps({"token": TOKEN}), headers={**JSON, **PAGE})
        assert r.status_code == 204
        yield c


def retranslated(t: Tab) -> list[dict]:
    return [m["custom"]["shinyReactMessage"]["data"] for m in t.messages
            if m.get("custom", {}).get("shinyReactMessage", {}).get("id") == "retranslate_result"]


def progress_seen(t: Tab) -> list:
    return [m["values"]["progress"] for m in t.messages if "progress" in m.get("values", {})]


def en_texts(ep: dict) -> list[str]:
    return [c["text"] for row in ep["rows"] for c in row["tr"]["en"]["cues"]]


RETRANSLATE_OUTPUTS = {"episode", "busy", "progress"}


@pytest.mark.media
def test_retranslating_stale_redoes_only_the_changed_cue_and_shows_that_it_is_working(
        tr_client, tr_rt, tmp_path):
    # S30, spec §13.4: only the stale cue changes; busy and each batch's progress are shown.
    video = make_episode(tmp_path / "ep")
    with tab(tr_client, RETRANSLATE_OUTPUTS) as t:
        ep = opened_in(t, video)
        ask = {"episode": ep["id"]}
        t.set(edit={**ask, "n": 1, "op": {"op": "set_text", "cue": ep["rows"][1]["id"],
                                          "text": "お元気ですか"}})
        latest(t, lambda e: e["dirty"])
        t.set(retranslate={**ask, "n": 2, "track": "en", "ids": None, "allow_cloud": False})
        assert t.until(lambda t: retranslated(t)) == [
            {"episode": ep["id"], "n": 2, "ok": True, "changed": 1, "added": 1}]
        done = latest(t, lambda e: en_texts(e)[1].startswith("EN "))
        assert en_texts(done) == [ENGLISH[0], f"EN {ep['rows'][1]['id']}", ENGLISH[2]]
        assert "stale" not in done["rows"][1]["tr"]["en"]["cues"][0]["flags"]
        assert tr_rt.backend.batches == [[ep["rows"][1]["id"]]]
        assert [p.allow_cloud for p in tr_rt.backend.policies] == [False]
        assert "retranslating" in busy_seen(t) and t.value("busy") is None
        assert {"done": 1, "of": 1} in progress_seen(t) and t.value("progress") is None
        t.set(undo={**ask, "n": 3})  # one undo step
        back = latest(t, lambda e: not en_texts(e)[1].startswith("EN "))
        assert en_texts(back) == list(ENGLISH)


@pytest.mark.media
def test_named_cues_are_retranslated_even_where_a_translation_was_edited(tr_client, tr_rt,
                                                                       tmp_path):
    # Decision 8: the person asked, so an edited translation is replaced.
    video = make_episode(tmp_path / "ep")
    with tab(tr_client, RETRANSLATE_OUTPUTS) as t:
        ep = opened_in(t, video)
        ask = {"episode": ep["id"]}
        first = ep["rows"][0]
        t.set(edit={**ask, "n": 1, "op": {"op": "set_translation_text", "track": "en",
                                          "cue": first["tr"]["en"]["cues"][0]["id"],
                                          "text": "Morning!"}})
        latest(t, lambda e: en_texts(e)[0] == "Morning!")
        t.set(retranslate={**ask, "n": 2, "track": "en", "ids": [first["id"]],
                           "allow_cloud": False})
        t.set(retranslate={**ask, "n": 3, "track": "en", "ids": None, "allow_cloud": False})
        t.until(lambda t: len(retranslated(t)) == 2)
        assert [r["changed"] for r in retranslated(t)] == [1, 0]  # then nothing is stale
        assert en_texts(t.value("episode"))[0] == f"EN {first['id']}"


@pytest.mark.media
def test_a_retranslation_that_only_drops_a_translation_counts_it_as_changed(tr_client, tr_rt,
                                                                           tmp_path):
    # Task 7 round 7a (I2): a source line deleted in another program leaves its translation
    # nothing to translate from; Retranslate stale drops it, asks no model, and says it changed.
    from episodes import source_cues, write_track

    from vid2sub import store

    video = make_episode(tmp_path / "ep")
    head = store.load(video)[0].head("ja").rendition
    write_track(video, "ja", source_cues(3)[:2], role="source", replaces=head)
    with tab(tr_client, RETRANSLATE_OUTPUTS) as t:
        ep = opened_in(t, video)
        t.set(retranslate={"episode": ep["id"], "n": 1, "track": "en", "ids": None,
                           "allow_cloud": False})
        assert t.until(lambda t: retranslated(t)) == [
            {"episode": ep["id"], "n": 1, "ok": True, "changed": 1, "added": 0}]  # a drop only
        assert tr_rt.backend.batches == [] and tr_rt.backend.policies == []
        assert en_texts(t.value("episode")) == list(ENGLISH[:2])


@pytest.mark.media
def test_an_edit_sent_while_retranslating_waits_its_turn_and_lands_on_the_new_episode(
        tr_client, tr_rt, tmp_path):
    video = make_episode(tmp_path / "ep")
    tr_rt.backend.gate = gate = threading.Event()
    with tab(tr_client, RETRANSLATE_OUTPUTS) as t:
        ep = opened_in(t, video)
        ask = {"episode": ep["id"]}
        t.set(retranslate={**ask, "n": 1, "track": "en", "ids": [ep["rows"][0]["id"]],
                           "allow_cloud": False})
        t.until(lambda t: t.value("busy") == "retranslating")
        t.set(edit={**ask, "n": 2, "op": {"op": "set_text", "cue": ep["rows"][2]["id"],
                                          "text": "はい"}})
        time.sleep(0.5)
        assert not t.value("episode")["dirty"]  # the edit waits for the retranslation
        gate.set()
        done = latest(t, lambda e: e["rows"][2]["text"] == "はい")
        assert en_texts(done)[0] == f"EN {ep['rows'][0]['id']}"
        t.set(undo={**ask, "n": 3})  # the edit came after the retranslation: undone first
        back = latest(t, lambda e: e["rows"][2]["text"] != "はい")
        assert en_texts(back)[0] == f"EN {ep['rows'][0]['id']}"


@pytest.mark.media
def test_allow_cloud_is_the_requests_own_true_or_false_and_anything_else_is_refused(
        tr_client, tr_rt, tmp_path):
    # Spec §7.2: the editor's box, unticked every time; nothing presets it, so a request that
    # doesn't say true or false (missing, "true", 1) asks no model.
    video = make_episode(tmp_path / "ep")
    with tab(tr_client, RETRANSLATE_OUTPUTS) as t:
        ep = opened_in(t, video)
        cue = ep["rows"][0]["id"]
        ask = {"episode": ep["id"], "track": "en", "ids": [cue]}
        t.set(retranslate={**ask, "n": 1})
        t.set(retranslate={**ask, "n": 2, "allow_cloud": "true"})
        t.set(retranslate={**ask, "n": 3, "allow_cloud": 1})
        t.until(lambda t: len(retranslated(t)) == 3)
        assert [n["text"] for n in t.notices()] == ["pick the cues to retranslate"] * 3
        assert tr_rt.backend.policies == []
        t.set(retranslate={**ask, "n": 4, "allow_cloud": True})
        t.until(lambda t: len(retranslated(t)) == 4)
        assert [p.allow_cloud for p in tr_rt.backend.policies] == [True]


@pytest.mark.media
def test_cues_that_arent_cue_ids_or_a_track_that_isnt_one_are_refused_without_echoing_them(
        tr_client, tr_rt, tmp_path):
    video = make_episode(tmp_path / "ep")
    with tab(tr_client, RETRANSLATE_OUTPUTS) as t:
        ep = opened_in(t, video)
        ask = {"episode": ep["id"], "allow_cloud": False}
        t.set(retranslate={**ask, "n": 1, "track": "en", "ids": ["<script>"]})
        t.set(retranslate={**ask, "n": 2, "track": "en", "ids": []})
        t.set(retranslate={**ask, "n": 3, "track": "<b>en</b>", "ids": None})
        t.set(retranslate={**ask, "n": 4, "track": "en", "ids": ["c" + "0" * 8]})
        t.until(lambda t: len(retranslated(t)) == 4)
        assert [n["text"] for n in t.notices()] == [
            "pick the cues to retranslate", "pick the cues to retranslate",
            "there's no such track", "one of those cues isn't in the source track"]
        assert "<" not in json.dumps(t.notices()) and tr_rt.backend.batches == []
        assert [r["changed"] for r in retranslated(t)] == [0, 0, 0, 0]


@pytest.mark.media
def test_a_retranslation_that_cant_run_is_a_notice_with_the_fix_and_changes_nothing(
        tr_client, tr_rt, tmp_path):
    # Spec §17.3: each error with the hint that names its fix.
    video = make_episode(tmp_path / "ep")
    with tab(tr_client, RETRANSLATE_OUTPUTS) as t:
        ep = opened_in(t, video)
        ask = {"episode": ep["id"], "track": "en", "ids": [ep["rows"][0]["id"]],
               "allow_cloud": False}
        tr_rt.backend.fail = EngineError(
            "connection", "the translation model's server isn't reachable",
            hint="is it running? For the Spark: is `make tunnel` running?")
        t.set(retranslate={**ask, "n": 1})
        t.until(lambda t: len(retranslated(t)) == 1)
        assert t.value("busy") is None  # a refusal that is a RetranslateError frees the tab too
        tr_rt.backend.fail = EngineError("cloud_not_allowed", "cloud is a cloud model, and this "
                                         "run doesn't allow cloud models",
                                         hint="add --allow-cloud to send audio or text to it")
        t.set(retranslate={**ask, "n": 2})
        t.until(lambda t: len(retranslated(t)) == 2)
        tr_rt.backend.fail = TranslationFailed("the model couldn't translate cue ca0000000 in "
                                               "the required shape")
        t.set(retranslate={**ask, "n": 3})
        t.until(lambda t: len(retranslated(t)) == 3)
        tr_rt.backend.fail = EngineError(
            "unavailable", "no usable translation model",
            hint="cloud: a cloud model: needs --allow-cloud; gemma: not in the translate route "
                 "for ja; choose it with --model")
        t.set(retranslate={**ask, "n": 4})
        t.until(lambda t: len(retranslated(t)) == 4)
        video.with_name("vid2sub.glossary.toml").write_bytes(b"\xff\xfe not utf-8")
        tr_rt.backend.fail = None
        t.set(retranslate={**ask, "n": 5})
        t.until(lambda t: len(retranslated(t)) == 5)
        t.set(retranslate={**ask, "n": 6, "ids": None})  # "Retranslate stale" fails the same way
        t.until(lambda t: len(retranslated(t)) == 6)
        assert [n["text"] for n in t.notices()] == [
            ("couldn't retranslate: the translation model's server isn't reachable → is it "
             "running? For the Spark: is `make tunnel` running?"),
            ("couldn't retranslate: cloud is a cloud model, and this run doesn't allow cloud "
             "models → tick Allow cloud models, then retranslate again"),
            ("couldn't retranslate: the model couldn't translate cue ca0000000 in the required "
             "shape → retranslate again, or pick fewer cues"),
            ("couldn't retranslate: no usable translation model → cloud: a cloud model: needs "
             "Allow cloud models ticked; gemma: not in the translate route for ja"),
            "the glossary isn't UTF-8; save it as UTF-8",
            "the glossary isn't UTF-8; save it as UTF-8"]
        # failed, so the page never says "nothing was stale" (Task 17's review)
        assert [(r["ok"], r["changed"]) for r in retranslated(t)] == [(False, 0)] * 6
        assert not t.value("episode")["dirty"] and t.value("busy") is None


@pytest.mark.media
def test_a_server_error_or_timeout_never_says_the_editor_retries_but_says_what_to_do(
        tr_client, tr_rt, tmp_path):
    # Task 17's Spec review (I-3): the CLI retries twice; the editor never does, so a hint that
    # says so would have the person wait for a retry that doesn't come.
    video = make_episode(tmp_path / "ep")
    with tab(tr_client, RETRANSLATE_OUTPUTS) as t:
        ep = opened_in(t, video)
        ask = {"episode": ep["id"], "track": "en", "ids": [ep["rows"][0]["id"]],
               "allow_cloud": False}
        tr_rt.backend.fail = EngineError("server", "the server failed (503)",
                                         hint="vid2sub retries twice")
        t.set(retranslate={**ask, "n": 1})
        t.until(lambda t: len(retranslated(t)) == 1)
        tr_rt.backend.fail = EngineError("server", "the server took too long to answer",
                                         hint="it may be busy; vid2sub retries twice")
        t.set(retranslate={**ask, "n": 2})
        t.until(lambda t: len(retranslated(t)) == 2)
        tr_rt.backend.fail = EngineError("bad_response", "the server answered 404: no such model")
        t.set(retranslate={**ask, "n": 3})  # no hint to begin with: none is made up (N-3)
        t.until(lambda t: len(retranslated(t)) == 3)
        assert [n["text"] for n in t.notices()] == [
            "couldn't retranslate: the server failed (503) → retranslate again",
            "couldn't retranslate: the server took too long to answer → it may be busy",
            "couldn't retranslate: the server answered 404: no such model"]


@pytest.mark.media
def test_a_batch_heard_after_its_retranslation_ended_never_shows_as_progress(
        tr_client, tr_rt, tmp_path):
    # Task 17's Spec review (M-1): the token check in `_progress` and its reset, once the
    # retranslation ends, are what keep a late batch (run_coroutine_threadsafe can land after
    # the result) from showing "9 of 9" on an idle tab.
    video = make_episode(tmp_path / "ep")
    with tab(tr_client, RETRANSLATE_OUTPUTS) as t:
        ep = opened_in(t, video)
        t.set(retranslate={"episode": ep["id"], "n": 1, "track": "en",
                           "ids": [ep["rows"][0]["id"]], "allow_cloud": False})
        t.until(lambda t: retranslated(t))
        assert t.value("busy") is None and t.value("progress") is None
        tr_rt.backend.on_batch(9, 9)  # late: from the thread the batch ran on
        time.sleep(0.5)
        assert {"done": 9, "of": 9} not in progress_seen(t) and t.value("progress") is None
