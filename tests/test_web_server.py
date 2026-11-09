"""The Shiny server for the React frontend: its page runs no inline script or style, so the spec's
CSP allows all of it; `capabilities` and `status` are JSON outputs, with keys by presence only;
and `notice` is a shinyreact message (spec §19.1, §19.2, §6.3; S26)."""

import asyncio
import contextlib
import json
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
        ep = t.until(opened)
        assert ep["video"]["url"] is None and ep["video"]["playable_audio"] is False
        audio = media_rt.media.resolve(ep["video"]["audio_url"].removeprefix("/media/"))
        assert audio is not None and audio.name == "playback-a0.m4a"
        assert audio.parent.parent == tmp_path / "cache"


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
        t.set(playback={"episode": ep["id"], "n": 2})
        audio = t.until(lambda t: opened(t)["video"]["audio_url"] and opened(t))["video"]
        assert audio["url"] is None
        played = media_rt.media.resolve(audio["audio_url"].removeprefix("/media/"))
        assert played is not None and played.name == "playback-a0.m4a"
        assert media_rt.media.resolve(token) is None
        busy = [m["values"]["busy"] for m in t.messages if "busy" in m.get("values", {})]
        assert "playback" in busy and t.value("busy") is None
        # Asked again, or for an episode the tab has moved on from, nothing happens.
        sent = len(t.messages)
        t.set(playback={"episode": ep["id"], "n": 3})
        t.set(playback={"episode": "e" + "0" * 16, "n": 4})
        time.sleep(0.5)
        assert not any("episode" in m.get("values", {}) for m in t.messages[sent:])
        assert t.notices() == []


@pytest.mark.media
def test_a_video_whose_chosen_audio_track_isnt_its_first_plays_that_tracks_sound_alone(
        media_client, media_rt, tmp_path):
    # Q&A item 48: the browser would play the first track under captions made from the second.
    second = make_episode(tmp_path / "second", audio_langs=("eng", "jpn"), audio_track=1)
    first = make_episode(tmp_path / "first", audio_langs=("jpn", "eng"), audio_track=0)
    with tab(media_client) as t:
        t.until(lambda t: t.has("episode"))
        t.set(open={"path": str(second), "n": 1})
        ep = t.until(opened)
        assert ep["video"]["url"] is None and ep["video"]["playable_audio"] is False
        audio = media_rt.media.resolve(ep["video"]["audio_url"].removeprefix("/media/"))
        assert audio is not None and audio.name == "playback-a1.m4a"
        t.set(open={"path": str(first), "n": 2})
        ep = t.until(lambda t: opened(t) and opened(t)["id"] != ep["id"] and opened(t))
        assert ep["video"]["url"] and ep["video"]["audio_url"] is None
