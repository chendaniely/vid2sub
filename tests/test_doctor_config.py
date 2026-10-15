import json
import sys

import pytest

from vid2sub import config as c
from vid2sub.cli import main
from vid2sub.commands import doctor
from vid2sub.media.tools import Tools


def test_config_init_prints_the_starter_and_writes_nothing(capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main(["config", "init"]) == 0
    assert capsys.readouterr().out == c.STARTER
    assert list(tmp_path.iterdir()) == []


def test_config_path_prints_where_vid2sub_looks(capsys, tmp_path):
    assert main(["config", "path", "--config", str(tmp_path / "x.toml")]) == 0
    assert capsys.readouterr().out.strip() == str(tmp_path / "x.toml")


def test_doctor_reports_keys_by_presence_only(tmp_path, monkeypatch, capsys):
    cfg = tmp_path / "vid2sub.toml"
    cfg.write_text(c.STARTER, encoding="utf-8")
    monkeypatch.setenv("SPARK_API_KEY", "supersecretvalue")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    main(["doctor", "--config", str(cfg), "--json", "--offline"])
    out = capsys.readouterr().out
    assert "supersecretvalue" not in out
    rows = {e["check"]: e for e in map(json.loads, out.splitlines())}
    assert rows["key SPARK_API_KEY"]["ok"] and not rows["key OPENAI_API_KEY"]["ok"]


def test_doctor_exits_69_without_ffmpeg(tmp_path, monkeypatch):
    monkeypatch.setattr(doctor.Tools, "find", classmethod(
        lambda cls: Tools(ffmpeg=None, ffprobe=None, deno=None)))
    assert main(["doctor", "--config", str(tmp_path / "none.toml"), "--offline"]) == 69


def test_doctor_exits_78_for_a_broken_config(tmp_path):
    cfg = tmp_path / "vid2sub.toml"
    cfg.write_text("[server]\ncolour = 1\n")
    assert main(["doctor", "--config", str(cfg), "--offline"]) == 78


@pytest.mark.skipif(sys.platform == "win32", reason="a POSIX shell script stands in for ffmpeg")
def test_doctor_accepts_an_ffmpeg_whose_version_cannot_be_read(tmp_path):
    fake = tmp_path / "ffmpeg"
    fake.write_text("#!/bin/sh\necho 'ffmpeg version N-117000-gabc123 Copyright (c) 2000-2026 "
                    "the FFmpeg developers'\n")
    fake.chmod(0o755)
    results, _ = doctor.checks(str(tmp_path / "none.toml"), environ={},
                               tools=Tools(ffmpeg=str(fake), ffprobe=str(fake), deno=None),
                               offline=True)
    ffmpeg = next(r for r in results if r.name == "ffmpeg")
    assert ffmpeg.ok
    assert ffmpeg.detail == "unknown version"
    assert ffmpeg.essential


def doctor_lines(capsys, tmp_path):
    main(["doctor", "--config", str(tmp_path / "none.toml"), "--offline"])
    return {line.split(":")[0][2:]: line for line in capsys.readouterr().out.splitlines()}


def test_a_passing_check_shows_no_fix_and_a_failing_one_does(tmp_path, monkeypatch, capsys):
    lines = doctor_lines(capsys, tmp_path)
    assert lines["python"].startswith("✓") and "→" not in lines["python"]
    assert "Python 3.12 or later" not in lines["python"]
    assert "config init" in lines["vid2sub.toml"]  # advice for a passing check stays
    monkeypatch.setattr(doctor.Tools, "find", classmethod(
        lambda cls: Tools(ffmpeg=None, ffprobe=None, deno=None)))
    lines = doctor_lines(capsys, tmp_path)
    assert lines["ffmpeg"].startswith("✗") and "→ install ffmpeg 6 or later" in lines["ffmpeg"]
