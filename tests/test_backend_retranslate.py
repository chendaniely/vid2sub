import re
from pathlib import Path

import pytest
from episodes import ENGLISH, LINES, make_episode, sid, tid, translation_cues, write_track
from fakes import FakeServer, chat_responder, closed_port_url
from hypothesis import given, settings
from hypothesis import strategies as st

from vid2sub import store
from vid2sub.cache import Cache
from vid2sub.catalog import Candidate
from vid2sub.config import Config, Endpoint, ModelEntry
from vid2sub.engines.base import EngineError
from vid2sub.engines.clients import KeyRing
from vid2sub.media.tools import Tools
from vid2sub.subs.edit import EditError
from vid2sub.subs.glossary import GlossaryError, parse_glossary
from vid2sub.subs.model import Cue, check_track
from vid2sub.subs.translate_shape import src_sha
from vid2sub.web import backend as web_backend
from vid2sub.web import views
from vid2sub.web.backend import LocalBackend
from vid2sub.web.ops import parse_op

pytestmark = pytest.mark.media
GEMMA = ModelEntry(catalog="gemma-4-26b-a4b", endpoint="spark", model="gemma", task="translate",
                   local=True)


def config(spark: str = "http://127.0.0.1:9/v1", cloud: str | None = None) -> Config:
    endpoints = {"spark": Endpoint(base_url=spark)}
    models = {"gemma": GEMMA}
    if cloud:
        endpoints["openai"] = Endpoint(base_url=cloud)
        models["cloud"] = ModelEntry(catalog="openai-gpt", endpoint="openai", model="gpt",
                                     task="translate", api="completions")
    return Config(endpoints=endpoints, models=models)


def make_backend(tmp_path, cfg: Config) -> LocalBackend:
    return LocalBackend(cfg, Tools.find(), KeyRing(environ={}),
                        Cache(tmp_path / "cache", max_bytes=10**9))


@pytest.fixture
def asked(monkeypatch) -> list[list[str]]:
    """The source cue ids each batch asked the model to translate; it answers 'EN <id>'. The
    server is there and lists gemma, so the route picks it without a request."""
    batches: list[list[str]] = []

    def make_ask(*args, **kwargs):
        def ask(system, prompt, model):
            ids = re.findall(r"^\[(\S+)\] \(max", prompt, flags=re.MULTILINE)
            batches.append(ids)
            return model.model_validate({"items": [{"src": [i], "text": f"EN {i}"} for i in ids]})
        return ask

    monkeypatch.setattr(web_backend, "make_ask", make_ask)
    monkeypatch.setattr(web_backend.detecting, "candidates", lambda config, keys, **kw: [
        Candidate("gemma", "gemma-4-26b-a4b", "endpoint", True)])
    return batches


@pytest.fixture
def backend(tmp_path) -> LocalBackend:
    return make_backend(tmp_path, config())


@pytest.fixture
def video(tmp_path):
    return make_episode(tmp_path / "show")


def edit(backend, ep, **data):
    return backend.apply(ep, parse_op(data))


def en(ep) -> list[tuple[str, str]]:
    return [(c.id, c.text) for c in ep.tracks.translations["en"]]


def spanning(video, *, edited: bool = False) -> None:
    """The en track as one cue for sid(0) and one covering sid(1) and sid(2) together."""
    head = store.load(video)[0].head("en").rendition
    first = translation_cues(_source(video))[0]
    both = Cue(id=tid(9), start_ms=3600, end_ms=10_200, text="How are you? Fine.",
               src=(sid(1), sid(2)), src_sha=src_sha([LINES[1], LINES[2]]),
               flags=("edited",) if edited else ())
    write_track(video, "en", [first, both], role="translation", replaces=head)


def _source(video):
    return store.current_cues(store.load(video)[0], "ja")[1]


# S30: Retranslate stale (spec §13.4)


def test_retranslating_stale_redoes_only_the_cues_whose_source_changed(backend, video, asked):
    ep = edit(backend, backend.open(str(video)), op="set_text", cue=sid(1), text="お元気ですか")
    out = backend.retranslate(ep, "en", ids=None)
    assert asked == [[sid(1)]]
    (new,) = [c for c in out.tracks.translations["en"] if c.id not in (tid(0), tid(2))]
    assert en(out) == [(tid(0), ENGLISH[0]), (new.id, f"EN {sid(1)}"), (tid(2), ENGLISH[2])]
    assert new.src == (sid(1),) and new.src_sha == src_sha(["お元気ですか"])
    assert new.id in out.taken and new.id not in ep.taken


def test_an_edited_translation_is_kept_when_retranslating_stale(backend, video, asked):
    ep = edit(backend, backend.open(str(video)), op="set_translation_text", track="en",
              cue=tid(1), text="How have you been?")
    ep = edit(backend, ep, op="set_text", cue=sid(1), text="お元気ですか")
    ep = edit(backend, ep, op="set_text", cue=sid(2), text="はい")
    out = backend.retranslate(ep, "en", ids=None)
    assert asked == [[sid(2)]]
    assert en(out)[:2] == [(tid(0), ENGLISH[0]), (tid(1), "How have you been?")]
    assert en(out)[2][1] == f"EN {sid(2)}"


def test_an_inserted_cue_is_translated_as_untranslated(backend, video, asked):
    ep = edit(backend, backend.open(str(video)), op="insert", start_ms=3100, end_ms=3500,
              text="えっ", id="cc0000001")
    inserted = ep.tracks.source[1].id
    out = backend.retranslate(ep, "en", ids=None)
    assert asked == [[inserted]]
    assert [t for _, t in en(out)] == [ENGLISH[0], f"EN {inserted}", *ENGLISH[1:]]


def test_a_cue_inserted_inside_a_translation_spanning_two_cues_is_translated_with_them(
        backend, video, asked):
    spanning(video)
    ep = edit(backend, backend.open(str(video)), op="insert", start_ms=6700, end_ms=7100,
              text="えっ", id="cc0000001")
    inserted = ep.tracks.source[2].id
    out = backend.retranslate(ep, "en", ids=None)
    assert asked == [[sid(1), inserted, sid(2)]]
    track = out.tracks.translations["en"]
    check_track(track)
    assert [c.src for c in track] == [(sid(0),), (sid(1),), (inserted,), (sid(2),)]
    assert tid(9) not in {c.id for c in track}


def test_an_edited_translation_spanning_an_inserted_cue_keeps_it_untranslated(backend, video,
                                                                             asked):
    spanning(video, edited=True)
    ep = edit(backend, backend.open(str(video)), op="insert", start_ms=6700, end_ms=7100,
              text="えっ", id="cc0000001")
    assert backend.retranslate(ep, "en", ids=None) is ep and asked == []


def test_named_cues_are_retranslated_even_an_edited_one(backend, video, asked):
    ep = edit(backend, backend.open(str(video)), op="set_translation_text", track="en",
              cue=tid(0), text="Morning!")
    out = backend.retranslate(ep, "en", ids=[sid(0)])
    assert asked == [[sid(0)]] and en(out)[0][1] == f"EN {sid(0)}"
    assert backend.undo(out).tracks == ep.tracks


def test_a_named_cue_brings_the_other_cues_its_translation_covers(backend, video, asked):
    spanning(video, edited=True)
    out = backend.retranslate(backend.open(str(video)), "en", ids=[sid(1)])
    assert asked == [[sid(1), sid(2)]]
    assert [c.src for c in out.tracks.translations["en"]] == [(sid(0),), (sid(1),), (sid(2),)]


def test_with_nothing_stale_no_model_is_asked(backend, video, asked):
    ep = backend.open(str(video))
    assert backend.retranslate(ep, "en", ids=None) is ep and asked == []
    assert backend.retranslate(ep, "en", ids=[]) is ep


def test_a_retranslation_is_one_undo_step_and_reports_each_batch(backend, video, asked):
    ep = edit(backend, backend.open(str(video)), op="set_text", cue=sid(1), text="お元気ですか")
    progress = []
    out = backend.retranslate(ep, "en", ids=None, on_batch=lambda n, of: progress.append((n, of)))
    assert progress == [(1, 1)]
    assert len(out.undo) == len(ep.undo) + 1 and out.redo == []
    assert backend.undo(out).tracks == ep.tracks


def test_a_track_in_conflict_or_an_unknown_one_cant_be_retranslated(backend, video, asked):
    head = store.load(video)[0].head("en").rendition
    for text in ("Mine", "Theirs"):
        write_track(video, "en", [Cue(id=tid(0), start_ms=0, end_ms=3000, text=text,
                                      src=(sid(0),))], role="translation", replaces=head)
    ep = backend.open(str(video))
    with pytest.raises(EditError, match="the en track has two versions: pick one"):
        backend.retranslate(ep, "en", ids=None)
    with pytest.raises(EditError, match="^there's no such track$"):
        backend.retranslate(ep, "<b>en</b>", ids=None)
    with pytest.raises(EditError, match="^there is no zh-Hant track$"):
        backend.retranslate(ep, "zh-Hant", ids=None)
    assert asked == []


def test_a_named_cue_that_isnt_in_the_source_is_refused_without_echoing_it(backend, video, asked):
    with pytest.raises(EditError, match="^one of those cues isn't in the source track$"):
        backend.retranslate(backend.open(str(video)), "en", ids=["<script>"])


# Spec §13.4's other two legs: a track made with another glossary or model is stale throughout

TERMS = '[terms]\n"工藤新一" = "Shinichi Kudo"\n'


def stale_flags(ep) -> list[bool]:
    return ["stale" in c["flags"]
            for row in views.episode_view(ep, video_url=None, audio_url=None)["rows"]
            for c in row["tr"]["en"]["cues"]]


def test_retranslating_stale_redoes_every_unedited_cue_when_the_glossary_changed(backend, video,
                                                                                asked):
    video.with_name("vid2sub.glossary.toml").write_text(TERMS, encoding="utf-8")
    ep = edit(backend, backend.open(str(video)), op="set_translation_text", track="en",
              cue=tid(1), text="How have you been?")
    out = backend.retranslate(ep, "en", ids=None)
    assert asked == [[sid(0)], [sid(2)]]
    assert en(out)[1] == (tid(1), "How have you been?")


def test_retranslating_stale_redoes_every_unedited_cue_when_the_model_changed(tmp_path, video,
                                                                             asked):
    newer = GEMMA.model_copy(update={"model": "gemma-2"})
    backend = make_backend(tmp_path, Config(endpoints={"spark": Endpoint(
        base_url="http://127.0.0.1:9/v1")}, models={"gemma": newer}))
    backend.retranslate(backend.open(str(video)), "en", ids=None)
    assert asked == [[sid(0), sid(1), sid(2)]]


def test_the_model_leg_compares_with_the_model_this_retranslation_uses(tmp_path, video, asked):
    other = GEMMA.model_copy(update={"model": "other-model"})
    backend = make_backend(tmp_path, Config(endpoints={"spark": Endpoint(
        base_url="http://127.0.0.1:9/v1")}, models={"gemma": GEMMA, "other": other}))
    ep = backend.open(str(video))
    assert backend.retranslate(ep, "en", ids=None) is ep and asked == []
    backend.retranslate(ep, "en", ids=None, model="other")
    assert asked == [[sid(0), sid(1), sid(2)]]


def test_after_retranslating_everything_and_saving_nothing_is_stale_any_more(backend, video,
                                                                            asked):
    video.with_name("vid2sub.glossary.toml").write_text(TERMS, encoding="utf-8")
    ep = backend.open(str(video))
    assert stale_flags(ep) == [True] * 3
    out = backend.retranslate(ep, "en", ids=None)
    assert stale_flags(out) == [False] * 3
    assert stale_flags(backend.undo(out)) == [True] * 3  # undone: the old glossary's again
    saved, _ = backend.save(out, formats=["srt"])
    body = store.load(video)[0].renditions()[saved.heads["en"]].body
    assert (body["payload"]["glossary_sha"], body["model"]) == (parse_glossary(TERMS).sha(),
                                                                "gemma")
    reopened = backend.open(str(video))
    assert stale_flags(saved) == stale_flags(reopened) == [False] * 3
    assert backend.retranslate(reopened, "en", ids=None) is reopened and len(asked) == 1


# Q&A item 45: an imported line (no src) is never stale and never replaced unless named


def write_imported(video, *spans, mixed: bool = False) -> None:
    """The en track as `store.import_subtitles` makes it (lines with no src); `mixed` keeps the
    translator's own line for the first source cue and imports the rest."""
    head = store.load(video)[0].head("en").rendition
    lines = [Cue(id=tid(i + (5 if mixed else 0)), start_ms=a, end_ms=b, text=f"Imported {i}")
             for i, (a, b) in enumerate(spans)]
    if mixed:
        lines = [translation_cues(_source(video))[0], *lines]
    write_track(video, "en", lines, role="translation", replaces=head)


def test_retranslating_stale_leaves_imported_lines_alone_and_translates_only_the_gap(
        backend, video, asked):
    write_imported(video, (0, 3200), (7200, 10_200))
    ep = backend.open(str(video))
    out = backend.retranslate(ep, "en", ids=None)
    assert asked == [[sid(1)]]
    assert en(out)[0] == (tid(0), "Imported 0") and en(out)[2] == (tid(1), "Imported 1")
    assert [t for _, t in en(out)][1] == f"EN {sid(1)}"


def test_retranslating_stale_after_a_glossary_change_still_leaves_imported_lines_alone(
        backend, video, asked):
    write_imported(video, (0, 3200), (7200, 10_200))
    video.with_name("vid2sub.glossary.toml").write_text(TERMS, encoding="utf-8")
    out = backend.retranslate(backend.open(str(video)), "en", ids=None)
    assert asked == [[sid(1)]]
    assert [t for _, t in en(out)][0::2] == ["Imported 0", "Imported 1"]


def test_a_named_cue_replaces_the_imported_line_it_overlaps(backend, video, asked):
    write_imported(video, (0, 3200), (7200, 10_200))
    out = backend.retranslate(backend.open(str(video)), "en", ids=[sid(0)])
    assert asked == [[sid(0)]]
    assert [t for _, t in en(out)] == [f"EN {sid(0)}", "Imported 1"]


def test_on_a_mixed_track_only_the_stale_linked_lines_change(backend, video, asked):
    write_imported(video, (3600, 6600), mixed=True)
    ep = edit(backend, backend.open(str(video)), op="set_text", cue=sid(0), text="おはようー")
    out = backend.retranslate(ep, "en", ids=None)
    assert asked == [[sid(0)], [sid(2)]]  # the stale linked line and the uncovered cue
    assert [t for _, t in en(out)] == [f"EN {sid(0)}", "Imported 0", f"EN {sid(2)}"]


def test_an_undo_between_two_redo_alls_gives_back_the_first_ones_glossary_and_model(
        backend, video, asked):
    first = edit(backend, backend.open(str(video)), op="glossary_add", term="工藤新一",
                 translation="Shinichi Kudo")
    first = backend.retranslate(first, "en", ids=None)
    second = edit(backend, first, op="glossary_add", term="毛利蘭", translation="Ran Mouri")
    second = backend.retranslate(second, "en", ids=None)
    assert web_backend.track_setup(second, "en") != web_backend.track_setup(first, "en")
    undone = backend.undo(second)
    assert undone.tracks == first.tracks
    assert web_backend.track_setup(undone, "en") == web_backend.track_setup(first, "en")
    assert web_backend.all_stale(undone, "en")  # its cues lack the second term
    assert backend.redo(undone).made_with == second.made_with


def gone_last(backend, video):
    """The last source line deleted in another program: its translation has no source left."""
    head = store.load(video)[0].head("ja").rendition
    write_track(video, "ja", _source(video)[:2], role="source", replaces=head)
    return backend.open(str(video))


def test_a_translation_whose_source_cues_are_all_gone_is_dropped_by_retranslating_stale(
        backend, video, asked):
    ep = gone_last(backend, video)
    assert [c.id for c in ep.tracks.translations["en"]][-1] == tid(2)
    out = backend.retranslate(ep, "en", ids=None)
    assert asked == [] and [c.id for c in out.tracks.translations["en"]] == [tid(0), tid(1)]
    check_track(out.tracks.translations["en"])
    assert len(out.undo) == len(ep.undo) + 1


def test_an_edited_translation_whose_source_cues_are_gone_is_kept(backend, video, asked):
    ep = gone_last(backend, video)
    ep = edit(backend, ep, op="set_translation_text", track="en", cue=tid(2), text="Mine")
    assert backend.retranslate(ep, "en", ids=None) is ep


def test_a_dropped_translation_does_not_keep_a_glossary_change_redoing_the_track(
        backend, video, asked):
    video.with_name("vid2sub.glossary.toml").write_text(TERMS, encoding="utf-8")
    ep = gone_last(backend, video)
    out = backend.retranslate(ep, "en", ids=None)
    assert asked == [[sid(0), sid(1)]] and tid(2) not in {c.id for c in
                                                         out.tracks.translations["en"]}
    assert backend.retranslate(out, "en", ids=None) is out and len(asked) == 1


# The model: chosen as M1 chooses it, cloud only when this call allows it (spec §7.2, §11.2)


def test_a_named_model_must_be_a_translation_model(backend, video, asked):
    with pytest.raises(EngineError, match="isn't a translation model in vid2sub.toml"):
        backend.retranslate(backend.open(str(video)), "en", ids=[sid(0)], model="nope")


def test_the_route_picks_a_model_and_the_request_goes_through_the_client_factory(tmp_path,
                                                                                video):
    def responder(req):
        if req.path.endswith("/models"):
            return 200, {"object": "list", "data": [{"id": "gemma", "object": "model"}]}, {}
        return chat_responder(req)

    with FakeServer(responder=responder) as srv:
        backend = make_backend(tmp_path, config(spark=srv.url))
        out = backend.retranslate(backend.open(str(video)), "en", ids=[sid(1)])
        chats = [r for r in srv.requests if r.path.endswith("/chat/completions")]
    assert out.tracks.translations["en"][1].text == f"EN {sid(1)}"
    assert len(chats) == 1 and chats[0].json()["model"] == "gemma"
    assert "Show" not in chats[0].body.decode("utf-8")  # no file name or title (spec §7.1)


def test_a_cloud_model_is_used_only_when_this_retranslation_allows_it(tmp_path, video):
    with FakeServer(responder=chat_responder) as srv:
        backend = make_backend(tmp_path, config(cloud=srv.url))
        ep = backend.open(str(video))
        with pytest.raises(EngineError) as err:
            backend.retranslate(ep, "en", ids=[sid(0)], model="cloud")
        assert err.value.kind == "cloud_not_allowed" and srv.requests == []
        out = backend.retranslate(ep, "en", ids=[sid(0)], model="cloud", allow_cloud=True)
        assert len(srv.requests) == 1
    assert out.tracks.translations["en"][0].text == f"EN {sid(0)}"


def test_a_down_server_never_falls_back_to_another_model_or_the_cloud(tmp_path, video):
    with FakeServer(responder=chat_responder) as srv:
        backend = make_backend(tmp_path, config(spark=closed_port_url(), cloud=srv.url))
        ep = backend.open(str(video))
        with pytest.raises(EngineError) as err:
            backend.retranslate(ep, "en", ids=[sid(0)], allow_cloud=True)
        assert err.value.kind == "connection" and srv.requests == []


def models_answering(status: int, body: dict):
    def responder(req):
        if req.path.endswith("/models"):
            return status, body, {}
        return chat_responder(req)
    return responder


@pytest.mark.parametrize("status, body, why", [
    (503, {"error": {"message": "overloaded"}}, "server"),
    (401, {"error": {"message": "unauthorised"}}, "auth"),
    (200, {"object": "list", "data": [{"id": "something-else", "object": "model"}]},
     "doesn't list gemma"),
])
def test_a_local_model_that_isnt_serving_is_never_replaced_by_the_cloud_or_another_model(
        tmp_path, video, status, body, why):
    with FakeServer(responder=chat_responder) as cloud, \
            FakeServer(responder=models_answering(status, body)) as spark:
        backend = make_backend(tmp_path, config(spark=spark.url, cloud=cloud.url))
        ep = backend.open(str(video))
        with pytest.raises(EngineError) as err:
            backend.retranslate(ep, "en", ids=[sid(0)], allow_cloud=True)
        chats = [r for r in spark.requests if r.path.endswith("/chat/completions")]
    assert err.value.kind == "unavailable" and "gemma" in str(err.value)
    assert "retries" not in str(err.value)  # the editor never retries
    assert "doesn't fall back" in err.value.hint and "doctor" in err.value.hint
    assert cloud.requests == [] and chats == []
    assert str(video.parent) not in str(err.value) + err.value.hint


def test_the_cloud_model_is_used_when_it_is_the_routes_own_pick_and_the_call_allows_it(
        tmp_path, video):
    with FakeServer(responder=chat_responder) as cloud:
        cfg = Config(endpoints={"openai": Endpoint(base_url=cloud.url)}, models={
            "cloud": ModelEntry(catalog="openai-gpt", endpoint="openai", model="gpt",
                                task="translate", api="completions")})
        backend = make_backend(tmp_path, cfg)
        out = backend.retranslate(backend.open(str(video)), "en", ids=[sid(0)], allow_cloud=True)
        assert len(cloud.requests) == 1
    assert out.tracks.translations["en"][0].text == f"EN {sid(0)}"


def test_a_glossary_vid2sub_cant_read_is_a_glossary_error_that_names_no_folder(
        backend, video, asked, monkeypatch):
    glossary = video.with_name("vid2sub.glossary.toml")
    glossary.write_text("[terms]\n", encoding="utf-8")
    ep = backend.open(str(video))
    real = Path.read_text

    def read_text(self, *args, **kwargs):
        if self.name == glossary.name:
            raise PermissionError(13, "Permission denied", str(self))
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_text)
    with pytest.raises(GlossaryError) as err:
        backend.retranslate(ep, "en", ids=[sid(0)])
    assert str(err.value) == "couldn't read vid2sub.glossary.toml (Permission denied)"
    assert str(video.parent) not in str(err.value) and asked == []


def test_a_glossary_whose_existence_check_is_refused_is_a_path_free_glossary_error(
        backend, video, asked, monkeypatch):
    ep = backend.open(str(video))
    real = Path.is_file

    def is_file(self, *args, **kwargs):
        if self.name == "vid2sub.glossary.toml":
            raise PermissionError(13, "Permission denied", str(self))
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "is_file", is_file)
    with pytest.raises(GlossaryError) as err:
        backend.retranslate(ep, "en", ids=[sid(0)])
    assert str(err.value) == "couldn't read vid2sub.glossary.toml (Permission denied)"
    assert str(video.parent) not in str(err.value) and asked == []


def test_allow_cloud_must_be_exactly_true_to_reach_a_cloud_model(tmp_path, video):
    with FakeServer(responder=chat_responder) as srv:
        backend = make_backend(tmp_path, config(cloud=srv.url))
        with pytest.raises(EngineError) as err:
            backend.retranslate(backend.open(str(video)), "en", ids=[sid(0)], model="cloud",
                                allow_cloud="false")  # type: ignore[arg-type]
        assert err.value.kind == "cloud_not_allowed" and srv.requests == []


# The plan itself, on any track: whole groups, so the result never overlaps


@st.composite
def tracks(draw):
    """Source cues with gaps; translations as contiguous groups, some edited, some stale, some
    left out (untranslated), and some cues sitting inside a group's span without being in its
    src, as a cue inserted between two that one translation covers."""
    source, t = [], 0
    for i in range(draw(st.integers(1, 12))):
        t += draw(st.integers(0, 500))
        dur = draw(st.integers(100, 2000))
        source.append(Cue(id=f"s{i}", start_ms=t, end_ms=t + dur, text=f"w{i}"))
        t += dur
    cues, k = [], 0
    while k < len(source):
        size = draw(st.integers(1, 3))
        group = source[k:k + size]
        k += size
        if draw(st.booleans()) and len(group) == 3:
            src = (group[0].id, group[2].id)  # the middle one was inserted later
        elif draw(st.integers(0, 4)) == 0:
            continue  # untranslated
        else:
            src = tuple(c.id for c in group)
        texts = [c.text for c in source if c.id in src]
        cues.append(Cue(id=f"t{k}", start_ms=group[0].start_ms, end_ms=group[-1].end_ms,
                        text="T", src=src,
                        src_sha=src_sha(texts) if draw(st.booleans()) else "stale",
                        flags=("edited",) if draw(st.integers(0, 3)) == 0 else ()))
    ids = draw(st.none() | st.lists(st.sampled_from([c.id for c in source]), max_size=4))
    return source, cues, ids


@settings(max_examples=300, deadline=None)
@given(tracks(), st.randoms())
def test_a_retranslation_never_overlaps_never_covers_a_cue_twice_and_keeps_edits(case, rnd):
    source, cues, ids = case
    check_track(cues)
    wanted, replaced = web_backend.retranslation(source, cues, ids)
    by_id = {c.id: c for c in source}
    order = [c.id for c in source]
    assert wanted == sorted(set(wanted), key=order.index)
    new, run = [], []
    for cid in wanted + [None]:  # the model may group any adjacent cues of a run
        if run and (cid is None or order.index(cid) != order.index(run[-1]) + 1
                    or rnd.random() < 0.5):
            new.append(Cue(id=f"n{len(new)}", start_ms=by_id[run[0]].start_ms,
                           end_ms=by_id[run[-1]].end_ms, text="N", src=tuple(run)))
            run = []
        if cid is not None:
            run.append(cid)
    kept = [c for c in cues if c.id not in replaced]
    result = sorted(kept + new, key=lambda c: (c.start_ms, c.end_ms))
    check_track(result)
    covered = [i for c in result for i in c.src or ()]
    assert len(covered) == len(set(covered))
    if ids is None:
        assert not {c.id for c in cues if "edited" in c.flags} & replaced
    else:
        assert set(ids) <= set(wanted)  # a named cue is always translated
