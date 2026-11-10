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
    for _ in range(16):
        page.keyboard.press("Shift+Tab")
        found = page.evaluate("() => document.activeElement.dataset.testid || null")
        if not (found or "").startswith("tool-"):
            break
        seen.append(found)
        assert page.evaluate("""() => document.activeElement.matches(':focus-visible')
            && getComputedStyle(document.activeElement).outlineStyle !== 'none'"""), found
    # Undo and Redo are disabled until there is something to undo, so Tab passes them by.
    assert seen == ["tool-find", "tool-delete", "tool-insert", "tool-merge", "tool-split",
                    "tool-later-500", "tool-later", "tool-earlier", "tool-earlier-500", "tool-end",
                    "tool-start", "tool-edit"]
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
    # While a box is open the bar also has Commit and Cancel, reached next to Edit (S-4).
    page.get_by_test_id("tool-edit").focus()
    for wanted in ("tool-commit", "tool-cancel"):
        page.keyboard.press("Tab")
        assert page.evaluate("() => document.activeElement.dataset.testid") == wanted
        assert page.evaluate("""() => document.activeElement.matches(':focus-visible')
            && getComputedStyle(document.activeElement).outlineStyle !== 'none'"""), wanted
    box.focus()
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


# ---- fix round 15d: found by Task 15's Spec review ----------------------------------------------


def standing(page) -> None:
    expect(page.get_by_test_id("app")).to_have_count(1)  # a render error unmounts the whole page


def start_ms(page, k: int) -> int:
    m, s, ms = re.match(r"(\d+):(\d+)\.(\d+)", page.get_by_test_id("cue-times").nth(k).inner_text(
    )).groups()
    return (int(m) * 60 + int(s)) * 1000 + int(ms)


def test_deleting_the_last_cue_while_it_is_current_leaves_the_page_standing(page, server):
    # S-1: the current cue's index outlived the cue
    rows = open_demo(page, server)
    pick(rows, 3)
    expect(rows.nth(3)).to_have_attribute("aria-current", "true")
    page.get_by_test_id("tool-delete").click()
    expect(rows).to_have_count(3)
    standing(page)


def test_merging_the_last_two_cues_with_the_playhead_in_the_last_leaves_the_page_standing(
        page, server):
    rows = open_demo(page, server)
    pick(rows, 2)
    seek(page, 10.0)
    page.get_by_test_id("cue-list").focus()
    expect(rows.nth(3)).to_have_attribute("aria-current", "true")
    page.get_by_test_id("tool-merge").click()
    expect(rows).to_have_count(3)
    standing(page)


def test_undoing_an_insert_at_the_end_while_it_is_current_leaves_the_page_standing(page, server):
    rows = open_demo(page, server)
    seek(page, 13.9)
    page.get_by_test_id("tool-insert").click()
    expect(rows).to_have_count(5)
    page.keyboard.press("Escape")
    seek(page, 14.0)
    expect(rows.nth(4)).to_have_attribute("aria-current", "true")
    page.get_by_test_id("tool-undo").click()
    expect(rows).to_have_count(4)
    standing(page)


def test_undoing_a_split_of_the_last_cue_with_its_second_half_selected_leaves_the_page_standing(
        page, server):
    rows = open_demo(page, server)
    pick(rows, 3)
    page.keyboard.press("Enter")
    page.get_by_test_id("cue-editor").evaluate("e => e.setSelectionRange(10, 10)")
    page.keyboard.press("ControlOrMeta+Shift+S")
    expect(rows).to_have_count(5)
    pick(rows, 4)
    expect(rows.nth(4)).to_have_attribute("aria-current", "true")
    page.get_by_test_id("tool-undo").click()
    expect(rows).to_have_count(4)
    standing(page)


def test_deleting_a_middle_cue_while_paused_leaves_no_stale_text_in_the_overlay(page, server):
    rows = open_demo(page, server)
    pick(rows, 1)
    expect(rows.nth(1)).to_have_attribute("aria-current", "true")
    expect(page.get_by_test_id("captions")).to_contain_text("occasion.")
    page.get_by_test_id("tool-delete").click()
    expect(rows).to_have_count(3)
    # the playhead is now in a gap: nothing shows, and above all not the next cue's text
    expect(page.get_by_test_id("captions")).not_to_contain_text("We meet at a college")
    expect(page.get_by_test_id("captions")).not_to_contain_text("occasion.")
    assert page.locator("[data-testid=cue-row][aria-current=true]").count() == 0


def test_a_draft_is_kept_when_the_person_clicks_another_cue(page, server):
    # S-2: Esc is the only way out of edit mode that discards
    rows = open_demo(page, server)
    pick(rows, 1)
    page.keyboard.press("Enter")
    page.get_by_test_id("cue-editor").fill("occasion!!")
    pick(rows, 2)
    expect(page.get_by_test_id("cue-editor")).to_have_count(0)
    expect(rows.nth(1).get_by_test_id("cue-text")).to_have_text("occasion!!")
    expect(page.get_by_test_id("tool-undo")).to_be_enabled()
    expect(rows.nth(2)).to_have_attribute("aria-selected", "true")
    page.get_by_test_id("tool-undo").click()
    expect(rows.nth(1).get_by_test_id("cue-text")).to_have_text("occasion.")


def test_the_edit_button_keeps_the_draft_and_insert_commits_it(page, server):
    rows = open_demo(page, server)
    pick(rows, 0)
    page.keyboard.press("Enter")
    box = page.get_by_test_id("cue-editor")
    box.fill("A draft")
    page.get_by_test_id("tool-edit").click()
    expect(box).to_have_value("A draft")
    expect(box).to_be_focused()
    seek(page, 4.8)
    page.get_by_test_id("tool-insert").click()
    expect(rows).to_have_count(5)
    expect(rows.first.get_by_test_id("cue-text")).to_have_text("A draft")  # committed, not lost
    expect(page.get_by_test_id("cue-editor")).to_have_value("…")  # and the new cue is open
    page.keyboard.press("Escape")
    page.get_by_test_id("tool-undo").click()  # the insert
    page.get_by_test_id("tool-undo").click()  # the draft
    expect(rows.first.get_by_test_id("cue-text")).to_have_text(LINE_1 + "\n" + LINE_2)


def test_a_click_away_never_lets_a_split_land_on_another_cue(page, server):
    # S-3: the measured case, a box open on cue 1, cue 3 selected, the caret back in the box
    rows = open_demo(page, server)
    before = texts(page)
    pick(rows, 0)
    page.keyboard.press("Enter")
    page.get_by_test_id("cue-editor").evaluate("e => e.setSelectionRange(10, 10)")
    pick(rows, 2)
    expect(page.get_by_test_id("cue-editor")).to_have_count(0)
    page.keyboard.press("ControlOrMeta+Shift+S")
    page.wait_for_timeout(300)
    expect(rows).to_have_count(4)
    assert texts(page) == before


def test_a_commit_goes_to_the_track_the_box_was_opened_on(page, server):
    # S-3: with two translations the track select can change while a box is open
    video = make_episode(Path(next(server.tmp.glob("vid2sub-demo-*/demo"))) / "two",
                         targets=("en", "ko"))
    page.get_by_test_id("open-path").fill(str(video))
    page.get_by_test_id("open-button").click()
    rows = page.get_by_test_id("cue-row")
    expect(rows.first).to_be_visible()
    page.get_by_test_id("track").select_option("en")
    rows.first.get_by_test_id("cue-translation").click()
    page.keyboard.press("Enter")
    box = page.get_by_test_id("cue-editor")
    box.fill("Good day")
    page.get_by_test_id("track").select_option("ko")
    box = page.get_by_test_id("cue-editor")
    box.focus()
    page.keyboard.press("ControlOrMeta+Enter")
    page.get_by_test_id("track").select_option("en")
    expect(rows.first.get_by_test_id("cue-translation")).to_have_text("Good day")
    assert page.get_by_test_id("notice").count() == 0


def test_a_mouse_can_commit_cancel_and_nudge_by_500_ms(page, server):
    # S-4
    rows = open_demo(page, server)
    expect(page.get_by_test_id("tool-commit")).to_have_count(0)
    pick(rows, 1)
    page.get_by_test_id("tool-edit").click()
    page.get_by_test_id("cue-editor").fill("occasion?")
    page.get_by_test_id("tool-commit").click()
    expect(rows.nth(1).get_by_test_id("cue-text")).to_have_text("occasion?")
    expect(page.get_by_test_id("cue-editor")).to_have_count(0)
    page.get_by_test_id("tool-edit").click()
    page.get_by_test_id("cue-editor").fill("never sent")
    page.get_by_test_id("tool-cancel").click()
    expect(rows.nth(1).get_by_test_id("cue-text")).to_have_text("occasion?")
    assert page.get_by_test_id("cue-editor").count() == 0
    pick(rows, 3)
    was = start_ms(page, 3)
    page.get_by_test_id("tool-later-500").click()
    expect(page.get_by_test_id("cue-times").nth(3)).to_contain_text(
        f"{(was + 500) // 60000}:{((was + 500) // 1000) % 60:02d}.{(was + 500) % 1000:03d} ")
    page.get_by_test_id("tool-earlier-500").click()
    for _ in range(100):
        if start_ms(page, 3) == was:
            break
        page.wait_for_timeout(50)
    assert start_ms(page, 3) == was


def test_a_split_at_the_caret_is_at_the_caret_past_astral_characters(page, server):
    # S-5: selectionStart counts UTF-16 units, the server's at_char code points
    rows = open_demo(page, server)
    pick(rows, 2)
    page.keyboard.press("Enter")
    draft = "🙂𠮷野家🙂に行く今日は牛丼を食べる"
    caret = len(draft[:draft.index("今")].encode("utf-16-le")) // 2
    box = page.get_by_test_id("cue-editor")
    box.fill(draft)
    box.evaluate(f"e => e.setSelectionRange({caret}, {caret})")
    page.keyboard.press("ControlOrMeta+Shift+S")
    expect(rows).to_have_count(5)
    assert texts(page)[2:4] == ["🙂𠮷野家🙂に行く", "今日は牛丼を食べる"]


def test_enter_in_the_find_box_changes_nothing(page, server):
    # S-6: Replace all is a button, not the form's submit
    open_demo(page, server)
    before = texts(page)
    page.get_by_test_id("tool-find").click()
    page.get_by_test_id("find").fill("delighted")
    page.get_by_test_id("replace").fill("")
    page.get_by_test_id("find").press("Enter")
    page.get_by_test_id("replace").press("Enter")
    page.wait_for_timeout(300)
    assert texts(page) == before
    expect(page.get_by_test_id("match-count")).to_have_text("2 matches")
    expect(page.get_by_test_id("tool-undo")).to_be_disabled()


def test_a_second_translation_cue_in_a_row_can_be_chosen_and_edited(page, server):
    # S-8: jfk.ja.srt edited outside, two lines inside the first cue's time
    copy = next(server.tmp.glob("vid2sub-demo-*/demo"))
    (copy / "jfk.ja.srt").write_text(
        "1\n00:00:00,000 --> 00:00:01,500\n一行目\n\n2\n00:00:02,000 --> 00:00:03,500\n二行目\n\n"
        "3\n00:00:04,940 --> 00:00:09,276\n三行目\n\n", encoding="utf-8")
    page.get_by_test_id("open-path").fill(str(copy / "jfk.mp4"))
    page.get_by_test_id("open-button").click()
    rows = page.get_by_test_id("cue-row")
    expect(rows).to_have_count(4)
    lines = rows.first.get_by_test_id("cue-translation-line")
    expect(lines).to_have_count(2)
    lines.nth(1).click()
    expect(lines.nth(1)).to_have_attribute("data-selected", "true")
    page.get_by_test_id("cue-list").focus()
    page.keyboard.press("Enter")
    box = page.get_by_test_id("cue-editor")
    expect(box).to_have_value("二行目")
    box.fill("二行目です")
    page.keyboard.press("ControlOrMeta+Enter")
    expect(lines.nth(1)).to_have_text("二行目です")
    expect(lines.first).to_have_text("一行目")
    # by keyboard: ← on the translation cell moves to the line before, → to the next one
    page.keyboard.press("ArrowLeft")
    expect(lines.first).to_have_attribute("data-selected", "true")
    page.keyboard.press("ArrowRight")
    expect(lines.nth(1)).to_have_attribute("data-selected", "true")
    page.keyboard.press("ArrowLeft")
    page.keyboard.press("ArrowLeft")  # and from the first line, to the source cell
    expect(rows.first.get_by_test_id("cue-text").locator("..")).to_have_attribute(
        "data-selected", "true")


def test_a_changed_draft_and_a_split_sent_in_one_keypress_both_land_and_undo_in_two_steps(
        page, server):
    # S-9: the pacer's reason to be; a commit and a split set in one task
    rows = open_demo(page, server)
    pick(rows, 1)
    page.keyboard.press("Enter")
    box = page.get_by_test_id("cue-editor")
    box.fill("occasion and more")
    box.evaluate("e => e.setSelectionRange(8, 8)")
    page.keyboard.press("ControlOrMeta+Shift+S")
    expect(rows).to_have_count(5)
    assert texts(page)[1:3] == ["occasion", "and more"]
    page.get_by_test_id("tool-undo").click()
    expect(rows).to_have_count(4)
    expect(rows.nth(1).get_by_test_id("cue-text")).to_have_text("occasion and more")
    page.get_by_test_id("tool-undo").click()
    expect(rows.nth(1).get_by_test_id("cue-text")).to_have_text("occasion.")
    expect(page.get_by_test_id("tool-undo")).to_be_disabled()


def test_several_requests_made_in_one_task_all_reach_the_server_in_order(page, server):
    # S-9: three nudges and an undo in one task move the cue 200 ms (the undo comes last, and
    # is not lost); three more nudges, 300 ms more
    rows = open_demo(page, server)
    pick(rows, 3)
    was = start_ms(page, 3)
    keys = """([n, undo]) => {
        const list = document.querySelector('[data-testid=cue-list]');
        for (let i = 0; i < n; i++) list.dispatchEvent(new KeyboardEvent('keydown',
            { key: 'ArrowRight', altKey: true, bubbles: true }));
        if (undo) list.dispatchEvent(new KeyboardEvent('keydown',
            { key: 'z', ctrlKey: true, bubbles: true }));
    }"""
    for args, moved in (([3, True], 200), ([3, False], 500)):
        page.evaluate(keys, args)
        for _ in range(100):
            if start_ms(page, 3) == was + moved:
                break
            page.wait_for_timeout(50)
        page.wait_for_timeout(300)  # and nothing more arrives
        assert start_ms(page, 3) == was + moved


def test_an_edit_made_while_the_playback_audio_is_made_says_so(page, server):
    # S-7: the queue holds the edit until the sound is ready; the page says so meanwhile
    copy = next(server.tmp.glob("vid2sub-demo-*/demo"))
    video = make_episode(Path(copy) / "ac3", audio_codec="ac3")
    page.evaluate("""() => {
        window.__noteSeen = false;
        new MutationObserver(() => {
            if (document.querySelector('[data-testid=busy-note]')) window.__noteSeen = true;
        }).observe(document.body, { childList: true, subtree: true });
    }""")
    page.get_by_test_id("open-path").fill(str(video))
    page.get_by_test_id("open-button").click()
    expect(page.get_by_test_id("cue-row").first).to_be_visible()
    page.wait_for_function("() => document.querySelector('[data-testid=busy-note]') === null")
    assert page.evaluate("() => window.__noteSeen")


def test_typing_in_the_box_reaches_only_the_box(page, server):
    # S-10: every key typed here is also a navigate command; none may act as one
    rows = open_demo(page, server)
    pick(rows, 1)
    page.keyboard.press("Enter")
    box = page.get_by_test_id("cue-editor")
    box.fill("")
    page.keyboard.type("j k l [ ]")
    page.keyboard.press("Enter")
    page.keyboard.press("ArrowUp")
    expect(box).to_have_value("j k l [ ]\n")
    expect(box).to_be_focused()
    expect(rows.nth(1)).to_have_attribute("aria-selected", "true")
    assert page.get_by_test_id("media").evaluate("m => m.paused")
    expect(page.get_by_test_id("tool-undo")).to_be_disabled()


def test_a_bare_keycode_229_in_navigate_mode_is_no_action(page, server):
    # S-10: Safari's shape, 229 with isComposing false, after compositionend
    rows = open_demo(page, server)
    pick(rows, 1)
    page.get_by_test_id("cue-list").focus()
    cdp = page.context.new_cdp_session(page)
    for key, code in (("Enter", "Enter"), (" ", "Space")):
        cdp.send("Input.dispatchKeyEvent", {"type": "rawKeyDown", "key": key, "code": code,
                                            "windowsVirtualKeyCode": 229,
                                            "nativeVirtualKeyCode": 229})
    page.wait_for_timeout(300)
    expect(page.get_by_test_id("cue-editor")).to_have_count(0)
    assert page.get_by_test_id("media").evaluate("m => m.paused")
    cdp.send("Input.dispatchKeyEvent", {"type": "rawKeyDown", "key": "Enter", "code": "Enter",
                                        "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13})
    expect(page.get_by_test_id("cue-editor")).to_have_count(1)  # and a real Enter does edit


def test_find_and_replace_works_across_the_source_and_a_translation_track(page, server):
    # S-11: "delighted" is only in the source; "光栄" only in the Japanese
    rows = open_demo(page, server)
    page.get_by_test_id("tool-find").click()
    page.get_by_test_id("find").fill("光栄")
    expect(page.get_by_test_id("match-count")).to_have_text("1 match")
    page.get_by_test_id("replace").fill("名誉")
    page.get_by_test_id("replace-all").click()
    expect(page.get_by_test_id("match-count")).to_have_text("0 matches")
    expect(rows.first.get_by_test_id("cue-translation")).to_have_text("ここに来られて名誉です。")
    expect(rows.first.locator("[data-flag=edited]")).to_have_count(1)
    assert texts(page)[0] == f"{LINE_1}\n{LINE_2}"  # the source is untouched


def test_merging_two_rows_with_their_own_translations_joins_them_and_flags_the_join(page, server):
    # S-12: the merge sends an id for each translation track's joined cue
    rows = open_demo(page, server)
    pick(rows, 2)
    page.get_by_test_id("tool-merge").click()
    expect(rows).to_have_count(3)
    merged = rows.nth(2)
    assert texts(page)[2].count("\n") >= 1
    translation = merged.get_by_test_id("cue-translation")
    assert translation.inner_text().strip() not in ("", "—")
    assert merged.locator("[data-flag]").count() >= 1
