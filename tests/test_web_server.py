"""The Shiny server for the React frontend: its page runs no inline script or style, so the spec's
CSP allows all of it; `capabilities` and `status` are JSON outputs, with keys by presence only;
`notice` is a shinyreact message (spec §19.1, §19.2, §6.3; S26); and the editor's `open` and
`playback` inputs and `episode` and `busy` outputs, with their media tokens and the queue that
runs them, are here too (spec §19.1, §20, §8.2, §8.8)."""

import asyncio
import contextlib
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
from vid2sub.config import Config
from vid2sub.engines import clients
from vid2sub.engines.base import EngineError
from vid2sub.engines.clients import KeyRing
from vid2sub.media.tools import Tools
from vid2sub.web import runtime, server, views
from vid2sub.web.app import create_app
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
            "op": "replace_all", "find": "元気", "replace": "げんき", "tracks": ["source", "en"]}})
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
