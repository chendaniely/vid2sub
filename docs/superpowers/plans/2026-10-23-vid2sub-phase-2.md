# vid2sub Phase 2 (M2): the editor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking. Every rule for running a task (the loop, the reviews,
> the stops, the commit formats) is in `AGENTS.md`; this plan never restates them.

**Goal:** `vid2sub serve`, a local web app on `127.0.0.1` behind a launch token, whose editor
opens an episode M1 made, plays it (through the playback audio when the browser can't play its
audio), and lets Dan fix, retranslate and save its subtitles; an SRT edited elsewhere comes back
as an external version.

**Architecture:** the editor's behaviour lives in the core and the backend (`vid2sub.subs.edit`
for edit rules, `vid2sub.web.backend` for opening, saving and retranslating through `vid2sub.store`
and `vid2sub.translate`), so the CLI and the web app share it (spec §18.3). A FastAPI shell
(`vid2sub.web.app`) serves `/auth`, `/healthz` and `/media/{token}` and mounts a shinyreact app
(`vid2sub.web.server`) at `/`, wrapped as `HostGuard(WriteGuard(TokenGuard(api)))`. The React
frontend (`frontend/`, built into `src/vid2sub/web/www/`) renders JSON outputs from pure view
functions (`vid2sub.web.views`) and sends edits as typed inputs.

**Tech Stack:** Python ≥3.12, uv, FastAPI 0.142.3 and uvicorn 0.54.0, shiny 1.8.0 and shinyreact
0.1.0 (pinned exactly, as `recordings` does), pydantic 2; React 19.2.8 kept external as
`window.shinyreact.React`, Vite 5.4.21 library build, TypeScript 5.9.3, Tailwind 4.3.3, shadcn
`radix-nova`, Vitest 3.2.7; Node 22; pytest, hypothesis, pytest-playwright 0.10.0 (Chromium);
ffmpeg ≥6 for the playback audio.

**Spec:** `docs/superpowers/specs/2026-10-14-vid2sub-design.md`

**Now:** Task 1: The M1 exit test (with Dan), open.

## Decisions made while planning (review these)

1. **Media tokens are bound to the launch,** not to a Shiny session: a `/media/` request carries
   only the launch cookie, so "bound to the session" (spec §6.5) means the engine's launch. Tokens
   are unguessable, die when the engine exits, and are revoked when their episode is closed.
2. **An audio track the browser can't play makes the video unplayable** (spec §8.2), so Phase 2's
   editor then plays the playback audio with no picture; the preview copy (picture) is Phase 3.
3. **Edits keep `w` (the word range) only where the words are unchanged:** text and time edits keep
   it; split and insert drop it; merge joins two ranges. A text edit drops the `halluc` flag and a
   time edit drops `est`, since a person has now checked them.
4. **The editor marks a translation cue it changes `edited`,** as `store.align_ids` does for
   outside edits, so M1's pipeline keeps it (spec §13.4). A Save's head is `by: "editor"`, which
   keeps the whole track from automatic replacement.
5. **The glossary is written at Save,** never on each keystroke (spec §16).
6. **The demo folder holds no video:** `vid2sub serve --demo` muxes the public-domain
   `tests/fixtures/speech/jfk-14s.wav` into a short MP4 in its temporary copy at start-up, beside
   a committed canned sidecar. Phase 4 replaces it with the non-English clip spec §21 asks for.
7. **Cancel stops between chunks and between translation batches;** a running ffmpeg finishes its
   (short) step first. M1's pipeline has no cancellation, so Task 4 adds a check to `RunContext`.

## Global Constraints

- Python `>=3.12`; CI runs 3.12 and 3.14. Everything runs through `uv`; never `pip install`.
- Pure packages (`vid2sub.subs`, `vid2sub.parse`, `vid2sub.catalog`) import only the standard
  library (no subprocess, socket, http, urllib, asyncio, threading, multiprocessing, ssl),
  pydantic, pysubs2, opencc_purepy, charset_normalizer and each other (`tests/test_purity.py`).
- Only `src/vid2sub/engines/clients.py` imports `openai`, `httpx` or `chatlas`.
- Times are integer milliseconds; cues sorted, `0 ≤ start < end`, no overlaps, `\n` line breaks,
  never a blank line (spec §12.1).
- Never overwrite an artifact: the sidecar is append-only; a subtitle file is rewritten only when
  the sidecar has a projection record for it (spec §14, §15.3).
- No titles, paths, tokens or keys in logs or `--json` output (spec §6.8).
- The engine binds `127.0.0.1` only (spec §6.1).
- CSP on every page, verbatim (spec §6.3): `default-src 'self'; script-src 'self'; connect-src
  'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; img-src 'self' data: blob:;
  media-src 'self' blob:`; never `unsafe-eval`. `/media/` responses: `Content-Security-Policy:
  sandbox`, `X-Content-Type-Options: nosniff`, `Cache-Control: no-store`.
- Untrusted text is rendered as plain text; the caption overlay renders `<i>` only, through a
  whitelist; never `dangerouslySetInnerHTML` (spec §6.3).
- Fonts are served locally; the app makes no third-party requests.
- React stays external (`react` → `window.shinyreact.React`, `react-dom/client` →
  `window.shinyreact.ReactDOM`); the `react-dom` index is bundled (shinyreact's global lacks
  `createPortal` and `flushSync`). `src/vid2sub/web/www/ui.js` and `ui.css` are build output.
  `ReactApp(server)` is called in `src/vid2sub/web/server.py`. Every output is subscribed and every
  message handler and input lives in `App` (shinyreact 0.1.0).
- Colours: NYC blue `#236192` (`#6CA6D9` dark) is the working colour; NYC orange `#F26522` marks
  bars and backgrounds, never text. Atkinson Hyperlegible and Atkinson Hyperlegible Mono.
- British spelling; module docstrings give one sentence of purpose, then why, citing spec sections
  and who decided; test names are sentences; guard tests fail without their fix.
- A hook blocks shell commands that name `src/vid2sub/media/`: read and edit files there with the
  file tools; `make test` and `uv run pytest` are unaffected.

## Review Focus

1. **A video whose path has non-ASCII, bidi or emoji characters, or that sits on a network
   share:** it opens, plays through `/media/`, and saves next to itself. (Task 10's and Task 6's
   tests.)
2. **The sidecar changed by a CLI run while the editor has the episode open** (`vid2sub translate`
   runs, then Save): the editor's version and the CLI's both survive; a diverged track shows as a
   conflict. (Task 6's tests.)
3. **A long episode** (two hours, about 2,000 cues): opening it and every edit stay under a
   second, and the cue list renders only what's on screen. (Task 5's and Task 14's tests.)
4. **Two tabs on one launch editing one episode:** each Save is compare-and-swap; the second sees
   the conflict. (Task 6's and Task 16's tests.)
5. **The engine restarted while a tab is open:** the old cookie is refused, and the page says to
   open the new URL instead of retrying forever. (Task 9's and Task 12's tests.)

***

### Task 1: The M1 exit test (with Dan)

**Tier:** 3 · **Scenarios:** S01, S02, S03, S04, S05 · **[Dan]**, on Dan's Mac with the Spark,
Plex and Jellyfin

The M1 plan's Task 36, Steps 2 and 3, moved here (Dan, 2026-10-23, Q&A item 7). The implementer
prepares the list and records the results; Dan runs every step that touches his media, his
servers and his machine. Each [Dan] step is asked one at a time, by *Asking Dan*.

**Files:**
- Modify: `docs/superpowers/specs/2026-10-14-vid2sub-design.md` (§29's M1 results, the Scenarios
  rows S01–S05, Open items)

**Interfaces:** none (no code).

- [ ] **Step 0: Record the base:** `git rev-parse HEAD > .git/TASK_BASE`.
- [ ] **Step 1: List the [Dan] steps** (2 to 8 below) for Dan, one line each, with the count,
  then present Step 2. Set **Now** to `waiting on Dan: Task 1, Step 2` and commit it as a wip
  (`chore(plan): 🤖 wip Task 1: waiting on Dan for the M1 exit test`, its body `Done so far:`
  the list, `Stopped at:` Step 2, `Tests:` not run, no code).
- [ ] **Step 2: [Dan] Install and check,** on the Mac, in this repo's folder:

```bash
brew install deno                       # yt-dlp needs it for YouTube (spec §4.2)
uv tool install --editable '.[mac]'
vid2sub config path                     # where vid2sub reads vid2sub.toml
vid2sub config init                     # a starter: save it at that path, then edit it
vid2sub doctor                          # every line green; keys by presence only
```

  In local-ai's folder, `make tunnel` running. Expected: `doctor` reports ffmpeg, ffprobe and
  deno with versions, the Spark reachable, and `SPARK_API_KEY` present.
- [ ] **Step 3: [Dan] A Cantonese episode (S01):**

```bash
time vid2sub run "<a Cantonese episode>" --from yue --to en
```

  Watch the `.en.srt` in Plex. Check the `.zh-HK.srt` shows as Chinese (Hong Kong) or similar,
  in Traditional characters. Note the run's time (Qwen3-ASR's speed on an idle Mac, §29).
- [ ] **Step 4: [Dan] A Japanese episode (S02),** detection on:

```bash
vid2sub run "<a Japanese episode>" --to en
```

  Watch the `.en.srt` in Plex; note whether Gemma's English reads well at 4 characters per second
  (Open items: Japanese reading speed). Optionally, for the Japanese routing (Open items), copy
  the episode into two empty folders and run each with `--model spark-turbo` and with
  `--model mac-qwen`; note which reads better.
- [ ] **Step 5: [Dan] The naming codes (S05):** next to a test video, copy one `.srt` to
  `<stem>.zh-CN.srt`, `<stem>.zh-TW.srt`, `<stem>.zh-HK.srt` and `<stem>.ja.srt`; note what Plex
  and Jellyfin each display for each.
- [ ] **Step 6: [Dan] YouTube (S03):**

```bash
vid2sub run "<an English YouTube video's link>" --to none
```

  Expected: the download and its `.en.srt` land in the YouTube folder (`defaults.youtube_dir`)
  under a safe name.
- [ ] **Step 7: [Dan] A season (S04):**

```bash
vid2sub run "<a Japanese season folder>" --from ja --to en
vid2sub run "<the same folder>" --from ja --to en --skip-existing; echo "exit $?"
```

  Expected: every episode done unattended; the second command does nothing and prints `exit 0`.
- [ ] **Step 8: [Dan] Hand back the notes** from Steps 2–7: what worked, what didn't, the times,
  and what Plex and Jellyfin showed for each code.
- [ ] **Step 9: Record the results in the spec.** In §29's "M1 results so far", replace each
  *pending* with the result, dated 2026-MM-DD (the day Dan ran it): the Plex and Jellyfin codes,
  Qwen3-ASR's time on an idle Mac, the real YouTube download, the season run. Set S01–S05 to
  `verified` where they passed. In Open items, update the Japanese reading-speed and routing
  lines with Dan's notes. Whisper.cpp's cue timing against a hand-corrected episode stays
  *pending*: it needs an episode corrected in the editor, so it moves to Task 23 (say so in
  §29). If a result contradicts a default (a file code Plex or Jellyfin shows wrongly), changing
  it would change the spec: that is the fifth stop (`AGENTS.md`, *Stops*), asked as a scenario
  before anything else changes. A step that failed for a bug is a new task, proposed to Dan.
- [ ] **Step 10: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
docs(spec): 🤖 M1's exit test results: <what passed, in one line>

<each result in a line: Plex and Jellyfin's codes, Qwen3-ASR's time, YouTube, the season run;
the scenario rows set to verified; what stays pending and why>

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 1
Co-Authored-By: <the model's own line>
```

  `git add docs/superpowers/specs/2026-10-14-vid2sub-design.md`, `git commit -F .git/COMMIT_MSG`,
  then `git log -1 --format='%(trailers)'` shows `Plan:`.
- [ ] **Step 11: Review, look forward, close.** The Tier 3 self-review from
  `$(cat .git/TASK_BASE)` under the two headings (*Standards*, *Spec*), plus `make check`; the
  forward review over Tasks 2–23 (a changed default, such as a file code, rewrites every later
  listing that names it); the docs this task made untrue (the README's naming table, if a code
  changed). Then the close, its own commit, holding this plan with this task's boxes ticked and
  **Now** set to `Task 2: Edit operations, open.`, and the spec's rows S01–S05 as Step 9 left
  them, with the message in `.git/CLOSE_MSG`:

```text
docs(plan): 🤖 close Task 1: The M1 exit test (with Dan)

Drift: none
Rulings: none
Phase-end: none
Forward: none
Tier: 3
Rounds: self-review (Standards, Spec); make check
Findings: none

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 1
Co-Authored-By: <the model's own line>
```

  `git add docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md
  docs/superpowers/specs/2026-10-14-vid2sub-design.md`, `git commit -F .git/CLOSE_MSG`.

***

### Task 2: Edit operations

**Tier:** 2 · **Scenarios:** S28

**Files:**
- Create: `src/vid2sub/subs/edit.py`
- Test: `tests/test_edit.py`

**Interfaces:**
- Consumes: `vid2sub.subs.model.Cue`, `TrackError`, `new_cue_id(taken)`, `check_track(cues)`;
  `vid2sub.subs.text.canonical(text)`.
- Produces (pure; every function returns a new `Tracks` and never mutates its input; the ones
  that make cues add the new ids to `taken`, as `new_cue_id` does):
  - `class EditError(ValueError)` (its message is fit to show)
  - `SOURCE = "source"` (the name `replace_all` gives the source track)
  - `@dataclass(frozen=True) class Tracks: source: tuple[Cue, ...]; translations:
    Mapping[str, tuple[Cue, ...]]` (target track key → cues)
  - `follow(source: Sequence[Cue], translation: Sequence[Cue]) -> tuple[Cue, ...]`: each cue
    that isn't `detached` takes the span of its `src` cues (a cue none of whose `src` is in the
    source keeps its times); the result is sorted by time.
  - `set_text(t, cue_id: str, text: str) -> Tracks` (drops `halluc`, keeps `w`)
  - `set_translation_text(t, track: str, cue_id: str, text: str) -> Tracks` (adds `edited`)
  - `set_times(t, cue_id: str, *, start_ms: int | None = None, end_ms: int | None = None)
    -> Tracks` (clamped to the neighbours; drops `est`, keeps `w`; `EditError` if nothing is
    left)
  - `nudge(t, cue_id: str, delta_ms: int, *, edge: Literal["start", "end", "both"] = "both")
    -> Tracks` (`"both"` moves the cue as a block that stops at its neighbours)
  - `split(t, cue_id: str, *, at_char: int, at_ms: int, taken: set[str])
    -> tuple[Tracks, tuple[str, str]]` (both halves `from` the old id, no `w`)
  - `merge_next(t, cue_id: str, *, taken: set[str]) -> tuple[Tracks, str]` (`w` joined when
    both parts have one; two or more translations covering the parts become one new cue with
    no `src_sha`)
  - `insert(t, *, start_ms: int, end_ms: int, text: str, taken: set[str])
    -> tuple[Tracks, str]` (start must be in a gap; the end is clamped to the next cue)
  - `delete(t, cue_id: str) -> Tracks`
  - `detach(t, track: str, cue_id: str, detached: bool) -> Tracks`
  - `replace_all(t, find: str, replace: str, *, tracks: Sequence[str]) -> tuple[Tracks, int]`
    (plain, case-sensitive; `"source"` names the source track; returns the count replaced)
  - Every result passes `check_track` for every track; an edit that would break one (a
    translation track overlapping a detached cue, say) raises `EditError` naming the track.

- [ ] **Step 0: Record the base:** `git rev-parse HEAD > .git/TASK_BASE`.
- [ ] **Step 1: Write the failing test,** `tests/test_edit.py`:

```python
import time

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from vid2sub.subs import edit
from vid2sub.subs.edit import EditError, Tracks
from vid2sub.subs.model import Cue, check_track
from vid2sub.subs.translate_shape import src_sha, stale_ids, untranslated


def cue(id, start, end, text, **kw):
    return Cue(id=id, start_ms=start, end_ms=end, text=text, **kw)


def tracks() -> Tracks:
    a = cue("a", 0, 1000, "おはよう", w=(0, 2))
    b = cue("b", 1000, 2000, "元気ですか", w=(2, 5), flags=("halluc",))
    c = cue("c", 3000, 4000, "はい、元気です", w=(5, 9), flags=("est",))
    en = (cue("ta", 0, 1000, "Good morning", src=("a",), src_sha=src_sha([a.text])),
          cue("tb", 1000, 4000, "How are you? Fine.", src=("b", "c"),
              src_sha=src_sha([b.text, c.text])))
    return Tracks((a, b, c), {"en": en})


def by_id(cues):
    return {c.id: c for c in cues}


def stale(t: Tracks, track: str = "en") -> set[str]:
    return stale_ids(t.translations[track], by_id(t.source))


def test_the_example_episode_starts_with_nothing_stale():
    assert stale(tracks()) == set()


def test_editing_a_cue_canonicalises_its_text_keeps_its_words_and_drops_halluc():
    t = tracks()
    out = edit.set_text(t, "b", "  元気  \n\n ですか ")
    b = by_id(out.source)["b"]
    assert b.text == "元気\nですか"
    assert b.w == (2, 5) and "halluc" not in b.flags
    assert t == tracks()


def test_a_cue_cannot_be_edited_down_to_nothing():
    with pytest.raises(EditError, match="delete it instead"):
        edit.set_text(tracks(), "a", " \n ")


def test_editing_a_source_cue_makes_its_translation_stale():
    assert stale(edit.set_text(tracks(), "c", "いいえ")) == {"tb"}


def test_editing_a_translation_marks_it_edited_and_keeps_its_source_hash():
    t = tracks()
    out = edit.set_translation_text(t, "en", "ta", "Morning!")
    ta = by_id(out.translations["en"])["ta"]
    assert ta.text == "Morning!" and "edited" in ta.flags
    assert ta.src_sha == by_id(t.translations["en"])["ta"].src_sha


def test_setting_times_is_clamped_to_the_neighbours_and_drops_est():
    out = edit.set_times(tracks(), "c", start_ms=500)
    c = by_id(out.source)["c"]
    assert (c.start_ms, c.end_ms) == (2000, 4000)
    assert "est" not in c.flags and c.w == (5, 9)


def test_times_that_leave_a_cue_nothing_are_refused():
    with pytest.raises(EditError, match="start before it ends"):
        edit.set_times(tracks(), "b", start_ms=2500)
    with pytest.raises(EditError, match="start before it ends"):
        edit.set_times(tracks(), "a", end_ms=-5)


def test_a_nudge_moves_a_cue_as_a_block_without_entering_its_neighbours():
    t = tracks()
    c = by_id(edit.nudge(t, "c", -1500).source)["c"]
    assert (c.start_ms, c.end_ms) == (2000, 3000)
    c = by_id(edit.nudge(t, "c", 400, edge="end").source)["c"]
    assert (c.start_ms, c.end_ms) == (3000, 4400)
    b = by_id(edit.nudge(t, "b", -300, edge="start").source)["b"]
    assert (b.start_ms, b.end_ms) == (1000, 2000)


def test_translations_follow_their_source_cues_unless_detached():
    t = edit.nudge(tracks(), "c", 500)
    assert by_id(t.translations["en"])["tb"].end_ms == 4500
    t = edit.detach(t, "en", "tb", True)
    t = edit.nudge(t, "c", 500)
    assert by_id(t.translations["en"])["tb"].end_ms == 4500
    t = edit.detach(t, "en", "tb", False)
    assert by_id(t.translations["en"])["tb"].end_ms == 5000


def test_an_edit_that_would_overlap_a_detached_translation_is_refused():
    t = edit.detach(tracks(), "en", "ta", True)
    t = edit.set_times(t, "a", end_ms=500)
    with pytest.raises(EditError, match="the en track"):
        edit.set_times(t, "b", start_ms=600)


def test_follow_gives_each_attached_translation_the_span_of_its_source_cues():
    source = (cue("a", 0, 1000, "x"), cue("b", 1500, 2500, "y"))
    trans = (cue("t1", 100, 200, "X Y", src=("a", "b")),
             cue("t2", 5000, 6000, "Z", src=("gone",)),
             cue("t3", 7000, 8000, "W", src=("a",), detached=True))
    out = by_id(edit.follow(source, trans))
    assert (out["t1"].start_ms, out["t1"].end_ms) == (0, 2500)
    assert (out["t2"].start_ms, out["t2"].end_ms) == (5000, 6000)
    assert (out["t3"].start_ms, out["t3"].end_ms) == (7000, 8000)


def test_a_split_gives_both_halves_new_ids_from_the_old_and_repoints_the_translation():
    taken = {"a", "b", "c", "ta", "tb"}
    out, (h1, h2) = edit.split(tracks(), "c", at_char=3, at_ms=3400, taken=taken)
    halves = [by_id(out.source)[h1], by_id(out.source)[h2]]
    assert [h.text for h in halves] == ["はい、", "元気です"]
    assert [(h.start_ms, h.end_ms) for h in halves] == [(3000, 3400), (3400, 4000)]
    assert all(h.from_ == ("c",) and h.w is None for h in halves)
    assert {h1, h2} <= taken and "c" not in by_id(out.source)
    assert by_id(out.translations["en"])["tb"].src == ("b", h1, h2)
    assert stale(out) == {"tb"}


@pytest.mark.parametrize("at_char, at_ms", [(0, 3400), (7, 3400), (3, 3000), (3, 4000)])
def test_a_split_needs_text_and_time_on_both_sides(at_char, at_ms):
    with pytest.raises(EditError, match="split"):
        edit.split(tracks(), "c", at_char=at_char, at_ms=at_ms, taken=set())


def test_a_merge_joins_the_text_the_times_the_word_ranges_and_the_flags():
    taken: set[str] = set()
    out, m = edit.merge_next(tracks(), "a", taken=taken)
    merged = by_id(out.source)[m]
    assert merged.text == "おはよう\n元気ですか"
    assert (merged.start_ms, merged.end_ms) == (0, 2000)
    assert merged.w == (0, 5) and merged.from_ == ("a", "b") and merged.flags == ("halluc",)
    assert m in taken and [c.id for c in out.source] == [m, "c"]


def test_a_merge_concatenates_the_translations_of_either_part_into_one_stale_cue():
    t = edit.set_translation_text(tracks(), "en", "ta", "Morning")
    taken: set[str] = set()
    out, m = edit.merge_next(t, "a", taken=taken)
    (joined,) = out.translations["en"]
    assert joined.id in taken and joined.id not in ("ta", "tb")
    assert joined.from_ == ("ta", "tb") and joined.src == (m, "c")
    assert joined.text == "Morning\nHow are you? Fine."
    assert (joined.start_ms, joined.end_ms) == (0, 4000)
    assert "edited" in joined.flags and stale(out) == {joined.id}


def test_merging_two_cues_one_translation_covers_keeps_that_translation():
    out, m = edit.merge_next(tracks(), "b", taken=set())
    tb = by_id(out.translations["en"])["tb"]
    assert tb.src == (m,) and stale(out) == {"tb"}


def test_a_merge_keeps_no_word_range_unless_both_parts_have_one():
    t, _ = edit.insert(tracks(), start_ms=2100, end_ms=2900, text="えっ", taken=set())
    out, m = edit.merge_next(t, "b", taken=set())
    assert by_id(out.source)[m].w is None


def test_the_last_cue_has_nothing_to_merge_with():
    with pytest.raises(EditError, match="last cue"):
        edit.merge_next(tracks(), "c", taken=set())


def test_a_delete_takes_the_id_out_of_every_src_and_drops_a_translation_left_with_none():
    out = edit.delete(tracks(), "a")
    assert [c.id for c in out.translations["en"]] == ["tb"]
    out = edit.delete(tracks(), "b")
    tb = by_id(out.translations["en"])["tb"]
    assert tb.src == ("c",) and (tb.start_ms, tb.end_ms) == (3000, 4000)
    assert stale(out) == {"tb"}


def test_an_inserted_cue_fills_the_gap_and_is_untranslated():
    taken: set[str] = set()
    out, new = edit.insert(tracks(), start_ms=2100, end_ms=3500, text=" えっ ", taken=taken)
    c = by_id(out.source)[new]
    assert (c.start_ms, c.end_ms, c.text, c.w) == (2100, 3000, "えっ", None)
    assert [x.id for x in out.source] == ["a", "b", new, "c"] and new in taken
    assert untranslated([x.id for x in out.source], out.translations["en"]) == [new]


def test_a_cue_cannot_be_inserted_on_top_of_another():
    with pytest.raises(EditError, match="already a cue"):
        edit.insert(tracks(), start_ms=500, end_ms=800, text="x", taken=set())


def test_replace_all_replaces_plain_text_across_the_named_tracks_and_counts_it():
    out, n = edit.replace_all(tracks(), "元気", "げんき", tracks=["source", "en"])
    assert n == 2
    assert by_id(out.source)["c"].text == "はい、げんきです"
    assert "halluc" not in by_id(out.source)["b"].flags
    out, n = edit.replace_all(tracks(), ".", "!", tracks=["en"])
    assert n == 1 and by_id(out.translations["en"])["tb"].text == "How are you? Fine!"
    assert "edited" in by_id(out.translations["en"])["tb"].flags
    out, n = edit.replace_all(tracks(), "good", "Bad", tracks=["en"])
    assert n == 0 and out == tracks()


def test_replace_all_refuses_to_leave_a_cue_empty():
    with pytest.raises(EditError, match="delete it instead"):
        edit.replace_all(tracks(), "おはよう", "", tracks=["source"])


@pytest.mark.parametrize("call", [
    lambda t: edit.set_text(t, "zz", "x"),
    lambda t: edit.set_translation_text(t, "de", "ta", "x"),
    lambda t: edit.detach(t, "en", "zz", True),
    lambda t: edit.replace_all(t, "x", "y", tracks=["de"]),
    lambda t: edit.replace_all(t, "", "y", tracks=["source"]),
])
def test_an_unknown_cue_or_track_or_an_empty_find_is_refused(call):
    with pytest.raises(EditError):
        call(tracks())


def test_every_edit_on_a_two_hour_episode_takes_well_under_a_second():
    source = tuple(cue(f"s{i}", i * 3600, i * 3600 + 3000, f"line {i}", w=(i, i + 1))
                   for i in range(2000))
    en = tuple(cue(f"t{i}", i * 3600, i * 3600 + 3000, f"Line {i}", src=(f"s{i}",))
               for i in range(2000))
    t = Tracks(source, {"en": en})
    taken = {c.id for c in source + en}
    began = time.perf_counter()
    t = edit.set_text(t, "s1000", "changed")
    t = edit.nudge(t, "s1000", 100)
    t, _ = edit.split(t, "s10", at_char=2, at_ms=36_100, taken=taken)
    t, _ = edit.merge_next(t, "s20", taken=taken)
    t = edit.delete(t, "s30")
    t, _ = edit.replace_all(t, "line", "Line", tracks=["source"])
    assert time.perf_counter() - began < 1.0


OP_NAMES = ["set_text", "set_translation_text", "set_times", "nudge", "split", "merge_next",
            "insert", "delete", "detach", "replace_all"]
TEXTS = ["", "x", "a b", "\n", "  y  ", "元気", "w1"]


def _start(spec) -> Tracks:
    t, source = 0, []
    for i, (gap, dur) in enumerate(spec):
        t += gap
        source.append(cue(f"s{i}", t, t + dur, f"w{i}", w=(i, i + 1)))
        t += dur
    pairs = [source[k:k + 2] for k in range(0, len(source), 2)]
    en = tuple(cue(f"t{k}", p[0].start_ms, p[-1].end_ms, f"T{k}", src=tuple(c.id for c in p),
                   src_sha=src_sha([c.text for c in p])) for k, p in enumerate(pairs))
    return Tracks(tuple(source), {"en": en})


def _apply(t: Tracks, op, taken: set[str]) -> Tracks:
    name, k, ms, delta, text = op
    if name == "insert" or not t.source:
        return edit.insert(t, start_ms=ms, end_ms=ms + abs(delta), text=text, taken=taken)[0]
    c = t.source[k % len(t.source)]
    en = t.translations["en"]
    if name == "set_text":
        return edit.set_text(t, c.id, text)
    if name == "set_translation_text":
        return edit.set_translation_text(t, "en", en[k % len(en)].id, text) if en else t
    if name == "set_times":
        return edit.set_times(t, c.id, start_ms=ms, end_ms=ms + delta)
    if name == "nudge":
        return edit.nudge(t, c.id, delta, edge=("start", "end", "both")[k % 3])
    if name == "split":
        at_ms = c.start_ms + ms % (c.end_ms - c.start_ms + 1)
        return edit.split(t, c.id, at_char=k % (len(c.text) + 1), at_ms=at_ms, taken=taken)[0]
    if name == "merge_next":
        return edit.merge_next(t, c.id, taken=taken)[0]
    if name == "delete":
        return edit.delete(t, c.id)
    if name == "detach":
        return edit.detach(t, "en", en[k % len(en)].id, bool(delta % 2)) if en else t
    return edit.replace_all(t, text or "w", text, tracks=["source", "en"])[0]


def _assert_invariants(t: Tracks) -> None:
    check_track(t.source)
    source = by_id(t.source)
    for cues in t.translations.values():
        check_track(cues)
        covered = [i for c in cues for i in c.src or ()]
        assert len(covered) == len(set(covered)), "a source cue is in two translations"
        for c in cues:
            assert c.src and all(i in source for i in c.src)
            if not c.detached:
                assert c.start_ms == min(source[i].start_ms for i in c.src)
                assert c.end_ms == max(source[i].end_ms for i in c.src)


@settings(max_examples=150, deadline=None)
@given(st.lists(st.tuples(st.integers(0, 800), st.integers(1, 2000)), min_size=1, max_size=10),
       st.lists(st.tuples(st.sampled_from(OP_NAMES), st.integers(0, 50),
                          st.integers(-3000, 30_000), st.integers(-3000, 3000),
                          st.sampled_from(TEXTS)), max_size=25))
def test_any_sequence_of_edits_keeps_every_track_valid_and_never_mutates_its_input(spec, ops):
    t = _start(spec)
    taken = {c.id for c in t.source} | {c.id for c in t.translations["en"]}
    for op in ops:
        before = Tracks(t.source, dict(t.translations))
        try:
            out = _apply(t, op, taken)
        except EditError:
            out = t
        assert t == before
        _assert_invariants(out)
        t = out
```

- [ ] **Step 2: Run it; watch it fail.** `uv run pytest tests/test_edit.py -q`. Expected:
  `E   ImportError: cannot import name 'edit' from 'vid2sub.subs'` and `1 error`.
- [ ] **Step 3: Write the code,** `src/vid2sub/subs/edit.py`:

```python
"""Edit operations on an episode's source track and its translations (spec §13.5, §20).

Pure, so the editor's server (Phase 2) and the Pages editor in Pyodide (Phase 4) share one set of
edit rules (spec §20). Every operation returns new `Tracks` and leaves its input alone, so undo is
a stack of old values. Pairing follows spec §13.5: a split re-points translations to both halves,
a merge concatenates the translations of its parts, a delete takes the id out of every `src`, and
an insert is untranslated. A re-pointed or merged translation keeps its old `src_sha` (or none),
so `translate_shape.stale_ids` reads it as stale and no flag is stored. Times are clamped to the
neighbours, never pushed into them (§12.1), and translations follow their source cues unless
detached (§13.4); an edit that would make a translation track overlap is refused. Word ranges and
flags follow the Phase 2 plan's Decision 3: text and time edits keep `w`, split and insert drop
it, merge joins two; a text edit drops `halluc` and a time edit drops `est`, since a person has
now checked them; an edited translation is marked `edited` (Decision 4), as `store.align_ids`
marks one edited outside.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from vid2sub.subs.model import Cue, TrackError, check_track, new_cue_id
from vid2sub.subs.text import canonical

SOURCE = "source"  # the name `replace_all` gives the source track


class EditError(ValueError):
    """An edit that can't be made; the reason is fit to show."""


@dataclass(frozen=True)
class Tracks:
    source: tuple[Cue, ...]
    translations: Mapping[str, tuple[Cue, ...]]  # target track key → cues


def follow(source: Sequence[Cue], translation: Sequence[Cue]) -> tuple[Cue, ...]:
    """Each cue that isn't `detached` takes the span of its `src` cues (spec §13.4).

    A cue none of whose `src` cues is in the source keeps its times."""
    by_id = {c.id: c for c in source}
    out = []
    for c in translation:
        spans = [by_id[i] for i in c.src or () if i in by_id]
        if c.detached or not spans:
            out.append(c)
            continue
        start, end = min(s.start_ms for s in spans), max(s.end_ms for s in spans)
        out.append(c if (start, end) == (c.start_ms, c.end_ms)
                   else c.model_copy(update={"start_ms": start, "end_ms": end}))
    return tuple(sorted(out, key=lambda c: (c.start_ms, c.end_ms)))


def set_text(t: Tracks, cue_id: str, text: str) -> Tracks:
    i = _at(t.source, cue_id)
    c = t.source[i]
    new = c.model_copy(update={"text": _text(text), "flags": _without(c.flags, "halluc")})
    return _done(_splice(t.source, i, 1, new), t.translations)


def set_translation_text(t: Tracks, track: str, cue_id: str, text: str) -> Tracks:
    cues = _track(t, track)
    i = _at(cues, cue_id)
    c = cues[i]
    new = c.model_copy(update={"text": _text(text), "flags": _with(c.flags, "edited")})
    return _done(t.source, {**t.translations, track: _splice(cues, i, 1, new)})


def set_times(t: Tracks, cue_id: str, *, start_ms: int | None = None,
              end_ms: int | None = None) -> Tracks:
    """Clamped to the neighbours: no earlier than the previous cue's end, no later than the next
    cue's start."""
    i = _at(t.source, cue_id)
    c = t.source[i]
    lo, hi = _bounds(t.source, i)
    start = _clamp(c.start_ms if start_ms is None else start_ms, lo, hi)
    end = _clamp(c.end_ms if end_ms is None else end_ms, lo, hi)
    if start >= end:
        raise EditError("a cue must start before it ends, in the gap between its neighbours")
    new = c.model_copy(update={"start_ms": start, "end_ms": end,
                               "flags": _without(c.flags, "est")})
    return _done(_splice(t.source, i, 1, new), t.translations)


def nudge(t: Tracks, cue_id: str, delta_ms: int, *,
          edge: Literal["start", "end", "both"] = "both") -> Tracks:
    """Moves one edge, or the whole cue as a block that stops at its neighbours."""
    i = _at(t.source, cue_id)
    c = t.source[i]
    if edge == "start":
        return set_times(t, cue_id, start_ms=c.start_ms + delta_ms)
    if edge == "end":
        return set_times(t, cue_id, end_ms=c.end_ms + delta_ms)
    if edge != "both":
        raise EditError("a nudge moves the start, the end or both")
    lo, hi = _bounds(t.source, i)
    delta = max(delta_ms, lo - c.start_ms)
    if hi is not None:
        delta = min(delta, hi - c.end_ms)
    return set_times(t, cue_id, start_ms=c.start_ms + delta, end_ms=c.end_ms + delta)


def split(t: Tracks, cue_id: str, *, at_char: int, at_ms: int,
          taken: set[str]) -> tuple[Tracks, tuple[str, str]]:
    """Two new cues from one, both `from` it; translations of it point at both halves.

    `taken` gains the new ids (as `model.new_cue_id` does)."""
    i = _at(t.source, cue_id)
    c = t.source[i]
    left = canonical(c.text[:at_char]) if 0 < at_char < len(c.text) else ""
    right = canonical(c.text[at_char:]) if left else ""
    if not left or not right:
        raise EditError("split inside the text, so both halves have some")
    if not c.start_ms < at_ms < c.end_ms:
        raise EditError("split at a time inside the cue")
    a = Cue(id=new_cue_id(taken), start_ms=c.start_ms, end_ms=at_ms, text=left,
            from_=(c.id,), flags=c.flags)
    b = Cue(id=new_cue_id(taken), start_ms=at_ms, end_ms=c.end_ms, text=right,
            from_=(c.id,), flags=c.flags)
    pairs = {c.id: (a.id, b.id)}
    translations = {k: tuple(_repoint(x, pairs) for x in v) for k, v in t.translations.items()}
    return _done(_splice(t.source, i, 1, a, b), translations), (a.id, b.id)


def merge_next(t: Tracks, cue_id: str, *, taken: set[str]) -> tuple[Tracks, str]:
    """One new cue from a cue and the next; the translations of either part become one."""
    i = _at(t.source, cue_id)
    if i + 1 >= len(t.source):
        raise EditError("the last cue has no next cue to merge with")
    a, b = t.source[i], t.source[i + 1]
    m = Cue(id=new_cue_id(taken), start_ms=a.start_ms, end_ms=b.end_ms,
            text=canonical(a.text + "\n" + b.text),
            w=(a.w[0], b.w[1]) if a.w and b.w else None, from_=(a.id, b.id),
            flags=tuple(sorted(set(a.flags) | set(b.flags))))
    pairs = {a.id: (m.id,), b.id: (m.id,)}
    translations = {k: _merge_translations(v, pairs, taken) for k, v in t.translations.items()}
    return _done(_splice(t.source, i, 2, m), translations), m.id


def insert(t: Tracks, *, start_ms: int, end_ms: int, text: str,
           taken: set[str]) -> tuple[Tracks, str]:
    """A new, untranslated cue in a gap; its end is clamped to the next cue's start."""
    body = _text(text)
    i = sum(1 for c in t.source if c.start_ms <= start_ms)
    if i and t.source[i - 1].end_ms > start_ms:
        raise EditError("there is already a cue at that time")
    start = max(start_ms, 0)
    end = end_ms if i == len(t.source) else min(end_ms, t.source[i].start_ms)
    if start >= end:
        raise EditError("a cue must start before it ends, in the gap between its neighbours")
    new = Cue(id=new_cue_id(taken), start_ms=start, end_ms=end, text=body)
    return _done(_splice(t.source, i, 0, new), t.translations), new.id


def delete(t: Tracks, cue_id: str) -> Tracks:
    """The id leaves every `src`; a translation left with none is deleted (spec §13.5)."""
    i = _at(t.source, cue_id)
    gone = {cue_id: ()}
    translations = {}
    for k, v in t.translations.items():
        kept = []
        for x in v:
            y = _repoint(x, gone)
            if x.src and not y.src:
                continue
            kept.append(y)
        translations[k] = tuple(kept)
    return _done(_splice(t.source, i, 1), translations)


def detach(t: Tracks, track: str, cue_id: str, detached: bool) -> Tracks:
    """A detached translation keeps its own times; reattached, it follows its source again."""
    cues = _track(t, track)
    i = _at(cues, cue_id)
    new = cues[i].model_copy(update={"detached": detached})
    return _done(t.source, {**t.translations, track: _splice(cues, i, 1, new)})


def replace_all(t: Tracks, find: str, replace: str, *,
                tracks: Sequence[str]) -> tuple[Tracks, int]:
    """Plain, case-sensitive text across the named tracks (`"source"` is the source track);
    returns how many were replaced. A source cue changed drops `halluc`; a translation is
    marked `edited`."""
    if not find:
        raise EditError("find needs some text")
    source, translations, count = t.source, dict(t.translations), 0
    for name in dict.fromkeys(tracks):
        if name == SOURCE:
            source, n = _replace_in(source, find, replace, lambda f: _without(f, "halluc"))
        else:
            translations[name], n = _replace_in(_track(t, name), find, replace,
                                                lambda f: _with(f, "edited"))
        count += n
    return _done(source, translations), count


def _done(source: Sequence[Cue], translations: Mapping[str, Sequence[Cue]]) -> Tracks:
    """Translations follow the new source, and every track keeps the invariants (spec §12.1)."""
    out = Tracks(tuple(source), {k: follow(source, v) for k, v in translations.items()})
    for name, cues in ((SOURCE, out.source), *out.translations.items()):
        try:
            check_track(cues)
        except TrackError as e:
            raise EditError(f"the {name} track would break: {e}") from None
    return out


def _merge_translations(cues: Sequence[Cue], pairs: Mapping[str, tuple[str, ...]],
                        taken: set[str]) -> tuple[Cue, ...]:
    parts = [c for c in cues if c.src and any(i in pairs for i in c.src)]
    if len(parts) < 2:
        return tuple(_repoint(c, pairs) for c in cues)
    joined = Cue(id=new_cue_id(taken), start_ms=min(p.start_ms for p in parts),
                 end_ms=max(p.end_ms for p in parts),
                 text=canonical("\n".join(p.text for p in parts)),
                 src=_mapped([i for p in parts for i in p.src or ()], pairs),
                 from_=tuple(p.id for p in parts),
                 flags=tuple(sorted({f for p in parts for f in p.flags})))
    first = cues.index(parts[0])
    rest = [c for c in cues if c not in parts]
    return tuple(rest[:first]) + (joined,) + tuple(rest[first:])


def _repoint(c: Cue, pairs: Mapping[str, tuple[str, ...]]) -> Cue:
    if not c.src or not any(i in pairs for i in c.src):
        return c
    return c.model_copy(update={"src": _mapped(c.src, pairs)})


def _mapped(src: Sequence[str], pairs: Mapping[str, tuple[str, ...]]) -> tuple[str, ...]:
    out: list[str] = []
    for i in src:
        for j in pairs.get(i, (i,)):
            if j not in out:
                out.append(j)
    return tuple(out)


def _replace_in(cues: Sequence[Cue], find: str, replace: str,
                flags: Callable[[tuple[str, ...]], tuple[str, ...]]) -> tuple[tuple[Cue, ...], int]:
    out, count = [], 0
    for c in cues:
        n = c.text.count(find)
        if not n:
            out.append(c)
            continue
        text = canonical(c.text.replace(find, replace))
        if not text:
            raise EditError(f"replacing would leave cue {c.id} empty: delete it instead")
        count += n
        out.append(c.model_copy(update={"text": text, "flags": flags(c.flags)}))
    return tuple(out), count


def _at(cues: Sequence[Cue], cue_id: str) -> int:
    for i, c in enumerate(cues):
        if c.id == cue_id:
            return i
    raise EditError(f"there is no cue {cue_id}")


def _track(t: Tracks, track: str) -> tuple[Cue, ...]:
    if track not in t.translations:
        raise EditError(f"there is no {track} track")
    return t.translations[track]


def _text(text: str) -> str:
    out = canonical(text)
    if not out:
        raise EditError("a cue needs text: delete it instead")
    return out


def _bounds(cues: Sequence[Cue], i: int) -> tuple[int, int | None]:
    lo = cues[i - 1].end_ms if i > 0 else 0
    hi = cues[i + 1].start_ms if i + 1 < len(cues) else None
    return lo, hi


def _clamp(ms: int, lo: int, hi: int | None) -> int:
    ms = max(ms, lo)
    return ms if hi is None else min(ms, hi)


def _splice(cues: Sequence[Cue], i: int, n: int, *new: Cue) -> tuple[Cue, ...]:
    return (*cues[:i], *new, *cues[i + n:])


def _without(flags: tuple[str, ...], flag: str) -> tuple[str, ...]:
    return tuple(f for f in flags if f != flag)


def _with(flags: tuple[str, ...], flag: str) -> tuple[str, ...]:
    return flags if flag in flags else (*flags, flag)
```

- [ ] **Step 4: Run the checks; they pass.** `uv run pytest tests/test_edit.py
  tests/test_purity.py -q` first (`34 passed`), then `make check`. Expected: `498 passed, 2
  skipped, 4 deselected` twice (the local zone, then UTC), `All checks passed!` and `no leaks
  found`.
- [ ] **Step 5: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(subs): 🤖 subs.edit splits, merges, nudges, inserts and deletes cues and re-points their translations

The editor's edit rules, pure so the server and (Phase 4) Pyodide share
them (spec §20): set_text, set_translation_text, set_times, nudge, split,
merge_next, insert, delete, detach and replace_all, each returning new
Tracks and never mutating its input. Pairing follows spec §13.5: a split
re-points translations to both halves, a merge concatenates the
translations of its parts into one new cue, a delete takes the id out of
every src and drops a translation left with none, an insert is
untranslated; each reads as stale through translate_shape.stale_ids, with
no stored flag. Times clamp to the neighbours; attached translations
follow their source (follow); an edit that would make a translation
track overlap a detached cue is refused. w, halluc and est follow the
plan's Decision 3; an edited translation is marked edited (Decision 4).

The new test failed first with: ImportError: cannot import name 'edit'
from 'vid2sub.subs'. A hypothesis property test runs random edit
sequences and checks spec §12.1's invariants on every track, each
translation's span and src, and that no input is mutated; with delete's
"drop a translation left with no src" rule removed, it and the delete
test fail. tests/test_purity.py stays green.

Docs read: none beyond the code (hypothesis used as tests/test_build.py
uses it: given, settings, strategies).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 2
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/subs/edit.py tests/test_edit.py`, `git commit -F .git/COMMIT_MSG`, then
  `git log -1 --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 6: Review, look forward, close.** The Tier 2 review from `$(cat .git/TASK_BASE)`
  (`AGENTS.md`, *Reviews*); the forward review over Tasks 5, 6, 7, 14 and 15 (the `Episode`
  holds `Tracks`; `ops.EditOp` maps one op to each function here; retranslate builds on
  `stale_ids` reading re-pointed and merged cues as stale); the docs this task made untrue
  (none expected: `subs.edit` is new). Then the close, its own commit, holding this plan with
  this task's boxes ticked and **Now** set to `Task 3: The cache and the playback audio,
  open.`; S28 stays `planned` (its proof's Playwright half is Task 15's). The message, in
  `.git/CLOSE_MSG`:

```text
docs(plan): 🤖 close Task 2: Edit operations

Drift: none
Rulings: none
Phase-end: none
Forward: none
Tier: 2
Rounds: none
Findings: none

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 2
Co-Authored-By: <the model's own line>
```

  `git add docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md`, `git commit -F
  .git/CLOSE_MSG`.

***

### Task 3: The cache and the playback audio

**Tier:** 2 · **Scenarios:** S43, S46

**Files:**
- Create: `src/vid2sub/cache.py`, `src/vid2sub/media/preview.py`,
  `src/vid2sub/commands/cache.py`
- Modify: `src/vid2sub/cli.py` (register `cache`), `src/vid2sub/commands/doctor.py` (cache size),
  `tests/helpers.py` (`make_clip` gains `audio_codec`, track titles and a chapter)
- Test: `tests/test_cache.py`, `tests/test_playback.py`

**Interfaces:**
- Consumes: `vid2sub.media.tools.Tools`, `run_tool`, `input_args`; `vid2sub.config.Config`
  (`defaults.cache_max_gb`); `platformdirs.user_cache_dir`.
- Produces:
  - `cache.default_root() -> Path` (`platformdirs.user_cache_dir("vid2sub", appauthor=False)`:
    `~/Library/Caches/vid2sub`, `%LOCALAPPDATA%\vid2sub\Cache`, `~/.cache/vid2sub`, spec §8.9;
    `$XDG_CACHE_HOME` wins where platformdirs 4.13 honours it, macOS included)
  - `cache.from_config(config: Config, root: Path | None = None) -> Cache` (capped at
    `defaults.cache_max_gb` × 10⁹ bytes; `root` defaults to `default_root()`)
  - `class Cache: __init__(self, root: Path, *, max_bytes: int)`; `root`, `max_bytes`
    attributes; `folder(self, key: str) -> Path` (`key` is a 64-hex `quick_sha256`, else
    `ValueError`; creates the root and the folder 0700 and marks it used by touching it);
    `size(self) -> int`; `evict(self, *, keep: str | None = None) -> int` (least recently used
    first, never `keep`, until `size() <= max_bytes`; returns bytes freed); `clear(self) -> int`
    (removes only 64-hex folders, never through a symlink; returns bytes freed)
  - `preview.playback_audio(video: Path, *, key: str, audio_index: int, tools: Tools,
    cache: Cache, timeout: float) -> Path` (`<cache>/<key>/playback-a<audio_index>.m4a`: AAC
    stereo 160k in MP4, `+faststart`, no video, subtitles, data, metadata or chapters; made once
    per key and track, then reused; `audio_index` counts audio tracks only, ffmpeg's `a:N`, as
    `probe.AudioTrack.index` and the transcript's `inputs.audio_track` do)
  - `vid2sub cache clear [--json]` (`{"event": "cache_cleared", "bytes": N}`, or
    `cleared N.N MB from the cache`; never the path)
  - `vid2sub doctor` gains a non-essential `cache` check, detail `<used> MB of <cap> GB`, in its
    human and `--json` output.

- [ ] **Step 0: Record the base:** `git rev-parse HEAD > .git/TASK_BASE`.
- [ ] **Step 1: Write the failing test,** `tests/test_cache.py`:

```python
import os
import stat
import sys
from pathlib import Path

import pytest

from vid2sub import cache as caching
from vid2sub.cache import Cache
from vid2sub.config import Config

OLD, MID, NEW = ("a" * 64, "b" * 64, "c" * 64)


def entry(cache: Cache, key: str, size: int, used: float) -> Path:
    folder = cache.folder(key)
    (folder / "playback-a0.m4a").write_bytes(b"x" * size)
    os.utime(folder, (used, used))
    return folder


@pytest.fixture
def cache(tmp_path) -> Cache:
    c = Cache(tmp_path / "cache", max_bytes=250)
    for key, used in ((OLD, 1_000), (MID, 2_000), (NEW, 3_000)):
        entry(c, key, 100, used)
    return c


def test_the_cache_is_the_platforms_cache_folder(monkeypatch, tmp_path):
    if sys.platform == "darwin":
        monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
        assert caching.default_root() == Path.home() / "Library" / "Caches" / "vid2sub"
    elif sys.platform == "win32":
        assert caching.default_root().parts[-2:] == ("vid2sub", "Cache")
    else:
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
        assert caching.default_root() == tmp_path / "vid2sub"


def test_the_cap_comes_from_cache_max_gb():
    config = Config.model_validate({"defaults": {"cache_max_gb": 1.5}})
    c = caching.from_config(config, Path("/nowhere"))
    assert c.max_bytes == 1_500_000_000 and c.root == Path("/nowhere")


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes")
def test_an_entry_folder_is_private_to_the_user(tmp_path):
    folder = Cache(tmp_path / "cache", max_bytes=1).folder(OLD)
    assert stat.S_IMODE(folder.stat().st_mode) == 0o700
    assert stat.S_IMODE((tmp_path / "cache").stat().st_mode) == 0o700


@pytest.mark.parametrize("key", ["abc", "A" * 64, "../" + "a" * 61, ""])
def test_a_key_that_isnt_a_quick_hash_is_refused(tmp_path, key):
    with pytest.raises(ValueError, match="64-hex"):
        Cache(tmp_path / "cache", max_bytes=1).folder(key)


def test_the_size_counts_every_entry(cache):
    assert cache.size() == 300


def test_past_the_cap_the_least_recently_used_entry_goes_first(cache):
    assert cache.evict() == 100
    assert not (cache.root / OLD).exists()
    assert (cache.root / MID).exists() and (cache.root / NEW).exists()
    assert cache.evict() == 0


def test_using_an_entry_makes_it_the_most_recent(cache):
    cache.folder(OLD)
    cache.evict()
    assert (cache.root / OLD).exists() and not (cache.root / MID).exists()


def test_eviction_never_removes_the_entry_it_is_told_to_keep(cache):
    cache.max_bytes = 0
    assert cache.evict(keep=OLD) == 200
    assert [p.name for p in cache.root.iterdir()] == [OLD]


def test_clear_removes_every_entry_and_nothing_else(cache):
    (cache.root / "notes").mkdir()
    (cache.root / "notes" / "keep.txt").write_text("mine")
    (cache.root / "readme.txt").write_text("mine")
    assert cache.clear() == 300
    assert sorted(p.name for p in cache.root.iterdir()) == ["notes", "readme.txt"]
    assert cache.size() == 0 and cache.clear() == 0


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges on Windows")
def test_clear_never_follows_a_symlink(cache, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "precious.mkv").write_bytes(b"v" * 1000)
    (cache.root / ("d" * 64)).symlink_to(outside, target_is_directory=True)
    (cache.root / NEW / "link").symlink_to(outside, target_is_directory=True)
    (cache.root / NEW / "file-link").symlink_to(outside / "precious.mkv")
    assert cache.size() == 300
    assert cache.clear() == 300
    assert (outside / "precious.mkv").read_bytes() == b"v" * 1000
    assert (cache.root / ("d" * 64)).is_symlink()


def test_a_missing_cache_is_empty(tmp_path):
    c = Cache(tmp_path / "never-made", max_bytes=1)
    assert (c.size(), c.evict(), c.clear()) == (0, 0, 0)
    assert not (tmp_path / "never-made").exists()
```

- [ ] **Step 2: Run it; watch it fail.** `uv run pytest tests/test_cache.py -q`. Expected:
  `E   ImportError: cannot import name 'cache' from 'vid2sub'` and `1 error`.
- [ ] **Step 3: Write the code,** `src/vid2sub/cache.py`:

```python
"""The cache of playback audio and preview copies, one folder per video (spec §8.9).

Everything in it can be made again from the video, so it is disposable: capped by
`defaults.cache_max_gb`, least recently used first, and emptied by `vid2sub cache clear` (S46).
An entry is a folder named by the video's 64-hex `quick_sha256` (§8.3), made 0700 like a job's
scratch folder because it holds the user's audio; using an entry touches its folder, so the
folder's mtime is its last use. Eviction and `clear()` remove only folders with such names and
never follow a symlink, so a cache folder that is shared with, or points into, anything else
loses nothing but vid2sub's own entries (the playback audio moved here from M3: Dan, Q&A item 13).
"""

from __future__ import annotations

import os
import re
import shutil
import stat
from pathlib import Path

import platformdirs

from vid2sub.config import Config

GB = 1_000_000_000
_KEY = re.compile(r"[0-9a-f]{64}")


def default_root() -> Path:
    """`~/Library/Caches/vid2sub`, `%LOCALAPPDATA%\\vid2sub\\Cache` or `~/.cache/vid2sub`
    (spec §8.9); `$XDG_CACHE_HOME` wins where platformdirs honours it."""
    return Path(platformdirs.user_cache_dir("vid2sub", appauthor=False))


def from_config(config: Config, root: Path | None = None) -> Cache:
    return Cache(root or default_root(), max_bytes=int(config.defaults.cache_max_gb * GB))


class Cache:
    def __init__(self, root: Path, *, max_bytes: int):
        self.root = root
        self.max_bytes = max_bytes

    def folder(self, key: str) -> Path:
        """The entry for one video, made 0700 if it's new, and marked used."""
        if not _KEY.fullmatch(key):
            raise ValueError("a cache key is a video's 64-hex quick_sha256")
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = self.root / key
        if path.is_symlink():
            path.unlink()
        path.mkdir(mode=0o700, exist_ok=True)
        os.utime(path)
        return path

    def size(self) -> int:
        return sum(_bytes(p) for p in self._entries())

    def evict(self, *, keep: str | None = None) -> int:
        """Removes the least recently used entries, never `keep`, until the cache fits its cap;
        returns the bytes freed."""
        entries = sorted(self._entries(), key=lambda p: (p.lstat().st_mtime_ns, p.name))
        total = sum(_bytes(p) for p in entries)
        freed = 0
        for p in entries:
            if total - freed <= self.max_bytes:
                break
            if p.name != keep:
                freed += _remove(p)
        return freed

    def clear(self) -> int:
        """Removes every entry and nothing else; returns the bytes freed."""
        return sum(_remove(p) for p in self._entries())

    def _entries(self) -> list[Path]:
        try:
            found = list(self.root.iterdir())
        except OSError:  # no cache yet, or one this user can't read
            return []
        return [p for p in found if _KEY.fullmatch(p.name) and _is_real_dir(p)]


def _is_real_dir(path: Path) -> bool:
    try:
        return stat.S_ISDIR(path.lstat().st_mode)
    except OSError:
        return False


def _bytes(folder: Path) -> int:
    """The regular files under `folder`, never following a symlink."""
    total = 0
    for dirpath, _, names in os.walk(folder):
        for name in names:
            try:
                st = os.lstat(os.path.join(dirpath, name))
            except OSError:
                continue
            if stat.S_ISREG(st.st_mode):
                total += st.st_size
    return total


def _remove(folder: Path) -> int:
    """Removes one entry folder; shutil.rmtree unlinks symlinks inside it, never their targets."""
    before = _bytes(folder)
    shutil.rmtree(folder, ignore_errors=True)
    return before - (_bytes(folder) if folder.exists() else 0)
```

- [ ] **Step 4: Run the checks; they pass.** `uv run pytest tests/test_cache.py -q` first
  (`14 passed` on macOS and Linux; Windows skips two), then the guard checks, then `make check`.
  **Guard checks** (data loss): in `Cache._entries`, change the return line to
  `return [p for p in found if _is_real_dir(p)]`; `uv run pytest tests/test_cache.py -q` gives
  `FAILED tests/test_cache.py::test_clear_removes_every_entry_and_nothing_else`; restore it.
  Then change it to `return [p for p in found if _KEY.fullmatch(p.name) and p.is_dir()]`, and in
  `_bytes` use `os.walk(folder, followlinks=True)` and `os.stat` for `os.lstat`; the run gives
  `FAILED tests/test_cache.py::test_clear_never_follows_a_symlink - assert 3300 ...`; restore
  all three. `make check`. Expected: `512 passed, 2 skipped, 4 deselected` twice (the local zone,
  then UTC), `All checks passed!` and `no leaks found`.
- [ ] **Step 5: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(cache): 🤖 the cache keeps one private folder per video and drops the least recently used past its cap

vid2sub.cache (spec §8.9, S46): default_root() is platformdirs'
user_cache_dir("vid2sub", appauthor=False), so ~/Library/Caches/vid2sub,
%LOCALAPPDATA%\vid2sub\Cache or ~/.cache/vid2sub; from_config() caps it at
defaults.cache_max_gb. An entry is a folder named by the video's 64-hex
quick_sha256, made 0700 and touched on every use; evict() removes the
least recently used entries until the cache fits, never `keep`; clear()
removes every entry and nothing else.

The new test failed first with: ImportError: cannot import name 'cache'
from 'vid2sub'. Guards checked by reverting each fix: without the 64-hex
name filter, test_clear_removes_every_entry_and_nothing_else fails; with
entries and their files found through symlinks (is_dir, os.stat,
followlinks=True), test_clear_never_follows_a_symlink fails (3300 bytes
counted, not 300).

Docs read: platformdirs 4.13.0's source (user_cache_dir's signature;
macos.py, windows.py and unix.py for the three folders; XDGMixin, so
XDG_CACHE_HOME also wins on macOS); Python 3.12's shutil.rmtree (it
refuses a symlinked top folder and is symlink-attack resistant where
fd-based functions exist).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 3
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/cache.py tests/test_cache.py`, `git commit -F .git/COMMIT_MSG`, then
  `git log -1 --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 6: Write the failing test,** in two parts. First, in `tests/helpers.py`, replace the
  whole `make_clip` function (from `def make_clip(` to its `return out`) with:

```python
def make_clip(directory: Path, name: str = "clip.mkv", *, seconds: float = 4.0,
              audio_delay: float = 0.0, audio_langs=("jpn",), default_audio: int = 0,
              title: str | None = None, speech: Path | None = None, audio_codec: str = "aac",
              chapter: str | None = None) -> Path:
    """A small video made with ffmpeg's lavfi sources: a test pattern, one sine-wave audio track
    per language (or `speech` for the first) in `audio_codec`, an optional audio delay, a title
    (on the file and each audio track) and one chapter with a title."""
    ffmpeg = shutil.which("ffmpeg")
    assert ffmpeg, "ffmpeg is needed for media tests"
    args = [ffmpeg, "-nostdin", "-v", "error", "-y",
            "-f", "lavfi", "-i", f"testsrc=size=160x120:rate=10:duration={seconds}"]
    for k, _ in enumerate(audio_langs):
        if audio_delay:
            args += ["-itsoffset", str(audio_delay)]
        if speech is not None and k == 0:
            args += ["-i", str(speech)]
        else:
            args += ["-f", "lavfi", "-i", f"sine=frequency={440 + 110 * k}:duration={seconds}"]
    if chapter:
        meta = directory / f"{name}.ffmetadata"
        meta.write_text(f";FFMETADATA1\n[CHAPTER]\nTIMEBASE=1/1000\nSTART=0\n"
                        f"END={int(seconds * 1000)}\ntitle={chapter}\n", encoding="utf-8")
        args += ["-f", "ffmetadata", "-i", str(meta)]
    args += ["-map", "0:v"]
    for k in range(len(audio_langs)):
        args += ["-map", f"{k + 1}:a"]
    if chapter:
        args += ["-map_chapters", str(len(audio_langs) + 1)]
    args += ["-c:v", "mpeg4", "-c:a", audio_codec]
    for k, lang in enumerate(audio_langs):
        args += [f"-metadata:s:a:{k}", f"language={lang}",
                 f"-disposition:a:{k}", "default" if k == default_audio else "0"]
        if title:
            args += [f"-metadata:s:a:{k}", f"title={title}"]
    if title:
        args += ["-metadata", f"title={title}"]
    out = directory / name
    subprocess.run(args + [str(out)], check=True)
    return out
```

  Then `tests/test_playback.py`:

```python
import json
import os
import subprocess

import numpy as np
import pytest
from helpers import make_clip

from vid2sub.cache import Cache
from vid2sub.media import preview
from vid2sub.media.tools import ToolFailed, Tools

pytestmark = pytest.mark.media
KEY = "a" * 64


def ffprobe(tools: Tools, path) -> dict:
    return json.loads(subprocess.run(
        [tools.ffprobe, "-v", "error", "-show_format", "-show_streams", "-show_chapters",
         "-of", "json", str(path)], capture_output=True, check=True).stdout)


def loudest_hz(tools: Tools, path) -> float:
    pcm = subprocess.run([tools.ffmpeg, "-v", "error", "-i", str(path), "-ac", "1", "-ar",
                          "16000", "-f", "s16le", "-"], capture_output=True, check=True).stdout
    samples = np.frombuffer(pcm, dtype="<i2").astype(np.float64)
    spectrum = np.abs(np.fft.rfft(samples))
    return float(np.fft.rfftfreq(len(samples), 1 / 16_000)[spectrum.argmax()])


@pytest.fixture
def clip(tmp_path):
    """Two AC-3 tracks (440 Hz, then 550 Hz), a title on the file and its tracks, a chapter."""
    return make_clip(tmp_path, "Show - S01E01.mkv", seconds=2.0, audio_langs=("jpn", "eng"),
                     audio_codec="ac3", title="Secret Show Title", chapter="Secret Chapter")


@pytest.fixture
def cache(tmp_path) -> Cache:
    return Cache(tmp_path / "cache", max_bytes=10**9)


def make(clip, cache, audio_index=0):
    return preview.playback_audio(clip, key=KEY, audio_index=audio_index, tools=Tools.find(),
                                  cache=cache, timeout=60)


def test_an_ac3_track_becomes_aac_stereo_in_mp4_with_no_title_or_chapters(clip, cache):
    tools = Tools.find()
    assert [s["codec_name"] for s in ffprobe(tools, clip)["streams"][1:]] == ["ac3", "ac3"]
    out = make(clip, cache)
    assert out == cache.root / KEY / "playback-a0.m4a"
    info = ffprobe(tools, out)
    assert "mp4" in info["format"]["format_name"].split(",")
    (stream,) = info["streams"]
    assert (stream["codec_type"], stream["codec_name"], stream["channels"]) == ("audio", "aac", 2)
    assert "Secret" not in json.dumps(info)
    assert "title" not in (info["format"].get("tags") or {})
    assert info["chapters"] == []
    assert [p.name for p in out.parent.iterdir()] == ["playback-a0.m4a"]


def test_the_chosen_audio_track_is_the_one_converted(clip, cache):
    tools = Tools.find()
    assert abs(loudest_hz(tools, make(clip, cache, 0)) - 440) < 5
    second = make(clip, cache, 1)
    assert second.name == "playback-a1.m4a"
    assert abs(loudest_hz(tools, second) - 550) < 5


def test_the_playback_audio_is_made_once_and_then_reused(clip, cache, monkeypatch):
    calls = []
    real = preview.run_tool
    monkeypatch.setattr(preview, "run_tool", lambda *a, **kw: calls.append(a) or real(*a, **kw))
    first = make(clip, cache)
    made = first.stat().st_mtime_ns
    os.utime(cache.root / KEY, (1_000, 1_000))
    second = make(clip, cache)
    assert second == first and len(calls) == 1
    assert second.stat().st_mtime_ns == made
    assert (cache.root / KEY).stat().st_mtime > 1_000  # reusing it marks the entry used


def test_making_one_evicts_older_entries_but_never_its_own(clip, tmp_path):
    cache = Cache(tmp_path / "cache", max_bytes=1)
    old = cache.folder("b" * 64)
    (old / "playback-a0.m4a").write_bytes(b"x" * 1000)
    os.utime(old, (1_000, 1_000))
    out = make(clip, cache)
    assert out.is_file() and not old.exists()


def test_a_file_ffmpeg_cannot_read_leaves_nothing_in_the_cache(tmp_path, cache):
    bad = tmp_path / "Show - S01E02.mkv"
    bad.write_bytes(b"not a video")
    with pytest.raises(ToolFailed):
        make(bad, cache)
    assert list((cache.root / KEY).iterdir()) == []


def test_a_negative_track_index_is_refused(clip, cache):
    with pytest.raises(ValueError, match="audio track"):
        make(clip, cache, -1)
```

- [ ] **Step 7: Run it; watch it fail.** `uv run pytest tests/test_playback.py -q`. Expected:
  `E   ImportError: cannot import name 'preview' from 'vid2sub.media'` and `1 error`.
- [ ] **Step 8: Write the code,** `src/vid2sub/media/preview.py`, with the file tools (a hook
  blocks shell commands that name `src/vid2sub/media/`):

```python
"""The playback audio: an episode's audio as AAC stereo, for a browser that can't play it (§8.8).

A browser plays neither AC-3, E-AC-3, DTS nor TrueHD, and silent playback is worse than none
(§8.2), so the editor plays this `.m4a` instead, made on demand into the cache (§8.9) the first
time an episode needs it and reused after that (Dan, 2026-10-14; Q&A item 13 brought it into
Phase 2, S43). Only the chosen audio track is kept, with no video, subtitles, data, metadata or
chapters, so the show's title never reaches the file, as with chunks (§7.3); `+faststart` puts
the index first so playback starts before the whole file is read. ffmpeg writes to a temporary
name in the entry's folder and the result is renamed into place, so a half-made file is never
served, and an entry being made is never evicted.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from vid2sub.cache import Cache
from vid2sub.media.tools import Tools, input_args, run_tool


def playback_audio(video: Path, *, key: str, audio_index: int, tools: Tools, cache: Cache,
                   timeout: float) -> Path:
    """`audio_index` counts audio tracks only (ffmpeg's `a:N`, `probe.AudioTrack.index`)."""
    if isinstance(audio_index, bool) or not isinstance(audio_index, int) or audio_index < 0:
        raise ValueError("an audio track is a number from 0")
    folder = cache.folder(key)
    out = folder / f"playback-a{audio_index}.m4a"
    if out.is_file():
        return out
    tmp = folder / f".playback-a{audio_index}-{secrets.token_hex(4)}.part"
    try:
        run_tool([tools.need("ffmpeg"), "-nostdin", "-hide_banner", "-loglevel", "error",
                  *input_args(video), "-map", f"0:a:{audio_index}", "-vn", "-sn", "-dn",
                  "-ac", "2", "-c:a", "aac", "-b:a", "160k", "-map_metadata", "-1",
                  "-map_chapters", "-1", "-fflags", "+bitexact", "-movflags", "+faststart",
                  "-f", "mp4", str(tmp)], cwd=folder, timeout=timeout)
        os.replace(tmp, out)
    finally:
        tmp.unlink(missing_ok=True)
    cache.evict(keep=key)
    return out
```

- [ ] **Step 9: Run the checks; they pass.** `uv run pytest tests/test_playback.py
  tests/test_decode.py tests/test_probe.py -q` first (`25 passed`: the old media tests still pass
  with the new `make_clip`), then the metadata check, then `make check`. **Metadata check:** with
  the file tools, delete `"-map_metadata", "-1",` and `"-map_chapters", "-1",` from the ffmpeg
  arguments; `uv run pytest tests/test_playback.py -q` gives `FAILED
  tests/test_playback.py::test_an_ac3_track_becomes_aac_stereo_in_mp4_with_no_title_or_chapters`;
  restore both. `make check`. Expected: `518 passed, 2 skipped, 4 deselected` twice, `All checks
  passed!` and `no leaks found`.
- [ ] **Step 10: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(media): 🤖 an episode's audio track becomes a metadata-free AAC stereo .m4a in the cache, made once

media.preview.playback_audio (spec §8.8, S43): ffmpeg, through run_tool
and input_args, maps the chosen audio track (ffmpeg's a:N, as
probe.AudioTrack.index and the transcript's inputs.audio_track count
them) to AAC stereo at 160k in MP4 with +faststart, with no video,
subtitles, data, metadata or chapters, into a temporary name in the
video's cache folder, then renames it to playback-a<N>.m4a. An existing
file is reused and its folder touched; after making one, the cache is
evicted down to its cap, never this entry. tests/helpers.make_clip gains
audio_codec, a title on each audio track as well as the file, and a
chapter, so the test clip is an MKV with two AC-3 tracks.

The new test failed first with: ImportError: cannot import name 'preview'
from 'vid2sub.media'. Without -map_metadata -1 the file's and the
track's titles reach the .m4a; without -map_chapters -1 an untitled
chapter does; with both removed,
test_an_ac3_track_becomes_aac_stereo_in_mp4_with_no_title_or_chapters
fails.

Docs read: ffmpeg's ffmpeg.html (-map with 0:a:N, -map_metadata and its
negative index, -map_chapters -1, -vn/-sn/-dn, -ac, -nostdin,
-hide_banner, -loglevel) and ffmpeg-formats.html (fflags bitexact: "Only
write platform-, build- and time-independent data"; movflags faststart);
checked against ffmpeg 9.0.2 locally (mp4 muxer, native aac and ac3
encoders).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 3
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/media/preview.py tests/helpers.py tests/test_playback.py` (when this
  listing was built the hook let `git add` name the path; if it blocks it, say so and stop
  rather than rephrasing the command), `git commit -F .git/COMMIT_MSG`, then
  `git log -1 --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 11: Write the failing test.** Replace `tests/test_cache.py` with this version:
  Step 1's file plus `import json`, `from vid2sub.cli import main`, and the tests from
  `def home_cache` down.

```python
import json
import os
import stat
import sys
from pathlib import Path

import pytest

from vid2sub import cache as caching
from vid2sub.cache import Cache
from vid2sub.cli import main
from vid2sub.config import Config

OLD, MID, NEW = ("a" * 64, "b" * 64, "c" * 64)


def entry(cache: Cache, key: str, size: int, used: float) -> Path:
    folder = cache.folder(key)
    (folder / "playback-a0.m4a").write_bytes(b"x" * size)
    os.utime(folder, (used, used))
    return folder


@pytest.fixture
def cache(tmp_path) -> Cache:
    c = Cache(tmp_path / "cache", max_bytes=250)
    for key, used in ((OLD, 1_000), (MID, 2_000), (NEW, 3_000)):
        entry(c, key, 100, used)
    return c


def test_the_cache_is_the_platforms_cache_folder(monkeypatch, tmp_path):
    if sys.platform == "darwin":
        monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
        assert caching.default_root() == Path.home() / "Library" / "Caches" / "vid2sub"
    elif sys.platform == "win32":
        assert caching.default_root().parts[-2:] == ("vid2sub", "Cache")
    else:
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
        assert caching.default_root() == tmp_path / "vid2sub"


def test_the_cap_comes_from_cache_max_gb():
    config = Config.model_validate({"defaults": {"cache_max_gb": 1.5}})
    c = caching.from_config(config, Path("/nowhere"))
    assert c.max_bytes == 1_500_000_000 and c.root == Path("/nowhere")


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes")
def test_an_entry_folder_is_private_to_the_user(tmp_path):
    folder = Cache(tmp_path / "cache", max_bytes=1).folder(OLD)
    assert stat.S_IMODE(folder.stat().st_mode) == 0o700
    assert stat.S_IMODE((tmp_path / "cache").stat().st_mode) == 0o700


@pytest.mark.parametrize("key", ["abc", "A" * 64, "../" + "a" * 61, ""])
def test_a_key_that_isnt_a_quick_hash_is_refused(tmp_path, key):
    with pytest.raises(ValueError, match="64-hex"):
        Cache(tmp_path / "cache", max_bytes=1).folder(key)


def test_the_size_counts_every_entry(cache):
    assert cache.size() == 300


def test_past_the_cap_the_least_recently_used_entry_goes_first(cache):
    assert cache.evict() == 100
    assert not (cache.root / OLD).exists()
    assert (cache.root / MID).exists() and (cache.root / NEW).exists()
    assert cache.evict() == 0


def test_using_an_entry_makes_it_the_most_recent(cache):
    cache.folder(OLD)
    cache.evict()
    assert (cache.root / OLD).exists() and not (cache.root / MID).exists()


def test_eviction_never_removes_the_entry_it_is_told_to_keep(cache):
    cache.max_bytes = 0
    assert cache.evict(keep=OLD) == 200
    assert [p.name for p in cache.root.iterdir()] == [OLD]


def test_clear_removes_every_entry_and_nothing_else(cache):
    (cache.root / "notes").mkdir()
    (cache.root / "notes" / "keep.txt").write_text("mine")
    (cache.root / "readme.txt").write_text("mine")
    assert cache.clear() == 300
    assert sorted(p.name for p in cache.root.iterdir()) == ["notes", "readme.txt"]
    assert cache.size() == 0 and cache.clear() == 0


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges on Windows")
def test_clear_never_follows_a_symlink(cache, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "precious.mkv").write_bytes(b"v" * 1000)
    (cache.root / ("d" * 64)).symlink_to(outside, target_is_directory=True)
    (cache.root / NEW / "link").symlink_to(outside, target_is_directory=True)
    (cache.root / NEW / "file-link").symlink_to(outside / "precious.mkv")
    assert cache.size() == 300
    assert cache.clear() == 300
    assert (outside / "precious.mkv").read_bytes() == b"v" * 1000
    assert (cache.root / ("d" * 64)).is_symlink()


def test_a_missing_cache_is_empty(tmp_path):
    c = Cache(tmp_path / "never-made", max_bytes=1)
    assert (c.size(), c.evict(), c.clear()) == (0, 0, 0)
    assert not (tmp_path / "never-made").exists()


@pytest.fixture
def home_cache(tmp_path, monkeypatch) -> Cache:
    monkeypatch.setattr(caching, "default_root", lambda: tmp_path / "cache")
    c = Cache(tmp_path / "cache", max_bytes=1)
    entry(c, OLD, 2_500_000, 1_000)
    return c


def test_cache_clear_reports_the_bytes_freed_as_one_json_line(home_cache, capsys):
    assert main(["cache", "clear", "--json"]) == 0
    out = capsys.readouterr().out
    assert [json.loads(line) for line in out.splitlines()] == [
        {"event": "cache_cleared", "bytes": 2_500_000}]
    assert str(home_cache.root) not in out
    assert not (home_cache.root / OLD).exists()


def test_cache_clear_tells_a_person_how_much_it_freed(home_cache, capsys):
    assert main(["cache", "clear"]) == 0
    assert capsys.readouterr().out == "cleared 2.5 MB from the cache\n"


def test_doctor_reports_the_cache_size_against_its_cap(home_cache, tmp_path, capsys):
    args = ["doctor", "--config", str(tmp_path / "none.toml"), "--offline"]
    main(args + ["--json"])
    out = capsys.readouterr().out
    rows = {e["check"]: e for e in map(json.loads, out.splitlines())}
    assert rows["cache"] == {"event": "check", "check": "cache", "ok": True,
                             "essential": False, "detail": "2.5 MB of 20 GB"}
    assert str(home_cache.root) not in out
    main(args)
    assert "✓ cache: 2.5 MB of 20 GB" in capsys.readouterr().out.splitlines()
```

- [ ] **Step 12: Run it; watch it fail.** `uv run pytest tests/test_cache.py -q`. Expected:
  `E           argparse.ArgumentError: argument COMMAND: invalid choice: 'cache' (choose from
  run, detect, translate, import, write, models, doctor, config)` (twice), `E       KeyError:
  'cache'`, and `3 failed, 14 passed`.
- [ ] **Step 13: Write the code.** `src/vid2sub/commands/cache.py`:

```python
"""`vid2sub cache clear`: empty the cache of playback audio and preview copies (spec §8.9, §18.1).

Everything in the cache can be made again, so clearing it asks nothing. Only vid2sub's own entry
folders are removed (`cache.Cache.clear`). The output gives the bytes freed and never the
cache's path, in `--json` or not (spec §6.8).
"""

from __future__ import annotations

import argparse

from vid2sub import cache as caching
from vid2sub import exitcodes
from vid2sub.commands._common import Output


def add_parser(sub) -> None:
    p = sub.add_parser("cache", help="manage the cache of playback audio and preview copies")
    actions = p.add_subparsers(dest="action", metavar="ACTION", required=True,
                               parser_class=type(p))
    clear = actions.add_parser("clear", help="remove everything in the cache")
    clear.add_argument("--json", action="store_true",
                       help="JSON Lines events for scripts (never paths)")
    clear.set_defaults(handler=_clear)


def _clear(args: argparse.Namespace) -> int:
    out = Output(args.json)
    freed = caching.Cache(caching.default_root(), max_bytes=0).clear()
    out.event("cache_cleared", bytes=freed)
    out.say(f"cleared {freed / 1_000_000:.1f} MB from the cache")
    return exitcodes.OK
```

  In `src/vid2sub/cli.py`, replace

```python
    "run", "detect", "translate", "import_", "write", "models", "doctor", "config",
```

  with

```python
    "run", "detect", "translate", "import_", "write", "models", "doctor", "config", "cache",
```

  In `src/vid2sub/commands/doctor.py`, replace the docstring's last line

```python
review: a passing Python printed "needs Python 3.12 or later").
```

  with

```python
review: a passing Python printed "needs Python 3.12 or later"). The cache's size is shown
against its cap, never its path (spec §18.1, §6.8).
```

  add `from vid2sub import cache as caching` below `from vid2sub import __version__, exitcodes`;
  in `checks`, insert `out.append(_cache(config))` between the `vid2sub.toml` check's
  `out.append(...)` and `out += _endpoints(config, environ, offline)`; and add this function
  directly above `def _endpoints(`:

```python
def _cache(config: Config) -> Check:
    used = caching.from_config(config).size()
    return Check("cache", True, f"{used / 1_000_000:.1f} MB of {config.defaults.cache_max_gb:g} GB",
                 essential=False)
```

- [ ] **Step 14: Run the checks; they pass.** `uv run pytest tests/test_cache.py
  tests/test_doctor_config.py tests/test_cli_scaffold.py -q` first (`27 passed`), then
  `make check`. Expected: `521 passed, 2 skipped, 4 deselected` twice, `All checks passed!` and
  `no leaks found`.
- [ ] **Step 15: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(cli): 🤖 vid2sub cache clear empties the cache, and vid2sub doctor shows the cache's size against its cap

`vid2sub cache clear [--json]` (spec §18.1, S46) removes every cache entry
through Cache.clear and reports the bytes freed: one JSON line,
{"event": "cache_cleared", "bytes": N}, or "cleared N MB from the cache";
never the cache's path (spec §6.8). Registered in cli.COMMAND_MODULES.
`vid2sub doctor` gains a non-essential "cache" check, "<used> MB of <cap>
GB", in its human and --json output (spec §18.1).

The new tests failed first with: argparse.ArgumentError: argument
COMMAND: invalid choice: 'cache', and KeyError: 'cache' for doctor's rows.

Docs read: none beyond the code (the commands follow config.py's
subcommand pattern and _common.Output).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 3
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/commands/cache.py src/vid2sub/cli.py src/vid2sub/commands/doctor.py
  tests/test_cache.py`, `git commit -F .git/COMMIT_MSG`, then `git log -1 --format='%(trailers)'`
  shows `Plan:`.

- [ ] **Step 16: Review, look forward, close.** The Tier 2 review from `$(cat .git/TASK_BASE)`
  (`AGENTS.md`, *Reviews*); the forward review over Tasks 5, 10, 11 and 23 (Task 5's
  `LocalBackend` takes a `Cache` and its `Episode.audio_index` is the `a:N` index this task's
  `playback_audio` takes; Task 10 serves the `.m4a` through a media token; Task 11's `serve`
  builds the cache with `cache.from_config(config)`); the docs this task made untrue (none
  expected; the README's *Use* block doesn't list `vid2sub cache clear` yet: a missing doc, for
  Task 22). Then the close, its own commit, holding this plan with this task's boxes ticked and
  **Now** set to `Task 4: The job queue, open.`, and the spec's scenario row S46 set to `built`
  (S43 stays `planned`: its Playwright and exit-test proof are Tasks 10, 14 and 23). The
  message, in `.git/CLOSE_MSG`:

```text
docs(plan): 🤖 close Task 3: The cache and the playback audio

Drift: none
Rulings: none
Phase-end: none
Forward: none
Tier: 2
Rounds: none
Findings: none

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 3
Co-Authored-By: <the model's own line>
```

  `git add docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md
  docs/superpowers/specs/2026-10-14-vid2sub-design.md`, `git commit -F .git/CLOSE_MSG`.

***

### Task 4: The job queue

**Tier:** 2 · **Scenarios:** S36

**Files:**
- Create: `src/vid2sub/jobs.py`
- Modify: `src/vid2sub/pipeline.py` (`RunContext.cancelled`, `Cancelled`, the check before every
  model call)
- Test: `tests/test_jobs.py`, `tests/test_pipeline.py` (cancellation)

**Interfaces:**
- Consumes: `pipeline.run_one(source, ctx) -> InputResult`, `pipeline.Event`,
  `pipeline.InputResult`.
- Produces:
  - `pipeline.Cancelled(Exception)`; `RunContext.cancelled: Callable[[], bool]` (default: never;
    a field with a default, so every existing constructor still works). The check is at the top
    of `pipeline._retrying`, which every transcription, translation and detection call goes
    through, so a cancel stops before the next chunk, the next translation batch or the next
    retry of a dropped connection; `run_one`, `translate_one` and `detect_one` re-raise it, as
    they do `Paused` and `StopRun`.
  - `jobs.JobState = Literal["queued", "running", "done", "failed", "cancelled"]`
  - `@dataclass(frozen=True) class JobView: id: str; input: str; state: JobState;
    stage: str | None = None; progress: tuple[int, int] | None = None;
    result: InputResult | None = None; hint: str | None = None`
  - `Runner = Callable[[str, Event, Callable[[], bool]], InputResult]` (the source, the events
    callback, the cancelled check); Task 19 wraps `run_one` as
    `lambda source, events, cancelled: run_one(source, dataclasses.replace(ctx, events=events,
    cancelled=cancelled))`.
  - `class Queue: __init__(self, runner: Runner)`; `submit(self, inputs: Sequence[str])
    -> list[str]` (`RuntimeError` once closed); `cancel(self, job_id: str) -> bool` (True for a
    queued job, now cancelled, or the running one, now asked to stop); `jobs(self) ->
    list[JobView]` (in submission order); `on_change(self, fn: Callable[[], None]) -> None`;
    `close(self, timeout: float = 5.0) -> None`. One worker thread runs one job at a time (spec
    §17.1). Events: `"stage"` sets `stage` and clears `progress`; `"chunk"` and `"batch"` set
    `progress = (index, of)` and the stage `"transcribe"` or `"translate"`; others are ignored.
    A result with status `"failed"` makes the job `failed`; any other makes it `done`; `hint` is
    the result's hint (or None). A runner exception makes it `failed` with `hint=None`, its kind
    logged to `vid2sub.jobs`. Listeners run on the thread that made the change (the worker, or
    the caller of `submit`, `cancel` or `close`); one that raises is logged by kind and ignored.

- [ ] **Step 0: Record the base:** `git rev-parse HEAD > .git/TASK_BASE`.
- [ ] **Step 1: Write the failing test.** In `tests/test_pipeline.py`, add `import functools`
  above `import json`, then append at the end of the file, after two blank lines:

```python
# Phase 2, Task 4: Cancel stops between chunks and translation batches (plan Decision 7, S36)


class ShortChunks(FakeEngine):
    max_chunk_s = 5.0


def test_a_run_is_never_cancelled_unless_asked():
    assert make_ctx(FakeEngine()).cancelled() is False


def test_a_cancel_stops_before_the_next_chunk_and_records_nothing(clip):
    engine = ShortChunks()
    ctx = make_ctx(engine)
    ctx.cancelled = lambda: len(engine.calls) >= 1
    with pytest.raises(pipeline.Cancelled):
        pipeline.run_one(str(clip), ctx)
    assert [c[0] for c in engine.calls] == ["transcribe"]
    assert store.load(clip)[0] is None


def test_a_cancel_stops_translation_before_its_next_batch(clip, monkeypatch):
    asked: list[list[str]] = []
    monkeypatch.setattr(pipeline, "make_ask", recording_make_ask(asked))
    monkeypatch.setattr(pipeline, "translate_cues",
                        functools.partial(pipeline.translate_cues, batch_size=1))
    ctx = make_ctx(FakeEngine())
    ctx.cancelled = lambda: bool(asked)
    with pytest.raises(pipeline.Cancelled):
        pipeline.run_one(str(clip), ctx)
    assert len(asked) == 1
    side, _ = store.load(clip)
    assert isinstance(side.head("ja"), HeadRecord) and side.head("en") is None


def test_a_cancel_stops_a_run_that_is_waiting_for_its_server(clip):
    engine = FakeEngine(fail=[EngineError("connection", "down")] * 100)
    ctx = make_ctx(engine)
    ctx.cancelled = lambda: bool(ctx.sleeps)
    with pytest.raises(pipeline.Cancelled):
        pipeline.run_one(str(clip), ctx)
    assert len(ctx.sleeps) == 1 and len(engine.calls) == 1
```

- [ ] **Step 2: Run it; watch it fail.** `uv run pytest tests/test_pipeline.py -q -k cancel`.
  Expected: `E       AttributeError: 'RunContext' object has no attribute 'cancelled'`, then
  `E       AttributeError: module 'vid2sub.pipeline' has no attribute 'Cancelled'` three times,
  and `4 failed, 51 deselected`.
- [ ] **Step 3: Write the code,** in `src/vid2sub/pipeline.py`. In the module docstring, replace

```python
cached for the life of the process. Any other error fails only this input, with the fix; an
unexpected one is named only by its type, and VID2SUB_DEBUG=1 prints its traceback (spec §17.3).
```

  with

```python
cached for the life of the process. A cancelled job (`RunContext.cancelled`, which the web
app's queue sets) raises Cancelled before its next model call, so Cancel stops between chunks,
translation batches and retries (Phase 2 plan, Decision 7). Any other error fails only this
input, with the fix; an unexpected one is named only by its type, and VID2SUB_DEBUG=1 prints its
traceback (spec §17.3).
```

  Below `class StopRun(RuntimeError):` and its `pass`, add:

```python


class Cancelled(Exception):
    """The job was cancelled; raised before a model call, never mid-call (plan Decision 7)."""
```

  Below `def _no_event(...)` and its `return None`, add:

```python


def _never() -> bool:
    return False
```

  In `class RunContext`, below `candidates: list | None = None`, add:

```python
    cancelled: Callable[[], bool] = _never
```

  In `_guarded` and again in `detect_one`, replace `except (Paused, StopRun):` with
  `except (Paused, StopRun, Cancelled):` (both are followed by `raise`). In `_retrying`, replace

```python
    raised as it came. Transcription and translation both go through here, so a Spark drop in
    either pauses the run rather than failing the input (controller ruling 1).
    """
    waited, server_tries = 0.0, 0
    while True:
        try:
```

  with

```python
    raised as it came. Transcription and translation both go through here, so a Spark drop in
    either pauses the run rather than failing the input (controller ruling 1), and a cancelled
    job stops before each call: the next chunk, the next translation batch or the next retry.
    """
    waited, server_tries = 0.0, 0
    while True:
        if ctx.cancelled():
            raise Cancelled()
        try:
```

- [ ] **Step 4: Run the checks; they pass.** `uv run pytest tests/test_pipeline.py -q` first
  (`55 passed`), then the propagation check, then `make check`. **Propagation check:** take
  `Cancelled` out of `_guarded`'s `except (Paused, StopRun, Cancelled):`; `uv run pytest
  tests/test_pipeline.py -q -k cancel` gives `3 failed, 1 passed, 51 deselected` (the cancel
  became a failed result); restore it. `make check`. Expected: `525 passed, 2 skipped, 4
  deselected` twice, `All checks passed!` and `no leaks found`.
- [ ] **Step 5: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(pipeline): 🤖 a cancelled run stops before its next chunk, translation batch or retry

RunContext gains `cancelled: Callable[[], bool]`, never by default, so
every existing caller is unchanged; pipeline.Cancelled is raised before
each model call in _retrying, which every transcription, translation and
detection call goes through, so Cancel stops between chunks, translation
batches and retries while a running ffmpeg step finishes first (the plan's
Decision 7, spec §17.3, S36). run_one and translate_one (through _guarded)
and detect_one re-raise Cancelled as they do Paused and StopRun, so the
queue sees it instead of a failed result; the scratch folder still goes,
and nothing is appended for a transcript that didn't finish.

The new tests failed first with: AttributeError: module 'vid2sub.pipeline'
has no attribute 'Cancelled'. With Cancelled left out of _guarded's
re-raise, the three cancel tests fail (it became a failed result).

Docs read: none beyond the code (pipeline's Paused/StopRun handling,
commands/run.py's KeyboardInterrupt handling, translate.run's batch loop,
whose ValueError retry doesn't catch Cancelled).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 4
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/pipeline.py tests/test_pipeline.py`, `git commit -F .git/COMMIT_MSG`,
  then `git log -1 --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 6: Write the failing test,** `tests/test_jobs.py`:

```python
import dataclasses
import logging
import threading
import time

import pytest

from vid2sub import jobs
from vid2sub.pipeline import Cancelled, InputResult


def until(check, timeout=5.0):
    end = time.monotonic() + timeout
    while not check():
        if time.monotonic() > end:
            raise AssertionError("timed out waiting")
        time.sleep(0.005)


class Runner:
    """A fake runner: each job reports stages and progress, then waits for the test to let it
    finish, checking for a cancel while it waits."""

    def __init__(self, results=None):
        self.results = results or {}
        self.started: list[str] = []
        self.running = 0
        self.most_at_once = 0
        self.gates: dict[str, threading.Event] = {}
        self.lock = threading.Lock()

    def gate(self, source: str) -> threading.Event:
        with self.lock:
            return self.gates.setdefault(source, threading.Event())

    def __call__(self, source, event, cancelled):
        with self.lock:
            self.started.append(source)
            self.running += 1
            self.most_at_once = max(self.most_at_once, self.running)
        try:
            event("stage", {"stage": "decode"})
            event("chunk", {"index": 1, "of": 3})
            event("chunk", {"index": 2, "of": 3})
            event("waiting", {"kind": "connection", "seconds": 5})
            while not self.gate(source).wait(0.005):
                if cancelled():
                    raise Cancelled()
            outcome = self.results.get(source, InputResult(input=source, status="done"))
            if isinstance(outcome, BaseException):
                raise outcome
            return outcome
        finally:
            with self.lock:
                self.running -= 1


@pytest.fixture
def runner():
    return Runner()


@pytest.fixture
def queue(runner):
    q = jobs.Queue(runner)
    yield q
    for gate in list(runner.gates.values()):
        gate.set()
    q.close()


def view(queue, job_id) -> jobs.JobView:
    return next(j for j in queue.jobs() if j.id == job_id)


def state(queue, job_id) -> str:
    return view(queue, job_id).state


def test_jobs_run_one_at_a_time_in_the_order_they_were_submitted(queue, runner):
    ids = queue.submit(["a.mkv", "b.mkv", "c.mkv"])
    assert len(set(ids)) == 3
    assert [j.input for j in queue.jobs()] == ["a.mkv", "b.mkv", "c.mkv"]
    for source in ("a.mkv", "b.mkv", "c.mkv"):
        runner.gate(source).set()
    until(lambda: all(j.state == "done" for j in queue.jobs()))
    assert runner.started == ["a.mkv", "b.mkv", "c.mkv"] and runner.most_at_once == 1


def test_a_running_job_shows_its_stage_and_progress(queue, runner):
    (job,) = queue.submit(["a.mkv"])
    until(lambda: view(queue, job).progress == (2, 3))
    assert view(queue, job).state == "running"
    assert view(queue, job).stage == "transcribe"
    runner.gate("a.mkv").set()
    until(lambda: state(queue, job) == "done")
    assert view(queue, job).result == InputResult(input="a.mkv", status="done")


def test_a_new_stage_clears_the_progress_and_a_batch_means_translating():
    seen = []

    def run(source, event, cancelled):
        event("chunk", {"index": 3, "of": 3})
        event("stage", {"stage": "write"})
        seen.append(q.jobs()[0])
        event("batch", {"index": 1, "of": 2})
        seen.append(q.jobs()[0])
        return InputResult(input=source, status="done")

    q = jobs.Queue(run)
    q.submit(["a.mkv"])
    until(lambda: q.jobs()[0].state == "done")
    q.close()
    assert [(v.stage, v.progress) for v in seen] == [("write", None), ("translate", (1, 2))]


def test_cancelling_a_queued_job_takes_it_out_of_the_queue(queue, runner):
    first, second = queue.submit(["a.mkv", "b.mkv"])
    until(lambda: state(queue, first) == "running")
    assert queue.cancel(second) is True
    assert state(queue, second) == "cancelled"
    runner.gate("a.mkv").set()
    until(lambda: state(queue, first) == "done")
    assert runner.started == ["a.mkv"]


def test_cancelling_the_running_job_stops_it_and_the_next_one_starts(queue, runner):
    first, second = queue.submit(["a.mkv", "b.mkv"])
    until(lambda: state(queue, first) == "running")
    assert queue.cancel(first) is True
    until(lambda: state(queue, first) == "cancelled")
    until(lambda: state(queue, second) == "running")
    runner.gate("b.mkv").set()
    until(lambda: state(queue, second) == "done")


def test_a_finished_or_unknown_job_cannot_be_cancelled(queue, runner):
    (job,) = queue.submit(["a.mkv"])
    runner.gate("a.mkv").set()
    until(lambda: state(queue, job) == "done")
    assert queue.cancel(job) is False
    assert queue.cancel("nope") is False
    assert state(queue, job) == "done"


def test_a_failed_input_fails_its_job_with_the_hint_that_names_the_fix():
    failed = InputResult(input="a.mkv", status="failed", reason="refused",
                         hint="is `make tunnel` running?")
    runner = Runner({"a.mkv": failed})
    q = jobs.Queue(runner)
    (job,) = q.submit(["a.mkv"])
    runner.gate("a.mkv").set()
    until(lambda: state(q, job) == "failed")
    assert view(q, job).hint == "is `make tunnel` running?" and view(q, job).result is failed
    q.close()


def test_a_runner_that_raises_fails_only_its_job_and_logs_only_the_error_kind(caplog):
    runner = Runner({"/films/Secret Show.mkv": RuntimeError("/films/Secret Show.mkv")})
    q = jobs.Queue(runner)
    caplog.set_level(logging.DEBUG, logger="vid2sub.jobs")
    bad, good = q.submit(["/films/Secret Show.mkv", "b.mkv"])
    runner.gate("/films/Secret Show.mkv").set()
    runner.gate("b.mkv").set()
    until(lambda: state(q, good) == "done")
    assert state(q, bad) == "failed" and view(q, bad).hint is None
    assert "RuntimeError" in caplog.text and "Secret" not in caplog.text
    q.close()


def test_listeners_hear_every_change_and_one_that_raises_is_ignored(queue, runner, caplog):
    heard = []

    def broken():
        raise ValueError("a listener's bug")

    def listener():
        (j,) = queue.jobs()
        heard.append((threading.current_thread().name, (j.state, j.stage, j.progress)))

    queue.on_change(broken)
    queue.on_change(listener)
    queue.submit(["a.mkv"])
    runner.gate("a.mkv").set()
    until(lambda: len(heard) == 6)
    assert [t for t, _ in heard].count("vid2sub-jobs") == 5  # and one from submit, here
    assert [v for t, v in heard if t == "vid2sub-jobs"] == [
        ("running", None, None), ("running", "decode", None),
        ("running", "transcribe", (1, 3)), ("running", "transcribe", (2, 3)),
        ("done", "transcribe", (2, 3))]
    assert "ValueError" in caplog.text and "a listener's bug" not in caplog.text


def test_jobs_are_frozen_snapshots(queue, runner):
    (job,) = queue.submit(["a.mkv"])
    before = view(queue, job)
    with pytest.raises(dataclasses.FrozenInstanceError):
        before.state = "done"  # type: ignore[misc]
    runner.gate("a.mkv").set()
    until(lambda: state(queue, job) == "done")
    assert before.state in ("queued", "running")


def test_close_cancels_the_running_and_waiting_jobs_and_stops_the_worker(runner):
    q = jobs.Queue(runner)
    first, _ = q.submit(["a.mkv", "b.mkv"])
    until(lambda: state(q, first) == "running")
    q.close()
    assert [j.state for j in q.jobs()] == ["cancelled", "cancelled"]
    assert not q._worker.is_alive()
    with pytest.raises(RuntimeError, match="closed"):
        q.submit(["c.mkv"])
```

- [ ] **Step 7: Run it; watch it fail.** `uv run pytest tests/test_jobs.py -q`. Expected:
  `E   ImportError: cannot import name 'jobs' from 'vid2sub'` and `1 error`.
- [ ] **Step 8: Write the code,** `src/vid2sub/jobs.py`:

```python
"""The job queue: one worker thread runs submitted inputs one at a time (spec §17.1, S36).

Jobs live in the engine's memory, owned by the engine rather than a browser tab, so closing a tab
cancels nothing and reopening shows the progress; when the engine exits the list is gone, and
finished results are already on disk (Dan, 2026-10-14). One worker runs one job at a time,
because the Spark's whisper serves one request at a time anyway. Cancel takes a queued job out of
the queue, or asks the running one to stop at its next check, between chunks or translation
batches (`pipeline.Cancelled`; the Phase 2 plan's Decision 7). Listeners are called after every
change of state, stage or progress, on the thread that made it (the worker, or the caller of
`submit`, `cancel` or `close`); one that raises is logged and the queue carries on. The log names
jobs by id and errors by kind, never an input, a title or a path (spec §6.8).
"""

from __future__ import annotations

import dataclasses
import logging
import secrets
import threading
from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from vid2sub.pipeline import Cancelled, Event, InputResult

log = logging.getLogger(__name__)

JobState = Literal["queued", "running", "done", "failed", "cancelled"]
Runner = Callable[[str, Event, Callable[[], bool]], InputResult]
_IMPLIED_STAGE = {"chunk": "transcribe", "batch": "translate"}


@dataclass(frozen=True)
class JobView:
    id: str
    input: str
    state: JobState
    stage: str | None = None
    progress: tuple[int, int] | None = None  # (index, of): a chunk or a translation batch
    result: InputResult | None = None
    hint: str | None = None


class Queue:
    def __init__(self, runner: Runner):
        self._runner = runner
        self._lock = threading.Condition()
        self._jobs: dict[str, JobView] = {}  # in the order they were submitted
        self._waiting: deque[str] = deque()
        self._running: str | None = None
        self._stop = threading.Event()  # set: the running job should stop
        self._listeners: list[Callable[[], None]] = []
        self._closed = False
        self._worker = threading.Thread(target=self._work, name="vid2sub-jobs", daemon=True)
        self._worker.start()

    def submit(self, inputs: Sequence[str]) -> list[str]:
        with self._lock:
            if self._closed:
                raise RuntimeError("the job queue is closed")
            ids = []
            for source in inputs:
                job_id = self._new_id()
                self._jobs[job_id] = JobView(job_id, source, "queued")
                self._waiting.append(job_id)
                ids.append(job_id)
            self._lock.notify()
        self._changed()
        return ids

    def cancel(self, job_id: str) -> bool:
        """True if the job was queued (now cancelled) or running (now asked to stop)."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.state not in ("queued", "running"):
                return False
            if job.state == "running":
                self._stop.set()
                return True
            self._waiting.remove(job_id)
            self._set(job_id, state="cancelled")
        self._changed()
        return True

    def jobs(self) -> list[JobView]:
        with self._lock:
            return list(self._jobs.values())

    def on_change(self, fn: Callable[[], None]) -> None:
        with self._lock:
            self._listeners.append(fn)

    def close(self, timeout: float = 5.0) -> None:
        """Cancels every queued job and the running one, then waits up to `timeout` seconds
        for the worker to stop."""
        with self._lock:
            self._closed = True
            while self._waiting:
                self._set(self._waiting.popleft(), state="cancelled")
            if self._running is not None:
                self._stop.set()
            self._lock.notify()
        self._changed()
        self._worker.join(timeout)

    def _new_id(self) -> str:
        while True:
            job_id = "j" + secrets.token_hex(4)
            if job_id not in self._jobs:
                return job_id

    def _set(self, job_id: str, **changes: Any) -> None:
        """Called with the lock held."""
        self._jobs[job_id] = dataclasses.replace(self._jobs[job_id], **changes)

    def _changed(self) -> None:
        with self._lock:
            listeners = list(self._listeners)
        for fn in listeners:
            try:
                fn()
            except Exception as err:  # noqa: BLE001 - a listener's bug never stops the queue
                log.error("a job listener raised %s", type(err).__name__)

    def _work(self) -> None:
        while True:
            with self._lock:
                while not self._waiting and not self._closed:
                    self._lock.wait()
                if not self._waiting:
                    return
                job_id = self._waiting.popleft()
                self._running = job_id
                self._stop.clear()
                self._set(job_id, state="running")
                source = self._jobs[job_id].input
            self._changed()
            final = self._run(job_id, source)
            with self._lock:
                self._set(job_id, **final)
                self._running = None
            self._changed()

    def _run(self, job_id: str, source: str) -> dict[str, Any]:
        def event(kind: str, fields: dict[str, Any]) -> None:
            if kind == "stage":
                changes = {"stage": fields.get("stage"), "progress": None}
            elif kind in _IMPLIED_STAGE:
                changes = {"stage": _IMPLIED_STAGE[kind],
                           "progress": (fields.get("index"), fields.get("of"))}
            else:
                return
            with self._lock:
                self._set(job_id, **changes)
            self._changed()

        try:
            result = self._runner(source, event, self._stop.is_set)
        except Cancelled:
            log.info("job %s cancelled", job_id)
            return {"state": "cancelled"}
        except Exception as err:  # noqa: BLE001 - a bug fails one job, not the queue (§17.3)
            log.error("job %s failed: %s", job_id, type(err).__name__)
            return {"state": "failed", "hint": None}
        if result.status == "failed":
            log.info("job %s failed: %s", job_id, result.kind or "failed")
        state = "failed" if result.status == "failed" else "done"
        return {"state": state, "result": result, "hint": result.hint or None}
```

- [ ] **Step 9: Run the checks; they pass.** `uv run pytest tests/test_jobs.py -q` first
  (`11 passed`; run it ten times, `for i in 1 2 3 4 5 6 7 8 9 10; do uv run pytest
  tests/test_jobs.py -q | tail -1; done`, and each says `11 passed`: these tests use threads),
  then the log check, then `make check`. **Log check** (spec §6.8): in `Queue._run`, change
  `log.error("job %s failed: %s", job_id, type(err).__name__)` to log `err` instead of
  `type(err).__name__`; `uv run pytest tests/test_jobs.py -q` gives `FAILED
  tests/test_jobs.py::test_a_runner_that_raises_fails_only_its_job_and_logs_only_the_error_kind`;
  restore it. `make check`. Expected: `536 passed, 2 skipped, 4 deselected` twice, `All checks
  passed!` and `no leaks found`.
- [ ] **Step 10: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(jobs): 🤖 the job queue runs inputs one at a time on a worker thread, with progress and cancel

vid2sub.jobs (spec §17.1, S36): Queue(runner) starts one daemon worker
that runs submitted inputs first in, first out, through a Runner(source,
events, cancelled). Jobs go queued → running → done | failed | cancelled;
a "stage" event sets the stage and clears the progress, a "chunk" or
"batch" event sets the progress (index, of) and implies the transcribe
or translate stage. Cancel takes a queued job out of the queue, or sets
the flag the running job's cancelled() reads, so pipeline.Cancelled ends
it as cancelled. A failed InputResult fails the job with its hint; an
exception fails it with no hint, and only its kind is logged. jobs()
returns frozen JobView snapshots; on_change listeners hear every change,
and one that raises is logged by kind and ignored. close() cancels the
waiting and running jobs and joins the worker.

The new tests failed first with: ImportError: cannot import name 'jobs'
from 'vid2sub'. With the runner's exception logged as its text instead
of its kind, test_a_runner_that_raises_fails_only_its_job_and_logs_only_
the_error_kind fails (the path reached the log). The queue tests passed
ten runs in a row.

Docs read: none beyond the code (Python's threading.Condition and Event,
as the standard library documents them).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 4
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/jobs.py tests/test_jobs.py`, `git commit -F .git/COMMIT_MSG`, then
  `git log -1 --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 11: Review, look forward, close.** The Tier 2 review from `$(cat .git/TASK_BASE)`
  (`AGENTS.md`, *Reviews*); the forward review over Tasks 11 and 19 (Task 11's `Runtime` holds
  the `Queue` and closes it on shutdown; Task 19 wraps `run_one` as the `Runner`, turns
  `on_change` into the `jobs` output, and must hop to the Shiny session's loop itself, since
  listeners run on the worker thread); the docs this task made untrue (none expected). Then the
  close, its own commit, holding this plan with this task's boxes ticked and **Now** set to
  `Task 5: The editor backend: opening an episode, open.`; S36 stays `planned` (its proof is
  Task 19's Playwright test). The message, in `.git/CLOSE_MSG`:

```text
docs(plan): 🤖 close Task 4: The job queue

Drift: none
Rulings: none
Phase-end: none
Forward: none
Tier: 2
Rounds: none
Findings: none

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 4
Co-Authored-By: <the model's own line>
```

  `git add docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md`, `git commit -F
  .git/CLOSE_MSG`.

***

### Task 5: The editor backend: opening an episode

**Tier:** 2 · **Scenarios:** S27, S31

**Files:**
- Create: `src/vid2sub/web/__init__.py`, `src/vid2sub/web/backend.py`, `src/vid2sub/web/views.py`
- Test: `tests/test_backend_open.py`, `tests/test_views.py`

**Interfaces:**
- Consumes: `store.load`, `store.check_external`, `store.current_cues`, `store.source_track`,
  `store.header_for`; `subs.sidecar.Sidecar.head`, `Conflict`; `subs.rendition.transcript_from_body`;
  `subs.lint.lint`, `subs.rules.rules_for`; `subs.translate_shape.stale_ids`, `untranslated`;
  `subs.edit.Tracks`; `media.probe`; `cache.Cache`.
- Produces:
  - `@dataclass(frozen=True) class Capabilities: engine: Literal["local", "browser"];
    generate: bool; save: Literal["disk", "download"]; path_input: bool`
  - `class OpenError(Exception)` (a reason fit to show: no sidecar yet, not a video, refused)
  - `@dataclass class Episode: id: str; video: Path; header: Header; source_key: str;
    tracks: Tracks; heads: dict[str, str]; conflicts: dict[str, tuple[str, ...]];
    words: tuple[Word, ...]; notes: list[str]; playable_audio: bool; audio_index: int;
    undo: list[Tracks]; redo: list[Tracks]; taken: set[str]; glossary_adds: dict[str, str]`
  - `class LocalBackend: __init__(self, config: Config, tools: Tools, keys: KeyRing, cache: Cache)`;
    `capabilities(self) -> Capabilities`; `open(self, path: str) -> Episode`;
    `close(self, episode_id: str) -> None`
  - `views.episode_view(ep: Episode, *, video_url: str | None, audio_url: str | None) -> dict`
    (JSON: `video`, `tracks`, `rows`, `words`, `dirty`, `notes`, `conflicts`)

<!-- steps: written in the next pass -->

***

### Task 6: The editor backend: edits and Save

**Tier:** 1 · **Scenarios:** S28, S29, S32

**Files:**
- Modify: `src/vid2sub/web/backend.py`
- Create: `src/vid2sub/web/ops.py`
- Test: `tests/test_backend_save.py`, `tests/test_ops.py`

**Interfaces:**
- Consumes: Task 2's `subs.edit`; Task 5's `Episode`, `LocalBackend`; `store.append`,
  `store.project`, `ForeignFile`, `EditedOnDisk`; `subs.sidecar.make_rendition`, `HeadRecord`;
  `subs.rendition.cues_body`; `subs.glossary`.
- Produces:
  - `ops.EditOp`: a pydantic union discriminated on `op` (`extra="forbid"`): `set_text`,
    `set_translation_text`, `set_times`, `nudge`, `split`, `merge_next`, `insert`, `delete`,
    `detach`, `replace_all`, `glossary_add`; `ops.parse_op(data: object) -> EditOp` (raises
    `ops.BadOp` naming the field, never echoing the value)
  - `LocalBackend.apply(self, ep: Episode, op: EditOp) -> Episode` (pushes undo, clears redo);
    `undo(self, ep) -> Episode`; `redo(self, ep) -> Episode`
  - `@dataclass(frozen=True) class SaveResult: written: tuple[str, ...]; foreign: tuple[str, ...];
    conflicts: tuple[str, ...]; notes: tuple[str, ...]`
  - `LocalBackend.save(self, ep: Episode, *, formats: Sequence[Literal["srt", "ass"]])
    -> tuple[Episode, SaveResult]`
  - `LocalBackend.resolve(self, ep: Episode, track: str, rendition: str) -> Episode`

<!-- steps: written in the next pass -->

***

### Task 7: The editor backend: retranslate

**Tier:** 2 · **Scenarios:** S30

**Files:**
- Modify: `src/vid2sub/web/backend.py`
- Test: `tests/test_backend_retranslate.py`

**Interfaces:**
- Consumes: `translate.run.translate_cues`, `make_ask`; `catalog` routing; Task 6's `apply`.
- Produces: `LocalBackend.retranslate(self, ep: Episode, track: str, *,
  ids: Sequence[str] | None, model: str | None = None, allow_cloud: bool = False,
  on_batch: Callable[[int, int], None] | None = None) -> Episode` (`ids=None` means every stale
  or untranslated cue; edited cues are never replaced; undoable)

<!-- steps: written in the next pass -->

***

### Task 8: The web dependencies, the guards and the CSP

**Tier:** 1 · **Scenarios:** S24, S25, S26

**Files:**
- Modify: `pyproject.toml`, `uv.lock` (fastapi, uvicorn, shiny, shinyreact; dev:
  pytest-playwright)
- Create: `src/vid2sub/web/guards.py` (HostGuard and WriteGuard copied from
  `recordings@8deb039:packages/ui/src/recordings_ui/hosts.py`, with its header)
- Test: `tests/test_web_guards.py` (copied from `recordings`' `test_hosts.py` and
  `test_writeguard.py`, plus the CSP and `/media/` headers)
- Uses: `src/vid2sub/web/__init__.py`, which Task 5 created (this task doesn't touch it)

**Interfaces:**
- Produces: `guards.LOCAL_HOSTS`; `class HostGuard: __init__(self, app: ASGIApp,
  allowed: frozenset[str])`; `class WriteGuard: __init__(self, app: ASGIApp,
  allowed: frozenset[str])`; `guards.CSP: str`; `guards.MEDIA_HEADERS: dict[str, str]` (lower-case
  names: `content-security-policy: sandbox`, `x-content-type-options: nosniff`,
  `cache-control: no-store`).
- Behaviour later tasks rely on: WriteGuard puts the security headers on every HTTP response,
  replacing any header of the same name the app set: `CSP`, `X-Frame-Options: DENY`,
  `Cross-Origin-Resource-Policy`, `Cross-Origin-Opener-Policy` and `Referrer-Policy` (all
  `same-origin`) everywhere, with `MEDIA_HEADERS` instead of `CSP` for a path starting `/media/`.
  HostGuard's own 400 carries them too. Task 12 may need a `style-src` once a real browser shows
  what Shiny and shinyreact need (spec §29): that is a one-line change to `CSP` and to
  `SPEC_CSP` in the test, and a spec change, so Dan's (the fifth stop).

- [ ] **Step 0: Record the base:** `git rev-parse HEAD > .git/TASK_BASE`, and check Task 5's
  package marker is there: `test -f src/vid2sub/web/__init__.py && echo ok` prints `ok`.

#### Round 8a: the packages

- [ ] **Step 1: Add the packages to `pyproject.toml`.** Replace the end of `dependencies`:

```toml
    "yt-dlp[default]>=2026.1.1",
]
```

  with:

```toml
    "yt-dlp[default]>=2026.1.1",
    # The local web app (spec §19.1). Pinned exactly, as recordings pins them, and upgraded
    # together on purpose (spec §4.3): shinyreact 0.1.0 needs shiny>=1.8.0.
    "fastapi==0.142.3",
    "uvicorn==0.54.0",
    "shiny==1.8.0",
    "shinyreact==0.1.0",
]
```

  and replace the dev group's line:

```toml
dev = ["pytest>=8.3", "hypothesis>=6.100", "jsonschema>=4.23", "ruff>=0.8"]
```

  with:

```toml
dev = [
    "pytest>=8.3",
    "hypothesis>=6.100",
    "jsonschema>=4.23",
    "ruff>=0.8",
    "pytest-playwright==0.10.0",  # the editor's browser tests (spec §22.7), as recordings pins it
]
```

  Then `uv lock`. Expected, among its lines: `Added fastapi v0.142.3`, `Added shiny v1.8.0`,
  `Added shinyreact v0.1.0`, `Added starlette v1.9.0`, `Added uvicorn v0.54.0`,
  `Added pytest-playwright v0.10.0`, `Added playwright v1.64.1`. (Starlette comes in through
  fastapi, unpinned: if it resolves to a version other than 1.9.0, read its release notes for
  `FileResponse`, `set_cookie` and routing before going on, and say so in the commit.) Then
  `make setup`, and `uv run python -c "from importlib.metadata import version as v; print(*(f'{p}
  {v(p)}' for p in ('fastapi', 'uvicorn', 'shiny', 'shinyreact', 'starlette',
  'pytest-playwright')))"`. Expected: `fastapi 0.142.3 uvicorn 0.54.0 shiny 1.8.0 shinyreact
  0.1.0 starlette 1.9.0 pytest-playwright 0.10.0`. All five pins declare requires-python `>=3.10`
  on PyPI, and `uv.lock` resolves both of its markers (`< 3.13` and `>= 3.13`), so Python 3.12
  is covered.

- [ ] **Step 2: Run the checks; they pass.** `make check`. Expected: the suite's line, twice,
  `N passed, 2 skipped, 4 deselected` with nothing failed (N was 465 when this listing was built,
  before Tasks 2–7's tests), then `All checks passed!` and `no leaks found`.

- [ ] **Step 3: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
build(deps): 🤖 the web app's packages are pinned exactly, as recordings pins them, and resolve on Python 3.12

fastapi 0.142.3, uvicorn 0.54.0, shiny 1.8.0 and shinyreact 0.1.0 (spec §4.3, §19.1), and
pytest-playwright 0.10.0 in the dev group for the editor's browser tests (spec §22.7). recordings
needs Python 3.14, so its pins were checked for 3.12: PyPI's metadata gives requires-python >=3.10
for all five, shinyreact 0.1.0 needs shiny>=1.8.0, and uv.lock resolves both of its markers
(<3.13 and >=3.13). Starlette resolves to 1.9.0. The suite passes unchanged with them.

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 8
Co-Authored-By: <the model's own line>
```

  `git add pyproject.toml uv.lock`, `git commit -F .git/COMMIT_MSG`, then
  `git log -1 --format='%(trailers)'` shows `Plan:`.

#### Round 8b: the guards

- [ ] **Step 4: Write the failing test,** `tests/test_web_guards.py`:

```python
"""The engine answers only to its own names, refuses websockets and writes from other sites, and
sends the security headers on every response (spec §6.2, §6.3; S24, S25).

The HostGuard and WriteGuard tests are copied from recordings (packages/ui/tests/test_hosts.py
and test_writeguard.py at 8deb039, spec §4.4); the CSP and /media/ header tests are new.
"""

from contextlib import asynccontextmanager

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse, PlainTextResponse, Response
from starlette.routing import Route, WebSocketRoute
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from vid2sub.web.guards import CSP, LOCAL_HOSTS, MEDIA_HEADERS, HostGuard, WriteGuard

# Spec §6.3, verbatim, so loosening guards.CSP fails here too.
SPEC_CSP = (
    "default-src 'self'; script-src 'self'; connect-src 'self'; object-src 'none'; "
    "base-uri 'none'; frame-ancestors 'none'; img-src 'self' data: blob:; media-src 'self' blob:"
)
EVERY_RESPONSE = {
    "cross-origin-resource-policy": "same-origin",
    "cross-origin-opener-policy": "same-origin",
    "x-frame-options": "DENY",
    "referrer-policy": "same-origin",
}
PAGE = {**EVERY_RESPONSE, "content-security-policy": SPEC_CSP}
MEDIA = {
    **EVERY_RESPONSE,
    "content-security-policy": "sandbox",
    "x-content-type-options": "nosniff",
    "cache-control": "no-store",
}
JSON = {"Content-Type": "application/json"}


async def _hello(request):
    return PlainTextResponse("hi")


async def _echo(websocket):
    await websocket.accept()
    await websocket.send_text("hello")
    await websocket.close()


async def _thing(request):
    return JSONResponse({"ok": True})


async def _weak(request):
    # A route that sets weaker headers of its own: the guard's must win, and be sent once.
    return PlainTextResponse(
        "weak",
        headers={"Content-Security-Policy": "script-src *", "X-Frame-Options": "SAMEORIGIN"},
    )


async def _media(request):
    # As Task 10's route answers: its own nosniff, and a CSP that the sandbox must replace.
    return Response(
        b"\x00" * 16,
        media_type="audio/mpeg",
        headers={"Content-Security-Policy": "default-src *", "X-Content-Type-Options": "nosniff"},
    )


def _inner(lifespan=None) -> Starlette:
    return Starlette(
        routes=[
            Route("/", _hello),
            WebSocketRoute("/ws", _echo),
            Route("/api/thing", _thing, methods=["GET", "POST", "DELETE"]),
            Route("/weak", _weak),
            Route("/media/{token}", _media),
            Route("/mediafile", _hello),
        ],
        lifespan=lifespan,
    )


def guarded(allowed=LOCAL_HOSTS, lifespan=None) -> TestClient:
    return TestClient(HostGuard(_inner(lifespan), frozenset(allowed)), base_url="http://localhost")


@pytest.fixture
def client():
    with TestClient(WriteGuard(_inner(), LOCAL_HOSTS), base_url="http://localhost:8000") as c:
        yield c


def _policy(response, names) -> dict:
    return {k: response.headers.get(k) for k in names}


# ---- HostGuard ---------------------------------------------------------------------------


def test_the_unknown_host_answer_carries_the_security_headers_too():
    # "Every response" carries the policy (spec §6.2), the 400 included.
    r = guarded().get("/", headers={"Host": "attacker.example"})
    assert r.status_code == 400
    assert _policy(r, PAGE) == PAGE


@pytest.mark.parametrize(
    "host",
    [
        "attacker.example",
        "attacker.example:8000",
        "localhost.attacker.example",
        "evil-localhost",
        "[::2]:8000",
        "",
    ],
)
def test_an_unknown_host_is_400(host):
    # DNS rebinding: a website's own name pointed at 127.0.0.1 still arrives in Host.
    r = guarded().get("/", headers={"Host": host})
    assert r.status_code == 400 and r.text == "unknown host"


@pytest.mark.parametrize(
    "host",
    [
        "localhost",
        "localhost:8000",
        "127.0.0.1:8000",
        "[::1]:8000",
        "[::1]",
        "LOCALHOST:8000",
        "LocalHost",
    ],
)
def test_allowed_host_variants_pass(host):
    r = guarded().get("/", headers={"Host": host})
    assert r.status_code == 200 and r.text == "hi"


def test_allowed_names_are_compared_lowercased():
    client = guarded(allowed={"My-Laptop"})
    assert client.get("/", headers={"Host": "my-laptop:8000"}).status_code == 200
    assert client.get("/", headers={"Host": "localhost"}).status_code == 400  # only what it's given


def _refused(client, url, headers) -> int:
    with pytest.raises(WebSocketDisconnect) as exc, client.websocket_connect(url, headers=headers):
        pass
    return exc.value.code


@pytest.mark.parametrize(
    "origin", ["http://evil.example", "https://localhost.evil.example", "null", "http://[::1"]
)
def test_a_websocket_from_a_foreign_origin_is_refused(origin):
    assert _refused(guarded(), "ws://localhost/ws", {"Origin": origin}) == 1008


def test_a_websocket_to_an_unknown_host_is_refused():
    assert (
        _refused(guarded(), "ws://attacker.example/ws", {"Origin": "http://attacker.example"})
        == 1008
    )


@pytest.mark.parametrize(
    "url, origin",
    [
        ("ws://localhost:8000/ws", "http://localhost:8000"),
        ("ws://127.0.0.1:8000/ws", "http://127.0.0.1:8000"),
        ("ws://[::1]:8000/ws", "http://[::1]:8000"),
        ("ws://localhost/ws", "HTTP://LOCALHOST"),
    ],
)
def test_a_websocket_from_its_own_origin_is_accepted(url, origin):
    # The page's own origin: the scheme, host name and port of the Host it connects to.
    with guarded().websocket_connect(url, headers={"Origin": origin}) as ws:
        assert ws.receive_text() == "hello"


@pytest.mark.parametrize(
    "origin", ["http://localhost:9999", "https://localhost:8000", "http://127.0.0.1:8000"]
)
def test_a_websocket_from_another_port_scheme_or_name_of_this_host_is_refused(origin):
    # An origin is a scheme, a host name and a port (RFC 6454). A page at http://localhost:9999
    # is another program, though its host name is allowed (S24).
    assert _refused(guarded(), "ws://localhost:8000/ws", {"Origin": origin}) == 1008


@pytest.mark.parametrize("site", ["cross-site", "same-site"])
def test_a_websocket_the_browser_marks_as_another_sites_is_refused(site):
    assert (
        _refused(
            guarded(),
            "ws://localhost:8000/ws",
            {"Origin": "http://localhost:8000", "Sec-Fetch-Site": site},
        )
        == 1008
    )


def test_a_websocket_without_an_origin_is_accepted():
    # Browsers always send Origin on a websocket; a client without one is not a web page.
    with guarded().websocket_connect("ws://localhost/ws") as ws:
        assert ws.receive_text() == "hello"


def test_lifespan_passes_straight_through():
    started = []

    @asynccontextmanager
    async def lifespan(app):
        started.append(True)
        yield

    with guarded(lifespan=lifespan):
        assert started == [True]


# ---- WriteGuard --------------------------------------------------------------------------


def test_a_same_origin_json_write_passes(client):
    assert (
        client.post(
            "/api/thing",
            json={},
            headers={"Origin": "http://localhost:8000", "Sec-Fetch-Site": "same-origin"},
        ).status_code
        == 200
    )


def test_a_write_from_no_browser_passes(client):
    # No Origin and no Sec-Fetch-Site: curl or a script, not a web page. TokenGuard (Task 9)
    # still asks it for the launch cookie.
    assert client.post("/api/thing", content=b"{}", headers=JSON).status_code == 200


@pytest.mark.parametrize(
    "headers",
    [
        {"Sec-Fetch-Site": "cross-site"},
        {"Sec-Fetch-Site": "same-site"},  # another port of this host is the same site
        {"Origin": "https://evil.example"},
        {"Origin": "null"},
        {"Origin": "http://localhost:9999"},  # the same name at another port: another program
        {"Origin": "https://localhost:8000"},  # another scheme
        {"Origin": "http://127.0.0.1:8000"},  # an allowed name, but not the page's own origin
        {"Origin": "http://localhost:8000", "Sec-Fetch-Site": "cross-site"},
    ],
    ids=[
        "cross-site",
        "same-site",
        "foreign-origin",
        "null-origin",
        "other-port",
        "other-scheme",
        "other-allowed-name",
        "mixed",
    ],
)
def test_a_cross_site_write_is_refused(client, headers):
    # S25: a page on another site, or another port of this host, can post to the engine's name.
    response = client.post("/api/thing", content=b"{}", headers={**JSON, **headers})
    assert response.status_code == 403


def test_a_write_to_an_unknown_host_is_refused_even_from_that_origin(client):
    # DNS rebinding: Host and Origin both name the attacker's site, so they agree.
    response = client.post(
        "/api/thing",
        content=b"{}",
        headers={**JSON, "Host": "evil.example", "Origin": "http://evil.example"},
    )
    assert response.status_code == 403


@pytest.mark.parametrize(
    "ctype",
    [
        "text/plain",
        "application/x-www-form-urlencoded",
        "multipart/form-data; boundary=x",
        "application/json; charset=utf-8",
        "",
    ],
)
def test_anything_but_exactly_json_is_refused(client, ctype):
    # A browser sends text/plain or a form cross-site without a CORS preflight (S25).
    headers = {"Content-Type": ctype} if ctype else {}
    refused = client.post("/api/thing", content=b"{}", headers=headers)
    assert refused.status_code == 415
    assert "exactly application/json" in refused.text  # says why a charset is refused too
    assert client.delete("/api/thing", headers=headers).status_code == 415


def test_reads_are_not_affected(client):
    assert client.get("/api/thing", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 200


# ---- the headers -------------------------------------------------------------------------


def test_the_csp_is_the_specs_verbatim_and_never_allows_eval():
    assert SPEC_CSP == CSP
    assert "unsafe-eval" not in CSP and "frame-ancestors 'none'" in CSP


def test_every_response_carries_the_security_headers_and_the_csp(client):
    # Spec §6.2, §6.3. Without CORP, another site could embed /media/ in an <audio> tag, or load
    # the engine's answers with a no-cors request. A framed engine is this origin, so its own
    # websocket passes every check: no page may frame it. The CSP stops any script but the
    # engine's own files. Refusals carry them too.
    forbidden = client.post(
        "/api/thing", content=b"{}", headers={**JSON, "Sec-Fetch-Site": "cross-site"}
    )
    unsupported = client.post("/api/thing", content=b"{}", headers={"Content-Type": "text/plain"})
    assert (forbidden.status_code, unsupported.status_code) == (403, 415)
    for response in (client.get("/api/thing"), client.get("/"), forbidden, unsupported):
        assert _policy(response, PAGE) == PAGE


def test_a_media_response_is_sandboxed_unsniffed_and_never_stored(client):
    # Spec §6.3: a user's file is never run as a page, never sniffed into another type, and
    # never left in the browser's disk cache.
    r = client.get("/media/abc")
    assert r.status_code == 200
    assert _policy(r, MEDIA) == MEDIA
    assert {k: r.headers[k] for k in MEDIA_HEADERS} == MEDIA_HEADERS


def test_only_media_is_kept_out_of_the_cache(client):
    for path in ("/", "/api/thing", "/mediafile"):
        assert "cache-control" not in client.get(path).headers


def test_a_path_that_only_starts_like_media_gets_the_page_csp(client):
    assert client.get("/mediafile").headers["content-security-policy"] == SPEC_CSP


def test_the_guards_headers_replace_weaker_ones_the_app_set(client):
    r = client.get("/weak")
    assert r.headers.get_list("content-security-policy") == [SPEC_CSP]
    assert r.headers.get_list("x-frame-options") == ["DENY"]


def test_on_media_the_sandbox_replaces_any_csp_the_route_set(client):
    r = client.get("/media/abc")
    assert r.headers.get_list("content-security-policy") == ["sandbox"]
    assert r.headers.get_list("x-content-type-options") == ["nosniff"]
```

- [ ] **Step 5: Run it; watch it fail.** `uv run pytest tests/test_web_guards.py -q`. Expected:
  `E   ModuleNotFoundError: No module named 'vid2sub.web.guards'`, then `1 error in 0.23s`.

- [ ] **Step 6: Write the code,** `src/vid2sub/web/guards.py`:

```python
# Copied from recordings, packages/ui/src/recordings_ui/hosts.py at 8deb039, and relicensed under
# this repo's MIT licence (Dan owns both; spec §4.4). Changed here: the headers every response
# carries (the spec's whole CSP, and /media/'s own set), which now replace any the app set; the
# docstrings; recordings' notes on TLS proxies and its upload exemption are left out.
"""The engine answers only to its own names, takes writes only from its own pages, and sends the
security headers on every response (spec §6.2, §6.3).

The engine is a local server that reads files and holds API keys, and every website open in the
browser can reach 127.0.0.1. Other ports on this machine count as the same site, so cookies alone
don't keep them out (the council's red team, spec §27). The guards are copied from `recordings`,
which has the same threat model:

- **DNS rebinding:** a website points its own name at 127.0.0.1, then reads the engine as "same
  origin". The request still carries the website's name in `Host`: HostGuard answers 400.
- **Cross-site websockets:** browsers let any page open a websocket to any address, and send that
  page's `Origin`. HostGuard closes the handshake (1008) before accepting it unless `Origin` is
  exactly the engine's own (scheme, name and port) and the browser doesn't mark it as sent by
  another site.
- **Cross-site writes:** WriteGuard refuses every method but GET, HEAD and OPTIONS unless it is
  from this origin (or from no browser) and carries exactly `Content-Type: application/json`,
  which no page can send to another origin without a CORS preflight the engine never answers.

Every response, refusals included, carries the CSP below, `X-Frame-Options: DENY`,
`Cross-Origin-Resource-Policy`, `Cross-Origin-Opener-Policy` and `Referrer-Policy`. A response
under `/media/` carries `MEDIA_HEADERS` instead of the page CSP. These replace any header of the
same name the app set, so no route can weaken them. The engine binds 127.0.0.1 only (§6.1), behind
no proxy.
"""

from __future__ import annotations

from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
POLICY_VIOLATION = 1008  # RFC 6455 close code

# Spec §6.3, verbatim. One constant, so a directive Shiny turns out to need (spec §29: its styles)
# is a one-line change, made with the spec and Dan's OK. Never 'unsafe-eval'.
CSP = (
    "default-src 'self'; script-src 'self'; connect-src 'self'; object-src 'none'; "
    "base-uri 'none'; frame-ancestors 'none'; img-src 'self' data: blob:; media-src 'self' blob:"
)
# Spec §6.3: what /media/ serves is a user's file, never a page. Sandboxed if a browser renders it
# anyway, never sniffed into another type, and never left in the disk cache (Range still seeks).
MEDIA_HEADERS = {
    "content-security-policy": "sandbox",
    "x-content-type-options": "nosniff",
    "cache-control": "no-store",
}
# Spec §6.2, on every response. CORP: another site can't embed /media/ in an <audio> tag, or load
# the engine's answers with a no-cors request. X-Frame-Options, as frame-ancestors does for newer
# browsers: a framed engine is this origin, so its own websocket would pass every check above, and
# a decoy page could steer the user's clicks. COOP: a page that opens the engine doesn't share its
# browsing context group. Referrer-Policy: a link out doesn't send the engine's address.
_EVERY_RESPONSE = {
    "cross-origin-resource-policy": "same-origin",
    "cross-origin-opener-policy": "same-origin",
    "x-frame-options": "DENY",
    "referrer-policy": "same-origin",
}


def host_name(host: str) -> str:
    """The name in a `Host` header, lowercased, without the port or IPv6 brackets."""
    host = host.strip().lower()
    if host.startswith("["):  # [::1]:8000
        end = host.find("]")
        return host[1:end] if end > 0 else ""
    return host.partition(":")[0]


def same_origin(scope: Scope, origin: str) -> bool:
    """Whether `origin` is exactly this request's own: its scheme, then its Host header as sent.

    An origin is a scheme, a host name and a port (RFC 6454). A page at http://localhost:9999 is
    another origin than the engine at http://localhost:8765, and may be another program, though
    its host name is allowed. Browsers leave a default port out of both headers, so those match.
    """
    host = (_header(scope, b"host") or "").strip().lower()
    scheme = scope.get("scheme", "http")
    scheme = {"ws": "http", "wss": "https"}.get(scheme, scheme)
    return bool(host) and origin.strip().lower() == f"{scheme}://{host}"


def sent_by_this_site(scope: Scope) -> bool:
    """False when the browser says another site sent the request: `Sec-Fetch-Site` is anything
    but `same-origin` or `none` (a typed address). `same-site` is refused too: another port of
    this host is the same site. With no header, Origin decides."""
    site = (_header(scope, b"sec-fetch-site") or "").strip().lower()
    return site in ("", "same-origin", "none")


def _header(scope: Scope, name: bytes) -> str | None:
    for key, value in scope["headers"]:
        if key == name:
            return value.decode("latin-1")
    return None


def _policy(path: str) -> list[tuple[bytes, bytes]]:
    """The security headers for a response to `path`: /media/'s set there, the page CSP
    elsewhere, and the others on both."""
    own = MEDIA_HEADERS if path.startswith("/media/") else {"content-security-policy": CSP}
    headers = {**_EVERY_RESPONSE, **own}
    return [(k.encode("latin-1"), v.encode("latin-1")) for k, v in headers.items()]


def _with_policy(scope: Scope, send: Send) -> Send:
    """`send`, with the security headers replacing any header of the same name the app set: a
    route can't weaken them, and none is sent twice."""
    extra = _policy(scope["path"])
    names = {k for k, _ in extra}

    async def wrapped(message: Message) -> None:
        if message["type"] == "http.response.start":
            kept = [(k, v) for k, v in message.get("headers", []) if bytes(k).lower() not in names]
            message = {**message, "headers": [*kept, *extra]}
        await send(message)

    return wrapped


class HostGuard:
    """Pure ASGI middleware: refuse requests addressed to a name not in `allowed`, and websockets
    from any origin but the engine's own."""

    def __init__(self, app: ASGIApp, allowed: frozenset[str]) -> None:
        self.app = app
        self.allowed = frozenset(h.lower() for h in allowed)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):  # lifespan
            await self.app(scope, receive, send)
            return
        host_ok = host_name(_header(scope, b"host") or "") in self.allowed
        if scope["type"] == "http":
            if not host_ok:
                await PlainTextResponse("unknown host", status_code=400)(
                    scope, receive, _with_policy(scope, send)
                )
                return
        else:
            # A browser always sends Origin on a websocket. It must be the engine's own, exactly,
            # and the handshake not marked as sent by another site. No Origin means no browser
            # sent it, so no website is behind it.
            origin = _header(scope, b"origin")
            origin_ok = (origin is None or same_origin(scope, origin)) and sent_by_this_site(scope)
            if not (host_ok and origin_ok):
                # Refuse the handshake without accepting (the server answers 403).
                if (await receive())["type"] == "websocket.connect":
                    await send({"type": "websocket.close", "code": POLICY_VIOLATION})
                return
        await self.app(scope, receive, send)


SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


class WriteGuard:
    """Every request that could change data comes from this engine's own page, or from no browser
    at all, and is exactly JSON (spec §6.2). Every response carries the security headers (above).

    - **Who sent it.** A browser names the sending page in `Origin`, and marks a request another
      site sent with `Sec-Fetch-Site: cross-site` or `same-site`. Either refuses it, and so does
      an `Origin` that isn't exactly the engine's own (same_origin). Without both headers, no
      browser sent it, so no website is behind it; TokenGuard still asks it for the cookie.
    - **What it carries.** `Content-Type: application/json` can't be sent to another origin
      without a CORS preflight, which the engine never answers. Exactly that: a charset parameter
      is refused too, so there is one spelling to check.
    """

    def __init__(self, app: ASGIApp, allowed: frozenset[str]) -> None:
        self.app = app
        self.allowed = frozenset(h.lower() for h in allowed)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        send = _with_policy(scope, send)
        if scope["method"] in SAFE_METHODS:
            await self.app(scope, receive, send)
            return
        origin = _header(scope, b"origin")
        own = origin is None or (
            same_origin(scope, origin) and host_name(_header(scope, b"host") or "") in self.allowed
        )
        if not (own and sent_by_this_site(scope)):
            await PlainTextResponse("cross-site request refused", status_code=403)(
                scope, receive, send
            )
            return
        if (_header(scope, b"content-type") or "").strip().lower() != "application/json":
            await PlainTextResponse("send Content-Type exactly application/json", status_code=415)(
                scope, receive, send
            )
            return
        await self.app(scope, receive, send)
```

- [ ] **Step 7: Run the checks; they pass.** `uv run pytest tests/test_web_guards.py -q`.
  Expected: `55 passed`. Then `make check`. Expected: the suite's line, twice, with nothing failed
  (`520 passed, 2 skipped, 4 deselected` when this listing was built without Tasks 2–7's tests),
  `All checks passed!`, `no leaks found`. Ruff's default rules leave out line length, so also
  check it: `uv run python -c "import sys; [print(f, i) for f in sys.argv[1:] for i, l in
  enumerate(open(f, encoding='utf-8'), 1) if len(l.rstrip()) > 100]"
  src/vid2sub/web/guards.py tests/test_web_guards.py` prints nothing.

- [ ] **Step 8: Each guard fails its tests without its fix.** `git add src/vid2sub/web/guards.py
  tests/test_web_guards.py`. Then, for each row, make the change in `guards.py`, run
  `uv run pytest tests/test_web_guards.py -q`, see it fail, and restore the file with
  `git checkout -- src/vid2sub/web/guards.py`. The last column is what this listing's build saw.

| Guard | Change | To | Failed |
|---|---|---|---|
| unknown Host | `host_ok = host_name(_header(scope, b"host") or "") in self.allowed` | `host_ok = True` | 9 |
| websocket Origin | `origin_ok = (origin is None or same_origin(scope, origin)) and sent_by_this_site(scope)` | `origin_ok = True` | 9 |
| websocket Sec-Fetch-Site | the same line | `origin_ok = origin is None or same_origin(scope, origin)` | 2 |
| write Origin | `if not (own and sent_by_this_site(scope)):` | `if False:` | 10 |
| write Sec-Fetch-Site | the same line | `if not own:` | 4 |
| exactly JSON | `if (_header(scope, b"content-type") or "").strip().lower() != "application/json":` | `if not (_header(scope, b"content-type") or "").strip().lower().startswith("application/json"):` | 1 |
| page CSP | `else {"content-security-policy": CSP}` | `else {}` | 4 |
| no eval | `script-src 'self'; connect-src` in `CSP` | `script-src 'self' 'unsafe-eval'; connect-src` | 5 |
| media headers | `own = MEDIA_HEADERS if path.startswith("/media/") else` | `own = {} if False else` | 2 |
| every response | `headers = {**_EVERY_RESPONSE, **own}` | `headers = {**own}` | 4 |
| replace, not append | `if bytes(k).lower() not in names]` | `if True]` | 3 |
| the 400 too | `scope, receive, _with_policy(scope, send)` | `scope, receive, send` | 1 |

- [ ] **Step 9: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(web): 🤖 the engine answers only to its own names, takes writes only from its own pages, and sends the spec's CSP on every response

src/vid2sub/web/guards.py copies HostGuard and WriteGuard from recordings
(packages/ui/src/recordings_ui/hosts.py at 8deb039, relicensed under MIT, spec §4.4), with its
tests in tests/test_web_guards.py. Changed from recordings: every response now carries the spec
§6.3 CSP (guards.CSP, one constant) with X-Frame-Options, CORP, COOP and Referrer-Policy; a
response under /media/ carries guards.MEDIA_HEADERS (CSP sandbox, nosniff, no-store) instead of
the page CSP; and the guard's headers replace any of the same name the app set, so a route can't
weaken them and none is sent twice. WriteGuard keeps the exactly-application/json rule.

The new test failed first with: ModuleNotFoundError: No module named 'vid2sub.web.guards'.
Each guard was then reverted in turn and its tests failed: <the rows of Step 8, with your
counts>.

Docs read: Starlette's middleware page (pure ASGI middleware, wrapping send on
http.response.start, scope types), and Starlette's TestClient source (a websocket.close before
accept raises WebSocketDisconnect with its code).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 8
Co-Authored-By: <the model's own line>
```

  `git commit -F .git/COMMIT_MSG` (both files are staged from Step 8), then
  `git log -1 --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 10: Review, look forward, close.** The Tier 1 review from `$(cat .git/TASK_BASE)`
  (`AGENTS.md`, *Reviews*, with the security checklist). Worth the reviewers' time: that every
  refusal (400, 403, 415) carries the headers; that nothing an inner app sets can remove or
  duplicate them; that the copied checks match recordings' line for line (`git show
  8deb039:packages/ui/src/recordings_ui/hosts.py` in `~/git/hub/recordings`); that `/media/`
  is matched as a prefix with its slash, so `/mediafile` keeps the page CSP. The forward review
  over Tasks 9, 10, 11, 12 and 13 (Task 11 wraps the app as
  `HostGuard(WriteGuard(TokenGuard(api), LOCAL_HOSTS), LOCAL_HOSTS)`; Task 12 checks the CSP in
  a real browser). The docs this task made untrue: none expected (grep `docs/` and `README.md`
  for "planned" next to the guards). Then the close, its own commit, holding this plan with this
  task's boxes ticked and **Now** set to `Task 9: The launch token, open.`, and the spec's
  scenario row S25 set to `built` (S24 waits for Task 9's TokenGuard; S26 for Task 13's
  Playwright tests), with the message in `.git/CLOSE_MSG`:

```text
docs(plan): 🤖 close Task 8: The web dependencies, the guards and the CSP

Drift: none
Rulings: none
Phase-end: none
Forward: none
Tier: 1
Rounds: <Matt's code-review, Standards and Spec in two subagents; any re-review>
  secrets: fine | a finding | n/a: why
  permissions: fine | a finding | n/a: why
  network exposure: fine | a finding | n/a: why
  failing closed: fine | a finding | n/a: why
  injection: fine | a finding | n/a: why
  logging: fine | a finding | n/a: why
Findings: none

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 8
Co-Authored-By: <the model's own line>
```

  `git add docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md
  docs/superpowers/specs/2026-10-14-vid2sub-design.md`, `git commit -F .git/CLOSE_MSG`.

***

### Task 9: The launch token

**Tier:** 1 · **Scenarios:** S23, S24

**Files:**
- Create: `src/vid2sub/web/auth.py`, `src/vid2sub/web/static/auth.html`,
  `src/vid2sub/web/static/auth.js`
- Test: `tests/test_web_auth.py`

**Interfaces:**
- Consumes: Task 8's `guards.HostGuard`, `guards.WriteGuard`, `guards.LOCAL_HOSTS` (in the test
  of the whole stack).
- Produces: `auth.new_token() -> str` (`secrets.token_urlsafe(32)`); `auth.cookie_name(port: int)
  -> str` (`vid2sub-<port>`); `auth.auth_url(port: int, token: str) -> str`
  (`http://127.0.0.1:<port>/auth#t=<token>`, the token only in the fragment); `auth.write_redirect(url:
  str) -> Path` (`open.html`, mode 0600, in a new `tempfile.mkdtemp(prefix="vid2sub-")` folder,
  0700; no script; the caller removes `path.parent` when the engine exits); `class TokenGuard:
  __init__(self, app: ASGIApp, *, token: str, port: int)` (every HTTP route and websocket needs
  the cookie except HTTP `/auth`, `/auth.js` and `/healthz`, matched exactly; 401 `text/plain`
  `auth.SIGN_IN_AGAIN` for HTTP, close 1008 before accept for a websocket; lifespan passes);
  `auth.routes(token: str, port: int) -> list[BaseRoute]` (`GET /auth`, `POST /auth`,
  `GET /auth.js`); constants `auth.STATIC`, `auth.OPEN_PATHS`, `auth.SIGN_IN_AGAIN`
  (`"open the link vid2sub printed when it started"`), `auth.MAX_BODY` (1024).
- `POST /auth`: `{"token": "<token>"}` with `Content-Type: application/json` exactly; 204 and the
  cookie (`HttpOnly`, `SameSite=Strict`, `Path=/`, no `Secure`, a session cookie) on a match
  (`secrets.compare_digest` on bytes); 403 and no cookie for a wrong or missing token; 400 for a
  malformed body; 413 over `MAX_BODY`. The cookie's value is an HMAC-SHA256 of the token, not the
  token, so the token appears in no response.

- [ ] **Step 0: Record the base:** `git rev-parse HEAD > .git/TASK_BASE`.

- [ ] **Step 1: Write the failing test,** `tests/test_web_auth.py`. Its `TOKEN` is deliberately
  low-entropy: a realistic-looking fake token beside the word "token" is a gitleaks
  `generic-api-key` hit, and a leak-scan hit is a stop (`AGENTS.md`, *Stops*).

```python
"""Only the browser vid2sub opened, with the cookie it got from the launch token, reaches the
engine; the token itself never reaches a response, a log or the command line (spec §6.1; S23,
S24; Review Focus 5)."""

import asyncio
import json
import logging
import re
import stat
import sys
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Route, WebSocketRoute
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from vid2sub.web import auth
from vid2sub.web.guards import LOCAL_HOSTS, HostGuard, WriteGuard

PORT = 8765
# 43 URL-safe characters, as new_token makes, and plainly not a secret (the leak scan agrees).
TOKEN = "testtokentesttokentesttokentesttokentesttok"
BASE = f"http://127.0.0.1:{PORT}"
# In full: the test client joins a bare path onto ws://testserver, which gets no cookie.
WS = f"ws://127.0.0.1:{PORT}/websocket/"
JSON = {"Content-Type": "application/json"}
SIGN_IN_AGAIN = "open the link vid2sub printed when it started"


async def _home(request):
    return PlainTextResponse("home")


async def _healthz(request):
    return JSONResponse({"ok": True})


async def _write(request):
    return JSONResponse({"written": True})


async def _echo(websocket):
    await websocket.accept()
    await websocket.send_text("hello")
    await websocket.close()


def _app(token=TOKEN, port=PORT, lifespan=None):
    inner = Starlette(
        routes=[
            *auth.routes(token, port),
            Route("/healthz", _healthz),
            Route("/", _home),
            Route("/api/write", _write, methods=["POST"]),
            Route("/media/{token}", _home),
            WebSocketRoute("/websocket/", _echo),
        ],
        lifespan=lifespan,
    )
    return auth.TokenGuard(inner, token=token, port=port)


@pytest.fixture
def client():
    with TestClient(_app(), base_url=BASE) as c:
        yield c


def _sign_in(client, token=TOKEN):
    return client.post("/auth", content=json.dumps({"token": token}), headers=JSON)


def _cookie_value(token=TOKEN, port=PORT) -> str:
    # What a signed-in browser holds: whatever POST /auth set.
    with TestClient(_app(token, port), base_url=f"http://127.0.0.1:{port}") as c:
        r = _sign_in(c, token)
        assert r.status_code == 204
        return c.cookies[auth.cookie_name(port)]


# ---- the token, the cookie's name, the sign-in link and the redirect file ------------------


def test_a_token_is_256_random_bits_in_url_safe_characters():
    tokens = {auth.new_token() for _ in range(50)}
    assert len(tokens) == 50
    assert all(re.fullmatch(r"[A-Za-z0-9_-]{43}", t) for t in tokens)


def test_the_cookie_is_named_for_the_port():
    assert auth.cookie_name(8765) == "vid2sub-8765"
    assert auth.cookie_name(9000) == "vid2sub-9000"


def test_the_sign_in_link_carries_the_token_only_in_the_fragment():
    # The fragment never reaches a request line, so never the server's logs (spec §6.1).
    url = auth.auth_url(PORT, TOKEN)
    assert url == f"http://127.0.0.1:{PORT}/auth#t={TOKEN}"
    parts = urlsplit(url)
    assert (parts.path, parts.query, parts.fragment) == ("/auth", "", f"t={TOKEN}")


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes")
def test_the_redirect_file_is_private_and_its_path_never_names_the_token():
    # `ps` shows the browser's arguments: the file's path, never the token (S23).
    page = auth.write_redirect(auth.auth_url(PORT, TOKEN))
    try:
        assert stat.S_IMODE(page.stat().st_mode) == 0o600
        assert stat.S_IMODE(page.parent.stat().st_mode) == 0o700
        assert TOKEN not in str(page)
    finally:
        page.unlink()
        page.parent.rmdir()


def test_the_redirect_file_sends_the_browser_on_without_any_script():
    url = auth.auth_url(PORT, TOKEN)
    page = auth.write_redirect(url)
    try:
        text = page.read_text(encoding="utf-8")
        assert f'<meta http-equiv="refresh" content="0;url={url}">' in text
        assert f'<a href="{url}">' in text  # for a browser that ignores the refresh
        assert "<script" not in text.lower()
    finally:
        page.unlink()
        page.parent.rmdir()


def test_the_redirect_file_escapes_what_it_is_given():
    page = auth.write_redirect('http://127.0.0.1:1/auth#t="><script>alert(1)</script>')
    try:
        text = page.read_text(encoding="utf-8")
        assert "<script" not in text and "&quot;&gt;&lt;script&gt;" in text
    finally:
        page.unlink()
        page.parent.rmdir()


# ---- /auth and its script --------------------------------------------------------------------


def test_the_auth_page_loads_its_script_from_a_file_and_has_none_inline(client):
    # The CSP allows only the engine's own files (spec §6.3): an inline script wouldn't run.
    page = client.get("/auth")
    assert page.status_code == 200
    assert page.headers["content-type"] == "text/html; charset=utf-8"
    scripts = re.findall(
        r"<script\b([^>]*)>(.*?)</script>", page.text, flags=re.DOTALL | re.IGNORECASE
    )
    assert scripts == [(' src="/auth.js"', "")]
    assert not re.search(r"\son[a-z]+\s*=|\sstyle\s*=|<style", page.text, flags=re.IGNORECASE)
    script = client.get("/auth.js")
    assert script.status_code == 200
    assert script.headers["content-type"] == "application/javascript"


def test_the_auth_script_posts_exactly_json_and_shows_text_only():
    # WriteGuard refuses `application/json; charset=…`, and the message is set as text.
    js = (auth.STATIC / "auth.js").read_text(encoding="utf-8")
    assert 'headers: { "Content-Type": "application/json" },' in js
    assert 'credentials: "same-origin"' in js
    assert 'location.replace("/")' in js and "location.hash" in js
    assert "This link is out of date: open the URL vid2sub printed when it started." in js
    assert "textContent" in js and "innerHTML" not in js and "eval" not in js


# ---- POST /auth ------------------------------------------------------------------------------


def test_the_right_token_sets_an_httponly_strict_cookie_for_the_whole_site(client):
    r = _sign_in(client)
    assert r.status_code == 204 and r.content == b""
    cookie = r.headers["set-cookie"]
    name, _, rest = cookie.partition("=")
    attributes = {a.strip().split("=")[0].lower(): a.strip() for a in rest.split(";")[1:]}
    assert name == "vid2sub-8765"
    assert attributes["httponly"] == "HttpOnly"
    assert attributes["samesite"] == "SameSite=strict"
    assert attributes["path"] == "Path=/"
    # Plain http on 127.0.0.1, so no Secure; a session cookie, so it dies with the browser.
    assert not {"secure", "max-age", "expires", "domain"} & set(attributes)


@pytest.mark.parametrize(
    "body",
    [
        {"token": "wrong"},
        {"token": ""},
        {"token": TOKEN + "x"},
        {"token": TOKEN[:-1]},
        {"token": "é" * 43},  # not ASCII: compared as bytes, never a TypeError
        {},
    ],
    ids=["wrong", "empty", "longer", "shorter", "non-ascii", "missing"],
)
def test_a_wrong_or_missing_token_is_403_and_sets_no_cookie(client, body):
    r = client.post("/auth", content=json.dumps(body), headers=JSON)
    assert r.status_code == 403
    assert "set-cookie" not in r.headers and not client.cookies


@pytest.mark.parametrize(
    "content",
    [b"", b"not json", b"[]", b'"token"', b'{"token": 5}', b'{"token": null}', b"\xff\xfe",
     b"[" * 500 + b"]" * 500],
    ids=["empty", "not-json", "list", "string", "number", "null", "bad-bytes", "deep"],
)
def test_a_malformed_body_is_400_and_sets_no_cookie(client, content):
    r = client.post("/auth", content=content, headers=JSON)
    assert r.status_code == 400
    assert "set-cookie" not in r.headers


def test_a_body_too_large_for_a_token_is_refused(client):
    r = client.post("/auth", content=json.dumps({"token": "x" * 2000}), headers=JSON)
    assert r.status_code == 413 and "set-cookie" not in r.headers


# ---- TokenGuard ------------------------------------------------------------------------------


def test_without_the_cookie_every_route_but_the_open_three_is_401(client):
    for method, path in [("GET", "/"), ("GET", "/media/abc"), ("POST", "/api/write"),
                         ("GET", "/no-such-page"), ("HEAD", "/")]:
        r = client.request(method, path, headers=JSON)
        assert r.status_code == 401, path
        assert r.headers["content-type"] == "text/plain; charset=utf-8"
        if method != "HEAD":
            assert r.text == SIGN_IN_AGAIN
    for path in ("/auth", "/auth.js", "/healthz"):
        assert client.get(path).status_code == 200, path


def test_after_signing_in_every_route_answers(client):
    assert _sign_in(client).status_code == 204
    assert client.get("/").text == "home"
    assert client.get("/media/abc").status_code == 200
    assert client.post("/api/write", content=b"{}", headers=JSON).json() == {"written": True}


def _status(app, path: str, cookie: str | None = None) -> int:
    """Call `app` with exactly this `scope["path"]`, as uvicorn passes it (an HTTP client would
    normalise `..` away first), and return the status it answers."""
    headers = [(b"host", f"127.0.0.1:{PORT}".encode())]
    if cookie is not None:
        headers.append((b"cookie", cookie.encode("latin-1")))
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "GET",
             "scheme": "http", "path": path, "raw_path": path.encode("latin-1"),
             "query_string": b"", "root_path": "", "headers": headers,
             "server": ("127.0.0.1", PORT), "client": ("127.0.0.1", 50000)}
    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    asyncio.run(app(scope, receive, send))
    return sent[0]["status"]


@pytest.fixture
def recorded():
    """A TokenGuard around an app that records each path it is reached with."""
    reached: list[str] = []

    async def inner(scope, receive, send):
        reached.append(scope["path"])
        await PlainTextResponse("inner")(scope, receive, send)

    return auth.TokenGuard(inner, token=TOKEN, port=PORT), reached


@pytest.mark.parametrize(
    "path",
    ["/auth/", "/auth/x", "/auth.js/", "/auth.jsx", "/authx", "/healthz/", "/healthz/../",
     "/healthz/..", "/healthz/../media/x", "/auth/../", "//healthz", "/HEALTHZ", "/Auth",
     "/auth\x00", "/auth;x", "/healthz ", " /healthz", "/./healthz", "", "/"],
)
def test_a_path_that_only_looks_open_needs_the_cookie(recorded, path):
    guard, reached = recorded
    assert _status(guard, path) == 401 and reached == []


def test_the_open_paths_are_matched_exactly_and_reach_the_app(recorded):
    guard, reached = recorded
    assert [_status(guard, p) for p in ("/auth", "/auth.js", "/healthz")] == [200, 200, 200]
    assert reached == ["/auth", "/auth.js", "/healthz"]


@pytest.mark.parametrize(
    "cookie",
    [
        "vid2sub-8765=wrong",
        f"vid2sub-8765={TOKEN}",  # the token itself is not the cookie
        "vid2sub-8765=",
        "vid2sub-8765",
        "vid2sub-9999={value}",  # the right value under another port's name
        "other={value}",
        "vid2sub-8765={value}x",
        "vid2sub-8765=x{value}",
    ],
)
def test_a_cookie_that_isnt_this_launchs_is_401(recorded, cookie):
    guard, reached = recorded
    assert _status(guard, "/", cookie.replace("{value}", _cookie_value())) == 401
    assert reached == []


def test_the_cookie_is_found_among_others_and_beside_a_planted_one(recorded):
    # A page on another port of 127.0.0.1 can set cookies for this host (cookies ignore ports),
    # but can't read or remove the HttpOnly one: a planted cookie of the same name is ignored.
    guard, reached = recorded
    value = _cookie_value()
    assert _status(guard, "/", f"theme=dark; vid2sub-8765=planted; vid2sub-8765={value}") == 200
    assert _status(guard, "/", f"vid2sub-8765={value}; vid2sub-8765=planted") == 200
    assert _status(guard, "/", f'vid2sub-8765={value}; other="x"') == 200
    assert reached == ["/", "/", "/"]


def test_a_restarted_engine_refuses_the_old_cookie():
    # Review Focus 5: a tab left open across a restart is told to open the new link.
    old = _cookie_value(TOKEN)
    with TestClient(_app(token=auth.new_token()), base_url=BASE) as c:
        c.cookies.set(auth.cookie_name(PORT), old, domain="127.0.0.1")
        r = c.get("/")
        assert r.request.headers["cookie"] == f"vid2sub-8765={old}"  # it was sent, and refused
        assert r.status_code == 401 and r.text == SIGN_IN_AGAIN
        with pytest.raises(WebSocketDisconnect) as exc, c.websocket_connect(WS):
            pass
        assert exc.value.code == 1008


def test_a_websocket_without_the_cookie_is_closed_before_accept(client):
    # S24: a page on another local port opening the websocket gets nothing.
    with pytest.raises(WebSocketDisconnect) as exc, client.websocket_connect(WS):
        pass
    assert exc.value.code == 1008


def test_a_websocket_with_the_cookie_is_accepted(client):
    _sign_in(client)
    with client.websocket_connect(WS) as ws:
        assert ws.receive_text() == "hello"


def test_lifespan_passes_straight_through():
    started = []

    @asynccontextmanager
    async def lifespan(app):
        started.append(True)
        yield

    with TestClient(_app(lifespan=lifespan), base_url=BASE):
        assert started == [True]


# ---- the token goes nowhere --------------------------------------------------------------


def test_the_token_is_in_no_response_and_no_log_record(caplog):
    # S23. It is in the redirect file, by design, and nowhere else.
    caplog.set_level(logging.DEBUG)
    page = auth.write_redirect(auth.auth_url(PORT, TOKEN))
    try:
        assert TOKEN in page.read_text(encoding="utf-8")  # so the checks below aren't vacuous
    finally:
        page.unlink()
        page.parent.rmdir()
    responses = []
    with TestClient(_app(), base_url=BASE) as c:
        responses += [c.get("/"), c.get("/auth"), c.get("/auth.js"), c.get("/healthz")]
        responses += [c.post("/auth", content=b"{}", headers=JSON),
                      c.post("/auth", content=b"nope", headers=JSON),
                      _sign_in(c, "wrong"), _sign_in(c)]
        responses += [c.get("/"), c.post("/api/write", content=b"{}", headers=JSON)]
    for r in responses:
        assert TOKEN.encode() not in r.content
        assert all(TOKEN.encode() not in k + v for k, v in r.headers.raw)
    assert caplog.records  # httpx logs each request
    for record in caplog.records:
        assert TOKEN not in record.getMessage() and TOKEN not in repr(record.args)


def test_the_whole_stack_signs_a_browser_in():
    # As Task 11 wraps it: HostGuard(WriteGuard(TokenGuard(app))), with a browser's headers.
    app = HostGuard(WriteGuard(_app(), LOCAL_HOSTS), LOCAL_HOSTS)
    page = {"Origin": BASE, "Sec-Fetch-Site": "same-origin"}
    with TestClient(app, base_url=BASE) as c:
        assert c.get("/").status_code == 401
        refused = c.post("/auth", content=json.dumps({"token": TOKEN}),
                         headers={**JSON, "Origin": "http://127.0.0.1:9999",
                                  "Sec-Fetch-Site": "same-site"})
        assert refused.status_code == 403 and "set-cookie" not in refused.headers
        charset = c.post("/auth", content=json.dumps({"token": TOKEN}),
                         headers={"Content-Type": "application/json; charset=utf-8", **page})
        assert charset.status_code == 415
        r = c.post("/auth", content=json.dumps({"token": TOKEN}), headers={**JSON, **page})
        assert r.status_code == 204
        assert c.get("/").text == "home"
        with c.websocket_connect(WS, headers={"Origin": BASE}) as ws:
            assert ws.receive_text() == "hello"
```

- [ ] **Step 2: Run it; watch it fail.** `uv run pytest tests/test_web_auth.py -q`. Expected:
  `E   ImportError: cannot import name 'auth' from 'vid2sub.web' (…/src/vid2sub/web/__init__.py)`,
  then `1 error in 0.21s`.

- [ ] **Step 3: Write the code,** `src/vid2sub/web/auth.py`:

```python
"""The launch token: only the browser vid2sub opened, holding the cookie it got for the token,
reaches the engine (spec §6.1).

As Jupyter does (the council's red team, spec §27). Each launch makes a token and opens the
browser through a redirect file (mode 0600, in a 0700 folder) that goes to `/auth#t=<token>`.
The token is in the fragment, which a browser never sends, so it reaches no request line, no
server log and no command line (`ps` shows only the file's path). The `/auth` page's script, a
file because the CSP allows no inline script, posts it back and gets an `HttpOnly`,
`SameSite=Strict` cookie named for the port, so launches on two ports don't clobber each other.
The cookie's value is an HMAC of the token, so the token itself is in no response either.

TokenGuard asks every other request and every websocket handshake for that cookie. A restart
makes a new token, so a tab left open is refused and told to open the new link (Review Focus 5).
No `Secure` flag: the engine is plain http on 127.0.0.1. Cookies ignore ports, so the cookie
alone doesn't keep out a page on another port of this machine; HostGuard and WriteGuard do
(spec §6.2).
"""

from __future__ import annotations

import hashlib
import hmac
import html
import json
import os
import secrets
import tempfile
from pathlib import Path

from starlette.requests import Request
from starlette.responses import FileResponse, PlainTextResponse, Response
from starlette.routing import BaseRoute, Route
from starlette.types import ASGIApp, Receive, Scope, Send

STATIC = Path(__file__).parent / "static"
# Matched exactly, never as prefixes: /auth/x or /healthz/../ needs the cookie like any path.
OPEN_PATHS = frozenset({"/auth", "/auth.js", "/healthz"})
POLICY_VIOLATION = 1008  # RFC 6455 close code
SIGN_IN_AGAIN = "open the link vid2sub printed when it started"
MAX_BODY = 1024  # bytes; {"token": "<43 characters>"} is 56
_MALFORMED = 'send {"token": "<the token>"} as JSON'


def new_token() -> str:
    """A fresh launch token: 256 random bits in 43 URL-safe characters."""
    return secrets.token_urlsafe(32)


def cookie_name(port: int) -> str:
    """The launch cookie's name, which names the port."""
    return f"vid2sub-{port}"


def auth_url(port: int, token: str) -> str:
    """The link that signs a browser in, with the token only in the fragment."""
    return f"http://127.0.0.1:{port}/auth#t={token}"


def _cookie_value(token: str) -> str:
    return hmac.new(token.encode(), b"vid2sub launch cookie", hashlib.sha256).hexdigest()


def write_redirect(url: str) -> Path:
    """Write a page that sends the browser to `url`, in a new private folder, and return its path.

    It is opened as a file, where no CSP applies, so it has no script: a meta refresh, and a link
    for a browser that ignores it. The folder is the caller's to remove when the engine exits.
    """
    folder = Path(tempfile.mkdtemp(prefix="vid2sub-"))  # mode 0700 (the tempfile docs)
    page = folder / "open.html"
    href = html.escape(url, quote=True)
    text = (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        f'<meta http-equiv="refresh" content="0;url={href}">\n'
        "<title>vid2sub</title>\n</head>\n"
        f'<body><p><a href="{href}">Open vid2sub</a></p></body>\n</html>\n'
    )
    fd = os.open(page, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    return page


def routes(token: str, port: int) -> list[BaseRoute]:
    """`GET /auth` (the page), `GET /auth.js` (its script) and `POST /auth` (the token for the
    cookie), to register before anything mounted at `/`."""
    expected = token.encode()
    name = cookie_name(port)
    value = _cookie_value(token)

    def page(request: Request) -> Response:
        return FileResponse(STATIC / "auth.html", media_type="text/html")

    def script(request: Request) -> Response:
        return FileResponse(STATIC / "auth.js", media_type="application/javascript")

    async def sign_in(request: Request) -> Response:
        try:
            data = json.loads(await request.body())
        except ValueError:  # not JSON, or not UTF-8; MAX_BODY keeps nesting far from the limit
            return PlainTextResponse(_MALFORMED, status_code=400)
        given = data.get("token", "") if isinstance(data, dict) else None  # missing: no match
        if not isinstance(given, str):
            return PlainTextResponse(_MALFORMED, status_code=400)
        if not secrets.compare_digest(given.encode(), expected):  # bytes: any text compares
            return PlainTextResponse("this link is out of date", status_code=403)
        response = Response(status_code=204)
        response.set_cookie(name, value, path="/", httponly=True, samesite="strict")
        return response

    return [
        Route("/auth", page, methods=["GET"]),
        Route("/auth", sign_in, methods=["POST"], max_body_size=MAX_BODY),
        Route("/auth.js", script, methods=["GET"]),
    ]


class TokenGuard:
    """Pure ASGI middleware: every HTTP request and websocket handshake needs this launch's
    cookie, except HTTP requests for the open paths, matched exactly. Lifespan passes through."""

    def __init__(self, app: ASGIApp, *, token: str, port: int) -> None:
        self.app = app
        self._name = cookie_name(port)
        self._value = _cookie_value(token).encode()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):  # lifespan
            await self.app(scope, receive, send)
            return
        if (scope["type"] == "http" and scope["path"] in OPEN_PATHS) or self._signed_in(scope):
            await self.app(scope, receive, send)
            return
        if scope["type"] == "http":
            await PlainTextResponse(SIGN_IN_AGAIN, status_code=401)(scope, receive, send)
        elif (await receive())["type"] == "websocket.connect":
            # Refuse the handshake without accepting (the server answers 403), as HostGuard does.
            await send({"type": "websocket.close", "code": POLICY_VIOLATION})

    def _signed_in(self, scope: Scope) -> bool:
        """Whether any cookie of this launch's name holds its value. Every one is checked: a page
        on another port can plant a cookie of the same name beside the real one."""
        found = False
        for key, raw in scope["headers"]:
            if key != b"cookie":
                continue
            for pair in raw.decode("latin-1").split(";"):
                name, sep, value = pair.strip().partition("=")
                if sep and name == self._name:
                    found |= secrets.compare_digest(value.strip().encode("latin-1"), self._value)
        return found
```

  `src/vid2sub/web/static/auth.html`:

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>vid2sub</title>
</head>
<body>
<main>
<h1>vid2sub</h1>
<p id="status" role="status">Signing in…</p>
<noscript><p>vid2sub needs JavaScript.</p></noscript>
</main>
<script src="/auth.js"></script>
</body>
</html>
```

  `src/vid2sub/web/static/auth.js`:

```javascript
// Signs this browser in to vid2sub (spec §6.1): posts the launch token from the URL's fragment
// to /auth, which answers with the launch cookie, then opens the app. A file, not an inline
// script, because the CSP allows only the engine's own files (spec §6.3).
"use strict";

(function () {
  const status = document.getElementById("status");
  const stale = "This link is out of date: open the URL vid2sub printed when it started.";
  const token = new URLSearchParams(location.hash.slice(1)).get("t");
  // The token leaves the address bar and the history before anything else happens.
  history.replaceState(null, "", location.pathname);
  if (!token) {
    status.textContent = stale;
    return;
  }
  fetch("/auth", {
    method: "POST",
    // Exactly this: WriteGuard refuses any other Content-Type, a charset included (spec §6.2).
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token: token }),
    credentials: "same-origin",
    cache: "no-store",
  }).then(
    function (response) {
      if (response.status === 204) {
        location.replace("/");
      } else {
        status.textContent = stale;
      }
    },
    function () {
      status.textContent = "vid2sub isn't answering: start it again and open the URL it prints.";
    },
  );
})();
```

- [ ] **Step 4: Run the checks; they pass.** `uv run pytest tests/test_web_auth.py -q`.
  Expected: `62 passed`. Then `make check`. Expected: the suite's line, twice, with nothing failed
  (`582 passed, 2 skipped, 4 deselected` when this listing was built without Tasks 2–7's tests),
  `All checks passed!`, `no leaks found`. Line length, which ruff's default rules leave out:
  `uv run python -c "import sys; [print(f, i) for f in sys.argv[1:] for i, l in
  enumerate(open(f, encoding='utf-8'), 1) if len(l.rstrip()) > 100]" src/vid2sub/web/auth.py
  src/vid2sub/web/static/auth.js tests/test_web_auth.py` prints nothing. The wheel carries the
  static files: `uv build --wheel -o "$(mktemp -d)"` and list the wheel; it has
  `vid2sub/web/static/auth.html` and `auth.js` (hatchling packs every file under
  `src/vid2sub`).

- [ ] **Step 5: Each guard fails its tests without its fix.** `git add src/vid2sub/web/auth.py
  src/vid2sub/web/static/auth.html src/vid2sub/web/static/auth.js tests/test_web_auth.py`. Then,
  for each row, make the change in `auth.py`, run `uv run pytest tests/test_web_auth.py -q`, see
  it fail, and restore with `git checkout -- src/vid2sub/web/auth.py`. The last column is what
  this listing's build saw.

| Guard | Change | To | Failed |
|---|---|---|---|
| open paths exact | `(scope["type"] == "http" and scope["path"] in OPEN_PATHS)` | `(scope["type"] == "http" and scope["path"].startswith(tuple(OPEN_PATHS)))` | 13 |
| no open websocket | the same | `(scope["path"] in OPEN_PATHS or scope["path"] == "/websocket/")` | 2 |
| the cookie at all | `or self._signed_in(scope):` | `or True:` | 32 |
| the cookie's value | `found \|= secrets.compare_digest(value.strip().encode("latin-1"), self._value)` | `found = True` | 6 |
| every same-named cookie | `found \|= secrets.compare_digest(` | `found = secrets.compare_digest(` | 1 |
| websockets | the three lines from `elif (await receive())["type"] == "websocket.connect":` | two lines: `else:` and `await self.app(scope, receive, send)` | 2 |
| the token | `if not secrets.compare_digest(given.encode(), expected):` | `if False:` | 6 |
| bytes compare | the same line | `if not secrets.compare_digest(given, expected.decode()):` | 1 |
| token not in the cookie | `return hmac.new(token.encode(), b"vid2sub launch cookie", hashlib.sha256).hexdigest()` | `return token` | 2 |
| HttpOnly | `httponly=True` | `httponly=False` | 1 |
| SameSite=Strict | `samesite="strict"` | `samesite="lax"` | 1 |
| port in the name | `return f"vid2sub-{port}"` | `return "vid2sub"` | 4 |
| body limit | `max_body_size=MAX_BODY` | `max_body_size=None` | 1 |
| malformed JSON | `except ValueError:` | `except KeyError:` | 4 |
| redirect file mode | `os.O_WRONLY \| os.O_CREAT \| os.O_EXCL, 0o600)` | `… 0o644)` | 1 |
| redirect escaping | `href = html.escape(url, quote=True)` | `href = url` | 1 |
| token in the fragment | `/auth#t={token}` | `/auth?t={token}` | 1 |

- [ ] **Step 6: See it in a real browser** (optional before Task 13's harness exists, but cheap;
  it is how this listing was checked). Only if Chromium is already installed for Playwright;
  otherwise skip it (Task 13 sets that up). Serve
  `HostGuard(WriteGuard(TokenGuard(Starlette(routes=[*auth.routes(token, port), <a "/" route>]),
  token=token, port=port), LOCAL_HOSTS), LOCAL_HOSTS)` with uvicorn on 127.0.0.1 and
  `access_log=False`, open `write_redirect(auth_url(port, token)).as_uri()` in a Playwright page,
  and wait for the URL `http://127.0.0.1:<port>/`. This listing's run: it landed on `/`, no
  console message (no CSP violation), the token in no request line and not in the address bar,
  the cookie `HttpOnly`, `Strict`, `Path=/`, not `Secure`, expiring with the session; a page at
  `/auth#t=wrong` showed "This link is out of date: open the URL vid2sub printed when it
  started." and `/` without the cookie answered `open the link vid2sub printed when it started`.
  Nothing from this step is committed.

- [ ] **Step 7: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(web): 🤖 only the browser vid2sub opened reaches the engine: the launch token, sent in a link's fragment, buys an HttpOnly cookie that every other route and the websocket need

src/vid2sub/web/auth.py (spec §6.1): new_token() is 256 random bits; auth_url() puts it only in
the fragment; write_redirect() writes a script-free page (meta refresh and a link, the URL
escaped) at mode 0600 in a mkdtemp folder, so `ps` shows only that path. GET /auth serves
static/auth.html, whose only script is /auth.js (the CSP allows no inline script); auth.js posts
{"token": t} with Content-Type exactly application/json and same-origin credentials, then
replaces the URL with "/", or says the link is out of date. POST /auth compares as bytes with
secrets.compare_digest and sets vid2sub-<port>, HttpOnly, SameSite=Strict, Path=/, no Secure (it
is http on loopback), as a session cookie: 204; a wrong or missing token is 403 with no cookie, a
malformed body 400, more than 1 KiB 413. The cookie's value is an HMAC of the token, so the token
is in no response. TokenGuard answers 401 "open the link vid2sub printed when it started" to any
HTTP request without the cookie except /auth, /auth.js and /healthz, matched exactly (path tricks
tested on the raw ASGI path), closes a websocket without it with 1008 before accept, checks every
cookie of its name (a page on another port can plant one), and passes lifespan through.

The new test failed first with: ImportError: cannot import name 'auth' from 'vid2sub.web'.
Each guard was then reverted in turn and its tests failed: <the rows of Step 5, with your
counts>. <Step 6's browser run, if made.>

Docs read: Starlette's responses page (set_cookie's arguments and defaults) and its source;
its routing page (max_body_size answers 413, GET-only function endpoints, the str path
convertor); its middleware page; Python's tempfile.mkdtemp (owner-only, the caller deletes it)
and hmac.compare_digest (ASCII str or bytes; only lengths may leak).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 9
Co-Authored-By: <the model's own line>
```

  `git commit -F .git/COMMIT_MSG` (the four files are staged from Step 5), then
  `git log -1 --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 8: Review, look forward, close.** The Tier 1 review from `$(cat .git/TASK_BASE)`
  (`AGENTS.md`, *Reviews*, with the security checklist). Worth the reviewers' time: that the open
  paths are matched exactly, on `scope["path"]`, and only for HTTP; that the token reaches no
  response, log record, URL path or query, or file name (the redirect file's contents are its
  one home); that every comparison is constant-time; that nothing in `auth.html` or `auth.js`
  would need `'unsafe-inline'` or `'unsafe-eval'`; that a malformed or oversized body can't
  raise a 500. Known and accepted (spec §6.2): cookies ignore ports, so a server the user visits
  on another port of 127.0.0.1 would receive the cookie; HostGuard and WriteGuard are what keep
  pages on other ports out. The forward review over Tasks 11, 12 and 13 (Task 11 prints
  `auth_url(port, token)` to the terminal only, opens `write_redirect(…)` with `webbrowser`,
  removes its folder at exit, and turns uvicorn's access log off; Task 12's page shows
  `SIGN_IN_AGAIN` instead of reconnecting when the websocket closes with 1008, Review Focus 5;
  Task 13's `page` fixture signs in through `/auth#t=<token>`). The docs this task made untrue:
  none expected. Then the close, its own commit, holding this plan with this task's boxes ticked
  and **Now** set to `Task 10: Media tokens and \`/media/{token}\`, open.`, and the spec's
  scenario row S24 set to `built`, its Proof reading `tests/test_web_guards.py`,
  `tests/test_web_auth.py` (S23 waits for Task 11, which binds and opens the browser), with the
  message in `.git/CLOSE_MSG`:

```text
docs(plan): 🤖 close Task 9: The launch token

Drift: none
Rulings: none
Phase-end: none
Forward: none
Tier: 1
Rounds: <Matt's code-review, Standards and Spec in two subagents; any re-review>
  secrets: fine | a finding | n/a: why
  permissions: fine | a finding | n/a: why
  network exposure: fine | a finding | n/a: why
  failing closed: fine | a finding | n/a: why
  injection: fine | a finding | n/a: why
  logging: fine | a finding | n/a: why
Findings: none

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 9
Co-Authored-By: <the model's own line>
```

  `git add docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md
  docs/superpowers/specs/2026-10-14-vid2sub-design.md`, `git commit -F .git/CLOSE_MSG`.

***

### Task 10: Media tokens and `/media/{token}`

**Tier:** 1 · **Scenarios:** S27, S43

**Files:**
- Create: `src/vid2sub/web/media.py`
- Test: `tests/test_web_media.py`

**Interfaces:**
- Consumes: Task 8's `guards.HostGuard`, `guards.WriteGuard`, `guards.LOCAL_HOSTS` (the tests
  check `/media/`'s headers through them).
- Produces: `class MediaTokens: issue(self, path: Path, *, owner: str) -> str` (records
  `(st_dev, st_ino, st_size)`; `path` must be an absolute path to a regular file whose type is
  audio/* or video/*, else `ValueError` with a message that names no path); `resolve(self, token:
  str) -> Path | None` (None when unknown, revoked, or the file was replaced, resized or removed);
  `revoke_owner(self, owner: str) -> None`; `media.media_type(path: Path) -> str | None`
  (`.mkv` → `video/x-matroska` and `.m4a` → `audio/mp4` fixed, the rest from `mimetypes`, a
  compressed name refused); `media.route(tokens: MediaTokens) -> BaseRoute` (`GET /media/{token}`
  and HEAD: Range, `Content-Disposition: inline`, 404 for a token that isn't live). Thread-safe;
  `owner` is the episode's id (plan Decision 1).
- Built differently from the design note: `FileResponse(…, content_disposition_type="inline")`
  writes no header unless a `filename` is passed (Starlette 1.9.0's source), and a filename would
  put the video's title in a header, so the route passes `headers={"Content-Disposition":
  "inline"}` instead.

- [ ] **Step 0: Record the base:** `git rev-parse HEAD > .git/TASK_BASE`.

- [ ] **Step 1: Write the failing test,** `tests/test_web_media.py`. Ruff refuses a literal bidi
  character in source (PLE2502), so the right-to-left override is written as `‮`.

```python
"""The browser plays a video or its playback audio by an unguessable token bound to the launch,
never by its path, and a file swapped since the token was issued is never served (spec §6.3,
§6.5; plan Decision 1; S27, S43; Review Focus 1).

The Range, 416 and 404 tests follow recordings' media route tests (packages/ui/tests/test_app.py
at 8deb039).
"""

import logging
import os
import re
import secrets
import sys
from pathlib import Path

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from vid2sub.web import media
from vid2sub.web.guards import LOCAL_HOSTS, HostGuard, WriteGuard

BODY = bytes(range(256)) * 4  # 1024 bytes, each position recognisable
MEDIA = {
    "content-security-policy": "sandbox",
    "x-content-type-options": "nosniff",
    "cache-control": "no-store",
    "cross-origin-resource-policy": "same-origin",
    "x-frame-options": "DENY",
}


@pytest.fixture
def tokens():
    return media.MediaTokens()


@pytest.fixture
def client(tokens):
    # As Task 11 wraps it, less TokenGuard (Task 9's tests cover the cookie).
    app = HostGuard(WriteGuard(Starlette(routes=[media.route(tokens)]), LOCAL_HOSTS), LOCAL_HOSTS)
    with TestClient(app, base_url="http://127.0.0.1:8765") as c:
        yield c


def _file(folder: Path, name: str, body: bytes = BODY) -> Path:
    path = folder / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return path


# ---- tokens ----------------------------------------------------------------------------------


def test_a_token_is_256_random_bits_and_never_names_the_file(tokens, tmp_path):
    video = _file(tmp_path, "Show S01E01.mp4")
    issued = [tokens.issue(video, owner="ep1") for _ in range(20)]
    assert len(set(issued)) == 20  # a fresh token each time, not one derived from the path
    assert all(re.fullmatch(r"[A-Za-z0-9_-]{43}", t) for t in issued)
    assert not any("Show" in t for t in issued)


def test_a_live_token_resolves_to_its_file(tokens, tmp_path):
    video = _file(tmp_path, "clip.mp4")
    assert tokens.resolve(tokens.issue(video, owner="ep1")) == video


@pytest.mark.parametrize("name", ["page.html", "image.svg", "notes.txt", "noextension",
                                  "clip.mp4.gz", "clip.mkv.zip"])
def test_only_an_audio_or_video_file_gets_a_token(tokens, tmp_path, name):
    # Never a page or an SVG served from the engine's own origin (as in recordings' route).
    path = _file(tmp_path, name, b"<script>alert(1)</script>")
    with pytest.raises(ValueError, match="not an audio or video file"):
        tokens.issue(path, owner="ep1")


def test_only_a_regular_file_gets_a_token(tokens, tmp_path):
    folder = tmp_path / "folder.mp4"
    folder.mkdir()
    with pytest.raises(ValueError, match="not a regular file"):
        tokens.issue(folder, owner="ep1")


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX FIFOs")
def test_a_fifo_gets_no_token(tokens, tmp_path):
    # Serving a FIFO would block a worker forever.
    fifo = tmp_path / "pipe.mp4"
    os.mkfifo(fifo)
    with pytest.raises(ValueError, match="not a regular file"):
        tokens.issue(fifo, owner="ep1")


def test_a_missing_or_relative_path_gets_no_token_and_the_error_names_no_path(tokens, tmp_path):
    # Spec §6.5: accepted paths are fully qualified. Spec §6.8: an error may be logged.
    for path in (tmp_path / "secret-title.mp4", Path("secret-title.mp4"),
                 tmp_path / "secret\x00title.mp4"):
        with pytest.raises(ValueError) as exc:
            tokens.issue(path, owner="ep1")
        assert "secret" not in str(exc.value) and str(tmp_path) not in str(exc.value)


def test_a_relative_path_gets_no_token_even_when_the_file_exists(tokens, tmp_path, monkeypatch):
    # Spec §6.5: accepted paths are fully qualified, so the working directory never decides.
    _file(tmp_path, "clip.mp4")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="must be absolute"):
        tokens.issue(Path("clip.mp4"), owner="ep1")


@pytest.mark.parametrize(
    "name, expected",
    [("a.mkv", "video/x-matroska"), ("A.MKV", "video/x-matroska"), ("a.m4a", "audio/mp4"),
     ("a.mp4", "video/mp4"), ("a.mp3", "audio/mpeg"), ("a.webm", "video/webm"),
     ("a.html", None), ("a.svg", None), ("a", None), ("a.mp4.gz", None)],
)
def test_the_media_type_is_audio_or_video_and_fixed_for_the_editors_formats(name, expected):
    # Python's mimetypes table differs by OS (it reads the system's files): .mkv and .m4a are
    # fixed here, since the editor plays both.
    assert media.media_type(Path(name)) == expected


# ---- revocation and swapped files ------------------------------------------------------------


def test_revoking_an_owner_revokes_only_its_tokens(tokens, client, tmp_path):
    # Plan Decision 1: closing an episode revokes its tokens; another episode's still play.
    video, audio, other = (_file(tmp_path, n) for n in ("v.mp4", "a.m4a", "o.mp4"))
    t1, t2 = tokens.issue(video, owner="ep1"), tokens.issue(audio, owner="ep1")
    t3 = tokens.issue(other, owner="ep2")
    tokens.revoke_owner("ep1")
    assert [client.get(f"/media/{t}").status_code for t in (t1, t2, t3)] == [404, 404, 200]
    assert tokens.resolve(t1) is None and tokens.resolve(t3) == other
    tokens.revoke_owner("no-such-episode")  # nothing to revoke is fine
    assert tokens.resolve(t3) == other


def test_a_file_replaced_since_the_token_was_issued_is_never_served(tokens, client, tmp_path):
    # Spec §6.5: the token records (dev, inode, size), so another file put in its place, even of
    # the same size, isn't served.
    video = _file(tmp_path, "clip.mp4")
    token = tokens.issue(video, owner="ep1")
    os.replace(_file(tmp_path, "planted.mp4", b"\xff" * len(BODY)), video)
    assert client.get(f"/media/{token}").status_code == 404
    assert tokens.resolve(token) is None


def test_a_file_rewritten_in_place_to_another_size_is_never_served(tokens, client, tmp_path):
    video = _file(tmp_path, "clip.mp4")
    token = tokens.issue(video, owner="ep1")
    with video.open("ab") as f:
        f.write(b"more")
    assert client.get(f"/media/{token}").status_code == 404


def test_a_file_deleted_since_is_404_not_500(tokens, client, tmp_path):
    video = _file(tmp_path, "clip.mp4")
    token = tokens.issue(video, owner="ep1")
    video.unlink()
    assert client.get(f"/media/{token}").status_code == 404


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges on Windows")
def test_a_symlink_pointed_elsewhere_since_is_never_served(tokens, client, tmp_path):
    real = _file(tmp_path, "real.mp4")
    other = _file(tmp_path, "other.mp4")
    link = tmp_path / "link.mp4"
    link.symlink_to(real)
    token = tokens.issue(link, owner="ep1")
    assert client.get(f"/media/{token}").content == BODY  # the file it points at
    link.unlink()
    link.symlink_to(other)
    assert client.get(f"/media/{token}").status_code == 404


# ---- the route -------------------------------------------------------------------------------


def test_media_is_served_whole_and_by_range(tokens, client, tmp_path):
    token = tokens.issue(_file(tmp_path, "clip.mp4"), owner="ep1")
    full = client.get(f"/media/{token}")
    assert full.status_code == 200 and full.content == BODY
    assert full.headers["content-type"] == "video/mp4"
    assert full.headers["accept-ranges"] == "bytes"
    part = client.get(f"/media/{token}", headers={"Range": "bytes=0-99"})
    assert part.status_code == 206
    assert part.headers["content-range"] == f"bytes 0-99/{len(BODY)}"
    assert part.content == BODY[:100]
    tail = client.get(f"/media/{token}", headers={"Range": "bytes=1000-"})
    assert tail.status_code == 206 and tail.content == BODY[1000:]


def test_a_range_past_the_end_is_416_not_500(tokens, client, tmp_path):
    token = tokens.issue(_file(tmp_path, "clip.mp4"), owner="ep1")
    r = client.get(f"/media/{token}", headers={"Range": "bytes=999999999-"})
    assert r.status_code == 416


def test_head_answers_the_headers_without_the_body(tokens, client, tmp_path):
    token = tokens.issue(_file(tmp_path, "clip.mkv"), owner="ep1")
    r = client.head(f"/media/{token}")
    assert r.status_code == 200 and r.content == b""
    assert r.headers["content-type"] == "video/x-matroska"
    assert r.headers["content-length"] == str(len(BODY))


@pytest.mark.parametrize(
    "token",
    ["", "x", "..", "%2e%2e", secrets.token_urlsafe(32)],
    ids=["empty", "short", "dots", "encoded-dots", "unknown"],
)
def test_an_unknown_token_is_404_and_echoes_nothing(tokens, client, tmp_path, token):
    live = tokens.issue(_file(tmp_path, "clip.mp4"), owner="ep1")
    r = client.get(f"/media/{token}")
    assert r.status_code == 404
    assert live.encode() not in r.content


def test_a_near_miss_of_a_live_token_is_404(tokens, client, tmp_path):
    live = tokens.issue(_file(tmp_path, "clip.mp4"), owner="ep1")
    for near in (live + "x", live[:-1], live.upper() if live.upper() != live else live + "A"):
        assert client.get(f"/media/{near}").status_code == 404


def test_the_file_name_is_in_no_header_and_the_file_plays_inline(tokens, client, tmp_path):
    token = tokens.issue(_file(tmp_path, "Secret Title S01E01.mp4"), owner="ep1")
    r = client.get(f"/media/{token}")
    assert r.headers["content-disposition"] == "inline"
    assert not any(b"Secret" in k + v for k, v in r.headers.raw)


@pytest.mark.parametrize(
    "folder, name",
    [
        ("日本語のドラマ", "第01話 字幕.mkv"),
        # A right-to-left override in the folder name: written as escapes, which ruff requires.
        ("Épisodes \u202efdp.exe\u202c", "Épisode 01 – l’été.mp4"),
        ("🎬 Films", "Clip 🎞️ 01.m4a"),
    ],
    ids=["cjk", "accents-and-bidi", "emoji"],
)
def test_a_path_with_non_ascii_bidi_or_emoji_characters_plays(tokens, client, tmp_path, caplog,
                                                              folder, name):
    # Review Focus 1: it opens and plays through /media/, and the path goes nowhere else.
    caplog.set_level(logging.DEBUG)
    path = _file(tmp_path / folder, name)
    token = tokens.issue(path, owner="ep1")
    full = client.get(f"/media/{token}")
    part = client.get(f"/media/{token}", headers={"Range": "bytes=10-19"})
    assert (full.status_code, full.content) == (200, BODY)
    assert (part.status_code, part.content) == (206, BODY[10:20])
    for r in (full, part):
        raw = b"".join(k + v for k, v in r.headers.raw).decode("latin-1")
        assert folder not in raw and name not in raw
    assert not any(folder in rec.getMessage() or name in rec.getMessage() for rec in caplog.records)


def test_every_media_answer_carries_the_media_headers_through_the_guard(tokens, client, tmp_path):
    # Spec §6.3. The headers are WriteGuard's (Task 8); 404 and 416 are under /media/ too.
    token = tokens.issue(_file(tmp_path, "clip.mp4"), owner="ep1")
    answers = [
        client.get(f"/media/{token}"),
        client.get(f"/media/{token}", headers={"Range": "bytes=0-9"}),
        client.get(f"/media/{token}", headers={"Range": "bytes=999999999-"}),
        client.get("/media/unknown"),
    ]
    assert [r.status_code for r in answers] == [200, 206, 416, 404]
    for r in answers:
        assert {k: r.headers.get(k) for k in MEDIA} == MEDIA
        assert r.headers.get_list("content-security-policy") == ["sandbox"]
```

- [ ] **Step 2: Run it; watch it fail.** `uv run pytest tests/test_web_media.py -q`. Expected:
  `E   ImportError: cannot import name 'media' from 'vid2sub.web' (…/src/vid2sub/web/__init__.py)`,
  then `1 error in 0.20s`.

- [ ] **Step 3: Write the code,** `src/vid2sub/web/media.py`:

```python
"""Media tokens and `/media/{token}`: the browser plays a video, or its playback audio, by an
unguessable token, never by its path (spec §6.3, §6.5).

A token is `secrets.token_urlsafe(32)`, bound to the engine's launch rather than a Shiny session,
because a `/media/` request carries only the launch cookie (plan Decision 1). Tokens live in
memory, so they die with the engine, and closing an episode revokes its own (`revoke_owner`).
Only an absolute path to a regular audio or video file is issued one, as recordings' media route
allowed only audio and video: never a page or an SVG served from the engine's origin. Each token
records the file's (device, inode, size), so a file replaced or rewritten since is never served.
Paths reach no URL, header, error message or log (spec §6.8). A token is looked up in a dict:
its hash reveals nothing usable about 256 random bits, so no constant-time compare is needed.

Starlette's FileResponse answers Range with 206 and a range past the end with 416. It opens the
file by path just after the check, so a swap in that instant isn't caught; whoever can do that
can already write the user's files. WriteGuard adds /media/'s headers (spec §6.3).
"""

from __future__ import annotations

import mimetypes
import os
import secrets
import stat
import threading
from dataclasses import dataclass
from pathlib import Path

from starlette.requests import Request
from starlette.responses import FileResponse, PlainTextResponse, Response
from starlette.routing import BaseRoute, Route

# Python's mimetypes table differs by OS and version (it reads the system's own files too), so
# the types the editor plays and Python may not know are fixed here.
_TYPES = {".mkv": "video/x-matroska", ".m4a": "audio/mp4"}


def media_type(path: Path) -> str | None:
    """The type `/media/` serves `path` as, from its name: audio/* or video/*, else None. A
    compressed name (`.mp4.gz`) is None: the browser would get the archive's bytes."""
    kind = _TYPES.get(path.suffix.lower())
    if kind is None:
        kind, encoding = mimetypes.guess_type(path.name)
        if encoding is not None:
            return None
    return kind if kind and kind.startswith(("audio/", "video/")) else None


def _identity(st: os.stat_result) -> tuple[int, int, int]:
    return (st.st_dev, st.st_ino, st.st_size)


@dataclass(frozen=True)
class _Issued:
    path: Path
    owner: str
    media_type: str
    identity: tuple[int, int, int]  # (st_dev, st_ino, st_size) when issued


class MediaTokens:
    """The media tokens this launch has issued. Thread-safe: the editor's session issues and
    revokes them while the route resolves them in a worker thread."""

    def __init__(self) -> None:
        self._issued: dict[str, _Issued] = {}
        self._lock = threading.Lock()

    def issue(self, path: Path, *, owner: str) -> str:
        """A new token for `path`, revoked with `owner` (the episode's id). `path` must be an
        absolute path to a regular audio or video file; otherwise ValueError, naming no path."""
        if not path.is_absolute():
            raise ValueError("a media path must be absolute")
        kind = media_type(path)
        if kind is None:
            raise ValueError("not an audio or video file")
        try:
            st = os.stat(path)  # follows a symlink: the identity is the file it points at
        except (OSError, ValueError):  # missing, unreadable, or a NUL in the name
            raise ValueError("the media file can't be read") from None
        if not stat.S_ISREG(st.st_mode):
            raise ValueError("not a regular file")
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._issued[token] = _Issued(path, owner, kind, _identity(st))
        return token

    def resolve(self, token: str) -> Path | None:
        """The file `token` serves, or None when it is unknown, revoked, or the file was replaced,
        resized or removed since it was issued."""
        live = self._live(token)
        return live[0].path if live else None

    def revoke_owner(self, owner: str) -> None:
        """Revoke every token issued for `owner`."""
        with self._lock:
            self._issued = {t: i for t, i in self._issued.items() if i.owner != owner}

    def _live(self, token: str) -> tuple[_Issued, os.stat_result] | None:
        with self._lock:
            issued = self._issued.get(token)
        if issued is None:
            return None
        try:
            st = os.stat(issued.path)  # outside the lock: a network share can be slow
        except (OSError, ValueError):
            return None
        if not stat.S_ISREG(st.st_mode) or _identity(st) != issued.identity:
            return None
        return issued, st


def route(tokens: MediaTokens) -> BaseRoute:
    """`GET /media/{token}` (HEAD too): the file inline, with Range; 404 for a token that isn't
    live. A plain function, so Starlette runs it in a worker thread and the stat never blocks the
    event loop."""

    def serve(request: Request) -> Response:
        live = tokens._live(request.path_params["token"])
        if live is None:
            return PlainTextResponse("not found", status_code=404)
        issued, st = live
        # FileResponse writes Content-Disposition only with a filename, which would put the
        # video's title in a header; `inline` alone names nothing. The checked stat is passed
        # on, so Content-Length is the size that was checked.
        return FileResponse(
            issued.path,
            media_type=issued.media_type,
            stat_result=st,
            headers={"Content-Disposition": "inline"},
        )

    return Route("/media/{token}", serve, methods=["GET"])
```

- [ ] **Step 4: Run the checks; they pass.** `uv run pytest tests/test_web_media.py -q`.
  Expected: `41 passed`. Then `make check`. Expected: the suite's line, twice, with nothing failed
  (`623 passed, 2 skipped, 4 deselected` when this listing was built without Tasks 2–7's tests),
  `All checks passed!`, `no leaks found`. Line length: `uv run python -c "import sys; [print(f,
  i) for f in sys.argv[1:] for i, l in enumerate(open(f, encoding='utf-8'), 1) if
  len(l.rstrip()) > 100]" src/vid2sub/web/media.py tests/test_web_media.py` prints nothing.

- [ ] **Step 5: Each guard fails its tests without its fix.** `git add src/vid2sub/web/media.py
  tests/test_web_media.py`. Then, for each row, make the change in `media.py`, run
  `uv run pytest tests/test_web_media.py -q`, see it fail, and restore with
  `git checkout -- src/vid2sub/web/media.py`. The last column is what this listing's build saw.
  The device half of the identity can't be exercised without a second file system; say so.

| Guard | Change | To | Failed |
|---|---|---|---|
| the identity | in `_live`, the two lines from `if not stat.S_ISREG(st.st_mode) or _identity(st) != issued.identity:` | nothing (keep `return issued, st`) | 3 |
| the inode | `return (st.st_dev, st.st_ino, st.st_size)` | `return (st.st_dev, 0, st.st_size)` | 2 |
| the size | the same | `return (st.st_dev, st.st_ino, 0)` | 1 |
| audio or video only | `return kind if kind and kind.startswith(("audio/", "video/")) else None` | `return kind or "application/octet-stream"` | 8 |
| no compressed names | the two lines from `if encoding is not None:` | nothing | 2 |
| .mkv and .m4a fixed | `_TYPES = {".mkv": "video/x-matroska", ".m4a": "audio/mp4"}` | `_TYPES = {}` | 1 (on this Mac's Python 3.14) |
| a regular file | in `issue`, the two lines from `if not stat.S_ISREG(st.st_mode):` | nothing | 2 |
| absolute paths | the two lines from `if not path.is_absolute():` | nothing | 1 |
| no path in errors | `except (OSError, ValueError):  # missing, …` and its `raise ValueError(…) from None` | `except KeyError:` and `raise` | 1 |
| revoke one owner | `self._issued = {t: i for t, i in self._issued.items() if i.owner != owner}` | `pass` | 1 |
| only that owner | the same | `self._issued = {}` | 1 |
| random tokens | `token = secrets.token_urlsafe(32)` | `token = __import__("hashlib").sha256(str(path).encode()).hexdigest()[:43]` | 1 |
| removed file is 404 | in `_live`, the `try:`/`except` around `os.stat(issued.path)` | `st = os.stat(issued.path)` alone | 1 |
| no title in headers | `headers={"Content-Disposition": "inline"},` | `filename=issued.path.name, content_disposition_type="inline",` | 1 |
| inline really sent | the same | `content_disposition_type="inline",` | 1 |

- [ ] **Step 6: See it in a real browser** (optional, and only if Chromium is already installed
  for Playwright, as in Task 9 Step 6; how this listing was checked). Make a WebM in a folder whose name has an accent, `‮` and an emoji
  (`ffmpeg -nostdin -i tests/fixtures/speech/jfk-14s.wav -c:a libopus -b:a 48k <that folder>/clip.webm`),
  issue a token for it, serve `HostGuard(WriteGuard(Starlette(routes=[media.route(tokens), <a
  "/" route whose page is <audio src="/media/<token>">>]), LOCAL_HOSTS), LOCAL_HOSTS)` with
  uvicorn, and in a Playwright page poll `readyState` with `page.evaluate` (the page CSP refuses
  `page.wait_for_function` with a string: it is `eval`). This listing's run: duration 14.01 s,
  seeked to 10 s with no media error, the request a 206 for `bytes=0-`, no console message, and
  404 once the owner was revoked. Nothing from this step is committed.

- [ ] **Step 7: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(web): 🤖 the browser plays a video or its playback audio by an unguessable token bound to the launch, and a file swapped since is never served

src/vid2sub/web/media.py (spec §6.3, §6.5; plan Decision 1). MediaTokens.issue(path, owner=...)
takes only an absolute path to a regular file whose type is audio/* or video/* (.mkv and .m4a
fixed, since mimetypes tables differ by OS; a compressed name like .mp4.gz refused), records its
(st_dev, st_ino, st_size), and returns secrets.token_urlsafe(32); its errors name no path.
resolve() is None for an unknown or revoked token, or a file replaced, resized or removed since;
revoke_owner() revokes one episode's tokens only. Tokens are found by dict lookup, which leaks
nothing usable about 256 random bits. route() serves GET (and HEAD) /media/{token} with
FileResponse in a worker thread, passing on the checked stat; 404 otherwise.

FileResponse's content_disposition_type="inline" writes no header unless a filename is passed,
and a filename would put the video's title in a header, so the route sends
"Content-Disposition: inline" itself.

The new test failed first with: ImportError: cannot import name 'media' from 'vid2sub.web'.
Each guard was then reverted in turn and its tests failed: <the rows of Step 5, with your
counts>. The device half of the identity can't be exercised without a second file system.
<Step 6's browser run, if made.>

Docs read: Starlette's responses page (FileResponse's Range: 206, 416 for an invalid range;
content_disposition_type) and its source (Content-Disposition only with a filename, a missing
file is a RuntimeError, stat_result is used as given); its routing page (function endpoints, the
str path convertor); Python's mimetypes page (guess_type returns the encoding; it reads the
system's files and, on Windows, the registry).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 10
Co-Authored-By: <the model's own line>
```

  `git commit -F .git/COMMIT_MSG` (both files are staged from Step 5), then
  `git log -1 --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 8: Review, look forward, close.** The Tier 1 review from `$(cat .git/TASK_BASE)`
  (`AGENTS.md`, *Reviews*, with the security checklist). Worth the reviewers' time: that no
  client-supplied text ever becomes a path (the token only selects a recorded entry); that a
  page, an SVG or anything but audio or video can't be issued a token, whatever the OS's
  mimetypes table says; that a token outlives neither its episode nor the engine; that no path
  or file name reaches a header, an error message or a log; that the stat runs off the event
  loop. Known and accepted, in the module docstring: FileResponse opens the file by path just
  after the check, so a swap in that instant isn't caught. The forward review over Tasks 3, 11,
  14 and 16 (Task 3's playback audio is an `.m4a`, served as `audio/mp4`; Task 11 puts
  `media.route(rt.media)` before the Shiny mount and holds one `MediaTokens` in `Runtime.media`;
  Task 14 issues the video's token, and the playback audio's when the browser can't play the
  video's audio, with `owner=ep.id`, and turns a `ValueError` into a plain notice; closing an
  episode calls `revoke_owner(ep.id)`). The docs this task made untrue: none expected. Then the
  close, its own commit, holding this plan with this task's boxes ticked and **Now** set to
  `Task 11: The app shell and \`vid2sub serve\`, open.`; no scenario row changes (S27 waits for
  Task 14's Playwright test, S43 for Tasks 3 and 14), with the message in `.git/CLOSE_MSG`:

```text
docs(plan): 🤖 close Task 10: Media tokens and `/media/{token}`

Drift: none
Rulings: none
Phase-end: none
Forward: none
Tier: 1
Rounds: <Matt's code-review, Standards and Spec in two subagents; any re-review>
  secrets: fine | a finding | n/a: why
  permissions: fine | a finding | n/a: why
  network exposure: fine | a finding | n/a: why
  failing closed: fine | a finding | n/a: why
  injection: fine | a finding | n/a: why
  logging: fine | a finding | n/a: why
Findings: none

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 10
Co-Authored-By: <the model's own line>
```

  `git add docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md
  docs/superpowers/specs/2026-10-14-vid2sub-design.md`, `git commit -F .git/CLOSE_MSG`.

***

### Task 11: The app shell and `vid2sub serve`

**Tier:** 1 · **Scenarios:** S23

**Files:**
- Create: `src/vid2sub/web/app.py`, `src/vid2sub/web/runtime.py`, `src/vid2sub/commands/serve.py`
- Modify: `src/vid2sub/cli.py` (register `serve`)
- Test: `tests/test_web_app.py`, `tests/test_cli_serve.py`

**Interfaces:**
- Consumes: Tasks 8–10; Task 5's `LocalBackend`; Task 4's `Queue`.
- Produces: `runtime.Runtime` (dataclass: `backend`, `queue`, `media`, `config`, `keys`);
  `runtime.configure(rt: Runtime) -> None`; `runtime.current() -> Runtime`;
  `app.create_app(rt: Runtime, *, token: str, port: int, shiny_app: ASGIApp) -> ASGIApp`;
  `vid2sub serve [--port N] [--no-browser] [--config PATH]` (refuses with exit 69 and
  "build the frontend first" when `www/ui.js` is missing)

<!-- steps: written in the next pass -->

***

### Task 12: The frontend scaffold and the shinyreact server

**Tier:** 2 · **Scenarios:** S26

**Files:**
- Create: `frontend/` (package.json, vite.config.js, tsconfig.json, components.json, .nvmrc,
  scripts/check-node.mjs, src/ui.tsx, src/App.tsx, src/sr.ts, src/index.css, src/theme.css,
  src/lib/theme.ts, src/lib/utils.ts, src/components/TopBar.tsx, src/components/ThemeSwitch.tsx,
  src/build.test.ts), `_brand.yml`, `scripts/brand_css.py`, `src/vid2sub/web/server.py`,
  `src/vid2sub/web/www/fonts/`
- Modify: `Makefile` (`build`, `test-js`, `skills`, `brand`; `check` runs `test-js`), `.gitignore`
- Test: `tests/test_web_server.py`, `tests/e2e/test_csp.py`

**Interfaces:**
- Consumes: Task 11's `runtime.current()`.
- Produces: outputs `capabilities`, `status`; message `notice` (`{kind: "info" | "error",
  text}`); `frontend/src/sr.ts` re-exports of shinyreact's hooks.

<!-- steps: written in the next pass -->

***

### Task 13: The end-to-end harness and the demo

**Tier:** 2 · **Scenarios:** S26

**Files:**
- Create: `demo/` (the canned sidecar, `CREDITS.md`), `src/vid2sub/web/demo.py`,
  `tests/e2e/conftest.py`, `tests/e2e/test_shell.py`, `tests/test_demo_guard.py`,
  `tests/fixtures/hostile/`
- Modify: `src/vid2sub/commands/serve.py` (`--demo`), `pyproject.toml` (the `e2e` marker),
  `Makefile` (`e2e`, `demo`)

**Interfaces:**
- Produces: `demo.prepare(tools: Tools) -> Path` (a temporary copy of `demo/` with its MP4 muxed);
  `vid2sub serve --demo`; the `server` and `page` e2e fixtures (a running demo server, its URL,
  and a page already through `/auth`).

<!-- steps: written in the next pass -->

***

### Task 14: The editor view

**Tier:** 2 · **Scenarios:** S27, S37

**Files:**
- Create: `frontend/src/components/{Editor,Player,CaptionOverlay,CueList,CueRow,Flags}.tsx`,
  `frontend/src/lib/{cues,overlay}.ts` and their `.test.ts`
- Modify: `src/vid2sub/web/server.py` (input `open`, output `episode`), `frontend/src/App.tsx`
- Test: `tests/test_web_server.py`, `tests/e2e/test_editor_view.py`

<!-- steps: written in the next pass -->

***

### Task 15: Editing in the editor

**Tier:** 2 · **Scenarios:** S28, S33, S37

**Files:**
- Create: `frontend/src/lib/keys.ts` (+ test), `frontend/src/components/FindReplace.tsx`
- Modify: `src/vid2sub/web/server.py` (inputs `edit`, `undo`, `redo`), the editor components
- Test: `tests/e2e/test_editing.py`

<!-- steps: written in the next pass -->

***

### Task 16: Saving

**Tier:** 2 · **Scenarios:** S29, S31, S32, S34

**Files:**
- Create: `frontend/src/lib/draft.ts` (+ test), `frontend/src/components/{SaveBar,ConflictPicker}.tsx`
- Modify: `src/vid2sub/web/server.py` (inputs `save`, `resolve`; message `save_result`)
- Test: `tests/e2e/test_saving.py`

<!-- steps: written in the next pass -->

***

### Task 17: Retranslating

**Tier:** 2 · **Scenarios:** S30

**Files:**
- Modify: `src/vid2sub/web/server.py` (input `retranslate`), the editor components
- Test: `tests/e2e/test_retranslate.py`

<!-- steps: written in the next pass -->

***

### Task 18: The settings drawer

**Tier:** 1 · **Scenarios:** S35

**Files:**
- Create: `frontend/src/components/SettingsDrawer.tsx`, `src/vid2sub/web/settings.py`
- Modify: `src/vid2sub/web/server.py` (output `settings`; inputs `typed_key`, `endpoint_test`;
  message `endpoint_test_result`)
- Test: `tests/test_web_settings.py`, `tests/e2e/test_settings.py`

<!-- steps: written in the next pass -->

***

### Task 19: The Jobs page

**Tier:** 2 · **Scenarios:** S36

**Files:**
- Create: `frontend/src/components/JobsPage.tsx`
- Modify: `src/vid2sub/web/server.py` (output `jobs`; inputs `jobs_submit`, `job_cancel`),
  `src/vid2sub/web/runtime.py` (the job runner)
- Test: `tests/test_web_jobs.py`, `tests/e2e/test_jobs.py`

<!-- steps: written in the next pass -->

***

### Task 20: The Spark's Qwen3-ASR endpoint

**Tier:** 2 · **Scenarios:** S22 · Steps 1 and 21 are **[Dan]**, on his Mac with local-ai's
`make tunnel`, once local-ai serves Qwen3-ASR with its forced aligner

**Why it is built this way** (read 2026-10-23): mlx-qwen3-asr's `docs/server/API-SPEC.md`
documents `verbose_json` as `task`, `language` (lower-cased name, `"english"`), `duration` (from
the last timestamp), `text` and top-level `words` of `{word, start, end}`, and never mentions
`timestamp_granularities`. Its source (0.4.4; `server.py` on main is the same) also sends
`segments`, which are Qwen's own 30 s pieces, and declares no `timestamp_granularities` field.
The aligner keeps only letters, digits and apostrophes (`forced_aligner.py`, `is_kept_char`), so
units carry no punctuation, although the API spec's example shows `"text."`. Its alias table maps
`en`, `zh`, `ja` and `ko` to Qwen's names but passes `yue` through unchanged. So the parser hands
the words to `parse_qwen`, as the Mac's engine does, and the engine sends Qwen's language names.

**Files:**
- Create: `tests/fixtures/qwen-endpoint/README.md`,
  `tests/fixtures/qwen-endpoint/documented-shape.en.json`, `tests/test_parse_qwen_endpoint.py`,
  `tests/test_spark_qwen.py`; from Dan's recording, `tests/fixtures/qwen-endpoint/jfk-14s.en.json`,
  `jfk-14s-detected.en.json` and, if there is a public-domain Cantonese clip, `<name>.yue.json`
- Modify: `src/vid2sub/parse/words.py` (`attach_punctuation`), `src/vid2sub/parse/qwen.py`,
  `src/vid2sub/config.py` (`ModelEntry.parser`), `src/vid2sub/engines/endpoint.py`,
  `src/vid2sub/example.toml` and `vid2sub.example.toml` (a commented `[models.spark-qwen]`),
  `src/vid2sub/catalog.py` (`runs_on`, Step 23), `tests/test_parse_words.py`,
  `tests/test_endpoint_engine.py`, `tests/test_config.py`, `tests/test_pipeline.py`,
  `tests/test_live_spark.py`, `tests/fixtures/CREDITS.md`, `tests/README.md`, `README.md`,
  `docs/architecture.md`, the spec
- Unchanged: `src/vid2sub/parse/__init__.py` holds only `ParsedChunk` and `ParseError`, no parser
  registry; the endpoint engine picks the parser, as it does for whisper.cpp and OpenAI.

**Interfaces:**
- Consumes: `vid2sub.parse.qwen.parse_qwen(result, *, duration_ms)`;
  `vid2sub.parse.words.attach_punctuation`; `vid2sub.subs.langs.get(code).qwen`, `langs.LANGS`,
  `langs.UnknownLanguage`; `vid2sub.catalog.CATALOG[id].max_chunk_s` (180 for both Qwen ids);
  `clients.call_transcription`; `detect.candidates`, `detect.choose_detector`, `catalog.suggest`;
  `tests/fakes.FakeServer`, `closed_port_url`.
- Produces:
  - `vid2sub.parse.qwen.parse_qwen_endpoint(data: Any, *, duration_ms: int) -> ParsedChunk`:
    `language` a Qwen name in any case or an ISO code; top-level `words` through `parse_qwen`;
    `segments` ignored; no `words` gives one unaligned segment over the chunk; `ParseError` when
    `text` isn't a string or `words` isn't a list.
  - `ModelEntry.parser: Literal["whisper.cpp", "openai", "qwen3-asr"] | None`
  - `EndpointEngine` for `parser="qwen3-asr"`: `name == "qwen3-asr"`; `max_chunk_s` from the
    catalog, else 180 (`endpoint.DEFAULT_CHUNK_S`); `language` sent as Qwen's name
    (`"Cantonese"`), and a language Qwen has no name for refused before anything is sent
    (`EngineError("unavailable")`); `timestamp_granularities=["word"]` (`endpoint.GRANULARITIES`).
  - `attach_punctuation` finds a unit with punctuation between its characters (`"wellknown"`
    gives `" well-known"`), earliest match first.
  - The starter's commented `[models.spark-qwen]`: `catalog = "qwen3-asr-1.7b"`,
    `endpoint = "spark"`, `model = "qwen3-asr-1.7b"`, `parser = "qwen3-asr"`, `local = true`.

The `make check` counts below come from a clone without Tasks 2–19, which add their own tests;
yours are higher by those. What matters is no failure, ruff's `All checks passed!` and
gitleaks' `no leaks found`.

- [ ] **Step 0: Record the base:** `git rev-parse HEAD > .git/TASK_BASE`.
- [ ] **Step 1 [Dan]: Record the Spark's answers.** On Dan's Mac, with local-ai's `make tunnel`
  running and `SPARK_API_KEY` exported, from the repo's root. The key is passed by name and never
  printed or written down. First, does local-ai serve Qwen3-ASR?

```bash
curl -sS -H "Authorization: Bearer $SPARK_API_KEY" http://127.0.0.1:9100/v1/models \
  | uv run python -c "import json, sys; print(sorted(m['id'] for m in json.load(sys.stdin)['data']))"
```

  - **The list has no Qwen3-ASR 1.7B:** set the plan's **Now** to
    `waiting on Dan: Task 20, Step 1`, write `.git/WIP_MSG`, then
    `git add docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md` and
    `git commit -F .git/WIP_MSG`. Then go on with Step 2: Steps 2–20 don't need the recording,
    and Step 21 waits for it.

```text
chore(plan): 🤖 wip Task 20: waiting on Dan for the Spark's Qwen3-ASR

Done so far: Step 0, the base recorded.
Stopped at: Step 1: local-ai doesn't list Qwen3-ASR yet, so there is nothing to record. Steps
2-20 go on against the documented shape; Step 21 waits for the recording.
Tests: make check green at the base.

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 20
Co-Authored-By: <the model's own line>
```

  - **It lists it:** Dan runs these, the same commands as the fixture README written in Step 6,
    with `MODEL` set to the 1.7B's id exactly as printed. Note the date, the 1.7B's id and
    whether the 0.6B is listed, for Steps 22 and 23. An id other than `qwen3-asr-1.7b` is drift
    (Step 22). The answers stay untracked until Step 22 commits them: stage by path, never
    `git add -A`.

```bash
mkdir -p tests/fixtures/qwen-endpoint
MODEL=qwen3-asr-1.7b   # the 1.7B's id, exactly as the list above prints it
OUT="${TMPDIR:-/tmp}/vid2sub-qwen" && mkdir -p "$OUT"
ffmpeg -nostdin -v error -i tests/fixtures/speech/jfk-14s.wav -ac 1 -ar 16000 \
  -map_metadata -1 -fflags +bitexact -c:a flac -y "$OUT/chunk-0000.flac"
record() {  # record LANGUAGE-NAME-OR-EMPTY FIXTURE-NAME
  lang=(); [ -n "$1" ] && lang=(-F "language=$1")
  curl -sS --fail-with-body --max-time 900 -o "$OUT/answer.json" -w 'HTTP %{http_code}\n' \
    -H "Authorization: Bearer $SPARK_API_KEY" \
    -F "file=@$OUT/chunk-0000.flac;filename=chunk-0000.flac;type=audio/flac" \
    -F "model=$MODEL" "${lang[@]}" -F "response_format=verbose_json" \
    -F "timestamp_granularities[]=word" \
    http://127.0.0.1:9100/v1/audio/transcriptions \
  && uv run python -m json.tool --indent 2 --no-ensure-ascii "$OUT/answer.json" \
       "tests/fixtures/qwen-endpoint/$2"
}
record English jfk-14s.en.json
record "" jfk-14s-detected.en.json   # no language: what detection reads
```

  Each `record` prints `HTTP 200`. A Cantonese clip, only if Dan has a public-domain one (its
  source and licence go in `tests/fixtures/CREDITS.md` in Step 22; the audio isn't committed):

```bash
CLIP=/path/to/the-public-domain-cantonese-clip
NAME=short-ascii-name
ffmpeg -nostdin -v error -i "$CLIP" -t 60 -ac 1 -ar 16000 \
  -map_metadata -1 -fflags +bitexact -c:a flac -y "$OUT/chunk-0000.flac"
record Cantonese "$NAME.yue.json"
```

- [ ] **Step 2: Write the failing test,** appended to the end of `tests/test_parse_words.py`:

```python


def test_a_unit_the_aligner_stripped_of_inner_punctuation_still_finds_its_word():
    # Qwen3-ForcedAligner keeps only letters, digits and apostrophes (mlx-qwen3-asr 0.4.4,
    # forced_aligner.py `is_kept_char`), so "well-known" comes back as "wellknown".
    words = attach_punctuation("A well-known man paid 3.5 dollars.",
                               [("A", 0, 1), ("wellknown", 1, 2), ("man", 2, 3), ("paid", 3, 4),
                                ("35", 4, 5), ("dollars", 5, 6)])
    assert [w.text for w in words] == ["A", " well-known", " man", " paid", " 3.5", " dollars."]
    assert all(w.timed for w in words)


def test_a_stripped_unit_takes_its_own_place_not_a_later_exact_match():
    words = attach_punctuation("3.5, then 35.", [("35", 0, 1), ("then", 1, 2), ("35", 2, 3)])
    assert [w.text for w in words] == ["3.5,", " then", " 35."]
```

- [ ] **Step 3: Run it; watch it fail.** `uv run pytest tests/test_parse_words.py -q`. Expected:
  `2 failed, 14 passed`, each with `E       TypeError: 'NoneType' object is not iterable`.
- [ ] **Step 4: Write the code,** `src/vid2sub/parse/words.py`, in full:

```python
"""Helpers shared by the parsers: tokens into words, untimed words, and punctuation (spec §9.2).

whisper.cpp's "words" are BPE tokens, so they're merged into words on the leading space; a CJK
token is a word of its own. Aligners (Qwen's, OpenAI's word list) return units without the
text's spaces and punctuation, so `attach_punctuation` maps them back: closing punctuation joins
the word before it, a space and any opening punctuation join the word after, and punctuation
inside a word ("well-known", "3.5") stays in it. A word with no time sits at the previous word's
end and is marked untimed (recordings' rule).
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections.abc import Sequence
from typing import Any

from vid2sub.subs.model import Word
from vid2sub.subs.text import NO_LINE_END, is_cjk

RawToken = tuple[str, int | None, int | None, float | None]
# What may sit between a unit's characters in the text: anything but a letter, digit, apostrophe
# or space (an aligner unit never spans a space).
INNER_PUNCTUATION = r"[^\w\s']*"


def ms(seconds: Any) -> int | None:
    if seconds is None or isinstance(seconds, bool):
        return None
    try:
        value = float(seconds)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value) or value < 0:
        return None
    return round(value * 1000)


def _is_opening(text: str) -> bool:
    body = text.strip()
    return bool(body) and all(ch in NO_LINE_END for ch in body)


def _is_closing(text: str) -> bool:
    body = text.strip()
    return bool(body) and all(unicodedata.category(ch).startswith("P") and ch not in NO_LINE_END
                              for ch in body)


def fill_untimed(raw: Sequence[Sequence[Any]], start_ms: int = 0) -> list[Word]:
    words: list[Word] = []
    prev_end = start_ms
    for text, start, end, prob in raw:
        if start is None or end is None or end < start:
            words.append(Word(text=text, start_ms=prev_end, end_ms=prev_end, prob=prob,
                              timed=False))
        else:
            words.append(Word(text=text, start_ms=start, end_ms=end, prob=prob))
            prev_end = end
    return words


def tokens_to_words(tokens: Sequence[RawToken], *, start_ms: int = 0) -> list[Word]:
    merged: list[list[Any]] = []
    for text, start, end, prob in tokens:
        if not text or not text.strip():
            continue
        head = text.lstrip()
        last = merged[-1][0].rstrip() if merged else ""
        if not merged or text[0].isspace():
            starts_word = True
        elif _is_opening(merged[-1][0]) or _is_closing(text):
            starts_word = False
        else:
            starts_word = is_cjk(head[0]) or (bool(last) and is_cjk(last[-1]))
        if starts_word:
            merged.append([text, start, end, prob])
            continue
        current = merged[-1]
        current[0] += text
        if end is not None:
            current[2] = end
        if prob is not None:
            current[3] = prob if current[3] is None else min(current[3], prob)
    return fill_untimed(merged, start_ms)


def _unit_pattern(needle: str) -> re.Pattern[str]:
    """The unit as it may appear in the text: any case, with punctuation between its characters.

    Qwen3-ForcedAligner keeps only letters, digits and apostrophes (mlx-qwen3-asr 0.4.4,
    `ForcedAlignTextProcessor.is_kept_char`), so "well-known" comes back as "wellknown" and "3.5"
    as "35". A plain search would miss them and leave the whole chunk unaligned.
    """
    return re.compile(INNER_PUNCTUATION.join(re.escape(ch) for ch in needle), re.IGNORECASE)


def attach_punctuation(text: str, units: Sequence[tuple[str, int | None, int | None]], *,
                       start_ms: int = 0) -> list[Word] | None:
    raw: list[list[Any]] = []
    pos = 0
    for utext, start, end in units:
        needle = utext.strip()
        if not needle:
            continue
        match = _unit_pattern(needle).search(text, pos)
        if match is None:
            return None
        found, after = match.span()
        gap = text[pos:found]
        lead = ""
        if gap:
            space = next((i for i, ch in enumerate(gap) if ch.isspace()), None)
            if space is not None:
                closing, lead = gap[:space], " " + gap[space:].strip()
            else:
                k = len(gap)
                while k > 0 and gap[k - 1] in NO_LINE_END:
                    k -= 1
                closing, lead = gap[:k], gap[k:]
            if closing:
                if raw:
                    raw[-1][0] += closing
                else:
                    lead = closing + lead
        raw.append([lead + text[found:after], start, end, None])
        pos = after
    if not raw:
        return None
    raw[-1][0] += text[pos:].rstrip()
    return fill_untimed(raw, start_ms)
```

- [ ] **Step 5: Run the checks; they pass.** `make check`. Expected: `467 passed, 2 skipped,
  4 deselected` twice (here; yours is your base's count plus 2), `All checks passed!`,
  `no leaks found`. Commit: write the message to `.git/COMMIT_MSG`:

```text
fix(parse): 🤖 a word the aligner stripped of inner punctuation still finds its place in the text

Qwen3-ForcedAligner keeps only letters, digits and apostrophes, so "well-known" comes back as the
unit "wellknown" and "3.5" as "35". attach_punctuation searched for the unit verbatim, found
nothing, and returned None, so one hyphenated word or decimal left a whole chunk (up to 180 s)
unaligned, through the Mac's engine today and the Spark's endpoint next. It now searches for the
unit with any case and any punctuation between its characters, earliest match first, and keeps
the text's characters in the word. Escaped from M1 Task 14 (parse_qwen), found while building
Phase 2 Task 20 from mlx-qwen3-asr's source.

The new tests failed first with: TypeError: 'NoneType' object is not iterable (both).
Docs read: mlx-qwen3-asr 0.4.4 forced_aligner.py (ForcedAlignTextProcessor.is_kept_char,
clean_token, tokenize_space_lang); Python's re docs (re.escape, IGNORECASE, \w).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 20
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/parse/words.py tests/test_parse_words.py`,
  `git commit -F .git/COMMIT_MSG`, then `git log -1 --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 6: Write the failing test, its fixture, the fixture README and the credit.**
  `tests/test_parse_qwen_endpoint.py`:

```python
"""Qwen3-ASR's `verbose_json` from an OpenAI-shaped server, as timed words (spec §9.2, §22.3, S22).

The contract tests run over every answer in `ANSWERS`; `tests/fixtures/qwen-endpoint/README.md`
says how each was made. A file is named `<clip>.<the language vid2sub should read>.json`.
"""

import json
from pathlib import Path

import pytest

from vid2sub.parse import ParseError
from vid2sub.parse.qwen import parse_qwen_endpoint

FIXTURES = Path(__file__).parent / "fixtures" / "qwen-endpoint"
ANSWERS = ["documented-shape.en.json"]
CHUNK_MS = 180_000  # the longest chunk vid2sub sends a Qwen model (catalog max_chunk_s)


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", ANSWERS)
def test_an_answer_has_the_text_language_and_top_level_words_the_parser_reads(name):
    data = load(name)
    assert isinstance(data["text"], str) and data["text"].strip()
    assert isinstance(data["language"], str) and data["language"]
    assert data["words"]
    for w in data["words"]:
        assert isinstance(w["word"], str) and w["word"].strip()
        assert isinstance(w["start"], int | float) and isinstance(w["end"], int | float)


@pytest.mark.parametrize("name", ANSWERS)
def test_every_unit_of_an_answer_becomes_a_timed_word_carrying_the_texts_punctuation(name):
    data = load(name)
    parsed = parse_qwen_endpoint(data, duration_ms=CHUNK_MS)
    assert parsed.language == name.rsplit(".", 2)[1]
    assert parsed.language_probs == {parsed.language: 1.0}
    [seg] = parsed.segments
    assert seg.aligned and len(seg.words) == len(data["words"])
    assert all(w.timed and 0 <= w.start_ms <= w.end_ms for w in seg.words)
    assert [w.start_ms for w in seg.words] == sorted(w.start_ms for w in seg.words)
    assert "".join(w.text for w in seg.words) == seg.text
    assert " ".join(seg.text.split()) == " ".join(data["text"].split())


def test_the_documented_shape_gives_the_clips_words_with_their_commas_and_full_stops():
    seg = parse_qwen_endpoint(load("documented-shape.en.json"), duration_ms=14_000).segments[0]
    assert [w.text for w in seg.words[:6]] == ["be", " very", " brief.", " I", " am", " delighted"]
    assert seg.words[8].text == " here," and seg.words[19].text == " occasion."
    assert (seg.start_ms, seg.end_ms) == (320, 13_840)


def test_the_api_specs_own_example_keeps_its_one_full_stop():
    # mlx-qwen3-asr's docs/server/API-SPEC.md, verbatim: its last unit carries the full stop.
    data = {"task": "transcribe", "language": "english", "duration": 5.1,
            "text": "The transcribed text.",
            "words": [{"word": "The", "start": 0.0, "end": 0.3},
                      {"word": "transcribed", "start": 0.3, "end": 0.8},
                      {"word": "text.", "start": 0.8, "end": 1.2}]}
    seg = parse_qwen_endpoint(data, duration_ms=5_100).segments[0]
    assert [w.text for w in seg.words] == ["The", " transcribed", " text."]
    assert (seg.start_ms, seg.end_ms) == (0, 1_200)


def test_a_cantonese_answer_reads_as_yue_with_its_chinese_punctuation_attached():
    text = "我哋去飲茶，好唔好？"
    data = {"language": "cantonese", "text": text,
            "words": [{"word": ch, "start": i * 0.2, "end": i * 0.2 + 0.2}
                      for i, ch in enumerate("我哋去飲茶好唔好")]}
    parsed = parse_qwen_endpoint(data, duration_ms=2_000)
    assert parsed.language == "yue"
    assert [w.text for w in parsed.segments[0].words] == [
        "我", "哋", "去", "飲", "茶，", "好", "唔", "好？"]


@pytest.mark.parametrize(("language", "code"), [
    ("english", "en"), ("English", "en"), ("en", "en"), ("cantonese", "yue"), ("yue", "yue"),
    ("Chinese", "zh"), ("zh", "zh"), ("japanese", "ja"),
])
def test_a_language_given_as_a_name_or_a_code_in_any_case_is_read(language, code):
    data = {"language": language, "text": "hi", "words": [{"word": "hi", "start": 0, "end": 0.5}]}
    assert parse_qwen_endpoint(data, duration_ms=1_000).language == code


@pytest.mark.parametrize("language", ["klingon", "", None])
def test_an_unknown_or_missing_language_gives_none_and_no_probabilities(language):
    parsed = parse_qwen_endpoint({"language": language, "text": "hi"}, duration_ms=1_000)
    assert parsed.language is None and parsed.language_probs == {}


def test_an_answer_without_words_is_one_unaligned_segment_spanning_the_chunk():
    parsed = parse_qwen_endpoint({"language": "english", "text": "Hello."}, duration_ms=1_500)
    [seg] = parsed.segments
    assert seg.words == () and (seg.start_ms, seg.end_ms) == (0, 1_500) and seg.text == "Hello."


def test_silence_gives_no_segments():
    assert parse_qwen_endpoint({"language": "english", "text": ""},
                               duration_ms=1_000).segments == ()


@pytest.mark.parametrize("data", [
    [], "text", {"words": []}, {"text": 3}, {"text": "hi", "words": "hi"},
])
def test_an_answer_that_is_not_qwens_verbose_json_is_refused(data):
    with pytest.raises(ParseError):
        parse_qwen_endpoint(data, duration_ms=1_000)
```

  `tests/fixtures/qwen-endpoint/documented-shape.en.json`, exactly (two spaces of indent, one
  word per line):

```json
{
  "task": "transcribe",
  "language": "english",
  "duration": 13.84,
  "text": "be very brief. I am delighted to be here, and I am particularly delighted to be here on this occasion. We meet at a college noted for knowledge, in a city noted for progress, in a",
  "words": [
    {"word": "be", "start": 0.32, "end": 0.54},
    {"word": "very", "start": 0.54, "end": 0.87},
    {"word": "brief", "start": 0.87, "end": 1.26},
    {"word": "I", "start": 1.76, "end": 1.93},
    {"word": "am", "start": 1.93, "end": 2.15},
    {"word": "delighted", "start": 2.15, "end": 2.76},
    {"word": "to", "start": 2.91, "end": 3.13},
    {"word": "be", "start": 3.13, "end": 3.35},
    {"word": "here", "start": 3.35, "end": 3.68},
    {"word": "and", "start": 3.68, "end": 3.96},
    {"word": "I", "start": 3.96, "end": 4.12},
    {"word": "am", "start": 4.12, "end": 4.34},
    {"word": "particularly", "start": 4.34, "end": 5.12},
    {"word": "delighted", "start": 5.12, "end": 5.73},
    {"word": "to", "start": 5.73, "end": 5.95},
    {"word": "be", "start": 5.95, "end": 6.17},
    {"word": "here", "start": 6.17, "end": 6.5},
    {"word": "on", "start": 6.5, "end": 6.72},
    {"word": "this", "start": 6.72, "end": 7.05},
    {"word": "occasion", "start": 7.05, "end": 7.61},
    {"word": "We", "start": 8.21, "end": 8.43},
    {"word": "meet", "start": 8.43, "end": 8.76},
    {"word": "at", "start": 8.76, "end": 8.98},
    {"word": "a", "start": 8.98, "end": 9.15},
    {"word": "college", "start": 9.15, "end": 9.64},
    {"word": "noted", "start": 9.64, "end": 10.03},
    {"word": "for", "start": 10.03, "end": 10.31},
    {"word": "knowledge", "start": 10.31, "end": 10.92},
    {"word": "in", "start": 11.22, "end": 11.44},
    {"word": "a", "start": 11.44, "end": 11.6},
    {"word": "city", "start": 11.6, "end": 11.94},
    {"word": "noted", "start": 11.94, "end": 12.32},
    {"word": "for", "start": 12.32, "end": 12.6},
    {"word": "progress", "start": 12.6, "end": 13.15},
    {"word": "in", "start": 13.45, "end": 13.67},
    {"word": "a", "start": 13.67, "end": 13.84}
  ],
  "segments": [
    {"id": 0, "start": 0.0, "end": 14.0, "text": "be very brief. I am delighted to be here, and I am particularly delighted to be here on this occasion. We meet at a college noted for knowledge, in a city noted for progress, in a"}
  ]
}
```

  `tests/fixtures/qwen-endpoint/README.md`:

````markdown
# Qwen3-ASR endpoint answers

`verbose_json` answers from OpenAI-shaped Qwen3-ASR servers, read by
`vid2sub.parse.qwen.parse_qwen_endpoint` (spec §9.2, §22.3). `tests/test_parse_qwen_endpoint.py`
runs its contract tests over each file in its `ANSWERS` list. A file is named
`<clip>.<the language vid2sub should read from it>.json`.

## Written by hand

- `documented-shape.en.json` is not a recording. It follows `mlx-qwen3-asr serve` in
  mlx-qwen3-asr 0.4.4 (`server.py`, `_openai_format_response`): `task`, `language` (Qwen's name,
  lower-cased), `duration` (the last word's end), `text`, top-level `words` of
  `{"word", "start", "end"}` in seconds, and `segments`, which are Qwen's own 30 s pieces rather
  than Whisper's segments. Its `docs/server/API-SPEC.md` documents the same fields but `segments`.
  The units carry no punctuation, as the aligner's don't (`forced_aligner.py`, `is_kept_char`
  keeps letters, digits and apostrophes), although the API spec's example shows `"text."`. The
  words are the speech in `../speech/jfk-14s.wav`; the times are made up.

## Recorded from the Spark

On Dan's Mac, with local-ai's `make tunnel` running and `SPARK_API_KEY` exported, from the repo's
root. The key is passed by name and never written down. Each clip is encoded as vid2sub encodes a
chunk (16 kHz mono FLAC, no metadata) and uploaded under vid2sub's upload name, with the fields
vid2sub sends for a `parser = "qwen3-asr"` model: Qwen's language name, `verbose_json` and word
timestamps.

```bash
curl -sS -H "Authorization: Bearer $SPARK_API_KEY" http://127.0.0.1:9100/v1/models \
  | uv run python -c "import json, sys; print(sorted(m['id'] for m in json.load(sys.stdin)['data']))"
MODEL=qwen3-asr-1.7b   # the 1.7B's id, exactly as the list above prints it
OUT="${TMPDIR:-/tmp}/vid2sub-qwen" && mkdir -p "$OUT"
ffmpeg -nostdin -v error -i tests/fixtures/speech/jfk-14s.wav -ac 1 -ar 16000 \
  -map_metadata -1 -fflags +bitexact -c:a flac -y "$OUT/chunk-0000.flac"
record() {  # record LANGUAGE-NAME-OR-EMPTY FIXTURE-NAME
  lang=(); [ -n "$1" ] && lang=(-F "language=$1")
  curl -sS --fail-with-body --max-time 900 -o "$OUT/answer.json" -w 'HTTP %{http_code}\n' \
    -H "Authorization: Bearer $SPARK_API_KEY" \
    -F "file=@$OUT/chunk-0000.flac;filename=chunk-0000.flac;type=audio/flac" \
    -F "model=$MODEL" "${lang[@]}" -F "response_format=verbose_json" \
    -F "timestamp_granularities[]=word" \
    http://127.0.0.1:9100/v1/audio/transcriptions \
  && uv run python -m json.tool --indent 2 --no-ensure-ascii "$OUT/answer.json" \
       "tests/fixtures/qwen-endpoint/$2"
}
record English jfk-14s.en.json
record "" jfk-14s-detected.en.json   # no language: what detection reads
```

A Cantonese clip, if there is a public-domain one: the first 60 s, then the same upload.

```bash
CLIP=/path/to/the-public-domain-cantonese-clip   # its source and licence go in ../CREDITS.md
NAME=short-ascii-name
ffmpeg -nostdin -v error -i "$CLIP" -t 60 -ac 1 -ar 16000 \
  -map_metadata -1 -fflags +bitexact -c:a flac -y "$OUT/chunk-0000.flac"
record Cantonese "$NAME.yue.json"
```

Before committing, each answer is checked for the key without printing it (this prints only
`False`, or `True` for a file that must not be committed):

```bash
for f in tests/fixtures/qwen-endpoint/*.json; do
  uv run python -c "import os, sys; print(sys.argv[1], os.environ['SPARK_API_KEY'] in open(sys.argv[1], encoding='utf-8').read())" "$f"
done
```

None yet: local-ai doesn't serve Qwen3-ASR yet.
````

  `tests/fixtures/CREDITS.md`, a row appended to the table:

```markdown
| `qwen-endpoint/documented-shape.en.json` | written by hand: the words of `speech/jfk-14s.wav` in `mlx-qwen3-asr serve`'s `verbose_json` shape, with made-up times (`qwen-endpoint/README.md`) | Public domain (the speech, as above) |
```

- [ ] **Step 7: Run it; watch it fail.** `uv run pytest tests/test_parse_qwen_endpoint.py -q`.
  Expected: `ERROR tests/test_parse_qwen_endpoint.py` with
  `E   ImportError: cannot import name 'parse_qwen_endpoint' from 'vid2sub.parse.qwen'`, then
  `1 error`.
- [ ] **Step 8: Write the code,** `src/vid2sub/parse/qwen.py`, in full:

```python
"""Qwen3-ASR's results → a ParsedChunk, in-process or from a server (spec §9.2, §9.4).

Qwen3-ASR gives the text; its forced aligner gives word or character units with times, keeping
only letters, digits and apostrophes (mlx-qwen3-asr 0.4.4, `is_kept_char`), so the text's
punctuation is attached to them. If the units can't be found in the text, or none of them has a
time, the chunk becomes one unaligned segment rather than wrong timings. A server
(`mlx-qwen3-asr serve`, or the Spark once local-ai serves Qwen3-ASR with its aligner, spec §26.1
item 7) sends the same units as OpenAI-shaped top-level `words`; its `segments` are Qwen's own
30 s pieces, not Whisper's segments, so they're ignored, and the Spark and the Mac give the same
words for the same result (Phase 2 plan, Task 20).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from vid2sub.parse import ParsedChunk, ParseError
from vid2sub.parse.words import attach_punctuation, ms
from vid2sub.subs import langs
from vid2sub.subs.model import Segment


def parse_qwen(result: Mapping[str, Any], *, duration_ms: int) -> ParsedChunk:
    text = str(result.get("text") or "")
    language = langs.from_qwen(str(result.get("language") or ""))
    # The engine reports only the language, not a distribution: 1.0 means "the engine said so",
    # not a measured probability.
    probs = {language: 1.0} if language else {}
    units = [(str(u.get("text", "")), ms(u.get("start")), ms(u.get("end")))
             for u in result.get("segments") or [] if isinstance(u, Mapping)]
    timed = [start for _, start, end in units if start is not None and end is not None
             and end >= start]
    words = (attach_punctuation(text, units, start_ms=timed[0] if timed else 0)
             if units and text.strip() else None)
    if words and any(w.timed for w in words):
        seg = Segment(text="".join(w.text for w in words), start_ms=words[0].start_ms,
                      end_ms=max(w.end_ms for w in words), words=tuple(words))
    elif text.strip():
        seg = Segment(text=text, start_ms=0, end_ms=duration_ms)
    else:
        return ParsedChunk((), language, probs)
    return ParsedChunk((seg,), language, probs)


def parse_qwen_endpoint(data: Any, *, duration_ms: int) -> ParsedChunk:
    """`verbose_json` from an OpenAI-shaped Qwen3-ASR server, `language` a name or a code."""
    if not isinstance(data, Mapping) or not isinstance(data.get("text"), str):
        raise ParseError("not a Qwen3-ASR verbose_json response")
    words = data.get("words")
    if words is None:
        words = []  # silence, or no aligned units: the text alone, unaligned
    if not isinstance(words, list):
        raise ParseError("a Qwen3-ASR response's words aren't a list")
    raw = str(data.get("language") or "").strip()
    name = langs.get(raw.lower()).qwen if raw.lower() in langs.LANGS else raw
    units = [{"text": w.get("word", ""), "start": w.get("start"), "end": w.get("end")}
             for w in words if isinstance(w, Mapping)]
    return parse_qwen({"text": data["text"], "language": name, "segments": units},
                      duration_ms=duration_ms)
```

- [ ] **Step 9: Run the checks; they pass.** `make check`. Expected: `490 passed, 2 skipped,
  4 deselected` twice (23 more), `All checks passed!`, `no leaks found`. Commit:

```text
feat(parse): 🤖 a Qwen3-ASR server's verbose_json becomes timed words with the text's punctuation

parse_qwen_endpoint reads an OpenAI-shaped Qwen3-ASR answer (mlx-qwen3-asr serve's shape, which
spec §26.1 item 7 asks local-ai to return): `text`, `language` as Qwen's name in any case or an
ISO code, and top-level `words` of {word, start, end}. It hands the units to parse_qwen, so the
Spark and the Mac give the same words for the same result, with the text's punctuation attached.
The answer's `segments` are Qwen's own 30 s pieces (return_chunks), not Whisper segments, so
they're ignored. No words gives one unaligned segment over the chunk; an answer without a string
`text`, or with `words` that aren't a list, is a ParseError. tests/fixtures/qwen-endpoint/ holds
documented-shape.en.json, written by hand from that shape until Step 1's recording lands, and a
README with the exact recording commands (dry-run against a local echo server in zsh and bash:
the upload is named chunk-0000.flac, `language` is left out for the detection answer).

The new test failed first with: ImportError: cannot import name 'parse_qwen_endpoint' from
'vid2sub.parse.qwen'.
Docs read: mlx-qwen3-asr 0.4.4 server.py (openai_transcriptions, _openai_format_response,
_estimate_duration), transcribe.py (chunks and aligned segments), tokenizer.py
(canonicalize_language: no `yue` alias), forced_aligner.py (is_kept_char); the GitHub main
branch's server.py (unchanged) and docs/server/API-SPEC.md (verbose_json example: no
`segments`; timestamp_granularities undocumented and not a declared form field).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 20
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/parse/qwen.py tests/test_parse_qwen_endpoint.py
  tests/fixtures/qwen-endpoint/README.md tests/fixtures/qwen-endpoint/documented-shape.en.json
  tests/fixtures/CREDITS.md`, `git commit -F .git/COMMIT_MSG`, then
  `git log -1 --format='%(trailers)'` shows `Plan:`. If Step 1's answers are in the folder, they
  stay unstaged.

- [ ] **Step 10: Write the failing tests.** In `tests/test_endpoint_engine.py`, add `import json`
  as the file's first line and `from pathlib import Path` after
  `from email.parser import BytesParser`, then append to the end of the file:

```python


QWEN_ANSWER = json.loads((Path(__file__).parent / "fixtures" / "qwen-endpoint"
                          / "documented-shape.en.json").read_text(encoding="utf-8"))


def qwen_engine(url, catalog="qwen3-asr-1.7b"):
    cfg = Config(endpoints={"spark": Endpoint(base_url=url, key_env="SPARK_API_KEY")},
                 models={"spark-qwen": ModelEntry(catalog=catalog, endpoint="spark",
                                                  model="qwen3-asr-1.7b", parser="qwen3-asr",
                                                  local=True)})
    return EndpointEngine("spark-qwen", cfg.models["spark-qwen"], cfg, RunPolicy(),
                          KeyRing(environ={"SPARK_API_KEY": SECRET}))


def test_a_qwen_entry_uploads_a_neutral_chunk_with_qwens_language_name_and_reads_timed_words():
    with FakeServer([(200, QWEN_ANSWER, {})]) as srv:
        result = qwen_engine(srv.url).transcribe(chunk(), language="en", prompt="Rice University.")
    req = srv.requests[0]
    form = req.form()
    assert req.path == "/v1/audio/transcriptions"
    assert req.headers["authorization"] == f"Bearer {SECRET}"
    assert form["file"] == ("chunk-0003.flac", b"fLaC-fake")
    assert form["model"][1] == b"qwen3-asr-1.7b"
    assert form["language"][1] == b"English"
    assert form["prompt"][1] == b"Rice University."
    assert form["response_format"][1] == b"verbose_json"
    assert field_values(req, "timestamp_granularities[]") == [b"word"]
    words = result.parsed.segments[0].words
    assert [w.text for w in words[:3]] == ["be", " very", " brief."]
    assert all(w.timed for w in words) and result.parsed.language == "en"


def test_a_qwen_entry_sends_cantonese_by_the_name_qwen_knows():
    # mlx-qwen3-asr 0.4.4 maps en, zh, ja and ko to Qwen's names but passes "yue" through as is.
    answer = {"language": "cantonese", "text": "飲茶。",
              "words": [{"word": "飲", "start": 0.0, "end": 0.2},
                        {"word": "茶", "start": 0.2, "end": 0.4}]}
    with FakeServer([(200, answer, {})]) as srv:
        result = qwen_engine(srv.url).transcribe(chunk(), language="yue", prompt="")
    assert srv.requests[0].form()["language"][1] == b"Cantonese"
    assert result.parsed.language == "yue"
    assert [w.text for w in result.parsed.segments[0].words] == ["飲", "茶。"]


def test_a_language_qwen_has_no_name_for_is_refused_before_anything_is_sent():
    with FakeServer([(200, QWEN_ANSWER, {})]) as srv, pytest.raises(EngineError) as err:
        qwen_engine(srv.url).transcribe(chunk(), language="xx", prompt="")
    assert err.value.kind == "unavailable" and srv.requests == []


def test_a_qwen_entry_is_named_for_qwen_and_takes_qwens_chunk_limit():
    e = qwen_engine("http://127.0.0.1:9/v1")
    assert e.name == "qwen3-asr" and e.max_chunk_s == 180
    assert e.stamp().label == "qwen3-asr-1.7b@unknown"
    assert qwen_engine("http://127.0.0.1:9/v1", catalog=None).max_chunk_s == 180


def test_qwen_endpoint_detection_reports_the_language_it_heard():
    with FakeServer([(200, {"language": "cantonese", "text": "飲茶。"}, {})]) as srv:
        assert qwen_engine(srv.url).detect_language(chunk()) == {"yue": 1.0}
    assert "language" not in srv.requests[0].form()


def test_a_qwen_endpoint_that_is_down_is_a_connection_error_and_nothing_else_is_asked():
    with pytest.raises(EngineError) as err:
        qwen_engine(closed_port_url()).transcribe(chunk(), language="yue", prompt="")
    assert err.value.kind == "connection" and "make tunnel" in err.value.hint


def test_a_qwen_answer_of_the_wrong_shape_is_a_bad_response():
    with FakeServer([(200, {"text": 3}, {})]) as srv, pytest.raises(EngineError) as err:
        qwen_engine(srv.url).transcribe(chunk(), language="en", prompt="")
    assert err.value.kind == "bad_response"
```

  In `tests/test_config.py`, insert before the line
  `def test_a_key_over_plain_http_to_the_lan_is_refused(tmp_path):`:

```python
        c.load_config(write(tmp_path, text))


def test_a_qwen3_asr_parser_is_accepted_for_a_local_endpoint_model(tmp_path):
    text = ('[endpoints.spark]\nbase_url = "http://127.0.0.1:9100/v1"\nkey_env = "SPARK_API_KEY"\n'
            '[models.spark-qwen]\ncatalog = "qwen3-asr-1.7b"\nendpoint = "spark"\n'
            'model = "qwen3-asr-1.7b"\nparser = "qwen3-asr"\nlocal = true\n')
    cfg = c.load_config(write(tmp_path, text))
    assert cfg.models["spark-qwen"].parser == "qwen3-asr"
    assert c.is_local(cfg.models["spark-qwen"], cfg)


def test_a_transcription_model_without_a_parser_is_told_the_three_it_can_have(tmp_path):
    text = ('[endpoints.spark]\nbase_url = "http://127.0.0.1:9100/v1"\n'
            '[models.q]\nendpoint = "spark"\nmodel = "qwen3-asr-1.7b"\n')
    with pytest.raises(c.ConfigError, match="whisper.cpp, openai or qwen3-asr"):
```

  In `tests/test_pipeline.py`, insert before the line
  `# final review 4: --dry-run never downloads`:

```python
def test_an_unreachable_spark_qwen_never_falls_back_to_the_macs_qwen_or_the_cloud(clip,
                                                                                  monkeypatch):
    spark = Candidate("spark-qwen", "qwen3-asr-1.7b", "endpoint", False, "down",
                      unreachable=True)
    mac = Candidate("mac-qwen", "qwen3-asr-1.7b", "in-process", True)
    cloud = Candidate("cloudwhisper", "openai-whisper-1", "endpoint", True, cloud=True)
    monkeypatch.setattr(detecting, "candidates", probes([spark, mac, cloud]))
    engine = FakeEngine(name="qwen3-asr", language="yue")
    ctx = make_ctx(engine, model=None, source_lang="yue", allow_cloud=True,
                   wait_on_connection_s=10)
    ctx.engines["mac-qwen"] = ctx.engines["cloudwhisper"] = engine
    with pytest.raises(pipeline.Paused):
        pipeline.run_one(str(clip), ctx)
    assert ctx.sleeps
    assert not [c for c in engine.calls if c[0] == "transcribe"]
```

- [ ] **Step 11: Run them; watch them fail.**
  `uv run pytest tests/test_endpoint_engine.py tests/test_config.py tests/test_pipeline.py -q`.
  Expected: `9 failed` (the 7 new engine tests with
  `E         Input should be 'whisper.cpp' or 'openai' [type=literal_error, input_value='qwen3-asr', input_type=str]`,
  the 2 config tests with
  `vid2sub.config.ConfigError: models.spark-qwen.parser: Input should be 'whisper.cpp' or 'openai'`
  and `E         Actual message: 'models.q.parser: whisper.cpp or openai'`), the rest passing.
  The new pipeline test passes already: the waiting is M1's (`pipeline._waits_for`), and the test
  is S22's proof that it covers the Mac's Qwen too. Show that it guards: in
  `src/vid2sub/pipeline.py` replace the line
  `    return any(c.name == hoped and c.unreachable for c in cands)` with `    return False`, run
  `uv run pytest "tests/test_pipeline.py::test_an_unreachable_spark_qwen_never_falls_back_to_the_macs_qwen_or_the_cloud" -q`
  (expected: `Failed: DID NOT RAISE Paused`, `1 failed`), then
  `git checkout -- src/vid2sub/pipeline.py` and run it again (`1 passed`).
- [ ] **Step 12: Write the code.** In `src/vid2sub/config.py`, replace

```python
    parser: Literal["whisper.cpp", "openai"] | None = None
```

  with

```python
    parser: Literal["whisper.cpp", "openai", "qwen3-asr"] | None = None
```

  and replace

```python
            raise ConfigError(f"{where}.parser: whisper.cpp or openai")
```

  with

```python
            raise ConfigError(f"{where}.parser: whisper.cpp, openai or qwen3-asr")
```

  `src/vid2sub/engines/endpoint.py`, in full:

```python
"""The endpoint engine: any OpenAI-shaped /v1/audio/transcriptions server (spec §9.3).

The Spark's whisper.cpp behind llama-swap, OpenAI, a local whisper.cpp server, or a Qwen3-ASR
server (`mlx-qwen3-asr serve`, or the Spark once local-ai serves Qwen3-ASR with its aligner). The
entry's `parser` picks the response shape. Requests ask for `verbose_json`, send the language and
prompt when given, and the chunk as `chunk-NNNN.flac`. A Qwen3-ASR server gets Qwen's language
names ("Cantonese"): mlx-qwen3-asr 0.4.4 maps en, zh, ja and ko to them but passes `yue` through
unchanged (Phase 2 plan, Task 20). If the server says which model answered (local-ai Phase 3's
`x-spark-model`), a different model from the one asked for fails the chunk: vid2sub never accepts
a substitute (spec §9.6, §17.4). The Spark reports no model revision today, so stamps say
`unknown`.
"""

from __future__ import annotations

from vid2sub.catalog import CATALOG
from vid2sub.config import Config, ModelEntry
from vid2sub.engines import clients
from vid2sub.engines.base import Chunk, ChunkResult, EngineError, ModelStamp
from vid2sub.parse import ParseError
from vid2sub.parse.openai import parse_openai
from vid2sub.parse.qwen import parse_qwen_endpoint
from vid2sub.parse.whispercpp import parse_whispercpp
from vid2sub.subs import langs

# Qwen3-ASR's chunks are at most 180 s (spec §9.4), catalogued or not.
DEFAULT_CHUNK_S = {"qwen3-asr": 180.0}
GRANULARITIES = {"openai": ["word", "segment"], "qwen3-asr": ["word"]}


class EndpointEngine:
    def __init__(self, name: str, entry: ModelEntry, config: Config,
                 policy: clients.RunPolicy, keys: clients.KeyRing):
        self.model_name = name
        self.entry = entry
        self.name = entry.parser or "openai"
        catalog = CATALOG.get(entry.catalog or "")
        self.max_chunk_s = (catalog.max_chunk_s if catalog
                            else DEFAULT_CHUNK_S.get(self.name, 300.0))
        self.supports_prompt = catalog.supports_prompt if catalog else True
        self._key_env = config.endpoints[entry.endpoint].key_env
        self._secrets = keys.secrets(config)
        self._client = clients.transcription_client(name, entry, config, policy, keys)

    def _language(self, language: str | None) -> str | None:
        if not language or self.entry.parser != "qwen3-asr":
            return language
        try:
            return langs.get(language).qwen
        except langs.UnknownLanguage:
            raise EngineError("unavailable", "Qwen3-ASR has no name for that language") from None

    def _parse(self, data: dict, chunk: Chunk):
        if self.entry.parser == "whisper.cpp":
            return parse_whispercpp(data)
        if self.entry.parser == "qwen3-asr":
            return parse_qwen_endpoint(data, duration_ms=chunk.duration_ms)
        return parse_openai(data)

    def _post(self, chunk: Chunk, *, language: str | None, prompt: str) -> ChunkResult:
        params: dict = {"model": self.entry.model, "response_format": "verbose_json"}
        language = self._language(language)
        if language:
            params["language"] = language
        if prompt and self.supports_prompt:
            params["prompt"] = prompt
        if self.entry.parser in GRANULARITIES:
            params["timestamp_granularities"] = GRANULARITIES[self.entry.parser]
        data, headers = clients.call_transcription(
            self._client, key_env=self._key_env, secrets=self._secrets,
            file=(chunk.upload_name, chunk.flac(), "audio/flac"), **params)
        answered = headers.get("x-spark-model")
        if answered and answered != self.entry.model:
            raise EngineError("bad_response",
                              f"asked for {self.entry.model} but {answered} answered",
                              hint="vid2sub never accepts a substitute model")
        try:
            parsed = self._parse(data, chunk)
        except (ParseError, ValueError, TypeError):
            # Segment validation raises pydantic errors (ValueError); the message names no server content.
            raise EngineError("bad_response",
                              "the server's answer didn't have the expected shape") from None
        return ChunkResult(parsed, answered)

    def transcribe(self, chunk: Chunk, *, language: str | None, prompt: str) -> ChunkResult:
        return self._post(chunk, language=language, prompt=prompt)

    def detect_language(self, chunk: Chunk) -> dict[str, float]:
        parsed = self._post(chunk, language=None, prompt="").parsed
        if parsed.language_probs:
            return dict(parsed.language_probs)
        # whisper.cpp reports the language it decoded in, not a detection, so it knows nothing here.
        if self.entry.parser == "whisper.cpp":
            return {}
        return {parsed.language: 1.0} if parsed.language else {}

    def stamp(self) -> ModelStamp:
        return ModelStamp(self.name, self.entry.model or "", "unknown")

    def close(self) -> None:
        self._client.close()
```

- [ ] **Step 13: Run the checks; they pass.** `make check`. Expected: `500 passed, 2 skipped,
  4 deselected` twice (10 more), `All checks passed!`, `no leaks found`. Commit:

```text
feat(engines): 🤖 a parser = "qwen3-asr" model transcribes through the endpoint engine

vid2sub.toml's parser takes "qwen3-asr", and a transcription model without a parser is told all
three. The endpoint engine, named qwen3-asr for such a model (so detection never treats Qwen's
"zh" as Whisper's ambiguous one), sends Qwen's language name ("Cantonese", not "yue": mlx-qwen3-asr
0.4.4's canonicalize_language has no yue alias and passes it through), asks for word timestamps
only, parses the answer with parse_qwen_endpoint, and takes its 180 s chunk limit from the
catalog, or 180 s for an uncatalogued Qwen model (spec §9.4). A language Qwen has no name for is
refused before anything is sent. A Qwen server that is down is a connection error, as for
whisper.cpp; the new pipeline test shows a Spark Qwen that doesn't answer is waited for and the
run paused, never handed to the Mac's Qwen or the cloud (S22, spec §17.4).

The new tests failed first with: pydantic_core._pydantic_core.ValidationError: 1 validation error
for ModelEntry ... Input should be 'whisper.cpp' or 'openai' (7 engine tests) and ConfigError /
regex mismatch (2 config tests). The pipeline test passed at once (M1's waiting rule); with
_waits_for returning False it failed with "DID NOT RAISE Paused", then passed again once restored.
Docs read: the openai SDK 3.31.0's transcriptions.create docstrings (language as ISO-639-1 for
OpenAI; timestamp_granularities word/segment, verbose_json only; platform.openai.com answered 403);
mlx-qwen3-asr 0.4.4 tokenizer.py and server.py as in the parser's commit.

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 20
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/config.py src/vid2sub/engines/endpoint.py tests/test_config.py
  tests/test_endpoint_engine.py tests/test_pipeline.py`, `git commit -F .git/COMMIT_MSG`, then
  `git log -1 --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 14: Write the failing test,** `tests/test_spark_qwen.py`:

```python
"""The Spark's Qwen3-ASR as a configured model: the starter's commented entry, routing, `models`
and `doctor` (spec §5.1, §10, §11.2, S22)."""

import json

from fakes import FakeServer

from vid2sub import config as c
from vid2sub import detect as detecting
from vid2sub.catalog import suggest
from vid2sub.cli import main
from vid2sub.engines.clients import KeyRing

LISTED = ("whisper-large-v3-turbo", "gemma-4-26b-a4b", "qwen3-asr-1.7b")


def served(*ids):
    return {"object": "list",
            "data": [{"id": i, "object": "model", "created": 0, "owned_by": "spark"} for i in ids]}


def with_spark_qwen(starter, base_url):
    """The starter with its commented `[models.spark-qwen]` lines switched on, at `base_url`."""
    lines = starter.splitlines()
    start = end = lines.index("# [models.spark-qwen]")
    while end < len(lines) and lines[end].startswith("# "):
        end += 1
    lines[start:end] = [line[2:] for line in lines[start:end]]
    return "\n".join(lines).replace('"http://127.0.0.1:9100/v1"', f'"{base_url}"') + "\n"


def write_config(tmp_path, base_url):
    path = tmp_path / "vid2sub.toml"
    path.write_text(with_spark_qwen(c.STARTER, base_url), encoding="utf-8")
    return path


def model_rows(capsys):
    return {e["name"]: e for e in map(json.loads, capsys.readouterr().out.splitlines())
            if e.get("event") == "model"}


def test_the_starters_spark_qwen_entry_is_commented_out_and_valid_once_switched_on(tmp_path):
    plain = tmp_path / "plain.toml"
    plain.write_text(c.STARTER, encoding="utf-8")
    assert "spark-qwen" not in c.load_config(plain).models
    assert c.STARTER.isascii()
    cfg = c.load_config(write_config(tmp_path, "http://127.0.0.1:9100/v1"))
    entry = cfg.models["spark-qwen"]
    assert (entry.catalog, entry.endpoint, entry.model, entry.parser) == (
        "qwen3-asr-1.7b", "spark", "qwen3-asr-1.7b", "qwen3-asr")
    assert c.is_local(entry, cfg)


def test_a_configured_spark_qwen_comes_first_for_cantonese_and_mandarin_and_detects(tmp_path,
                                                                                  monkeypatch):
    monkeypatch.setattr(detecting, "mlx_available", lambda: True)  # the Mac's Qwen is usable too
    with FakeServer(responder=lambda req: (200, served(*LISTED), {})) as srv:
        cfg = c.load_config(write_config(tmp_path, srv.url))
        cands = detecting.candidates(cfg, KeyRing(environ={"SPARK_API_KEY": "test-only"}))
    usable = {x.name for x in cands if x.available}
    assert {"spark-qwen", "mac-qwen", "spark-turbo"} <= usable
    for lang in ("yue", "zh"):
        assert suggest(lang, cands, "transcribe", allow_cloud=False).model == "spark-qwen"
    assert suggest("en", cands, "transcribe", allow_cloud=False).model == "spark-turbo"
    assert detecting.choose_detector(cands, allow_cloud=False) == "spark-qwen"


def test_models_shows_spark_qwen_usable_once_the_spark_lists_it_and_why_not_before(
        tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SPARK_API_KEY", "test-only")
    with FakeServer(responder=lambda req: (200, served(*LISTED), {})) as srv:
        assert main(["models", "--config", str(write_config(tmp_path, srv.url)), "--json"]) == 0
    row = model_rows(capsys)["spark-qwen"]
    assert row["available"] and row["catalog"] == "qwen3-asr-1.7b" and row["task"] == "transcribe"
    with FakeServer(responder=lambda req: (200, served(*LISTED[:2]), {})) as srv:
        assert main(["models", "--config", str(write_config(tmp_path, srv.url)), "--json"]) == 0
    row = model_rows(capsys)["spark-qwen"]
    assert not row["available"] and row["reason"] == "the server doesn't list qwen3-asr-1.7b"


def test_doctor_asks_the_spark_for_its_models_and_says_how_many_it_serves(tmp_path, monkeypatch,
                                                                         capsys):
    monkeypatch.setenv("SPARK_API_KEY", "test-only")
    with FakeServer(responder=lambda req: (200, served(*LISTED), {})) as srv:
        main(["doctor", "--config", str(write_config(tmp_path, srv.url)), "--json"])
    rows = {e["check"]: e for e in map(json.loads, capsys.readouterr().out.splitlines())}
    assert rows["endpoint spark"]["ok"] and rows["endpoint spark"]["detail"] == "serves 3 model(s)"
    assert "test-only" not in json.dumps(rows)
    assert {r.path for r in srv.requests} == {"/v1/models"}
```

- [ ] **Step 15: Run it; watch it fail.** `uv run pytest tests/test_spark_qwen.py -q`. Expected:
  `4 failed`, each with `E       ValueError: list.index(x): x not in list`.
- [ ] **Step 16: Write the code.** In both `src/vid2sub/example.toml` and
  `vid2sub.example.toml` (they must stay identical: `test_config.py` checks), insert after the
  line `engine = "mlx-qwen3-asr"` and its following blank line, and before
  `# Cloud models are used only when a run passes --allow-cloud.`, this block and one blank line:

```toml
# Qwen3-ASR on the Spark, once local-ai serves it with its forced aligner: uncomment these lines.
# Cantonese and Mandarin then go to the Spark first and the Mac second, and it detects languages.
# [models.spark-qwen]
# catalog = "qwen3-asr-1.7b"
# endpoint = "spark"
# model = "qwen3-asr-1.7b"   # the name the Spark's /v1/models lists
# parser = "qwen3-asr"
# local = true
```

  Then `cmp src/vid2sub/example.toml vid2sub.example.toml` prints nothing.
- [ ] **Step 17: Run the checks; they pass.** `make check`. Expected: `504 passed, 2 skipped,
  4 deselected` twice (4 more), `All checks passed!`, `no leaks found`. Commit:

```text
feat(config): 🤖 the starter config carries a commented spark-qwen entry that routes first for Cantonese and Mandarin

vid2sub.example.toml (and its packaged copy, which `vid2sub config init` prints) gains a
commented [models.spark-qwen] for Qwen3-ASR on the Spark, to uncomment once local-ai serves it.
Commented, so the starter's models are unchanged and stay ASCII. Switched on and pointed at a fake
Spark: it is a usable local endpoint candidate, the route picks it before the Mac's Qwen for yue
and zh (spark-turbo still for en), it becomes the language detector, `vid2sub models` shows it
usable or "the server doesn't list qwen3-asr-1.7b", and `vid2sub doctor` asks the Spark for its
model list and reports the count, with the key absent from the output. No routing code changed:
catalog.suggest already sorts endpoints before in-process models (spec §11.2).

The new tests failed first with: ValueError: list.index(x): x not in list (all 4).
Docs read: none beyond this repo (TOML comments only; config and catalog code read).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 20
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/example.toml vid2sub.example.toml tests/test_spark_qwen.py`,
  `git commit -F .git/COMMIT_MSG`, then `git log -1 --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 18: Write the opt-in live test,** `tests/test_live_spark.py`, in full (it never runs
  without `VID2SUB_LIVE_SPARK=1`, so there is no failing run; Step 21 runs it for real):

```python
"""The real Spark (opt-in): VID2SUB_LIVE_SPARK=1 with `make tunnel` running and SPARK_API_KEY
exported. Checks whisper.cpp's and Qwen3-ASR's verbose_json and Gemma's structured output against
vid2sub's parsers and schemas (spec §29, S21, S22). The Qwen test needs local-ai to serve
Qwen3-ASR with its forced aligner as `qwen3-asr-1.7b`."""

import os

import pytest
from helpers import SPEECH

from vid2sub.config import Config, Endpoint, ModelEntry
from vid2sub.engines.base import Chunk
from vid2sub.engines.clients import KeyRing, RunPolicy
from vid2sub.engines.endpoint import EndpointEngine
from vid2sub.media.decode import encode_flac, read_wav
from vid2sub.media.tools import Tools
from vid2sub.subs.glossary import EMPTY_GLOSSARY
from vid2sub.subs.model import Cue
from vid2sub.translate.run import make_ask, translate_cues

pytestmark = [pytest.mark.live, pytest.mark.skipif(os.environ.get("VID2SUB_LIVE_SPARK") != "1",
                                                   reason="needs VID2SUB_LIVE_SPARK=1")]
CONFIG = Config(
    endpoints={"spark": Endpoint(base_url="http://127.0.0.1:9100/v1", key_env="SPARK_API_KEY")},
    models={"turbo": ModelEntry(catalog="whisper-large-v3-turbo", endpoint="spark",
                                model="whisper-large-v3-turbo", parser="whisper.cpp", local=True),
            "qwen": ModelEntry(catalog="qwen3-asr-1.7b", endpoint="spark", model="qwen3-asr-1.7b",
                               parser="qwen3-asr", local=True),
            "gemma": ModelEntry(catalog="gemma-4-26b-a4b", endpoint="spark",
                                model="gemma-4-26b-a4b", task="translate", local=True,
                                request_extra={"chat_template_kwargs":
                                               {"enable_thinking": False}})})


def test_the_sparks_whisper_returns_timed_words(tmp_path):
    samples = read_wav(SPEECH)
    engine = EndpointEngine("turbo", CONFIG.models["turbo"], CONFIG, RunPolicy(), KeyRing())
    chunk = Chunk(0, samples, lambda s: encode_flac(s, Tools.find(), scratch=tmp_path))
    words = [w for s in engine.transcribe(chunk, language="en", prompt="").parsed.segments
             for w in s.words]
    assert len(words) > 10 and all(w.end_ms >= w.start_ms for w in words)


def test_the_sparks_qwen_returns_timed_words_with_the_texts_punctuation_and_detects(tmp_path):
    samples = read_wav(SPEECH)
    engine = EndpointEngine("qwen", CONFIG.models["qwen"], CONFIG, RunPolicy(), KeyRing())
    chunk = Chunk(0, samples, lambda s: encode_flac(s, Tools.find(), scratch=tmp_path))
    parsed = engine.transcribe(chunk, language="en", prompt="").parsed
    words = [w for s in parsed.segments for w in s.words]
    assert parsed.language == "en"
    assert len(words) > 10 and all(w.timed and w.end_ms >= w.start_ms for w in words)
    assert any(w.text.rstrip()[-1] in ",." for w in words)
    assert engine.detect_language(chunk) == {"en": 1.0}


def test_gemma_translates_a_batch_in_the_required_shape():
    cues = [Cue(id=f"s{i}", start_ms=i * 2000, end_ms=i * 2000 + 1500, text=t)
            for i, t in enumerate(["おはようございます。", "今日はいい天気ですね。", "また明日。"])]
    ask = make_ask("gemma", CONFIG.models["gemma"], CONFIG, RunPolicy(), KeyRing())
    out = translate_cues(cues, source_lang="ja", target_track="en", glossary=EMPTY_GLOSSARY,
                         ask=ask)
    assert [c.src for c in out] == [("s0",), ("s1",), ("s2",)]
```

- [ ] **Step 19: Run it and the checks.** `uv run pytest -m live tests/test_live_spark.py -q -rs`.
  Expected: `3 skipped`, each `needs VID2SUB_LIVE_SPARK=1`. Never run it here with
  `VID2SUB_LIVE_SPARK=1`: that reaches the real Spark with Dan's key. `make check`. Expected:
  `504 passed, 2 skipped, 5 deselected` twice, `All checks passed!`, `no leaks found`. Commit:

```text
test(live): 🤖 the opt-in Spark test checks Qwen3-ASR's timed, punctuated words and detection

With VID2SUB_LIVE_SPARK=1 (make tunnel running, SPARK_API_KEY exported), the 14 s public-domain
clip goes to the Spark's qwen3-asr-1.7b through the endpoint engine: English, more than ten timed
words, a comma or full stop attached to a word, and detection without a language says en. It
needs local-ai to serve Qwen3-ASR with its forced aligner, so it isn't run until Task 20's
Step 21. Without the opt-in it is deselected (-m 'not live') or skipped (-m live): "3 skipped".

Docs read: none beyond this repo.

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 20
Co-Authored-By: <the model's own line>
```

  `git add tests/test_live_spark.py`, `git commit -F .git/COMMIT_MSG`, then
  `git log -1 --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 20: The docs this build made untrue or incomplete.** In the spec, replace

```markdown
- `mlx-qwen3-asr serve` `verbose_json`: top-level aligner words. The aligner's text has no
  punctuation (assumed until §29 confirms), so a pure `attach_punctuation(text, units)` maps the
  ASR text's punctuation onto aligned units.
```

  with

```markdown
- `mlx-qwen3-asr serve` `verbose_json`, and the Spark's Qwen3-ASR in the same shape
  (`parser = "qwen3-asr"`): top-level aligner words. The aligner keeps only letters, digits and
  apostrophes (§29), so a pure `attach_punctuation(text, units)` maps the ASR text's punctuation
  onto aligned units, punctuation inside a word ("well-known", "3.5") included. The answer's
  `segments` are Qwen's own 30 s pieces and are ignored, so the Spark and the Mac give the same
  words.
```

  replace

```markdown
(through llama-swap), OpenAI, a local whisper.cpp server, or `mlx-qwen3-asr serve`. The `parser`
field (§5.1) picks the response parser. Requests send `language`, `prompt`,
`response_format=verbose_json` and, for OpenAI, `timestamp_granularities[]`. Responses' model
headers are recorded (§9.6).
```

  with

```markdown
(through llama-swap), OpenAI, a local whisper.cpp server, `mlx-qwen3-asr serve`, or the Spark's
Qwen3-ASR once local-ai serves it. The `parser` field (§5.1) picks the response parser. Requests
send `language`, `prompt`, `response_format=verbose_json` and, for OpenAI and Qwen3-ASR,
`timestamp_granularities[]`; a Qwen3-ASR server gets Qwen's language name (`Cantonese`), since
mlx-qwen3-asr passes `yue` through unrecognised. Qwen3-ASR's chunks are at most 180 s (§9.4).
Responses' model headers are recorded (§9.6).
```

  insert after the §29 line that ends `isn't used in M1 (vid2sub runs it in-process).`:

```markdown
  - *The forced aligner's units and `mlx-qwen3-asr serve`'s answer* (Phase 2, Task 20, from
    mlx-qwen3-asr 0.4.4's source): the aligner keeps only letters, digits and apostrophes
    (`is_kept_char`), so "well-known" comes back as "wellknown"; vid2sub finds such units in the
    text. `serve`'s `verbose_json` has `task`, `language` (Qwen's name, lower-cased), `duration`
    (the last word's end), `text`, top-level `words` of `{word, start, end}` and, though its API
    spec leaves them out, `segments` holding Qwen's 30 s pieces. It declares no
    `timestamp_granularities` field and ignores one.
```

  and in its Open items replace

```markdown
  `Qwen3-ForcedAligner-0.6B` too; vLLM serves the text but no words (§26.1, item 7). vid2sub has
  no parser for a Qwen endpoint yet (M1 plan, decision 3). Proposed as a Phase 2 task (S22), its
  first step recording a real response.
```

  with

```markdown
  `Qwen3-ForcedAligner-0.6B` too; vLLM serves the text but no words (§26.1, item 7). vid2sub
  reads such a server with `parser = "qwen3-asr"` (Phase 2, Task 20); S22 waits on local-ai
  serving it and an answer recorded from the Spark.
```

  In `README.md`, replace

```markdown
  `http://127.0.0.1:9100/v1`.
```

  with

```markdown
  `http://127.0.0.1:9100/v1`. Once local-ai serves Qwen3-ASR with its forced aligner, uncomment
  the starter's `[models.spark-qwen]`: Cantonese and Mandarin then go to the Spark first.
```

  In `tests/README.md`, replace

```markdown
    the Spark's whisper.cpp and Gemma 4.
```

  with

```markdown
    the Spark's whisper.cpp, Gemma 4 and Qwen3-ASR (`qwen3-asr-1.7b`, once local-ai serves it).
```

  `make check` (as Step 19). Commit:

```text
docs: 🤖 the spec, README and tests README say how vid2sub reads a Qwen3-ASR server

Spec §9.2: the Qwen parser covers the Spark's Qwen3-ASR in mlx-qwen3-asr serve's shape, the
aligner's units carry no punctuation (no longer "assumed"), inner punctuation included, and
`segments` are ignored. §9.3: the endpoint engine's servers include the Spark's Qwen3-ASR, which
gets word timestamps and Qwen's language names, in chunks of at most 180 s. §29: what
mlx-qwen3-asr 0.4.4's source showed. Open items: vid2sub has its Qwen parser now; S22 waits on
local-ai and a recording. README: uncomment `[models.spark-qwen]` once local-ai serves
Qwen3-ASR. tests/README.md: the live Spark test now covers Qwen3-ASR too.

Checked: make check; "no parser for a Qwen endpoint" survives only on the Q&A page, which records
the question as it was asked. Docs read: mlx-qwen3-asr 0.4.4 server.py, forced_aligner.py,
tokenizer.py (as in this task's parser commit).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 20
Co-Authored-By: <the model's own line>
```

  `git add README.md tests/README.md docs/superpowers/specs/2026-10-14-vid2sub-design.md`,
  `git commit -F .git/COMMIT_MSG`, then `git log -1 --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 21 [Dan]: The recording, and the live test.** If Step 1 found no Qwen3-ASR, wait
  here (**Now** already says so) until Dan says local-ai serves it, then run Step 1's commands.
  With `tests/fixtures/qwen-endpoint/jfk-14s.en.json` and `jfk-14s-detected.en.json` in place,
  Dan runs, with the tunnel up and the key exported:
  `VID2SUB_LIVE_SPARK=1 uv run pytest -m live tests/test_live_spark.py -q -k qwen`. Expected:
  `1 passed, 2 deselected`. If the 1.7B's id isn't `qwen3-asr-1.7b`, change `model=` in
  `CONFIG["qwen"]` first (Step 22 makes it drift). Note the date.
- [ ] **Step 22: The real answers through the contract tests.** First the key check, which prints
  only `False` per file (a `True` file must never be committed: delete it and tell Dan):

```bash
for f in tests/fixtures/qwen-endpoint/*.json; do
  uv run python -c "import os, sys; print(sys.argv[1], os.environ['SPARK_API_KEY'] in open(sys.argv[1], encoding='utf-8').read())" "$f"
done
```

  Then compare their shape with the documented one (keys, the language's spelling, how many
  units carry anything but letters, digits and apostrophes):

```bash
uv run python -c "
import json, pathlib
for p in sorted(pathlib.Path('tests/fixtures/qwen-endpoint').glob('*.json')):
    d = json.loads(p.read_text(encoding='utf-8'))
    w = d.get('words') or []
    print(p.name, sorted(d), sorted(w[0]) if w else None, repr(d.get('language')),
          sum(not x['word'].replace(\"'\", '').isalnum() for x in w), 'of', len(w))
"
```

  In `tests/test_parse_qwen_endpoint.py`, replace `ANSWERS = ["documented-shape.en.json"]` with
  `ANSWERS = ["documented-shape.en.json", "jfk-14s.en.json", "jfk-14s-detected.en.json"]` (add
  `"<name>.yue.json"` if Dan recorded one) and run
  `uv run pytest tests/test_parse_qwen_endpoint.py -q`. Expected: `27 passed` (`29 passed` with
  the Cantonese answer). **Any failure, or any difference the comparison shows (another key set,
  `words` under another name, units carrying punctuation, a 1.7B id other than
  `qwen3-asr-1.7b`), is drift:** build it right (the parser, its tests, and every place the id
  appears: both starter files, `tests/test_spark_qwen.py`, `tests/test_live_spark.py`, the
  fixture README's `MODEL=`), with a "Built differently" note at this task's head and the
  close's `Drift:` line. Then in `tests/fixtures/qwen-endpoint/README.md` replace the line
  `None yet: local-ai doesn't serve Qwen3-ASR yet.` with this table, one row per answer, filled
  from Step 1:

```markdown
| File | Clip | `language` sent | Model | Recorded |
|---|---|---|---|---|
| `jfk-14s.en.json` | `../speech/jfk-14s.wav` | `English` | `<the 1.7B's id>` | <date> |
| `jfk-14s-detected.en.json` | `../speech/jfk-14s.wav` | none | `<the 1.7B's id>` | <date> |
| `<name>.yue.json` | the first 60 s of `<the clip's source>` | `Cantonese` | `<the 1.7B's id>` | <date> |
```

  and append to the table in `tests/fixtures/CREDITS.md`:

```markdown
| `qwen-endpoint/jfk-14s.en.json`, `qwen-endpoint/jfk-14s-detected.en.json` | the Spark's Qwen3-ASR answers to `speech/jfk-14s.wav`, recorded <date> (`qwen-endpoint/README.md`) | Public domain (the speech, as above) |
| `qwen-endpoint/<name>.yue.json` | the Spark's Qwen3-ASR answer to the first 60 s of <the clip's source and URL>, recorded <date> | <its licence> |
```

  If **Now** reads `waiting on Dan: Task 20, Step 1`, set it back to
  `Task 20: The Spark's Qwen3-ASR endpoint, open.` `make check` (as Step 19, plus 4 or 6).
  Commit:

```text
test(fixtures): 🤖 answers recorded from the Spark's Qwen3-ASR pass the contract tests

Dan recorded the Spark's verbose_json for the public-domain 14 s clip, with language=English and
without a language<, and for a public-domain Cantonese clip>, on <date>, uploaded as
chunk-0000.flac with word timestamps (tests/fixtures/qwen-endpoint/README.md). Each file was
checked for the key without printing it (False for every file). Compared with the documented
shape: <the same keys and units without punctuation | what differed, and the Built differently
note>. The contract tests now run over them too: <27|29> passed.

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 20
Co-Authored-By: <the model's own line>
```

  `git add tests/fixtures/qwen-endpoint/jfk-14s.en.json
  tests/fixtures/qwen-endpoint/jfk-14s-detected.en.json` (and the `.yue.json`)
  `tests/fixtures/qwen-endpoint/README.md tests/fixtures/CREDITS.md
  tests/test_parse_qwen_endpoint.py docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md` (and
  each file a drift fix touched), `git commit -F .git/COMMIT_MSG`, then
  `git log -1 --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 23: The docs the Spark serving Qwen3-ASR makes true.** In `src/vid2sub/catalog.py`,
  replace `        runs_on="Mac (mlx-qwen3-asr); the Spark once local-ai serves it",` with
  `        runs_on="Mac (mlx-qwen3-asr); the Spark (local-ai)",`; if Step 1's list had the 0.6B
  too, also replace `        weak="less accurate than the 1.7B", runs_on="Mac (mlx-qwen3-asr)",`
  with `        weak="less accurate than the 1.7B", runs_on="Mac (mlx-qwen3-asr); the Spark (local-ai)",`.
  Run `make readme`. In the spec's §11.1 table, the 1.7B row (the line starting
  ``| `qwen3-asr-1.7b` (+ ForcedAligner-0.6B) |``) ends, instead of
  ``| Mac (`mlx-qwen3-asr`); the Spark once local-ai serves it (§26.1) |``, with:

```markdown
| Mac (`mlx-qwen3-asr`); the Spark (local-ai, §26.1) |
```

  and, with the 0.6B listed, the next row becomes:

```markdown
| `qwen3-asr-0.6b` | the same, lighter | less accurate | Mac; the Spark (local-ai) |
```

  In the spec's Open items, delete the bullet that starts
  `- **Qwen3-ASR on the Spark** (Dan, 2026-10-23:` (four lines, as Step 20 left it). In §29,
  replace
  `- **local-ai:** Qwen3-ASR under vLLM or torch on the GB10 (aarch64, sm_121).` with

```markdown
- **local-ai:** Qwen3-ASR under vLLM or torch on the GB10 (aarch64, sm_121): local-ai serves it
  with its forced aligner, and its answer was recorded on <date> (Phase 2, Task 20).
```

  In `docs/architecture.md`, the Spark's Qwen3-ASR joins the Spark's node, solid: replace

```text
  spark["DGX Spark via SSH tunnel<br/>127.0.0.1:9100/v1<br/>whisper.cpp · Gemma 4"]
  sparkqwen["DGX Spark<br/>Qwen3-ASR + forced aligner<br/>(Phase 2, once local-ai serves it)"]
```

  with

```text
  spark["DGX Spark via SSH tunnel<br/>127.0.0.1:9100/v1<br/>whisper.cpp · Gemma 4<br/>Qwen3-ASR + forced aligner"]
```

  delete the line `  core -.->|"chunks"| sparkqwen`, and replace
  `  class browser,web,fw,sparkqwen,pages planned` with `  class browser,web,fw,pages planned`.
  `make check` (as Step 22). Commit:

```text
docs: 🤖 the Spark serves Qwen3-ASR: the catalog, README table, spec and diagram say so

The catalog's runs_on (and so `make readme`'s table) and the spec's §11.1 put Qwen3-ASR 1.7B
<and 0.6B> on the Spark through local-ai; the open item on it is closed; §29's local-ai line
records it as served; docs/architecture.md draws it in the Spark's node, solid.

Checked: make check (test_readme: the README table is the catalog's); grep for "sparkqwen" and
"once local-ai serves it" in docs/ and README.md finds only the starter's comment and README's
config advice, which hold for any local-ai.

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 20
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/catalog.py README.md docs/architecture.md
  docs/superpowers/specs/2026-10-14-vid2sub-design.md`, `git commit -F .git/COMMIT_MSG`, then
  `git log -1 --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 24: Review, look forward, close.** The Tier 2 review from `$(cat .git/TASK_BASE)`
  (`AGENTS.md`, *Reviews*: Matt Pocock's `code-review`, two axes in two subagents; fix Critical
  and Important). Give the Spec axis S22, spec §9.2, §9.3, §17.4 and §26.1 item 7. The forward
  review over Tasks 22 (the docs: the README's Spark advice), 23 (the M2 exit test) and 24 (the
  phase end: `docs/architecture.md` already solid for this part), and Phase 3's Models page
  (S44), which lists `spark-qwen` through `detect.candidates` unchanged. The docs this task made
  untrue: Steps 20 and 23 cover them; grep for `whisper.cpp or openai` and `"whisper.cpp" |
  "openai"` once more. Then the close, its own commit, holding this plan with this task's boxes
  ticked and **Now** set to `Task 21: CI: the frontend and end-to-end jobs, open.`, and the
  spec's S22 row: replace

```markdown
| S22 | a Cantonese episode through the Spark's Qwen3-ASR and forced aligner, once local-ai serves them | timed words with the text's punctuation attached; when the Spark is down, no fallback | Phase 2 | a fixture recorded from the Spark; `VID2SUB_LIVE_SPARK=1` | planned |
```

  with (verified: Step 21's live run checked it for real)

```markdown
| S22 | a Cantonese episode through the Spark's Qwen3-ASR and forced aligner, once local-ai serves them | timed words with the text's punctuation attached; when the Spark is down, no fallback | Phase 2, Task 20 | `tests/test_parse_qwen_endpoint.py` on answers recorded from the Spark; `tests/test_pipeline.py::test_an_unreachable_spark_qwen_never_falls_back_to_the_macs_qwen_or_the_cloud`; `tests/test_live_spark.py`, passed <Step 21's date> | verified |
```

  with the message in `.git/CLOSE_MSG`:

```text
docs(plan): 🤖 close Task 20: The Spark's Qwen3-ASR endpoint

Drift: none
Rulings: none
Phase-end: none
Forward: none
Tier: 2
Rounds: <the reviews run>
Findings: none

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 20
Co-Authored-By: <the model's own line>
```

  `git add docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md
  docs/superpowers/specs/2026-10-14-vid2sub-design.md`, `git commit -F .git/CLOSE_MSG`.

***

### Task 21: CI: the frontend and end-to-end jobs

**Tier:** 3

<!-- steps: written in the next pass -->

***

### Task 22: The docs

**Tier:** 3

<!-- steps: written in the next pass -->

***

### Task 23: The M2 exit test (with Dan)

**Tier:** 3 · **Scenarios:** S27, S29, S30, S31, S43 · **[Dan]**, on Dan's Mac

Spec §25's M2 exit test, plus the two checks that wait on the editor: whisper.cpp's cue timing
against a hand-corrected episode (§29, moved from Task 1) and the browser codec matrix (§29, M2).
The implementer prepares and records; Dan runs every step on his media.

**Files:**
- Modify: `docs/superpowers/specs/2026-10-14-vid2sub-design.md` (§29's M1 timing line and M2
  results, the Scenarios rows, Open items)

**Interfaces:** none (no code).

- [ ] **Step 0: Record the base:** `git rev-parse HEAD > .git/TASK_BASE`.
- [ ] **Step 1: List the [Dan] steps** (2 to 7 below), one line each, with the count, then present
  Step 2. Set **Now** to `waiting on Dan: Task 23, Step 2` in a wip commit
  (`chore(plan): 🤖 wip Task 23: waiting on Dan for the M2 exit test`; `Done so far:` the list,
  `Stopped at:` Step 2, `Tests:` `make check` and `make e2e` green at the base).
- [ ] **Step 2: [Dan] Start the editor:**

```bash
uv tool install --editable '.[mac]'
(cd frontend && npm ci && npm run build)
vid2sub serve
```

  Expected: the browser opens on the editor through the launch link, and the terminal prints the
  same link for opening by hand.
- [ ] **Step 3: [Dan] Open an M1 episode (S27, S43):** type the path of an episode Task 1 made.
  Note whether it played as video or through the playback audio, and in which browser (try
  Chrome, and Safari or Firefox if you use them: the codec matrix, §29).
- [ ] **Step 4: [Dan] Fix lines and save (S29):** go through the first five minutes cue by cue
  and fix every start, end and line (this is the hand-corrected stretch Step 8 measures); split
  one cue and merge two; correct two translations; then Save. Expected: the subtitle files are
  rewritten, and reopening shows the corrections.
- [ ] **Step 5: [Dan] Retranslate stale cues (S30):** after Step 4, **Retranslate stale**.
  Expected: only the cues whose source changed get new English; the two translations you
  corrected are kept.
- [ ] **Step 6: [Dan] An outside edit (S31):** edit the episode's `.en.srt` in another editor
  (change one line), save it, then reopen the episode in vid2sub. Expected: the editor says it
  kept your outside edit, and shows the changed line.
- [ ] **Step 7: [Dan] Hand back the notes** from Steps 2–6, and the episode's path for Step 8.
- [ ] **Step 8: Measure the cue timing** (§29: whisper.cpp tokens without DTW, against the
  episode Dan corrected in Step 4). In this repo's folder, with the episode's path in `$EP`:

```bash
uv run python - "$EP" <<'PY'
import statistics, sys
from pathlib import Path
from vid2sub import store
from vid2sub.subs.rendition import cues_from_body
sidecar, _ = store.load(Path(sys.argv[1]))
track = store.source_track(sidecar)
auto_id = next(h.rendition for h in sidecar.heads(track) if h.by == "auto")
first = {c.id: c for c in cues_from_body(sidecar.renditions()[auto_id].body)}
_, edited = store.current_cues(sidecar, track)
pairs = [(c, first[c.id]) for c in edited if c.id in first and c.end_ms <= 300_000]
d = [abs(c.start_ms - a.start_ms) for c, a in pairs] + [abs(c.end_ms - a.end_ms) for c, a in pairs]
print(f"{len(pairs)} cues compared; median {statistics.median(d)} ms; "
      f"90th percentile {sorted(d)[int(len(d) * 0.9)]} ms")
PY
```

  Expected: one line, `<n> cues compared; median <m> ms; 90th percentile <p> ms`. It prints no
  title or path.
- [ ] **Step 9: Record the results in the spec.** §29: the timing line (M1) with Step 8's numbers,
  dated; the M2 bullets with the CSP Task 12 recorded and the codec matrix from Step 3. Set S27,
  S29, S30, S31 and S43 to `verified` where they passed. A failure caused by a bug is a new task,
  proposed to Dan; a result that would change the spec is the fifth stop.
- [ ] **Step 10: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
docs(spec): 🤖 M2's exit test results: <what passed, in one line>

<each result in a line: playback in each browser, Save, retranslate, the outside edit, the cue
timing numbers; the rows set to verified; anything still pending and why>

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 23
Co-Authored-By: <the model's own line>
```

  `git add docs/superpowers/specs/2026-10-14-vid2sub-design.md`, `git commit -F .git/COMMIT_MSG`,
  then `git log -1 --format='%(trailers)'` shows `Plan:`.
- [ ] **Step 11: Review, look forward, close.** The Tier 3 self-review from
  `$(cat .git/TASK_BASE)` (*Standards*, *Spec*) plus `make check`; the forward review over the
  Phase 3 and 4 plans (the codec matrix decides how much Phase 3's preview copy matters). Then
  the close, its own commit, holding this plan with this task's boxes ticked and **Now** set to
  `Phase end, step 1: The final whole-branch review.`, with the message in `.git/CLOSE_MSG`:

```text
docs(plan): 🤖 close Task 23: The M2 exit test (with Dan)

Drift: none
Rulings: none
Phase-end: none
Forward: none
Tier: 3
Rounds: self-review (Standards, Spec); make check
Findings: none

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 23
Co-Authored-By: <the model's own line>
```

  `git add docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md
  docs/superpowers/specs/2026-10-14-vid2sub-design.md`, `git commit -F .git/CLOSE_MSG`.

***

### Task 24: Phase end

Each box is one step of plan-driven-development's phase end, run as its `references/phase-end.md`
gives it, in the project's root folder on `phase-2`. A step ends with its commit
(`docs(plan): 🤖 phase end step K: <what it did>`, trailer
`Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Phase end`), which ticks its box and
sets **Now** to `Phase end, step K+1: <its title>.` After a crash, resume at the first unticked
box; never re-run a ticked one.

Two parts of the skill aren't built yet, so two steps differ (`AGENTS.md`, the interim line):
there is no `scripts/leakcheck.py`, so step 8's text scans run `gitleaks stdin` only, and the
merge waits for Dan, as every push does.

- [ ] **1. The final whole-branch review:** Matt Pocock's two-axis `code-review` from
  `git merge-base main HEAD`; then one fix dispatch and one scoped re-review (`AGENTS.md`,
  *Reviews*), with a ruling on whatever is left. Each fix is its own commit.
- [ ] **2. The rest of the ledger copied into the plan:** whatever
  `.superpowers/sdd/2026-10-23-vid2sub-phase-2/progress.md` holds that no closing commit carries,
  under the task it belongs to.
- [ ] **3. The phase-end council:** four read-only reviewers (goal fit and scenarios,
  reliability, security, simplicity) on the whole branch; their reports committed first, in
  `docs/superpowers/plans/2026-10-23-vid2sub-phase-2-end-council.md`; each claim checked against
  the code before Dan sees it; each finding a severity and a decision.
- [ ] **4. The phase-end list worked through:** each row of this plan's Phase-end list fixed in
  its own commit at the tier of what it touches, or moved to the spec's Later with a reason.
  Missing docs are written now; in `docs/architecture.md`, Phase 2's parts turn solid.
- [ ] **5. The forward look:** the Phase 3 and Phase 4 plans rewritten to fit what was built
  (every listing that consumes a Phase 2 interface checked against the code).
- [ ] **6. The retro:** `docs/superpowers/plans/2026-10-23-vid2sub-phase-2-retro.md`, in four
  parts (departures from the plan, items carried forward, metrics per tier, starting over), from
  the closing commits:

```bash
base=$(git merge-base main HEAD)
git log --format='%h %s%n%b' --grep='close Task' "$base..HEAD"
git log --format='%h %s' --grep='reopen Task' --grep='escaped from Task' "$base..HEAD"
```

  Then the retuning rules set Phase 3's tiers, written into its plan and the retro.
- [ ] **7. A dated `CHANGELOG.md` entry** for Phase 2, and the spec's status line set to
  `Phase 2 (M2) PR open (#N)`, its number filled in once step 8 opens the PR.
- [ ] **8. The PR:** superpowers:finishing-a-development-branch, its PR option. The title is
  `chore(repo): 🤖 merge Phase 2: the editor`; the body summarises what each task built, the
  council's findings and what became of them, links the retro, lists every file no scan can read
  for Dan to check by eye, and ends with `Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md
  Phase end`. The files no scan can read:

```bash
git log --format= --numstat origin/main..HEAD |
  awk '$1 == "-" { print "not scanned, check by eye: " $3 }'
```

  With the title in `.git/PR_TITLE` and the body in `.git/PR_BODY.md`, then, after Dan's OK to
  push and open it:

```bash
if cat .git/PR_TITLE .git/PR_BODY.md |
     gitleaks stdin --redact --no-banner --config .gitleaks.toml; then
  gh pr create --base main --head phase-2 \
    --title "$(cat .git/PR_TITLE)" --body-file .git/PR_BODY.md
else
  echo "STOP: the PR text has a finding; tell Dan its kind and where, never the matched text"
fi
```

  Attended: the PR waits for Dan's merge (a merge commit, never squash or rebase).
- [ ] **9. After the merge:** this project's docs are read on GitHub and its Pages site arrives in
  Phase 4, so there is no live site to check; the status line's `merged` entry comes with Phase
  3's start.

***

## Phase-end list

| Source task | Severity | File | Finding | Status |
|---|---|---|---|---|
