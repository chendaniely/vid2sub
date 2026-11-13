import pytest

from vid2sub.config import Config, Endpoint, ModelEntry
from vid2sub.engines import clients
from vid2sub.engines.base import Chunk, EngineError, ModelStamp


def config(spark_url="http://127.0.0.1:9100/v1"):
    return Config(
        endpoints={"spark": Endpoint(base_url=spark_url, key_env="SPARK_API_KEY"),
                   "openai": Endpoint(base_url="https://api.openai.com/v1",
                                      key_env="OPENAI_API_KEY", allow_typed_key=True)},
        models={"turbo": ModelEntry(endpoint="spark", model="whisper-large-v3-turbo",
                                    parser="whisper.cpp", local=True),
                "w1": ModelEntry(endpoint="openai", model="whisper-1", parser="openai")})


def test_a_cloud_model_is_refused_unless_the_run_allows_it():
    cfg = config()
    with pytest.raises(EngineError) as err:
        clients.check_allowed("w1", cfg.models["w1"], cfg, clients.RunPolicy(allow_cloud=False))
    assert err.value.kind == "cloud_not_allowed" and "--allow-cloud" in err.value.hint
    clients.check_allowed("w1", cfg.models["w1"], cfg, clients.RunPolicy(allow_cloud=True))
    clients.check_allowed("turbo", cfg.models["turbo"], cfg, clients.RunPolicy())


def test_a_missing_key_names_its_variable_and_never_a_value():
    cfg = config()
    keys = clients.KeyRing(environ={})
    with pytest.raises(EngineError) as err:
        clients.transcription_client("turbo", cfg.models["turbo"], cfg, clients.RunPolicy(), keys)
    assert err.value.kind == "key_missing" and "SPARK_API_KEY" in str(err.value)


def test_a_typed_key_is_used_only_where_the_endpoint_allows_it():
    cfg = config()
    keys = clients.KeyRing(typed={"openai": "typed-key", "spark": "typed-spark"},
                           environ={"SPARK_API_KEY": "env-spark"})
    assert keys.key_for("openai", cfg.endpoints["openai"]) == "typed-key"
    assert keys.key_for("spark", cfg.endpoints["spark"]) == "env-spark"
    assert set(keys.secrets(cfg)) >= {"typed-key", "env-spark"}


def test_clients_use_the_configured_address_and_key_never_the_sdks_environment(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "https://evil.example/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "env-openai")
    cfg = config()
    keys = clients.KeyRing(environ={"SPARK_API_KEY": "spark-secret"})
    client = clients.transcription_client("turbo", cfg.models["turbo"], cfg, clients.RunPolicy(),
                                          keys)
    assert str(client.base_url).startswith("http://127.0.0.1:9100/v1")
    assert client.api_key == "spark-secret"


def test_a_chunk_names_its_upload_and_encodes_once():
    import numpy as np
    calls = []

    def encode(samples):
        calls.append(1)
        return b"fLaC"

    chunk = Chunk(index=3, samples=np.zeros(16_000, dtype=np.int16), encode=encode)
    assert chunk.upload_name == "chunk-0003.flac" and chunk.duration_ms == 1000
    assert chunk.flac() == chunk.flac() == b"fLaC" and len(calls) == 1


def test_a_model_stamp_labels_the_model_and_revision():
    assert ModelStamp("qwen3-asr", "Qwen/Qwen3-ASR-1.7B", "0123456789abcdef").label == \
        "Qwen3-ASR-1.7B@0123456789ab"


# --- cleartext key transport (spec §5.2) ---

LAN = "http://192.0.2.50:9100/v1"


def lan_config(**endpoint):
    return Config(endpoints={"lan": Endpoint(base_url=LAN, **endpoint)},
                  models={"m": ModelEntry(endpoint="lan", model="x", parser="openai",
                                          local=True)})


def test_a_key_from_the_environment_is_never_attached_over_plain_http_to_the_lan():
    cfg = lan_config(key_env="LAN_API_KEY")
    keys = clients.KeyRing(environ={"LAN_API_KEY": "lan-secret"})
    with pytest.raises(EngineError) as err:
        clients.transcription_client("m", cfg.models["m"], cfg,
                                     clients.RunPolicy(allow_cloud=True), keys)
    assert err.value.kind == "auth" and "https" in err.value.hint
    assert "lan-secret" not in str(err.value)


def test_a_typed_key_is_never_attached_over_plain_http_to_the_lan():
    cfg = lan_config(allow_typed_key=True)
    keys = clients.KeyRing(typed={"lan": "typed-key"}, environ={})
    with pytest.raises(EngineError) as err:
        clients.transcription_client("m", cfg.models["m"], cfg,
                                     clients.RunPolicy(allow_cloud=True), keys)
    assert err.value.kind == "auth"


def test_listing_models_refuses_to_send_a_key_over_plain_http_to_the_lan():
    cfg = lan_config(key_env="LAN_API_KEY")
    keys = clients.KeyRing(environ={"LAN_API_KEY": "lan-secret"})
    with pytest.raises(EngineError) as err:
        clients.list_models("lan", cfg.endpoints["lan"], keys)
    assert err.value.kind == "auth"


def test_loopback_with_a_key_and_https_still_work():
    from fakes import FakeServer
    with FakeServer(responses=[(200, {"data": [{"id": "m1", "object": "model"}]}, {})]) as srv:
        cfg = Config(endpoints={"here": Endpoint(base_url=srv.url, key_env="HERE_KEY")},
                     models={"m": ModelEntry(endpoint="here", model="x", parser="openai",
                                             local=True)})
        keys = clients.KeyRing(environ={"HERE_KEY": "here-secret"})
        assert clients.list_models("here", cfg.endpoints["here"], keys) == ["m1"]
        assert srv.requests[0].headers["authorization"] == "Bearer here-secret"
    cfg = config()
    keys = clients.KeyRing(typed={"openai": "typed-key"}, environ={})
    client = clients.transcription_client("w1", cfg.models["w1"], cfg,
                                          clients.RunPolicy(allow_cloud=True), keys)
    assert client.api_key == "typed-key"


# --- retry hints and non-object answers ---

def _transcribe(responses):
    from fakes import FakeServer
    with FakeServer(responses=responses) as srv:
        cfg = Config(endpoints={"here": Endpoint(base_url=srv.url)},
                     models={"m": ModelEntry(endpoint="here", model="x", parser="openai",
                                             local=True)})
        client = clients.transcription_client("m", cfg.models["m"], cfg, clients.RunPolicy(),
                                              clients.KeyRing(environ={}))
        return clients.call_transcription(client, key_env=None, secrets=[],
                                          file=("chunk-0000.flac", b"fLaC", "audio/flac"),
                                          model="x")


def _refusal(retry):
    return (409, {"error": {"code": "loading"}, "retry_after_s": retry}, {})


def _refusal_with(code, *, status=409, body_retry=None, header=None):
    """local-ai's refusal (its spark/src/spark/messages.py): the code in `error`, a top-level
    retry_after_s, a Retry-After header and x-should-retry: false."""
    body: dict = {"error": {"code": code, "message": "no"}}
    if body_retry is not None:
        body["retry_after_s"] = body_retry
    headers = {"x-should-retry": "false"}
    if header is not None:
        headers["Retry-After"] = header
    return (status, body, headers)


@pytest.mark.parametrize("code, status", [
    ("restarting", 409), ("draining", 409), ("llama_swap_down", 409), ("gate_down", 503),
    ("no_fit", 409), ("loading", 409), ("held_by_brake", 409)])
def test_every_refusal_worth_waiting_out_is_refused_with_its_retry_after(code, status):
    with pytest.raises(EngineError) as err:
        _transcribe([_refusal_with(code, status=status, body_retry=60)])
    assert err.value.kind == "refused" and err.value.retry_after == 60.0


@pytest.mark.parametrize("code", ["footprint_suspect", "load_failed", "not_downloaded"])
def test_a_refusal_that_waiting_wont_fix_still_fails(code):
    with pytest.raises(EngineError) as err:
        _transcribe([_refusal_with(code, body_retry=30, header="30")])
    assert err.value.kind != "refused"


def test_the_top_level_retry_after_s_wins_over_the_header():
    with pytest.raises(EngineError) as err:
        _transcribe([_refusal_with("restarting", body_retry=45, header="9")])
    assert err.value.retry_after == 45.0


def test_the_retry_after_header_is_used_when_the_body_has_none():
    with pytest.raises(EngineError) as err:
        _transcribe([_refusal_with("draining", header="12")])
    assert err.value.kind == "refused" and err.value.retry_after == 12.0


def test_a_refusal_with_neither_leaves_the_wait_to_vid2subs_own_backoff():
    with pytest.raises(EngineError) as err:
        _transcribe([_refusal_with("llama_swap_down")])
    assert err.value.kind == "refused" and err.value.retry_after is None


def test_an_unreadable_retry_hint_in_a_refusal_is_ignored_not_a_crash():
    with pytest.raises(EngineError) as err:
        _transcribe([_refusal("soon")])
    assert err.value.kind == "refused" and err.value.retry_after is None


def test_a_zero_retry_hint_in_a_refusal_stays_zero():
    with pytest.raises(EngineError) as err:
        _transcribe([_refusal(0)])
    assert err.value.retry_after == 0.0


@pytest.mark.parametrize("header", ["nan", "inf", "-5", "soon"])
def test_an_unusable_retry_after_header_on_a_429_falls_back_to_thirty_seconds(header):
    with pytest.raises(EngineError) as err:
        _transcribe([(429, {}, {"Retry-After": header})])
    assert err.value.kind == "refused" and err.value.retry_after == 30.0


def test_a_json_answer_that_is_not_an_object_is_a_bad_response():
    with pytest.raises(EngineError) as err:
        _transcribe([(200, [1], {})])
    assert err.value.kind == "bad_response" and "JSON object" in str(err.value)


# ---- a key goes only to the origin it was declared with (spec §6.4) --------------------------


def _models_server(seen: list):
    """A loopback server (port 0) that records each request's path and whether it carried an
    Authorization header, and answers like a model list."""
    import http.server
    import threading

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            seen.append((self.path, bool(self.headers.get("Authorization"))))
            body = (b'{"object":"list","data":'
                    b'[{"id":"w","object":"model","created":0,"owned_by":"x"}]}')
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def test_a_plain_http_endpoint_is_reached_directly_and_never_through_a_proxy(monkeypatch):
    proxy_saw: list = []
    endpoint_saw: list = []
    proxy, endpoint = _models_server(proxy_saw), _models_server(endpoint_saw)
    try:
        for name in ("NO_PROXY", "no_proxy", "HTTPS_PROXY", "https_proxy", "ALL_PROXY",
                     "all_proxy", "http_proxy"):
            monkeypatch.delenv(name, raising=False)
        monkeypatch.setenv("HTTP_PROXY", f"http://127.0.0.1:{proxy.server_address[1]}")
        ep = Endpoint(base_url=f"http://127.0.0.1:{endpoint.server_address[1]}/v1",
                      key_env="SPARK_API_KEY")
        keys = clients.KeyRing(environ={"SPARK_API_KEY": "k" * 24})
        assert clients.list_models("spark", ep, keys) == ["w"]
        assert proxy_saw == []  # the key's request never reached the proxy
        assert endpoint_saw == [("/v1/models", True)]
    finally:
        proxy.shutdown()
        endpoint.shutdown()


def test_only_an_https_endpoint_trusts_the_environments_proxy():
    # Over https a proxy sees only CONNECT and the key stays inside TLS, so cloud calls through a
    # corporate proxy keep working; over plain http, the request itself would reach the proxy.
    assert clients._http("https://api.openai.com/v1", 5.0).trust_env is True
    assert clients._http("http://127.0.0.1:9100/v1", 5.0).trust_env is False


# ---- a junk answer is an unreachable endpoint (spec §19.2) -----------------------------------


@pytest.mark.parametrize("body, content_type", ids=[
    "html", "broken json as html", "broken json", "null", "list", "data string", "data int",
    "data ints", "deeply nested"], argvalues=[
    (b"<html>a web page</html>", "text/html"),
    (b"{not json", "text/html"),
    (b"{not json", "application/json"),  # JSONDecodeError (a ValueError) out of the client
    (b"null", "application/json"),
    (b"[1,2]", "application/json"),
    (b'{"data":"x"}', "application/json"),
    (b'{"data":5}', "application/json"),  # TypeError: an int isn't iterable
    (b'{"data":[1,2]}', "application/json"),
    (b"[" * 300_000, "application/json"),  # RecursionError out of the JSON parser
])
def test_a_200_that_is_not_a_model_list_is_an_engine_error_naming_no_url(body, content_type):
    import http.server
    import threading

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        ep = Endpoint(base_url=f"http://127.0.0.1:{srv.server_address[1]}/v1")
        with pytest.raises(EngineError) as err:
            clients.list_models("junk", ep, clients.KeyRing(environ={}))
    finally:
        srv.shutdown()
    assert err.value.kind == "bad_response" and "127.0.0.1" not in str(err.value)
