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


def test_a_word_before_the_first_segment_lands_in_it_and_the_segment_stays_aligned():
    data = {"language": "english", "segments": [{"start": 1.0, "end": 2.0, "text": " I saw a cat."}],
            "words": [{"word": "I", "start": 0.2, "end": 0.4}, {"word": "saw", "start": 1.1, "end": 1.3},
                      {"word": "a", "start": 1.4, "end": 1.5}, {"word": "cat", "start": 1.6, "end": 1.9}]}
    seg = parse_openai(data).segments[0]
    assert [w.text for w in seg.words] == [" I", " saw", " a", " cat."]
    assert seg.aligned and seg.text == " I saw a cat."


def test_a_word_in_the_gap_between_segments_goes_to_the_nearer_one():
    data = {"language": "english",
            "segments": [{"start": 0.0, "end": 1.0, "text": " Yes."},
                         {"start": 2.0, "end": 3.0, "text": " hmm no."}],
            "words": [{"word": "Yes", "start": 0.1, "end": 0.3},
                      {"word": "hmm", "start": 1.7, "end": 1.9},
                      {"word": "no", "start": 2.1, "end": 2.3}]}
    first, second = parse_openai(data).segments
    assert [w.text for w in first.words] == [" Yes."]
    assert [w.text for w in second.words] == [" hmm", " no."]
    assert second.aligned


def test_a_word_exactly_between_two_segments_goes_to_the_earlier_one():
    data = {"language": "english",
            "segments": [{"start": 0.0, "end": 1.0, "text": " Yes hmm."},
                         {"start": 2.0, "end": 3.0, "text": " No."}],
            "words": [{"word": "Yes", "start": 0.1, "end": 0.3},
                      {"word": "hmm", "start": 1.4, "end": 1.6},
                      {"word": "No", "start": 2.1, "end": 2.3}]}
    first, second = parse_openai(data).segments
    assert [w.text for w in first.words] == [" Yes", " hmm."]
    assert [w.text for w in second.words] == [" No."]


@pytest.mark.parametrize(("text", "words"), [
    (" 7 cats.", [("seven", 0.1, 0.5)]),
    (" I saw.", [("saw", 0.5, 0.7)]),
])
def test_a_segment_whose_words_do_not_spell_its_text_is_unaligned_with_its_text_intact(text, words):
    data = {"language": "english", "segments": [{"start": 0.0, "end": 1.0, "text": text}],
            "words": [{"word": w, "start": s, "end": e} for w, s, e in words]}
    seg = parse_openai(data).segments[0]
    assert seg.words == () and seg.text == text


def test_joining_an_aligned_openai_segments_words_gives_its_text():
    for seg in parse_openai(OPENAI).segments:
        assert seg.aligned
        assert "".join(w.text for w in seg.words) == seg.text


def test_an_unknown_or_missing_openai_language_gives_no_language_and_no_probabilities():
    for language in ("klingon", None):
        parsed = parse_openai({"language": language, "segments": []})
        assert parsed.language is None and parsed.language_probs == {}


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


def test_untimed_qwen_units_give_one_unaligned_segment_spanning_the_chunk():
    parsed = parse_qwen({"text": "Hello there.", "language": "English",
                         "segments": [{"text": "Hello"}, {"text": "there"}]}, duration_ms=1500)
    seg = parsed.segments[0]
    assert len(parsed.segments) == 1
    assert seg.words == () and seg.end_ms == 1500


def test_untimed_leading_qwen_units_start_at_the_first_timed_unit():
    parsed = parse_qwen({"text": "Hello there.", "language": "English",
                         "segments": [{"text": "Hello"}, {"text": "there", "start": 0.5, "end": 0.9}]},
                        duration_ms=1500)
    seg = parsed.segments[0]
    assert seg.aligned and seg.start_ms == 500
    assert seg.end_ms == 900


def test_empty_qwen_output_gives_no_segments():
    assert parse_qwen({"text": "", "language": "English", "segments": []},
                      duration_ms=1000).segments == ()
