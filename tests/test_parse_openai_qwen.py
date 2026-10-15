import pytest

from vid2sub.parse import ParseError
from vid2sub.parse.openai import parse_openai
from vid2sub.parse.qwen import parse_qwen

OPENAI = {
    "language": "english", "duration": 4.0, "text": "Hello, world. Bye.",
    "segments": [{"start": 0.0, "end": 2.0, "text": " Hello, world.", "avg_logprob": -0.1,
                  "compression_ratio": 1.2, "no_speech_prob": 0.0},
                 {"start": 2.0, "end": 4.0, "text": " Bye.", "avg_logprob": -0.3,
                  "compression_ratio": 1.0, "no_speech_prob": 0.0}],
    "words": [{"word": "Hello", "start": 0.1, "end": 0.5}, {"word": "world", "start": 0.6, "end": 1.0},
              {"word": "Bye", "start": 2.2, "end": 2.6}],
}


def test_openai_words_are_assigned_to_segments_with_the_texts_punctuation():
    parsed = parse_openai(OPENAI)
    assert parsed.language == "en"
    assert [w.text for w in parsed.segments[0].words] == [" Hello,", " world."]
    assert [w.text for w in parsed.segments[1].words] == [" Bye."]
    assert parsed.segments[0].compression_ratio == 1.2


def test_an_openai_response_without_segments_is_refused():
    with pytest.raises(ParseError):
        parse_openai({"text": "hi"})


def test_an_openai_segment_that_is_not_an_object_is_refused():
    with pytest.raises(ParseError):
        parse_openai({"segments": ["x"]})


def test_qwen_units_get_the_texts_punctuation_and_the_language_code():
    parsed = parse_qwen({"text": "你好，世界。", "language": "Chinese",
                         "segments": [{"text": "你", "start": 0.0, "end": 0.2},
                                      {"text": "好", "start": 0.2, "end": 0.4},
                                      {"text": "世", "start": 0.6, "end": 0.8},
                                      {"text": "界", "start": 0.8, "end": 1.0}]}, duration_ms=1500)
    assert parsed.language == "zh"
    seg = parsed.segments[0]
    assert [w.text for w in seg.words] == ["你", "好，", "世", "界。"]
    assert (seg.start_ms, seg.end_ms) == (0, 1000)


def test_qwen_text_that_doesnt_match_its_units_becomes_one_unaligned_segment():
    parsed = parse_qwen({"text": "abc", "language": "English",
                         "segments": [{"text": "zzz", "start": 0, "end": 1}]}, duration_ms=1500)
    assert parsed.segments[0].words == () and parsed.segments[0].end_ms == 1500


def test_empty_qwen_output_gives_no_segments():
    assert parse_qwen({"text": "", "language": "English", "segments": []},
                      duration_ms=1000).segments == ()
