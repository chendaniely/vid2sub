import pytest

from vid2sub.subs import formats as f
from vid2sub.subs.model import Cue
from vid2sub.subs.text import canonical

CUES = [Cue(id="a", start_ms=1000, end_ms=2500, text="Hello\nworld"),
        Cue(id="b", start_ms=3000, end_ms=4000, text="<i>Bye</i>")]


def test_srt_bytes_use_lf_and_utf8_and_are_stable():
    data = f.to_srt(CUES)
    text = data.decode("utf-8")
    assert "\r" not in text
    assert text.startswith("1\n00:00:01,000 --> 00:00:02,500\nHello\nworld\n")
    assert "<i>Bye</i>" in text
    assert f.sha256_hex(data) == f.sha256_hex(f.to_srt(CUES))


def test_a_bom_is_added_only_when_asked():
    assert f.to_srt(CUES, bom=True).startswith(b"\xef\xbb\xbf")
    assert not f.to_srt(CUES).startswith(b"\xef\xbb\xbf")


def test_srt_round_trips_text_italics_and_times():
    parsed = f.parse_subtitles(f.to_srt(CUES), "srt")
    assert [(p.start_ms, p.end_ms, p.text) for p in parsed] == [
        (1000, 2500, "Hello\nworld"), (3000, 4000, "<i>Bye</i>")]


def test_ass_round_trips_at_centisecond_precision():
    cues = [Cue(id="a", start_ms=1234, end_ms=2567, text="One\ntwo")]
    parsed = f.parse_subtitles(f.to_ass(cues), "ass")
    assert parsed[0].text == "One\ntwo"
    assert f.same_cues(parsed, cues, precision_ms=f.PRECISION_MS["ass"])
    assert not f.same_cues(parsed, cues, precision_ms=1)


def test_braces_in_text_cant_become_ass_override_tags():
    data = f.to_ass([Cue(id="a", start_ms=0, end_ms=1000, text=canonical("{not a tag}"))]).decode()
    assert "{not a tag}" not in data
    assert "｛not a tag｝" in data


EXISTING_ASS = """[Script Info]
Title: My show
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 720

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,48,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1
Style: Sign,Arial,40,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,8,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,Hello
Dialogue: 0,0:00:05.00,0:00:06.00,Sign,,0,0,0,,A sign
"""


def test_rewriting_an_ass_file_keeps_its_styles_info_and_other_events():
    out = f.to_ass([Cue(id="a", start_ms=1000, end_ms=2000, text="New")],
                   existing=EXISTING_ASS.encode()).decode()
    assert "Title: My show" in out and "PlayResX: 1280" in out
    assert "Style: Sign" in out and "A sign" in out
    assert "New" in out and "Hello" not in out


def test_foreign_markup_is_stripped_on_import():
    srt = "1\n00:00:01,000 --> 00:00:02,000\n<font color=\"red\">Red</font> {\\an8}top\n\n"
    assert f.parse_subtitles(srt.encode(), "srt")[0].text == "Red top"


@pytest.mark.parametrize("encoding, line", [
    ("gbk", "今天天气很好，我们一起去公园散步吧。"),
    ("big5", "今天天氣很好，我們一起去公園散步吧。"),
    ("shift_jis", "今日はとても良い天気なので、公園を散歩しましょう。"),
])
def test_legacy_east_asian_encodings_are_detected(encoding, line):
    body = "".join(f"{i}\n00:00:0{i},000 --> 00:00:0{i},900\n{line}\n\n" for i in range(1, 6))
    parsed = f.parse_subtitles(body.encode(encoding), "srt")
    assert parsed[0].text == line


def test_an_unreadable_file_raises_a_subtitle_error():
    with pytest.raises(f.SubtitleError):
        f.parse_subtitles(b"\x00\x01\x02 not subtitles", "ass")


@pytest.mark.parametrize("fmt, write", [("srt", f.to_srt), ("ass", f.to_ass)])
def test_text_with_braces_and_backslashes_round_trips_exactly(fmt, write):
    cue = Cue(id="a", start_ms=1000, end_ms=2000, text=canonical("{x} a\\Nb"))
    parsed = f.parse_subtitles(write([cue]), fmt)
    assert f.same_cues(parsed, [cue], precision_ms=f.PRECISION_MS[fmt])


@pytest.mark.parametrize("raw, expected", [
    (r"{\i1}a{\i}b", "<i>a</i>b"),
    (r"{\an8\i1}x{\i0}", "<i>x</i>"),
    (r"{\i1}x", "<i>x</i>"),
    (r"a{\i0}b", "ab"),
])
def test_imported_italics_stay_balanced(raw, expected):
    assert f.ass_to_canonical(raw) == expected


def test_raw_braces_that_skipped_canonical_cant_reach_ass_as_tags():
    data = f.to_ass([Cue(id="a", start_ms=0, end_ms=1000, text="{raw}")]).decode()
    assert "{raw}" not in data
    assert "｛raw｝" in data


def test_only_default_style_events_are_read_when_asked():
    ass = f.to_ass([Cue(id="a", start_ms=0, end_ms=1000, text="line")]).decode("utf-8")
    ass += "Dialogue: 0,0:00:00.50,0:00:01.20,Sign,,0,0,0,,STATION\n"
    data = ass.encode("utf-8")
    assert [c.text for c in f.parse_subtitles(data, "ass")] == ["line", "STATION"]
    assert [c.text for c in f.parse_subtitles(data, "ass", default_style_only=True)] == ["line"]
