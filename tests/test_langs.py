import pytest

from vid2sub.subs import langs


def test_the_four_languages_dan_needs_are_known_and_marked_cjk_correctly():
    assert {"en", "ja", "zh", "yue"} <= set(langs.LANGS)
    assert not langs.get("en").cjk
    assert langs.get("ja").cjk and langs.get("zh").cjk and langs.get("yue").cjk


def test_an_unknown_language_names_the_known_ones():
    with pytest.raises(langs.UnknownLanguage, match="known: en"):
        langs.get("xx")


def test_whisper_cpp_full_names_and_qwen_names_map_back_to_codes():
    assert langs.from_whisper_full("japanese") == "ja"
    assert langs.from_whisper_full("Cantonese") == "yue"
    assert langs.from_qwen("Chinese") == "zh"
    assert langs.from_qwen("Cantonese") == "yue"
    assert langs.from_qwen("Klingon") is None


def test_media_language_tags_map_to_codes():
    assert langs.from_media_tag("jpn") == "ja"
    assert langs.from_media_tag("chi") == "zh"
    assert langs.from_media_tag("ENG") == "en"
    assert langs.from_media_tag("und") is None
    assert langs.from_media_tag(None) is None
