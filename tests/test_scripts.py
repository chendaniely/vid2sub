from vid2sub.subs.model import Cue
from vid2sub.subs.scripts import config_for, convert, convert_cues


def test_tracks_map_to_opencc_configs():
    assert config_for("zh-Hant") == "s2tw"
    assert config_for("yue-Hant") == "s2hk"
    assert config_for("zh-Hans") == "t2s"
    assert config_for("en") is None


def test_conversions_go_both_ways_and_leave_latin_alone():
    assert convert("汉语", "s2tw") == "漢語"
    assert convert("漢語", "t2s") == "汉语"
    assert convert("头发", "s2hk") == "頭髮"
    assert convert("Hello", "s2tw") == "Hello"


def test_converting_cues_keeps_their_ids_and_times():
    cues = [Cue(id="c1", start_ms=0, end_ms=900, text="汉语\n学习", w=(0, 2))]
    out = convert_cues(cues, "s2tw")
    assert out[0].text == "漢語\n學習"
    assert (out[0].id, out[0].start_ms, out[0].w) == ("c1", 0, (0, 2))
