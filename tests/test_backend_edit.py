import time

import pytest
from episodes import LINES, make_episode, sid, source_cues, tid, write_track

from vid2sub import store
from vid2sub.cache import Cache
from vid2sub.config import Config
from vid2sub.engines.clients import KeyRing
from vid2sub.media.tools import Tools
from vid2sub.subs.edit import EditError
from vid2sub.subs.model import Cue
from vid2sub.web import backend as web_backend
from vid2sub.web import views
from vid2sub.web.backend import LocalBackend, OpenError
from vid2sub.web.ops import parse_op

pytestmark = pytest.mark.media
NEW = ("cc0000001", "cc0000002")  # new cues' ids, as the page draws them (Decision 31)


@pytest.fixture
def backend(tmp_path) -> LocalBackend:
    return LocalBackend(Config(), Tools.find(), KeyRing(environ={}),
                        Cache(tmp_path / "cache", max_bytes=10**9))


@pytest.fixture
def video(tmp_path):
    return make_episode(tmp_path / "show")


def op(**data):
    return parse_op(data)


def texts(cues) -> list[str]:
    return [c.text for c in cues]


def test_an_edit_returns_a_new_episode_and_leaves_the_old_one_as_it_was(backend, video):
    ep = backend.open(str(video))
    out = backend.apply(ep, op(op="set_text", cue=sid(0), text="こんばんは"))
    assert texts(out.tracks.source) == ["こんばんは", *LINES[1:]]
    assert texts(ep.tracks.source) == list(LINES) and ep.undo == []
    assert out.undo == [(ep.tracks, {})] and out.redo == [] and out.dirty
    assert out.base == ep.base and out.id == ep.id


@pytest.mark.parametrize("data, check", [
    ({"op": "set_translation_text", "track": "en", "cue": tid(1), "text": "How's it going?"},
     lambda t: "edited" in t.translations["en"][1].flags),
    ({"op": "set_times", "cue": sid(1), "end_ms": 6000},
     lambda t: t.source[1].end_ms == 6000 and t.translations["en"][1].end_ms == 6000),
    ({"op": "nudge", "cue": sid(2), "delta_ms": 500},
     lambda t: (t.source[2].start_ms, t.source[2].end_ms) == (7700, 10_700)),
    ({"op": "split", "cue": sid(2), "at_char": 3, "at_ms": 8000, "ids": list(NEW)},
     lambda t: texts(t.source)[2:] == ["はい、", "元気です"]),
    ({"op": "merge_next", "cue": sid(0), "id": NEW[0], "joined": {"en": NEW[1]}},
     lambda t: texts(t.source)[0] == "おはよう\n元気ですか" and len(t.translations["en"]) == 2),
    ({"op": "insert", "start_ms": 3100, "end_ms": 3500, "text": "えっ", "id": NEW[0]},
     lambda t: texts(t.source)[1] == "えっ"),
    ({"op": "delete", "cue": sid(1)},
     lambda t: texts(t.source) == [LINES[0], LINES[2]] and len(t.translations["en"]) == 2),
    ({"op": "detach", "track": "en", "cue": tid(0), "detached": True},
     lambda t: t.translations["en"][0].detached),
    ({"op": "replace_all", "find": "元気", "replace": "げんき", "tracks": ["source"]},
     lambda t: texts(t.source)[1:] == ["げんきですか", "はい、げんきです"]),
])
def test_every_kind_of_edit_runs_through_the_edit_rules(backend, video, data, check):
    ep = backend.open(str(video))
    out = backend.apply(ep, parse_op(data))
    assert check(out.tracks) and out.tracks != ep.tracks and len(out.undo) == 1


def test_a_new_cue_takes_the_id_the_page_proposes_and_one_already_used_is_refused(backend,
                                                                                  video):
    ep = backend.open(str(video))
    out = backend.apply(ep, op(op="split", cue=sid(0), at_char=2, at_ms=1500, ids=list(NEW)))
    halves = {c.id for c in out.tracks.source} - {c.id for c in ep.tracks.source}
    assert halves == set(NEW) and halves <= out.taken and not halves & ep.taken
    for used, on in ((NEW[0], out), (tid(0), ep)):  # one the tab made, one the sidecar has
        with pytest.raises(EditError, match="already in use"):
            backend.apply(on, op(op="insert", start_ms=3100, end_ms=3500, text="x", id=used))


def test_undo_and_redo_step_back_and_forward(backend, video):
    ep = backend.open(str(video))
    one = backend.apply(ep, op(op="set_text", cue=sid(0), text="一"))
    two = backend.apply(one, op(op="delete", cue=sid(2)))
    back = backend.undo(two)
    assert back.tracks == one.tracks and back.redo == [(two.tracks, {})]
    back = backend.undo(back)
    assert back.tracks == ep.tracks and not back.dirty and back.undo == []
    forward = backend.redo(backend.redo(back))
    assert forward.tracks == two.tracks and forward.redo == []


def test_a_new_edit_after_an_undo_drops_what_could_have_been_redone(backend, video):
    ep = backend.open(str(video))
    one = backend.undo(backend.apply(ep, op(op="set_text", cue=sid(0), text="一")))
    other = backend.apply(one, op(op="set_text", cue=sid(1), text="二"))
    assert other.redo == [] and len(other.undo) == 1


def test_undo_or_redo_with_nothing_to_step_to_changes_nothing(backend, video):
    ep = backend.open(str(video))
    assert backend.undo(ep) is ep and backend.redo(ep) is ep


def test_an_edit_that_changes_nothing_adds_no_undo_step(backend, video):
    ep = backend.open(str(video))
    assert backend.apply(ep, op(op="replace_all", find="zzz", replace="y",
                                tracks=["source", "en"])) is ep
    assert backend.apply(ep, op(op="set_text", cue=sid(0), text=f" {LINES[0]} ")) is ep


def test_undo_keeps_the_last_200_steps(backend, video):
    ep = backend.open(str(video))
    for k in range(web_backend.UNDO_STEPS + 5):
        ep = backend.apply(ep, op(op="set_text", cue=sid(0), text=f"台詞{k}"))
    assert len(ep.undo) == web_backend.UNDO_STEPS == 200
    assert ep.undo[0][0].source[0].text == "台詞4"


def test_an_edit_the_rules_refuse_says_why_and_changes_nothing(backend, video):
    ep = backend.open(str(video))
    with pytest.raises(EditError, match="delete it instead"):
        backend.apply(ep, op(op="set_text", cue=sid(0), text="  "))
    with pytest.raises(EditError, match="there is no zh-Hant track"):
        backend.apply(ep, op(op="detach", track="zh-Hant", cue=tid(0), detached=True))
    assert ep.undo == [] and ep.tracks == ep.base


def test_a_glossary_add_waits_for_save_and_can_be_undone(backend, video):
    ep = backend.open(str(video))
    out = backend.apply(ep, op(op="glossary_add", term=" 工藤新一 ", translation="Shinichi Kudo"))
    assert out.glossary_adds == {"工藤新一": "Shinichi Kudo"} and out.dirty
    assert out.tracks == ep.tracks
    assert backend.undo(out).glossary_adds == {} and not backend.undo(out).dirty


def test_a_track_in_conflict_cant_be_edited_until_a_version_is_picked(backend, video):
    head = store.load(video)[0].head("en").rendition
    for text in ("Mine", "Theirs"):
        write_track(video, "en", [Cue(id=tid(0), start_ms=0, end_ms=3000, text=text,
                                      src=(sid(0),))], role="translation", replaces=head)
    ep = backend.open(str(video))
    with pytest.raises(EditError, match="the en track has two versions: pick one"):
        backend.apply(ep, op(op="set_translation_text", track="en", cue=tid(0), text="x"))
    with pytest.raises(EditError, match="the en track has two versions: pick one"):
        backend.apply(ep, op(op="replace_all", find="M", replace="m", tracks=["source", "en"]))
    out = backend.apply(ep, op(op="set_text", cue=sid(0), text="こんばんは"))
    assert out.tracks.source[0].text == "こんばんは"


def test_nothing_but_a_glossary_add_can_be_made_while_the_source_is_in_conflict(backend, video):
    head = store.load(video)[0].head("ja").rendition
    write_track(video, "ja", source_cues(3)[:1], role="source", replaces=head)
    write_track(video, "ja", source_cues(3)[1:], role="source", replaces=head)
    ep = backend.open(str(video))
    for data in ({"op": "set_text", "cue": sid(0), "text": "x"},
                 {"op": "insert", "start_ms": 0, "end_ms": 900, "text": "x", "id": NEW[0]},
                 {"op": "detach", "track": "en", "cue": tid(0), "detached": True}):
        with pytest.raises(EditError, match="the ja track has two versions: pick one"):
            backend.apply(ep, parse_op(data))
    assert backend.apply(ep, op(op="glossary_add", term="工藤", translation="Kudo")).dirty


def test_a_closed_episode_cant_be_edited(backend, video):
    ep = backend.open(str(video))
    backend.close(ep.id)
    with pytest.raises(OpenError, match="closed"):
        backend.apply(ep, op(op="delete", cue=sid(0)))
    with pytest.raises(OpenError, match="closed"):
        backend.undo(ep)


def test_each_edit_on_a_two_hour_episode_and_its_new_view_take_well_under_a_second(backend,
                                                                                    tmp_path):
    ep = backend.open(str(make_episode(tmp_path / "long", n=2000)))
    edits = [{"op": "set_text", "cue": sid(1000), "text": "変更"},
             {"op": "nudge", "cue": sid(1000), "delta_ms": 100},
             {"op": "split", "cue": sid(10), "at_char": 2, "at_ms": 36_100, "ids": list(NEW)},
             {"op": "merge_next", "cue": sid(20), "id": "cc0000003",
              "joined": {"en": "cc0000004"}},
             {"op": "delete", "cue": sid(30)},
             {"op": "replace_all", "find": "台詞", "replace": "セリフ", "tracks": ["source"]},
             {"op": "set_translation_text", "track": "en", "cue": tid(5), "text": "x"}]
    for data in edits:
        began = time.perf_counter()
        ep = backend.apply(ep, parse_op(data))
        views.episode_view(ep, video_url=None, audio_url=None)
        elapsed = time.perf_counter() - began
        # Review Focus 3: about 0.02 s each where this was built; 1 s leaves CI room
        assert elapsed < 1.0, f"{data['op']}: {elapsed:.2f} s"
