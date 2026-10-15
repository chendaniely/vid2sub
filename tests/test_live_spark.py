"""The real Spark (opt-in): VID2SUB_LIVE_SPARK=1 with `make tunnel` running and SPARK_API_KEY
exported. Checks whisper.cpp's verbose_json and Gemma's structured output against vid2sub's
parsers and schemas (spec §29)."""

import os

import pytest
from helpers import SPEECH

from vid2sub.config import Config, Endpoint, ModelEntry
from vid2sub.engines.base import Chunk
from vid2sub.engines.clients import KeyRing, RunPolicy
from vid2sub.engines.endpoint import EndpointEngine
from vid2sub.media.decode import encode_flac, read_wav
from vid2sub.media.tools import Tools
from vid2sub.subs.glossary import EMPTY_GLOSSARY
from vid2sub.subs.model import Cue
from vid2sub.translate.run import make_ask, translate_cues

pytestmark = [pytest.mark.live, pytest.mark.skipif(os.environ.get("VID2SUB_LIVE_SPARK") != "1",
                                                   reason="needs VID2SUB_LIVE_SPARK=1")]
CONFIG = Config(
    endpoints={"spark": Endpoint(base_url="http://127.0.0.1:9100/v1", key_env="SPARK_API_KEY")},
    models={"turbo": ModelEntry(catalog="whisper-large-v3-turbo", endpoint="spark",
                                model="whisper-large-v3-turbo", parser="whisper.cpp", local=True),
            "gemma": ModelEntry(catalog="gemma-4-26b-a4b", endpoint="spark",
                                model="gemma-4-26b-a4b", task="translate", local=True,
                                request_extra={"chat_template_kwargs":
                                               {"enable_thinking": False}})})


def test_the_sparks_whisper_returns_timed_words(tmp_path):
    samples = read_wav(SPEECH)
    engine = EndpointEngine("turbo", CONFIG.models["turbo"], CONFIG, RunPolicy(), KeyRing())
    chunk = Chunk(0, samples, lambda s: encode_flac(s, Tools.find(), scratch=tmp_path))
    words = [w for s in engine.transcribe(chunk, language="en", prompt="").parsed.segments
             for w in s.words]
    assert len(words) > 10 and all(w.end_ms >= w.start_ms for w in words)


def test_gemma_translates_a_batch_in_the_required_shape():
    cues = [Cue(id=f"s{i}", start_ms=i * 2000, end_ms=i * 2000 + 1500, text=t)
            for i, t in enumerate(["おはようございます。", "今日はいい天気ですね。", "また明日。"])]
    ask = make_ask("gemma", CONFIG.models["gemma"], CONFIG, RunPolicy(), KeyRing())
    out = translate_cues(cues, source_lang="ja", target_track="en", glossary=EMPTY_GLOSSARY,
                         ask=ask)
    assert [c.src for c in out] == [("s0",), ("s1",), ("s2",)]
