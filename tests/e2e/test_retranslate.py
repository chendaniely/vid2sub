"""Retranslating in Chromium, against `vid2sub serve --demo` and its canned translation (spec
§13.4, §20, §7.2; S30, the plan's Decisions 8 and 9): Retranslate stale changes only the stale
cues and keeps the translations a person edited; the selected cues, a run of them picked with
Shift, are retranslated even where edited; Allow cloud models starts unticked and unticks again
after each request; and a crashed tab's draft never replays a retranslation. Run with
`make e2e`."""

import re

import pytest
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
