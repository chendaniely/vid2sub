import dataclasses
import json
import time
from pathlib import Path

import pytest
from episodes import (
    ENGLISH,
    LINES,
    make_episode,
    sid,
    source_cues,
    tid,
    track_body,
    translation_cues,
)

from vid2sub.cache import Cache
from vid2sub.config import Config
from vid2sub.engines.clients import KeyRing
from vid2sub.media.tools import Tools
from vid2sub.subs.edit import Tracks
from vid2sub.subs.glossary import EMPTY_GLOSSARY, parse_glossary
from vid2sub.subs.model import Cue, Word
from vid2sub.subs.rendition import cues_body
from vid2sub.subs.sidecar import Header, HeadRecord, Sidecar, VideoInfo, make_rendition
from vid2sub.web import views
from vid2sub.web.backend import Episode, LocalBackend

VIDEO = Path("/Users/someone/Secret Shows/Show - S01E01.mkv")
HEADER = Header(video=VideoInfo(name=VIDEO.name, size=1, quick_sha256="a" * 64,
                                duration_ms=20_000))
AT = "2026-10-23T10:00:00Z"
GLOSSARY = parse_glossary('[terms]\n"工藤新一" = "Shinichi Kudo"\n')


def body(cues, lang: str, role: str, *, model=None, glossary_sha=None) -> dict:
    return cues_body(cues, language=lang, script=None, engine="vid2sub", model=model,
                     version="t", created_at=AT, inputs={}, meta={"role": role},
                     glossary_sha=glossary_sha)


def episode(source=None, en=None, *, records=(), en_model=None, en_glossary_sha=None,
            **changes) -> Episode:
    source = tuple(source_cues(3) if source is None else source)
    en = tuple(translation_cues(source) if en is None else en)
    ja_rec = make_rendition([], "ja", body(source, "ja", "source"))
    en_rec = make_rendition([ja_rec.id], "en", body(en, "en", "translation", model=en_model,
                                                    glossary_sha=en_glossary_sha))
    side = Sidecar(HEADER, (ja_rec, HeadRecord(track="ja", rendition=ja_rec.id, by="auto", at=AT),
                            en_rec, HeadRecord(track="en", rendition=en_rec.id, by="editor",
                                               at="2026-10-23T11:00:00Z"), *records))
    tracks = Tracks(source, {"en": en})
    words = tuple(Word(text=t, start_ms=k * 500, end_ms=k * 500 + 400)
                  for k, t in enumerate(["おは", "よう"]))
    ep = Episode(id="e1", video=VIDEO, header=HEADER, source_key="ja", tracks=tracks,
                 heads={"ja": ja_rec.id, "en": en_rec.id}, conflicts={}, words=words, notes=[],
                 playable_audio=True, audio_index=0, sidecar=side, base=tracks,
                 glossary=EMPTY_GLOSSARY, translate_model=None)
    return dataclasses.replace(ep, **changes)


def view(ep: Episode, **urls) -> dict:
    return views.episode_view(ep, video_url=urls.get("video_url"),
                              audio_url=urls.get("audio_url"))


def test_each_source_cue_is_a_row_with_its_number_times_text_and_word_range():
    rows = view(episode())["rows"]
    assert [(r["id"], r["n"], r["text"]) for r in rows] == [
        (sid(0), 1, LINES[0]), (sid(1), 2, LINES[1]), (sid(2), 3, LINES[2])]
    assert (rows[1]["start_ms"], rows[1]["end_ms"], rows[1]["w"]) == (3600, 6600, [2, 4])


def test_a_rows_flags_are_its_stored_flags_and_its_lint_flags():
    source = source_cues(3)
    source[2] = source[2].model_copy(update={"end_ms": 7200 + 1000, "flags": ("est",)})
    rows = view(episode(source))["rows"]
    assert rows[2]["flags"] == ["cps", "est"]  # 7 characters in a second, past Japanese's 4
    assert rows[0]["flags"] == []


def test_a_translation_shows_in_the_row_of_its_first_source_cue():
    source = source_cues(3)
    en = translation_cues(source)
    both = Cue(id=tid(9), start_ms=3600, end_ms=10_200, text="How are you? Fine.",
               src=(sid(1), sid(2)), src_sha=en[1].src_sha)
    rows = view(episode(source, [en[0], both]))["rows"]
    assert [c["id"] for c in rows[1]["tr"]["en"]["cues"]] == [tid(9)]
    assert rows[1]["tr"]["en"]["cues"][0]["src"] == [sid(1), sid(2)]
    assert rows[2]["tr"]["en"] == {"cues": [], "flags": []}


def test_a_translation_whose_source_changed_is_stale_and_an_edited_one_says_so():
    source = source_cues(3)
    en = translation_cues(source)
    en[1] = en[1].model_copy(update={"text": "How are things?", "flags": ("edited",)})
    source[0] = source[0].model_copy(update={"text": "こんばんは"})
    rows = view(episode(source, en))["rows"]
    assert rows[0]["tr"]["en"]["cues"][0]["flags"] == ["stale"]
    assert rows[1]["tr"]["en"]["cues"][0]["flags"] == ["edited"]
    assert rows[2]["tr"]["en"]["cues"][0]["flags"] == []


def test_a_source_cue_no_translation_covers_is_untranslated_in_that_track():
    source = source_cues(3)
    rows = view(episode(source, translation_cues(source)[:2]))["rows"]
    assert rows[2]["tr"]["en"] == {"cues": [], "flags": ["untranslated"]}
    assert rows[1]["tr"]["en"]["flags"] == []


def test_a_translation_whose_source_cues_are_gone_shows_at_its_time_and_is_stale():
    source = source_cues(3)
    lost = Cue(id=tid(5), start_ms=4000, end_ms=5000, text="Lost", src=("c00000000",))
    rows = view(episode(source, [*translation_cues(source)[:1], lost]))["rows"]
    (cue,) = rows[1]["tr"]["en"]["cues"]
    assert cue["id"] == tid(5) and cue["flags"] == ["stale"]


def test_translations_are_linted_by_their_own_languages_rules():
    source = source_cues(3)
    en = translation_cues(source)
    en[0] = en[0].model_copy(update={"text": "A single line that is far too wide for a screen"})
    cue = view(episode(source, en))["rows"][0]["tr"]["en"]["cues"][0]
    assert cue["flags"] == ["width"]


def test_the_tracks_say_their_role_who_set_their_head_and_whether_they_are_in_conflict():
    other = make_rendition([], "zh-Hant", body([], "zh", "translation"))
    ep = episode(records=(other,), conflicts={"zh-Hant": (other.id, "r_other")})
    ep = dataclasses.replace(ep, sidecar=Sidecar(HEADER, ep.sidecar.records + (
        HeadRecord(track="zh-Hant", rendition=other.id, by="auto", at=AT),
        HeadRecord(track="zh-Hant", rendition="r_other", by="editor", at=AT))))
    assert view(ep)["tracks"] == [
        {"key": "ja", "label": "Japanese", "role": "source", "head_by": "auto",
         "in_conflict": False, "all_stale": False},
        {"key": "en", "label": "English", "role": "translation", "head_by": "editor",
         "in_conflict": False, "all_stale": False},
        {"key": "zh-Hant", "label": "Mandarin (Traditional)", "role": "translation",
         "head_by": None, "in_conflict": True, "all_stale": False},
    ]


def test_each_version_of_a_track_in_conflict_says_who_made_it_when_and_how_many_cues():
    source = source_cues(3)
    mine = make_rendition([], "en", body(translation_cues(source)[:2], "en", "translation"))
    theirs = make_rendition([], "en", body(translation_cues(source), "en", "translation"))
    ep = episode(source, records=(
        mine, HeadRecord(track="en", rendition=mine.id, by="editor", at="2026-10-23T12:00:00Z"),
        theirs, HeadRecord(track="en", rendition=theirs.id, by="auto", at="2026-10-23T12:05:00Z")))
    ep = dataclasses.replace(ep, conflicts={"en": (mine.id, theirs.id)},
                             tracks=Tracks(ep.tracks.source, {}))
    v = view(ep)
    assert v["conflicts"] == {"en": [
        {"rendition": mine.id, "by": "editor", "at": "2026-10-23T12:00:00Z", "cue_count": 2},
        {"rendition": theirs.id, "by": "auto", "at": "2026-10-23T12:05:00Z", "cue_count": 3}]}
    assert "en" not in v["rows"][0]["tr"]


def test_dirty_undo_and_redo_follow_the_episode():
    ep = episode()
    assert (view(ep)["dirty"], view(ep)["can_undo"], view(ep)["can_redo"]) == (False, False, False)
    changed = Tracks(ep.tracks.source[:2], ep.tracks.translations)
    v = view(dataclasses.replace(ep, tracks=changed, undo=[(ep.tracks, {}, {})]))
    assert (v["dirty"], v["can_undo"], v["can_redo"]) == (True, True, False)
    v = view(dataclasses.replace(ep, glossary_adds={"工藤": "Kudo"}))
    assert v["dirty"] is True and v["glossary_adds"] == {"工藤": "Kudo"}


def test_the_words_are_listed_in_transcript_order_with_their_times():
    assert view(episode())["words"] == [{"start_ms": 0, "end_ms": 400, "text": "おは"},
                                        {"start_ms": 500, "end_ms": 900, "text": "よう"}]


def test_the_video_has_the_urls_it_was_given_its_name_and_never_its_folder():
    ep = episode(notes=["kept your outside edit to en"])
    v = view(ep, audio_url="/media/abc")
    assert v["video"] == {"name": "Show - S01E01.mkv", "duration_ms": 20_000, "url": None,
                          "audio_url": "/media/abc", "playable_audio": True}
    assert (v["id"], v["source"], v["notes"]) == ("e1", "ja", ["kept your outside edit to en"])
    text = json.dumps(v, ensure_ascii=False)
    assert "Secret Shows" not in text and "/Users/" not in text


def test_a_view_is_plain_json():
    v = view(episode())
    assert json.loads(json.dumps(v, ensure_ascii=False)) == v
    assert v["rows"][0]["tr"]["en"]["cues"][0] == {
        "id": tid(0), "start_ms": 0, "end_ms": 3000, "text": ENGLISH[0], "src": [sid(0)],
        "detached": False, "flags": []}


# Spec §13.4: a translation made with another glossary or model is stale, as M1 decides it


def en_flags(v: dict) -> list[list[str]]:
    return [c["flags"] for row in v["rows"] for c in row["tr"]["en"]["cues"]]


def test_a_translation_made_with_another_glossary_is_stale_in_every_cue():
    v = view(episode(en_model="gemma", glossary=GLOSSARY))
    assert en_flags(v) == [["stale"]] * 3
    assert [t["all_stale"] for t in v["tracks"]] == [False, True]


def test_a_translation_made_with_the_glossary_beside_the_video_is_not():
    assert en_flags(view(episode(glossary=GLOSSARY, en_glossary_sha=GLOSSARY.sha()))) == [[]] * 3


def test_a_glossary_term_waiting_for_save_makes_every_translation_stale():
    ep = episode(en_model="gemma")
    assert en_flags(view(ep)) == [[]] * 3
    waiting = dataclasses.replace(ep, glossary_adds={"工藤新一": "Shinichi Kudo"})
    assert en_flags(view(waiting)) == [["stale"]] * 3


def test_a_translation_made_with_another_model_is_stale_in_every_cue():
    assert en_flags(view(episode(en_model="gemma", translate_model="gemma-2"))) == [["stale"]] * 3
    assert en_flags(view(episode(en_model="gemma", translate_model="gemma"))) == [[]] * 3


def test_an_edited_translation_is_stale_too_and_keeps_its_edited_flag():
    source = source_cues(3)
    en = translation_cues(source)
    en[1] = en[1].model_copy(update={"flags": ("edited",)})
    assert en_flags(view(episode(source, en, en_model="gemma", glossary=GLOSSARY)))[1] == ["edited", "stale"]


def test_an_unreadable_glossary_or_no_usable_model_leaves_that_leg_out():
    ep = episode(en_model="old", en_glossary_sha="abcd1234", glossary=None, translate_model=None)
    assert en_flags(view(ep)) == [[]] * 3


def test_a_track_no_translator_made_has_neither_staleness_leg():
    source = source_cues(3)
    ep = episode(source, glossary=GLOSSARY, translate_model="gemma-2")
    imported = make_rendition([], "en", track_body(translation_cues(source), "en",
                                                   role="translation", engine="import"))
    ep = dataclasses.replace(
        ep, heads={**ep.heads, "en": imported.id},
        sidecar=Sidecar(HEADER, ep.sidecar.records + (
            imported, HeadRecord(track="en", rendition=imported.id, by="import", at=AT))))
    v = view(ep)
    assert [t["all_stale"] for t in v["tracks"]] == [False, False]
    assert en_flags(v) == [[]] * 3


def imported(*spans) -> list[Cue]:
    """Lines as `store.import_subtitles` makes them: no src, no src_sha (Q&A item 45)."""
    return [Cue(id=tid(i), start_ms=a, end_ms=b, text=f"Imported {i}")
            for i, (a, b) in enumerate(spans)]


def test_an_imported_line_is_never_stale_and_covers_the_source_cues_it_overlaps():
    en = imported((0, 3200), (7200, 10_200))  # over the first and third cues; the second is a gap
    v = view(episode(en=en, en_model="gemma", glossary=GLOSSARY, translate_model="gemma-2"))
    assert en_flags(v) == [[], []]
    assert [r["tr"]["en"]["flags"] for r in v["rows"]] == [[], ["untranslated"], []]


@pytest.mark.media
def test_a_two_hour_episode_opens_and_becomes_a_view_in_under_a_second(tmp_path):
    video = make_episode(tmp_path / "long", n=2000)
    backend = LocalBackend(Config(), Tools.find(), KeyRing(environ={}),
                           Cache(tmp_path / "cache", max_bytes=10**9))
    began = time.perf_counter()
    ep = backend.open(str(video))
    v = views.episode_view(ep, video_url="/media/v", audio_url=None)
    elapsed = time.perf_counter() - began
    assert len(v["rows"]) == 2000 and len(v["words"]) == 4000
    # Review Focus 3 asks for under a second; this took about 0.1 s where it was built,
    # so the bound leaves room for a slow CI runner without hiding a real slowdown.
    assert elapsed < 1.0, f"{elapsed:.2f} s"
