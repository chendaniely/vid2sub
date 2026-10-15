import json

import pytest
from fakes import FakeEngine, fake_make_ask
from helpers import SPEECH, make_clip

from vid2sub import pipeline, store
from vid2sub.catalog import Candidate
from vid2sub.cli import main
from vid2sub.commands import _common
from vid2sub.engines.base import EngineError

pytestmark = pytest.mark.media
CONFIG = """[endpoints.spark]
base_url = "http://127.0.0.1:9/v1"
[models.fake]
catalog = "whisper-large-v3-turbo"
endpoint = "spark"
model = "fake"
parser = "whisper.cpp"
local = true
[models.gemma]
catalog = "gemma-4-26b-a4b"
endpoint = "spark"
model = "gemma"
task = "translate"
local = true
"""


@pytest.fixture
def setup(tmp_path, monkeypatch):
    cfg = tmp_path / "vid2sub.toml"
    cfg.write_text(CONFIG)
    engine = FakeEngine()
    real = _common.new_context

    def with_fakes(config, options, output):
        ctx = real(config, options, output)
        ctx.engines["fake"] = engine
        ctx.candidates = [Candidate("fake", "whisper-large-v3-turbo", "endpoint", True),
                          Candidate("gemma", "gemma-4-26b-a4b", "endpoint", True)]
        return ctx

    monkeypatch.setattr(_common, "new_context", with_fakes)
    monkeypatch.setattr(pipeline, "make_ask", fake_make_ask)
    clip = make_clip(tmp_path, "Show - S01E01.mkv", seconds=14, speech=SPEECH)
    return cfg, engine, clip


def events(text):
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def test_run_json_reports_progress_and_results_without_titles(setup, capsys):
    cfg, _, clip = setup
    code = main(["run", str(clip), "--from", "ja", "--config", str(cfg), "--json"])
    out = capsys.readouterr().out
    assert code == 0
    assert "Show - S01E01" not in out
    kinds = [e["event"] for e in events(out)]
    assert kinds[0] == "input" and "chunk" in kinds and kinds[-1] == "summary"
    result = next(e for e in events(out) if e["event"] == "result")
    assert result["status"] == "done" and result["written"] == 2


def test_to_none_writes_captions_in_the_spoken_language_only(setup):
    cfg, _, clip = setup
    assert main(["run", str(clip), "--from", "ja", "--to", "none", "--config", str(cfg)]) == 0
    assert clip.with_name("Show - S01E01.ja.srt").exists()
    assert not clip.with_name("Show - S01E01.en.srt").exists()


def test_plain_output_to_a_pipe_names_inputs_by_number(setup, capsys):
    cfg, _, clip = setup
    main(["run", str(clip), "--from", "ja", "--config", str(cfg)])
    out = capsys.readouterr().out
    assert "input 1" in out and "Show - S01E01" not in out


def test_a_connection_that_stays_down_exits_75_and_says_how_to_resume(setup, capsys):
    cfg, engine, clip = setup
    engine.fail = [EngineError("connection", "down", hint="is `make tunnel` running?")] * 100
    code = main(["run", str(clip), "--from", "ja", "--wait-on-connection", "1s",
                 "--config", str(cfg)])
    assert code == 75 and "--skip-existing" in capsys.readouterr().err


def test_ctrl_c_exits_75(setup):
    cfg, engine, clip = setup
    engine.fail = [KeyboardInterrupt()]
    assert main(["run", str(clip), "--from", "ja", "--config", str(cfg)]) == 75


def test_usage_and_config_errors_have_their_own_exit_codes(setup, tmp_path):
    cfg, _, clip = setup
    assert main(["run", str(clip), "--from", "xx", "--config", str(cfg)]) == 64
    assert main(["run", "--config", str(cfg)]) == 64
    bad = tmp_path / "bad.toml"
    bad.write_text('[endpoints.x]\nbase_url = "https://a.example/v1"\nkey_env = "sk-oops"\n')
    assert main(["run", str(clip), "--config", str(bad)]) == 78


def test_detect_reports_the_language_and_the_models_it_would_use(setup, capsys):
    cfg, _, clip = setup
    assert main(["detect", str(clip), "--config", str(cfg), "--json"]) == 0
    [report] = [e for e in events(capsys.readouterr().out) if e["event"] == "detect"]
    assert report["language"] == "ja" and report["transcribe"] == "fake"
    assert report["translate"] == "gemma" and report["uncertain"] is False


class AlwaysDown(FakeEngine):
    def detect_language(self, chunk):
        raise EngineError("connection", "down", hint="is `make tunnel` running?")


def test_detect_with_a_connection_that_stays_down_exits_75_and_says_so(setup, monkeypatch,
                                                                       capsys):
    cfg, _, clip = setup
    real = _common.new_context  # the fixture's factory, already with the fakes in

    def down(config, options, output):
        ctx = real(config, options, output)
        ctx.engines["fake"] = AlwaysDown()
        ctx.options.wait_on_connection_s = 1.0
        ctx.sleep = lambda seconds: None
        return ctx

    monkeypatch.setattr(_common, "new_context", down)
    code = main(["detect", str(clip), "--config", str(cfg), "--json"])
    captured = capsys.readouterr()
    assert code == 75
    assert "paused" in [e["event"] for e in events(captured.out)]
    assert "Show - S01E01" not in captured.out


def test_a_missing_input_list_is_a_usage_error_that_does_not_name_the_path(setup, tmp_path,
                                                                          capsys):
    cfg, _, _ = setup
    missing = tmp_path / "missing-list.txt"
    assert main(["run", "--from-file", str(missing), "--config", str(cfg)]) == 64
    assert "missing-list" not in capsys.readouterr().err


def test_detect_with_nothing_to_do_is_a_usage_error(setup, capsys):
    cfg, _, _ = setup
    assert main(["detect", "--config", str(cfg)]) == 64
    assert "nothing to do" in capsys.readouterr().err


def test_ctrl_c_while_expanding_inputs_exits_75(setup, monkeypatch):
    cfg, _, clip = setup

    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(_common, "expand", interrupted)
    assert main(["run", str(clip), "--config", str(cfg)]) == 75
    assert main(["detect", str(clip), "--config", str(cfg)]) == 75


@pytest.mark.parametrize("flags", [["--json"], []])
def test_a_failed_input_never_puts_its_name_in_the_output(setup, tmp_path, capsys, flags):
    cfg, _, _ = setup
    ghost = tmp_path / "Secret Show - S01E01.mkv"
    code = main(["run", str(ghost), "--from", "ja", "--config", str(cfg), *flags])
    out = capsys.readouterr().out
    assert code == 1 and "Secret Show" not in out
    if flags:
        assert next(e for e in events(out) if e["event"] == "result")["status"] == "failed"
    else:
        assert "failed" in out


def test_an_unexpected_error_fails_one_input_and_the_next_still_runs(setup, tmp_path, capsys,
                                                                    monkeypatch):
    monkeypatch.delenv("VID2SUB_DEBUG", raising=False)
    cfg, engine, clip = setup
    second = make_clip(tmp_path, "Show - S01E02.mkv", seconds=14, speech=SPEECH)
    engine.fail = [RuntimeError("boom /secret/path")]
    code = main(["run", str(clip), str(second), "--from", "ja", "--config", str(cfg), "--json"])
    captured = capsys.readouterr()
    results = [e for e in events(captured.out) if e["event"] == "result"]
    assert code == 1
    assert [(r["status"], r["kind"]) for r in results] == [("failed", "RuntimeError"),
                                                           ("done", "")]
    assert "/secret/path" not in captured.out + captured.err
    assert second.with_name("Show - S01E02.en.srt").exists()


@pytest.mark.parametrize("flags", [
    ["--from", "yue", "--script", "hans"],
    ["--from", "yue", "--script", "hant"],
    ["--from", "ja", "--model", "nope"],
    ["--from", "ja", "--model", "gemma"],
    ["--from", "ja", "--translate-model", "nope"],
    ["--from", "ja", "--translate-model", "fake"],
])
def test_a_contradictory_or_unknown_choice_is_a_usage_error_before_any_input(setup, capsys,
                                                                             flags):
    cfg, engine, clip = setup
    assert main(["run", str(clip), *flags, "--config", str(cfg)]) == 64
    assert engine.calls == []
    assert not store.sidecar_path(clip).exists()
    assert "Show - S01E01" not in capsys.readouterr().err


@pytest.mark.parametrize("model", ["nope", "fake"])
def test_translate_refuses_a_translation_model_it_does_not_know_up_front(setup, model):
    cfg, _, clip = setup
    assert main(["run", str(clip), "--from", "ja", "--to", "none", "--config", str(cfg)]) == 0
    before = store.sidecar_path(clip).read_bytes()
    code = main(["translate", str(clip), "--to", "en", "--translate-model", model,
                 "--config", str(cfg)])
    assert code == 64
    assert store.sidecar_path(clip).read_bytes() == before
