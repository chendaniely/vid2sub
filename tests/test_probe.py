import pytest
from helpers import make_clip

from vid2sub.media.probe import ProbeError, parse_probe, pick_track, probe, timeline_offset_ms
from vid2sub.media.tools import Tools

DATA = {
    "format": {"duration": "1440.5", "format_name": "matroska,webm", "start_time": "0.000"},
    "streams": [
        {"index": 0, "codec_type": "video", "codec_name": "hevc", "start_time": "0.000"},
        {"index": 1, "codec_type": "audio", "codec_name": "aac", "channels": 2,
         "start_time": "0.250", "tags": {"language": "jpn"}, "disposition": {"default": 0}},
        {"index": 2, "codec_type": "audio", "codec_name": "ac3", "channels": 6,
         "start_time": "0.000", "tags": {"language": "eng"}, "disposition": {"default": 1}},
        {"index": 3, "codec_type": "video", "codec_name": "mjpeg",
         "disposition": {"attached_pic": 1}},
    ],
}


def test_a_probe_lists_audio_tracks_with_languages_and_skips_cover_art():
    p = parse_probe(DATA)
    assert p.duration_ms == 1_440_500 and p.video_codec == "hevc"
    assert [(t.index, t.stream_index, t.language, t.default) for t in p.audio] == [
        (0, 1, "ja", False), (1, 2, "en", True)]


def test_the_track_matching_the_language_wins_then_the_default():
    p = parse_probe(DATA)
    assert pick_track(p, "ja").index == 0
    assert pick_track(p, "zh").index == 1  # no Mandarin track: the default
    assert pick_track(p, None).index == 1
    assert pick_track(p, "ja", override=1).index == 1
    assert pick_track(p, None, override="ja").index == 0


def test_a_bad_override_says_what_exists():
    p = parse_probe(DATA)
    with pytest.raises(ProbeError, match="has 2"):
        pick_track(p, None, override=5)
    with pytest.raises(ProbeError, match="tagged ko"):
        pick_track(p, None, override="ko")


def test_an_audio_track_that_starts_late_gives_a_timeline_offset():
    p = parse_probe(DATA)
    assert timeline_offset_ms(p, p.audio[0]) == 250
    assert timeline_offset_ms(p, p.audio[1]) == 0


def test_a_file_without_audio_is_refused():
    data = {"format": {"duration": "10"}, "streams": [{"index": 0, "codec_type": "video"}]}
    with pytest.raises(ProbeError, match="no audio"):
        parse_probe(data)


@pytest.mark.media
def test_probing_a_real_clip_finds_its_tracks_languages_and_audio_delay(tmp_path):
    clip = make_clip(tmp_path, audio_delay=2.0, audio_langs=("jpn", "eng"), default_audio=1)
    p = probe(clip, Tools.find(), scratch=tmp_path)
    assert [t.language for t in p.audio] == ["ja", "en"]
    assert p.audio[1].default
    assert abs(timeline_offset_ms(p, p.audio[0]) - 2000) < 50
