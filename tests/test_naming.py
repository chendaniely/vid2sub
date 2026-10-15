import pytest

from vid2sub.subs import naming as n


def test_file_codes_follow_the_spec_table():
    assert n.track("en").file_code == "en"
    assert n.track("zh-Hans").file_code == "zh-CN"
    assert n.track("zh-Hant").file_code == "zh-TW"
    assert n.track("yue-Hant").file_code == "zh-HK"


def test_subtitle_and_sidecar_names_sit_next_to_the_video():
    assert n.subtitle_name("Show - S01E02.mkv", "yue-Hant", "srt") == "Show - S01E02.zh-HK.srt"
    assert n.subtitle_name("Show.mkv", "en", "ass", sdh=True) == "Show.en.sdh.ass"
    assert n.sidecar_name("Show - S01E02.mkv") == "Show - S01E02.vid2sub.jsonl"


def test_source_tracks_follow_language_and_script():
    assert n.source_track("zh", None) == "zh-Hans"
    assert n.source_track("zh", "hant") == "zh-Hant"
    assert n.source_track("yue", None) == "yue-Hant"
    assert n.source_track("ja", None) == "ja"
    with pytest.raises(n.UnknownTrack, match="Traditional only"):
        n.source_track("yue", "hans")


def test_targets_accept_short_aliases():
    assert n.target_track("en") == "en"
    assert n.target_track("zh") == "zh-Hans"
    assert n.target_track("ZH-hant") == "zh-Hant"
    assert n.target_track("yue") == "yue-Hant"
    with pytest.raises(n.UnknownTrack):
        n.target_track("xx")


def test_an_existing_subtitle_names_its_track():
    assert n.track_from_subtitle_name("Show.mkv", "Show.zh-HK.srt") == "yue-Hant"
    assert n.track_from_subtitle_name("Show.mkv", "Show.en.srt") == "en"
    assert n.track_from_subtitle_name("Show.mkv", "Show.jpn.ass") == "ja"
    assert n.track_from_subtitle_name("Show.mkv", "Other.en.srt") is None
