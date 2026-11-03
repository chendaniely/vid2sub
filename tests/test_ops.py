import pytest
from pydantic import ValidationError

from vid2sub.subs.model import new_cue_id
from vid2sub.web import ops
from vid2sub.web.ops import BadOp

CUE = "ca0000001"
NEW, NEW2 = "cb0000002", "cb0000003"  # new cues' ids, as the page draws them
SECRET = "SECRET-7f3a"  # stands for anything a hostile page might send


@pytest.mark.parametrize("data, kind", [
    ({"op": "set_text", "cue": CUE, "text": "こんにちは"}, ops.SetText),
    ({"op": "set_translation_text", "track": "en", "cue": CUE, "text": "Hi"},
     ops.SetTranslationText),
    ({"op": "set_times", "cue": CUE, "start_ms": 100}, ops.SetTimes),
    ({"op": "nudge", "cue": CUE, "delta_ms": -100, "edge": "start"}, ops.Nudge),
    ({"op": "split", "cue": CUE, "at_char": 2, "at_ms": 1500, "ids": [NEW, NEW2]}, ops.Split),
    ({"op": "merge_next", "cue": CUE, "id": NEW, "joined": {"en": NEW2}}, ops.MergeNext),
    ({"op": "insert", "start_ms": 0, "end_ms": 900, "text": "えっ", "id": NEW}, ops.Insert),
    ({"op": "delete", "cue": CUE}, ops.Delete),
    ({"op": "detach", "track": "en", "cue": CUE, "detached": True}, ops.Detach),
    ({"op": "replace_all", "find": "元気", "replace": "", "tracks": ["source", "en"]},
     ops.ReplaceAll),
    ({"op": "glossary_add", "term": "工藤新一", "translation": "Shinichi Kudo"},
     ops.GlossaryAdd),
])
def test_each_edit_the_editor_sends_is_read_as_its_own_kind(data, kind):
    op = ops.parse_op(data)
    assert type(op) is kind and op.op == data["op"]
    assert op.model_dump(exclude_defaults=True) | {"op": data["op"]} == data


def test_a_nudge_moves_the_whole_cue_unless_told_otherwise():
    assert ops.parse_op({"op": "nudge", "cue": CUE, "delta_ms": 500}).edge == "both"


def test_cue_ids_have_the_shape_new_cue_id_makes():
    cid = new_cue_id(set())
    assert ops.parse_op({"op": "delete", "cue": cid}).cue == cid


def test_an_edit_is_frozen():
    op = ops.parse_op({"op": "delete", "cue": CUE})
    with pytest.raises(ValidationError):
        op.cue = "cb0000002"  # type: ignore[misc]


@pytest.mark.parametrize("data", ["set_text", None, 3, [{"op": "delete", "cue": CUE}]])
def test_an_edit_must_be_an_object(data):
    with pytest.raises(BadOp, match="an edit is a JSON object"):
        ops.parse_op(data)


def test_an_unknown_edit_is_refused_without_echoing_it():
    with pytest.raises(BadOp) as err:
        ops.parse_op({"op": f"<script>{SECRET}</script>", "cue": CUE})
    assert str(err.value) == "this edit can't be made: op isn't a known edit"
    assert err.value.field == "op"


def test_an_edit_with_no_kind_is_refused():
    with pytest.raises(BadOp, match="op is missing"):
        ops.parse_op({"cue": CUE})


def test_an_unknown_field_is_refused_without_naming_it():
    with pytest.raises(BadOp) as err:
        ops.parse_op({"op": "set_text", "cue": CUE, "text": "x", f"evil_{SECRET}": 1})
    assert str(err.value) == "this edit can't be made: it has a field no edit has"
    assert SECRET not in str(err.value) and err.value.field is None


@pytest.mark.parametrize("data, field, reason", [
    ({"op": "set_text", "cue": CUE}, "text", "is missing"),
    ({"op": "set_text", "cue": CUE, "text": "x" * 2000 + SECRET}, "text", "is too long"),
    ({"op": "set_text", "cue": f"../{SECRET}", "text": "x"}, "cue", "isn't valid"),
    ({"op": "set_text", "cue": "c1", "text": "x"}, "cue", "isn't valid"),
    ({"op": "set_times", "cue": CUE, "start_ms": -1}, "start_ms", "is out of range"),
    ({"op": "set_times", "cue": CUE, "end_ms": 48 * 3600 * 1000 + 1}, "end_ms",
     "is out of range"),
    ({"op": "nudge", "cue": CUE, "delta_ms": "100"}, "delta_ms", "has the wrong type"),
    ({"op": "nudge", "cue": CUE, "delta_ms": 100, "edge": SECRET}, "edge",
     "isn't one of the choices"),
    ({"op": "split", "cue": CUE, "at_char": 1.5, "at_ms": 10, "ids": [NEW, NEW2]}, "at_char",
     "has the wrong type"),
    ({"op": "split", "cue": CUE, "at_char": 1, "at_ms": 10}, "ids", "is missing"),
    ({"op": "split", "cue": CUE, "at_char": 1, "at_ms": 10, "ids": [NEW]}, "ids",
     "has the wrong number of items"),
    ({"op": "split", "cue": CUE, "at_char": 1, "at_ms": 10, "ids": [NEW, f"../{SECRET}"]},
     "ids", "isn't valid"),
    ({"op": "merge_next", "cue": CUE, "id": "C0000000A", "joined": {}}, "id", "isn't valid"),
    ({"op": "merge_next", "cue": CUE, "id": NEW, "joined": [NEW2]}, "joined",
     "has the wrong type"),
    ({"op": "merge_next", "cue": CUE, "id": NEW, "joined": {SECRET: NEW2}}, "joined",
     "isn't one of the choices"),
    ({"op": "insert", "start_ms": 0, "end_ms": 900, "text": "x"}, "id", "is missing"),
    ({"op": "detach", "track": "en", "cue": CUE, "detached": "yes"}, "detached",
     "has the wrong type"),
    ({"op": "detach", "track": SECRET, "cue": CUE, "detached": True}, "track",
     "isn't one of the choices"),
    ({"op": "replace_all", "find": "", "replace": "x", "tracks": ["en"]}, "find",
     "is too short"),
    ({"op": "replace_all", "find": "a", "replace": "x", "tracks": []}, "tracks",
     "has the wrong number of items"),
    ({"op": "replace_all", "find": "a", "replace": "x", "tracks": ["source", SECRET]},
     "tracks", "isn't one of the choices"),
    ({"op": "glossary_add", "term": "工藤\n新一", "translation": "Kudo"}, "term",
     "isn't valid"),
    ({"op": "glossary_add", "term": "工藤", "translation": "   "}, "translation",
     "isn't valid"),
])
def test_a_bad_value_names_its_field_and_never_echoes_the_value(data, field, reason):
    with pytest.raises(BadOp) as err:
        ops.parse_op(data)
    assert str(err.value) == f"this edit can't be made: {field} {reason}"
    assert err.value.field == field and SECRET not in str(err.value)
    assert err.value.__cause__ is None and err.value.__context__ is None  # it quotes them


def test_set_times_needs_a_start_or_an_end():
    with pytest.raises(BadOp, match="this edit can't be made: set_times isn't valid"):
        ops.parse_op({"op": "set_times", "cue": CUE})


@pytest.mark.parametrize("text", ["a\ud800b", "nul\x00", "\x1b[31mred"])
def test_text_with_characters_that_cant_be_saved_is_refused(text):
    with pytest.raises(BadOp, match="text isn't valid"):
        ops.parse_op({"op": "set_text", "cue": CUE, "text": text})


def test_text_may_hold_line_breaks_tabs_and_bidi_marks():
    op = ops.parse_op({"op": "set_text", "cue": CUE, "text": "שלום\u200f\nline\ttwo"})
    assert op.text == "שלום\u200f\nline\ttwo"


def test_every_kind_of_edit_is_in_the_union():
    kinds = {k.model_fields["op"].default for k in ops.EDIT_KINDS}
    assert kinds == {"set_text", "set_translation_text", "set_times", "nudge", "split",
                     "merge_next", "insert", "delete", "detach", "replace_all", "glossary_add"}
