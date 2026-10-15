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
