import json
import re
from pathlib import Path

import pytest
from fakes import FakeEngine, fake_make_ask
from helpers import SPEECH, make_clip
from jsonschema import Draft202012Validator

from vid2sub import detect as detecting
from vid2sub import pipeline, store
from vid2sub.catalog import Candidate
from vid2sub.config import Config, Endpoint, ModelEntry
from vid2sub.engines.base import EngineError
from vid2sub.engines.clients import KeyRing
from vid2sub.media.identity import identify
from vid2sub.media.tools import Tools
from vid2sub.subs import naming
from vid2sub.subs.rendition import cues_body
from vid2sub.subs.sidecar import HeadRecord, make_rendition

pytestmark = pytest.mark.media
CONTRACTS = Path(__file__).parent / "contracts"


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
    assert 2000 <= cues[0].start_ms < 2000 + 1000  # the delay once, not twice


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
    assert any("ja" in n and "readable" in n for n in result.notes)
    assert not any("Show - S01E01" in n for n in result.notes)
    assert ja.read_bytes() == b"\x00garbage"
    assert "Show - S01E01.ja.srt" in result.foreign


def recording_make_ask(seen):
    """A translator that records the cue ids of each call."""
    def make(*args, **kwargs):
        inner = fake_make_ask()

        def ask(system, prompt, model):
            seen.append(re.findall(r"^\[(\S+)\] \(max", prompt, flags=re.MULTILINE))
            return inner(system, prompt, model)
        return ask
    return make


def add_version(clip, track, edit, by="auto"):
    """Append a new rendition of `track` made by `edit(cues)`, with a head by `by`."""
    side, _ = store.load(clip)
    rec, cues = store.current_cues(side, track)
    info = naming.track(track)
    body = cues_body(edit(cues), language=info.lang, script=info.script, engine="test",
                     model=rec.body.get("model"), version="test", created_at=store.now(),
                     inputs={}, meta=rec.body.get("meta", {}),
                     glossary_sha=rec.body["payload"].get("glossary_sha"))
    new = make_rendition([rec.id], track, body)
    head = store.head_record(side, track, new.id, by, replace_person=True)
    header = store.header_for(clip, identify(clip), side.header.video.duration_ms)
    store.append(clip, header, [new, head])
    return new


# 1. detection and discovery follow the wait/pause policy


class DropsDetectOnce(FakeEngine):
    def __init__(self, *args, errors=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.detect_errors = list(errors)

    def detect_language(self, chunk):
        if self.detect_errors:
            raise self.detect_errors.pop(0)
        return super().detect_language(chunk)


def detector_candidates():
    return [Candidate("fake", "whisper-large-v3-turbo", "endpoint", True),
            Candidate("gemma", "gemma-4-26b-a4b", "endpoint", True)]


def test_a_dropped_connection_during_language_detection_waits_and_carries_on(clip):
    engine = DropsDetectOnce(errors=[EngineError("connection", "down")])
    ctx = make_ctx(engine, source_lang=None, model="fake")
    ctx.candidates = detector_candidates()
    result = pipeline.run_one(str(clip), ctx)
    assert result.status == "done", (result.reason, result.hint)
    assert ctx.sleeps


def test_models_that_cannot_be_reached_pause_the_run_instead_of_reporting_none(clip, monkeypatch):
    down = [Candidate("fake", "whisper-large-v3-turbo", "endpoint", False, "down",
                      unreachable=True)]
    monkeypatch.setattr(detecting, "candidates", lambda *a, **k: list(down))
    ctx = make_ctx(FakeEngine(), source_lang=None, model="fake", wait_on_connection_s=10)
    ctx.candidates = list(down)
    with pytest.raises(pipeline.Paused) as caught:
        pipeline.run_one(str(clip), ctx)
    assert caught.value.error.kind == "connection"


def test_unreachable_models_that_come_back_let_the_run_carry_on(clip, monkeypatch):
    down = [Candidate("fake", "whisper-large-v3-turbo", "endpoint", False, "down",
                      unreachable=True)]
    looks = []

    def look(*args, **kwargs):
        looks.append(1)
        return list(down) if len(looks) == 1 else detector_candidates()
    monkeypatch.setattr(detecting, "candidates", look)
    ctx = make_ctx(FakeEngine(), source_lang=None, model="fake")
    ctx.candidates = down
    assert pipeline.run_one(str(clip), ctx).status == "done"
    assert ctx.sleeps


def test_candidates_that_failed_to_connect_are_marked_unreachable(monkeypatch):
    from vid2sub.engines import clients

    def boom(*args, **kwargs):
        raise EngineError("connection", "down")
    monkeypatch.setattr(clients, "list_models", boom)
    cfg = make_ctx(FakeEngine()).config
    found = detecting.candidates(cfg, KeyRing(environ={}))
    assert found and all(c.unreachable and not c.available for c in found)


# 2. a track whose head can't move is never re-translated


def test_an_edited_english_file_is_kept_and_not_translated_again(clip, monkeypatch):
    pipeline.run_one(str(clip), make_ctx(FakeEngine()))
    en = clip.with_name("Show - S01E01.en.srt")
    en.write_text(en.read_text(encoding="utf-8").replace("EN ", "MINE ", 1), encoding="utf-8")
    seen: list = []
    monkeypatch.setattr(pipeline, "make_ask", recording_make_ask(seen))
    def translations():
        return [r for r in store.load(clip)[0].records if getattr(r, "type", "") == "rendition"
                and str(r.body.get("engine", "")).startswith("translate")]
    before = len(translations())
    result = pipeline.run_one(str(clip), make_ctx(FakeEngine()))
    assert result.status == "done", (result.reason, result.hint)
    assert seen == []
    assert "en" in result.kept
    assert any("en" in n and "--replace-edited" in n for n in result.notes)
    assert len(translations()) == before
    assert "MINE" in en.read_text(encoding="utf-8")


def test_a_translation_with_an_edited_cue_keeps_it_when_the_glossary_changes(clip, monkeypatch):
    pipeline.run_one(str(clip), make_ctx(FakeEngine()))
    add_version(clip, "en", lambda cues: [
        c.model_copy(update={"text": "MINE", "flags": ("edited",)}) if i == 0 else c
        for i, c in enumerate(cues)])
    clip.with_name(naming.GLOSSARY_NAME).write_text(
        'description = "new"\n[terms]\n"字" = "ji"\n', encoding="utf-8")
    seen: list = []
    monkeypatch.setattr(pipeline, "make_ask", recording_make_ask(seen))
    result = pipeline.run_one(str(clip), make_ctx(FakeEngine()))
    assert result.status == "done", (result.reason, result.hint)
    side, _ = store.load(clip)
    _, source = store.current_cues(side, "ja")
    _, english = store.current_cues(side, "en")
    kept_src = set(english[0].src)
    sent = [i for call in seen for i in call]
    assert sent and not kept_src & set(sent)
    assert set(sent) == {c.id for c in source} - kept_src
    assert "MINE" in clip.with_name("Show - S01E01.en.srt").read_text(encoding="utf-8")


def test_only_the_cues_whose_source_changed_are_translated_again(clip, monkeypatch):
    pipeline.run_one(str(clip), make_ctx(FakeEngine()))
    side, _ = store.load(clip)
    _, source = store.current_cues(side, "ja")
    assert len(source) > 1
    add_version(clip, "ja", lambda cues: [
        c.model_copy(update={"text": "新しい"}) if i == 0 else c for i, c in enumerate(cues)])
    seen: list = []
    monkeypatch.setattr(pipeline, "make_ask", recording_make_ask(seen))
    result = pipeline.run_one(str(clip), make_ctx(FakeEngine()))
    assert result.status == "done", (result.reason, result.hint)
    assert [i for call in seen for i in call] == [source[0].id]


def test_a_source_track_with_two_versions_fails_without_transcribing_again(clip):
    pipeline.run_one(str(clip), make_ctx(FakeEngine()))
    side, _ = store.load(clip)
    rec, _ = store.current_cues(side, "ja")
    forks = [make_rendition([rec.id], "ja", {**rec.body, "version": f"fork{n}"})
             for n in (1, 2)]
    header = store.header_for(clip, identify(clip), side.header.video.duration_ms)
    store.append(clip, header, [r for f in forks for r in (
        f, HeadRecord(track="ja", rendition=f.id, replaces=rec.id, by="user", at=store.now()))])
    assert not isinstance(store.load(clip)[0].head("ja"), HeadRecord)
    engine = FakeEngine()
    result = pipeline.run_one(str(clip), make_ctx(engine))
    assert result.status == "failed" and "two versions" in result.reason
    assert not [c for c in engine.calls if c[0] == "transcribe"]


# 3. folder language inheritance


def folder_clips(tmp_path, count):
    return [make_clip(tmp_path, f"Show - S01E0{n}.mkv", seconds=14, speech=SPEECH)
            for n in range(1, count + 1)]


def detect_calls(engine):
    return [c for c in engine.calls if c[0] == "detect"]


def test_the_third_video_in_a_folder_inherits_the_language_from_two_confident_ones(tmp_path):
    engine = FakeEngine(detect={"ja": 0.95})
    ctx = make_ctx(engine, source_lang=None, model="fake", targets=[])
    ctx.candidates = detector_candidates()
    first, second, third = folder_clips(tmp_path, 3)
    for video in (first, second):
        assert pipeline.run_one(str(video), ctx).status == "done"
    seen = len(detect_calls(engine))
    result = pipeline.run_one(str(third), ctx)
    assert result.status == "done", (result.reason, result.hint)
    assert len(detect_calls(engine)) == seen
    assert any("ja" in n and "like the other videos" in n for n in result.notes)


def test_uncertain_detections_are_not_pooled_into_a_folder_vote(tmp_path):
    engine = FakeEngine(detect={"zh": 0.95})
    ctx = make_ctx(engine, source_lang=None, model="fake", targets=[], on_uncertain="proceed")
    ctx.candidates = detector_candidates()
    first, second, third = folder_clips(tmp_path, 3)
    for video in (first, second):
        result = pipeline.run_one(str(video), ctx)
        assert result.status == "done", (result.reason, result.hint)
        assert any("went ahead with zh" in n for n in result.notes)
    seen = len(detect_calls(engine))
    pipeline.run_one(str(third), ctx)
    assert len(detect_calls(engine)) > seen


# 4. ordinary errors fail the input, not the run


def test_a_glossary_that_is_not_utf8_fails_the_input_with_a_fix(clip):
    clip.with_name(naming.GLOSSARY_NAME).write_bytes('[terms]\n"用語" = "term"\n'.encode("shift_jis"))
    result = pipeline.run_one(str(clip), make_ctx(FakeEngine()))
    assert result.status == "failed" and result.kind == "GlossaryError"
    assert "UTF-8" in result.reason


def test_a_permission_error_fails_the_input_without_naming_the_path(clip, monkeypatch):
    def refuse(*args, **kwargs):
        raise PermissionError(13, "Permission denied", "/x")
    monkeypatch.setattr(store, "append", refuse)
    result = pipeline.run_one(str(clip), make_ctx(FakeEngine()))
    assert result.status == "failed" and result.kind == "PermissionError"
    assert "/x" not in result.reason and "Permission denied" in result.reason
    assert "permissions" in result.hint


# 6. keep_awake lives in tests/test_awake.py. 7. dry runs


def test_a_dry_run_does_not_record_outside_edits(clip):
    pipeline.run_one(str(clip), make_ctx(FakeEngine()))
    ja = clip.with_name("Show - S01E01.ja.srt")
    ja.write_text(ja.read_text(encoding="utf-8").replace("字", "X", 1), encoding="utf-8")
    before = store.sidecar_path(clip).read_bytes()
    result = pipeline.run_one(str(clip), make_ctx(FakeEngine(), dry_run=True))
    assert result.status == "planned"
    assert store.sidecar_path(clip).read_bytes() == before


# folds


def test_the_vocabulary_is_part_of_the_chunk_cache_key(clip):
    engine = FakeEngine()
    ctx = make_ctx(engine, targets=[])
    pipeline.run_one(str(clip), ctx)
    clip.with_name(naming.GLOSSARY_NAME).write_text('[terms]\n"字" = "ji"\n', encoding="utf-8")
    store.sidecar_path(clip).unlink()
    calls = len(engine.calls)
    pipeline.run_one(str(clip), ctx)
    assert len(engine.calls) > calls


def test_videos_whose_names_differ_only_by_case_are_refused(clip):
    clip.with_name("show - s01e01.MP4").write_bytes(b"x")
    result = pipeline.run_one(str(clip), make_ctx(FakeEngine()))
    assert result.status == "failed" and "same name" in result.reason


def test_a_given_language_that_differs_from_the_existing_transcript_is_noted(clip):
    pipeline.run_one(str(clip), make_ctx(FakeEngine()))
    result = pipeline.run_one(str(clip), make_ctx(FakeEngine(), source_lang="ko"))
    assert any("kept the existing ja transcript" in n and "--from ko" in n
               for n in result.notes)


def test_a_server_error_is_retried_twice_then_fails_the_input(clip):
    engine = FakeEngine(fail=[EngineError("server", "boom")] * 10)
    ctx = make_ctx(engine)
    result = pipeline.run_one(str(clip), ctx)
    assert result.status == "failed" and result.kind == "server"
    assert ctx.sleeps == [2.0, 4.0]
    assert len([c for c in engine.calls if c[0] == "transcribe"]) == 3


def test_a_bad_key_fails_at_once_without_waiting(clip):
    engine = FakeEngine(fail=[EngineError("auth", "no")] * 10)
    ctx = make_ctx(engine)
    result = pipeline.run_one(str(clip), ctx)
    assert result.status == "failed" and result.kind == "auth"
    assert ctx.sleeps == []


def test_a_paused_run_carries_the_connection_error(clip):
    engine = FakeEngine(fail=[EngineError("connection", "down")] * 100)
    with pytest.raises(pipeline.Paused) as caught:
        pipeline.run_one(str(clip), make_ctx(engine, wait_on_connection_s=10))
    assert caught.value.error.kind == "connection"


def fork_track(clip, track):
    side, _ = store.load(clip)
    rec, _ = store.current_cues(side, track)
    forks = [make_rendition([rec.id], track, {**rec.body, "version": f"fork{n}"})
             for n in (1, 2)]
    header = store.header_for(clip, identify(clip), side.header.video.duration_ms)
    store.append(clip, header, [r for f in forks for r in (
        f, HeadRecord(track=track, rendition=f.id, replaces=rec.id, by="user", at=store.now()))])


def test_a_translation_with_two_versions_is_left_alone_and_not_translated_again(clip,
                                                                                monkeypatch):
    pipeline.run_one(str(clip), make_ctx(FakeEngine()))
    fork_track(clip, "en")
    seen: list = []
    monkeypatch.setattr(pipeline, "make_ask", recording_make_ask(seen))
    result = pipeline.run_one(str(clip), make_ctx(FakeEngine()))
    assert seen == []
    assert any("en" in n and "two versions" in n for n in result.notes)


def test_a_download_neither_inherits_a_folder_language_nor_votes(tmp_path):
    import numpy as np
    engine = FakeEngine(detect={"ko": 0.95})
    ctx = make_ctx(engine, source_lang=None, model="fake")
    ctx.candidates = detector_candidates()
    ctx.folder_votes[tmp_path] = ["ja", "ja"]
    samples = np.zeros(16 * 30_000, dtype=np.int16)
    result = pipeline.InputResult(input="x")
    lang, _, _ = pipeline._choose(tmp_path / "v.mp4", samples, [(0, 30_000)], lambda s: b"",
                                  ctx, result, is_url=True)
    assert lang == "ko" and detect_calls(engine)
    assert ctx.folder_votes[tmp_path] == ["ja", "ja"]


# final review 1: model selection never silently falls back past an unreachable preferred model


def gemma(available=True):
    if available:
        return Candidate("gemma", "gemma-4-26b-a4b", "endpoint", True)
    return Candidate("gemma", "gemma-4-26b-a4b", "endpoint", False, "down", unreachable=True)


def probes(*lists):
    """detecting.candidates answering each list in turn, then the last one for ever."""
    answers = [list(x) for x in lists]

    def look(*args, **kwargs):
        return list(answers.pop(0) if len(answers) > 1 else answers[0])
    return look


def recording_models(seen):
    def make(model_name, *args, **kwargs):
        seen.append(model_name)
        return fake_make_ask()
    return make


def with_cloud_translator(ctx):
    ctx.config.endpoints["openai"] = Endpoint(base_url="https://api.openai.com/v1",
                                              key_env="OPENAI_API_KEY")
    ctx.config.models["gpt"] = ModelEntry(catalog="openai-gpt", endpoint="openai",
                                          model="gpt-test", task="translate")
    return Candidate("gpt", "openai-gpt", "endpoint", True, cloud=True)


def test_a_translation_model_unreachable_at_first_is_waited_for_and_used(clip, monkeypatch):
    monkeypatch.setattr(detecting, "candidates", probes([gemma(False)], [gemma(False)],
                                                        [gemma()]))
    ctx = make_ctx(FakeEngine(), translate_model=None)
    result = pipeline.run_one(str(clip), ctx)
    assert result.status == "done", (result.reason, result.hint)
    assert ctx.sleeps
    assert "EN " in clip.with_name("Show - S01E01.en.srt").read_text(encoding="utf-8")


def test_a_translation_model_that_stays_unreachable_pauses_the_run(clip, monkeypatch):
    monkeypatch.setattr(detecting, "candidates", probes([gemma(False)]))
    ctx = make_ctx(FakeEngine(), translate_model=None, wait_on_connection_s=10)
    with pytest.raises(pipeline.Paused) as caught:
        pipeline.run_one(str(clip), ctx)
    assert caught.value.error.kind == "connection"


def test_an_unreachable_spark_never_falls_back_to_the_cloud_even_when_allowed(clip, monkeypatch):
    seen: list = []
    monkeypatch.setattr(pipeline, "make_ask", recording_models(seen))
    ctx = make_ctx(FakeEngine(), translate_model=None, allow_cloud=True, wait_on_connection_s=10)
    cloud = with_cloud_translator(ctx)
    monkeypatch.setattr(detecting, "candidates", probes([gemma(False), cloud]))
    with pytest.raises(pipeline.Paused):
        pipeline.run_one(str(clip), ctx)
    assert ctx.sleeps
    assert "gpt" not in seen
    assert not clip.with_name("Show - S01E01.en.srt").exists()


def test_an_unreachable_model_the_route_would_not_pick_causes_no_waiting(clip, monkeypatch):
    lower = Candidate("local", "local-llm", "endpoint", False, "down", unreachable=True)
    monkeypatch.setattr(detecting, "candidates", probes([gemma(), lower]))
    ctx = make_ctx(FakeEngine(), translate_model=None)
    result = pipeline.run_one(str(clip), ctx)
    assert result.status == "done", (result.reason, result.hint)
    assert ctx.sleeps == []


def test_an_unreachable_spark_whisper_never_falls_back_to_cloud_transcription(clip,
                                                                              monkeypatch):
    spark = Candidate("fake", "whisper-large-v3-turbo", "endpoint", False, "down",
                      unreachable=True)
    cloud = Candidate("cloudwhisper", "openai-whisper-1", "endpoint", True, cloud=True)
    monkeypatch.setattr(detecting, "candidates", probes([spark, cloud]))
    engine = FakeEngine()
    ctx = make_ctx(engine, model=None, allow_cloud=True, wait_on_connection_s=10)
    ctx.engines["cloudwhisper"] = engine
    with pytest.raises(pipeline.Paused):
        pipeline.run_one(str(clip), ctx)
    assert ctx.sleeps
    assert not [c for c in engine.calls if c[0] == "transcribe"]


# final review 4: --dry-run never downloads

LINK = "https://youtu.be/dQw4w9WgXcQ"


@pytest.fixture
def no_download(monkeypatch):
    def download(*args, **kwargs):
        pytest.fail("a dry run downloaded a video")
    monkeypatch.setattr(pipeline.youtube, "download", download)


def test_a_dry_run_of_a_link_never_downloads_and_plans_by_the_video_id(tmp_path, no_download):
    ctx = make_ctx(FakeEngine(), dry_run=True)
    ctx.config.defaults.youtube_dir = str(tmp_path / "yt")
    result = pipeline.run_one(LINK, ctx)
    assert result.status == "planned", (result.reason, result.hint)
    assert "dQw4w9WgXcQ" in result.plan["download"]
    assert result.title == ""
    assert not (tmp_path / "yt").exists()


def test_a_dry_run_of_a_link_already_downloaded_plans_against_that_file(tmp_path, no_download):
    yt = tmp_path / "yt"
    yt.mkdir()
    make_clip(yt, "Never Gonna [dQw4w9WgXcQ].mkv", seconds=14, speech=SPEECH)
    ctx = make_ctx(FakeEngine(), dry_run=True)
    ctx.config.defaults.youtube_dir = str(yt)
    result = pipeline.run_one(LINK, ctx)
    assert result.status == "planned", (result.reason, result.hint)
    assert "download" not in result.plan
    assert result.plan["files"] == ["Never Gonna [dQw4w9WgXcQ].en.srt"]
    assert not store.sidecar_path(yt / "Never Gonna [dQw4w9WgXcQ].mkv").exists()


# final review 6: a replaced video is noticed (spec §8.3)

CHANGED = "this video changed since its subtitles were made"


def replace_video(clip):
    with clip.open("ab") as f:
        f.write(b"\0" * 4096)


def test_a_replaced_video_is_noticed_with_the_difference_and_no_name(clip):
    assert pipeline.run_one(str(clip), make_ctx(FakeEngine())).status == "done"
    again = pipeline.run_one(str(clip), make_ctx(FakeEngine()))
    assert not [n for n in again.notes if CHANGED in n]
    side_before = store.sidecar_path(clip).read_bytes()
    replace_video(clip)
    result = pipeline.run_one(str(clip), make_ctx(FakeEngine()))
    assert result.status == "done", (result.reason, result.hint)
    [note] = [n for n in result.notes if CHANGED in n]
    assert "size" in note and "→" in note and "may no longer line up" in note
    assert "Show" not in note and "S01E01" not in note and "mkv" not in note
    assert store.sidecar_path(clip).read_bytes().startswith(side_before.splitlines()[0])


def test_rewriting_the_files_of_a_replaced_video_notices_it_too(clip):
    pipeline.run_one(str(clip), make_ctx(FakeEngine()))
    replace_video(clip)
    result = pipeline.write_one(str(clip), make_ctx(FakeEngine()))
    assert result.status == "done", (result.reason, result.hint)
    assert [n for n in result.notes if CHANGED in n]


@pytest.mark.parametrize("old, new, expected", [
    ((1_200_000_000, "a", 1_420_000), (1_400_000_000, "b", 1_421_000),
     "size 1.2 GB → 1.4 GB, duration 23:40 → 23:41"),
    ((95_301, "a", 14_000), (95_311, "b", 14_000), "size 95,301 bytes → 95,311 bytes"),
    ((10, "a", 14_000), (10, "b", 14_020), "duration 14,000 ms → 14,020 ms"),
    ((10, "a", 14_000), (10, "b", 14_000), "same size and duration, different content"),
])
def test_the_difference_is_said_in_units_a_person_reads(old, new, expected):
    from vid2sub.subs.sidecar import VideoInfo
    def info(size, quick, ms):
        return VideoInfo(name="x.mkv", size=size, quick_sha256=quick, duration_ms=ms)
    assert pipeline.video_change(info(*old), info(*new)) == expected
    assert pipeline.video_change(info(*old), info(*old)) is None


# final review 7: one unexpected error fails one input, not the season (spec §17.3)


def test_an_unexpected_error_fails_only_this_input_and_keeps_its_details_out(clip, capsys,
                                                                             monkeypatch):
    monkeypatch.delenv("VID2SUB_DEBUG", raising=False)
    engine = FakeEngine(fail=[RuntimeError("boom /secret/path")])
    result = pipeline.run_one(str(clip), make_ctx(engine))
    assert result.status == "failed" and result.kind == "RuntimeError"
    assert result.reason == "vid2sub hit an unexpected error (RuntimeError)"
    assert result.hint == "please report it; set VID2SUB_DEBUG=1 to see the details"
    assert "/secret/path" not in capsys.readouterr().err


def test_vid2sub_debug_prints_the_traceback_of_an_unexpected_error(clip, capsys, monkeypatch):
    monkeypatch.setenv("VID2SUB_DEBUG", "1")
    engine = FakeEngine(fail=[RuntimeError("boom /secret/path")])
    assert pipeline.run_one(str(clip), make_ctx(engine)).status == "failed"
    err = capsys.readouterr().err
    assert "Traceback" in err and "boom /secret/path" in err
