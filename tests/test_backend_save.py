import sys
import threading

import pytest
from episodes import (
    make_episode,
    sid,
    source_cues,
    tid,
    transcript_for,
    translation_cues,
    write_track,
)
from fakes import fake_make_ask

from vid2sub import __version__, pipeline, security, store
from vid2sub.cache import Cache
from vid2sub.config import Config, Endpoint, ModelEntry
from vid2sub.engines.clients import KeyRing
from vid2sub.media.tools import Tools
from vid2sub.subs.formats import sha256_hex, to_srt
from vid2sub.subs.glossary import parse_glossary
from vid2sub.subs.model import Cue
from vid2sub.subs.rendition import cues_body, cues_from_body
from vid2sub.subs.sidecar import (
    Conflict,
    HeadRecord,
    ProjectionRecord,
    RenditionRecord,
    Sidecar,
    make_rendition,
)
from vid2sub.web.backend import LocalBackend, OpenError, SaveError, SaveResult
from vid2sub.web.ops import parse_op

pytestmark = pytest.mark.media
JA, EN = "Show - S01E01.ja.srt", "Show - S01E01.en.srt"
GLOSSARY = "vid2sub.glossary.toml"
BAZARR = b"1\n00:00:00,000 --> 00:00:01,000\nBazarr's line\n"


@pytest.fixture
def backend(tmp_path) -> LocalBackend:
    return LocalBackend(Config(), Tools.find(), KeyRing(environ={}),
                        Cache(tmp_path / "cache", max_bytes=10**9))


@pytest.fixture
def video(tmp_path):
    return make_episode(tmp_path / "show")


def edit(backend, ep, **data):
    return backend.apply(ep, parse_op(data))


def added_since(video, before: Sidecar) -> list:
    side, _ = store.load(video)
    return list(side.records[len(before.records):])


def leaf_texts(video, track: str) -> list[tuple[str, str]]:
    """Each diverged version of `track`: its engine and its first cue's text, sorted."""
    side, _ = store.load(video)
    head = side.head(track)
    assert isinstance(head, Conflict)
    bodies = [side.renditions()[r].body for r in head.leaves]
    return sorted((b["engine"], cues_from_body(b)[0].text) for b in bodies)


def cli_translate(video, monkeypatch) -> None:
    """`vid2sub translate` (not --stale-only) on the episode: M1's own pipeline, faked model."""
    monkeypatch.setattr(pipeline, "make_ask", fake_make_ask)
    config = Config(endpoints={"spark": Endpoint(base_url="http://127.0.0.1:9/v1")},
                    models={"gemma": ModelEntry(catalog="gemma-4-26b-a4b", endpoint="spark",
                                                model="gemma", task="translate", local=True)})
    ctx = pipeline.RunContext(config=config, tools=Tools.find(), keys=KeyRing(environ={}),
                              options=pipeline.RunOptions(targets=["en"], translate_model="gemma"))
    result = pipeline.translate_one(str(video), ctx, fresh=True)
    assert result.status == "done", (result.reason, result.hint)


def conflicted(video, track: str = "en") -> None:
    """Two writers each replace the track's head: it diverges."""
    head = store.load(video)[0].head(track).rendition
    for text in ("Mine", "Theirs"):
        write_track(video, track, [Cue(id=tid(0), start_ms=0, end_ms=3000, text=text,
                                       src=(sid(0),))], role="translation", replaces=head)


# S29: what a Save writes (spec §14.5)


def test_a_save_appends_a_version_and_a_head_per_changed_track_then_rewrites_its_files(backend,
                                                                                       video):
    ep = backend.open(str(video))
    before, _ = store.load(video)
    ep = edit(backend, ep, op="set_text", cue=sid(0), text="こんばんは")
    ep = edit(backend, ep, op="set_translation_text", track="en", cue=tid(1),
              text="How have you been?")
    saved, result = backend.save(ep, formats=["srt"])
    assert result == SaveResult(written=(JA, EN), foreign=(), conflicts=(), notes=())
    added = added_since(video, before)
    versions = [r for r in added if isinstance(r, RenditionRecord)]
    heads = [r for r in added if isinstance(r, HeadRecord)]
    projections = [r for r in added if isinstance(r, ProjectionRecord)]
    assert [(r.track, r.parents, r.body["engine"]) for r in versions] == [
        ("ja", (ep.heads["ja"],), "editor"), ("en", (ep.heads["en"],), "editor")]
    assert [(h.track, h.rendition, h.replaces, h.by) for h in heads] == [
        ("ja", versions[0].id, ep.heads["ja"], "editor"),
        ("en", versions[1].id, ep.heads["en"], "editor")]
    assert added.index(heads[-1]) < added.index(projections[0])
    assert [p.path for p in projections] == [JA, EN]
    for p in projections:
        assert p.sha256 == sha256_hex(video.with_name(p.path).read_bytes())
    assert video.with_name(JA).read_bytes() == to_srt(saved.tracks.source)
    assert "How have you been?" in video.with_name(EN).read_text(encoding="utf-8")


def test_an_editor_version_keeps_its_tracks_language_role_model_and_glossary_hash(backend, video):
    side, _ = store.load(video)
    head = side.head("en").rendition
    body = cues_body(translation_cues(source_cues(3)), language="en", script=None,
                     engine="translate:gemma", model="gemma", version="g", created_at=store.now(),
                     inputs={}, meta={"role": "translation"}, glossary_sha="abcd1234")
    rec = make_rendition([head], "en", body)
    store.append(video, side.header, [rec, HeadRecord(track="en", rendition=rec.id,
                                                      replaces=head, by="auto", at=store.now())])
    ep = edit(backend, backend.open(str(video)), op="set_text", cue=sid(0), text="こんばんは")
    ep = edit(backend, ep, op="set_translation_text", track="en", cue=tid(0), text="Evening")
    saved, _ = backend.save(ep, formats=["srt"])
    renditions = store.load(video)[0].renditions()
    ja, en = renditions[saved.heads["ja"]].body, renditions[saved.heads["en"]].body
    assert (ja["payload"]["language"], ja["meta"], ja["model"]) == ("ja", {"role": "source"}, None)
    assert (en["payload"]["language"], en["meta"], en["model"]) == (
        "en", {"role": "translation"}, "gemma")
    assert en["payload"]["glossary_sha"] == "abcd1234" and "glossary_sha" not in ja["payload"]
    assert en["inputs"] == {"source": saved.heads["ja"]} and ja["inputs"] == {}
    assert ja["version"] == en["version"] == f"editor@{__version__}"


def test_after_a_save_the_episode_is_clean_and_the_next_save_builds_on_it(backend, video):
    ep = edit(backend, backend.open(str(video)), op="set_text", cue=sid(0), text="一")
    saved, _ = backend.save(ep, formats=["srt"])
    side, _ = store.load(video)
    assert not saved.dirty and saved.undo == [] and saved.redo == []
    assert saved.heads["ja"] == side.head("ja").rendition != ep.heads["ja"]
    assert saved.base == saved.tracks == ep.tracks and saved.sidecar == side
    again, result = backend.save(edit(backend, saved, op="set_text", cue=sid(0), text="二"),
                                 formats=["srt"])
    head = store.load(video)[0].head("ja")
    assert isinstance(head, HeadRecord) and head.replaces == saved.heads["ja"]
    assert result.conflicts == () and again.tracks.source[0].text == "二"


def test_srt_is_always_written_and_ass_when_asked_for(backend, video):
    ep = edit(backend, backend.open(str(video)), op="set_text", cue=sid(0), text="一")
    _, result = backend.save(ep, formats=["ass"])
    assert result.written == (JA, "Show - S01E01.ja.ass", "Show - S01E01.en.ass")


def test_a_save_with_nothing_changed_writes_back_a_missing_file_and_no_version(backend, video):
    video.with_name(EN).unlink()
    ep = backend.open(str(video))
    before, _ = store.load(video)
    _, result = backend.save(ep, formats=["srt"])
    assert result.written == (EN,)
    assert all(isinstance(r, ProjectionRecord) for r in added_since(video, before))


# Never overwrite an artifact (spec §6.6, §15.3)


def test_someone_elses_subtitle_file_is_never_overwritten(backend, tmp_path):
    video = make_episode(tmp_path / "show", project=("en",))
    theirs = video.with_name(JA)
    theirs.write_bytes(BAZARR)
    ep = edit(backend, backend.open(str(video)), op="set_text", cue=sid(0), text="こんばんは")
    saved, result = backend.save(ep, formats=["srt"])
    assert result.foreign == (JA,) and result.written == ()
    assert theirs.read_bytes() == BAZARR
    assert store.load(video)[0].head("ja").rendition == saved.heads["ja"] != ep.heads["ja"]


def test_a_file_changed_outside_since_the_episode_opened_is_kept_and_both_versions_wait(backend,
                                                                                       video):
    ep = backend.open(str(video))
    srt = video.with_name(EN)
    outside = srt.read_bytes().replace(b"How are you?", b"How do you do?")
    srt.write_bytes(outside)
    ep = edit(backend, ep, op="set_translation_text", track="en", cue=tid(0), text="Morning!")
    saved, result = backend.save(ep, formats=["srt"])
    assert result.conflicts == ("en",) and result.notes == ("kept your outside edit to en",)
    assert srt.read_bytes() == outside
    assert leaf_texts(video, "en") == [("editor", "Morning!"), ("external", "Good morning")]
    reopened = backend.open(str(video))
    assert reopened.conflicts == saved.conflicts and reopened.notes == []


def test_an_outside_edit_to_another_track_is_kept_at_save_and_the_save_says_so(backend, video):
    ep = backend.open(str(video))
    srt = video.with_name(JA)
    srt.write_bytes(srt.read_bytes().replace("おはよう".encode(), "おっす".encode()))
    ep = edit(backend, ep, op="set_translation_text", track="en", cue=tid(0), text="Morning!")
    saved, result = backend.save(ep, formats=["srt"])
    assert result.conflicts == () and result.notes == ("kept your outside edit to ja",)
    assert saved.tracks.source[0].text == "おっす"
    assert saved.tracks.translations["en"][0].text == "Morning!"


# Never lose a concurrent writer's records; a diverged track waits for a person (spec §14.4, §14.6)


def test_a_cli_translation_made_while_the_episode_was_open_survives_and_both_are_kept(
        backend, video, monkeypatch):
    ep = edit(backend, backend.open(str(video)), op="set_translation_text", track="en",
              cue=tid(0), text="Morning!")
    cli_translate(video, monkeypatch)
    cli_file = video.with_name(EN).read_bytes()
    saved, result = backend.save(ep, formats=["srt"])
    assert result.conflicts == ("en",) and result.written == ()
    assert leaf_texts(video, "en") == [("editor", "Morning!"), ("translate:gemma", f"EN {sid(0)}")]
    assert video.with_name(EN).read_bytes() == cli_file
    side, _ = store.load(video)
    assert saved.conflicts == {"en": side.head("en").leaves}
    assert "en" not in saved.tracks.translations and "en" not in saved.heads
    assert not [h for h in side.heads("en") if h.by == "user"]


def test_a_cli_change_to_another_track_and_the_editors_save_both_land(backend, video, monkeypatch):
    ep = edit(backend, backend.open(str(video)), op="set_text", cue=sid(0), text="こんばんは")
    cli_translate(video, monkeypatch)
    saved, result = backend.save(ep, formats=["srt"])
    side, _ = store.load(video)
    assert result.conflicts == () and result.written == (JA,)
    assert side.head("ja").by == "editor" and side.head("en").by == "auto"
    assert saved.tracks.source[0].text == "こんばんは"
    assert saved.tracks.translations["en"][0].text == f"EN {sid(0)}"


def test_two_tabs_saving_one_track_keep_both_versions_and_the_second_sees_the_conflict(backend,
                                                                                      video):
    a = edit(backend, backend.open(str(video)), op="set_translation_text", track="en",
             cue=tid(0), text="From tab A")
    b = edit(backend, backend.open(str(video)), op="set_translation_text", track="en",
             cue=tid(0), text="From tab B")
    _, first = backend.save(a, formats=["srt"])
    b_saved, second = backend.save(b, formats=["srt"])
    assert first.conflicts == () and first.written == (EN,)
    assert second.conflicts == ("en",) and "en" in b_saved.conflicts
    assert leaf_texts(video, "en") == [("editor", "From tab A"), ("editor", "From tab B")]
    assert "From tab A" in video.with_name(EN).read_text(encoding="utf-8")


def test_two_tabs_saving_different_tracks_both_land_without_a_conflict(backend, video):
    a = edit(backend, backend.open(str(video)), op="set_text", cue=sid(0), text="こんばんは")
    b = edit(backend, backend.open(str(video)), op="set_translation_text", track="en",
             cue=tid(1), text="From tab B")
    backend.save(a, formats=["srt"])
    b_saved, result = backend.save(b, formats=["srt"])
    side, _ = store.load(video)
    assert result.conflicts == () and isinstance(side.head("en"), HeadRecord)
    assert b_saved.tracks.source[0].text == "こんばんは"
    assert b_saved.tracks.translations["en"][1].text == "From tab B"


def test_a_save_never_moves_the_head_of_a_track_already_in_conflict(backend, video):
    conflicted(video)
    ep = backend.open(str(video))
    leaves = ep.conflicts["en"]
    en_file = video.with_name(EN).read_bytes()
    before, _ = store.load(video)
    _, result = backend.save(edit(backend, ep, op="set_text", cue=sid(0), text="こんばんは"),
                             formats=["srt"])
    assert store.load(video)[0].head("en") == Conflict("en", leaves)
    assert not [r for r in added_since(video, before) if getattr(r, "track", None) == "en"]
    assert result.written == (JA,) and result.conflicts == ("en",)
    assert video.with_name(EN).read_bytes() == en_file


# Picking a version (spec §14.4)


def test_picking_a_version_makes_it_the_head_writes_its_files_and_loads_it(backend, video,
                                                                          monkeypatch):
    ep = edit(backend, backend.open(str(video)), op="set_translation_text", track="en",
              cue=tid(0), text="Morning!")
    cli_translate(video, monkeypatch)
    saved, _ = backend.save(ep, formats=["srt"])
    renditions = store.load(video)[0].renditions()
    mine, theirs = sorted(saved.conflicts["en"],
                          key=lambda r: renditions[r].body["engine"] != "editor")
    picked, result = backend.resolve(saved, "en", mine)
    side, _ = store.load(video)
    assert side.head("en").rendition == mine and side.head("en").by == "user"
    assert [(h.rendition, h.replaces) for h in side.heads("en") if h.by == "user"] == [
        (mine, theirs)]
    assert result == SaveResult(written=(EN,), foreign=(), conflicts=(), notes=())
    assert "Morning!" in video.with_name(EN).read_text(encoding="utf-8")
    assert picked.conflicts == {} and picked.heads["en"] == mine and not picked.dirty
    assert picked.tracks.translations["en"][0].text == "Morning!"


def test_picking_a_version_keeps_the_unsaved_edits_on_other_tracks(backend, video):
    conflicted(video)
    ep = edit(backend, backend.open(str(video)), op="set_text", cue=sid(0), text="こんばんは")
    picked, _ = backend.resolve(ep, "en", ep.conflicts["en"][1])
    assert picked.tracks.source[0].text == "こんばんは" and picked.dirty
    assert picked.tracks.translations["en"][0].text == "Theirs"
    assert picked.base.translations["en"] == picked.tracks.translations["en"]
    saved, result = backend.save(picked, formats=["srt"])
    assert result.conflicts == () and saved.tracks.source[0].text == "こんばんは"


def test_picking_something_that_isnt_one_of_the_versions_is_refused(backend, video):
    conflicted(video)
    ep = backend.open(str(video))
    with pytest.raises(SaveError, match="that isn't one of the en track's versions"):
        backend.resolve(ep, "en", "r_0000000000000000")
    with pytest.raises(SaveError, match="^there's no such track$"):
        backend.resolve(ep, "<b>en</b>", ep.conflicts["en"][0])
    assert isinstance(store.load(video)[0].head("en"), Conflict)


def test_a_pick_on_a_track_with_one_version_is_refused_and_keeps_unsaved_edits(backend, video):
    ep = edit(backend, backend.open(str(video)), op="set_translation_text", track="en",
              cue=tid(0), text="Unsaved!")
    with pytest.raises(SaveError, match="the en track has only one version"):
        backend.resolve(ep, "en", ep.heads["en"])
    assert ep.tracks.translations["en"][0].text == "Unsaved!" and ep.dirty


def test_picking_a_version_of_the_source_brings_the_words_it_was_built_from(backend, video):
    side, _ = store.load(video)
    head = side.head("ja").rendition
    ours = [c.model_copy(update={"text": c.text + "ね"}) for c in source_cues(3)]
    theirs = [c.model_copy(update={"text": c.text + "よ"}) for c in source_cues(3)]
    transcripts = [make_rendition([], None, transcript_for(cues, audio_track=0, quick="q"))
                   for cues in (ours, theirs)]
    store.append(video, side.header, transcripts)
    mine = write_track(video, "ja", ours, role="source", parents=(transcripts[0].id,),
                       replaces=head)
    write_track(video, "ja", theirs, role="source", parents=(transcripts[1].id,), replaces=head)
    ep = backend.open(str(video))
    assert ep.words[-1].text == "気ですよ"  # in conflict: the newest transcript's words
    picked, _ = backend.resolve(ep, "ja", mine.id)
    assert picked.words[-1].text == "気ですね" and picked.tracks.source[0].text == "おはようね"


def test_a_version_picked_in_another_tab_is_shown_rather_than_picked_again(backend, video):
    conflicted(video)
    a, b = backend.open(str(video)), backend.open(str(video))
    backend.resolve(a, "en", a.conflicts["en"][0])
    picked, result = backend.resolve(b, "en", b.conflicts["en"][1])
    assert result.notes == ("the en track's version was already picked elsewhere: showing it",)
    assert picked.tracks.translations["en"][0].text == "Mine"
    assert [h.by for h in store.load(video)[0].heads("en")].count("user") == 1


# A Save that goes wrong


def test_saving_one_episode_twice_writes_its_versions_once(backend, video, monkeypatch):
    ep = edit(backend, backend.open(str(video)), op="set_text", cue=sid(0), text="こんばんは")
    backend.save(ep, formats=["srt"])
    monkeypatch.setattr(store, "now", lambda: "2099-01-01T00:00:00Z")  # a later second
    before, _ = store.load(video)
    again, result = backend.save(ep, formats=["srt"])  # a retry, or a second click
    assert result.conflicts == () and isinstance(store.load(video)[0].head("ja"), HeadRecord)
    assert not [r for r in added_since(video, before) if isinstance(r, RenditionRecord)]
    assert again.tracks.source[0].text == "こんばんは" and not again.dirty


def test_two_picks_at_once_are_made_one_after_the_other(backend, video, monkeypatch):
    conflicted(video)
    a, b = backend.open(str(video)), backend.open(str(video))
    real, entered, release = store.append, threading.Event(), threading.Event()

    def slow_append(*args, **kwargs):
        if not entered.is_set():
            entered.set()
            release.wait(5)
        return real(*args, **kwargs)

    monkeypatch.setattr(store, "append", slow_append)
    results = {}
    first = threading.Thread(target=lambda: results.update(a=backend.resolve(
        a, "en", a.conflicts["en"][0])))
    second = threading.Thread(target=lambda: results.update(b=backend.resolve(
        b, "en", b.conflicts["en"][1])))
    first.start()
    assert entered.wait(5)
    second.start()
    second.join(0.2)
    assert second.is_alive()  # waiting for the first pick to finish
    release.set()
    first.join(5)
    second.join(5)
    head = store.load(video)[0].head("en")
    assert isinstance(head, HeadRecord) and head.rendition == a.conflicts["en"][0]
    assert results["b"][1].notes == (
        "the en track's version was already picked elsewhere: showing it",)


def test_a_jobs_write_during_a_save_waits_for_it_and_both_keep_their_records(backend, video,
                                                                              monkeypatch):
    ep = edit(backend, backend.open(str(video)), op="set_text", cue=sid(0), text="こんばんは")
    # what a Jobs-page job appends first, from its worker thread
    theirs = make_rendition([], None, transcript_for(source_cues(3), audio_track=0, quick="q"))
    real_replace, appended, job = security._replace, threading.Event(), []

    def mid_save(src, dst):  # the Save has re-read the sidecar and is about to rename its own
        if dst == store.sidecar_path(video) and not job:
            job.append(threading.Thread(target=lambda: (
                store.append(video, ep.header, [theirs]), appended.set())))
            job[0].start()
            appended.wait(0.5)  # done by now, unless the Save's lock holds it back (Decision 30)
        real_replace(src, dst)

    monkeypatch.setattr(security, "_replace", mid_save)
    saved, _ = backend.save(ep, formats=["srt"])
    job[0].join(5)
    side, _ = store.load(video)
    assert theirs.id in side.renditions() and saved.heads["ja"] in side.renditions()


def test_a_save_cut_short_after_the_sidecar_never_makes_the_next_save_conflict_with_itself(
        backend, video, monkeypatch):
    real = store.safe_write

    def full_disk(path, data, **kwargs):
        if path.suffix == ".srt":
            raise OSError(28, "No space left on device")
        return real(path, data, **kwargs)

    monkeypatch.setattr(store, "safe_write", full_disk)
    ep = edit(backend, backend.open(str(video)), op="set_text", cue=sid(0), text="こんばんは")
    saved, result = backend.save(ep, formats=["srt"])
    assert result.written == () and result.notes == (
        f"couldn't write {JA} (No space left on device)",)
    assert not saved.dirty
    monkeypatch.setattr(store, "safe_write", real)
    _, result = backend.save(saved, formats=["srt"])
    assert result.written == (JA,) and result.conflicts == ()
    assert isinstance(store.load(video)[0].head("ja"), HeadRecord)


def test_a_sidecar_that_cant_be_read_any_more_stops_the_save_before_anything_is_written(backend,
                                                                                         video):
    ep = edit(backend, backend.open(str(video)), op="set_text", cue=sid(0), text="こんばんは")
    path = store.sidecar_path(video)
    broken = path.read_bytes() + b"not json\n{}\n"
    path.write_bytes(broken)
    ja = video.with_name(JA).read_bytes()
    with pytest.raises(SaveError, match="can't read"):
        backend.save(ep, formats=["srt"])
    assert path.read_bytes() == broken and video.with_name(JA).read_bytes() == ja


def test_a_sidecar_deleted_since_the_episode_opened_stops_the_save(backend, video):
    ep = edit(backend, backend.open(str(video)), op="set_text", cue=sid(0), text="こんばんは")
    store.sidecar_path(video).unlink()
    with pytest.raises(SaveError, match="open the episode again"):
        backend.save(ep, formats=["srt"])
    assert not store.sidecar_path(video).exists()


def test_a_closed_episode_cant_be_saved(backend, video):
    ep = backend.open(str(video))
    backend.close(ep.id)
    with pytest.raises(OpenError, match="closed"):
        backend.save(ep, formats=["srt"])


# The glossary is written at Save (the plan's Decision 5; spec §16)


def test_glossary_terms_are_added_beside_the_video_at_save_keeping_what_was_there(backend, video):
    glossary = video.with_name(GLOSSARY)
    glossary.write_text('# mine\ndescription = "A show"\n[terms]\n"毛利蘭" = "Ran Mouri"\n',
                        encoding="utf-8")
    ep = edit(backend, backend.open(str(video)), op="glossary_add", term="工藤新一",
              translation="Shinichi Kudo")
    ep = edit(backend, ep, op="glossary_add", term="毛利蘭", translation="Rachel Moore")
    saved, result = backend.save(ep, formats=["srt"])
    assert result.notes == (f"added 1 term to {GLOSSARY}",
                            f"{GLOSSARY} already has 毛利蘭 with another translation: kept that one")
    text = glossary.read_text(encoding="utf-8")
    assert text.startswith('# mine\ndescription = "A show"\n')
    assert parse_glossary(text).terms == (("毛利蘭", "Ran Mouri"), ("工藤新一", "Shinichi Kudo"))
    assert saved.glossary_adds == {} and not saved.dirty


def test_a_new_glossary_is_made_when_there_is_none(backend, video):
    ep = edit(backend, backend.open(str(video)), op="glossary_add", term="工藤新一",
              translation="Shinichi Kudo")
    backend.save(ep, formats=["srt"])
    assert parse_glossary(video.with_name(GLOSSARY).read_text(encoding="utf-8")).terms == (
        ("工藤新一", "Shinichi Kudo"),)


def test_an_empty_glossary_file_takes_terms(backend, video):
    video.with_name(GLOSSARY).write_bytes(b"")
    ep = edit(backend, backend.open(str(video)), op="glossary_add", term="工藤新一",
              translation="Shinichi Kudo")
    _, result = backend.save(ep, formats=["srt"])
    assert result.notes == (f"added 1 term to {GLOSSARY}",)
    assert parse_glossary(video.with_name(GLOSSARY).read_text(encoding="utf-8")).terms == (
        ("工藤新一", "Shinichi Kudo"),)


def test_a_glossary_that_cant_take_the_terms_is_left_alone_and_they_wait(backend, video):
    glossary = video.with_name(GLOSSARY)
    glossary.write_text('terms = { "毛利蘭" = "Ran Mouri" }\n', encoding="utf-8")
    ep = edit(backend, backend.open(str(video)), op="glossary_add", term="工藤新一",
              translation="Shinichi Kudo")
    saved, result = backend.save(ep, formats=["srt"])
    assert len(result.notes) == 1 and result.notes[0].startswith(f"couldn't add to {GLOSSARY}: ")
    assert "by hand" in result.notes[0]
    assert glossary.read_text(encoding="utf-8") == 'terms = { "毛利蘭" = "Ran Mouri" }\n'
    assert saved.glossary_adds == {"工藤新一": "Shinichi Kudo"} and saved.dirty


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges on Windows")
def test_a_glossary_that_is_a_link_is_neither_read_nor_written(backend, video, tmp_path):
    target = tmp_path / "elsewhere.toml"
    target.write_text('[terms]\n"a" = "b"\n', encoding="utf-8")
    video.with_name(GLOSSARY).symlink_to(target)
    ep = edit(backend, backend.open(str(video)), op="glossary_add", term="工藤新一",
              translation="Shinichi Kudo")
    saved, result = backend.save(ep, formats=["srt"])
    assert result.notes == (f"couldn't add to {GLOSSARY}: it isn't a regular file",)
    assert target.read_text(encoding="utf-8") == '[terms]\n"a" = "b"\n' and saved.dirty


# Review Focus 1: a hostile path


def test_a_save_next_to_a_video_with_a_hostile_name_lands_next_to_it(backend, tmp_path):
    folder = tmp_path / "Ünïcödé 番組 🎬"
    name = f"Show {chr(0x202E)}evil S01E01 ✨.mkv"
    video = make_episode(folder, name)
    ep = edit(backend, backend.open(str(video)), op="set_text", cue=sid(0), text="こんばんは")
    _, result = backend.save(ep, formats=["srt"])
    stem = name.removesuffix(".mkv")
    assert result.written == (f"{stem}.ja.srt",)
    assert (folder / f"{stem}.ja.srt").read_text(encoding="utf-8").count("こんばんは") == 1
    assert str(folder) not in repr(result)
