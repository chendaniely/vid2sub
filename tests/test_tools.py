import os
import stat
import sys

import pytest

from vid2sub.media import tools as t


def make_exe(directory, name):
    path = directory / (name + (".exe" if os.name == "nt" else ""))
    path.write_bytes(b"#!/bin/sh\nexit 0\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


def test_which_finds_absolute_path_entries_and_ignores_relative_ones(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    exe = make_exe(bin_dir, "faketool")
    monkeypatch.chdir(bin_dir)
    assert t.which("faketool", path=os.pathsep.join([".", "bin"])) is None
    assert t.which("faketool", path=str(bin_dir)) == str(exe)


def test_run_tool_refuses_a_relative_executable(tmp_path):
    with pytest.raises(ValueError, match="absolute"):
        t.run_tool(["ffmpeg", "-version"], cwd=tmp_path, timeout=5)


def test_child_processes_see_no_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "should-not-leak")
    proc = t.run_tool([sys.executable, "-c",
                       "import os; print('OPENAI_API_KEY' in os.environ)"], cwd=tmp_path,
                      timeout=30)
    assert proc.stdout.strip() == b"False"


def test_a_failing_tool_raises_with_its_stderr(tmp_path):
    with pytest.raises(t.ToolFailed) as err:
        t.run_tool([sys.executable, "-c", "import sys; sys.stderr.write('bad'); sys.exit(3)"],
                   cwd=tmp_path, timeout=30)
    assert err.value.returncode == 3 and "bad" in err.value.stderr


def test_a_missing_tool_says_how_to_install_it():
    tools = t.Tools(ffmpeg=None, ffprobe=None, deno=None)
    with pytest.raises(t.ToolMissing) as err:
        tools.need("deno")
    assert "deno" in err.value.hint


@pytest.mark.media
def test_a_playlist_disguised_as_mp4_is_refused_before_it_can_fetch_anything(tmp_path):
    """Documents ffmpeg's own behaviour, not vid2sub's code: ffmpeg >= 6 refuses to probe HLS
    under a non-standard extension, so this does not guard the whitelist (see the test below)."""
    evil = tmp_path / "evil.mp4"
    evil.write_text("#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:1\n#EXTINF:1.0,\n"
                    "http://127.0.0.1:9/seg.ts\n#EXT-X-ENDLIST\n")
    tools = t.Tools.find()
    with pytest.raises(t.ToolFailed):
        t.run_tool([tools.need("ffprobe"), "-v", "error", *t.input_args(evil), "-show_format"],
                   cwd=tmp_path, timeout=30)


@pytest.mark.media
def test_a_local_playlist_is_refused_by_the_format_whitelist(tmp_path):
    playlist = tmp_path / "playlist.m3u8"
    playlist.write_text("#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:1\n#EXTINF:1.0,\n"
                        "http://127.0.0.1:9/seg.ts\n#EXT-X-ENDLIST\n")
    tools = t.Tools.find()
    with pytest.raises(t.ToolFailed) as err:
        t.run_tool([tools.need("ffprobe"), "-v", "error", *t.input_args(playlist), "-show_format"],
                   cwd=tmp_path, timeout=30)
    assert "Format not on whitelist" in err.value.stderr


@pytest.mark.media
def test_ffmpeg_reports_a_version():
    assert t.version(t.Tools.find().need("ffmpeg")) >= (4,)
