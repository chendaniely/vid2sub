from pathlib import Path

import pytest
from episodes import (
    ENGLISH,
    LINES,
    header_of,
    make_episode,
    sid,
    source_cues,
    tid,
    track_body,
    write_track,
)
from fakes import FakeServer
from helpers import make_clip

from vid2sub import store
from vid2sub.cache import Cache
from vid2sub.config import Config, Endpoint, ModelEntry
from vid2sub.engines.clients import KeyRing
from vid2sub.media.tools import Tools
from vid2sub.subs.edit import Tracks
from vid2sub.subs.glossary import EMPTY_GLOSSARY, parse_glossary
from vid2sub.subs.model import Cue, Segment, Transcript, Word
from vid2sub.subs.rendition import transcript_body
from vid2sub.subs.sidecar import HeadRecord, make_rendition
from vid2sub.web import backend as web_backend
from vid2sub.web import views
from vid2sub.web.backend import Capabilities, LocalBackend, OpenError

pytestmark = pytest.mark.media


@pytest.fixture
def backend(tmp_path) -> LocalBackend:
    return LocalBackend(Config(), Tools.find(), KeyRing(environ={}),
                        Cache(tmp_path / "cache", max_bytes=10**9))


@pytest.fixture
def video(tmp_path):
    return make_episode(tmp_path / "show")


def test_the_local_backend_has_every_control(backend):
    assert backend.capabilities() == Capabilities(engine="local", generate=True, save="disk",
                                                  path_input=True)


def test_an_m1_episode_opens_with_its_source_its_translation_and_their_heads(backend, video):
    ep = backend.open(str(video))
    side, _ = store.load(video)
    assert ep.video == video and ep.source_key == "ja"
    assert [c.text for c in ep.tracks.source] == list(LINES)
    assert [c.text for c in ep.tracks.translations["en"]] == list(ENGLISH)
    assert ep.heads == {"ja": side.head("ja").rendition, "en": side.head("en").rendition}
    assert ep.conflicts == {} and ep.notes == []
    assert ep.base == ep.tracks and not ep.dirty
    assert ep.undo == [] and ep.redo == [] and ep.glossary_adds == {}
    assert {sid(0), sid(2), tid(1)} <= ep.taken
    assert ep.header.video.quick_sha256 == side.header.video.quick_sha256
    assert ep.glossary == EMPTY_GLOSSARY and ep.translate_model is None
    assert backend.is_open(ep.id)


def test_each_open_is_its_own_episode_and_closing_one_forgets_only_it(backend, video):
    first, second = backend.open(str(video)), backend.open(str(video))
    assert first.id != second.id
    backend.close(first.id)
    assert not backend.is_open(first.id) and backend.is_open(second.id)
    backend.close("no-such-episode")


def test_the_spoken_words_come_from_the_transcript_the_source_was_built_from(backend, video):
    newer = make_rendition([], None, transcript_body(
        _one_word_transcript(), engine="whisper.cpp", model="other", version="other",
        created_at=store.now(), inputs={"audio_track": 0}, meta={}))
    store.append(video, store.load(video)[0].header, [newer])
    ep = backend.open(str(video))
    assert [w.text for w in ep.words] == ["おは", "よう", "元気", "ですか", "はい、", "元気です"]
    assert (ep.words[2].start_ms, ep.words[3].end_ms) == (3600, 6600)


def _one_word_transcript() -> Transcript:
    word = Word(text="x", start_ms=0, end_ms=10)
    return Transcript(language="ja", segments=(Segment(text="x", start_ms=0, end_ms=10,
                                                       words=(word,)),))


@pytest.mark.parametrize("codec, playable", [("aac", True), ("ac3", False), ("eac3", False)])
def test_a_browser_cant_play_ac3_or_e_ac3_audio(backend, tmp_path, codec, playable):
    ep = backend.open(str(make_episode(tmp_path / codec, audio_codec=codec)))
    assert ep.playable_audio is playable and ep.audio_index == 0


def test_dts_and_truehd_are_unplayable_too():
    assert web_backend.UNPLAYABLE_AUDIO == {"ac3", "eac3", "dts", "truehd"}


def test_the_audio_track_is_the_one_the_transcript_was_made_from(backend, tmp_path):
    video = make_episode(tmp_path / "two", audio_langs=("jpn", "eng"), audio_codec="ac3",
                         audio_track=1)
    ep = backend.open(str(video))
    assert ep.audio_index == 1 and ep.playable_audio is False


def test_a_track_other_than_the_first_makes_the_audio_unplayable_whatever_its_codec(backend,
                                                                                    tmp_path):
    # Q&A item 48: a browser picks the track it likes (an MKV's first), so the sound under captions
    # made from the second track would be the wrong language; the playback audio maps 0:a:N.
    second = make_episode(tmp_path / "second", audio_langs=("eng", "jpn"), audio_track=1)
    first = make_episode(tmp_path / "first", audio_langs=("jpn", "eng"), audio_track=0)
    ep = backend.open(str(second))
    assert ep.audio_index == 1 and ep.streams.audio_codec == "aac" and ep.playable_audio is False
    ep = backend.open(str(first))
    assert ep.audio_index == 0 and ep.playable_audio is True


def test_with_no_transcript_the_audio_track_is_the_source_languages(backend, tmp_path):
    folder = tmp_path / "imported"
    folder.mkdir()
    video = make_clip(folder, "Show - S01E01.mkv", seconds=2.0, audio_langs=("eng", "jpn"),
                      default_audio=0)
    rec = make_rendition([], "ja", track_body(source_cues(3), "ja", role="source"))
    store.append(video, header_of(video), [rec, HeadRecord(track="ja", rendition=rec.id,
                                                           by="import", at=store.now())])
    ep = backend.open(str(video))
    assert ep.audio_index == 1 and ep.words == ()


def test_a_video_with_no_sidecar_says_how_to_make_its_subtitles(backend, tmp_path):
    video = make_clip(tmp_path, "Plain.mkv", seconds=1.0)
    with pytest.raises(OpenError, match="no subtitles yet: make them with vid2sub run"):
        backend.open(str(video))


@pytest.mark.parametrize("path", ["relative/Show.mkv", "{tmp}", "{tmp}/missing.mkv"])
def test_only_the_full_path_of_a_file_is_opened(backend, tmp_path, path):
    with pytest.raises(OpenError):
        backend.open(path.format(tmp=tmp_path))


def test_an_outside_edit_comes_back_as_the_head_and_the_editor_says_so(backend, video):
    srt = video.with_name("Show - S01E01.en.srt")
    srt.write_text(srt.read_text(encoding="utf-8").replace("How are you?", "How have you been?"),
                   encoding="utf-8")
    ep = backend.open(str(video))
    side, _ = store.load(video)
    assert ep.notes == ["kept your outside edit to en"]
    assert ep.tracks.translations["en"][1].text == "How have you been?"
    assert "edited" in ep.tracks.translations["en"][1].flags
    assert side.head("en").by == "external" and ep.heads["en"] == side.head("en").rendition


def test_an_unreadable_subtitle_file_is_left_alone_and_named_without_its_folder(backend, video,
                                                                               tmp_path):
    srt = video.with_name("Show - S01E01.en.srt")
    srt.write_bytes(b"\x00\x01 not subtitles")
    ep = backend.open(str(video))
    assert ep.notes == ["left Show - S01E01.en.srt alone: it isn't a readable subtitle file"]
    assert srt.read_bytes() == b"\x00\x01 not subtitles"
    assert not any(str(tmp_path) in note for note in ep.notes)


def test_a_track_in_conflict_lists_both_versions_and_isnt_loaded(backend, video):
    side, _ = store.load(video)
    head = side.head("en").rendition
    mine = write_track(video, "en", [Cue(id=tid(0), start_ms=0, end_ms=3000, text="Mine",
                                         src=(sid(0),))], role="translation", replaces=head,
                       by="editor")
    theirs = write_track(video, "en", [Cue(id=tid(0), start_ms=0, end_ms=3000, text="Theirs",
                                           src=(sid(0),))], role="translation", replaces=head)
    ep = backend.open(str(video))
    assert ep.conflicts == {"en": (mine.id, theirs.id)}
    assert "en" not in ep.tracks.translations and "en" not in ep.heads
    assert [c.text for c in ep.tracks.source] == list(LINES)


def test_a_source_in_conflict_opens_with_nothing_to_edit(backend, video):
    side, _ = store.load(video)
    head = side.head("ja").rendition
    one = write_track(video, "ja", source_cues(3)[:1], role="source", replaces=head, by="editor")
    two = write_track(video, "ja", source_cues(3)[1:], role="source", replaces=head)
    ep = backend.open(str(video))
    assert ep.source_key == "ja" and ep.tracks.source == ()
    assert ep.conflicts == {"ja": (one.id, two.id)} and "ja" not in ep.heads


def test_a_sidecar_vid2sub_cant_read_is_refused_and_left_alone(backend, video):
    path = store.sidecar_path(video)
    broken = path.read_bytes() + b"not json\n{}\n"
    path.write_bytes(broken)
    with pytest.raises(OpenError, match="can't read"):
        backend.open(str(video))
    assert path.read_bytes() == broken


def test_another_video_with_the_same_name_is_refused(backend, video):
    video.with_suffix(".mp4").write_bytes(b"x")
    with pytest.raises(OpenError, match="same name"):
        backend.open(str(video))


def test_a_replaced_video_is_noted_with_the_difference(backend, video):
    make_clip(video.parent, video.name, seconds=3.0)
    ep = backend.open(str(video))
    assert len(ep.notes) == 1
    assert ep.notes[0].startswith("this video changed since its subtitles were made (size")


def test_an_episode_holds_tracks_the_edit_rules_take(backend, video):
    ep = backend.open(str(video))
    assert isinstance(ep.tracks, Tracks) and set(ep.tracks.translations) == {"en"}


def test_the_glossary_beside_the_video_is_read_at_open(backend, video):
    text = '[terms]\n"工藤新一" = "Shinichi Kudo"\n'
    video.with_name("vid2sub.glossary.toml").write_text(text, encoding="utf-8")
    assert backend.open(str(video)).glossary == parse_glossary(text)


def test_a_glossary_vid2sub_cant_read_is_noted_and_left_out(backend, video):
    video.with_name("vid2sub.glossary.toml").write_text("nonsense = [", encoding="utf-8")
    ep = backend.open(str(video))
    assert ep.glossary is None and len(ep.notes) == 1
    assert ep.notes[0].startswith("couldn't read vid2sub.glossary.toml: the glossary isn't valid")


def test_the_model_retranslate_would_use_is_picked_without_asking_any_server(tmp_path, video):
    with FakeServer() as srv:
        config = Config(endpoints={"spark": Endpoint(base_url=srv.url),
                                   "openai": Endpoint(base_url=srv.url)},
                        models={"gpt": ModelEntry(catalog="openai-gpt", endpoint="openai",
                                                  model="gpt", task="translate"),
                                "gemma": ModelEntry(catalog="gemma-4-26b-a4b", endpoint="spark",
                                                    model="gemma-2", task="translate",
                                                    local=True)})
        ep = LocalBackend(config, Tools.find(), KeyRing(environ={}),
                          Cache(tmp_path / "cache", max_bytes=10**9)).open(str(video))
        assert srv.requests == []
    assert ep.translate_model == "gemma-2"
    flags = [c["flags"] for row in views.episode_view(ep, video_url=None, audio_url=None)["rows"]
             for c in row["tr"]["en"]["cues"]]
    assert flags == [["stale"]] * 3  # the episode's English was made by "gemma"


def test_a_cloud_model_is_never_the_one_retranslate_would_use_unasked(tmp_path, video):
    config = Config(endpoints={"openai": Endpoint(base_url="https://api.openai.com/v1")},
                    models={"gpt": ModelEntry(catalog="openai-gpt", endpoint="openai",
                                              model="gpt", task="translate")})
    ep = LocalBackend(config, Tools.find(), KeyRing(environ={}),
                      Cache(tmp_path / "cache", max_bytes=10**9)).open(str(video))
    assert ep.translate_model is None


def _denied(path) -> PermissionError:
    return PermissionError(13, "Permission denied", str(path))


def test_an_unreadable_glossary_opens_without_it_and_the_note_names_no_folder(
        backend, video, monkeypatch):
    glossary = video.with_name("vid2sub.glossary.toml")
    glossary.write_text("[terms]\n", encoding="utf-8")
    real = Path.read_text

    def read_text(self, *args, **kwargs):
        if self.name == glossary.name:
            raise _denied(self)
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_text)
    ep = backend.open(str(video))
    assert ep.glossary is None
    assert ep.notes == ["couldn't read vid2sub.glossary.toml (Permission denied)"]
    assert str(video.parent) not in " ".join(ep.notes)


def test_an_unreadable_sidecar_is_refused_without_naming_its_folder(backend, video, monkeypatch):
    def load(_video):
        raise _denied(store.sidecar_path(video))

    monkeypatch.setattr(store, "load", load)
    with pytest.raises(OpenError) as refused:
        backend.open(str(video))
    assert "Permission denied" in str(refused.value)
    assert str(video.parent) not in str(refused.value)
