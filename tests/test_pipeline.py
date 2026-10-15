import json
import re
from pathlib import Path

import pytest
from fakes import FakeEngine
from helpers import SPEECH, make_clip
from jsonschema import Draft202012Validator

from vid2sub import pipeline, store
from vid2sub.catalog import Candidate
from vid2sub.config import Config, Endpoint, ModelEntry
from vid2sub.engines.base import EngineError
from vid2sub.engines.clients import KeyRing
from vid2sub.media.tools import Tools
from vid2sub.subs.sidecar import HeadRecord

pytestmark = pytest.mark.media
CONTRACTS = Path(__file__).parent / "contracts"


def fake_make_ask(*args, **kwargs):
    def ask(system, prompt, model):
        ids = re.findall(r"^\[(\S+)\] \(max", prompt, flags=re.MULTILINE)
        return model.model_validate({"items": [{"src": [i], "text": f"EN {i}"} for i in ids]})
    return ask


def failing_make_ask(failures):
    """An ask that raises each of `failures` in turn, then answers like fake_make_ask."""
    pending = list(failures)

    def make(*args, **kwargs):
        answer = fake_make_ask()

        def ask(system, prompt, model):
            if pending:
                raise pending.pop(0)
            return answer(system, prompt, model)
        return ask
    return make


@pytest.fixture(autouse=True)
def no_real_translation(monkeypatch):
    monkeypatch.setattr(pipeline, "make_ask", fake_make_ask)


def make_ctx(engine, **options):
    cfg = Config(endpoints={"spark": Endpoint(base_url="http://127.0.0.1:9/v1")},
                 models={"fake": ModelEntry(catalog="whisper-large-v3-turbo", endpoint="spark",
                                            model="fake", parser="whisper.cpp", local=True),
                         "gemma": ModelEntry(catalog="gemma-4-26b-a4b", endpoint="spark",
                                             model="gemma", task="translate", local=True)})
    defaults = {"source_lang": "ja", "model": "fake", "translate_model": "gemma"}
    defaults.update(options)
    sleeps: list[float] = []
    ctx = pipeline.RunContext(config=cfg, tools=Tools.find(), keys=KeyRing(environ={}),
                              options=pipeline.RunOptions(**defaults), sleep=sleeps.append)
    ctx.engines["fake"] = engine
    ctx.sleeps = sleeps
    return ctx


@pytest.fixture
def clip(tmp_path):
    return make_clip(tmp_path, "Show - S01E01.mkv", seconds=14, speech=SPEECH)


def test_a_japanese_episode_gets_japanese_and_english_subtitles_and_a_sidecar(clip):
    result = pipeline.run_one(str(clip), make_ctx(FakeEngine()))
    assert result.status == "done", (result.reason, result.hint)
    assert sorted(result.written) == ["Show - S01E01.en.srt", "Show - S01E01.ja.srt"]
    side, _ = store.load(clip)
    [transcript] = side.transcripts()
    Draft202012Validator(json.loads((CONTRACTS / "recordings-rendition.schema.json").read_text())
                         ).validate(transcript.body)
    assert isinstance(side.head("ja"), HeadRecord) and isinstance(side.head("en"), HeadRecord)
    assert side.identity() is not None
    assert "EN " in clip.with_name("Show - S01E01.en.srt").read_text(encoding="utf-8")


def test_a_second_run_with_skip_existing_does_nothing(clip):
    engine = FakeEngine()
    pipeline.run_one(str(clip), make_ctx(engine))
    calls = len(engine.calls)
    again = pipeline.run_one(str(clip), make_ctx(engine, skip_existing=True))
    assert again.status == "skipped" and len(engine.calls) == calls


def test_someone_elses_english_file_is_left_alone(clip):
    theirs = clip.with_name("Show - S01E01.en.srt")
    theirs.write_text("1\n00:00:00,000 --> 00:00:01,000\nBazarr\n", encoding="utf-8")
    result = pipeline.run_one(str(clip), make_ctx(FakeEngine()))
    assert result.foreign == ["Show - S01E01.en.srt"]
    assert "Bazarr" in theirs.read_text(encoding="utf-8")
    assert "Show - S01E01.ja.srt" in result.written


def test_cues_follow_an_audio_delay(tmp_path):
    clip = make_clip(tmp_path, "Delayed.mkv", seconds=14, speech=SPEECH, audio_delay=2.0)
    pipeline.run_one(str(clip), make_ctx(FakeEngine()))
    side, _ = store.load(clip)
    _, cues = store.current_cues(side, "ja")
    assert cues[0].start_ms >= 2000


def test_a_dropped_connection_waits_and_carries_on(clip):
    ctx = make_ctx(FakeEngine(fail=[EngineError("connection", "down")]))
    assert pipeline.run_one(str(clip), ctx).status == "done"
    assert ctx.sleeps


def test_a_connection_that_stays_down_pauses_the_run(clip):
    engine = FakeEngine(fail=[EngineError("connection", "down")] * 100)
    with pytest.raises(pipeline.Paused):
        pipeline.run_one(str(clip), make_ctx(engine, wait_on_connection_s=10))


def test_a_translation_server_that_drops_once_waits_and_carries_on(clip, monkeypatch):
    monkeypatch.setattr(pipeline, "make_ask",
                        failing_make_ask([EngineError("connection", "down")]))
    ctx = make_ctx(FakeEngine())
    result = pipeline.run_one(str(clip), ctx)
    assert result.status == "done", (result.reason, result.hint)
    assert ctx.sleeps
    assert "EN " in clip.with_name("Show - S01E01.en.srt").read_text(encoding="utf-8")


def test_a_translation_server_that_stays_down_pauses_the_run(clip, monkeypatch):
    monkeypatch.setattr(pipeline, "make_ask",
                        failing_make_ask([EngineError("connection", "down")] * 100))
    with pytest.raises(pipeline.Paused):
        pipeline.run_one(str(clip), make_ctx(FakeEngine(), wait_on_connection_s=10))


def test_the_language_is_detected_when_not_given(clip):
    ctx = make_ctx(FakeEngine(detect={"ja": 0.95}), source_lang=None, model=None)
    ctx.candidates = [Candidate("fake", "whisper-large-v3-turbo", "endpoint", True),
                      Candidate("gemma", "gemma-4-26b-a4b", "endpoint", True)]
    assert pipeline.run_one(str(clip), ctx).status == "done"


def test_whisper_hearing_chinese_is_left_for_the_user_to_decide(clip):
    ctx = make_ctx(FakeEngine(detect={"zh": 0.95}), source_lang=None, model=None)
    ctx.candidates = [Candidate("fake", "whisper-large-v3-turbo", "endpoint", True)]
    result = pipeline.run_one(str(clip), ctx)
    assert result.status == "uncertain" and "--from" in result.hint
    assert not clip.with_name("Show - S01E01.en.srt").exists()


def test_cantonese_is_written_in_traditional_characters_as_zh_hk(clip):
    ctx = make_ctx(FakeEngine(language="yue", text="头"), source_lang="yue", targets=[])
    result = pipeline.run_one(str(clip), ctx)
    assert result.written == ["Show - S01E01.zh-HK.srt"]
    assert "頭" in clip.with_name("Show - S01E01.zh-HK.srt").read_text(encoding="utf-8")


def test_two_videos_with_the_same_name_are_refused(clip):
    clip.with_suffix(".mp4").write_bytes(b"x")
    result = pipeline.run_one(str(clip), make_ctx(FakeEngine()))
    assert result.status == "failed" and "same name" in result.reason


def test_a_missing_file_fails_with_a_reason(tmp_path):
    result = pipeline.run_one(str(tmp_path / "nope.mkv"), make_ctx(FakeEngine()))
    assert result.status == "failed" and "no file" in result.reason


def test_a_dry_run_writes_nothing(clip):
    result = pipeline.run_one(str(clip), make_ctx(FakeEngine(), dry_run=True))
    assert result.status == "planned" and not store.sidecar_path(clip).exists()


def test_an_unreadable_subtitle_file_is_reported_and_left_alone(clip):
    pipeline.run_one(str(clip), make_ctx(FakeEngine()))
    ja = clip.with_name("Show - S01E01.ja.srt")
    ja.write_bytes(b"\x00garbage")
    result = pipeline.run_one(str(clip), make_ctx(FakeEngine()))
    assert any("Show - S01E01.ja.srt" in n and "readable" in n for n in result.notes)
    assert ja.read_bytes() == b"\x00garbage"
    assert "Show - S01E01.ja.srt" in result.foreign
