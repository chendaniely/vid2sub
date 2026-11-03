import json
import os
import subprocess

import numpy as np
import pytest
from helpers import make_clip

from vid2sub.cache import Cache
from vid2sub.media import preview
from vid2sub.media.tools import ToolFailed, Tools

pytestmark = pytest.mark.media
KEY = "a" * 64


def ffprobe(tools: Tools, path) -> dict:
    return json.loads(subprocess.run(
        [tools.ffprobe, "-v", "error", "-show_format", "-show_streams", "-show_chapters",
         "-of", "json", str(path)], capture_output=True, check=True).stdout)


def loudest_hz(tools: Tools, path) -> float:
    pcm = subprocess.run([tools.ffmpeg, "-v", "error", "-i", str(path), "-ac", "1", "-ar",
                          "16000", "-f", "s16le", "-"], capture_output=True, check=True).stdout
    samples = np.frombuffer(pcm, dtype="<i2").astype(np.float64)
    spectrum = np.abs(np.fft.rfft(samples))
    return float(np.fft.rfftfreq(len(samples), 1 / 16_000)[spectrum.argmax()])


@pytest.fixture
def clip(tmp_path):
    """Two AC-3 tracks (440 Hz, then 550 Hz), a title on the file and its tracks, a chapter."""
    return make_clip(tmp_path, "Show - S01E01.mkv", seconds=2.0, audio_langs=("jpn", "eng"),
                     audio_codec="ac3", title="Secret Show Title", chapter="Secret Chapter")


@pytest.fixture
def cache(tmp_path) -> Cache:
    return Cache(tmp_path / "cache", max_bytes=10**9)


def make(clip, cache, audio_index=0):
    return preview.playback_audio(clip, key=KEY, audio_index=audio_index, tools=Tools.find(),
                                  cache=cache, timeout=60)


def test_an_ac3_track_becomes_aac_stereo_in_mp4_with_no_title_or_chapters(clip, cache):
    tools = Tools.find()
    assert [s["codec_name"] for s in ffprobe(tools, clip)["streams"][1:]] == ["ac3", "ac3"]
    out = make(clip, cache)
    assert out == cache.root / KEY / "playback-a0.m4a"
    info = ffprobe(tools, out)
    assert "mp4" in info["format"]["format_name"].split(",")
    (stream,) = info["streams"]
    assert (stream["codec_type"], stream["codec_name"], stream["channels"]) == ("audio", "aac", 2)
    assert "Secret" not in json.dumps(info)
    assert "title" not in (info["format"].get("tags") or {})
    assert info["chapters"] == []
    assert [p.name for p in out.parent.iterdir()] == ["playback-a0.m4a"]


def test_the_chosen_audio_track_is_the_one_converted(clip, cache):
    tools = Tools.find()
    assert abs(loudest_hz(tools, make(clip, cache, 0)) - 440) < 5
    second = make(clip, cache, 1)
    assert second.name == "playback-a1.m4a"
    assert abs(loudest_hz(tools, second) - 550) < 5


def test_the_playback_audio_is_made_once_and_then_reused(clip, cache, monkeypatch):
    calls = []
    real = preview.run_tool
    monkeypatch.setattr(preview, "run_tool", lambda *a, **kw: calls.append(a) or real(*a, **kw))
    first = make(clip, cache)
    made = first.stat().st_mtime_ns
    os.utime(cache.root / KEY, (1_000, 1_000))
    second = make(clip, cache)
    assert second == first and len(calls) == 1
    assert second.stat().st_mtime_ns == made
    assert (cache.root / KEY).stat().st_mtime > 1_000  # reusing it marks the entry used


def test_making_one_evicts_older_entries_but_never_its_own(clip, tmp_path):
    cache = Cache(tmp_path / "cache", max_bytes=1)
    old = cache.folder("b" * 64)
    (old / "playback-a0.m4a").write_bytes(b"x" * 1000)
    os.utime(old, (1_000, 1_000))
    out = make(clip, cache)
    assert out.is_file() and not old.exists()


def test_a_file_ffmpeg_cannot_read_leaves_nothing_in_the_cache(tmp_path, cache):
    bad = tmp_path / "Show - S01E02.mkv"
    bad.write_bytes(b"not a video")
    with pytest.raises(ToolFailed):
        make(bad, cache)
    assert list((cache.root / KEY).iterdir()) == []


def test_a_negative_track_index_is_refused(clip, cache):
    with pytest.raises(ValueError, match="audio track"):
        make(clip, cache, -1)
