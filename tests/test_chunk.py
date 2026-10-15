import itertools

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from vid2sub.media.chunk import chunk_samples, place, plan_chunks
from vid2sub.subs.model import Segment, Word


def test_short_audio_is_one_chunk_that_owns_the_whole_timeline():
    plans = plan_chunks([(1000, 5000)], 10_000, 300)
    assert len(plans) == 1
    p = plans[0]
    assert (p.start_ms, p.end_ms) == (500, 5500)
    assert p.owns(0) and p.owns(9_999) and p.last


def test_chunks_respect_the_engines_limit_and_cut_in_silence():
    speech = [(i * 30_000, i * 30_000 + 25_000) for i in range(20)]  # 10 minutes
    plans = plan_chunks(speech, 600_000, 180)
    assert all(p.end_ms - p.start_ms <= 180_000 for p in plans)
    for a, b in itertools.pairwise(plans):
        assert a.core_end_ms == b.core_start_ms
        assert not any(s < a.core_end_ms < e for s, e in speech)


def test_a_long_silence_forces_a_new_chunk():
    plans = plan_chunks([(0, 5000), (60_000, 65_000)], 70_000, 300)
    assert len(plans) == 2


def test_continuous_speech_longer_than_a_chunk_is_split():
    plans = plan_chunks([(0, 400_000)], 400_000, 180)
    assert len(plans) == 3
    assert all(p.end_ms - p.start_ms <= 180_000 for p in plans)


def test_long_non_speech_inside_a_chunk_is_silenced_but_speech_is_kept():
    samples = np.ones(16 * 20_000, dtype=np.int16)
    plan = plan_chunks([(0, 2000), (10_000, 12_000)], 20_000, 300, max_gap_ms=30_000)[0]
    out = chunk_samples(samples, plan, [(0, 2000), (10_000, 12_000)])
    assert out[16 * 1000] == 1  # speech
    assert out[16 * 6000] == 0  # 8 s of non-speech, silenced


def test_place_moves_words_to_the_global_timeline_and_keeps_only_owned_ones():
    plans = plan_chunks([(0, 100_000), (110_000, 200_000)], 200_000, 120)
    p = plans[1]
    seg = Segment(text=" a b", start_ms=0, end_ms=2000,
                  words=(Word(text=" a", start_ms=0, end_ms=100),
                         Word(text=" b", start_ms=1500, end_ms=1600)))
    placed = place(p, [seg])
    owned = [w for s in placed for w in s.words]
    assert all(p.owns((w.start_ms + w.end_ms) // 2) for w in owned)
    assert all(w.start_ms >= p.start_ms for w in owned)


@settings(max_examples=80, deadline=None)
@given(st.lists(st.tuples(st.integers(0, 20_000), st.integers(100, 90_000)), min_size=1,
                max_size=30),
       st.lists(st.integers(0, 999_999), min_size=1, max_size=200),
       st.sampled_from([180, 300]))
def test_every_moment_is_owned_by_exactly_one_chunk(gaps_and_lengths, mids, max_chunk_s):
    t, speech = 0, []
    for gap, length in gaps_and_lengths:
        t += gap
        speech.append((t, t + length))
        t += length
    duration = t + 1000
    plans = plan_chunks(speech, duration, max_chunk_s)
    assert all(p.end_ms - p.start_ms <= max_chunk_s * 1000 for p in plans)
    for mid in (m % duration for m in mids):
        assert sum(p.owns(mid) for p in plans) == 1


def _middle_plan():
    plans = plan_chunks([(0, 400_000)], 400_000, 180)
    assert len(plans) == 3
    return plans[1]


def test_place_drops_words_owned_by_the_neighbouring_chunks():
    p = _middle_plan()
    before = (0, 300)  # global midpoint lies before p.core_start_ms
    inside = (10_000, 10_200)  # inside p's core
    after = (p.end_ms - p.start_ms - 300, p.end_ms - p.start_ms)  # after p.core_end_ms
    assert p.start_ms + before[1] // 2 < p.core_start_ms
    assert p.core_start_ms <= p.start_ms + inside[0] < p.core_end_ms
    assert p.start_ms + (after[0] + after[1]) // 2 >= p.core_end_ms
    seg = Segment(text=" a b c", start_ms=0, end_ms=p.end_ms - p.start_ms,
                  words=(Word(text=" a", start_ms=before[0], end_ms=before[1]),
                         Word(text=" b", start_ms=inside[0], end_ms=inside[1]),
                         Word(text=" c", start_ms=after[0], end_ms=after[1])))
    placed = place(p, [seg])
    owned = [w for s in placed for w in s.words]
    assert [w.text for w in owned] == [" b"]
    assert owned[0].start_ms == p.start_ms + inside[0]


def test_place_clamps_an_unaligned_segment_to_its_core():
    p = _middle_plan()
    # Midpoint 100 ms inside the core; the span runs 400 ms before core_end to 200 ms after it.
    start = p.core_end_ms - 400 - p.start_ms
    end = p.core_end_ms + 200 - p.start_ms
    seg = Segment(text=" spans the boundary", start_ms=start, end_ms=end)
    placed = place(p, [seg])
    assert len(placed) == 1
    assert placed[0].start_ms == p.core_end_ms - 400
    assert placed[0].end_ms == p.core_end_ms


def test_place_keeps_the_original_text_when_every_word_is_owned():
    plans = plan_chunks([(0, 5000)], 10_000, 300)
    seg = Segment(text=" a  b", start_ms=0, end_ms=2000,
                  words=(Word(text=" a", start_ms=0, end_ms=100),
                         Word(text=" b", start_ms=1500, end_ms=1600)))
    placed = place(plans[0], [seg])
    assert [s.text for s in placed] == [" a  b"]
