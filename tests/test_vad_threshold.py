import inspect

import pytest
from fakes import FakeEngine, fake_make_ask
from helpers import SPEECH, make_clip
from test_cli_run import CONFIG
from test_pipeline import make_ctx

from vid2sub import config as c
from vid2sub import pipeline, store
from vid2sub.catalog import Candidate
from vid2sub.cli import main
from vid2sub.commands import _common
from vid2sub.media import vad

pytestmark = pytest.mark.media
MEASURED = 0.25  # Phase 2 Task 27's measurement on M1's exit-test episode (spec §8.6)


@pytest.fixture
def heard(monkeypatch) -> list[float | None]:
    """The threshold each call to speech_regions was given (None: none); the regions are real."""
    given: list[float | None] = []
    real = pipeline.speech_regions

    def spy(samples, **kwargs):
        given.append(kwargs.get("threshold"))
        return real(samples, **kwargs)

    monkeypatch.setattr(pipeline, "speech_regions", spy)
    return given


@pytest.fixture
def cli(tmp_path, monkeypatch):
    """A 14 s episode, the fake engines, and a vid2sub.toml that sets vad_threshold = 0.4."""
    cfg = tmp_path / "vid2sub.toml"
    cfg.write_text(CONFIG + "[defaults]\nvad_threshold = 0.4\n")
    real = _common.new_context

    def with_fakes(config, options, output):
        ctx = real(config, options, output)
        ctx.engines["fake"] = FakeEngine()
        ctx.candidates = [Candidate("fake", "whisper-large-v3-turbo", "endpoint", True),
                          Candidate("gemma", "gemma-4-26b-a4b", "endpoint", True)]
        return ctx

    monkeypatch.setattr(_common, "new_context", with_fakes)
    monkeypatch.setattr(pipeline, "make_ask", fake_make_ask)
    return make_clip(tmp_path, "Show - S01E01.mkv", seconds=14, speech=SPEECH), cfg


def test_the_default_is_the_threshold_measured_on_a_drama_episode():
    assert vad.THRESHOLD == MEASURED
    assert inspect.signature(vad.speech_regions).parameters["threshold"].default == MEASURED
    assert c.Config().defaults.vad_threshold == MEASURED
    assert f"# vad_threshold = {MEASURED}" in c.STARTER


def test_vad_threshold_in_vid2sub_toml_is_read(tmp_path):
    path = tmp_path / "vid2sub.toml"
    path.write_text("[defaults]\nvad_threshold = 0.4\n", encoding="utf-8")
    assert c.load_config(path).defaults.vad_threshold == 0.4


@pytest.mark.parametrize("value", ["0", "1", "1.5", "-0.2", "nan", "true"])
def test_a_threshold_outside_0_to_1_is_refused_at_load_naming_the_setting(tmp_path, value):
    path = tmp_path / "vid2sub.toml"
    path.write_text(f"[defaults]\nvad_threshold = {value}\n", encoding="utf-8")
    with pytest.raises(c.ConfigError,
                       match=r"^defaults\.vad_threshold: Input should be (greater|less) than"):
        c.load_config(path)


def test_a_run_with_no_setting_uses_the_measured_default(tmp_path, heard):
    clip = make_clip(tmp_path, "Show - S01E01.mkv", seconds=14, speech=SPEECH)
    assert pipeline.run_one(str(clip), make_ctx(FakeEngine(), targets=[])).status == "done"
    assert heard == [MEASURED]


def test_the_threshold_in_vid2sub_toml_reaches_speech_regions(cli, heard):
    clip, cfg = cli
    assert main(["run", str(clip), "--from", "ja", "--to", "none", "--config", str(cfg)]) == 0
    assert heard == [0.4]


def test_vad_threshold_on_the_command_line_overrides_vid2sub_toml(cli, heard):
    clip, cfg = cli
    assert main(["run", str(clip), "--from", "ja", "--to", "none", "--config", str(cfg),
                 "--vad-threshold", "0.3"]) == 0
    assert heard == [0.3]


@pytest.mark.parametrize("value", ["0", "1", "1.5", "loud"])
def test_a_vad_threshold_flag_outside_0_to_1_is_a_usage_error(cli, capsys, value):
    clip, cfg = cli
    with pytest.raises(SystemExit) as err:
        main(["run", str(clip), "--config", str(cfg), "--vad-threshold", value])
    assert err.value.code == 64
    assert "--vad-threshold: a number above 0 and below 1" in capsys.readouterr().err


def test_detect_finds_speech_with_the_threshold_in_vid2sub_toml_too(cli, heard):
    clip, cfg = cli
    assert main(["detect", str(clip), "--config", str(cfg), "--json"]) == 0
    assert heard == [0.4]


def test_a_chunk_heard_at_one_threshold_is_not_reused_at_another(tmp_path, monkeypatch):
    # The same regions whatever the threshold, so the chunk plan is the same and only the cache
    # key can tell the two runs apart.
    regions = pipeline.speech_regions
    monkeypatch.setattr(pipeline, "speech_regions",
                        lambda samples, **kwargs: regions(samples, threshold=0.5))
    clip = make_clip(tmp_path, "Show - S01E01.mkv", seconds=14, speech=SPEECH)
    engine = FakeEngine()
    ctx = make_ctx(engine, targets=[], vad_threshold=0.3)
    pipeline.run_one(str(clip), ctx)
    store.sidecar_path(clip).unlink()
    calls = len(engine.calls)
    pipeline.run_one(str(clip), ctx)
    assert len(engine.calls) == calls  # the same threshold: the cached chunk is used
    store.sidecar_path(clip).unlink()
    ctx.options.vad_threshold = 0.4
    pipeline.run_one(str(clip), ctx)
    assert len(engine.calls) > calls


def test_the_transcript_records_the_threshold_it_used_and_its_version_changes_with_it(tmp_path):
    clip = make_clip(tmp_path, "Show - S01E01.mkv", seconds=14, speech=SPEECH)
    versions = []
    for threshold in (0.3, 0.4):
        store.sidecar_path(clip).unlink(missing_ok=True)
        pipeline.run_one(str(clip), make_ctx(FakeEngine(), targets=[], vad_threshold=threshold))
        [transcript] = store.load(clip)[0].transcripts()
        assert transcript.body["meta"]["vad"] == {"id": vad.VAD_ID, "threshold": threshold}
        versions.append(transcript.body["version"])
    # §9.6: pipeline8 hashes the VAD's settings, so another threshold mints another version.
    assert versions[0] != versions[1]
    assert versions[0].endswith(f"+p{pipeline.pipeline8(0.3)}")
