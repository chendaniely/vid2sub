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
   `tests/fixtures/speech/jfk-14s.wav` into a short MP4 (VP9 and Opus, since Playwright's
   Chromium plays neither H.264 nor AAC) in its temporary copy at start-up, beside a committed
   canned sidecar. Phase 4 replaces it with the non-English clip spec §21 asks for.
7. **Cancel stops between chunks and between translation batches;** a running ffmpeg finishes its
   (short) step first. M1's pipeline has no cancellation, so Task 4 adds a check to `RunContext`.
8. **Retranslating cues a person names replaces them even where a translation was edited:** the
   person asked, so it isn't "replaced automatically" (spec §13.4). **Retranslate stale** never
   replaces an edited cue (S30).
9. **Stale follows spec §13.4 in full, as M1 does:** a cue is stale when its source changed, and
   every unedited cue of a track is stale when the glossary or the translation model changed. So a
   term added at Save makes the whole track stale on the next open. An outside edit keeps the
   glossary hash and model of the version its file was written from, so fixing a typo in an SRT
   marks nothing stale (Task 5, Task 6 round 6f, Task 7).
10. **An outside edit to a file written from an older version diverges** rather than replacing the
    head (spec §14.4), and a Save whose file write fails records the version the file still holds.
    M1's `store` did neither; Task 6 round 6f fixes both (escaped from M1 Task 28).
11. **HostGuard allows only `127.0.0.1`** for the app (`app.HOSTS`), not `localhost` or `::1`:
    the browser is sent to `http://127.0.0.1:<port>/auth`, so the cookie exists only there, and
    a narrower list leaves DNS rebinding less to work with (Task 11).
12. **`vid2sub serve` prints the sign-in link only to a terminal;** when its output goes
    anywhere else it prints the path of the 0600 redirect file instead, so the token never
    reaches a log (spec §6.1, S23; Task 11).
13. **Modal parts are the browser's own `<dialog>` with `showModal()`,** not Radix's modal
    Dialog, Sheet or Select, which inject a `<style>` the CSP blocks: the page behind is inert,
    Esc closes and focus returns (spec §6.3, §19.3). Menus are Radix with `modal={false}`;
    choices are a native `<select>` (Tasks 12, 16, 18).
14. **Shiny's busy-indicator script is served as a file,** so `script-src 'self'` stays as spec
    §6.3 has it and no `style-src` is needed (Task 12, recorded in §29 at its close).

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
- Create: `tests/episodes.py` (M1-shaped episodes for the editor's tests; Tasks 6 and 7 use it)
- Test: `tests/test_backend_open.py`, `tests/test_views.py`

**Interfaces:**
- Consumes: `store.load`, `store.check_external`, `store.source_track`, `store.header_for`;
  `subs.sidecar.Sidecar.head`, `Conflict`, `HeadRecord`; `subs.rendition.cues_from_body`,
  `transcript_from_body`; `subs.lint.lint`, `subs.rules.rules_for`;
  `subs.translate_shape.stale_ids`, `untranslated`; `subs.edit.Tracks`;
  `subs.glossary.parse_glossary`, `Glossary`, `EMPTY_GLOSSARY`, `GlossaryError`;
  `detect.candidates` (`probe_endpoints=False`), `catalog.suggest`; `media.probe.probe`,
  `pick_track`; `media.identity.identify`; `pipeline.video_change`, `pipeline.MEDIA_SUFFIXES`;
  `security.resolve_input`; `cache.Cache`.
- Produces (`vid2sub.web.backend`):
  - `UNPLAYABLE_AUDIO = frozenset({"ac3", "eac3", "dts", "truehd"})` (ffprobe's codec names);
    `NO_SUBTITLES` (the refusal for a video with no sidecar)
  - `@dataclass(frozen=True) class Capabilities: engine: Literal["local", "browser"];
    generate: bool; save: Literal["disk", "download"]; path_input: bool`
  - `class OpenError(Exception)` (a reason fit to show: no sidecar yet, not a full path, not a
    file, a twin with the same name, a sidecar vid2sub can't read, ffprobe's refusal)
  - `@dataclass(frozen=True) class Episode: id: str; video: Path; header: Header; source_key: str;
    tracks: Tracks; heads: dict[str, str]; conflicts: dict[str, tuple[str, ...]];
    words: tuple[Word, ...]; notes: list[str]; playable_audio: bool; audio_index: int;
    sidecar: Sidecar; base: Tracks; glossary: Glossary | None; translate_model: str | None;
    undo: list[tuple[Tracks, dict[str, str]]] = [];
    redo: list[tuple[Tracks, dict[str, str]]] = []; taken: set[str] = set();
    glossary_adds: dict[str, str] = {}`, and the property `dirty -> bool` (`tracks != base` or a
    glossary add waiting). Frozen: every backend call returns a new Episode, so a reactive value
    that holds one sees each change. `header` is the video as probed at open, so
    `header.video.quick_sha256` is the cache key `preview.playback_audio` takes; `heads` names, per
    loaded track, the rendition its cues came from; a track in `conflicts` (its diverged versions'
    rendition ids) isn't in `tracks` or `heads`; a source in conflict opens with
    `tracks.source == ()`; `sidecar` and `base` are as of the open (Task 6: or the last Save);
    `taken` is every cue id any version of any track has used; `audio_index` is the `a:N` index
    of the audio track the transcript was made from (`inputs.audio_track`), else §8.4's pick;
    `glossary` is `vid2sub.glossary.toml` beside the video as M1 reads it (`EMPTY_GLOSSARY` when
    there's none; None, with a note, when it can't be read); `translate_model` is the server's
    name (`ModelEntry.model`) of the model Retranslate would use with none named and no cloud:
    M1's catalog route over the configured models, each local server taken to answer, so open
    makes no request (None when no translation model is usable). Retranslate probes the servers
    and refuses a down one, so the two can differ only when a server answers without listing its
    model.
  - `class LocalBackend: __init__(self, config: Config, tools: Tools, keys: KeyRing, cache: Cache)`
    (`config`, `tools`, `keys`, `cache` attributes); `capabilities(self) -> Capabilities`;
    `open(self, path: str) -> Episode` (the path must be fully qualified, §6.5; it probes, hashes
    the ends and may append outside edits to the sidecar, so it blocks); `is_open(self,
    episode_id: str) -> bool`; `close(self, episode_id: str) -> None`
  - `load_tracks(side: Sidecar) -> tuple[str, Tracks, dict[str, str], dict[str, tuple[str, ...]]]`
    (source key, tracks, heads, conflicts); `cue_ids(side: Sidecar) -> set[str]`
  - Spec §13.4's other two legs, as M1 decides them (`pipeline._translate_targets`):
    `read_glossary(video: Path) -> Glossary` (`GlossaryError` when unreadable);
    `glossary_with(glossary, adds: dict[str, str]) -> Glossary` (as it will read once Save has
    added the terms); `track_setup(ep, track) -> tuple[str, str | None]` (the glossary hash, ""
    for none, and the model the head was made with); `setup_changed(setup, glossary_sha: str |
    None, model: str | None) -> bool` (a None leg is left out); `all_stale(ep, track) -> bool`
    (against the glossary with the terms waiting for Save, and `ep.translate_model`)
  - `vid2sub.web.views.episode_view(ep: Episode, *, video_url: str | None,
    audio_url: str | None) -> dict` (plain JSON, never a path): `id`; `video` (`name`, the bare
    file name; `duration_ms`; `url`; `audio_url`; `playable_audio`); `source`; `tracks` (each
    `key`, `label`, `role` "source" or "translation", `head_by`, `in_conflict`, `all_stale`
    (every cue stale: made with another glossary or model); the source first,
    then the sidecar's order, conflicted tracks included); `rows` (one per source cue: `id`, `n`,
    `start_ms`, `end_ms`, `text`, `w` (`[i, j]` or null), `flags`, and `tr`: per loaded
    translation track `{"cues": [{"id", "start_ms", "end_ms", "text", "src", "detached",
    "flags"}], "flags": [] or ["untranslated"]}`, each cue in the row of the first source cue it
    covers, else the row at its time); `words` (`start_ms`, `end_ms`, `text`, in transcript order:
    `w` indexes them); `dirty`; `can_undo`; `can_redo`; `notes`; `conflicts` (track → its
    versions, each `rendition`, `by`, `at`, `cue_count`); `glossary_adds` (term → translation).
    Flags are sorted: the stored ones (`est`, `halluc`, `edited`) with lint (`cps`, `width`,
    `duration`) by the track's own language rules, `stale` from `translate_shape.stale_ids`, or
    on every cue of a track `all_stale` names (spec §13.4; edited cues too, which keep `edited`).
- Produces (`tests/episodes.py`, for Tasks 5–7): `make_episode(folder, name="Show -
  S01E01.mkv", *, n=3, targets=("en",), audio_langs=("jpn",), audio_codec="aac",
  audio_track=0, project=("ja", "en")) -> Path`; `write_track(video, track, cues, *, role,
  parents=(), by="auto", replaces=None) -> RenditionRecord`; `sid(i)`, `tid(i)` (cue ids
  `ca…`, `cb…`); `LINES`, `ENGLISH`; `source_cues(n)`, `translation_cues(source)`,
  `header_of(video)`, `track_body(cues, track, *, role, engine="vid2sub", model=None)`.

- [ ] **Step 0: Record the base:** `git rev-parse HEAD > .git/TASK_BASE`.
- [ ] **Step 1: Write the failing test,** in two files. First `tests/episodes.py`, the episodes
  the editor's tests open (built with store's own functions in the shape M1 writes):

```python
"""M1-shaped episodes for the editor's tests: a short video, its sidecar and its subtitle files.

Built with store's own functions in the shape M1's pipeline writes (pipeline._transcribe and
_translate_targets): a transcript, a source track whose cues point into its words, a
translation per target whose cues record src and src_sha, auto heads, and each track's SRT
projected next to the video. Ids are fixed (`sid(i)`, `tid(i)`) so tests can name cues; they
have new_cue_id's shape, as the editor's edits require.
"""

from __future__ import annotations

import tempfile
from collections.abc import Sequence
from pathlib import Path

from helpers import make_clip

from vid2sub import store
from vid2sub.media.identity import identify
from vid2sub.media.probe import probe
from vid2sub.media.tools import Tools
from vid2sub.subs.model import Cue, Segment, Transcript, Word
from vid2sub.subs.rendition import cues_body, transcript_body
from vid2sub.subs.sidecar import Header, HeadRecord, RenditionRecord, Sidecar, make_rendition
from vid2sub.subs.translate_shape import src_sha

LINES = ("おはよう", "元気ですか", "はい、元気です")
ENGLISH = ("Good morning", "How are you?", "Yes, I'm fine")
STEP_MS, LENGTH_MS = 3600, 3000  # cue i runs from i × 3.6 s for 3 s


def sid(i: int) -> str:
    return f"ca{i:07x}"


def tid(i: int) -> str:
    return f"cb{i:07x}"


def source_cues(n: int) -> list[Cue]:
    texts = LINES if n == len(LINES) else [f"台詞{i}" for i in range(n)]
    return [Cue(id=sid(i), start_ms=i * STEP_MS, end_ms=i * STEP_MS + LENGTH_MS, text=texts[i],
                w=(2 * i, 2 * i + 2)) for i in range(n)]


def translation_cues(source: Sequence[Cue]) -> list[Cue]:
    texts = ENGLISH if len(source) == len(ENGLISH) else [f"Line {i}" for i in range(len(source))]
    return [Cue(id=tid(i), start_ms=c.start_ms, end_ms=c.end_ms, text=texts[i], src=(c.id,),
                src_sha=src_sha([c.text])) for i, c in enumerate(source)]


def transcript_for(source: Sequence[Cue], *, audio_track: int, quick: str) -> dict:
    """Two words per cue, so cue i's words are 2i and 2i+1 (its `w`)."""
    segments = []
    for c in source:
        mid = (c.start_ms + c.end_ms) // 2
        half = len(c.text) // 2 or 1
        words = (Word(text=c.text[:half], start_ms=c.start_ms, end_ms=mid),
                 Word(text=c.text[half:] or "。", start_ms=mid, end_ms=c.end_ms))
        segments.append(Segment(text=c.text, start_ms=c.start_ms, end_ms=c.end_ms, words=words))
    return transcript_body(
        Transcript(language="ja", segments=tuple(segments)), engine="whisper.cpp",
        model="fake", version="fake@test", created_at=store.now(),
        inputs={"audio_sha256": "0" * 64, "video_quick_sha256": quick,
                "audio_track": audio_track, "timeline_offset_ms": 0},
        meta={})


def header_of(video: Path) -> Header:
    with tempfile.TemporaryDirectory() as scratch:
        duration = probe(video, Tools.find(), scratch=Path(scratch)).duration_ms
    return store.header_for(video, identify(video), duration)


def track_body(cues: Sequence[Cue], track: str, *, role: str, engine: str = "vid2sub",
               model: str | None = None) -> dict:
    lang = "ja" if track == "ja" else track.split("-")[0]
    return cues_body(cues, language=lang, script=None, engine=engine, model=model,
                     version="test", created_at=store.now(), inputs={}, meta={"role": role})


def write_track(video: Path, track: str, cues: Sequence[Cue], *, role: str,
                parents: Sequence[str] = (), by: str = "auto",
                replaces: str | None = None) -> RenditionRecord:
    """Appends a rendition of `track`, and a head for it that replaces `replaces`, to the
    episode's existing sidecar, as another writer (a CLI run, another tab) would."""
    engine, model = ("vid2sub", None) if role == "source" else ("translate:gemma", "gemma")
    rec = make_rendition(list(parents), track, track_body(cues, track, role=role, engine=engine,
                                                          model=model))
    header = store.load(video)[0].header
    store.append(video, header, [rec, HeadRecord(track=track, rendition=rec.id,
                                                 replaces=replaces, by=by, at=store.now())])
    return rec


def make_episode(folder: Path, name: str = "Show - S01E01.mkv", *, n: int = len(LINES),
                 targets: Sequence[str] = ("en",), audio_langs: Sequence[str] = ("jpn",),
                 audio_codec: str = "aac", audio_track: int = 0,
                 project: Sequence[str] = ("ja", "en")) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    video = make_clip(folder, name, seconds=2.0, audio_langs=tuple(audio_langs),
                      audio_codec=audio_codec)
    header = header_of(video)
    source = source_cues(n)
    transcript = make_rendition([], None, transcript_for(
        source, audio_track=audio_track, quick=header.video.quick_sha256))
    src = make_rendition([transcript.id], "ja", track_body(source, "ja", role="source"))
    records: list = [transcript, src,
                     HeadRecord(track="ja", rendition=src.id, by="auto", at=store.now())]
    for target in targets:
        rec = make_rendition([src.id], target, track_body(
            translation_cues(source), target, role="translation", engine="translate:gemma",
            model="gemma"))
        records += [rec, HeadRecord(track=target, rendition=rec.id, by="auto", at=store.now())]
    side: Sidecar = store.append(video, header, records)
    for track in project:
        side, _, _ = store.project(video, header, side, track, "srt", overwrite_foreign=False)
    return video
```

  Then `tests/test_backend_open.py`:

```python
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
from helpers import make_clip

from vid2sub import store
from vid2sub.cache import Cache
from vid2sub.config import Config
from vid2sub.engines.clients import KeyRing
from vid2sub.media.tools import Tools
from vid2sub.subs.edit import Tracks
from vid2sub.subs.model import Cue, Segment, Transcript, Word
from vid2sub.subs.rendition import transcript_body
from vid2sub.subs.sidecar import HeadRecord, make_rendition
from vid2sub.web import backend as web_backend
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
```

- [ ] **Step 2: Run it; watch it fail.** `uv run pytest tests/test_backend_open.py -q`. Expected:
  `E   ModuleNotFoundError: No module named 'vid2sub.web'` and `1 error`.
- [ ] **Step 3: Write the code.** `src/vid2sub/web/__init__.py` (Tasks 8–11 add modules to this
  package):

```python
"""The local web app: the editor's backend, the app shell and its server (spec §19)."""
```

  Then `src/vid2sub/web/backend.py`:

```python
"""The editor's backend: opening an episode M1 made, from its sidecar (spec §19.1, §20, §15.3).

The web app's server calls this, never the store directly, so the CLI and the editor share one
core (spec §18.3); `capabilities()` tells the frontend which controls exist (`BrowserBackend`, in
Pages, is Phase 4's). Phase 2's editor opens only episodes that already have a sidecar: making
subtitles is `vid2sub run` or the Jobs page. Opening folds in edits made outside vid2sub, as
every M1 command does (§15.3, S31), and says so in notes that name files only by their bare name
(§6.8). A track whose heads diverged is in conflict (§14.4): it isn't loaded, and its versions
are listed for the person to pick; when that is the source, every edit waits for the pick, since
translations hang off source cues. The spoken words come from the transcript the source was
built from, following rendition parents, so word highlighting matches the cues' `w` ranges. Audio
in AC-3, E-AC-3, DTS or TrueHD can't be played by a browser (§8.2), so the editor then plays the
playback audio instead (the Phase 2 plan's Decision 2). An `Episode` is never changed in place:
every call returns a new one, so a reactive value that holds it sees each change.
"""

from __future__ import annotations

import os
import secrets
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from vid2sub import store
from vid2sub.cache import Cache
from vid2sub.config import Config
from vid2sub.engines.clients import KeyRing
from vid2sub.media.identity import identify
from vid2sub.media.probe import Probe, ProbeError, pick_track, probe
from vid2sub.media.tools import ToolFailed, ToolMissing, Tools
from vid2sub.pipeline import MEDIA_SUFFIXES, video_change
from vid2sub.security import InputRefused, WriteRefused, resolve_input
from vid2sub.subs import naming
from vid2sub.subs.edit import Tracks
from vid2sub.subs.model import Word
from vid2sub.subs.rendition import cues_from_body, transcript_from_body
from vid2sub.subs.sidecar import (
    Conflict,
    Header,
    HeadRecord,
    RenditionRecord,
    Sidecar,
    SidecarError,
)

UNPLAYABLE_AUDIO = frozenset({"ac3", "eac3", "dts", "truehd"})  # ffprobe's codec names (§8.2)
NO_SUBTITLES = "no subtitles yet: make them with vid2sub run or the Jobs page first"


class OpenError(Exception):
    """An episode that can't be opened; the reason is fit to show."""


@dataclass(frozen=True)
class Capabilities:
    engine: Literal["local", "browser"]
    generate: bool
    save: Literal["disk", "download"]
    path_input: bool


@dataclass(frozen=True)
class Episode:
    id: str
    video: Path
    header: Header  # the video as it is now, from the probe at open
    source_key: str
    tracks: Tracks
    heads: dict[str, str]  # track → the head rendition its cues came from
    conflicts: dict[str, tuple[str, ...]]  # track → its diverged versions (rendition ids)
    words: tuple[Word, ...]
    notes: list[str]
    playable_audio: bool
    audio_index: int  # among audio tracks: ffmpeg's a:N, as preview.playback_audio takes
    sidecar: Sidecar  # as of the open or the last Save
    base: Tracks  # the tracks as of the open or the last Save
    undo: list[tuple[Tracks, dict[str, str]]] = field(default_factory=list)
    redo: list[tuple[Tracks, dict[str, str]]] = field(default_factory=list)
    taken: set[str] = field(default_factory=set)
    glossary_adds: dict[str, str] = field(default_factory=dict)

    @property
    def dirty(self) -> bool:
        return self.tracks != self.base or bool(self.glossary_adds)


class LocalBackend:
    def __init__(self, config: Config, tools: Tools, keys: KeyRing, cache: Cache):
        self.config = config
        self.tools = tools
        self.keys = keys
        self.cache = cache
        self._open: dict[str, Path] = {}
        self._lock = threading.Lock()

    def capabilities(self) -> Capabilities:
        return Capabilities(engine="local", generate=True, save="disk", path_input=True)

    def open(self, path: str) -> Episode:
        """Probes the video and reads its sidecar, recording outside edits first (§15.3)."""
        video = _video(path)
        try:
            side, warnings = store.load(video)
        except SidecarError as err:
            raise OpenError(str(err)) from None
        if side is None:
            raise OpenError(NO_SUBTITLES)
        p = self._probe(video)
        header = store.header_for(video, identify(video), p.duration_ms)
        notes = list(warnings)
        change = video_change(side.header.video, header.video)
        if change:
            notes.append(f"this video changed since its subtitles were made ({change}); its "
                         "transcript may no longer line up")

        def unreadable(name: str) -> None:
            notes.append(f"left {name} alone: it isn't a readable subtitle file")

        try:
            side, changed = store.check_external(video, header, side, on_unreadable=unreadable)
        except (SidecarError, store.StoreError, WriteRefused) as err:
            raise OpenError(str(err)) from None
        except OSError as err:  # never err.filename: a full path
            raise OpenError("couldn't read or write the files next to the video"
                            + (f" ({err.strerror})" if err.strerror else "")) from None
        notes += [f"kept your outside edit to {t}" for t in changed]
        source_key, tracks, heads, conflicts = load_tracks(side)
        transcript = _transcript(side, heads.get(source_key))
        track = _audio_track(p, transcript, naming.TRACKS.get(source_key))
        ep = Episode(
            id="e" + secrets.token_hex(8), video=video, header=header, source_key=source_key,
            tracks=tracks, heads=heads, conflicts=conflicts,
            words=tuple(transcript_from_body(transcript.body).words()) if transcript else (),
            notes=notes, playable_audio=track.codec not in UNPLAYABLE_AUDIO,
            audio_index=track.index, sidecar=side, base=tracks, taken=cue_ids(side))
        with self._lock:
            self._open[ep.id] = video
        return ep

    def is_open(self, episode_id: str) -> bool:
        with self._lock:
            return episode_id in self._open

    def close(self, episode_id: str) -> None:
        """Forgets the episode; unsaved edits in it are dropped (the tab keeps a draft, §14.5)."""
        with self._lock:
            self._open.pop(episode_id, None)

    def _probe(self, video: Path) -> Probe:
        try:
            with tempfile.TemporaryDirectory(prefix="vid2sub-") as scratch:
                return probe(video, self.tools, scratch=Path(scratch))
        except (ProbeError, ToolMissing) as err:
            raise OpenError(str(err)) from None
        except ToolFailed:
            raise OpenError("ffprobe couldn't read this file: check that it plays in a media "
                            "player") from None


def _video(path: str) -> Path:
    """A typed path must be fully qualified (spec §6.5): the server's folder means nothing to
    the person typing."""
    try:
        if not os.path.isabs(os.path.expanduser(path)):
            raise OpenError("give the video's full path")
        video = resolve_input(path)
    except InputRefused as err:
        raise OpenError(str(err)) from None
    if not video.is_file():
        raise OpenError("there's no video at that path")
    twins = [p for p in video.parent.iterdir() if p != video
             and p.stem.casefold() == video.stem.casefold() and p.suffix.lower() in MEDIA_SUFFIXES]
    if twins:
        raise OpenError("another video in this folder has the same name, so their subtitles "
                        "would collide: rename one of them")
    return video


def load_tracks(side: Sidecar) -> tuple[str, Tracks, dict[str, str], dict[str, tuple[str, ...]]]:
    """The source track's key, every track's cues at its head, the heads, and the tracks in
    conflict (not loaded: a person picks a version first, §14.4)."""
    source_key = store.source_track(side) or _forked_source(side)
    if source_key is None:
        raise OpenError(NO_SUBTITLES)
    renditions = side.renditions()
    heads: dict[str, str] = {}
    conflicts: dict[str, tuple[str, ...]] = {}
    loaded: dict[str, tuple] = {}
    for track in side.tracks():
        head = side.head(track)
        if isinstance(head, Conflict):
            conflicts[track] = head.leaves
        elif isinstance(head, HeadRecord):
            heads[track] = head.rendition
            loaded[track] = tuple(cues_from_body(renditions[head.rendition].body))
    source = loaded.pop(source_key, ())
    return source_key, Tracks(source, loaded), heads, conflicts


def cue_ids(side: Sidecar) -> set[str]:
    """Every cue id any version of any track has used: ids are never reused (spec §14.3)."""
    return {c["id"] for r in side.renditions().values() if r.body.get("kind") == "cues"
            for c in r.body["payload"]["cues"]}


def _forked_source(side: Sidecar) -> str | None:
    """A source track in conflict: one of its versions says it is the source."""
    renditions = side.renditions()
    for track in side.tracks():
        head = side.head(track)
        if isinstance(head, Conflict) and any(
                renditions[i].body.get("meta", {}).get("role") == "source"
                for i in head.leaves if i in renditions):
            return track
    return None


def _transcript(side: Sidecar, source_head: str | None) -> RenditionRecord | None:
    """The transcript the source's head was built from, else the newest one."""
    renditions = side.renditions()
    seen: set[str] = set()
    todo = [source_head] if source_head else []
    while todo:
        rid = todo.pop(0)
        if rid in seen or rid not in renditions:
            continue
        seen.add(rid)
        rec = renditions[rid]
        if rec.body.get("kind") == "transcript":
            return rec
        todo += rec.parents
    found = side.transcripts()
    return found[-1] if found else None


def _audio_track(p: Probe, transcript: RenditionRecord | None, info: naming.TrackInfo | None):
    """The track the transcript was made from (its `inputs.audio_track`), else §8.4's pick."""
    if transcript is not None:
        value = str(transcript.body.get("inputs", {}).get("audio_track", ""))
        if value.isdigit() and int(value) < len(p.audio):
            return p.audio[int(value)]
    return pick_track(p, info.lang if info else None)
```

- [ ] **Step 4: Run the checks; they pass.** `uv run pytest tests/test_backend_open.py -q` first
  (`22 passed`), then `make check`. Expected: `558 passed, 2 skipped, 4 deselected` twice (the
  local zone, then UTC), `All checks passed!` and `no leaks found`.
- [ ] **Step 5: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(web): 🤖 the editor's backend opens an M1 episode from its sidecar and keeps outside edits

vid2sub.web.backend (spec §19.1, §20, §15.3; S27, S31):
LocalBackend(config, tools, keys, cache).open(path) takes the full path of
a video that already has a sidecar (else "no subtitles yet: make them with
vid2sub run or the Jobs page first"), probes it, records edits made
outside vid2sub through store.check_external, and says so in notes that
name a file by its bare name only ("kept your outside edit to en", "left
<name> alone: it isn't a readable subtitle file"); a replaced video is
noted with the difference, as M1 does. The Episode holds the source and
translation tracks at their heads as subs.edit.Tracks, the heads, the
tracks in conflict (listed, not loaded; a source in conflict opens with
nothing to edit), the words of the transcript the source was built from,
the audio track that transcript used (else §8.4's pick) and whether a
browser can play it (not AC-3, E-AC-3, DTS or TrueHD: the plan's Decision
2), and every cue id any version has used. Episodes are frozen: every call
returns a new one. tests/episodes.py builds M1-shaped episodes for this
task and the next two.

The new test failed first with: ModuleNotFoundError: No module named
'vid2sub.web'.

Docs read: none beyond the code (store.load, check_external and
source_track; pipeline._check_external, _resolve and video_change;
media.probe.pick_track; subs.sidecar.Sidecar.head).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 5
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/web/__init__.py src/vid2sub/web/backend.py tests/episodes.py
  tests/test_backend_open.py`, `git commit -F .git/COMMIT_MSG`, then `git log -1
  --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 6: Write the failing test,** `tests/test_views.py`:

```python
import dataclasses
import json
import time
from pathlib import Path

import pytest
from episodes import ENGLISH, LINES, make_episode, sid, source_cues, tid, translation_cues

from vid2sub.cache import Cache
from vid2sub.config import Config
from vid2sub.engines.clients import KeyRing
from vid2sub.media.tools import Tools
from vid2sub.subs.edit import Tracks
from vid2sub.subs.model import Cue, Word
from vid2sub.subs.rendition import cues_body
from vid2sub.subs.sidecar import Header, HeadRecord, Sidecar, VideoInfo, make_rendition
from vid2sub.web import views
from vid2sub.web.backend import Episode, LocalBackend

VIDEO = Path("/Users/someone/Secret Shows/Show - S01E01.mkv")
HEADER = Header(video=VideoInfo(name=VIDEO.name, size=1, quick_sha256="a" * 64,
                                duration_ms=20_000))
AT = "2026-10-23T10:00:00Z"


def body(cues, lang: str, role: str) -> dict:
    return cues_body(cues, language=lang, script=None, engine="vid2sub", model=None,
                     version="t", created_at=AT, inputs={}, meta={"role": role})


def episode(source=None, en=None, *, records=(), **changes) -> Episode:
    source = tuple(source_cues(3) if source is None else source)
    en = tuple(translation_cues(source) if en is None else en)
    ja_rec = make_rendition([], "ja", body(source, "ja", "source"))
    en_rec = make_rendition([ja_rec.id], "en", body(en, "en", "translation"))
    side = Sidecar(HEADER, (ja_rec, HeadRecord(track="ja", rendition=ja_rec.id, by="auto", at=AT),
                            en_rec, HeadRecord(track="en", rendition=en_rec.id, by="editor",
                                               at="2026-10-23T11:00:00Z"), *records))
    tracks = Tracks(source, {"en": en})
    words = tuple(Word(text=t, start_ms=k * 500, end_ms=k * 500 + 400)
                  for k, t in enumerate(["おは", "よう"]))
    ep = Episode(id="e1", video=VIDEO, header=HEADER, source_key="ja", tracks=tracks,
                 heads={"ja": ja_rec.id, "en": en_rec.id}, conflicts={}, words=words, notes=[],
                 playable_audio=True, audio_index=0, sidecar=side, base=tracks)
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
         "in_conflict": False},
        {"key": "en", "label": "English", "role": "translation", "head_by": "editor",
         "in_conflict": False},
        {"key": "zh-Hant", "label": "Mandarin (Traditional)", "role": "translation",
         "head_by": None, "in_conflict": True},
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
    v = view(dataclasses.replace(ep, tracks=changed, undo=[(ep.tracks, {})]))
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
```

- [ ] **Step 7: Run it; watch it fail.** `uv run pytest tests/test_views.py -q`. Expected:
  `E   ImportError: cannot import name 'views' from 'vid2sub.web' (…/src/vid2sub/web/__init__.py)`
  and `1 error`.
- [ ] **Step 8: Write the code,** `src/vid2sub/web/views.py`:

```python
"""The editor's view of an episode: plain JSON for the React frontend (spec §19.1, §20, §12.5).

A pure function of the `Episode`, so the shinyreact server only sends what it returns, and every
flag the cue list shows is computed here once. One row per source cue, in order, with each
translation track's cues in the row of the first source cue they cover; a translation whose
source cues are all gone sits in the row at its time, so nothing is hidden. Flags are the stored
ones (`est`, `halluc`, `edited`) with the lint flags recomputed each time, never stored as truth
(§12.5): reading speed, width and duration by each track's own language rules; `stale` from the
source text a translation was made from (§13.4); `untranslated` for a source cue no translation
in a track covers. The view never holds a path, only the video's bare file name (§6.8).
"""

from __future__ import annotations

from bisect import bisect_right
from typing import Any

from vid2sub.subs import langs, naming
from vid2sub.subs.lint import lint
from vid2sub.subs.model import Cue
from vid2sub.subs.rules import rules_for
from vid2sub.subs.sidecar import HeadRecord
from vid2sub.subs.translate_shape import stale_ids, untranslated
from vid2sub.web.backend import Episode

_SCRIPTS = {"Hant": " (Traditional)", "Hans": " (Simplified)"}


def episode_view(ep: Episode, *, video_url: str | None, audio_url: str | None) -> dict[str, Any]:
    return {
        "id": ep.id,
        "video": {"name": ep.video.name, "duration_ms": ep.header.video.duration_ms,
                  "url": video_url, "audio_url": audio_url, "playable_audio": ep.playable_audio},
        "source": ep.source_key,
        "tracks": _tracks(ep),
        "rows": _rows(ep),
        "words": [{"start_ms": w.start_ms, "end_ms": w.end_ms, "text": w.text}
                  for w in ep.words],
        "dirty": ep.dirty,
        "can_undo": bool(ep.undo),
        "can_redo": bool(ep.redo),
        "notes": list(ep.notes),
        "conflicts": _conflicts(ep),
        "glossary_adds": dict(ep.glossary_adds),
    }


def _rows(ep: Episode) -> list[dict[str, Any]]:
    source = ep.tracks.source
    linted = lint(source, rules_for(_lang(ep.source_key)))
    rows = [{"id": c.id, "n": n, "start_ms": c.start_ms, "end_ms": c.end_ms, "text": c.text,
             "w": list(c.w) if c.w else None, "flags": _flags(c.flags, linted.get(c.id, ())),
             "tr": {}} for n, c in enumerate(source, 1)]
    if not rows:
        return rows
    by_id = {c.id: c for c in source}
    index = {c.id: k for k, c in enumerate(source)}
    starts = [c.start_ms for c in source]
    for track, cues in ep.tracks.translations.items():
        linted = lint(cues, rules_for(_lang(track)))
        stale = stale_ids(cues, by_id)
        cells: list[dict[str, list]] = [{"cues": [], "flags": []} for _ in rows]
        for c in cues:
            extra = ("stale",) if c.id in stale else ()
            cells[_row_of(c, index, starts)]["cues"].append({
                "id": c.id, "start_ms": c.start_ms, "end_ms": c.end_ms, "text": c.text,
                "src": list(c.src or ()), "detached": c.detached,
                "flags": _flags(c.flags, linted.get(c.id, ()) + extra)})
        for cid in untranslated(list(index), cues):
            cells[index[cid]]["flags"] = ["untranslated"]
        for row, cell in zip(rows, cells, strict=True):
            row["tr"][track] = cell
    return rows


def _row_of(c: Cue, index: dict[str, int], starts: list[int]) -> int:
    """The row of the first source cue it covers; else the row at its time."""
    covered = [index[i] for i in c.src or () if i in index]
    if covered:
        return min(covered)
    return max(bisect_right(starts, c.start_ms) - 1, 0)


def _tracks(ep: Episode) -> list[dict[str, Any]]:
    keys = [ep.source_key] + [t for t in ep.sidecar.tracks() if t != ep.source_key
                              and (t in ep.tracks.translations or t in ep.conflicts)]
    out = []
    for key in keys:
        head = ep.sidecar.head(key)
        out.append({"key": key, "label": _label(key),
                    "role": "source" if key == ep.source_key else "translation",
                    "head_by": head.by if isinstance(head, HeadRecord) else None,
                    "in_conflict": key in ep.conflicts})
    return out


def _conflicts(ep: Episode) -> dict[str, list[dict[str, Any]]]:
    renditions = ep.sidecar.renditions()
    out: dict[str, list[dict[str, Any]]] = {}
    for track, leaves in ep.conflicts.items():
        heads = {h.rendition: h for h in ep.sidecar.heads(track)}  # the latest for each
        out[track] = []
        for rid in leaves:
            head, rec = heads.get(rid), renditions.get(rid)
            out[track].append({
                "rendition": rid, "by": head.by if head else None, "at": head.at if head else None,
                "cue_count": len(rec.body.get("payload", {}).get("cues", [])) if rec else 0})
    return out


def _flags(stored: tuple[str, ...], computed: tuple[str, ...]) -> list[str]:
    return sorted(set(stored) | set(computed))


def _lang(track: str) -> str:
    info = naming.TRACKS.get(track)
    return info.lang if info else track.split("-")[0]


def _label(track: str) -> str:
    info = naming.TRACKS.get(track)
    if info is None:
        return track
    name = langs.LANGS[info.lang].name if info.lang in langs.LANGS else info.lang
    return name + _SCRIPTS.get(info.script or "", "")
```

- [ ] **Step 9: Run the checks; they pass.** `uv run pytest tests/test_views.py -q` first
  (`14 passed`; the two-hour test took about 0.08 s where this listing was built: 0.06 s to open,
  0.02 s for the view), then `make check`. Expected: `572 passed, 2 skipped, 4 deselected` twice,
  `All checks passed!` and `no leaks found`.
- [ ] **Step 10: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(web): 🤖 the editor's view lists one row per source cue with its translations, flags and words, as JSON

vid2sub.web.views.episode_view(ep, *, video_url, audio_url) (spec §19.1,
§20, §12.5; S27): a pure function of the Episode, so the server sends
only what it returns. One row per source cue, in order: its number, times,
text, word range and flags (stored est and halluc with the lint flags
recomputed by the source language's rules); per translation track, the
cues whose first source cue is this row, each with its stored flags,
lint by its own language's rules, and stale when its source text changed
(translate_shape.stale_ids); untranslated where no cue of that track
covers the row. A translation whose source cues are all gone sits in the
row at its time. Also the tracks (key, label, role, who set the head, in
conflict), the words, dirty, can_undo and can_redo, the notes, each
version of a track in conflict (who, when, how many cues) and the
pending glossary adds. Never a path: only the video's bare name.

The new test failed first with: ImportError: cannot import name 'views'
from 'vid2sub.web'. Review Focus 3: opening a 2,000-cue episode and
building its view took about 0.08 s here (0.06 s open, 0.02 s view);
the test bounds it at 1 s.

Docs read: none beyond the code (subs.lint.lint, rules.rules_for,
translate_shape.stale_ids and untranslated, naming.TRACKS, langs.LANGS).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 5
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/web/views.py tests/test_views.py`, `git commit -F .git/COMMIT_MSG`, then
  `git log -1 --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 11: Write the failing tests:** a translation made with another glossary or model is
  stale (spec §13.4). Replace `tests/test_views.py` with this version (the `episode` helper
  gains the glossary and model; each track says `all_stale`; six new tests above the two-hour
  test):

```python
import dataclasses
import json
import time
from pathlib import Path

import pytest
from episodes import ENGLISH, LINES, make_episode, sid, source_cues, tid, translation_cues

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
    v = view(dataclasses.replace(ep, tracks=changed, undo=[(ep.tracks, {})]))
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
    v = view(episode(glossary=GLOSSARY))
    assert en_flags(v) == [["stale"]] * 3
    assert [t["all_stale"] for t in v["tracks"]] == [False, True]


def test_a_translation_made_with_the_glossary_beside_the_video_is_not():
    assert en_flags(view(episode(glossary=GLOSSARY, en_glossary_sha=GLOSSARY.sha()))) == [[]] * 3


def test_a_glossary_term_waiting_for_save_makes_every_translation_stale():
    ep = episode()
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
    assert en_flags(view(episode(source, en, glossary=GLOSSARY)))[1] == ["edited", "stale"]


def test_an_unreadable_glossary_or_no_usable_model_leaves_that_leg_out():
    ep = episode(en_model="old", en_glossary_sha="abcd1234", glossary=None, translate_model=None)
    assert en_flags(view(ep)) == [[]] * 3


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
```

  and replace `tests/test_backend_open.py` with this version (the first test checks the two new
  fields; four new tests at the end):

```python
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
```

- [ ] **Step 12: Run them; watch them fail.** `uv run pytest tests/test_views.py
  tests/test_backend_open.py -q`. Expected: `E       TypeError: Episode.__init__() got an
  unexpected keyword argument 'glossary'` (19 times), `E       AttributeError: 'Episode' object
  has no attribute 'glossary'` and `… 'translate_model'`, and `24 failed, 22 passed`.
- [ ] **Step 13: Write the code.**
  In `src/vid2sub/web/backend.py`, replace the module docstring

```python
"""The editor's backend: opening an episode M1 made, from its sidecar (spec §19.1, §20, §15.3).

The web app's server calls this, never the store directly, so the CLI and the editor share one
core (spec §18.3); `capabilities()` tells the frontend which controls exist (`BrowserBackend`, in
Pages, is Phase 4's). Phase 2's editor opens only episodes that already have a sidecar: making
subtitles is `vid2sub run` or the Jobs page. Opening folds in edits made outside vid2sub, as
every M1 command does (§15.3, S31), and says so in notes that name files only by their bare name
(§6.8). A track whose heads diverged is in conflict (§14.4): it isn't loaded, and its versions
are listed for the person to pick; when that is the source, every edit waits for the pick, since
translations hang off source cues. The spoken words come from the transcript the source was
built from, following rendition parents, so word highlighting matches the cues' `w` ranges. Audio
in AC-3, E-AC-3, DTS or TrueHD can't be played by a browser (§8.2), so the editor then plays the
playback audio instead (the Phase 2 plan's Decision 2). An `Episode` is never changed in place:
every call returns a new one, so a reactive value that holds it sees each change.
"""
```

  with

```python
"""The editor's backend: opening an episode M1 made, from its sidecar (spec §19.1, §20, §15.3).

The web app's server calls this, never the store directly, so the CLI and the editor share one
core (spec §18.3); `capabilities()` tells the frontend which controls exist (`BrowserBackend`, in
Pages, is Phase 4's). Phase 2's editor opens only episodes that already have a sidecar: making
subtitles is `vid2sub run` or the Jobs page. Opening folds in edits made outside vid2sub, as
every M1 command does (§15.3, S31), and says so in notes that name files only by their bare name
(§6.8). A track whose heads diverged is in conflict (§14.4): it isn't loaded, and its versions
are listed for the person to pick; when that is the source, every edit waits for the pick, since
translations hang off source cues. The spoken words come from the transcript the source was
built from, following rendition parents, so word highlighting matches the cues' `w` ranges. Audio
in AC-3, E-AC-3, DTS or TrueHD can't be played by a browser (§8.2), so the editor then plays the
playback audio instead (the Phase 2 plan's Decision 2). An `Episode` is never changed in place:
every call returns a new one, so a reactive value that holds it sees each change. A translation
is stale, as spec §13.4 says and M1 decides (pipeline._translate_targets), when its source text
changed, and every cue of it is when the glossary's hash or the translation model differs from
the ones its head was made with; so the episode holds the glossary beside the video and the model
Retranslate would use with none named, picked offline from the catalog route as M1 picks it but
taking every configured local server to answer (no request is made at open).
"""
```

  Replace

```python
from vid2sub import store
```

  with

```python
from vid2sub import detect as detecting
from vid2sub import store
```

  Replace

```python
from vid2sub.cache import Cache
```

  with

```python
from vid2sub.cache import Cache
from vid2sub.catalog import suggest
```

  Replace

```python
from vid2sub.subs.edit import Tracks
```

  with

```python
from vid2sub.subs.edit import Tracks
from vid2sub.subs.glossary import EMPTY_GLOSSARY, Glossary, GlossaryError, parse_glossary
```

  In `class Episode`, below `base: Tracks  # …`, add:

```python
    glossary: Glossary | None  # beside the video at open; None if it couldn't be read
    translate_model: str | None  # the model Retranslate would use with none named (offline)
```

  In `open`, below `track = _audio_track(p, transcript, naming.TRACKS.get(source_key))`, add:

```python
        try:
            glossary: Glossary | None = read_glossary(video)
        except GlossaryError as err:
            glossary = None
            notes.append(f"couldn't read {naming.GLOSSARY_NAME}: {err}")
```

  and replace the last line of the `Episode(…)` call

```python
            audio_index=track.index, sidecar=side, base=tracks, taken=cue_ids(side))
```

  with

```python
            audio_index=track.index, sidecar=side, base=tracks, taken=cue_ids(side),
            glossary=glossary, translate_model=self._route_model(_lang(source_key)))
```

  Directly above `    def _probe(self, video: Path) -> Probe:`, add (followed by one blank line):

```python
    def _route_model(self, lang: str) -> str | None:
        """The model Retranslate would use with none named and no cloud: M1's catalog route over
        the configured models, each local server taken to answer (`probe_endpoints=False`)."""
        cands = detecting.candidates(self.config, self.keys, probe_endpoints=False)
        name = suggest(lang, cands, "translate", allow_cloud=False).model
        return self.config.models[name].model if name else None
```

  At the end of the file, after two blank lines, add (each function followed by two blank lines but the last):

```python
def read_glossary(video: Path) -> Glossary:
    """The glossary beside the video, read as M1 reads it; EMPTY_GLOSSARY when there's none."""
    path = video.with_name(naming.GLOSSARY_NAME)
    if not path.is_file():
        return EMPTY_GLOSSARY
    try:
        return parse_glossary(path.read_text(encoding="utf-8-sig"))
    except UnicodeDecodeError:
        raise GlossaryError("the glossary isn't UTF-8; save it as UTF-8") from None


def glossary_with(glossary: Glossary, adds: dict[str, str]) -> Glossary:
    """The glossary as it will read once Save has added `adds`: a term it has keeps its own."""
    have = dict(glossary.terms)
    return Glossary(glossary.description, glossary.terms + tuple(
        (term, translation) for term, translation in adds.items() if term not in have))


def track_setup(ep: Episode, track: str) -> tuple[str, str | None]:
    """The glossary hash ("" for none) and the model the track's cues were made with."""
    body = ep.sidecar.renditions()[ep.heads[track]].body
    return body.get("payload", {}).get("glossary_sha") or "", body.get("model")


def setup_changed(setup: tuple[str, str | None], glossary_sha: str | None,
                  model: str | None) -> bool:
    """Spec §13.4's other two legs, as M1 decides them: the glossary's hash, or the model, isn't
    the one the cues were made with. A leg whose current value is unknown (None) is left out."""
    made_sha, made_model = setup
    return ((glossary_sha is not None and made_sha != glossary_sha)
            or (model is not None and made_model != model))


def all_stale(ep: Episode, track: str) -> bool:
    """Every cue of a loaded translation track is stale: against the glossary beside the video
    with the terms waiting for Save, and the model Retranslate would use with none named."""
    sha = None if ep.glossary is None else glossary_with(ep.glossary, ep.glossary_adds).sha()
    return setup_changed(track_setup(ep, track), sha, ep.translate_model)


def _lang(track: str) -> str:
    info = naming.TRACKS.get(track)
    return info.lang if info else track.split("-")[0]
```

  Replace `src/vid2sub/web/views.py` with:

```python
"""The editor's view of an episode: plain JSON for the React frontend (spec §19.1, §20, §12.5).

A pure function of the `Episode`, so the shinyreact server only sends what it returns, and every
flag the cue list shows is computed here once. One row per source cue, in order, with each
translation track's cues in the row of the first source cue they cover; a translation whose
source cues are all gone sits in the row at its time, so nothing is hidden. Flags are the stored
ones (`est`, `halluc`, `edited`) with the lint flags recomputed each time, never stored as truth
(§12.5): reading speed, width and duration by each track's own language rules; `stale` from the
source text a translation was made from, and on every cue of a track made with another glossary
or model (§13.4, `backend.all_stale`); `untranslated` for a source cue no translation in a track
covers. The view never holds a path, only the video's bare file name (§6.8).
"""

from __future__ import annotations

from bisect import bisect_right
from typing import Any

from vid2sub.subs import langs, naming
from vid2sub.subs.lint import lint
from vid2sub.subs.model import Cue
from vid2sub.subs.rules import rules_for
from vid2sub.subs.sidecar import HeadRecord
from vid2sub.subs.translate_shape import stale_ids, untranslated
from vid2sub.web.backend import Episode, all_stale

_SCRIPTS = {"Hant": " (Traditional)", "Hans": " (Simplified)"}


def episode_view(ep: Episode, *, video_url: str | None, audio_url: str | None) -> dict[str, Any]:
    return {
        "id": ep.id,
        "video": {"name": ep.video.name, "duration_ms": ep.header.video.duration_ms,
                  "url": video_url, "audio_url": audio_url, "playable_audio": ep.playable_audio},
        "source": ep.source_key,
        "tracks": _tracks(ep),
        "rows": _rows(ep),
        "words": [{"start_ms": w.start_ms, "end_ms": w.end_ms, "text": w.text}
                  for w in ep.words],
        "dirty": ep.dirty,
        "can_undo": bool(ep.undo),
        "can_redo": bool(ep.redo),
        "notes": list(ep.notes),
        "conflicts": _conflicts(ep),
        "glossary_adds": dict(ep.glossary_adds),
    }


def _rows(ep: Episode) -> list[dict[str, Any]]:
    source = ep.tracks.source
    linted = lint(source, rules_for(_lang(ep.source_key)))
    rows = [{"id": c.id, "n": n, "start_ms": c.start_ms, "end_ms": c.end_ms, "text": c.text,
             "w": list(c.w) if c.w else None, "flags": _flags(c.flags, linted.get(c.id, ())),
             "tr": {}} for n, c in enumerate(source, 1)]
    if not rows:
        return rows
    by_id = {c.id: c for c in source}
    index = {c.id: k for k, c in enumerate(source)}
    starts = [c.start_ms for c in source]
    for track, cues in ep.tracks.translations.items():
        linted = lint(cues, rules_for(_lang(track)))
        stale = {c.id for c in cues} if all_stale(ep, track) else stale_ids(cues, by_id)
        cells: list[dict[str, list]] = [{"cues": [], "flags": []} for _ in rows]
        for c in cues:
            extra = ("stale",) if c.id in stale else ()
            cells[_row_of(c, index, starts)]["cues"].append({
                "id": c.id, "start_ms": c.start_ms, "end_ms": c.end_ms, "text": c.text,
                "src": list(c.src or ()), "detached": c.detached,
                "flags": _flags(c.flags, linted.get(c.id, ()) + extra)})
        for cid in untranslated(list(index), cues):
            cells[index[cid]]["flags"] = ["untranslated"]
        for row, cell in zip(rows, cells, strict=True):
            row["tr"][track] = cell
    return rows


def _row_of(c: Cue, index: dict[str, int], starts: list[int]) -> int:
    """The row of the first source cue it covers; else the row at its time."""
    covered = [index[i] for i in c.src or () if i in index]
    if covered:
        return min(covered)
    return max(bisect_right(starts, c.start_ms) - 1, 0)


def _tracks(ep: Episode) -> list[dict[str, Any]]:
    keys = [ep.source_key] + [t for t in ep.sidecar.tracks() if t != ep.source_key
                              and (t in ep.tracks.translations or t in ep.conflicts)]
    out = []
    for key in keys:
        head = ep.sidecar.head(key)
        out.append({"key": key, "label": _label(key),
                    "role": "source" if key == ep.source_key else "translation",
                    "head_by": head.by if isinstance(head, HeadRecord) else None,
                    "in_conflict": key in ep.conflicts,
                    "all_stale": key in ep.tracks.translations and all_stale(ep, key)})
    return out


def _conflicts(ep: Episode) -> dict[str, list[dict[str, Any]]]:
    renditions = ep.sidecar.renditions()
    out: dict[str, list[dict[str, Any]]] = {}
    for track, leaves in ep.conflicts.items():
        heads = {h.rendition: h for h in ep.sidecar.heads(track)}  # the latest for each
        out[track] = []
        for rid in leaves:
            head, rec = heads.get(rid), renditions.get(rid)
            out[track].append({
                "rendition": rid, "by": head.by if head else None, "at": head.at if head else None,
                "cue_count": len(rec.body.get("payload", {}).get("cues", [])) if rec else 0})
    return out


def _flags(stored: tuple[str, ...], computed: tuple[str, ...]) -> list[str]:
    return sorted(set(stored) | set(computed))


def _lang(track: str) -> str:
    info = naming.TRACKS.get(track)
    return info.lang if info else track.split("-")[0]


def _label(track: str) -> str:
    info = naming.TRACKS.get(track)
    if info is None:
        return track
    name = langs.LANGS[info.lang].name if info.lang in langs.LANGS else info.lang
    return name + _SCRIPTS.get(info.script or "", "")
```

- [ ] **Step 14: Run the checks; they pass.** `uv run pytest tests/test_views.py
  tests/test_backend_open.py -q` first (`46 passed`), then `make check`. Expected: `582
  passed, 2 skipped, 4 deselected` twice, `All checks passed!` and `no leaks found`.
- [ ] **Step 15: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(web): 🤖 a translation made with another glossary or model shows every cue stale, as spec §13.4 says

The editor's stale follows spec §13.4 in full, as M1 decides it
(pipeline._translate_targets): besides a source cue gone or changed, every
cue of a translation track is stale when its head's payload.glossary_sha
(absent is "") differs from the glossary's hash, or its `model` differs
from the model a run would use. The Episode gains `glossary` (read at
open as M1 reads it; None, with a note, when it can't be read) and
`translate_model` (the model Retranslate would use with none named: M1's
catalog route over the configured models with no cloud, each local
server taken to answer, detect.candidates(probe_endpoints=False), so open
makes no request). backend.all_stale(ep, track) compares against the
glossary with the terms waiting for Save and that model; a leg whose
current value is unknown is left out. The view flags every cue of such a
track stale (edited cues too, which keep their flag) and each track says
`all_stale`. Helpers for Tasks 6 and 7: read_glossary, glossary_with,
track_setup, setup_changed.

The new tests failed first with: TypeError: Episode.__init__() got an
unexpected keyword argument 'glossary' (19 times) and AttributeError:
'Episode' object has no attribute 'glossary' / 'translate_model';
24 failed, 22 passed.

Docs read: none beyond the code (pipeline._translate_targets lines
645-647 and _translator, detect.candidates' probe_endpoints,
catalog.suggest).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 5
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/web/backend.py src/vid2sub/web/views.py tests/test_views.py
  tests/test_backend_open.py`, `git commit -F .git/COMMIT_MSG`, then `git log -1
  --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 16: Review, look forward, close.** The Tier 2 review from `$(cat .git/TASK_BASE)`
  (`AGENTS.md`, *Reviews*); the forward review over Tasks 6, 7, 10, 14, 16 and 17 (Task 6 adds
  `apply`, `undo`, `redo`, `save` and `resolve` on this `Episode`, reading `heads`, `base` and
  `sidecar`; Task 7's `retranslate` reads `stale_ids` and `untranslated` as this view does;
  Task 7's stale set takes the same two legs against the model it uses; Task 10's media tokens
  are owned by `ep.id`; Task 14 calls `open` off Shiny's event loop (it
  blocks on ffprobe and the disk), passes `video_url` only when `ep.playable_audio` and the
  browser can play the file, else `audio_url` from `preview.playback_audio(ep.video,
  key=ep.header.video.quick_sha256, audio_index=ep.audio_index, …)`, and renders `rows` and
  `words`, and says why every cue of a track is stale when its `all_stale` is set (the glossary
  or the model changed; a glossary term waiting for Save does it too); Task 16's conflict picker
  reads `conflicts`); the docs this task made untrue: the
  spec's S31 row names `tests/test_external.py`, a file that doesn't exist; its Proof becomes
  `tests/test_backend_open.py::test_an_outside_edit_comes_back_as_the_head_and_the_editor_says_so;
  the exit test`. Then the close, its own commit, holding this plan with this task's boxes ticked
  and **Now** set to `Task 6: The editor backend: edits and Save, open.`, and the spec with S31's
  Proof corrected; S27 and S31 stay `planned` (their Playwright and exit-test proofs are Tasks
  14 and 23). The message, in `.git/CLOSE_MSG`:

```text
docs(plan): 🤖 close Task 5: The editor backend: opening an episode

Drift: none
Rulings: none
Phase-end: none
Forward: none
Tier: 2
Rounds: none
Findings: none

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 5
Co-Authored-By: <the model's own line>
```

  `git add docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md
  docs/superpowers/specs/2026-10-14-vid2sub-design.md`, `git commit -F .git/CLOSE_MSG`.

***

### Task 6: The editor backend: edits and Save

**Tier:** 1 · **Scenarios:** S28, S29, S32

**Files:**
- Create: `src/vid2sub/web/ops.py`
- Modify: `src/vid2sub/web/backend.py`, `src/vid2sub/subs/glossary.py` (`add_terms`: the
  glossary had no writer), `src/vid2sub/store.py` (`check_external` and `project`: round 6f,
  escaped from M1 Task 28)
- Test: `tests/test_ops.py`, `tests/test_backend_edit.py`, `tests/test_backend_save.py`,
  `tests/test_glossary.py` (the writer's tests), `tests/test_store.py` (round 6f)

**Interfaces:**
- Consumes: Task 2's `subs.edit` (every operation, `EditError`, `SOURCE`, `Tracks`); Task 5's
  `Episode`, `LocalBackend`, `OpenError`, `load_tracks`, `cue_ids`, `tests/episodes.py`;
  `store.append`, `store.project`, `store.load`, `store.sidecar_path`, `store.subtitle_path`,
  `ForeignFile`, `EditedOnDisk`, `StoreError`; `subs.sidecar.make_rendition`, `HeadRecord`,
  `Conflict`; `subs.rendition.cues_body`; `subs.glossary.parse_glossary`;
  `security.safe_write`, `WriteRefused`.
- Produces:
  - `vid2sub.web.ops`: `SetText{cue, text}`, `SetTranslationText{track, cue, text}`,
    `SetTimes{cue, start_ms?, end_ms?}` (one of them), `Nudge{cue, delta_ms, edge="both"}`,
    `Split{cue, at_char, at_ms}`, `MergeNext{cue}`, `Insert{start_ms, end_ms, text}`,
    `Delete{cue}`, `Detach{track, cue, detached}`, `ReplaceAll{find, replace, tracks}`,
    `GlossaryAdd{term, translation}`: pydantic models with `extra="forbid"`, `strict`, frozen,
    each `op` a Literal with its own name as default; `EditOp` (their union, discriminated on
    `op`); `EDIT_KINDS`; bounds `MAX_MS` (48 h), `MAX_TEXT` (2,000), `MAX_TERM` (200); cue ids
    `^c[0-9a-f]{8}$`; tracks the keys of `naming.TRACKS` (and `"source"` in `replace_all`);
    `parse_op(data: object) -> EditOp`; `class BadOp(ValueError)` with `.field` (the field's
    name, or None for an unknown field or a non-object), message
    `this edit can't be made: <field> <reason>`, never the value, never chained.
  - `LocalBackend.apply(self, ep, op: ops.EditOp) -> Episode` (one undo step; `ep` itself when
    nothing changed; `EditError` when the rules refuse, when the track or the source is in
    conflict, and for a split, merge or delete while any translation is); `undo(self, ep) ->
    Episode`; `redo(self, ep) -> Episode` (`ep` itself with
    nothing to step to); `backend.UNDO_STEPS = 200`. The undo and redo stacks hold
    `(tracks, glossary_adds)`, so a glossary add is undone like an edit. A closed episode raises
    `OpenError`.
  - `class SaveError(Exception)` (nothing was saved; a reason fit to show);
    `@dataclass(frozen=True) class SaveResult: written: tuple[str, ...]; foreign: tuple[str, ...];
    conflicts: tuple[str, ...]; notes: tuple[str, ...]` (bare file names; `foreign` is left
    alone: someone else's, or changed outside since; `conflicts` is every track in conflict after
    the call, none of whose files were written)
  - `LocalBackend.save(self, ep, *, formats: Sequence[Literal["srt", "ass"]])
    -> tuple[Episode, SaveResult]` (SRT always; blocks on the disk). It records outside edits
    first (`store.check_external`; its notes come back in `notes`), skips a track whose head on
    disk already holds these cues, and once the versions are appended never raises. Afterwards
    the episode's tracks, heads and conflicts are read back from the sidecar, `dirty` is false
    unless glossary terms are still waiting, and undo and redo are empty.
  - `LocalBackend.resolve(self, ep, track: str, rendition: str) -> tuple[Episode, SaveResult]`
    (changed from the skeleton's `-> Episode`: a pick writes the track's files, and the server
    must say which it couldn't); `SaveError` for an unknown track, a track not in conflict in
    `ep`, or a rendition that isn't one of the track's versions. Saves and picks on one video
    take turns within one `LocalBackend` (a lock per video).
  - After a Save the episode's `glossary` is read back from the file, so a term just added makes
    every translation made without it stale (`backend.all_stale`, spec §13.4), as M1 decides it:
    intended (round 6g).
  - `store.check_external`: an outside edit's head replaces the version its file was written
    from (`proj.rendition`), not the current head, so an edit to a file the head has moved on
    from diverges from it (spec §14.4); `store.project`: a write that fails with `OSError` or
    `WriteRefused` puts the file's previous projection record back; the external version copies
    the `model` and `payload.glossary_sha` of the version its file was written from; `align_ids`
    marks a line with no match (added, or reworded and retimed) `edited`, as it already marked a
    reworded one (round 6f).
  - `subs.glossary.add_terms(text: str, adds: Mapping[str, str]) -> tuple[str, list[str]]`
    (pure: the new text, and the terms kept with the file's other translation).

- [ ] **Step 0: Record the base:** `git rev-parse HEAD > .git/TASK_BASE`.
- [ ] **Step 1: Write the failing test,** `tests/test_ops.py`:

```python
import pytest
from pydantic import ValidationError

from vid2sub.subs.model import new_cue_id
from vid2sub.web import ops
from vid2sub.web.ops import BadOp

CUE = "ca0000001"
SECRET = "SECRET-7f3a"  # stands for anything a hostile page might send


@pytest.mark.parametrize("data, kind", [
    ({"op": "set_text", "cue": CUE, "text": "こんにちは"}, ops.SetText),
    ({"op": "set_translation_text", "track": "en", "cue": CUE, "text": "Hi"},
     ops.SetTranslationText),
    ({"op": "set_times", "cue": CUE, "start_ms": 100}, ops.SetTimes),
    ({"op": "nudge", "cue": CUE, "delta_ms": -100, "edge": "start"}, ops.Nudge),
    ({"op": "split", "cue": CUE, "at_char": 2, "at_ms": 1500}, ops.Split),
    ({"op": "merge_next", "cue": CUE}, ops.MergeNext),
    ({"op": "insert", "start_ms": 0, "end_ms": 900, "text": "えっ"}, ops.Insert),
    ({"op": "delete", "cue": CUE}, ops.Delete),
    ({"op": "detach", "track": "en", "cue": CUE, "detached": True}, ops.Detach),
    ({"op": "replace_all", "find": "元気", "replace": "", "tracks": ["source", "en"]},
     ops.ReplaceAll),
    ({"op": "glossary_add", "term": "工藤新一", "translation": "Shinichi Kudo"},
     ops.GlossaryAdd),
])
def test_each_edit_the_editor_sends_is_read_as_its_own_kind(data, kind):
    op = ops.parse_op(data)
    assert type(op) is kind and op.op == data["op"]
    assert op.model_dump(exclude_defaults=True) | {"op": data["op"]} == data


def test_a_nudge_moves_the_whole_cue_unless_told_otherwise():
    assert ops.parse_op({"op": "nudge", "cue": CUE, "delta_ms": 500}).edge == "both"


def test_cue_ids_have_the_shape_new_cue_id_makes():
    cid = new_cue_id(set())
    assert ops.parse_op({"op": "delete", "cue": cid}).cue == cid


def test_an_edit_is_frozen():
    op = ops.parse_op({"op": "delete", "cue": CUE})
    with pytest.raises(ValidationError):
        op.cue = "cb0000002"  # type: ignore[misc]


@pytest.mark.parametrize("data", ["set_text", None, 3, [{"op": "delete", "cue": CUE}]])
def test_an_edit_must_be_an_object(data):
    with pytest.raises(BadOp, match="an edit is a JSON object"):
        ops.parse_op(data)


def test_an_unknown_edit_is_refused_without_echoing_it():
    with pytest.raises(BadOp) as err:
        ops.parse_op({"op": f"<script>{SECRET}</script>", "cue": CUE})
    assert str(err.value) == "this edit can't be made: op isn't a known edit"
    assert err.value.field == "op"


def test_an_edit_with_no_kind_is_refused():
    with pytest.raises(BadOp, match="op is missing"):
        ops.parse_op({"cue": CUE})


def test_an_unknown_field_is_refused_without_naming_it():
    with pytest.raises(BadOp) as err:
        ops.parse_op({"op": "set_text", "cue": CUE, "text": "x", f"evil_{SECRET}": 1})
    assert str(err.value) == "this edit can't be made: it has a field no edit has"
    assert SECRET not in str(err.value) and err.value.field is None


@pytest.mark.parametrize("data, field, reason", [
    ({"op": "set_text", "cue": CUE}, "text", "is missing"),
    ({"op": "set_text", "cue": CUE, "text": "x" * 2000 + SECRET}, "text", "is too long"),
    ({"op": "set_text", "cue": f"../{SECRET}", "text": "x"}, "cue", "isn't valid"),
    ({"op": "set_text", "cue": "c1", "text": "x"}, "cue", "isn't valid"),
    ({"op": "set_times", "cue": CUE, "start_ms": -1}, "start_ms", "is out of range"),
    ({"op": "set_times", "cue": CUE, "end_ms": 48 * 3600 * 1000 + 1}, "end_ms",
     "is out of range"),
    ({"op": "nudge", "cue": CUE, "delta_ms": "100"}, "delta_ms", "has the wrong type"),
    ({"op": "nudge", "cue": CUE, "delta_ms": 100, "edge": SECRET}, "edge",
     "isn't one of the choices"),
    ({"op": "split", "cue": CUE, "at_char": 1.5, "at_ms": 10}, "at_char", "has the wrong type"),
    ({"op": "detach", "track": "en", "cue": CUE, "detached": "yes"}, "detached",
     "has the wrong type"),
    ({"op": "detach", "track": SECRET, "cue": CUE, "detached": True}, "track",
     "isn't one of the choices"),
    ({"op": "replace_all", "find": "", "replace": "x", "tracks": ["en"]}, "find",
     "is too short"),
    ({"op": "replace_all", "find": "a", "replace": "x", "tracks": []}, "tracks",
     "has the wrong number of items"),
    ({"op": "replace_all", "find": "a", "replace": "x", "tracks": ["source", SECRET]},
     "tracks", "isn't one of the choices"),
    ({"op": "glossary_add", "term": "工藤\n新一", "translation": "Kudo"}, "term",
     "isn't valid"),
    ({"op": "glossary_add", "term": "工藤", "translation": "   "}, "translation",
     "isn't valid"),
])
def test_a_bad_value_names_its_field_and_never_echoes_the_value(data, field, reason):
    with pytest.raises(BadOp) as err:
        ops.parse_op(data)
    assert str(err.value) == f"this edit can't be made: {field} {reason}"
    assert err.value.field == field and SECRET not in str(err.value)
    assert err.value.__cause__ is None and err.value.__context__ is None  # it quotes them


def test_set_times_needs_a_start_or_an_end():
    with pytest.raises(BadOp, match="this edit can't be made: set_times isn't valid"):
        ops.parse_op({"op": "set_times", "cue": CUE})


@pytest.mark.parametrize("text", ["a\ud800b", "nul\x00", "\x1b[31mred"])
def test_text_with_characters_that_cant_be_saved_is_refused(text):
    with pytest.raises(BadOp, match="text isn't valid"):
        ops.parse_op({"op": "set_text", "cue": CUE, "text": text})


def test_text_may_hold_line_breaks_tabs_and_bidi_marks():
    op = ops.parse_op({"op": "set_text", "cue": CUE, "text": "שלום\u200f\nline\ttwo"})
    assert op.text == "שלום\u200f\nline\ttwo"


def test_every_kind_of_edit_is_in_the_union():
    kinds = {k.model_fields["op"].default for k in ops.EDIT_KINDS}
    assert kinds == {"set_text", "set_translation_text", "set_times", "nudge", "split",
                     "merge_next", "insert", "delete", "detach", "replace_all", "glossary_add"}
```

- [ ] **Step 2: Run it; watch it fail.** `uv run pytest tests/test_ops.py -q`. Expected:
  `E   ImportError: cannot import name 'ops' from 'vid2sub.web' (…/src/vid2sub/web/__init__.py)`
  and `1 error`.
- [ ] **Step 3: Write the code,** `src/vid2sub/web/ops.py`:

```python
"""The edits the editor sends, as typed values checked at the door (spec §20, §6.3).

Every edit arrives from the browser, so it is untrusted until `parse_op` has checked it: one
pydantic model per kind, discriminated on `op`, with unknown fields refused (`extra="forbid"`)
and nothing coerced (`strict`), so a string never becomes a number. Bounds keep a hostile page
from handing the server work or text it can't save: text up to 2,000 characters with no control
characters but line breaks and tabs and no lone surrogates (they can't be written as UTF-8),
times from 0 to 48 hours, cue ids in the shape `model.new_cue_id` makes, tracks only the keys
vid2sub knows. `BadOp` names the field and why, never the value or an unknown field's name, so
nothing the page sent comes back in a message or a log (spec §6.8); pydantic's own error, which
quotes the input, is dropped. Each kind maps to one `subs.edit` operation; `glossary_add` is held
until Save writes the glossary (the Phase 2 plan's Decision 5).
"""

from __future__ import annotations

import unicodedata
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    TypeAdapter,
    ValidationError,
    model_validator,
)

from vid2sub.subs import naming
from vid2sub.subs.edit import SOURCE

MAX_MS = 48 * 60 * 60 * 1000
MAX_TEXT = 2000
MAX_TERM = 200
_ALLOWED_CONTROLS = frozenset("\n\r\t")


def _saveable(text: str) -> str:
    for ch in text:
        category = unicodedata.category(ch)
        if category == "Cs" or (category == "Cc" and ch not in _ALLOWED_CONTROLS):
            raise ValueError("a character that can't be saved")
    return text


def _one_line(text: str) -> str:
    if not text.strip() or "\n" in text or "\r" in text:
        raise ValueError("one line of text")
    return _saveable(text)


CueId = Annotated[str, StringConstraints(pattern=r"^c[0-9a-f]{8}$")]
Ms = Annotated[int, Field(ge=0, le=MAX_MS)]
Delta = Annotated[int, Field(ge=-MAX_MS, le=MAX_MS)]
Text = Annotated[str, Field(max_length=MAX_TEXT), AfterValidator(_saveable)]
Find = Annotated[str, Field(min_length=1, max_length=MAX_TEXT), AfterValidator(_saveable)]
Term = Annotated[str, Field(min_length=1, max_length=MAX_TERM), AfterValidator(_one_line)]
Track = Literal[tuple(naming.TRACKS)]  # type: ignore[valid-type]
TrackOrSource = Literal[(SOURCE, *naming.TRACKS)]  # type: ignore[valid-type]


class _Op(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class SetText(_Op):
    op: Literal["set_text"] = "set_text"
    cue: CueId
    text: Text


class SetTranslationText(_Op):
    op: Literal["set_translation_text"] = "set_translation_text"
    track: Track
    cue: CueId
    text: Text


class SetTimes(_Op):
    op: Literal["set_times"] = "set_times"
    cue: CueId
    start_ms: Ms | None = None
    end_ms: Ms | None = None

    @model_validator(mode="after")
    def _an_edge(self) -> SetTimes:
        if self.start_ms is None and self.end_ms is None:
            raise ValueError("a start or an end")
        return self


class Nudge(_Op):
    op: Literal["nudge"] = "nudge"
    cue: CueId
    delta_ms: Delta
    edge: Literal["start", "end", "both"] = "both"


class Split(_Op):
    op: Literal["split"] = "split"
    cue: CueId
    at_char: Annotated[int, Field(ge=0, le=MAX_TEXT)]
    at_ms: Ms


class MergeNext(_Op):
    op: Literal["merge_next"] = "merge_next"
    cue: CueId


class Insert(_Op):
    op: Literal["insert"] = "insert"
    start_ms: Ms
    end_ms: Ms
    text: Text


class Delete(_Op):
    op: Literal["delete"] = "delete"
    cue: CueId


class Detach(_Op):
    op: Literal["detach"] = "detach"
    track: Track
    cue: CueId
    detached: bool


class ReplaceAll(_Op):
    op: Literal["replace_all"] = "replace_all"
    find: Find
    replace: Text
    tracks: Annotated[list[TrackOrSource], Field(min_length=1, max_length=len(naming.TRACKS) + 1)]


class GlossaryAdd(_Op):
    op: Literal["glossary_add"] = "glossary_add"
    term: Term
    translation: Term


EDIT_KINDS = (SetText, SetTranslationText, SetTimes, Nudge, Split, MergeNext, Insert, Delete,
              Detach, ReplaceAll, GlossaryAdd)
EditOp = Annotated[SetText | SetTranslationText | SetTimes | Nudge | Split | MergeNext | Insert
                   | Delete | Detach | ReplaceAll | GlossaryAdd, Field(discriminator="op")]
_ADAPTER: TypeAdapter[EditOp] = TypeAdapter(EditOp)

_REASONS = {
    "missing": "is missing",
    "union_tag_not_found": "is missing",
    "union_tag_invalid": "isn't a known edit",
    "string_too_long": "is too long",
    "string_too_short": "is too short",
    "greater_than_equal": "is out of range",
    "less_than_equal": "is out of range",
    "literal_error": "isn't one of the choices",
    "too_short": "has the wrong number of items",
    "too_long": "has the wrong number of items",
    "int_type": "has the wrong type",
    "string_type": "has the wrong type",
    "bool_type": "has the wrong type",
    "list_type": "has the wrong type",
}


class BadOp(ValueError):
    """An edit that doesn't pass; the message names the field, never what was sent."""

    def __init__(self, field: str | None, reason: str):
        self.field = field
        super().__init__(f"this edit can't be made: {reason}" if field is None
                         else f"this edit can't be made: {field} {reason}")


def parse_op(data: object) -> EditOp:
    if not isinstance(data, dict):
        raise BadOp(None, "an edit is a JSON object")
    try:
        return _ADAPTER.validate_python(data)
    except ValidationError as err:
        first = err.errors(include_url=False, include_context=False, include_input=False)[0]
    kind = first["type"]
    if kind == "extra_forbidden":
        raise BadOp(None, "it has a field no edit has")
    if kind in ("union_tag_invalid", "union_tag_not_found"):
        raise BadOp("op", _REASONS[kind])
    names = [part for part in first["loc"][1:] if isinstance(part, str)]
    raise BadOp(names[0] if names else str(first["loc"][0]), _REASONS.get(kind, "isn't valid"))
```

- [ ] **Step 4: Run the checks; they pass.** `uv run pytest tests/test_ops.py -q` first
  (`43 passed`), then the guard check, then `make check`. **Guard check** (an unknown field):
  in `class _Op`, change `ConfigDict(extra="forbid", frozen=True, strict=True)` to
  `ConfigDict(frozen=True, strict=True)`; `uv run pytest tests/test_ops.py -q` gives
  `FAILED tests/test_ops.py::test_an_unknown_field_is_refused_without_naming_it` and
  `1 failed, 42 passed`; restore it. `make check`. Expected: `625 passed, 2 skipped, 4
  deselected` twice (the local zone, then UTC), `All checks passed!` and `no leaks found`.
- [ ] **Step 5: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(web): 🤖 the editor's edits are typed and checked at the door, and a bad one is refused without echoing it

vid2sub.web.ops (spec §20, §6.3, §6.8): one pydantic model per edit kind
(set_text, set_translation_text, set_times, nudge, split, merge_next,
insert, delete, detach, replace_all, glossary_add), a union discriminated
on `op`, each with extra="forbid", strict and frozen. Text is at most
2,000 characters with no control characters but line breaks and tabs and
no lone surrogates (they can't be written as UTF-8); times are 0 to 48
hours; cue ids have new_cue_id's shape (c + 8 hex); tracks are the keys
naming.TRACKS knows ("source" too for replace_all); glossary terms are
one line of at most 200 characters. parse_op(data) raises BadOp naming
the field and why, never the value or an unknown field's name, and
without chaining pydantic's ValidationError, which quotes the input.

The new test failed first with: ImportError: cannot import name 'ops'
from 'vid2sub.web'. Guard checked by reverting it: without
extra="forbid", test_an_unknown_field_is_refused_without_naming_it
fails.

Docs read: pydantic 2.14.1's docs (concepts/unions.md: discriminated
unions with Field(discriminator); errors/validation_errors.md:
union_tag_invalid quotes the input tag, union_tag_not_found;
concepts/strict_mode.md: strict=True refuses "123" for an int).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 6
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/web/ops.py tests/test_ops.py`, `git commit -F .git/COMMIT_MSG`, then
  `git log -1 --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 6: Write the failing test,** `tests/test_backend_edit.py`:

```python
import time

import pytest
from episodes import LINES, make_episode, sid, source_cues, tid, write_track

from vid2sub import store
from vid2sub.cache import Cache
from vid2sub.config import Config
from vid2sub.engines.clients import KeyRing
from vid2sub.media.tools import Tools
from vid2sub.subs.edit import EditError
from vid2sub.subs.model import Cue
from vid2sub.web import backend as web_backend
from vid2sub.web import views
from vid2sub.web.backend import LocalBackend, OpenError
from vid2sub.web.ops import parse_op

pytestmark = pytest.mark.media


@pytest.fixture
def backend(tmp_path) -> LocalBackend:
    return LocalBackend(Config(), Tools.find(), KeyRing(environ={}),
                        Cache(tmp_path / "cache", max_bytes=10**9))


@pytest.fixture
def video(tmp_path):
    return make_episode(tmp_path / "show")


def op(**data):
    return parse_op(data)


def texts(cues) -> list[str]:
    return [c.text for c in cues]


def test_an_edit_returns_a_new_episode_and_leaves_the_old_one_as_it_was(backend, video):
    ep = backend.open(str(video))
    out = backend.apply(ep, op(op="set_text", cue=sid(0), text="こんばんは"))
    assert texts(out.tracks.source) == ["こんばんは", *LINES[1:]]
    assert texts(ep.tracks.source) == list(LINES) and ep.undo == []
    assert out.undo == [(ep.tracks, {})] and out.redo == [] and out.dirty
    assert out.base == ep.base and out.id == ep.id


@pytest.mark.parametrize("data, check", [
    ({"op": "set_translation_text", "track": "en", "cue": tid(1), "text": "How's it going?"},
     lambda t: "edited" in t.translations["en"][1].flags),
    ({"op": "set_times", "cue": sid(1), "end_ms": 6000},
     lambda t: t.source[1].end_ms == 6000 and t.translations["en"][1].end_ms == 6000),
    ({"op": "nudge", "cue": sid(2), "delta_ms": 500},
     lambda t: (t.source[2].start_ms, t.source[2].end_ms) == (7700, 10_700)),
    ({"op": "split", "cue": sid(2), "at_char": 3, "at_ms": 8000},
     lambda t: texts(t.source)[2:] == ["はい、", "元気です"]),
    ({"op": "merge_next", "cue": sid(0)},
     lambda t: texts(t.source)[0] == "おはよう\n元気ですか" and len(t.translations["en"]) == 2),
    ({"op": "insert", "start_ms": 3100, "end_ms": 3500, "text": "えっ"},
     lambda t: texts(t.source)[1] == "えっ"),
    ({"op": "delete", "cue": sid(1)},
     lambda t: texts(t.source) == [LINES[0], LINES[2]] and len(t.translations["en"]) == 2),
    ({"op": "detach", "track": "en", "cue": tid(0), "detached": True},
     lambda t: t.translations["en"][0].detached),
    ({"op": "replace_all", "find": "元気", "replace": "げんき", "tracks": ["source"]},
     lambda t: texts(t.source)[1:] == ["げんきですか", "はい、げんきです"]),
])
def test_every_kind_of_edit_runs_through_the_edit_rules(backend, video, data, check):
    ep = backend.open(str(video))
    out = backend.apply(ep, parse_op(data))
    assert check(out.tracks) and out.tracks != ep.tracks and len(out.undo) == 1


def test_new_cues_get_ids_no_version_of_the_track_has_used(backend, video):
    ep = backend.open(str(video))
    out = backend.apply(ep, op(op="split", cue=sid(0), at_char=2, at_ms=1500))
    halves = {c.id for c in out.tracks.source} - {c.id for c in ep.tracks.source}
    assert len(halves) == 2 and halves <= out.taken and not halves & ep.taken


def test_undo_and_redo_step_back_and_forward(backend, video):
    ep = backend.open(str(video))
    one = backend.apply(ep, op(op="set_text", cue=sid(0), text="一"))
    two = backend.apply(one, op(op="delete", cue=sid(2)))
    back = backend.undo(two)
    assert back.tracks == one.tracks and back.redo == [(two.tracks, {})]
    back = backend.undo(back)
    assert back.tracks == ep.tracks and not back.dirty and back.undo == []
    forward = backend.redo(backend.redo(back))
    assert forward.tracks == two.tracks and forward.redo == []


def test_a_new_edit_after_an_undo_drops_what_could_have_been_redone(backend, video):
    ep = backend.open(str(video))
    one = backend.undo(backend.apply(ep, op(op="set_text", cue=sid(0), text="一")))
    other = backend.apply(one, op(op="set_text", cue=sid(1), text="二"))
    assert other.redo == [] and len(other.undo) == 1


def test_undo_or_redo_with_nothing_to_step_to_changes_nothing(backend, video):
    ep = backend.open(str(video))
    assert backend.undo(ep) is ep and backend.redo(ep) is ep


def test_an_edit_that_changes_nothing_adds_no_undo_step(backend, video):
    ep = backend.open(str(video))
    assert backend.apply(ep, op(op="replace_all", find="zzz", replace="y",
                                tracks=["source", "en"])) is ep
    assert backend.apply(ep, op(op="set_text", cue=sid(0), text=f" {LINES[0]} ")) is ep


def test_undo_keeps_the_last_200_steps(backend, video):
    ep = backend.open(str(video))
    for k in range(web_backend.UNDO_STEPS + 5):
        ep = backend.apply(ep, op(op="set_text", cue=sid(0), text=f"台詞{k}"))
    assert len(ep.undo) == web_backend.UNDO_STEPS == 200
    assert ep.undo[0][0].source[0].text == "台詞4"


def test_an_edit_the_rules_refuse_says_why_and_changes_nothing(backend, video):
    ep = backend.open(str(video))
    with pytest.raises(EditError, match="delete it instead"):
        backend.apply(ep, op(op="set_text", cue=sid(0), text="  "))
    with pytest.raises(EditError, match="there is no zh-Hant track"):
        backend.apply(ep, op(op="detach", track="zh-Hant", cue=tid(0), detached=True))
    assert ep.undo == [] and ep.tracks == ep.base


def test_a_glossary_add_waits_for_save_and_can_be_undone(backend, video):
    ep = backend.open(str(video))
    out = backend.apply(ep, op(op="glossary_add", term=" 工藤新一 ", translation="Shinichi Kudo"))
    assert out.glossary_adds == {"工藤新一": "Shinichi Kudo"} and out.dirty
    assert out.tracks == ep.tracks
    assert backend.undo(out).glossary_adds == {} and not backend.undo(out).dirty


def test_a_track_in_conflict_cant_be_edited_until_a_version_is_picked(backend, video):
    head = store.load(video)[0].head("en").rendition
    for text in ("Mine", "Theirs"):
        write_track(video, "en", [Cue(id=tid(0), start_ms=0, end_ms=3000, text=text,
                                      src=(sid(0),))], role="translation", replaces=head)
    ep = backend.open(str(video))
    with pytest.raises(EditError, match="the en track has two versions: pick one"):
        backend.apply(ep, op(op="set_translation_text", track="en", cue=tid(0), text="x"))
    with pytest.raises(EditError, match="the en track has two versions: pick one"):
        backend.apply(ep, op(op="replace_all", find="M", replace="m", tracks=["source", "en"]))
    out = backend.apply(ep, op(op="set_text", cue=sid(0), text="こんばんは"))
    assert out.tracks.source[0].text == "こんばんは"


def test_nothing_but_a_glossary_add_can_be_made_while_the_source_is_in_conflict(backend, video):
    head = store.load(video)[0].head("ja").rendition
    write_track(video, "ja", source_cues(3)[:1], role="source", replaces=head)
    write_track(video, "ja", source_cues(3)[1:], role="source", replaces=head)
    ep = backend.open(str(video))
    for data in ({"op": "set_text", "cue": sid(0), "text": "x"},
                 {"op": "insert", "start_ms": 0, "end_ms": 900, "text": "x"},
                 {"op": "detach", "track": "en", "cue": tid(0), "detached": True}):
        with pytest.raises(EditError, match="the ja track has two versions: pick one"):
            backend.apply(ep, parse_op(data))
    assert backend.apply(ep, op(op="glossary_add", term="工藤", translation="Kudo")).dirty


def test_a_closed_episode_cant_be_edited(backend, video):
    ep = backend.open(str(video))
    backend.close(ep.id)
    with pytest.raises(OpenError, match="closed"):
        backend.apply(ep, op(op="delete", cue=sid(0)))
    with pytest.raises(OpenError, match="closed"):
        backend.undo(ep)


def test_each_edit_on_a_two_hour_episode_and_its_new_view_take_well_under_a_second(backend,
                                                                                    tmp_path):
    ep = backend.open(str(make_episode(tmp_path / "long", n=2000)))
    edits = [{"op": "set_text", "cue": sid(1000), "text": "変更"},
             {"op": "nudge", "cue": sid(1000), "delta_ms": 100},
             {"op": "split", "cue": sid(10), "at_char": 2, "at_ms": 36_100},
             {"op": "merge_next", "cue": sid(20)},
             {"op": "delete", "cue": sid(30)},
             {"op": "replace_all", "find": "台詞", "replace": "セリフ", "tracks": ["source"]},
             {"op": "set_translation_text", "track": "en", "cue": tid(5), "text": "x"}]
    for data in edits:
        began = time.perf_counter()
        ep = backend.apply(ep, parse_op(data))
        views.episode_view(ep, video_url=None, audio_url=None)
        elapsed = time.perf_counter() - began
        # Review Focus 3: about 0.02 s each where this was built; 1 s leaves CI room
        assert elapsed < 1.0, f"{data['op']}: {elapsed:.2f} s"
```

- [ ] **Step 7: Run it; watch it fail.** `uv run pytest tests/test_backend_edit.py -q`.
  Expected: `E       AttributeError: 'LocalBackend' object has no attribute 'apply'` (and
  `undo`, and `module 'vid2sub.web.backend' has no attribute 'UNDO_STEPS'`), `22 failed`.
- [ ] **Step 8: Write the code.**
  In `src/vid2sub/web/backend.py`, replace the module docstring

```python
"""The editor's backend: opening an episode M1 made, from its sidecar (spec §19.1, §20, §15.3).

The web app's server calls this, never the store directly, so the CLI and the editor share one
core (spec §18.3); `capabilities()` tells the frontend which controls exist (`BrowserBackend`, in
Pages, is Phase 4's). Phase 2's editor opens only episodes that already have a sidecar: making
subtitles is `vid2sub run` or the Jobs page. Opening folds in edits made outside vid2sub, as
every M1 command does (§15.3, S31), and says so in notes that name files only by their bare name
(§6.8). A track whose heads diverged is in conflict (§14.4): it isn't loaded, and its versions
are listed for the person to pick; when that is the source, every edit waits for the pick, since
translations hang off source cues. The spoken words come from the transcript the source was
built from, following rendition parents, so word highlighting matches the cues' `w` ranges. Audio
in AC-3, E-AC-3, DTS or TrueHD can't be played by a browser (§8.2), so the editor then plays the
playback audio instead (the Phase 2 plan's Decision 2). An `Episode` is never changed in place:
every call returns a new one, so a reactive value that holds it sees each change. A translation
is stale, as spec §13.4 says and M1 decides (pipeline._translate_targets), when its source text
changed, and every cue of it is when the glossary's hash or the translation model differs from
the ones its head was made with; so the episode holds the glossary beside the video and the model
Retranslate would use with none named, picked offline from the catalog route as M1 picks it but
taking every configured local server to answer (no request is made at open).
"""
```

  with

```python
"""The editor's backend: opening an episode M1 made, and editing it (spec §19.1, §20, §15.3).

The web app's server calls this, never the store directly, so the CLI and the editor share one
core (spec §18.3); `capabilities()` tells the frontend which controls exist (`BrowserBackend`, in
Pages, is Phase 4's). Phase 2's editor opens only episodes that already have a sidecar: making
subtitles is `vid2sub run` or the Jobs page. Opening folds in edits made outside vid2sub, as
every M1 command does (§15.3, S31), and says so in notes that name files only by their bare name
(§6.8). A track whose heads diverged is in conflict (§14.4): it isn't loaded, and its versions
are listed for the person to pick; when that is the source, every edit waits for the pick, since
translations hang off source cues. The spoken words come from the transcript the source was
built from, following rendition parents, so word highlighting matches the cues' `w` ranges. Audio
in AC-3, E-AC-3, DTS or TrueHD can't be played by a browser (§8.2), so the editor then plays the
playback audio instead (the Phase 2 plan's Decision 2). An `Episode` is never changed in place:
every call returns a new one, so a reactive value that holds it sees each change. A translation
is stale, as spec §13.4 says and M1 decides (pipeline._translate_targets), when its source text
changed, and every cue of it is when the glossary's hash or the translation model differs from
the ones its head was made with; so the episode holds the glossary beside the video and the model
Retranslate would use with none named, picked offline from the catalog route as M1 picks it but
taking every configured local server to answer (no request is made at open). Edits run
through the pure `subs.edit` rules, so they exist once (§20); each one that changes something
pushes the tracks and the pending glossary adds onto the undo stack (the last 200 steps) and
clears redo. A track in conflict can't be edited, and nothing but a glossary add can while the
source is, until a person picks a version.
"""
```

  Replace the imports and constants, from `from __future__ import annotations` down to `NO_SUBTITLES = …`,

```python
from __future__ import annotations

import os
import secrets
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from vid2sub import detect as detecting
from vid2sub import store
from vid2sub.cache import Cache
from vid2sub.catalog import suggest
from vid2sub.config import Config
from vid2sub.engines.clients import KeyRing
from vid2sub.media.identity import identify
from vid2sub.media.probe import Probe, ProbeError, pick_track, probe
from vid2sub.media.tools import ToolFailed, ToolMissing, Tools
from vid2sub.pipeline import MEDIA_SUFFIXES, video_change
from vid2sub.security import InputRefused, WriteRefused, resolve_input
from vid2sub.subs import naming
from vid2sub.subs.edit import Tracks
from vid2sub.subs.glossary import EMPTY_GLOSSARY, Glossary, GlossaryError, parse_glossary
from vid2sub.subs.model import Word
from vid2sub.subs.rendition import cues_from_body, transcript_from_body
from vid2sub.subs.sidecar import (
    Conflict,
    Header,
    HeadRecord,
    RenditionRecord,
    Sidecar,
    SidecarError,
)

UNPLAYABLE_AUDIO = frozenset({"ac3", "eac3", "dts", "truehd"})  # ffprobe's codec names (§8.2)
NO_SUBTITLES = 
```

  with

```python
from __future__ import annotations

import os
import secrets
import tempfile
import threading
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Literal

from vid2sub import detect as detecting
from vid2sub import store
from vid2sub.cache import Cache
from vid2sub.catalog import suggest
from vid2sub.config import Config
from vid2sub.engines.clients import KeyRing
from vid2sub.media.identity import identify
from vid2sub.media.probe import Probe, ProbeError, pick_track, probe
from vid2sub.media.tools import ToolFailed, ToolMissing, Tools
from vid2sub.pipeline import MEDIA_SUFFIXES, video_change
from vid2sub.security import InputRefused, WriteRefused, resolve_input
from vid2sub.subs import edit, naming
from vid2sub.subs.edit import SOURCE, EditError, Tracks
from vid2sub.subs.glossary import EMPTY_GLOSSARY, Glossary, GlossaryError, parse_glossary
from vid2sub.subs.model import Word
from vid2sub.subs.rendition import cues_from_body, transcript_from_body
from vid2sub.subs.sidecar import (
    Conflict,
    Header,
    HeadRecord,
    RenditionRecord,
    Sidecar,
    SidecarError,
)
from vid2sub.web import ops

UNPLAYABLE_AUDIO = frozenset({"ac3", "eac3", "dts", "truehd"})  # ffprobe's codec names (§8.2)
NO_SUBTITLES = 
```

  Add the undo limit below `NO_SUBTITLES = …`:

```python
UNDO_STEPS = 200
```

  In `class LocalBackend`, directly above `def _route_model(self, lang: str)`, add (each method followed by one blank line):

```python
    def apply(self, ep: Episode, op: ops.EditOp) -> Episode:
        """One edit; EditError (fit to show) if the rules refuse it. An edit that changes
        nothing returns `ep` itself, with no undo step."""
        self._check_open(ep)
        taken = set(ep.taken)
        tracks, adds = _edit(ep, op, taken)
        if tracks == ep.tracks and adds == ep.glossary_adds:
            return ep
        return replace(ep, tracks=tracks, glossary_adds=adds, taken=taken, redo=[],
                       undo=[*ep.undo, (ep.tracks, ep.glossary_adds)][-UNDO_STEPS:])

    def undo(self, ep: Episode) -> Episode:
        self._check_open(ep)
        if not ep.undo:
            return ep
        tracks, adds = ep.undo[-1]
        return replace(ep, tracks=tracks, glossary_adds=adds, undo=ep.undo[:-1],
                       redo=[*ep.redo, (ep.tracks, ep.glossary_adds)])

    def redo(self, ep: Episode) -> Episode:
        self._check_open(ep)
        if not ep.redo:
            return ep
        tracks, adds = ep.redo[-1]
        return replace(ep, tracks=tracks, glossary_adds=adds, redo=ep.redo[:-1],
                       undo=[*ep.undo, (ep.tracks, ep.glossary_adds)][-UNDO_STEPS:])

    def _check_open(self, ep: Episode) -> None:
        if not self.is_open(ep.id):
            raise OpenError("this episode was closed: open it again")
```

  Directly above `def _video(path: str) -> Path:`, add (each function followed by two blank lines):

```python
def _edit(ep: Episode, op: ops.EditOp, taken: set[str]) -> tuple[Tracks, dict[str, str]]:
    """The tracks and glossary adds after `op`; new cue ids are added to `taken`."""
    if isinstance(op, ops.GlossaryAdd):
        return ep.tracks, {**ep.glossary_adds, op.term.strip(): op.translation.strip()}
    t = ep.tracks
    match op:
        case ops.SetText():
            _editable(ep, ep.source_key)
            return edit.set_text(t, op.cue, op.text), ep.glossary_adds
        case ops.SetTranslationText():
            _editable(ep, op.track)
            return edit.set_translation_text(t, op.track, op.cue, op.text), ep.glossary_adds
        case ops.SetTimes():
            _editable(ep, ep.source_key)
            return (edit.set_times(t, op.cue, start_ms=op.start_ms, end_ms=op.end_ms),
                    ep.glossary_adds)
        case ops.Nudge():
            _editable(ep, ep.source_key)
            return edit.nudge(t, op.cue, op.delta_ms, edge=op.edge), ep.glossary_adds
        case ops.Split():
            _editable(ep, ep.source_key)
            return (edit.split(t, op.cue, at_char=op.at_char, at_ms=op.at_ms, taken=taken)[0],
                    ep.glossary_adds)
        case ops.MergeNext():
            _editable(ep, ep.source_key)
            return edit.merge_next(t, op.cue, taken=taken)[0], ep.glossary_adds
        case ops.Insert():
            _editable(ep, ep.source_key)
            return (edit.insert(t, start_ms=op.start_ms, end_ms=op.end_ms, text=op.text,
                                taken=taken)[0], ep.glossary_adds)
        case ops.Delete():
            _editable(ep, ep.source_key)
            return edit.delete(t, op.cue), ep.glossary_adds
        case ops.Detach():
            _editable(ep, op.track)
            return edit.detach(t, op.track, op.cue, op.detached), ep.glossary_adds
        case ops.ReplaceAll():
            _editable(ep, *(ep.source_key if name == SOURCE else name for name in op.tracks))
            return edit.replace_all(t, op.find, op.replace, tracks=op.tracks)[0], ep.glossary_adds
    raise EditError("that isn't an edit the editor knows")


def _editable(ep: Episode, *tracks: str) -> None:
    """A track in conflict waits for a person to pick a version (spec §14.4); while the source
    is, so does every track, since translations hang off source cues."""
    for name in (ep.source_key, *tracks):
        if name in ep.conflicts:
            raise EditError(f"the {name} track has two versions: pick one before editing")
```

- [ ] **Step 9: Run the checks; they pass.** `uv run pytest tests/test_backend_edit.py -q` first
  (`22 passed`), then the guard check, then `make check`. **Guard check** (no edit on a
  conflicted track): in `_editable`, change `for name in (ep.source_key, *tracks):` to
  `for name in ():`; the run gives `FAILED
  tests/test_backend_edit.py::test_a_track_in_conflict_cant_be_edited_until_a_version_is_picked`,
  `FAILED tests/test_backend_edit.py::test_nothing_but_a_glossary_add_can_be_made_while_the_source_is_in_conflict`
  and `2 failed, 20 passed`; restore it. `make check`. Expected: `647 passed, 2 skipped, 4
  deselected` twice, `All checks passed!` and `no leaks found`.
- [ ] **Step 10: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(web): 🤖 the editor's backend applies, undoes and redoes edits, and refuses them on a track in conflict

LocalBackend.apply(ep, op) runs one ops.EditOp through its subs.edit
operation (spec §20: the edit rules exist once) and returns a new
Episode, the old one untouched; an edit that changes nothing returns ep
itself, with no undo step. Each step pushes the tracks and the pending
glossary adds onto the undo stack, the last 200 kept (UNDO_STEPS), and
clears redo; undo() and redo() step back and forward and return ep when
there's nothing to step to. glossary_add only records the term for Save
(the plan's Decision 5), and is undone like an edit. A track in conflict
can't be edited, and nothing but a glossary add can while the source is
(spec §14.4), each refused with EditError: "the en track has two
versions: pick one before editing". A closed episode is refused with
OpenError. Review Focus 3: each edit on a 2,000-cue episode, with its new
view, took about 0.02 s.

The new test failed first with: AttributeError: 'LocalBackend' object has
no attribute 'apply'. Guard checked by reverting it: with _editable
checking no track, the two conflict tests fail.

Docs read: none beyond the code (subs.edit, Task 2's listing).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 6
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/web/backend.py tests/test_backend_edit.py`, `git commit -F
  .git/COMMIT_MSG`, then `git log -1 --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 11: Write the failing test.** In `tests/test_glossary.py`, replace

```python
from vid2sub.subs.glossary import (
    EMPTY_GLOSSARY,
    GlossaryError,
    chunk_prompt,
```

  with

```python
from vid2sub.subs.glossary import (
    EMPTY_GLOSSARY,
    Glossary,
    GlossaryError,
    add_terms,
    chunk_prompt,
```

  and append at the end of the file, after two blank lines:

```python
# Phase 2, Task 6: the editor's Save adds terms (spec §16; the plan's Decision 5)


def test_adding_terms_keeps_the_description_the_terms_and_the_comments():
    text = "# names from the first season\n" + TOML + "# more to come\n"
    out, kept = add_terms(text, {"阿笠博士": "Professor Agasa"})
    assert out == text + '"阿笠博士" = "Professor Agasa"\n' and kept == []
    assert parse_glossary(out) == Glossary("Detective Conan, a Japanese anime", (
        ("工藤新一", "Shinichi Kudo"), ("毛利蘭", "Ran Mouri"), ("阿笠博士", "Professor Agasa")))


def test_adding_to_no_glossary_starts_one_with_a_terms_table():
    assert add_terms("", {" 工藤新一 ": "Shinichi Kudo"}) == (
        '[terms]\n"工藤新一" = "Shinichi Kudo"\n', [])


def test_adding_to_a_glossary_with_only_a_description_gives_it_a_terms_table():
    out, _ = add_terms('description = "A show"', {"a": "b"})
    assert out == 'description = "A show"\n\n[terms]\n"a" = "b"\n'
    assert parse_glossary(out) == Glossary("A show", (("a", "b"),))


def test_a_file_with_windows_line_ends_keeps_them():
    out, _ = add_terms('[terms]\r\n"a" = "b"\r\n', {"c": "d"})
    assert out == '[terms]\r\n"a" = "b"\r\n"c" = "d"\r\n'


def test_a_term_already_there_is_left_and_one_with_another_translation_is_reported():
    out, kept = add_terms(TOML, {"工藤新一": "Shinichi Kudo", "毛利蘭": "Rachel Moore"})
    assert out == TOML and kept == ["毛利蘭"]


def test_terms_with_quotes_backslashes_and_control_characters_round_trip():
    adds = {'say "hi"': "back\\slash", "tab\there": "bell\x07", "ü ✨": "ok"}
    out, _ = add_terms("", adds)
    assert dict(parse_glossary(out).terms) == adds


def test_a_term_or_translation_with_no_text_is_refused():
    with pytest.raises(GlossaryError, match="both need text"):
        add_terms(TOML, {"x": "  "})


def test_a_glossary_written_as_an_inline_table_is_refused_rather_than_rewritten():
    with pytest.raises(GlossaryError, match="add them by hand"):
        add_terms('terms = { "a" = "b" }\n', {"c": "d"})


def test_a_glossary_that_isnt_toml_is_refused():
    with pytest.raises(GlossaryError, match="isn't valid TOML"):
        add_terms("nonsense = [", {"c": "d"})
```

- [ ] **Step 12: Run it; watch it fail.** `uv run pytest tests/test_glossary.py -q`. Expected:
  `E   ImportError: cannot import name 'add_terms' from 'vid2sub.subs.glossary'
  (…/src/vid2sub/subs/glossary.py)` and `1 error`.
- [ ] **Step 13: Write the code,** in `src/vid2sub/subs/glossary.py`.
  In the module docstring, replace

```python
versions so a glossary edit marks translations stale.
```

  with

```python
versions so a glossary edit marks translations stale. The editor's Save adds terms to it by
appending lines to its `[terms]`, never by writing it out again, so the person's comments and
layout survive (it is their file, spec §16); the result must read back as the old glossary plus
the new terms, or nothing is written (Phase 2 plan, Task 6).
```

  Replace

```python
from collections.abc import Iterable
```

  with

```python
from collections.abc import Iterable, Mapping
```

  Directly above the comment `# vocabulary_prompt and prompt_sha are copied from audio-router,`, add (each function followed by two blank lines):

```python
def add_terms(text: str, adds: Mapping[str, str]) -> tuple[str, list[str]]:
    """`text` (a glossary file's, or "" for none) with `adds` appended to its `[terms]`, and the
    terms it already had with another translation: those keep the file's translation.

    A layout that appending can't extend (an inline `terms = {...}` table) raises GlossaryError
    rather than being rewritten."""
    current = parse_glossary(text) if text.strip() else EMPTY_GLOSSARY
    have = dict(current.terms)
    new: dict[str, str] = {}
    kept: list[str] = []
    for term, translation in adds.items():
        term, translation = term.strip(), translation.strip()
        if not term or not translation:
            raise GlossaryError("a glossary term and its translation both need text")
        if term in have:
            if have[term] != translation:
                kept.append(term)
            continue
        new[term] = translation
    if not new:
        return text, kept
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = "".join(f"{_toml_string(k)} = {_toml_string(v)}{nl}" for k, v in new.items())
    base = text if not text or text.endswith("\n") else text + nl
    expected = Glossary(current.description, current.terms + tuple(new.items()))
    for candidate in (base + lines, base + (nl if base else "") + "[terms]" + nl + lines):
        try:
            if parse_glossary(candidate) == expected:
                return candidate, kept
        except GlossaryError:
            continue
    raise GlossaryError("the glossary's layout can't take new terms without being rewritten; "
                        "add them by hand")


def _toml_string(s: str) -> str:
    """A TOML basic string: quotes, backslashes and control characters escaped."""
    out = []
    for ch in s:
        if ch in '"\\':
            out.append("\\" + ch)
        elif ord(ch) < 0x20 or ord(ch) == 0x7F:
            out.append(f"\\u{ord(ch):04X}")
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'
```

- [ ] **Step 14: Run the checks; they pass.** `uv run pytest tests/test_glossary.py
  tests/test_purity.py -q` first (`21 passed`: `subs` stays pure), then `make check`. Expected:
  `656 passed, 2 skipped, 4 deselected` twice, `All checks passed!` and `no leaks found`.
- [ ] **Step 15: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(subs): 🤖 a glossary takes new terms by appending to its [terms], keeping the person's comments and layout

subs.glossary.add_terms(text, adds) -> (text, kept) (spec §16; the plan's
Decision 5): the editor's Save adds glossary terms by appending
`"term" = "translation"` lines to the file's [terms] (adding the table
when there is none), in the file's own line ends, never by writing the
file out again, so the person's comments, order and layout survive. The
result is parsed again and must read as the old glossary plus the new
terms; a layout appending can't extend (an inline `terms = {...}`
table) raises GlossaryError ("add them by hand") rather than being
rewritten. A term already there is left as it is; one there with another
translation keeps the file's, and is returned in `kept` so the editor
can say so. Keys and values are TOML basic strings with quotes,
backslashes and control characters escaped. Pure, as subs must be
(tests/test_purity.py stays green).

The new tests failed first with: ImportError: cannot import name
'add_terms' from 'vid2sub.subs.glossary'.

Docs read: the TOML 1.0.0 spec (toml.io: basic strings must escape the
quotation mark, the backslash and the control characters other than tab,
U+007F included; \uXXXX escapes; dotted keys and inline tables can't be
extended by a later table header); Python 3.12's tomllib (loads).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 6
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/subs/glossary.py tests/test_glossary.py`, `git commit -F
  .git/COMMIT_MSG`, then `git log -1 --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 16: Write the failing test,** `tests/test_backend_save.py`:

```python
import sys

import pytest
from episodes import make_episode, sid, source_cues, tid, translation_cues, write_track
from fakes import fake_make_ask

from vid2sub import __version__, pipeline, store
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


def test_a_file_changed_outside_since_the_episode_opened_is_never_overwritten(backend, video):
    ep = backend.open(str(video))
    srt = video.with_name(EN)
    outside = srt.read_bytes().replace(b"How are you?", b"How do you do?")
    srt.write_bytes(outside)
    ep = edit(backend, ep, op="set_translation_text", track="en", cue=tid(0), text="Morning!")
    saved, result = backend.save(ep, formats=["srt"])
    assert result.foreign == (EN,) and srt.read_bytes() == outside
    assert store.load(video)[0].head("en").rendition == saved.heads["en"]


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


def test_a_version_picked_in_another_tab_is_shown_rather_than_picked_again(backend, video):
    conflicted(video)
    a, b = backend.open(str(video)), backend.open(str(video))
    backend.resolve(a, "en", a.conflicts["en"][0])
    picked, result = backend.resolve(b, "en", b.conflicts["en"][1])
    assert result.notes == ("the en track's version was already picked elsewhere: showing it",)
    assert picked.tracks.translations["en"][0].text == "Mine"
    assert [h.by for h in store.load(video)[0].heads("en")].count("user") == 1


# A Save that goes wrong


def test_a_save_cut_short_after_the_sidecar_never_makes_the_next_save_conflict_with_itself(
        backend, video, monkeypatch):
    real = store.safe_write

    def full_disk(path, data, *, overwrite):
        if path.suffix == ".srt":
            raise OSError(28, "No space left on device")
        return real(path, data, overwrite=overwrite)

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
```

- [ ] **Step 17: Run it; watch it fail.** `uv run pytest tests/test_backend_save.py -q`.
  Expected: `E   ImportError: cannot import name 'SaveError' from 'vid2sub.web.backend'
  (…/src/vid2sub/web/backend.py)` and `1 error`.
- [ ] **Step 18: Write the code.**
  In `src/vid2sub/web/backend.py`, replace the module docstring

```python
"""The editor's backend: opening an episode M1 made, and editing it (spec §19.1, §20, §15.3).

The web app's server calls this, never the store directly, so the CLI and the editor share one
core (spec §18.3); `capabilities()` tells the frontend which controls exist (`BrowserBackend`, in
Pages, is Phase 4's). Phase 2's editor opens only episodes that already have a sidecar: making
subtitles is `vid2sub run` or the Jobs page. Opening folds in edits made outside vid2sub, as
every M1 command does (§15.3, S31), and says so in notes that name files only by their bare name
(§6.8). A track whose heads diverged is in conflict (§14.4): it isn't loaded, and its versions
are listed for the person to pick; when that is the source, every edit waits for the pick, since
translations hang off source cues. The spoken words come from the transcript the source was
built from, following rendition parents, so word highlighting matches the cues' `w` ranges. Audio
in AC-3, E-AC-3, DTS or TrueHD can't be played by a browser (§8.2), so the editor then plays the
playback audio instead (the Phase 2 plan's Decision 2). An `Episode` is never changed in place:
every call returns a new one, so a reactive value that holds it sees each change. A translation
is stale, as spec §13.4 says and M1 decides (pipeline._translate_targets), when its source text
changed, and every cue of it is when the glossary's hash or the translation model differs from
the ones its head was made with; so the episode holds the glossary beside the video and the model
Retranslate would use with none named, picked offline from the catalog route as M1 picks it but
taking every configured local server to answer (no request is made at open). Edits run
through the pure `subs.edit` rules, so they exist once (§20); each one that changes something
pushes the tracks and the pending glossary adds onto the undo stack (the last 200 steps) and
clears redo. A track in conflict can't be edited, and nothing but a glossary add can while the
source is, until a person picks a version.
"""
```

  with

```python
"""The editor's backend: opening an episode M1 made, editing it and saving it (spec §19.1, §20).

The web app's server calls this, never the store directly, so the CLI and the editor share one
core (spec §18.3); `capabilities()` tells the frontend which controls exist (`BrowserBackend`, in
Pages, is Phase 4's). Phase 2's editor opens only episodes that already have a sidecar: making
subtitles is `vid2sub run` or the Jobs page. Opening folds in edits made outside vid2sub, as
every M1 command does (§15.3, S31), and says so in notes that name files only by their bare name
(§6.8). A track whose heads diverged is in conflict (§14.4): it isn't loaded, and its versions
are listed for the person to pick; when that is the source, every edit waits for the pick, since
translations hang off source cues. The spoken words come from the transcript the source was
built from, following rendition parents, so word highlighting matches the cues' `w` ranges. Audio
in AC-3, E-AC-3, DTS or TrueHD can't be played by a browser (§8.2), so the editor then plays the
playback audio instead (the Phase 2 plan's Decision 2). An `Episode` is never changed in place:
every call returns a new one, so a reactive value that holds it sees each change. A translation
is stale, as spec §13.4 says and M1 decides (pipeline._translate_targets), when its source text
changed, and every cue of it is when the glossary's hash or the translation model differs from
the ones its head was made with; so the episode holds the glossary beside the video and the model
Retranslate would use with none named, picked offline from the catalog route as M1 picks it but
taking every configured local server to answer (no request is made at open). Edits run
through the pure `subs.edit` rules, so they exist once (§20); each one that changes something
pushes the tracks and the pending glossary adds onto the undo stack (the last 200 steps) and
clears redo. A track in conflict can't be edited, and nothing but a glossary add can while the
source is, until a person picks a version.

Save (spec §14.5, §14.6) appends one `editor` version per changed track, whose parent is the head
the editor's cues came from, and a head that replaces that same head: never the head on disk now,
so a CLI run or another tab that moved it meanwhile leaves two heads, a conflict both versions
survive, rather than one silently replacing the other (Review Focus 2 and 4). The records go in
one `store.append`, which is compare-and-swap with a union merge, so no other writer's records
are lost. Only then are the files written, through `store.project` with `overwrite_foreign` off:
someone else's file, or one changed outside since, is left alone and reported (§6.6, §15.3), and
a track in conflict isn't written until a person picks a version with `resolve`, the only thing
that moves a head on a conflicted track. Once the versions are in the sidecar nothing raises: a
file that can't be written is a note, and the episode moves to the new heads either way, so a
second Save never conflicts with the first. Glossary terms are written at Save (the plan's
Decision 5), appended to the file beside the video so its comments survive. A Save, like a pick,
starts the undo history again, because the tracks are read back from the sidecar.
"""
```

  Replace everything from `from __future__ import annotations` down to `class OpenError`'s docstring

```python
from __future__ import annotations

import os
import secrets
import tempfile
import threading
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Literal

from vid2sub import detect as detecting
from vid2sub import store
from vid2sub.cache import Cache
from vid2sub.catalog import suggest
from vid2sub.config import Config
from vid2sub.engines.clients import KeyRing
from vid2sub.media.identity import identify
from vid2sub.media.probe import Probe, ProbeError, pick_track, probe
from vid2sub.media.tools import ToolFailed, ToolMissing, Tools
from vid2sub.pipeline import MEDIA_SUFFIXES, video_change
from vid2sub.security import InputRefused, WriteRefused, resolve_input
from vid2sub.subs import edit, naming
from vid2sub.subs.edit import SOURCE, EditError, Tracks
from vid2sub.subs.glossary import EMPTY_GLOSSARY, Glossary, GlossaryError, parse_glossary
from vid2sub.subs.model import Word
from vid2sub.subs.rendition import cues_from_body, transcript_from_body
from vid2sub.subs.sidecar import (
    Conflict,
    Header,
    HeadRecord,
    RenditionRecord,
    Sidecar,
    SidecarError,
)
from vid2sub.web import ops

UNPLAYABLE_AUDIO = frozenset({"ac3", "eac3", "dts", "truehd"})  # ffprobe's codec names (§8.2)
NO_SUBTITLES = "no subtitles yet: make them with vid2sub run or the Jobs page first"
UNDO_STEPS = 200


class OpenError(Exception):
    """An episode that can't be opened; the reason is fit to show."""
```

  with

```python
from __future__ import annotations

import codecs
import os
import secrets
import tempfile
import threading
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Literal

from vid2sub import __version__, store
from vid2sub import detect as detecting
from vid2sub.cache import Cache
from vid2sub.catalog import suggest
from vid2sub.config import Config
from vid2sub.engines.clients import KeyRing
from vid2sub.media.identity import identify
from vid2sub.media.probe import Probe, ProbeError, pick_track, probe
from vid2sub.media.tools import ToolFailed, ToolMissing, Tools
from vid2sub.pipeline import MEDIA_SUFFIXES, video_change
from vid2sub.security import InputRefused, WriteRefused, resolve_input, safe_write
from vid2sub.subs import edit, naming
from vid2sub.subs.edit import SOURCE, EditError, Tracks
from vid2sub.subs.glossary import (
    EMPTY_GLOSSARY,
    Glossary,
    GlossaryError,
    add_terms,
    parse_glossary,
)
from vid2sub.subs.model import Cue, Word
from vid2sub.subs.rendition import cues_body, cues_from_body, transcript_from_body
from vid2sub.subs.sidecar import (
    Conflict,
    Header,
    HeadRecord,
    RenditionRecord,
    Sidecar,
    SidecarError,
    make_rendition,
)
from vid2sub.web import ops

UNPLAYABLE_AUDIO = frozenset({"ac3", "eac3", "dts", "truehd"})  # ffprobe's codec names (§8.2)
NO_SUBTITLES = "no subtitles yet: make them with vid2sub run or the Jobs page first"
UNDO_STEPS = 200
FORMATS = ("srt", "ass")
GONE = "the sidecar next to the video is gone, so nothing was saved: open the episode again"


class OpenError(Exception):
    """An episode that can't be opened; the reason is fit to show."""
```

  Below `class OpenError` and its docstring, add (with two blank lines before each class):

```python
class SaveError(Exception):
    """Nothing was saved; the reason is fit to show."""


@dataclass(frozen=True)
class SaveResult:
    written: tuple[str, ...]  # file names written
    foreign: tuple[str, ...]  # file names left alone: someone else's, or changed outside since
    conflicts: tuple[str, ...]  # tracks in conflict, so not written until a version is picked
    notes: tuple[str, ...]
```

  In `class LocalBackend`, directly above `def _check_open(self, ep: Episode)`, add (each method followed by one blank line):

```python
    def save(self, ep: Episode, *, formats: Sequence[Literal["srt", "ass"]]
             ) -> tuple[Episode, SaveResult]:
        """SRT is always written, ASS when asked for (spec §15.2). SaveError means nothing was
        saved; once the versions are in the sidecar, every later problem is a note."""
        self._check_open(ep)
        fmts = _formats(formats)
        records = _versions(ep)
        try:
            if not store.sidecar_path(ep.video).is_file():
                raise SaveError(GONE)
            side = store.append(ep.video, ep.header, records) if records else _reload(ep.video)
        except (SidecarError, store.StoreError, WriteRefused) as err:
            raise SaveError(str(err)) from None
        except OSError as err:  # never err.filename: a full path
            raise SaveError(_failed("couldn't save next to the video", err)) from None
        side, written, foreign, conflicts, notes = _project(ep.video, ep.header, side,
                                                             side.tracks(), fmts)
        adds, glossary_notes = _write_glossary(ep.video, ep.glossary_adds)
        source_key, tracks, heads, in_conflict = load_tracks(side)
        saved = replace(ep, sidecar=side, source_key=source_key, tracks=tracks, base=tracks,
                        heads=heads, conflicts=in_conflict, undo=[], redo=[],
                        taken=ep.taken | cue_ids(side), glossary_adds=adds)
        return saved, SaveResult(tuple(written), tuple(foreign), tuple(conflicts),
                                 tuple(notes + glossary_notes))

    def resolve(self, ep: Episode, track: str, rendition: str) -> tuple[Episode, SaveResult]:
        """A person's pick of one of a conflicted track's versions (spec §14.4): it replaces
        every other version, by "user", and the track is loaded and written. Unsaved edits on
        other tracks are kept."""
        self._check_open(ep)
        if track not in naming.TRACKS:  # it comes from the browser: never echoed unchecked
            raise SaveError("there's no such track")
        notes: list[str] = []
        try:
            side = _reload(ep.video)
            head = side.head(track)
            if isinstance(head, Conflict):
                if rendition not in head.leaves:
                    raise SaveError(f"that isn't one of the {track} track's versions")
                now = store.now()
                side = store.append(ep.video, ep.header, [
                    HeadRecord(track=track, rendition=rendition, replaces=other, by="user", at=now)
                    for other in head.leaves if other != rendition])
            elif track in ep.conflicts:
                notes.append(f"the {track} track's version was already picked elsewhere: "
                             "showing it")
        except (SidecarError, store.StoreError, WriteRefused) as err:
            raise SaveError(str(err)) from None
        except OSError as err:
            raise SaveError(_failed("couldn't save next to the video", err)) from None
        has_ass = any(p.track == track and p.format == "ass"
                      for p in side.projections().values())
        side, written, foreign, conflicts, more = _project(ep.video, ep.header, side, [track],
                                                           ["srt", "ass"] if has_ass else ["srt"])
        return _with_track(ep, side, track), SaveResult(tuple(written), tuple(foreign),
                                                        tuple(conflicts), tuple(notes + more))
```

  Directly above `def _edit(ep: Episode, …)`, add (each function followed by two blank lines):

```python
def _formats(formats: Sequence[str]) -> list[str]:
    if any(f not in FORMATS for f in formats):
        raise ValueError("the formats are srt and ass")
    return ["srt"] + (["ass"] if "ass" in formats else [])


def _reload(video: Path) -> Sidecar:
    side, _ = store.load(video)
    if side is None:
        raise SaveError(GONE)
    return side


def _failed(what: str, err: OSError) -> str:
    return what + (f" ({err.strerror})" if err.strerror else "")


def _cues(t: Tracks, track: str, source_key: str) -> tuple[Cue, ...] | None:
    return t.source if track == source_key else t.translations.get(track)


def _versions(ep: Episode) -> list:
    """An editor version and a head for each track whose cues differ from its head's; the head
    replaces the one the cues came from, never the head on disk now (spec §14.4)."""
    renditions = ep.sidecar.renditions()
    now = store.now()
    records: list = []
    source_rid = ep.heads.get(ep.source_key)
    for track in [ep.source_key, *ep.tracks.translations]:
        cues = _cues(ep.tracks, track, ep.source_key)
        if track not in ep.heads or cues is None or cues == _cues(ep.base, track, ep.source_key):
            continue
        parent = ep.heads[track]
        is_source = track == ep.source_key
        body = _editor_body(renditions[parent].body, cues, is_source=is_source, created_at=now,
                            inputs={} if is_source or not source_rid else {"source": source_rid})
        rec = make_rendition([parent], track, body)
        if is_source:
            source_rid = rec.id
        records += [rec, HeadRecord(track=track, rendition=rec.id, replaces=parent, by="editor",
                                    at=now)]
    return records


def _editor_body(head: dict, cues: Sequence[Cue], *, is_source: bool, created_at: str,
                 inputs: dict[str, str]) -> dict:
    """The head's language, script and glossary hash; its model too, since the cues the person
    didn't touch are still that model's, and M1 reads a changed model as every cue stale."""
    payload = head.get("payload", {})
    return cues_body(cues, language=payload["language"], script=payload.get("script"),
                     engine="editor", model=head.get("model"), version=f"editor@{__version__}",
                     created_at=created_at, inputs=inputs,
                     meta={"role": "source" if is_source else "translation"},
                     glossary_sha=payload.get("glossary_sha"))


def _project(video: Path, header: Header, side: Sidecar, tracks: Sequence[str],
             fmts: Sequence[str]) -> tuple[Sidecar, list[str], list[str], list[str], list[str]]:
    """Writes each track's files; never raises, since the versions are already saved."""
    written: list[str] = []
    foreign: list[str] = []
    conflicts: list[str] = []
    notes: list[str] = []
    for track in tracks:
        head = side.head(track)
        if isinstance(head, Conflict):
            conflicts.append(track)
            continue
        if not isinstance(head, HeadRecord):
            continue
        for fmt in fmts:
            try:
                name = store.subtitle_path(video, track, fmt).name
            except naming.UnknownTrack:
                notes.append(f"couldn't write the {track} track: vid2sub has no file name for it")
                break
            try:
                side, _, did = store.project(video, header, side, track, fmt,
                                             overwrite_foreign=False)
            except (store.ForeignFile, WriteRefused):
                foreign.append(name)
                continue
            except (SidecarError, store.StoreError) as err:
                notes.append(f"couldn't write {name}: {err}")
                continue
            except OSError as err:
                notes.append(_failed(f"couldn't write {name}", err))
                continue
            if did:
                written.append(name)
    return side, written, foreign, conflicts, notes


def _with_track(ep: Episode, side: Sidecar, track: str) -> Episode:
    """The episode with one track read again from the sidecar; the others as they were."""
    heads, conflicts = dict(ep.heads), dict(ep.conflicts)
    tracks, base = ep.tracks, ep.base
    head = side.head(track)
    if isinstance(head, HeadRecord):
        cues = tuple(cues_from_body(side.renditions()[head.rendition].body))
        heads[track] = head.rendition
        conflicts.pop(track, None)
        tracks, base = (_put(t, track, cues, ep.source_key) for t in (tracks, base))
    elif isinstance(head, Conflict):
        conflicts[track] = head.leaves
        heads.pop(track, None)
    return replace(ep, sidecar=side, heads=heads, conflicts=conflicts, tracks=tracks, base=base,
                   undo=[], redo=[], taken=ep.taken | cue_ids(side))


def _put(t: Tracks, track: str, cues: tuple[Cue, ...], source_key: str) -> Tracks:
    if track == source_key:
        return Tracks(cues, t.translations)
    return Tracks(t.source, {**t.translations, track: cues})


def _write_glossary(video: Path, adds: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    """Appends the terms to the glossary beside the video, compare-and-swap like the sidecar;
    returns the terms still waiting (all of them if it couldn't) and the notes."""
    if not adds:
        return {}, []
    path = video.with_name(naming.GLOSSARY_NAME)
    name = path.name
    if path.is_symlink():  # never read or write through a link planted in the folder (§6.6)
        return dict(adds), [f"couldn't add to {name}: it isn't a regular file"]
    try:
        for _ in range(3):
            data = path.read_bytes() if path.is_file() else b""
            text = data.decode("utf-8-sig")
            out, kept = add_terms(text, adds)
            if out == text:
                break
            latest = path.read_bytes() if path.is_file() else b""
            if latest != data:
                continue
            bom = codecs.BOM_UTF8 if data.startswith(codecs.BOM_UTF8) else b""
            safe_write(path, bom + out.encode("utf-8"), overwrite=bool(data))
            break
        else:
            return dict(adds), [f"couldn't add to {name}: it kept changing; save again"]
    except UnicodeDecodeError:
        return dict(adds), [f"couldn't add to {name}: it isn't UTF-8"]
    except (GlossaryError, WriteRefused) as err:
        return dict(adds), [f"couldn't add to {name}: {err}"]
    except OSError as err:
        return dict(adds), [_failed(f"couldn't add to {name}", err)]
    had = dict(parse_glossary(text).terms) if text.strip() else {}
    new = sum(1 for term in adds if term not in had)
    notes = [f"added {new} term{'' if new == 1 else 's'} to {name}"] if new else []
    notes += [f"{name} already has {term} with another translation: kept that one"
              for term in kept]
    return {}, notes
```

- [ ] **Step 19: Run the checks; they pass.** `uv run pytest tests/test_backend_save.py -q` first
  (`25 passed`), then the guard checks, then `make check`. **Guard checks** (Tier 1: each must
  fail without its fix; revert one, run `uv run pytest tests/test_backend_save.py -q`, restore it,
  then the next):
  1. *Never overwrite someone else's file:* in `_project`, change `overwrite_foreign=False` to
     `overwrite_foreign=True`: `FAILED
     tests/test_backend_save.py::test_someone_elses_subtitle_file_is_never_overwritten`,
     `1 failed, 24 passed`.
  2. *Never lose a concurrent writer's records:* in `save`, replace
     `side = store.append(ep.video, ep.header, records) if records else _reload(ep.video)` with
     the three lines `from vid2sub.subs.sidecar import serialize`, `side =
     ep.sidecar.add(*records)` and `safe_write(store.sidecar_path(ep.video),
     serialize(side).encode(), overwrite=True)` (a write from the copy read at open): six fail,
     among them `test_a_cli_translation_made_while_the_episode_was_open_survives_and_both_are_kept`,
     `test_a_cli_change_to_another_track_and_the_editors_save_both_land` and both two-tabs tests,
     `6 failed, 19 passed`.
  3. *Never move a head on a conflicted track without the person:* in `_versions`, replace
     `records += [rec, HeadRecord(track=track, rendition=rec.id, replaces=parent, by="editor",`
     and its next line with `on_disk = store.load(ep.video)[0].head(track)` and `records +=
     [rec, HeadRecord(track=track, rendition=rec.id, replaces=on_disk.rendition, by="editor",
     at=now)]` (the head on disk now): five fail, among them the CLI-translation test,
     `test_two_tabs_saving_one_track_keep_both_versions_and_the_second_sees_the_conflict` and
     `test_picking_a_version_makes_it_the_head_writes_its_files_and_loads_it`, `5 failed, 20
     passed` (the CLI's version is silently displaced).
  4. *A Save cut short never conflicts with the next:* in `_project`, make the `except OSError`
     branch `raise SaveError(_failed(f"couldn't write {name}", err)) from None`: `FAILED
     tests/test_backend_save.py::test_a_save_cut_short_after_the_sidecar_never_makes_the_next_save_conflict_with_itself`,
     `1 failed, 24 passed`.
  5. *Never through a planted link:* in `_write_glossary`, change `if path.is_symlink():` to
     `if False:`: `FAILED
     tests/test_backend_save.py::test_a_glossary_that_is_a_link_is_neither_read_nor_written`,
     `1 failed, 24 passed`.

  `make check`. Expected: `681 passed, 2 skipped, 4 deselected` twice, `All checks passed!` and
  `no leaks found`.
- [ ] **Step 20: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(web): 🤖 Save appends an editor version per changed track and writes only vid2sub's files, and a diverged track waits for the person's pick

LocalBackend.save(ep, *, formats) -> (Episode, SaveResult) (spec §14.5,
§14.6, §15.2, §15.3; S29, S32): one `editor` version per changed track,
whose parent is the head its cues came from, with the head's language,
script, glossary hash and model and meta.role "source" or "translation",
and a head (by "editor") that replaces that same head, never the head on
disk now; all in one store.append, compare-and-swap with a union merge.
So a CLI run or another tab that moved the head meanwhile leaves two
heads, a conflict in which both versions survive (Review Focus 2 and 4),
and no other writer's record is lost. Then every track not in conflict is
projected, SRT always and ASS when asked, with overwrite_foreign off:
someone else's file, or one changed outside since, is left alone and
listed in `foreign`; a missing file is written back (§15.3). Once the
versions are in the sidecar nothing raises: a file that can't be written
is a note, and the episode moves to the new heads either way, so the next
Save never conflicts with the first. SaveError (nothing saved) when the
sidecar can't be read or is gone. Glossary adds are appended beside the
video with safe_write, compare-and-swap, keeping the file's comments; a
glossary that can't take them is left alone and they wait. A Save starts
the undo history again: the tracks are read back from the sidecar.

LocalBackend.resolve(ep, track, rendition) -> (Episode, SaveResult): the
person's pick appends one head by "user" replacing each other version,
then loads and writes that track only, keeping unsaved edits on the
others; a pick already made in another tab is shown, not made again.

A glossary beside the video that is a link is neither read nor written
(spec §6.6): the terms wait, with a note.

The new test failed first with: ImportError: cannot import name
'SaveError' from 'vid2sub.web.backend'. Guards checked by reverting each:
with overwrite_foreign=True, test_someone_elses_subtitle_file_is_never_
overwritten fails; with the sidecar written from the copy read at open
instead of store.append, six tests fail (the CLI's and the other tab's
records are lost); with the head replacing the head on disk now instead
of the one the edits came from, the CLI-translation, two-tabs and pick
tests fail (the CLI's version is silently displaced); with a file error
after the append raised as SaveError, test_a_save_cut_short_after_the_
sidecar_never_makes_the_next_save_conflict_with_itself fails. With the
link check removed, test_a_glossary_that_is_a_link_is_neither_read_nor_
written fails.

Docs read: none beyond the code (store.append, project, check_external,
ForeignFile and EditedOnDisk; subs.sidecar.Sidecar.head's leaves;
pipeline._translate_targets, which reads a changed `model` as every cue
stale, hence the copied model).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 6
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/web/backend.py tests/test_backend_save.py`, `git commit -F
  .git/COMMIT_MSG`, then `git log -1 --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 21: Write the failing tests:** Save and pick with other writers about (an outside
  edit since the open, the same Save sent twice, two picks at once, a stale pick), the words of
  a picked source, an empty glossary file, and a source edit that would orphan a conflicted
  translation's cues.
  In `tests/test_backend_save.py`, replace the imports from `import sys` to `from fakes import fake_make_ask`

```python
import sys

import pytest
from episodes import make_episode, sid, source_cues, tid, translation_cues, write_track
from fakes import fake_make_ask
```

  with

```python
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
```

  Replace the test `test_a_file_changed_outside_since_the_episode_opened_is_never_overwritten` (an outside edit is now kept, and diverges from the editor's) with two

```python
def test_a_file_changed_outside_since_the_episode_opened_is_never_overwritten(backend, video):
    ep = backend.open(str(video))
    srt = video.with_name(EN)
    outside = srt.read_bytes().replace(b"How are you?", b"How do you do?")
    srt.write_bytes(outside)
    ep = edit(backend, ep, op="set_translation_text", track="en", cue=tid(0), text="Morning!")
    saved, result = backend.save(ep, formats=["srt"])
    assert result.foreign == (EN,) and srt.read_bytes() == outside
    assert store.load(video)[0].head("en").rendition == saved.heads["en"]


# Never lose a concurrent writer's records
```

  with

```python
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


# Never lose a concurrent writer's records
```

  Directly above `def test_a_save_cut_short_after_the_sidecar_never_makes_the_next_save_conflict_with_itself(`, add (each test followed by two blank lines):

```python
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
```

  Directly above `def test_a_version_picked_in_another_tab_is_shown_rather_than_picked_again(`, add:

```python
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
```

  Directly above `def test_a_glossary_that_cant_take_the_terms_is_left_alone_and_they_wait(`, add:

```python
def test_an_empty_glossary_file_takes_terms(backend, video):
    video.with_name(GLOSSARY).write_bytes(b"")
    ep = edit(backend, backend.open(str(video)), op="glossary_add", term="工藤新一",
              translation="Shinichi Kudo")
    _, result = backend.save(ep, formats=["srt"])
    assert result.notes == (f"added 1 term to {GLOSSARY}",)
    assert parse_glossary(video.with_name(GLOSSARY).read_text(encoding="utf-8")).terms == (
        ("工藤新一", "Shinichi Kudo"),)
```

  In `tests/test_backend_edit.py`, directly above `def test_nothing_but_a_glossary_add_can_be_made_while_the_source_is_in_conflict(`, add:

```python
def test_no_cue_can_be_split_merged_or_deleted_while_a_translation_is_in_conflict(backend,
                                                                                    video):
    head = store.load(video)[0].head("en").rendition
    for text in ("Mine", "Theirs"):
        write_track(video, "en", [Cue(id=tid(0), start_ms=0, end_ms=3000, text=text,
                                      src=(sid(0),))], role="translation", replaces=head)
    ep = backend.open(str(video))
    for data in ({"op": "delete", "cue": sid(0)}, {"op": "merge_next", "cue": sid(0)},
                 {"op": "split", "cue": sid(0), "at_char": 2, "at_ms": 1500}):
        with pytest.raises(EditError, match="the en track has two versions: pick one"):
            backend.apply(ep, parse_op(data))
    assert backend.apply(ep, op(op="nudge", cue=sid(0), delta_ms=100)).dirty
```

- [ ] **Step 22: Run them; watch them fail.** `uv run pytest tests/test_backend_save.py
  tests/test_backend_edit.py -q`. Expected: `8 failed, 46 passed`, the eight being
  `test_a_file_changed_outside_since_the_episode_opened_is_kept_and_both_versions_wait`
  (`assert () == ('en',)`), `test_an_outside_edit_to_another_track_is_kept_at_save_and_the_save_says_so`,
  `test_saving_one_episode_twice_writes_its_versions_once` (`assert ('ja',) == ()`),
  `test_two_picks_at_once_are_made_one_after_the_other` (the second pick isn't waiting),
  `test_a_pick_on_a_track_with_one_version_is_refused_and_keeps_unsaved_edits` (`DID NOT RAISE`),
  `test_picking_a_version_of_the_source_brings_the_words_it_was_built_from`
  (`assert '気ですよ' == '気ですね'`), `test_an_empty_glossary_file_takes_terms`
  (`vid2sub.glossary.toml already exists`) and
  `test_no_cue_can_be_split_merged_or_deleted_while_a_translation_is_in_conflict`
  (`DID NOT RAISE`).
- [ ] **Step 23: Write the code.**
  In `src/vid2sub/web/backend.py`, replace the module docstring

```python
"""The editor's backend: opening an episode M1 made, editing it and saving it (spec §19.1, §20).

The web app's server calls this, never the store directly, so the CLI and the editor share one
core (spec §18.3); `capabilities()` tells the frontend which controls exist (`BrowserBackend`, in
Pages, is Phase 4's). Phase 2's editor opens only episodes that already have a sidecar: making
subtitles is `vid2sub run` or the Jobs page. Opening folds in edits made outside vid2sub, as
every M1 command does (§15.3, S31), and says so in notes that name files only by their bare name
(§6.8). A track whose heads diverged is in conflict (§14.4): it isn't loaded, and its versions
are listed for the person to pick; when that is the source, every edit waits for the pick, since
translations hang off source cues. The spoken words come from the transcript the source was
built from, following rendition parents, so word highlighting matches the cues' `w` ranges. Audio
in AC-3, E-AC-3, DTS or TrueHD can't be played by a browser (§8.2), so the editor then plays the
playback audio instead (the Phase 2 plan's Decision 2). An `Episode` is never changed in place:
every call returns a new one, so a reactive value that holds it sees each change. A translation
is stale, as spec §13.4 says and M1 decides (pipeline._translate_targets), when its source text
changed, and every cue of it is when the glossary's hash or the translation model differs from
the ones its head was made with; so the episode holds the glossary beside the video and the model
Retranslate would use with none named, picked offline from the catalog route as M1 picks it but
taking every configured local server to answer (no request is made at open). Edits run
through the pure `subs.edit` rules, so they exist once (§20); each one that changes something
pushes the tracks and the pending glossary adds onto the undo stack (the last 200 steps) and
clears redo. A track in conflict can't be edited, and nothing but a glossary add can while the
source is, until a person picks a version.

Save (spec §14.5, §14.6) appends one `editor` version per changed track, whose parent is the head
the editor's cues came from, and a head that replaces that same head: never the head on disk now,
so a CLI run or another tab that moved it meanwhile leaves two heads, a conflict both versions
survive, rather than one silently replacing the other (Review Focus 2 and 4). The records go in
one `store.append`, which is compare-and-swap with a union merge, so no other writer's records
are lost. Only then are the files written, through `store.project` with `overwrite_foreign` off:
someone else's file, or one changed outside since, is left alone and reported (§6.6, §15.3), and
a track in conflict isn't written until a person picks a version with `resolve`, the only thing
that moves a head on a conflicted track. Once the versions are in the sidecar nothing raises: a
file that can't be written is a note, and the episode moves to the new heads either way, so a
second Save never conflicts with the first. Glossary terms are written at Save (the plan's
Decision 5), appended to the file beside the video so its comments survive. A Save, like a pick,
starts the undo history again, because the tracks are read back from the sidecar.
"""
```

  with

```python
"""The editor's backend: opening an episode M1 made, editing it and saving it (spec §19.1, §20).

The web app's server calls this, never the store directly, so the CLI and the editor share one
core (spec §18.3); `capabilities()` tells the frontend which controls exist (`BrowserBackend`, in
Pages, is Phase 4's). Phase 2's editor opens only episodes that already have a sidecar: making
subtitles is `vid2sub run` or the Jobs page. Opening folds in edits made outside vid2sub, as
every M1 command does (§15.3, S31), and says so in notes that name files only by their bare name
(§6.8). A track whose heads diverged is in conflict (§14.4): it isn't loaded, and its versions
are listed for the person to pick; when that is the source, every edit waits for the pick, since
translations hang off source cues. The spoken words come from the transcript the source was
built from, following rendition parents, so word highlighting matches the cues' `w` ranges. Audio
in AC-3, E-AC-3, DTS or TrueHD can't be played by a browser (§8.2), so the editor then plays the
playback audio instead (the Phase 2 plan's Decision 2). An `Episode` is never changed in place:
every call returns a new one, so a reactive value that holds it sees each change. A translation
is stale, as spec §13.4 says and M1 decides (pipeline._translate_targets), when its source text
changed, and every cue of it is when the glossary's hash or the translation model differs from
the ones its head was made with; so the episode holds the glossary beside the video and the model
Retranslate would use with none named, picked offline from the catalog route as M1 picks it but
taking every configured local server to answer (no request is made at open). Edits run
through the pure `subs.edit` rules, so they exist once (§20); each one that changes something
pushes the tracks and the pending glossary adds onto the undo stack (the last 200 steps) and
clears redo. A track in conflict can't be edited, and nothing but a glossary add can while the
source is, until a person picks a version.

Save (spec §14.5, §14.6) first records any outside edit to a subtitle file as M1 does, so an
edit made in another program since the open is a version too, never something a later open puts
over the editor's. Then it appends one `editor` version per changed track, whose parent is the
head the editor's cues came from, and a head that replaces that same head: never the head on disk
now, so a CLI run, another tab or that outside edit leaves two heads, a conflict both versions
survive, rather than one silently replacing the other (Review Focus 2 and 4). A track whose head
on disk already holds exactly these cues (the same Save sent twice) gets nothing. The records go
in one `store.append`, compare-and-swap with a union merge, so no other writer's records are
lost. Only then are the files written, through `store.project` with `overwrite_foreign` off:
someone else's file is left alone and reported (§6.6, §15.3), and a track in conflict isn't
written until a person picks a version with `resolve`, the only thing that moves a head on a
conflicted track. Once the versions are in the sidecar nothing raises: a file that can't be
written is a note, and the episode moves to the new heads either way. Saves and picks on one
video take turns within this engine, so two picks at once can't replace each other in a cycle.
Glossary terms are written at Save (the plan's Decision 5), appended to the file beside the video
so its comments survive. A Save, like a pick, starts the undo history again, because the tracks
are read back from the sidecar. While a translation is in conflict, no source cue can be split,
merged or deleted: the unloaded version's cues would keep pointing at ids that are gone.
"""
```

  Replace

```python
from collections.abc import Sequence
```

  with

```python
from collections.abc import Callable, Sequence
```

  In `LocalBackend.__init__`, replace

```python
        self._lock = threading.Lock()
```

  with

```python
        self._lock = threading.Lock()
        self._writing: dict[Path, threading.Lock] = {}  # one per video: saves and picks take turns
```

  In `open`, replace

```python
        ep = Episode(
            id="e" + secrets.token_hex(8), video=video, header=header, source_key=source_key,
            tracks=tracks, heads=heads, conflicts=conflicts,
            words=tuple(transcript_from_body(transcript.body).words()) if transcript else (),
            notes=notes, playable_audio=track.codec not in UNPLAYABLE_AUDIO,
            audio_index=
```

  with

```python
        ep = Episode(
            id="e" + secrets.token_hex(8), video=video, header=header, source_key=source_key,
            tracks=tracks, heads=heads, conflicts=conflicts, words=_words(transcript), notes=notes,
            playable_audio=track.codec not in UNPLAYABLE_AUDIO,
            audio_index=
```

  Replace the methods `save` and `resolve`, from `    def save(self` to the end of `resolve`,

```python
    def save(self, ep: Episode, *, formats: Sequence[Literal["srt", "ass"]]
             ) -> tuple[Episode, SaveResult]:
        """SRT is always written, ASS when asked for (spec §15.2). SaveError means nothing was
        saved; once the versions are in the sidecar, every later problem is a note."""
        self._check_open(ep)
        fmts = _formats(formats)
        records = _versions(ep)
        try:
            if not store.sidecar_path(ep.video).is_file():
                raise SaveError(GONE)
            side = store.append(ep.video, ep.header, records) if records else _reload(ep.video)
        except (SidecarError, store.StoreError, WriteRefused) as err:
            raise SaveError(str(err)) from None
        except OSError as err:  # never err.filename: a full path
            raise SaveError(_failed("couldn't save next to the video", err)) from None
        side, written, foreign, conflicts, notes = _project(ep.video, ep.header, side,
                                                             side.tracks(), fmts)
        adds, glossary_notes = _write_glossary(ep.video, ep.glossary_adds)
        source_key, tracks, heads, in_conflict = load_tracks(side)
        saved = replace(ep, sidecar=side, source_key=source_key, tracks=tracks, base=tracks,
                        heads=heads, conflicts=in_conflict, undo=[], redo=[],
                        taken=ep.taken | cue_ids(side), glossary_adds=adds)
        return saved, SaveResult(tuple(written), tuple(foreign), tuple(conflicts),
                                 tuple(notes + glossary_notes))

    def resolve(self, ep: Episode, track: str, rendition: str) -> tuple[Episode, SaveResult]:
        """A person's pick of one of a conflicted track's versions (spec §14.4): it replaces
        every other version, by "user", and the track is loaded and written. Unsaved edits on
        other tracks are kept."""
        self._check_open(ep)
        if track not in naming.TRACKS:  # it comes from the browser: never echoed unchecked
            raise SaveError("there's no such track")
        notes: list[str] = []
        try:
            side = _reload(ep.video)
            head = side.head(track)
            if isinstance(head, Conflict):
                if rendition not in head.leaves:
                    raise SaveError(f"that isn't one of the {track} track's versions")
                now = store.now()
                side = store.append(ep.video, ep.header, [
                    HeadRecord(track=track, rendition=rendition, replaces=other, by="user", at=now)
                    for other in head.leaves if other != rendition])
            elif track in ep.conflicts:
                notes.append(f"the {track} track's version was already picked elsewhere: "
                             "showing it")
        except (SidecarError, store.StoreError, WriteRefused) as err:
            raise SaveError(str(err)) from None
        except OSError as err:
            raise SaveError(_failed("couldn't save next to the video", err)) from None
        has_ass = any(p.track == track and p.format == "ass"
                      for p in side.projections().values())
        side, written, foreign, conflicts, more = _project(ep.video, ep.header, side, [track],
                                                           ["srt", "ass"] if has_ass else ["srt"])
        return _with_track(ep, side, track), SaveResult(tuple(written), tuple(foreign),
                                                        tuple(conflicts), tuple(notes + more))
```

  with

```python
    def save(self, ep: Episode, *, formats: Sequence[Literal["srt", "ass"]]
             ) -> tuple[Episode, SaveResult]:
        """SRT is always written, ASS when asked for (spec §15.2). SaveError means nothing was
        saved; once the versions are in the sidecar, every later problem is a note."""
        self._check_open(ep)
        fmts = _formats(formats)
        notes: list[str] = []
        with self._writing_lock(ep.video):
            try:
                side, changed = store.check_external(ep.video, ep.header, _reload(ep.video),
                                                     on_unreadable=_unreadable(notes))
                notes += [f"kept your outside edit to {t}" for t in changed]
                records = _versions(ep, side)
                if records:
                    side = store.append(ep.video, ep.header, records)
            except (SidecarError, store.StoreError, WriteRefused) as err:
                raise SaveError(str(err)) from None
            except OSError as err:  # never err.filename: a full path
                raise SaveError(_failed("couldn't save next to the video", err)) from None
            side, written, foreign, conflicts, more = _project(ep.video, ep.header, side,
                                                               side.tracks(), fmts)
            notes += more
            adds, glossary_notes = _write_glossary(ep.video, ep.glossary_adds)
        source_key, tracks, heads, in_conflict = load_tracks(side)
        saved = replace(ep, sidecar=side, source_key=source_key, tracks=tracks, base=tracks,
                        heads=heads, conflicts=in_conflict, undo=[], redo=[],
                        taken=ep.taken | cue_ids(side), glossary_adds=adds)
        return saved, SaveResult(tuple(written), tuple(foreign), tuple(conflicts),
                                 tuple(notes + glossary_notes))

    def resolve(self, ep: Episode, track: str, rendition: str) -> tuple[Episode, SaveResult]:
        """A person's pick of one of a conflicted track's versions (spec §14.4): it replaces
        every other version, by "user", and the track is loaded and written. Unsaved edits on
        other tracks are kept."""
        self._check_open(ep)
        if track not in naming.TRACKS:  # it comes from the browser: never echoed unchecked
            raise SaveError("there's no such track")
        if track not in ep.conflicts:  # a stale request must never reload a track being edited
            raise SaveError(f"the {track} track has only one version: there's nothing to pick")
        notes: list[str] = []
        with self._writing_lock(ep.video):
            try:
                side = _reload(ep.video)
                head = side.head(track)
                if isinstance(head, Conflict):
                    if rendition not in head.leaves:
                        raise SaveError(f"that isn't one of the {track} track's versions")
                    now = store.now()
                    side = store.append(ep.video, ep.header, [
                        HeadRecord(track=track, rendition=rendition, replaces=other, by="user",
                                   at=now)
                        for other in head.leaves if other != rendition])
                else:
                    notes.append(f"the {track} track's version was already picked elsewhere: "
                                 "showing it")
            except (SidecarError, store.StoreError, WriteRefused) as err:
                raise SaveError(str(err)) from None
            except OSError as err:
                raise SaveError(_failed("couldn't save next to the video", err)) from None
            has_ass = any(p.track == track and p.format == "ass"
                          for p in side.projections().values())
            side, written, foreign, conflicts, more = _project(
                ep.video, ep.header, side, [track], ["srt", "ass"] if has_ass else ["srt"])
        return _with_track(ep, side, track), SaveResult(tuple(written), tuple(foreign),
                                                        tuple(conflicts), tuple(notes + more))
```

  Directly above `    def _check_open(self, ep: Episode) -> None:`, add (followed by one blank line):

```python
    def _writing_lock(self, video: Path) -> threading.Lock:
        with self._lock:
            return self._writing.setdefault(video, threading.Lock())
```

  In `_edit`, under `case ops.Split():`, replace

```python
        case ops.Split():
            _editable(ep, ep.source_key)
```

  with

```python
        case ops.Split():
            _editable(ep, ep.source_key, *ep.conflicts)
```

  In `_edit`, under `case ops.MergeNext():`, replace

```python
        case ops.MergeNext():
            _editable(ep, ep.source_key)
```

  with

```python
        case ops.MergeNext():
            _editable(ep, ep.source_key, *ep.conflicts)
```

  In `_edit`, under `case ops.Delete():`, replace

```python
        case ops.Delete():
            _editable(ep, ep.source_key)
```

  with

```python
        case ops.Delete():
            _editable(ep, ep.source_key, *ep.conflicts)
```

  Replace the function `_versions`, from `def _versions(` to its `return records`,

```python
def _versions(ep: Episode) -> list:
    """An editor version and a head for each track whose cues differ from its head's; the head
    replaces the one the cues came from, never the head on disk now (spec §14.4)."""
    renditions = ep.sidecar.renditions()
    now = store.now()
    records: list = []
    source_rid = ep.heads.get(ep.source_key)
    for track in [ep.source_key, *ep.tracks.translations]:
        cues = _cues(ep.tracks, track, ep.source_key)
        if track not in ep.heads or cues is None or cues == _cues(ep.base, track, ep.source_key):
            continue
        parent = ep.heads[track]
        is_source = track == ep.source_key
        body = _editor_body(renditions[parent].body, cues, is_source=is_source, created_at=now,
                            inputs={} if is_source or not source_rid else {"source": source_rid})
        rec = make_rendition([parent], track, body)
        if is_source:
            source_rid = rec.id
        records += [rec, HeadRecord(track=track, rendition=rec.id, replaces=parent, by="editor",
                                    at=now)]
    return records
```

  with

```python
def _versions(ep: Episode, side: Sidecar) -> list:
    """An editor version and a head for each track whose cues differ from its head's; the head
    replaces the one the cues came from, never the head on disk now (spec §14.4). A track whose
    head on disk, or one of whose diverged versions, already holds these cues gets nothing."""
    renditions = side.renditions()
    now = store.now()
    records: list = []
    source_rid = ep.heads.get(ep.source_key)
    for track in [ep.source_key, *ep.tracks.translations]:
        cues = _cues(ep.tracks, track, ep.source_key)
        if track not in ep.heads or cues is None or cues == _cues(ep.base, track, ep.source_key):
            continue
        is_source = track == ep.source_key
        same = _holding(side, track, cues)
        if same is not None:
            if is_source:
                source_rid = same
            continue
        parent = ep.heads[track]
        body = _editor_body(renditions[parent].body, cues, is_source=is_source, created_at=now,
                            inputs={} if is_source or not source_rid else {"source": source_rid})
        rec = make_rendition([parent], track, body)
        if is_source:
            source_rid = rec.id
        records += [rec, HeadRecord(track=track, rendition=rec.id, replaces=parent, by="editor",
                                    at=now)]
    return records
```

  Directly above `def _editor_body(`, add (each function followed by two blank lines):

```python
def _holding(side: Sidecar, track: str, cues: tuple[Cue, ...]) -> str | None:
    """The rendition at the track's head on disk (or among its diverged versions) whose cues are
    exactly `cues`, if there is one."""
    head = side.head(track)
    current = (head.leaves if isinstance(head, Conflict)
               else (head.rendition,) if isinstance(head, HeadRecord) else ())
    renditions = side.renditions()
    for rid in current:
        if rid in renditions and tuple(cues_from_body(renditions[rid].body)) == cues:
            return rid
    return None


def _unreadable(notes: list[str]) -> Callable[[str], None]:
    def note(name: str) -> None:
        notes.append(f"left {name} alone: it isn't a readable subtitle file")
    return note


def _words(transcript: RenditionRecord | None) -> tuple[Word, ...]:
    return tuple(transcript_from_body(transcript.body).words()) if transcript else ()
```

  In `_project`, below the `except OSError as err:` branch (its `continue`), add:

```python
            except Exception as err:  # noqa: BLE001 - the versions are saved; this is one file
                notes.append(f"couldn't write {name} ({type(err).__name__})")
                continue
```

  Replace the function `_with_track`'s body, from its docstring to its `return`,

```python
    """The episode with one track read again from the sidecar; the others as they were."""
    heads, conflicts = dict(ep.heads), dict(ep.conflicts)
    tracks, base = ep.tracks, ep.base
    head = side.head(track)
    if isinstance(head, HeadRecord):
        cues = tuple(cues_from_body(side.renditions()[head.rendition].body))
        heads[track] = head.rendition
        conflicts.pop(track, None)
        tracks, base = (_put(t, track, cues, ep.source_key) for t in (tracks, base))
    elif isinstance(head, Conflict):
        conflicts[track] = head.leaves
        heads.pop(track, None)
    return replace(ep, sidecar=side, heads=heads, conflicts=conflicts, tracks=tracks, base=base,
                   undo=[], redo=[], taken=ep.taken | cue_ids(side))
```

  with

```python
    """The episode with one track read again from the sidecar; the others as they were."""
    heads, conflicts = dict(ep.heads), dict(ep.conflicts)
    tracks, base, words = ep.tracks, ep.base, ep.words
    head = side.head(track)
    if isinstance(head, HeadRecord):
        cues = tuple(cues_from_body(side.renditions()[head.rendition].body))
        heads[track] = head.rendition
        conflicts.pop(track, None)
        tracks, base = (_put(t, track, cues, ep.source_key) for t in (tracks, base))
        if track == ep.source_key:
            words = _words(_transcript(side, head.rendition))
    elif isinstance(head, Conflict):
        conflicts[track] = head.leaves
        heads.pop(track, None)
    return replace(ep, sidecar=side, heads=heads, conflicts=conflicts, tracks=tracks, base=base,
                   words=words, undo=[], redo=[], taken=ep.taken | cue_ids(side))
```

  In `_write_glossary`, replace

```python
            data = path.read_bytes() if path.is_file() else b""
```

  with

```python
            existed = path.is_file()
            data = path.read_bytes() if existed else b""
```

  and replace

```python
overwrite=bool(data))
```

  with

```python
overwrite=existed)
```

- [ ] **Step 24: Run the checks; they pass.** `uv run pytest tests/test_backend_save.py
  tests/test_backend_edit.py -q` first (`54 passed`), then `make check`. Expected: `688 passed,
  2 skipped, 4 deselected` twice, `All checks passed!` and `no leaks found`.
- [ ] **Step 25: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(web): 🤖 Save keeps an outside edit made since the open as a version, saves each change once, and picks take turns

Save and pick when other writers are about (spec §14.4, §14.6, §15.3, §13.5):
- Save first runs store.check_external, as every M1 command does, so a
  subtitle file edited in another program since the open becomes an
  external version; when the editor changed that track too, the two
  diverge and the person picks. Before, the editor's head went on and the
  next open put the outside edit over it with only a note.
- A changed track whose head on disk (or one of whose diverged versions)
  already holds exactly these cues gets no new version, so the same Save
  sent twice never conflicts with itself.
- Saves and picks on one video take turns within the engine (a lock per
  video), so two picks at once can't append "A replaces B" and "B
  replaces A", a cycle that left the track with no head.
- resolve refuses a track that isn't in conflict ("only one version"),
  so a stale pick never reloads a track being edited; a pick on the
  source brings the words of the transcript it was built from.
- No source cue can be split, merged or deleted while a translation is
  in conflict: that unloaded version's cues would point at ids that are
  gone.
- An empty glossary file takes terms (it was refused as "already
  exists"); a file that fails to project for any reason is a note, never
  an exception, once the versions are in the sidecar.

The eight new tests failed first, each on the finding it covers (among
them: assert () == ('en',) for the outside edit; DID NOT RAISE SaveError
for the one-version pick; the second pick wasn't waiting).

Docs read: none beyond the code (store.check_external, Sidecar.head's
replacement-cycle rule).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 6
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/web/backend.py tests/test_backend_save.py tests/test_backend_edit.py`,
  `git commit -F .git/COMMIT_MSG`, then `git log -1 --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 26: Write the failing tests:** an outside edit to a file written from an older
  version than the head diverges from it (spec §14.4); a failed write leaves the file counted as
  the version it holds; an outside edit keeps the glossary hash and model its translation was
  made with (a text edit changes neither, §13.4), so fixing one typo doesn't make every cue
  stale; and a line the person added, or reworded and retimed, is `edited`, so Retranslate stale
  never replaces it. This round fixes M1's `store` (escaped from M1 Task 28). The `--stale-only`
  test is a check: M1 keeps a track whose head isn't `auto`, before and after.
  In `tests/test_store.py`, replace

```python
from vid2sub.subs.sidecar import HeadRecord, SidecarError, make_rendition, parse_sidecar
```

  with

```python
from vid2sub.subs.sidecar import (
    Conflict,
    HeadRecord,
    SidecarError,
    make_rendition,
    parse_sidecar,
)
```

  In `test_a_write_interrupted_after_its_record_is_not_taken_for_an_outside_edit`, replace (the record now names what the file holds)

```python
    assert side.projections()[path.name].sha256 != store.sha256_hex(old)
```

  with

```python
    assert side.projections()[path.name].sha256 == store.sha256_hex(old)  # what the file holds
```

  At the end of the file, after two blank lines, add:

```python
# Phase 2, Task 6: an outside edit to a file written from an older version diverges (spec §14.4)


def newer_head(video, side):
    """A newer version of en that becomes the head without being written to the file."""
    projected = side.head("en").rendition
    body = cues_body([CUES[0], CUES[1].model_copy(update={"text": "Planet"})], language="en",
                     script=None, engine="editor", model=None, version="e",
                     created_at=store.now(), inputs={}, meta={"role": "source"})
    rec = make_rendition([projected], "en", body)
    side = store.append(video, header(video), [rec, HeadRecord(
        track="en", rendition=rec.id, replaces=projected, by="editor", at=store.now())])
    return side, rec.id


def test_an_outside_edit_to_a_file_from_an_older_version_diverges_from_the_head(video):
    side = with_track(video)
    side, path, _ = store.project(video, header(video), side, "en", "srt",
                                  overwrite_foreign=False)
    side, newer = newer_head(video, side)
    path.write_bytes(path.read_bytes().replace(b"World", b"Earth"))
    side, changed = store.check_external(video, header(video), side)
    assert changed == ["en"]
    head = side.head("en")
    assert isinstance(head, Conflict)
    (external,) = [r for r in head.leaves if r != newer]
    assert newer in head.leaves and side.renditions()[external].body["engine"] == "external"


def test_a_failed_write_leaves_the_file_counted_as_the_version_it_still_holds(video,
                                                                             monkeypatch):
    side = with_track(video)
    side, path, _ = store.project(video, header(video), side, "en", "srt",
                                  overwrite_foreign=False)
    written = side.projections()[path.name]
    side, newer = newer_head(video, side)
    real = store.safe_write

    def full_disk(target, data, **kwargs):
        if target == path:
            raise OSError(28, "No space left on device")
        return real(target, data, **kwargs)

    monkeypatch.setattr(store, "safe_write", full_disk)
    with pytest.raises(OSError):
        store.project(video, header(video), side, "en", "srt", overwrite_foreign=False)
    monkeypatch.setattr(store, "safe_write", real)
    side, _ = store.load(video)
    latest = side.projections()[path.name]
    assert (latest.rendition, latest.sha256) == (written.rendition, written.sha256)
    path.write_bytes(path.read_bytes().replace(b"World", b"Earth"))
    side, _ = store.check_external(video, header(video), side)
    assert isinstance(side.head("en"), Conflict) and newer in side.head("en").leaves
```

  In `tests/test_backend_save.py`, replace

```python
from vid2sub.web.backend import LocalBackend, OpenError, SaveError, SaveResult
```

  with

```python
from vid2sub.web import views
from vid2sub.web.backend import LocalBackend, OpenError, SaveError, SaveResult
```

  and

```python
GLOSSARY = "vid2sub.glossary.toml"
```

  with

```python
GLOSSARY = "vid2sub.glossary.toml"
TERMS = '[terms]\n"工藤新一" = "Shinichi Kudo"\n'
```

  Replace `cli_translate` (it takes `fresh` and returns the result; the config is shared)

```python
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
```

  with

```python
def gemma() -> Config:
    return Config(endpoints={"spark": Endpoint(base_url="http://127.0.0.1:9/v1")},
                  models={"gemma": ModelEntry(catalog="gemma-4-26b-a4b", endpoint="spark",
                                              model="gemma", task="translate", local=True)})


def cli_translate(video, monkeypatch, *, fresh: bool = True) -> pipeline.InputResult:
    """`vid2sub translate` on the episode (`--stale-only` when not `fresh`): M1's own pipeline,
    with the model faked."""
    monkeypatch.setattr(pipeline, "make_ask", fake_make_ask)
    ctx = pipeline.RunContext(config=gemma(), tools=Tools.find(), keys=KeyRing(environ={}),
                              options=pipeline.RunOptions(targets=["en"], translate_model="gemma"))
    result = pipeline.translate_one(str(video), ctx, fresh=fresh)
    assert result.status == "done", (result.reason, result.hint)
    return result
```

  Directly above `def test_a_sidecar_that_cant_be_read_any_more_stops_the_save_before_anything_is_written(`, add (each function followed by two blank lines):

```python
def test_an_outside_edit_to_a_file_a_save_couldnt_write_diverges_from_the_save(backend, video,
                                                                              monkeypatch):
    real = store.safe_write

    def full_disk(path, data, *, overwrite):
        if path.suffix == ".srt":
            raise OSError(28, "No space left on device")
        return real(path, data, overwrite=overwrite)

    monkeypatch.setattr(store, "safe_write", full_disk)
    ep = edit(backend, backend.open(str(video)), op="set_text", cue=sid(0), text="こんばんは")
    backend.save(ep, formats=["srt"])  # the head moves on; the file still holds the old version
    monkeypatch.setattr(store, "safe_write", real)
    srt = video.with_name(JA)
    srt.write_bytes(srt.read_bytes().replace("元気ですか".encode(), "お元気ですか".encode()))
    reopened = backend.open(str(video))  # check_external, as every M1 command runs it
    assert set(reopened.conflicts) == {"ja"}
    assert leaf_texts(video, "ja") == [("editor", "こんばんは"), ("external", "おはよう")]


def en_stale(ep) -> list[bool]:
    return ["stale" in c["flags"]
            for row in views.episode_view(ep, video_url=None, audio_url=None)["rows"]
            for c in row["tr"]["en"]["cues"]]


def test_an_outside_edit_keeps_the_glossary_and_model_its_translation_was_made_with(tmp_path,
                                                                                  video):
    sha = parse_glossary(TERMS).sha()
    video.with_name(GLOSSARY).write_text(TERMS, encoding="utf-8")
    side, _ = store.load(video)
    head = side.head("en").rendition
    rec = make_rendition([head], "en", cues_body(
        translation_cues(source_cues(3)), language="en", script=None, engine="translate:gemma",
        model="gemma", version="g", created_at=store.now(), inputs={},
        meta={"role": "translation"}, glossary_sha=sha))
    side = store.append(video, side.header, [rec, HeadRecord(
        track="en", rendition=rec.id, replaces=head, by="auto", at=store.now())])
    store.project(video, side.header, side, "en", "srt", overwrite_foreign=False)
    srt = video.with_name(EN)
    srt.write_bytes(srt.read_bytes().replace(b"How are you?", b"How do you do?"))
    backend = LocalBackend(gemma(), Tools.find(), KeyRing(environ={}),
                           Cache(tmp_path / "cache", max_bytes=10**9))
    ep = backend.open(str(video))
    body = ep.sidecar.renditions()[ep.heads["en"]].body
    assert (body["engine"], body["model"], body["payload"].get("glossary_sha")) == (
        "external", "gemma", sha)
    assert en_stale(ep) == [False, False, False]
    assert en_stale(edit(backend, ep, op="set_text", cue=sid(2), text="はい")) == [
        False, False, True]


def test_vid2sub_translate_stale_only_still_keeps_a_track_edited_outside(video, monkeypatch):
    srt = video.with_name(EN)
    srt.write_bytes(srt.read_bytes().replace(b"How are you?", b"How do you do?"))
    result = cli_translate(video, monkeypatch, fresh=False)
    assert result.kept == ["en"] and store.load(video)[0].head("en").by == "external"
    assert "How do you do?" in srt.read_text(encoding="utf-8")


def test_a_line_reworded_and_retimed_outside_is_kept_as_a_persons_edit(backend, video):
    srt = video.with_name(EN)
    srt.write_text(srt.read_text(encoding="utf-8").replace(
        "00:00:03,600 --> 00:00:06,600\nHow are you?",
        "00:00:04,100 --> 00:00:06,600\nHow have you been?"), encoding="utf-8")
    ep = backend.open(str(video))
    (fixed,) = [c for c in ep.tracks.translations["en"] if c.text == "How have you been?"]
    assert fixed.flags == ("edited",)  # so Retranslate stale never replaces it (§13.4)
```

- [ ] **Step 27: Run them; watch them fail.** `uv run pytest tests/test_store.py
  tests/test_backend_save.py -q`. Expected: `6 failed, 50 passed`:
  `test_an_outside_edit_to_a_file_from_an_older_version_diverges_from_the_head`
  (`E       AssertionError: assert False`, at `isinstance(head, Conflict)`),
  `test_a_failed_write_leaves_the_file_counted_as_the_version_it_still_holds`
  (`E       AssertionError: assert ('r_…') == ('r_…')`),
  `test_an_outside_edit_to_a_file_a_save_couldnt_write_diverges_from_the_save`
  (`E       AssertionError: assert set() == {'ja'}`),
  `test_an_outside_edit_keeps_the_glossary_and_model_its_translation_was_made_with`
  (`E       AssertionError: assert ('external', None, None) == ('external', ...', '7537b9fd')`),
  `test_a_line_reworded_and_retimed_outside_is_kept_as_a_persons_edit`
  (`E       AssertionError: assert () == ('edited',)`), and M1's
  `test_a_write_interrupted_after_its_record_is_not_taken_for_an_outside_edit`, whose one changed
  line now asserts what the file holds (`E       AssertionError: assert '…' == '…'`).
- [ ] **Step 28: Write the code,** in `src/vid2sub/store.py`.
  Replace the module docstring's last sentence

```python
ours edited since vid2sub wrote it is never overwritten until the edit has been recorded as a
version (controller ruling, Task 28).
"""
```

  with

```python
ours edited since vid2sub wrote it is never overwritten until the edit has been recorded as a
version (controller ruling, Task 28). That version replaces the one its file was written from, not
whatever head is current, so an edit to a file the head has moved on from diverges from the head,
a conflict the person resolves (spec §14.4); and a write that fails puts back the file's previous
projection record, so the file still counts as the version it holds. The external version keeps
the glossary hash and model of the version its file was written from, since a text edit changes
neither (§13.4), and every line the person changed or added is `edited`, so it is never replaced
automatically (Phase 2, Task 6).
"""
```

  In `project`, replace

```python
    sidecar = append(video, header, [record])
    safe_write(path, data, overwrite=existing is not None)
    return sidecar, path, True
```

  with

```python
    sidecar = append(video, header, [record])
    try:
        safe_write(path, data, overwrite=existing is not None)
    except (OSError, WriteRefused):
        if previous is not None:  # the file still holds the version `previous` recorded
            # a finer time than now()'s seconds, so it never merges into the record it copies
            at = datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
            append(video, header, [previous.model_copy(update={"at": at})])
        raise
    return sidecar, path, True
```

  In `check_external`'s docstring, replace

```python
    An unreadable or emptied file is neither adopted nor touched, so `project` later refuses it
    as `EditedOnDisk`. Two edited files of one track chain their heads rather than diverge.
    """
```

  with

```python
    An unreadable or emptied file is neither adopted nor touched, so `project` later refuses it
    as `EditedOnDisk`. The new version's head replaces the version the file was written from, so
    if the head has moved on since, the two diverge (spec §14.4); two edited files of one track
    chain their heads rather than diverge.
    """
```

  In `align_ids`, replace

```python
        if match is None:
            out.append(Cue(id=new_cue_id(taken), start_ms=p.start_ms, end_ms=p.end_ms,
                           text=p.text))
```

  with

```python
        if match is None:  # a line the person added, or reworded and retimed: theirs
            out.append(Cue(id=new_cue_id(taken), start_ms=p.start_ms, end_ms=p.end_ms,
                           text=p.text, flags=("edited",)))
```

  In `check_external`, replace

```python
        body = cues_body(align_ids(parsed, projected), language=language, script=script,
                         engine="external", model=None, version=f"external@{digest[:12]}",
                         created_at=now(), inputs={"file_sha256": digest},
                         meta={"file": name, "role": projected_body.get("meta", {}).get("role")})
        rec = make_rendition(
```

  with

```python
        body = cues_body(align_ids(parsed, projected), language=language, script=script,
                         engine="external", model=projected_body.get("model"),
                         version=f"external@{digest[:12]}", created_at=now(),
                         inputs={"file_sha256": digest},
                         meta={"file": name, "role": projected_body.get("meta", {}).get("role")},
                         glossary_sha=projected_body.get("payload", {}).get("glossary_sha"))
        rec = make_rendition(
```

  and in its loop, replace

```python
        if proj.track not in latest:
            head = sidecar.head(proj.track)
            if isinstance(head, HeadRecord):
                latest[proj.track] = head.rendition
```

  with

```python
        latest.setdefault(proj.track, proj.rendition)
```

- [ ] **Step 29: Run the checks; they pass.** `uv run pytest tests/test_store.py
  tests/test_backend_save.py tests/test_pipeline.py tests/test_cli_more.py -q` first (every M1
  external-edit test passes unchanged but the one line above), then the guard checks, then
  `make check`. **Guard checks** (revert one, run `uv run pytest tests/test_store.py
  tests/test_backend_save.py -q`, restore it, then the next):
  1. *An outside edit never silently replaces a newer head:* replace
     `latest.setdefault(proj.track, proj.rendition)` with M1's `if proj.track not in latest:`,
     `head = sidecar.head(proj.track)`, `if isinstance(head, HeadRecord):`,
     `latest[proj.track] = head.rendition`: the two outside-edit tests and the failed-write test
     fail, `3 failed, 53 passed`.
  2. *A failed write leaves the file counted as what it holds:* replace
     `append(video, header, [previous.model_copy(update={"at": at})])` with `pass`: the
     failed-write test, the editor test and M1's interrupted-write test fail, `3 failed, 53
     passed`.
  3. *A text edit keeps the model:* in `check_external`, change `model=projected_body.get(
     "model"),` to `model=None,`: `FAILED tests/test_backend_save.py::test_an_outside_edit_keeps_the_glossary_and_model_its_translation_was_made_with`,
     `1 failed, 55 passed`.
  4. *A person's added line is theirs:* in `align_ids`, drop `, flags=("edited",)`: `FAILED
     tests/test_backend_save.py::test_a_line_reworded_and_retimed_outside_is_kept_as_a_persons_edit`,
     `1 failed, 55 passed`.

  `make check`. Expected: `694 passed, 2 skipped, 4 deselected` twice, `All checks passed!` and
  `no leaks found`.
- [ ] **Step 30: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
fix(store): 🤖 an outside edit diverges from a newer head, keeps its glossary and model, and marks the person's lines edited

Escaped from M1 Task 28 (no tier: built before this workflow), found by
Task 6's Tier 1 review. Spec §14.4: two heads neither of which descends
from the other are a conflict the person resolves; §15.3: an outside edit
comes back as an external version; §13.4: a translation is stale when its
source, the glossary's hash or the model changed, and one the user edited
is never replaced automatically.

- store.check_external made the external version's head replace the
  track's current head, so an edit to a file the head had moved on from
  silently replaced the newer version. It now replaces the version the
  file was written from (proj.rendition); two edited files of one track
  still chain, starting from that version. When the file was written
  from the current head, which is the usual case, nothing changes.
- store.project appends a file's projection record before writing it
  (so an interrupted write is never taken for a person's edit), so after
  a failed write the latest record named a version the file never held,
  and the fix above alone wouldn't help: a Save whose file write failed,
  then an outside edit, then any M1 command still replaced the editor's
  version. A write that fails with OSError or WriteRefused now appends
  the previous record again (at a microsecond time, so it never merges
  into the record it copies), and the file counts as the version it
  holds.
- The external version had model None and no glossary_sha, so one typo
  fixed in en.srt made every English cue stale (§13.4's model and
  glossary legs) and Retranslate stale would redo every unedited one. It
  now copies the model and payload.glossary_sha of the version its file
  was written from, as editor versions copy their head's: a text edit
  changes neither.
- align_ids flagged a changed line `edited` only when it kept its times
  (within 100 ms); a line the person added, or reworded and retimed, got
  no flag and no src, so Retranslate stale could replace it through the
  time-overlap rule. Such lines are now `edited` too.

M1's test_a_write_interrupted_after_its_record_is_not_taken_for_an_
outside_edit asserted the old record (sha256 != the old bytes'); it now
asserts the record names what the file holds (==). Everything else in
that test, and every other M1 external-edit test, passes unchanged.
`vid2sub translate --stale-only` after an outside edit to a translation
track still keeps the whole track (its head isn't auto): checked by
test_vid2sub_translate_stale_only_still_keeps_a_track_edited_outside.

The new tests failed first with: assert False (isinstance(head,
Conflict)) for test_an_outside_edit_to_a_file_from_an_older_version_
diverges_from_the_head; assert ('r_…') == ('r_…') for test_a_failed_
write_leaves_the_file_counted_as_the_version_it_still_holds; assert set()
== {'ja'} for test_an_outside_edit_to_a_file_a_save_couldnt_write_
diverges_from_the_save; assert ('external', None, None) == ('external',
'gemma', '7537b9fd') for test_an_outside_edit_keeps_the_glossary_and_
model_its_translation_was_made_with; assert () == ('edited',) for test_a_
line_reworded_and_retimed_outside_is_kept_as_a_persons_edit. Guards
checked by reverting each: with the head replacing the current head, or
with no record restored, three fail; without the copy, or without the
flag, one fails.

Docs read: none beyond the code (store.project, check_external,
align_ids, projected_digests; subs.sidecar.Sidecar.add, which merges
records by content; pipeline._translate_targets).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 6
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/store.py tests/test_store.py tests/test_backend_save.py`, `git commit -F
  .git/COMMIT_MSG`, then `git log -1 --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 31: Write the failing test:** a term added at Save makes every translation stale
  straight away, as it does while it waits and on the next open (spec §13.4; M1 decides it the
  same way, and this is intended, not a side effect).
  In `tests/test_backend_save.py`, directly above `def test_a_new_glossary_is_made_when_there_is_none(`, add (each function followed by two blank lines):

```python
def every_translation_stale(ep) -> bool:
    flags = [c["flags"] for row in views.episode_view(ep, video_url=None, audio_url=None)["rows"]
             for c in row["tr"]["en"]["cues"]]
    return bool(flags) and all("stale" in f for f in flags)


def test_a_term_added_at_save_makes_every_translation_stale_as_intended(backend, video):
    """Spec §13.4: the glossary's hash is part of what a translation was made with, so once a
    term is added every translation made without it is stale, as M1 decides it too."""
    ep = backend.open(str(video))
    assert not every_translation_stale(ep)
    ep = edit(backend, ep, op="glossary_add", term="工藤新一", translation="Shinichi Kudo")
    assert every_translation_stale(ep)  # already, while the term waits for Save
    saved, _ = backend.save(ep, formats=["srt"])
    assert saved.glossary == parse_glossary(video.with_name(GLOSSARY).read_text(encoding="utf-8"))
    assert every_translation_stale(saved) and every_translation_stale(backend.open(str(video)))
```

- [ ] **Step 32: Run it; watch it fail.** `uv run pytest tests/test_backend_save.py -q`.
  Expected: `E       AssertionError: assert Glossary(desc...='', terms=()) == Glossary(desc...ichi
  Kudo'),))` (the saved episode still held the glossary as it was at open) and `1 failed, 35
  passed`.
- [ ] **Step 33: Write the code.**
  In `src/vid2sub/web/backend.py`'s module docstring, replace

```python
Glossary terms are written at Save (the plan's Decision 5), appended to the file beside the video
so its comments survive. A Save, like a pick, starts the undo history again, because the tracks
are read back from the sidecar. While a translation is in conflict, no source cue can be split,
merged or deleted: the unloaded version's cues would keep pointing at ids that are gone.
```

  with

```python
Glossary terms are written at Save (the plan's Decision 5), appended to the file beside the video
so its comments survive, and the file is read back: a term just added makes every translation
made without it stale (§13.4), as M1 decides it too, and that is intended. A Save, like a pick,
starts the undo history again, because the tracks are read back from the sidecar. While a
translation is in conflict, no source cue can be split, merged or deleted: the unloaded version's
cues would keep pointing at ids that are gone.
```

  In `save`, below `adds, glossary_notes = _write_glossary(ep.video, ep.glossary_adds)`, add:

```python
            try:  # read back, so a term just added makes translations stale (§13.4), as at open
                glossary: Glossary | None = read_glossary(ep.video)
            except (GlossaryError, OSError):
                glossary = None
```

  and replace

```python
                        taken=ep.taken | cue_ids(side), glossary_adds=adds)
```

  with

```python
                        taken=ep.taken | cue_ids(side), glossary_adds=adds, glossary=glossary)
```

- [ ] **Step 34: Run the checks; they pass.** `uv run pytest tests/test_backend_save.py -q` first
  (`36 passed`), then `make check`. Expected: `695 passed, 2 skipped, 4 deselected` twice,
  `All checks passed!` and `no leaks found`.
- [ ] **Step 35: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(web): 🤖 Save reads the glossary back, so a term just added makes every translation stale, as spec §13.4 intends

After writing the glossary terms, Save reads vid2sub.glossary.toml back
into the episode's `glossary` (None if it can't be read), as open does.
So once a term is added, every translation made without it shows stale
straight away, as it already did while the term waited for Save and as
it will on the next open: the glossary's hash is part of what a
translation was made with (spec §13.4), and M1's pipeline decides it the
same way. This is intended, not a side effect: Retranslate stale then
redoes those translations with the term, keeping edited ones.

The new test failed first with: AssertionError: assert Glossary(
description='', terms=()) == Glossary(… ('工藤新一', 'Shinichi Kudo'),))
(the saved episode still held the glossary as it was at open).

Docs read: none beyond the code (pipeline._translate_targets).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 6
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/web/backend.py tests/test_backend_save.py`, `git commit -F
  .git/COMMIT_MSG`, then `git log -1 --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 36: Review, look forward, close.** The Tier 1 review from `$(cat .git/TASK_BASE)`
  (`AGENTS.md`, *Reviews*, with the security checklist: secrets (none touched: no key or
  token is read here); permissions (the glossary and subtitle files go through `safe_write`,
  never through a link); network exposure (none: no network call in this task); failing closed
  (a sidecar vid2sub can't read, or one that's gone, stops the Save before anything is written;
  a conflicted track is never written or re-headed); injection (`parse_op` refuses unknown
  fields and kinds, coerces nothing, bounds every value, and never echoes one; `resolve` checks
  the track before naming it); logging (no logger here; every message names files by their bare
  name only)); the forward review over Tasks 7, 15, 16 and 17 (Task 7's `retranslate` pushes
  one undo step as `apply` does and reads `_editable`; Task 15's `edit`, `undo` and `redo`
  inputs call `parse_op`, show a `BadOp` or `EditError` as a notice, and may run `apply` on the
  event loop (about 0.02 s for a 2,000-cue episode); Task 16's `save` and `resolve` inputs run
  off the event loop, show `SaveResult` as the `save_result` message (written, foreign, conflicts,
  notes), offer the conflict picker from the view's `conflicts`, and now take `resolve`'s
  `(Episode, SaveResult)`; after a Save that added a glossary term, every translation shows
  stale, which is intended); the docs this task made untrue: the skeleton's `resolve -> Episode`
  (now `-> tuple[Episode, SaveResult]`, in Task 6's Interfaces and any later listing that names
  it), and the spec's S29 and S32 rows, which name `tests/test_save.py`: their Proof becomes
  `tests/test_backend_save.py` (S29: `tests/test_backend_save.py; the exit test`). Then the
  close, its own commit, holding this plan with this task's boxes ticked and **Now** set to
  `Task 7: The editor backend: retranslate, open.`, and the spec's S32 set to `built`; S28 and
  S29 stay `planned` (Task 15's Playwright and the exit test). The message, in
  `.git/CLOSE_MSG`:

```text
docs(plan): 🤖 close Task 6: The editor backend: edits and Save

Drift: none
Rulings: none
Phase-end: none
Forward: none
Tier: 1
Rounds: none
Findings: none

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 6
Co-Authored-By: <the model's own line>
```

  `git add docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md
  docs/superpowers/specs/2026-10-14-vid2sub-design.md`, `git commit -F .git/CLOSE_MSG`.

***

### Task 7: The editor backend: retranslate

**Tier:** 2 · **Scenarios:** S30

**Files:**
- Modify: `src/vid2sub/web/backend.py`
- Test: `tests/test_backend_retranslate.py`

**Interfaces:**
- Consumes: `translate.run.translate_cues`, `make_ask`; `detect.candidates`; `catalog.suggest`
  (M1's translate route); `engines.clients.RunPolicy`, `check_allowed`; `engines.base.EngineError`;
  `subs.translate_shape.stale_ids`, `untranslated`; `subs.model.check_track`; Task 5's
  `read_glossary`, `glossary_with`, `track_setup`, `setup_changed`, `_lang`; Task 6's undo stack,
  `_editable` and `_editor_body`; `tests/fakes.FakeServer`, `chat_responder`, `closed_port_url`.
- Produces:
  - `LocalBackend.retranslate(self, ep: Episode, track: str, *, ids: Sequence[str] | None,
    model: str | None = None, allow_cloud: bool = False,
    on_batch: Callable[[int, int], None] | None = None) -> Episode`: `ids=None` is every stale
    or untranslated source cue, never replacing a translation flagged `edited` (spec §13.4);
    named `ids` are source cue ids, translated whatever their translation (the person asked).
    One undo step; `ep` itself when there's nothing to translate (no model is asked). The model
    is `model` (a translation model in `vid2sub.toml`), else the catalog route's pick, as M1
    picks; a route whose model's server isn't answering raises rather than taking the next
    model or the cloud. Cloud only when this call's `allow_cloud` is set, checked before
    anything is sent. It blocks on the model's server, for minutes on a whole episode: the
    server runs it off Shiny's event loop, holds edits to that episode until it returns, and
    shows progress from `on_batch(n, of)`, which runs on the calling thread. Raises
    `EditError` (a track in conflict; an unknown track or cue, named without echoing it),
    `EngineError` (`.kind`, `.hint`: no usable model, a cloud model not allowed, the server down
    or refusing), `TranslationFailed` or `GlossaryError`; the episode is unchanged then. With
    `ids=None`, spec §13.4's other two legs apply as M1 applies them: when the track's glossary
    hash or model (`track_setup`) isn't the one this call uses (the glossary beside the video with
    the terms waiting for Save; `model`, else the route's pick), every unedited cue is stale. The
    model is chosen before the plan, so with none named the route's servers are asked which
    models they serve even when nothing turns out stale.
  - `Episode.made_with: dict[str, tuple[str, str | None]] = {}`: the glossary hash and model of
    a retranslation that redid every unedited cue of a track; `track_setup` returns it while none
    of the cues it replaced is back (an undo), so the view stops flagging the track and Save
    records that pair in the editor version (`_editor_body` takes `setup=track_setup(ep,
    track)`). Save and a pick clear it.
  - `backend.retranslation(source: Sequence[Cue], cues: Sequence[Cue],
    ids: Sequence[str] | None, *, everything: bool = False) -> tuple[list[str], set[str]]`
    (pure; `everything`: every cue stale, for the two legs above; returns the source ids to
    translate, in order, and the translation ids they replace, in whole groups so the result
    never overlaps; with `ids=None`, cues an edited translation would have to give up are left
    out)

- [ ] **Step 0: Record the base:** `git rev-parse HEAD > .git/TASK_BASE`.
- [ ] **Step 1: Write the failing test,** `tests/test_backend_retranslate.py`:

```python
import re

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
from vid2sub.subs.model import Cue, check_track
from vid2sub.subs.translate_shape import src_sha
from vid2sub.web import backend as web_backend
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
              text="えっ")
    inserted = ep.tracks.source[1].id
    out = backend.retranslate(ep, "en", ids=None)
    assert asked == [[inserted]]
    assert [t for _, t in en(out)] == [ENGLISH[0], f"EN {inserted}", *ENGLISH[1:]]


def test_a_cue_inserted_inside_a_translation_spanning_two_cues_is_translated_with_them(
        backend, video, asked):
    spanning(video)
    ep = edit(backend, backend.open(str(video)), op="insert", start_ms=6700, end_ms=7100,
              text="えっ")
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
              text="えっ")
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
```

- [ ] **Step 2: Run it; watch it fail.** `uv run pytest tests/test_backend_retranslate.py -q`.
  Expected: `E       AttributeError: <module 'vid2sub.web.backend' from
  '…/src/vid2sub/web/backend.py'> has no attribute 'make_ask'` (twelve times, from the `asked`
  fixture), `E           AttributeError: 'LocalBackend' object has no attribute 'retranslate'`,
  `E       AttributeError: module 'vid2sub.web.backend' has no attribute 'retranslation'`, and
  `4 failed, 12 errors`.
- [ ] **Step 3: Write the code.**
  In `src/vid2sub/web/backend.py`, replace the module docstring

```python
"""The editor's backend: opening an episode M1 made, editing it and saving it (spec §19.1, §20).

The web app's server calls this, never the store directly, so the CLI and the editor share one
core (spec §18.3); `capabilities()` tells the frontend which controls exist (`BrowserBackend`, in
Pages, is Phase 4's). Phase 2's editor opens only episodes that already have a sidecar: making
subtitles is `vid2sub run` or the Jobs page. Opening folds in edits made outside vid2sub, as
every M1 command does (§15.3, S31), and says so in notes that name files only by their bare name
(§6.8). A track whose heads diverged is in conflict (§14.4): it isn't loaded, and its versions
are listed for the person to pick; when that is the source, every edit waits for the pick, since
translations hang off source cues. The spoken words come from the transcript the source was
built from, following rendition parents, so word highlighting matches the cues' `w` ranges. Audio
in AC-3, E-AC-3, DTS or TrueHD can't be played by a browser (§8.2), so the editor then plays the
playback audio instead (the Phase 2 plan's Decision 2). An `Episode` is never changed in place:
every call returns a new one, so a reactive value that holds it sees each change. A translation
is stale, as spec §13.4 says and M1 decides (pipeline._translate_targets), when its source text
changed, and every cue of it is when the glossary's hash or the translation model differs from
the ones its head was made with; so the episode holds the glossary beside the video and the model
Retranslate would use with none named, picked offline from the catalog route as M1 picks it but
taking every configured local server to answer (no request is made at open). Edits run
through the pure `subs.edit` rules, so they exist once (§20); each one that changes something
pushes the tracks and the pending glossary adds onto the undo stack (the last 200 steps) and
clears redo. A track in conflict can't be edited, and nothing but a glossary add can while the
source is, until a person picks a version.

Save (spec §14.5, §14.6) first records any outside edit to a subtitle file as M1 does, so an
edit made in another program since the open is a version too, never something a later open puts
over the editor's. Then it appends one `editor` version per changed track, whose parent is the
head the editor's cues came from, and a head that replaces that same head: never the head on disk
now, so a CLI run, another tab or that outside edit leaves two heads, a conflict both versions
survive, rather than one silently replacing the other (Review Focus 2 and 4). A track whose head
on disk already holds exactly these cues (the same Save sent twice) gets nothing. The records go
in one `store.append`, compare-and-swap with a union merge, so no other writer's records are
lost. Only then are the files written, through `store.project` with `overwrite_foreign` off:
someone else's file is left alone and reported (§6.6, §15.3), and a track in conflict isn't
written until a person picks a version with `resolve`, the only thing that moves a head on a
conflicted track. Once the versions are in the sidecar nothing raises: a file that can't be
written is a note, and the episode moves to the new heads either way. Saves and picks on one
video take turns within this engine, so two picks at once can't replace each other in a cycle.
Glossary terms are written at Save (the plan's Decision 5), appended to the file beside the video
so its comments survive, and the file is read back: a term just added makes every translation
made without it stale (§13.4), as M1 decides it too, and that is intended. A Save, like a pick,
starts the undo history again, because the tracks are read back from the sidecar. While a
translation is in conflict, no source cue can be split, merged or deleted: the unloaded version's
cues would keep pointing at ids that are gone.
"""
```

  with

```python
"""The editor's backend: opening, editing, retranslating and saving an episode (spec §19.1, §20).

The web app's server calls this, never the store directly, so the CLI and the editor share one
core (spec §18.3); `capabilities()` tells the frontend which controls exist (`BrowserBackend`, in
Pages, is Phase 4's). Phase 2's editor opens only episodes that already have a sidecar: making
subtitles is `vid2sub run` or the Jobs page. Opening folds in edits made outside vid2sub, as
every M1 command does (§15.3, S31), and says so in notes that name files only by their bare name
(§6.8). A track whose heads diverged is in conflict (§14.4): it isn't loaded, and its versions
are listed for the person to pick; when that is the source, every edit waits for the pick, since
translations hang off source cues. The spoken words come from the transcript the source was
built from, following rendition parents, so word highlighting matches the cues' `w` ranges. Audio
in AC-3, E-AC-3, DTS or TrueHD can't be played by a browser (§8.2), so the editor then plays the
playback audio instead (the Phase 2 plan's Decision 2). An `Episode` is never changed in place:
every call returns a new one, so a reactive value that holds it sees each change. A translation
is stale, as spec §13.4 says and M1 decides (pipeline._translate_targets), when its source text
changed, and every cue of it is when the glossary's hash or the translation model differs from
the ones its head was made with; so the episode holds the glossary beside the video and the model
Retranslate would use with none named, picked offline from the catalog route as M1 picks it but
taking every configured local server to answer (no request is made at open). Edits run
through the pure `subs.edit` rules, so they exist once (§20); each one that changes something
pushes the tracks and the pending glossary adds onto the undo stack (the last 200 steps) and
clears redo. A track in conflict can't be edited, and nothing but a glossary add can while the
source is, until a person picks a version.

Save (spec §14.5, §14.6) first records any outside edit to a subtitle file as M1 does, so an
edit made in another program since the open is a version too, never something a later open puts
over the editor's. Then it appends one `editor` version per changed track, whose parent is the
head the editor's cues came from, and a head that replaces that same head: never the head on disk
now, so a CLI run, another tab or that outside edit leaves two heads, a conflict both versions
survive, rather than one silently replacing the other (Review Focus 2 and 4). A track whose head
on disk already holds exactly these cues (the same Save sent twice) gets nothing. The records go
in one `store.append`, compare-and-swap with a union merge, so no other writer's records are
lost. Only then are the files written, through `store.project` with `overwrite_foreign` off:
someone else's file is left alone and reported (§6.6, §15.3), and a track in conflict isn't
written until a person picks a version with `resolve`, the only thing that moves a head on a
conflicted track. Once the versions are in the sidecar nothing raises: a file that can't be
written is a note, and the episode moves to the new heads either way. Saves and picks on one
video take turns within this engine, so two picks at once can't replace each other in a cycle.
Glossary terms are written at Save (the plan's Decision 5), appended to the file beside the video
so its comments survive, and the file is read back: a term just added makes every translation
made without it stale (§13.4), as M1 decides it too, and that is intended. A Save, like a pick,
starts the undo history again, because the tracks are read back from the sidecar. While a
translation is in conflict, no source cue can be split, merged or deleted: the unloaded version's
cues would keep pointing at ids that are gone.

Retranslate (spec §13.4, §20) redoes the stale and untranslated cues, or the cues a person names,
as one undoable edit. The model is the one named, else the one M1's catalog route picks; a cloud
model only when this call allows it (§7.2), checked before anything is sent, and a route whose
model's server is down is never passed over for the next one or the cloud (§17.4). Retranslating
stale never replaces a translation a person edited (§13.4); naming a cue does, since that is the
person asking. Translations are replaced in whole groups: every source cue a replaced translation
covers is translated with it, and a translation whose time overlaps the cues being translated is
replaced too (a cue inserted inside a translation that spans two cues), so the track never
overlaps; where that would replace an edited translation, those cues are left as they are.
"""
```

  Replace the imports, from `from __future__ import annotations` down to `from vid2sub.web import ops`,

```python
from __future__ import annotations

import codecs
import os
import secrets
import tempfile
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Literal

from vid2sub import __version__, store
from vid2sub import detect as detecting
from vid2sub.cache import Cache
from vid2sub.catalog import suggest
from vid2sub.config import Config
from vid2sub.engines.clients import KeyRing
from vid2sub.media.identity import identify
from vid2sub.media.probe import Probe, ProbeError, pick_track, probe
from vid2sub.media.tools import ToolFailed, ToolMissing, Tools
from vid2sub.pipeline import MEDIA_SUFFIXES, video_change
from vid2sub.security import InputRefused, WriteRefused, resolve_input, safe_write
from vid2sub.subs import edit, naming
from vid2sub.subs.edit import SOURCE, EditError, Tracks
from vid2sub.subs.glossary import (
    EMPTY_GLOSSARY,
    Glossary,
    GlossaryError,
    add_terms,
    parse_glossary,
)
from vid2sub.subs.model import Cue, Word
from vid2sub.subs.rendition import cues_body, cues_from_body, transcript_from_body
from vid2sub.subs.sidecar import (
    Conflict,
    Header,
    HeadRecord,
    RenditionRecord,
    Sidecar,
    SidecarError,
    make_rendition,
)
from vid2sub.web import ops
```

  with

```python
from __future__ import annotations

import codecs
import os
import secrets
import tempfile
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Literal

from vid2sub import __version__, store
from vid2sub import detect as detecting
from vid2sub.cache import Cache
from vid2sub.catalog import suggest
from vid2sub.config import Config
from vid2sub.engines.base import EngineError
from vid2sub.engines.clients import KeyRing, RunPolicy, check_allowed
from vid2sub.media.identity import identify
from vid2sub.media.probe import Probe, ProbeError, pick_track, probe
from vid2sub.media.tools import ToolFailed, ToolMissing, Tools
from vid2sub.pipeline import MEDIA_SUFFIXES, video_change
from vid2sub.security import InputRefused, WriteRefused, resolve_input, safe_write
from vid2sub.subs import edit, naming
from vid2sub.subs.edit import SOURCE, EditError, Tracks
from vid2sub.subs.glossary import (
    EMPTY_GLOSSARY,
    Glossary,
    GlossaryError,
    add_terms,
    parse_glossary,
)
from vid2sub.subs.model import Cue, TrackError, Word, check_track
from vid2sub.subs.rendition import cues_body, cues_from_body, transcript_from_body
from vid2sub.subs.sidecar import (
    Conflict,
    Header,
    HeadRecord,
    RenditionRecord,
    Sidecar,
    SidecarError,
    make_rendition,
)
from vid2sub.subs.translate_shape import stale_ids, untranslated
from vid2sub.translate.run import make_ask, translate_cues
from vid2sub.web import ops
```

  In `class LocalBackend`, directly above `    def _check_open(self, ep: Episode) -> None:`, add (each method followed by one blank line):

```python
    def retranslate(self, ep: Episode, track: str, *, ids: Sequence[str] | None,
                    model: str | None = None, allow_cloud: bool = False,
                    on_batch: Callable[[int, int], None] | None = None) -> Episode:
        """`ids=None`: every stale or untranslated source cue, never replacing an edited
        translation; else those source cues, whatever their translation. One undo step; `ep`
        itself when there's nothing to translate. Blocks on the model's server. Raises EditError
        (a track in conflict, an unknown track or cue), EngineError (no usable model, a cloud
        model this call doesn't allow, the server down or refusing: `.hint` names the fix),
        TranslationFailed, or GlossaryError (a glossary beside the video vid2sub can't read);
        nothing changes then."""
        self._check_open(ep)
        if track not in naming.TRACKS:  # it comes from the browser: never echoed unchecked
            raise EditError("there's no such track")
        _editable(ep, track)
        if track not in ep.tracks.translations:
            raise EditError(f"there is no {track} track")
        source, cues = ep.tracks.source, ep.tracks.translations[track]
        wanted, replaced = retranslation(source, cues, ids)
        if not wanted:
            return ep
        lang = _lang(ep.source_key)
        name = self._translator(lang, model, allow_cloud)
        entry = self.config.models[name]
        policy = RunPolicy(allow_cloud)
        check_allowed(name, entry, self.config, policy)
        ask = make_ask(name, entry, self.config, policy, self.keys)
        taken = set(ep.taken)
        new = translate_cues(source, source_lang=lang, target_track=track,
                             glossary=glossary_with(read_glossary(ep.video), ep.glossary_adds),
                             ask=ask, only=wanted, taken=taken, on_batch=on_batch)
        result = tuple(sorted([c for c in cues if c.id not in replaced] + new,
                              key=lambda c: (c.start_ms, c.end_ms)))
        try:
            check_track(result)
        except TrackError as err:
            raise EditError(f"the {track} track would break: {err}") from None
        tracks = Tracks(source, {**ep.tracks.translations, track: result})
        return replace(ep, tracks=tracks, taken=taken, redo=[],
                       undo=[*ep.undo, (ep.tracks, ep.glossary_adds)][-UNDO_STEPS:])

    def _translator(self, lang: str, model: str | None, allow_cloud: bool) -> str:
        """The named model, else the catalog route's pick, as M1's pipeline picks (§11.2). A route
        whose model's server isn't answering stops here rather than taking the next model."""
        if model is not None:
            entry = self.config.models.get(model)
            if entry is None or entry.task != "translate":
                raise EngineError("unavailable", "that isn't a translation model in vid2sub.toml",
                                  hint="`vid2sub models` lists them")
            return model
        cands = detecting.candidates(self.config, self.keys)

        def pick(c: list) -> str | None:
            return suggest(lang, c, "translate", allow_cloud=allow_cloud).model

        hoped = pick([replace(c, available=True, reason="") if c.unreachable else c
                      for c in cands])
        if any(c.name == hoped and c.unreachable for c in cands):
            raise EngineError("connection", "the translation model's server isn't reachable",
                              hint="is it running? For the Spark: is `make tunnel` running?")
        s = suggest(lang, cands, "translate", allow_cloud=allow_cloud)
        if s.model is None:
            raise EngineError("unavailable", "no usable translation model",
                              hint="; ".join(f"{n}: {r}" for n, r in s.considered)
                              or "add one to vid2sub.toml (`vid2sub config init`)")
        return s.model
```

  Directly above `def _formats(formats: Sequence[str]) -> list[str]:`, add (each function followed by two blank lines):

```python
def retranslation(source: Sequence[Cue], cues: Sequence[Cue], ids: Sequence[str] | None
                  ) -> tuple[list[str], set[str]]:
    """The source cue ids to translate, in order, and the translation cue ids they replace.

    Whole groups, so the new cues never overlap the kept ones: a replaced translation brings
    every source cue it covers, and a translation that covers a cue being translated, or whose
    time overlaps a run of them, is replaced too. With `ids=None` an edited translation is never
    replaced; the cues it would have brought in are left out instead."""
    order = {c.id: k for k, c in enumerate(source)}
    by_id = {c.id: c for c in source}
    if ids is None:
        stale = stale_ids(cues, by_id)
        wanted = {i for c in cues if c.id in stale and "edited" not in c.flags
                  for i in c.src or () if i in by_id}
        wanted |= set(untranslated(list(order), cues))
    else:
        if any(i not in by_id for i in ids):
            raise EditError("one of those cues isn't in the source track")
        wanted = set(ids)
    blocked: set[str] = set()
    while True:
        chosen = sorted(wanted - blocked, key=order.__getitem__)
        runs = _runs(chosen, order, by_id)
        replaced: set[str] = set()
        grow: set[str] = set()
        block: set[str] = set()
        for c in cues:
            covers = {i for i in c.src or () if i in by_id}
            hits = [ids_ for start, end, ids_ in runs
                    if covers & ids_ or (c.start_ms < end and start < c.end_ms)]
            if not hits:
                continue
            if (ids is not None or "edited" not in c.flags) and not covers & blocked:
                replaced.add(c.id)
                grow |= covers
            else:
                block |= covers.union(*hits)
        if block - blocked:
            blocked |= block
        elif grow - wanted:
            wanted |= grow
        else:
            return chosen, replaced


def _runs(chosen: Sequence[str], order: dict[str, int], by_id: dict[str, Cue]
          ) -> list[tuple[int, int, set[str]]]:
    """Each run of adjacent source cues: its start, its end and its ids."""
    runs: list[tuple[int, int, set[str]]] = []
    last = -2
    for cid in chosen:
        c = by_id[cid]
        if order[cid] == last + 1:
            start, _, members = runs[-1]
            runs[-1] = (start, c.end_ms, members | {cid})
        else:
            runs.append((c.start_ms, c.end_ms, {cid}))
        last = order[cid]
    return runs
```

- [ ] **Step 4: Run the checks; they pass.** `uv run pytest tests/test_backend_retranslate.py -q`
  first (`16 passed`), then the group check, then `make check`. **Group check** (Task 2's author
  found the hazard: a cue inserted inside a translation that spans two cues): in
  `retranslation`, change `if covers & ids_ or (c.start_ms < end and start < c.end_ms)]` to
  `if covers & ids_]`; the run gives `FAILED
  tests/test_backend_retranslate.py::test_a_cue_inserted_inside_a_translation_spanning_two_cues_is_translated_with_them`
  (`the en track would break: cue … overlaps cb0000009`), the edited variant, and the property
  test (`cue n0 overlaps t3`, or another), `3 failed, 13 passed`; restore it. `make check`.
  Expected: `711 passed, 2 skipped, 4 deselected` twice (the local zone, then UTC),
  `All checks passed!` and `no leaks found`.
- [ ] **Step 5: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(web): 🤖 the editor retranslates stale cues, or the cues a person names, in whole groups, as one undoable edit

LocalBackend.retranslate(ep, track, *, ids, model=None, allow_cloud=False,
on_batch=None) (spec §13.4, §20, §7.2; S30). ids=None takes every stale
source cue (translate_shape.stale_ids) and every untranslated one, never
replacing a translation flagged edited; named ids are translated whatever
their translation, since the person asked. backend.retranslation plans
it in whole groups: a replaced translation brings every source cue it
covers, and a translation that covers a cue being translated, or whose
time overlaps a run of them, is replaced too, so a cue inserted inside a
translation spanning two cues is translated with both and the track never
overlaps (subs.edit would refuse it); where that would replace an edited
translation, those cues are left out. The model is the one named (it must
be a translation model in vid2sub.toml), else the one M1's catalog route
picks from detect.candidates; a route whose model's server isn't
answering raises EngineError("connection") rather than taking the next
model or the cloud (§17.4); a cloud model is used only when this call sets
allow_cloud, checked with clients.check_allowed before anything is sent;
make_ask goes through the one client factory. The glossary is read as M1
reads it, with the terms waiting for Save. translate_cues gets
taken=ep.taken and on_batch; the result is checked with check_track and
pushed as one undo step. It blocks on the network: the server calls it
off Shiny's event loop.

The new test failed first with: AttributeError: <module
'vid2sub.web.backend'> has no attribute 'make_ask' (12 errors) and
AttributeError: 'LocalBackend' object has no attribute 'retranslate'.
With the time-overlap rule removed from retranslation, the two
inserted-cue tests fail ("the en track would break: cue … overlaps
cb0000009") and so does the hypothesis property test ("cue n0 overlaps
t3"), which checks over random tracks (groups, edited, stale, untranslated
and inserted cues) that the plan never overlaps, never covers a source
cue twice and, for stale, never replaces an edited cue.

Docs read: none beyond the code (translate.run.make_ask and
translate_cues, clients.check_allowed and chat, detect.candidates,
catalog.suggest, pipeline._translator and _candidates_that_work); chatlas
is reached only through the existing client factory, unchanged.

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 7
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/web/backend.py tests/test_backend_retranslate.py`, `git commit -F
  .git/COMMIT_MSG`, then `git log -1 --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 6: Write the failing tests:** retranslating stale takes spec §13.4's other two legs,
  the glossary and the model, as M1 does. In `tests/test_backend_retranslate.py`:
  replace

```python
from vid2sub.subs.edit import EditError
```

  with

```python
from vid2sub.subs.edit import EditError
from vid2sub.subs.glossary import parse_glossary
```

  and

```python
from vid2sub.web import backend as web_backend
```

  with

```python
from vid2sub.web import backend as web_backend
from vid2sub.web import views
```

  Then directly above the comment `# The model: chosen as M1 chooses it, cloud only when this call allows it (spec §7.2, §11.2)`, add:

```python
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
```

- [ ] **Step 7: Run them; watch them fail.** `uv run pytest tests/test_backend_retranslate.py
  -q`. Expected: `E       AssertionError: assert [] == [['ca0000000'], ['ca0000002']]` (the
  glossary), `E       AssertionError: assert [] == [['ca0000000'... 'ca0000002']]` (twice: the
  model, and the named model), `E       assert [True, True, True] == [False, False, False]` (after
  redoing everything), and `4 failed, 16 passed`.
- [ ] **Step 8: Write the code.**
  In `src/vid2sub/web/backend.py`, replace the module docstring

```python
"""The editor's backend: opening, editing, retranslating and saving an episode (spec §19.1, §20).

The web app's server calls this, never the store directly, so the CLI and the editor share one
core (spec §18.3); `capabilities()` tells the frontend which controls exist (`BrowserBackend`, in
Pages, is Phase 4's). Phase 2's editor opens only episodes that already have a sidecar: making
subtitles is `vid2sub run` or the Jobs page. Opening folds in edits made outside vid2sub, as
every M1 command does (§15.3, S31), and says so in notes that name files only by their bare name
(§6.8). A track whose heads diverged is in conflict (§14.4): it isn't loaded, and its versions
are listed for the person to pick; when that is the source, every edit waits for the pick, since
translations hang off source cues. The spoken words come from the transcript the source was
built from, following rendition parents, so word highlighting matches the cues' `w` ranges. Audio
in AC-3, E-AC-3, DTS or TrueHD can't be played by a browser (§8.2), so the editor then plays the
playback audio instead (the Phase 2 plan's Decision 2). An `Episode` is never changed in place:
every call returns a new one, so a reactive value that holds it sees each change. A translation
is stale, as spec §13.4 says and M1 decides (pipeline._translate_targets), when its source text
changed, and every cue of it is when the glossary's hash or the translation model differs from
the ones its head was made with; so the episode holds the glossary beside the video and the model
Retranslate would use with none named, picked offline from the catalog route as M1 picks it but
taking every configured local server to answer (no request is made at open). Edits run
through the pure `subs.edit` rules, so they exist once (§20); each one that changes something
pushes the tracks and the pending glossary adds onto the undo stack (the last 200 steps) and
clears redo. A track in conflict can't be edited, and nothing but a glossary add can while the
source is, until a person picks a version.

Save (spec §14.5, §14.6) first records any outside edit to a subtitle file as M1 does, so an
edit made in another program since the open is a version too, never something a later open puts
over the editor's. Then it appends one `editor` version per changed track, whose parent is the
head the editor's cues came from, and a head that replaces that same head: never the head on disk
now, so a CLI run, another tab or that outside edit leaves two heads, a conflict both versions
survive, rather than one silently replacing the other (Review Focus 2 and 4). A track whose head
on disk already holds exactly these cues (the same Save sent twice) gets nothing. The records go
in one `store.append`, compare-and-swap with a union merge, so no other writer's records are
lost. Only then are the files written, through `store.project` with `overwrite_foreign` off:
someone else's file is left alone and reported (§6.6, §15.3), and a track in conflict isn't
written until a person picks a version with `resolve`, the only thing that moves a head on a
conflicted track. Once the versions are in the sidecar nothing raises: a file that can't be
written is a note, and the episode moves to the new heads either way. Saves and picks on one
video take turns within this engine, so two picks at once can't replace each other in a cycle.
Glossary terms are written at Save (the plan's Decision 5), appended to the file beside the video
so its comments survive, and the file is read back: a term just added makes every translation
made without it stale (§13.4), as M1 decides it too, and that is intended. A Save, like a pick,
starts the undo history again, because the tracks are read back from the sidecar. While a
translation is in conflict, no source cue can be split, merged or deleted: the unloaded version's
cues would keep pointing at ids that are gone.

Retranslate (spec §13.4, §20) redoes the stale and untranslated cues, or the cues a person names,
as one undoable edit. The model is the one named, else the one M1's catalog route picks; a cloud
model only when this call allows it (§7.2), checked before anything is sent, and a route whose
model's server is down is never passed over for the next one or the cloud (§17.4). Retranslating
stale never replaces a translation a person edited (§13.4); naming a cue does, since that is the
person asking. Translations are replaced in whole groups: every source cue a replaced translation
covers is translated with it, and a translation whose time overlaps the cues being translated is
replaced too (a cue inserted inside a translation that spans two cues), so the track never
overlaps; where that would replace an edited translation, those cues are left as they are.
"""
```

  with

```python
"""The editor's backend: opening, editing, retranslating and saving an episode (spec §19.1, §20).

The web app's server calls this, never the store directly, so the CLI and the editor share one
core (spec §18.3); `capabilities()` tells the frontend which controls exist (`BrowserBackend`, in
Pages, is Phase 4's). Phase 2's editor opens only episodes that already have a sidecar: making
subtitles is `vid2sub run` or the Jobs page. Opening folds in edits made outside vid2sub, as
every M1 command does (§15.3, S31), and says so in notes that name files only by their bare name
(§6.8). A track whose heads diverged is in conflict (§14.4): it isn't loaded, and its versions
are listed for the person to pick; when that is the source, every edit waits for the pick, since
translations hang off source cues. The spoken words come from the transcript the source was
built from, following rendition parents, so word highlighting matches the cues' `w` ranges. Audio
in AC-3, E-AC-3, DTS or TrueHD can't be played by a browser (§8.2), so the editor then plays the
playback audio instead (the Phase 2 plan's Decision 2). An `Episode` is never changed in place:
every call returns a new one, so a reactive value that holds it sees each change. A translation
is stale, as spec §13.4 says and M1 decides (pipeline._translate_targets), when its source text
changed, and every cue of it is when the glossary's hash or the translation model differs from
the ones its head was made with; so the episode holds the glossary beside the video and the model
Retranslate would use with none named, picked offline from the catalog route as M1 picks it but
taking every configured local server to answer (no request is made at open). Edits run
through the pure `subs.edit` rules, so they exist once (§20); each one that changes something
pushes the tracks and the pending glossary adds onto the undo stack (the last 200 steps) and
clears redo. A track in conflict can't be edited, and nothing but a glossary add can while the
source is, until a person picks a version.

Save (spec §14.5, §14.6) first records any outside edit to a subtitle file as M1 does, so an
edit made in another program since the open is a version too, never something a later open puts
over the editor's. Then it appends one `editor` version per changed track, whose parent is the
head the editor's cues came from, and a head that replaces that same head: never the head on disk
now, so a CLI run, another tab or that outside edit leaves two heads, a conflict both versions
survive, rather than one silently replacing the other (Review Focus 2 and 4). A track whose head
on disk already holds exactly these cues (the same Save sent twice) gets nothing. The records go
in one `store.append`, compare-and-swap with a union merge, so no other writer's records are
lost. Only then are the files written, through `store.project` with `overwrite_foreign` off:
someone else's file is left alone and reported (§6.6, §15.3), and a track in conflict isn't
written until a person picks a version with `resolve`, the only thing that moves a head on a
conflicted track. Once the versions are in the sidecar nothing raises: a file that can't be
written is a note, and the episode moves to the new heads either way. Saves and picks on one
video take turns within this engine, so two picks at once can't replace each other in a cycle.
Glossary terms are written at Save (the plan's Decision 5), appended to the file beside the video
so its comments survive, and the file is read back: a term just added makes every translation
made without it stale (§13.4), as M1 decides it too, and that is intended. A Save, like a pick,
starts the undo history again, because the tracks are read back from the sidecar. While a
translation is in conflict, no source cue can be split, merged or deleted: the unloaded version's
cues would keep pointing at ids that are gone.

Retranslate (spec §13.4, §20) redoes the stale and untranslated cues, or the cues a person names,
as one undoable edit. The model is the one named, else the one M1's catalog route picks; a cloud
model only when this call allows it (§7.2), checked before anything is sent, and a route whose
model's server is down is never passed over for the next one or the cloud (§17.4). Retranslating
stale never replaces a translation a person edited (§13.4); naming a cue does, since that is the
person asking. Translations are replaced in whole groups: every source cue a replaced translation
covers is translated with it, and a translation whose time overlaps the cues being translated is
replaced too (a cue inserted inside a translation that spans two cues), so the track never
overlaps; where that would replace an edited translation, those cues are left as they are. When
the glossary or the model this call uses isn't the one the track was made with, every unedited
cue is stale (§13.4, as M1 decides it); once a retranslation has redone them all, the track counts
as made with the new pair, which Save records, for as long as none of the cues it replaced is back.
"""
```

  In `class Episode`, below `glossary_adds: …`, add:

```python
    made_with: dict[str, tuple[str, str | None]] = field(default_factory=dict)  # since a redo-all
```

  Replace the method `retranslate`, from `    def retranslate(self` to its `return`,

```python
    def retranslate(self, ep: Episode, track: str, *, ids: Sequence[str] | None,
                    model: str | None = None, allow_cloud: bool = False,
                    on_batch: Callable[[int, int], None] | None = None) -> Episode:
        """`ids=None`: every stale or untranslated source cue, never replacing an edited
        translation; else those source cues, whatever their translation. One undo step; `ep`
        itself when there's nothing to translate. Blocks on the model's server. Raises EditError
        (a track in conflict, an unknown track or cue), EngineError (no usable model, a cloud
        model this call doesn't allow, the server down or refusing: `.hint` names the fix),
        TranslationFailed, or GlossaryError (a glossary beside the video vid2sub can't read);
        nothing changes then."""
        self._check_open(ep)
        if track not in naming.TRACKS:  # it comes from the browser: never echoed unchecked
            raise EditError("there's no such track")
        _editable(ep, track)
        if track not in ep.tracks.translations:
            raise EditError(f"there is no {track} track")
        source, cues = ep.tracks.source, ep.tracks.translations[track]
        wanted, replaced = retranslation(source, cues, ids)
        if not wanted:
            return ep
        lang = _lang(ep.source_key)
        name = self._translator(lang, model, allow_cloud)
        entry = self.config.models[name]
        policy = RunPolicy(allow_cloud)
        check_allowed(name, entry, self.config, policy)
        ask = make_ask(name, entry, self.config, policy, self.keys)
        taken = set(ep.taken)
        new = translate_cues(source, source_lang=lang, target_track=track,
                             glossary=glossary_with(read_glossary(ep.video), ep.glossary_adds),
                             ask=ask, only=wanted, taken=taken, on_batch=on_batch)
        result = tuple(sorted([c for c in cues if c.id not in replaced] + new,
                              key=lambda c: (c.start_ms, c.end_ms)))
        try:
            check_track(result)
        except TrackError as err:
            raise EditError(f"the {track} track would break: {err}") from None
        tracks = Tracks(source, {**ep.tracks.translations, track: result})
        return replace(ep, tracks=tracks, taken=taken, redo=[],
                       undo=[*ep.undo, (ep.tracks, ep.glossary_adds)][-UNDO_STEPS:])
```

  with

```python
    def retranslate(self, ep: Episode, track: str, *, ids: Sequence[str] | None,
                    model: str | None = None, allow_cloud: bool = False,
                    on_batch: Callable[[int, int], None] | None = None) -> Episode:
        """`ids=None`: every stale or untranslated source cue, never replacing an edited
        translation; else those source cues, whatever their translation. One undo step; `ep`
        itself when there's nothing to translate (no model is asked to translate; with none
        named, the route's servers are asked which models they serve). Blocks on the network.
        Raises EditError (a track in conflict, an unknown track or cue), EngineError (no usable
        model, a cloud model this call doesn't allow, the server down or refusing: `.hint` names
        the fix), TranslationFailed, or GlossaryError (a glossary beside the video vid2sub can't
        read); nothing changes then."""
        self._check_open(ep)
        if track not in naming.TRACKS:  # it comes from the browser: never echoed unchecked
            raise EditError("there's no such track")
        _editable(ep, track)
        if track not in ep.tracks.translations:
            raise EditError(f"there is no {track} track")
        if ids is not None and not ids:
            return ep
        source, cues = ep.tracks.source, ep.tracks.translations[track]
        lang = _lang(ep.source_key)
        name = self._translator(lang, model, allow_cloud)
        entry = self.config.models[name]
        glossary = glossary_with(read_glossary(ep.video), ep.glossary_adds)
        everything = ids is None and setup_changed(track_setup(ep, track), glossary.sha(),
                                                   entry.model)
        wanted, replaced = retranslation(source, cues, ids, everything=everything)
        if not wanted:
            return ep
        policy = RunPolicy(allow_cloud)
        check_allowed(name, entry, self.config, policy)
        ask = make_ask(name, entry, self.config, policy, self.keys)
        taken = set(ep.taken)
        new = translate_cues(source, source_lang=lang, target_track=track,
                             glossary=glossary, ask=ask, only=wanted, taken=taken,
                             on_batch=on_batch)
        result = tuple(sorted([c for c in cues if c.id not in replaced] + new,
                              key=lambda c: (c.start_ms, c.end_ms)))
        try:
            check_track(result)
        except TrackError as err:
            raise EditError(f"the {track} track would break: {err}") from None
        tracks = Tracks(source, {**ep.tracks.translations, track: result})
        made_with = ({**ep.made_with, track: (glossary.sha(), entry.model)} if everything
                     else ep.made_with)
        return replace(ep, tracks=tracks, taken=taken, made_with=made_with, redo=[],
                       undo=[*ep.undo, (ep.tracks, ep.glossary_adds)][-UNDO_STEPS:])
```

  In `save`, replace

```python
                        taken=ep.taken | cue_ids(side), glossary_adds=adds, glossary=glossary)
```

  with

```python
                        taken=ep.taken | cue_ids(side), glossary_adds=adds, glossary=glossary,
                        made_with={})
```

  In `_versions`, in the `_editor_body(…)` call, add an argument after `inputs=…`:

```python
,
                            setup=track_setup(ep, track)
```

  Replace the function `_editor_body`

```python
def _editor_body(head: dict, cues: Sequence[Cue], *, is_source: bool, created_at: str,
                 inputs: dict[str, str]) -> dict:
    """The head's language, script and glossary hash; its model too, since the cues the person
    didn't touch are still that model's, and M1 reads a changed model as every cue stale."""
    payload = head.get("payload", {})
    return cues_body(cues, language=payload["language"], script=payload.get("script"),
                     engine="editor", model=head.get("model"), version=f"editor@{__version__}",
                     created_at=created_at, inputs=inputs,
                     meta={"role": "source" if is_source else "translation"},
                     glossary_sha=payload.get("glossary_sha"))


def _project(
```

  with

```python
def _editor_body(head: dict, cues: Sequence[Cue], *, is_source: bool, created_at: str,
                 inputs: dict[str, str], setup: tuple[str, str | None]) -> dict:
    """The head's language and script, and the glossary hash and model the cues were made with
    (`track_setup`): the head's, or a retranslation's that redid them all; M1 reads a changed
    glossary or model as every cue stale."""
    payload = head.get("payload", {})
    glossary_sha, model = setup
    return cues_body(cues, language=payload["language"], script=payload.get("script"),
                     engine="editor", model=model, version=f"editor@{__version__}",
                     created_at=created_at, inputs=inputs,
                     meta={"role": "source" if is_source else "translation"},
                     glossary_sha=glossary_sha or None)


def _project(
```

  In `_with_track`, replace

```python
                   words=words, undo=[], redo=[], taken=ep.taken | cue_ids(side))
```

  with

```python
                   words=words, undo=[], redo=[], taken=ep.taken | cue_ids(side),
                   made_with={k: v for k, v in ep.made_with.items() if k != track})
```

  Replace the start of `retranslation`, down to its `wanted = {…}` set

```python
def retranslation(source: Sequence[Cue], cues: Sequence[Cue], ids: Sequence[str] | None
                  ) -> tuple[list[str], set[str]]:
    """The source cue ids to translate, in order, and the translation cue ids they replace.

    Whole groups, so the new cues never overlap the kept ones: a replaced translation brings
    every source cue it covers, and a translation that covers a cue being translated, or whose
    time overlaps a run of them, is replaced too. With `ids=None` an edited translation is never
    replaced; the cues it would have brought in are left out instead."""
    order = {c.id: k for k, c in enumerate(source)}
    by_id = {c.id: c for c in source}
    if ids is None:
        stale = stale_ids(cues, by_id)
        wanted = {i for c in cues if c.id in stale and "edited" not in c.flags
                  for i in c.src or () if i in by_id}
```

  with

```python
def retranslation(source: Sequence[Cue], cues: Sequence[Cue], ids: Sequence[str] | None, *,
                  everything: bool = False) -> tuple[list[str], set[str]]:
    """The source cue ids to translate, in order, and the translation cue ids they replace.

    Whole groups, so the new cues never overlap the kept ones: a replaced translation brings
    every source cue it covers, and a translation that covers a cue being translated, or whose
    time overlaps a run of them, is replaced too. With `ids=None` an edited translation is never
    replaced; the cues it would have brought in are left out instead. `everything`: the track
    was made with another glossary or model, so with `ids=None` every cue of it is stale."""
    order = {c.id: k for k, c in enumerate(source)}
    by_id = {c.id: c for c in source}
    if ids is None:
        stale = {c.id for c in cues} if everything else stale_ids(cues, by_id)
        wanted = {i for c in cues if c.id in stale and "edited" not in c.flags
                  for i in c.src or () if i in by_id}
```

  Replace the start of `track_setup`, down to its `body = …` line

```python
def track_setup(ep: Episode, track: str) -> tuple[str, str | None]:
    """The glossary hash ("" for none) and the model the track's cues were made with."""
    body = ep.sidecar.renditions()[ep.heads[track]].body
```

  with

```python
def track_setup(ep: Episode, track: str) -> tuple[str, str | None]:
    """The glossary hash ("" for none) and the model the track's cues were made with: those of a
    retranslation that redid every unedited cue, while none of the cues it replaced is back (an
    undo), else its head's."""
    made = ep.made_with.get(track)
    if made is not None:
        before = {c.id for c in ep.base.translations.get(track, ())}
        if not any(c.id in before for c in ep.tracks.translations.get(track, ())
                   if "edited" not in c.flags):
            return made
    body = ep.sidecar.renditions()[ep.heads[track]].body
```

- [ ] **Step 9: Run the checks; they pass.** `uv run pytest tests/test_backend_retranslate.py -q`
  first (`20 passed`), then the leg checks, then `make check`. **Leg checks:** in
  `retranslate`, pass `None` for `glossary.sha()` in the `setup_changed(...)` call: the
  glossary test and the save test fail, `2 failed, 18 passed`; restore it; then pass `None` for
  `entry.model`: the two model tests fail, `2 failed, 18 passed`; restore it. `make check`.
  Expected: `715 passed, 2 skipped, 4 deselected` twice, `All checks passed!` and `no leaks
  found`.
- [ ] **Step 10: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(web): 🤖 Retranslate stale redoes every unedited cue when the glossary or the model changed, as spec §13.4 says

retranslate(ids=None) takes spec §13.4's other two legs, as M1 decides
them (pipeline._translate_targets): when the track's glossary hash or
model (backend.track_setup) isn't the one this call uses, the glossary
beside the video with the terms waiting for Save and the model named or
picked by the route, every cue is stale (retranslation(everything=True));
edited cues are still kept. So the model is chosen first; with none named
the route's servers are asked which models they serve even when nothing
turns out stale. Once a retranslation has redone every unedited cue, the
episode's made_with remembers the pair it used, and track_setup returns
it while none of the replaced cues is back (an undo brings them back):
the view stops flagging the track, and Save records that glossary hash
and model in the editor version, so reopening shows nothing stale. Save
and a pick clear made_with.

The new tests failed first with: assert [] == [['ca0000000'],
['ca0000002']] (glossary), assert [] == [['ca0000000', …]] (model, and the
named model), and assert [True, True, True] == [False, False, False]
(after redoing everything). With the glossary leg left out, the glossary
and save tests fail; with the model leg left out, the two model tests
fail (2 failed, 18 passed each).

Docs read: none beyond the code (pipeline._translate_targets lines
645-647).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 7
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/web/backend.py tests/test_backend_retranslate.py`, `git commit -F
  .git/COMMIT_MSG`, then `git log -1 --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 11: Review, look forward, close.** The Tier 2 review from `$(cat .git/TASK_BASE)`
  (`AGENTS.md`, *Reviews*); the forward review over Tasks 17 and 23 (Task 17's `retranslate`
  input runs `LocalBackend.retranslate` off the event loop for the current cue, the selection
  or `ids=None` ("Retranslate stale"), holds other edits to the episode until it returns, sends
  each `on_batch` as progress through the session's loop, takes `allow_cloud` from a control
  that starts unticked every time (spec §7.2), and shows `EditError`, `EngineError` (with its
  `hint`), `TranslationFailed` and `GlossaryError` as notices; with no model named it asks the
  route's servers which models they serve before planning, so even "nothing stale" takes a
  moment; after a glossary or model change "Retranslate stale" redoes every unedited cue, which
  the view's `all_stale` explains; Task 23's Step 5 runs it on a real episode); the docs this
  task made untrue (none expected). Then the close, its own commit,
  holding this plan with this task's boxes ticked and **Now** set to `Task 8: The web
  dependencies, the guards and the CSP, open.`; S30 stays `planned` (its proof is Task 17's
  Playwright test and the exit test). The message, in `.git/CLOSE_MSG`:

```text
docs(plan): 🤖 close Task 7: The editor backend: retranslate

Drift: none
Rulings: none
Phase-end: none
Forward: none
Tier: 2
Rounds: none
Findings: none

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 7
Co-Authored-By: <the model's own line>
```

  `git add docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md`, `git commit -F
  .git/CLOSE_MSG`.

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
  what Shiny and shinyreact need: spec §6.3 leaves style rules to that, verified in M2 (§29), so
  it would be a one-line change to `CSP` and to `SPEC_CSP` in the test, recorded in §29, not a
  spec change. Any change to `script-src`, or `'unsafe-eval'`, would be Dan's (the fifth stop).

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

# Spec §6.3, verbatim. One constant, so a style rule Shiny turns out to need (§6.3 leaves them to
# §29) is a one-line change; script-src never changes without Dan. Never 'unsafe-eval'.
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
  `SIGN_IN_AGAIN` instead of reconnecting when the websocket is refused, Review Focus 5: the
  refusal comes before accept, so the browser sees an HTTP 403 (close code 1006), never 1008;
  Task 12's `page` fixture signs in through `/auth#t=<token>`). The docs this task made untrue:
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
- Create: `src/vid2sub/web/runtime.py`, `src/vid2sub/web/app.py`, `src/vid2sub/commands/serve.py`
- Modify: `src/vid2sub/cli.py` (register `serve`), `src/vid2sub/web/__init__.py` (`WWW`, round 11c)
- Test: `tests/test_web_app.py`, `tests/test_cli_serve.py`

**Interfaces:**
- Consumes: Task 8's `guards.HostGuard`, `guards.WriteGuard`; Task 9's `auth.routes`,
  `auth.TokenGuard`, `auth.new_token`, `auth.auth_url`, `auth.write_redirect`,
  `auth.SIGN_IN_AGAIN`; Task 10's `media.MediaTokens`, `media.route`; Task 5's `LocalBackend`;
  Task 4's `jobs.Queue`; Task 3's `cache.from_config`; `commands._common` (`CommandError`,
  `Output`, `fail`, `load`); `engines.clients.KeyRing`, `quiet_libraries`; `media.tools.Tools`.
- Produces:
  - `runtime.Runtime`, a frozen dataclass: `backend: LocalBackend`, `queue: Queue`,
    `media: MediaTokens`, `config: Config`, `keys: KeyRing`. `runtime.configure(rt: Runtime | None)
    -> None` (None forgets it, for tests); `runtime.current() -> Runtime` (RuntimeError before
    `configure`); `runtime.build(config: Config, *, tools: Tools | None = None, keys: KeyRing |
    None = None, cache: Cache | None = None) -> Runtime` (defaults: `Tools.find()`, `KeyRing()`,
    `cache.from_config(config)`). The queue's runner, `runtime._no_jobs`, fails every job without
    running anything: Task 19 gives the queue the pipeline.
  - `app.create_app(rt: Runtime, *, token: str, port: int, shiny_app: ASGIApp) -> ASGIApp`: a
    FastAPI app with `/docs`, `/redoc` and `/openapi.json` off; `GET /healthz` answers
    `{"ok": true}` and nothing more; Task 9's `/auth` routes and Task 10's `/media/{token}` come
    before `shiny_app`, mounted at "/" last; wrapped as `HostGuard(WriteGuard(TokenGuard(api),
    HOSTS), HOSTS)` with `app.HOSTS = frozenset({"127.0.0.1"})`; its lifespan closes the job
    queue at shutdown, off the event loop. A Starlette mount passes no lifespan events on, so
    shutdown work for the Shiny side goes in this lifespan.
  - `vid2sub.web.WWW`: `src/vid2sub/web/www/`, the built frontend's folder.
  - `vid2sub serve [--port N] [--no-browser] [--config PATH]`: exits 69 with "build the frontend
    first" when `WWW / "ui.js"` is missing (before reading vid2sub.toml or binding), and 69 for a
    port it can't have; binds 127.0.0.1 only, on `--port`, else `[server] port` (8765), 0 taking
    any free port; prints the link `auth.auth_url(port, token)` only to a terminal, and otherwise
    the redirect file's path; opens the browser on the redirect file (`webbrowser`, from a thread)
    unless `--no-browser` or `[server] open_browser = false`; Ctrl-C exits 0 and SIGTERM 143, and
    the redirect file's folder is removed on every exit; shutdown waits at most `serve.GRACE` (3)
    seconds for open responses; uvicorn's access log off, proxy headers not believed.
  - `serve.bind(port: int) -> socket.socket`; `serve.serve(app: ASGIApp, sock: socket.socket, *,
    token: str, open_browser: bool, out: Output) -> int`; `serve.uvicorn_config(app) ->
    uvicorn.Config`; `serve.shiny_app() -> ASGIApp` (imports `vid2sub.web.server.app`, which
    Task 12 creates: until then `serve` stops at the frontend check).
- Behaviour later tasks rely on: a harness whose stdout isn't a terminal reads the link from the
  redirect file whose path `serve` prints on the line after "Open the editor by opening this
  file in a browser" (Task 12's e2e conftest does).

Round 11c is the independent Tier 1 review this listing's build had: its two Important findings
and the reading for Dan, fixed with tests that failed first. Build it as a round, as written, so
the commits match the listing.

- [ ] **Step 0: Record the base:** `git rev-parse HEAD > .git/TASK_BASE`.

#### Round 11a: the runtime and the app shell

- [ ] **Step 1: Write the failing test,** `tests/test_web_app.py`:

```python
"""The app shell: `/healthz`, `/auth` and `/media/` come before the Shiny app mounted at "/", the
whole engine sits inside HostGuard, WriteGuard and TokenGuard, FastAPI's own pages are off, and
stopping the engine closes the job queue (spec §19.1, §6.1, §6.2, §17.1; S23, S24, S25)."""

import json

import pytest
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route, WebSocketRoute
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from vid2sub import cache as caching
from vid2sub.cache import Cache
from vid2sub.config import Config
from vid2sub.engines.clients import KeyRing
from vid2sub.jobs import Queue
from vid2sub.media.tools import Tools
from vid2sub.web import auth, runtime
from vid2sub.web.app import create_app
from vid2sub.web.backend import LocalBackend
from vid2sub.web.guards import CSP
from vid2sub.web.media import MediaTokens

PORT = 8765
TOKEN = "t" * 43  # as long as a real token, and plainly not one (the leak scan agrees)
BASE = f"http://127.0.0.1:{PORT}"
# In full: the test client joins a bare path onto ws://testserver, which gets no cookie.
WS = f"ws://127.0.0.1:{PORT}/websocket/"
JSON = {"Content-Type": "application/json"}
PAGE = {"Origin": BASE, "Sec-Fetch-Site": "same-origin"}  # what the engine's own page sends


async def _page(request):
    return PlainTextResponse("shiny")


async def _echo(websocket):
    await websocket.accept()
    await websocket.send_text("hello")
    await websocket.close()


def _shiny() -> Starlette:
    """Stands in for the Shiny app: it answers every path, as an app mounted at "/" does."""
    return Starlette(routes=[WebSocketRoute("/websocket/", _echo), Route("/{rest:path}", _page)])


@pytest.fixture
def rt(tmp_path):
    made = runtime.build(Config(), tools=Tools(None, None, None), keys=KeyRing(environ={}),
                         cache=Cache(tmp_path / "cache", max_bytes=0))
    yield made
    made.queue.close()


@pytest.fixture
def client(rt):
    with TestClient(create_app(rt, token=TOKEN, port=PORT, shiny_app=_shiny()),
                    base_url=BASE) as c:
        yield c


def _sign_in(client):
    r = client.post("/auth", content=json.dumps({"token": TOKEN}), headers={**JSON, **PAGE})
    assert r.status_code == 204
    return r


def test_healthz_answers_ok_and_nothing_more_without_the_cookie(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    assert r.headers["content-security-policy"] == CSP


@pytest.mark.parametrize("path", ["/", "/editor", "/media/x", "/docs", "/openapi.json",
                                  "/healthz/", "/auth/x", "/lib/shiny-1.8.0/shiny.js"])
def test_every_other_path_needs_the_launch_cookie(client, path):
    r = client.get(path)
    assert r.status_code == 401
    assert r.text == auth.SIGN_IN_AGAIN
    expected = "sandbox" if path.startswith("/media/") else CSP  # MEDIA_HEADERS there
    assert r.headers["content-security-policy"] == expected


def test_the_websocket_needs_the_launch_cookie(client):
    with pytest.raises(WebSocketDisconnect) as refused, client.websocket_connect(
            WS, headers={"Origin": BASE}):
        pass
    assert refused.value.code == 1008


def test_a_signed_in_browser_reaches_the_shiny_app_and_its_websocket(client):
    _sign_in(client)
    assert client.get("/").text == "shiny"
    assert client.get("/editor").text == "shiny"
    with client.websocket_connect(WS, headers={"Origin": BASE}) as ws:
        assert ws.receive_text() == "hello"


@pytest.mark.parametrize("path", ["/docs", "/docs/oauth2-redirect", "/redoc", "/openapi.json"])
def test_fastapis_own_pages_are_off(client, path):
    # Swagger UI and ReDoc load scripts from a CDN, which the CSP and spec §6.3 forbid.
    _sign_in(client)
    assert client.get(path).text == "shiny"


def test_the_shells_routes_come_before_the_shiny_app(client, rt, tmp_path):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"0123456789")
    token = rt.media.issue(clip, owner="e1")
    _sign_in(client)
    r = client.get(f"/media/{token}")
    assert r.status_code == 200 and r.content == b"0123456789"
    assert r.headers["content-security-policy"] == "sandbox"
    assert client.get("/healthz").json() == {"ok": True}
    assert "<script src=\"/auth.js\"></script>" in client.get("/auth").text
    assert client.get("/media/unknown").status_code == 404  # the route, not the Shiny app


def test_the_guards_wrap_the_whole_engine(client):
    # HostGuard: a name the engine isn't called by, as DNS rebinding sends it.
    assert client.get("/healthz", headers={"Host": "evil.example"}).status_code == 400
    # WriteGuard: a sign-in sent from a page on another local port, and one that isn't JSON.
    other = client.post("/auth", content=json.dumps({"token": TOKEN}),
                        headers={**JSON, "Origin": "http://127.0.0.1:9999",
                                 "Sec-Fetch-Site": "same-site"})
    assert other.status_code == 403 and "set-cookie" not in other.headers
    charset = client.post("/auth", content=json.dumps({"token": TOKEN}),
                          headers={"Content-Type": "application/json; charset=utf-8", **PAGE})
    assert charset.status_code == 415
    _sign_in(client)
    # HostGuard: the cookie doesn't let another origin's page open the websocket.
    with pytest.raises(WebSocketDisconnect) as refused, client.websocket_connect(
            WS, headers={"Origin": "http://127.0.0.1:9999"}):
        pass
    assert refused.value.code == 1008


def test_stopping_the_engine_closes_the_job_queue(rt):
    with TestClient(create_app(rt, token=TOKEN, port=PORT, shiny_app=_shiny()), base_url=BASE):
        rt.queue.jobs()  # open while the engine runs
    with pytest.raises(RuntimeError, match="closed"):
        rt.queue.submit(["/videos/a.mkv"])


# ---- the runtime ------------------------------------------------------------------------------


def test_current_needs_configure_first():
    runtime.configure(None)
    with pytest.raises(RuntimeError, match="configure"):
        runtime.current()


def test_configure_sets_what_current_returns(rt):
    runtime.configure(rt)
    try:
        assert runtime.current() is rt
    finally:
        runtime.configure(None)


def test_build_puts_one_backend_queue_and_token_store_together(tmp_path):
    config, keys = Config(), KeyRing(environ={})
    cache = Cache(tmp_path / "cache", max_bytes=0)
    rt = runtime.build(config, tools=Tools(None, None, None), keys=keys, cache=cache)
    try:
        assert isinstance(rt.backend, LocalBackend)
        assert (rt.backend.config, rt.backend.keys, rt.backend.cache) == (config, keys, cache)
        assert isinstance(rt.queue, Queue) and isinstance(rt.media, MediaTokens)
        assert (rt.config, rt.keys) == (config, keys)
    finally:
        rt.queue.close()


def test_the_cache_follows_cache_max_gb_from_vid2sub_toml(tmp_path, monkeypatch):
    monkeypatch.setattr(caching, "default_root", lambda: tmp_path / "cache")
    config = Config.model_validate({"defaults": {"cache_max_gb": 3}})
    rt = runtime.build(config, tools=Tools(None, None, None), keys=KeyRing(environ={}))
    try:
        assert rt.backend.cache.root == tmp_path / "cache"
        assert rt.backend.cache.max_bytes == 3 * caching.GB
    finally:
        rt.queue.close()
```

- [ ] **Step 2: Run it; watch it fail.** `uv run pytest tests/test_web_app.py -q`. Expected:
  `E   ImportError: cannot import name 'runtime' from 'vid2sub.web' (…/src/vid2sub/web/__init__.py)`,
  then `1 error in 0.34s`.
- [ ] **Step 3: Write the code,** `src/vid2sub/web/runtime.py`:

```python
"""The engine's running parts, made once per launch by `vid2sub serve` and read by the Shiny
server (spec §19.1).

As recordings' runtime does: Shiny's app object is made when its module is imported, and its
server function runs once per browser session, so the server finds the backend, the job queue
and the media tokens here (`current()`), and `serve` calls `configure()` before it imports the
Shiny app. There is one of each per launch: the backend holds the open episodes, the queue holds
the jobs, which belong to the engine rather than a tab (spec §17.1), and the media tokens die
with the engine (the Phase 2 plan's Decision 1). Until the Jobs page gives the queue the
pipeline (S36), a job that somehow reaches it fails without running anything.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from vid2sub import cache as caching
from vid2sub.cache import Cache
from vid2sub.config import Config
from vid2sub.engines.clients import KeyRing
from vid2sub.jobs import Queue
from vid2sub.media.tools import Tools
from vid2sub.pipeline import Event, InputResult
from vid2sub.web.backend import LocalBackend
from vid2sub.web.media import MediaTokens


@dataclass(frozen=True)
class Runtime:
    backend: LocalBackend
    queue: Queue
    media: MediaTokens
    config: Config
    keys: KeyRing


_current: Runtime | None = None


def configure(rt: Runtime | None) -> None:
    """Make `rt` the launch's runtime; None forgets it (tests)."""
    global _current
    _current = rt


def current() -> Runtime:
    if _current is None:
        raise RuntimeError("vid2sub.web.runtime.configure() was not called")
    return _current


def build(config: Config, *, tools: Tools | None = None, keys: KeyRing | None = None,
          cache: Cache | None = None) -> Runtime:
    """One launch's parts: the tools found on PATH, the keys from the environment, and the cache
    that `[defaults] cache_max_gb` caps, unless the caller gives its own."""
    tools = tools if tools is not None else Tools.find()
    keys = keys if keys is not None else KeyRing()
    cache = cache if cache is not None else caching.from_config(config)
    return Runtime(backend=LocalBackend(config, tools, keys, cache), queue=Queue(_no_jobs),
                   media=MediaTokens(), config=config, keys=keys)


def _no_jobs(source: str, events: Event, cancelled: Callable[[], bool]) -> InputResult:
    raise RuntimeError("this engine has no job runner")
```

  and `src/vid2sub/web/app.py`:

```python
"""The app shell: `/auth`, `/healthz` and `/media/{token}`, with the Shiny app mounted at "/"
last, and the whole engine wrapped in the guards (spec §19.1, §6.1, §6.2).

As recordings' create_app does (packages/ui/src/recordings_ui/app.py at 8deb039): a FastAPI app
whose own routes win because the Shiny mount comes after them, and guards around everything,
the Shiny app and its websocket included. vid2sub adds the launch token, so the order is
`HostGuard(WriteGuard(TokenGuard(api)))`: a wrong name is refused before anything else, every
response carries the security headers, and only then is the cookie asked for. FastAPI's own
pages (`/docs`, `/redoc`, `/openapi.json`) are off: they load scripts from a CDN, and the engine
makes no third-party requests (§6.3). `/healthz` says only `{"ok": true}` (§6.1). The Shiny app
is passed in, made by its own module once `runtime.configure()` has run. Stopping the engine
closes the job queue, which cancels what waits and asks the running job to stop (§17.1).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from starlette.types import ASGIApp

from vid2sub.web import auth, media
from vid2sub.web.guards import LOCAL_HOSTS, HostGuard, WriteGuard
from vid2sub.web.runtime import Runtime

# The built frontend (`ui.js`, `ui.css` and the fonts), which `vid2sub serve` needs (spec §18).
WWW = Path(__file__).parent / "www"


def create_app(rt: Runtime, *, token: str, port: int, shiny_app: ASGIApp) -> ASGIApp:
    @asynccontextmanager
    async def lifespan(_api: FastAPI) -> AsyncIterator[None]:
        yield
        await asyncio.to_thread(rt.queue.close)  # bounded (5 s), and off the event loop

    api = FastAPI(title="vid2sub", docs_url=None, redoc_url=None, openapi_url=None,
                  lifespan=lifespan)

    @api.get("/healthz")
    def healthz() -> dict:
        return {"ok": True}

    api.router.routes.extend([*auth.routes(token, port), media.route(rt.media)])
    api.mount("/", shiny_app)  # last, so the routes above win
    return HostGuard(WriteGuard(auth.TokenGuard(api, token=token, port=port), LOCAL_HOSTS),
                     LOCAL_HOSTS)
```

- [ ] **Step 4: Run the checks; they pass.** `uv run pytest tests/test_web_app.py -q`. Expected:
  `22 passed`. Then `make check`. Expected: the suite's line, twice,
  `895 passed, 2 skipped, 4 deselected` with nothing failed (873 before this task when this
  listing was built), `All checks passed!` and `no leaks found`. Line length, which ruff's
  default rules leave out: `uv run python -c "import sys; [print(f, i) for f in sys.argv[1:] for i, l in enumerate(open(f, encoding='utf-8'), 1) if len(l.rstrip()) > 100]" src/vid2sub/web/runtime.py src/vid2sub/web/app.py
  tests/test_web_app.py` prints nothing.

- [ ] **Step 5: Each guard fails its tests without its fix.** `git add src/vid2sub/web/runtime.py src/vid2sub/web/app.py tests/test_web_app.py`. Then,
  for each row, make the change in `src/vid2sub/web/app.py`, run `uv run pytest tests/test_web_app.py -q`, see it fail, and
  restore with `git checkout -- <the file>`. The last column is what this listing's build saw.

| Guard | Change | To | Failed |
|---|---|---|---|
| TokenGuard | `HostGuard(WriteGuard(auth.TokenGuard(api, token=token, port=port), LOCAL_HOSTS), LOCAL_HOSTS)` | `HostGuard(WriteGuard(api, LOCAL_HOSTS), LOCAL_HOSTS)` | 9 |
| HostGuard | `the same` | `WriteGuard(auth.TokenGuard(api, token=token, port=port), LOCAL_HOSTS)` | 1 |
| WriteGuard | `the same` | `HostGuard(auth.TokenGuard(api, token=token, port=port), LOCAL_HOSTS)` | 11 |
| FastAPI's pages off | `docs_url=None, redoc_url=None, openapi_url=None,` | `(removed)` | 4 |
| routes before the mount | `the `extend` line, then `api.mount(...)`` | ``api.mount(...)` first` | 7 |
| the queue closed | `await asyncio.to_thread(rt.queue.close)  # …` | `pass` | 1 |
| /healthz says only ok | `return {"ok": True}` | `return {"ok": True, "port": port}` | 2 |

- [ ] **Step 6: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(web): 🤖 the app shell serves /auth, /healthz and /media/ ahead of the Shiny app, inside HostGuard, WriteGuard and TokenGuard

src/vid2sub/web/runtime.py holds one launch's parts (spec §19.1): the LocalBackend, the job
queue, the media tokens, the config and the keys, made by build() and set by configure() before
the Shiny app is imported, as recordings' runtime is. Until the Jobs page gives the queue the
pipeline (S36), a job that reaches it fails without running anything. src/vid2sub/web/app.py's
create_app() follows recordings' create_app (packages/ui/src/recordings_ui/app.py at 8deb039): a
FastAPI app whose routes (/healthz, Task 9's /auth routes, Task 10's /media/{token}) come before
the Shiny app mounted at "/", wrapped as HostGuard(WriteGuard(TokenGuard(api))). /healthz says
only {"ok": true} (spec §6.1); FastAPI's /docs, /redoc and /openapi.json are off, since Swagger UI
and ReDoc load scripts from a CDN (§6.3); stopping the engine closes the job queue, off the event
loop (§17.1). app.WWW names the built frontend's folder for serve.

The new test failed first with: ImportError: cannot import name 'runtime' from 'vid2sub.web'.
Each guard was then reverted in turn and its tests failed: TokenGuard left out (9 failed),
HostGuard left out (1), WriteGuard left out (11), FastAPI's pages back on (4), the Shiny app
mounted before the routes (7), the queue left open at shutdown (1), /healthz saying more (2).

Docs read: FastAPI's applications.py docstrings for docs_url, redoc_url, openapi_url (None turns
each off) and lifespan, and its routes parameter (deprecated in FastAPI, so the Starlette routes
go on api.router.routes); Starlette's routing page (Mount, the path convertor) and TestClient
(lifespan runs inside the with block).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 11
Co-Authored-By: <the model's own line>
```

  `git commit -F .git/COMMIT_MSG` (the three files are staged from the step before), then
  `git log -1 --format='%(trailers)'` shows `Plan:`.

#### Round 11b: `vid2sub serve`

- [ ] **Step 7: Write the failing test,** `tests/test_cli_serve.py`. It runs the real CLI in a
  child process, with a stand-in Shiny app, since `vid2sub.web.server` is Task 12's:

```python
"""`vid2sub serve` binds 127.0.0.1 only, prints the link that signs a browser in, opens the
browser on the redirect file rather than the token, and removes that file's folder when it stops;
the token reaches no log and no command line (spec §6.1, §6.8, §18.1; S23).

The real CLI runs in a child process, as recordings' SIGTERM test runs its server, with a stand-in
for the Shiny app (the frontend and the Shiny server aren't needed to test the shell). Its
TMPDIR is the test's own, so the redirect file's folder can be watched. Signals and an executable
BROWSER script are POSIX: Windows gets its own run in Phase 3.
"""

import json
import os
import re
import signal
import socket
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from vid2sub import exitcodes
from vid2sub.cli import main
from vid2sub.commands import serve
from vid2sub.web import auth

POSIX = pytest.mark.skipif(os.name == "nt", reason="POSIX signals and an executable script")
LINK = re.compile(r"http://127\.0\.0\.1:(\d+)/auth#t=([A-Za-z0-9_-]{43})")
# The child: the real `vid2sub serve`, with `www/` pointing at a folder holding a ui.js, and a
# stand-in for the Shiny app.
CHILD = r"""
import sys
from pathlib import Path

from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from vid2sub.cli import main
from vid2sub.commands import serve


async def page(request):
    return PlainTextResponse("shiny")


serve.WWW = Path(sys.argv[1])
serve.shiny_app = lambda: Starlette(routes=[Route("/{rest:path}", page)])
raise SystemExit(main(sys.argv[2:]))
"""


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@dataclass
class Serving:
    proc: subprocess.Popen
    log: Path
    tmp: Path  # the child's TMPDIR
    port: int
    token: str

    def get(self, path: str, data: bytes | None = None, headers: dict | None = None):
        request = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data,
                                         headers=headers or {})
        try:
            with urllib.request.urlopen(request, timeout=10) as r:
                return r.status, dict(r.headers), r.read()
        except urllib.error.HTTPError as err:
            return err.code, dict(err.headers), err.read()

    def stop(self, sig: int = signal.SIGINT) -> int:
        if os.name == "nt":
            self.proc.terminate()
        else:
            self.proc.send_signal(sig)
        try:
            return self.proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            raise

    def folders(self) -> list[Path]:
        return sorted(self.tmp.glob("vid2sub-*"))


@pytest.fixture
def start(tmp_path):
    started: list[Serving] = []

    def run(*args: str, toml: str = "", env: dict | None = None) -> Serving:
        www = tmp_path / "www"
        www.mkdir(exist_ok=True)
        (www / "ui.js").write_text("// built\n", encoding="utf-8")
        scratch = tmp_path / f"tmp{len(started)}"
        scratch.mkdir()
        config = tmp_path / f"vid2sub{len(started)}.toml"
        config.write_text(toml, encoding="utf-8")
        log = tmp_path / f"serve{len(started)}.log"
        child_env = {k: v for k, v in os.environ.items() if k != "BROWSER"}
        child_env.update({"TMPDIR": str(scratch), **(env or {})})
        with log.open("wb") as out:
            proc = subprocess.Popen(
                [sys.executable, "-c", CHILD, str(www), "serve", "--config", str(config), *args],
                env=child_env, stdout=out, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + 60
        while not (found := LINK.search(log.read_text(encoding="utf-8", errors="replace"))):
            assert proc.poll() is None, log.read_text(encoding="utf-8", errors="replace")
            assert time.monotonic() < deadline, "no link printed in 60 s"
            time.sleep(0.1)
        serving = Serving(proc, log, scratch, int(found.group(1)), found.group(2))
        started.append(serving)
        while True:  # the socket listens before the link is printed; wait for the app too
            try:
                if serving.get("/healthz")[0] == 200:
                    break
            except OSError:
                pass
            assert time.monotonic() < deadline, "healthz never answered"
            time.sleep(0.1)
        return serving

    yield run
    for serving in started:
        if serving.proc.poll() is None:
            serving.proc.kill()
            serving.proc.wait()


def _browser(tmp_path: Path) -> tuple[Path, Path]:
    """An executable BROWSER that records the command line it was run with, as `ps` shows it."""
    script = tmp_path / "browser"
    record = tmp_path / "browser.json"
    script.write_text(f"#!{sys.executable}\nimport json, sys\n"
                      f"open({str(record)!r}, 'w').write(json.dumps(sys.argv))\n",
                      encoding="utf-8")
    script.chmod(0o755)
    return script, record


def _sign_in(serving: Serving, token: str) -> tuple[int, dict, bytes]:
    return serving.get("/auth", json.dumps({"token": token}).encode(),
                       {"Content-Type": "application/json"})


def test_serve_refuses_without_the_built_frontend(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(serve, "WWW", tmp_path / "www")  # no ui.js
    broken = tmp_path / "vid2sub.toml"
    broken.write_text("[server\n", encoding="utf-8")  # checked after the frontend
    assert main(["serve", "--config", str(broken)]) == exitcodes.UNAVAILABLE
    assert "build the frontend first" in capsys.readouterr().err


def test_a_port_in_use_exits_69_and_says_how_to_pick_another(tmp_path, monkeypatch, capsys):
    (tmp_path / "www").mkdir()
    (tmp_path / "www" / "ui.js").write_text("// built\n", encoding="utf-8")
    monkeypatch.setattr(serve, "WWW", tmp_path / "www")
    config = tmp_path / "vid2sub.toml"
    config.write_text("", encoding="utf-8")
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen()
        port = taken.getsockname()[1]
        code = main(["serve", "--port", str(port), "--no-browser", "--config", str(config)])
    assert code == exitcodes.UNAVAILABLE
    err = capsys.readouterr().err
    assert f"port {port}" in err and "--port" in err


def test_bind_listens_on_127_0_0_1_only():
    sock = serve.bind(0)
    try:
        assert sock.family == socket.AF_INET
        assert sock.getsockname()[0] == "127.0.0.1"
        with socket.create_connection(sock.getsockname(), timeout=5):
            pass  # listening already: a browser opened now waits rather than being refused
    finally:
        sock.close()


def test_uvicorn_keeps_no_access_log_and_believes_no_proxy_headers():
    config = serve.uvicorn_config(lambda scope, receive, send: None)
    assert config.access_log is False
    assert config.proxy_headers is False
    assert config.server_header is False


@pytest.mark.parametrize("value", ["-1", "65536", "http", "80.5"])
def test_port_must_be_a_port_number(value, capsys):
    with pytest.raises(SystemExit) as exited:
        main(["serve", "--port", value])
    assert exited.value.code == exitcodes.USAGE
    assert "a port is a number from 0 to 65535" in capsys.readouterr().err


def test_the_printed_link_signs_a_browser_in_on_the_port_given(start):
    configured, given = _free_port(), _free_port()
    serving = start("--port", str(given), "--no-browser", toml=f"[server]\nport = {configured}\n")
    assert serving.port == given  # --port wins over vid2sub.toml
    assert serving.get("/healthz")[2] == b'{"ok":true}'
    assert serving.get("/")[0] == 401
    assert _sign_in(serving, "t" * 43)[0] == 403
    status, headers, _ = _sign_in(serving, serving.token)
    assert status == 204
    cookie = headers["set-cookie"].split(";")[0]
    assert cookie.startswith(f"vid2sub-{given}=")
    status, _, body = serving.get("/", headers={"Cookie": cookie})
    assert (status, body) == (200, b"shiny")
    serving.stop()


@POSIX
def test_the_browser_opens_the_redirect_file_and_ctrl_c_removes_its_folder(start, tmp_path):
    script, record = _browser(tmp_path)
    port = _free_port()
    serving = start(toml=f"[server]\nport = {port}\n", env={"BROWSER": str(script)})
    assert serving.port == port  # [server] port from vid2sub.toml
    deadline = time.monotonic() + 30
    while not record.exists():
        assert time.monotonic() < deadline, "the browser was never opened"
        time.sleep(0.1)
    argv = json.loads(record.read_text(encoding="utf-8"))
    assert serving.token not in " ".join(argv)  # the browser's command line names a file
    page = Path(urllib.request.url2pathname(urlsplit(argv[1]).path))
    assert page.name == "open.html" and page.parent.name.startswith("vid2sub-")
    assert page.parent.parent.resolve() == serving.tmp.resolve()
    assert stat.S_IMODE(page.stat().st_mode) == 0o600
    assert stat.S_IMODE(page.parent.stat().st_mode) == 0o700
    assert auth.auth_url(port, serving.token) in page.read_text(encoding="utf-8")
    assert serving.stop(signal.SIGINT) == exitcodes.OK
    assert serving.folders() == []


@POSIX
def test_the_token_reaches_no_log_or_command_line_and_sigterm_removes_the_folder(start):
    serving = start("--port", "0", "--no-browser")
    ps = subprocess.run(["ps", "-ww", "-o", "command=", "-p", str(serving.proc.pid)],
                        capture_output=True, text=True, check=True).stdout
    assert "serve" in ps and serving.token not in ps
    _sign_in(serving, "t" * 43)
    status, headers, _ = _sign_in(serving, serving.token)
    assert status == 204
    cookie = headers["set-cookie"].split(";")[0]
    serving.get("/", headers={"Cookie": cookie})
    serving.get("/media/unknown", headers={"Cookie": cookie})
    assert len(serving.folders()) == 1
    assert serving.stop(signal.SIGTERM) == 128 + signal.SIGTERM
    assert serving.folders() == []
    lines = serving.log.read_text(encoding="utf-8").splitlines()
    assert [line for line in lines if serving.token in line] == [
        f"  {auth.auth_url(serving.port, serving.token)}"]  # printed once, for the terminal
    assert not [line for line in lines if "GET /" in line or "POST /" in line]  # no access log


@POSIX
@pytest.mark.parametrize(("args", "toml"), [((), "[server]\nopen_browser = false\n"),
                                            (("--no-browser",), "")])
def test_open_browser_false_or_no_browser_opens_nothing(start, tmp_path, args, toml):
    script, record = _browser(tmp_path)
    serving = start("--port", "0", *args, toml=toml, env={"BROWSER": str(script)})
    time.sleep(1)  # the browser is opened just after the link is printed, if at all
    assert not record.exists()
    assert len(serving.folders()) == 1  # the link still works by hand
    serving.stop()
```

- [ ] **Step 8: Run it; watch it fail.** `uv run pytest tests/test_cli_serve.py -q`. Expected:
  `E   ImportError: cannot import name 'serve' from 'vid2sub.commands'
  (…/src/vid2sub/commands/__init__.py)`, then `1 error`.
- [ ] **Step 9: Write the code,** `src/vid2sub/commands/serve.py`:

```python
"""`vid2sub serve`: start the local web app on 127.0.0.1 and open the browser through the launch
token's redirect file (spec §18.1, §6.1, §19.1).

The engine binds 127.0.0.1 only (§6.1), on `--port`, else `[server] port` (8765); 0 takes any free
port. The socket is bound and listening before anything is printed or opened, so the link names
the real port and a browser that loads it early waits instead of being refused. Each launch makes
a new token. Its link (`/auth#t=<token>`) is printed to the terminal for opening by hand, and the
browser, unless `--no-browser` or `[server] open_browser = false`, is opened on a redirect file
holding it (mode 0600 in a private folder), so `ps` shows only that file's path. A browser that
doesn't come back doesn't hold up the engine: it is opened from a thread, as Jupyter does. The
folder goes when the engine stops, on Ctrl-C and SIGTERM too: uvicorn re-raises the signal after
its own shutdown, and SIGTERM's default action would skip `finally`, so it becomes a normal exit
with status 143 (recordings' __main__ does the same). uvicorn's access log is off and it trusts
no proxy headers, since none is in front of it (§6.8, §6.2); the token goes to no log. Without
the built frontend (`www/ui.js`), serve refuses before it reads or binds anything (§18, §23.5).
The Shiny app is imported only once `runtime.configure()` has run, as recordings imports it.
"""

from __future__ import annotations

import argparse
import atexit
import os
import shutil
import signal
import socket
import sys
import threading
import webbrowser
from pathlib import Path

import uvicorn
from starlette.types import ASGIApp

from vid2sub import exitcodes
from vid2sub.commands._common import CommandError, Output, fail, load
from vid2sub.web import auth, runtime
from vid2sub.web.app import WWW, create_app

HOST = "127.0.0.1"


def add_parser(sub) -> None:
    p = sub.add_parser("serve", help="start the editor in your browser")
    p.add_argument("--port", type=_port, metavar="N",
                   help="the port on 127.0.0.1 (default: [server] port in vid2sub.toml, 8765; "
                        "0 takes any free port)")
    p.add_argument("--no-browser", action="store_true",
                   help="print the link to open, but don't open a browser")
    p.add_argument("--config", metavar="PATH", help="the vid2sub.toml to use")
    p.set_defaults(handler=run)


def _port(value: str) -> int:
    if not value.isdigit() or int(value) > 65535:
        raise argparse.ArgumentTypeError("a port is a number from 0 to 65535")
    return int(value)


def shiny_app() -> ASGIApp:
    """The Shiny app, imported now: its module makes it at import, from `www/`, and its server
    reads `runtime.current()`."""
    from vid2sub.web.server import app

    return app


def bind(port: int) -> socket.socket:
    """A socket listening on 127.0.0.1 and `port` (0: any free one); CommandError (69) if the
    port can't be had."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if os.name != "nt":  # on Windows, SO_REUSEADDR would let another program share the port
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((HOST, port))
        sock.listen(128)
    except OSError as err:
        sock.close()
        raise CommandError(exitcodes.UNAVAILABLE,
                           f"port {port} can't be used on {HOST}"
                           + (f" ({err.strerror})" if err.strerror else ""),
                           "is vid2sub already running? Pick another port with --port N, "
                           "or --port 0 for any free one") from None
    return sock


def run(args: argparse.Namespace) -> int:
    out = Output(False)
    try:
        if not (WWW / "ui.js").is_file():
            raise CommandError(exitcodes.UNAVAILABLE, "build the frontend first",
                               "make build (it needs Node 22 or later), then vid2sub serve")
        config = load(args)
        sock = bind(config.server.port if args.port is None else args.port)
    except CommandError as err:
        return fail(out, err)
    rt = runtime.build(config)
    runtime.configure(rt)
    port = sock.getsockname()[1]
    token = auth.new_token()
    app = create_app(rt, token=token, port=port, shiny_app=shiny_app())
    browser = config.server.open_browser and not args.no_browser
    return serve(app, sock, token=token, open_browser=browser, out=out)


def serve(app: ASGIApp, sock: socket.socket, *, token: str, open_browser: bool,
          out: Output) -> int:
    """Run `app` on the listening `sock` until Ctrl-C or SIGTERM, with the link printed and, if
    asked, the browser opened on the redirect file. Blocks; call it from the main thread."""
    port = sock.getsockname()[1]
    link = auth.auth_url(port, token)
    page = auth.write_redirect(link)
    atexit.register(shutil.rmtree, page.parent, ignore_errors=True)  # if `finally` never runs
    previous = signal.signal(signal.SIGTERM, _exit_on_sigterm)
    try:
        out.say(f"vid2sub is running on {HOST}, port {port}. Open the editor with this link "
                "(it works until vid2sub stops):")
        out.say(f"  {link}")
        out.say("Ctrl-C stops vid2sub.")
        if open_browser:
            threading.Thread(target=_open, args=(page, out), name="vid2sub-browser",
                             daemon=True).start()
        uvicorn.Server(uvicorn_config(app)).run(sockets=[sock])
    except KeyboardInterrupt:
        pass
    finally:
        signal.signal(signal.SIGTERM, previous)
        shutil.rmtree(page.parent, ignore_errors=True)
        sock.close()
    return exitcodes.OK


def uvicorn_config(app: ASGIApp) -> uvicorn.Config:
    """No access log (§6.8), no proxy headers believed (no proxy is in front of the engine, and
    X-Forwarded-Proto would change the scheme the guards compare Origin with), no Server header,
    and only warnings from uvicorn itself: the terminal shows vid2sub's lines."""
    return uvicorn.Config(app, access_log=False, proxy_headers=False, server_header=False,
                          log_level="warning", lifespan="on")


def _exit_on_sigterm(signum: int, frame: object) -> None:
    sys.exit(128 + signal.SIGTERM)


def _open(page: Path, out: Output) -> None:
    try:
        opened = webbrowser.open(page.as_uri())
    except webbrowser.Error:
        opened = False
    if not opened:
        out.warn("vid2sub couldn't open a browser: open the link above by hand")
```

  In `src/vid2sub/cli.py`, replace

```python
COMMAND_MODULES: list[str] = [
    "run", "detect", "translate", "import_", "write", "models", "doctor", "config", "cache",
]
```

  with

```python
COMMAND_MODULES: list[str] = [
    "run", "detect", "translate", "import_", "write", "models", "doctor", "config", "cache",
    "serve",
]
```

- [ ] **Step 10: Run the checks; they pass.** `uv run pytest tests/test_cli_serve.py -q`.
  Expected: `13 passed in 7.74s` or so (each child process starts the CLI). Then `make check`.
  Expected: `908 passed, 2 skipped, 4 deselected` twice, `All checks passed!`,
  `no leaks found`; the line-length check on the three files prints nothing.

- [ ] **Step 11: Each guard fails its tests without its fix.** `git add src/vid2sub/commands/serve.py src/vid2sub/cli.py tests/test_cli_serve.py`. Then,
  for each row, make the change in `src/vid2sub/commands/serve.py`, run `uv run pytest tests/test_cli_serve.py -q`, see it fail, and
  restore with `git checkout -- <the file>`. The last column is what this listing's build saw.

| Guard | Change | To | Failed |
|---|---|---|---|
| 127.0.0.1 only | `sock.bind((HOST, port))` | `sock.bind(("0.0.0.0", port))` | 2 |
| listening first | `sock.listen(128)` | `(removed)` | 1 |
| no access log | `access_log=False, proxy_headers=False` | `access_log=True, proxy_headers=False` | 1 |
| no proxy headers | `access_log=False, proxy_headers=False` | `access_log=False, proxy_headers=True` | 1 |
| SIGTERM exits normally | `previous = signal.signal(signal.SIGTERM, _exit_on_sigterm)` | `previous = signal.getsignal(signal.SIGTERM)` | 1 |
| the folder removed | `the `atexit.register(...)` line and the `shutil.rmtree(...)` in `finally`` | `both removed` | 2 |
| the browser flags | `browser = config.server.open_browser and not args.no_browser` | `browser = True` | 2 |
| [server] open_browser | `the same` | `browser = not args.no_browser` | 1 |
| --port | `sock = bind(config.server.port if args.port is None else args.port)` | `sock = bind(config.server.port)` | 5 |
| [server] port | `the same` | `sock = bind(args.port or 0)` | 1 |
| the frontend first | `the `if not (WWW / "ui.js").is_file():` check before `config = load(args)`` | `after it` | 1 |

- [ ] **Step 12: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(cli): 🤖 vid2sub serve binds 127.0.0.1 only, prints the sign-in link and opens the browser on a redirect file, never the token

src/vid2sub/commands/serve.py (spec §18.1, §6.1, §19.1). Without the built frontend (www/ui.js) it
exits 69 with "build the frontend first", before reading vid2sub.toml or binding (§18, §23.5).
It binds and listens on 127.0.0.1 itself, on --port N, else [server] port (8765), with 0 taking
any free port, so the printed link names the real port and an early browser waits rather than
being refused; a port it can't have exits 69 and says how to pick another. Each launch makes a
token (auth.new_token); the link auth.auth_url(port, token) is printed to the terminal, and,
unless --no-browser or [server] open_browser = false, webbrowser opens auth.write_redirect's
file from a thread (as Jupyter does), so the browser's command line and `ps` name only that file.
Its folder is removed at exit: in `finally`, with atexit as a backstop, and on SIGTERM, which
becomes sys.exit(143) because uvicorn re-raises the signal after its own shutdown and the default
action would skip both (as recordings' __main__ does). Ctrl-C exits 0. uvicorn runs on that socket
with its access log off, proxy headers not believed (nothing is in front of it, and
X-Forwarded-Proto would change the scheme the guards compare Origin with), no Server header and
only its warnings (§6.8, §6.2). runtime.configure() runs before the Shiny app is imported, as
recordings does. cli.py registers the command.

The new test failed first with: ImportError: cannot import name 'serve' from 'vid2sub.commands'.
It runs the real CLI in a child process with a stand-in Shiny app and its own TMPDIR, as
recordings' SIGTERM test does, and an executable BROWSER script that records its command line.
Each guard was then reverted in turn and its tests failed: binding 0.0.0.0 (2 failed), not
listening before the link is printed (1), the access log on (1), proxy headers believed (1),
SIGTERM left to its default (1), the folder's removal left out of both `finally` and atexit (2),
the browser opened whatever the flags (2), [server] open_browser ignored (1), --port ignored (5),
[server] port ignored (1), the frontend checked after vid2sub.toml (1).

Docs read: uvicorn's server.py (Server.run(sockets=...) serves already-bound sockets without
logging a start line; capture_signals restores the previous handlers and re-raises the signal)
and config.py (access_log, proxy_headers with forwarded_allow_ips defaulting to 127.0.0.1,
server_header, log_level, bind_socket's SO_REUSEADDR); Python's webbrowser (BROWSER is tried
first; open() returns False when no browser runs), signal (handlers only in the main thread) and
socket pages.

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 11
Co-Authored-By: <the model's own line>
```

  `git commit -F .git/COMMIT_MSG` (the three files are staged from the step before), then
  `git log -1 --format='%(trailers)'` shows `Plan:`.

#### Round 11c: the review's fixes

The listing's Tier 1 reviewer found: shutdown waited for every open response, so a paused
video's stream kept Ctrl-C and SIGTERM from finishing and a SIGKILL then left the token's file
behind (Important); `serve` never called `quiet_libraries()`, so `OPENAI_LOG` could put the
openai logger at DEBUG (Important, spec §6.8); the link was printed to stdout whatever it was,
so `vid2sub serve > log` put a live token in a file (for Dan: spec §18.1 says only "prints that
URL for opening by hand"; the brief said the terminal only, which this round does); and Minor
ones (the guards allowed localhost and ::1; nothing was cleaned up after a failure past `bind`;
the SIGTERM handler's window; `--port ٣`; every command imported FastAPI; two test flakes).

- [ ] **Step 13: Write the failing tests.** Replace `tests/test_cli_serve.py` with:

```python
"""`vid2sub serve` binds 127.0.0.1 only, prints the sign-in link to a terminal and only there,
opens the browser on the redirect file rather than the token, and removes that file's folder
whenever it stops; the token reaches no log and no command line (spec §6.1, §6.8, §18.1; S23).

The real CLI runs in a child process, as recordings' SIGTERM test runs its server, with a stand-in
for the Shiny app (the frontend and the Shiny server aren't needed to test the shell). Its
TMPDIR is the test's own, so the redirect file's folder can be watched. Signals, a terminal and
an executable BROWSER script are POSIX: Windows gets its own run in Phase 3.
"""

import json
import logging
import os
import re
import signal
import socket
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from vid2sub import exitcodes
from vid2sub.cli import main
from vid2sub.commands import serve
from vid2sub.web import auth

POSIX = pytest.mark.skipif(os.name == "nt", reason="POSIX signals, terminals and scripts")
LINK = re.compile(r"http://127\.0\.0\.1:(\d+)/auth#t=([A-Za-z0-9_-]{43})")
PAGE_LINE = re.compile(r"^  (.+open\.html)$", re.MULTILINE)  # the redirect file, when not a tty
# The child: the real `vid2sub serve`, with `www/` pointing at a folder holding a ui.js, and a
# stand-in for the Shiny app whose /stream never ends, as a paused video's stream doesn't.
CHILD = r"""
import asyncio
import sys
from pathlib import Path

from starlette.applications import Starlette
from starlette.responses import PlainTextResponse, StreamingResponse
from starlette.routing import Route

from vid2sub.cli import main
from vid2sub.commands import serve


async def page(request):
    return PlainTextResponse("shiny")


async def forever():
    while True:
        yield b"x" * 65536
        await asyncio.sleep(0.01)


async def stream(request):
    return StreamingResponse(forever(), media_type="application/octet-stream")


serve.WWW = Path(sys.argv[1])
serve.shiny_app = lambda: Starlette(routes=[Route("/stream", stream), Route("/{rest:path}", page)])
raise SystemExit(main(sys.argv[2:]))
"""


def _free_ports(n: int) -> list[int]:
    """`n` different free ports: held at once while they are picked, so none comes twice."""
    socks = [socket.socket() for _ in range(n)]
    try:
        for s in socks:
            s.bind(("127.0.0.1", 0))
        return [s.getsockname()[1] for s in socks]
    finally:
        for s in socks:
            s.close()


@dataclass
class Serving:
    proc: subprocess.Popen
    log: Path
    tmp: Path  # the child's TMPDIR
    port: int
    token: str

    def get(self, path: str, data: bytes | None = None, headers: dict | None = None):
        request = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data,
                                         headers=headers or {})
        try:
            with urllib.request.urlopen(request, timeout=10) as r:
                return r.status, dict(r.headers), r.read()
        except urllib.error.HTTPError as err:
            return err.code, dict(err.headers), err.read()

    def stop(self, sig: int = signal.SIGINT) -> int:
        if os.name == "nt":
            self.proc.terminate()
        else:
            self.proc.send_signal(sig)
        try:
            return self.proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            raise

    def folders(self) -> list[Path]:
        return sorted(self.tmp.glob("vid2sub-*"))

    def text(self) -> str:
        return self.log.read_text(encoding="utf-8", errors="replace")


def _child(tmp_path: Path, n: int, args: tuple[str, ...], toml: str, env: dict | None):
    www = tmp_path / "www"
    www.mkdir(exist_ok=True)
    (www / "ui.js").write_text("// built\n", encoding="utf-8")
    scratch = tmp_path / f"tmp{n}"
    scratch.mkdir()
    config = tmp_path / f"vid2sub{n}.toml"
    config.write_text(toml, encoding="utf-8")
    child_env = {k: v for k, v in os.environ.items() if k != "BROWSER"}
    child_env.update({"TMPDIR": str(scratch), **(env or {})})
    command = [sys.executable, "-c", CHILD, str(www), "serve", "--config", str(config), *args]
    return command, child_env, scratch


def _wait_for_health(serving: Serving, deadline: float) -> None:
    while True:  # the socket listens before anything is printed; wait for the app too
        try:
            if serving.get("/healthz")[0] == 200:
                return
        except OSError:
            pass
        assert time.monotonic() < deadline, "healthz never answered"
        time.sleep(0.1)


@pytest.fixture
def start(tmp_path):
    """Starts `vid2sub serve` with its output in a file, as a log would be. The link is then not
    printed, so it is read from the redirect file whose path is."""
    started: list[Serving] = []

    def run(*args: str, toml: str = "", env: dict | None = None) -> Serving:
        command, child_env, scratch = _child(tmp_path, len(started), args, toml, env)
        log = tmp_path / f"serve{len(started)}.log"
        with log.open("wb") as out:
            proc = subprocess.Popen(command, env=child_env, stdout=out, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + 60
        while not (found := PAGE_LINE.search(log.read_text(encoding="utf-8", errors="replace"))):
            assert proc.poll() is None, log.read_text(encoding="utf-8", errors="replace")
            assert time.monotonic() < deadline, "no redirect file named in 60 s"
            time.sleep(0.1)
        link = LINK.search(Path(found.group(1)).read_text(encoding="utf-8"))
        serving = Serving(proc, log, scratch, int(link.group(1)), link.group(2))
        started.append(serving)
        _wait_for_health(serving, deadline)
        return serving

    yield run
    for serving in started:
        if serving.proc.poll() is None:
            serving.proc.kill()
            serving.proc.wait()


def _browser(tmp_path: Path) -> tuple[Path, Path]:
    """An executable BROWSER that records the command line it was run with, as `ps` shows it.
    It writes the record whole (a rename), so it is never seen half-written."""
    script = tmp_path / "browser"
    record = tmp_path / "browser.json"
    script.write_text(f"#!{sys.executable}\nimport json, os, sys\n"
                      f"open({str(record)!r} + '.part', 'w').write(json.dumps(sys.argv))\n"
                      f"os.replace({str(record)!r} + '.part', {str(record)!r})\n",
                      encoding="utf-8")
    script.chmod(0o755)
    return script, record


def _sign_in(serving: Serving, token: str) -> tuple[int, dict, bytes]:
    return serving.get("/auth", json.dumps({"token": token}).encode(),
                       {"Content-Type": "application/json"})


def _cookie(serving: Serving) -> str:
    status, headers, _ = _sign_in(serving, serving.token)
    assert status == 204
    return headers["set-cookie"].split(";")[0]


def test_serve_refuses_without_the_built_frontend(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(serve, "WWW", tmp_path / "www")  # no ui.js
    broken = tmp_path / "vid2sub.toml"
    broken.write_text("[server\n", encoding="utf-8")  # checked after the frontend
    assert main(["serve", "--config", str(broken)]) == exitcodes.UNAVAILABLE
    assert "build the frontend first" in capsys.readouterr().err


def test_a_port_in_use_exits_69_and_says_how_to_pick_another(tmp_path, monkeypatch, capsys):
    (tmp_path / "www").mkdir()
    (tmp_path / "www" / "ui.js").write_text("// built\n", encoding="utf-8")
    monkeypatch.setattr(serve, "WWW", tmp_path / "www")
    config = tmp_path / "vid2sub.toml"
    config.write_text("", encoding="utf-8")
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen()
        port = taken.getsockname()[1]
        code = main(["serve", "--port", str(port), "--no-browser", "--config", str(config)])
    assert code == exitcodes.UNAVAILABLE
    err = capsys.readouterr().err
    assert f"port {port}" in err and "--port" in err


def test_serve_keeps_the_model_libraries_loggers_at_warning(tmp_path, monkeypatch):
    # Spec §6.8: OPENAI_LOG and CHATLAS_LOG are ignored, as every other command ignores them.
    monkeypatch.setattr(serve, "WWW", tmp_path / "www")  # it stops at the frontend check
    for name in ("openai", "httpx", "chatlas"):
        logging.getLogger(name).setLevel(logging.DEBUG)
    main(["serve"])
    assert [logging.getLogger(n).level for n in ("openai", "httpx", "chatlas")] == [
        logging.WARNING] * 3


def test_a_failure_after_binding_leaves_nothing_running(tmp_path, monkeypatch):
    (tmp_path / "www").mkdir()
    (tmp_path / "www" / "ui.js").write_text("// built\n", encoding="utf-8")
    monkeypatch.setattr(serve, "WWW", tmp_path / "www")

    def broken():
        raise RuntimeError("the Shiny app failed to load")

    monkeypatch.setattr(serve, "shiny_app", broken)
    (port,) = _free_ports(1)
    with pytest.raises(RuntimeError, match="failed to load"):
        main(["serve", "--port", str(port), "--no-browser", "--config", str(tmp_path / "x.toml")])
    with socket.socket() as again:
        again.bind(("127.0.0.1", port))  # the engine's socket was closed
    from vid2sub.web import runtime

    with pytest.raises(RuntimeError, match="closed"):
        runtime.current().queue.submit(["/videos/a.mkv"])  # and its job queue stopped
    runtime.configure(None)


def test_bind_listens_on_127_0_0_1_only():
    sock = serve.bind(0)
    try:
        assert sock.family == socket.AF_INET
        assert sock.getsockname()[0] == "127.0.0.1"
        with socket.create_connection(sock.getsockname(), timeout=5):
            pass  # listening already: a browser opened now waits rather than being refused
    finally:
        sock.close()


def test_uvicorn_keeps_no_access_log_believes_no_proxy_and_stops_within_seconds():
    config = serve.uvicorn_config(lambda scope, receive, send: None)
    assert config.access_log is False
    assert config.proxy_headers is False
    assert config.server_header is False
    assert config.timeout_graceful_shutdown == 3


@pytest.mark.parametrize("value", ["-1", "65536", "http", "80.5", "٣"])
def test_port_must_be_a_port_number(value, capsys):
    with pytest.raises(SystemExit) as exited:
        main(["serve", "--port", value])
    assert exited.value.code == exitcodes.USAGE
    assert "a port is a number from 0 to 65535" in capsys.readouterr().err


def test_the_link_signs_a_browser_in_on_the_port_given(start):
    configured, given = _free_ports(2)
    serving = start("--port", str(given), "--no-browser", toml=f"[server]\nport = {configured}\n")
    assert serving.port == given  # --port wins over vid2sub.toml
    assert serving.get("/healthz")[2] == b'{"ok":true}'
    assert serving.get("/")[0] == 401
    assert _sign_in(serving, "t" * 43)[0] == 403
    cookie = _cookie(serving)
    assert cookie.startswith(f"vid2sub-{given}=")
    status, _, body = serving.get("/", headers={"Cookie": cookie})
    assert (status, body) == (200, b"shiny")
    serving.stop()


@POSIX
def test_a_terminal_gets_the_link_itself(tmp_path):
    import pty

    command, env, scratch = _child(tmp_path, 0, ("--port", "0", "--no-browser"), "", None)
    leader, follower = pty.openpty()
    proc = subprocess.Popen(command, env=env, stdin=subprocess.DEVNULL, stdout=follower,
                            stderr=follower)
    os.close(follower)
    seen, deadline = b"", time.monotonic() + 60
    try:
        while not LINK.search(seen.decode(errors="replace")):
            assert time.monotonic() < deadline, seen.decode(errors="replace")
            seen += os.read(leader, 4096)
        port, token = LINK.search(seen.decode()).groups()
        assert len(list(scratch.glob("vid2sub-*"))) == 1
        serving = Serving(proc, tmp_path / "unused.log", scratch, int(port), token)
        _wait_for_health(serving, deadline)
        assert _sign_in(serving, token)[0] == 204  # the link printed is the live one
        assert serving.stop(signal.SIGINT) == exitcodes.OK
        assert serving.folders() == []
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        os.close(leader)


@POSIX
def test_the_browser_opens_the_redirect_file_and_ctrl_c_removes_its_folder(start, tmp_path):
    script, record = _browser(tmp_path)
    (port,) = _free_ports(1)
    serving = start(toml=f"[server]\nport = {port}\n", env={"BROWSER": str(script)})
    assert serving.port == port  # [server] port from vid2sub.toml
    deadline = time.monotonic() + 30
    while not record.exists():
        assert time.monotonic() < deadline, "the browser was never opened"
        time.sleep(0.1)
    argv = json.loads(record.read_text(encoding="utf-8"))
    assert serving.token not in " ".join(argv)  # the browser's command line names a file
    page = Path(urllib.request.url2pathname(urlsplit(argv[1]).path))
    assert page.name == "open.html" and page.parent.name.startswith("vid2sub-")
    assert page.parent.parent.resolve() == serving.tmp.resolve()
    assert stat.S_IMODE(page.stat().st_mode) == 0o600
    assert stat.S_IMODE(page.parent.stat().st_mode) == 0o700
    assert auth.auth_url(port, serving.token) in page.read_text(encoding="utf-8")
    assert serving.stop(signal.SIGINT) == exitcodes.OK
    assert serving.folders() == []


@POSIX
def test_the_token_reaches_no_log_or_command_line_and_sigterm_removes_the_folder(start):
    serving = start("--port", "0", "--no-browser")
    ps = subprocess.run(["ps", "-ww", "-o", "command=", "-p", str(serving.proc.pid)],
                        capture_output=True, text=True, check=True).stdout
    assert "serve" in ps and serving.token not in ps
    _sign_in(serving, "t" * 43)
    cookie = _cookie(serving)
    serving.get("/", headers={"Cookie": cookie})
    serving.get("/media/unknown", headers={"Cookie": cookie})
    assert len(serving.folders()) == 1
    assert serving.stop(signal.SIGTERM) == 128 + signal.SIGTERM
    assert serving.folders() == []
    assert serving.token not in serving.text()  # output to a file names the redirect file


@POSIX
@pytest.mark.parametrize("sig", [signal.SIGINT, signal.SIGTERM])
def test_a_stalled_response_doesnt_keep_the_engine_from_stopping(start, sig):
    serving = start("--port", "0", "--no-browser")
    cookie = _cookie(serving)
    with socket.create_connection(("127.0.0.1", serving.port), timeout=10) as stalled:
        stalled.sendall(f"GET /stream HTTP/1.1\r\nHost: 127.0.0.1:{serving.port}\r\n"
                        f"Cookie: {cookie}\r\n\r\n".encode())
        stalled.recv(1024)  # streaming; then never read again, as a paused video
        began = time.monotonic()
        code = serving.stop(sig)
    assert time.monotonic() - began < 15
    assert code == (exitcodes.OK if sig == signal.SIGINT else 128 + signal.SIGTERM)
    assert serving.folders() == []


@POSIX
@pytest.mark.parametrize(("args", "toml"), [((), "[server]\nopen_browser = false\n"),
                                            (("--no-browser",), "")])
def test_open_browser_false_or_no_browser_opens_nothing(start, tmp_path, args, toml):
    script, record = _browser(tmp_path)
    serving = start("--port", "0", *args, toml=toml, env={"BROWSER": str(script)})
    deadline = time.monotonic() + 3  # the browser opens just after the output, if at all
    while time.monotonic() < deadline:
        assert not record.exists()
        time.sleep(0.1)
    assert len(serving.folders()) == 1  # the redirect file still works by hand
    serving.stop()
```

  In `tests/test_web_app.py`, replace

```python
    # HostGuard: a name the engine isn't called by, as DNS rebinding sends it.
    assert client.get("/healthz", headers={"Host": "evil.example"}).status_code == 400
```

  with

```python
    # HostGuard: a name the engine isn't called by, as DNS rebinding sends it. Only 127.0.0.1,
    # which the engine binds and its link names, is allowed.
    assert client.get("/healthz", headers={"Host": "evil.example"}).status_code == 400
    assert client.get("/healthz", headers={"Host": f"localhost:{PORT}"}).status_code == 400
```

- [ ] **Step 14: Run them; watch them fail.** `uv run pytest tests/test_cli_serve.py
  tests/test_web_app.py -q`. Expected, after about 7 minutes (each child-process test waits 60 s
  for the redirect file's path, which round 11b's `serve` doesn't print):
  `FAILED tests/test_cli_serve.py::test_serve_keeps_the_model_libraries_loggers_at_warning`,
  `::test_a_failure_after_binding_leaves_nothing_running`,
  `::test_uvicorn_keeps_no_access_log_believes_no_proxy_and_stops_within_seconds`,
  `::test_port_must_be_a_port_number[\u0663]`, `::test_the_link_signs_a_browser_in_on_the_port_given`,
  `::test_the_browser_opens_the_redirect_file_and_ctrl_c_removes_its_folder`,
  `::test_the_token_reaches_no_log_or_command_line_and_sigterm_removes_the_folder`,
  `::test_a_stalled_response_doesnt_keep_the_engine_from_stopping[2]` and `[15]`,
  `::test_open_browser_false_or_no_browser_opens_nothing` (both),
  `FAILED tests/test_web_app.py::test_the_guards_wrap_the_whole_engine`, then
  `12 failed, 29 passed in 422.29s (0:07:02)`.
- [ ] **Step 15: Write the code.** Replace `src/vid2sub/web/__init__.py` with:

```python
"""The local web app: the editor's backend, the app shell and its server (spec §19)."""

from pathlib import Path

# The built frontend (`ui.js`, `ui.css`) and its fonts, which `vid2sub serve` needs (spec §18).
WWW = Path(__file__).parent / "www"
```

  Replace `src/vid2sub/web/app.py` with (`WWW` moves to the package, and `HOSTS` is 127.0.0.1
  only):

```python
"""The app shell: `/auth`, `/healthz` and `/media/{token}`, with the Shiny app mounted at "/"
last, and the whole engine wrapped in the guards (spec §19.1, §6.1, §6.2).

As recordings' create_app does (packages/ui/src/recordings_ui/app.py at 8deb039): a FastAPI app
whose own routes win because the Shiny mount comes after them, and guards around everything,
the Shiny app and its websocket included. vid2sub adds the launch token, so the order is
`HostGuard(WriteGuard(TokenGuard(api)))`: a wrong name is refused before anything else, every
response carries the security headers, and only then is the cookie asked for. The one name
allowed is 127.0.0.1, which the engine binds and its link names; the cookie belongs to that name,
so a request to localhost could never sign in anyway. FastAPI's own pages (`/docs`, `/redoc`,
`/openapi.json`) are off: they load scripts from a CDN, and the engine makes no third-party
requests (§6.3). `/healthz` says only `{"ok": true}` (§6.1). The Shiny app is passed in, made by
its own module once `runtime.configure()` has run; the mount doesn't pass lifespan events on, so
anything that must happen at shutdown goes in this app's lifespan. Stopping the engine closes the
job queue, which cancels what waits and asks the running job to stop (§17.1).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.types import ASGIApp

from vid2sub.web import auth, media
from vid2sub.web.guards import HostGuard, WriteGuard
from vid2sub.web.runtime import Runtime

HOSTS = frozenset({"127.0.0.1"})  # the one name the engine answers to (spec §6.1, §6.2)


def create_app(rt: Runtime, *, token: str, port: int, shiny_app: ASGIApp) -> ASGIApp:
    @asynccontextmanager
    async def lifespan(_api: FastAPI) -> AsyncIterator[None]:
        yield
        await asyncio.to_thread(rt.queue.close)  # bounded (5 s), and off the event loop

    api = FastAPI(title="vid2sub", docs_url=None, redoc_url=None, openapi_url=None,
                  lifespan=lifespan)

    @api.get("/healthz")
    def healthz() -> dict:
        return {"ok": True}

    api.router.routes.extend([*auth.routes(token, port), media.route(rt.media)])
    api.mount("/", shiny_app)  # last, so the routes above win
    return HostGuard(WriteGuard(auth.TokenGuard(api, token=token, port=port), HOSTS), HOSTS)
```

  Replace `src/vid2sub/commands/serve.py` with:

```python
"""`vid2sub serve`: start the local web app on 127.0.0.1 and open the browser through the launch
token's redirect file (spec §18.1, §6.1, §19.1).

The engine binds 127.0.0.1 only (§6.1), on `--port`, else `[server] port` (8765); 0 takes any free
port. The socket is bound and listening before anything is printed or opened, so the link names
the real port and a browser that loads it early waits instead of being refused. Each launch makes
a new token. Its link (`/auth#t=<token>`) is printed only to a terminal, for opening by hand: when
the output goes to a file or a pipe, which may be a log other people can read, the redirect
file's path is printed instead. The browser, unless `--no-browser` or `[server] open_browser =
false`, is opened on that redirect file (mode 0600 in a private folder), so `ps` shows only its
path. A browser that doesn't come back doesn't hold up the engine: it is opened from a thread, as
Jupyter does. The folder goes when the engine stops, on Ctrl-C and SIGTERM too: uvicorn re-raises
the signal after its own shutdown, and SIGTERM's default action would skip `finally`, so it
becomes a normal exit with status 143 (recordings' __main__ does the same; Windows' Ctrl-Break
likewise). Shutdown waits at most 3 seconds for open responses, since a paused video holds its
stream open. uvicorn's access log is off and it trusts no proxy headers, since none is in front of
it; the openai, httpx and chatlas loggers stay at WARNING, as for every command (§6.8, §6.2).
Without the built frontend (`www/ui.js`), serve refuses before it reads or binds anything (§18,
§23.5). The web modules are imported only when serve runs, so other commands don't load them, and
the Shiny app only once `runtime.configure()` has run, as recordings imports it.
"""

from __future__ import annotations

import argparse
import atexit
import os
import shutil
import signal
import socket
import sys
import threading
import webbrowser
from pathlib import Path
from typing import TYPE_CHECKING

from vid2sub import exitcodes
from vid2sub.commands._common import CommandError, Output, fail, load
from vid2sub.web import WWW

if TYPE_CHECKING:
    import uvicorn
    from starlette.types import ASGIApp

HOST = "127.0.0.1"
GRACE = 3  # seconds a shutdown waits for open responses before it cancels them


def add_parser(sub) -> None:
    p = sub.add_parser("serve", help="start the editor in your browser")
    p.add_argument("--port", type=_port, metavar="N",
                   help="the port on 127.0.0.1 (default: [server] port in vid2sub.toml, 8765; "
                        "0 takes any free port)")
    p.add_argument("--no-browser", action="store_true",
                   help="print the link to open, but don't open a browser")
    p.add_argument("--config", metavar="PATH", help="the vid2sub.toml to use")
    p.set_defaults(handler=run)


def _port(value: str) -> int:
    if not (value.isascii() and value.isdigit()) or int(value) > 65535:
        raise argparse.ArgumentTypeError("a port is a number from 0 to 65535")
    return int(value)


def shiny_app() -> ASGIApp:
    """The Shiny app, imported now: its module makes it at import, from `www/`, and its server
    reads `runtime.current()`."""
    from vid2sub.web.server import app

    return app


def bind(port: int) -> socket.socket:
    """A socket listening on 127.0.0.1 and `port` (0: any free one); CommandError (69) if the
    port can't be had."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if os.name != "nt":  # on Windows, SO_REUSEADDR would let another program share the port
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((HOST, port))
        sock.listen(128)
    except OSError as err:
        sock.close()
        raise CommandError(exitcodes.UNAVAILABLE,
                           f"port {port} can't be used on {HOST}"
                           + (f" ({err.strerror})" if err.strerror else ""),
                           "is vid2sub already running? Pick another port with --port N, "
                           "or --port 0 for any free one") from None
    return sock


def run(args: argparse.Namespace) -> int:
    from vid2sub.engines.clients import quiet_libraries
    from vid2sub.web import auth, runtime
    from vid2sub.web.app import create_app

    quiet_libraries()  # OPENAI_LOG and CHATLAS_LOG are ignored (§6.8)
    out = Output(False)
    try:
        if not (WWW / "ui.js").is_file():
            raise CommandError(exitcodes.UNAVAILABLE, "build the frontend first",
                               "make build (it needs Node 22 or later), then vid2sub serve")
        config = load(args)
        sock = bind(config.server.port if args.port is None else args.port)
    except CommandError as err:
        return fail(out, err)
    rt = None
    try:
        rt = runtime.build(config)
        runtime.configure(rt)
        token = auth.new_token()
        app = create_app(rt, token=token, port=sock.getsockname()[1], shiny_app=shiny_app())
    except BaseException:  # a bug: leave nothing running behind the traceback
        sock.close()
        if rt is not None:
            rt.queue.close()
        raise
    browser = config.server.open_browser and not args.no_browser
    return serve(app, sock, token=token, open_browser=browser, out=out)


def serve(app: ASGIApp, sock: socket.socket, *, token: str, open_browser: bool,
          out: Output) -> int:
    """Run `app` on the listening `sock` until Ctrl-C or SIGTERM, with the link printed and, if
    asked, the browser opened on the redirect file. Blocks; call it from the main thread."""
    import uvicorn

    from vid2sub.web import auth

    port = sock.getsockname()[1]
    previous = {sig: signal.signal(sig, _exit_on_signal) for sig in _EXIT_SIGNALS}
    page: Path | None = None
    try:
        link = auth.auth_url(port, token)
        page = auth.write_redirect(link)
        atexit.register(shutil.rmtree, page.parent, ignore_errors=True)  # if `finally` never runs
        out.say(f"vid2sub is running on {HOST}, port {port}.")
        if out.tty:
            out.say("Open the editor with this link (it works until vid2sub stops):")
            out.say(f"  {link}")
        else:  # a file or a pipe: the link would put the token where others may read it
            out.say("Open the editor by opening this file in a browser (it works until vid2sub "
                    "stops):")
            out.say(f"  {page}")
        out.say("Ctrl-C stops vid2sub.")
        if open_browser:
            threading.Thread(target=_open, args=(page, out), name="vid2sub-browser",
                             daemon=True).start()
        uvicorn.Server(uvicorn_config(app)).run(sockets=[sock])
    except KeyboardInterrupt:
        pass
    finally:
        if page is not None:
            shutil.rmtree(page.parent, ignore_errors=True)
        sock.close()
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    return exitcodes.OK


def uvicorn_config(app: ASGIApp) -> uvicorn.Config:
    """No access log (§6.8), no proxy headers believed (no proxy is in front of the engine, and
    X-Forwarded-Proto would change the scheme the guards compare Origin with), no Server header,
    only uvicorn's warnings, and a shutdown that waits GRACE seconds for open responses."""
    import uvicorn

    return uvicorn.Config(app, access_log=False, proxy_headers=False, server_header=False,
                          log_level="warning", lifespan="on", timeout_graceful_shutdown=GRACE)


# The signals uvicorn re-raises after its shutdown whose default action skips `finally` and
# atexit: SIGTERM everywhere, Ctrl-Break on Windows. SIGINT raises KeyboardInterrupt already.
_EXIT_SIGNALS = [signal.SIGTERM] + ([signal.SIGBREAK] if hasattr(signal, "SIGBREAK") else [])


def _exit_on_signal(signum: int, frame: object) -> None:
    sys.exit(128 + signum)


def _open(page: Path, out: Output) -> None:
    try:
        opened = webbrowser.open(page.as_uri())
    except webbrowser.Error:
        opened = False
    if not opened:
        out.warn("vid2sub couldn't open a browser: open what it printed above by hand")
```

- [ ] **Step 16: Run the checks; they pass.** `uv run pytest tests/test_cli_serve.py
  tests/test_web_app.py -q`. Expected: `41 passed in 21.02s` or so. Then `make check`. Expected:
  `914 passed, 2 skipped, 4 deselected` twice, `All checks passed!`, `no leaks found`; the
  line-length check on the changed files prints nothing.

- [ ] **Step 17: Each guard fails its tests without its fix.** `git add src/vid2sub/commands/serve.py src/vid2sub/web/__init__.py src/vid2sub/web/app.py tests/test_cli_serve.py tests/test_web_app.py`. Then,
  for each row, make the change in `src/vid2sub/commands/serve.py` (the last row: `src/vid2sub/web/app.py`), run `uv run pytest tests/test_cli_serve.py tests/test_web_app.py -q`, see it fail, and
  restore with `git checkout -- <the file>`. The last column is what this listing's build saw.

| Guard | Change | To | Failed |
|---|---|---|---|
| the libraries' loggers | `quiet_libraries()  # OPENAI_LOG and CHATLAS_LOG are ignored (§6.8)` | `pass` | 1 |
| ASCII digits | `if not (value.isascii() and value.isdigit()) or int(value) > 65535:` | `if not value.isdigit() or int(value) > 65535:` | 1 |
| shutdown grace | `lifespan="on", timeout_graceful_shutdown=GRACE)` | `lifespan="on")` | 3 |
| the link to a terminal only | `if out.tty:` | `if True:` | 7 |
| cleanup after a failure | `the three cleanup lines in `except BaseException:`` | ``raise` alone` | 1 |
| 127.0.0.1 only (Host) | `HOSTS = frozenset({"127.0.0.1"})` | `HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})` | 1 |

- [ ] **Step 18: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
fix(cli): 🤖 vid2sub serve stops within seconds of Ctrl-C even with a video streaming, prints the token only to a terminal, and answers only to 127.0.0.1

Task 11's Tier 1 review (one independent reviewer, with AGENTS.md's security checklist) found
two Important bugs and a spec reading for Dan, each reproduced and fixed here:
- Shutdown waited for every open response, so a paused video's /media/ stream kept Ctrl-C and
  SIGTERM from ever finishing, and a service manager's SIGKILL then left the redirect file, with
  the token in it. uvicorn_config sets timeout_graceful_shutdown=3 (serve.GRACE).
- serve never called clients.quiet_libraries(), so OPENAI_LOG could set the openai logger to
  DEBUG in the process that retranslates (spec §6.8; every other command calls it).
- The link was printed to stdout whatever stdout was, so `vid2sub serve > log` put a live token
  in a file others may read; the brief says the terminal only. It is now printed only to a
  terminal; to a file or a pipe, the redirect file's path (mode 0600) is printed instead. Spec
  §18.1 says only "prints that URL for opening by hand", which a terminal still gets: Dan may
  prefer it printed everywhere.
And the Minor ones: the guards allow only 127.0.0.1 (app.HOSTS), which the engine binds and its
link names; a failure after binding closes the socket and the job queue before the traceback;
the SIGTERM handler is installed before the redirect file is written and put back after it is
removed, and Windows' Ctrl-Break gets the same exit; --port refuses non-ASCII digits; the web
modules are imported only when serve runs, so other commands don't load FastAPI (vid2sub.web.WWW
moves to the package so serve can name it without importing app.py). The tests' BROWSER script
writes its record whole, two ports picked for one test are always different, and the
no-browser test watches for 3 s.

The new tests failed first with: 12 failed, 29 passed (the loggers, the cleanup after a failure,
the shutdown grace, the non-ASCII port, the link written to a file in five child-process tests,
the stalled stream twice, and localhost's Host).
Each fix was then reverted in turn and its tests failed: the libraries' loggers left (1 failed),
non-ASCII digits (1), no shutdown grace (3), the link printed to a file (7), nothing closed after
a failure (1), localhost allowed (1).

Docs read: uvicorn's config.py (timeout_graceful_shutdown) and server.py (shutdown waits for
connections, then cancels their tasks after the timeout); Python's pty (openpty) and signal
(SIGBREAK on Windows) pages.

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 11
Co-Authored-By: <the model's own line>
```

  `git commit -F .git/COMMIT_MSG` (the five files are staged from the step before), then
  `git log -1 --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 19: Review, look forward, close.** The Tier 1 review from `$(cat .git/TASK_BASE)`
  (`AGENTS.md`, *Reviews*, with the security checklist). Worth the reviewers' time: that the token
  reaches no log, response, URL path or query, file name or command line (`ps`), and is printed
  only to a terminal; that nothing binds or answers beyond 127.0.0.1 (the socket, `HOSTS`); that
  uvicorn's defaults (proxy headers, access log, Server header) can't weaken the guards; that the
  redirect folder goes on every exit (normal, Ctrl-C, SIGTERM, a failure after `bind`, a stalled
  stream); that the lifespan closes the queue without blocking the loop; that every guard test
  fails without its fix. Known and accepted: Windows' signals and terminals aren't tested until
  Phase 3 (the tests skip there; Ctrl-Break exits like SIGTERM). The forward review over Tasks 12,
  13, 14, 19, 21, 22 and 23 (Task 12 creates `vid2sub.web.server.app`, which `serve.shiny_app()`
  imports, and its e2e harness reads the link from the redirect file; Task 13 adds `--demo`;
  Task 14 closes an episode with `rt.backend.close(ep.id)` and `rt.media.revoke_owner(ep.id)` when
  a session ends, in the server's `session.on_ended`, since the mount passes no lifespan; Task 19
  replaces `runtime._no_jobs` with the pipeline's runner; Task 21's CI e2e job runs `make e2e`;
  Task 22's README says the link is printed only to a terminal; Task 23's Step 2 expects the
  terminal to print it). The docs this task made untrue: none expected (the README's *Use* block
  doesn't list `vid2sub serve` yet: a missing doc, for Task 22). Then the close, its own commit,
  holding this plan with this task's boxes ticked and **Now** set to `Task 12: The frontend
  scaffold and the shinyreact server, open.`, and the spec's scenario row S23 set to `built`, its
  Proof reading `tests/test_cli_serve.py`, `tests/test_web_app.py`, `tests/test_web_auth.py`,
  with the message in `.git/CLOSE_MSG`:

```text
docs(plan): 🤖 close Task 11: The app shell and `vid2sub serve`

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

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 11
Co-Authored-By: <the model's own line>
```

  `git add docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md
  docs/superpowers/specs/2026-10-14-vid2sub-design.md`, `git commit -F .git/CLOSE_MSG`.

***

### Task 12: The frontend scaffold and the shinyreact server

**Tier:** 2 · **Scenarios:** S26

**Files:**
- Create: `frontend/` (`package.json`, `package-lock.json`, `vite.config.js`, `tsconfig.json`,
  `components.json`, `.nvmrc`, `scripts/check-node.mjs`, `src/ui.tsx`, `src/App.tsx`, `src/sr.ts`,
  `src/types.ts`, `src/index.css`, `src/theme.css`, `src/lib/theme.ts` (+ test),
  `src/lib/utils.ts`, `src/lib/notices.ts` (+ test), `src/lib/connection.ts` (+ test),
  `src/components/TopBar.tsx` (+ test), `src/components/ThemeSwitch.tsx`,
  `src/components/ui/toggle.tsx`, `src/components/ui/toggle-group.tsx`, `src/build.test.ts`),
  `_brand.yml`, `scripts/brand_css.py`, `src/vid2sub/web/server.py`,
  `src/vid2sub/web/static/busy/busy-indicators.js`, `src/vid2sub/web/www/fonts/`,
  `tests/e2e/conftest.py` (moved here from Task 13: the CSP test needs a browser against
  `vid2sub serve`)
- Modify: `Makefile` (`setup` runs `npm ci`; `build`, `test-js` (in `check`), `e2e`, `brand`,
  `skills`), `.gitignore`, `pyproject.toml` (pyyaml in the dev group; the `e2e` marker, moved
  here from Task 13), `uv.lock`, `src/vid2sub/web/views.py` (`capabilities_view`,
  `local_endpoints`, `status_view`)
- Test: `tests/test_web_server.py`, `tests/test_brand.py`, `tests/e2e/test_csp.py`

**Interfaces:**
- Consumes: Task 11's `runtime.current()`, `app.create_app`, `vid2sub.web.WWW`, and `serve`
  (which imports `server.app`); Task 5's `Capabilities`; `engines.clients.list_models`,
  `KeyRing`; `config.is_local`.
- Produces:
  - Outputs `capabilities` (`views.capabilities_view(caps) -> dict`: `engine`, `generate`, `save`,
    `path_input`) and `status` (`views.status_view(config, keys, reachable, *, ffmpeg) -> dict`:
    `{"endpoints": [{"name", "local", "key": "present" | "missing" | "none", "reachable": bool |
    None}], "ffmpeg": bool}`, keys by presence only; `reachable` only for local endpoints, checked
    off the loop now and every `server.STATUS_EVERY` (60) seconds by `server.reachable(config,
    keys)`; None until checked, and always for cloud ones, never contacted);
    `views.local_endpoints(config) -> list[str]`.
  - Message `notice` (`{kind: "info" | "error", text}`): `await server.notice(session, kind,
    text)`; the frontend shows it as plain text, info in a polite live region and errors in an
    alert, the newest three (`lib/notices.ts`).
  - `server.app = ReactApp(server, ui=server.page, static_assets={"/": WWW})`: the page is
    shinyreact's `page_react` with `server.BUSY_INDICATORS` (see *The CSP* below); `www/` is also
    served at "/" for the fonts, as ReactApp's own discovery mounts it.
  - `frontend/src/sr.ts`: re-exports `useShinyInput`, `useShinyOutputValue`,
    `useShinyOutputStatus`, `useShinyOutputError`, `useShinyInitialized`, `useSetShinyInput`,
    `useShinyMessageHandler` from `window.shinyreact` (types only from the npm package). Every
    output is subscribed, and every input and message handler lives, in `App`.
  - `frontend/src/lib/connection.ts`: on Shiny's `shiny:disconnected` (a jQuery event, which
    `addEventListener` never sees) the page asks for "/" once with its cookie and says, in an alert
    with `data-testid="lost"`: on a 401, that vid2sub was restarted, with `auth.SIGN_IN_AGAIN`; on
    no answer, that it isn't running (with **Check again**, `data-testid="check-again"`); else, to
    reload. It never reconnects. A refused websocket handshake reaches the browser as an HTTP 403
    (close code 1006), never 1008 (Review Focus 5).
  - The e2e fixtures (`tests/e2e/conftest.py`): `server` (a `vid2sub serve --no-browser` on a free
    port, its URL and launch link), `page` (signed in through `/auth#t=<token>`; the test fails on
    any console error or CSP violation), `watch` (its `errors`, `requests`, `violations()`,
    `clear()`), `open_page(server)` and `launch(tmp, *args, port=0)`. Task 13 makes `server` the
    demo.
  - `data-testid`s: `app`, `topbar`, `engine`, `status`, `endpoint`, `main`, `notice`,
    `theme-light`, `theme-system`, `theme-dark`, `lost`, `check-again`.

**The CSP (spec §6.3, §29), found in Chromium while this listing was built.** Shiny 1.8.0's page
has one inline script, its busy indicators (`busy_indicators.use()` in the
`shiny-busy-indicators` dependency's head), which `script-src 'self'` blocks: one violation per
page load, costing only the busy pulse (spinners attach to Shiny output elements, which a React
page has none of). Shiny has no option that leaves it out (`use(spinners=False, pulse=False)`
writes an inline script too). htmltools keeps the highest version of a dependency per name, so
`server.py` passes `page_react` a `shiny-busy-indicators` at Shiny's version plus `+vid2sub` (no
head) and the same two lines as a file: no violation, and the pulse still works. No `style-src` is
needed: `default-src 'self'` covers stylesheet files, React's `style` props go through the CSSOM,
and the page has no `<style>` or style attribute. The test of the rendered page is the guard: an
upgrade that stops the replacement winning fails it.

**For Tasks 15–18: Radix's modal parts inject a `<style>` element** (react-remove-scroll), which
the CSP blocks. Probed on this scaffold in Chromium (radix-ui 1.8.1): Dialog (modal, the default,
so shadcn's Dialog and Sheet), DropdownMenu (modal, the default) and Popover with `modal` each log
one `style-src-elem` violation; Select logs eight (it injects its own scrollbar style too);
Dialog and DropdownMenu with `modal={false}`, and Popover as it is, log none. So, with no CSP
change (decided with the coordinator, 2026-10-24):
- **Modal** (the conflict picker, any confirm, Task 18's settings drawer as a side sheet): the
  native `<dialog>` with `showModal()`, which puts it in the top layer, makes the rest of the page
  inert for focus and screen readers, closes on Esc and moves focus in and back, and injects no
  `<style>`. Scroll lock is the `dialog-open` class on `<html>`, from `index.css`
  (`html.dialog-open { overflow: hidden; }`): a class, which the CSP allows. Whichever of Task 16
  or 18 comes first builds `frontend/src/components/ui/dialog.tsx`, probed as this, with zero
  violations, focus in, Tab kept inside, the backdrop taking the pointer, Esc closing it and focus
  back on the opener (the `dialog-open` class goes on the `close` event, a task later: assert it
  with `expect(page.locator("html")).not_to_have_class(re.compile(r"\bdialog-open\b"))`, which
  retries):

```tsx
import { type ReactNode, useEffect, useId, useRef } from "react";

import { cn } from "@/lib/utils";

/** A modal dialog, or with `side` a sheet at that edge, on the native <dialog> element.
 * showModal() puts it in the top layer, makes the rest of the page inert for focus and screen
 * readers, closes it on Esc and moves focus in and, on close, back to the opener. Radix's modal
 * parts inject a <style> element, which the CSP blocks (Task 12's probe), so the editor's modal
 * parts are this one. Scroll lock is the `dialog-open` class on <html>, from index.css: a class,
 * which the CSP allows, where an inline style isn't. */
export function Dialog({ open, onClose, title, side, children, className }: {
  open: boolean;
  onClose: () => void;
  title: string;
  side?: "left" | "right";
  children: ReactNode;
  className?: string;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      dialog.showModal();
      document.documentElement.classList.add("dialog-open");
    } else if (!open && dialog.open) {
      dialog.close();
    }
  }, [open]);
  useEffect(() => () => document.documentElement.classList.remove("dialog-open"), []);
  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      data-side={side}
      onClose={() => {
        document.documentElement.classList.remove("dialog-open");
        onClose();
      }}
      className={cn(
        "rounded-lg border border-border bg-popover p-4 text-popover-foreground shadow-lg backdrop:bg-black/40",
        side && "m-0 h-dvh max-h-none w-96 max-w-full rounded-none data-[side=left]:mr-auto data-[side=right]:ml-auto",
        className,
      )}
    >
      <h2 id={titleId} className="mb-3 font-bold">{title}</h2>
      {children}
    </dialog>
  );
}
```

  and an e2e test that opens it from a button and checks, through the `page` fixture (zero console
  errors and violations), `dialog[open]` matches `:modal`, `document.activeElement` is inside it,
  six Tabs never leave it, `document.elementFromPoint` over a top-bar button isn't that button,
  Escape closes it and focus is the opener again, and `html` loses `dialog-open`.
- **Menus and popovers:** Radix DropdownMenu with `modal={false}`; Popover as it is.
- **Choices:** a native `<select>`, styled; never Radix or shadcn Select.
- The `page` fixture's console-error guard stays as it is, so a modal Radix part or a Radix
  Select fails the task that adds it.

- [ ] **Step 0: Record the base:** `git rev-parse HEAD > .git/TASK_BASE`.

#### Round 12a: the frontend scaffold, the brand and the fonts

- [ ] **Step 1: Write the failing tests.** `frontend/src/lib/theme.test.ts` (recordings', with
  this repo's storage key):

```ts
import { describe, expect, it, vi } from "vitest";

import { applyTheme, browserStorage, currentTheme, loadChoice, resolveTheme, saveChoice } from "./theme";

describe("theme", () => {
  it("follows the OS only in system mode", () => {
    expect(resolveTheme("system", true)).toBe("dark");
    expect(resolveTheme("system", false)).toBe("light");
    expect(resolveTheme("light", true)).toBe("light");
    expect(resolveTheme("dark", false)).toBe("dark");
  });

  it("remembers a choice and ignores junk", () => {
    const store = new Map<string, string>();
    const storage = { getItem: (k: string) => store.get(k) ?? null, setItem: (k: string, v: string) => void store.set(k, v) };
    expect(loadChoice(storage)).toBe("system");
    saveChoice(storage, "dark");
    expect(loadChoice(storage)).toBe("dark");
    store.set("vid2sub.theme", "purple");
    expect(loadChoice(storage)).toBe("system");
  });

  it("survives storage that throws (private windows, blocked site data)", () => {
    const broken = { getItem: () => { throw new Error("denied"); }, setItem: () => { throw new Error("denied"); } };
    expect(loadChoice(broken)).toBe("system");
    expect(() => saveChoice(broken, "light")).not.toThrow();
  });

  it("sets exactly one of the classes dark/light on <html>", () => {
    const root = document.documentElement;
    applyTheme(root, "dark");
    expect(root.classList.contains("dark")).toBe(true);
    expect(root.classList.contains("light")).toBe(false);
    applyTheme(root, "light");
    expect(root.classList.contains("light")).toBe(true);
    expect(root.classList.contains("dark")).toBe(false);
  });

  it("browserStorage is localStorage, or null where the browser forbids it", () => {
    expect(browserStorage()).toBe(window.localStorage);
    const spy = vi.spyOn(window, "localStorage", "get").mockImplementation(() => {
      throw new Error("blocked");
    });
    try {
      expect(browserStorage()).toBeNull();
    } finally {
      spy.mockRestore();
    }
  });
});

describe("currentTheme", () => {
  it("reads the resolved theme from the dark class that applyTheme sets", () => {
    const root = document.createElement("html");
    applyTheme(root, "dark");
    expect(currentTheme(root)).toBe("dark");
    applyTheme(root, "light");
    expect(currentTheme(root)).toBe("light");
  });
});
```

  `frontend/src/lib/notices.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import { MAX_SHOWN, addNotice, dismissNotice } from "./notices";

describe("notices", () => {
  it("shows the newest last and keeps at most three", () => {
    let shown = addNotice([], { kind: "info", text: "one" }, 1);
    for (const [i, text] of ["two", "three", "four"].entries()) {
      shown = addNotice(shown, { kind: "info", text }, i + 2);
    }
    expect(MAX_SHOWN).toBe(3);
    expect(shown.map((n) => n.text)).toEqual(["two", "three", "four"]);
  });

  it("doesn't show the same notice twice in a row", () => {
    const once = addNotice([], { kind: "error", text: "couldn't save" }, 1);
    expect(addNotice(once, { kind: "error", text: "couldn't save" }, 2)).toBe(once);
    expect(addNotice(once, { kind: "info", text: "couldn't save" }, 2)).toHaveLength(2);
  });

  it("ignores anything that isn't a notice, since it comes over the wire", () => {
    for (const junk of [null, "text", { kind: "warn", text: "x" }, { kind: "info", text: 3 }]) {
      expect(addNotice([], junk, 1)).toEqual([]);
    }
  });

  it("keeps only the fields it shows", () => {
    const [n] = addNotice([], { kind: "info", text: "ok", html: "<b>x</b>" }, 7);
    expect(n).toEqual({ kind: "info", text: "ok", id: 7 });
  });

  it("dismisses by id", () => {
    const shown = addNotice(addNotice([], { kind: "info", text: "a" }, 1), { kind: "info", text: "b" }, 2);
    expect(dismissNotice(shown, 1).map((n) => n.text)).toEqual(["b"]);
  });
});
```

  `frontend/src/components/TopBar.test.ts`:

```ts
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("./ThemeSwitch", () => ({ ThemeSwitch: () => null }));

import type { Status } from "@/types";

import { TopBar, endpointLabel } from "./TopBar";

describe("the top bar (spec §19.2)", () => {
  it("says which engine this is, from capabilities", () => {
    const caps = { engine: "local", generate: true, save: "disk", path_input: true } as const;
    expect(renderToStaticMarkup(createElement(TopBar, { capabilities: caps }))).toContain("Local engine");
    const browser = { ...caps, engine: "browser", save: "download" } as const;
    expect(renderToStaticMarkup(createElement(TopBar, { capabilities: browser }))).toContain("Browser editor");
  });

  it("names each endpoint's reach and key in words", () => {
    expect(endpointLabel({ name: "spark", local: true, key: "present", reachable: true })).toBe("spark: reachable, key set");
    expect(endpointLabel({ name: "spark", local: true, key: "missing", reachable: false })).toBe("spark: not reachable, key missing");
    expect(endpointLabel({ name: "spark", local: true, key: "none", reachable: null })).toBe("spark: checking…");
    expect(endpointLabel({ name: "openai", local: false, key: "present", reachable: null })).toBe("openai: cloud, key set");
  });

  it("shows an endpoint's name as text, never as markup", () => {
    const status: Status = { ffmpeg: true, endpoints: [{ name: "<img src=x onerror=alert(1)>", local: true, key: "none", reachable: true }] };
    const html = renderToStaticMarkup(createElement(TopBar, { status }));
    expect(html).not.toContain("<img");
    expect(html).toContain("&lt;img src=x onerror=alert(1)&gt;");
  });

  it("says when ffmpeg is missing", () => {
    expect(renderToStaticMarkup(createElement(TopBar, { status: { ffmpeg: false, endpoints: [] } }))).toContain("ffmpeg missing");
  });
});
```

  `frontend/src/build.test.ts` (recordings', with this repo's paths):

```ts
// @vitest-environment node
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import config, { EXTERNAL, GLOBALS } from "../vite.config.js";

describe("the build", () => {
  it("keeps React and react-dom/client external and bundles the react-dom index", () => {
    // why: shinyreact's ReactDOM global is react-dom/client only, with no createPortal or
    // flushSync (recordings' docs/upstream-issues.md). Mapping "react-dom" to it breaks every
    // portal (the plan's Global Constraints).
    expect(EXTERNAL).toEqual(["react", "react-dom/client"]);
    expect(GLOBALS).toEqual({
      react: "window.shinyreact.React",
      "react-dom/client": "window.shinyreact.ReactDOM",
    });
    type Rollup = { external: unknown; output: { globals: unknown } };
    const rollup = (config as unknown as { build: { rollupOptions: Rollup } }).build.rollupOptions;
    expect(rollup.external).toBe(EXTERNAL);
    expect(rollup.output.globals).toBe(GLOBALS);
  });
});

// why: the config test above checks what the build is told; this one checks what it made, as
// recordings' build.test.ts does. It reads the built www/ui.js (build output, not in git) and
// shinyreact.js from the project's venv. Where either is missing the checks skip, unless told they
// must run: CI=true (set by GitHub Actions) fails a missing ui.js, and
// VID2SUB_REQUIRE_SHINYREACT=1 (make check, and CI's job that has the venv) fails a missing
// shinyreact.js.
const here = dirname(fileURLToPath(import.meta.url));
const built = join(here, "../../src/vid2sub/web/www/ui.js");
const venvLib = join(here, "../../.venv/lib");
const mustBuild = Boolean(process.env.CI);
const mustHaveShinyreact = process.env.VID2SUB_REQUIRE_SHINYREACT === "1";

function shinyreactJs(): string | undefined {
  if (!existsSync(venvLib)) return undefined;
  for (const py of readdirSync(venvLib)) {
    const path = join(venvLib, py, "site-packages/shinyreact/www/shinyreact.js");
    if (existsSync(path)) return path;
  }
  return undefined;
}

const shinyreact = shinyreactJs();

describe.skipIf(!existsSync(built) && !mustBuild)("the built bundle", () => {
  const have = existsSync(built);
  const bundle = have ? readFileSync(built, "utf8") : "";

  it("exists (CI builds before it tests)", () => {
    expect(have, `${built} is missing: run npm run build first`).toBe(true);
  });

  it.skipIf(!have)("is called with the one React that shinyreact exposes, and carries no copy of its own", () => {
    expect(bundle.trimEnd().endsWith("(window.shinyreact.React);")).toBe(true);
    expect(bundle).not.toMatch(/react\.production/);
    expect(bundle).not.toMatch(/react-dom-client/);
    expect(bundle).not.toMatch(/scheduler\.production/);
    // the react-dom index is bundled on purpose (it has createPortal and flushSync)
    expect(bundle).toMatch(/react-dom\.production/);
  });

  it.skipIf(!have || (shinyreact === undefined && !mustHaveShinyreact))(
    "bundles a react-dom of the same major.minor as the React it runs beside",
    () => {
      expect(shinyreact, "shinyreact.js not found in .venv: run uv sync").toBeDefined();
      // react-dom's own version line follows its useHostTransitionStatus export; React's in
      // shinyreact.js is the one before `.exports=`.
      const mine = bundle.match(/useHostTransitionStatus\(\)\},\w+\.version="(\d+\.\d+)\.\d+"/)?.[1];
      const theirs = readFileSync(shinyreact as string, "utf8").match(/\.version="(\d+\.\d+)\.\d+",\w+\.exports=/)?.[1];
      expect(mine).toBeDefined();
      expect(theirs).toBeDefined();
      expect(mine).toBe(theirs);
    },
  );
});
```

  and `tests/test_brand.py`:

```python
"""The theme comes from _brand.yml, its text colours are readable in both modes, and NYC orange is
never a text colour (spec §19.3). Copied from recordings' packages/core/tests/test_brand.py at
8deb039, with this repo's paths."""

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def brand_css():
    spec = importlib.util.spec_from_file_location("brand_css", REPO / "scripts" / "brand_css.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def contrast(a: str, b: str) -> float:
    def lum(h):
        c = [int(h[i : i + 2], 16) / 255 for i in (1, 3, 5)]
        c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]

    hi, lo = sorted([lum(a), lum(b)], reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_theme_css_is_made_from_brand_yml():
    committed = (REPO / "frontend/src/theme.css").read_text(encoding="utf-8")
    assert committed == brand_css().render(REPO), "theme.css is stale: run `make brand`"


def test_text_colours_meet_wcag_aa_in_both_modes():
    module = brand_css()
    for mode in ("light", "dark"):
        t = module.tokens(REPO, mode)
        for fg in ("foreground", "muted-foreground", "primary"):
            for bg in ("background", "card", "muted", "sidebar"):
                assert contrast(t[fg], t[bg]) >= 4.5, f"{mode}: {fg} on {bg}"
        assert contrast(t["primary-foreground"], t["primary"]) >= 4.5, f"{mode}: button text"


def test_orange_is_never_a_light_mode_text_colour():
    # why: 3.2:1 on white, so it marks bars and backgrounds only (spec §19.3)
    assert contrast(brand_css().tokens(REPO, "light")["brand-orange"], "#FFFFFF") < 4.5
```

- [ ] **Step 2: Write the frontend's configuration and install its packages.** Every package is
  pinned exactly, as recordings' versions (packages/ui/frontend at 8deb039), less what this
  scaffold doesn't use yet (cmdk, sonner, @tanstack/react-virtual, axe-core: a later task adds
  what it needs).

  `frontend/package.json`:

```json
{
  "name": "vid2sub-frontend",
  "private": true,
  "type": "module",
  "engines": {
    "node": ">=22"
  },
  "scripts": {
    "preinstall": "node scripts/check-node.mjs",
    "prebuild": "node scripts/check-node.mjs",
    "build": "vite build",
    "dev": "vite build --watch",
    "typecheck": "tsc --noEmit",
    "test": "vitest run"
  },
  "devDependencies": {
    "@posit-dev/shinyreact": "0.1.1",
    "@tailwindcss/vite": "4.3.3",
    "@types/node": "22.20.5",
    "@types/react": "19.2.18",
    "@types/react-dom": "19.2.7",
    "@vitejs/plugin-react": "4.7.0",
    "jsdom": "30.1.2",
    "react": "19.2.8",
    "react-dom": "19.2.8",
    "tailwindcss": "4.3.3",
    "typescript": "5.9.3",
    "vite": "5.4.21",
    "vitest": "3.2.7"
  },
  "dependencies": {
    "class-variance-authority": "0.7.1",
    "cn": "0.4.0",
    "lucide-react": "1.55.0",
    "radix-ui": "1.8.1",
    "shadcn": "4.21.4",
    "tw-animate-css": "1.4.0"
  }
}
```

  `frontend/.nvmrc`:

```text
22
```

  `frontend/scripts/check-node.mjs`:

```js
// Fail fast on a Node older than 22: shinyreact builds and tests its JS with Node 22
// (pkg-js/.nvmrc), and Vite 5 and Vitest 3 need 18 or later. Newer majors are accepted: CI and
// .nvmrc pin 22, and a developer's Node may be ahead of it.
const major = Number(process.versions.node.split(".")[0]);
if (!(major >= 22)) {
  console.error(`Node 22 or later is required (found ${process.versions.node}). Run: nvm use`);
  process.exit(1);
}
```

  `frontend/vite.config.js`:

```js
import path from "node:path";
import { fileURLToPath } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// As recordings' vite.config.js (packages/ui/frontend at 8deb039). React stays external: `react`
// and `react-dom/client` come from window.shinyreact, so this bundle (shadcn's components
// included) shares the React instance that owns the shinyreact hooks; two copies leave the hooks
// silently empty. The `react-dom` INDEX module is bundled: shinyreact's ReactDOM global is
// react-dom/client only, without createPortal or flushSync, which Radix imports. That module
// requires `react`, which stays external, so there is still one React.
export const EXTERNAL = ["react", "react-dom/client"];
export const GLOBALS = {
  react: "window.shinyreact.React",
  "react-dom/client": "window.shinyreact.ReactDOM",
};

export default defineConfig({
  define: { "process.env.NODE_ENV": JSON.stringify("production") },
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  build: {
    // src/vid2sub/web/www/, which src/vid2sub/web/server.py serves (ui.js, ui.css).
    outDir: path.resolve(__dirname, "../src/vid2sub/web/www"),
    emptyOutDir: false, // www/ also holds the committed fonts
    cssCodeSplit: false,
    lib: {
      entry: path.resolve(__dirname, "src/ui.tsx"),
      formats: ["iife"],
      name: "Vid2subUI",
      fileName: () => "ui.js",
    },
    rollupOptions: {
      external: EXTERNAL,
      output: { assetFileNames: "ui.[ext]", globals: GLOBALS },
    },
  },
  test: { environment: "jsdom", include: ["src/**/*.test.ts"] },
});
```

  `frontend/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "jsx": "react-jsx",
    "strict": true,
    "allowJs": true,
    "noEmit": true,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "baseUrl": ".",
    "paths": { "@/*": ["./src/*"] }
  },
  "include": ["src"]
}
```

  `frontend/components.json`:

```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "radix-nova",
  "rsc": false,
  "tsx": true,
  "tailwind": {
    "config": "",
    "css": "src/index.css",
    "baseColor": "neutral",
    "cssVariables": true,
    "prefix": ""
  },
  "iconLibrary": "lucide",
  "rtl": false,
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils",
    "ui": "@/components/ui",
    "lib": "@/lib",
    "hooks": "@/hooks"
  },
  "menuColor": "default",
  "menuAccent": "subtle",
  "registries": {}
}
```


  Then `cd frontend && npm install --no-audit --no-fund` (Node 22 or later: `nvm use` reads
  `.nvmrc`). Expected: `added 492 packages`. It writes `frontend/package-lock.json`, which is
  committed.
- [ ] **Step 3: Run the tests; watch them fail.** `cd frontend && npx vitest run`. Expected:
  `FAIL  src/components/TopBar.test.ts`, `Error: Failed to resolve import "./TopBar" from
  "src/components/TopBar.test.ts". Does the file exist?`, and likewise `./notices` and `./theme`,
  then `Test Files  3 failed | 1 passed (4)`. And `uv run pytest tests/test_brand.py -q`:
  `E   FileNotFoundError: [Errno 2] No such file or directory: '…/scripts/brand_css.py'`, then
  `3 failed`.
- [ ] **Step 4: Write the code.**

  `frontend/src/sr.ts`:

```ts
// shinyreact's hooks, read from the window.shinyreact global the server loads (the
// shinyreact-build-app skill, Step 1), as recordings' sr.ts does. The npm package is imported for
// its TYPES only: `import type` is erased, so no second copy of React or the hooks can enter the
// bundle. Every output is subscribed, and every input and message handler lives, in App
// (shinyreact 0.1.0 drops a message that has no handler, and an unmounted output logs errors).
import type * as SR from "@posit-dev/shinyreact";

type Hooks = Pick<
  typeof SR,
  | "useShinyInput" | "useShinyOutputValue" | "useShinyOutputStatus" | "useShinyOutputError"
  | "useShinyInitialized" | "useSetShinyInput" | "useShinyMessageHandler"
>;

const shinyreact = (window as unknown as { shinyreact: Hooks }).shinyreact;

export const {
  useShinyInput, useShinyOutputValue, useShinyOutputStatus, useShinyOutputError,
  useShinyInitialized, useSetShinyInput, useShinyMessageHandler,
} = shinyreact;
```

  `frontend/src/types.ts`:

```ts
// The JSON the server sends: src/vid2sub/web/views.py makes each shape (spec §19.1).

/** Which controls exist: the local engine, or (Phase 4) the browser editor (spec §19.1). */
export type Capabilities = {
  engine: "local" | "browser";
  generate: boolean;
  save: "disk" | "download";
  path_input: boolean;
};

/** One endpoint from vid2sub.toml: a key by presence only, never its value (spec §19.2). */
export type EndpointStatus = {
  name: string;
  local: boolean;
  key: "present" | "missing" | "none";
  reachable: boolean | null; // null: a cloud endpoint (never contacted), or not checked yet
};

export type Status = { endpoints: EndpointStatus[]; ffmpeg: boolean };

/** The `notice` message: something to tell the person, as plain text. */
export type Notice = { kind: "info" | "error"; text: string };
```

  `frontend/src/ui.tsx`:

```tsx
import "@/index.css";
import "@/theme.css";

import App from "@/App";
import { applyTheme, browserStorage, loadChoice, resolveTheme } from "@/lib/theme";

const { ReactDOM } = (window as unknown as { shinyreact: { ReactDOM: typeof import("react-dom/client") } }).shinyreact;

// Apply the saved theme now, not when ThemeSwitch mounts after Shiny connects, so a saved
// light or dark choice never flashes the OS theme first (as recordings' ui.tsx does).
applyTheme(document.documentElement, resolveTheme(loadChoice(browserStorage()), window.matchMedia("(prefers-color-scheme: dark)").matches));

ReactDOM.createRoot(document.body.appendChild(document.createElement("div"))).render(<App />);
```

  `frontend/src/App.tsx`:

```tsx
import { useRef, useState } from "react";

import { TopBar } from "@/components/TopBar";
import { type Shown, addNotice, dismissNotice } from "@/lib/notices";
import { useShinyInitialized, useShinyMessageHandler, useShinyOutputValue } from "@/sr";
import type { Capabilities, Status } from "@/types";

export default function App() {
  const initialized = useShinyInitialized();
  // Every output is subscribed here, and every message handler lives here: shinyreact 0.1.0
  // drops a message that has no handler, and an output that unmounts logs "Output <id> not found"
  // for each later value (recordings' App.tsx). A new output or message gets a line here too.
  const capabilities = useShinyOutputValue<Capabilities>("capabilities");
  const status = useShinyOutputValue<Status>("status");
  const [notices, setNotices] = useState<Shown[]>([]);
  const nextId = useRef(1);
  useShinyMessageHandler("notice", (data: unknown) => {
    setNotices((shown) => addNotice(shown, data, nextId.current++));
  });

  if (!initialized) return null; // no flash of empty defaults while connecting
  return (
    <div className="flex h-dvh flex-col" data-testid="app">
      <TopBar capabilities={capabilities} status={status} />
      <main className="flex flex-1 items-center justify-center text-muted-foreground" data-testid="main">
        <p>The editor opens here.</p>
      </main>
      <section aria-label="Notices" className="fixed right-4 bottom-4 z-[99999] flex w-80 flex-col gap-2">
        <div role="status" aria-live="polite" className="flex flex-col gap-2">
          {notices.filter((n) => n.kind === "info").map((n) => <NoticeCard key={n.id} notice={n} onDismiss={setNotices} />)}
        </div>
        <div role="alert" className="flex flex-col gap-2">
          {notices.filter((n) => n.kind === "error").map((n) => <NoticeCard key={n.id} notice={n} onDismiss={setNotices} />)}
        </div>
      </section>
    </div>
  );
}

function NoticeCard({ notice, onDismiss }: { notice: Shown; onDismiss: (f: (s: Shown[]) => Shown[]) => void }) {
  return (
    <div className={`flex items-start gap-2 rounded-lg border bg-card p-3 text-sm shadow ${notice.kind === "error" ? "border-destructive text-destructive" : "border-border"}`} data-testid="notice">
      {/* Plain text: a notice can carry a file name or a server's error (spec §6.3). */}
      <span className="flex-1">{notice.text}</span>
      <button type="button" aria-label="Dismiss" onClick={() => onDismiss((s) => dismissNotice(s, notice.id))}>×</button>
    </div>
  );
}
```

  `frontend/src/index.css`:

```css
/* shadcn/ui's tokens (radix-nova), as recordings' index.css (8deb039); the colours come from
   theme.css, made from _brand.yml. The fonts are the engine's own files, never a CDN (spec §6.3,
   §19.3): /fonts/ is src/vid2sub/web/www/fonts/. */
@import "tailwindcss";
@import "tw-animate-css";
@import "shadcn/tailwind.css";

@custom-variant dark (&:is(.dark *));

@font-face { font-family: "Atkinson Hyperlegible"; src: url("/fonts/AtkinsonHyperlegible-Regular.woff2") format("woff2"); font-weight: 400; font-style: normal; font-display: swap; }
@font-face { font-family: "Atkinson Hyperlegible"; src: url("/fonts/AtkinsonHyperlegible-Italic.woff2") format("woff2"); font-weight: 400; font-style: italic; font-display: swap; }
@font-face { font-family: "Atkinson Hyperlegible"; src: url("/fonts/AtkinsonHyperlegible-Bold.woff2") format("woff2"); font-weight: 700; font-style: normal; font-display: swap; }
@font-face { font-family: "Atkinson Hyperlegible"; src: url("/fonts/AtkinsonHyperlegible-BoldItalic.woff2") format("woff2"); font-weight: 700; font-style: italic; font-display: swap; }
@font-face { font-family: "Atkinson Hyperlegible Mono"; src: url("/fonts/AtkinsonHyperlegibleMono-Regular.woff2") format("woff2"); font-weight: 400; font-display: swap; }
@font-face { font-family: "Atkinson Hyperlegible Mono"; src: url("/fonts/AtkinsonHyperlegibleMono-Bold.woff2") format("woff2"); font-weight: 700; font-display: swap; }

@theme inline {
    --font-heading: var(--font-sans);
    --font-sans: "Atkinson Hyperlegible", system-ui, sans-serif;
    --font-mono: "Atkinson Hyperlegible Mono", ui-monospace, monospace;
    --color-sidebar-ring: var(--sidebar-ring);
    --color-sidebar-border: var(--sidebar-border);
    --color-sidebar-accent-foreground: var(--sidebar-accent-foreground);
    --color-sidebar-accent: var(--sidebar-accent);
    --color-sidebar-primary-foreground: var(--sidebar-primary-foreground);
    --color-sidebar-primary: var(--sidebar-primary);
    --color-sidebar-foreground: var(--sidebar-foreground);
    --color-sidebar: var(--sidebar);
    --color-chart-5: var(--chart-5);
    --color-chart-4: var(--chart-4);
    --color-chart-3: var(--chart-3);
    --color-chart-2: var(--chart-2);
    --color-chart-1: var(--chart-1);
    --color-ring: var(--ring);
    --color-input: var(--input);
    --color-border: var(--border);
    --color-destructive: var(--destructive);
    --color-accent-foreground: var(--accent-foreground);
    --color-accent: var(--accent);
    --color-muted-foreground: var(--muted-foreground);
    --color-muted: var(--muted);
    --color-secondary-foreground: var(--secondary-foreground);
    --color-secondary: var(--secondary);
    --color-primary-foreground: var(--primary-foreground);
    --color-primary: var(--primary);
    --color-popover-foreground: var(--popover-foreground);
    --color-popover: var(--popover);
    --color-card-foreground: var(--card-foreground);
    --color-card: var(--card);
    --color-foreground: var(--foreground);
    --color-background: var(--background);
    --radius-sm: calc(var(--radius) * 0.6);
    --radius-md: calc(var(--radius) * 0.8);
    --radius-lg: var(--radius);
    --radius-xl: calc(var(--radius) * 1.4);
    --radius-2xl: calc(var(--radius) * 1.8);
    --radius-3xl: calc(var(--radius) * 2.2);
    --radius-4xl: calc(var(--radius) * 2.6);
}

:root {
    --background: oklch(1 0 0);
    --foreground: oklch(0.145 0 0);
    --card: oklch(1 0 0);
    --card-foreground: oklch(0.145 0 0);
    --popover: oklch(1 0 0);
    --popover-foreground: oklch(0.145 0 0);
    --primary: oklch(0.205 0 0);
    --primary-foreground: oklch(0.985 0 0);
    --secondary: oklch(0.97 0 0);
    --secondary-foreground: oklch(0.205 0 0);
    --muted: oklch(0.97 0 0);
    --muted-foreground: oklch(0.556 0 0);
    --accent: oklch(0.97 0 0);
    --accent-foreground: oklch(0.205 0 0);
    --destructive: oklch(0.577 0.245 27.325);
    --border: oklch(0.922 0 0);
    --input: oklch(0.922 0 0);
    --ring: oklch(0.708 0 0);
    --chart-1: oklch(0.87 0 0);
    --chart-2: oklch(0.556 0 0);
    --chart-3: oklch(0.439 0 0);
    --chart-4: oklch(0.371 0 0);
    --chart-5: oklch(0.269 0 0);
    --radius: 0.625rem;
    --sidebar: oklch(0.985 0 0);
    --sidebar-foreground: oklch(0.145 0 0);
    --sidebar-primary: oklch(0.205 0 0);
    --sidebar-primary-foreground: oklch(0.985 0 0);
    --sidebar-accent: oklch(0.97 0 0);
    --sidebar-accent-foreground: oklch(0.205 0 0);
    --sidebar-border: oklch(0.922 0 0);
    --sidebar-ring: oklch(0.708 0 0);
}

.dark {
    --background: oklch(0.145 0 0);
    --foreground: oklch(0.985 0 0);
    --card: oklch(0.205 0 0);
    --card-foreground: oklch(0.985 0 0);
    --popover: oklch(0.205 0 0);
    --popover-foreground: oklch(0.985 0 0);
    --primary: oklch(0.922 0 0);
    --primary-foreground: oklch(0.205 0 0);
    --secondary: oklch(0.269 0 0);
    --secondary-foreground: oklch(0.985 0 0);
    --muted: oklch(0.269 0 0);
    --muted-foreground: oklch(0.708 0 0);
    --accent: oklch(0.269 0 0);
    --accent-foreground: oklch(0.985 0 0);
    --destructive: oklch(0.704 0.191 22.216);
    --border: oklch(1 0 0 / 10%);
    --input: oklch(1 0 0 / 15%);
    --ring: oklch(0.556 0 0);
    --chart-1: oklch(0.87 0 0);
    --chart-2: oklch(0.556 0 0);
    --chart-3: oklch(0.439 0 0);
    --chart-4: oklch(0.371 0 0);
    --chart-5: oklch(0.269 0 0);
    --sidebar: oklch(0.205 0 0);
    --sidebar-foreground: oklch(0.985 0 0);
    --sidebar-primary: oklch(0.488 0.243 264.376);
    --sidebar-primary-foreground: oklch(0.985 0 0);
    --sidebar-accent: oklch(0.269 0 0);
    --sidebar-accent-foreground: oklch(0.985 0 0);
    --sidebar-border: oklch(1 0 0 / 10%);
    --sidebar-ring: oklch(0.556 0 0);
}

@layer base {
  * {
    @apply border-border outline-ring/50;
    }
  body {
    @apply bg-background text-foreground;
    }
  html {
    @apply font-sans;
    }
}
```

  `frontend/src/lib/utils.ts`:

```ts
export { cn } from "cn"
```

  `frontend/src/lib/theme.ts`:

```ts
export type ThemeChoice = "light" | "dark" | "system";
export type Resolved = "light" | "dark";

const KEY = "vid2sub.theme";
type Storage = { getItem(k: string): string | null; setItem(k: string, v: string): void };

export function resolveTheme(choice: ThemeChoice, prefersDark: boolean): Resolved {
  return choice === "system" ? (prefersDark ? "dark" : "light") : choice;
}

export function loadChoice(storage: Storage | null): ThemeChoice {
  try {
    const v = storage?.getItem(KEY);
    return v === "light" || v === "dark" || v === "system" ? v : "system";
  } catch {
    return "system"; // storage can throw in private windows; the theme must still work
  }
}

export function saveChoice(storage: Storage | null, choice: ThemeChoice): void {
  try {
    storage?.setItem(KEY, choice);
  } catch {
    /* a per-browser convenience only; nothing else depends on it */
  }
}

/** shadcn's convention: the `dark` class on <html>. `light` is set too, so theme.css can tell
 * "the user chose light" from "nothing chosen yet, follow the OS". */
export function applyTheme(root: HTMLElement, resolved: Resolved): void {
  root.classList.toggle("dark", resolved === "dark");
  root.classList.toggle("light", resolved === "light");
}

/** localStorage, or null where the browser forbids it (private windows, blocked site data). */
export function browserStorage(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

/** The theme applyTheme last set on `root`: the `dark` class, or light. */
export function currentTheme(root: HTMLElement): Resolved {
  return root.classList.contains("dark") ? "dark" : "light";
}
```

  `frontend/src/lib/notices.ts`:

```ts
import type { Notice } from "@/types";

/** A notice on screen, with an id to dismiss it by. */
export type Shown = Notice & { id: number };

export const MAX_SHOWN = 3;

/** The notices after one more arrives: newest last, at most MAX_SHOWN, and a notice that repeats
 * the newest one isn't shown twice. Anything that isn't a well-formed notice is ignored, since it
 * comes over the wire. */
export function addNotice(shown: Shown[], notice: unknown, id: number): Shown[] {
  if (!isNotice(notice)) return shown;
  const last = shown[shown.length - 1];
  if (last && last.kind === notice.kind && last.text === notice.text) return shown;
  return [...shown, { kind: notice.kind, text: notice.text, id }].slice(-MAX_SHOWN);
}

export function dismissNotice(shown: Shown[], id: number): Shown[] {
  return shown.filter((n) => n.id !== id);
}

function isNotice(value: unknown): value is Notice {
  if (typeof value !== "object" || value === null) return false;
  const { kind, text } = value as Record<string, unknown>;
  return (kind === "info" || kind === "error") && typeof text === "string";
}
```

  `frontend/src/components/TopBar.tsx`:

```tsx
import type { Capabilities, EndpointStatus, Status } from "@/types";

import { ThemeSwitch } from "./ThemeSwitch";

const ENGINE: Record<Capabilities["engine"], string> = {
  local: "Local engine",
  browser: "Browser editor",
};

/** One endpoint in words, not colour alone: reachable or not (cloud ones are never contacted),
 * and its key by presence only (spec §19.2). */
export function endpointLabel(e: EndpointStatus): string {
  const reach = e.reachable === null ? (e.local ? "checking…" : "cloud") : e.reachable ? "reachable" : "not reachable";
  const key = e.key === "none" ? "" : e.key === "present" ? ", key set" : ", key missing";
  return `${e.name}: ${reach}${key}`;
}

/** Which engine this is (from `capabilities`, not a toggle), the engine's status, and the theme
 * switch (spec §19.2). */
export function TopBar({ capabilities, status }: { capabilities?: Capabilities; status?: Status }) {
  return (
    <header className="flex items-center gap-4 border-b border-border bg-card px-4 py-2" data-testid="topbar">
      <span className="flex items-center gap-2 font-bold">
        <i aria-hidden className="inline-block size-2.5 rounded-full bg-(--brand-orange)" />
        vid2sub
      </span>
      {capabilities && <span className="text-sm text-muted-foreground" data-testid="engine">{ENGINE[capabilities.engine]}</span>}
      {status && (
        <ul className="flex flex-wrap gap-2 text-sm" aria-label="Engine status" data-testid="status">
          {!status.ffmpeg && <li className="rounded-full bg-muted px-2 text-destructive">ffmpeg missing</li>}
          {status.endpoints.map((e) => (
            <li key={e.name} className="rounded-full bg-muted px-2" data-testid="endpoint">{endpointLabel(e)}</li>
          ))}
        </ul>
      )}
      <ThemeSwitch />
    </header>
  );
}
```

  `frontend/src/components/ThemeSwitch.tsx`:

```tsx
import { Monitor, Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";

import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { applyTheme, browserStorage, loadChoice, resolveTheme, saveChoice, type ThemeChoice } from "@/lib/theme";

export function ThemeSwitch() {
  const [choice, setChoice] = useState<ThemeChoice>(() => loadChoice(browserStorage()));

  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const sync = () => applyTheme(document.documentElement, resolveTheme(choice, media.matches));
    sync();
    media.addEventListener("change", sync);
    return () => media.removeEventListener("change", sync);
  }, [choice]);

  return (
    <ToggleGroup
      type="single"
      size="sm"
      variant="outline"
      className="ml-auto"
      value={choice}
      aria-label="Colour theme"
      onValueChange={(v) => {
        if (!v) return; // Radix sends "" when the active item is clicked again
        setChoice(v as ThemeChoice);
        saveChoice(browserStorage(), v as ThemeChoice);
      }}
    >
      <ToggleGroupItem value="light" aria-label="Light" data-testid="theme-light"><Sun /></ToggleGroupItem>
      <ToggleGroupItem value="system" aria-label="System" data-testid="theme-system"><Monitor /></ToggleGroupItem>
      <ToggleGroupItem value="dark" aria-label="Dark" data-testid="theme-dark"><Moon /></ToggleGroupItem>
    </ToggleGroup>
  );
}
```

  `frontend/src/components/ui/toggle.tsx`:

```tsx
"use client"

import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "cn"
import { Toggle as TogglePrimitive } from "radix-ui"

const toggleVariants = cva(
  "group/toggle inline-flex items-center justify-center gap-1 rounded-lg text-sm font-medium whitespace-nowrap transition-all outline-none hover:bg-muted hover:text-foreground focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:pointer-events-none disabled:opacity-50 aria-invalid:border-destructive aria-invalid:ring-destructive/20 aria-pressed:bg-muted data-[state=on]:bg-muted dark:aria-invalid:ring-destructive/40 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        default: "bg-transparent",
        outline: "border border-input bg-transparent hover:bg-muted",
      },
      size: {
        default:
          "h-8 min-w-8 px-2.5 has-data-[icon=inline-end]:pr-2 has-data-[icon=inline-start]:pl-2",
        sm: "h-7 min-w-7 rounded-[min(var(--radius-md),12px)] px-2.5 text-[0.8rem] has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-1.5 [&_svg:not([class*='size-'])]:size-3.5",
        lg: "h-9 min-w-9 px-2.5 has-data-[icon=inline-end]:pr-2 has-data-[icon=inline-start]:pl-2",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

function Toggle({
  className,
  variant = "default",
  size = "default",
  ...props
}: React.ComponentProps<typeof TogglePrimitive.Root> &
  VariantProps<typeof toggleVariants>) {
  return (
    <TogglePrimitive.Root
      data-slot="toggle"
      className={cn(toggleVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Toggle, toggleVariants }
```

  `frontend/src/components/ui/toggle-group.tsx`:

```tsx
import * as React from "react"
import { type VariantProps } from "class-variance-authority"
import { cn } from "cn"
import { ToggleGroup as ToggleGroupPrimitive } from "radix-ui"

import { toggleVariants } from "@/components/ui/toggle"

const ToggleGroupContext = React.createContext<
  VariantProps<typeof toggleVariants> & {
    spacing?: number
    orientation?: "horizontal" | "vertical"
  }
>({
  size: "default",
  variant: "default",
  spacing: 2,
  orientation: "horizontal",
})

function ToggleGroup({
  className,
  variant,
  size,
  spacing = 2,
  orientation = "horizontal",
  children,
  ...props
}: React.ComponentProps<typeof ToggleGroupPrimitive.Root> &
  VariantProps<typeof toggleVariants> & {
    spacing?: number
    orientation?: "horizontal" | "vertical"
  }) {
  return (
    <ToggleGroupPrimitive.Root
      data-slot="toggle-group"
      data-variant={variant}
      data-size={size}
      data-spacing={spacing}
      data-orientation={orientation}
      style={{ "--gap": spacing } as React.CSSProperties}
      className={cn(
        "group/toggle-group flex w-fit flex-row items-center gap-[--spacing(var(--gap))] rounded-lg data-[size=sm]:rounded-[min(var(--radius-md),10px)] data-vertical:flex-col data-vertical:items-stretch",
        className
      )}
      {...props}
    >
      <ToggleGroupContext.Provider
        value={{ variant, size, spacing, orientation }}
      >
        {children}
      </ToggleGroupContext.Provider>
    </ToggleGroupPrimitive.Root>
  )
}

function ToggleGroupItem({
  className,
  children,
  variant = "default",
  size = "default",
  ...props
}: React.ComponentProps<typeof ToggleGroupPrimitive.Item> &
  VariantProps<typeof toggleVariants>) {
  const context = React.useContext(ToggleGroupContext)

  return (
    <ToggleGroupPrimitive.Item
      data-slot="toggle-group-item"
      data-variant={context.variant || variant}
      data-size={context.size || size}
      data-spacing={context.spacing}
      className={cn(
        "shrink-0 group-data-[spacing=0]/toggle-group:rounded-none group-data-[spacing=0]/toggle-group:px-2 focus:z-10 focus-visible:z-10 group-data-[spacing=0]/toggle-group:has-data-[icon=inline-end]:pr-1.5 group-data-[spacing=0]/toggle-group:has-data-[icon=inline-start]:pl-1.5 group-data-horizontal/toggle-group:data-[spacing=0]:first:rounded-l-lg group-data-vertical/toggle-group:data-[spacing=0]:first:rounded-t-lg group-data-horizontal/toggle-group:data-[spacing=0]:last:rounded-r-lg group-data-vertical/toggle-group:data-[spacing=0]:last:rounded-b-lg group-data-horizontal/toggle-group:data-[spacing=0]:data-[variant=outline]:border-l-0 group-data-vertical/toggle-group:data-[spacing=0]:data-[variant=outline]:border-t-0 group-data-horizontal/toggle-group:data-[spacing=0]:data-[variant=outline]:first:border-l group-data-vertical/toggle-group:data-[spacing=0]:data-[variant=outline]:first:border-t",
        toggleVariants({
          variant: context.variant || variant,
          size: context.size || size,
        }),
        className
      )}
      {...props}
    >
      {children}
    </ToggleGroupPrimitive.Item>
  )
}

export { ToggleGroup, ToggleGroupItem }
```

  `_brand.yml` (recordings', renamed):

```yaml
# vid2sub's theme, from recordings' _brand.yml (8deb039): NYC blue is the working colour and NYC
# orange the accent, on warm neutrals (spec §19.3). Every colour that differs between modes is
# {light, dark}. scripts/brand_css.py turns this into shadcn/ui's CSS variables.
meta:
  name: vid2sub
color:
  palette:
    nyc-blue: "#236192"
    nyc-blue-light: "#6CA6D9"   # #236192 is only 2.8:1 on the dark base
    nyc-orange: "#F26522"
    warm-white: "#F8F6F2"
    paper: "#FFFDFA"
    linen: "#EFE8DF"
    sand: "#E8DDD2"
    hairline: "#E0D6CB"
    warm-gray: "#6B6258"
    near-black: "#1C1A17"
    green-text: "#3D6123"
    burgundy: "#9A4665"
    dark-base: "#171512"
    dark-surface: "#232019"
    dark-side: "#1C1A16"
    dark-hairline: "#2E2B26"
    stone: "#B8AEA2"
    green-light: "#9CC27A"
    rose: "#D27A9A"
  foreground: { light: near-black, dark: warm-white }
  background: { light: warm-white, dark: dark-base }
  primary: { light: nyc-blue, dark: nyc-blue-light }
  secondary: { light: warm-gray, dark: stone }
  tertiary: { light: linen, dark: dark-side }
  success: { light: green-text, dark: green-light }
  warning: nyc-orange
  danger: { light: burgundy, dark: rose }
  light: { light: paper, dark: dark-surface }
  dark: { light: near-black, dark: warm-white }
typography:
  base: Atkinson Hyperlegible
  monospace: Atkinson Hyperlegible Mono
```

  `scripts/brand_css.py` (recordings', writing `frontend/src/theme.css`):

```python
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml==6.0.3"]
# ///
"""Generate frontend/src/theme.css (shadcn/ui's CSS variables) from _brand.yml (spec §19.3).

    make brand        (uv run scripts/brand_css.py)

Copied from recordings' scripts/brand_css.py at 8deb039, with the output path changed.
_brand.yml uses brand.yml's {light, dark} colour objects; this reads them directly, so the
R/Python brand_yml packages (which don't read that form) are not involved.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "frontend" / "src" / "theme.css"

# Roles brand.yml has no theme key for: a palette name per mode.
EXTRA = {
    "chip": {"light": "sand", "dark": "dark-hairline"},
    "hairline": {"light": "hairline", "dark": "dark-hairline"},
}
# shadcn token -> brand.yml theme key, or extra:<role>
TOKENS = {
    "background": "background",
    "foreground": "foreground",
    "card": "light",
    "card-foreground": "foreground",
    "popover": "light",
    "popover-foreground": "foreground",
    "primary": "primary",
    "primary-foreground": "background",
    "secondary": "extra:chip",
    "secondary-foreground": "foreground",
    "muted": "tertiary",
    "muted-foreground": "secondary",
    "accent": "extra:chip",
    "accent-foreground": "foreground",
    "destructive": "danger",
    "border": "extra:hairline",
    "input": "extra:hairline",
    "ring": "primary",
    "sidebar": "tertiary",
    "sidebar-foreground": "foreground",
    "sidebar-primary": "primary",
    "sidebar-primary-foreground": "background",
    "sidebar-accent": "extra:chip",
    "sidebar-accent-foreground": "foreground",
    "sidebar-border": "extra:hairline",
    "sidebar-ring": "primary",
    "brand-orange": "warning",
    "brand-success": "success",
}


def _resolve(palette: dict, value, mode: str) -> str:
    if isinstance(value, dict):
        value = value[mode]
    seen = set()
    while value in palette and value not in seen:  # palette entries may alias each other
        seen.add(value)
        value = palette[value]
    return value


def tokens(repo: Path, mode: str) -> dict[str, str]:
    color = yaml.safe_load((repo / "_brand.yml").read_text(encoding="utf-8"))["color"]
    out = {}
    for name, ref in TOKENS.items():
        value = EXTRA[ref.removeprefix("extra:")][mode] if ref.startswith("extra:") else color[ref]
        out[name] = _resolve(color["palette"], value, mode)
    return out


def _block(selector: str, values: dict[str, str], scheme: str, indent: str = "") -> str:
    lines = [
        f"{indent}{selector} {{",
        f"{indent}  color-scheme: {scheme};",
        f"{indent}  --radius: 0.5rem;",
    ]
    lines += [f"{indent}  --{k}: {v};" for k, v in values.items()]
    return "\n".join([*lines, f"{indent}}}"])


def render(repo: Path) -> str:
    light, dark = tokens(repo, "light"), tokens(repo, "dark")
    return "\n".join(
        [
            "/* Generated by scripts/brand_css.py from _brand.yml. Do not edit. */",
            _block(":root", light, "light"),
            _block(".dark", dark, "dark"),
            "/* Before the app picks a mode (class light/dark on <html>), follow the OS. */",
            "@media (prefers-color-scheme: dark) {",
            _block(":root:not(.light):not(.dark)", dark, "dark", indent="  "),
            "}",
            "",
        ]
    )


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(REPO), encoding="utf-8")
    print(f"wrote {OUT}", file=sys.stderr)
```

  Then `uv run scripts/brand_css.py`, which writes `frontend/src/theme.css` (it matches
  recordings' `packages/ui/frontend/src/theme.css` byte for byte).

  The fonts, recordings' files (SIL Open Font License): `mkdir -p src/vid2sub/web/www/fonts`, then
  for each file `git -C <recordings> show
  8deb039:packages/ui/src/recordings_ui/www/fonts/<file> > src/vid2sub/web/www/fonts/<file>`.
  Their SHA-256 (`shasum -a 256`):

  - `AtkinsonHyperlegible-Bold.woff2`: `943b7aaf5db6e9fc77ad55d62dc788905a1d1b42a49b5d5a28200c1a1e0db852`
  - `AtkinsonHyperlegible-BoldItalic.woff2`: `70fc038d31c1c1c188cd10387e7746b03e85470b7bf29783ee8d3c895cf104d9`
  - `AtkinsonHyperlegible-Italic.woff2`: `43dc4dde8cc93427a06b068564428c346539c09742009251577d012a816e49d9`
  - `AtkinsonHyperlegible-Regular.woff2`: `6d00e3139d1c29dcc16f0b194c8ec39b6a0dca5754e61f1f3e9f148aeb3e66d6`
  - `AtkinsonHyperlegibleMono-Bold.woff2`: `d5a9e53e9534f79bc34454a1bc30ee69a344355eb0f1ed88002c9c43af80ffe9`
  - `AtkinsonHyperlegibleMono-Regular.woff2`: `89eda5637b138b054617259cbd88ec85cb01337c8f761ac73dc48edff6c4444f`
  - `OFL.txt`: `f32d22b3908fcad2c86a74000614ec22e6a7f66ea7e867e616026a27aebdc143`

  In `pyproject.toml`'s dev group, replace

```toml
    "pytest-playwright==0.10.0",  # the editor's browser tests (spec §22.7), as recordings pins it
]
```

  with

```toml
    "pytest-playwright==0.10.0",  # the editor's browser tests (spec §22.7), as recordings pins it
    "pyyaml==6.0.3",  # tests/test_brand.py reads _brand.yml, as scripts/brand_css.py does
]
```

  then `uv lock` (Expected: `Resolved 107 packages`) and `uv sync --group dev` (`+ pyyaml==6.0.3`).

  In the `Makefile`, replace the first lines,

```make
.PHONY: setup test test-utc lint leaks check hooks live readme help

setup: ## Install the dev environment
	uv sync --group dev
```

  with

```make
.PHONY: setup build test test-utc test-js lint leaks check hooks live readme brand skills help

FRONTEND := frontend
# Each recipe line runs in its own shell, so nvm is loaded per line when it is there, and switched
# to the Node in frontend/.nvmrc (as recordings' Makefile does). Without nvm (CI), whatever Node is
# on PATH runs, and frontend/scripts/check-node.mjs refuses one older than 22.
NVM := if [ -s "$$HOME/.nvm/nvm.sh" ]; then . "$$HOME/.nvm/nvm.sh" && nvm use --silent "$$(cat $(CURDIR)/$(FRONTEND)/.nvmrc)"; fi;

setup: ## Install the dev environment, the frontend's packages included
	uv sync --group dev
	cd $(FRONTEND) && $(NVM) npm ci

build: ## Build the frontend into src/vid2sub/web/www/ (vid2sub serve needs it)
	cd $(FRONTEND) && $(NVM) npm run build
```

  Below `test-utc`'s recipe, replace

```make
lint: ## Lint with ruff
```

  with

```make
test-js: ## Typecheck the frontend and run its Vitest tests
	cd $(FRONTEND) && $(NVM) npm run typecheck && VID2SUB_REQUIRE_SHINYREACT=1 npm test

lint: ## Lint with ruff
```

  replace `check`'s line

```make
check: test test-utc lint leaks ## Everything CI checks: the suite, again under UTC, lint, leaks
```

  with

```make
check: test test-utc test-js lint leaks ## Everything CI checks: the suite, again under UTC, the frontend's tests, lint, leaks
```

  and replace `help`'s first line

```make
help: ## List the targets
```

  with

```make
brand: ## Regenerate frontend/src/theme.css from _brand.yml
	uv run scripts/brand_css.py

skills: ## Install the shinyreact and shadcn agent skills (local tooling, never committed)
	uvx library-skills install --claude --yes --skill shinyreact-build-app --skill shinyreact-convert-app
	$(NVM) npx skills add shadcn/ui --skill shadcn --agent claude-code --yes

help: ## List the targets
```

  At the end of `.gitignore`, add:

```text
# The frontend: its packages, and its build output in www/ (make build). The fonts are committed.
frontend/node_modules/
src/vid2sub/web/www/ui.js
src/vid2sub/web/www/ui.css
# The Python template's lib/ above would hide the frontend's own lib/.
!frontend/src/lib/
# Agent skills are local tooling, made again by make skills.
.claude/skills/
.agents/
skills-lock.json
```

- [ ] **Step 5: Run the checks; they pass.** `make setup` (npm ci under nvm's Node 22), then
  `make build`. Expected, among its lines: `../src/vid2sub/web/www/ui.css  22.62 kB`,
  `../src/vid2sub/web/www/ui.js   71.15 kB`, `✓ built in` (Vite also says each `/fonts/…` URL
  "didn't resolve at build time, it will remain unchanged to be resolved at runtime", which is
  meant: the engine serves `www/` at "/"). `make test-js`. Expected: `Test Files  4 passed (4)`,
  `Tests  19 passed (19)`. `make check`. Expected: `917 passed, 2 skipped, 4 deselected` twice,
  the Vitest lines again, `All checks passed!`, `no leaks found`. `make help` lists `build`,
  `test-js`, `brand` and `skills`. `git check-ignore -v frontend/src/lib/theme.ts` prints nothing
  (the template's `lib/` no longer hides it); `src/vid2sub/web/www/ui.js` and
  `frontend/node_modules` are ignored. `make skills` isn't run here (it fetches agent tooling).
- [ ] **Step 6: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(frontend): 🤖 the editor's frontend builds into src/vid2sub/web/www/ with React kept external, the brand's theme and fonts served locally

frontend/ is recordings' scaffold (packages/ui/frontend at 8deb039): a Vite 5 library build
(IIFE) of src/ui.tsx into src/vid2sub/web/www/ui.js and ui.css, with react and react-dom/client
external as window.shinyreact.React and ReactDOM and the react-dom index bundled (createPortal,
flushSync); TypeScript 5.9, Tailwind 4, shadcn radix-nova (components.json; toggle and
toggle-group copied as shadcn's add command wrote them for recordings), Vitest 3 in jsdom. Every
package is pinned exactly. sr.ts re-exports shinyreact's hooks from the global, the npm package
imported for its types only. App subscribes every output (capabilities, status) and holds the
notice handler, as shinyreact 0.1.0 needs; notices are plain text, newest last, three at most,
info in a polite live region and errors in an alert (spec §19.3). TopBar says which engine this
is from capabilities and each endpoint's reach and key in words (spec §19.2); ThemeSwitch and
lib/theme.ts are recordings', with the key vid2sub.theme. scripts/check-node.mjs accepts Node 22
or later (.nvmrc says 22; this machine runs 25). _brand.yml and scripts/brand_css.py are
recordings', writing frontend/src/theme.css; tests/test_brand.py (recordings') checks it is up to
date, that text meets WCAG AA in both modes and that NYC orange is never a text colour (spec
§19.3), with pyyaml 6.0.3 in the dev group to read _brand.yml. The Atkinson Hyperlegible fonts
(OFL) are recordings' files in src/vid2sub/web/www/fonts/. The Makefile gains setup's npm ci,
build, test-js (in check), brand and skills, loading nvm per line as recordings does;
.gitignore keeps node_modules and the build output out, and lets frontend/src/lib/ past the
Python template's lib/.

The new tests failed first with: Error: Failed to resolve import "./theme" from
"src/lib/theme.test.ts". Does the file exist? (and likewise ./notices and ./TopBar: Test Files
3 failed | 1 passed), and tests/test_brand.py with FileNotFoundError (3 failed).

Docs read: Vite 5's library-mode and build options (build.lib formats and fileName,
rollupOptions external and output.globals, cssCodeSplit, emptyOutDir); Tailwind 4's Vite plugin
and @import "tailwindcss"; shadcn's components.json; Vitest 3's environment option and
describe.skipIf; shinyreact 0.1.0's _page.py and _dep.py (page_react serves ui.js as a module
script and ui.css, versioned by ui.js's mtime) and its window.shinyreact global.

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 12
Co-Authored-By: <the model's own line>
```

  `git add frontend _brand.yml scripts/brand_css.py src/vid2sub/web/www/fonts Makefile .gitignore
  pyproject.toml uv.lock tests/test_brand.py` (`git status --short` then shows no
  `node_modules`, `ui.js` or `ui.css`), `git commit -F .git/COMMIT_MSG`, then
  `git log -1 --format='%(trailers)'` shows `Plan:`.

#### Round 12b: the shinyreact server, and a page the CSP allows

- [ ] **Step 7: Write the failing test,** `tests/test_web_server.py`:

```python
"""The Shiny server for the React frontend: its page runs no inline script or style, so the spec's
CSP allows all of it; `capabilities` and `status` are JSON outputs, with keys by presence only;
and `notice` is a shinyreact message (spec §19.1, §19.2, §6.3; S26)."""

import asyncio
import json
import re
import threading

import pytest
from starlette.testclient import TestClient

from vid2sub.cache import Cache
from vid2sub.config import Config
from vid2sub.engines import clients
from vid2sub.engines.base import EngineError
from vid2sub.engines.clients import KeyRing
from vid2sub.media.tools import Tools
from vid2sub.web import runtime, server, views
from vid2sub.web.app import create_app
from vid2sub.web.guards import CSP

PORT = 8765
TOKEN = "t" * 43  # as long as a real token, and plainly not one (the leak scan agrees)
BASE = f"http://127.0.0.1:{PORT}"
WS = f"ws://127.0.0.1:{PORT}/websocket/"
JSON = {"Content-Type": "application/json"}
PAGE = {"Origin": BASE, "Sec-Fetch-Site": "same-origin"}
KEY = "v" * 24  # a key's value, which must reach no output
CONFIG = {
    "endpoints": {
        "spark": {"base_url": "http://127.0.0.1:9/v1", "key_env": "SPARK_TEST_KEY"},
        "openai": {"base_url": "https://api.openai.com/v1", "key_env": "OPENAI_TEST_KEY"},
        "lan": {"base_url": "http://127.0.0.1:10/v1"},
    },
    "models": {
        "spark-turbo": {"endpoint": "spark", "model": "w", "parser": "whisper.cpp", "local": True},
        "lan-gemma": {"endpoint": "lan", "model": "g", "task": "translate", "local": True},
        "cloud": {"endpoint": "openai", "model": "whisper-1", "parser": "openai"},
    },
}


@pytest.fixture(autouse=True)
def fresh_reactive_lock():
    """shiny's reactive lock is one asyncio.Lock per process, bound to the first event loop it is
    contended on, and each TestClient runs its own loop: dropping it makes a new one (recordings'
    packages/ui/tests/conftest.py)."""
    from shiny.reactive import _core

    _core._reactive_environment._lock = None
    yield
    _core._reactive_environment._lock = None


@pytest.fixture
def probed(monkeypatch):
    """No endpoint is contacted for real: the spark answers, the LAN one is down."""
    calls: list[str] = []

    def list_models(name, endpoint, keys, *, timeout=5.0):
        calls.append(name)
        if name == "lan":
            raise EngineError("connection", "the server isn't reachable")
        return ["w"]

    monkeypatch.setattr(clients, "list_models", list_models)
    return calls


@pytest.fixture
def rt(tmp_path):
    made = runtime.build(Config.model_validate(CONFIG), tools=Tools(None, None, None),
                         keys=KeyRing(environ={"SPARK_TEST_KEY": KEY}),
                         cache=Cache(tmp_path / "cache", max_bytes=0))
    runtime.configure(made)
    yield made
    runtime.configure(None)
    made.queue.close()


@pytest.fixture
def client(rt):
    with TestClient(create_app(rt, token=TOKEN, port=PORT, shiny_app=server.app),
                    base_url=BASE) as c:
        r = c.post("/auth", content=json.dumps({"token": TOKEN}), headers={**JSON, **PAGE})
        assert r.status_code == 204
        yield c


def _session(client, outputs: set[str], until) -> list[dict]:
    """Every message the server sends a new session until `until(messages)` holds (20 s at
    most). Shiny runs the server function after the client's `init`, and sends an output only
    once the client says it isn't hidden (recordings' test_demo_guard.py)."""
    messages: list[dict] = []
    with client.websocket_connect(WS, headers={"Origin": BASE}) as ws:
        init = {f".clientdata_output_{name}_hidden": False for name in outputs}
        ws.send_text(json.dumps({"method": "init", "data": init}))

        def read() -> None:
            while not until(messages):
                messages.append(json.loads(ws.receive_text()))

        reader = threading.Thread(target=read, daemon=True)
        reader.start()
        reader.join(20)  # receive_text has no timeout: a missing output must not hang
    assert until(messages), f"the session sent only {messages}"
    return messages


def _values(messages: list[dict]) -> dict:
    out: dict = {}
    for m in messages:
        out.update(m.get("values", {}))
    return out


def test_the_page_runs_no_inline_script_or_style(client):
    # The CSP's script-src 'self' blocks inline scripts, and with no style-src, default-src
    # 'self' blocks inline styles (spec §6.3). Shiny 1.8.0's own page has one inline script,
    # the busy indicators; server.py serves it as a file instead.
    r = client.get("/")
    assert r.status_code == 200 and r.headers["content-security-policy"] == CSP
    for attrs, body in re.findall(r"<script\b([^>]*)>(.*?)</script>", r.text, re.DOTALL):
        if "src=" in attrs:
            assert body.strip() == ""
            continue
        kind = re.search(r'type="([^"]+)"', attrs)
        assert kind and kind.group(1) in ("application/json", "application/html-dependencies"), (
            f"an inline script the CSP would block: <script{attrs}>{body[:80]}")
    assert "<style" not in r.text and " style=" not in r.text


def test_the_busy_indicators_still_switch_on_from_a_file(client):
    page = client.get("/").text
    srcs = re.findall(r'<script src="([^"]*busy-indicators\.js)"', page)
    assert len(srcs) == 1
    script = client.get("/" + srcs[0].lstrip("/"))
    assert script.status_code == 200
    assert "document.documentElement.dataset.shinyBusySpinners = true;" in script.text
    assert "document.documentElement.dataset.shinyBusyPulse = true;" in script.text
    assert re.search(r'href="[^"]*busy-indicators\.css"', page)  # Shiny's stylesheet stays


def test_the_page_loads_the_frontend_and_its_fonts_from_the_engine(client):
    page = client.get("/").text
    assert "<title>vid2sub</title>" in page
    assert client.get("/fonts/AtkinsonHyperlegible-Regular.woff2").status_code == 200
    assert "http://" not in page.replace(BASE, "") and "https://" not in page  # nothing third-party


def test_capabilities_says_this_is_the_local_engine(client, probed):
    values = _values(_session(client, {"capabilities"}, lambda m: "capabilities" in _values(m)))
    assert values["capabilities"] == {"engine": "local", "generate": True, "save": "disk",
                                      "path_input": True}


def test_status_names_each_endpoint_its_reach_and_its_key_by_presence_only(client, probed):
    def probed_all(messages):
        status = _values(messages).get("status")
        return bool(status) and all(e["reachable"] is not None or not e["local"]
                                    for e in status["endpoints"])

    messages = _session(client, {"status"}, probed_all)
    assert _values(messages)["status"] == {
        "ffmpeg": False,
        "endpoints": [
            {"name": "spark", "local": True, "key": "present", "reachable": True},
            {"name": "openai", "local": False, "key": "missing", "reachable": None},
            {"name": "lan", "local": True, "key": "none", "reachable": False},
        ],
    }
    assert sorted(probed) == ["lan", "spark"]  # a cloud endpoint is never contacted
    assert KEY not in json.dumps(messages)


def test_a_notice_reaches_the_browser_as_a_shinyreact_message():
    class Session:
        def __init__(self):
            self.sent = []

        async def send_custom_message(self, kind, message):
            self.sent.append((kind, message))

    session = Session()
    asyncio.run(server.notice(session, "error", "couldn't save Show.en.srt"))
    assert session.sent == [("shinyReactMessage", {"id": "notice", "data": {
        "kind": "error", "text": "couldn't save Show.en.srt"}})]


# ---- the views -------------------------------------------------------------------------------


def test_a_typed_key_counts_as_present_and_is_never_shown():
    config = Config.model_validate({"endpoints": {"openai": {
        "base_url": "https://api.openai.com/v1", "allow_typed_key": True}}})
    keys = KeyRing(typed={"openai": KEY}, environ={})
    status = views.status_view(config, keys, {}, ffmpeg=True)
    assert status["endpoints"] == [
        {"name": "openai", "local": False, "key": "present", "reachable": None}]
    assert KEY not in json.dumps(status)


def test_an_endpoint_not_checked_yet_or_in_the_cloud_is_neither_reachable_nor_not():
    config = Config.model_validate(CONFIG)
    found = {"spark": True, "openai": True}  # a cloud endpoint is never shown as checked
    status = views.status_view(config, KeyRing(environ={}), found, ffmpeg=True)
    assert [(e["name"], e["reachable"]) for e in status["endpoints"]] == [
        ("spark", True), ("openai", None), ("lan", None)]


def test_capabilities_view_is_the_backends_capabilities_as_json(rt):
    assert views.capabilities_view(rt.backend.capabilities()) == {
        "engine": "local", "generate": True, "save": "disk", "path_input": True}
```

- [ ] **Step 8: Run it; watch it fail.** `uv run pytest tests/test_web_server.py -q`. Expected:
  `E   ImportError: cannot import name 'server' from 'vid2sub.web' (…/src/vid2sub/web/__init__.py)`.
- [ ] **Step 9: Write the code,** `src/vid2sub/web/static/busy/busy-indicators.js`:

```js
// Shiny's busy indicators, switched on as Shiny 1.8.0's shiny.ui.busy_indicators.use() does, but
// from a file: Shiny writes these two lines as an inline script, which the CSP's script-src
// 'self' blocks (spec §6.3). src/vid2sub/web/server.py puts this file in that script's place.
document.documentElement.dataset.shinyBusySpinners = true;
document.documentElement.dataset.shinyBusyPulse = true;
```

  `src/vid2sub/web/server.py`:

```python
"""The Shiny server for the React frontend: every output is JSON from a pure view function, and
every message goes through shinyreact's `send_message` (spec §19.1).

As recordings' shiny_app.py does (packages/ui/src/recordings_ui/shiny_app.py at 8deb039): the
server holds only reactive computation and returns JSON (the shinyreact-build-app skill), and
`ReactApp(...)` is called in this file. It reads the launch's parts from `runtime.current()`,
which `vid2sub serve` sets before importing this module. An unset input is a silent exception the
client treats as pending; an explicit null clears a pane (§19.1). Work that blocks (the endpoint
check here; opening, saving and retranslating later) runs off the event loop. Shiny's reconnect
stays off: nothing here calls `session.allow_reconnect`, so a tab whose engine restarted asks for
the new link instead of retrying (Review Focus 5).

The page is shinyreact's `page_react` (`www/ui.js` and `ui.css`), with `www/` also served at "/"
for the fonts, as ReactApp's own discovery mounts it. Its one change: Shiny 1.8.0 switches its busy
indicators on with an inline script, which the CSP's `script-src 'self'` blocks (§6.3), so the
same two lines are served as a file instead (checked in Chromium, spec §29). With that, the page
runs no inline script or style, and the CSP needs no `style-src` of its own.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Literal

import shiny
import shinyreact
from htmltools import HTMLDependency
from shiny import Inputs, Outputs, Session, reactive
from shinyreact import ReactApp, page_react, reactive_output

from vid2sub.config import Config
from vid2sub.engines import clients
from vid2sub.engines.base import EngineError
from vid2sub.engines.clients import KeyRing
from vid2sub.web import WWW, runtime, views

# By name: a test may load this file as a module of another name.
log = logging.getLogger("vid2sub.web.server")

STATUS_EVERY = 60  # seconds between checks of the local endpoints
# htmltools keeps the highest version of a dependency per name. Shiny's own version with a local
# label (1.8.0+vid2sub, which PEP 440 sorts above 1.8.0) makes this one replace Shiny's
# shiny-busy-indicators: its stylesheet, without the inline script in its head. The second
# dependency is that script, as a file. tests/test_web_server.py checks the rendered page, so a
# Shiny or htmltools upgrade that stops this winning fails there.
BUSY_INDICATORS = [
    HTMLDependency(
        "shiny-busy-indicators",
        f"{shiny.__version__}+vid2sub",
        source={"package": "shiny", "subdir": "www/shared/busy-indicators"},
        stylesheet={"href": "busy-indicators.css"},
        all_files=True,
    ),
    HTMLDependency(
        "vid2sub-busy-indicators",
        "1",
        source={"subdir": str(Path(__file__).parent / "static" / "busy")},
        script={"src": "busy-indicators.js"},
    ),
]


def page(request: Any) -> Any:
    """The page, built per request, so a rebuilt `ui.js` is fetched without a restart (its mtime
    is the dependency's version, as in ReactApp's own discovery)."""
    return page_react(*BUSY_INDICATORS, src_dir=WWW, title="vid2sub")


async def notice(session: Session, kind: Literal["info", "error"], text: str) -> None:
    """Tell the person something, as plain text (the frontend never renders it as markup)."""
    await shinyreact.send_message(session, "notice", {"kind": kind, "text": text})


def reachable(config: Config, keys: KeyRing) -> dict[str, bool]:
    """Whether each local endpoint answers its model list. Blocks on the network: run it off the
    event loop. Cloud endpoints are never contacted."""
    found = {}
    for name in views.local_endpoints(config):
        try:
            clients.list_models(name, config.endpoints[name], keys, timeout=3.0)
            found[name] = True
        except EngineError:
            found[name] = False
    return found


def server(input: Inputs, output: Outputs, session: Session) -> None:
    rt = runtime.current()

    @reactive_output
    def capabilities():
        return views.capabilities_view(rt.backend.capabilities())

    # The endpoint check runs as this session's extended task, off the event loop and outside
    # Shiny's reactive lock, now and every STATUS_EVERY seconds. The status keeps showing the last
    # result while the next check runs.
    found = reactive.value({})

    @reactive.extended_task
    async def check() -> dict[str, bool]:
        return await asyncio.to_thread(reachable, rt.config, rt.keys)

    @reactive.effect
    def _check_every_minute() -> None:
        reactive.invalidate_later(STATUS_EVERY)
        check.invoke()

    @reactive.effect
    def _keep_the_last_check() -> None:
        if check.status() == "success":
            found.set(check.result())

    @reactive_output
    def status():
        return views.status_view(rt.config, rt.keys, found(),
                                 ffmpeg=bool(rt.backend.tools.ffmpeg))


app = ReactApp(server, ui=page, static_assets={"/": WWW})
```

  In `src/vid2sub/web/views.py`, replace the docstring's last sentence

```python
covers. The view never holds a path, only the video's bare file name (§6.8).
"""
```

  with

```python
covers. The view never holds a path, only the video's bare file name (§6.8). The top bar's
views are here too (§19.2): the backend's capabilities, and the engine's status, which gives each
endpoint's key by presence only, never its value, and its reach only for local endpoints: a cloud
endpoint is never contacted (as `vid2sub doctor` decides).
"""
```

  replace the imports' first lines

```python
from bisect import bisect_right
from typing import Any

from vid2sub.subs import langs, naming
```

  with

```python
import dataclasses
from bisect import bisect_right
from collections.abc import Mapping
from typing import Any

from vid2sub.config import Config, is_local
from vid2sub.engines.clients import KeyRing
from vid2sub.subs import langs, naming
```

  replace the backend import

```python
from vid2sub.web.backend import Episode, all_stale
```

  with

```python
from vid2sub.web.backend import Capabilities, Episode, all_stale
```

  and add, directly above `def _rows(ep: Episode) -> list[dict[str, Any]]:`, so that it reads

```python
def _rows(ep: Episode) -> list[dict[str, Any]]:
```

  with

```python
def capabilities_view(caps: Capabilities) -> dict[str, Any]:
    return dataclasses.asdict(caps)


def local_endpoints(config: Config) -> list[str]:
    """The endpoints that serve a local model, the only ones the engine contacts unasked."""
    return [name for name in config.endpoints
            if any(m.endpoint == name and is_local(m, config) for m in config.models.values())]


def status_view(config: Config, keys: KeyRing, reachable: Mapping[str, bool], *,
                ffmpeg: bool) -> dict[str, Any]:
    """`reachable`: what the last check found for each local endpoint; one not in it is `None`
    (not checked yet), as is every cloud endpoint (never contacted)."""
    local = set(local_endpoints(config))
    endpoints = []
    for name, ep in config.endpoints.items():
        needs_key = bool(ep.key_env) or ep.allow_typed_key
        key = ("present" if keys.key_for(name, ep) else "missing") if needs_key else "none"
        endpoints.append({"name": name, "local": name in local, "key": key,
                          "reachable": reachable.get(name) if name in local else None})
    return {"endpoints": endpoints, "ffmpeg": ffmpeg}


def _rows(ep: Episode) -> list[dict[str, Any]]:
```

- [ ] **Step 10: Run the checks; they pass.** `uv run pytest tests/test_web_server.py -q`.
  Expected: `9 passed`. Without the build (move `www/ui.js` and `ui.css` aside) it still passes,
  with shinyreact's "JS entry point not found" warnings, as CI's Python job will. `make check`.
  Expected: `926 passed, 2 skipped, 4 deselected` twice, `Test Files  4 passed (4)`,
  `All checks passed!`, `no leaks found`.
- [ ] **Step 11: Each guard fails its tests without its fix.** `git add src/vid2sub/web/server.py
  src/vid2sub/web/views.py src/vid2sub/web/static/busy/busy-indicators.js
  tests/test_web_server.py`. Then, for each row, make the change in `server.py` (the middle two
  rows: `views.py`), run `uv run pytest tests/test_web_server.py -q`, see it fail, and restore
  with `git checkout -- <the file>`. The last column is what this listing's build saw.

| Guard | Change | To | Failed |
|---|---|---|---|
| Shiny's inline script replaced | `return page_react(*BUSY_INDICATORS, src_dir=WWW, title="vid2sub")` | `return page_react(src_dir=WWW, title="vid2sub")` | 2 |
| the replacement wins | `f"{shiny.__version__}+vid2sub",` | `shiny.__version__,` | 1 |
| a cloud endpoint never checked | `"reachable": reachable.get(name) if name in local else None})` | `"reachable": reachable.get(name)})` | 1 |
| keys by presence only | `key = ("present" if keys.key_for(name, ep) else "missing") if needs_key else "none"` | `key = keys.key_for(name, ep) or "none"` | 2 |
| only local endpoints probed | `for name in views.local_endpoints(config):` | `for name in config.endpoints:` | 1 |

- [ ] **Step 12: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(web): 🤖 the Shiny server sends capabilities and status as JSON, and its page runs no inline script, so the spec's CSP allows all of it

src/vid2sub/web/server.py follows recordings' shiny_app.py (8deb039): ReactApp(...) is called
here, the server reads runtime.current() and returns JSON from pure view functions (spec §19.1).
Outputs: capabilities (views.capabilities_view of the backend's Capabilities) and status
(views.status_view: each endpoint in vid2sub.toml with its key by presence only, never its value,
and its reach for local endpoints only, checked off the event loop as an extended task now and
every 60 s, keeping the last result; a cloud endpoint is never contacted, as doctor decides;
whether ffmpeg is there). server.notice(session, kind, text) sends the notice message.

The CSP: in Chromium (Playwright 1.64.1), Shiny 1.8.0's page logs one violation, its busy
indicators' inline script (busy_indicators.use() in the shiny-busy-indicators dependency's head,
sha256-erP5hScmId9gRru9k52QQl/lSJmUl8NfFAiLNMbPtcg=). Shiny has no option that leaves it out:
use(spinners=False, pulse=False) emits an inline script too. htmltools keeps the highest version
of a dependency per name, so the page is page_react with a shiny-busy-indicators of version
"<Shiny's>+vid2sub" (a PEP 440 local version, above Shiny's): the same stylesheet, no head, and
static/busy/busy-indicators.js with the same two lines as a file. Checked in Chromium: no
violation, no console line, and the busy pulse still animates while the server is busy. Without
it, blocking the script costs only that pulse (spinners attach to Shiny output elements, which a
React page has none of). No style-src is needed: default-src 'self' covers the stylesheets,
React's style props go through the CSSOM, and the page has no <style> or style attribute. www/
stays served at "/" (static_assets) for the fonts, as ReactApp's own discovery mounts it.

The new test failed first with: ImportError: cannot import name 'server' from 'vid2sub.web'.
Each guard was then reverted in turn and its tests failed: Shiny's inline script back (2 failed),
the replacement at Shiny's own version (1), a cloud endpoint shown as checked (1), a key's value
in the status (2), every endpoint probed (1). The page test checks the rendered page, so an
upgrade that stops the replacement winning fails it.

Docs read: shiny 1.8.0's html_dependencies.py and ui/busy_indicators.py, and shiny.js's busy
and disconnect handling; htmltools 0.7.0's _resolve_dependencies; shinyreact 0.1.0's _app.py
(ReactApp's ui= and static_assets) and _page.py (page_react); shiny's ExtendedTask (invoke
queues behind a running one and isolates itself); CSP Level 3 on script-src-elem and the
fallback of style-src to default-src (MDN).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 12
Co-Authored-By: <the model's own line>
```

  `git commit -F .git/COMMIT_MSG` (the four files are staged from Step 11), then
  `git log -1 --format='%(trailers)'` shows `Plan:`.

#### Round 12c: the browser tests, and a tab whose engine restarted

- [ ] **Step 13: Write the failing tests.** `tests/e2e/conftest.py`:

```python
"""Servers and pages for the browser tests (spec §22.7): the real `vid2sub serve`, on a free port,
in a child process with its own TMPDIR and an empty vid2sub.toml, and a page signed in through
the launch link as a person's browser is (Task 9's token flow, scripted).

As recordings' e2e conftest (packages/ui/tests/e2e/conftest.py at 8deb039): a server per test,
polled on /healthz, stopped at the end. vid2sub prints the link only to a terminal, so the
harness reads it from the redirect file whose path the server prints (0600, its own user's).
`page` replaces pytest-playwright's: it is already signed in, and the test fails on any console
error or CSP violation the page saw, unless the test took them itself (`watch`). Run with
`make e2e`, which builds the frontend first.
"""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from playwright.sync_api import BrowserContext, Page, expect

from vid2sub.web import WWW

LINK = re.compile(r"http://127\.0\.0\.1:(\d+)/auth#t=([A-Za-z0-9_-]{43})")
PAGE_LINE = re.compile(r"^  (.+open\.html)$", re.MULTILINE)
# Runs before any page script, outside the CSP (Playwright injects it): a page's CSP violations,
# with what was blocked, for the document that is open now.
WATCH_CSP = """
window.__csp = [];
document.addEventListener("securitypolicyviolation", (e) => {
  window.__csp.push(`${e.violatedDirective} ${e.blockedURI} ${e.sample || ""}`.trim());
});
"""


@dataclass
class Server:
    url: str  # http://127.0.0.1:<port>
    link: str  # the launch link, /auth#t=<token>
    port: int
    proc: subprocess.Popen
    log: Path
    tmp: Path  # the server's TMPDIR

    def stop(self) -> int:
        if self.proc.poll() is None:
            if os.name == "nt":
                self.proc.terminate()
            else:
                self.proc.send_signal(signal.SIGINT)
            try:
                self.proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
        return self.proc.returncode


def start_server(tmp: Path, *args: str, port: int = 0) -> Server:
    """`vid2sub serve --no-browser` on `port` (0: any free one), up and answering."""
    if not (WWW / "ui.js").is_file():
        pytest.fail("the frontend isn't built: run make build (make e2e does)")
    tmp.mkdir(parents=True, exist_ok=True)
    config = tmp / "vid2sub.toml"
    config.write_text("", encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if not k.startswith("VID2SUB_")}
    env["TMPDIR"] = str(tmp)
    log = tmp / "server.log"
    with log.open("wb") as out:
        proc = subprocess.Popen(
            [sys.executable, "-m", "vid2sub", "serve", "--no-browser", "--port", str(port),
             "--config", str(config), *args],
            env=env, stdout=out, stderr=subprocess.STDOUT)

    def tail() -> str:
        return log.read_text(encoding="utf-8", errors="replace")[-2000:]

    deadline = time.monotonic() + 60
    while not (found := PAGE_LINE.search(log.read_text(encoding="utf-8", errors="replace"))):
        if proc.poll() is not None:
            pytest.fail(f"vid2sub serve exited with {proc.returncode}:\n{tail()}")
        if time.monotonic() > deadline:
            proc.kill()
            pytest.fail(f"vid2sub serve printed no redirect file in 60 s:\n{tail()}")
        time.sleep(0.1)
    link = LINK.search(Path(found.group(1)).read_text(encoding="utf-8"))
    url = f"http://127.0.0.1:{link.group(1)}"
    while True:
        try:
            with urllib.request.urlopen(f"{url}/healthz", timeout=1) as r:
                if json.load(r) == {"ok": True}:
                    break
        except OSError:
            pass
        if time.monotonic() > deadline:
            proc.kill()
            pytest.fail(f"vid2sub serve never answered /healthz:\n{tail()}")
        time.sleep(0.1)
    return Server(url, link.group(0), int(link.group(1)), proc, log, tmp)


@pytest.fixture
def server(tmp_path):
    started = start_server(tmp_path / "server")
    yield started
    started.stop()


@pytest.fixture
def launch():
    """Starts another server, `launch(tmp, *args, port=0)`, stopped at the end of the test."""
    started: list[Server] = []

    def run(tmp: Path, *args: str, port: int = 0) -> Server:
        started.append(start_server(tmp, *args, port=port))
        return started[-1]

    yield run
    for s in started:
        s.stop()


@dataclass
class Watch:
    """What a page did: console errors (CSP violations among them, as Chromium logs each one)
    and every request it made, across navigations."""

    page: Page
    errors: list[str] = field(default_factory=list)
    requests: list[str] = field(default_factory=list)

    def violations(self) -> list[str]:
        """The CSP violations in the document open now."""
        return self.page.evaluate("() => window.__csp")

    def clear(self) -> None:
        """Takes what was seen so far, for a test whose point it was."""
        self.errors.clear()
        self.page.evaluate("() => { window.__csp = []; }")


def watched_page(context: BrowserContext) -> Watch:
    context.add_init_script(script=WATCH_CSP)
    page = context.new_page()
    watch = Watch(page)
    page.on("console", lambda m: watch.errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: watch.errors.append(f"uncaught: {e}"))
    page.on("request", lambda r: watch.requests.append(r.url))
    return watch


def sign_in(page: Page, server: Server) -> None:
    """Through the launch link, as the browser vid2sub opens does: /auth posts the token from the
    fragment, gets the cookie and replaces the address with "/"."""
    page.goto(server.link)
    page.wait_for_url(f"{server.url}/")
    expect(page.get_by_test_id("app")).to_be_visible()


@pytest.fixture
def open_page(context):
    """Opens a new page signed in to `server`, watched; the test checks what it saw itself."""

    def run(server: Server) -> Watch:
        watched = watched_page(context)
        sign_in(watched.page, server)
        return watched

    return run


@pytest.fixture
def watch(open_page, server):
    watched = open_page(server)
    yield watched
    assert watched.errors == [], f"console errors: {watched.errors}"
    assert watched.violations() == []


@pytest.fixture
def page(watch) -> Page:
    """A page already through /auth on the `server` fixture's engine; the test fails on any
    console error or CSP violation it saw."""
    return watch.page
```

  `tests/e2e/test_csp.py`:

```python
"""In Chromium, the engine's page runs under the spec's CSP with no violation and no console
error, the CSP blocks inline scripts, eval and inline styles, nothing leaves the engine's own
origin, and a tab whose engine restarted says to open the new link instead of reconnecting
(spec §6.3, §29; S26; Review Focus 5). Run with `make e2e`."""

import time

import pytest
from playwright.sync_api import expect

from vid2sub.web.auth import SIGN_IN_AGAIN
from vid2sub.web.guards import CSP

pytestmark = pytest.mark.e2e


def test_the_page_loads_with_no_csp_violation_or_console_error(page, server, watch):
    expect(page.get_by_test_id("engine")).to_have_text("Local engine")
    for theme in ("dark", "light", "system"):  # Radix's toggle group, and the theme classes
        page.get_by_test_id(f"theme-{theme}").click()
    assert page.evaluate("() => document.documentElement.classList.contains('light')")
    assert page.request.get(f"{server.url}/").headers["content-security-policy"] == CSP
    # Shiny's busy indicators still switch on, from the file that replaced the inline script.
    assert page.evaluate("() => document.documentElement.dataset.shinyBusyPulse") == "true"
    # The fonts are the engine's own (spec §19.3).
    loaded = page.evaluate("""async () => {
        await document.fonts.ready;
        return document.fonts.check('16px "Atkinson Hyperlegible"');
    }""")
    assert loaded
    assert watch.errors == [] and watch.violations() == []


def test_the_csp_blocks_an_inline_script_eval_and_inline_styles(page, watch):
    ran = page.evaluate("""() => {
        const s = document.createElement("script");
        s.textContent = "window.__ran = true";
        document.body.append(s);
        return window.__ran === true;
    }""")
    assert ran is False
    # eval here only proves the CSP refuses it ('unsafe-eval' is never allowed, spec §6.3). It
    # runs from a real click: code Playwright evaluates itself is exempt from the CSP's eval rule.
    page.evaluate("""() => {
        window.__eval = "not run";
        document.querySelector("main").addEventListener("click", () => {
            try { window.__eval = String(eval("1 + 1")); } catch (e) { window.__eval = e.name; }
        }, { once: true });
    }""")
    page.get_by_test_id("main").click()
    assert page.evaluate("() => window.__eval") == "EvalError"
    styled = page.evaluate("""() => {
        const style = document.createElement("style");
        style.textContent = "main { color: rgb(1, 2, 3) }";
        document.head.append(style);
        const main = document.querySelector("main");
        main.setAttribute("style", "background-color: rgb(4, 5, 6)");
        const seen = getComputedStyle(main);
        return [seen.color, seen.backgroundColor];
    }""")
    assert "rgb(1, 2, 3)" not in styled and "rgb(4, 5, 6)" not in styled
    # The browser reports each violation as a task of its own, and logs the three inline ones.
    deadline = time.monotonic() + 5
    while (len(watch.violations()) < 4 or len(watch.errors) < 3) and time.monotonic() < deadline:
        page.wait_for_timeout(50)
    assert sorted(v.split()[0] for v in watch.violations()) == [
        "script-src", "script-src-elem", "style-src-attr", "style-src-elem"]
    watch.clear()  # the violations were the point


def test_nothing_leaves_the_engines_own_origin(page, server, watch):
    page.get_by_test_id("theme-dark").click()
    assert watch.requests, "no request was seen"
    assert [u for u in watch.requests if not u.startswith(f"{server.url}/")] == []


def test_a_restarted_engine_tells_the_page_to_open_the_new_link_and_it_never_reconnects(
        open_page, server, launch, tmp_path):
    # Review Focus 5. A refused websocket reaches the browser as an HTTP 403 (close code 1006),
    # so the page asks the engine for "/" once when Shiny says the socket closed.
    watch = open_page(server)
    page = watch.page
    expect(page.get_by_test_id("engine")).to_have_text("Local engine")
    opened = []  # websockets opened after the first
    page.on("websocket", lambda ws: opened.append(ws.url))
    server.stop()
    lost = page.get_by_test_id("lost")
    expect(lost).to_contain_text("vid2sub isn't running")
    launch(tmp_path / "again", port=server.port)  # a new launch, so a new token
    page.wait_for_timeout(2000)  # long enough for any reconnect Shiny might try
    page.get_by_test_id("check-again").click()
    expect(lost).to_contain_text(f"vid2sub was restarted, so this page is signed out: "
                                 f"{SIGN_IN_AGAIN}.")
    assert opened == []  # it never reconnected
    page.reload()  # the old cookie is refused by the new launch
    expect(page.locator("body")).to_have_text(SIGN_IN_AGAIN)
    # A closed socket, a refused fetch and a 401 are logged; a CSP violation never is.
    assert [e for e in watch.errors if "Content Security Policy" in e] == []
```

  In `pyproject.toml`, replace `addopts` and the markers

```toml
addopts = "--import-mode=importlib -m 'not live'"
markers = [
    "media: needs ffmpeg and ffprobe (skipped without them unless VID2SUB_REQUIRE_FFMPEG=1)",
    "live: a real model or the Spark; opt-in, see tests/README.md",
]
```

  with

```toml
addopts = "--import-mode=importlib -m 'not live and not e2e'"
markers = [
    "media: needs ffmpeg and ffprobe (skipped without them unless VID2SUB_REQUIRE_FFMPEG=1)",
    "live: a real model or the Spark; opt-in, see tests/README.md",
    "e2e: Chromium against vid2sub serve; needs the built frontend (make e2e)",
]
```

  In the `Makefile`, replace the `.PHONY` line

```make
.PHONY: setup build test test-utc test-js lint leaks check hooks live readme brand skills help
```

  with

```make
.PHONY: setup build test test-utc test-js e2e lint leaks check hooks live readme brand skills help
```

  and add the target above `lint`:

```make
lint: ## Lint with ruff
```

  with

```make
e2e: build ## The browser tests against vid2sub serve (installs Playwright's Chromium first)
	uv run playwright install chromium
	uv run pytest -m e2e

lint: ## Lint with ruff
```

- [ ] **Step 14: Run them; watch them fail.** `make e2e` (it builds the frontend, installs
  Playwright's Chromium if it isn't there, and runs `pytest -m e2e`). Expected:
  `FAILED tests/e2e/test_csp.py::test_a_restarted_engine_tells_the_page_to_open_the_new_link_and_it_never_reconnects[chromium]`,
  with `AssertionError: Locator expected to contain text 'vid2sub isn't running'`,
  `Actual value: None`, then `1 failed, 3 passed`.
- [ ] **Step 15: Write the code,** `frontend/src/lib/connection.test.ts`:

```ts
import { describe, expect, it, vi } from "vitest";

import { LOST_MESSAGES, SIGN_IN_AGAIN, whyLost } from "./connection";

describe("a lost connection (Review Focus 5)", () => {
  it("asks for / once, with the cookie and nothing cached", async () => {
    const fetchFn = vi.fn(async () => ({ status: 200 }));
    await whyLost(fetchFn);
    expect(fetchFn).toHaveBeenCalledTimes(1);
    expect(fetchFn).toHaveBeenCalledWith("/", { cache: "no-store", credentials: "same-origin" });
  });

  it("a 401 means the engine restarted: open the new link", async () => {
    expect(await whyLost(async () => ({ status: 401 }))).toBe("signed-out");
    expect(LOST_MESSAGES["signed-out"]).toContain(SIGN_IN_AGAIN);
  });

  it("no answer means vid2sub isn't running", async () => {
    expect(await whyLost(async () => { throw new TypeError("Failed to fetch"); })).toBe("stopped");
  });

  it("any other answer means the engine is up: reload", async () => {
    expect(await whyLost(async () => ({ status: 200 }))).toBe("dropped");
  });

  it("says what the engine says to a page without its cookie", () => {
    expect(SIGN_IN_AGAIN).toBe("open the link vid2sub printed when it started");
  });
});
```

  `frontend/src/lib/connection.ts`:

```ts
// What the page says when its websocket to the engine closes (Review Focus 5). Shiny's own
// reconnect stays off, so the page never retries by itself. It asks the engine for "/" once, with
// its cookie: a 401 means the engine was restarted and this page's cookie is from the old launch,
// so the person must open the new link; no answer means vid2sub isn't running; any other answer
// means the engine is up, and a reload carries on. A refused websocket handshake reaches the
// browser as an HTTP 403 (close code 1006), never 1008, so the close code can't tell these apart.

/** auth.SIGN_IN_AGAIN, as the engine says it to a request without its cookie. */
export const SIGN_IN_AGAIN = "open the link vid2sub printed when it started";

export type Lost = "signed-out" | "stopped" | "dropped";

export const LOST_MESSAGES: Record<Lost, string> = {
  "signed-out": `vid2sub was restarted, so this page is signed out: ${SIGN_IN_AGAIN}.`,
  stopped: "vid2sub isn't running. Start it again, then open the link it prints.",
  dropped: "The connection to vid2sub closed. Reload the page to carry on.",
};

type Fetch = (input: string, init: RequestInit) => Promise<{ status: number }>;

/** Asks the engine once why the connection closed. */
export async function whyLost(fetchFn: Fetch): Promise<Lost> {
  try {
    const r = await fetchFn("/", { cache: "no-store", credentials: "same-origin" });
    return r.status === 401 ? "signed-out" : "dropped";
  } catch {
    return "stopped";
  }
}
```

  and replace `frontend/src/App.tsx` with:

```tsx
import { useCallback, useEffect, useRef, useState } from "react";

import { TopBar } from "@/components/TopBar";
import { LOST_MESSAGES, type Lost, whyLost } from "@/lib/connection";
import { type Shown, addNotice, dismissNotice } from "@/lib/notices";
import { useShinyInitialized, useShinyMessageHandler, useShinyOutputValue } from "@/sr";
import type { Capabilities, Status } from "@/types";

type JQueryLike = (target: Document) => {
  on(event: string, handler: () => void): unknown;
  off(event: string, handler: () => void): unknown;
};

export default function App() {
  const initialized = useShinyInitialized();
  // Every output is subscribed here, and every message handler lives here: shinyreact 0.1.0
  // drops a message that has no handler, and an output that unmounts logs "Output <id> not found"
  // for each later value (recordings' App.tsx). A new output or message gets a line here too.
  const capabilities = useShinyOutputValue<Capabilities>("capabilities");
  const status = useShinyOutputValue<Status>("status");
  const [notices, setNotices] = useState<Shown[]>([]);
  const nextId = useRef(1);
  useShinyMessageHandler("notice", (data: unknown) => {
    setNotices((shown) => addNotice(shown, data, nextId.current++));
  });

  // The websocket closed: ask the engine once why, and say so; never reconnect (Review Focus 5).
  const [lost, setLost] = useState<Lost | null>(null);
  const check = useCallback(() => {
    void whyLost((input, init) => window.fetch(input, init)).then(setLost);
  }, []);
  useEffect(() => {
    // Shiny triggers shiny:disconnected through jQuery, which addEventListener never sees.
    const $ = (window as unknown as { jQuery?: JQueryLike }).jQuery;
    if (!$) return;
    $(document).on("shiny:disconnected", check);
    return () => void $(document).off("shiny:disconnected", check);
  }, [check]);

  if (!initialized && lost === null) return null; // no flash of empty defaults while connecting
  return (
    <div className="flex h-dvh flex-col" data-testid="app">
      <TopBar capabilities={capabilities} status={status} />
      {lost && (
        // Above Shiny's grey disconnected overlay (z-index 99998), which ignores the pointer.
        <div role="alert" data-testid="lost" className="relative z-[99999] flex items-center gap-3 border-b border-destructive bg-card px-4 py-2 text-destructive">
          <span>{LOST_MESSAGES[lost]}</span>
          {lost === "stopped" && (
            <button type="button" className="underline" onClick={check} data-testid="check-again">Check again</button>
          )}
          {lost === "dropped" && (
            <button type="button" className="underline" onClick={() => window.location.reload()}>Reload</button>
          )}
        </div>
      )}
      <main className="flex flex-1 items-center justify-center text-muted-foreground" data-testid="main">
        <p>The editor opens here.</p>
      </main>
      <section aria-label="Notices" className="fixed right-4 bottom-4 z-[99999] flex w-80 flex-col gap-2">
        <div role="status" aria-live="polite" className="flex flex-col gap-2">
          {notices.filter((n) => n.kind === "info").map((n) => <NoticeCard key={n.id} notice={n} onDismiss={setNotices} />)}
        </div>
        <div role="alert" className="flex flex-col gap-2">
          {notices.filter((n) => n.kind === "error").map((n) => <NoticeCard key={n.id} notice={n} onDismiss={setNotices} />)}
        </div>
      </section>
    </div>
  );
}

function NoticeCard({ notice, onDismiss }: { notice: Shown; onDismiss: (f: (s: Shown[]) => Shown[]) => void }) {
  return (
    <div className={`flex items-start gap-2 rounded-lg border bg-card p-3 text-sm shadow ${notice.kind === "error" ? "border-destructive text-destructive" : "border-border"}`} data-testid="notice">
      {/* Plain text: a notice can carry a file name or a server's error (spec §6.3). */}
      <span className="flex-1">{notice.text}</span>
      <button type="button" aria-label="Dismiss" onClick={() => onDismiss((s) => dismissNotice(s, notice.id))}>×</button>
    </div>
  );
}
```

- [ ] **Step 16: Run the checks; they pass.** `make test-js`. Expected: `Test Files  5 passed
  (5)`, `Tests  24 passed (24)`. `make e2e`, twice. Expected: `4 passed, 932 deselected` each
  time. `make check`. Expected: `926 passed, 2 skipped, 8 deselected` twice (the e2e tests are
  the 4 new ones deselected), the Vitest lines, `All checks passed!`, `no leaks found`.
- [ ] **Step 17: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
test(e2e): 🤖 in Chromium the editor runs with no CSP violation, and a tab whose engine restarted says to open the new link instead of reconnecting

tests/e2e/conftest.py, as recordings' e2e conftest (8deb039): the real `vid2sub serve
--no-browser` on a free port in a child process with its own TMPDIR and an empty vid2sub.toml,
polled on /healthz; the link read from the redirect file the server names (it prints the link
only to a terminal); a page signed in through /auth#t=<token> as a person's browser is; and a
watch on every console error, CSP violation (a securitypolicyviolation listener injected before
the page's scripts) and request, which fails the test unless it took them (`page`, `watch`,
`open_page`, `launch`, `server`). The e2e marker is off by default (pyproject addopts);
`make e2e` builds the frontend, installs Playwright's Chromium and runs them.

tests/e2e/test_csp.py: the page loads with no violation and no console error, theme switching
included, with the spec's CSP header, the busy pulse switched on from its file, and the fonts the
engine's own; an inline script, eval (from a real click: code Playwright evaluates is exempt) and
an inline style element and attribute are each blocked and reported (script-src-elem,
script-src, style-src-elem, style-src-attr); every request goes to the engine's own origin; and
Review Focus 5 with a real restart: the engine stopped, the page says vid2sub isn't running;
started again on the same port, Check again says it was restarted and to open the link vid2sub
printed (auth.SIGN_IN_AGAIN), no websocket was opened again, and a reload gets the new launch's
401. The frontend's lib/connection.ts asks for "/" once with the cookie when Shiny says the
socket closed (a 401: signed out; no answer: stopped; else: reload), and App shows it in an alert
above Shiny's grey overlay; Shiny triggers shiny:disconnected through jQuery, which
addEventListener never sees, so App listens with jQuery. A refused websocket handshake reaches
the browser as an HTTP 403 (close code 1006), never 1008.

The new test failed first with: Locator expected to contain text 'vid2sub isn't running',
Actual value: None (1 failed, 3 passed).

Docs read: Playwright for Python 1.64's BrowserContext.add_init_script (runs before page
scripts, not subject to the page's CSP), Page.on("console"/"pageerror"/"request"/"websocket"),
expect().to_have_text and to_contain_text, page.request; pytest-playwright 0.10.0's context and
page fixtures (page is overridden here); CDP's Runtime.evaluate (allowUnsafeEvalBlockedByCSP,
why an evaluated eval isn't refused); MDN on SecurityPolicyViolationEvent; shiny.js's
socket.onclose (shiny:disconnected only after a socket opened, 1012 marks a restart).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 12
Co-Authored-By: <the model's own line>
```

  `git add tests/e2e/conftest.py tests/e2e/test_csp.py pyproject.toml Makefile
  frontend/src/lib/connection.ts frontend/src/lib/connection.test.ts frontend/src/App.tsx`,
  `git commit -F .git/COMMIT_MSG`, then `git log -1 --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 18: Review, look forward, close.** The Tier 2 review from `$(cat .git/TASK_BASE)`
  (`AGENTS.md`, *Reviews*). Worth the reviewers' time: that the rendered page has no executable
  inline script, `<style>` or style attribute, and the test checks the page, not the dependency
  object; that `status` never holds a key's value and never contacts a cloud endpoint; that
  untrusted text (endpoint names, notices) reaches React only as text; that React stays external
  (the build test) and every output and message handler lives in `App`; that the restart path
  never reconnects. The forward review over Tasks 13–19, 21, 22 and 23 (Task 13 makes the e2e
  `server` the demo and adds `start_server(..., toml=...)`; Tasks 14–19 add each output to
  `App`'s subscriptions and each message to its handlers, use `notice` for plain-text errors, and
  build their modal parts on the native `<dialog>` described above, never a modal Radix part or
  Radix Select; Task 18's drawer is that dialog with `side="right"`; Task 21's CI frontend job runs
  `make test-js` with `CI=true` and the e2e job `make e2e`, both on Node 22; Task 22's README
  says `make build` comes before `vid2sub serve`; Task 23's Step 2 builds with `make build`). The
  docs this task made untrue: spec §29's M2 bullet on the CSP, which this task settles: add to it
  "*Result (2026-10-24, Chromium via Playwright 1.64.1):* Shiny 1.8.0's one inline script, its
  busy indicators, is served as a file instead (`server.BUSY_INDICATORS`), so `script-src 'self'`
  holds with no violation; no `style-src` is needed and none is set; `eval` is never needed.
  Radix's modal parts and Select inject `<style>` elements, so the editor's modal parts use the
  native `<dialog>`, its menus are non-modal and its choices native `<select>`s." Then the close,
  its own commit, holding this plan with this task's boxes ticked and **Now** set to
  `Task 13: The end-to-end harness and the demo, open.`, and the spec's §29 as above; S26 stays
  `planned` (its hostile fixtures are Task 13's and its overlay Task 14's), with the message in
  `.git/CLOSE_MSG`:

```text
docs(plan): 🤖 close Task 12: The frontend scaffold and the shinyreact server

Drift: none
Rulings: none
Phase-end: none
Forward: none
Tier: 2
Rounds: <Matt's code-review, Standards and Spec in two subagents; any re-review>
Findings: none

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 12
Co-Authored-By: <the model's own line>
```

  `git add docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md
  docs/superpowers/specs/2026-10-14-vid2sub-design.md`, `git commit -F .git/CLOSE_MSG`.

***

### Task 13: The end-to-end harness and the demo

**Tier:** 2 · **Scenarios:** S26

**Files:**
- Create: `demo/` (`CREDITS.md`, the canned sidecar `jfk.vid2sub.jsonl`, `jfk.en.srt`,
  `jfk.ja.srt`), `src/vid2sub/web/demo.py`, `scripts/demo_sidecar.py`,
  `tests/test_demo_guard.py`, `tests/fixtures/hostile/` (`hostile.srt`, `hostile.ass`,
  `names.json`), `tests/test_hostile_fixtures.py`, `tests/e2e/test_shell.py`
- Modify: `src/vid2sub/commands/serve.py` (`--demo`), `Makefile` (`demo`, `demo-sidecar`),
  `tests/e2e/conftest.py` (the demo server; `toml=`), `tests/fixtures/CREDITS.md`
- `tests/e2e/conftest.py`, the `e2e` marker and `make e2e` came with Task 12, whose CSP test needs
  them.

**Interfaces:**
- Consumes: Task 11's `runtime.build`, `Runtime`, `serve`; Task 12's e2e fixtures; Task 5's
  `LocalBackend`, `OpenError`; M1's `pipeline.run_one`, `RunContext`, `RunOptions` (for the
  canned sidecar), `store.header_for`, `sidecar_path`, `now`, `media.identity`, `media.probe`,
  `media.tools.run_tool`, `subs.sidecar`.
- Produces:
  - `demo.prepare(tools: Tools) -> Path`: a fresh copy of `demo/` at `<a new mkdtemp
    "vid2sub-demo-…" folder>/demo`, removed at exit, with `jfk.mp4` muxed (14 000 ms; a still
    640×360 picture in VP9 and the clip in Opus, which Playwright's Chromium plays) and the
    sidecar's header and identity naming it. Raises `demo.DemoMissing` outside a checkout of the
    repository, and ffmpeg's `ToolMissing` or `ToolFailed`.
  - `demo.runtime_for(copy: Path, tools: Tools) -> Runtime`: no vid2sub.toml (`Config()`), no key
    (`KeyRing(environ={})`), a cache in `copy.parent / "cache"`, and `demo.DemoBackend`
    (`LocalBackend` whose `open` refuses any path outside the copy with `OpenError("the demo
    opens only its own episode")`).
  - `demo.isolate(folder: Path, *, home: Path | None = None) -> None` and `demo.release()`: an
    audit hook refusing, with `demo.DemoIsolationError` (a `PermissionError`), writes outside
    `folder`, reads in `home` (default `Path.home()`) outside `folder`, `sys.prefix`,
    `sys.base_prefix` and the vid2sub package, and lookups or connections beyond 127.0.0.1, ::1
    and localhost; `tempfile.tempdir` becomes `folder / "tmp"`; bytecode isn't written; released
    at exit before the folder is removed.
  - `demo.CannedEngine` (the Engine protocol: the clip's words, one chunk), `demo.canned_ask(system,
    prompt, data_model)` (translate.run's AskFn: `demo.JAPANESE`, else `demo.NO_TRANSLATION`),
    `demo.WORDS`, `demo.mux(tools, out)`, `demo.DEMO`, `demo.CLIP`, `demo.VIDEO` (`"jfk.mp4"`).
  - `vid2sub serve --demo` (exclusive with `--config`; exit 69 without ffmpeg, without libvpx
    and libopus, or outside a checkout); `make demo`; `make demo-sidecar`.
  - The e2e `server` fixture is now the demo; `start_server(tmp, *args, port=0, toml=None)` and
    `launch(tmp, *args, port=0, toml=None)` serve a vid2sub.toml instead when given one.
  - The demo episode: source `en`, 4 cues ("I am delighted to be here, and I am / particularly
    delighted to be here on this", "occasion.", "We meet at a college noted for knowledge,", "in a
    city noted for progress, / in a state noted for strength,"), 37 timed words; translation `ja`,
    3 cues, the first covering source cues 1 and 2; `jfk.en.srt` and `jfk.ja.srt` projected.

**For later tasks.** Task 14 finds the demo's copy from the test as
`next(server.tmp.glob("vid2sub-demo-*/demo"))` and opens `<copy>/jfk.mp4`; to show the hostile
SRT in the editor, it writes `tests/fixtures/hostile/hostile.srt` over `<copy>/jfk.en.srt` before
opening (an outside edit, which the open keeps as an external version). Task 17's retranslate in
the demo needs a translator: give `LocalBackend` a seam (`_translator` and a new `_ask(name,
entry, policy)` wrapping `make_ask`) and have `DemoBackend` answer with a `canned-ja` model and
`canned_ask`. Task 19's demo jobs give `runtime_for`'s queue a runner using `CannedEngine` (the
demo clip only). Anything new that writes while the demo runs must write in its folder:
`tempfile` already goes there, and the cache is `copy.parent / "cache"`. Task 21's e2e job needs
an ffmpeg with libvpx and libopus (Ubuntu's apt ffmpeg has both).

- [ ] **Step 0: Record the base:** `git rev-parse HEAD > .git/TASK_BASE`.

#### Round 13a: the demo, isolated by the app

- [ ] **Step 1: Write the failing test,** `tests/test_demo_guard.py`:

```python
"""Demo mode touches nothing but its own copy, and the app enforces it (spec §22.4, §22.7):
writes outside the demo's folder, reads in the home folder, lookups and connections beyond this
machine are refused while the demo runs, its backend opens only its own episode, it reads no
vid2sub.toml and no key, and its folder goes when it stops. As recordings' test_demo_guard.py
(packages/ui/tests at 8deb039), whose audit hook only watched; vid2sub's refuses. Each refusal is
a DemoIsolationError, which these tests expect, so they fail if the hook isn't there."""

import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

import pytest
from starlette.testclient import TestClient

import vid2sub
from vid2sub.media.tools import Tools
from vid2sub.web import demo, runtime, server
from vid2sub.web.app import create_app
from vid2sub.web.backend import OpenError
from vid2sub.web.demo import DemoIsolationError
from vid2sub.web.views import episode_view

TOKEN = "t" * 43  # as long as a real token, and plainly not one (the leak scan agrees)
PORT = 8765
BASE = f"http://127.0.0.1:{PORT}"
PAGE = {"Origin": BASE, "Sec-Fetch-Site": "same-origin", "Content-Type": "application/json"}


@pytest.fixture(autouse=True)
def fresh_reactive_lock():
    """As tests/test_web_server.py: each TestClient runs its own event loop."""
    from shiny.reactive import _core

    _core._reactive_environment._lock = None
    yield
    _core._reactive_environment._lock = None


@pytest.fixture
def place(tmp_path):
    """A demo folder, a stand-in for the person's home with their config and a secret in it, and
    a folder elsewhere with a file in it, all made before the demo is isolated."""
    folder, home, outside = tmp_path / "demo", tmp_path / "home", tmp_path / "outside"
    for d in (folder, home, outside / "dir"):
        d.mkdir(parents=True)
    (home / "vid2sub.toml").write_text("[server]\nport = 1\n", encoding="utf-8")
    (outside / "file.txt").write_text("x", encoding="utf-8")
    (folder / "inside.txt").write_text("x", encoding="utf-8")
    yield folder, home, outside
    demo.release()


def test_the_demo_refuses_every_kind_of_write_outside_its_folder(place):
    folder, home, outside = place
    demo.isolate(folder, home=home)
    file, d = outside / "file.txt", outside / "dir"
    writes = [
        lambda: open(outside / "new.txt", "w"),  # noqa: SIM115
        lambda: (file).open("a"),
        lambda: os.open(outside / "fd.txt", os.O_WRONLY | os.O_CREAT),
        lambda: os.replace(folder / "inside.txt", outside / "moved.txt"),
        lambda: os.mkdir(outside / "made"),
        lambda: os.chmod(file, 0o600),
        lambda: os.utime(file),
        lambda: os.symlink(folder / "inside.txt", outside / "link"),
        lambda: os.link(folder / "inside.txt", outside / "hard"),
        lambda: os.truncate(file, 0),
        lambda: os.remove(file),
        lambda: os.rmdir(d),
        lambda: shutil.rmtree(d),
        lambda: shutil.copyfile(folder / "inside.txt", outside / "copy.txt"),
        lambda: tempfile.mkdtemp(dir=outside),
    ]
    for write in writes:
        with pytest.raises(DemoIsolationError, match="inside its own folder"):
            write()
    assert sorted(p.name for p in outside.iterdir()) == ["dir", "file.txt"]
    assert file.read_text(encoding="utf-8") == "x"
    # Inside, everything works, shutil.rmtree's removals through a folder's descriptor included.
    (folder / "sub").mkdir()
    (folder / "sub" / "a.txt").write_text("y", encoding="utf-8")
    os.replace(folder / "sub" / "a.txt", folder / "sub" / "b.txt")
    shutil.rmtree(folder / "sub")
    assert not (folder / "sub").exists()


def test_the_demo_reads_nothing_in_the_home_folder_but_python_and_vid2sub(place):
    folder, home, outside = place
    demo.isolate(folder, home=home)
    with pytest.raises(DemoIsolationError, match="nothing of yours"):
        (home / "vid2sub.toml").read_text(encoding="utf-8")
    assert (folder / "inside.txt").read_text(encoding="utf-8") == "x"
    assert (outside / "file.txt").read_text(encoding="utf-8") == "x"  # outside home: allowed
    assert Path(vid2sub.__file__).read_text(encoding="utf-8")
    assert Path(os.__file__).read_text(encoding="utf-8")


def test_the_demo_looks_up_and_connects_to_nothing_beyond_this_machine(place):
    folder, home, _ = place
    demo.isolate(folder, home=home)
    with pytest.raises(DemoIsolationError, match="no other machine"):
        socket.getaddrinfo("example.com", 443)
    with socket.socket() as s, pytest.raises(DemoIsolationError, match="beyond this machine"):
        s.settimeout(2)
        s.connect(("192.0.2.1", 9))  # refused before a packet goes
    assert socket.getaddrinfo("127.0.0.1", 9)


def test_the_demos_temporary_files_go_in_its_folder_until_it_is_released(place):
    folder, home, _ = place
    before = tempfile.gettempdir()
    demo.isolate(folder, home=home)
    made = Path(tempfile.mkdtemp(prefix="vid2sub-"))
    assert made.parent == folder / "tmp"
    demo.release()
    assert tempfile.gettempdir() == before
    with open(home / "vid2sub.toml", encoding="utf-8"):  # released: nothing is refused
        pass


@pytest.mark.media
def test_demo_mode_serves_and_opens_its_episode_touching_nothing_else(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    secret = home / "Films" / "secret.mkv"
    secret.parent.mkdir()
    secret.write_bytes(b"\0" * 16)
    tools = Tools.find()
    copy = demo.prepare(tools)
    rt = demo.runtime_for(copy, tools)
    assert rt.config.endpoints == {} and dict(rt.keys.environ) == {}  # no toml, no key
    runtime.configure(rt)
    demo.isolate(copy.parent, home=home)
    try:
        with TestClient(create_app(rt, token=TOKEN, port=PORT, shiny_app=server.app),
                        base_url=BASE) as client:
            assert client.post("/auth", content=json.dumps({"token": TOKEN}),
                               headers=PAGE).status_code == 204
            assert client.get("/").status_code == 200
            seen = _session_values(client, {"capabilities", "status"})
            assert seen["status"] == {"endpoints": [], "ffmpeg": True}
            ep = rt.backend.open(str(copy / demo.VIDEO))  # probes, hashes, reads the sidecar
            view = episode_view(ep, video_url=None, audio_url=None)
            assert view["notes"] == [] and view["tracks"]
            texts = [r["text"] for r in view["rows"]]
            assert texts[2] == "We meet at a college noted for knowledge,"
            token = rt.media.issue(copy / demo.VIDEO, owner=ep.id)
            r = client.get(f"/media/{token}", headers={"Range": "bytes=0-9"})
            assert r.status_code == 206
            with pytest.raises(OpenError, match="only its own episode"):
                rt.backend.open(str(secret))
            with pytest.raises(DemoIsolationError):
                secret.read_bytes()  # and the hook would stop a bug that got past the backend
    finally:
        demo.release()
        runtime.configure(None)
        rt.queue.close()


def _session_values(client, outputs: set[str]) -> dict:
    values: dict = {}
    with client.websocket_connect("ws://127.0.0.1:8765/websocket/",
                                  headers={"Origin": BASE}) as ws:
        init = {f".clientdata_output_{name}_hidden": False for name in outputs}
        ws.send_text(json.dumps({"method": "init", "data": init}))

        def read() -> None:
            while not outputs <= values.keys() or not values.get("status", {}).get("ffmpeg"):
                values.update(json.loads(ws.receive_text()).get("values", {}))

        reader = threading.Thread(target=read, daemon=True)
        reader.start()
        reader.join(20)
    assert outputs <= values.keys(), f"the demo's session sent only {sorted(values)}"
    return values


# The child: the real `vid2sub serve --demo`, with `www/` pointing at a folder holding a ui.js,
# as tests/test_cli_serve.py runs it, so the frontend needn't be built.
CHILD = r"""
import sys
from pathlib import Path

from vid2sub.cli import main
from vid2sub.commands import serve

serve.WWW = Path(sys.argv[1])
raise SystemExit(main(sys.argv[2:]))
"""


@pytest.mark.media
@pytest.mark.skipif(os.name == "nt", reason="POSIX signals")
@pytest.mark.parametrize("sig", [signal.SIGINT, signal.SIGTERM])
def test_demo_mode_reads_no_vid2sub_toml_and_removes_its_copy_when_it_stops(tmp_path, sig):
    www = tmp_path / "www"
    www.mkdir()
    (www / "ui.js").write_text("// built\n", encoding="utf-8")
    scratch = tmp_path / "tmp"
    scratch.mkdir()
    broken = tmp_path / "vid2sub.toml"
    broken.write_text("[server\n", encoding="utf-8")  # would exit 78 if it were read
    env = {**os.environ, "TMPDIR": str(scratch), "VID2SUB_CONFIG": str(broken)}
    log = tmp_path / "serve.log"
    with log.open("wb") as out:
        proc = subprocess.Popen([sys.executable, "-c", CHILD, str(www), "serve", "--demo",
                                 "--no-browser", "--port", "0"],
                                env=env, stdout=out, stderr=subprocess.STDOUT)
    try:
        deadline = time.monotonic() + 60
        while "port " not in log.read_text(encoding="utf-8", errors="replace"):
            assert proc.poll() is None, log.read_text(encoding="utf-8", errors="replace")
            assert time.monotonic() < deadline, "the demo never started"
            time.sleep(0.1)
        port = log.read_text(encoding="utf-8").split("port ")[1].split(".")[0]
        while True:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=1):
                    break
            except OSError:
                assert time.monotonic() < deadline, "healthz never answered"
                time.sleep(0.1)
        (made,) = scratch.glob("vid2sub-demo-*")
        assert (made / "demo" / demo.VIDEO).is_file()
        proc.send_signal(sig)
        code = proc.wait(timeout=30)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
    assert code == (0 if sig == signal.SIGINT else 128 + signal.SIGTERM)
    assert list(scratch.glob("vid2sub-demo-*")) == []
```

- [ ] **Step 2: Run it; watch it fail.** `uv run pytest tests/test_demo_guard.py -q`. Expected:
  `E   ImportError: cannot import name 'demo' from 'vid2sub.web' (…/src/vid2sub/web/__init__.py)`.
- [ ] **Step 3: Write the code,** `src/vid2sub/web/demo.py`:

```python
"""The demo: `vid2sub serve --demo` serves a fresh copy of `demo/`, with a canned engine, and
touches nothing else on the machine (spec §21, §22.4, §22.7; the Phase 2 plan's Decision 6).

`demo/` holds no video. `prepare` copies it into a new private temporary folder, muxes the
public-domain `tests/fixtures/speech/jfk-14s.wav` under a still NYC-blue picture into `jfk.mp4`
(VP9 and Opus, which every Chromium plays, Playwright's included), and makes the copied sidecar's
header and identity name that MP4, so the episode opens as the M1 episode it is. The canned sidecar
and its subtitle files were made by the real pipeline (`make demo-sidecar`) with the canned engine:
the clip's words as Whisper heard them (recordings' demo transcript of the same speech, cut to
these 14 s) and a hand-written Japanese translation. Everything goes when the engine exits.

Demo isolation is as in recordings, but enforced by the app, not only watched by a test: a
Python audit hook (`isolate`) refuses, while the demo runs, any file written outside the demo's
folder, any file read in the person's home folder outside the demo, Python and vid2sub
themselves, and any connection or name lookup beyond this machine. The demo's backend opens only
episodes in its copy, and its runtime reads no vid2sub.toml and no key from the environment.
"""

from __future__ import annotations

import atexit
import os
import re
import shutil
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

import vid2sub
from vid2sub.cache import Cache
from vid2sub.config import Config
from vid2sub.engines.base import ChunkResult, ModelStamp
from vid2sub.engines.clients import KeyRing
from vid2sub.media.identity import full_sha256, identify
from vid2sub.media.probe import probe
from vid2sub.media.tools import Tools, run_tool
from vid2sub.parse import ParsedChunk
from vid2sub.store import header_for, now, sidecar_path
from vid2sub.subs.model import Segment, Word
from vid2sub.subs.sidecar import IdentityRecord, Sidecar, parse_sidecar, serialize
from vid2sub.web import runtime
from vid2sub.web.backend import Episode, LocalBackend, OpenError

REPO = Path(__file__).resolve().parents[3]
DEMO = REPO / "demo"
CLIP = REPO / "tests" / "fixtures" / "speech" / "jfk-14s.wav"
VIDEO = "jfk.mp4"
CACHE_BYTES = 200_000_000  # the demo's own cache, in its temporary folder

# The clip's words as Whisper heard them, in ms: recordings' demo transcript (demo/canned/
# transcripts/jfk-rice.json at 8deb039) from 0:30 to 0:44, moved to start at 0.
WORDS: tuple[tuple[str, int, int], ...] = (
    (" I", 0, 140), (" am", 140, 320), (" delighted", 320, 600), (" to", 600, 760),
    (" be", 760, 900), (" here,", 900, 1160), (" and", 1360, 2060), (" I", 2060, 2160),
    (" am", 2160, 2240), (" particularly", 2240, 2600), (" delighted", 2600, 3000),
    (" to", 3000, 3160), (" be", 3160, 3300), (" here", 3300, 3520), (" on", 3520, 3660),
    (" this", 3660, 3820), (" occasion.", 3820, 4180), (" We", 4940, 5540),
    (" meet", 5540, 5880), (" at", 5880, 6040), (" a", 6040, 6160), (" college", 6160, 6620),
    (" noted", 6620, 8240), (" for", 8240, 8480), (" knowledge,", 8480, 8880),
    (" in", 9360, 10120), (" a", 10120, 10240), (" city", 10240, 10520),
    (" noted", 10520, 10800), (" for", 10800, 11000), (" progress,", 11000, 11440),
    (" in", 11980, 12560), (" a", 12560, 12680), (" state", 12680, 12940),
    (" noted", 12940, 13220), (" for", 13220, 13420), (" strength,", 13420, 13780),
)
# A hand-written Japanese translation: each English run of cues (as the pipeline cuts the clip
# into cues, line breaks as spaces) with its Japanese. A sentence across two cues is one item.
JAPANESE: tuple[tuple[tuple[str, ...], str], ...] = (
    (("I am delighted to be here, and I am particularly delighted to be here on this",
      "occasion."), "ここに来られて、とてもうれしく思います。この機会に来られたことは格別の喜びです。"),
    (("We meet at a college noted for knowledge,",), "私たちが集うのは、知識で知られる大学、"),
    (("in a city noted for progress, in a state noted for strength,",),
     "進歩で知られる都市、力強さで知られる州です。"),
)
NO_TRANSLATION = "（訳はありません）"


class DemoMissing(Exception):
    """The demo isn't here: it lives in vid2sub's repository, not in an installed wheel."""


class DemoIsolationError(PermissionError):
    """The demo tried to touch something outside itself. A PermissionError, so Python's own
    best-effort writes (bytecode caches) shrug it off as they would any refused write."""


class CannedEngine:
    """A transcription engine that hears the demo clip's words, for the demo's one chunk."""

    name = "canned"
    max_chunk_s = 300.0
    supports_prompt = False

    def transcribe(self, chunk, *, language: str | None, prompt: str) -> ChunkResult:
        if chunk.index != 0:
            raise ValueError("the canned engine hears only the demo clip, in one chunk")
        words = tuple(Word(text=t, start_ms=s, end_ms=e) for t, s, e in WORDS)
        seg = Segment(text="".join(w.text for w in words), start_ms=words[0].start_ms,
                      end_ms=words[-1].end_ms, words=words)
        return ChunkResult(ParsedChunk((seg,), "en", {"en": 1.0}))

    def detect_language(self, chunk) -> dict[str, float]:
        return {"en": 1.0}

    def stamp(self) -> ModelStamp:
        return ModelStamp(self.name, "canned-jfk", "demo")

    def close(self) -> None:
        pass


def canned_ask(system: str, prompt: str, data_model):
    """translate.run's AskFn for the demo: the hand-written Japanese for each run of lines it
    knows, and NO_TRANSLATION for any other line (one a person edited, say)."""
    asked = re.findall(r"^\[(\S+)\] \(max \d+ characters\) (.*)$", prompt, flags=re.MULTILINE)
    items, i = [], 0
    while i < len(asked):
        for lines, text in JAPANESE:
            run = asked[i:i + len(lines)]
            if tuple(line for _, line in run) == lines:
                items.append({"src": [cid for cid, _ in run], "text": text})
                i += len(lines)
                break
        else:
            items.append({"src": [asked[i][0]], "text": NO_TRANSLATION})
            i += 1
    return data_model.model_validate({"items": items})


def mux(tools: Tools, out: Path) -> None:
    """The demo clip under a still picture, as an MP4 of VP9 and Opus, with no metadata."""
    ffmpeg = tools.need("ffmpeg")
    with tempfile.TemporaryDirectory(prefix="vid2sub-") as scratch:
        run_tool([ffmpeg, "-nostdin", "-v", "error", "-y",
                  "-f", "lavfi", "-i", "color=c=0x236192:s=640x360:r=2:d=14",
                  "-i", f"file:{CLIP}", "-map", "0:v", "-map", "1:a", "-shortest",
                  "-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "40", "-deadline", "realtime",
                  "-c:a", "libopus", "-b:a", "48k", "-map_metadata", "-1",
                  "-fflags", "+bitexact", f"file:{out}"], cwd=Path(scratch), timeout=120)


def prepare(tools: Tools) -> Path:
    """A fresh copy of `demo/` in a new private temporary folder, with its MP4 muxed and its
    sidecar's header naming that MP4; the folder is removed at exit. DemoMissing outside a
    checkout of vid2sub's repository."""
    if not (DEMO / VIDEO.replace(".mp4", ".vid2sub.jsonl")).is_file() or not CLIP.is_file():
        raise DemoMissing("the demo is in vid2sub's repository: run it from a checkout "
                          "(make demo)")
    folder = Path(tempfile.mkdtemp(prefix="vid2sub-demo-"))  # mode 0700
    atexit.register(shutil.rmtree, folder, ignore_errors=True)
    copy = folder / "demo"
    shutil.copytree(DEMO, copy)
    video = copy / VIDEO
    mux(tools, video)
    path = sidecar_path(video)
    side, _ = parse_sidecar(path.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="vid2sub-") as scratch:
        duration = probe(video, tools, scratch=Path(scratch)).duration_ms
    header = header_for(video, identify(video), duration)
    records = [r for r in side.records if not isinstance(r, IdentityRecord)]
    records.append(IdentityRecord(sha256=full_sha256(video), at=now()))
    path.write_text(serialize(Sidecar(header, tuple(records))), encoding="utf-8")
    return copy


class DemoBackend(LocalBackend):
    """LocalBackend, opening only episodes in the demo's copy."""

    def __init__(self, copy: Path, tools: Tools, cache: Cache):
        super().__init__(Config(), tools, KeyRing(environ={}), cache)
        self.copy = copy.resolve()

    def open(self, path: str) -> Episode:
        try:
            inside = Path(path).resolve().is_relative_to(self.copy)
        except (OSError, ValueError):
            inside = False
        if not inside:
            raise OpenError("the demo opens only its own episode")
        return super().open(path)


def runtime_for(copy: Path, tools: Tools) -> runtime.Runtime:
    """The demo's parts: no vid2sub.toml, no key from the environment, a cache in the demo's own
    folder, and a backend that opens only the copy's episodes."""
    cache = Cache(copy.parent / "cache", max_bytes=CACHE_BYTES)
    backend = DemoBackend(copy, tools, cache)
    built = runtime.build(backend.config, tools=tools, keys=backend.keys, cache=cache)
    return replace(built, backend=backend)


# ---- isolation --------------------------------------------------------------------------------

# The audit events that change the file system: each path argument's position, with the position
# of the dir_fd it is relative to, if any (Python's audit events table; os.replace is os.rename).
# shutil.rmtree removes through dir_fd, so a bare name there is resolved against that folder.
_WRITES: dict[str, tuple[tuple[int, int | None], ...]] = {
    "os.rename": ((0, 2), (1, 3)), "os.link": ((0, 2), (1, 3)), "os.symlink": ((1, 2),),
    "os.mkdir": ((0, 2),), "os.remove": ((0, 1),), "os.rmdir": ((0, 1),),
    "os.chmod": ((0, 2),), "os.chown": ((0, 3),), "os.utime": ((0, 3),),
    "os.truncate": ((0, None),), "shutil.rmtree": ((0, 1),), "shutil.copyfile": ((1, None),),
    "shutil.copymode": ((1, None),), "shutil.copystat": ((1, None),),
    "shutil.move": ((1, None),),
}
_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
_LOOPBACK = {"127.0.0.1", "::1", "localhost"}
_state: dict = {"folder": None, "home": None, "reads": (), "tempdir": None}


def isolate(folder: Path, *, home: Path | None = None) -> None:
    """Refuse, from now on in this process, writes outside `folder`, reads in `home` (the
    person's home folder) outside `folder` and Python's and vid2sub's own files, and any
    connection or name lookup beyond this machine. Temporary files go in `folder/tmp` (scratch,
    the redirect file, Shiny's upload folders), and bytecode isn't written, so a lazy import
    doesn't write beside the code. The hook is installed once and can't be removed (Python's
    rule); `release()` lets everything through again and puts the temporary folder back, as
    happens at exit, before the folder is removed."""
    scratch = folder / "tmp"
    scratch.mkdir(mode=0o700, exist_ok=True)
    _state["tempdir"] = tempfile.tempdir
    tempfile.tempdir = str(scratch)
    _state["folder"] = os.path.realpath(folder)
    _state["home"] = os.path.realpath(home if home is not None else Path.home())
    roots = (folder, sys.prefix, sys.base_prefix, Path(vid2sub.__file__).parent)
    _state["reads"] = tuple(os.path.realpath(p) for p in roots)
    sys.dont_write_bytecode = True
    if not _state.get("installed"):
        sys.addaudithook(_hook)
        _state["installed"] = True
    atexit.register(release)  # atexit runs last-in first: before prepare's removal of `folder`


def release() -> None:
    if _state["folder"] is not None:
        tempfile.tempdir = _state["tempdir"]
    _state["folder"] = None


def _inside(path: str, roots: Sequence[str], *, as_given: bool = False) -> bool:
    """Whether `path`, symlinks resolved, is in one of `roots`; with `as_given`, the path as
    written counts too (a read through a venv's symlink to uv's cache)."""
    seen = [os.path.realpath(path)] + ([os.path.abspath(path)] if as_given else [])
    return any(p == r or p.startswith(r.rstrip(os.sep) + os.sep) for p in seen for r in roots)


def _fd_folder(fd: int) -> str | None:
    """The folder an open directory descriptor names, where the OS says (macOS, Linux)."""
    try:
        if sys.platform == "darwin":
            import fcntl

            return os.fsdecode(fcntl.fcntl(fd, fcntl.F_GETPATH, bytes(1024)).split(b"\0")[0])
        return os.readlink(f"/proc/self/fd/{fd}")
    except (OSError, AttributeError):
        return None


def _target(value, dir_fd) -> str | None:
    """An event's path argument as an absolute path; None when there is none to check (a file
    descriptor), "" when it can't be told (a dir_fd the OS won't name), which is refused."""
    if not isinstance(value, (str, bytes, os.PathLike)):
        return None
    path = os.fsdecode(value)
    if os.path.isabs(path):
        return path
    if isinstance(dir_fd, int):
        folder = _fd_folder(dir_fd)
        return os.path.join(folder, path) if folder else ""
    return os.path.abspath(path)


def _refuse_write(path: str | None) -> None:
    if path is not None and (path == "" or not _inside(path, [_state["folder"]])):
        raise DemoIsolationError("the demo writes only inside its own folder")


def _hook(event: str, args: tuple) -> None:
    if _state["folder"] is None:
        return
    if event == "open" and args:
        mode = args[1] if len(args) > 1 else None
        flags = args[2] if len(args) > 2 else 0
        writes = (isinstance(mode, str) and bool(set(mode) & set("wax+"))) or (
            isinstance(flags, int) and bool(flags & _WRITE_FLAGS))
        if writes:
            _refuse_write(_target(args[0], None))
            return
        # A read by a bare name is relative to a dir_fd the event doesn't carry (shutil.rmtree's
        # walk), so only absolute paths are checked; vid2sub itself opens only those.
        raw = args[0]
        if not isinstance(raw, (str, bytes, os.PathLike)) or not os.path.isabs(os.fsdecode(raw)):
            return
        path = os.fsdecode(raw)
        if _inside(path, [_state["home"]]) and not _inside(path, _state["reads"], as_given=True):
            raise DemoIsolationError("the demo reads nothing of yours")
    elif event in _WRITES:
        for at, fd_at in _WRITES[event]:
            if len(args) > at:
                dir_fd = args[fd_at] if fd_at is not None and len(args) > fd_at else None
                _refuse_write(_target(args[at], dir_fd))
    elif event == "socket.connect" and len(args) > 1:
        address = args[1]
        if isinstance(address, tuple) and address and address[0] not in _LOOPBACK:
            raise DemoIsolationError("the demo connects to nothing beyond this machine")
    elif event in ("socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyaddr") and args:
        host = args[0].decode() if isinstance(args[0], bytes) else args[0]
        if host is not None and host not in _LOOPBACK:
            raise DemoIsolationError("the demo looks up no other machine")
```

  `scripts/demo_sidecar.py`:

```python
"""Make demo/'s canned sidecar and subtitle files with the real pipeline and the canned engine.

    make demo-sidecar        (uv run python scripts/demo_sidecar.py)

As recordings' demo/build.py makes its canned archive. vid2sub.web.demo muxes the clip; M1's
pipeline transcribes it with the canned engine (the clip's words) and translates it to Japanese
with the canned translation, exactly as `vid2sub run --from en --to ja` would; then the sidecar,
`jfk.en.srt` and `jfk.ja.srt` are copied into demo/. The MP4 isn't kept: `vid2sub serve --demo`
muxes its own and points the sidecar's header at it.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

from vid2sub import pipeline
from vid2sub.config import Config
from vid2sub.engines.clients import KeyRing
from vid2sub.media.tools import Tools
from vid2sub.store import sidecar_path
from vid2sub.web import demo

CONFIG = Config.model_validate({
    "endpoints": {"canned": {"base_url": "http://127.0.0.1:9/v1"}},
    "models": {
        "canned": {"endpoint": "canned", "model": "canned-jfk", "parser": "whisper.cpp",
                   "local": True},
        "canned-ja": {"endpoint": "canned", "model": "canned-ja", "task": "translate",
                      "local": True},
    },
})


def main() -> int:
    tools = Tools.find()
    with tempfile.TemporaryDirectory(prefix="vid2sub-demo-build-") as tmp:
        video = Path(tmp) / demo.VIDEO
        demo.mux(tools, video)
        options = pipeline.RunOptions(source_lang="en", targets=["ja"], model="canned",
                                      translate_model="canned-ja", formats=["srt"])
        ctx = pipeline.RunContext(config=CONFIG, tools=tools, keys=KeyRing(environ={}),
                                  options=options, engines={"canned": demo.CannedEngine()})
        pipeline.make_ask = lambda *args, **kwargs: demo.canned_ask  # the canned translation
        result = pipeline.run_one(str(video), ctx)
        if result.status != "done":
            print(f"the pipeline failed: {result.reason}", file=sys.stderr)
            return 1
        for path in (sidecar_path(video), video.with_name("jfk.en.srt"),
                     video.with_name("jfk.ja.srt")):
            shutil.copyfile(path, demo.DEMO / path.name)
            print(f"wrote demo/{path.name}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

  In `src/vid2sub/commands/serve.py`, replace the docstring's last sentences

```python
Without the built frontend (`www/ui.js`), serve refuses before it reads or binds anything (§18,
§23.5). The web modules are imported only when serve runs, so other commands don't load them, and
the Shiny app only once `runtime.configure()` has run, as recordings imports it.
```

  with

```python
Without the built frontend (`www/ui.js`), serve refuses before it reads or binds anything (§18,
§23.5). `--demo` serves a fresh copy of the demo instead, reading no vid2sub.toml and no key,
and isolated from everything else once it is set up (`vid2sub.web.demo`, spec §22.7). The web
modules are imported only when serve runs, so other commands don't load them, and the Shiny app
only once `runtime.configure()` has run, as recordings imports it.
```

  replace the type-checking imports

```python
    import uvicorn
    from starlette.types import ASGIApp
```

  with

```python
    import uvicorn
    from starlette.types import ASGIApp

    from vid2sub.media.tools import Tools
```

  replace `--config`'s argument

```python
    p.add_argument("--config", metavar="PATH", help="the vid2sub.toml to use")
```

  with

```python
    which = p.add_mutually_exclusive_group()
    which.add_argument("--config", metavar="PATH", help="the vid2sub.toml to use")
    which.add_argument("--demo", action="store_true",
                       help="serve a fresh copy of the demo episode, reading no vid2sub.toml "
                            "and touching nothing else")
```

  replace `run`'s imports

```python
    from vid2sub.engines.clients import quiet_libraries
    from vid2sub.web import auth, runtime
```

  with

```python
    from vid2sub.config import Config
    from vid2sub.engines.clients import quiet_libraries
    from vid2sub.web import auth, demo, runtime
```

  replace the config's line

```python
        config = load(args)
        sock = bind
```

  with

```python
        made = _demo() if args.demo else None
        config = Config() if args.demo else load(args)  # the demo reads no vid2sub.toml
        sock = bind
```

  replace the runtime's lines

```python
        rt = runtime.build(config)
        runtime.configure(rt)
        token = auth.new_token()
        app = create_app(rt, token=token, port=sock.getsockname()[1], shiny_app=shiny_app())
```

  with

```python
        rt = demo.runtime_for(*made) if made else runtime.build(config)
        runtime.configure(rt)
        token = auth.new_token()
        app = create_app(rt, token=token, port=sock.getsockname()[1], shiny_app=shiny_app())
        if made:
            demo.isolate(made[0].parent)  # from here on, the demo touches nothing else
```

  and add, directly above `def serve(`, so that it reads

```python
def serve(app: ASGIApp, sock: socket.socket, *, token: str, open_browser: bool,
```

  with

```python
def _demo() -> tuple[Path, Tools]:
    """The demo's fresh copy (spec §22.7), and the tools that made its video."""
    from vid2sub.media.tools import ToolFailed, ToolMissing, Tools
    from vid2sub.web import demo

    tools = Tools.find()
    try:
        return demo.prepare(tools), tools
    except demo.DemoMissing as err:
        raise CommandError(exitcodes.UNAVAILABLE, str(err)) from None
    except ToolMissing:
        raise CommandError(exitcodes.UNAVAILABLE, "the demo needs ffmpeg",
                           "install ffmpeg 6 or later (vid2sub doctor checks it)") from None
    except ToolFailed:
        raise CommandError(exitcodes.UNAVAILABLE, "ffmpeg couldn't make the demo's video",
                           "it needs ffmpeg built with libvpx and libopus") from None


def serve(app: ASGIApp, sock: socket.socket, *, token: str, open_browser: bool,
```

  In the `Makefile`, replace the `.PHONY` line

```make
.PHONY: setup build test test-utc test-js e2e lint leaks check hooks live readme brand skills help
```

  with

```make
.PHONY: setup build test test-utc test-js e2e demo demo-sidecar lint leaks check hooks live readme brand skills help
```

  and add the targets above `lint`:

```make
lint: ## Lint with ruff
```

  with

```make
demo: build ## Serve a fresh copy of the demo episode, touching nothing else (needs ffmpeg)
	uv run vid2sub serve --demo

demo-sidecar: ## Remake demo/'s canned sidecar and subtitles with the pipeline and the canned engine
	uv run python scripts/demo_sidecar.py

lint: ## Lint with ruff
```

  `demo/CREDITS.md`:

```markdown
# The demo

`vid2sub serve --demo` (`make demo`) serves a fresh copy of this folder. It holds no video: at
start-up vid2sub muxes `tests/fixtures/speech/jfk-14s.wav` under a still picture into `jfk.mp4`
in the copy. `make demo-sidecar` remakes the sidecar and subtitles here with the real pipeline
and the canned engine in `src/vid2sub/web/demo.py`.

| File | Source | License |
|---|---|---|
| `jfk.mp4` (made at start-up) | 14 s from 0:30 of "JFK at Rice University", https://commons.wikimedia.org/wiki/File:Jfk_rice_university_we_choose_to_go_to_the_moon.ogg (via `recordings`' demo, as `tests/fixtures/speech/jfk-14s.wav`) | Public domain (John F. Kennedy Presidential Library & Museum) |
| `jfk.vid2sub.jsonl`, `jfk.en.srt` | the clip's words with their times from `recordings`' demo transcript of the same speech (local Whisper output, `demo/canned/transcripts/jfk-rice.json` at 8deb039), cut into cues by vid2sub | Public domain speech; the transcript is Dan's, MIT here |
| `jfk.ja.srt` | a Japanese translation written for this demo | MIT |
```

  Then `make demo-sidecar`. Expected: `wrote demo/jfk.vid2sub.jsonl`, `wrote demo/jfk.en.srt`,
  `wrote demo/jfk.ja.srt`. `demo/jfk.en.srt` reads:

```text
1
00:00:00,000 --> 00:00:03,736
I am delighted to be here, and I am
particularly delighted to be here on this

2
00:00:03,820 --> 00:00:04,653
occasion.

3
00:00:04,940 --> 00:00:09,276
We meet at a college noted for knowledge,

4
00:00:09,360 --> 00:00:13,780
in a city noted for progress,
in a state noted for strength,
```

  and `demo/jfk.ja.srt`:

```text
1
00:00:00,000 --> 00:00:04,653
ここに来られて、とてもうれしく思います。この機会に来られたことは格別の喜びです。

2
00:00:04,940 --> 00:00:09,276
私たちが集うのは、
知識で知られる大学、

3
00:00:09,360 --> 00:00:13,780
進歩で知られる都市、
力強さで知られる州です。
```

  The sidecar has 9 lines: the header, the transcript, `en` and `ja` renditions, their two heads,
  two projection records and an identity record (its ids and times differ from run to run).
- [ ] **Step 4: Run the checks; they pass.** `uv run pytest tests/test_demo_guard.py -q`.
  Expected: `7 passed`. By hand: `TMPDIR=$(mktemp -d) uv run vid2sub serve --demo --no-browser
  --port 0`, then Ctrl-C: a `vid2sub-demo-…` folder is in that TMPDIR while it runs and gone after.
  `make check`. Expected: `933 passed, 2 skipped, 8 deselected` twice, `Test Files  5 passed (5)`,
  `All checks passed!`, `no leaks found`. The line-length check on the Python files prints nothing.
- [ ] **Step 5: Each guard fails its tests without its fix.** `git add demo
  scripts/demo_sidecar.py src/vid2sub/web/demo.py tests/test_demo_guard.py
  src/vid2sub/commands/serve.py Makefile`. Then, for each row, make the change in `demo.py` (the
  sixth row: `serve.py`), run `uv run pytest tests/test_demo_guard.py -q`, see it fail, and
  restore with `git checkout -- <the file>`. The last column is what this listing's build saw.

| Guard | Change | To | Failed |
|---|---|---|---|
| the hook | `sys.addaudithook(_hook)` | `pass` | 4 |
| the backend's copy only | `the two lines from `if not inside:`` | `pass` | 1 |
| temporary files inside | `tempfile.tempdir = str(scratch)` | `pass` | 4 |
| a descriptor's folder | `return os.path.join(folder, path) if folder else ""` | `return os.path.abspath(path)` | 1 |
| no key from the environment | `super().__init__(Config(), tools, KeyRing(environ={}), cache)` | `super().__init__(Config(), tools, KeyRing(), cache)` | 1 |
| no vid2sub.toml (serve.py) | `config = Config() if args.demo else load(args)  # …` | `config = load(args)` | 2 |
| the copy removed | `atexit.register(shutil.rmtree, folder, ignore_errors=True)` | `pass` | 2 |
| no reads in the home folder | `raise DemoIsolationError("the demo reads nothing of yours")` | `pass` | 2 |
| no connections | `raise DemoIsolationError("the demo connects to nothing beyond this machine")` | `pass` | 1 |

- [ ] **Step 6: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(web): 🤖 vid2sub serve --demo serves a fresh copy of the demo episode, and the app itself refuses anything the demo would touch outside it

src/vid2sub/web/demo.py (spec §21, §22.4, §22.7; the Phase 2 plan's Decision 6). demo/ holds no
video: prepare() copies it into a new mkdtemp folder (removed at exit), muxes
tests/fixtures/speech/jfk-14s.wav under a still NYC-blue picture into jfk.mp4 (VP9 and Opus, which
Playwright's Chromium plays; it has no H.264 or AAC, as recordings found), and points the copied
sidecar's header and identity at that MP4. demo/'s canned sidecar and its jfk.en.srt and
jfk.ja.srt were made by the real pipeline (scripts/demo_sidecar.py, `make demo-sidecar`, as
recordings' demo/build.py makes its archive) with the canned engine: the clip's 37 words with
Whisper's times from recordings' demo transcript of the same speech (0:30 to 0:44, moved to 0),
and a hand-written Japanese translation (canned_ask, a sentence across two cues as one item).
The demo's runtime reads no vid2sub.toml and no key (Config(), KeyRing(environ={})), caches in its
own folder, and its DemoBackend opens only episodes in the copy. `serve --demo` (exclusive with
--config) prepares it, then demo.isolate(): an audit hook, as recordings' demo guard but enforced
by the app rather than only watched by a test, refusing writes outside the demo's folder (each of
Python's write events, shutil.rmtree's removals through a folder's descriptor resolved by the OS),
reads in the home folder outside the demo, Python and vid2sub, and lookups and connections beyond
this machine; temporary files go in the folder's tmp/, bytecode isn't written, and at exit the
hook lets go before the folder is removed. `make demo` builds and serves it.

The new test failed first with: ImportError: cannot import name 'demo' from 'vid2sub.web'.
Each guard was then reverted in turn and its tests failed: the hook not installed (4 failed),
the backend opening anything (1), temporary files left in TMPDIR (4), a descriptor-relative path
not followed (1), keys from the environment (1), the demo reading vid2sub.toml (2), the copy
never removed (2), reads in the home folder allowed (2), connections allowed (1).

Docs read: Python's audit events table (os.rename, os.remove, os.rmdir, os.mkdir, os.chmod,
os.utime, os.symlink, os.link, os.truncate, shutil.rmtree with their dir_fd arguments; open's
path, mode, flags; socket.connect, socket.getaddrinfo) and sys.addaudithook (hooks can't be
removed); shutil.rmtree's fd-based walk; tempfile.tempdir; fcntl F_GETPATH (macOS) and
/proc/self/fd (Linux); ffmpeg's libvpx-vp9 and libopus encoder options; recordings'
test_demo_guard.py and settings.py (its demo copy and atexit removal).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 13
Co-Authored-By: <the model's own line>
```

  `git commit -F .git/COMMIT_MSG` (the files are staged from Step 5), then
  `git log -1 --format='%(trailers)'` shows `Plan:`.

#### Round 13b: the hostile fixtures, and the shell in a browser

- [ ] **Step 7: Write the failing tests,** `tests/test_hostile_fixtures.py`:

```python
"""The hostile fixtures (spec §6.3, §22.4; S26) are what the browser tests expect: M1's parser
keeps a subtitle's text and only `<i>` of its markup, so a `<script>`, an `<img onerror>`, `<font>`
or an ASS override reaches the editor as inert text, which it must show as text."""

import json
from pathlib import Path

from vid2sub.subs.formats import parse_subtitles

HOSTILE = Path(__file__).parent / "fixtures" / "hostile"


def test_a_hostile_srt_keeps_its_text_and_only_italics():
    cues = parse_subtitles((HOSTILE / "hostile.srt").read_bytes(), "srt")
    assert [c.text for c in cues] == [
        "window.__pwned = 1after the script",
        "red bold <i>italic</i>",
        "an image",
        "a link &lt;b&gt; &amp;",
        "braces *gone?",
    ]


def test_a_hostile_ass_keeps_its_text_and_only_italics():
    cues = parse_subtitles((HOSTILE / "hostile.ass").read_bytes(), "ass")
    assert [c.text for c in cues] == [
        "moved, huge and red",
        "<i>italic</i> and bold\nsecond line",
        "m 0 0 l 100 0 100 100after a drawing",
        "window.__pwned = 5tags in ASS",
    ]


def test_the_hostile_names_are_markup_bidi_and_paths():
    names = json.loads((HOSTILE / "names.json").read_text(encoding="utf-8"))["names"]
    assert any("<img" in n for n in names) and any("<script>" in n for n in names)
    assert any("\u202e" in n for n in names) and "../../etc/passwd" in names
```

  and `tests/e2e/test_shell.py`:

```python
"""The shell in Chromium, against `vid2sub serve --demo` and a hostile vid2sub.toml: the top bar
says this is the local engine, every hostile name shows as plain text, and nothing it carries
runs (spec §6.3, §19.2; S26). Run with `make e2e`."""

import json
from pathlib import Path

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e

HOSTILE = Path(__file__).parents[1] / "fixtures" / "hostile"
NAMES = json.loads((HOSTILE / "names.json").read_text(encoding="utf-8"))["names"]


def test_the_demo_is_the_local_engine_with_nothing_configured(page):
    expect(page.get_by_test_id("engine")).to_have_text("Local engine")
    expect(page.get_by_test_id("endpoint")).to_have_count(0)  # the demo reads no vid2sub.toml
    expect(page.get_by_text("ffmpeg missing")).to_have_count(0)


def test_hostile_names_show_as_plain_text_and_run_nothing(open_page, launch, tmp_path):
    toml = "".join(f"[endpoints.{json.dumps(name, ensure_ascii=False)}]\n"
                   'base_url = "http://127.0.0.1:9/v1"\n' for name in NAMES)
    watch = open_page(launch(tmp_path / "hostile", toml=toml))
    page = watch.page
    shown = page.get_by_test_id("endpoint")
    expect(shown).to_have_count(len(NAMES))
    assert shown.all_inner_texts() == [f"{name}: cloud" for name in NAMES]
    assert page.locator("[data-testid=endpoint] *").count() == 0  # text only, no element
    assert page.evaluate("() => window.__pwned") is None
    assert watch.errors == [] and watch.violations() == []
```

- [ ] **Step 8: Run them; watch them fail.** `uv run pytest tests/test_hostile_fixtures.py -q`.
  Expected: `E       FileNotFoundError: [Errno 2] No such file or directory:
  '…/tests/fixtures/hostile/hostile.srt'`, then `3 failed`; `uv run pytest -m e2e
  tests/e2e/test_shell.py -q` stops at collection with the same for `names.json`.
- [ ] **Step 9: Write the code.** `tests/fixtures/hostile/hostile.srt`:

```text
1
00:00:00,500 --> 00:00:02,000
<script>window.__pwned = 1</script>after the script

2
00:00:02,500 --> 00:00:04,000
<font color="#ff0000">red</font> <b>bold</b> <i>italic</i>

3
00:00:04,500 --> 00:00:06,000
<img src=x onerror="window.__pwned = 2">an image

4
00:00:06,500 --> 00:00:08,000
<a href="javascript:window.__pwned=3">a link</a> &lt;b&gt; &amp;

5
00:00:08,500 --> 00:00:10,000
{\an8}{\b1}braces{\b0} <style>*{display:none}</style>gone?
```

  `tests/fixtures/hostile/hostile.ass`:

```text
[Script Info]
ScriptType: v4.00+
PlayResX: 640
PlayResY: 360

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.50,0:00:02.00,Default,,0,0,0,,{\an8}{\fs99}{\1c&H0000FF&}moved, huge and red
Dialogue: 0,0:00:02.50,0:00:04.00,Default,,0,0,0,,{\i1}italic{\i0} and {\b1}bold{\b0}\Nsecond line
Dialogue: 0,0:00:04.50,0:00:06.00,Default,,0,0,0,,{\p1}m 0 0 l 100 0 100 100{\p0}after a drawing
Dialogue: 0,0:00:06.50,0:00:08.00,Default,,0,0,0,,<script>window.__pwned = 5</script><img src=x onerror="window.__pwned = 6">tags in ASS
```

  `tests/fixtures/hostile/names.json` (the bidi override and the emoji as JSON escapes, so no
  file holds a raw bidi character):

```json
{
  "why": "Names and titles that must show as plain text wherever the app shows them (spec §6.3, S26): file names, YouTube titles, endpoint names from vid2sub.toml.",
  "names": [
    "<img src=x onerror=\"window.__pwned = 7\">",
    "<script>window.__pwned = 8</script>",
    "\u202ekcod.exe",
    "\ud83c\udfac <b>Bold</b> & <i>it</i>",
    "../../etc/passwd",
    "CON"
  ]
}
```

  At the end of `tests/fixtures/CREDITS.md`'s table, add:

```markdown
| `hostile/hostile.srt`, `hostile/hostile.ass`, `hostile/names.json` | written for these tests: markup, ASS overrides, a bidi override and path-like names that must show as plain text (spec §6.3, S26) | MIT |
```

  In `tests/e2e/conftest.py`, replace the docstring's first paragraph

```python
"""Servers and pages for the browser tests (spec §22.7): the real `vid2sub serve`, on a free port,
in a child process with its own TMPDIR and an empty vid2sub.toml, and a page signed in through
the launch link as a person's browser is (Task 9's token flow, scripted).
```

  with

```python
"""Servers and pages for the browser tests (spec §22.7): the real `vid2sub serve --demo` (a canned
engine over a copy of demo/), on a free port, in a child process with its own TMPDIR, and a page
signed in through the launch link as a person's browser is (Task 9's token flow, scripted).
`start_server(..., toml=...)` serves a vid2sub.toml instead of the demo.
```

  replace `start_server`'s head, down to its `Popen`

```python
def start_server(tmp: Path, *args: str, port: int = 0) -> Server:
    """`vid2sub serve --no-browser` on `port` (0: any free one), up and answering."""
    if not (WWW / "ui.js").is_file():
        pytest.fail("the frontend isn't built: run make build (make e2e does)")
    tmp.mkdir(parents=True, exist_ok=True)
    config = tmp / "vid2sub.toml"
    config.write_text("", encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if not k.startswith("VID2SUB_")}
    env["TMPDIR"] = str(tmp)
    log = tmp / "server.log"
    with log.open("wb") as out:
        proc = subprocess.Popen(
            [sys.executable, "-m", "vid2sub", "serve", "--no-browser", "--port", str(port),
             "--config", str(config), *args],
            env=env, stdout=out, stderr=subprocess.STDOUT)
```

  with

```python
def start_server(tmp: Path, *args: str, port: int = 0, toml: str | None = None) -> Server:
    """`vid2sub serve --no-browser --demo` on `port` (0: any free one), up and answering; with
    `toml`, that vid2sub.toml instead of the demo."""
    if not (WWW / "ui.js").is_file():
        pytest.fail("the frontend isn't built: run make build (make e2e does)")
    tmp.mkdir(parents=True, exist_ok=True)
    which = ["--demo"]
    if toml is not None:
        config = tmp / "vid2sub.toml"
        config.write_text(toml, encoding="utf-8")
        which = ["--config", str(config)]
    env = {k: v for k, v in os.environ.items() if not k.startswith("VID2SUB_")}
    env["TMPDIR"] = str(tmp)
    log = tmp / "server.log"
    with log.open("wb") as out:
        proc = subprocess.Popen(
            [sys.executable, "-m", "vid2sub", "serve", "--no-browser", "--port", str(port),
             *which, *args],
            env=env, stdout=out, stderr=subprocess.STDOUT)
```

  and replace `launch`'s head

```python
def launch():
    """Starts another server, `launch(tmp, *args, port=0)`, stopped at the end of the test."""
    started: list[Server] = []

    def run(tmp: Path, *args: str, port: int = 0) -> Server:
        started.append(start_server(tmp, *args, port=port))
        return started[-1]
```

  with

```python
def launch():
    """Starts another server, `launch(tmp, *args, port=0, toml=None)`, stopped at the end."""
    started: list[Server] = []

    def run(tmp: Path, *args: str, port: int = 0, toml: str | None = None) -> Server:
        started.append(start_server(tmp, *args, port=port, toml=toml))
        return started[-1]
```

- [ ] **Step 10: Run the checks; they pass.** `uv run pytest tests/test_hostile_fixtures.py -q`.
  Expected: `3 passed`. `make e2e`. Expected: `6 passed, 942 deselected` (Task 12's four, now
  against the demo, and these two). `make check`. Expected: `936 passed, 2 skipped, 10 deselected`
  twice, `Test Files  5 passed (5)`, `All checks passed!`, `no leaks found`.
- [ ] **Step 11: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
test(e2e): 🤖 the browser tests run against vid2sub serve --demo, and hostile names show as plain text and run nothing

tests/e2e/conftest.py's server is now `vid2sub serve --demo` (spec §22.7: a canned engine over a
copy of demo/), isolated as the app runs it; `start_server(..., toml=...)` and `launch(...,
toml=...)` serve a vid2sub.toml instead. tests/fixtures/hostile/ holds the hostile files S26
names (spec §6.3, §22.4): an SRT with <script>, <font>, <img onerror>, a javascript: link, HTML
entities and ASS braces; an ASS file with position, size and colour overrides, \N, a drawing and
HTML; and names.json, names and titles with markup, a bidi override, an emoji and path-like
names. tests/test_hostile_fixtures.py pins what M1's parser makes of them, text and only <i>, so
the editor's tests (Task 14) know what reaches React. tests/e2e/test_shell.py: the demo is the
local engine with nothing configured; a vid2sub.toml whose endpoints carry every hostile name
shows each as plain text in the top bar, with no element made from it, no script run
(window.__pwned stays unset) and no console error or CSP violation.

The new tests failed first with: FileNotFoundError: [Errno 2] No such file or directory:
'…/tests/fixtures/hostile/hostile.srt' (3 failed), and the e2e module with the same for
names.json.

Docs read: TOML 1.0's quoted keys and basic strings (a name with quotes and backslashes,
json.dumps-escaped, non-ASCII kept literal); pysubs2's SRT and ASS readers through
subs.formats.parse_subtitles; Playwright's Locator.all_inner_texts.

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 13
Co-Authored-By: <the model's own line>
```

  `git add tests/fixtures/hostile tests/fixtures/CREDITS.md tests/test_hostile_fixtures.py
  tests/e2e/test_shell.py tests/e2e/conftest.py`, `git commit -F .git/COMMIT_MSG`, then
  `git log -1 --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 12: Review, look forward, close.** The Tier 2 review from `$(cat .git/TASK_BASE)`
  (`AGENTS.md`, *Reviews*). Worth the reviewers' time: that every write event Python audits is
  covered, `shutil.rmtree`'s descriptor-relative removals included, and that a path the OS won't
  name is refused, not let through; that the demo reads no vid2sub.toml and no key, and opens only
  its copy; that nothing the demo starts with (`prepare`, imports) runs after `isolate` in a way
  the hook would break; that the copy goes on Ctrl-C and SIGTERM; that the canned sidecar holds no
  path or personal data (it names `jfk.mp4` only); that the hostile names show as text. Known and
  accepted: the hook can't watch child processes (ffprobe, ffmpeg, the browser opener), which the
  demo starts only on its own files; reads by a bare name (a descriptor-relative walk) aren't
  checked. The forward review over Tasks 14, 16, 17, 19 and 21 (the notes *For later tasks*
  above). The docs this task made untrue: none expected (the README's *Use* block will name
  `make demo`: Task 22). Then the close, its own commit, holding this plan with this task's
  boxes ticked and **Now** set to `Task 14: The editor view, open.`; S26 stays `planned` (Task 14
  shows the hostile subtitles and the overlay), with the message in `.git/CLOSE_MSG`:

```text
docs(plan): 🤖 close Task 13: The end-to-end harness and the demo

Drift: none
Rulings: none
Phase-end: none
Forward: none
Tier: 2
Rounds: <Matt's code-review, Standards and Spec in two subagents; any re-review>
Findings: none

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md Task 13
Co-Authored-By: <the model's own line>
```

  `git add docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md`, `git commit -F .git/CLOSE_MSG`.

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
| Task 7 (planning) | Minor | `src/vid2sub/web/backend.py` | With no model named, `retranslate` asks the route's servers which models they serve before it knows anything is stale, so a server that's down gives an error where "nothing is stale" would do | open |
| Task 6 (planning) | Minor | `src/vid2sub/store.py` | A crash (not an exception) between a projection record and its file write leaves the record naming the new head while the file holds the old one; an outside edit to that file before the next Save would then replace the new head without a conflict | open |
| Task 12 (planning) | Minor | `frontend/package.json` | `npm install` reports 8 audit findings in the pinned dev dependencies (the same pins as `recordings`); none is triaged yet, so Task 21 or the phase end checks whether any reaches the built `ui.js` | open |
