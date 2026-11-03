import os
import sys
import threading

import pytest

from vid2sub import security, store
from vid2sub.media.identity import VideoIdentity
from vid2sub.security import WriteRefused
from vid2sub.subs.formats import to_srt
from vid2sub.subs.model import Cue
from vid2sub.subs.rendition import cues_body
from vid2sub.subs.sidecar import (
    Conflict,
    HeadRecord,
    Sidecar,
    SidecarError,
    make_rendition,
    parse_sidecar,
    serialize,
)

CUES = [Cue(id="c1", start_ms=0, end_ms=1500, text="Hello"),
        Cue(id="c2", start_ms=2000, end_ms=3500, text="World")]


@pytest.fixture
def video(tmp_path):
    v = tmp_path / "Show - S01E02.mkv"
    v.write_bytes(b"video")
    return v


def header(video):
    return store.header_for(video, VideoIdentity(size=5, quick_sha256="ab"), 10_000)


def with_track(video, cues=CUES, track="en", role="source", by="auto"):
    body = cues_body(cues, language="en", script=None, engine="vid2sub", model=None,
                     version="v1", created_at=store.now(), inputs={}, meta={"role": role})
    rec = make_rendition([], track, body)
    side, _ = store.load(video)
    head = store.head_record(side or store.append(video, header(video), []), track, rec.id, by)
    return store.append(video, header(video), [rec, head])


def test_append_creates_the_sidecar_and_adds_records(video):
    side = with_track(video)
    text = store.sidecar_path(video).read_text(encoding="utf-8")
    assert parse_sidecar(text)[0] == side
    assert store.source_track(side) == "en"


def test_a_sidecar_vid2sub_cant_read_is_never_overwritten(video):
    path = store.sidecar_path(video)
    path.write_text("not a sidecar\n")
    with pytest.raises(SidecarError):
        store.append(video, header(video), [])
    assert path.read_text() == "not a sidecar\n"


def test_a_concurrent_writer_is_merged_not_lost(video, monkeypatch):
    with_track(video)
    other = make_rendition([], "ja", {"kind": "cues"})
    real = store.serialize
    calls = []

    def racing(sidecar):
        if not calls:
            calls.append(1)
            path = store.sidecar_path(video)
            path.write_text(path.read_text(encoding="utf-8")
                            + real(sidecar.__class__(sidecar.header, (other,)))
                            .splitlines()[1] + "\n", encoding="utf-8")
        return real(sidecar)

    monkeypatch.setattr(store, "serialize", racing)
    mine = make_rendition([], "en", {"kind": "cues", "n": 2})
    side = store.append(video, header(video), [mine])
    assert other.id in side.renditions() and mine.id in side.renditions()


def test_a_writer_that_replaces_the_sidecar_while_the_temporary_file_is_written_loses_nothing(
        video, monkeypatch):
    with_track(video)
    other = make_rendition([], "ja", {"kind": "cues"})
    path, real_fsync, calls = store.sidecar_path(video), os.fsync, []

    def racing(fd):  # another process writes the sidecar after the re-read M1 did, before ours
        if not calls:  # is renamed into place
            calls.append(1)
            side, _ = store.load(video)
            path.write_text(serialize(side.add(other)), encoding="utf-8")
        real_fsync(fd)

    monkeypatch.setattr(security.os, "fsync", racing)
    mine = make_rendition([], "en", {"kind": "cues", "n": 2})
    side = store.append(video, header(video), [mine])
    assert other.id in side.renditions() and mine.id in side.renditions()
    assert side == store.load(video)[0]


def test_a_sidecar_another_writer_makes_after_vid2sub_found_none_is_merged(video, monkeypatch):
    other = make_rendition([], "ja", {"kind": "cues"})
    real, calls = store.serialize, []

    def racing(sidecar):  # another process makes the sidecar after vid2sub looked for it
        if not calls:
            calls.append(1)
            store.sidecar_path(video).write_text(real(Sidecar(header(video), (other,))),
                                                 encoding="utf-8")
        return real(sidecar)

    monkeypatch.setattr(store, "serialize", racing)
    mine = make_rendition([], "en", {"kind": "cues", "n": 2})
    side = store.append(video, header(video), [mine])
    assert other.id in side.renditions() and mine.id in side.renditions()


def test_a_sidecar_read_before_another_writers_save_is_read_again_and_nothing_is_adopted(video):
    side = with_track(video)
    stale, path, _ = store.project(video, header(video), side, "en", "srt",
                                   overwrite_foreign=False)
    # meanwhile another writer (the editor's Save) puts a newer version and writes its file
    side = with_track(video, cues=[CUES[0], CUES[1].model_copy(update={"text": "Planet"})])
    store.project(video, header(video), side, "en", "srt", overwrite_foreign=False)
    now, _ = store.load(video)
    side, changed = store.check_external(video, header(video), stale)
    assert changed == [] and side == now  # its file is no outside edit
    side, _, written = store.project(video, header(video), stale, "en", "srt",
                                     overwrite_foreign=False)
    assert not written and side == now and "Planet" in path.read_text(encoding="utf-8")


def locked_elsewhere(video) -> bool:
    """Whether another thread would have to wait for the video's sidecar lock just now."""
    got: list[bool] = []

    def try_it() -> None:
        lock = store.write_lock(video)
        got.append(lock.acquire(blocking=False))
        if got[0]:
            lock.release()

    other = threading.Thread(target=try_it)
    other.start()
    other.join()
    return not got[0]


def test_a_projection_holds_the_sidecars_write_lock_while_it_writes(video, monkeypatch):
    side = with_track(video)
    real, held = security._replace, []

    def watched(src, dst, **kwargs):
        held.append((dst.name, locked_elsewhere(video)))
        real(src, dst, **kwargs)

    monkeypatch.setattr(security, "_replace", watched)
    store.project(video, header(video), side, "en", "srt", overwrite_foreign=False)
    assert held == [(store.sidecar_path(video).name, True), ("Show - S01E02.en.srt", True)]


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges on Windows")
def test_two_spellings_of_one_sidecar_share_its_write_lock(tmp_path):
    folder = tmp_path / "Show"
    folder.mkdir()
    (tmp_path / "linked").symlink_to(folder, target_is_directory=True)
    lock = store.write_lock(folder / "Show - S01E01.mkv")
    assert store.write_lock(tmp_path / "linked" / "Show - S01E01.mkv") is lock
    assert store.write_lock(folder / "SHOW - s01e01.mkv") is lock  # a case-insensitive volume's
    assert store.write_lock(folder / "Show - S01E02.mkv") is not lock


def test_an_auto_version_never_replaces_a_persons(video):
    side = with_track(video, by="editor")
    assert store.head_record(side, "en", "r_new", "auto") is None
    assert store.head_record(side, "en", "r_new", "auto", replace_person=True) is not None
    assert store.head_record(side, "en", "r_new", "editor").replaces == side.head("en").rendition


def test_projecting_writes_lf_srt_and_records_its_hash_first(video):
    side = with_track(video)
    side, path, written = store.project(video, header(video), side, "en", "srt",
                                        overwrite_foreign=False)
    assert written and path.name == "Show - S01E02.en.srt"
    assert path.read_bytes() == to_srt(CUES)
    assert side.projections()[path.name].sha256 == store.sha256_hex(path.read_bytes())
    _, _, again = store.project(video, header(video), side, "en", "srt", overwrite_foreign=False)
    assert not again


def test_someone_elses_subtitle_file_is_never_overwritten(video):
    side = with_track(video)
    theirs = video.with_name("Show - S01E02.en.srt")
    theirs.write_text("1\n00:00:00,000 --> 00:00:01,000\nBazarr\n")
    with pytest.raises(store.ForeignFile):
        store.project(video, header(video), side, "en", "srt", overwrite_foreign=False)
    assert "Bazarr" in theirs.read_text()
    store.project(video, header(video), side, "en", "srt", overwrite_foreign=True)
    assert "Hello" in theirs.read_text()


def test_a_file_edited_since_vid2sub_wrote_it_is_never_overwritten(video):
    side = with_track(video)
    side, path, _ = store.project(video, header(video), side, "en", "srt",
                                  overwrite_foreign=False)
    edited = path.read_bytes().replace(b"World", b"Earth")
    path.write_bytes(edited)
    with pytest.raises(store.EditedOnDisk):
        store.project(video, header(video), side, "en", "srt", overwrite_foreign=False)
    with pytest.raises(store.EditedOnDisk):
        store.project(video, header(video), side, "en", "srt", overwrite_foreign=True)
    assert path.read_bytes() == edited
    side, _ = store.check_external(video, header(video), side)
    store.project(video, header(video), side, "en", "srt", overwrite_foreign=False)
    assert b"Earth" in path.read_bytes()


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges on Windows")
def test_a_symlink_where_the_subtitle_goes_is_refused(video, tmp_path):
    side = with_track(video)
    target = tmp_path / "elsewhere.txt"
    target.write_text("precious")
    video.with_name("Show - S01E02.en.srt").symlink_to(target)
    with pytest.raises(WriteRefused):
        store.project(video, header(video), side, "en", "srt", overwrite_foreign=True)
    assert target.read_text() == "precious"


def test_an_edit_made_in_another_editor_comes_back_as_an_external_version(video):
    side = with_track(video)
    side, path, _ = store.project(video, header(video), side, "en", "srt",
                                  overwrite_foreign=False)
    path.write_bytes(path.read_bytes().replace(b"World", b"Earth"))
    side, changed = store.check_external(video, header(video), side)
    assert changed == ["en"]
    head = side.head("en")
    assert isinstance(head, HeadRecord) and head.by == "external"
    _, cues = store.current_cues(side, "en")
    assert [c.id for c in cues] == ["c1", "c2"] and cues[1].text == "Earth"
    assert "edited" in cues[1].flags
    _, changed_again = store.check_external(video, header(video), side)
    assert changed_again == []


def test_importing_a_legacy_encoded_srt_makes_it_the_source(video, tmp_path):
    sub = tmp_path / "fansub.srt"
    lines = ["今天天气很好，我们去公园吧。", "明天也是好天气，我们再去吧。",
             "公园里有很多人在散步和跑步。", "我们一起去吃午饭，然后回家休息。"]
    sub.write_bytes("".join(f"{i}\n00:00:0{i},000 --> 00:00:0{i},900\n{line}\n\n"
                            for i, line in enumerate(lines, 1)).encode("gbk"))
    side = store.import_subtitles(video, header(video), sub, "zh-Hans", role="source")
    assert store.source_track(side) == "zh-Hans"
    head = side.head("zh-Hans")
    assert head.by == "import"
    _, cues = store.current_cues(side, "zh-Hans")
    assert cues[0].text.startswith("今天")


def test_overlapping_imported_cues_are_clamped():
    out = store.normalise_track([Cue(id="a", start_ms=0, end_ms=2000, text="x"),
                                 Cue(id="b", start_ms=1000, end_ms=3000, text="y"),
                                 Cue(id="c", start_ms=3000, end_ms=3000, text="z")])
    assert [(c.id, c.start_ms, c.end_ms) for c in out] == [("a", 0, 1000), ("b", 1000, 3000)]


def two_projected_tracks(video):
    with_track(video, track="en")
    with_track(video, track="ja")
    side, _ = store.load(video)
    paths = {}
    for track in ("en", "ja"):
        side, paths[track], _ = store.project(video, header(video), side, track, "srt",
                                              overwrite_foreign=False)
    return side, paths


@pytest.mark.parametrize("junk", [b"\x00garbage", b""])
def test_an_unreadable_or_emptied_file_is_skipped_and_reported(video, junk):
    side, paths = two_projected_tracks(video)
    head_before = side.head("ja")
    paths["en"].write_bytes(paths["en"].read_bytes().replace(b"World", b"Earth"))
    paths["ja"].write_bytes(junk)
    seen = []
    side, changed = store.check_external(video, header(video), side, on_unreadable=seen.append)
    assert changed == ["en"]
    assert seen == [paths["ja"].name]
    assert paths["ja"].read_bytes() == junk
    assert side.head("ja") == head_before
    with pytest.raises(store.EditedOnDisk):
        store.project(video, header(video), side, "ja", "srt", overwrite_foreign=True)


def test_two_edited_files_of_one_track_chain_instead_of_conflicting(video):
    side = with_track(video)
    paths = []
    for fmt in ("srt", "ass"):
        side, path, _ = store.project(video, header(video), side, "en", fmt,
                                      overwrite_foreign=False)
        paths.append(path)
    srt, ass = paths
    srt.write_bytes(srt.read_bytes().replace(b"World", b"Earth"))
    ass.write_bytes(ass.read_bytes().replace(b"Hello", b"Howdy"))
    before = set(side.renditions())
    side, changed = store.check_external(video, header(video), side)
    assert changed == ["en", "en"]
    assert isinstance(side.head("en"), HeadRecord)
    assert len(set(side.renditions()) - before) == 2


# final review 2: a person's ASS work is never wiped or turned into dialogue


def test_a_restyled_ass_of_the_current_version_is_not_rewritten(video):
    side = with_track(video)
    side, path, _ = store.project(video, header(video), side, "en", "ass",
                                  overwrite_foreign=False)
    text = path.read_text(encoding="utf-8")
    assert ",,Hello" in text
    path.write_text(text.replace(",,Hello", ",,{\\an8}Hello"), encoding="utf-8")
    side, changed = store.check_external(video, header(video), side)
    assert changed == []
    side, _, written = store.project(video, header(video), side, "en", "ass",
                                     overwrite_foreign=False)
    assert not written
    assert "{\\an8}Hello" in path.read_text(encoding="utf-8")


def add_sign(path, text="TOKYO STATION"):
    import pysubs2
    subs = pysubs2.SSAFile.from_string(path.read_text(encoding="utf-8"), format_="ass")
    subs.styles["Sign"] = pysubs2.SSAStyle(fontname="Arial", fontsize=40,
                                           alignment=pysubs2.Alignment.TOP_CENTER)
    subs.append(pysubs2.SSAEvent(start=500, end=1200, style="Sign", text=text))
    path.write_text(subs.to_string("ass"), encoding="utf-8")


def test_a_sign_added_in_aegisub_stays_a_sign_and_never_becomes_dialogue(video):
    side = with_track(video)
    paths = {}
    for fmt in ("srt", "ass"):
        side, paths[fmt], _ = store.project(video, header(video), side, "en", fmt,
                                            overwrite_foreign=False)
    add_sign(paths["ass"])
    before = set(side.renditions())
    head = side.head("en")
    side, changed = store.check_external(video, header(video), side)
    assert changed == []
    assert set(side.renditions()) == before and side.head("en") == head
    for fmt in ("srt", "ass"):
        side, _, _ = store.project(video, header(video), side, "en", fmt,
                                   overwrite_foreign=False)
    assert "TOKYO" not in paths["srt"].read_text(encoding="utf-8")
    assert paths["ass"].read_text(encoding="utf-8").count("TOKYO STATION") == 1


def test_an_edited_dialogue_line_next_to_a_sign_is_still_an_outside_edit(video):
    side = with_track(video)
    side, path, _ = store.project(video, header(video), side, "en", "ass",
                                  overwrite_foreign=False)
    add_sign(path)
    path.write_text(path.read_text(encoding="utf-8").replace(",,World", ",,Earth"),
                    encoding="utf-8")
    side, changed = store.check_external(video, header(video), side)
    assert changed == ["en"]
    _, cues = store.current_cues(side, "en")
    assert [c.text for c in cues] == ["Hello", "Earth"]


# final review 3: a file vid2sub was writing when interrupted is not "your outside edit"


def test_a_write_interrupted_after_its_record_is_not_taken_for_an_outside_edit(video,
                                                                               monkeypatch):
    side = with_track(video)
    side, path, _ = store.project(video, header(video), side, "en", "srt",
                                  overwrite_foreign=False)
    old = path.read_bytes()
    newer = [CUES[0], CUES[1].model_copy(update={"text": "Planet"})]
    side = with_track(video, cues=newer)
    real = store.safe_write

    def full_disk(target, data, **kwargs):
        if target == path:
            raise OSError(28, "No space left on device")
        return real(target, data, **kwargs)

    monkeypatch.setattr(store, "safe_write", full_disk)
    with pytest.raises(OSError):
        store.project(video, header(video), side, "en", "srt", overwrite_foreign=False)
    monkeypatch.setattr(store, "safe_write", real)
    assert path.read_bytes() == old
    side, _ = store.load(video)
    assert side.projections()[path.name].sha256 == store.sha256_hex(old)  # what the file holds
    before, head = set(side.renditions()), side.head("en")
    side, changed = store.check_external(video, header(video), side)
    assert changed == []
    assert set(side.renditions()) == before and side.head("en") == head
    side, _, written = store.project(video, header(video), side, "en", "srt",
                                     overwrite_foreign=False)
    assert written and b"Planet" in path.read_bytes()


def test_every_digest_ever_projected_for_a_file_is_known(video):
    side = with_track(video)
    side, path, _ = store.project(video, header(video), side, "en", "srt",
                                  overwrite_foreign=False)
    first = store.sha256_hex(path.read_bytes())
    side = with_track(video, cues=[CUES[0]])
    side, _, _ = store.project(video, header(video), side, "en", "srt", overwrite_foreign=False)
    second = store.sha256_hex(path.read_bytes())
    assert store.projected_digests(side, path.name) == {first, second}
    assert store.projected_digests(side, "other.srt") == set()


# Phase 2, Task 6: an outside edit to a file written from an older version diverges (spec §14.4)


def newer_head(video, side):
    """A newer version of en that becomes the head without being written to the file."""
    projected = side.head("en").rendition
    body = cues_body([CUES[0], CUES[1].model_copy(update={"text": "Planet"})], language="en",
                     script=None, engine="editor", model=None, version="e",
                     created_at=store.now(), inputs={}, meta={"role": "source"})
    rec = make_rendition([projected], "en", body)
    side = store.append(video, header(video), [rec, HeadRecord(
        track="en", rendition=rec.id, replaces=projected, by="editor", at=store.now())])
    return side, rec.id


def test_an_outside_edit_to_a_file_from_an_older_version_diverges_from_the_head(video):
    side = with_track(video)
    side, path, _ = store.project(video, header(video), side, "en", "srt",
                                  overwrite_foreign=False)
    side, newer = newer_head(video, side)
    path.write_bytes(path.read_bytes().replace(b"World", b"Earth"))
    side, changed = store.check_external(video, header(video), side)
    assert changed == ["en"]
    head = side.head("en")
    assert isinstance(head, Conflict)
    (external,) = [r for r in head.leaves if r != newer]
    assert newer in head.leaves and side.renditions()[external].body["engine"] == "external"


def test_a_failed_write_leaves_the_file_counted_as_the_version_it_still_holds(video,
                                                                             monkeypatch):
    side = with_track(video)
    side, path, _ = store.project(video, header(video), side, "en", "srt",
                                  overwrite_foreign=False)
    written = side.projections()[path.name]
    side, newer = newer_head(video, side)
    real = store.safe_write

    def full_disk(target, data, **kwargs):
        if target == path:
            raise OSError(28, "No space left on device")
        return real(target, data, **kwargs)

    monkeypatch.setattr(store, "safe_write", full_disk)
    with pytest.raises(OSError):
        store.project(video, header(video), side, "en", "srt", overwrite_foreign=False)
    monkeypatch.setattr(store, "safe_write", real)
    side, _ = store.load(video)
    latest = side.projections()[path.name]
    assert (latest.rendition, latest.sha256) == (written.rendition, written.sha256)
    path.write_bytes(path.read_bytes().replace(b"World", b"Earth"))
    side, _ = store.check_external(video, header(video), side)
    assert isinstance(side.head("en"), Conflict) and newer in side.head("en").leaves
