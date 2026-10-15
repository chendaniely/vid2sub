import pytest
from pydantic import ValidationError

from vid2sub.subs import translate_shape as ts
from vid2sub.subs.model import Cue

IDS = [f"s{i}" for i in range(100)]
SOURCE = {cid: Cue(id=cid, start_ms=i * 2000, end_ms=i * 2000 + 1500, text=f"text {i}")
          for i, cid in enumerate(IDS)}


def test_batches_cover_every_id_once_with_read_only_context_on_both_sides():
    batches = ts.plan_batches(IDS, size=40, context=5)
    assert [len(b.ids) for b in batches] == [40, 40, 20]
    assert batches[0].before == () and batches[0].after == tuple(IDS[40:45])
    assert batches[1].before == tuple(IDS[35:40])


def test_selected_ids_batch_in_contiguous_runs():
    batches = ts.plan_batches(IDS, ["s3", "s4", "s9"], size=40)
    assert [b.ids for b in batches] == [("s3", "s4"), ("s9",)]


def test_splitting_a_batch_halves_it():
    batch = ts.plan_batches(IDS[:10], size=40)[0]
    halves = ts.split_batch(batch, IDS[:10])
    assert [len(h.ids) for h in halves] == [5, 5]


def test_the_batch_schema_admits_only_this_batchs_ids():
    model = ts.batch_model(["a", "b"])
    model.model_validate({"items": [{"src": ["a", "b"], "text": "AB"}]})
    with pytest.raises(ValidationError):
        model.model_validate({"items": [{"src": ["z"], "text": "?"}]})
    schema = model.model_json_schema()
    assert "a" in str(schema) and "b" in str(schema)


def test_an_item_may_merge_adjacent_cues_but_must_cover_all_in_order():
    ok = [ts.Item(("s0", "s1"), "Both"), ts.Item(("s2",), "Third")]
    assert ts.validate_partition(ok, ["s0", "s1", "s2"]) == ok
    for bad in ([ts.Item(("s1",), "x"), ts.Item(("s0",), "y"), ts.Item(("s2",), "z")],
                [ts.Item(("s0",), "x"), ts.Item(("s2",), "z")],
                [ts.Item(("s0", "s1", "s2"), "  ")]):
        with pytest.raises(ts.PartitionError):
            ts.validate_partition(bad, ["s0", "s1", "s2"])


def test_assembled_translation_spans_its_source_cues_and_records_their_hash():
    taken: set[str] = set()
    out = ts.assemble([ts.Item(("s0", "s1"), "One long English line")], SOURCE, "en", taken)
    assert (out[0].start_ms, out[0].end_ms) == (0, 3500)
    assert out[0].src == ("s0", "s1")
    assert out[0].src_sha == ts.src_sha(["text 0", "text 1"])
    assert out[0].id in taken


def test_limits_follow_reading_speed_and_line_width():
    limits = ts.item_limits([SOURCE["s0"]], "en")
    assert limits["s0"] == 30  # 20 cps for 1.5 s; two lines of 42 would allow 84


def test_a_translation_goes_stale_when_its_source_changes_or_disappears():
    taken: set[str] = set()
    trans = ts.assemble([ts.Item(("s0",), "Zero"), ts.Item(("s1",), "One")], SOURCE, "en", taken)
    changed = dict(SOURCE)
    changed["s0"] = SOURCE["s0"].model_copy(update={"text": "edited"})
    del changed["s1"]
    assert ts.stale_ids(trans, changed) == {trans[0].id, trans[1].id}
    assert ts.stale_ids(trans, SOURCE) == set()
    assert ts.untranslated(IDS[:3], trans) == ["s2"]
