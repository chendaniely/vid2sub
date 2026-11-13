"""The settings drawer (spec §19.2, §5.3, §5.4, §6.4, §6.8; S35): endpoints and models as
vid2sub.toml has them, keys by presence only; a typed key only for an endpoint that allows one,
kept in the engine's memory and shown back only as "key entered for this session", never in an
output, a notice, a log or Shiny's input map; Test lists an endpoint's models, asking only its
own origin; the session's defaults change in one tab and reach every tab; cue rules are shown as
built; Copy settings loads back as it is, holding no key; and Pages is offered none of it."""

import dataclasses
import json
import logging

import pytest
from episodes import make_episode
from fakes import FakeServer, closed_port_url
from shiny import reactive
from starlette.testclient import TestClient
from test_web_server import (  # noqa: F401 - fresh_reactive_lock is autouse
    BASE,
    JSON,
    PAGE,
    PORT,
    TOKEN,
    Tab,
    fresh_reactive_lock,
    tab,
)

from vid2sub.cache import Cache
from vid2sub.config import Config, load_config
from vid2sub.engines.clients import KeyRing
from vid2sub.media.tools import Tools
from vid2sub.web import runtime, server, settings
from vid2sub.web.app import create_app
from vid2sub.web.episode import Capabilities
from vid2sub.web.settings import Defaults, Session

KEY = "k" * 40  # a typed key's value: low entropy, plainly not a real one
ENV_KEY = "e" * 32  # an environment key's value
OUTPUTS = {"settings", "status"}


def config(spark: str = "http://127.0.0.1:9/v1", lan: str = "http://127.0.0.1:10/v1",
           **defaults) -> Config:
    return Config.model_validate({
        "endpoints": {
            "spark": {"base_url": spark, "key_env": "SPARK_TEST_KEY"},
            "lan": {"base_url": lan, "allow_typed_key": True},
            "openai": {"base_url": "https://api.openai.com/v1", "key_env": "OPENAI_TEST_KEY"},
        },
        "models": {
            "spark-turbo": {"catalog": "whisper-large-v3-turbo", "endpoint": "spark",
                            "model": "w", "parser": "whisper.cpp", "local": True},
            "lan-gemma": {"endpoint": "lan", "model": "g", "task": "translate"},
        },
        "defaults": defaults,
    })


# ---- the pure parts ----------------------------------------------------------------------------


def test_the_view_shows_the_toml_as_it_is_and_every_key_by_presence_only():
    keys = KeyRing(typed={"lan": KEY}, environ={"SPARK_TEST_KEY": ENV_KEY})
    view = settings.settings_view(config(), keys, Defaults(("en",), ("srt",)))
    assert view["endpoints"] == [
        {"name": "spark", "base_url": "http://127.0.0.1:9/v1", "local": True,
         "key_env": "SPARK_TEST_KEY", "key": "present", "allow_typed_key": False,
         "typed": False},
        {"name": "lan", "base_url": "http://127.0.0.1:10/v1", "local": False, "key_env": None,
         "key": "present", "allow_typed_key": True, "typed": True},
        {"name": "openai", "base_url": "https://api.openai.com/v1", "local": False,
         "key_env": "OPENAI_TEST_KEY", "key": "missing", "allow_typed_key": False,
         "typed": False}]
    assert view["models"] == [
        {"name": "spark-turbo", "task": "transcribe", "catalog": "whisper-large-v3-turbo",
         "endpoint": "spark", "engine": None, "model": "w", "local": True},
        {"name": "lan-gemma", "task": "translate", "catalog": None, "endpoint": "lan",
         "engine": None, "model": "g", "local": False}]
    assert view["defaults"] == {"targets": ["en"], "formats": ["srt"]}
    assert [t["key"] for t in view["targets"]] == ["en", "ja", "ko", "zh-Hans", "zh-Hant",
                                                   "yue-Hant"]
    assert KEY not in json.dumps(view) and ENV_KEY not in json.dumps(view)


def test_the_cue_rules_are_shown_as_built_and_nothing_can_change_them():
    # Phase 2 Decision 21: nothing in vid2sub.toml holds cue rules yet.
    rules = settings.settings_view(config(), KeyRing(environ={}), Defaults())["rules"]
    assert rules[0] == {"lang": "en", "label": "English", "max_width": 42, "max_lines": 2,
                        "cps": 20.0, "min_ms": 833, "max_ms": 7000}
    assert [r["lang"] for r in rules] == ["en", "ja", "zh", "yue", "ko"]
    with pytest.raises(settings.BadSetting):
        settings.change_defaults(Defaults(), {"n": 1, "rules": {"en": {"max_width": 99}}})


def test_copy_settings_loads_back_with_m1s_config_giving_the_same_defaults_and_no_key(tmp_path):
    # §5.4: the session's settings as TOML to paste into the file, never including a key.
    cfg = config(youtube_dir='C:\\Users\\"Dan"\\動画\tclips', cache_max_gb=7.5)
    keys = KeyRing(typed={"lan": KEY}, environ={"SPARK_TEST_KEY": ENV_KEY})
    session = Defaults(("ja", "zh-Hant"), ("srt", "ass"))
    text = settings.settings_view(cfg, keys, session)["toml"]
    assert KEY not in text and ENV_KEY not in text and "[endpoints" not in text
    path = tmp_path / "vid2sub.toml"
    path.write_text(text, encoding="utf-8")
    back = load_config(path).defaults
    assert (back.targets, back.formats) == (["ja", "zh-Hant"], ["srt", "ass"])
    assert back.youtube_dir == cfg.defaults.youtube_dir and back.cache_max_gb == 7.5
    assert settings.Defaults.from_config(back) == session


def test_a_typed_key_is_kept_only_for_an_endpoint_that_allows_one_and_never_echoed():
    keys = KeyRing(environ={})
    assert settings.enter_key(config(), keys, {"endpoint": "lan", "key": KEY, "n": 1}) == \
        "key entered for this session"
    assert keys.typed == {"lan": KEY}
    for request in ({"endpoint": "spark", "key": KEY}, {"endpoint": "<b>", "key": KEY},
                    {"endpoint": ["lan"], "key": KEY}, "lan"):
        with pytest.raises(settings.BadSetting) as err:
            settings.enter_key(config(), keys, request)
        assert str(err.value) == settings.NO_TYPED_KEY
    for bad in (KEY + " ", KEY + "\n", "ключ" * 10, "k" * 1025, 42, None):
        with pytest.raises(settings.BadSetting) as err:
            settings.enter_key(config(), keys, {"endpoint": "lan", "key": bad})
        assert str(err.value) == settings.BAD_KEY
    assert keys.typed == {"lan": KEY}  # nothing refused replaced it
    assert settings.enter_key(config(), keys, {"endpoint": "lan", "key": ""}) == \
        "the typed key is forgotten"
    assert keys.typed == {}


def test_defaults_change_one_at_a_time_and_only_to_what_vid2sub_knows():
    now = Defaults(("en",), ("srt",))
    assert settings.change_defaults(now, {"n": 1, "targets": ["ja", "en"]}) == \
        Defaults(("ja", "en"), ("srt",))
    assert settings.change_defaults(now, {"n": 2, "formats": ["srt", "ass"]}) == \
        Defaults(("en",), ("srt", "ass"))
    for bad in ({"targets": []}, {"targets": ["xx"]}, {"targets": ["en", "en"]},
                {"targets": "en"}, {"formats": ["ass"]}, {"formats": ["srt", "vtt"]},
                {"targets": ["en"], "formats": ["srt"]}, {}, [], {"targets": [{"a": 1}]}):
        with pytest.raises(settings.BadSetting):
            settings.change_defaults(now, bad)


def test_the_session_tells_each_listener_of_a_change_until_it_stops_listening():
    heard: list[str] = []
    session = Session()
    stop = session.on_change(lambda: heard.append("a"))
    session.on_change(lambda: heard.append("b"))
    session.set_defaults(Defaults(("ja",), ("srt",)))
    stop()
    session.changed()
    assert heard == ["a", "b", "b"] and session.defaults().targets == ("ja",)


def test_a_test_lists_what_a_hostile_server_sends_only_as_much_as_fits():
    names, more = settings.models_shown([f"m{i}" for i in range(150)] + ["x" * 5000])
    assert len(names) == 100 and more == 51
    assert settings.models_shown(["<img src=x>", "y" * 300]) == (["<img src=x>", "y" * 200], 0)


# ---- the runtime: Test --------------------------------------------------------------------------


def models_responder(req):
    if req.path.endswith("/models"):
        return 200, {"object": "list", "data": [{"id": "w", "object": "model", "created": 0,
                                                 "owned_by": "spark"},
                                                {"id": "g", "object": "model", "created": 0,
                                                 "owned_by": "spark"}]}, {}
    return 404, {}, {}


def test_test_asks_only_the_endpoints_own_origin_with_its_own_key(tmp_path):
    with FakeServer(responder=models_responder) as spark, \
            FakeServer(responder=models_responder) as lan:
        cfg = config(spark=spark.url, lan=lan.url)
        rt = runtime.build(cfg, tools=Tools(None, None, None),
                           keys=KeyRing(typed={"lan": KEY}, environ={"SPARK_TEST_KEY": ENV_KEY}),
                           cache=Cache(tmp_path / "cache", max_bytes=0))
        try:
            assert rt.endpoint_models("lan") == ["w", "g"]
            assert rt.endpoint_models("spark") == ["w", "g"]
        finally:
            rt.queue.close()
    assert [r.headers.get("authorization") for r in lan.requests] == [f"Bearer {KEY}"]
    assert [r.headers.get("authorization") for r in spark.requests] == [f"Bearer {ENV_KEY}"]


def test_a_test_that_fails_names_the_fix_and_never_holds_a_key(tmp_path):
    def echo(req):  # a server that puts what it was sent in its error
        return 400, {"error": {"message": f"bad request with {req.headers['authorization']}"}}, {}

    with FakeServer(responder=echo) as lan:
        rt = runtime.build(config(lan=lan.url), tools=Tools(None, None, None),
                           keys=KeyRing(typed={"lan": KEY}, environ={}),
                           cache=Cache(tmp_path / "cache", max_bytes=0))
        try:
            with pytest.raises(settings.EndpointError) as err:
                rt.endpoint_models("lan")
            rt2 = dataclasses.replace(rt, config=config(lan=closed_port_url()))
            with pytest.raises(settings.EndpointError) as down:
                rt2.endpoint_models("lan")
        finally:
            rt.queue.close()
    assert KEY not in str(err.value) and "400" in str(err.value)
    assert str(down.value) == "couldn't reach the server" and "make tunnel" in down.value.hint


# ---- the server -------------------------------------------------------------------------------


@pytest.fixture
def rt(tmp_path):
    made = runtime.build(config(), tools=Tools(None, None, None),
                         keys=KeyRing(environ={"SPARK_TEST_KEY": ENV_KEY}),
                         cache=Cache(tmp_path / "cache", max_bytes=0))
    runtime.configure(made)
    yield made
    runtime.configure(None)
    made.queue.close()


def client_for(rt):
    c = TestClient(create_app(rt, token=TOKEN, port=PORT, shiny_app=server.app), base_url=BASE)
    c.__enter__()
    assert c.post("/auth", content=json.dumps({"token": TOKEN}),
                  headers={**JSON, **PAGE}).status_code == 204
    return c


@pytest.fixture
def client(rt, monkeypatch):
    from vid2sub.engines import clients

    monkeypatch.setattr(clients, "list_models", lambda *a, **kw: ["w"])  # the status check
    c = client_for(rt)
    yield c
    c.__exit__(None, None, None)


def view(t: Tab) -> dict:
    return t.until(lambda t: t.has("settings") and t.value("settings"))


def lan_of(view: dict) -> dict:
    return next(e for e in view["endpoints"] if e["name"] == "lan")


def test_a_typed_key_reaches_the_engine_and_is_shown_only_as_entered(client, rt, caplog):
    caplog.set_level(logging.DEBUG)
    with tab(client, OUTPUTS) as t:
        assert not lan_of(view(t))["typed"]
        t.set(typed_key={"endpoint": "lan", "key": KEY, "n": 1})
        t.set(typed_key=None)  # the page sends null straight after (spec §5.3)
        t.until(lambda t: lan_of(t.value("settings"))["typed"])
        assert [n["text"] for n in t.notices()] == ["key entered for this session"]
        t.until(lambda t: next(e for e in t.value("status")["endpoints"]
                               if e["name"] == "lan")["key"] == "present")
        assert rt.keys.typed == {"lan": KEY}
        # Shiny keeps every input's last value in the session; the page's null replaced the key.
        (shiny_session,) = server.app._sessions.values()
        with reactive.isolate():
            assert shiny_session.input["typed_key"]() is None
        t.set(typed_key={"endpoint": "lan", "key": "", "n": 2})
        t.until(lambda t: not lan_of(t.value("settings"))["typed"])
    assert rt.keys.typed == {}
    assert KEY not in json.dumps(t.messages) and KEY not in caplog.text


def test_a_typed_key_for_an_endpoint_that_doesnt_allow_one_is_kept_nowhere(client, rt):
    with tab(client, OUTPUTS) as t:
        view(t)
        t.set(typed_key={"endpoint": "spark", "key": KEY, "n": 1})
        t.set(typed_key={"endpoint": "lan", "key": KEY + " x", "n": 2})
        t.until(lambda t: len(t.notices()) == 2)
        assert [n["text"] for n in t.notices()] == [settings.NO_TYPED_KEY, settings.BAD_KEY]
    assert rt.keys.typed == {} and KEY not in json.dumps(t.messages)


def results(t: Tab) -> list[dict]:
    return [m["custom"]["shinyReactMessage"]["data"] for m in t.messages
            if m.get("custom", {}).get("shinyReactMessage", {}).get("id")
            == "endpoint_test_result"]


def test_test_answers_with_the_models_or_the_fix_and_refuses_an_unknown_endpoint(tmp_path):
    with FakeServer(responder=models_responder) as lan:
        made = runtime.build(config(lan=lan.url, spark=closed_port_url()),
                             tools=Tools(None, None, None), keys=KeyRing(environ={}),
                             cache=Cache(tmp_path / "cache", max_bytes=0))
        runtime.configure(made)
        c = client_for(made)
        try:
            with tab(c, OUTPUTS) as t:
                view(t)
                t.set(endpoint_test={"endpoint": "lan", "n": 1})
                t.set(endpoint_test={"endpoint": "spark", "n": 2})
                t.set(endpoint_test={"endpoint": "<script>", "n": 3})
                t.until(lambda t: len(results(t)) == 2 and t.notices())
        finally:
            c.__exit__(None, None, None)
            runtime.configure(None)
            made.queue.close()
    by = {r["endpoint"]: r for r in results(t)}
    assert by["lan"] == {"endpoint": "lan", "n": 1, "ok": True, "models": ["w", "g"],
                         "more": 0, "error": None}
    assert by["spark"]["ok"] is False and by["spark"]["error"].startswith(
        "couldn't reach the server → is it running?")
    assert [n["text"] for n in t.notices()] == [settings.NO_ENDPOINT]
    assert "<script>" not in json.dumps(t.notices())


def test_a_default_changed_in_one_tab_reaches_every_tab_and_copy_settings(client, rt):
    with tab(client, OUTPUTS) as a, tab(client, OUTPUTS) as b:
        view(a), view(b)
        a.set(session_defaults={"n": 1, "targets": ["en", "ja"]})
        a.set(session_defaults={"n": 2, "formats": ["srt", "ass"]})
        a.set(session_defaults={"n": 3, "formats": ["ass"]})
        seen = b.until(lambda t: t.value("settings")["defaults"]["formats"] == ["srt", "ass"]
                       and t.value("settings"))
        assert seen["defaults"] == {"targets": ["en", "ja"], "formats": ["srt", "ass"]}
        assert 'targets = ["en", "ja"]' in seen["toml"]
        assert 'formats = ["srt", "ass"]' in seen["toml"]
        a.until(lambda t: t.notices())
        assert [n["text"] for n in a.notices()] == [settings.BAD_FORMATS] and b.notices() == []
    assert rt.session.defaults() == Defaults(("en", "ja"), ("srt", "ass"))


class Browser:
    """A backend as the Pages editor's capabilities describe it."""

    def __init__(self, backend):
        self._backend = backend

    def capabilities(self):
        return Capabilities(engine="browser", generate=False, save="download", path_input=False)

    def __getattr__(self, name):
        return getattr(self._backend, name)


def test_the_pages_editor_is_offered_no_settings_and_takes_no_key(rt, monkeypatch):
    pages = dataclasses.replace(rt, backend=Browser(rt.backend))
    runtime.configure(pages)
    c = client_for(pages)
    try:
        with tab(c, OUTPUTS) as t:
            t.until(lambda t: t.has("settings"))
            assert t.value("settings") is None
            t.set(typed_key={"endpoint": "lan", "key": KEY, "n": 1})
            t.set(session_defaults={"n": 2, "targets": ["ja"]})
            t.set(endpoint_test={"endpoint": "lan", "n": 3})
            t.until(lambda t: t.notices())
            assert [n["text"] for n in t.notices()] == [settings.NO_ENDPOINT]
    finally:
        c.__exit__(None, None, None)
    assert rt.keys.typed == {} and rt.session.defaults() == Defaults(("en",), ("srt",))


@pytest.mark.media
def test_an_episode_opened_once_ass_is_a_default_starts_save_with_ass_too(tmp_path):
    # Task 16's Save: "ASS too" starts from the episode view's formats.
    video = make_episode(tmp_path / "ep")
    made = runtime.build(Config(), tools=Tools.find(), keys=KeyRing(environ={}),
                         cache=Cache(tmp_path / "cache", max_bytes=10**9))
    made.session.set_defaults(Defaults(("en",), ("srt", "ass")))
    runtime.configure(made)
    c = client_for(made)
    try:
        with tab(c, {"episode"}) as t:
            t.until(lambda t: t.has("episode"))
            t.set(open={"path": str(video), "n": 1})
            ep = t.until(lambda t: t.value("episode"))
    finally:
        c.__exit__(None, None, None)
        runtime.configure(None)
        made.queue.close()
    assert ep["formats"] == ["srt", "ass"]
