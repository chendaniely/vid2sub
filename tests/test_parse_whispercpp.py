import pytest

from vid2sub.parse import ParseError
from vid2sub.parse.whispercpp import parse_whispercpp


def word(text, start, end, dtw=-1, p=0.9):
    return {"word": text, "start": start, "end": end, "t_dtw": dtw, "probability": p}


EN = {"task": "transcribe", "language": "english", "duration": 3.0, "text": " Hello, world.",
      "segments": [{"id": 0, "text": " Hello, world.", "start": 0.0, "end": 2.0,
                    "avg_logprob": -0.2, "no_speech_prob": 0.01,
                    "words": [word(" Hel", 0.0, 0.2), word("lo", 0.2, 0.4), word(",", 0.4, 0.42),
                              word(" world", 0.5, 0.9), word(".", 0.9, 0.95)]}],
      "language_probabilities": {"en": 0.98, "de": 0.01}}


def test_a_verbose_json_response_becomes_segments_of_words_in_milliseconds():
    parsed = parse_whispercpp(EN)
    assert parsed.language == "en"
    assert parsed.language_probs["en"] == 0.98
    seg = parsed.segments[0]
    assert [w.text for w in seg.words] == [" Hello,", " world."]
    assert seg.text == " Hello, world." and seg.end_ms == 2000
    assert seg.avg_logprob == -0.2


def test_dtw_times_are_used_when_the_server_sends_them():
    data = {"language": "japanese", "segments": [{"text": "こんにちは", "start": 0.0, "end": 1.0,
            "words": [word("こん", 0.0, 0.5, dtw=12), word("にちは", 0.5, 1.0, dtw=55)]}]}
    seg = parse_whispercpp(data).segments[0]
    assert [(w.start_ms, w.end_ms) for w in seg.words] == [(120, 550), (550, 1000)]


def test_a_broken_utf8_token_makes_the_segment_unaligned():
    data = {"language": "chinese", "segments": [{"text": "你好", "start": 0.0, "end": 1.0,
            "words": [word("�", 0.0, 0.5), word("好", 0.5, 1.0)]}]}
    seg = parse_whispercpp(data).segments[0]
    assert seg.words == () and seg.text == "你好"


def test_cantonese_is_recognised_by_its_full_name():
    assert parse_whispercpp({"language": "cantonese", "segments": []}).language == "yue"


def test_something_that_isnt_verbose_json_is_refused():
    with pytest.raises(ParseError):
        parse_whispercpp({"text": "plain"})


def dtw_segment(words, end=1.0):
    return {"language": "japanese", "segments": [{"text": "こんにちは", "start": 0.0, "end": end,
            "words": words}]}


def test_decreasing_dtw_times_fall_back_to_the_token_times():
    data = dtw_segment([word("こん", 0.0, 0.5, dtw=50), word("にちは", 0.5, 1.0, dtw=40)])
    seg = parse_whispercpp(data).segments[0]
    assert [(w.start_ms, w.end_ms) for w in seg.words] == [(0, 500), (500, 1000)]


def test_a_dtw_time_past_the_segment_end_falls_back_to_the_token_times():
    data = dtw_segment([word("こん", 0.0, 0.5, dtw=0), word("にちは", 0.5, 1.0, dtw=150)])
    seg = parse_whispercpp(data).segments[0]
    assert [(w.start_ms, w.end_ms) for w in seg.words] == [(0, 500), (500, 1000)]


def test_a_segment_that_is_not_an_object_is_refused():
    with pytest.raises(ParseError):
        parse_whispercpp({"segments": ["oops"]})


def test_a_language_probability_that_is_not_a_number_is_refused():
    with pytest.raises(ParseError):
        parse_whispercpp({"segments": [], "language_probabilities": {"en": "high"}})
