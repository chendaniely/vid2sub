import os
import platform
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from vid2sub.config import Config, Endpoint, ModelEntry
from vid2sub.engines.base import Chunk, EngineError
from vid2sub.engines.clients import KeyRing, RunPolicy
from vid2sub.engines.endpoint import EndpointEngine
from vid2sub.engines.qwen_mlx import QwenMLXEngine
from vid2sub.engines.registry import make_engine

ENTRY = ModelEntry(catalog="qwen3-asr-1.7b", engine="mlx-qwen3-asr")


def chunk(seconds=1.0):
    return Chunk(index=0, samples=np.zeros(int(16_000 * seconds), dtype=np.int16),
                 encode=lambda s: b"")


def test_qwen_gets_its_language_name_context_and_16khz_audio():
    seen = {}

    def fake(audio, **kw):
        seen.update(kw, audio=audio)
        return SimpleNamespace(text="你好。", language="Cantonese",
                               segments=[{"text": "你", "start": 0.0, "end": 0.2},
                                         {"text": "好", "start": 0.2, "end": 0.4}])

    e = QwenMLXEngine("mac-qwen", ENTRY, transcribe_fn=fake)
    result = e.transcribe(chunk(), language="yue", prompt="工藤新一.")
    assert seen["language"] == "Cantonese" and seen["context"] == "工藤新一."
    assert seen["model"] == "Qwen/Qwen3-ASR-1.7B" and seen["return_timestamps"] is True
    assert seen["audio"][1] == 16_000
    assert result.parsed.language == "yue"
    assert [w.text for w in result.parsed.segments[0].words] == ["你", "好。"]
    assert e.max_chunk_s == 180


def test_qwen_detects_a_language_by_name():
    fake = lambda audio, **kw: SimpleNamespace(text="hi", language="Japanese", segments=[])
    assert QwenMLXEngine("q", ENTRY, transcribe_fn=fake).detect_language(chunk()) == {"ja": 1.0}


def test_without_the_mac_extra_qwen_says_how_to_install_it(monkeypatch):
    monkeypatch.setitem(sys.modules, "mlx_qwen3_asr", None)
    with pytest.raises(EngineError) as err:
        QwenMLXEngine("q", ENTRY).transcribe(chunk(), language="en", prompt="")
    assert err.value.kind == "unavailable" and "vid2sub[mac]" in err.value.hint


def test_engines_are_built_from_the_config_entry():
    cfg = Config(endpoints={"spark": Endpoint(base_url="http://127.0.0.1:9/v1")},
                 models={"q": ENTRY,
                         "t": ModelEntry(endpoint="spark", model="m", parser="whisper.cpp",
                                         local=True)})
    assert isinstance(make_engine("q", cfg, RunPolicy(), KeyRing()), QwenMLXEngine)
    assert isinstance(make_engine("t", cfg, RunPolicy(), KeyRing()), EndpointEngine)


@pytest.mark.live
@pytest.mark.skipif(not (sys.platform == "darwin" and platform.machine() == "arm64"
                         and os.environ.get("VID2SUB_LIVE_MLX") == "1"),
                    reason="needs an Apple Silicon Mac and VID2SUB_LIVE_MLX=1")
def test_qwen_transcribes_real_speech_with_word_times():
    from helpers import SPEECH

    from vid2sub.media.decode import read_wav
    samples = read_wav(SPEECH)
    result = QwenMLXEngine("q", ENTRY).transcribe(
        Chunk(index=0, samples=samples, encode=lambda s: b""), language="en", prompt="")
    words = [w for s in result.parsed.segments for w in s.words]
    assert len(words) > 10 and words[-1].end_ms > 5000
