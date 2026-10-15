from vid2sub.subs import text as t


def test_wide_characters_count_two_and_latin_counts_one():
    assert t.width("abc") == 3
    assert t.width("日本") == 4
    assert t.width("Hi，") == 4  # a full-width comma is wide


def test_canonical_text_uses_lf_and_has_no_blank_or_padded_lines():
    assert t.canonical("  a  b \r\n\r\n c ") == "a b\nc"


def test_unwrap_joins_latin_lines_with_a_space_and_cjk_lines_with_nothing():
    assert t.unwrap("Hello\nworld") == "Hello world"
    assert t.unwrap("日本\n語") == "日本語"


def test_short_text_stays_on_one_line():
    assert t.wrap("Hello there", 42) == ["Hello there"]


def test_english_wraps_into_two_balanced_lines_within_the_width():
    lines = t.wrap("We choose to go to the moon in this decade and do the other things", 42)
    assert lines is not None and len(lines) == 2
    assert all(t.width(line) <= 42 for line in lines)
    assert abs(t.width(lines[0]) - t.width(lines[1])) <= 12


def test_japanese_wraps_between_characters_without_breaking_kinsoku():
    text = "今日はいい天気ですね。明日も晴れるといいな。"
    lines = t.wrap(text, 26)
    assert lines is not None and len(lines) == 2
    assert all(t.width(line) <= 26 for line in lines)
    assert lines[1][0] not in t.NO_LINE_START
    assert "".join(lines) == text


def test_a_latin_word_inside_cjk_text_is_never_split():
    text = "我哋聽日一齊去 shopping 啦，好唔好呀？"
    lines = t.wrap(text, 26)
    assert lines is not None
    assert len(lines) == 2
    assert not any(line.endswith("shop") or line.startswith("ping") for line in lines)
    assert any("shopping" in line for line in lines)
    assert "".join(lines).replace(" ", "") == text.replace(" ", "")


def test_text_that_cannot_fit_in_two_lines_returns_none():
    assert t.wrap("x" * 100, 42) is None


def test_chinese_line_ends_lose_their_comma_and_full_stop():
    assert t.strip_line_ends(["你好，", "世界。"]) == ["你好", "世界"]


def test_canonical_stores_ass_markup_characters_full_width():
    assert t.canonical("{x} a\\Nb") == "｛x｝ a＼Nb"
