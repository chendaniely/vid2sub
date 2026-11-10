"""Saving in Chromium, against `vid2sub serve --demo` (spec §14.4, §14.5, §15.3; S29, S31, S32,
S34; Review Focus 4): Save appends a version and rewrites only vid2sub's own files, leaving
someone else's alone and saying which command replaces it (Decision 32); an SRT edited elsewhere
comes back as an outside version and the editor says so; two tabs saving one episode end in a
conflict the second sees, picked in the native <dialog>; a crashed tab's draft is offered back,
and closing with unsaved edits warns first; a restored draft brings back edits to the cues a
split, a merge or an insert made, each tab keeps its own draft, and a draft is cleared only when
every step of it was done again (Decision 31). Run with `make e2e`."""

import re
from pathlib import Path

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e

EN = "jfk.en.srt"
LINE_1 = "I am delighted to be here, and I am"


def demo_copy(server) -> Path:
    return next(server.tmp.glob("vid2sub-demo-*/demo"))


def open_demo(page, server):
    page.get_by_test_id("open-path").fill(str(demo_copy(server) / "jfk.mp4"))
    page.get_by_test_id("open-button").click()
    rows = page.get_by_test_id("cue-row")
    expect(rows).to_have_count(4)
    return rows


def edit_cue(page, rows, k: int, text: str) -> None:
    rows.nth(k).get_by_test_id("cue-text").click()
    page.keyboard.press("Enter")
    page.get_by_test_id("cue-editor").fill(text)
    page.keyboard.press("ControlOrMeta+Enter")
    expect(rows.nth(k).get_by_test_id("cue-text")).to_have_text(text)


def notices(page) -> list[str]:
    return [t.removesuffix("×").strip() for t in page.get_by_test_id("notice").all_inner_texts()]


def seek(page, seconds: float) -> None:
    page.get_by_test_id("media").evaluate(
        "(m, s) => new Promise((done) => { m.addEventListener('seeked', done, { once: true });"
        " m.currentTime = s; })", seconds)


def texts(page) -> list[str]:
    return page.get_by_test_id("cue-text").all_inner_texts()


def drafts_kept(page) -> dict[str, int]:
    """Each draft in localStorage, by its tab's id, with how many steps it holds."""
    return page.evaluate("""() => Object.fromEntries(Object.keys(localStorage)
        .filter((k) => k.startsWith("vid2sub.draft."))
        .map((k) => [k.split(";")[1], JSON.parse(localStorage.getItem(k)).steps.length]))""")


def tab_of(page) -> str:
    return page.evaluate("() => sessionStorage.getItem('vid2sub.tab')")


def test_save_appends_a_version_and_rewrites_only_vid2subs_own_files(page, server):
    # S29, spec §14.5: an editor rendition, a head and projection records, then the files; a file
    # vid2sub didn't write is left alone and said so, with the command that replaces it (§15.3,
    # §6.6; Decision 32: never replaced from the UI).
    copy = demo_copy(server)
    sidecar = copy / "jfk.vid2sub.jsonl"
    before = len(sidecar.read_text(encoding="utf-8").splitlines())
    ja = (copy / "jfk.ja.srt").read_bytes()
    (copy / "jfk.en.ass").write_text("someone else's file\n", encoding="utf-8")
    rows = open_demo(page, server)
    expect(page.get_by_test_id("save-state")).to_have_text("All changes saved")
    edit_cue(page, rows, 1, "occasion!")
    expect(page.get_by_test_id("save-state")).to_have_text("Unsaved changes")
    page.get_by_test_id("save-ass").check()
    page.get_by_test_id("save").click()
    expect(page.get_by_test_id("save-state")).to_have_text("All changes saved")
    expect(page.get_by_test_id("notice").first).to_be_visible()
    # ASS is asked for, so the Japanese ASS is written too; the English one is someone else's.
    assert notices(page) == ["Saved: wrote jfk.en.srt, jfk.ja.ass",
                             ("Left jfk.en.ass alone: vid2sub didn't write it, or it was changed "
                              "outside vid2sub since. To replace a file vid2sub didn't write, run "
                              "vid2sub write <video> --overwrite-foreign in the video's folder "
                              "(the video: jfk.mp4)")]
    assert "occasion!" in (copy / EN).read_text(encoding="utf-8")
    assert (copy / "jfk.ja.srt").read_bytes() == ja  # no Japanese edit: no new version or SRT
    assert (copy / "jfk.en.ass").read_text(encoding="utf-8") == "someone else's file\n"
    records = sidecar.read_text(encoding="utf-8").splitlines()[before:]
    kinds = [re.search(r'"type":"(\w+)"', r).group(1) for r in records]
    assert kinds[:2] == ["rendition", "head"] and "projection" in kinds
    expect(page.get_by_test_id("tool-undo")).to_be_disabled()  # a Save starts the history again


def test_an_srt_edited_elsewhere_comes_back_as_an_outside_version_and_the_editor_says_so(
        page, server):
    # S31: reopened after an outside edit, the change is the head and the editor says so.
    copy = demo_copy(server)
    srt = copy / EN
    srt.write_text(srt.read_text(encoding="utf-8").replace("occasion.", "occasion, truly."),
                   encoding="utf-8")
    rows = open_demo(page, server)
    expect(page.get_by_test_id("episode-notes")).to_contain_text("kept your outside edit to en")
    expect(rows.nth(1).get_by_test_id("cue-text")).to_have_text("occasion, truly.")
    # S32's other half: edited outside again while the editor has unsaved edits, then Save keeps
    # both, as two versions to pick from, and writes neither over the other.
    edit_cue(page, rows, 2, "We meet at a college.")
    srt.write_text(srt.read_text(encoding="utf-8").replace("occasion, truly.", "occasion, again."),
                   encoding="utf-8")
    page.get_by_test_id("save").click()
    expect(page.get_by_test_id("conflict-picker")).to_be_visible()
    assert notices(page) == ["Kept your outside edit to en",
                             "English has two versions: pick the one to keep"]
    assert "occasion, again." in srt.read_text(encoding="utf-8")  # left as the outside edit made it


def test_two_tabs_saving_one_episode_end_in_a_conflict_the_second_sees_and_picks_from(
        open_page, server):
    # Review Focus 4, S32: each Save is compare-and-swap on the version it was opened at.
    first, second = open_page(server), open_page(server)
    a, b = first.page, second.page
    rows_a, rows_b = open_demo(a, server), open_demo(b, server)
    edit_cue(a, rows_a, 1, "occasion!")
    a.get_by_test_id("save").click()
    expect(a.get_by_test_id("save-state")).to_have_text("All changes saved")
    edit_cue(b, rows_b, 1, "occasion?")
    opener = b.get_by_test_id("save")
    opener.click()
    dialog = b.locator("dialog[open]")
    expect(dialog).to_be_visible()
    expect(rows_b).to_have_count(0)  # the source is in conflict, so it isn't loaded (§14.4)
    assert any(n.startswith("English has two versions") for n in notices(b))
    # Decision 13: the native <dialog>, modal, focus inside, Tab kept inside, the page behind
    # inert, Esc closes it and focus goes back to the opener.
    assert dialog.evaluate("d => d.matches(':modal')")
    assert dialog.evaluate("d => d.contains(document.activeElement)")
    landed = set()
    for _ in range(6):  # never on the page behind: inside, or out to the browser's own UI (body)
        b.keyboard.press("Tab")
        where = dialog.evaluate("""d => d.contains(document.activeElement)
            ? document.activeElement.dataset.testid || document.activeElement.tagName
            : document.activeElement === document.body ? "body" : "outside" """)
        assert where != "outside"
        landed.add(where)
    assert "picker-close" in landed
    theme = b.get_by_test_id("theme-dark").bounding_box()
    x, y = theme["x"] + theme["width"] / 2, theme["y"] + theme["height"] / 2
    assert b.evaluate("([x, y]) => document.elementFromPoint(x, y)?.dataset.testid ?? null",
                      [x, y]) != "theme-dark"
    b.keyboard.press("Escape")
    expect(dialog).to_have_count(0)
    expect(opener).to_be_focused()
    expect(b.locator("html")).not_to_have_class(re.compile(r"\bdialog-open\b"))
    # The note's button opens it again; keep the first tab's version.
    b.get_by_test_id("pick-version").click()
    versions = b.get_by_test_id("version")
    expect(versions).to_have_count(2)
    assert [re.sub(r", .+:", ":", v) for v in versions.all_inner_texts()] == [
        "Version 1: Saved in the editor: 4 cues", "Version 2: Saved in the editor: 4 cues"]
    # §14.4, S32: the editor shows both: the cue they differ in, each version's text beside it.
    difference = b.get_by_test_id("difference")
    expect(difference).to_have_count(1)
    expect(difference.locator("td")).to_have_text(["0:03.820", "occasion!", "occasion?"])
    versions.first.check()
    b.get_by_test_id("keep-en").click()
    expect(dialog).to_have_count(0)
    expect(b.get_by_test_id("pick-version")).to_have_count(0)  # no track in conflict now
    expect(rows_b).to_have_count(4)  # the source is loaded again
    picked = rows_b.nth(1).get_by_test_id("cue-text").inner_text()
    assert picked in ("occasion!", "occasion?")
    assert picked in (demo_copy(server) / EN).read_text(encoding="utf-8")
    for watched in (first, second):
        assert watched.errors == [] and watched.violations() == []


def test_a_crashed_tab_offers_its_draft_back_and_closing_with_unsaved_edits_warns_first(
        open_page, server):
    # S34, spec §14.5: the draft is in localStorage; the warning is beforeunload's.
    first = open_page(server)
    a = first.page
    rows = open_demo(a, server)
    edit_cue(a, rows, 1, "occasion!")
    edit_cue(a, rows, 2, "We meet.")
    a.get_by_test_id("tool-undo").click()
    expect(rows.nth(2).get_by_test_id("cue-text")).to_have_text(
        "We meet at a college noted for knowledge,")
    warned = []
    a.on("dialog", lambda d: (warned.append(d.type), d.dismiss()))
    a.close(run_before_unload=True)
    a.wait_for_timeout(500)
    assert warned == ["beforeunload"] and not a.is_closed()  # dismissing it kept the tab
    a.close()  # a crash: no warning, no Save
    second = open_page(server)
    b = second.page
    rows = open_demo(b, server)
    draft = b.get_by_test_id("draft")
    expect(draft).to_contain_text("3 unsaved edits from")
    b.get_by_test_id("draft-restore").click()
    expect(rows.nth(1).get_by_test_id("cue-text")).to_have_text("occasion!")
    expect(rows.nth(2).get_by_test_id("cue-text")).to_have_text(
        "We meet at a college noted for knowledge,")
    expect(b.get_by_test_id("save-state")).to_have_text("Unsaved changes")
    expect(draft).to_have_count(0)
    b.get_by_test_id("save").click()
    expect(b.get_by_test_id("save-state")).to_have_text("All changes saved")
    b.reload()  # saved: nothing is offered any more
    rows = open_demo(b, server)
    expect(rows.nth(1).get_by_test_id("cue-text")).to_have_text("occasion!")
    expect(b.get_by_test_id("draft")).to_have_count(0)
    assert second.errors == [] and second.violations() == []


def test_a_restored_draft_brings_back_the_edits_made_to_new_cues(open_page, server):
    # Decision 31 (the kickoff council's reliability finding 2): the page draws each new cue's id
    # and the draft keeps the ops as sent, so the replay makes the same cues and every edit to
    # them lands.
    first = open_page(server)
    a = first.page
    rows = open_demo(a, server)
    seek(a, 4.8)  # in the gap after "occasion." (ends 4.653): insert a cue there and type its line
    a.get_by_test_id("tool-insert").click()
    expect(rows).to_have_count(5)
    a.get_by_test_id("cue-editor").fill("Hm.")
    a.keyboard.press("ControlOrMeta+Enter")
    expect(rows.nth(2).get_by_test_id("cue-text")).to_have_text("Hm.")
    # split the first cue at the end of its first line, then fix the second half
    rows.nth(0).get_by_test_id("cue-text").click()
    a.keyboard.press("Enter")
    a.get_by_test_id("cue-editor").evaluate(f"e => e.setSelectionRange({len(LINE_1)}, "
                                            f"{len(LINE_1)})")
    a.keyboard.press("ControlOrMeta+Shift+S")
    expect(rows).to_have_count(6)
    edit_cue(a, rows, 1, "particularly delighted to be here today")
    # merge the last two cues, each with its own Japanese cue, then fix what they made
    rows.nth(4).get_by_test_id("cue-text").click()
    a.get_by_test_id("tool-merge").click()
    expect(rows).to_have_count(5)
    edit_cue(a, rows, 4, "We meet at a college, in a city noted for progress.")
    done = texts(a)
    assert done == [LINE_1, "particularly delighted to be here today", "occasion.", "Hm.",
                    "We meet at a college, in a city noted for progress."]
    a.close()  # a crash: no unload handlers, no Save
    second = open_page(server)
    b = second.page
    rows = open_demo(b, server)
    expect(b.get_by_test_id("draft")).to_contain_text("6 unsaved edits from")
    b.get_by_test_id("draft-restore").click()
    expect(rows).to_have_count(5)
    expect(rows.nth(4).get_by_test_id("cue-text")).to_have_text(done[4])
    assert texts(b) == done
    expect(b.get_by_test_id("draft")).to_have_count(0)
    # every step was done again, so the crashed tab's draft is gone; this tab keeps its own
    expect(b.get_by_test_id("save-state")).to_have_text("Unsaved changes")
    assert drafts_kept(b) == {tab_of(b): 6}
    assert second.errors == [] and second.violations() == []


def test_two_tabs_on_one_episode_keep_separate_drafts(open_page, server):
    # Decision 31 (reliability finding 3): each tab's draft is its own; reopening offers each,
    # with its time, and a Save clears only the saving tab's.
    first, second = open_page(server), open_page(server)
    a, b = first.page, second.page
    rows_a, rows_b = open_demo(a, server), open_demo(b, server)
    edit_cue(a, rows_a, 1, "occasion!")
    edit_cue(b, rows_b, 2, "We meet.")
    edit_cue(b, rows_b, 3, "in a city.")
    assert drafts_kept(a) == {tab_of(a): 1, tab_of(b): 2}
    b.close()  # the second tab crashes
    third = open_page(server)
    c = third.page
    rows_c = open_demo(c, server)
    offered = c.get_by_test_id("draft")
    expect(offered).to_have_count(2)
    kept = [re.sub(r" from .*", "", t, flags=re.DOTALL) for t in offered.all_inner_texts()]
    assert kept == ["1 unsaved edit", "2 unsaved edits"]
    offered.nth(1).get_by_test_id("draft-restore").click()
    expect(rows_c.nth(3).get_by_test_id("cue-text")).to_have_text("in a city.")
    expect(rows_c.nth(2).get_by_test_id("cue-text")).to_have_text("We meet.")
    expect(rows_c.nth(1).get_by_test_id("cue-text")).to_have_text("occasion.")
    expect(offered).to_have_count(0)
    assert drafts_kept(c) == {tab_of(a): 1, tab_of(c): 2}
    a.get_by_test_id("save").click()
    expect(a.get_by_test_id("save-state")).to_have_text("All changes saved")
    assert drafts_kept(c) == {tab_of(c): 2}  # the first tab's Save cleared only its own
    for watched in (first, third):
        assert watched.errors == [] and watched.violations() == []


def test_a_restore_the_server_refuses_a_step_of_keeps_the_draft_and_says_how_many(
        open_page, server):
    # A draft is cleared only after a replay with no refused step (Decision 31).
    first = open_page(server)
    a = first.page
    rows = open_demo(a, server)
    edit_cue(a, rows, 1, "occasion!")
    a.evaluate("""() => {  // a step this episode can't take: a cue it never had
        const key = Object.keys(localStorage).find((k) => k.startsWith("vid2sub.draft."));
        const draft = JSON.parse(localStorage.getItem(key));
        draft.steps.push({ edit: { op: "set_text", cue: "c00000000", text: "lost" }, n: 999 });
        localStorage.setItem(key, JSON.stringify(draft));
    }""")
    a.close()
    second = open_page(server)
    b = second.page
    rows = open_demo(b, server)
    b.get_by_test_id("draft-restore").click()
    expect(b.get_by_test_id("notice").filter(has_text="couldn't be replayed")).to_have_text(
        re.compile(r"^1 restored step of 2 couldn.t be replayed: the draft is kept"))
    expect(rows.nth(1).get_by_test_id("cue-text")).to_have_text("occasion!")
    assert sorted(drafts_kept(b).values()) == [1, 2]  # this tab's one step, and the draft kept
    b.reload()
    open_demo(b, server)
    expect(b.get_by_test_id("draft")).to_have_count(2)


def type_box(page, rows, k: int, text: str) -> None:
    """Opens cue k's box and types its line, without committing it."""
    rows.nth(k).get_by_test_id("cue-text").click()
    page.keyboard.press("Enter")
    page.get_by_test_id("cue-editor").fill(text)


def test_save_includes_the_line_being_typed_and_closing_warns_of_it(open_page, server):
    # Task 16's Spec review, C-1: pressing Save with a box open commits it first (round 15d: only
    # Esc discards), the status counts the box, and closing warns while its text differs.
    first = open_page(server)
    a = first.page
    rows = open_demo(a, server)
    type_box(a, rows, 1, "typed, never committed")
    expect(a.get_by_test_id("save-state")).to_have_text("Unsaved changes")
    # (the listener is added by an effect two renders later: let them paint)
    a.evaluate("() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))")
    warned = []
    a.on("dialog", lambda d: (warned.append(d.type), d.dismiss()))
    a.close(run_before_unload=True)
    a.wait_for_timeout(500)
    assert warned == ["beforeunload"] and not a.is_closed()
    a.get_by_test_id("save").click()
    expect(a.get_by_test_id("notice").first).to_contain_text("wrote jfk.en.srt")
    expect(a.get_by_test_id("save-state")).to_have_text("All changes saved")
    assert "typed, never committed" in (demo_copy(server) / EN).read_text(encoding="utf-8")
    expect(rows.nth(1).get_by_test_id("cue-text")).to_have_text("typed, never committed")
    assert first.errors == [] and first.violations() == []


def test_a_save_that_ends_in_a_conflict_keeps_the_line_being_typed(open_page, server):
    # C-1 (the reviewer's P2c): the conflict empties the rows and closes the box, so the text has
    # to be in the version Save wrote.
    first, second = open_page(server), open_page(server)
    a, b = first.page, second.page
    rows_a, rows_b = open_demo(a, server), open_demo(b, server)
    edit_cue(a, rows_a, 1, "occasion!")
    a.get_by_test_id("save").click()
    expect(a.get_by_test_id("save-state")).to_have_text("All changes saved")
    edit_cue(b, rows_b, 2, "b's own edit")
    type_box(b, rows_b, 3, "typed in b, box open")
    b.get_by_test_id("save").click()
    expect(b.locator("dialog[open]")).to_be_visible()
    sidecar = demo_copy(server) / "jfk.vid2sub.jsonl"
    assert "typed in b, box open" in sidecar.read_text(encoding="utf-8")
    for watched in (first, second):
        assert watched.errors == [] and watched.violations() == []


def edit_translation(page, rows, text: str) -> None:
    rows.nth(0).get_by_test_id("cue-translation-line").first.click()
    page.keyboard.press("Enter")
    page.get_by_test_id("cue-editor").fill(text)
    page.keyboard.press("ControlOrMeta+Enter")
    expect(rows.nth(0).get_by_test_id("cue-translation-line").first).to_have_text(text)


def tear_the_japanese_track(open_page, server):
    """Two tabs save a Japanese edit from one version: the second sees the track in conflict. The
    second tab comes back with its picker closed (Esc)."""
    first, second = open_page(server), open_page(server)
    a, b = first.page, second.page
    rows_a, rows_b = open_demo(a, server), open_demo(b, server)
    edit_translation(a, rows_a, "訳A")
    a.get_by_test_id("save").click()
    expect(a.get_by_test_id("save-state")).to_have_text("All changes saved")
    edit_translation(b, rows_b, "訳B")
    b.get_by_test_id("save").click()
    expect(b.locator("dialog[open]")).to_be_visible()
    b.keyboard.press("Escape")
    return first, second, a, b, rows_a, rows_b


def test_an_edit_sent_while_a_save_runs_stays_in_the_draft(open_page, server):
    # Task 16's Spec review, C-3: the Save moves the heads, and the edit sent behind it (the page
    # has not heard back yet) was cleared with the old key's draft.
    a = open_page(server).page
    rows = open_demo(a, server)
    edit_cue(a, rows, 1, "occasion!")
    a.evaluate("""() => {  // one task: the page hears nothing between the two requests
        document.querySelector('[data-testid="save"]').click();
        document.querySelector('[data-testid="tool-later"]').click();
    }""")
    expect(a.get_by_test_id("notice").first).to_contain_text("Saved: wrote jfk.en.srt")
    expect(a.get_by_test_id("save-state")).to_have_text("Unsaved changes")  # the nudge landed
    assert drafts_kept(a) == {tab_of(a): 1}  # the nudge, not the edit the Save wrote
    a.close()  # a crash
    second = open_page(server)
    b = second.page
    open_demo(b, server)
    expect(b.get_by_test_id("draft")).to_have_count(1)
    expect(b.get_by_test_id("draft")).to_contain_text("1 unsaved edit from")
    assert second.errors == [] and second.violations() == []


def test_a_glossary_term_that_was_saved_leaves_no_draft(open_page, server):
    # Task 16's Spec review, I-1 (P5): a Save moves no head for a glossary term, and the draft
    # stayed, offering a term that was already written.
    first = open_page(server)
    a = first.page
    open_demo(a, server)
    a.get_by_test_id("tool-find").click()
    a.get_by_test_id("glossary-term").fill("Kennedy")
    a.get_by_test_id("glossary-translation").fill("ケネディ")
    a.get_by_test_id("glossary-add").click()
    expect(a.get_by_test_id("save-state")).to_have_text("Unsaved changes")
    assert drafts_kept(a) == {tab_of(a): 1}
    a.get_by_test_id("save").click()
    expect(a.get_by_test_id("save-state")).to_have_text("All changes saved")
    expect(a.get_by_test_id("notice").first).to_be_visible()
    assert drafts_kept(a) == {}
    a.on("dialog", lambda d: d.accept())
    a.reload()
    open_demo(a, server)
    a.wait_for_timeout(300)
    expect(a.get_by_test_id("draft")).to_have_count(0)


def test_an_edit_that_was_undone_leaves_no_draft_once_saved(open_page, server):
    # I-1 (P6): edit, undo, Save: the changes net to nothing, and no later open offers them.
    first = open_page(server)
    a = first.page
    rows = open_demo(a, server)
    edit_cue(a, rows, 1, "occasion!")
    a.get_by_test_id("tool-undo").click()
    expect(a.get_by_test_id("save-state")).to_have_text("All changes saved")
    assert drafts_kept(a) == {tab_of(a): 2}
    a.get_by_test_id("save").click()
    expect(a.get_by_test_id("notice").first).to_be_visible()
    assert drafts_kept(a) == {}


def test_an_offer_for_old_versions_goes_when_a_save_moves_the_heads(open_page, server):
    # Task 16's Spec review, C-2 (P7): a crashed tab's draft is on offer; the SRT is edited
    # outside and Save records that, so the heads move. The draft was made on the old versions.
    first = open_page(server)
    a = first.page
    rows = open_demo(a, server)
    edit_cue(a, rows, 1, "crashed edit")
    a.close()
    second = open_page(server)
    b = second.page
    rows = open_demo(b, server)
    expect(b.get_by_test_id("draft")).to_have_count(1)
    srt = demo_copy(server) / EN
    srt.write_text(srt.read_text(encoding="utf-8").replace("occasion.", "occasion, outside."),
                   encoding="utf-8")
    b.get_by_test_id("save").click()
    expect(rows.nth(1).get_by_test_id("cue-text")).to_have_text("occasion, outside.")
    expect(b.get_by_test_id("draft")).to_have_count(0)
    assert second.errors == [] and second.violations() == []


def test_this_tabs_offered_draft_comes_across_a_pick_and_can_still_be_restored(open_page, server):
    # C-2 (P8b): reloaded onto a torn episode, the picker covers the offer; the pick moves the
    # heads, and the draft goes with them instead of being deleted under its Restore button.
    first, second, a, b, rows_a, rows_b = tear_the_japanese_track(open_page, server)
    edit_cue(b, rows_b, 1, "source edit, then reload")
    b.on("dialog", lambda d: d.accept())
    b.reload()
    rows_b = open_demo(b, server)
    expect(b.locator("dialog[open]")).to_be_visible()  # a torn episode opens the picker at once
    expect(b.get_by_test_id("draft")).to_have_count(1)
    b.get_by_test_id("version").first.check()
    b.get_by_test_id("keep-ja").click()
    expect(b.get_by_test_id("pick-version")).to_have_count(0)
    expect(b.get_by_test_id("draft")).to_have_count(1)
    assert list(drafts_kept(b).values()) == [1]
    b.get_by_test_id("draft-restore").click()
    expect(rows_b.nth(1).get_by_test_id("cue-text")).to_have_text("source edit, then reload")
    expect(b.get_by_test_id("draft")).to_have_count(0)
    expect(b.get_by_test_id("save-state")).to_have_text("Unsaved changes")
    for watched in (first, second):
        assert watched.errors == [] and watched.violations() == []
