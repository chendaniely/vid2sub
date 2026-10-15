import json

import pytest
from fakes import FakeEngine, fake_make_ask
from helpers import SPEECH, make_clip
from test_cli_run import CONFIG

from vid2sub import detect as detecting
from vid2sub import pipeline
from vid2sub.catalog import Candidate, readme_table
from vid2sub.cli import main
from vid2sub.commands import _common

pytestmark = pytest.mark.media


@pytest.fixture
def setup(tmp_path, monkeypatch):
    cfg = tmp_path / "vid2sub.toml"
    cfg.write_text(CONFIG)
    calls = []
    real = _common.new_context

    def with_fakes(config, options, output):
        ctx = real(config, options, output)
        ctx.engines["fake"] = FakeEngine()
        ctx.candidates = [Candidate("fake", "whisper-large-v3-turbo", "endpoint", True),
                          Candidate("gemma", "gemma-4-26b-a4b", "endpoint", True)]
        return ctx

    def counting_ask(*args, **kwargs):
        inner = fake_make_ask()

        def ask(system, prompt, model):
            calls.append(prompt)
            return inner(system, prompt, model)
        return ask

    monkeypatch.setattr(_common, "new_context", with_fakes)
    monkeypatch.setattr(pipeline, "make_ask", counting_ask)
    clip = make_clip(tmp_path, "Show - S01E01.mkv", seconds=14, speech=SPEECH)
    return cfg, clip, calls


def test_translate_adds_a_language_to_an_existing_video(setup):
    cfg, clip, _ = setup
    assert main(["run", str(clip), "--from", "ja", "--to", "none", "--config", str(cfg)]) == 0
    assert main(["translate", str(clip), "--to", "zh-Hant", "--config", str(cfg)]) == 0
    assert clip.with_name("Show - S01E01.zh-TW.srt").exists()


def test_translate_stale_only_redoes_only_what_changed(setup):
    cfg, clip, calls = setup
    main(["run", str(clip), "--from", "ja", "--config", str(cfg)])
    ja = clip.with_name("Show - S01E01.ja.srt")
    text = ja.read_text(encoding="utf-8")
    first_line = text.split("\n")[2]
    ja.write_text(text.replace(first_line, "直した", 1), encoding="utf-8")
    calls.clear()
    assert main(["translate", str(clip), "--to", "en", "--stale-only", "--config", str(cfg)]) == 0
    assert len(calls) == 1 and calls[0].count("(max") == 1


def test_translate_needs_a_sidecar_first(setup, capsys):
    cfg, clip, _ = setup
    assert main(["translate", str(clip), "--to", "en", "--config", str(cfg)]) == 1
    assert "vid2sub run" in capsys.readouterr().out


def test_import_makes_an_existing_srt_the_source_then_translate_uses_it(setup, tmp_path):
    cfg, clip, _ = setup
    sub = tmp_path / "fansub.srt"
    sub.write_text("1\n00:00:01,000 --> 00:00:02,000\nこんにちは\n\n"
                   "2\n00:00:03,000 --> 00:00:04,000\nさようなら\n", encoding="utf-8")
    assert main(["import", str(sub), "--video", str(clip), "--lang", "ja",
                 "--config", str(cfg)]) == 0
    assert main(["translate", str(clip), "--to", "en", "--config", str(cfg)]) == 0
    assert "EN " in clip.with_name("Show - S01E01.en.srt").read_text(encoding="utf-8")


def test_write_puts_back_a_deleted_subtitle_file(setup):
    cfg, clip, _ = setup
    main(["run", str(clip), "--from", "ja", "--config", str(cfg)])
    en = clip.with_name("Show - S01E01.en.srt")
    en.unlink()
    assert main(["write", str(clip), "--config", str(cfg)]) == 0
    assert en.exists()


def test_write_can_add_ass_files(setup):
    cfg, clip, _ = setup
    main(["run", str(clip), "--from", "ja", "--config", str(cfg)])
    assert main(["write", str(clip), "--format", "ass", "--config", str(cfg)]) == 0
    assert clip.with_name("Show - S01E01.ja.ass").exists()


def test_models_lists_what_is_configured_and_usable(setup, capsys, monkeypatch):
    cfg, _, _ = setup
    monkeypatch.setattr(detecting, "candidates", lambda config, keys, **kw: [
        Candidate("fake", "whisper-large-v3-turbo", "endpoint", True),
        Candidate("gemma", "gemma-4-26b-a4b", "endpoint", False, "Spark not reachable")])
    assert main(["models", "--config", str(cfg), "--json"]) == 0
    rows = {e["name"]: e for e in map(json.loads, capsys.readouterr().out.splitlines())
            if e.get("event") == "model"}
    assert rows["fake"]["available"] and not rows["gemma"]["available"]
    assert rows["gemma"]["reason"] == "Spark not reachable"


def test_models_markdown_is_the_readme_table(capsys):
    assert main(["models", "--markdown"]) == 0
    assert capsys.readouterr().out == readme_table()


def test_translate_never_redoes_an_edited_track_without_replace_edited(setup):
    cfg, clip, calls = setup
    main(["run", str(clip), "--from", "ja", "--config", str(cfg)])
    en = clip.with_name("Show - S01E01.en.srt")
    text = en.read_text(encoding="utf-8")
    en.write_text(text.replace("EN ", "MY ", 1), encoding="utf-8")
    calls.clear()
    assert main(["translate", str(clip), "--to", "en", "--config", str(cfg)]) == 0
    assert calls == []
    assert "MY " in en.read_text(encoding="utf-8")


def test_translate_fresh_redoes_current_cues_but_stale_only_does_not(setup):
    cfg, clip, calls = setup
    main(["run", str(clip), "--from", "ja", "--config", str(cfg)])
    calls.clear()
    assert main(["translate", str(clip), "--to", "en", "--stale-only", "--config", str(cfg)]) == 0
    assert calls == []
    assert main(["translate", str(clip), "--to", "en", "--config", str(cfg)]) == 0
    assert len(calls) >= 1


def test_translate_and_write_json_events_carry_no_names(setup, capsys):
    cfg, clip, _ = setup
    main(["run", str(clip), "--from", "ja", "--config", str(cfg)])
    capsys.readouterr()
    assert main(["write", str(clip), "--config", str(cfg), "--json"]) == 0
    assert "Show" not in capsys.readouterr().out


def test_write_with_nothing_to_do_is_a_usage_error(setup):
    cfg, _, _ = setup
    assert main(["write", "--config", str(cfg)]) == 64

