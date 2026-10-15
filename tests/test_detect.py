import numpy as np
from fakes import FakeEngine, FakeServer, closed_port_url

from vid2sub import detect as d
from vid2sub.catalog import Candidate
from vid2sub.config import Config, Endpoint, ModelEntry
from vid2sub.engines.clients import KeyRing

SAMPLES = np.zeros(16 * 200_000, dtype=np.int16)
SPEECH = [(0, 60_000), (120_000, 180_000)]


def run(engine):
    return d.detect(engine, SAMPLES, SPEECH, 200_000, encode=lambda s: b"")


def test_windows_are_taken_from_speech_at_three_points():
    assert d.sample_windows(SPEECH, 200_000) == [(12_000, 32_000), (60_000, 80_000),
                                                 (156_000, 176_000)]
    assert d.sample_windows([], 200_000) == []


def test_three_agreeing_samples_give_a_confident_language():
    result = run(FakeEngine(detect={"ja": 0.9, "zh": 0.05}))
    assert (result.language, result.confidence, result.uncertain) == ("ja", 0.9, False)


def test_whisper_hearing_chinese_asks_mandarin_or_cantonese():
    result = run(FakeEngine(detect={"zh": 0.9}))
    assert result.ambiguous_zh_yue and result.uncertain
    assert "Mandarin or Cantonese" in result.reason()
    assert not run(FakeEngine(name="qwen3-asr", detect={"zh": 0.9})).ambiguous_zh_yue


def test_disagreeing_samples_are_flagged_as_mixed():
    result = run(FakeEngine(detect=[{"ja": 0.9}, {"en": 0.9}, {"ja": 0.9}]))
    assert result.language == "ja" and result.mixed and result.uncertain


def config(url):
    return Config(
        endpoints={"spark": Endpoint(base_url=url, key_env="SPARK_API_KEY"),
                   "openai": Endpoint(base_url="https://api.openai.com/v1",
                                      key_env="OPENAI_API_KEY")},
        models={"turbo": ModelEntry(catalog="whisper-large-v3-turbo", endpoint="spark",
                                    model="whisper-large-v3-turbo", parser="whisper.cpp",
                                    local=True),
                "missing": ModelEntry(catalog="whisper-large-v3", endpoint="spark",
                                      model="whisper-large-v3", parser="whisper.cpp",
                                      local=True),
                "w1": ModelEntry(catalog="openai-whisper-1", endpoint="openai",
                                 model="whisper-1", parser="openai"),
                "mac": ModelEntry(catalog="qwen3-asr-1.7b", engine="mlx-qwen3-asr")})


def test_candidates_know_what_the_spark_serves_and_what_is_missing(monkeypatch):
    monkeypatch.setattr(d, "mlx_available", lambda: False)
    models = {"object": "list", "data": [{"id": "whisper-large-v3-turbo", "object": "model",
                                          "created": 0, "owned_by": "spark"}]}
    with FakeServer([(200, models, {})]) as srv:
        cands = {c.name: c for c in d.candidates(config(srv.url),
                                                 KeyRing(environ={"SPARK_API_KEY": "k"}))}
    assert cands["turbo"].available
    assert not cands["missing"].available and "doesn't list" in cands["missing"].reason
    assert not cands["w1"].available and "OPENAI_API_KEY" in cands["w1"].reason
    assert cands["w1"].cloud
    assert not cands["mac"].available and "vid2sub[mac]" in cands["mac"].reason


def test_an_unreachable_spark_marks_its_models_unavailable_with_the_tunnel_hint(monkeypatch):
    monkeypatch.setattr(d, "mlx_available", lambda: True)
    cands = {c.name: c for c in d.candidates(config(closed_port_url()),
                                             KeyRing(environ={"SPARK_API_KEY": "k"}))}
    assert not cands["turbo"].available and "make tunnel" in cands["turbo"].reason
    assert cands["mac"].available


def test_the_detector_prefers_qwen_then_local_whisper_then_the_cloud():
    qwen = Candidate("mac", "qwen3-asr-1.7b", "in-process", True)
    turbo = Candidate("turbo", "whisper-large-v3-turbo", "endpoint", True)
    cloud = Candidate("w1", "openai-whisper-1", "endpoint", True, cloud=True)
    assert d.choose_detector([turbo, qwen], allow_cloud=False) == "mac"
    assert d.choose_detector([turbo, cloud], allow_cloud=False) == "turbo"
    assert d.choose_detector([cloud], allow_cloud=False) is None
    assert d.choose_detector([cloud], allow_cloud=True) == "w1"
