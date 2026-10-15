import errno
import json
import os
import stat
import subprocess
import sys

import pytest

from vid2sub.media import youtube as yt
from vid2sub.media.tools import ToolFailed, Tools

TOOLS = Tools(ffmpeg="/usr/bin/ffmpeg", ffprobe="/usr/bin/ffprobe", deno="/usr/bin/deno")


@pytest.mark.parametrize("url", [
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42",
    "https://youtu.be/dQw4w9WgXcQ?si=abc",
    "https://m.youtube.com/watch?v=dQw4w9WgXcQ",
    "https://music.youtube.com/watch?v=dQw4w9WgXcQ&list=RD",
    "https://www.youtube.com/shorts/dQw4w9WgXcQ",
])
def test_youtube_links_give_their_video_id(url):
    assert yt.video_id(url) == "dQw4w9WgXcQ"


def test_an_id_starting_with_a_dash_is_fine():
    assert yt.video_id("https://youtu.be/-abcdefghij") == "-abcdefghij"


@pytest.mark.parametrize("url", [
    "https://vimeo.com/123", "https://www.youtube.com/playlist?list=PL123",
    "file:///etc/passwd", "https://www.youtube.com/watch?v=short",
])
def test_anything_but_one_youtube_video_is_refused(url):
    with pytest.raises(yt.NotYouTube):
        yt.video_id(url)


def fake_runner(record, title="a/b: c?", ext="m4a"):
    def run(args, *, cwd, timeout, **_):
        record["args"] = args
        out = cwd / f"dQw4w9WgXcQ.{ext}"
        out.write_bytes(b"audio")
        line = json.dumps({"id": "dQw4w9WgXcQ", "title": title, "upload_date": "20091025",
                           "filepath": str(out)})
        return subprocess.CompletedProcess(args, 0, stdout=line.encode() + b"\n", stderr=b"")
    return run


def test_a_download_runs_yt_dlp_locked_down_and_names_the_file_safely(tmp_path):
    record = {}
    scratch, out_dir = tmp_path / "scratch", tmp_path / "out"
    scratch.mkdir()
    got = yt.download("https://youtu.be/dQw4w9WgXcQ", out_dir=out_dir, scratch=scratch,
                      keep_video=False, tools=TOOLS, runner=fake_runner(record))
    args = record["args"]
    for flag in ("--ignore-config", "--no-plugin-dirs", "--no-playlist"):
        assert flag in args
    assert args[args.index("--use-extractors") + 1] == "youtube"
    assert args[args.index("--js-runtimes") + 1] == "deno:/usr/bin/deno"
    assert args.index("--no-js-runtimes") < args.index("--js-runtimes")
    assert args[-2:] == ["--", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"]
    assert args[args.index("-f") + 1] == "bestaudio/best"
    assert got.path == out_dir / "a_b_ c_ [dQw4w9WgXcQ].m4a"
    assert got.published == "20091025" and got.path.read_bytes() == b"audio"


def test_keep_video_asks_for_video_and_audio(tmp_path):
    record = {}
    (tmp_path / "s").mkdir()
    yt.download("https://youtu.be/dQw4w9WgXcQ", out_dir=tmp_path / "o", scratch=tmp_path / "s",
                keep_video=True, tools=TOOLS, runner=fake_runner(record, ext="mkv"))
    assert record["args"][record["args"].index("-f") + 1] == "bv*+ba/b"


def test_an_existing_download_is_reused(tmp_path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    existing = out_dir / "Old title [dQw4w9WgXcQ].m4a"
    existing.write_bytes(b"x")
    got = yt.download("https://youtu.be/dQw4w9WgXcQ", out_dir=out_dir, scratch=tmp_path,
                      keep_video=False, tools=TOOLS,
                      runner=lambda *a, **k: pytest.fail("should not download"))
    assert got.path == existing and got.title == "Old title"


def test_a_bot_check_says_to_upgrade_yt_dlp(tmp_path):
    def blocked(args, **_):
        raise ToolFailed("python", 1, "ERROR: Sign in to confirm you're not a bot")
    (tmp_path / "s").mkdir()
    with pytest.raises(yt.YouTubeError) as err:
        yt.download("https://youtu.be/dQw4w9WgXcQ", out_dir=tmp_path / "o",
                    scratch=tmp_path / "s", keep_video=False, tools=TOOLS, runner=blocked)
    assert err.value.kind == "bot_check" and "upgrade yt-dlp" in err.value.hint


def test_deno_is_required(tmp_path):
    from vid2sub.media.tools import ToolMissing
    with pytest.raises(ToolMissing):
        yt.download("https://youtu.be/dQw4w9WgXcQ", out_dir=tmp_path, scratch=tmp_path,
                    keep_video=False, tools=Tools(ffmpeg=None, ffprobe=None, deno=None))


def test_a_sign_in_wall_is_not_called_a_bot_check(tmp_path):
    def gated(args, **_):
        raise ToolFailed("python", 1, "ERROR: Sign in to confirm your age")
    (tmp_path / "s").mkdir()
    with pytest.raises(yt.YouTubeError) as err:
        yt.download("https://youtu.be/dQw4w9WgXcQ", out_dir=tmp_path / "o",
                    scratch=tmp_path / "s", keep_video=False, tools=TOOLS, runner=gated)
    assert err.value.kind == "sign_in"
    assert str(err.value) == "YouTube wants a signed-in account for this video"
    assert err.value.hint == "vid2sub can't download videos that need an account"


def test_a_bot_check_wins_over_a_sign_in_wording(tmp_path):
    def blocked(args, **_):
        raise ToolFailed("python", 1, "Sign in to confirm you're not a bot")
    (tmp_path / "s").mkdir()
    with pytest.raises(yt.YouTubeError) as err:
        yt.download("https://youtu.be/dQw4w9WgXcQ", out_dir=tmp_path / "o",
                    scratch=tmp_path / "s", keep_video=False, tools=TOOLS, runner=blocked)
    assert err.value.kind == "bot_check"


def test_a_partial_or_sidecar_file_is_not_reused(tmp_path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "x [dQw4w9WgXcQ].part").write_bytes(b"x")
    (out_dir / "x [dQw4w9WgXcQ].json").write_bytes(b"{}")
    assert yt.find_existing(out_dir, "dQw4w9WgXcQ") is None
    media = out_dir / "x [dQw4w9WgXcQ].m4a"
    media.write_bytes(b"audio")
    assert yt.find_existing(out_dir, "dQw4w9WgXcQ") == media


@pytest.mark.parametrize("stdout", [b"", b"not json\n", b'{"id": "dQw4w9WgXcQ"}\n'],
                         ids=["empty", "not-json", "no-filepath"])
def test_unreadable_yt_dlp_output_is_a_youtube_error(tmp_path, stdout):
    (tmp_path / "s").mkdir()

    def answer(args, **_):
        return subprocess.CompletedProcess(args, 0, stdout=stdout, stderr=b"")
    with pytest.raises(yt.YouTubeError) as err:
        yt.download("https://youtu.be/dQw4w9WgXcQ", out_dir=tmp_path / "o",
                    scratch=tmp_path / "s", keep_video=False, tools=TOOLS, runner=answer)
    assert err.value.kind == "failed"
    assert str(err.value) == "yt-dlp's answer couldn't be read"


def test_a_move_never_replaces_an_existing_file(tmp_path):
    src = tmp_path / "src.m4a"
    src.write_bytes(b"new")
    dest = tmp_path / "dest.m4a"
    dest.write_bytes(b"old")
    with pytest.raises(yt.YouTubeError) as err:
        yt._move_new(src, dest)
    assert dest.read_bytes() == b"old"
    assert err.value.kind == "failed"
    assert str(err.value) == "a file with that name appeared while downloading; try again"


def test_the_move_falls_back_to_a_copy_across_devices(tmp_path, monkeypatch):
    real_link = os.link
    calls = []

    def cross_device_once(a, b, *args, **kwargs):
        calls.append(a)
        if len(calls) == 1:
            raise OSError(errno.EXDEV, "cross-device")
        return real_link(a, b, *args, **kwargs)
    monkeypatch.setattr(yt.os, "link", cross_device_once)
    src = tmp_path / "src.m4a"
    src.write_bytes(b"audio")
    dest = tmp_path / "dest.m4a"
    yt._move_new(src, dest)
    assert dest.read_bytes() == b"audio" and not src.exists()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["dest.m4a"]


def test_the_move_renames_when_hard_links_are_refused(tmp_path, monkeypatch):
    def no_links(a, b, *args, **kwargs):
        raise OSError(errno.EPERM, "operation not permitted")
    monkeypatch.setattr(yt.os, "link", no_links)
    src = tmp_path / "src.m4a"
    src.write_bytes(b"audio")
    dest = tmp_path / "dest.m4a"
    yt._move_new(src, dest)
    assert dest.read_bytes() == b"audio" and not src.exists()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["dest.m4a"]


@pytest.mark.live
@pytest.mark.skipif(not os.environ.get("VID2SUB_LIVE_YOUTUBE_URL"),
                    reason="set VID2SUB_LIVE_YOUTUBE_URL to a short public-domain video")
def test_a_real_video_downloads_as_audio(tmp_path):
    (tmp_path / "s").mkdir()
    got = yt.download(os.environ["VID2SUB_LIVE_YOUTUBE_URL"], out_dir=tmp_path / "o",
                      scratch=tmp_path / "s", keep_video=False, tools=Tools.find())
    assert got.path.exists() and got.path.stat().st_size > 10_000


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes")
@pytest.mark.parametrize("link_error", [errno.EXDEV, errno.EPERM])
def test_a_copied_download_keeps_the_source_files_mode(tmp_path, monkeypatch, link_error):
    real_link = os.link
    calls = []

    def refuse_first(a, b, *args, **kwargs):
        calls.append(a)
        if len(calls) == 1 or link_error == errno.EPERM:
            raise OSError(link_error, "no link")
        return real_link(a, b, *args, **kwargs)
    monkeypatch.setattr(yt.os, "link", refuse_first)
    src = tmp_path / "src.m4a"
    src.write_bytes(b"audio")
    src.chmod(0o644)
    dest = tmp_path / "dest.m4a"
    yt._move_new(src, dest)
    assert stat.S_IMODE(dest.stat().st_mode) == 0o644
