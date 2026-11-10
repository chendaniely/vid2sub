"""Editing in Chromium, against `vid2sub serve --demo` (spec §20, §13.5, §19.3; S28, S33, S37;
Review Focus 3): text, times, nudges, split, merge, insert and delete go through the server's
rules and come back with translations re-pointed and flagged, undo and redo walk them back and
forth, find and replace works across tracks with a glossary term held for Save, committing an
input method's candidate with Enter fires nothing, everything is done by keyboard with focus
visible, and an edit to a two-hour episode comes back in under a second. Run with `make e2e`."""

import re
import time
from pathlib import Path

import pytest
from episodes import make_episode
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e

LINE_1 = "I am delighted to be here, and I am"
LINE_2 = "particularly delighted to be here on this"


def open_demo(page, server):
    copy = next(server.tmp.glob("vid2sub-demo-*/demo"))
    page.get_by_test_id("open-path").fill(str(copy / "jfk.mp4"))
    page.get_by_test_id("open-button").click()
    rows = page.get_by_test_id("cue-row")
    expect(rows).to_have_count(4)
    return rows


def pick(rows, k: int) -> None:
    """Selects row k's source cell, as a click on its text does (a click on the translation
    selects that cell instead)."""
    rows.nth(k).get_by_test_id("cue-text").click()


def seek(page, seconds: float) -> None:
    page.get_by_test_id("media").evaluate(
        "(m, s) => new Promise((done) => { m.addEventListener('seeked', done, { once: true });"
        " m.currentTime = s; })", seconds)


def texts(page) -> list[str]:
    return page.get_by_test_id("cue-text").all_inner_texts()


def test_a_cue_edited_flags_its_translation_stale_and_undo_and_redo_walk_it_back_and_forth(
        page, server):
    rows = open_demo(page, server)
    pick(rows, 1)  # "occasion.", covered with cue 1 by the first Japanese cue
    expect(rows.nth(1)).to_have_attribute("aria-selected", "true")
    page.keyboard.press("Enter")
    box = page.get_by_test_id("cue-editor")
    expect(box).to_be_focused()
    expect(box).to_have_value("occasion.")
    box.fill("occasion!")
    page.keyboard.press("ControlOrMeta+Enter")
    expect(rows.nth(1).get_by_test_id("cue-text")).to_have_text("occasion!")
    expect(page.get_by_test_id("cue-list")).to_be_focused()  # back in navigate mode
    expect(rows.first.locator("[data-flag=stale]")).to_have_count(1)  # §13.5: flagged
    page.get_by_test_id("tool-undo").click()
    expect(rows.nth(1).get_by_test_id("cue-text")).to_have_text("occasion.")
    expect(rows.first.locator("[data-flag=stale]")).to_have_count(0)
    page.get_by_test_id("cue-list").focus()
    page.keyboard.press("ControlOrMeta+Shift+Z")
    expect(rows.nth(1).get_by_test_id("cue-text")).to_have_text("occasion!")
    page.keyboard.press("ControlOrMeta+Z")
    expect(rows.nth(1).get_by_test_id("cue-text")).to_have_text("occasion.")
    expect(page.get_by_test_id("tool-undo")).to_be_disabled()


def test_split_merge_nudge_set_times_insert_and_delete_go_through_the_servers_rules(
        page, server):
    rows = open_demo(page, server)
    times = page.get_by_test_id("cue-times")
    # Split at the caret: the end of the first cue's first line.
    pick(rows, 0)
    page.keyboard.press("Enter")
    # (Home and End move the caret on Linux and Windows, not on macOS: the caret is set directly)
    page.get_by_test_id("cue-editor").evaluate(f"e => e.setSelectionRange({len(LINE_1)}, "
                                               f"{len(LINE_1)})")
    page.keyboard.press("ControlOrMeta+Shift+S")
    expect(rows).to_have_count(5)
    assert texts(page)[:2] == [LINE_1, LINE_2]
    # the Japanese cue that covered cue 1 now covers both halves, flagged stale (§13.5)
    expect(rows.first.locator("[data-flag=stale]")).to_have_count(1)
    # Merge them again, from the edit bar.
    pick(rows, 0)
    page.get_by_test_id("tool-merge").click()
    expect(rows).to_have_count(4)
    assert texts(page)[0] == f"{LINE_1}\n{LINE_2}"
    # Nudge cue 3 (4.940 to 9.276): 100 ms earlier, then 500 ms, stopped by cue 2's end (4.653).
    pick(rows, 2)
    page.keyboard.press("Alt+ArrowLeft")
    expect(times.nth(2)).to_have_text("0:04.840 → 0:09.176")
    page.keyboard.press("Shift+Alt+ArrowLeft")
    expect(times.nth(2)).to_have_text("0:04.653 → 0:08.989")
    # [ and ] set its start and end to the playhead.
    seek(page, 5.5)
    page.get_by_test_id("cue-list").focus()
    page.keyboard.press("[")
    expect(times.nth(2)).to_have_text("0:05.500 → 0:08.989")
    seek(page, 8.0)
    page.keyboard.press("]")
    expect(times.nth(2)).to_have_text("0:05.500 → 0:08.000")
    # Insert at the playhead, in the gap after cue 2: a new cue, untranslated, edited at once.
    seek(page, 4.8)
    page.get_by_test_id("tool-insert").click()
    expect(rows).to_have_count(5)
    box = page.get_by_test_id("cue-editor")
    expect(box).to_be_focused()
    box.fill("Hm.")
    page.keyboard.press("ControlOrMeta+Enter")
    new = rows.nth(2)
    expect(new.get_by_test_id("cue-text")).to_have_text("Hm.")
    expect(new.get_by_test_id("cue-times")).to_have_text("0:04.800 → 0:05.500")
    expect(new.locator("[data-flag=untranslated]")).to_have_count(1)
    page.get_by_test_id("tool-delete").click()
    expect(rows).to_have_count(4)
    assert "Hm." not in texts(page)


def test_find_and_replace_works_across_tracks_and_a_glossary_term_waits_for_save(page, server):
    rows = open_demo(page, server)
    page.get_by_test_id("tool-find").click()
    page.get_by_test_id("find").fill("delighted")
    expect(page.get_by_test_id("match-count")).to_have_text("2 matches")
    page.get_by_test_id("find-track-en").uncheck()
    expect(page.get_by_test_id("match-count")).to_have_text("0 matches")
    page.get_by_test_id("find-track-en").check()
    page.get_by_test_id("replace").fill("pleased")
    page.get_by_test_id("replace-all").click()
    expect(rows.first.get_by_test_id("cue-text")).to_have_text(
        "I am pleased to be here, and I am\nparticularly pleased to be here on this")
    expect(page.get_by_test_id("match-count")).to_have_text("0 matches")
    page.get_by_test_id("glossary-term").fill("ケネディ")
    page.get_by_test_id("glossary-translation").fill("Kennedy")
    page.get_by_test_id("glossary-add").click()
    expect(page.get_by_test_id("glossary-adds")).to_have_text("ケネディ → Kennedy (written at Save)")
    # A term waiting for Save makes every cue of the translation stale (Decision 9).
    expect(page.get_by_test_id("episode-notes")).to_contain_text("Every Japanese cue is stale")
    page.get_by_test_id("tool-undo").click()  # the glossary add is an undo step too
    expect(page.get_by_test_id("glossary-adds")).to_have_count(0)


def test_committing_an_input_methods_candidate_with_enter_fires_no_editor_action(page, server):
    # S33, through Chromium's own IME path (CDP Input.imeSetComposition, then Input.insertText to
    # commit), with Enter sent while the composition runs, as a Japanese IME sends it.
    rows = open_demo(page, server)
    pick(rows, 1)
    page.keyboard.press("Enter")
    box = page.get_by_test_id("cue-editor")
    box.fill("")
    page.evaluate("""() => {
        window.__keys = [];
        document.addEventListener('keydown', (e) => window.__keys.push(
            [e.key, e.keyCode, e.isComposing]), true);
    }""")
    cdp = page.context.new_cdp_session(page)
    cdp.send("Input.imeSetComposition", {"text": "にほんご", "selectionStart": 4,
                                         "selectionEnd": 4})
    expect(box).to_have_value("にほんご")
    cdp.send("Input.dispatchKeyEvent", {"type": "rawKeyDown", "key": "Enter", "code": "Enter",
                                        "windowsVirtualKeyCode": 229,
                                        "nativeVirtualKeyCode": 229})
    cdp.send("Input.insertText", {"text": "日本語"})
    cdp.send("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Enter", "code": "Enter",
                                        "windowsVirtualKeyCode": 13})
    expect(box).to_have_value("日本語")
    assert page.evaluate("() => window.__keys") == [["Enter", 229, True]]
    # Nothing fired: still in edit mode, the cue unchanged on the server, no undo step.
    expect(box).to_be_focused()
    expect(page.get_by_test_id("tool-undo")).to_be_disabled()
    # A plain keydown that says it is composing is ignored in navigate mode too.
    page.keyboard.press("Escape")
    expect(page.get_by_test_id("cue-list")).to_be_focused()
    page.get_by_test_id("cue-list").dispatch_event("keydown", {"key": "Enter", "isComposing": True})
    expect(page.get_by_test_id("cue-editor")).to_have_count(0)
    page.keyboard.press("Enter")  # and without the composition, Enter edits
    expect(page.get_by_test_id("cue-editor")).to_be_focused()
    page.keyboard.press("ControlOrMeta+Enter")  # nothing changed, so nothing is sent
    expect(rows.nth(1).get_by_test_id("cue-text")).to_have_text("occasion.")


def test_the_editor_works_by_keyboard_alone_with_focus_always_visible(page, server):
    # S37, spec §19.3: Tab reaches the cue list, the keyboard model selects a cue, and then
    # Shift+Tab reaches every button of the edit bar, each with its focus visible.
    rows = open_demo(page, server)
    page.get_by_test_id("follow").focus()
    for _ in range(10):
        page.keyboard.press("Tab")
        if page.evaluate("() => document.activeElement.dataset.testid") == "cue-list":
            break
    expect(page.get_by_test_id("cue-list")).to_be_focused()
    page.keyboard.press("ArrowDown")
    expect(rows.first).to_have_attribute("aria-selected", "true")
    page.keyboard.press("ArrowDown")
    expect(rows.nth(1)).to_have_attribute("aria-selected", "true")
    expect(page.get_by_test_id("cue-list")).to_have_attribute(
        "aria-activedescendant", re.compile(r"^cue-c[0-9a-f]{8}$"))
    seen = []
    for _ in range(10):
        page.keyboard.press("Shift+Tab")
        found = page.evaluate("() => document.activeElement.dataset.testid || null")
        if not (found or "").startswith("tool-"):
            break
        seen.append(found)
        assert page.evaluate("""() => document.activeElement.matches(':focus-visible')
            && getComputedStyle(document.activeElement).outlineStyle !== 'none'"""), found
    # Undo and Redo are disabled until there is something to undo, so Tab passes them by.
    assert seen == ["tool-find", "tool-delete", "tool-insert", "tool-merge", "tool-split",
                    "tool-later", "tool-earlier", "tool-end", "tool-start", "tool-edit"]
    page.get_by_test_id("cue-list").focus()
    page.keyboard.press("ArrowRight")  # the translation cell: none starts in this row
    expect(rows.nth(1).get_by_test_id("cue-translation")).to_have_text("—")
    expect(rows.nth(1).get_by_test_id("cue-translation")).to_have_attribute("data-selected", "true")
    page.keyboard.press("ArrowUp")
    expect(rows.first.get_by_test_id("cue-translation")).to_have_attribute("data-selected", "true")
    page.keyboard.press("Enter")
    box = page.get_by_test_id("cue-editor")
    expect(box).to_have_value(re.compile("^ここに来られて"))
    box.fill("ここに来られてうれしいです。")
    page.keyboard.press("ControlOrMeta+Enter")
    expect(rows.first.get_by_test_id("cue-translation")).to_have_text("ここに来られてうれしいです。")
    expect(rows.first.locator("[data-flag=edited]")).to_have_count(1)  # Decision 4
    page.keyboard.press("ArrowLeft")
    page.keyboard.press("Enter")
    page.keyboard.press("Escape")  # leaves edit mode without sending anything
    expect(page.get_by_test_id("cue-editor")).to_have_count(0)
    expect(page.get_by_test_id("cue-list")).to_be_focused()
    media = page.get_by_test_id("media")
    media.evaluate("m => { m.muted = true; }")
    page.keyboard.press(" ")
    page.wait_for_function("() => !document.querySelector('[data-testid=media]').paused")
    page.keyboard.press("k")
    page.wait_for_function("() => document.querySelector('[data-testid=media]').paused")
    seek(page, 6.0)
    page.get_by_test_id("cue-list").focus()
    page.keyboard.press("j")
    page.wait_for_function("() => document.querySelector('[data-testid=media]').currentTime < 4.1")
    page.keyboard.press("l")
    page.wait_for_function("() => !document.querySelector('[data-testid=media]').paused")
    page.keyboard.press("k")
    expect(page.get_by_test_id("tool-undo")).to_be_enabled()


def test_an_edit_to_a_two_hour_episode_comes_back_in_under_a_second(page, server):
    # Review Focus 3: 2,000 cues; the edit, the new view and its render, end to end.
    copy = next(server.tmp.glob("vid2sub-demo-*/demo"))
    video = make_episode(Path(copy) / "long", n=2000)
    page.get_by_test_id("open-path").fill(str(video))
    page.get_by_test_id("open-button").click()
    rows = page.get_by_test_id("cue-row")
    rows.first.click()
    page.keyboard.press("Enter")
    page.get_by_test_id("cue-editor").fill("新しい台詞")
    began = time.monotonic()
    page.keyboard.press("ControlOrMeta+Enter")
    expect(rows.first.get_by_test_id("cue-text")).to_have_text("新しい台詞")
    elapsed = time.monotonic() - began
    assert elapsed < 1.0, f"{elapsed:.2f} s"


def test_markup_typed_into_a_cue_is_shown_as_text_and_the_overlay_draws_only_italics(page, server):
    # Task 14's review: a literal <b> can arrive by an edit. Spec §6.3.
    rows = open_demo(page, server)
    pick(rows, 1)
    page.keyboard.press("Enter")
    page.get_by_test_id("cue-editor").fill("<b>bold</b> <i>slant</i> <img src=x>")
    page.keyboard.press("ControlOrMeta+Enter")
    text = rows.nth(1).get_by_test_id("cue-text")
    expect(text).to_have_text("<b>bold</b> <i>slant</i> <img src=x>")
    assert rows.nth(1).locator("b, i, img").count() == 0  # all text, no elements
    seek(page, 4.0)
    overlay = page.get_by_test_id("captions")
    expect(overlay).to_contain_text("bold")
    assert overlay.locator("b, img").count() == 0
    assert overlay.locator("i").all_inner_texts() == ["slant"]
