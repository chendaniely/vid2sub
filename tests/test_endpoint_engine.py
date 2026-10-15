from email import policy
from email.parser import BytesParser

import numpy as np
import pytest
from fakes import FakeServer, closed_port_url

from vid2sub.config import Config, Endpoint, ModelEntry
from vid2sub.engines.base import Chunk, EngineError
from vid2sub.engines.clients import KeyRing, RunPolicy
from vid2sub.engines.endpoint import EndpointEngine

SECRET = "spark-secret-123"
WHISPER = {"language": "japanese", "segments": [{"text": "こんにちは", "start": 0.0, "end": 1.0,
           "words": [{"word": "こん", "start": 0.0, "end": 0.5, "t_dtw": -1, "probability": 0.9},
                     {"word": "にちは", "start": 0.5, "end": 1.0, "t_dtw": -1,
                      "probability": 0.8}]}],
           "language_probabilities": {"ja": 0.97, "zh": 0.02}}


def engine(url, model="whisper-large-v3-turbo"):
    cfg = Config(endpoints={"spark": Endpoint(base_url=url, key_env="SPARK_API_KEY")},
                 models={"turbo": ModelEntry(catalog="whisper-large-v3-turbo", endpoint="spark",
                                             model=model, parser="whisper.cpp", local=True)})
    return EndpointEngine("turbo", cfg.models["turbo"], cfg, RunPolicy(),
                          KeyRing(environ={"SPARK_API_KEY": SECRET}))


def chunk():
    return Chunk(index=3, samples=np.zeros(16_000, dtype=np.int16),
                 encode=lambda s: b"fLaC-fake")


def test_a_chunk_is_uploaded_with_a_neutral_name_the_key_and_the_settings():
    with FakeServer([(200, WHISPER, {})]) as srv:
        result = engine(srv.url).transcribe(chunk(), language="ja", prompt="工藤新一.")
    req = srv.requests[0]
    assert req.path == "/v1/audio/transcriptions"
    assert req.headers["authorization"] == f"Bearer {SECRET}"
    form = req.form()
    assert form["file"] == ("chunk-0003.flac", b"fLaC-fake")
    assert form["model"][1] == b"whisper-large-v3-turbo"
    assert form["language"][1] == b"ja"
    assert form["prompt"][1] == "工藤新一.".encode()
    assert form["response_format"][1] == b"verbose_json"
    assert [w.text for w in result.parsed.segments[0].words] == ["こん", "にちは"]


def test_language_detection_returns_the_servers_probabilities():
    with FakeServer([(200, WHISPER, {})]) as srv:
        assert engine(srv.url).detect_language(chunk())["ja"] == 0.97
        assert "language" not in srv.requests[0].form()


def test_a_401_names_the_variable_to_export_and_never_shows_the_key():
    with FakeServer([(401, {"error": {"message": f"bad key {SECRET}"}}, {})]) as srv, \
            pytest.raises(EngineError) as err:
        engine(srv.url).transcribe(chunk(), language="ja", prompt="")
    assert err.value.kind == "auth" and "SPARK_API_KEY" in err.value.hint
    assert SECRET not in str(err.value) and SECRET not in err.value.hint


def test_a_redirect_is_never_followed():
    with FakeServer([(200, WHISPER, {})]) as target, \
            FakeServer([(307, b"", {"location": target.url + "/audio/transcriptions"})]) as srv, \
            pytest.raises(EngineError) as err:
        engine(srv.url).transcribe(chunk(), language="ja", prompt="")
    assert target.requests == []
    assert err.value.kind == "bad_response"


@pytest.mark.parametrize("status, payload, headers, kind, retry", [
    (413, {"error": {"message": "too big"}}, {}, "too_large", None),
    (429, {"error": {"message": "busy"}}, {"retry-after": "7"}, "refused", 7.0),
    (503, {"error": {"code": "no_fit", "message": "doesn't fit", "retry_after_s": 30}}, {},
     "refused", 30.0),
    (500, {"error": {"message": "boom"}}, {}, "server", None),
])
def test_server_answers_become_error_kinds(status, payload, headers, kind, retry):
    with FakeServer([(status, payload, headers)]) as srv, \
            pytest.raises(EngineError) as err:
        engine(srv.url).transcribe(chunk(), language="ja", prompt="")
    assert err.value.kind == kind and err.value.retry_after == retry


def test_an_unreachable_server_suggests_the_tunnel():
    with pytest.raises(EngineError) as err:
        engine(closed_port_url()).transcribe(chunk(), language="ja", prompt="")
    assert err.value.kind == "connection" and "make tunnel" in err.value.hint


def test_a_substitute_model_is_refused():
    with FakeServer([(200, WHISPER, {"x-spark-model": "some-other-model"})]) as srv, \
            pytest.raises(EngineError, match="some-other-model"):
        engine(srv.url).transcribe(chunk(), language="ja", prompt="")


def test_the_engine_takes_its_chunk_limit_from_the_catalog():
    e = engine("http://127.0.0.1:9/v1")
    assert e.max_chunk_s == 300 and e.name == "whisper.cpp"
    assert e.stamp().label == "whisper-large-v3-turbo@unknown"


OPENAI = {"language": "english",
          "segments": [{"start": 0, "end": 2, "text": " Hello, world."}],
          "words": [{"word": "Hello", "start": 0.1, "end": 0.5},
                    {"word": "world", "start": 0.6, "end": 1.0}]}


def openai_engine(url):
    cfg = Config(endpoints={"spark": Endpoint(base_url=url, key_env="SPARK_API_KEY")},
                 models={"oa": ModelEntry(endpoint="spark", model="whisper-1", parser="openai",
                                          local=True)})
    return EndpointEngine("oa", cfg.models["oa"], cfg, RunPolicy(),
                          KeyRing(environ={"SPARK_API_KEY": SECRET}))


def field_values(req, name):
    message = BytesParser(policy=policy.HTTP).parsebytes(
        b"Content-Type: " + req.headers["content-type"].encode() + b"\r\n\r\n" + req.body)
    return [part.get_payload(decode=True) for part in message.iter_parts()
            if part.get_param("name", header="content-disposition") == name]


def test_an_openai_entry_asks_for_word_and_segment_times_and_parses_openai_json():
    with FakeServer([(200, OPENAI, {})]) as srv:
        engine = openai_engine(srv.url)
        result = engine.transcribe(chunk(), language=None, prompt="")
    req = srv.requests[0]
    assert engine.name == "openai"
    assert req.form()["response_format"][1] == b"verbose_json"
    assert sorted(field_values(req, "timestamp_granularities[]")) == [b"segment", b"word"]
    assert [w.text for w in result.parsed.segments[0].words] == [" Hello,", " world."]


def test_a_malformed_answer_is_a_bad_response_not_a_raw_exception():
    bad = {"language": "english",
           "segments": [{"text": "a", "start": 0, "end": 1, "avg_logprob": "abc"}]}
    with FakeServer([(200, bad, {})]) as srv, \
            pytest.raises(EngineError) as err:
        engine(srv.url).transcribe(chunk(), language="ja", prompt="")
    assert err.value.kind == "bad_response"


def test_whisper_cpp_detection_without_probabilities_knows_nothing():
    no_probs = {k: v for k, v in WHISPER.items() if k != "language_probabilities"}
    with FakeServer([(200, no_probs, {})]) as srv:
        assert engine(srv.url).detect_language(chunk()) == {}


def test_openai_detection_reports_the_language_it_decoded_in():
    with FakeServer([(200, {"language": "japanese", "segments": []}, {})]) as srv:
        assert openai_engine(srv.url).detect_language(chunk()) == {"ja": 1.0}
