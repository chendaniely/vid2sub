import pytest

from vid2sub.subs.model import (
    Cue,
    Segment,
    TrackError,
    Transcript,
    Word,
    check_track,
    new_cue_id,
    shift_segment,
)


def cue(id, start, end, text="x", **kw):
    return Cue(id=id, start_ms=start, end_ms=end, text=text, **kw)


def test_a_cue_dumps_with_its_aliases_and_without_defaults():
    c = cue("c1", 0, 1000, "Hi", from_=("c0",), w=(0, 2))
    assert c.dump() == {"id": "c1", "start_ms": 0, "end_ms": 1000, "text": "Hi",
                        "from": ["c0"], "w": [0, 2]}
    assert Cue.model_validate(c.dump()) == c


def test_new_cue_ids_are_unique_and_recorded_as_taken():
    taken: set[str] = set()
    ids = {new_cue_id(taken) for _ in range(500)}
    assert len(ids) == 500 and ids == taken


def test_a_valid_track_passes_the_invariants():
    check_track([cue("a", 0, 1000), cue("b", 1000, 2000, "y\nz")])


@pytest.mark.parametrize("cues, message", [
    ([cue("a", 1000, 1000)], "starts at or after its end"),
    ([cue("a", 0, 1000), cue("b", 500, 2000)], "overlaps"),
    ([cue("a", 2000, 3000), cue("b", 0, 1000)], "out of order"),
    ([cue("a", 0, 1000), cue("a", 1000, 2000)], "duplicate id"),
    ([cue("a", 0, 1000, "x\n\ny")], "blank line"),
    ([cue("a", 0, 1000, "  ")], "empty"),
])
def test_a_broken_track_is_refused_with_a_reason(cues, message):
    with pytest.raises(TrackError, match=message):
        check_track(cues)


def test_shifting_a_segment_moves_its_words_too():
    seg = Segment(text=" a b", start_ms=0, end_ms=900,
                  words=(Word(text=" a", start_ms=0, end_ms=400),
                         Word(text=" b", start_ms=500, end_ms=900)))
    moved = shift_segment(seg, 1500)
    assert (moved.start_ms, moved.end_ms) == (1500, 2400)
    assert [w.start_ms for w in moved.words] == [1500, 2000]


def test_a_transcript_lists_all_its_words_in_order():
    t = Transcript(language="en", segments=(
        Segment(text=" a", start_ms=0, end_ms=1, words=(Word(text=" a", start_ms=0, end_ms=1),)),
        Segment(text="unaligned", start_ms=2, end_ms=3),
        Segment(text=" b", start_ms=4, end_ms=5, words=(Word(text=" b", start_ms=4, end_ms=5),)),
    ))
    assert [w.text for w in t.words()] == [" a", " b"]
    assert not t.segments[1].aligned
