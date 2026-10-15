import json
import os
import subprocess

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


@pytest.mark.live
@pytest.mark.skipif(not os.environ.get("VID2SUB_LIVE_YOUTUBE_URL"),
                    reason="set VID2SUB_LIVE_YOUTUBE_URL to a short public-domain video")
def test_a_real_video_downloads_as_audio(tmp_path):
    (tmp_path / "s").mkdir()
    got = yt.download(os.environ["VID2SUB_LIVE_YOUTUBE_URL"], out_dir=tmp_path / "o",
                      scratch=tmp_path / "s", keep_video=False, tools=Tools.find())
    assert got.path.exists() and got.path.stat().st_size > 10_000
