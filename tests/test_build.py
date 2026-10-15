from itertools import pairwise

from hypothesis import given, settings
from hypothesis import strategies as st

from vid2sub.subs.build import build_cues
from vid2sub.subs.model import Segment, Transcript, Word, check_track
from vid2sub.subs.rules import rules_for
from vid2sub.subs.text import width


def words(texts, start=0, step=400, dur=350):
    return tuple(Word(text=t, start_ms=start + i * step, end_ms=start + i * step + dur)
                 for i, t in enumerate(texts))


def seg(ws, **kw):
    return Segment(text="".join(w.text for w in ws), start_ms=ws[0].start_ms,
                   end_ms=ws[-1].end_ms, words=ws, **kw)


def transcript(lang, *segments):
    return Transcript(language=lang, segments=segments)


def test_a_short_english_sentence_becomes_one_cue_covering_every_word():
    ws = words([" We", " choose", " to", " go", " to", " the", " moon."])
    cues = build_cues(transcript("en", seg(ws)), rules_for("en"))
    assert [c.text for c in cues] == ["We choose to go to the moon."]
    assert cues[0].w == (0, 7)
    assert cues[0].start_ms == 0


def test_a_long_pause_starts_a_new_cue():
    first = words([" Hello", " there."])
    second = words([" How", " are", " you?"], start=3000)
    cues = build_cues(transcript("en", seg(first + second)), rules_for("en"))
    assert [c.text for c in cues] == ["Hello there.", "How are you?"]


def test_a_long_run_of_speech_is_split_into_cues_that_fit():
    ws = words([" word"] * 80, step=450)
    cues = build_cues(transcript("en", seg(ws)), rules_for("en"))
    check_track(cues)
    assert len(cues) > 3
    for c in cues:
        assert all(width(line) <= 42 for line in c.text.split("\n"))
        assert c.end_ms - c.start_ms <= 7000


def test_japanese_words_join_without_spaces_and_wrap_within_26():
    text = "今日はいい天気ですね明日も晴れるといいなと思っていますよ"
    ws = words(list(text), step=200, dur=180)
    cues = build_cues(transcript("ja", seg(ws)), rules_for("ja"))
    check_track(cues)
    assert " " not in "".join(c.text for c in cues)
    assert all(width(line) <= 26 for c in cues for line in c.text.split("\n"))


def test_chinese_lines_drop_a_trailing_comma_or_full_stop():
    ws = words(["你", "好", "，", "世", "界", "。"], step=300)
    cues = build_cues(transcript("zh", seg(ws)), rules_for("zh"))
    assert not any(line.endswith(("，", "。")) for c in cues for line in c.text.split("\n"))


def test_an_unaligned_segment_is_spread_over_its_time_and_flagged_estimated():
    s = Segment(text="This segment lost its word timings because of a temperature fallback "
                     "and has to be estimated from the segment instead of the words",
                start_ms=10_000, end_ms=20_000)
    cues = build_cues(transcript("en", s), rules_for("en"))
    check_track(cues)
    assert len(cues) >= 2
    assert all("est" in c.flags for c in cues)
    assert cues[0].start_ms == 10_000 and cues[-1].end_ms == 20_000


def test_a_lone_short_word_is_stretched_to_the_minimum_duration():
    cues = build_cues(transcript("en", seg(words([" Yes."], dur=200))), rules_for("en"))
    assert cues[0].end_ms - cues[0].start_ms >= 833


def test_a_gap_under_half_a_second_is_closed_to_two_frames():
    first = words([" One", " two", " three."])
    second = words([" Four."], start=first[-1].end_ms + 300)
    cues = build_cues(transcript("en", seg(first), seg(second)), rules_for("en"))
    assert cues[1].start_ms - cues[0].end_ms == 84


def test_a_known_hallucination_is_flagged_not_deleted():
    ws = words(["ご", "視", "聴", "あ", "り", "が", "と", "う", "ご", "ざ", "い", "ま", "し", "た"],
               step=200)
    cues = build_cues(transcript("ja", seg(ws)), rules_for("ja"))
    assert cues and all("halluc" in c.flags for c in cues)


def test_words_spoken_where_the_vad_heard_no_speech_are_flagged():
    ws = words([" Mystery", " words", " here."], start=50_000)
    cues = build_cues(transcript("en", seg(ws)), rules_for("en"), speech=[(0, 10_000)])
    assert "halluc" in cues[0].flags


@settings(max_examples=60, deadline=None)
@given(st.lists(st.tuples(st.integers(0, 2500), st.integers(30, 1500),
                          st.sampled_from([" word", " the.", " end,", "字", "。"])),
                min_size=1, max_size=120))
def test_any_word_sequence_gives_a_valid_track_that_covers_every_word_once(spec):
    t, ws = 0, []
    for gap, dur, text in spec:
        t += gap
        ws.append(Word(text=text, start_ms=t, end_ms=t + dur))
        t += dur
    cues = build_cues(transcript("en", seg(tuple(ws))), rules_for("en"))
    check_track(cues)
    for c in cues:
        assert c.end_ms - c.start_ms <= 7000
    for a, b in pairwise(cues):
        assert b.start_ms - a.end_ms >= 84
    covered = sorted(i for c in cues if c.w for i in range(*c.w))
    assert covered == list(range(len(ws)))


def test_a_sparse_unaligned_segment_is_split_into_cues_of_at_most_seven_seconds():
    s = Segment(text="alpha bravo charlie delta echo foxtrot", start_ms=0, end_ms=30_000)
    cues = build_cues(transcript("en", s), rules_for("en"))
    check_track(cues)
    assert len(cues) >= 5
    assert all(c.end_ms - c.start_ms <= 7000 for c in cues)
    assert all("est" in c.flags for c in cues)


def test_an_unaligned_segment_with_a_high_compression_ratio_is_flagged():
    s = Segment(text="Some perfectly ordinary words", start_ms=0, end_ms=4000,
                compression_ratio=3.0)
    cues = build_cues(transcript("en", s), rules_for("en"))
    assert cues and all("halluc" in c.flags for c in cues)


def test_an_unaligned_segment_outside_speech_is_flagged():
    s = Segment(text="Some perfectly ordinary words", start_ms=50_000, end_ms=54_000)
    cues = build_cues(transcript("en", s), rules_for("en"), speech=[(0, 10_000)])
    assert cues and all("halluc" in c.flags for c in cues)


def test_segments_whose_words_overlap_in_time_still_keep_the_minimum_gap():
    a = words([" First", " part."], start=1000)
    b = words([" Second", " part."], start=1020)
    cues = build_cues(transcript("en", seg(a), seg(b)), rules_for("en"))
    check_track(cues)
    assert len(cues) == 2
    assert cues[1].start_ms - cues[0].end_ms >= 84
