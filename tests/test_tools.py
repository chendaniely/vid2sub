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
    v = t.version(t.Tools.find().need("ffmpeg"))
    assert v is not None and v >= (4,)


@pytest.mark.skipif(os.name == "nt", reason="the fake tool is a POSIX shell script")
def test_a_git_build_version_line_is_unknown_not_a_crash(tmp_path):
    fake = tmp_path / "ffmpeg"
    fake.write_text("#!/bin/sh\necho 'ffmpeg version N-117000-gabc123 Copyright (c) 2000-2026 "
                    "the FFmpeg developers'\n")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    assert t.version(str(fake)) is None


@pytest.mark.media
def test_real_wav_and_mkv_inputs_pass_the_format_whitelist(tmp_path):
    ffmpeg = t.Tools.find().need("ffmpeg")
    wav = tmp_path / "tone.wav"
    mkv = tmp_path / "clip.mkv"
    t.run_tool([ffmpeg, "-v", "error", "-f", "lavfi", "-i", "sine=duration=1", str(wav)],
               cwd=tmp_path, timeout=60)
    t.run_tool([ffmpeg, "-v", "error", "-f", "lavfi", "-i", "testsrc=duration=1:size=64x64:rate=10",
                "-f", "lavfi", "-i", "sine=duration=1", "-c:v", "ffv1", "-c:a", "flac", str(mkv)],
               cwd=tmp_path, timeout=60)
    ffprobe = t.Tools.find().need("ffprobe")
    for media in (wav, mkv):
        t.run_tool([ffprobe, "-v", "error", *t.input_args(media), "-show_format"],
                   cwd=tmp_path, timeout=60)


@pytest.mark.media
@pytest.mark.parametrize("suffix, codec_args", [
    ("mpg", ["-f", "mpeg"]),
    ("ac3", ["-c:a", "ac3", "-f", "ac3"]),
    ("eac3", ["-c:a", "eac3", "-f", "eac3"]),
    ("dts", ["-c:a", "dca", "-strict", "-2", "-f", "dts"]),
])
def test_dvd_and_dolby_inputs_pass_the_format_whitelist(tmp_path, suffix, codec_args):
    ffmpeg = t.Tools.find().need("ffmpeg")
    media = tmp_path / f"tone.{suffix}"
    t.run_tool([ffmpeg, "-v", "error", "-f", "lavfi", "-i", "sine=duration=1", *codec_args,
                str(media)], cwd=tmp_path, timeout=60)
    t.run_tool([t.Tools.find().need("ffprobe"), "-v", "error", *t.input_args(media),
                "-show_format"], cwd=tmp_path, timeout=60)


def test_exts_are_lower_case_without_empties_on_windows_and_blank_elsewhere():
    assert t._exts({"PATHEXT": ".COM;.EXE;;.BAT;"}, nt=True) == [".com", ".exe", ".bat"]
    assert t._exts({"PATHEXT": ".COM;.EXE"}, nt=False) == [""]


@pytest.mark.skipif(os.name != "nt", reason="PATHEXT only applies on Windows")
def test_which_accepts_a_name_that_already_ends_in_an_extension(tmp_path):
    exe = make_exe(tmp_path, "faketool")
    assert t.which("faketool.exe", path=str(tmp_path)) == str(exe)
