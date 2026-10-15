import pytest

from vid2sub.subs.sidecar import (
    Conflict,
    Header,
    HeadRecord,
    IdentityRecord,
    ProjectionRecord,
    Sidecar,
    SidecarError,
    VideoInfo,
    make_rendition,
    parse_sidecar,
    serialize,
)

HEADER = Header(video=VideoInfo(name="Show.mkv", size=10, quick_sha256="ab", duration_ms=1000))
AT = "2026-10-14T12:00:00Z"


def head(track, rid, replaces=None, by="auto"):
    return HeadRecord(track=track, rendition=rid, replaces=replaces, by=by, at=AT)


def test_a_rendition_id_is_a_hash_of_its_content():
    a = make_rendition([], "en", {"x": 1})
    assert a.id.startswith("r_") and len(a.id) == 18
    assert make_rendition([], "en", {"x": 1}).id == a.id
    assert make_rendition([], "en", {"x": 2}).id != a.id
    assert make_rendition([a.id], "en", {"x": 1}).id != a.id


def test_a_sidecar_round_trips_through_jsonl():
    r = make_rendition([], "en", {"kind": "cues"})
    side = Sidecar(HEADER).add(r, head("en", r.id), IdentityRecord(sha256="ff", at=AT))
    text = serialize(side)
    assert text.endswith("\n") and text.count("\n") == 4
    again, warnings = parse_sidecar(text)
    assert again == side and warnings == []


def test_a_truncated_last_line_is_ignored_and_reported():
    r = make_rendition([], "en", {"kind": "cues"})
    text = serialize(Sidecar(HEADER).add(r)) + '{"type":"head","tra'
    side, warnings = parse_sidecar(text)
    assert list(side.renditions()) == [r.id]
    assert warnings == ["ignored a truncated last line"]


def test_a_broken_line_in_the_middle_refuses_the_whole_file():
    r = make_rendition([], "en", {"kind": "cues"})
    lines = serialize(Sidecar(HEADER).add(r)).splitlines()
    text = "\n".join([lines[0], "not json", lines[1]]) + "\n"
    with pytest.raises(SidecarError, match="line 2"):
        parse_sidecar(text)


def test_heads_follow_replacements_and_a_divergence_is_a_conflict():
    r1, r2, r3 = (make_rendition([], "en", {"n": i}) for i in range(3))
    side = Sidecar(HEADER).add(r1, r2, r3, head("en", r1.id), head("en", r2.id, r1.id, "editor"))
    assert side.head("en").rendition == r2.id
    diverged = side.add(head("en", r3.id, r1.id))
    result = diverged.head("en")
    assert isinstance(result, Conflict) and set(result.leaves) == {r2.id, r3.id}
    assert side.head("ja") is None


def test_adding_the_same_record_twice_keeps_one():
    r = make_rendition([], "en", {"n": 1})
    side = Sidecar(HEADER).add(r).add(r)
    assert len(side.records) == 1


def test_the_latest_projection_per_file_wins():
    p1 = ProjectionRecord(path="Show.en.srt", format="srt", track="en", rendition="r_1",
                          sha256="a", at=AT)
    p2 = p1.model_copy(update={"sha256": "b", "rendition": "r_2"})
    assert Sidecar(HEADER).add(p1, p2).projections()["Show.en.srt"].sha256 == "b"


def test_a_replacement_cycle_is_a_conflict_not_a_file_order_guess():
    x, y = (make_rendition([], "en", {"n": i}) for i in range(2))
    side = Sidecar(HEADER).add(x, y, head("en", x.id), head("en", y.id, x.id),
                               head("en", x.id, y.id, "user"))
    result = side.head("en")
    assert isinstance(result, Conflict) and set(result.leaves) == {x.id, y.id}
