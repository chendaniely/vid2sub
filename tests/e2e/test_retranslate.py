"""Retranslating in Chromium, against `vid2sub serve --demo` and its canned translation (spec
§13.4, §20, §7.2; S30, the plan's Decisions 8 and 9): Retranslate stale changes only the stale
cues and keeps the translations a person edited; the selected cues, a run of them picked with
Shift, are retranslated even where edited; Allow cloud models starts unticked and unticks again
after each request; and a crashed tab's draft never replays a retranslation. Run with
`make e2e`."""

import re
import threading
from dataclasses import dataclass
from pathlib import Path

import pytest
from episodes import make_episode
from fakes import FakeServer, chat_responder
from playwright.sync_api import expect

from vid2sub.web.demo import JAPANESE, NO_TRANSLATION

pytestmark = pytest.mark.e2e

COLLEGE, STATE = JAPANESE[1][1], JAPANESE[2][1]  # the canned Japanese of rows 2 and 3


def open_demo(page, server):
    copy = next(server.tmp.glob("vid2sub-demo-*/demo"))
    page.get_by_test_id("open-path").fill(str(copy / "jfk.mp4"))
    page.get_by_test_id("open-button").click()
    rows = page.get_by_test_id("cue-row")
    expect(rows).to_have_count(4)
    return rows


def edit(page, cell, text: str) -> None:
    """Edits a source cell (`cue-text`) or a translation cell (`cue-translation`)."""
    cell.click()
    page.keyboard.press("Enter")
    page.get_by_test_id("cue-editor").fill(text)
    page.keyboard.press("ControlOrMeta+Enter")
    expect(cell).to_have_text(text)


def translation(rows, k: int) -> str:
    return rows.nth(k).get_by_test_id("cue-translation").inner_text().replace("\n", "")


def notices(page) -> list[str]:
    return [t.removesuffix("×").strip() for t in page.get_by_test_id("notice").all_inner_texts()]


def test_retranslate_stale_changes_only_the_stale_cues_and_keeps_edited_translations(
        page, server):
    # S30: two source cues changed; the translation of one of them was edited by hand.
    rows = open_demo(page, server)
    first = translation(rows, 0)
    edit(page, rows.nth(3).get_by_test_id("cue-translation"), "力強い州。")
    edit(page, rows.nth(3).get_by_test_id("cue-text"), "in a state noted for strength,")
    edit(page, rows.nth(2).get_by_test_id("cue-text"), "We meet at a college known for knowledge,")
    expect(rows.nth(2).locator("[data-flag=stale]")).to_have_count(1)
    expect(rows.nth(3).locator("[data-flag=stale]")).to_have_count(1)
    allow = page.get_by_test_id("allow-cloud")
    expect(allow).not_to_be_checked()  # §7.2: unticked every time
    page.get_by_test_id("retranslate-stale").click()
    expect(rows.nth(2).get_by_test_id("cue-translation")).to_have_text(NO_TRANSLATION)
    assert translation(rows, 3) == "力強い州。"  # edited: kept (§13.4)
    assert translation(rows, 0) == first  # not stale: untouched
    expect(rows.nth(2).locator("[data-flag=stale]")).to_have_count(0)
    expect(rows.nth(3).locator("[data-flag=edited]")).to_have_count(1)
    assert notices(page) == ["Retranslated 1 Japanese cue"]
    page.get_by_test_id("retranslate-stale").click()
    expect(page.get_by_test_id("notice")).to_have_count(2)
    assert notices(page)[-1] == ("Nothing to retranslate: no Japanese cue is stale or "
                                 "untranslated, apart from those you edited")
    page.get_by_test_id("tool-undo").click()  # one undo step
    expect(rows.nth(2).get_by_test_id("cue-translation")).to_have_text(
        re.compile("^私たちが集うのは"))


def test_the_selected_cues_are_retranslated_even_where_edited_and_the_cloud_box_unticks(
        page, server):
    # Decision 8: the person named them; spec §7.2: the box unticks after each request.
    rows = open_demo(page, server)
    edit(page, rows.nth(2).get_by_test_id("cue-translation"), "大学。")
    rows.nth(2).get_by_test_id("cue-text").click()
    rows.nth(3).get_by_test_id("cue-text").click(modifiers=["Shift"])
    for k, selected in enumerate(["false", "false", "true", "true"]):
        expect(rows.nth(k)).to_have_attribute("aria-selected", selected)
    named = page.get_by_test_id("retranslate-selected")
    expect(named).to_have_text("Retranslate 2 cues")
    allow = page.get_by_test_id("allow-cloud")
    allow.check()
    named.click()
    expect(allow).not_to_be_checked()
    expect(rows.nth(2).get_by_test_id("cue-translation")).not_to_have_text("大学。")
    assert translation(rows, 2) == COLLEGE and translation(rows, 3) == STATE
    assert notices(page) == ["Retranslated 2 Japanese cues"]
    # Shift+↓ grows the selection by keyboard, ↓ alone goes back to one cue (S37)
    rows.first.get_by_test_id("cue-text").click()
    page.get_by_test_id("cue-list").focus()
    page.keyboard.press("Shift+ArrowDown")
    page.keyboard.press("Shift+ArrowDown")
    expect(named).to_have_text("Retranslate 3 cues")
    page.keyboard.press("ArrowDown")
    expect(named).to_have_text("Retranslate this cue")
    expect(page.get_by_test_id("cue-list")).to_have_attribute("aria-multiselectable", "true")


def test_a_crashed_tabs_draft_never_replays_a_retranslation_or_the_undo_that_undid_it(
        open_page, server):
    first = open_page(server)
    a = first.page
    rows = open_demo(a, server)
    edit(a, rows.nth(2).get_by_test_id("cue-translation"), "大学。")
    rows.nth(2).get_by_test_id("cue-text").click()
    a.get_by_test_id("retranslate-selected").click()
    expect(rows.nth(2).get_by_test_id("cue-translation")).not_to_have_text("大学。")
    a.get_by_test_id("tool-undo").click()  # takes back the retranslation, not the edit
    expect(rows.nth(2).get_by_test_id("cue-translation")).to_have_text("大学。")
    edit(a, rows.nth(1).get_by_test_id("cue-text"), "occasion!")
    a.close()  # a crash: no warning, no Save
    second = open_page(server)
    b = second.page
    rows = open_demo(b, server)
    expect(b.get_by_test_id("draft")).to_contain_text("2 unsaved edits from")
    b.get_by_test_id("draft-restore").click()
    expect(rows.nth(1).get_by_test_id("cue-text")).to_have_text("occasion!")
    expect(rows.nth(2).get_by_test_id("cue-translation")).to_have_text("大学。")
    assert notices(b) == []  # nothing replayed failed, and no model was asked
    assert first.errors == [] and second.errors == [] and second.violations() == []


def test_a_step_that_changed_nothing_never_makes_restore_take_back_the_wrong_one(open_page,
                                                                                server):
    # Task 17's review: a nudge with nowhere to go pushes no undo step on the server, so the
    # draft drops it; kept, Restore would follow the wrong undo history and lose the redone edit.
    first = open_page(server)
    a = first.page
    rows = open_demo(a, server)
    edit(a, rows.nth(1).get_by_test_id("cue-text"), "occasion!")
    a.get_by_test_id("tool-undo").click()
    expect(rows.nth(1).get_by_test_id("cue-text")).to_have_text("occasion.")
    rows.nth(0).get_by_test_id("cue-text").click()
    a.keyboard.press("Alt+ArrowLeft")  # the first cue starts at 0: the nudge changes nothing
    a.get_by_test_id("tool-redo").click()
    expect(rows.nth(1).get_by_test_id("cue-text")).to_have_text("occasion!")
    a.close()
    second = open_page(server)
    b = second.page
    rows = open_demo(b, server)
    expect(b.get_by_test_id("draft")).to_contain_text("3 unsaved edits from")
    b.get_by_test_id("draft-restore").click()
    expect(rows.nth(1).get_by_test_id("cue-text")).to_have_text("occasion!")
    expect(b.get_by_test_id("draft")).to_have_count(0)
    assert notices(b) == [] and second.errors == [] and second.violations() == []


def test_an_undo_with_nothing_to_undo_after_a_pick_never_makes_restore_take_back_a_real_edit(
        open_page, server):
    # Task 16's Spec review, I-2: a pick starts the undo history again, so Ctrl+Z then has nothing
    # to undo; kept in the draft as made, Restore would apply the edit and then undo it.
    first, second = open_page(server), open_page(server)
    a, b = first.page, second.page
    rows_a, rows_b = open_demo(a, server), open_demo(b, server)
    for page, rows, text in ((a, rows_a, "訳A"), (b, rows_b, "訳B")):  # two Saves from one version
        edit(page, rows.nth(0).get_by_test_id("cue-translation-line").first, text)
        page.get_by_test_id("save").click()
        if page is a:
            expect(a.get_by_test_id("save-state")).to_have_text("All changes saved")
    expect(b.locator("dialog[open]")).to_be_visible()  # the Japanese track is in conflict
    b.keyboard.press("Escape")
    edit(b, rows_b.nth(1).get_by_test_id("cue-text"), "source edit before the pick")
    b.get_by_test_id("pick-version").click()
    b.get_by_test_id("version").first.check()
    b.get_by_test_id("keep-ja").click()
    expect(b.get_by_test_id("pick-version")).to_have_count(0)
    b.get_by_test_id("cue-list").focus()
    b.keyboard.press("ControlOrMeta+z")  # nothing to undo
    b.wait_for_timeout(400)
    expect(b.get_by_test_id("save-state")).to_have_text("Unsaved changes")
    b.close()  # a crash
    third = open_page(server)
    c = third.page
    rows_c = open_demo(c, server)
    expect(c.get_by_test_id("draft")).to_have_count(1)
    c.get_by_test_id("draft-restore").click()
    expect(rows_c.nth(1).get_by_test_id("cue-text")).to_have_text("source edit before the pick")
    expect(c.get_by_test_id("save-state")).to_have_text("Unsaved changes")
    assert third.errors == [] and third.violations() == []


def type_into_translation(page, rows, k: int, text: str) -> None:
    """Opens row k's translation box and types, without committing."""
    cell = rows.nth(k).get_by_test_id("cue-translation")
    cell.click()
    page.keyboard.press("Enter")
    page.get_by_test_id("cue-editor").fill(text)


def test_retranslating_a_cue_commits_the_box_open_on_it_first(page, server):
    # Task 17's Spec review, C-1: Esc and Cancel are the only discards, so Retranslate commits an
    # open box as Save does: the typed text is an undo step, the retranslation the next.
    rows = open_demo(page, server)
    type_into_translation(page, rows, 2, "手で直した訳")
    page.get_by_test_id("retranslate-selected").click()
    expect(page.get_by_test_id("cue-editor")).to_have_count(0)
    expect(page.get_by_test_id("notice")).to_have_count(1)
    assert notices(page) == ["Retranslated 1 Japanese cue"] and translation(rows, 2) == COLLEGE
    page.get_by_test_id("tool-undo").click()  # the retranslation
    expect(rows.nth(2).get_by_test_id("cue-translation")).to_have_text("手で直した訳")
    expect(page.get_by_test_id("cue-editor")).to_have_count(0)  # committed text, not a box again


def test_retranslate_stale_commits_the_box_open_on_a_stale_cue_and_keeps_it(page, server):
    # C-1: the typed fix makes the translation an edited one, which Retranslate stale never
    # replaces; dropped, it was lost with the box.
    rows = open_demo(page, server)
    edit(page, rows.nth(2).get_by_test_id("cue-text"), "We meet at a college known for knowledge,")
    expect(rows.nth(2).locator("[data-flag=stale]")).to_have_count(1)
    type_into_translation(page, rows, 2, "手で直した訳")
    page.get_by_test_id("retranslate-stale").click()
    expect(page.get_by_test_id("cue-editor")).to_have_count(0)
    expect(page.get_by_test_id("notice")).to_have_count(1)  # "Nothing to retranslate": it is edited
    expect(rows.nth(2).get_by_test_id("cue-translation")).to_have_text("手で直した訳")
    expect(rows.nth(2).locator("[data-flag=edited]")).to_have_count(1)


def test_restore_after_editing_a_retranslations_new_cue_and_undoing_it_keeps_the_first_edit(
        open_page, server):
    # Task 17's Spec review, C-2: the edit to the cue a retranslation made can't be replayed (the
    # restored episode never had the cue), so neither can the undo that took it back.
    first = open_page(server)
    a = first.page
    rows = open_demo(a, server)
    edit(a, rows.nth(1).get_by_test_id("cue-text"), "occasion!")
    rows.nth(2).get_by_test_id("cue-text").click()
    a.get_by_test_id("retranslate-selected").click()
    expect(a.get_by_test_id("notice")).to_have_count(1)
    edit(a, rows.nth(2).get_by_test_id("cue-translation"), "新訳")
    a.get_by_test_id("tool-undo").click()
    expect(rows.nth(2).get_by_test_id("cue-translation")).not_to_have_text("新訳")
    assert translation(rows, 2) == COLLEGE
    expect(rows.nth(1).get_by_test_id("cue-text")).to_have_text("occasion!")
    a.close()
    second = open_page(server)
    b = second.page
    rows = open_demo(b, server)
    expect(b.get_by_test_id("draft")).to_contain_text("1 unsaved edit from")
    b.get_by_test_id("draft-restore").click()
    expect(rows.nth(1).get_by_test_id("cue-text")).to_have_text("occasion!")
    expect(b.get_by_test_id("draft")).to_have_count(0)
    assert notices(b) == [] and second.errors == [] and second.violations() == []


# ---- a retranslation held on a loopback model: the tab's queue while it runs (Task 17, 17d) ----


@dataclass
class Held:
    server: object
    video: Path
    gate: threading.Event  # the model answers once this is set
    fake: FakeServer


@pytest.fixture
def held(launch, tmp_path):
    """A `vid2sub serve` with a translation model on a loopback fake that holds each chat answer
    until `gate` is set, and an episode with two translation tracks (en and ko). Nothing leaves
    this machine."""
    gate = threading.Event()

    def responder(req):
        if req.path.endswith("/models"):
            return 200, {"object": "list", "data": [{"id": "gemma", "object": "model"}]}, {}
        assert gate.wait(60)
        return chat_responder(req)

    with FakeServer(responder=responder) as fake:
        video = make_episode(tmp_path / "ep", targets=("en", "ko"), project=("ja", "en", "ko"))
        toml = (f'[endpoints.spark]\nbase_url = "{fake.url}"\n\n[models.gemma]\n'
                'catalog = "gemma-4-26b-a4b"\nendpoint = "spark"\nmodel = "gemma"\n'
                'task = "translate"\nlocal = true\n')
        server = launch(tmp_path / "server", toml=toml)
        try:
            yield Held(server, video, gate, fake)
        finally:
            gate.set()


def open_held(open_page, held, *, before=None):
    """The held server's episode, open; `before(page)` runs first (the page reloaded after it)."""
    page = open_page(held.server).page
    if before:
        before(page)
        page.reload()
    page.get_by_test_id("open-path").fill(str(held.video))
    page.get_by_test_id("open-button").click()
    rows = page.get_by_test_id("cue-row")
    expect(rows).to_have_count(3)
    return page, rows


def test_a_track_being_retranslated_opens_no_box_and_says_why_while_other_edits_wait(
        open_page, held):
    # Task 17's Spec review, C-3 (Dan's A, Q&A item 53) and I-2: an edit to a line the run
    # replaces would be refused, and its text lost; the page opens no box on the track while the
    # retranslation is pending or running, and a line says that other edits apply when it ends.
    page, rows = open_held(open_page, held)
    rows.nth(0).get_by_test_id("cue-text").click()
    page.get_by_test_id("retranslate-selected").click()
    note = page.get_by_test_id("retranslating-note")
    expect(note).to_contain_text("Retranslating the English translation")
    expect(note).to_contain_text("its lines can be edited when it finishes")
    expect(note).to_contain_text("other edits apply then")
    rows.nth(1).get_by_test_id("cue-translation").click()
    page.keyboard.press("Enter")
    page.get_by_test_id("tool-edit").click()
    expect(page.get_by_test_id("cue-editor")).to_have_count(0)  # nothing opens, and...
    expect(rows.nth(1).get_by_test_id("cue-translation")).to_have_text("How are you?")
    # ...another track, and the source, are not locked: a source edit queues behind the run
    rows.nth(2).get_by_test_id("cue-text").click()
    page.keyboard.press("Enter")
    page.get_by_test_id("cue-editor").fill("はい、元気です！")
    page.keyboard.press("ControlOrMeta+Enter")
    expect(page.get_by_test_id("cue-editor")).to_have_count(0)
    expect(rows.nth(2).get_by_test_id("cue-text")).to_have_text("はい、元気です")  # not yet
    held.gate.set()
    expect(rows.nth(2).get_by_test_id("cue-text")).to_have_text("はい、元気です！")
    expect(rows.nth(0).get_by_test_id("cue-translation")).to_have_text(re.compile(r"^EN ca"))
    expect(note).to_have_count(0)  # the lock ended with the result
    rows.nth(1).get_by_test_id("cue-translation").click()
    page.keyboard.press("Enter")
    expect(page.get_by_test_id("cue-editor")).to_have_count(1)


def hide_retranslating(page) -> None:
    """The page never hears `busy` is "retranslating": a request waiting behind another call in
    the tab's queue (a Save, the playback audio) looks like this, whose buttons the page itself
    must hold. Every other message goes through."""
    def through(ws):
        server = ws.connect_to_server()
        ws.on_message(lambda m: server.send(m))
        server.on_message(lambda m: None if '"retranslating"' in str(m) else ws.send(m))

    page.route_web_socket(re.compile(r".*/websocket/.*"), through)


def test_a_double_click_on_retranslate_sends_one_request(open_page, held):
    # Task 17's Spec review, I-1: the buttons were enabled until `busy` arrived, so a double-click
    # asked the model twice (and with two allow_cloud values).
    page, rows = open_held(open_page, held, before=hide_retranslating)
    page.evaluate("""() => {
        window.__sent = 0;
        const send = WebSocket.prototype.send;
        WebSocket.prototype.send = function (data) {
            if (String(data).includes("retranslate:shinyreact.default")) window.__sent += 1;
            return send.call(this, data);
        };
    }""")
    rows.nth(0).get_by_test_id("cue-text").click()
    page.get_by_test_id("retranslate-selected").dblclick()
    expect(page.get_by_test_id("retranslate-progress")).to_have_text("Waiting to retranslate…")
    expect(page.get_by_test_id("retranslating-note")).to_be_visible()  # pending counts too
    expect(page.get_by_test_id("retranslate-stale")).to_be_disabled()
    held.gate.set()
    expect(page.get_by_test_id("notice")).to_have_text(re.compile("^Retranslated 1 English cue"))
    # (a second click lands within Shiny's input debounce and would replace the first request,
    # which then never answers: its pending state would never end, so the track would stay
    # locked and its note shown)
    expect(page.get_by_test_id("retranslating-note")).to_have_count(0)
    expect(page.get_by_test_id("retranslate-selected")).to_be_enabled()
    expect(page.get_by_test_id("retranslate-stale")).to_be_enabled()
    assert page.evaluate("() => window.__sent") == 1
    assert len([r for r in held.fake.requests if r.path.endswith("/chat/completions")]) == 1


def test_each_translation_tracks_cloud_box_starts_unticked(open_page, held):
    # Task 17's Spec review (M-1), Decision 33: another track's box is its own.
    page, _rows = open_held(open_page, held)
    page.get_by_test_id("allow-cloud").check()
    page.get_by_test_id("track").select_option("ko")
    expect(page.get_by_test_id("allow-cloud")).not_to_be_checked()


def test_an_offered_draft_goes_when_the_person_retranslates_instead(open_page, server):
    # Decision 18, and the Spec review's M-1: editing (a retranslation too) instead of restoring
    # starts this tab afresh.
    first = open_page(server)
    a = first.page
    rows = open_demo(a, server)
    edit(a, rows.nth(0).get_by_test_id("cue-translation"), "訳A")
    a.close()
    second = open_page(server)
    b = second.page
    rows = open_demo(b, server)
    expect(b.get_by_test_id("draft")).to_have_count(1)
    b.get_by_test_id("retranslate-stale").click()
    expect(b.get_by_test_id("draft")).to_have_count(0)


def test_a_retranslation_that_changed_nothing_leaves_no_marker_to_swallow_an_undo(
        open_page, server):
    # The Spec review's M-1: a marker kept for a retranslation that changed nothing would take the
    # next undo on Restore and bring back an edit the person had undone.
    first = open_page(server)
    a = first.page
    rows = open_demo(a, server)
    edit(a, rows.nth(0).get_by_test_id("cue-translation"), "訳A")
    a.get_by_test_id("retranslate-stale").click()  # nothing is stale: it changes nothing
    expect(a.get_by_test_id("notice")).to_have_count(1)
    a.get_by_test_id("tool-undo").click()  # takes back 訳A
    expect(rows.nth(0).get_by_test_id("cue-translation")).not_to_have_text("訳A")
    a.close()
    second = open_page(server)
    b = second.page
    rows = open_demo(b, server)
    expect(b.get_by_test_id("draft")).to_contain_text("2 unsaved edits from")
    b.get_by_test_id("draft-restore").click()
    expect(b.get_by_test_id("draft")).to_have_count(0)
    expect(rows.nth(0).get_by_test_id("cue-translation")).not_to_have_text("訳A")
