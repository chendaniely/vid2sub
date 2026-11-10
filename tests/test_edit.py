import time

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from vid2sub.subs import edit
from vid2sub.subs.edit import EditError, Tracks
from vid2sub.subs.model import Cue, check_track, new_cue_id
from vid2sub.subs.translate_shape import src_sha, stale_ids, untranslated

# New cues' ids, as the page draws them: c + 8 lowercase hex (Decision 31)
A, B, M, J, USED = "c0000000a", "c0000000b", "c000000a1", "c000000b1", "c0ffee000"


def cue(id, start, end, text, **kw):
    return Cue(id=id, start_ms=start, end_ms=end, text=text, **kw)


def tracks() -> Tracks:
    a = cue("a", 0, 1000, "おはよう", w=(0, 2))
    b = cue("b", 1000, 2000, "元気ですか", w=(2, 5), flags=("halluc",))
    c = cue("c", 3000, 4000, "はい、元気です", w=(5, 9), flags=("est",))
    en = (cue("ta", 0, 1000, "Good morning", src=("a",), src_sha=src_sha([a.text])),
          cue("tb", 1000, 4000, "How are you? Fine.", src=("b", "c"),
              src_sha=src_sha([b.text, c.text])))
    return Tracks((a, b, c), {"en": en})


def by_id(cues):
    return {c.id: c for c in cues}


def stale(t: Tracks, track: str = "en") -> set[str]:
    return stale_ids(t.translations[track], by_id(t.source))


def test_the_example_episode_starts_with_nothing_stale():
    assert stale(tracks()) == set()


def test_editing_a_cue_canonicalises_its_text_keeps_its_words_and_drops_halluc():
    t = tracks()
    out = edit.set_text(t, "b", "  元気  \n\n ですか ")
    b = by_id(out.source)["b"]
    assert b.text == "元気\nですか"
    assert b.w == (2, 5) and "halluc" not in b.flags
    assert t == tracks()


def test_a_cue_cannot_be_edited_down_to_nothing():
    with pytest.raises(EditError, match="delete it instead"):
        edit.set_text(tracks(), "a", " \n ")


def test_editing_a_source_cue_makes_its_translation_stale():
    assert stale(edit.set_text(tracks(), "c", "いいえ")) == {"tb"}


def test_editing_a_translation_marks_it_edited_and_keeps_its_source_hash():
    t = tracks()
    out = edit.set_translation_text(t, "en", "ta", "Morning!")
    ta = by_id(out.translations["en"])["ta"]
    assert ta.text == "Morning!" and "edited" in ta.flags
    assert ta.src_sha == by_id(t.translations["en"])["ta"].src_sha


def test_setting_times_is_clamped_to_the_neighbours_and_drops_est():
    out = edit.set_times(tracks(), "c", start_ms=500)
    c = by_id(out.source)["c"]
    assert (c.start_ms, c.end_ms) == (2000, 4000)
    assert "est" not in c.flags and c.w == (5, 9)


def test_times_that_leave_a_cue_nothing_are_refused():
    with pytest.raises(EditError, match="start before it ends"):
        edit.set_times(tracks(), "b", start_ms=2500)
    with pytest.raises(EditError, match="start before it ends"):
        edit.set_times(tracks(), "a", end_ms=-5)


def test_a_nudge_moves_a_cue_as_a_block_without_entering_its_neighbours():
    t = tracks()
    c = by_id(edit.nudge(t, "c", -1500).source)["c"]
    assert (c.start_ms, c.end_ms) == (2000, 3000)
    c = by_id(edit.nudge(t, "c", 400, edge="end").source)["c"]
    assert (c.start_ms, c.end_ms) == (3000, 4400)
    b = by_id(edit.nudge(t, "b", -300, edge="start").source)["b"]
    assert (b.start_ms, b.end_ms) == (1000, 2000)


def test_translations_follow_their_source_cues_unless_detached():
    t = edit.nudge(tracks(), "c", 500)
    assert by_id(t.translations["en"])["tb"].end_ms == 4500
    t = edit.detach(t, "en", "tb", True)
    t = edit.nudge(t, "c", 500)
    assert by_id(t.translations["en"])["tb"].end_ms == 4500
    t = edit.detach(t, "en", "tb", False)
    assert by_id(t.translations["en"])["tb"].end_ms == 5000


def test_an_edit_that_would_overlap_a_detached_translation_is_refused():
    t = edit.detach(tracks(), "en", "ta", True)
    t = edit.set_times(t, "a", end_ms=500)
    with pytest.raises(EditError, match="the en track"):
        edit.set_times(t, "b", start_ms=600)


def test_follow_gives_each_attached_translation_the_span_of_its_source_cues():
    source = (cue("a", 0, 1000, "x"), cue("b", 1500, 2500, "y"))
    trans = (cue("t1", 100, 200, "X Y", src=("a", "b")),
             cue("t2", 5000, 6000, "Z", src=("gone",)),
             cue("t3", 7000, 8000, "W", src=("a",), detached=True))
    out = by_id(edit.follow(source, trans))
    assert (out["t1"].start_ms, out["t1"].end_ms) == (0, 2500)
    assert (out["t2"].start_ms, out["t2"].end_ms) == (5000, 6000)
    assert (out["t3"].start_ms, out["t3"].end_ms) == (7000, 8000)


def test_a_split_gives_both_halves_the_ids_it_is_given_and_repoints_the_translation():
    taken = {"a", "b", "c", "ta", "tb"}
    out, (h1, h2) = edit.split(tracks(), "c", at_char=3, at_ms=3400, ids=(A, B), taken=taken)
    assert (h1, h2) == (A, B)
    halves = [by_id(out.source)[h1], by_id(out.source)[h2]]
    assert [h.text for h in halves] == ["はい、", "元気です"]
    assert [(h.start_ms, h.end_ms) for h in halves] == [(3000, 3400), (3400, 4000)]
    assert all(h.from_ == ("c",) and h.w is None for h in halves)
    assert {h1, h2} <= taken and "c" not in by_id(out.source)
    assert by_id(out.translations["en"])["tb"].src == ("b", h1, h2)
    assert stale(out) == {"tb"}


@pytest.mark.parametrize("at_char, at_ms", [(0, 3400), (7, 3400), (3, 3000), (3, 4000)])
def test_a_split_needs_text_and_time_on_both_sides(at_char, at_ms):
    with pytest.raises(EditError, match="split"):
        edit.split(tracks(), "c", at_char=at_char, at_ms=at_ms, ids=(A, B), taken=set())


def test_a_merge_joins_the_text_the_times_the_word_ranges_and_the_flags():
    taken: set[str] = set()
    out, m = edit.merge_next(tracks(), "a", new_id=M, joined_ids={"en": J}, taken=taken)
    merged = by_id(out.source)[m]
    assert merged.text == "おはよう\n元気ですか"
    assert (merged.start_ms, merged.end_ms) == (0, 2000)
    assert merged.w == (0, 5) and merged.from_ == ("a", "b") and merged.flags == ("halluc",)
    assert m == M and m in taken and [c.id for c in out.source] == [m, "c"]


def test_a_merge_concatenates_the_translations_of_either_part_into_one_stale_cue():
    t = edit.set_translation_text(tracks(), "en", "ta", "Morning")
    taken: set[str] = set()
    out, m = edit.merge_next(t, "a", new_id=M, joined_ids={"en": J}, taken=taken)
    (joined,) = out.translations["en"]
    assert joined.id == J and J in taken
    assert joined.from_ == ("ta", "tb") and joined.src == (m, "c")
    assert joined.text == "Morning\nHow are you? Fine."
    assert (joined.start_ms, joined.end_ms) == (0, 4000)
    assert "edited" in joined.flags and stale(out) == {joined.id}


def test_merging_two_cues_one_translation_covers_keeps_that_translation():
    out, m = edit.merge_next(tracks(), "b", new_id=M, joined_ids={}, taken=set())
    tb = by_id(out.translations["en"])["tb"]
    assert tb.src == (m,) and stale(out) == {"tb"}


def test_a_merge_keeps_no_word_range_unless_both_parts_have_one():
    t, _ = edit.insert(tracks(), start_ms=2100, end_ms=2900, text="えっ", new_id=A, taken=set())
    out, m = edit.merge_next(t, "b", new_id=M, joined_ids={}, taken=set())
    assert by_id(out.source)[m].w is None


def test_the_last_cue_has_nothing_to_merge_with():
    with pytest.raises(EditError, match="last cue"):
        edit.merge_next(tracks(), "c", new_id=M, joined_ids={}, taken=set())


def test_a_delete_takes_the_id_out_of_every_src_and_drops_a_translation_left_with_none():
    out = edit.delete(tracks(), "a")
    assert [c.id for c in out.translations["en"]] == ["tb"]
    out = edit.delete(tracks(), "b")
    tb = by_id(out.translations["en"])["tb"]
    assert tb.src == ("c",) and (tb.start_ms, tb.end_ms) == (3000, 4000)
    assert stale(out) == {"tb"}


def test_an_inserted_cue_fills_the_gap_and_is_untranslated():
    taken: set[str] = set()
    out, new = edit.insert(tracks(), start_ms=2100, end_ms=3500, text=" えっ ", new_id=A,
                           taken=taken)
    c = by_id(out.source)[new]
    assert new == A and (c.start_ms, c.end_ms, c.text, c.w) == (2100, 3000, "えっ", None)
    assert [x.id for x in out.source] == ["a", "b", new, "c"] and new in taken
    assert untranslated([x.id for x in out.source], out.translations["en"]) == [new]


def test_a_cue_cannot_be_inserted_on_top_of_another():
    with pytest.raises(EditError, match="already a cue"):
        edit.insert(tracks(), start_ms=500, end_ms=800, text="x", new_id=A, taken=set())


def test_a_merge_that_joins_translations_needs_a_new_id_for_each_joined_track():
    t = edit.set_translation_text(tracks(), "en", "ta", "Morning")
    taken = {"a", "b", "c", "ta", "tb"}
    with pytest.raises(EditError, match="the en track's translations"):
        edit.merge_next(t, "a", new_id=M, joined_ids={}, taken=taken)
    assert taken == {"a", "b", "c", "ta", "tb"}


@pytest.mark.parametrize("call", [
    lambda t, taken: edit.split(t, "c", at_char=3, at_ms=3400, ids=(A, "C0000000B"),
                                taken=taken),
    lambda t, taken: edit.split(t, "c", at_char=3, at_ms=3400, ids=(A, A), taken=taken),
    lambda t, taken: edit.split(t, "c", at_char=3, at_ms=3400, ids=(A, USED), taken=taken),
    lambda t, taken: edit.merge_next(t, "b", new_id="c123", joined_ids={}, taken=taken),
    lambda t, taken: edit.merge_next(t, "a", new_id=M, joined_ids={"en": M}, taken=taken),
    lambda t, taken: edit.insert(t, start_ms=2100, end_ms=2900, text="x", new_id=USED,
                                 taken=taken),
])
def test_a_malformed_or_taken_new_id_is_refused_and_nothing_changes(call):
    taken = {"a", "b", "c", "ta", "tb", USED}
    with pytest.raises(EditError, match="new cue's id"):
        call(tracks(), taken)
    assert taken == {"a", "b", "c", "ta", "tb", USED}


def test_an_edit_the_tracks_refuse_leaves_taken_as_it_was():
    # merging joins ta and tb across a detached cue between them, which the en track can't hold
    a, b = cue("a", 0, 1000, "x"), cue("b", 2000, 3000, "y")
    en = (cue("ta", 0, 1000, "X", src=("a",)),
          cue("tx", 1200, 1800, "Z", src=("gone",), detached=True),
          cue("tb", 2000, 3000, "Y", src=("b",)))
    taken = {"a", "b", "ta", "tx", "tb"}
    with pytest.raises(EditError, match="the en track would break"):
        edit.merge_next(Tracks((a, b), {"en": en}), "a", new_id=M, joined_ids={"en": J},
                        taken=taken)
    assert taken == {"a", "b", "ta", "tx", "tb"}


def test_the_same_edits_with_the_same_ids_make_the_same_tracks():
    # what lets a crash draft replay exactly: a later edit names the cue an earlier one made
    def run() -> Tracks:
        taken = {"a", "b", "c", "ta", "tb"}
        t, _ = edit.insert(tracks(), start_ms=2100, end_ms=2900, text="…", new_id=A,
                           taken=taken)
        t = edit.set_text(t, A, "えっと")
        t, _ = edit.split(t, "c", at_char=3, at_ms=3400, ids=(B, M), taken=taken)
        t = edit.set_text(t, M, "元気だ")
        t = edit.set_translation_text(t, "en", "ta", "Morning")
        t, _ = edit.merge_next(t, "a", new_id=J, joined_ids={"en": USED}, taken=taken)
        return edit.set_translation_text(t, "en", USED, "Morning! How are you?")

    out = run()
    assert out == run()
    assert by_id(out.source)[A].text == "えっと" and by_id(out.source)[M].text == "元気だ"
    assert by_id(out.translations["en"])[USED].text == "Morning! How are you?"


def test_replace_all_replaces_plain_text_across_the_named_tracks_and_counts_it():
    out, n = edit.replace_all(tracks(), "元気", "げんき", tracks=["source", "en"])
    assert n == 2
    assert by_id(out.source)["c"].text == "はい、げんきです"
    assert "halluc" not in by_id(out.source)["b"].flags
    out, n = edit.replace_all(tracks(), ".", "!", tracks=["en"])
    assert n == 1 and by_id(out.translations["en"])["tb"].text == "How are you? Fine!"
    assert "edited" in by_id(out.translations["en"])["tb"].flags
    out, n = edit.replace_all(tracks(), "good", "Bad", tracks=["en"])
    assert n == 0 and out == tracks()


def test_replace_all_refuses_to_leave_a_cue_empty():
    with pytest.raises(EditError, match="delete it instead"):
        edit.replace_all(tracks(), "おはよう", "", tracks=["source"])


@pytest.mark.parametrize("call", [
    lambda t: edit.set_text(t, "zz", "x"),
    lambda t: edit.set_translation_text(t, "de", "ta", "x"),
    lambda t: edit.detach(t, "en", "zz", True),
    lambda t: edit.replace_all(t, "x", "y", tracks=["de"]),
    lambda t: edit.replace_all(t, "", "y", tracks=["source"]),
])
def test_an_unknown_cue_or_track_or_an_empty_find_is_refused(call):
    with pytest.raises(EditError):
        call(tracks())


def test_every_edit_on_a_two_hour_episode_takes_well_under_a_second():
    source = tuple(cue(f"s{i}", i * 3600, i * 3600 + 3000, f"line {i}", w=(i, i + 1))
                   for i in range(2000))
    en = tuple(cue(f"t{i}", i * 3600, i * 3600 + 3000, f"Line {i}", src=(f"s{i}",))
               for i in range(2000))
    start = Tracks(source, {"en": en})
    ids = {c.id for c in source + en}

    def every_edit() -> float:
        t, taken = start, set(ids)  # the edits add to `taken`
        began = time.perf_counter()
        t = edit.set_text(t, "s1000", "changed")
        t = edit.nudge(t, "s1000", 100)
        t, _ = edit.split(t, "s10", at_char=2, at_ms=36_100, ids=(A, B), taken=taken)
        t, _ = edit.merge_next(t, "s20", new_id=M, joined_ids={"en": J}, taken=taken)
        t = edit.delete(t, "s30")
        t, _ = edit.replace_all(t, "line", "Line", tracks=["source"])
        return time.perf_counter() - began

    # The fastest of three, each from the same start: a busy machine (three suites at once)
    # slows a run without it being a slow edit, and a real slowdown is slow in all three.
    assert min(every_edit() for _ in range(3)) < 1.0


OP_NAMES = ["set_text", "set_translation_text", "set_times", "nudge", "split", "merge_next",
            "insert", "delete", "detach", "replace_all"]
TEXTS = ["", "x", "a b", "\n", "  y  ", "元気", "w1"]


def _start(spec) -> Tracks:
    t, source = 0, []
    for i, (gap, dur) in enumerate(spec):
        t += gap
        source.append(cue(f"s{i}", t, t + dur, f"w{i}", w=(i, i + 1)))
        t += dur
    pairs = [source[k:k + 2] for k in range(0, len(source), 2)]
    en = tuple(cue(f"t{k}", p[0].start_ms, p[-1].end_ms, f"T{k}", src=tuple(c.id for c in p),
                   src_sha=src_sha([c.text for c in p])) for k, p in enumerate(pairs))
    return Tracks(tuple(source), {"en": en})


def _fresh(taken: set[str], n: int) -> list[str]:
    """n new ids, as the page draws them; the edit itself adds them to `taken`."""
    pool = set(taken)
    return [new_cue_id(pool) for _ in range(n)]


def _apply(t: Tracks, op, taken: set[str]) -> Tracks:
    name, k, ms, delta, text = op
    if name == "insert" or not t.source:
        return edit.insert(t, start_ms=ms, end_ms=ms + abs(delta), text=text,
                           new_id=_fresh(taken, 1)[0], taken=taken)[0]
    c = t.source[k % len(t.source)]
    en = t.translations["en"]
    if name == "set_text":
        return edit.set_text(t, c.id, text)
    if name == "set_translation_text":
        return edit.set_translation_text(t, "en", en[k % len(en)].id, text) if en else t
    if name == "set_times":
        return edit.set_times(t, c.id, start_ms=ms, end_ms=ms + delta)
    if name == "nudge":
        return edit.nudge(t, c.id, delta, edge=("start", "end", "both")[k % 3])
    if name == "split":
        at_ms = c.start_ms + ms % (c.end_ms - c.start_ms + 1)
        return edit.split(t, c.id, at_char=k % (len(c.text) + 1), at_ms=at_ms,
                          ids=tuple(_fresh(taken, 2)), taken=taken)[0]
    if name == "merge_next":
        new_id, joined = _fresh(taken, 2)
        return edit.merge_next(t, c.id, new_id=new_id, joined_ids={"en": joined}, taken=taken)[0]
    if name == "delete":
        return edit.delete(t, c.id)
    if name == "detach":
        return edit.detach(t, "en", en[k % len(en)].id, bool(delta % 2)) if en else t
    return edit.replace_all(t, text or "w", text, tracks=["source", "en"])[0]


def _assert_invariants(t: Tracks) -> None:
    check_track(t.source)
    source = by_id(t.source)
    for cues in t.translations.values():
        check_track(cues)
        covered = [i for c in cues for i in c.src or ()]
        assert len(covered) == len(set(covered)), "a source cue is in two translations"
        for c in cues:
            assert c.src and all(i in source for i in c.src)
            if not c.detached:
                assert c.start_ms == min(source[i].start_ms for i in c.src)
                assert c.end_ms == max(source[i].end_ms for i in c.src)


@settings(max_examples=150, deadline=None)
@given(st.lists(st.tuples(st.integers(0, 800), st.integers(1, 2000)), min_size=1, max_size=10),
       st.lists(st.tuples(st.sampled_from(OP_NAMES), st.integers(0, 50),
                          st.integers(-3000, 30_000), st.integers(-3000, 3000),
                          st.sampled_from(TEXTS)), max_size=25))
def test_any_sequence_of_edits_keeps_every_track_valid_and_never_mutates_its_input(spec, ops):
    t = _start(spec)
    taken = {c.id for c in t.source} | {c.id for c in t.translations["en"]}
    for op in ops:
        before = Tracks(t.source, dict(t.translations))
        try:
            out = _apply(t, op, taken)
        except EditError:
            out = t
        assert t == before
        _assert_invariants(out)
        t = out
