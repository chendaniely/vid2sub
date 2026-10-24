# vid2sub Phase 4 (M4): Pages and releases — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking. Every rule for running a task is in `AGENTS.md`; this
> plan never restates them.

**Goal:** the editor at `chendaniely.github.io/vid2sub/` with no install: open a local folder,
edit, and save next to the video in Chrome and Edge, or download in Safari and Firefox; a demo
clip; tagged releases with build provenance; and an install index so
`uv tool install 'vid2sub[mac]' --index https://chendaniely.github.io/vid2sub/simple/` works.

**Architecture:** the same shinyreact server and React UI as the local app, run in the browser
through Shinylive with a `BrowserBackend`: React holds the file handles and hands Python text;
Python returns new file contents; React writes them. `pages.yml` is the only workflow that
deploys Pages; `release.yml` builds wheels on a `v*` tag; the index is generated from releases.

**Tech Stack:** as Phase 2's, plus Shinylive 0.8.12 (assets 0.10.15, Pyodide 0.27.7, Python
3.12.7, pydantic 2.10.5), the File System Access API, GitHub Pages from Actions, and GitHub's
build-provenance attestations.

**Spec:** `docs/superpowers/specs/2026-10-14-vid2sub-design.md`

**Now:** Task 1: The browser backend, open. (Phase 4 starts after Phase 3's PR merges; its
listings are run and revised at its phase start.)

## Decisions made while planning (review these)

1. **The M4 exit test runs in two parts.** Before the PR (Task 11), Dan tests the site
   `make pages` builds, served on this machine: Chrome's save with the re-read (S47), Safari's
   download (S48) and the demo (S50). Pages deploys only from `main` or a release (spec §23.3),
   tags are Dan's, and the index lists only releases. So the live site, the first release and
   the install from the index (S47 live, S51, S52) run after the merge, as the phase end's step
   9. Their results go out in a short PR from `phase-4-live`, which also carries the status
   line's `merged` entry, since no Phase 5 start follows to carry it.
2. **`pages.yml` runs when `release.yml` succeeds, not on `release: published`.** A release that
   `release.yml` creates with `GITHUB_TOKEN` starts no other workflow (GitHub's docs: "events
   triggered by the `GITHUB_TOKEN`, with the exception of `workflow_dispatch` and
   `repository_dispatch`, will not create a new workflow run"). As specced, then, the index
   would never list a new release (S52). So `pages.yml` triggers on
   `workflow_run: {workflows: [release], types: [completed]}` and deploys only when that run
   succeeded, was a tag push in this repository, and built from main's own files. The run's ref
   is `main`, so the `github-pages` environment needs no tag rule, and `release.yml` keeps only
   the three write permissions its publish job needs (Task 7, Task 8; found while writing Task
   8). The other ways each cost more: `release.yml` dispatching `pages.yml` needs
   `actions: write`, and a GitHub App or personal token is a secret. **This changes the spec**
   (§23.3's triggers), so it waits for Dan's yes at approval.
3. **What both backends do with an episode's files moves into `vid2sub.web.folder`** (Task 1): a
   refactor of Phase 2's `LocalBackend`, with no change in behaviour; `pipeline.video_change`
   moves to `subs.sidecar` and `MEDIA_SUFFIXES` to `subs.naming`, the pipeline keeping both
   names. The Pages bundle grows by `web.folder`, `web.browser`, `store`, `security`, `media`
   and `media.identity`, each importing only the standard library and the pure packages.
   **This changes the spec** (§3.2's tree, §19.1 and §21 say what the bundle holds), so it
   waits for Dan's yes at approval.
4. **`BrowserBackend` runs `store` unchanged** on a staged copy of the files in Pyodide's
   in-memory file system, rather than on a second copy of the write logic (Task 1).
5. **The page hands Python each file's bytes** (base64 on the wire), not decoded text, so a
   projection's hash is of the bytes on disk (§15.2) (Task 3). **This changes the spec** (§14.6
   and §21 say "text"), so it waits for Dan's yes at approval.
6. **A browser Save is kept only once the page has written its files** (Task 3): it waits in the
   tab's queue for up to 300 s, and merges again, up to 3 times, if the sidecar changed in
   between; otherwise nothing is saved, and the notice says so.
7. **A download Save offers the whole set every time:** the sidecar and every subtitle file it
   projects, and the glossary, a quarter second apart, so a download the browser blocked comes
   again (Task 3).
8. **Python decides which files are an episode's, from their names alone** (Task 3): a name
   vid2sub writes, spelled in another case, is staged under vid2sub's spelling; two names one
   case apart are refused; a name vid2sub couldn't stage is left out of the listing.
9. **The vendored packages are unpacked into the app folder, not listed in `requirements.txt`**
   (Task 2): Shinylive hands what that file lists to micropip, which fetches from PyPI, so it
   lists only Pyodide's own pydantic. **This changes the spec** (§21: "lists them in
   `requirements.txt`"), so it waits for Dan's yes at approval; Task 2 rewords §21.
10. **Shinylive's assets are pinned by SHA-256,** checked before unpacking, and the `dev` group
    includes the `pages` group, so `make check`'s environment can build the site (Task 2).
11. **`pages/site/start.js` replaces Shinylive's export template** (Tasks 2 and 4). It refuses to
    run in a frame before loading anything; it revalidates the deploy's unhashed files (Review
    Focus 3); it stops `message` events from other origins; and it drops the query string.
    Shinylive 0.10.15's own listener checks no origin and pastes what it is sent into Python it
    runs, so without the filter a page that opened the editor could run Python in it and send
    the open episode away (found by Task 4's security review; a test reproduces it). Any
    Shinylive upgrade must re-check its `message` listeners against the filter.
12. **`save = "download"` means Python hands the files back,** and the page writes or downloads
    them. Where `generate` is false the server's `status` output is null and the endpoint check
    never starts (Task 1).
13. **In the browser nothing probes the video** (Tasks 1 and 2): its duration comes from its
    sidecar, and the player tries the video itself (an unprobed container reads as playable)
    rather than asking for the playback audio, which needs ffmpeg.
14. **Shiny's busy-indicators replacement is labelled `1.8.0.post1`, not `1.8.0+vid2sub`**
    (Task 2): in Pages, Shinylive's Starlette 0.38.1 answers a path holding "+" with 404. Both
    sort above Shiny's own 1.8.0, as Phase 2 Task 13 needs.
15. **`make pages-serve` sends `Cache-Control: max-age=600`** on every response (Task 2), as
    GitHub Pages is widely reported to; GitHub's docs don't say, so Task 11 checks it on the live
    site.

## Global Constraints

Phase 2's Global Constraints, in full (`docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md`),
plus:

- The Pages editor refuses to run inside a frame (checked in JS), never persists folder handles,
  and touches no network beyond its own files (spec §6.9).
- Video bytes never enter Python (wasm32 has a 4 GB address space); React re-reads the sidecar
  before writing (spec §14.6, §21).
- The site never fetches from PyPI: pysubs2, opencc-purepy and charset-normalizer are vendored as
  wheels (spec §21).
- `pages.yml` is the only workflow that deploys Pages; no `gh-pages` branch (spec §23.3).
- No PyPI: releases go to GitHub Releases, installs through the index (Dan, 2026-10-14, §23.4).
- Tags, releases, repo settings and Pages settings are Dan's (`AGENTS.md`, *Stops*).

## Review Focus

1. **The folder's permission revoked, or the folder moved or renamed, while an episode is open
   in Chrome:** Save writes nothing half-way, says what happened, and asks for the folder again;
   the edits stay in the tab and its draft. (Task 3's tests.)
2. **A multi-gigabyte video:** opening it reads only what the quick hash needs, and the video
   plays from a blob URL; its bytes never reach Python, and the tab's memory stays flat.
   (Task 3's tests.)
3. **A visitor whose browser cached the previous deploy's Shinylive assets:** after a new deploy
   the page loads one consistent version, or says to reload, and never mixes old and new files.
   (Task 2's and Task 7's tests.)
4. **`release.yml` run again for a tag that already has a release** (a re-run, or the same tag
   pushed again): it fails rather than replacing a published wheel or sdist, since a release
   asset is never overwritten. (Task 8's tests.)
5. **A release with no wheel, or a deleted one:** the index skips it and never links a file that
   isn't there; an install still gets the newest good release. (Task 9's tests.)

***

### Task 1: The browser backend

**Tier:** 2 · **Scenarios:** S47

**Why it is built this way** (read 2026-10-24):
- **The rules exist once.** LocalBackend's own module imports ffprobe's tools, the engines, the
  pipeline and the network client, none of which Pyodide has, so what both backends share (open,
  the edit rules, Save, the pick of a conflicted version) moves, unchanged, into a Pages-safe
  `web.folder`, and LocalBackend keeps what needs this machine. Every existing backend, server,
  views, demo and pipeline test passes unchanged: the guard for the move.
- **On a staged copy, through `vid2sub.store`.** The browser backend writes the bytes the page
  hands over into a private staging folder (Pyodide's in-memory file system; a temporary folder
  on the host), runs `web.folder` there, and hands back the bytes of each file that changed, the
  sidecar first. So the browser's Save is the local one, compare-and-swap, projections and
  foreign files included, and the Pages bundle grows by `vid2sub.store`, `vid2sub.security`,
  `vid2sub.media` and `vid2sub.media.identity`, each standard library and pure packages only.
  Round 1a checks first, in the real Pyodide 0.27.7, that `safe_write` works there.
- **Bytes, not decoded text.** A projection's hash is of a file's bytes (spec §15.2), so a
  subtitle file with a BOM, or in GBK, must arrive as it is on disk; spec §21's "as text" means
  the files' contents, never the video's. The page's half (reading them, base64 on the wire) is
  Task 3's.
- **A Save keeps nothing.** It returns the saved episode and the bytes to write; the caller keeps
  the episode only once the page has written them (Task 3), so a write that fails leaves the edits
  unsaved in the tab (Review Focus 1). Given the folder's files read again (Chrome), the merge is
  the union of the folder's sidecar and the episode's own records: the outside edits recorded at
  open live only in the episode until a Save writes them. Given none (Safari's read-only folder),
  Save builds on the files the episode last saw (`BrowserEpisode.files`).
- **Which files are an episode's is Python's call**, from the folder's names alone (`listing`),
  so the rules stay in one place; a name vid2sub writes, in another case, is staged under
  vid2sub's (macOS and Windows see one file), so someone else's `Show.EN.SRT` is still left alone.
- **Pyodide's WebLoop.** `runtime.blocking` works in Pyodide with or without `runtime.INLINE`:
  Pyodide 0.27.7's `run_in_executor` runs the call synchronously on the loop's thread
  (`pyodide/webloop.py`: "Best we can do is to run func(args) in this thread"). INLINE only skips
  the executor; round 1a's check says so.
- **The Pyodide check is a Vitest test** (`frontend/src/pyodide.test.ts`, Vitest's node
  environment), so `make check` and CI's frontend job run it: only Pyodide's core loads (no
  package, so no network after `npm ci`), and the modules it imports need only the standard
  library. It adds `pyodide@0.27.7` to the frontend's dev dependencies, which Task 6's harness
  uses too (see the close's Forward line).

**Files:**
- Create: `frontend/src/pyodide.test.ts`, `src/vid2sub/web/folder.py`,
  `src/vid2sub/web/browser.py`, `tests/test_browser_backend.py`, `tests/test_web_browser.py`
- Modify: `frontend/package.json` and `frontend/package-lock.json` (`pyodide` 0.27.7, exact),
  `src/vid2sub/web/backend.py` (what both backends share moves to `web.folder`),
  `src/vid2sub/subs/sidecar.py` (`video_change`, from the pipeline), `src/vid2sub/subs/naming.py`
  (`MEDIA_SUFFIXES`, from the pipeline), `src/vid2sub/pipeline.py` (imports both),
  `src/vid2sub/web/server.py` (`status` null and no endpoint check where `generate` is false),
  `tests/test_pages_imports.py` (the bundle's new members), `docs/architecture.md`, the spec
  (§4.1's layout, §19.1, §21's bundle)
- Modify at the close: this plan

**Interfaces:**
- Consumes: Phase 2's Pages-safe server (Phase 2 Task 14, round 14a): `vid2sub.web.server` and
  `views` import only what the bundle has; the types they share are in `vid2sub.web.episode`; the
  local runtime is configured, not imported, and `runtime.blocking` is the one place blocking
  calls run. `blocking` already runs inline when `runtime.INLINE` (`sys.platform ==
  "emscripten"`), which Phase 2 couldn't check in Pyodide; this task checks it first. So Pages
  configures a `Runtime` holding a `BrowserBackend` before importing the server, as
  `recordings`' `pages/app.py` does. These `Runtime` parts are local-only: `media_for` (Pages
  plays a blob URL), `reachable`, and, from Phase 2 Tasks 17–19, `retranslate`, `endpoint_models`
  and `job_context`. The server offers Retranslate, the settings drawer and the Jobs page only
  where `capabilities.generate` is true (Phase 2 Decision 23), so Pages calls none of the last
  three; its `session` (a `vid2sub.web.settings.Session`, bundled) still gives Save's default
  formats. This task says what each does in the browser.
- Produces:
  - `vid2sub.web.folder` (Pages-safe; both backends call it, holding their own open episodes
    and, for Save and a pick, the video's lock): `opened(video, header, side, notes, *,
    translate_model=None) -> Episode`, `apply(ep, op)`, `undo(ep)`, `redo(ep)`, `save(ep, *,
    formats) -> (Episode, SaveResult)`, `resolve(ep, track, rendition) -> (Episode,
    SaveResult)`, `changed_video(old: Header, new: Header) -> list[str]`, `editable`,
    `load_tracks`, `cue_ids`, `transcript_of`, `words_of`, `read_glossary`; `NO_SUBTITLES`,
    `UNDO_STEPS`, `FORMATS`, `GONE`. `web.backend` still exports what its callers import
    (`LocalBackend`, `Episode`, `OpenError`, `SaveError`, `SaveResult`, `Capabilities`,
    `Streams`, `UNDO_STEPS`, `retranslation`, `make_ask`, `detecting`).
  - `vid2sub.subs.sidecar.video_change(old, new) -> str | None` and
    `vid2sub.subs.naming.MEDIA_SUFFIXES`; `pipeline.video_change` and `pipeline.MEDIA_SUFFIXES`
    are still there.
  - `vid2sub.web.browser` (Pages-safe): `BrowserBackend()`, with `capabilities()` (engine
    `browser`, no generate, save `download`: the page writes or downloads what Save hands back,
    no path box); `listing(names) -> list[Found]` (`Found(name, reads, problem)`: each video
    beside a sidecar with the files to read, the sidecar first, never the video; or why it can't
    open); `open(video, *, size, quick_sha256, url, files, names=None) -> BrowserEpisode` (the
    page's quick hash, a blob URL the page made, the files' bytes by name, the folder's names);
    `apply`, `undo`, `redo`, `is_open`, `close`; `save(ep, *, formats, files=None, names=None)`
    and `resolve(ep, track, rendition, *, files=None, names=None)`, each `-> (Episode,
    SaveResult, dict[str, bytes])`, the bytes to write, the sidecar first, keeping nothing;
    `video_url(episode_id)`; `revoke_owner(owner)` (the runtime's media part: nothing to
    revoke). `BrowserEpisode(Episode)` adds `files`. Refusals are `OpenError` or `SaveError`
    with fixed messages (`BAD_NAMES`, `BAD_VIDEO`, `BAD_URL`, `TOO_MANY`, `TOO_BIG`, `CHANGED`,
    `ANOTHER`, `NO_SUBTITLES`, `NO_VIDEO`, `TWINS`, and "… differ only in case …").
  - `browser_runtime(backend=None) -> BrowserRuntime`, Pages' `Runtime`, each part in the
    browser: `backend` a BrowserBackend; `queue`, `config`, `keys` and `job_context` None (no
    jobs, endpoints, models or keys); `media` the backend (no media tokens); `session` a
    `Session()`, whose defaults give Save's SRT; `reachable()` `{}`; `media_for(ep)` the page's
    blob URL, and with `audio_only` no playback audio but `CANT_PLAY` (no ffmpeg);
    `retranslate` raises `RetranslateError(LOCAL_ONLY, INSTALL)` and `endpoint_models`
    `EndpointError(LOCAL_ONLY, INSTALL)`, neither offered since `generate` is false.
  - The server: `status` is an explicit null, and the endpoint check never starts, where
    `capabilities.generate` is false.

The `make check` counts below come from a clone of the finished Phase 2 with only this phase's
Tasks 1 to 4; yours are higher once Phase 3 is in. What matters is no failure, ruff's
`All checks passed!` and gitleaks' `no leaks found`; the new tests' own counts are exact. Each
`diff` block applies with `git apply` from the repository's root (save it to a file first).

- [ ] **Step 0: Record the base:** `git rev-parse HEAD > .git/TASK_BASE`.

#### Round 1a: the Pyodide check, first

- [ ] **Step 1: Add Pyodide to the frontend's dev dependencies.** With Node 22 (`nvm use 22`):

```bash
cd frontend && npx --yes npm@11.11.1 install --save-dev --save-exact pyodide@0.27.7 && cd ..
git diff --stat frontend/
```

  npm 11 because it wrote the lockfile: Node 22's npm 10 also drops the lock's `libc` fields.
  Expected: `frontend/package-lock.json | 36 ++++` and `frontend/package.json | 1 +`, 37
  insertions and nothing else: `"pyodide": "0.27.7",` between `"jsdom"` and `"react"` in
  `devDependencies`, the same line in the lockfile's root package, and the lockfile entries
  `node_modules/pyodide` (0.27.7, `sha512-RUSVJlhQdfWfgO9hVHCiXoG+nVZQRS5D9FzgpLJ/VcgGBLSAKoPL8kT
  iOikxbHQm1kRISeWUBdulEgO26qpSRA==`, dependency `ws ^8.5.0`) and `node_modules/ws` (8.22.0), as
  Phase 4 Task 6's listing gives them in full. If `ws` resolves newer by then, keep what npm
  wrote. `npm audit`'s count is unchanged by these two.
- [ ] **Step 2: The check,** `frontend/src/pyodide.test.ts`:

```ts
// @vitest-environment node
// The Pages editor's Python runs in Pyodide 0.27.7 (spec §21's Shinylive 0.8.12 pin), which has no
// threads: "Attempts to use threading, multiprocessing, or subprocess will raise a RuntimeError"
// (Pyodide's FAQ). Two things the browser backend relies on can't be shown on the host, so they
// are checked here, in that Pyodide (the npm package, no network: only its core is loaded, and
// these modules need nothing but the standard library): runtime.blocking runs a call inline there
// (Phase 2's Pages-safe server, Task 14 round 14a), and security.safe_write works in Pyodide's
// in-memory file system, where web.browser stages an episode's files (Phase 4 Task 1).
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { loadPyodide, version } from "pyodide";
import { expect, test } from "vitest";

const HERE = dirname(fileURLToPath(import.meta.url));
const SRC = resolve(HERE, "../../src");
// Vitest transforms the package, so Pyodide can't find its own files from import.meta.url.
const INDEX = resolve(HERE, "../node_modules/pyodide") + "/";

const CHECK = `
import asyncio, os, sys, tempfile, threading
from pathlib import Path

sys.dont_write_bytecode = True  # nothing is written into the mounted checkout
sys.path.insert(0, "/vid2sub/src")
from vid2sub import security
from vid2sub.web import runtime

found = {"platform": sys.platform, "inline": runtime.INLINE}
try:
    threading.Thread(target=lambda: None).start()
    found["thread"] = "started"
except RuntimeError as err:
    found["thread"] = f"RuntimeError: {err}"
here = threading.get_ident()
ran_on, total = await runtime.blocking(lambda a, *, b: (threading.get_ident(), a + b), 1, b=2)
found["blocking"] = [total, ran_on == here]
runtime.INLINE = False  # asyncio.to_thread, as on the host
try:
    found["to_thread"] = await runtime.blocking(threading.get_ident) == here
finally:
    runtime.INLINE = True
stage = Path(tempfile.mkdtemp(prefix="vid2sub-stage-"))
security.safe_write(stage / "a.srt", b"one", overwrite=False)
security.safe_write(stage / "a.srt", b"two", overwrite=True)
os.symlink(stage / "a.srt", stage / "b.srt")
try:
    security.safe_write(stage / "b.srt", b"three", overwrite=True)
    found["link"] = "written"
except security.WriteRefused as err:
    found["link"] = str(err)
found["files"] = sorted(os.listdir(stage))
found["bytes"] = (stage / "a.srt").read_bytes().decode()
found
`;

test("the Pages editor's Pyodide runs blocking calls inline and stages files in memory", async () => {
  expect(version).toBe("0.27.7");
  const pyodide = await loadPyodide({ indexURL: INDEX });
  pyodide.mountNodeFS("/vid2sub/src", SRC);
  const found = (await pyodide.runPythonAsync(CHECK)).toJs({ dict_converter: Object.fromEntries });
  expect(found.platform).toBe("emscripten");
  expect(found.inline).toBe(true);
  expect(found.thread).toMatch(/^RuntimeError: /); // so blocking can't hand the call to a thread
  expect(found.blocking).toEqual([3, true]); // inline, on the event loop's own thread
  // Without INLINE it still runs on that thread: Pyodide's WebLoop runs an executor's call
  // synchronously ("Best we can do is to run func(args) in this thread", pyodide/webloop.py's
  // run_in_executor), so INLINE only skips the executor.
  expect(found.to_thread).toBe(true);
  expect(found.link).toBe("b.srt exists and isn't a regular file");
  expect(found.files).toEqual(["a.srt", "b.srt"]); // no temporary file left behind
  expect(found.bytes).toBe("two");
}, 60_000);
```

- [ ] **Step 3: Run it; it passes.** `cd frontend && npx vitest run src/pyodide.test.ts`.
  Expected: `✓ the Pages editor's Pyodide runs blocking calls inline and stages files in memory`,
  about 1.2 s, then `Test Files  1 passed (1)` and `Tests  1 passed (1)`.
- [ ] **Step 4: Make INLINE wrong; watch it fail.** In `src/vid2sub/web/runtime.py`, change
  `INLINE = sys.platform == "emscripten"` to `INLINE = sys.platform == "pyodide"`, run Step 3's
  command, then `git checkout src/vid2sub/web/runtime.py`. Expected: `AssertionError: expected
  false to be true // Object.is equality` and `Tests  1 failed (1)`.
- [ ] **Step 5: Run the checks; they pass.** `make check`. Expected: `1037 passed, 2 skipped, 36
  deselected` (twice), `Test Files  20 passed (20)`, `Tests  89 passed (89)`, `All checks
  passed!`, `no leaks found`.
- [ ] **Step 6: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
test(pages): 🤖 the Pages editor's Pyodide runs blocking calls inline and stages files in memory

Phase 4 Task 1 checks first what Phase 2 couldn't: runtime.blocking inside the real Pyodide
0.27.7 (spec §21's Shinylive 0.8.12 pin), and safe_write in Pyodide's in-memory file system,
where the browser backend will stage an episode's files.

- frontend/src/pyodide.test.ts runs in Vitest's node environment, so make test-js (and with it
  make check and CI's frontend job) runs it: it loads Pyodide's core from the pyodide npm
  package, with no network (vid2sub.web.runtime and vid2sub.security need only the standard
  library), mounts src/ and runs the check. sys.platform is "emscripten", runtime.INLINE is
  true, starting a thread raises RuntimeError, and blocking returns its result on the loop's own
  thread. With INLINE off it still runs there: Pyodide's WebLoop runs an executor's call
  synchronously (run_in_executor in pyodide/webloop.py, read in 0.27.7's python_stdlib.zip: "Best
  we can do is to run func(args) in this thread"), so INLINE only skips the executor. safe_write
  creates and replaces a file in /tmp, refuses a symlinked target, and leaves no temporary file.
- With runtime.py's INLINE made `sys.platform == "pyodide"`, the test fails: "AssertionError:
  expected false to be true".
- pyodide 0.27.7 (exact) is a frontend dev dependency, written with npm 11.11.1: the lockfile
  gains pyodide and its one dependency, ws 8.22.0, the same entries Phase 4 Task 6's listing
  names; Vitest needs indexURL given, since it transforms the package. npm audit's count is
  unchanged.

Docs read: Pyodide 0.27.7's FAQ ("sys.platform == 'emscripten'"; "Attempts to use threading,
multiprocessing, or subprocess will raise a RuntimeError"), "Pyodide Python compatibility"
(threading and multiprocessing import but don't work), the JS API (loadPyodide's indexURL,
mountNodeFS, runPythonAsync, toJs's dict_converter) and pyodide/webloop.py; Vitest 3.2's
per-file `@vitest-environment` comment.

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-4.md Task 1
Co-Authored-By: <the model's own line>
```

  `git add frontend/package.json frontend/package-lock.json frontend/src/pyodide.test.ts`,
  `git commit -F .git/COMMIT_MSG`, then `git log -1 --format='%(trailers)'` shows `Plan:`.

#### Round 1b: what both backends share, in a module the Pages bundle can hold

- [ ] **Step 7: Write the failing test.** In `tests/test_pages_imports.py`, replace the bundle's
  lists and add a test below `test_the_server_and_its_views_import_with_only_what_the_pages_bundle_has`:

```diff
diff --git a/tests/test_pages_imports.py b/tests/test_pages_imports.py
index 21de934..7767844 100644
--- a/tests/test_pages_imports.py
+++ b/tests/test_pages_imports.py
@@ -25,11 +25,15 @@ SRC = Path(__file__).resolve().parents[1] / "src" / "vid2sub"
 
 # What spec §21's bundle holds of vid2sub: whole packages, then single modules. `web.ops` parses
 # the editor's edits at the door, so the browser editor needs it too; it is pure. `web.settings`
-# holds the session's defaults, which the runtime makes (Task 18).
+# holds the session's defaults, which the runtime makes (Task 18). `web.folder` opens, edits and
+# saves an episode for both backends, through `store`, which needs `security` and the video's
+# identity type (`media.identity`): each imports only the standard library and the pure
+# packages (Phase 4 Task 1).
 BUNDLED_TREES = ("vid2sub.subs", "vid2sub.parse")
 BUNDLED_MODULES = ("vid2sub", "vid2sub.catalog", "vid2sub.web", "vid2sub.web.server",
                    "vid2sub.web.views", "vid2sub.web.episode", "vid2sub.web.runtime",
-                   "vid2sub.web.ops", "vid2sub.web.settings")
+                   "vid2sub.web.ops", "vid2sub.web.settings", "vid2sub.web.folder",
+                   "vid2sub.store", "vid2sub.security", "vid2sub.media", "vid2sub.media.identity")
 # vid2sub's own dependencies (pyproject.toml, the mac extra, and Phase 3's faster-whisper) that
 # the bundle doesn't have.
 NOT_BUNDLED = ("platformdirs", "numpy", "onnxruntime", "chatlas", "openai", "httpx", "yt_dlp",
@@ -78,6 +82,14 @@ def test_the_server_and_its_views_import_with_only_what_the_pages_bundle_has():
     assert done.stdout.strip() == "imported vid2sub.web.views vid2sub.web.server"
 
 
+def test_what_both_backends_share_imports_with_only_what_the_pages_bundle_has():
+    # why: the Pages editor opens, edits and saves through the same code as the local engine
+    # (spec §14.6, §21), so that code can't import ffmpeg's tools, the engines or the network.
+    done = _import_as_pages("vid2sub.web.folder")
+    assert done.returncode == 0, done.stderr[-3000:]
+    assert done.stdout.strip() == "imported vid2sub.web.folder"
+
+
 def test_the_refusal_itself_works():
     # why: a finder that refused nothing would pass the test above whatever the server imports.
     done = _import_as_pages("vid2sub.web.backend")
```

- [ ] **Step 8: Run it; watch it fail.** `uv run pytest tests/test_pages_imports.py -q`.
  Expected: `1 failed, 5 passed`, with `ModuleNotFoundError: No module named
  'vid2sub.web.folder'`.
- [ ] **Step 9: `video_change` moves beside `VideoInfo`.** In `src/vid2sub/subs/sidecar.py`, and
  in `src/vid2sub/pipeline.py`, which now imports it (its `_size`, `_clock` and `_difference` go
  with it; nothing else used them):

```diff
diff --git a/src/vid2sub/subs/sidecar.py b/src/vid2sub/subs/sidecar.py
index 726f9ba..b98a0b7 100644
--- a/src/vid2sub/subs/sidecar.py
+++ b/src/vid2sub/subs/sidecar.py
@@ -13,7 +13,7 @@ from __future__ import annotations
 
 import hashlib
 import json
-from collections.abc import Sequence
+from collections.abc import Callable, Sequence
 from dataclasses import dataclass, field
 from typing import Annotated, Any, Literal
 
@@ -81,6 +81,40 @@ class SidecarError(ValueError):
     pass
 
 
+def _size(n: int) -> str:
+    for unit, scale in (("GB", 10**9), ("MB", 10**6), ("kB", 10**3)):
+        if n >= scale:
+            return f"{n / scale:.1f} {unit}"
+    return f"{n:,} bytes"
+
+
+def _clock(ms: int) -> str:
+    s = ms // 1000
+    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"
+
+
+def _difference(label: str, old: int, new: int, show: Callable[[int], str],
+                exact: Callable[[int], str]) -> str:
+    a, b = show(old), show(new)
+    if a == b:  # too small a change to see when rounded
+        a, b = exact(old), exact(new)
+    return f"{label} {a} → {b}"
+
+
+def video_change(old: VideoInfo, new: VideoInfo) -> str | None:
+    """What differs between the video a sidecar was made for and the one here, or None (spec
+    §8.3). Here, not in the pipeline, so the Pages editor says it too (Phase 4 Task 1)."""
+    changes = []
+    if old.size != new.size:
+        changes.append(_difference("size", old.size, new.size, _size, lambda n: f"{n:,} bytes"))
+    if old.duration_ms != new.duration_ms:
+        changes.append(_difference("duration", old.duration_ms, new.duration_ms, _clock,
+                                   lambda ms: f"{ms:,} ms"))
+    if not changes and old.quick_sha256 != new.quick_sha256:
+        changes.append("same size and duration, different content")
+    return ", ".join(changes) or None
+
+
 @dataclass(frozen=True)
 class Conflict:
     track: str
```
```diff
diff --git a/src/vid2sub/pipeline.py b/src/vid2sub/pipeline.py
index 186341d..3d81163 100644
--- a/src/vid2sub/pipeline.py
+++ b/src/vid2sub/pipeline.py
@@ -66,8 +66,8 @@ from vid2sub.subs.sidecar import (
     IdentityRecord,
     Sidecar,
     SidecarError,
-    VideoInfo,
     make_rendition,
+    video_change,
 )
 from vid2sub.subs.translate_shape import stale_ids
 from vid2sub.translate.run import (
@@ -234,39 +234,6 @@ def _check_external(video: Path, header, sidecar: Sidecar, result: InputResult)
     return sidecar
 
 
-def _size(n: int) -> str:
-    for unit, scale in (("GB", 10**9), ("MB", 10**6), ("kB", 10**3)):
-        if n >= scale:
-            return f"{n / scale:.1f} {unit}"
-    return f"{n:,} bytes"
-
-
-def _clock(ms: int) -> str:
-    s = ms // 1000
-    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"
-
-
-def _difference(label: str, old: int, new: int, show: Callable[[int], str],
-                exact: Callable[[int], str]) -> str:
-    a, b = show(old), show(new)
-    if a == b:  # too small a change to see when rounded
-        a, b = exact(old), exact(new)
-    return f"{label} {a} → {b}"
-
-
-def video_change(old: VideoInfo, new: VideoInfo) -> str | None:
-    """What differs between the video a sidecar was made for and the one here, or None."""
-    changes = []
-    if old.size != new.size:
-        changes.append(_difference("size", old.size, new.size, _size, lambda n: f"{n:,} bytes"))
-    if old.duration_ms != new.duration_ms:
-        changes.append(_difference("duration", old.duration_ms, new.duration_ms, _clock,
-                                   lambda ms: f"{ms:,} ms"))
-    if not changes and old.quick_sha256 != new.quick_sha256:
-        changes.append("same size and duration, different content")
-    return ", ".join(changes) or None
-
-
 def _notice_replaced(sidecar: Sidecar, header, result: InputResult) -> None:
     """A replaced video is warned about with the difference; nothing is discarded (spec §8.3).
 
```

- [ ] **Step 10: What both backends share,** `src/vid2sub/web/folder.py` (moved from `backend.py`
  unchanged, bar the names its callers now import: `editable`, `transcript_of`, `words_of`,
  `opened`, `changed_video`):

```python
"""An episode's files beside its video, read, edited and saved through `vid2sub.store`: what the
local engine's backend and the Pages editor's share (spec §3.3, §14.5, §14.6, §15.3, §20).

Why: the rules for opening, editing, saving and picking a version exist once (spec §18.3, §20),
and the Pages editor runs them too, on a copy of the files the page hands it (§14.6, §21), so this
module imports nothing the Pages bundle lacks: `vid2sub.store` and `vid2sub.security` (the
standard library), the pure packages and `web.episode` (Phase 4 Task 1). `LocalBackend` probes and
hashes the video, picks the translation model and retranslates; `BrowserBackend` is handed the
files' bytes; both then call these, holding their own record of open episodes and, for Save and a
pick, the video's lock.

Opening folds in edits made outside vid2sub, as every M1 command does (§15.3, S31), and says so in
notes that name files only by their bare name (§6.8). A track whose heads diverged is in conflict
(§14.4): it isn't loaded, and its versions are listed for the person to pick; when that is the
source, every edit waits for the pick, since translations hang off source cues. The spoken words
come from the transcript the source was built from, following rendition parents, so word
highlighting matches the cues' `w` ranges. An `Episode` is never changed in place: every call
returns a new one, so a reactive value that holds it sees each change. Edits run through the pure
`subs.edit` rules (§20); each one that changes something pushes the tracks and the pending
glossary adds onto the undo stack (the last 200 steps) and clears redo. A track in conflict can't
be edited, and nothing but a glossary add can while the source is, until a person picks a version.

Save (spec §14.5, §14.6) first records any outside edit to a subtitle file as M1 does, so an edit
made in another program since the open is a version too, never something a later open puts over
the editor's. Then it appends one `editor` version per changed track, whose parent is the head the
editor's cues came from, and a head that replaces that same head: never the head on disk now, so a
CLI run, another tab or that outside edit leaves two heads, a conflict both versions survive,
rather than one silently replacing the other (the Phase 2 plan's Review Focus 2 and 4). A track
whose head on disk already holds exactly these cues (the same Save sent twice) gets nothing. The
records go in one `store.append`, compare-and-swap with a union merge, so no other writer's records
are lost. Only then are the files written, through `store.project` with `overwrite_foreign` off:
someone else's file is left alone and reported (§6.6, §15.3), and a track in conflict isn't written
until a person picks a version with `resolve`, the only thing that moves a head on a conflicted
track. Once the versions are in the sidecar nothing raises: a file that can't be written is a note,
and the episode moves to the new heads either way. Glossary terms are written at Save (the Phase 2
plan's Decision 5), appended to the file beside the video so its comments survive, and the file is
read back: a term just added makes every translation made without it stale (§13.4), as M1 decides
it too, and that is intended. A Save, like a pick, starts the undo history again, because the
tracks are read back from the sidecar. While a translation is in conflict, no source cue can be
split, merged or deleted: the unloaded version's cues would keep pointing at ids that are gone.
"""

from __future__ import annotations

import codecs
import secrets
from collections.abc import Callable, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Literal

from vid2sub import __version__, store
from vid2sub.security import WriteRefused, safe_write
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
    video_change,
)
from vid2sub.web import ops
from vid2sub.web.episode import Episode, OpenError, SaveError, SaveResult, track_setup

NO_SUBTITLES = "no subtitles yet: make them with vid2sub run or the Jobs page first"
UNDO_STEPS = 200
FORMATS = ("srt", "ass")
GONE = "the sidecar next to the video is gone, so nothing was saved: open the episode again"


def changed_video(old: Header, new: Header) -> list[str]:
    """The note that the video isn't the one its subtitles were made for (spec §8.3), if so."""
    change = video_change(old.video, new.video)
    note = (f"this video changed since its subtitles were made ({change}); its transcript may "
            "no longer line up")
    return [note] if change else []


def opened(video: Path, header: Header, side: Sidecar, notes: list[str], *,
           translate_model: str | None = None) -> Episode:
    """The episode `side` holds, once the outside edits to its subtitle files are recorded
    (§15.3): `notes` first, then what the open found. Its audio is taken to play, from track 0,
    with no stream names, which LocalBackend.open replaces from its probe."""

    def unreadable(name: str) -> None:
        notes.append(f"left {name} alone: it isn't a readable subtitle file")

    try:
        side, changed = store.check_external(video, header, side, on_unreadable=unreadable)
    except (SidecarError, store.StoreError, WriteRefused) as err:
        raise OpenError(str(err)) from None
    except OSError as err:  # never err.filename: a full path
        raise OpenError(_failed("couldn't read or write the files next to the video",
                                err)) from None
    notes += [f"kept your outside edit to {t}" for t in changed]
    source_key, tracks, heads, conflicts = load_tracks(side)
    words = words_of(transcript_of(side, heads.get(source_key)))
    try:
        glossary: Glossary | None = read_glossary(video)
    except GlossaryError as err:
        glossary = None
        notes.append(f"couldn't read {naming.GLOSSARY_NAME}: {err}")
    return Episode(
        id="e" + secrets.token_hex(8), video=video, header=header, source_key=source_key,
        tracks=tracks, heads=heads, conflicts=conflicts, words=words, notes=notes,
        playable_audio=True, audio_index=0, sidecar=side, base=tracks, taken=cue_ids(side),
        glossary=glossary, translate_model=translate_model)


def apply(ep: Episode, op: ops.EditOp) -> Episode:
    """One edit; EditError (fit to show) if the rules refuse it. An edit that changes nothing
    returns `ep` itself, with no undo step."""
    taken = set(ep.taken)
    tracks, adds = _edit(ep, op, taken)
    if tracks == ep.tracks and adds == ep.glossary_adds:
        return ep
    return replace(ep, tracks=tracks, glossary_adds=adds, taken=taken, redo=[],
                   undo=[*ep.undo, (ep.tracks, ep.glossary_adds)][-UNDO_STEPS:])


def undo(ep: Episode) -> Episode:
    if not ep.undo:
        return ep
    tracks, adds = ep.undo[-1]
    return replace(ep, tracks=tracks, glossary_adds=adds, undo=ep.undo[:-1],
                   redo=[*ep.redo, (ep.tracks, ep.glossary_adds)])


def redo(ep: Episode) -> Episode:
    if not ep.redo:
        return ep
    tracks, adds = ep.redo[-1]
    return replace(ep, tracks=tracks, glossary_adds=adds, redo=ep.redo[:-1],
                   undo=[*ep.undo, (ep.tracks, ep.glossary_adds)][-UNDO_STEPS:])


def save(ep: Episode, *, formats: Sequence[Literal["srt", "ass"]]
         ) -> tuple[Episode, SaveResult]:
    """SRT is always written, ASS when asked for (spec §15.2). SaveError means nothing was saved;
    once the versions are in the sidecar, every later problem is a note. The caller holds the
    video's lock."""
    fmts = _formats(formats)
    notes: list[str] = []
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
    side, written, foreign, conflicts, more = _project(ep.video, ep.header, side, side.tracks(),
                                                       fmts)
    notes += more
    adds, glossary_notes = _write_glossary(ep.video, ep.glossary_adds)
    try:  # read back, so a term just added makes translations stale (§13.4), as at open
        glossary: Glossary | None = read_glossary(ep.video)
    except (GlossaryError, OSError):
        glossary = None
    source_key, tracks, heads, in_conflict = load_tracks(side)
    saved = replace(ep, sidecar=side, source_key=source_key, tracks=tracks, base=tracks,
                    heads=heads, conflicts=in_conflict, undo=[], redo=[],
                    taken=ep.taken | cue_ids(side), glossary_adds=adds, glossary=glossary,
                    made_with={})
    return saved, SaveResult(tuple(written), tuple(foreign), tuple(conflicts),
                             tuple(notes + glossary_notes))


def resolve(ep: Episode, track: str, rendition: str) -> tuple[Episode, SaveResult]:
    """A person's pick of one of a conflicted track's versions (spec §14.4): it replaces every
    other version, by "user", and the track is loaded and written. Unsaved edits on other tracks
    are kept. The caller holds the video's lock."""
    if track not in naming.TRACKS:  # it comes from the browser: never echoed unchecked
        raise SaveError("there's no such track")
    if track not in ep.conflicts:  # a stale request must never reload a track being edited
        raise SaveError(f"the {track} track has only one version: there's nothing to pick")
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
        else:
            notes.append(f"the {track} track's version was already picked elsewhere: showing it")
    except (SidecarError, store.StoreError, WriteRefused) as err:
        raise SaveError(str(err)) from None
    except OSError as err:
        raise SaveError(_failed("couldn't save next to the video", err)) from None
    has_ass = any(p.track == track and p.format == "ass" for p in side.projections().values())
    side, written, foreign, conflicts, more = _project(
        ep.video, ep.header, side, [track], ["srt", "ass"] if has_ass else ["srt"])
    return _with_track(ep, side, track), SaveResult(tuple(written), tuple(foreign),
                                                    tuple(conflicts), tuple(notes + more))


def editable(ep: Episode, *tracks: str) -> None:
    """A track in conflict waits for a person to pick a version (spec §14.4); while the source
    is, so does every track, since translations hang off source cues."""
    for name in (ep.source_key, *tracks):
        if name in ep.conflicts:
            raise EditError(f"the {name} track has two versions: pick one before editing")


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


def transcript_of(side: Sidecar, source_head: str | None) -> RenditionRecord | None:
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


def words_of(transcript: RenditionRecord | None) -> tuple[Word, ...]:
    return tuple(transcript_from_body(transcript.body).words()) if transcript else ()


def read_glossary(video: Path) -> Glossary:
    """The glossary beside the video, read as M1 reads it; EMPTY_GLOSSARY when there's none."""
    path = video.with_name(naming.GLOSSARY_NAME)
    if not path.is_file():
        return EMPTY_GLOSSARY
    try:
        return parse_glossary(path.read_text(encoding="utf-8-sig"))
    except UnicodeDecodeError:
        raise GlossaryError("the glossary isn't UTF-8; save it as UTF-8") from None


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
                            inputs={} if is_source or not source_rid else {"source": source_rid},
                            setup=track_setup(ep, track))
        rec = make_rendition([parent], track, body)
        if is_source:
            source_rid = rec.id
        records += [rec, HeadRecord(track=track, rendition=rec.id, replaces=parent, by="editor",
                                    at=now)]
    return records


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
            except Exception as err:  # noqa: BLE001 - the versions are saved; this is one file
                notes.append(f"couldn't write {name} ({type(err).__name__})")
                continue
            if did:
                written.append(name)
    return side, written, foreign, conflicts, notes


def _with_track(ep: Episode, side: Sidecar, track: str) -> Episode:
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
            words = words_of(transcript_of(side, head.rendition))
    elif isinstance(head, Conflict):
        conflicts[track] = head.leaves
        heads.pop(track, None)
    return replace(ep, sidecar=side, heads=heads, conflicts=conflicts, tracks=tracks, base=base,
                   words=words, undo=[], redo=[], taken=ep.taken | cue_ids(side),
                   made_with={k: v for k, v in ep.made_with.items() if k != track})


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
            existed = path.is_file()
            data = path.read_bytes() if existed else b""
            text = data.decode("utf-8-sig")
            out, kept = add_terms(text, adds)
            if out == text:
                break
            latest = path.read_bytes() if path.is_file() else b""
            if latest != data:
                continue
            bom = codecs.BOM_UTF8 if data.startswith(codecs.BOM_UTF8) else b""
            safe_write(path, bom + out.encode("utf-8"), overwrite=existed)
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


def _edit(ep: Episode, op: ops.EditOp, taken: set[str]) -> tuple[Tracks, dict[str, str]]:
    """The tracks and glossary adds after `op`; new cue ids are added to `taken`."""
    if isinstance(op, ops.GlossaryAdd):
        return ep.tracks, {**ep.glossary_adds, op.term.strip(): op.translation.strip()}
    t = ep.tracks
    match op:
        case ops.SetText():
            editable(ep, ep.source_key)
            return edit.set_text(t, op.cue, op.text), ep.glossary_adds
        case ops.SetTranslationText():
            editable(ep, op.track)
            return edit.set_translation_text(t, op.track, op.cue, op.text), ep.glossary_adds
        case ops.SetTimes():
            editable(ep, ep.source_key)
            return (edit.set_times(t, op.cue, start_ms=op.start_ms, end_ms=op.end_ms),
                    ep.glossary_adds)
        case ops.Nudge():
            editable(ep, ep.source_key)
            return edit.nudge(t, op.cue, op.delta_ms, edge=op.edge), ep.glossary_adds
        case ops.Split():
            editable(ep, ep.source_key, *ep.conflicts)
            return (edit.split(t, op.cue, at_char=op.at_char, at_ms=op.at_ms, taken=taken)[0],
                    ep.glossary_adds)
        case ops.MergeNext():
            editable(ep, ep.source_key, *ep.conflicts)
            return edit.merge_next(t, op.cue, taken=taken)[0], ep.glossary_adds
        case ops.Insert():
            editable(ep, ep.source_key)
            return (edit.insert(t, start_ms=op.start_ms, end_ms=op.end_ms, text=op.text,
                                taken=taken)[0], ep.glossary_adds)
        case ops.Delete():
            editable(ep, ep.source_key, *ep.conflicts)
            return edit.delete(t, op.cue), ep.glossary_adds
        case ops.Detach():
            editable(ep, op.track)
            return edit.detach(t, op.track, op.cue, op.detached), ep.glossary_adds
        case ops.ReplaceAll():
            editable(ep, *(ep.source_key if name == SOURCE else name for name in op.tracks))
            return edit.replace_all(t, op.find, op.replace, tracks=op.tracks)[0], ep.glossary_adds
    raise EditError("that isn't an edit the editor knows")


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
```

- [ ] **Step 11: LocalBackend calls it.** Replace `src/vid2sub/web/backend.py` with:

```python
"""The local engine's backend: opening, editing, retranslating and saving an episode beside a
video on this machine (spec §19.1, §20).

The web app's server calls this, never the store directly, so the CLI and the editor share one
core (spec §18.3); `capabilities()` tells the frontend which controls exist (`BrowserBackend`, in
Pages, is `web.browser`'s). What both backends share, opening a sidecar, the edit rules, Save and
the pick of a conflicted version, is `web.folder`'s, which runs in Pages too (Phase 4 Task 1); this
module adds what needs this machine: a typed path, ffprobe, the video's quick hash, the model
Retranslate would use and Retranslate itself. Phase 2's editor opens only episodes that already
have a sidecar: making subtitles is `vid2sub run` or the Jobs page. Audio in AC-3, E-AC-3, DTS or
TrueHD can't be played by a browser (§8.2), so the editor then plays the playback audio instead
(the Phase 2 plan's Decision 2). The `Episode`, `SaveResult`, the errors and the stale test live
in the pure `web.episode`, so the Shiny server imports nothing local (Task 14 round 14a); they are
re-exported here. A translation is stale, as spec §13.4 says and M1 decides
(pipeline._translate_targets), when its source text changed, and every cue of it is when the
glossary's hash or the translation model differs from the ones its head was made with; so the
episode holds the glossary beside the video and the model Retranslate would use with none named,
picked offline from the catalog route as M1 picks it but taking every configured local server to
answer (no request is made at open). Saves and picks on one video take turns within this engine,
so two picks at once can't replace each other in a cycle.

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

from __future__ import annotations

import os
import tempfile
import threading
from collections.abc import Callable, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Literal

from vid2sub import detect as detecting
from vid2sub import store
from vid2sub.cache import Cache
from vid2sub.catalog import suggest
from vid2sub.config import Config, ModelEntry
from vid2sub.engines.base import EngineError
from vid2sub.engines.clients import KeyRing, RunPolicy, check_allowed
from vid2sub.media.identity import identify
from vid2sub.media.probe import Probe, ProbeError, pick_track, probe
from vid2sub.media.tools import ToolFailed, ToolMissing, Tools
from vid2sub.pipeline import MEDIA_SUFFIXES
from vid2sub.security import InputRefused, resolve_input
from vid2sub.subs import naming
from vid2sub.subs.edit import EditError, Tracks
from vid2sub.subs.model import Cue, TrackError, check_track
from vid2sub.subs.sidecar import RenditionRecord, SidecarError
from vid2sub.subs.translate_shape import stale_ids, untranslated
from vid2sub.translate.run import AskFn, make_ask, translate_cues
from vid2sub.web import folder, ops
from vid2sub.web.episode import (  # re-exported: the backend's callers import them from here
    Capabilities,
    Episode,
    OpenError,
    SaveError,
    SaveResult,
    Streams,
    glossary_with,
    setup_changed,
    track_setup,
)
from vid2sub.web.folder import NO_SUBTITLES, UNDO_STEPS

__all__ = ["Capabilities", "Episode", "LocalBackend", "OpenError", "SaveError", "SaveResult",
           "Streams", "retranslation"]

UNPLAYABLE_AUDIO = frozenset({"ac3", "eac3", "dts", "truehd"})  # ffprobe's codec names (§8.2)


class LocalBackend:
    def __init__(self, config: Config, tools: Tools, keys: KeyRing, cache: Cache):
        self.config = config
        self.tools = tools
        self.keys = keys
        self.cache = cache
        self._open: dict[str, Path] = {}
        self._lock = threading.Lock()
        self._writing: dict[Path, threading.Lock] = {}  # one per video: saves and picks take turns

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
        ep = folder.opened(video, header, side,
                           [*warnings, *folder.changed_video(side.header, header)])
        transcript = folder.transcript_of(ep.sidecar, ep.heads.get(ep.source_key))
        track = _audio_track(p, transcript, naming.TRACKS.get(ep.source_key))
        ep = replace(ep, playable_audio=track.codec not in UNPLAYABLE_AUDIO,
                     audio_index=track.index,
                     translate_model=self._route_model(_lang(ep.source_key)),
                     streams=Streams(p.container, p.video_codec, track.codec))
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

    def apply(self, ep: Episode, op: ops.EditOp) -> Episode:
        """One edit; EditError (fit to show) if the rules refuse it. An edit that changes
        nothing returns `ep` itself, with no undo step."""
        self._check_open(ep)
        return folder.apply(ep, op)

    def undo(self, ep: Episode) -> Episode:
        self._check_open(ep)
        return folder.undo(ep)

    def redo(self, ep: Episode) -> Episode:
        self._check_open(ep)
        return folder.redo(ep)

    def save(self, ep: Episode, *, formats: Sequence[Literal["srt", "ass"]]
             ) -> tuple[Episode, SaveResult]:
        """SRT is always written, ASS when asked for (spec §15.2). SaveError means nothing was
        saved; once the versions are in the sidecar, every later problem is a note."""
        self._check_open(ep)
        with self._writing_lock(ep.video):
            return folder.save(ep, formats=formats)

    def resolve(self, ep: Episode, track: str, rendition: str) -> tuple[Episode, SaveResult]:
        """A person's pick of one of a conflicted track's versions (spec §14.4): it replaces
        every other version, by "user", and the track is loaded and written. Unsaved edits on
        other tracks are kept."""
        self._check_open(ep)
        with self._writing_lock(ep.video):
            return folder.resolve(ep, track, rendition)

    def _writing_lock(self, video: Path) -> threading.Lock:
        with self._lock:
            return self._writing.setdefault(video, threading.Lock())

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
        folder.editable(ep, track)
        if track not in ep.tracks.translations:
            raise EditError(f"there is no {track} track")
        if ids is not None and not ids:
            return ep
        source, cues = ep.tracks.source, ep.tracks.translations[track]
        lang = _lang(ep.source_key)
        name, entry = self._translator(lang, model, allow_cloud)
        glossary = glossary_with(folder.read_glossary(ep.video), ep.glossary_adds)
        everything = ids is None and setup_changed(track_setup(ep, track), glossary.sha(),
                                                   entry.model)
        wanted, replaced = retranslation(source, cues, ids, everything=everything)
        if not wanted:
            return ep
        ask = self._ask(name, entry, RunPolicy(allow_cloud))
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

    def _translator(self, lang: str, model: str | None, allow_cloud: bool
                    ) -> tuple[str, ModelEntry]:
        """The named model, else the catalog route's pick, as M1's pipeline picks (§11.2), with
        its entry. A route whose model's server isn't answering stops here rather than taking
        the next model. The demo's backend answers with its canned model instead."""
        if model is not None:
            entry = self.config.models.get(model)
            if entry is None or entry.task != "translate":
                raise EngineError("unavailable", "that isn't a translation model in vid2sub.toml",
                                  hint="`vid2sub models` lists them")
            return model, entry
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
        return s.model, self.config.models[s.model]

    def _ask(self, name: str, entry: ModelEntry, policy: RunPolicy) -> AskFn:
        """The model's ask function, once this call may use it: a cloud model only when the call
        allows it (spec §7.2), checked here, before anything is sent."""
        check_allowed(name, entry, self.config, policy)
        return make_ask(name, entry, self.config, policy, self.keys)

    def _check_open(self, ep: Episode) -> None:
        if not self.is_open(ep.id):
            raise OpenError("this episode was closed: open it again")

    def _route_model(self, lang: str) -> str | None:
        """The model Retranslate would use with none named and no cloud: M1's catalog route over
        the configured models, each local server taken to answer (`probe_endpoints=False`)."""
        cands = detecting.candidates(self.config, self.keys, probe_endpoints=False)
        name = suggest(lang, cands, "translate", allow_cloud=False).model
        return self.config.models[name].model if name else None

    def _probe(self, video: Path) -> Probe:
        try:
            with tempfile.TemporaryDirectory(prefix="vid2sub-") as scratch:
                return probe(video, self.tools, scratch=Path(scratch))
        except (ProbeError, ToolMissing) as err:
            raise OpenError(str(err)) from None
        except ToolFailed:
            raise OpenError("ffprobe couldn't read this file: check that it plays in a media "
                            "player") from None


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


def _audio_track(p: Probe, transcript: RenditionRecord | None, info: naming.TrackInfo | None):
    """The track the transcript was made from (its `inputs.audio_track`), else §8.4's pick."""
    if transcript is not None:
        value = str(transcript.body.get("inputs", {}).get("audio_track", ""))
        if value.isdigit() and int(value) < len(p.audio):
            return p.audio[int(value)]
    return pick_track(p, info.lang if info else None)


def _lang(track: str) -> str:
    info = naming.TRACKS.get(track)
    return info.lang if info else track.split("-")[0]
```

- [ ] **Step 12: Run the checks; they pass.** First `uv run pytest tests/test_pages_imports.py
  -q`: `6 passed`. Then, the guard for a move, every test of the backend and what calls it,
  unchanged: `VID2SUB_REQUIRE_FFMPEG=1 uv run pytest tests/test_backend_open.py
  tests/test_backend_edit.py tests/test_backend_save.py tests/test_backend_retranslate.py
  tests/test_views.py tests/test_web_server.py tests/test_demo_guard.py tests/test_pipeline.py
  tests/test_pages_imports.py tests/test_purity.py tests/test_sidecar.py -q`: `239 passed`.
  Then `make check`: `1038 passed, 2 skipped, 36 deselected` (twice), `Test Files  20 passed
  (20)`, `Tests  89 passed (89)`, `All checks passed!`, `no leaks found`.
- [ ] **Step 13: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
refactor(web): 🤖 opening, editing, saving and picking a version live in web.folder, which the Pages bundle can hold

Spec §20 and §14.6: the edit and save rules exist once, and the Pages editor runs them too, on the
files the page hands it (§21). LocalBackend's own module imports ffprobe's tools, the engines, the
pipeline and the network client, none of which Pyodide has, so what both backends share moved out.

- src/vid2sub/web/folder.py holds, unchanged in behaviour, what LocalBackend did on the files beside
  the video: `opened` (outside edits recorded, tracks, heads, conflicts, words, glossary), `apply`,
  `undo`, `redo`, `save`, `resolve`, `editable`, `load_tracks`, `cue_ids`, `transcript_of`,
  `words_of`, `read_glossary`, and the helpers they use. It imports only store, security, the
  pure packages and web.episode.
- LocalBackend keeps what needs this machine (the typed path, ffprobe, the quick hash, the
  route's model, Retranslate) and the open episodes and per-video locks, and calls folder for the
  rest; backend.py still exports what its callers and tests import from it.
- video_change, the note that a video isn't the one its subtitles were made for (§8.3), moved
  from the pipeline into subs.sidecar beside VideoInfo, so the browser says it too; the pipeline
  imports it, so pipeline.video_change is still there.
- tests/test_pages_imports.py names the bundle's new members (web.folder, store, security, media,
  media.identity, each standard library and pure packages only) and imports web.folder as Pages
  would; it failed first: "ModuleNotFoundError: No module named 'vid2sub.web.folder'". Every
  existing backend, server, views, demo and pipeline test passes unchanged, the guard for a move.

Docs read: none beyond the code; this moves Phase 2's code without changing it.

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-4.md Task 1
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/pipeline.py src/vid2sub/subs/sidecar.py src/vid2sub/web/backend.py
  src/vid2sub/web/folder.py tests/test_pages_imports.py`, `git commit -F .git/COMMIT_MSG`, then
  `git log -1 --format='%(trailers)'` shows `Plan:`.

#### Round 1c: the browser backend and its runtime

- [ ] **Step 14: Write the failing tests,** `tests/test_browser_backend.py`:

```python
"""The Pages editor's backend works on the bytes of an episode's files, handed over by the page,
as the local engine works on the files themselves (spec §3.3, §14.6, §21; S47, S48).

Each test makes an M1-shaped episode in a real folder, then plays the page's part: it lists the
folder, hands over the files the listing names (never the video), and writes back what a Save
returns (Chrome) or keeps it (a download, Safari). The local engine then opens the folder, so a
browser Save is checked against the same reading of the sidecar as every other writer's.
"""

from __future__ import annotations

import pytest
from episodes import ENGLISH, LINES, make_episode, sid, source_cues, translation_cues, write_track

from vid2sub import store
from vid2sub.cache import Cache
from vid2sub.config import Config
from vid2sub.engines.clients import KeyRing
from vid2sub.media.identity import identify
from vid2sub.media.tools import Tools
from vid2sub.subs.formats import to_srt
from vid2sub.subs.glossary import parse_glossary
from vid2sub.subs.model import Cue
from vid2sub.subs.rendition import cues_from_body
from vid2sub.web import runtime, views
from vid2sub.web.backend import LocalBackend
from vid2sub.web.browser import (
    ANOTHER,
    BAD_NAMES,
    BAD_URL,
    CANT_PLAY,
    CHANGED,
    INSTALL,
    NO_SUBTITLES,
    NO_VIDEO,
    TWINS,
    BrowserBackend,
    BrowserEpisode,
    Found,
    browser_runtime,
)
from vid2sub.web.episode import Capabilities, OpenError, RetranslateError, SaveError
from vid2sub.web.folder import GONE
from vid2sub.web.ops import parse_op
from vid2sub.web.settings import EndpointError

pytestmark = pytest.mark.media
NAME = "Show - S01E01.mkv"
JA, EN, SIDECAR = "Show - S01E01.ja.srt", "Show - S01E01.en.srt", "Show - S01E01.vid2sub.jsonl"
GLOSSARY = "vid2sub.glossary.toml"
URL = "blob:https://chendaniely.github.io/4f1c2a9e-1b2c-4d3e-8f90-123456789abc"
BAZARR = b"1\n00:00:00,000 --> 00:00:01,000\nBazarr's line\n"


@pytest.fixture
def video(tmp_path):
    return make_episode(tmp_path / "show")


@pytest.fixture
def local(tmp_path) -> LocalBackend:
    return LocalBackend(Config(), Tools.find(), KeyRing(environ={}),
                        Cache(tmp_path / "cache", max_bytes=10**9))


def names_in(video) -> list[str]:
    return sorted(p.name for p in video.parent.iterdir())


def read_again(video, backend: BrowserBackend) -> tuple[dict[str, bytes], list[str]]:
    """What the page hands over: the files the listing names for this video, read now, and the
    folder's names. Never the video itself."""
    names = names_in(video)
    found = next(f for f in backend.listing(names) if f.name == video.name)
    assert video.name not in found.reads
    return {n: (video.parent / n).read_bytes() for n in found.reads}, names


def open_in_browser(backend: BrowserBackend, video):
    files, names = read_again(video, backend)
    ident = identify(video)
    return backend.open(video.name, size=ident.size, quick_sha256=ident.quick_sha256, url=URL,
                        files=files, names=names)


def write_out(video, writes: dict[str, bytes]) -> None:
    """What the page does with a Save's result where it can write (Chrome, Edge)."""
    for name, data in writes.items():
        (video.parent / name).write_bytes(data)


def edit(backend, ep, **data):
    return backend.apply(ep, parse_op(data))


def test_a_folder_listing_names_each_episode_and_the_files_the_page_reads_for_it(video):
    folder = video.parent
    (folder / GLOSSARY).write_text('[terms]\n"東京" = "Tokyo"\n', encoding="utf-8")
    (folder / "Show - S01E01.fr.srt").write_bytes(BAZARR)  # a language vid2sub never writes
    (folder / "Show - S01E02.mkv").write_bytes(b"")  # no subtitles yet
    (folder / "Show - S01E03.vid2sub.jsonl").write_text("{}\n", encoding="utf-8")  # no video
    (folder / "Twin.mkv").write_bytes(b"")
    (folder / "Twin.mp4").write_bytes(b"")
    (folder / "Twin.vid2sub.jsonl").write_text("{}\n", encoding="utf-8")
    found = BrowserBackend().listing(names_in(video))
    assert found == [
        Found(NAME, (SIDECAR, EN, JA, GLOSSARY)),
        Found("Show - S01E02.mkv", problem=NO_SUBTITLES),
        Found("Show - S01E03.vid2sub.jsonl", problem=NO_VIDEO),
        Found("Twin.mkv", problem=TWINS),
        Found("Twin.mp4", problem=TWINS),
    ]


@pytest.mark.parametrize("bad", ["../etc/passwd", "a/b.srt", "a\\b.srt", "..", "", "x\0.srt",
                                 "bell\x07.srt", "x" * 256])
def test_a_listing_with_a_name_that_isnt_a_files_own_is_refused(bad):
    with pytest.raises(OpenError, match=BAD_NAMES):
        BrowserBackend().listing(["Show - S01E01.mkv", bad])


def test_opening_from_the_handed_over_bytes_gives_the_episode_the_local_engine_opens(video,
                                                                                    local):
    # why: the rules exist once (spec §20); the browser runs web.folder on a staged copy.
    browser = BrowserBackend()
    ep = open_in_browser(browser, video)
    there = local.open(str(video))
    assert isinstance(ep, BrowserEpisode)
    assert (ep.source_key, ep.tracks, ep.heads, ep.conflicts, ep.words, ep.notes) == (
        there.source_key, there.tracks, there.heads, there.conflicts, there.words, there.notes)
    assert ep.header == there.header  # the page's size and quick hash, the sidecar's duration
    assert ep.video.name == NAME and str(ep.video) == NAME  # a bare name, never a path
    assert browser.video_url(ep.id) == URL
    view = views.episode_view(ep, video_url=URL, audio_url=None)
    assert view["video"]["name"] == NAME and str(video.parent) not in str(view)
    assert browser.capabilities() == Capabilities(engine="browser", generate=False,
                                                  save="download", path_input=False)


def test_a_video_the_page_says_has_changed_is_noted_as_the_local_engine_notes_it(video):
    browser = BrowserBackend()
    files, names = read_again(video, browser)
    ident = identify(video)
    ep = browser.open(NAME, size=ident.size + 10, quick_sha256="0" * 64, url=URL, files=files,
                      names=names)
    change = f"size {ident.size:,} bytes → {ident.size + 10:,} bytes"
    note = (f"this video changed since its subtitles were made ({change}); its transcript may "
            "no longer line up")
    assert ep.notes == [note]


def test_a_save_where_the_page_can_write_lands_as_the_local_engine_would_save_it(video, local):
    browser = BrowserBackend()
    ep = edit(browser, open_in_browser(browser, video), op="set_text", cue=sid(0),
              text="おはよう！")
    before = (video.parent / SIDECAR).read_bytes()
    files, names = read_again(video, browser)
    saved, result, writes = browser.save(ep, formats=["srt"], files=files, names=names)
    assert (video.parent / SIDECAR).read_bytes() == before  # nothing written here: the page does
    assert list(writes) == [SIDECAR, JA]  # the sidecar first, then the file it projects
    assert result.written == (JA,) and result.foreign == () and result.conflicts == ()
    assert not saved.dirty and saved.files[JA] == writes[JA]
    write_out(video, writes)
    there = local.open(str(video))
    assert there.tracks.source[0].text == "おはよう！"
    assert there.heads["ja"] == saved.heads["ja"] and there.notes == []


def test_save_merges_with_what_another_writer_added_since_the_page_opened_it(video, local):
    # why: spec §14.6 and S47: the page re-reads the sidecar first, and the merge is a union, so
    # a CLI run that translated meanwhile is kept, and the editor's version is added beside it.
    browser = BrowserBackend()
    ep = edit(browser, open_in_browser(browser, video), op="set_text", cue=sid(1), text="元気？")
    head = store.load(video)[0].head("en").rendition
    theirs = write_track(video, "en", [c.model_copy(update={"text": c.text + "!"})
                                       for c in translation_cues(source_cues(len(LINES)))],
                         role="translation", parents=[head], replaces=head)
    files, names = read_again(video, browser)
    saved, _, writes = browser.save(ep, formats=["srt"], files=files, names=names)
    write_out(video, writes)
    side = store.load(video)[0]
    assert theirs.id in side.renditions() and side.head("en").rendition == theirs.id
    assert side.head("ja").rendition == saved.heads["ja"]
    there = local.open(str(video))
    assert there.tracks.source[1].text == "元気？"
    assert [c.text for c in there.tracks.translations["en"]] == [t + "!" for t in ENGLISH]


def test_an_outside_edit_found_at_open_is_saved_once_the_page_writes(video, local, monkeypatch):
    # why: the open records it in the episode only (the page hasn't written anything yet), so the
    # Save's merge must bring that version along: the editor's version of the same track hangs
    # off it, and recorded again at Save, a second later, it would be another version.
    srt = video.parent / EN
    cues = translation_cues(source_cues(len(LINES)))
    srt.write_bytes(to_srt([cues[0].model_copy(update={"text": "Morning!"}), *cues[1:]]))
    browser = BrowserBackend()
    before = (video.parent / SIDECAR).read_bytes()
    monkeypatch.setattr(store, "now", lambda: "2026-10-24T10:00:00Z")
    ep = open_in_browser(browser, video)
    assert ep.notes == ["kept your outside edit to en"]
    assert (video.parent / SIDECAR).read_bytes() == before
    ep = edit(browser, ep, op="set_translation_text", track="en", cue=ep.tracks.translations[
        "en"][2].id, text="Yes, fine")
    monkeypatch.setattr(store, "now", lambda: "2026-10-24T10:00:05Z")
    files, names = read_again(video, browser)
    _, _, writes = browser.save(ep, formats=["srt"], files=files, names=names)
    write_out(video, writes)
    side = store.load(video)[0]
    renditions = side.renditions()
    external = [r for r in renditions.values() if r.body.get("engine") == "external"]
    assert len(external) == 1
    assert renditions[side.head("en").rendition].parents == (external[0].id,)
    there = local.open(str(video))
    assert there.notes == []
    assert [c.text for c in there.tracks.translations["en"]] == ["Morning!", ENGLISH[1],
                                                                 "Yes, fine"]


def test_a_download_builds_on_the_files_as_the_episode_last_saw_them(video, local):
    # why: S48: Safari reads the folder once and can't write it, so each Save offers the whole
    # sidecar and the subtitle files; a second download must hold the first one's versions and
    # glossary terms too, or putting it beside the video would lose them.
    browser = BrowserBackend()
    ep = edit(browser, open_in_browser(browser, video), op="set_text", cue=sid(0), text="一")
    ep = edit(browser, ep, op="glossary_add", term="東京", translation="Tokyo")
    first, _, writes = browser.save(ep, formats=["srt"])
    assert list(writes) == [SIDECAR, JA, GLOSSARY]
    ep = edit(browser, first, op="set_text", cue=sid(1), text="二")
    ep = edit(browser, ep, op="glossary_add", term="大阪", translation="Osaka")
    second, _, writes = browser.save(ep, formats=["srt"])
    assert list(writes) == [SIDECAR, JA, GLOSSARY]
    assert dict(parse_glossary(writes[GLOSSARY].decode()).terms) == {"東京": "Tokyo",
                                                                     "大阪": "Osaka"}
    write_out(video, writes)
    there = local.open(str(video))
    assert [c.text for c in there.tracks.source[:2]] == ["一", "二"]
    assert there.heads == second.heads


def test_someone_elses_subtitle_file_is_left_alone_and_never_handed_back(tmp_path):
    video = make_episode(tmp_path / "show", project=("ja",))
    (video.parent / EN).write_bytes(BAZARR)
    browser = BrowserBackend()
    ep = edit(browser, open_in_browser(browser, video), op="set_text", cue=sid(0), text="朝")
    files, names = read_again(video, browser)
    assert EN in files
    _, result, writes = browser.save(ep, formats=["srt"], files=files, names=names)
    assert result.foreign == (EN,) and EN not in writes


def test_a_name_vid2sub_writes_in_another_case_is_its_name_on_a_case_blind_disk(tmp_path):
    # why: macOS and Windows see Show.EN.SRT as the Show.en.srt vid2sub would write, so a
    # Bazarr file named so must be left alone, as the local engine leaves it there (§6.6).
    video = make_episode(tmp_path / "show", project=("ja",))
    (video.parent / "Show - S01E01.EN.SRT").write_bytes(BAZARR)
    browser = BrowserBackend()
    ep = edit(browser, open_in_browser(browser, video), op="set_text", cue=sid(0), text="朝")
    files, names = read_again(video, browser)
    _, result, writes = browser.save(ep, formats=["srt"], files=files, names=names)
    assert result.foreign == (EN,) and EN not in writes


def test_two_names_one_case_apart_are_refused():
    files = {"Show - S01E01.en.srt": BAZARR, "Show - S01E01.EN.srt": BAZARR,
             SIDECAR: b"{}\n"}
    with pytest.raises(OpenError, match="differ only in case"):
        BrowserBackend().open(NAME, size=1, quick_sha256="0" * 64, url=URL, files=files)


def test_a_file_of_the_episode_the_page_didnt_hand_over_stops_the_open_and_the_save(video):
    # why: a subtitle file Python never saw would look missing, and Save would write over it.
    browser = BrowserBackend()
    files, names = read_again(video, browser)
    ident = identify(video)
    without = {n: d for n, d in files.items() if n != EN}
    with pytest.raises(OpenError, match=CHANGED):
        browser.open(NAME, size=ident.size, quick_sha256=ident.quick_sha256, url=URL,
                     files=without, names=names)
    ep = browser.open(NAME, size=ident.size, quick_sha256=ident.quick_sha256, url=URL,
                      files=files, names=names)
    with pytest.raises(SaveError, match=CHANGED):
        browser.save(ep, formats=["srt"], files=without, names=names)


def test_a_save_into_a_folder_whose_sidecar_is_gone_or_another_videos_saves_nothing(video,
                                                                                    tmp_path):
    browser = BrowserBackend()
    ep = edit(browser, open_in_browser(browser, video), op="set_text", cue=sid(0), text="朝")
    files, names = read_again(video, browser)
    without = {n: d for n, d in files.items() if n != SIDECAR}
    with pytest.raises(SaveError, match=GONE):
        browser.save(ep, formats=["srt"], files=without,
                     names=[n for n in names if n != SIDECAR])
    other = make_episode(tmp_path / "other", n=2)  # another video under the same name
    theirs, their_names = read_again(other, browser)
    with pytest.raises(SaveError, match=ANOTHER):
        browser.save(ep, formats=["srt"], files=theirs, names=their_names)


@pytest.mark.parametrize("url", ["https://example.com/video.mp4", "../demo/clip.mp4",
                                 "javascript:alert(1)", "blob:https://x/not-a-uuid", None])
def test_a_video_address_the_page_didnt_make_is_refused(video, url):
    # why: the player loads whatever address it's given, so only the blob URL the page made for
    # the picked video may come back from Python (spec §6.9: nothing beyond the site's files).
    browser = BrowserBackend()
    files, names = read_again(video, browser)
    ident = identify(video)
    with pytest.raises(OpenError, match=BAD_URL):
        browser.open(NAME, size=ident.size, quick_sha256=ident.quick_sha256, url=url,
                     files=files, names=names)


def test_a_closed_episode_is_edited_or_saved_no_more(video):
    browser = BrowserBackend()
    ep = open_in_browser(browser, video)
    browser.close(ep.id)
    assert browser.video_url(ep.id) is None
    with pytest.raises(OpenError, match="was closed"):
        edit(browser, ep, op="set_text", cue=sid(0), text="朝")
    with pytest.raises(OpenError, match="was closed"):
        browser.save(ep, formats=["srt"])


def test_a_pick_of_a_conflicted_version_is_written_as_the_local_engine_writes_it(video, local):
    head = store.load(video)[0].head("en").rendition
    cues = translation_cues(source_cues(len(LINES)))
    mine = write_track(video, "en", [c.model_copy(update={"text": "A"}) for c in cues],
                       role="translation", parents=[head], replaces=head, by="editor")
    write_track(video, "en", [c.model_copy(update={"text": "B"}) for c in cues],
                role="translation", parents=[head], replaces=head, by="editor")
    browser = BrowserBackend()
    ep = open_in_browser(browser, video)
    assert "en" in ep.conflicts
    files, names = read_again(video, browser)
    picked, result, writes = browser.resolve(ep, "en", mine.id, files=files, names=names)
    assert result.written == (EN,) and list(writes) == [SIDECAR, EN]
    write_out(video, writes)
    there = local.open(str(video))
    assert there.conflicts == {} and there.heads["en"] == mine.id == picked.heads["en"]
    assert [c.text for c in cues_from_body(store.load(video)[0].renditions()[mine.id].body)] \
        == ["A"] * len(LINES)
    assert all(isinstance(c, Cue) for c in there.tracks.translations["en"])


def test_in_the_browser_the_runtime_plays_the_pages_own_video_and_has_nothing_local(video):
    # why: Pages configures this runtime before it imports the server (spec §21); each local-only
    # part says what it does here, and the server reaches nothing else.
    rt = browser_runtime()
    ep = open_in_browser(rt.backend, video)
    assert rt.media_for(ep) == runtime.Media(URL, None)  # the blob URL the page made
    assert rt.media_for(ep, audio_only=True) == runtime.Media(None, None, CANT_PLAY)  # no ffmpeg
    rt.media.revoke_owner(ep.id)  # no media tokens: the page owns its blob URLs
    assert rt.media_for(ep) == runtime.Media(URL, None)
    assert rt.reachable() == {}  # no endpoints to check
    with pytest.raises(RetranslateError) as refused:
        rt.retranslate(ep, "en", ids=None, allow_cloud=False)
    assert refused.value.hint == INSTALL
    with pytest.raises(EndpointError):
        rt.endpoint_models("spark")
    assert rt.session.defaults().formats == ("srt",)  # Save's default formats
    assert (rt.queue, rt.config, rt.keys, rt.job_context) == (None, None, None, None)
    assert rt.backend.capabilities().generate is False
```

- [ ] **Step 15: Run them; watch them fail.** `VID2SUB_REQUIRE_FFMPEG=1 uv run pytest
  tests/test_browser_backend.py -q`. Expected: `ERROR tests/test_browser_backend.py`, `E
  ModuleNotFoundError: No module named 'vid2sub.web.browser'`.
- [ ] **Step 16: The video suffixes move into the pure naming module,** so the listing finds
  videos by the pipeline's own list:

```diff
diff --git a/src/vid2sub/subs/naming.py b/src/vid2sub/subs/naming.py
index 179b74e..49eb40b 100644
--- a/src/vid2sub/subs/naming.py
+++ b/src/vid2sub/subs/naming.py
@@ -13,6 +13,10 @@ from pathlib import PurePath
 
 GLOSSARY_NAME = "vid2sub.glossary.toml"
 SIDECAR_SUFFIX = ".vid2sub.jsonl"
+# The files vid2sub takes as videos (and audio): here, not in the pipeline, so the Pages editor
+# finds a folder's videos by the same list (Phase 4 Task 1).
+MEDIA_SUFFIXES = frozenset({".mkv", ".mp4", ".m4v", ".mov", ".webm", ".avi", ".ts", ".m2ts",
+                            ".wmv", ".mp3", ".m4a", ".aac", ".flac", ".wav", ".ogg", ".opus"})
 
 
 @dataclass(frozen=True)
```
```diff
diff --git a/src/vid2sub/pipeline.py b/src/vid2sub/pipeline.py
index 3d81163..65df683 100644
--- a/src/vid2sub/pipeline.py
+++ b/src/vid2sub/pipeline.py
@@ -78,8 +78,7 @@ from vid2sub.translate.run import (
     translate_cues,
 )
 
-MEDIA_SUFFIXES = frozenset({".mkv", ".mp4", ".m4v", ".mov", ".webm", ".avi", ".ts", ".m2ts",
-                            ".wmv", ".mp3", ".m4a", ".aac", ".flac", ".wav", ".ogg", ".opus"})
+MEDIA_SUFFIXES = naming.MEDIA_SUFFIXES  # its callers import it from here
 CHUNKER_VERSION = "c1"
 PROMPT_POLICY = "p1"
 PIPELINE = hashlib.sha256(f"{VAD_ID}|{CHUNKER_VERSION}|{PROMPT_POLICY}".encode()).hexdigest()[:8]
```

- [ ] **Step 17: The backend,** `src/vid2sub/web/browser.py`:

```python
"""The Pages editor's backend: opening, editing and saving an episode on the bytes of its files,
which the page reads from the folder the person picked and hands over (spec §3.3, §14.6, §21).

Why: in Pages, Python runs in a Web Worker under Pyodide while the page holds the folder's handles
(§21), so the page lists the folder, reads the sidecar, the subtitle files and the glossary beside
the video and hands their bytes over, then writes what comes back, or offers it as downloads where
the browser can't write (Safari and Firefox, S48). Video bytes never enter Python (wasm32's 4 GB
address space): the page computes the video's quick hash itself (§8.3) and plays it from a blob
URL it made. Which files are an episode's is decided here, from the folder's names alone
(`listing`), so the rules stay in Python. The rules exist once: each open, Save and pick runs
`web.folder`, the code LocalBackend runs, on a copy of the files in a private staging folder
(Pyodide's in-memory file system; a temporary folder on the host), and hands back the bytes of
each file that changed, the sidecar first. Bytes, not decoded text, as spec §21's "text" is meant:
a projection's hash is of a file's bytes (§15.2), so a subtitle file with a BOM, or in GBK, must
arrive as it is on disk. A name that differs from vid2sub's own only in case is staged under
vid2sub's, as the case-blind file systems of macOS and Windows see it, so someone else's
`Show.EN.SRT` is still left alone (§6.6).

Save where the page can write (Chrome and Edge, §14.6, S47): the page reads the files again and
hands them over, and the merge is the union of the folder's sidecar now and the episode's own
records (the outside edits recorded at open, which the folder doesn't hold yet), so another
writer's records are never lost; the page re-reads the sidecar just before it writes, and saves
again if it changed (Phase 4 Task 3). A sidecar that is gone, or that names another video (the
person picked another folder), saves nothing. Where the page can't read the folder again
(Safari's read-only folder), Save builds on the files as the episode last saw them, kept in the
episode (`BrowserEpisode.files`), so a second download holds the first one's versions and
glossary terms too. A Save or a pick changes nothing here: it returns the saved episode and the
bytes to write, and the caller keeps the episode once they are written, so a write that fails
leaves the edits unsaved in the tab (Phase 4 Review Focus 1).

The browser has no endpoints, models, jobs, ffmpeg or keys (`capabilities.generate` is false, the
Phase 2 plan's Decision 23), so `BrowserRuntime` says what each local-only part of the runtime
does here (Phase 4 Task 1). Like the server, this module imports only what the Pages bundle has
(`tests/test_pages_imports.py`).
"""

from __future__ import annotations

import re
import tempfile
import threading
from collections.abc import Collection, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field, fields, replace
from pathlib import Path, PurePath
from types import MappingProxyType
from typing import Literal

from vid2sub import store
from vid2sub.media.identity import VideoIdentity
from vid2sub.security import WriteRefused, safe_write
from vid2sub.subs import naming
from vid2sub.subs.sidecar import SidecarError, serialize
from vid2sub.web import folder, ops, runtime
from vid2sub.web.episode import (
    Capabilities,
    Episode,
    OpenError,
    RetranslateError,
    SaveError,
    SaveResult,
)
from vid2sub.web.settings import EndpointError, Session

MAX_NAMES = 10_000  # file names in one folder's listing
MAX_FILES = 64  # files one open or Save hands over: a sidecar, a glossary and subtitle files
MAX_BYTES = 64 * 2**20  # bytes in each: a sidecar is about 400 KB plus 50 KB a version (§14.7)
MAX_NAME = 255  # characters in a file name
SHA256 = re.compile(r"[0-9a-f]{64}")
# What URL.createObjectURL returns: blob:<the page's origin>/<a UUID> (File API).
BLOB_URL = re.compile(r"blob:https?://[A-Za-z0-9.:\[\]-]+/[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}"
                      r"-[0-9A-Fa-f]{12}")
SUBTITLES = (".srt", ".ass")
NO_SUBTITLES = "no subtitles yet: making them needs the local app (vid2sub run)"
NO_VIDEO = "its video isn't in this folder"
TWINS = ("another video in this folder has the same name, so their subtitles would collide: "
         "rename one of them")
BAD_NAMES = "the page sent a file name that isn't a file in the folder"
BAD_VIDEO = "the page didn't say which video this is, or how big it is"
BAD_URL = "the video's address isn't one this page made"
TOO_MANY = "that's more files than an episode has"
TOO_BIG = "one of the episode's files is too big to open"
CHANGED = "the folder changed while it was being read"
CASES = "differ only in case, so vid2sub can't tell which is its own: rename one of them"
ANOTHER = ("that folder's sidecar is another video's, so nothing was saved: open the folder this "
           "episode came from")
CANT_PLAY = ("this browser can't play this video; the local app can make a copy of its sound "
             "that plays (vid2sub serve)")
LOCAL_ONLY = "the browser editor can't translate"
INSTALL = "generating subtitles needs the local app: install vid2sub and run vid2sub serve"


@dataclass(frozen=True)
class Found:
    """An episode in a folder's listing: its video's name (the sidecar's when the video isn't
    there), the files the page reads and hands to `open`, the sidecar first, and why it can't be
    opened, if it can't."""

    name: str
    reads: tuple[str, ...] = ()
    problem: str | None = None


@dataclass(frozen=True)
class BrowserEpisode(Episode):
    """An episode the page handed over: `video` is the video's bare name, and `files` the
    episode's files as Python last saw them, by name (what Save builds on when the page can't
    read the folder again)."""

    files: Mapping[str, bytes] = field(default_factory=dict)


class BrowserBackend:
    def __init__(self) -> None:
        self._open: dict[str, str] = {}  # episode id → the blob URL the page plays it from
        self._lock = threading.Lock()  # Pyodide has no threads, but tests share a backend

    def capabilities(self) -> Capabilities:
        """No path box, nothing generated, and Save hands the files back to the page, which
        writes them where it can (Chrome, Edge) and offers them as downloads elsewhere (§21)."""
        return Capabilities(engine="browser", generate=False, save="download", path_input=False)

    def listing(self, names: Sequence[str]) -> list[Found]:
        """The episodes in a folder, from its file names alone: each video beside a sidecar, with
        the files to read for it, and each that can't be opened, with why; by name."""
        names = _names(names, MAX_NAMES)
        videos: dict[str, list[str]] = {}
        for name in names:
            if PurePath(name).suffix.lower() in naming.MEDIA_SUFFIXES:
                videos.setdefault(naming.stem(name).casefold(), []).append(name)
        found: list[Found] = []
        with_sidecar: set[str] = set()
        for name in names:
            if not name.endswith(naming.SIDECAR_SUFFIX):
                continue
            stem = name.removesuffix(naming.SIDECAR_SUFFIX).casefold()
            twins = sorted(videos.get(stem, []))
            with_sidecar.add(stem)
            if not twins:
                found.append(Found(name, problem=NO_VIDEO))
            elif len(twins) > 1:
                found += [Found(video, problem=TWINS) for video in twins]
            else:
                video = twins[0]
                rest = sorted(n for n in names if n != name and _belongs(video, n))
                found.append(Found(video, (name, *rest)))
        found += [Found(video, problem=NO_SUBTITLES) for stem, group in videos.items()
                  if stem not in with_sidecar for video in group]
        return sorted(found, key=lambda f: (f.name.casefold(), f.name))

    def open(self, video: str, *, size: int, quick_sha256: str, url: str,
             files: Mapping[str, bytes], names: Collection[str] | None = None) -> Episode:
        """The episode the handed-over files hold, as LocalBackend opens one: outside edits to
        its subtitle files recorded (kept in the episode until a Save writes them), its tracks,
        heads, conflicts, words and glossary. `size` and `quick_sha256` are the page's (§8.3);
        the duration is the sidecar's, since the browser can't measure it as ffprobe does.
        `names`, the folder's, prove every file of the episode was handed over."""
        name = _video_name(video)
        if (type(size) is not int or size < 0 or not isinstance(quick_sha256, str)
                or not SHA256.fullmatch(quick_sha256)):
            raise OpenError(BAD_VIDEO)
        if not isinstance(url, str) or not BLOB_URL.fullmatch(url):
            raise OpenError(BAD_URL)
        handed = _handed(name, files, names, OpenError)
        if naming.sidecar_name(name) not in handed:
            raise OpenError(NO_SUBTITLES)
        with _staging(handed) as stage:
            staged = stage / name
            try:
                side, warnings = store.load(staged)
            except SidecarError as err:
                raise OpenError(str(err)) from None
            header = store.header_for(staged, VideoIdentity(size, quick_sha256),
                                      side.header.video.duration_ms)
            ep = folder.opened(staged, header, side,
                               [*warnings, *folder.changed_video(side.header, header)])
            ep = _browser(ep, name, _read(stage))
        with self._lock:
            self._open[ep.id] = url
        return ep

    def is_open(self, episode_id: str) -> bool:
        with self._lock:
            return episode_id in self._open

    def close(self, episode_id: str) -> None:
        """Forgets the episode; unsaved edits in it are dropped (the tab keeps a draft, §14.5)."""
        with self._lock:
            self._open.pop(episode_id, None)

    def video_url(self, episode_id: str) -> str | None:
        """The blob URL the page plays an open episode's video from."""
        with self._lock:
            return self._open.get(episode_id)

    def revoke_owner(self, owner: str) -> None:
        """The runtime's media part: nothing to revoke, since the page owns its blob URLs and
        revokes them itself (spec §6.5's media tokens are the local engine's)."""

    def apply(self, ep: Episode, op: ops.EditOp) -> Episode:
        self._check_open(ep)
        return folder.apply(ep, op)

    def undo(self, ep: Episode) -> Episode:
        self._check_open(ep)
        return folder.undo(ep)

    def redo(self, ep: Episode) -> Episode:
        self._check_open(ep)
        return folder.redo(ep)

    def save(self, ep: Episode, *, formats: Sequence[Literal["srt", "ass"]],
             files: Mapping[str, bytes] | None = None, names: Collection[str] | None = None
             ) -> tuple[Episode, SaveResult, dict[str, bytes]]:
        """Save (spec §14.5) on `files`, the folder's files read again, or with none, on those
        the episode last saw: the saved episode, what Save did, and the bytes of each file to
        write, the sidecar first. Nothing is kept here until the caller keeps the episode."""
        self._check_open(ep)
        return self._staged(ep, files, names, lambda staged: folder.save(staged, formats=formats))

    def resolve(self, ep: Episode, track: str, rendition: str, *,
                files: Mapping[str, bytes] | None = None, names: Collection[str] | None = None
                ) -> tuple[Episode, SaveResult, dict[str, bytes]]:
        """A pick of a conflicted track's version (spec §14.4), as `save` works on files."""
        self._check_open(ep)
        return self._staged(ep, files, names,
                            lambda staged: folder.resolve(staged, track, rendition))

    def _staged(self, ep: Episode, files: Mapping[str, bytes] | None,
                names: Collection[str] | None, act) -> tuple[Episode, SaveResult,
                                                             dict[str, bytes]]:
        name = ep.video.name
        if files is None:
            before = dict(ep.files) if isinstance(ep, BrowserEpisode) else {}
        else:
            before = _handed(name, files, names, SaveError)
        sidecar = naming.sidecar_name(name)
        if sidecar not in before:
            raise SaveError(folder.GONE)
        with _staging(before) as stage:
            staged = stage / name
            try:
                disk, _ = store.load(staged)
                if disk is None or disk.header != ep.sidecar.header:
                    raise SaveError(ANOTHER)
                merged = disk.add(*ep.sidecar.records)
                if merged != disk:  # the outside edits recorded at open, not in the folder yet
                    safe_write(stage / sidecar, serialize(merged).encode("utf-8"), overwrite=True)
            except (SidecarError, WriteRefused) as err:
                raise SaveError(str(err)) from None
            done, result = act(replace(ep, video=staged))
            after = _read(stage)
        writes = {n: data for n, data in sorted(after.items(), key=lambda kv: kv[0] != sidecar)
                  if before.get(n) != data}
        return _browser(done, name, after), result, writes

    def _check_open(self, ep: Episode) -> None:
        if not self.is_open(ep.id):
            raise OpenError("this episode was closed: open it again")


class BrowserRuntime(runtime.Runtime):
    """Pages' runtime (spec §21), made by `browser_runtime`: the backend is a BrowserBackend, and
    there is no queue, config or keys (no jobs, endpoints or models in the browser), no job
    context, and no media tokens (`media` is the backend, which has none to revoke). The session
    is a bundled `web.settings.Session`, whose defaults give Save's formats (SRT). The local-only
    parts, in the browser: `reachable` finds nothing to check; `media_for` gives the blob URL the
    page made for the video, and no playback audio, since there is no ffmpeg; `retranslate` and
    `endpoint_models` refuse, and the server offers neither, as `capabilities.generate` is
    false."""

    def reachable(self) -> dict[str, bool]:
        return {}

    def media_for(self, ep: Episode, *, audio_only: bool = False) -> runtime.Media:
        url = self.backend.video_url(ep.id)
        if audio_only or url is None:
            return runtime.Media(None, None, CANT_PLAY)
        return runtime.Media(url, None)

    def retranslate(self, ep: Episode, track: str, *, ids: Sequence[str] | None,
                    allow_cloud: bool, on_batch=None) -> Episode:
        raise RetranslateError(LOCAL_ONLY, INSTALL)

    def endpoint_models(self, name: str) -> list[str]:
        raise EndpointError(LOCAL_ONLY, INSTALL)


def browser_runtime(backend: BrowserBackend | None = None) -> BrowserRuntime:
    """The runtime Pages configures before it imports the server (as recordings' pages/app.py
    does)."""
    backend = backend if backend is not None else BrowserBackend()
    return BrowserRuntime(backend=backend, queue=None, media=backend, config=None, keys=None,
                          session=Session(), job_context=None)


def _names(names: object, limit: int) -> list[str]:
    if not isinstance(names, (list, tuple)) or len(names) > limit:
        raise OpenError(TOO_MANY)
    if not all(_bare(n) for n in names):
        raise OpenError(BAD_NAMES)
    return list(names)


def _bare(name: object) -> bool:
    """A file's own name: no folder, no control character, at most MAX_NAME characters."""
    return (isinstance(name, str) and 0 < len(name) <= MAX_NAME and name not in (".", "..")
            and not any(ch in name for ch in "/\\\0") and name.isprintable())


def _video_name(video: object) -> str:
    if not _bare(video) or PurePath(video).suffix.lower() not in naming.MEDIA_SUFFIXES:
        raise OpenError(BAD_VIDEO)
    return video


def _own_names(video: str) -> dict[str, str]:
    """Each name vid2sub reads or writes beside `video`, by its case-folded form (§14.1, §15.1,
    §16)."""
    own = [naming.sidecar_name(video), naming.GLOSSARY_NAME]
    own += [naming.subtitle_name(video, track, fmt.lstrip(".")) for track in naming.TRACKS
            for fmt in SUBTITLES]
    return {n.casefold(): n for n in own}


def _belongs(video: str, name: str) -> bool:
    return name.casefold() in _own_names(video)


def _handed(video: str, files: object, names: Collection[str] | None,
            error: type[Exception]) -> dict[str, bytes]:
    """The handed-over files that are the episode's, under vid2sub's names for them. Refused:
    too many or too big, a name with a folder in it, two names one case apart, and a file of the
    episode the folder's `names` list that wasn't handed over."""
    if not isinstance(files, Mapping) or len(files) > MAX_FILES:
        raise error(TOO_MANY)
    own = _own_names(video)
    out: dict[str, bytes] = {}
    for name, data in files.items():
        if not _bare(name):
            raise error(BAD_NAMES)
        if not isinstance(data, bytes) or len(data) > MAX_BYTES:
            raise error(TOO_BIG)
        canonical = own.get(name.casefold())
        if canonical is None:
            continue  # not the episode's: a fansub's .fr.srt, say
        if canonical in out:
            raise error(f"{canonical} and another file {CASES}")
        out[canonical] = data
    if names is not None:
        try:
            listed = _names(list(names), MAX_NAMES)
        except OpenError as err:
            raise error(str(err)) from None
        if any(n.casefold() in own and n not in files for n in listed):
            raise error(CHANGED)  # a file of the episode the page didn't hand over
    return out


@contextmanager
def _staging(files: Mapping[str, bytes]) -> Iterator[Path]:
    """A private folder holding `files` (`tempfile`'s, mode 0700), removed afterwards."""
    with tempfile.TemporaryDirectory(prefix="vid2sub-stage-") as folder_:
        stage = Path(folder_)
        for name, data in files.items():
            safe_write(stage / name, data, overwrite=False)
        yield stage


def _read(stage: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(stage.iterdir())
            if p.is_file() and not p.is_symlink() and not p.name.startswith(".")}


def _browser(ep: Episode, name: str, files: Mapping[str, bytes]) -> BrowserEpisode:
    values = {f.name: getattr(ep, f.name) for f in fields(Episode)}
    return BrowserEpisode(**{**values, "video": Path(name)}, files=MappingProxyType(dict(files)))
```

- [ ] **Step 18: Run them; they pass, and each guard fails without its fix.** `VID2SUB_REQUIRE_
  FFMPEG=1 uv run pytest tests/test_browser_backend.py -q`: `28 passed`. Then revert each fix in
  turn in `src/vid2sub/web/browser.py`, run the file again, and restore it (`git checkout` won't
  do: it is new; keep a copy):
  - the merge, `merged = disk.add(*ep.sidecar.records)` made `merged = disk`: `FAILED
    …test_an_outside_edit_found_at_open_is_saved_once_the_page_writes`, `E KeyError:
    'r_…'` (the editor's version's parent isn't in the folder's sidecar);
  - exact names only, `canonical = own.get(name.casefold())` made `canonical = name if name in
    own.values() else None`: `2 failed`, the two case tests;
  - the completeness check's `if any(n.casefold() in own and n not in files for n in listed):`
    made `if False:`: `1 failed`, `…test_a_file_of_the_episode_the_page_didnt_hand_over_stops_
    the_open_and_the_save`;
  - the header check, `if disk is None or disk.header != ep.sidecar.header:` made `if disk is
    None:`: `1 failed`, `…saves_nothing`;
  - the URL check's `if not isinstance(url, str) or not BLOB_URL.fullmatch(url):` made `if
    False:`: `5 failed`, every `test_a_video_address_the_page_didnt_make_is_refused` case.
- [ ] **Step 19: Run the checks; they pass.** `make check`. Expected: `1066 passed, 2 skipped, 36
  deselected` (twice), `Test Files  20 passed (20)`, `Tests  89 passed (89)`, `All checks
  passed!`, `no leaks found`.
- [ ] **Step 20: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(web): 🤖 the browser backend opens, edits and saves an episode on the bytes of its files, never the video's

Spec §3.3, §14.6 and §21 (S47, S48): in Pages the page holds the folder's handles, so Python works
on what it hands over. vid2sub.web.browser's BrowserBackend:

- listing(names): from the folder's file names alone, each video beside a sidecar, with the
  files the page reads for it (the sidecar first, then the subtitle files vid2sub would write
  for that video, then the glossary), and each one that can't open, with why (no subtitles yet,
  no video, two videos one stem). Never the video itself. A name with a folder, a control
  character or over 255 characters is refused.
- open(video, size, quick_sha256, url, files, names): the page's quick hash (§8.3) and blob URL;
  the duration is the sidecar's (the browser can't measure it as ffprobe does). It runs
  web.folder.opened, the code LocalBackend runs, on a copy of the files in a private staging
  folder (Pyodide's in-memory file system, a temporary folder on the host), so the episode is
  the local engine's: the test compares tracks, heads, conflicts, words and notes. An outside
  edit is recorded in the episode only, and the folder's file is untouched.
- save and resolve (a pick) return the saved episode, what Save did, and the bytes of each file
  that changed, the sidecar first, and keep nothing: the caller keeps the episode once the page
  has written them (Phase 4 Review Focus 1). Given the folder's files read again, the merge is
  the union of the folder's sidecar and the episode's own records, so another writer's version
  is kept (Review Focus 2's case, built against a CLI-shaped writer) and the outside edit found
  at open is saved once. Given none (Safari's read-only folder), Save builds on the files the
  episode last saw (BrowserEpisode.files), so a second download holds the first one's versions
  and glossary terms.
- Bytes, not decoded text: a projection's hash is of a file's bytes (§15.2). A name vid2sub
  writes, in another case, is staged under vid2sub's (macOS and Windows see one file), so
  someone else's Show.EN.SRT is left alone; two names one case apart are refused.
- Refused: a sidecar gone or naming another video at Save (nothing saved), a file of the episode
  the folder lists but the page didn't hand over (Save would have written over it), too many or
  too big files, and a video address that isn't a blob URL the page made (§6.9).
- BrowserRuntime (browser_runtime()) is Pages' Runtime: no queue, config, keys or job context;
  media is the backend (no media tokens to revoke); reachable finds nothing; media_for gives the
  page's blob URL and, asked for the sound alone, says the local app can make it (no ffmpeg);
  retranslate and endpoint_models refuse; the session's defaults give Save's SRT.
- naming.MEDIA_SUFFIXES: the video suffixes moved from the pipeline into the pure naming module,
  so the listing finds videos by the same list; the pipeline keeps the name.

Each guard failed without its fix, reverted in turn: without the merge, a KeyError, the editor's
version's parent missing from the folder's sidecar (the test
moves the clock between open and save); with exact names only, the case tests; without the
completeness check, the file-not-handed-over test; without the header check, the other video's
sidecar test; without the URL check, all five address cases.

Docs read: the W3C File API's "generate a new blob URL" (blob:, the origin's serialization, /,
a UUID). Pyodide's docs don't say where /tmp lives; round 1a's check showed safe_write works
in Pyodide's /tmp.

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-4.md Task 1
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/pipeline.py src/vid2sub/subs/naming.py src/vid2sub/web/browser.py
  tests/test_browser_backend.py`, `git commit -F .git/COMMIT_MSG`, then `git log -1
  --format='%(trailers)'` shows `Plan:`.

#### Round 1d: the server with the browser runtime

- [ ] **Step 21: Write the failing tests,** `tests/test_web_browser.py`:

```python
"""The Shiny server with the Pages editor's runtime, as Shinylive runs it: the Shiny app alone,
with no FastAPI shell, guards or launch token (spec §21; Phase 4 Task 1).

The browser has no endpoints, ffmpeg, models or jobs, so the server offers none of them: the
capabilities say so, and the engine status, the settings drawer and the Jobs page are explicit
nulls (spec §19.1: a null clears a pane), never an output error, which the page would log.
"""

import json
import threading

import pytest
from starlette.testclient import TestClient

from vid2sub.web import runtime, server
from vid2sub.web.browser import BrowserRuntime, browser_runtime

OUTPUTS = {"capabilities", "status", "settings", "jobs", "episode", "busy", "progress"}
CHECKS: list[str] = []  # each endpoint check the server asked the runtime for


@pytest.fixture(autouse=True)
def fresh_reactive_lock():
    """shiny's reactive lock is bound to the first event loop it is contended on, and each
    TestClient runs its own loop (as tests/test_web_server.py does)."""
    from shiny.reactive import _core

    _core._reactive_environment._lock = None
    yield
    _core._reactive_environment._lock = None


class Watched(BrowserRuntime):
    """The browser's runtime, noting each endpoint check the server asks for."""

    def reachable(self) -> dict[str, bool]:
        CHECKS.append("reachable")
        return super().reachable()


@pytest.fixture
def rt():
    made = browser_runtime()
    made = Watched(**{name: getattr(made, name) for name in made.__dataclass_fields__})
    CHECKS.clear()
    runtime.configure(made)
    yield made
    runtime.configure(None)


def session(until) -> list[dict]:
    """The messages a new session gets until `until(messages)` holds (20 s at most)."""
    messages: list[dict] = []
    with TestClient(server.app) as client, client.websocket_connect("/websocket/") as ws:
        init = {f".clientdata_output_{name}_hidden": False for name in OUTPUTS}
        ws.send_text(json.dumps({"method": "init", "data": init}))

        def read() -> None:
            while not until(messages):
                messages.append(json.loads(ws.receive_text()))

        reader = threading.Thread(target=read, daemon=True)
        reader.start()
        reader.join(20)
    assert until(messages), f"the session sent only {messages}"
    return messages


def values(messages: list[dict]) -> dict:
    out: dict = {}
    for m in messages:
        out.update(m.get("values", {}))
    return out


def errors(messages: list[dict]) -> dict:
    out: dict = {}
    for m in messages:
        out.update(m.get("errors", {}))
    return out


def test_the_browser_editor_offers_no_engine_status_settings_or_jobs(rt):
    got = session(lambda ms: OUTPUTS <= set(values(ms)) | set(errors(ms)))
    assert errors(got) == {}
    shown = values(got)
    assert shown["capabilities"] == {"engine": "browser", "generate": False, "save": "download",
                                     "path_input": False}
    assert (shown["status"], shown["settings"], shown["jobs"], shown["episode"]) == (
        None, None, None, None)
    assert CHECKS == []  # nothing to check: the browser has no endpoints
```

  and in `tests/test_pages_imports.py`:

```diff
diff --git a/tests/test_pages_imports.py b/tests/test_pages_imports.py
index 7767844..5180996 100644
--- a/tests/test_pages_imports.py
+++ b/tests/test_pages_imports.py
@@ -27,13 +27,14 @@ SRC = Path(__file__).resolve().parents[1] / "src" / "vid2sub"
 # the editor's edits at the door, so the browser editor needs it too; it is pure. `web.settings`
 # holds the session's defaults, which the runtime makes (Task 18). `web.folder` opens, edits and
 # saves an episode for both backends, through `store`, which needs `security` and the video's
-# identity type (`media.identity`): each imports only the standard library and the pure
-# packages (Phase 4 Task 1).
+# identity type (`media.identity`), and `web.browser` is the Pages editor's backend: each imports
+# only the standard library, the pure packages and the bundle's own (Phase 4 Task 1).
 BUNDLED_TREES = ("vid2sub.subs", "vid2sub.parse")
 BUNDLED_MODULES = ("vid2sub", "vid2sub.catalog", "vid2sub.web", "vid2sub.web.server",
                    "vid2sub.web.views", "vid2sub.web.episode", "vid2sub.web.runtime",
                    "vid2sub.web.ops", "vid2sub.web.settings", "vid2sub.web.folder",
-                   "vid2sub.store", "vid2sub.security", "vid2sub.media", "vid2sub.media.identity")
+                   "vid2sub.web.browser", "vid2sub.store", "vid2sub.security", "vid2sub.media",
+                   "vid2sub.media.identity")
 # vid2sub's own dependencies (pyproject.toml, the mac extra, and Phase 3's faster-whisper) that
 # the bundle doesn't have.
 NOT_BUNDLED = ("platformdirs", "numpy", "onnxruntime", "chatlas", "openai", "httpx", "yt_dlp",
@@ -90,6 +91,14 @@ def test_what_both_backends_share_imports_with_only_what_the_pages_bundle_has():
     assert done.stdout.strip() == "imported vid2sub.web.folder"
 
 
+def test_the_browser_backend_imports_with_only_what_the_pages_bundle_has_before_the_server():
+    # why: Pages configures a Runtime holding a BrowserBackend, then imports the server (spec
+    # §21, as recordings' pages/app.py does).
+    done = _import_as_pages("vid2sub.web.browser", "vid2sub.web.server")
+    assert done.returncode == 0, done.stderr[-3000:]
+    assert done.stdout.strip() == "imported vid2sub.web.browser vid2sub.web.server"
+
+
 def test_the_refusal_itself_works():
     # why: a finder that refused nothing would pass the test above whatever the server imports.
     done = _import_as_pages("vid2sub.web.backend")
```

- [ ] **Step 22: Run them; watch them fail.** `uv run pytest tests/test_web_browser.py
  tests/test_pages_imports.py -q`. Expected: `1 failed, 7 passed`, with `assert {'status':
  {'...'type': None}} == {}` and `'message': "'BrowserBackend' object has no attribute 'tools'"`.
- [ ] **Step 23: The server's status and check are the local engine's.** In
  `src/vid2sub/web/server.py`:

```diff
diff --git a/src/vid2sub/web/server.py b/src/vid2sub/web/server.py
index c534356..e67b5df 100644
--- a/src/vid2sub/web/server.py
+++ b/src/vid2sub/web/server.py
@@ -40,8 +40,9 @@ through the runtime, whose `retranslate` turns the engine's errors into the pure
 `RetranslateError`, so nothing here imports them. Cloud models only when the request itself says
 `allow_cloud: true` (§7.2): the editor's box, unticked every time.
 
-The settings drawer (§19.2, S35) is `web.settings`'s: the `settings` output (null in Pages, which
-has no endpoints), a typed key (`typed_key`, read in the flush of its own message and replaced by
+The top bar's engine status (§19.2) is the local engine's, and null in Pages, which has no
+endpoints, ffmpeg or keys to check (Phase 4 Task 1). The settings drawer (§19.2, S35) is
+`web.settings`'s: the `settings` output (null in Pages, which has no endpoints), a typed key (`typed_key`, read in the flush of its own message and replaced by
 the page's null straight after, so Shiny's input map doesn't keep it; it lives only in the
 engine's `KeyRing`), the session's defaults (`session_defaults`), and Test (`endpoint_test`, its
 answer the `endpoint_test_result` message), which asks the endpoint's `/v1/models` through the
@@ -405,6 +406,8 @@ def _cue_ids(ids: object) -> bool:
 
 def server(input: Inputs, output: Outputs, session: Session) -> None:
     rt = runtime.current()
+    # The local engine's: the Pages editor has no endpoints, ffmpeg, models or jobs (spec §21).
+    local = rt.backend.capabilities().generate
 
     @reactive_output
     def capabilities():
@@ -412,7 +415,7 @@ def server(input: Inputs, output: Outputs, session: Session) -> None:
 
     # The endpoint check runs as this session's extended task, off the event loop and outside
     # Shiny's reactive lock, now and every STATUS_EVERY seconds. The status keeps showing the last
-    # result while the next check runs.
+    # result while the next check runs. The browser editor has nothing to check.
     found = reactive.value({})
 
     @reactive.extended_task
@@ -421,6 +424,8 @@ def server(input: Inputs, output: Outputs, session: Session) -> None:
 
     @reactive.effect
     def _check_every_minute() -> None:
+        if not local:
+            return
         reactive.invalidate_later(STATUS_EVERY)
         check.invoke()
 
@@ -433,7 +438,6 @@ def server(input: Inputs, output: Outputs, session: Session) -> None:
     # editor has no endpoints (`generate` is false there), so it is offered none of this. The
     # session's settings are the launch's, shared by every tab: a change any tab makes (a default,
     # a typed key) reaches every tab's views through the session's listeners.
-    local = rt.backend.capabilities().generate
     ticks = itertools.count(1)
     changed = reactive.value(0)
     session.on_ended(rt.session.on_change(lambda: changed.set(next(ticks))))
@@ -441,6 +445,8 @@ def server(input: Inputs, output: Outputs, session: Session) -> None:
     @reactive_output
     def status():
         changed()  # a typed key makes a key present
+        if not local:
+            return None  # an explicit null: the browser editor has no engine status
         return views.status_view(rt.config, rt.keys, found(),
                                  ffmpeg=bool(rt.backend.tools.ffmpeg))
 
```

- [ ] **Step 24: The docs the browser backend made untrue.** `docs/architecture.md`'s Pages-safe
  diagram, and the spec's §4.1, §19.1 and §21:

````diff
diff --git a/docs/architecture.md b/docs/architecture.md
index f2c5cea..f542da6 100644
--- a/docs/architecture.md
+++ b/docs/architecture.md
@@ -76,6 +76,10 @@ only the pure packages, shiny, shinyreact, htmltools, pydantic and `web.episode`
 reached through the launch's `Runtime`, and every call that blocks goes through
 `runtime.blocking`: a worker thread here, inline in Pyodide. Each tab's `Editor` runs that
 tab's requests one at a time, in order; the job queue is the engine's, shared by every tab.
+Opening, the edit rules, Save and a pick are `web.folder`'s, through `vid2sub.store`, so both
+backends share them: `LocalBackend` adds the typed path, ffprobe, the quick hash and
+Retranslate; `web.browser.BrowserBackend`, which Pages' runtime holds (Phase 4), runs them on
+a staged copy of the files the page hands over.
 
 ```mermaid
 flowchart TB
@@ -87,9 +91,11 @@ flowchart TB
     settings["web.settings<br/>settings_view · Session's defaults"]
     runtime["web.runtime<br/>Runtime · blocking"]
     pure["vid2sub.subs · parse · catalog · web.episode"]
+    folder["web.folder<br/>open · apply · save · resolve,<br/>through vid2sub.store"]
+    browserbe["web.browser.BrowserBackend<br/>in Pages: on the bytes the page<br/>hands over, staged in memory"]
   end
   subgraph local["Local only"]
-    backend["web.backend.LocalBackend<br/>open · apply · save · resolve · retranslate"]
+    backend["web.backend.LocalBackend<br/>typed path · ffprobe · quick hash · retranslate"]
     queue["jobs.Queue<br/>one worker thread, one job at a time"]
     tokens["web.media.MediaTokens"]
     keys["engines.clients.KeyRing<br/>keys from the environment;<br/>typed keys, this launch only"]
@@ -104,7 +110,10 @@ flowchart TB
   editor -->|"rt.backend · runtime.blocking"| runtime
   server -->|"jobs_submit · job_cancel"| runtime
   runtime --> backend & queue & tokens & keys
+  runtime -->|"in Pages"| browserbe
+  backend & browserbe --> folder
   backend --> core
+  folder --> files
   queue -->|"runtime.job_runner"| core
   core <--> files
 ```
````
```diff
diff --git a/docs/superpowers/specs/2026-10-14-vid2sub-design.md b/docs/superpowers/specs/2026-10-14-vid2sub-design.md
index a00837d..900c088 100644
--- a/docs/superpowers/specs/2026-10-14-vid2sub-design.md
+++ b/docs/superpowers/specs/2026-10-14-vid2sub-design.md
@@ -307,7 +307,9 @@ src/vid2sub/
     app.py                FastAPI shell: /auth, /healthz, /media/{token}; Shiny mounted at /
     guards.py             HostGuard, WriteGuard (copied from recordings), TokenGuard, CSP
     server.py             the shinyreact server (ReactApp(server) is called in this file)
-    backend.py            Backend protocol, LocalBackend, BrowserBackend
+    backend.py            LocalBackend (the engine)
+    browser.py            BrowserBackend (Pages)
+    folder.py             what both backends share: open, edit, save, pick
     www/                  ui.js + ui.css (build output), fonts
 frontend/                 Vite + React 19 + TypeScript + Tailwind v4 + shadcn (radix-nova)
 pages/                    the Shinylive entry (app.py, requirements.txt)
@@ -1240,9 +1242,9 @@ UI run from a terminal or a script.
   the calling frame). Outputs are `@reactive_output` JSON values from pure view functions;
   progress uses `send_message`. An unset input is a silent exception the client treats as
   pending; an explicit null clears a pane (`recordings`' pattern).
-- **Backend** (`web/backend.py`, §3.3): the server calls `LocalBackend` or `BrowserBackend`; a
-  `capabilities` output tells React which controls exist (path box or folder picker; Generate or
-  not; Save to disk or Download).
+- **Backend** (`web/backend.py`, `web/browser.py`, §3.3): the server calls `LocalBackend` or
+  `BrowserBackend`, which share `web/folder.py`; a `capabilities` output tells React which
+  controls exist (path box or folder picker; Generate or not; Save to disk or Download).
 
 ### 19.2 Screens
 
@@ -1302,10 +1304,11 @@ Dan, 2026-10-14: the Pages site is a working subtitle editor with no install, pl
 
 - **Build:** Shinylive 0.8.12 (assets 0.10.15, Pyodide 0.27.7, Python 3.12.7, pydantic 2.10.5),
   pinned through `scripts/shinylive_local.py` as in `recordings`. The app bundles
-  `vid2sub.subs`, `vid2sub.catalog`, `vid2sub.parse`, `web/server.py` with `BrowserBackend`,
-  shinyreact, and vendored wheels of pysubs2, opencc-purepy and charset-normalizer, so the site
-  never fetches from PyPI. Pyodide loads packages only for imports in the app directory's top-level
-  `.py` files, so `pages/app.py` imports them at the top and lists them in `requirements.txt`.
+  `vid2sub.subs`, `vid2sub.catalog`, `vid2sub.parse`, `web/server.py` with `BrowserBackend`
+  (and `vid2sub.store`, which both backends save through), shinyreact, and vendored wheels of
+  pysubs2, opencc-purepy and charset-normalizer, so the site never fetches from PyPI. Pyodide
+  loads packages only for imports in the app directory's top-level `.py` files, so
+  `pages/app.py` imports them at the top and lists them in `requirements.txt`.
   There is no FastAPI (Shinylive's Starlette is 0.38).
 - **Opening files:** `FolderPicker` from `meanwhile`, with `showDirectoryPicker({mode:
   'readwrite'})` in Chrome and Edge (a file handle has no parent, so the user picks **the
```

- [ ] **Step 25: Run the checks; they pass.** First `uv run pytest tests/test_web_browser.py
  tests/test_pages_imports.py tests/test_web_server.py -q`: `38 passed`. With the check's gate
  (`if not local: return` in `_check_every_minute`) taken out, `tests/test_web_browser.py` fails:
  `AssertionError: assert ['reachable'] == []`; put it back. Then `make check`: `1068 passed, 2
  skipped, 36 deselected` (twice), `Test Files  20 passed (20)`, `Tests  89 passed (89)`,
  `All checks passed!`, `no leaks found`.
- [ ] **Step 26: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(web): 🤖 the server runs with the browser runtime: no engine status or endpoint checks, and the browser backend imports as Pages has it

Spec §21: Pages configures a Runtime holding a BrowserBackend before it imports the server. The
server offered every tab the local engine's status, built from the launch's config, keys and
ffmpeg, which the browser has none of.

- The `status` output is an explicit null where `capabilities.generate` is false (Phase 2
  Decision 23's one gate), as `settings` and `jobs` already were, and the endpoint check never
  starts there. tests/test_web_browser.py drives the Shiny app alone, as Shinylive serves it
  (no FastAPI shell, guards or token), with browser_runtime(): capabilities say browser, no
  generate, download, no path box; status, settings, jobs and episode are null; no output
  error. It failed first: the status output's error "'BrowserBackend' object has no attribute
  'tools'". With the check's gate taken out it fails: "assert ['reachable'] == []".
- tests/test_pages_imports.py imports vid2sub.web.browser, then the server, with only what the
  bundle has; web.browser joins the bundle's list.
- The docs the browser backend made untrue: the spec's layout (§4.1) names backend.py,
  browser.py and folder.py; §19.1 names both backends and what they share; §21's bundle names
  vid2sub.store. docs/architecture.md's Pages-safe diagram draws web.folder and the browser
  backend beside LocalBackend (mermaid 11's parser reads all three diagrams).

Docs read: shinyreact 0.1.0's page_react and reactive_output (an explicit null clears an
output), Shiny 1.8.0's reactive.effect and invalidate_later.

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-4.md Task 1
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/web/server.py tests/test_pages_imports.py tests/test_web_browser.py
  docs/architecture.md docs/superpowers/specs/2026-10-14-vid2sub-design.md`, `git commit -F
  .git/COMMIT_MSG`, then `git log -1 --format='%(trailers)'` shows `Plan:`.
- [ ] **Step 27: Review, look forward, close.** The Tier 2 review from `$(cat .git/TASK_BASE)`
  (`AGENTS.md`, *Reviews*: Matt Pocock's `code-review`, two axes in two subagents). Worth
  checking: `web.folder` is LocalBackend's code moved, not changed (`git diff
  $(cat .git/TASK_BASE) -M -- src/vid2sub/web/`); no path reaches a view or a message from the
  browser backend (`Episode.video` is a bare name); every refusal echoes nothing the page sent.
  The forward review over Tasks 2, 3, 6 and 11: Task 2's `pages/app.py` calls
  `browser_runtime(...)` before it imports the server, and its bundle is
  `tests/test_pages_imports.py`'s lists; Task 3's server inputs hand `BrowserBackend.open`,
  `save` and `resolve` the files' bytes (base64 on the wire), keep the saved episode only once
  the page has written `writes`, and the page reads `Found.reads`; Task 6's Step 2 finds
  `pyodide` 0.27.7 already in `frontend/package.json` and its lockfile, so it adds nothing
  there and its expected diff loses those 37 lines, and its Step 9 counts gain this task's
  Vitest file (`Test Files  21 passed`, one more test); Task 11's Step 3 relies on Save's merge.
  The docs this task made untrue are fixed in round 1d. Then the close, its own commit,
  holding this plan with this task's boxes ticked and **Now** set to `Task 2: The Pages build,
  open.`, with the message in `.git/CLOSE_MSG`:

```text
docs(plan): 🤖 close Task 1: The browser backend

Drift: none
Rulings: none
Phase-end: none
Forward: none
Tier: 2
Rounds: none
Findings: none

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-4.md Task 1
Co-Authored-By: <the model's own line>
```

  `git add docs/superpowers/plans/2026-10-23-vid2sub-phase-4.md`, `git commit -F .git/CLOSE_MSG`.

***

### Task 2: The Pages build

**Tier:** 2 · **Scenarios:** S47, S50

**Why it is built this way** (read 2026-10-24):
- **The vendored packages are folders beside `app.py`, not lines in `requirements.txt`.**
  Shinylive 0.10.15's runtime hands every line of `requirements.txt` to micropip
  (`_install_requirements_from_dir` in `shinylive.js`), which resolves a name Pyodide's lock lacks
  from PyPI at page load. So `build_pages.py` unpacks uv.lock's pure-Python wheels of pysubs2,
  opencc-purepy and charset-normalizer, each checked against uv.lock's SHA-256, into the app
  folder, which is on `sys.path` while `app.py` is imported; `requirements.txt` lists only
  Pyodide's own pydantic, which `app.py` imports at its top so Pyodide loads it.
  charset-normalizer isn't imported at the top, so Pyodide's own 3.3.2 is never loaded over the
  vendored 3.5.2. Shinylive's export still copies 3.3.2's wheel into the site (it scans every
  `.py` for imports); nothing loads it.
- **Shinylive's assets pinned by hash.** Shinylive downloads them from GitHub with no check
  (`_assets.download_shinylive`), so `shinylive_local.py` downloads `shinylive-0.10.15.tar.gz`
  itself the first time and unpacks it, with Shinylive's own `tar_safe_extractall`, only if its
  SHA-256 is the pinned one; the folder is `.cache/shinylive/`, as recordings keeps it.
- **A stale cached deploy (Review Focus 3).** Pages caches every file for ten minutes, and
  Shinylive's service worker caches nothing (`useCaching = false`). In Chromium a second visit
  took `shinylive.js`, Pyodide's worker, `pyodide.asm.js` and the standard library from the
  cache and asked only for `app.json` (through the service worker), so a deploy that bumps
  Shinylive would run the new app on the old Shinylive. Shinylive's template is replaced by
  `pages/site/`: `start.js` revalidates (`fetch(…, {cache: "no-cache"})`, a 304 when nothing
  changed) every file a deploy names alike, then starts the app as the template's inline script
  did. A Pages test checks the list against the built site.
- **The demo, for now, is Phase 2's** (Task 5 makes the public-domain clip): `web.demo.prepare`
  muxes `jfk.mp4` with ffmpeg and names it in the sidecar's header, so `make pages` needs ffmpeg
  until Task 5. Its sidecar and subtitles are bundled with the app; its video is the site's own
  `_site/demo/jfk.mp4`, played at `../demo/` (Shinylive runs the app at `<site>/app_<id>/`), so
  its bytes never reach Python. The browser editor's start screen opens it (the `demo` input).
- **A version label with `+` isn't served in Pages.** Phase 2's busy-indicators stylesheet was a
  dependency versioned `1.8.0+vid2sub`, and the version is in its path; Shinylive passes the
  page's `url.pathname` to Starlette 0.38.1 (`reqToASGI`), which answered it 404. A post release,
  `1.8.0.post1`, sorts above 1.8.0 as well, and is served (round 2c found it).
- **A video nothing probed plays.** The browser has no ffprobe, so the episode has no container
  or codec names; `canPlay` leaves such a video to the player's own error and picture checks
  instead of asking for playback audio the browser can't make.

**Files:**
- Create: `pages/app.py`, `pages/requirements.txt`, `pages/site/index.html`,
  `pages/site/start.js`, `scripts/build_pages.py`, `scripts/shinylive_local.py`,
  `scripts/rangeserver.py`, `tests/test_build_pages.py`, `tests/test_rangeserver.py`,
  `tests/pages/test_pages_site.py`
- Modify: `src/vid2sub/web/browser.py` (`Demo`, `open_demo`), `src/vid2sub/web/server.py` (the
  `demo` input; the busy indicators' version label), `frontend/src/App.tsx`,
  `frontend/src/components/Editor.tsx` (the start screen), `frontend/src/components/TopBar.tsx`
  and `TopBar.test.ts` (the banner), `frontend/src/lib/playable.ts` and `playable.test.ts`,
  `tests/test_browser_backend.py`, `tests/test_web_browser.py`, `pyproject.toml` (the `pages`
  group and marker), `uv.lock`, `Makefile` (`pages`, `pages-serve`, `pages-test`)
- Modify at the close: this plan

**Interfaces:**
- Produces, for Task 11 and `pages.yml` (Task 7), as `recordings`' `Makefile` has them:
  `make pages` builds the site into `_site/` and prints the Pyodide and Shinylive versions it
  used; `make pages-serve` serves `_site/` under `/vid2sub/` with Range requests on `127.0.0.1`
  and prints the address; `make pages-test` runs the Pages Playwright tests (Task 4).
- Consumes: the versions Task 6's Pyodide job installs, which are `uv.lock`'s (pysubs2 1.9.0,
  opencc-purepy 1.4.4, charset-normalizer 3.5.2 when Task 6 was written). Vendor those wheels;
  take charset-normalizer from PyPI, not Pyodide 0.27.7's own 3.3.2, which is below
  `pyproject.toml`'s `>=3.4`.
- Also produces:
  - `make pages`: `make build`, then `uv run --group pages python scripts/build_pages.py`; the
    first build downloads Shinylive's assets (434,679,785 bytes, SHA-256
    `92deba97423ef2baba39df1806372af320cd6f0e751f4a36f3a7faf2645ea19b`) into
    `.cache/shinylive/` and the three wheels into `.cache/wheels/`; it needs ffmpeg until Task 5.
    It prints `build_pages: wrote _site/ (44.0 MB) with Shinylive 0.8.12 (assets 0.10.15),
    Pyodide 0.27.7, Python 3.12.7. Serve it as Pages does with `make pages-serve`.`
  - `_site/`: `index.html` and `start.js` (from `pages/site/`), `app.json`, `shinylive/`,
    `shinylive-sw.js`, `demo/<the demo's video>`, `.nojekyll`.
  - `scripts/build_pages.py`: `BUNDLE_TREES`, `BUNDLE_MODULES` (held to
    `tests/test_pages_imports.py`'s), `VENDORED`, `check_inputs`, `module_files(src)`,
    `locked_wheel(name)`, `fetch_wheel(url, sha256)`, `unpack(wheel, into)`,
    `relative_font_urls(css)`, `refuse_symlinks(*roots)`, `demo_folder()`, `assemble(app, demo,
    video, *, src, wheel)`, `export(app)`, `main()`.
  - `scripts/shinylive_local.py`: `PINNED = "0.8.12"`, `ASSETS = "0.10.15"`, `ASSETS_SHA256`,
    `CACHE`, `assets(cache)`, `versions(folder)`, `main(argv)`.
  - `scripts/rangeserver.py` `serve(root, *, prefix, port=0, quiet=False, max_age=600)`: every
    response `Cache-Control: max-age=600`.
  - `pages/site/start.js`: `REVALIDATE`, the files a deploy names alike (Task 4 adds the frame
    refusal at its top).
  - `BrowserBackend(*, demo: Demo | None)`, `Demo(folder, url)`, `open_demo()`, `NO_DEMO`; the
    server's `demo` input (`{n}`), and `NO_DEMO_HERE` for the local engine; the frontend's
    `Editor` prop `onDemo` (Task 3 replaces it with `pages`), `TopBar`'s `INSTALL_URL`, test ids
    `pages-start`, `open-demo`, `local-app`.
  - pytest's `pages` marker (deselected by default; `make pages-test` runs it).

The `make check` counts below come from a clone of the finished Phase 2 with only this phase's
Tasks 1 to 4; yours are higher once Phase 3 is in. What matters is no failure, ruff's
`All checks passed!` and gitleaks' `no leaks found`; the new tests' own counts are exact. Each
`diff` block applies with `git apply` from the repository's root (save it to a file first).

- [ ] **Step 0: Record the base:** `git rev-parse HEAD > .git/TASK_BASE`.

#### Round 2a: the demo in the browser editor

- [ ] **Step 1: Write the failing tests.** Append to `tests/test_browser_backend.py` (and import
  `NO_DEMO` and `Demo` from `vid2sub.web.browser`), and in `tests/test_web_browser.py`:

```diff
diff --git a/tests/test_browser_backend.py b/tests/test_browser_backend.py
index 388b69c..7a24e3d 100644
--- a/tests/test_browser_backend.py
+++ b/tests/test_browser_backend.py
@@ -31,11 +31,13 @@ from vid2sub.web.browser import (
     CANT_PLAY,
     CHANGED,
     INSTALL,
+    NO_DEMO,
     NO_SUBTITLES,
     NO_VIDEO,
     TWINS,
     BrowserBackend,
     BrowserEpisode,
+    Demo,
     Found,
     browser_runtime,
 )
@@ -360,3 +362,23 @@ def test_in_the_browser_the_runtime_plays_the_pages_own_video_and_has_nothing_lo
     assert rt.session.defaults().formats == ("srt",)  # Save's default formats
     assert (rt.queue, rt.config, rt.keys, rt.job_context) == (None, None, None, None)
     assert rt.backend.capabilities().generate is False
+
+
+def test_the_demo_opens_from_the_files_bundled_with_the_site_and_plays_from_its_own_copy(
+        video, local, tmp_path):
+    # why: S50 and spec §21: the demo's sidecar and subtitles are bundled with the app, and its
+    # video is the site's own file, so its bytes never reach Python; its identity is the one its
+    # sidecar was made for. The site's demo is Phase 2's until Phase 4 Task 5's clip.
+    demo = tmp_path / "bundled"
+    demo.mkdir()
+    for p in video.parent.iterdir():
+        if p != video:
+            (demo / p.name).write_bytes(p.read_bytes())
+    browser = BrowserBackend(demo=Demo(demo, "../demo/"))
+    ep = browser.open_demo()
+    there = local.open(str(video))
+    assert (ep.tracks, ep.heads, ep.words, ep.notes) == (there.tracks, there.heads, there.words,
+                                                         [])
+    assert browser.video_url(ep.id) == "../demo/Show%20-%20S01E01.mkv"
+    with pytest.raises(OpenError, match=NO_DEMO):
+        BrowserBackend().open_demo()
```
```diff
diff --git a/tests/test_web_browser.py b/tests/test_web_browser.py
index 915f822..d275fa5 100644
--- a/tests/test_web_browser.py
+++ b/tests/test_web_browser.py
@@ -8,14 +8,16 @@ nulls (spec §19.1: a null clears a pane), never an output error, which the page
 
 import json
 import threading
+from pathlib import Path
 
 import pytest
 from starlette.testclient import TestClient
 
 from vid2sub.web import runtime, server
-from vid2sub.web.browser import BrowserRuntime, browser_runtime
+from vid2sub.web.browser import BrowserBackend, BrowserRuntime, Demo, browser_runtime
 
 OUTPUTS = {"capabilities", "status", "settings", "jobs", "episode", "busy", "progress"}
+DEMO = Path(__file__).resolve().parents[1] / "demo"
 CHECKS: list[str] = []  # each endpoint check the server asked the runtime for
 
 
@@ -40,7 +42,7 @@ class Watched(BrowserRuntime):
 
 @pytest.fixture
 def rt():
-    made = browser_runtime()
+    made = browser_runtime(BrowserBackend(demo=Demo(DEMO, "../demo/")))
     made = Watched(**{name: getattr(made, name) for name in made.__dataclass_fields__})
     CHECKS.clear()
     runtime.configure(made)
@@ -48,12 +50,15 @@ def rt():
     runtime.configure(None)
 
 
-def session(until) -> list[dict]:
-    """The messages a new session gets until `until(messages)` holds (20 s at most)."""
+def session(until, *, send: tuple[dict, ...] = ()) -> list[dict]:
+    """The messages a new session gets until `until(messages)` holds (20 s at most), with
+    `send`'s inputs set once it has started."""
     messages: list[dict] = []
     with TestClient(server.app) as client, client.websocket_connect("/websocket/") as ws:
         init = {f".clientdata_output_{name}_hidden": False for name in OUTPUTS}
         ws.send_text(json.dumps({"method": "init", "data": init}))
+        for data in send:
+            ws.send_text(json.dumps({"method": "update", "data": data}))
 
         def read() -> None:
             while not until(messages):
@@ -89,3 +94,18 @@ def test_the_browser_editor_offers_no_engine_status_settings_or_jobs(rt):
     assert (shown["status"], shown["settings"], shown["jobs"], shown["episode"]) == (
         None, None, None, None)
     assert CHECKS == []  # nothing to check: the browser has no endpoints
+
+
+def test_the_demo_input_opens_the_demo_which_plays_from_the_sites_own_copy(rt):
+    # why: S50: the Pages editor's demo is the bundled episode, its video the site's demo/ file.
+    def opened(ms):
+        episode = values(ms).get("episode")
+        return bool(episode)
+
+    got = session(opened, send=({"demo:shinyreact.default": {"n": 1}},))
+    assert errors(got) == {}
+    episode = values(got)["episode"]
+    assert episode["video"]["name"] == "jfk.mp4"
+    assert episode["video"]["url"] == "../demo/jfk.mp4"
+    assert episode["source"] == "en" and [t["key"] for t in episode["tracks"]] == ["en", "ja"]
+    assert episode["notes"] == []
```

  and in the frontend's tests:

```diff
diff --git a/frontend/src/lib/playable.test.ts b/frontend/src/lib/playable.test.ts
index 73a4fa9..78be106 100644
--- a/frontend/src/lib/playable.test.ts
+++ b/frontend/src/lib/playable.test.ts
@@ -62,4 +62,10 @@ describe("whether the browser can play a video", () => {
     const ask = browser("video/mp4", 'audio/mp4; codecs="mp4a.40.2"');
     expect(canPlay(ask, { ...MP4, video_codec: null })).toBe(true);
   });
+
+  it("leaves a video nothing probed to the player's own errors (the browser editor)", () => {
+    // The Pages editor has no ffprobe (spec §21), so there's no container or codec to ask about.
+    const unprobed: Video = { name: "jfk.mp4", container: "", video_codec: null, audio_codec: "" };
+    expect(canPlay(() => "", unprobed)).toBe(true);
+  });
 });
```
```diff
diff --git a/frontend/src/components/TopBar.test.ts b/frontend/src/components/TopBar.test.ts
index 5f4bca7..17b8615 100644
--- a/frontend/src/components/TopBar.test.ts
+++ b/frontend/src/components/TopBar.test.ts
@@ -38,4 +38,14 @@ describe("the top bar (spec §19.2)", () => {
   it("says when ffmpeg is missing", () => {
     expect(renderToStaticMarkup(createElement(TopBar, { status: { ffmpeg: false, endpoints: [] } }))).toContain("ffmpeg missing");
   });
+
+  it("in the browser editor, says generating subtitles needs the local app, and links to installing it in a new tab", () => {
+    // spec §21: "A banner says 'Generating subtitles needs the local app — Install →'".
+    const browser = { engine: "browser", generate: false, save: "download", path_input: false } as const;
+    const html = renderToStaticMarkup(createElement(TopBar, { capabilities: browser }));
+    expect(html).toContain("Generating subtitles needs the local app");
+    expect(html).toContain('href="https://github.com/chendaniely/vid2sub#install" target="_blank" rel="noopener noreferrer"');
+    const local = { ...browser, engine: "local", generate: true, save: "disk", path_input: true } as const;
+    expect(renderToStaticMarkup(createElement(TopBar, { capabilities: local }))).not.toContain("needs the local app");
+  });
 });
```

- [ ] **Step 2: Run them; watch them fail.** `VID2SUB_REQUIRE_FFMPEG=1 uv run pytest
  tests/test_browser_backend.py tests/test_web_browser.py -q`. Expected: `ImportError: cannot
  import name 'NO_DEMO' from 'vid2sub.web.browser'` and `cannot import name 'Demo'`. `cd frontend
  && npx vitest run src/lib/playable.test.ts src/components/TopBar.test.ts`: `Tests  2 failed |
  12 passed (14)`, with `AssertionError: expected '<header class="flex items-center gap-…' to
  contain 'Generating subtitles needs the local …'` and `AssertionError: expected false to be
  true`.
- [ ] **Step 3: The demo in the backend and the server.** In `src/vid2sub/web/browser.py` and
  `src/vid2sub/web/server.py`:

```diff
diff --git a/src/vid2sub/web/browser.py b/src/vid2sub/web/browser.py
index f0dd469..a636653 100644
--- a/src/vid2sub/web/browser.py
+++ b/src/vid2sub/web/browser.py
@@ -45,12 +45,13 @@ from dataclasses import dataclass, field, fields, replace
 from pathlib import Path, PurePath
 from types import MappingProxyType
 from typing import Literal
+from urllib.parse import quote
 
 from vid2sub import store
 from vid2sub.media.identity import VideoIdentity
 from vid2sub.security import WriteRefused, safe_write
 from vid2sub.subs import naming
-from vid2sub.subs.sidecar import SidecarError, serialize
+from vid2sub.subs.sidecar import SidecarError, parse_sidecar, serialize
 from vid2sub.web import folder, ops, runtime
 from vid2sub.web.episode import (
     Capabilities,
@@ -87,6 +88,7 @@ ANOTHER = ("that folder's sidecar is another video's, so nothing was saved: open
 CANT_PLAY = ("this browser can't play this video; the local app can make a copy of its sound "
              "that plays (vid2sub serve)")
 LOCAL_ONLY = "the browser editor can't translate"
+NO_DEMO = "this site has no demo"
 INSTALL = "generating subtitles needs the local app: install vid2sub and run vid2sub serve"
 
 
@@ -101,6 +103,16 @@ class Found:
     problem: str | None = None
 
 
+@dataclass(frozen=True)
+class Demo:
+    """The demo the site carries (spec §21, S50): `folder` holds its sidecar and subtitles,
+    bundled with the app, and `url` is where its video plays from, the site's own copy beside
+    the page (`../demo/` from the app), so the video's bytes never reach Python."""
+
+    folder: Path
+    url: str
+
+
 @dataclass(frozen=True)
 class BrowserEpisode(Episode):
     """An episode the page handed over: `video` is the video's bare name, and `files` the
@@ -111,8 +123,9 @@ class BrowserEpisode(Episode):
 
 
 class BrowserBackend:
-    def __init__(self) -> None:
-        self._open: dict[str, str] = {}  # episode id → the blob URL the page plays it from
+    def __init__(self, *, demo: Demo | None = None) -> None:
+        self.demo = demo
+        self._open: dict[str, str] = {}  # episode id → the URL the page plays its video from
         self._lock = threading.Lock()  # Pyodide has no threads, but tests share a backend
 
     def capabilities(self) -> Capabilities:
@@ -161,7 +174,27 @@ class BrowserBackend:
             raise OpenError(BAD_VIDEO)
         if not isinstance(url, str) or not BLOB_URL.fullmatch(url):
             raise OpenError(BAD_URL)
-        handed = _handed(name, files, names, OpenError)
+        return self._opened(name, size, quick_sha256, url, _handed(name, files, names, OpenError))
+
+    def open_demo(self) -> Episode:
+        """The demo's episode (S50), from the files bundled with the site: its video is the one
+        its sidecar names, with the size and quick hash it was made for, playing from the site's
+        own copy."""
+        if self.demo is None:
+            raise OpenError(NO_DEMO)
+        names = sorted(p.name for p in self.demo.folder.iterdir() if p.is_file())
+        sidecars = [n for n in names if n.endswith(naming.SIDECAR_SUFFIX)]
+        if len(sidecars) != 1:
+            raise OpenError(NO_DEMO)
+        info = parse_sidecar((self.demo.folder / sidecars[0]).read_text(encoding="utf-8"))[
+            0].header.video
+        files = {n: (self.demo.folder / n).read_bytes() for n in names if _belongs(info.name, n)}
+        return self._opened(info.name, info.size, info.quick_sha256,
+                            self.demo.url + quote(info.name),
+                            _handed(info.name, files, names, OpenError))
+
+    def _opened(self, name: str, size: int, quick_sha256: str, url: str,
+                handed: dict[str, bytes]) -> Episode:
         if naming.sidecar_name(name) not in handed:
             raise OpenError(NO_SUBTITLES)
         with _staging(handed) as stage:
```
```diff
diff --git a/src/vid2sub/web/server.py b/src/vid2sub/web/server.py
index e67b5df..832831d 100644
--- a/src/vid2sub/web/server.py
+++ b/src/vid2sub/web/server.py
@@ -15,7 +15,7 @@ stays off: nothing here calls `session.allow_reconnect`, so a tab whose engine r
 the new link instead of retrying (Review Focus 5).
 
 The editor (spec §20): each tab holds at most one open episode, in an `Editor`. Every call that
-changes it (open, edits, undo, redo, Save and picks) runs one at a time, in the order the tab sent
+changes it (open, the Pages editor's demo, edits, undo, redo, Save and picks) runs one at a time, in the order the tab sent
 them, in a task of the tab's own that holds no reactive lock while it waits on the disk or ffmpeg,
 so a slow open never freezes another tab and no edit is lost to a Save running at the same time.
 The backend returns a new frozen `Episode` each time, which the editor sets as the reactive value
@@ -106,6 +106,7 @@ CUE_ID = re.compile(r"c[0-9a-f]{8}")  # model.new_cue_id's ids, as ops.CueId che
 MAX_IDS = 10_000  # source cues one retranslation may name: every cue of a long episode
 PICK_CUES = "pick the cues to retranslate"
 JOB_ID = re.compile(r"j[0-9a-f]{8}")  # jobs.Queue's ids
+NO_DEMO_HERE = "the demo here is vid2sub serve --demo's; this one is the Pages editor's"
 MAX_JOBS = 500  # paths one Start may queue
 TYPE_PATHS = "type each video's full path, one per line: nothing was queued"
 FINISHED = "that job had already finished"
@@ -209,6 +210,25 @@ class Editor:
             await self._set_busy(None)
             await notice(self.session, "error", str(err))
             return
+        await self._opened(ep)
+
+    async def _demo(self, request: object) -> None:
+        """The Pages editor's demo (spec §21, S50): the episode the site carries."""
+        open_demo = getattr(self.rt.backend, "open_demo", None)
+        if open_demo is None:  # the local engine's demo is a launch of its own (--demo)
+            await notice(self.session, "error", NO_DEMO_HERE)
+            return
+        await self._set_busy("opening")
+        try:
+            ep = await runtime.blocking(open_demo)
+        except OpenError as err:
+            await self._set_busy(None)
+            await notice(self.session, "error", str(err))
+            return
+        await self._opened(ep)
+
+    async def _opened(self, ep: Episode) -> None:
+        """Shows an episode just opened, with its video, and closes the one before."""
         media = await runtime.blocking(self.rt.media_for, ep)
         old, self.ep, self.media = self.ep, ep, media
         if old is not None:
@@ -526,6 +546,11 @@ def server(input: Inputs, output: Outputs, session: Session) -> None:
     def _open() -> None:
         editor.submit("open", input.open())
 
+    @reactive.effect
+    @reactive.event(input.demo)
+    def _demo() -> None:
+        editor.submit("demo", input.demo())
+
     @reactive.effect
     @reactive.event(input.playback)
     def _playback() -> None:
```

- [ ] **Step 4: The frontend.** In `frontend/src/lib/playable.ts`,
  `frontend/src/components/TopBar.tsx`, `frontend/src/components/Editor.tsx` and
  `frontend/src/App.tsx`:

```diff
diff --git a/frontend/src/lib/playable.ts b/frontend/src/lib/playable.ts
index 56eab3e..b588f5e 100644
--- a/frontend/src/lib/playable.ts
+++ b/frontend/src/lib/playable.ts
@@ -53,8 +53,10 @@ export function mediaTypes(video: Video): { container: string[]; video: string[]
 }
 
 /** Yes when the container, the picture (if there is one) and the sound each have a type the
- * browser doesn't answer "" for. */
+ * browser doesn't answer "" for. A video nothing probed (the browser editor has no ffprobe, spec
+ * §21) is left to the player's own error and picture checks. */
 export function canPlay(ask: Ask, video: Video): boolean {
+  if (video.container === "") return true;
   const types = mediaTypes(video);
   const any = (list: string[]) => list.some((t) => ask(t) !== "");
   return any(types.container) && (video.video_codec === null || any(types.video)) && any(types.audio);
```
```diff
diff --git a/frontend/src/components/TopBar.tsx b/frontend/src/components/TopBar.tsx
index 58ef2aa..b8c9ee4 100644
--- a/frontend/src/components/TopBar.tsx
+++ b/frontend/src/components/TopBar.tsx
@@ -8,6 +8,8 @@ const ENGINE: Record<Capabilities["engine"], string> = {
   local: "Local engine",
   browser: "Browser editor",
 };
+// The README's install section, read on GitHub (spec §21's "Install →").
+export const INSTALL_URL = "https://github.com/chendaniely/vid2sub#install";
 
 /** One endpoint in words, not colour alone: reachable or not (cloud ones are never contacted),
  * and its key by presence only (spec §19.2). */
@@ -19,7 +21,8 @@ export function endpointLabel(e: EndpointStatus): string {
 
 /** Which engine this is (from `capabilities`, not a toggle), the engine's status, the theme
  * switch, and Settings where the engine has settings (`onSettings`: the local engine's; spec
- * §19.2, §21). */
+ * §19.2, §21). The browser editor says that generating subtitles needs the local app, linking to
+ * how to install it in a new tab, so the editor itself never leaves its own files (§6.9). */
 export function TopBar({ capabilities, status, onSettings }: { capabilities?: Capabilities; status?: Status; onSettings?: () => void }) {
   return (
     <header className="flex items-center gap-4 border-b border-border bg-card px-4 py-2" data-testid="topbar">
@@ -28,6 +31,12 @@ export function TopBar({ capabilities, status, onSettings }: { capabilities?: Ca
         vid2sub
       </span>
       {capabilities && <span className="text-sm text-muted-foreground" data-testid="engine">{ENGINE[capabilities.engine]}</span>}
+      {capabilities?.engine === "browser" && (
+        <p className="text-sm" data-testid="local-app">
+          Generating subtitles needs the local app —{" "}
+          <a href={INSTALL_URL} target="_blank" rel="noopener noreferrer" className="font-bold underline">Install →</a>
+        </p>
+      )}
       {status && (
         <ul className="flex flex-wrap gap-2 text-sm" aria-label="Engine status" data-testid="status">
           {!status.ffmpeg && <li className="rounded-full bg-muted px-2 text-destructive">ffmpeg missing</li>}
```
```diff
diff --git a/frontend/src/components/Editor.tsx b/frontend/src/components/Editor.tsx
index 76de6dc..8b1e33c 100644
--- a/frontend/src/components/Editor.tsx
+++ b/frontend/src/components/Editor.tsx
@@ -37,16 +37,17 @@ export type Saving = {
   onDiscard: () => void;
 };
 
-/** The editor (spec §20): the path box, then, once an episode is open, the player on the left
- * and the cue list on the right, with the edit bar, Retranslate (where the engine has models:
- * `generate`) and find and replace. */
-export function Editor({ episode, busy, progress, pathInput, generate, onOpen, onCantPlay, requests, saving }: {
+/** The editor (spec §20): the path box, or in the browser editor the demo (`onDemo`, spec §21),
+ * then, once an episode is open, the player on the left and the cue list on the right, with the
+ * edit bar, Retranslate (where the engine has models: `generate`) and find and replace. */
+export function Editor({ episode, busy, progress, pathInput, generate, onOpen, onDemo, onCantPlay, requests, saving }: {
   episode: EpisodeView | null;
   busy: Busy;
   progress: Progress;
   pathInput: boolean;
   generate: boolean;
   onOpen: (path: string) => void;
+  onDemo: (() => void) | null;
   onCantPlay: () => void;
   requests: Requests;
   saving: Saving;
@@ -54,15 +55,29 @@ export function Editor({ episode, busy, progress, pathInput, generate, onOpen, o
   return (
     <div className="flex h-full min-h-0 flex-col gap-3 p-4" data-testid="editor">
       {pathInput && <OpenForm busy={busy} onOpen={onOpen} />}
+      {onDemo && <PagesStart busy={busy} onDemo={onDemo} />}
       {episode ? (
         <EpisodeEditor key={episode.id} episode={episode} busy={busy} progress={progress} generate={generate} requests={requests} saving={saving} onCantPlay={onCantPlay} />
       ) : (
-        <p className="m-auto text-muted-foreground">Type the full path of a video vid2sub has made subtitles for, then Open.</p>
+        pathInput && <p className="m-auto text-muted-foreground">Type the full path of a video vid2sub has made subtitles for, then Open.</p>
       )}
     </div>
   );
 }
 
+/** The browser editor's way in (spec §21): the demo, a short public-domain clip with its
+ * captions and a translation. */
+function PagesStart({ busy, onDemo }: { busy: Busy; onDemo: () => void }) {
+  return (
+    <div className="flex flex-wrap items-center gap-2" data-testid="pages-start">
+      <button type="button" className={control} onClick={onDemo} disabled={busy === "opening"} data-testid="open-demo">
+        Open the demo
+      </button>
+      <span className="text-sm text-muted-foreground">a short public-domain clip, with its captions and a translation</span>
+    </div>
+  );
+}
+
 function OpenForm({ busy, onOpen }: { busy: Busy; onOpen: (path: string) => void }) {
   const [path, setPath] = useState("");
   const submit = (e: FormEvent) => {
```
```diff
diff --git a/frontend/src/App.tsx b/frontend/src/App.tsx
index f802454..6694f65 100644
--- a/frontend/src/App.tsx
+++ b/frontend/src/App.tsx
@@ -35,6 +35,7 @@ export default function App() {
   // Every input is set from here too. Each request carries a count, so the same path asked for
   // twice is still two requests, and "event" sends it at once, never merged with the next.
   const setOpen = useSetShinyInput<{ path: string; n: number } | null>("open", null, { priority: "event", debounceMs: 0 });
+  const setDemo = useSetShinyInput<{ n: number } | null>("demo", null, { priority: "event", debounceMs: 0 });
   const setPlayback = useSetShinyInput<{ episode: string; n: number } | null>("playback", null, { priority: "event", debounceMs: 0 });
   const setEdit = useSetShinyInput<(Ask & { op: EditOp }) | null>("edit", null, { priority: "event", debounceMs: 0 });
   const setUndo = useSetShinyInput<Ask | null>("undo", null, { priority: "event", debounceMs: 0 });
@@ -256,6 +257,7 @@ export default function App() {
           pathInput={capabilities?.path_input ?? false}
           generate={generate}
           onOpen={(path) => setOpen({ path, n: ++sent.current })}
+          onDemo={capabilities?.engine === "browser" ? () => setDemo({ n: ++sent.current }) : null}
           onCantPlay={() => episode && setPlayback({ episode: episode.id, n: ++sent.current })}
           requests={requests}
           saving={saving}
```

- [ ] **Step 5: Run the checks; they pass.** `VID2SUB_REQUIRE_FFMPEG=1 uv run pytest
  tests/test_browser_backend.py tests/test_web_browser.py tests/test_web_server.py
  tests/test_pages_imports.py -q`: `68 passed`. `cd frontend && npm run typecheck && npx vitest
  run`: `Test Files  20 passed (20)`, `Tests  91 passed (91)`. Then `make check`: `1070 passed, 2
  skipped, 36 deselected` (twice), `Test Files  20 passed (20)`, `Tests  91 passed (91)`, `All
  checks passed!`, `no leaks found`; and `make e2e`: `31 passed` (the local editor's start
  screen is as it was).
- [ ] **Step 6: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(pages): 🤖 the browser editor opens the site's demo, says generating needs the local app, and plays a video nothing probed

Spec §21 and S50: the Pages editor is a working editor with no install, plus a demo clip, and a
banner says "Generating subtitles needs the local app — Install →".

- BrowserBackend(demo=Demo(folder, url)).open_demo(): the demo's sidecar and subtitles are
  bundled with the app (`folder`); its video is the one the sidecar names, with the size and
  quick hash the sidecar was made for, playing from the site's own copy (`url`, `../demo/` from
  Shinylive's app_<id>/ iframe), so the video's bytes never reach Python. The server's `demo`
  input opens it through the tab's queue as `open` does (the shared tail is Editor._opened); the
  local engine, whose demo is a launch of its own (--demo), says so.
- The frontend: in the browser editor the start screen offers "Open the demo" (`onDemo`, the
  `demo` input; the path box is the local engine's alone), and the top bar says generating
  subtitles needs the local app, with "Install →" opening the README's install section in a new
  tab (rel="noopener noreferrer"), so the editor itself never leaves its files (§6.9).
- canPlay leaves a video nothing probed (container "", as the browser editor has no ffprobe) to
  the player's own error and picture checks: asked about nothing, it said no, and the demo would
  have asked for playback audio the browser can't make.
- Tests failed first: "ImportError: cannot import name 'NO_DEMO' from 'vid2sub.web.browser'"
  and "cannot import name 'Demo'"; the top bar's "expected '<header class=…' to contain
  'Generating subtitles needs the local …'", and canPlay's "expected false to be true". The
  server test drives the `demo` input as shinyreact sends it (`demo:shinyreact.default`): the
  episode is jfk.mp4 at ../demo/jfk.mp4, source en with ja, no notes.

Docs read: Shinylive 0.10.15's shinylive.js (setupAppProxyPath: the app iframe is
app_<random>/ beside the page), shinyreact 0.1.0's useSetShinyInput, MDN on <a target="_blank">
and rel="noopener noreferrer".

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-4.md Task 2
Co-Authored-By: <the model's own line>
```

  `git add frontend/src/App.tsx frontend/src/components/Editor.tsx
  frontend/src/components/TopBar.test.ts frontend/src/components/TopBar.tsx
  frontend/src/lib/playable.test.ts frontend/src/lib/playable.ts src/vid2sub/web/browser.py
  src/vid2sub/web/server.py tests/test_browser_backend.py tests/test_web_browser.py`, `git commit
  -F .git/COMMIT_MSG`, then `git log -1 --format='%(trailers)'` shows `Plan:`.

#### Round 2b: the build

- [ ] **Step 7: The `pages` group and marker.** `uv add --group pages 'shinylive==0.8.12'`, then
  edit `pyproject.toml` to read as below (the group's comment, `dev` including it, and the
  marker), and `uv lock`:

```diff
diff --git a/pyproject.toml b/pyproject.toml
index 322a475..b28b351 100644
--- a/pyproject.toml
+++ b/pyproject.toml
@@ -43,6 +43,17 @@ dev = [
     "ruff>=0.8",
     "pytest-playwright==0.10.0",  # the editor's browser tests (spec §22.7), as recordings pins it
     "pyyaml==6.0.3",  # tests/test_brand.py reads _brand.yml, as scripts/brand_css.py does
+    # tests/test_build_pages.py checks scripts/shinylive_local.py against the Shinylive it patches
+    {include-group = "pages"},
+]
+# The Pages editor (spec §21): `make pages`, run with `uv run --group pages` (dev includes it, for
+# the tests; its assets, about 435 MB, are downloaded only by `make pages`). Pinned exactly:
+# scripts/shinylive_local.py patches one of its private functions, and the version fixes the
+# Shinylive assets it downloads (0.8.12 uses assets 0.10.15, with Pyodide 0.27.7, Python 3.12.7,
+# shiny 1.8.0 and pydantic 2.10.5). A bump changes what every visitor's browser runs, so it must
+# pass make pages-test (Phase 4 Task 2).
+pages = [
+    "shinylive==0.8.12",
 ]
 
 [build-system]
@@ -55,11 +66,12 @@ packages = ["src/vid2sub"]
 [tool.pytest.ini_options]
 testpaths = ["tests"]
 pythonpath = ["tests"]  # tests/helpers.py and tests/fakes.py are importable
-addopts = "--import-mode=importlib -m 'not live and not e2e'"
+addopts = "--import-mode=importlib -m 'not live and not e2e and not pages'"
 markers = [
     "media: needs ffmpeg and ffprobe (skipped without them unless VID2SUB_REQUIRE_FFMPEG=1)",
     "live: a real model or the Spark; opt-in, see tests/README.md",
     "e2e: Chromium against vid2sub serve; needs the built frontend (make e2e)",
+    "pages: Chromium against the built Pages site in _site/ (make pages, then make pages-test)",
 ]
 
 [tool.ruff]
```

  `uv lock` adds shinylive 0.8.12 and its dependencies (appdirs, chevron, click, future,
  lzstring) to `uv.lock`: `uv.lock | 60 ++++`.
- [ ] **Step 8: Write the failing tests,** `tests/test_build_pages.py`:

```python
"""scripts/build_pages.py, scripts/shinylive_local.py and pages/app.py, the Pages editor's build
(spec §21), without a browser, the network or Shinylive's assets. The browser tests are
tests/pages/ (`make pages`, then `make pages-test`)."""

import hashlib
import importlib.util
import io
import shutil
import tarfile
import tomllib
import zipfile
from pathlib import Path

import pytest

from vid2sub.web import runtime
from vid2sub.web.browser import BrowserRuntime

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src" / "vid2sub"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def build_pages():
    return load("build_pages", REPO / "scripts" / "build_pages.py")


@pytest.fixture(scope="module")
def shinylive_local():
    pytest.importorskip("shinylive", reason="the pages group: uv run --group pages pytest")
    return load("shinylive_local", REPO / "scripts" / "shinylive_local.py")


def built_src(tmp_path: Path) -> Path:
    """A copy of src/vid2sub with stand-ins for the built frontend, so no `make build` is needed."""
    src = tmp_path / "src" / "vid2sub"
    shutil.copytree(SRC, src, ignore=shutil.ignore_patterns("__pycache__", "ui.js", "ui.css"))
    (src / "web" / "www" / "ui.js").write_text("// stand-in bundle\n", encoding="utf-8")
    (src / "web" / "www" / "ui.css").write_text("x{src:url(/fonts/A.woff2)}", encoding="utf-8")
    return src


def a_wheel(path: Path, package: str) -> Path:
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(f"{package}/__init__.py", "")
        z.writestr(f"{package}-1.0.dist-info/METADATA", "Name: x\n")
    return path


def test_it_refuses_to_run_without_the_built_frontend(build_pages, tmp_path):
    with pytest.raises(SystemExit, match=r"ui\.js is missing.*make build"):
        build_pages.check_inputs(www=tmp_path)


def test_the_bundle_it_copies_is_the_one_the_server_is_held_to(build_pages):
    # why: tests/test_pages_imports.py proves the server imports with only what these hold; a
    # module copied but not listed there, or listed but not copied, would split the two.
    pages_imports = load("pages_imports", REPO / "tests" / "test_pages_imports.py")
    assert build_pages.BUNDLE_TREES == pages_imports.BUNDLED_TREES
    assert build_pages.BUNDLE_MODULES == pages_imports.BUNDLED_MODULES


def test_the_bundle_holds_the_browser_parts_and_nothing_local(build_pages):
    files = {p.as_posix() for p in build_pages.module_files()}
    assert {"vid2sub/__init__.py", "vid2sub/web/server.py", "vid2sub/web/browser.py",
            "vid2sub/web/folder.py", "vid2sub/store.py", "vid2sub/media/identity.py",
            "vid2sub/subs/sidecar.py", "vid2sub/parse/__init__.py",
            "vid2sub/web/www/fonts/OFL.txt",
            "vid2sub/web/static/busy/busy-indicators.js"} <= files
    assert not files & {"vid2sub/web/backend.py", "vid2sub/web/app.py", "vid2sub/web/demo.py",
                        "vid2sub/pipeline.py", "vid2sub/config.py", "vid2sub/media/probe.py",
                        "vid2sub/web/static/auth.js"}


def test_the_vendored_wheels_are_uv_locks_pure_python_ones(build_pages):
    lock = {p["name"]: p for p in tomllib.loads((REPO / "uv.lock").read_text())["package"]}
    for name in build_pages.VENDORED:
        url, digest = build_pages.locked_wheel(name)
        version = lock[name]["version"]
        assert url.endswith(f"-{version}-py3-none-any.whl") and len(digest) == 64
    assert [lock[n]["version"] for n in build_pages.VENDORED] == ["1.9.0", "1.4.4", "3.5.2"]


def test_a_wheel_whose_hash_isnt_uv_locks_is_refused_and_thrown_away(build_pages, tmp_path):
    # why: the site runs what the wheel holds in every visitor's browser (spec §21).
    wheel = a_wheel(tmp_path / "pysubs2-1.9.0-py3-none-any.whl", "pysubs2")
    good = hashlib.sha256(wheel.read_bytes()).hexdigest()
    url = "https://files.pythonhosted.org/packages/x/pysubs2-1.9.0-py3-none-any.whl"
    assert build_pages.fetch_wheel(url, good, cache=tmp_path) == wheel  # cached: no download
    with pytest.raises(SystemExit, match="SHA-256 is .*, not uv.lock's"):
        build_pages.fetch_wheel(url, "0" * 64, cache=tmp_path)
    assert not wheel.exists()


def test_a_wheel_reaching_outside_its_folder_is_refused(build_pages, tmp_path):
    wheel = tmp_path / "evil-1.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as z:
        z.writestr("../outside.py", "")
    with pytest.raises(SystemExit, match="outside itself"):
        build_pages.unpack(wheel, tmp_path / "app")
    assert not (tmp_path / "outside.py").exists()


def test_font_urls_become_relative_and_nothing_else_may_be_root_absolute(build_pages):
    css = 'a{src:url(/fonts/A.woff2)}b{src:url("/fonts/B.woff2")}c{background:url(data:x)}'
    assert build_pages.relative_font_urls(css) == (
        'a{src:url(fonts/A.woff2)}b{src:url("fonts/B.woff2")}c{background:url(data:x)}')
    with pytest.raises(SystemExit, match="url"):
        build_pages.relative_font_urls("a{src:url(/fonts/A.woff2)}b{background:url(/img/x.png)}")
    with pytest.raises(SystemExit, match="url"):
        build_pages.relative_font_urls("a{color:red}")  # the fonts moved: check, don't guess


def test_the_app_holds_the_bundle_the_vendored_packages_and_the_demo_without_its_video(
        build_pages, tmp_path):
    src = built_src(tmp_path)
    demo = tmp_path / "demo"
    shutil.copytree(REPO / "demo", demo)
    (demo / "jfk.mp4").write_bytes(b"not for the app")
    wheels = {name: a_wheel(tmp_path / f"{name}.whl", name.replace("-", "_"))
              for name in build_pages.VENDORED}
    app = tmp_path / "app"
    app.mkdir()
    build_pages.assemble(app, demo, "jfk.mp4", src=src, wheel=wheels.__getitem__)
    files = {p.relative_to(app).as_posix() for p in app.rglob("*") if p.is_file()}
    assert {"app.py", "requirements.txt", "vid2sub/web/browser.py", "vid2sub/web/www/ui.js",
            "shinyreact/__init__.py", "pysubs2/__init__.py", "opencc_purepy/__init__.py",
            "charset_normalizer/__init__.py", "demo/jfk.vid2sub.jsonl", "demo/jfk.ja.srt",
            "demo/CREDITS.md"} <= files
    assert not [f for f in files if "__pycache__" in f or f.endswith(".mp4")]
    assert "shinyreact/playwright.py" not in files and "vid2sub/web/backend.py" not in files
    assert (app / "vid2sub/web/www/ui.css").read_text() == "x{src:url(fonts/A.woff2)}"
    assert (src / "web/www/ui.css").read_text() == "x{src:url(/fonts/A.woff2)}"  # untouched


def test_a_symlink_in_the_sources_stops_the_build(build_pages, tmp_path):
    # why: copytree would follow it, and copy whatever it points at into the public site.
    secret = tmp_path / "outside.txt"
    secret.write_text("not for the site", encoding="utf-8")
    src = built_src(tmp_path)
    (src / "web" / "www" / "fonts" / "extra.woff2").symlink_to(secret)
    app = tmp_path / "app"
    app.mkdir()
    with pytest.raises(SystemExit, match=r"symlink.*extra\.woff2"):
        build_pages.assemble(app, REPO / "demo", "jfk.mp4", src=src,
                             wheel=lambda name: pytest.fail("refused before any wheel"))
    assert not any(app.iterdir())


def test_shinylives_assets_are_unpacked_only_with_the_pinned_hash(shinylive_local, tmp_path,
                                                                 monkeypatch):
    # why: Shinylive downloads its assets with no check, and they run in every visitor's browser.
    def tarball(path: Path) -> bytes:
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode="w:gz") as t:
            body = b"{}"
            info = tarfile.TarInfo(f"shinylive-{shinylive_local.ASSETS}/marker.json")
            info.size = len(body)
            t.addfile(info, io.BytesIO(body))
        path.write_bytes(data.getvalue())
        return data.getvalue()

    cached = tmp_path / f"shinylive-{shinylive_local.ASSETS}.tar.gz"
    tarball(cached)
    with pytest.raises(SystemExit, match="not the pinned"):
        shinylive_local.assets(tmp_path)
    assert not cached.exists() and not (tmp_path / f"shinylive-{shinylive_local.ASSETS}").exists()
    body = tarball(cached)
    monkeypatch.setattr(shinylive_local, "ASSETS_SHA256", hashlib.sha256(body).hexdigest())
    folder = shinylive_local.assets(tmp_path)
    assert (folder / "marker.json").read_bytes() == b"{}" and not cached.exists()


def test_pages_app_configures_the_browser_runtime_before_it_imports_the_server():
    # why: the server reads runtime.current() for each tab (spec §21; recordings' pages/app.py).
    namespace = load("pages_app", REPO / "pages" / "app.py")
    try:
        rt = runtime.current()
        assert isinstance(rt, BrowserRuntime)
        assert rt.backend.demo.url == "../demo/"
        assert rt.backend.demo.folder == REPO / "pages" / "demo"
        assert namespace.app is not None
    finally:
        runtime.configure(None)
```

  and `tests/test_rangeserver.py`, copied from recordings' `packages/ui/tests/test_rangeserver.py`
  at 8deb039 with vid2sub's prefix and Pages' caching:

```python
"""scripts/rangeserver.py: the local stand-in for GitHub Pages (`make pages-serve`, and the Pages
tests). Media seeks only if Range gets a 206, and a browser caches what it serves as it caches
Pages' files. Copied from recordings (packages/ui/tests/test_rangeserver.py at 8deb039), with the
caching test added (Phase 4 Task 2)."""

import importlib.util
import urllib.error
import urllib.request
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("site")
    spec = importlib.util.spec_from_file_location(
        "rangeserver", REPO / "scripts" / "rangeserver.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    (tmp_path / "media").mkdir()
    (tmp_path / "media" / "a.mp3").write_bytes(b"0123456789")
    (tmp_path / "index.html").write_text("<p>hi</p>", encoding="utf-8")
    server = module.serve(tmp_path, prefix="vid2sub", quiet=True)
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


def get(url: str, range_: str | None = None):
    request = urllib.request.Request(url, headers={"Range": range_} if range_ else {})
    try:
        with urllib.request.urlopen(request, timeout=5) as r:
            return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, b""


def test_a_whole_file_says_it_accepts_ranges(site):
    status, headers, body = get(f"{site}/vid2sub/media/a.mp3")
    assert (status, body) == (200, b"0123456789")
    assert headers["Accept-Ranges"] == "bytes" and headers["Content-Type"] == "audio/mpeg"


@pytest.mark.parametrize(
    ("range_", "content_range", "body"),
    [
        ("bytes=2-4", "bytes 2-4/10", b"234"),
        ("bytes=7-", "bytes 7-9/10", b"789"),
        ("bytes=-3", "bytes 7-9/10", b"789"),
        ("bytes=8-99", "bytes 8-9/10", b"89"),
    ],
)
def test_a_range_gets_206_and_just_those_bytes(site, range_, content_range, body):
    status, headers, got = get(f"{site}/vid2sub/media/a.mp3", range_)
    assert (status, headers["Content-Range"], got) == (206, content_range, body)
    assert headers["Content-Length"] == str(len(body))


def test_a_range_past_the_end_is_416(site):
    status, headers, _ = get(f"{site}/vid2sub/media/a.mp3", "bytes=10-")
    assert (status, headers["Content-Range"]) == (416, "bytes */10")


def test_only_the_prefix_is_served_like_a_project_site(site):
    assert get(f"{site}/media/a.mp3")[0] == 404  # a root-absolute URL fails, as on Pages
    assert get(f"{site}/vid2subx/media/a.mp3")[0] == 404
    assert get(f"{site}/vid2sub")[2] == b"<p>hi</p>"  # redirected to /vid2sub/
    assert get(f"{site}/vid2sub/../../etc/passwd")[0] == 404


def test_every_response_is_cached_for_ten_minutes_as_pages_caches_it(site):
    # why: the Phase 4 plan's Review Focus 3: a deploy's files stay in a visitor's cache, and
    # the Pages tests must see what a visitor would.
    status, headers, _ = get(f"{site}/vid2sub/index.html")
    assert status == 200 and headers["Cache-Control"] == "max-age=600"
    assert headers["Last-Modified"]
    status, headers, _ = get(f"{site}/vid2sub/media/a.mp3", "bytes=2-4")
    assert status == 206 and headers["Cache-Control"] == "max-age=600"
```

- [ ] **Step 9: Run them; watch them fail.** `uv run pytest tests/test_build_pages.py
  tests/test_rangeserver.py -q`. Expected: `1 failed, 18 errors`, each
  `FileNotFoundError: [Errno 2] No such file or directory: '…/scripts/build_pages.py'`, `…
  scripts/rangeserver.py'` or `… pages/app.py'`.
- [ ] **Step 10: The entry,** `pages/app.py`:

```python
"""The Pages editor's entry (spec §21): vid2sub's Shiny server on Pyodide, through Shinylive.

`make pages` copies this file to the top of the app it exports, beside the parts of vid2sub the
Pages bundle holds, shinyreact, the vendored packages and the demo's sidecar and subtitles; the
demo's video is beside the site's page, which the app reaches at ../demo/ (Shinylive runs it at
<site>/app_<id>/). As recordings' pages/app.py does, it configures the runtime, here one holding
a BrowserBackend, before it imports the server, and reads nothing of the environment: there are
no endpoints, keys or vid2sub.toml in the browser. There is no FastAPI or uvicorn here, because
Shinylive's Starlette 0.38 can't run them; Shinylive serves the Shiny app itself.
"""

# Shinylive loads Pyodide's own packages only for imports in the app directory's top-level .py
# files, and the bundled code imports this one, so it is imported here and listed in
# requirements.txt. The vendored packages (pysubs2, opencc_purepy, charset_normalizer) are
# folders beside this file, so they need no loading, and aren't listed: micropip would fetch
# them from PyPI.
from pathlib import Path

import pydantic  # noqa: F401

from vid2sub.web import runtime
from vid2sub.web.browser import BrowserBackend, Demo, browser_runtime

HERE = Path(__file__).parent
runtime.configure(browser_runtime(BrowserBackend(demo=Demo(HERE / "demo", "../demo/"))))

from vid2sub.web.server import app  # after configure(), which the server reads

__all__ = ["app"]
```

  `pages/requirements.txt`:

```text
# Pyodide's own packages the Pages editor imports, loaded from the site's copy of Shinylive's
# Pyodide (spec §21). pysubs2, opencc-purepy and charset-normalizer are vendored beside app.py
# instead, so the site never fetches from PyPI.
pydantic
```

  the page's template, `pages/site/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    {{#title}}
    <title>{{.}}</title>
    {{/title}}
    <!-- Shinylive 0.10.15's export template, with its scripts and stylesheets loaded by
         start.js, which revalidates the deploy's files first (Phase 4 Task 2). -->
    <script src="./start.js" type="module"></script>
  </head>
  <body>
    <div style="height: 100vh; width: 100vw" id="root"></div>
  </body>
</html>
```

  and `pages/site/start.js`:

```js
// Starts the Pages editor (spec §21), as Shinylive 0.10.15's export template does with its inline
// script, once the browser's cache can't mix two deploys. Pages caches every file for ten minutes
// and Shinylive fetches app.json, its own scripts and Pyodide's under names that don't change from
// one deploy to the next, so a visitor who loaded the last deploy could run its app.json, or its
// Shinylive, in this one's page (the Phase 4 plan's Review Focus 3). So each of those is asked for
// again first, "no-cache": the server answers 304 when it hasn't changed, and the cached copy the
// app then loads is this deploy's. Files whose names carry a hash or a version (Shinylive's chunks,
// Pyodide's wheels) can't be mixed. tests/test_build_pages.py checks this list against the site.
export const REVALIDATE = [
  "./app.json",
  "./shinylive/load-shinylive-sw.js",
  "./shinylive/shinylive.js",
  "./shinylive/shinylive.css",
  "./shinylive/style-resets.css",
  "./shinylive/Editor.js",
  "./shinylive/Editor.css",
  "./shinylive/pyodide-worker.js",
  "./shinylive/pyodide/pyodide.asm.js",
  "./shinylive/pyodide/pyodide.asm.wasm",
  "./shinylive/pyodide/pyodide-lock.json",
  "./shinylive/pyodide/python_stdlib.zip",
];

await Promise.all(REVALIDATE.map((url) => fetch(url, { cache: "no-cache" })));
for (const href of ["./shinylive/style-resets.css", "./shinylive/shinylive.css"]) {
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = href;
  document.head.append(link);
}
await import("./shinylive/load-shinylive-sw.js");
const { runExportedApp } = await import("./shinylive/shinylive.js");
runExportedApp({ id: "root", appEngine: "python", relPath: "" });
```

- [ ] **Step 11: The scripts,** `scripts/shinylive_local.py`:

```python
"""Runs Shinylive's CLI with its assets cached in the repository and checked against a pinned hash.

    uv run --group pages python scripts/shinylive_local.py export APPDIR DESTDIR [OPTIONS]

Copied from recordings (scripts/shinylive_local.py at 8deb039; Dan owns both), with the assets
pinned by hash (Phase 4 Task 2). Why: Shinylive keeps its web assets, about 740 MB per version
unpacked, in `appdirs.user_cache_dir("shinylive")` and has no option or environment variable to
move them (`shinylive._assets.shinylive_cache_dir()`), so this points that private function at
`.cache/shinylive/` in the repository, which is git-ignored, and runs Shinylive's own CLI; CI
caches that folder. Shinylive downloads the assets from GitHub with no check of what arrives, so
this downloads them itself first, the first time, and unpacks them only if the tarball's SHA-256
is the pinned one: what runs in every visitor's browser is fixed by version and by hash, as a
package install is (spec §21).

Because it patches a private function, it refuses any Shinylive but the pinned one: the `pages`
dependency group in pyproject.toml, `shinylive==0.8.12`, whose assets are 0.10.15 (Pyodide
0.27.7, Python 3.12.7). A Shinylive bump must re-check `_assets.py`, where every cache path goes
through `shinylive_cache_dir()`, and pin the new tarball's hash here.
"""

from __future__ import annotations

import hashlib
import json
import sys
import urllib.request
from pathlib import Path

from shinylive import __version__ as shinylive_version
from shinylive import _assets, _main, _utils
from shinylive._version import SHINYLIVE_ASSETS_VERSION

PINNED = "0.8.12"
ASSETS = "0.10.15"
# shinylive-0.10.15.tar.gz from github.com/posit-dev/shinylive's v0.10.15 release, 434,679,785
# bytes, hashed when it was pinned (2026-10-24).
ASSETS_SHA256 = "92deba97423ef2baba39df1806372af320cd6f0e751f4a36f3a7faf2645ea19b"
CACHE = Path(__file__).resolve().parents[1] / ".cache" / "shinylive"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def assets(cache: Path = CACHE, *, url: str | None = None) -> Path:
    """The pinned assets' folder in `cache`: downloaded and checked the first time, then unpacked
    with Shinylive's own safe extractor. A tarball whose hash isn't the pinned one is deleted and
    nothing is unpacked."""
    folder = cache / f"shinylive-{ASSETS}"
    if folder.is_dir():
        return folder
    cache.mkdir(parents=True, exist_ok=True)
    tarball = cache / f"shinylive-{ASSETS}.tar.gz"
    if not tarball.is_file():
        url = url or _assets.shinylive_bundle_url(ASSETS)
        print(f"shinylive_local: downloading {url}", file=sys.stderr)
        part = tarball.with_name(tarball.name + ".part")
        urllib.request.urlretrieve(url, part)
        part.replace(tarball)
    digest = sha256_of(tarball)
    if digest != ASSETS_SHA256:
        tarball.unlink()
        raise SystemExit(f"shinylive_local: the Shinylive {ASSETS} assets' SHA-256 is {digest}, "
                         f"not the pinned {ASSETS_SHA256}; nothing was unpacked")
    _utils.tar_safe_extractall(str(tarball), str(cache))
    tarball.unlink()
    return folder


def versions(folder: Path) -> dict[str, str]:
    """What the assets in `folder` run: Shinylive's, its assets', Pyodide's and Python's."""
    lock = json.loads((folder / "shinylive" / "pyodide" / "pyodide-lock.json").read_text(
        encoding="utf-8"))
    return {"shinylive": shinylive_version, "assets": ASSETS,
            "pyodide": lock["info"]["version"], "python": lock["info"]["python"]}


def main(argv: list[str] | None = None) -> None:
    if shinylive_version != PINNED or SHINYLIVE_ASSETS_VERSION != ASSETS:
        raise SystemExit(
            f"shinylive {shinylive_version} (assets {SHINYLIVE_ASSETS_VERSION}) is installed, but "
            f"this wrapper patches shinylive {PINNED}'s private cache function and pins assets "
            f"{ASSETS} by hash. Check shinylive/_assets.py, then update PINNED, ASSETS and "
            "ASSETS_SHA256.")
    _assets.shinylive_cache_dir = lambda: str(CACHE)
    assets()
    _main.main(args=sys.argv[1:] if argv is None else argv, prog_name="shinylive")


if __name__ == "__main__":
    main()
```

  `scripts/rangeserver.py`:

```python
"""A local static server that answers Range requests, to stand in for GitHub Pages.

    uv run python scripts/rangeserver.py _site --prefix /vid2sub/ --port 8008

Copied from recordings (scripts/rangeserver.py at 8deb039; Dan owns both), with Pages' caching
added (Phase 4 Task 2). Python's http.server ignores Range, so the browser can't seek media it
serves; GitHub Pages answers Range with 206. `--prefix` serves the folder under a subpath, as
Pages serves a project site (https://<user>.github.io/<repo>/), so root-absolute URLs fail here
as they would there. Every response says `Cache-Control: max-age=600`, as Pages' do, beside
http.server's own Last-Modified and If-Modified-Since, so a browser here keeps a deploy's files
for ten minutes as it would there (the Phase 4 plan's Review Focus 3). Binds 127.0.0.1 only. The
Pages tests import `serve()`.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import threading
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

_RANGE = re.compile(r"bytes=(\d*)-(\d*)")


class RangeHandler(SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler, plus a single `bytes=` range, a path prefix and Pages' caching."""

    prefix = "/"  # always ends in "/"
    quiet = False
    max_age = 600  # seconds, as GitHub Pages sends

    def translate_path(self, path: str) -> str:
        base = self.prefix.rstrip("/")
        url_path = urlsplit(path).path
        if url_path != base and not url_path.startswith(base + "/"):
            return ""  # outside the prefix: 404
        return super().translate_path(path[len(base) :] or "/")

    def send_head(self):
        path = self.translate_path(self.path)
        match = _RANGE.fullmatch((self.headers.get("Range") or "").strip())
        if not match or not os.path.isfile(path) or match.group(1) == match.group(2) == "":
            return super().send_head()
        size = os.path.getsize(path)
        if match.group(1) == "":  # the last N bytes
            start, end = max(0, size - int(match.group(2))), size - 1
        else:
            start = int(match.group(1))
            end = min(int(match.group(2)), size - 1) if match.group(2) else size - 1
        if start >= size or start > end:
            self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
            self.send_header("Content-Range", f"bytes */{size}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return None
        f = open(path, "rb")  # noqa: SIM115  (closed by the caller, as in http.server)
        f.seek(start)
        self._remaining = end - start + 1
        self.send_response(HTTPStatus.PARTIAL_CONTENT)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(self._remaining))
        self.end_headers()
        return f

    def end_headers(self) -> None:
        # Advertise ranges, and cache for ten minutes, on every response, as Pages does.
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", f"max-age={self.max_age}")
        super().end_headers()

    def copyfile(self, source, outputfile) -> None:
        remaining, self._remaining = getattr(self, "_remaining", None), None
        if remaining is None:
            return super().copyfile(source, outputfile)
        try:
            while remaining > 0 and (chunk := source.read(min(64 * 1024, remaining))):
                outputfile.write(chunk)
                remaining -= len(chunk)
        except ConnectionError:
            pass  # the browser cancelled a media request it no longer needs

    def log_message(self, format: str, *args) -> None:
        if not self.quiet:
            super().log_message(format, *args)


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address) -> None:
        # The browser drops media connections it no longer needs, mid-response; that's normal.
        if not isinstance(sys.exception(), ConnectionError):
            super().handle_error(request, client_address)


def normalize_prefix(prefix: str) -> str:
    """ "recordings", "/recordings" and "/recordings/" all mean "/recordings/"."""
    return f"/{prefix.strip('/')}/" if prefix.strip("/") else "/"


def serve(root: Path, *, prefix: str = "/", port: int = 0, quiet: bool = False,
          max_age: int = 600) -> Server:
    """Start serving `root` under `prefix` on 127.0.0.1 in a background thread.

    Port 0 picks a free port (`server.server_address[1]`). Stop with `server.shutdown()`, then
    `server.server_close()`.
    """
    prefix = normalize_prefix(prefix)
    handler = type("Handler", (RangeHandler,),
                   {"prefix": prefix, "quiet": quiet, "max_age": max_age})
    server = Server(("127.0.0.1", port), partial(handler, directory=str(root)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("root", type=Path)
    ap.add_argument("--prefix", default="/")
    ap.add_argument("--port", type=int, default=8008)
    args = ap.parse_args()
    if not args.root.is_dir():
        raise SystemExit(f"{args.root}/ does not exist; run `make pages` first")
    server = serve(args.root, prefix=args.prefix, port=args.port)
    host, port = server.server_address[:2]
    url = f"http://{host}:{port}{normalize_prefix(args.prefix)}"
    print(f"Serving {args.root}/ at {url} (Ctrl-C stops it)", flush=True)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
```

  and `scripts/build_pages.py`:

```python
"""Builds the Pages editor (spec §21) into _site/.

    make pages        # = make build, then: uv run --group pages python scripts/build_pages.py

Adapted from recordings (scripts/build_pages.py at 8deb039; Dan owns both) (Phase 4 Task 2):

1. Assemble a Shinylive app in build/pages/app/ (git-ignored): pages/app.py and
   pages/requirements.txt; the parts of vid2sub the Pages bundle holds (BUNDLE, which
   tests/test_build_pages.py holds to tests/test_pages_imports.py's list), with the built
   frontend and its fonts; shinyreact; the vendored packages, unpacked from the wheels of
   pysubs2, opencc-purepy and charset-normalizer at uv.lock's versions, each checked against
   uv.lock's SHA-256 (the site never fetches from PyPI); and the demo's sidecar and subtitles.
2. Export it with Shinylive (the `pages` group, 0.8.12) through scripts/shinylive_local.py, which
   keeps its assets (0.10.15, checked against a pinned SHA-256) in .cache/shinylive/, with
   pages/site/ as the page's template: its start.js revalidates the deploy's files before it
   starts the app (the Phase 4 plan's Review Focus 3).
3. Put the demo's video in _site/demo/, where the app plays it (../demo/<name>; the video never
   enters the app, so its bytes never reach Python), add _site/.nojekyll, and print the
   Pyodide and Shinylive versions the build used (spec §29's M4 check).

Only the demo is exported, and nothing here reads vid2sub.toml, a key or any folder of the
person's: everything in the site is public. Until Phase 4 Task 5 commits the public-domain clip,
the demo is Phase 2's (`vid2sub serve --demo`'s): `web.demo.prepare` muxes its MP4 with ffmpeg
from the committed JFK speech and names it in the sidecar's header.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
import urllib.request
import zipfile
from collections.abc import Callable
from pathlib import Path, PurePosixPath

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src" / "vid2sub"
ENTRY = REPO / "pages"
BUILD = REPO / "build" / "pages"
SITE = REPO / "_site"
WHEELS = REPO / ".cache" / "wheels"
SHINYLIVE = REPO / "scripts" / "shinylive_local.py"
TEMPLATE_PARAMS = {"title": "vid2sub"}
# What the Pages bundle holds of vid2sub: whole packages, then single modules (spec §21;
# tests/test_pages_imports.py's BUNDLED_TREES and BUNDLED_MODULES, which tests/test_build_pages.py
# holds this to).
BUNDLE_TREES = ("vid2sub.subs", "vid2sub.parse")
BUNDLE_MODULES = ("vid2sub", "vid2sub.catalog", "vid2sub.web", "vid2sub.web.server",
                  "vid2sub.web.views", "vid2sub.web.episode", "vid2sub.web.runtime",
                  "vid2sub.web.ops", "vid2sub.web.settings", "vid2sub.web.folder",
                  "vid2sub.web.browser", "vid2sub.store", "vid2sub.security", "vid2sub.media",
                  "vid2sub.media.identity")
VENDORED = ("pysubs2", "opencc-purepy", "charset-normalizer")  # at uv.lock's versions
FONT_URL = re.compile(r"""url\((["']?)/fonts/""")
ROOT_URL = re.compile(r"""url\(\s*["']?/""")
SKIP = shutil.ignore_patterns("__pycache__", "*.pyc", ".*")
# shinyreact's Playwright helpers: only its tests use them.
SHINYREACT_SKIP = shutil.ignore_patterns("__pycache__", "*.pyc", ".*", "playwright.py")


def _shown(path: Path) -> str:
    return str(path.relative_to(REPO)) if path.is_relative_to(REPO) else str(path)


def check_inputs(www: Path = SRC / "web" / "www") -> None:
    for name in ("ui.js", "ui.css"):
        if not (www / name).is_file():
            raise SystemExit(f"build_pages: {_shown(www / name)} is missing. Build the frontend "
                             "first with `make build`, or run `make pages`, which builds it.")


def module_files(src: Path = SRC) -> list[Path]:
    """The bundle's source files, relative to src/: each module, each package's __init__.py,
    each tree's every .py file, the built frontend and its fonts, and the busy indicators'
    script, which the page loads as a file (Phase 2 Decision 14)."""
    root = src.parent
    files: set[Path] = set()
    for name in BUNDLE_MODULES:
        path = root / Path(*name.split("."))
        files.add((path / "__init__.py") if path.is_dir() else path.with_suffix(".py"))
    for name in BUNDLE_TREES:
        files.update((root / Path(*name.split("."))).rglob("*.py"))
    web = src / "web"
    files.update(p for p in (web / "www").rglob("*") if p.is_file() and not p.name.startswith("."))
    files.update((web / "static" / "busy").rglob("*.js"))
    return sorted(p.relative_to(root) for p in files if "__pycache__" not in p.parts)


def locked_wheel(name: str, lock: Path = REPO / "uv.lock") -> tuple[str, str]:
    """The URL and SHA-256 of `name`'s pure-Python wheel at uv.lock's version."""
    packages = {p["name"]: p for p in tomllib.loads(lock.read_text(encoding="utf-8"))["package"]}
    wheels = [w for w in packages[name].get("wheels", []) if w["url"].endswith("-none-any.whl")]
    if len(wheels) != 1:
        raise SystemExit(f"build_pages: uv.lock has {len(wheels)} pure-Python wheels of {name}, "
                         "not one; Pyodide can't run a compiled one")
    algo, _, digest = wheels[0]["hash"].partition(":")
    assert algo == "sha256", wheels[0]["hash"]
    return wheels[0]["url"], digest


def fetch_wheel(url: str, sha256: str, cache: Path = WHEELS) -> Path:
    """The wheel at `url`, from the cache or downloaded, refused unless its SHA-256 is uv.lock's."""
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / PurePosixPath(url).name
    if not path.is_file():
        part = path.with_name(path.name + ".part")
        urllib.request.urlretrieve(url, part)
        part.replace(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != sha256:
        path.unlink()
        raise SystemExit(f"build_pages: {path.name}'s SHA-256 is {digest}, not uv.lock's {sha256}")
    return path


def unpack(wheel: Path, into: Path) -> list[str]:
    """The wheel's files, as an installer lays them out, into `into`; returns their top folders.
    A member outside `into` (an absolute path or ..) is refused."""
    tops: set[str] = set()
    with zipfile.ZipFile(wheel) as z:
        for member in z.namelist():
            parts = PurePosixPath(member).parts
            if member.startswith("/") or ".." in parts or not parts:
                raise SystemExit(f"build_pages: {wheel.name} holds a path outside itself")
            tops.add(parts[0])
        z.extractall(into)
    return sorted(tops)


def relative_font_urls(css: str) -> str:
    """Shinylive serves the app under app_<id>/, where ui.css's root-absolute /fonts/ URLs leave
    the site (spec §6.9). Relative to ui.css they resolve to www/fonts/, which page_react serves
    beside it."""
    text, n = FONT_URL.subn(r"url(\1fonts/", css)
    if n == 0 or ROOT_URL.search(text):
        raise SystemExit("build_pages: ui.css should load its fonts from url(/fonts/…) and "
                         "nothing else from the site root; check its url()s")
    return text


def refuse_symlinks(*roots: Path) -> None:
    """copytree and copy2 follow symlinks, so a link in a source could copy anything it points
    at, a sidecar of the person's or a secret, into the public site. None is expected, so none is
    allowed."""
    found = [root for root in roots if root.is_symlink()]
    for root in roots:
        if root.is_dir() and not root.is_symlink():
            for folder, dirs, files in os.walk(root):  # never enters a linked folder
                found += [Path(folder) / n for n in dirs + files if (Path(folder) / n).is_symlink()]
    if found:
        raise SystemExit("build_pages: refusing to copy a symlink into the site, which would copy "
                         "what it points at: " + ", ".join(_shown(p) for p in sorted(found)))


def demo_folder() -> tuple[Path, str]:
    """The demo's files and its video's name: a fresh copy of demo/, its MP4 muxed and named in
    its sidecar (web.demo.prepare, as `vid2sub serve --demo` makes it)."""
    from vid2sub.media.tools import Tools
    from vid2sub.web import demo

    return demo.prepare(Tools.find()), demo.VIDEO


def locked(name: str) -> Path:
    """`name`'s wheel at uv.lock's version, checked against uv.lock's hash."""
    return fetch_wheel(*locked_wheel(name))


def assemble(app: Path, demo: Path, video: str, *, src: Path = SRC,
             wheel: Callable[[str], Path] = locked) -> None:
    """The Shinylive app folder: the entry, the bundle (from `src`), shinyreact, the vendored
    packages (each `wheel(name)`, unpacked) and the demo's sidecar and subtitles, never its
    video."""
    import shinyreact

    shinyreact_dir = Path(shinyreact.__file__).parent
    refuse_symlinks(ENTRY, src, shinyreact_dir, demo)
    shutil.copy2(ENTRY / "app.py", app / "app.py")
    shutil.copy2(ENTRY / "requirements.txt", app / "requirements.txt")
    for rel in module_files(src):
        (app / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src.parent / rel, app / rel)
    shutil.copytree(shinyreact_dir, app / "shinyreact", ignore=SHINYREACT_SKIP)
    for name in VENDORED:
        unpack(wheel(name), app)
    shutil.copytree(demo, app / "demo", ignore=shutil.ignore_patterns(video, ".*", "tmp"))
    css = app / "vid2sub" / "web" / "www" / "ui.css"
    css.write_text(relative_font_urls(css.read_text(encoding="utf-8")), encoding="utf-8")


def export(app: Path) -> None:
    subprocess.run([sys.executable, str(SHINYLIVE), "export", str(app), str(SITE),
                    "--template-dir", str(ENTRY / "site"),
                    "--template-params", json.dumps(TEMPLATE_PARAMS)], check=True)


def main() -> None:
    check_inputs()
    if importlib.util.find_spec("shinylive") is None:  # before anything is deleted
        raise SystemExit("build_pages: Shinylive isn't installed here. Run `make pages`, or "
                         "`uv run --group pages python scripts/build_pages.py`.")
    sys.path.insert(0, str(SHINYLIVE.parent))
    import shinylive_local

    for old in (BUILD, SITE):  # both are build output, git-ignored
        shutil.rmtree(old, ignore_errors=True)
    app = BUILD / "app"
    app.mkdir(parents=True)
    demo, video = demo_folder()
    assemble(app, demo, video)
    export(app)
    (SITE / "demo").mkdir()
    shutil.copy2(demo / video, SITE / "demo" / video)
    # Pages deployed from an Actions artifact skips Jekyll anyway; this keeps a branch deploy
    # from hiding files whose names start with "_".
    (SITE / ".nojekyll").touch()
    v = shinylive_local.versions(shinylive_local.CACHE / f"shinylive-{shinylive_local.ASSETS}")
    size = sum(f.stat().st_size for f in SITE.rglob("*") if f.is_file())
    # Not Shinylive's suggested `python3 -m http.server`: it ignores Range, so media can't seek.
    print(f"build_pages: wrote {_shown(SITE)}/ ({size / 1e6:.1f} MB) with Shinylive "
          f"{v['shinylive']} (assets {v['assets']}), Pyodide {v['pyodide']}, Python "
          f"{v['python']}. Serve it as Pages does with `make pages-serve`.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 12: The targets.** In the `Makefile`:

```diff
diff --git a/Makefile b/Makefile
index 0418123..e10f05e 100644
--- a/Makefile
+++ b/Makefile
@@ -1,4 +1,4 @@
-.PHONY: setup build test test-utc test-js e2e demo demo-sidecar lint actionlint leaks check hooks live readme brand skills help
+.PHONY: setup build test test-utc test-js e2e pages pages-serve pages-test demo demo-sidecar lint actionlint leaks check hooks live readme brand skills help
 
 FRONTEND := frontend
 # Each recipe line runs in its own shell, so nvm is loaded per line when it is there, and switched
@@ -28,6 +28,18 @@ e2e: build ## The browser tests against vid2sub serve (installs Playwright's Chr
 	uv run playwright install chromium
 	uv run pytest -m e2e
 
+# The Pages editor (spec §21): only the demo is exported. The first build downloads Shinylive's
+# assets (about 435 MB, checked by hash) and the vendored wheels (checked against uv.lock).
+pages: build ## Build the Pages editor into _site/ (needs ffmpeg for the demo's video until Phase 4 Task 5)
+	uv run --group pages python scripts/build_pages.py
+
+pages-serve: ## Serve _site/ as GitHub Pages does: under /vid2sub/, with Range requests, on 127.0.0.1
+	uv run python scripts/rangeserver.py _site --prefix /vid2sub/ --port 8008
+
+pages-test: ## The browser tests against the built Pages site in _site/ (make pages first)
+	uv run playwright install chromium
+	uv run pytest -m pages -rs
+
 demo: build ## Serve a fresh copy of the demo episode, touching nothing else (needs ffmpeg)
 	uv run vid2sub serve --demo
 
```

  In the spec, §21 (Decision 9), replace

```markdown
  `pages/app.py` imports them at the top and lists them in `requirements.txt`.
```

  with

```markdown
  `pages/app.py` imports them at the top. `requirements.txt` lists only Pyodide's own packages
  (pydantic): Shinylive hands what it lists to micropip, which would fetch from PyPI, so the
  vendored packages are unpacked into the app folder instead.
```

- [ ] **Step 13: Run the checks; they pass, and each hash guard fails without its check.**
  `uv run pytest tests/test_build_pages.py tests/test_rangeserver.py -q`: `19 passed`. `make lint`
  covers `src` and `tests` only, so also `uv run ruff check pages scripts/build_pages.py
  scripts/shinylive_local.py scripts/rangeserver.py`: `All checks passed!`. Then, in turn, make
  `fetch_wheel`'s `if digest != sha256:` read `if False:`, and `assets()`'s `if digest !=
  ASSETS_SHA256:` read `if False:`, run `uv run pytest tests/test_build_pages.py -q` and restore
  each: `FAILED …test_a_wheel_whose_hash_isnt_uv_locks_is_refused_and_thrown_away` and `FAILED
  …test_shinylives_assets_are_unpacked_only_with_the_pinned_hash`. Then the build itself,
  `make pages`. Expected, the first time, `shinylive_local: downloading
  https://github.com/posit-dev/shinylive/releases/download/v0.10.15/shinylive-0.10.15.tar.gz`
  (435 MB), then Shinylive's own lines (`Copying base Shinylive files …`, `Copying imported
  packages …`, `Writing …/_site/app.json: 7505529 bytes` or about that) and `build_pages: wrote
  _site/ (44.0 MB) with Shinylive 0.8.12 (assets 0.10.15), Pyodide 0.27.7, Python 3.12.7. Serve
  it as Pages does with `make pages-serve`.` `ls .cache/wheels` shows the three wheels, and
  `ls _site` shows `app.json demo index.html shinylive shinylive-sw.js start.js`. Then `make
  check`: `1089 passed, 2 skipped, 40 deselected` (twice), `Test Files  20 passed (20)`, `Tests
  91 passed (91)`, `All checks passed!`, `no leaks found`.
- [ ] **Step 14: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
build(pages): 🤖 make pages builds the Pages editor into _site/, its Shinylive assets and vendored wheels pinned by hash

Spec §21 and §23.3: the editor at chendaniely.github.io/vid2sub/ is vid2sub's Shiny server on
Pyodide, through Shinylive, with no install. As recordings' Makefile has them:

- make pages builds the frontend, then scripts/build_pages.py assembles a Shinylive app in
  build/pages/app/: pages/app.py (it configures browser_runtime(BrowserBackend(demo=…)) before it
  imports the server, as recordings' pages/app.py does) and pages/requirements.txt (pydantic,
  Pyodide's own); the Pages bundle (BUNDLE_TREES and BUNDLE_MODULES, which a test holds to
  tests/test_pages_imports.py's lists) with the built frontend, its fonts made relative and the
  busy indicators' script; shinyreact without its Playwright helpers; and pysubs2 1.9.0,
  opencc-purepy 1.4.4 and charset-normalizer 3.5.2 unpacked from uv.lock's pure-Python wheels,
  each refused unless its SHA-256 is uv.lock's (charset-normalizer from PyPI, not Pyodide 0.27.7's
  3.3.2, below pyproject.toml's >=3.4). They are folders beside app.py, not lines in
  requirements.txt: Shinylive's runtime hands each requirement to micropip, which would fetch it
  from PyPI at page load (its _install_requirements_from_dir, read in shinylive.js 0.10.15), and
  app.py doesn't import charset_normalizer at its top, so Pyodide's own isn't loaded over it.
  The app runs from /home/pyodide/app_<id>/, on sys.path while app.py is imported.
- The demo: until Phase 4 Task 5 commits the public-domain clip, it is Phase 2's, made by
  web.demo.prepare (the MP4 muxed with ffmpeg from the JFK speech, named in the sidecar's
  header); its sidecar and subtitles go in the app, its video in _site/demo/, never in Python.
- scripts/shinylive_local.py (from recordings, 8deb039) runs Shinylive 0.8.12's own CLI with its
  assets in .cache/shinylive/, refusing any other Shinylive or assets version; the first time it
  downloads shinylive-0.10.15.tar.gz itself and unpacks it (with Shinylive's tar_safe_extractall)
  only if its SHA-256 is the pinned 92deba97…a19b (434,679,785 bytes, hashed 2026-10-24).
- Shinylive's template is replaced by pages/site/ (index.html and start.js, which loads the app
  as the template's inline script does, after revalidating the deploy's unhashed files: Review
  Focus 3, whose browser test is the next commit's).
- make pages prints the versions it used: "build_pages: wrote _site/ (44.0 MB) with Shinylive
  0.8.12 (assets 0.10.15), Pyodide 0.27.7, Python 3.12.7" (spec §29's M4 check).
- make pages-serve: scripts/rangeserver.py (from recordings, 8deb039) under /vid2sub/, with Range
  requests, on 127.0.0.1:8008, printing the address; it now sends Cache-Control: max-age=600 on
  every response, the ten minutes Pages is widely reported to cache for (GitHub's Pages docs give
  no caching headers; not checked against Pages here). make pages-test runs `pytest -m pages`.
- pyproject.toml: the `pages` group (shinylive==0.8.12, which dev includes so the tests have it;
  the assets download only at make pages) and the `pages` marker, deselected by default.
- Tests, no network or browser: tests/test_build_pages.py (the bundle is test_pages_imports'
  lists; nothing local is copied; uv.lock's three wheels; a wheel off uv.lock's hash refused and
  deleted; a wheel reaching outside itself refused; font URLs; a symlink stops the build; the
  assets unpacked only with the pinned hash; pages/app.py configures the browser runtime before
  the server) and tests/test_rangeserver.py (from recordings, plus Pages' caching). They failed
  first: "FileNotFoundError: … scripts/build_pages.py", "… scripts/rangeserver.py", "…
  pages/app.py" (1 failed, 18 errors). Each hash check reverted, its test fails: "FAILED
  …test_a_wheel_whose_hash_isnt_uv_locks_is_refused_and_thrown_away" and "FAILED
  …test_shinylives_assets_are_unpacked_only_with_the_pinned_hash".

Docs read: Shinylive 0.8.12's source (_export.py: --template-dir, and the template's files
copied beside index.html; _deps.py: imports in every .py copy Pyodide's packages into the site;
_assets.py: download_shinylive, shinylive_bundle_url, no hash; _app_json.py) and its 0.10.15
assets (shinylive.js's _start_app and _install_requirements_from_dir; pyodide-lock.json: Pyodide
0.27.7, Python 3.12.7, shiny 1.8.0, pydantic 2.10.5, charset-normalizer 3.3.2); uv's dependency
groups (include-group); recordings' scripts/build_pages.py, shinylive_local.py, rangeserver.py,
pages/app.py and Makefile at 8deb039.

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-4.md Task 2
Co-Authored-By: <the model's own line>
```

  `git add Makefile pyproject.toml uv.lock pages/app.py pages/requirements.txt
  pages/site/index.html pages/site/start.js scripts/build_pages.py scripts/rangeserver.py
  scripts/shinylive_local.py tests/test_build_pages.py tests/test_rangeserver.py
  docs/superpowers/specs/2026-10-14-vid2sub-design.md`, `git commit -F .git/COMMIT_MSG`, then `git
  log -1 --format='%(trailers)'` shows `Plan:`.

#### Round 2c: the site in Chromium

- [ ] **Step 15: Write the tests,** `tests/pages/test_pages_site.py`:

```python
"""The Pages editor in Chromium, on the site `make pages` builds (spec §21, §22.7; S47, S50; the
Phase 4 plan's Review Focus 3). Run with `make pages`, then `make pages-test`.

The site is served as Pages serves it (scripts/rangeserver.py): under /vid2sub/, answering Range
requests, and cached for ten minutes. Shinylive runs the app in an iframe at <site>/app_<id>/,
with Python in a Web Worker under Pyodide 0.27.7, so each test boots Pyodide from the site's own
copy; its first boot in a context takes several seconds. Each test fails on any console error.
"""

import os
import re
import shutil
import time
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import FrameLocator, Page, expect

pytestmark = pytest.mark.pages

REPO = Path(__file__).resolve().parents[2]
SITE = REPO / "_site"
PREFIX = "/vid2sub/"  # https://chendaniely.github.io/vid2sub/
BOOT = 90_000  # ms: the first visit downloads Pyodide and starts Python in the browser
RENDER = 30_000  # ms: every wait on Python's answer, slower in Pyodide than on the server
DEMO_EN = "I am delighted to be here, and I am\nparticularly delighted to be here on this"


def _rangeserver():
    import importlib.util

    spec = importlib.util.spec_from_file_location("rangeserver",
                                                  REPO / "scripts" / "rangeserver.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def served(root: Path):
    server = _rangeserver().serve(root, prefix=PREFIX, quiet=True)
    return server, f"http://127.0.0.1:{server.server_address[1]}{PREFIX}"


@pytest.fixture(scope="module")
def site_url():
    if not (SITE / "index.html").is_file():
        pytest.fail("_site/ isn't built: run make pages first")
    server, url = served(SITE)
    try:
        yield url
    finally:
        server.shutdown()
        server.server_close()


class Errors:
    """Every console error and uncaught exception the page, its frames and workers report."""

    def __init__(self, page: Page):
        self.seen: list[str] = []
        page.on("console", lambda m: m.type == "error" and self.seen.append(m.text))
        page.on("pageerror", lambda e: self.seen.append(f"uncaught: {e}"))


@pytest.fixture
def errors(page: Page) -> Errors:
    return Errors(page)


def boot(page: Page, url: str) -> FrameLocator:
    """Load the site and wait for the editor: Shinylive runs the app in an iframe."""
    page.goto(url)
    app = page.frame_locator("iframe").first
    expect(app.get_by_test_id("engine")).to_have_text("Browser editor", timeout=BOOT)
    return app


def test_the_editor_starts_in_the_browser_with_no_install(page: Page, site_url, errors, capsys):
    began = time.monotonic()
    app = boot(page, site_url)
    with capsys.disabled():
        print(f"\nPages editor: cold first load in {time.monotonic() - began:.1f} s")
    expect(app.get_by_test_id("local-app")).to_contain_text(
        "Generating subtitles needs the local app")
    expect(app.get_by_role("link", name="Install →")).to_have_attribute(
        "href", "https://github.com/chendaniely/vid2sub#install")
    expect(app.get_by_test_id("open-demo")).to_be_visible()
    # Hidden in Pages (spec §21): Jobs, the settings drawer, the path box, the engine status.
    for hidden in ("nav-jobs", "open-settings", "open-path", "status"):
        expect(app.get_by_test_id(hidden)).to_have_count(0)
    assert errors.seen == []


def test_the_demo_plays_with_its_captions_and_its_translation(page: Page, site_url, errors):
    # S50: the site's demo (Phase 2's JFK clip until Phase 4 Task 5's), its video the site's
    # own file, its sidecar and subtitles bundled with the app.
    app = boot(page, site_url)
    app.get_by_test_id("open-demo").click()
    expect(app.get_by_test_id("episode-name")).to_have_text("jfk.mp4", timeout=RENDER)
    rows = app.get_by_test_id("cue-row")
    expect(rows).to_have_count(4)
    expect(app.get_by_test_id("cue-text").first).to_have_text(DEMO_EN)
    expect(app.get_by_test_id("cue-translation").first).to_have_text(
        "ここに来られて、とてもうれしく思います。この機会に来られたことは格別の喜びです。")
    media = app.get_by_test_id("media")
    media.evaluate("m => { m.muted = true; return m.play(); }")
    frame = page.locator("iframe").first.element_handle().content_frame()
    frame.wait_for_function("() => document.querySelector('[data-testid=media]').currentTime > 0.5",
                            timeout=RENDER)
    src = urlsplit(media.evaluate("m => m.currentSrc"))
    assert src.path == f"{PREFIX}demo/jfk.mp4"  # the site's own copy
    expect(app.get_by_test_id("caption-line")).to_have_text(
        [DEMO_EN, re.compile("^ここに来られて")], timeout=RENDER)
    assert errors.seen == []


def deploy(root: Path, name: str, change) -> None:
    """A new deploy of one file: changed, and dated a minute later (If-Modified-Since is to the
    second)."""
    path = root / name
    path.write_text(change(path.read_text(encoding="utf-8")), encoding="utf-8")
    later = path.stat().st_mtime + 60
    os.utime(path, (later, later))


def test_a_new_deploy_runs_whole_though_the_browser_cached_the_last_one(page: Page, tmp_path,
                                                                        errors):
    # why: Review Focus 3: Pages caches each file for ten minutes, and Shinylive and Pyodide keep
    # their files' names from one deploy to the next, so a visitor's second visit took
    # shinylive.js, Pyodide's worker and its runtime from the cache, and only app.json afresh
    # (seen in Chromium, through Shinylive's service worker): a deploy that bumps Shinylive
    # would run the new app on the old Shinylive. start.js revalidates them first. The "deploy"
    # here changes shinylive.js and the editor's bundle in app.json after the browser has
    # cached both.
    root = tmp_path / "site"
    shutil.copytree(SITE, root)
    server, url = served(root)
    try:
        boot(page, url)
        assert page.evaluate("() => globalThis.__deploy") is None
        deploy(root, "shinylive/shinylive.js", lambda js: js + '\nglobalThis.__deploy = "next";\n')
        deploy(root, "app.json", lambda text: text.replace("Browser editor",
                                                           "Browser editor, next deploy"))
        page.goto(url)
        app = page.frame_locator("iframe").first
        expect(app.get_by_test_id("engine")).to_have_text("Browser editor, next deploy",
                                                          timeout=BOOT)
        assert page.evaluate("() => globalThis.__deploy") == "next"
    finally:
        server.shutdown()
        server.server_close()
    assert errors.seen == []


# Files whose names carry their content's hash or their version can't be mixed across deploys:
# Shinylive's chunks (an 8-character hash) and Pyodide's wheels (their versions). The page itself
# is a navigation, and start.js, the service worker and the demo's video change only with Phase 4
# Task 5 or a Shinylive bump, which re-checks this list (pages/site/start.js's header).
HASHED = re.compile(r"-[A-Z0-9]{8}\.(js|css|woff2)$|\.whl$|-\d[\w.]*\.(zip|tar)$")
# An exported app's viewer never loads Shinylive's code-URL worker or Quarto's blocks.
EXEMPT = {"index.html", "start.js", "shinylive-sw.js", ".nojekyll", "demo/jfk.mp4",
          "shinylive/lzstring-worker.js", "shinylive/run-python-blocks.js"}


def test_every_file_a_deploy_names_alike_is_revalidated_before_the_app_starts():
    if not (SITE / "index.html").is_file():
        pytest.fail("_site/ isn't built: run make pages first")
    start = (SITE / "start.js").read_text(encoding="utf-8")
    listed = set(re.findall(r'"\./([^"]+)"', start.split("];")[0]))
    named_alike = {p.relative_to(SITE).as_posix() for p in SITE.rglob("*") if p.is_file()}
    named_alike = {f for f in named_alike if not HASHED.search(f) and f not in EXEMPT
                   and not f.startswith(("shinylive/pyright/", "edit/"))}
    assert named_alike - listed == set(), "add these to pages/site/start.js's REVALIDATE"
    assert listed <= {p.relative_to(SITE).as_posix() for p in SITE.rglob("*")}
```

- [ ] **Step 16: Run them; watch the first fail.** `make pages-test`. Expected: `3 failed, 1
  passed`, each `AssertionError: assert ['Failed to l...us of 404 ()'] == []`: the page's
  busy-indicators stylesheet, `…/app_<id>/lib/shiny-busy-indicators-1.8.0+vid2sub/
  busy-indicators.css`, answered 404 (a copy of the site with the label `1.8.0.post1` serves it).
- [ ] **Step 17: The label, a post release.** In `src/vid2sub/web/server.py`:

```diff
diff --git a/src/vid2sub/web/server.py b/src/vid2sub/web/server.py
index 832831d..12deefc 100644
--- a/src/vid2sub/web/server.py
+++ b/src/vid2sub/web/server.py
@@ -111,15 +111,17 @@ MAX_JOBS = 500  # paths one Start may queue
 TYPE_PATHS = "type each video's full path, one per line: nothing was queued"
 FINISHED = "that job had already finished"
 STOPPING = "vid2sub is stopping: nothing was queued"
-# htmltools keeps the highest version of a dependency per name. Shiny's own version with a local
-# label (1.8.0+vid2sub, which PEP 440 sorts above 1.8.0) makes this one replace Shiny's
+# htmltools keeps the highest version of a dependency per name. Shiny's own version as a post
+# release (1.8.0.post1, which PEP 440 sorts above 1.8.0) makes this one replace Shiny's
 # shiny-busy-indicators: its stylesheet, without the inline script in its head. The second
 # dependency is that script, as a file. tests/test_web_server.py checks the rendered page, so a
-# Shiny or htmltools upgrade that stops this winning fails there.
+# Shiny or htmltools upgrade that stops this winning fails there. Not a local label (+vid2sub):
+# the version is in the stylesheet's path, and in Pages, Shinylive's Starlette 0.38.1 answers a
+# path with a "+" in it with 404 (Phase 4 Task 2; tests/pages/ fails on that console error).
 BUSY_INDICATORS = [
     HTMLDependency(
         "shiny-busy-indicators",
-        f"{shiny.__version__}+vid2sub",
+        f"{shiny.__version__}.post1",
         source={"package": "shiny", "subdir": "www/shared/busy-indicators"},
         stylesheet={"href": "busy-indicators.css"},
         all_files=True,
```

- [ ] **Step 18: Run them; they pass, and the deploy test fails without the revalidation.** `make
  pages` (to rebuild with the label), then `make pages-test`: `4 passed`, about 17 s, the boot
  test printing `Pages editor: cold first load in 4.1 s` or so. Then in `_site/start.js` (the
  built copy) replace the line `await Promise.all(REVALIDATE.map((url) => fetch(url, { cache:
  "no-cache" })));` with a comment, run `uv run pytest -m pages tests/pages -q -k new_deploy`,
  and copy `pages/site/start.js` back over it: `E AssertionError: assert None == 'next'`, `1
  failed`. Then `uv run pytest tests/test_web_server.py -q`: `30 passed` (the local app still
  takes the stylesheet in place of Shiny's), and `make check`: the counts of Step 13.
- [ ] **Step 19: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
test(pages): 🤖 the built site's editor starts in Chromium, plays the demo with its captions and translation, and runs a new deploy whole

Spec §21, §22.7 and S50, and the Phase 4 plan's Review Focus 3: tests/pages/test_pages_site.py
(marker `pages`, make pages-test) serves _site/ as Pages serves it (rangeserver.py: /vid2sub/,
Range, max-age=600) and fails on any console error:

- the editor starts in the browser with no install: "Browser editor", the banner that generating
  needs the local app, with its Install link, Open the demo, and no Jobs, settings, path box or
  engine status; it prints the cold first load's time (about 4 s here);
- the demo (S50, Phase 2's JFK clip until Task 5's): four cues, the Japanese beside the English,
  the video playing from the site's own /vid2sub/demo/jfk.mp4, both captions shown;
- a new deploy runs whole though the browser cached the last one: the "deploy" changes
  shinylive.js and the editor's bundle in app.json after a first visit; the second visit must run
  both. Without start.js's revalidation it fails, "assert None == 'next'": seen in Chromium, a
  second visit took shinylive.js, Pyodide's worker, pyodide.asm.js and the standard library from
  the cache, asking the server only for app.json (through Shinylive's service worker), so a
  deploy that bumps Shinylive would have run the new app on the old Shinylive;
- every file a deploy names alike is in start.js's list (Shinylive's hashed chunks and Pyodide's
  versioned wheels can't mix; Shinylive's code-URL worker and Quarto's blocks aren't loaded by an
  exported app), so a Shinylive bump that adds one fails here.

The first run found the page's busy-indicators stylesheet answered 404 in Pages: its
dependency's version, Shiny's with a local label (1.8.0+vid2sub), is in its path, and Shinylive
passes url.pathname to Starlette 0.38.1 (reqToASGI in shinylive-sw.js), which doesn't serve the
"+" path; a copy of the site with the label 1.8.0.post1 served it. server.py's label is now a
post release, which PEP 440 also sorts above 1.8.0, so it still replaces Shiny's (the local
app's tests/test_web_server.py, which checks that, passes).

make pages-test: 4 passed in 17 s.

Docs read: Playwright 1.64's frame_locator, Frame.wait_for_function and page.on("console") and
("pageerror"); Shinylive 0.10.15's shinylive-sw.js (useCaching is false: the service worker
caches nothing; reqToASGI) and load-shinylive-sw.js; the Fetch standard's `cache: "no-cache"` (a
conditional request that refreshes the HTTP cache's entry); htmltools 0.7.0's source_path_map and
Shiny 1.8.0's _register_web_dependency (the version is in the mount's path).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-4.md Task 2
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/web/server.py tests/pages/test_pages_site.py`, `git commit -F
  .git/COMMIT_MSG`, then `git log -1 --format='%(trailers)'` shows `Plan:`.
- [ ] **Step 20: Review, look forward, close.** The Tier 2 review from `$(cat .git/TASK_BASE)`
  (`AGENTS.md`, *Reviews*: Matt Pocock's `code-review`, two axes in two subagents). Worth
  checking: nothing outside `demo/` and the bundle reaches `_site/` (`find _site -type f | grep
  -v ^_site/shinylive/` lists only `app.json`, `index.html`, `start.js`, `shinylive-sw.js`,
  `.nojekyll` and `demo/`'s video), and `app.json`'s file names are the bundle's, shinyreact's,
  the vendored packages' and `demo/`'s (`python3 -c "import json; print(sorted({f['name'].split('/')[0]
  for f in json.load(open('_site/app.json'))}))"`); no request leaves `/vid2sub/` (Task 4's
  test proves it). The forward review over Tasks 3, 4, 5, 7, 10 and 11: Task 3 replaces the
  `Editor`'s `onDemo` with `pages` (a folder too), and saves the demo as downloads; Task 4 puts
  the frame refusal at the top of `pages/site/start.js` and a `Watch` on every Pages test; Task
  5 commits the clip into `demo/`, so `build_pages.demo_folder()` copies `demo/` instead of
  muxing (`make pages` then needs no ffmpeg), the tests' `jfk.mp4`, `DEMO_EN` and the Japanese
  line change, and `EXEMPT`'s `demo/jfk.mp4` follows the clip's name; Task 7's `pages.yml` runs
  `make pages` (with ffmpeg until Task 5) and `make pages-test` before uploading `_site/`,
  caches `.cache/shinylive/` by `shinylive_local.ASSETS` and `.cache/wheels/` by `uv.lock`, and
  needs Playwright's Chromium (`uv run playwright install --with-deps chromium`, as CI's e2e
  job has it); Task 10's README names `make pages`, `make pages-serve` and `make pages-test`;
  Task 11's Step 2 matches these targets. The spec's rows stay as they are: S47 is `built` once
  Tasks 3 and 4's Pages tests are in, and S50 once Task 5's clip plays (its "public-domain clip"
  isn't here yet). Then the close, its own commit, holding this plan with this task's boxes ticked
  and **Now** set to `Task 3: Opening and saving local files in the browser, open.`, with the
  message in `.git/CLOSE_MSG`:

```text
docs(plan): 🤖 close Task 2: The Pages build

Drift: none
Rulings: none
Phase-end: none
Forward: none
Tier: 2
Rounds: none
Findings: none

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-4.md Task 2
Co-Authored-By: <the model's own line>
```

  `git add docs/superpowers/plans/2026-10-23-vid2sub-phase-4.md`, `git commit -F .git/CLOSE_MSG`.

***

### Task 3: Opening and saving local files in the browser

**Tier:** 1 · **Scenarios:** S47, S48

**Why it is built this way** (read 2026-10-24):
- **The page does the I/O; Python decides.** Python runs in a Web Worker without the folder's
  handles (spec §21), so the page lists the folder and hands Python the names (`folder`); Python
  names each episode and the files to read for it (Task 1's `listing`); the page reads those,
  hashes the video's two ends as `media.identity.quick_sha256` does, makes a blob URL of the
  video for the player, and hands Python the files' bytes as base64 (`open_files`). The video's
  bytes never reach Python, and only two MiB of it are read (Review Focus 2).
- **A Save is kept only once the page has written it.** The merge (Task 1's `save` and
  `resolve`) returns the bytes to write; the server sends them (`write_files`) and waits, inside
  the tab's queue, for the page's `written` answer, so edits sent meanwhile wait their turn, as
  in the local engine. Only `ok` keeps the saved episode; anything else leaves the edits unsaved
  with their draft (Review Focus 1).
- **The re-read (spec §14.6, S47).** A Save in Chrome reads the folder's files again first. Just
  before it writes, the page reads the sidecar once more and compares its SHA-256 with the one
  the merge read (`read`); if another writer changed it, the page sends the files as they are now
  and Python merges again, up to three times.
- **All or none.** `writeAll` checks the folder's permission (asking again while the Save's
  click still counts), opens every file for writing before writing any, aborts the rest on a
  failure (the File System Access API writes to a swap file that only `close()` puts in place),
  and closes the sidecar first: a write cut short after that leaves a subtitle file holding an
  earlier version, which the next open recognises as vid2sub's own (§14.6's projection hashes).
- **No handle is kept.** The folder's handle lives in a React ref, in the tab's memory (spec
  §6.9): no IndexedDB, no localStorage, so a reload or a new tab asks for the folder again.
- **Safari and Firefox (S48), and the demo, download.** `<input webkitdirectory>` reads only, so
  the request carries no files and Save builds on the files the episode last saw (Task 1's
  `BrowserEpisode.files`); `write_files` is answered by offering each file as a download.
- **Testing the write path for real.** Playwright 1.64 can't click through
  `showDirectoryPicker`'s dialog, so the Pages tests hand the page a real directory handle
  instead: a folder in the site's origin-private file system, returned by an init script's
  `showDirectoryPicker` in every frame. The page lists, reads, hashes, plays and writes through
  the File System Access API as it does on a disk. What that can't cover: the picker's dialog,
  the permission prompt itself, a folder on a real disk moved by the Finder or on a network share,
  and Safari and Firefox themselves (S48's path runs in Chromium with `showDirectoryPicker` taken
  away, through `<input webkitdirectory>`): Task 11's exit test covers those by hand. The "the
  sidecar changed between the re-read and the write" loop runs in the server's tests, not in a
  browser: its timing can't be arranged there.

**Files:**
- Create: `frontend/src/lib/folder.ts`, `frontend/src/lib/folder.test.ts`,
  `frontend/src/components/FolderPicker.tsx`, `tests/pagesite.py`,
  `tests/pages/test_pages_files.py`
- Modify: `src/vid2sub/web/server.py` (the `folder`, `open_files` and `written` inputs; Save and
  a pick in the browser), `frontend/src/App.tsx`, `frontend/src/components/Editor.tsx` (`pages`
  in place of `onDemo`), `frontend/src/types.ts`, `tests/test_web_browser.py`,
  `tests/pages/test_pages_site.py` (its helpers move to `tests/pagesite.py`)
- Modify at the close: this plan; the spec (S48 `built`; S47 stays `planned` until Task 4's
  Pages tests are in, as its Proof names them)

**Interfaces:**
- Consumes: Task 1's `BrowserBackend` (`listing`, `open`, `save`, `resolve`, `Found`,
  `BrowserEpisode.files`) and `browser_runtime`; Task 2's site, `make pages`, `make
  pages-test`, `tests/pages/test_pages_site.py` and the demo (`demo` input).
- Produces:
  - Server inputs (the browser editor's; each refused with a fixed notice, echoing nothing):
    `folder` `{names, n}` → message `folder_listing` `{n, found: [{name, reads, problem}]}`;
    `open_files` `{video, size, quick_sha256, url, files: {name: base64}, names, n}`; `save`
    and `resolve` gain `files` (`{name: base64}` or null) and `names` (or null); message
    `write_files` `{episode, n, sidecar, read, files: [{name, data}]}`, answered by input
    `written` `{episode, n, ok, why?, files?, names?}` (`why`: `permission`, `gone`, `write`,
    or `changed` with the files as they are now). `server.MAX_FILES`, `MAX_B64`, `MAX_NAMES`,
    `WRITES = 3`, `WRITE_TIMEOUT = 300.0`, `BAD_FILES`, `KEPT_CHANGING`, `OPEN_A_FOLDER`;
    `Editor.browser`, `Editor.written(request)`.
  - `frontend/src/lib/folder.ts`: `Folder` (`name`, `writable`, `names()`, `file(name)`,
    `write(files)`), `pickFolder()`, `handleFolder(dir)`, `filesFolder(list)`, `writeAll(dir,
    files)`, `FolderError(why)`, `FAILURES`, `quickHash(blob)`, `sha256Hex(blob)`,
    `nearby(video, name)`, `toBase64`, `fromBase64`, `readFiles(folder, names)`,
    `download(files)`, `MIB`, `GLOSSARY`.
  - `FolderPicker` (`onPicked`, `onError`, `disabled`); `Editor`'s `pages` prop (`onFolder`,
    `found`, `onPick`, `onDemo`, `onError`); test ids `open-folder`, `folder-input`, `found`,
    `found-episode`.
  - `tests/pagesite.py`: `SITE`, `PREFIX`, `BOOT`, `RENDER`, `served(root)`, `built()`,
    `Errors(page)`, `boot(page, url)`, `app_frame(page)`.

The `make check` counts below come from a clone of the finished Phase 2 with only this phase's
Tasks 1 to 4; yours are higher once Phase 3 is in. What matters is no failure, ruff's
`All checks passed!` and gitleaks' `no leaks found`; the new tests' own counts are exact. Each
`diff` block applies with `git apply` from the repository's root (save it to a file first).

- [ ] **Step 0: Record the base:** `git rev-parse HEAD > .git/TASK_BASE`.

#### Round 3a: the page's folder

- [ ] **Step 1: Write the failing tests,** `frontend/src/lib/folder.test.ts`:

```ts
// @vitest-environment node
// The browser editor's folder (spec §21, §8.3; S47, S48; the Phase 4 plan's Review Focus 1 and 2):
// the quick hash is vid2sub's own, read from two MiB of any video, and a Save's files are written
// all or none. Node's environment: it has crypto.subtle, Blob and DOMException as browsers do.
import { describe, expect, it } from "vitest";

import { type DirectoryHandle, FolderError, MIB, filesFolder, fromBase64, nearby, quickHash, toBase64, writeAll } from "./folder";

/** Byte k is k % 251, as the Python side of these cases has it. */
const pattern = (n: number) => Uint8Array.from({ length: n }, (_, k) => k % 251);

describe("the quick hash (spec §8.3)", () => {
  it("is vid2sub.media.identity's quick_sha256, at every size it reads differently", async () => {
    // Each made by quick_sha256 on a file of these bytes (Phase 4 Task 3).
    const cases: [number, string][] = [
      [10, "307f156a1eb1bc5094ede355d256c9215f290a9eef01def61739b426a65a81e6"],
      [MIB, "eb8764ac9920fe59b277ed601268b00aed9a9909df8af118722b7a8c38e7d3c1"],
      [MIB + 10, "4ab92751b317702cf98aa99e77c1270b6a7e5d7f222cb78705a85a9ce4951101"],
      [3 * MIB + 7, "2c9f05e862b41b06a3ce410f4f4bb3197c652863f7f114bdf685036bcd50f266"],
    ];
    for (const [n, hash] of cases) expect(await quickHash(new Blob([pattern(n)]))).toBe(hash);
  });

  it("reads two MiB of a five-gigabyte video, and nothing else of it", async () => {
    // why: Review Focus 2: opening a multi-gigabyte video reads only what the quick hash needs.
    const size = 5_000_000_000;
    const read: [number, number][] = [];
    const video = { size, slice: (from: number, to: number) => { read.push([from, to]); return new Blob([new Uint8Array(Math.min(to, size) - from)]); } } as unknown as Blob;
    expect(await quickHash(video)).toBe("e6247268aaaff43e97b124a2fde6892aeae140da39c63a286141acd58ba9cec9");
    expect(read).toEqual([[0, MIB], [size - MIB, size]]);
  });
});

describe("which files are a video's own", () => {
  it("are its sidecar, its subtitle files and the folder's glossary, in any case", () => {
    const video = "Show - S01E01.mkv";
    for (const name of ["Show - S01E01.vid2sub.jsonl", "Show - S01E01.en.srt", "Show - S01E01.ja.ass", "show - s01e01.EN.SRT", "vid2sub.glossary.toml"]) {
      expect(nearby(video, name)).toBe(true);
    }
    for (const name of ["Show - S01E01.mkv", "Show - S01E02.en.srt", "Show - S01E01.nfo", "Show - S01E01.en.srt.bak", "notes.txt"]) {
      expect(nearby(video, name)).toBe(false);
    }
  });
});

describe("files on the wire", () => {
  it("go as base64 and come back byte for byte, past the argument limit of one call", () => {
    const bytes = pattern(200_000);
    expect(fromBase64(toBase64(bytes))).toEqual(bytes);
    expect(toBase64(new Uint8Array([0xef, 0xbb, 0xbf, 0x31]))).toBe("77u/MQ=="); // a BOM survives
  });
});

describe("a folder read through <input webkitdirectory> (Safari, Firefox)", () => {
  it("is its top level, read only", async () => {
    const at = (path: string) => Object.assign(new File(["x"], path.split("/").pop() ?? ""), { webkitRelativePath: path });
    const folder = filesFolder([at("show/a.mkv"), at("show/a.en.srt"), at("show/extras/b.mkv")]);
    expect(folder.name).toBe("show");
    expect(folder.writable).toBe(false);
    expect(await folder.names()).toEqual(["a.en.srt", "a.mkv"]);
    await expect(folder.write([{ name: "a.en.srt", data: new Uint8Array() }])).rejects.toEqual(new FolderError("permission"));
  });
});

/** A directory handle over a Map, recording what happens to each file. */
function fakeFolder({ permission = "granted", request = "granted", missing = "" }: { permission?: string; request?: string; missing?: string } = {}) {
  const files = new Map<string, Uint8Array<ArrayBuffer>>([["a.vid2sub.jsonl", new Uint8Array([1])]]);
  const log: string[] = [];
  const dir = {
    kind: "directory",
    name: "show",
    async *entries() {},
    queryPermission: async () => permission,
    requestPermission: async () => { log.push("asked"); return request; },
    async getFileHandle(name: string) {
      if (name === missing) throw new DOMException("gone", "NotFoundError");
      return {
        kind: "file",
        name,
        getFile: async () => new File([files.get(name) ?? new Uint8Array()], name),
        async createWritable() {
          let pending: Uint8Array<ArrayBuffer> | null = null;
          log.push(`open ${name}`);
          return {
            write: async (data: Uint8Array<ArrayBuffer>) => { pending = data; },
            close: async () => { if (pending) files.set(name, pending); log.push(`close ${name}`); },
            abort: async () => { log.push(`abort ${name}`); },
          };
        },
      };
    },
  } as unknown as DirectoryHandle;
  return { dir, files, log };
}

const SAVE = [
  { name: "a.vid2sub.jsonl", data: new Uint8Array([2]) },
  { name: "a.en.srt", data: new Uint8Array([3]) },
];

describe("writing a Save's files (Review Focus 1)", () => {
  it("opens every file, then puts them in place, the sidecar first", async () => {
    const { dir, files, log } = fakeFolder();
    await writeAll(dir, SAVE);
    expect(log).toEqual(["open a.vid2sub.jsonl", "open a.en.srt", "close a.vid2sub.jsonl", "close a.en.srt"]);
    expect(files.get("a.vid2sub.jsonl")).toEqual(new Uint8Array([2]));
    expect(files.get("a.en.srt")).toEqual(new Uint8Array([3]));
  });

  it("asks for the folder's permission again where it lapsed, while the click still counts", async () => {
    const { dir, log } = fakeFolder({ permission: "prompt" });
    await writeAll(dir, SAVE);
    expect(log[0]).toBe("asked");
  });

  it("writes nothing when the permission was taken back", async () => {
    // why: a revoked permission must leave the folder as it was, and say so.
    const { dir, files, log } = fakeFolder({ permission: "prompt", request: "denied" });
    await expect(writeAll(dir, SAVE)).rejects.toEqual(new FolderError("permission"));
    expect(log).toEqual(["asked"]);
    expect(files.get("a.vid2sub.jsonl")).toEqual(new Uint8Array([1]));
  });

  it("writes nothing when the folder has moved, and lets go of what it had opened", async () => {
    // why: a file of the Save missing mid-way must not leave the sidecar put in place without it.
    const { dir, files, log } = fakeFolder({ missing: "a.en.srt" });
    await expect(writeAll(dir, SAVE)).rejects.toEqual(new FolderError("gone"));
    expect(log).toEqual(["open a.vid2sub.jsonl", "abort a.vid2sub.jsonl"]);
    expect(files.get("a.vid2sub.jsonl")).toEqual(new Uint8Array([1]));
  });
});
```

- [ ] **Step 2: Run them; watch them fail.** `cd frontend && npx vitest run
  src/lib/folder.test.ts`. Expected: `Error: Cannot find module './folder' imported from
  '…/frontend/src/lib/folder.test.ts'`, `Test Files  1 failed (1)`.
- [ ] **Step 3: The folder,** `frontend/src/lib/folder.ts`:

```ts
// The folder the person picks in the browser editor (spec §21, S47, S48): its names, its files'
// bytes, the video's quick hash, and writing Save's files back, all in the page, since Python runs
// in a Web Worker without the folder's handles. As meanwhile's FolderPicker (src/viewer/media/
// folder.ts at f1279d9; Dan owns both): showDirectoryPicker where the browser has it (Chrome,
// Edge), asked for read and write, so Save writes next to the video; <input webkitdirectory>
// elsewhere (Safari, Firefox), which reads only, so Save downloads. The handle lives only in
// this tab's memory: never in IndexedDB, localStorage or anywhere else (spec §6.9), so a reload
// asks for the folder again. Video bytes never reach Python: the quick hash reads two MiB of the
// video at most (§8.3), and the player plays a blob URL of it (Phase 4 Review Focus 2).

export const MIB = 1 << 20;
export const GLOSSARY = "vid2sub.glossary.toml";

/** Why a write failed, for the person: the folder's permission was taken back, or the folder
 * isn't where it was (moved, renamed or deleted), or anything else (Review Focus 1). */
export type WriteFailure = "permission" | "gone" | "write";

export class FolderError extends Error {
  constructor(readonly why: WriteFailure) {
    super(why);
  }
}

export const FAILURES: Record<WriteFailure, string> = {
  permission: "vid2sub may no longer write to that folder, so nothing was saved: open the folder again to save your edits",
  gone: "the folder isn't where it was (moved or renamed?), so nothing was saved: open it again to save your edits",
  write: "the browser couldn't write to that folder, so nothing was saved: open it again to save your edits",
};

/** A folder the page reads, and writes where the browser lets it. */
export interface Folder {
  readonly name: string;
  readonly writable: boolean;
  names(): Promise<string[]>;
  file(name: string): Promise<File>;
  write(files: readonly Written[]): Promise<void>;
}

export type Written = { name: string; data: Uint8Array<ArrayBuffer> };

// The File System Access API's shapes, which TypeScript's DOM library leaves out (MDN).
type Permission = "granted" | "denied" | "prompt";
interface Writable { write(data: BufferSource): Promise<void>; close(): Promise<void>; abort(): Promise<void> }
interface FileHandle { kind: "file"; name: string; getFile(): Promise<File>; createWritable(): Promise<Writable> }
export interface DirectoryHandle {
  kind: "directory";
  name: string;
  entries(): AsyncIterableIterator<[string, FileHandle | DirectoryHandle]>;
  getFileHandle(name: string, options?: { create?: boolean }): Promise<FileHandle>;
  queryPermission?(descriptor: { mode: "readwrite" }): Promise<Permission>;
  requestPermission?(descriptor: { mode: "readwrite" }): Promise<Permission>;
}
type PickerWindow = typeof globalThis & {
  showDirectoryPicker?: (options?: { mode?: "read" | "readwrite" }) => Promise<DirectoryHandle>;
};

export function supportsDirectoryPicker(): boolean {
  return typeof (globalThis as PickerWindow).showDirectoryPicker === "function";
}

/** Ask for a folder, to read and write. Null when the person cancels. */
export async function pickFolder(): Promise<Folder | null> {
  const picker = (globalThis as PickerWindow).showDirectoryPicker;
  if (!picker) throw new Error("This browser can't open a folder directly.");
  try {
    return handleFolder(await picker({ mode: "readwrite" }));
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") return null;
    throw err;
  }
}

function why(err: unknown): WriteFailure {
  const name = err instanceof DOMException ? err.name : "";
  if (name === "NotAllowedError" || name === "SecurityError") return "permission";
  if (name === "NotFoundError" || name === "InvalidStateError") return "gone";
  return "write";
}

/** A folder through its directory handle (Chrome, Edge): read, and written. */
export function handleFolder(dir: DirectoryHandle): Folder {
  return {
    name: dir.name,
    writable: true,
    async names() {
      const out: string[] = [];
      try {
        for await (const [name, handle] of dir.entries()) if (handle.kind === "file") out.push(name);
      } catch (err) {
        throw new FolderError(why(err));
      }
      return out.sort();
    },
    async file(name) {
      try {
        return await (await dir.getFileHandle(name)).getFile();
      } catch (err) {
        throw new FolderError(why(err));
      }
    },
    write: (files) => writeAll(dir, files),
  };
}

/** Every file, or none: the folder's permission is checked (and asked again, while the Save's
 * click still counts), every file is opened for writing before any is written, and a failure
 * aborts the files not yet closed, whose writes the browser then throws away (createWritable
 * writes a swap file that only close() puts in place, MDN). The sidecar comes first, as Save
 * lists it, so a cut-short write leaves at most a subtitle file holding an earlier version,
 * which the next open recognises as vid2sub's own (spec §14.6). */
export async function writeAll(dir: DirectoryHandle, files: readonly Written[]): Promise<void> {
  const writables: Writable[] = [];
  try {
    let state = await dir.queryPermission?.({ mode: "readwrite" });
    if (state === "prompt") state = await dir.requestPermission?.({ mode: "readwrite" });
    if (state !== undefined && state !== "granted") throw new FolderError("permission");
    for (const f of files) writables.push(await (await dir.getFileHandle(f.name, { create: true })).createWritable());
    for (const [k, f] of files.entries()) await writables[k].write(f.data);
  } catch (err) {
    await Promise.all(writables.map((w) => w.abort().catch(() => undefined)));
    throw err instanceof FolderError ? err : new FolderError(why(err));
  }
  for (const [k, w] of writables.entries()) {
    try {
      await w.close();
    } catch (err) {
      await Promise.all(writables.slice(k + 1).map((v) => v.abort().catch(() => undefined)));
      throw new FolderError(why(err));
    }
  }
}

/** A folder through <input webkitdirectory> (Safari, Firefox): read only, its top level. */
export function filesFolder(list: FileList | readonly File[]): Folder {
  const files = new Map<string, File>();
  let name = "";
  for (const file of Array.from(list)) {
    const parts = (file.webkitRelativePath || file.name).split("/");
    if (parts.length > 2) continue; // a subfolder's: not this folder's
    name = parts.length === 2 ? parts[0] : name;
    files.set(parts[parts.length - 1], file);
  }
  return {
    name,
    writable: false,
    names: async () => [...files.keys()].sort(),
    async file(n) {
      const f = files.get(n);
      if (!f) throw new FolderError("gone");
      return f;
    },
    write: async () => {
      throw new FolderError("permission");
    },
  };
}

/** The video's quick hash (spec §8.3), as vid2sub.media.identity's quick_sha256 makes it: the
 * SHA-256 of its size as 8 big-endian bytes, its first MiB and, past one MiB, its last MiB (from
 * no earlier than one MiB in). Only those bytes are read, whatever the video's size. */
export async function quickHash(file: Blob, digest?: Digest): Promise<string> {
  const size = file.size;
  const head = new DataView(new ArrayBuffer(8));
  head.setBigUint64(0, BigInt(size));
  const parts: BlobPart[] = [head.buffer, file.slice(0, MIB)];
  if (size > MIB) {
    const from = Math.max(MIB, size - MIB);
    parts.push(file.slice(from, from + MIB));
  }
  return sha256Hex(new Blob(parts), digest);
}

type Digest = (data: ArrayBuffer) => Promise<ArrayBuffer>;

/** A file's SHA-256, as hex: the sidecar's, read again just before a Save writes (spec §14.6). */
export async function sha256Hex(blob: Blob, digest: Digest = (d) => crypto.subtle.digest("SHA-256", d)): Promise<string> {
  const hash = await digest(await blob.arrayBuffer());
  return [...new Uint8Array(hash)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

/** Whether a file might be one of the video's own (its sidecar, its subtitle files, the folder's
 * glossary): the page reads these for a Save, and Python takes the ones that are (BrowserBackend,
 * by its own rule) and refuses a Save whose folder lists one it wasn't handed. */
export function nearby(video: string, name: string): boolean {
  const dot = video.lastIndexOf(".");
  const stem = (dot > 0 ? video.slice(0, dot) : video).toLowerCase();
  const lower = name.toLowerCase();
  return lower === GLOSSARY || (lower.startsWith(`${stem}.`) && /\.(srt|ass|vid2sub\.jsonl)$/.test(lower));
}

/** Bytes as base64, in pieces small enough for String.fromCharCode's arguments. */
export function toBase64(bytes: Uint8Array): string {
  let text = "";
  for (let at = 0; at < bytes.length; at += 0x8000) text += String.fromCharCode(...bytes.subarray(at, at + 0x8000));
  return btoa(text);
}

export function fromBase64(text: string): Uint8Array<ArrayBuffer> {
  return Uint8Array.from(atob(text), (c) => c.charCodeAt(0));
}

/** Reads `names` from the folder, as base64 by name: the bytes Python takes (spec §15.2). */
export async function readFiles(folder: Folder, names: readonly string[]): Promise<Record<string, string>> {
  const out: Record<string, string> = {};
  for (const name of names) out[name] = toBase64(new Uint8Array(await (await folder.file(name)).arrayBuffer()));
  return out;
}

/** Offers each file as a download (where the browser can't write the folder: Safari, Firefox,
 * the demo), through a blob URL revoked once the click has started it. */
export function download(files: readonly Written[], doc: Document = document): void {
  for (const f of files) {
    const url = URL.createObjectURL(new Blob([f.data]));
    const a = doc.createElement("a");
    a.href = url;
    a.download = f.name;
    a.rel = "noopener";
    doc.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}
```

- [ ] **Step 4: Run them; they pass, and each write guard fails without its fix.** `npx vitest
  run src/lib/folder.test.ts`: `Tests  9 passed (9)`; `npm run typecheck`: no error. Then delete
  `writeAll`'s line `if (state !== undefined && state !== "granted") throw new
  FolderError("permission");`, run the file, and restore it: `× writing a Save's files (Review
  Focus 1) > writes nothing when the permission was taken back`; then delete the `await
  Promise.all(writables.map((w) => w.abort().catch(() => undefined)));` in its `catch`, run, and
  restore: `× … > writes nothing when the folder has moved, and lets go of what it had opened`.
  Then `make test-js`: `Test Files  21 passed (21)`, `Tests  100 passed (100)`.
- [ ] **Step 5: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(pages): 🤖 the page reads a picked folder, hashes a video from its two ends as vid2sub does, and writes a Save's files all or none

Spec §21, §8.3 and §14.6 (S47, S48), and the Phase 4 plan's Review Focus 1 and 2: Python runs in
a Web Worker without the folder's handles, so the page holds them. frontend/src/lib/folder.ts,
after meanwhile's src/viewer/media/folder.ts (f1279d9):

- pickFolder: showDirectoryPicker({mode: "readwrite"}) where the browser has it (Chrome, Edge);
  a cancel is null. handleFolder reads the folder's top-level names and files through the handle
  and writes through it; filesFolder takes <input webkitdirectory>'s files (Safari, Firefox), its
  top level, read only. The handle is only ever held in memory (spec §6.9): nothing here touches
  IndexedDB or localStorage.
- quickHash is media.identity's quick_sha256: the SHA-256 of the size as 8 big-endian bytes, the
  first MiB and, past one MiB, the last MiB from no earlier than one MiB in. The test's four
  hashes were made by quick_sha256 itself, at the sizes it reads differently; on a five-gigabyte
  video it reads [0, 1 MiB) and the last MiB, nothing else (Review Focus 2).
- writeAll: the folder's permission is checked, and asked for again if it lapsed; every file is
  opened (createWritable) before any is written; a failure aborts the files not yet closed,
  whose writes the browser then drops; the sidecar is closed first. A NotAllowedError or
  SecurityError is "permission", NotFoundError or InvalidStateError "gone" (the folder moved,
  renamed or deleted), anything else "write", each with a sentence that says nothing was saved
  and to open the folder again (FAILURES). With the permission check taken out, "writes nothing
  when the permission was taken back" fails; without the abort, "writes nothing when the folder
  has moved, and lets go of what it had opened" fails.
- nearby (the files a Save reads again: the video's sidecar, subtitle files and the glossary, in
  any case; Python takes those that are), base64 both ways (in 32 KiB pieces, a BOM kept),
  readFiles, sha256Hex, and download (a blob URL per file, revoked after the click).
- The test runs in Vitest's node environment (crypto.subtle, Blob and DOMException as browsers
  have them). It failed first: "Error: Cannot find module './folder'".

Docs read: MDN on Window.showDirectoryPicker (mode, AbortError on cancel, transient activation),
FileSystemDirectoryHandle (entries, getFileHandle with create), FileSystemFileHandle.createWritable
(writes go to a swap file that close() puts in place; abort() discards it),
FileSystemHandle.queryPermission and requestPermission (the latter needs transient activation),
HTMLInputElement.webkitdirectory and File.webkitRelativePath, SubtleCrypto.digest; meanwhile's
folder.ts and FolderPicker.tsx at f1279d9; TypeScript 5.9's Uint8Array<ArrayBuffer> for
BlobPart.

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-4.md Task 3
Co-Authored-By: <the model's own line>
```

  `git add frontend/src/lib/folder.ts frontend/src/lib/folder.test.ts`, `git commit -F
  .git/COMMIT_MSG`, then `git log -1 --format='%(trailers)'` shows `Plan:`.

#### Round 3b: the server's half

- [ ] **Step 6: Write the failing tests.** In `tests/test_web_browser.py`:

```diff
diff --git a/tests/test_web_browser.py b/tests/test_web_browser.py
index d275fa5..a041006 100644
--- a/tests/test_web_browser.py
+++ b/tests/test_web_browser.py
@@ -1,18 +1,26 @@
 """The Shiny server with the Pages editor's runtime, as Shinylive runs it: the Shiny app alone,
-with no FastAPI shell, guards or launch token (spec §21; Phase 4 Task 1).
+with no FastAPI shell, guards or launch token (spec §21; Phase 4 Tasks 1 to 3).
 
 The browser has no endpoints, ffmpeg, models or jobs, so the server offers none of them: the
 capabilities say so, and the engine status, the settings drawer and the Jobs page are explicit
-nulls (spec §19.1: a null clears a pane), never an output error, which the page would log.
+nulls (spec §19.1: a null clears a pane), never an output error, which the page would log. The
+page hands over a folder's names and an episode's files, and writes back what a Save returns,
+which is kept only once the page says so (Task 3).
 """
 
+import base64
+import hashlib
 import json
 import threading
+import time
 from pathlib import Path
 
 import pytest
+from episodes import LINES, make_episode, sid, source_cues, translation_cues, write_track
 from starlette.testclient import TestClient
 
+from vid2sub import store
+from vid2sub.media.identity import identify
 from vid2sub.web import runtime, server
 from vid2sub.web.browser import BrowserBackend, BrowserRuntime, Demo, browser_runtime
 
@@ -109,3 +117,198 @@ def test_the_demo_input_opens_the_demo_which_plays_from_the_sites_own_copy(rt):
     assert episode["video"]["url"] == "../demo/jfk.mp4"
     assert episode["source"] == "en" and [t["key"] for t in episode["tracks"]] == ["en", "ja"]
     assert episode["notes"] == []
+
+
+# ---- the page's files: a folder, opening an episode, and the write-back (Task 3) --------------
+
+URL = "blob:http://127.0.0.1:8008/4f1c2a9e-1b2c-4d3e-8f90-123456789abc"
+NAME, SIDECAR = "Show - S01E01.mkv", "Show - S01E01.vid2sub.jsonl"
+JA = "Show - S01E01.ja.srt"
+
+
+class Tab:
+    """One tab's websocket, driven by hand as the page drives it (as tests/test_web_server.py's
+    Tab): inputs go in as shinyreact sends them, and a reader thread keeps every message."""
+
+    def __init__(self, ws):
+        self.ws = ws
+        self.messages: list[dict] = []
+        threading.Thread(target=self._read, daemon=True).start()
+
+    def _read(self) -> None:
+        try:
+            while True:
+                self.messages.append(json.loads(self.ws.receive_text()))
+        except Exception:  # noqa: BLE001 - until the socket closes
+            return
+
+    def set(self, **inputs) -> None:
+        self.ws.send_text(json.dumps({"method": "update", "data": {
+            f"{name}:shinyreact.default": v for name, v in inputs.items()}}))
+
+    def until(self, check, timeout: float = 20.0):
+        deadline = time.monotonic() + timeout
+        while time.monotonic() < deadline:
+            found = check()
+            if found:
+                return found
+            time.sleep(0.02)
+        raise AssertionError(f"timed out; the tab saw {self.messages[-5:]}")
+
+    def value(self, name: str):
+        for m in reversed(self.messages):
+            if name in m.get("values", {}):
+                return m["values"][name]
+        return None
+
+    def sent(self, kind: str) -> list[dict]:
+        return [m["custom"]["shinyReactMessage"]["data"] for m in self.messages
+                if m.get("custom", {}).get("shinyReactMessage", {}).get("id") == kind]
+
+
+@pytest.fixture
+def tab(rt):
+    with TestClient(server.app) as client, client.websocket_connect("/websocket/") as ws:
+        t = Tab(ws)
+        ws.send_text(json.dumps({"method": "init", "data": {
+            f".clientdata_output_{name}_hidden": False for name in OUTPUTS}}))
+        t.until(lambda: t.value("capabilities"))
+        yield t
+
+
+def b64(data: bytes) -> str:
+    return base64.b64encode(data).decode("ascii")
+
+
+def folder_files(video: Path) -> tuple[dict[str, str], list[str]]:
+    """What the page hands over for `video`: its other files, as base64, and the folder's names."""
+    names = sorted(p.name for p in video.parent.iterdir())
+    return {p.name: b64(p.read_bytes()) for p in video.parent.iterdir() if p != video}, names
+
+
+def opened(t: Tab, video: Path) -> dict:
+    files, names = folder_files(video)
+    ident = identify(video)
+    t.set(open_files={"video": video.name, "size": ident.size, "quick_sha256": ident.quick_sha256,
+                      "url": URL, "files": files, "names": names, "n": 1})
+    return t.until(lambda: t.value("episode"))
+
+
+def edited(t: Tab, ep: dict, text: str, n: int) -> dict:
+    t.set(edit={"episode": ep["id"], "n": n, "op": {"op": "set_text", "cue": sid(0),
+                                                     "text": text}})
+    return t.until(lambda: (e := t.value("episode")) and e["rows"][0]["text"] == text and e)
+
+
+@pytest.mark.media
+def test_a_folders_names_come_back_as_its_episodes_and_the_files_to_read(tab, tmp_path):
+    video = make_episode(tmp_path / "show")
+    tab.set(folder={"names": sorted(p.name for p in video.parent.iterdir()), "n": 7})
+    listing = tab.until(lambda: tab.sent("folder_listing"))[0]
+    assert listing == {"n": 7, "found": [{"name": NAME, "reads": [
+        SIDECAR, "Show - S01E01.en.srt", JA], "problem": None}]}
+
+
+@pytest.mark.media
+def test_the_page_opens_an_episode_from_its_files_and_plays_its_blob_url(tab, tmp_path):
+    ep = opened(tab, make_episode(tmp_path / "show"))
+    assert ep["video"]["name"] == NAME and ep["video"]["url"] == URL
+    assert [r["text"] for r in ep["rows"]] == list(LINES) and ep["notes"] == []
+
+
+def test_a_typed_path_or_files_it_cant_read_are_refused_in_the_browser(tab):
+    tab.set(open={"path": "/Users/someone/Show.mkv", "n": 1})
+    tab.set(open_files={"video": NAME, "size": 1, "quick_sha256": "0" * 64, "url": URL,
+                        "files": {SIDECAR: "not base64!"}, "names": [SIDECAR], "n": 2})
+    notices = tab.until(lambda: len(tab.sent("notice")) == 2 and tab.sent("notice"))
+    assert [n["text"] for n in notices] == [server.OPEN_A_FOLDER, server.BAD_FILES]
+
+
+@pytest.mark.media
+def test_a_save_is_kept_only_once_the_page_says_its_files_are_written(tab, tmp_path):
+    # why: spec §21 and Review Focus 1: until the page has written the files, nothing is saved,
+    # so the tab's draft and its unsaved edits stay if the write fails.
+    video = make_episode(tmp_path / "show")
+    ep = edited(tab, opened(tab, video), "おはよう！", 2)
+    files, names = folder_files(video)
+    tab.set(save={"episode": ep["id"], "n": 3, "formats": ["srt"], "files": files,
+                  "names": names})
+    asked = tab.until(lambda: tab.sent("write_files"))[0]
+    assert [f["name"] for f in asked["files"]] == [SIDECAR, JA]
+    assert asked["sidecar"] == SIDECAR and asked["n"] == 3
+    assert asked["read"] == hashlib.sha256((video.parent / SIDECAR).read_bytes()).hexdigest()
+    time.sleep(0.3)
+    assert tab.value("episode")["dirty"] is True and tab.value("busy") == "saving"
+    assert tab.sent("save_result") == []
+    tab.set(written={"episode": ep["id"], "n": 3, "ok": True})
+    result = tab.until(lambda: tab.sent("save_result"))[0]
+    assert result["written"] == [JA] and tab.value("episode")["dirty"] is False
+
+
+@pytest.mark.media
+def test_a_write_the_page_couldnt_make_leaves_the_edits_unsaved(tab, tmp_path):
+    video = make_episode(tmp_path / "show")
+    ep = edited(tab, opened(tab, video), "おはよう！", 2)
+    files, names = folder_files(video)
+    tab.set(save={"episode": ep["id"], "n": 3, "formats": ["srt"], "files": files,
+                  "names": names})
+    tab.until(lambda: tab.sent("write_files"))
+    tab.set(written={"episode": ep["id"], "n": 3, "ok": False, "why": "gone"})
+    tab.until(lambda: tab.value("busy") is None)
+    assert tab.value("episode")["dirty"] is True and tab.sent("save_result") == []
+
+
+@pytest.mark.media
+def test_a_sidecar_that_changed_before_the_page_wrote_is_merged_again(tab, tmp_path):
+    # why: spec §14.6: the page re-reads the sidecar just before it writes; another writer's
+    # version since then is merged, never written over.
+    video = make_episode(tmp_path / "show")
+    ep = edited(tab, opened(tab, video), "おはよう！", 2)
+    files, names = folder_files(video)
+    tab.set(save={"episode": ep["id"], "n": 3, "formats": ["srt"], "files": files,
+                  "names": names})
+    tab.until(lambda: tab.sent("write_files"))
+    head = store.load(video)[0].head("en").rendition
+    theirs = write_track(video, "en", translation_cues(source_cues(len(LINES))),
+                         role="translation", parents=[head], replaces=head)
+    again, names = folder_files(video)
+    tab.set(written={"episode": ep["id"], "n": 3, "ok": False, "why": "changed",
+                     "files": again, "names": names})
+    second = tab.until(lambda: len(tab.sent("write_files")) == 2 and tab.sent("write_files"))[1]
+    sidecar = base64.b64decode(second["files"][0]["data"]).decode("utf-8")
+    assert theirs.id in sidecar
+    tab.set(written={"episode": ep["id"], "n": 3, "ok": True})
+    tab.until(lambda: tab.sent("save_result"))
+    assert tab.value("episode")["dirty"] is False
+
+
+@pytest.mark.media
+def test_edits_sent_while_a_save_waits_land_on_the_saved_episode(tab, tmp_path):
+    video = make_episode(tmp_path / "show")
+    ep = edited(tab, opened(tab, video), "一", 2)
+    files, names = folder_files(video)
+    tab.set(save={"episode": ep["id"], "n": 3, "formats": ["srt"], "files": files,
+                  "names": names})
+    tab.until(lambda: tab.sent("write_files"))
+    tab.set(edit={"episode": ep["id"], "n": 4, "op": {"op": "set_text", "cue": sid(1),
+                                                       "text": "二"}})
+    time.sleep(0.3)
+    assert tab.value("episode")["rows"][1]["text"] != "二"  # it waits for the Save
+    tab.set(written={"episode": ep["id"], "n": 3, "ok": True})
+    final = tab.until(lambda: (e := tab.value("episode")) and e["rows"][1]["text"] == "二" and e)
+    assert final["rows"][0]["text"] == "一" and final["dirty"] is True and final["can_undo"]
+
+
+def test_the_demos_save_hands_back_its_files_to_download(tab):
+    tab.set(demo={"n": 1})
+    ep = tab.until(lambda: tab.value("episode"))
+    tab.set(edit={"episode": ep["id"], "n": 2, "op": {
+        "op": "set_text", "cue": ep["rows"][0]["id"], "text": "Hello."}})
+    tab.until(lambda: (e := tab.value("episode")) and e["dirty"])
+    tab.set(save={"episode": ep["id"], "n": 3, "formats": ["srt"], "files": None,
+                  "names": None})
+    asked = tab.until(lambda: tab.sent("write_files"))[0]
+    assert asked["read"] is None
+    assert [f["name"] for f in asked["files"]] == ["jfk.vid2sub.jsonl", "jfk.en.srt"]
+    tab.set(written={"episode": ep["id"], "n": 3, "ok": True})
+    tab.until(lambda: tab.sent("save_result"))
```

- [ ] **Step 7: Run them; watch them fail.** `VID2SUB_REQUIRE_FFMPEG=1 uv run pytest
  tests/test_web_browser.py -q` (slow: each failing test waits 20 s). Expected: `8 failed, 2
  passed`, the server logging `the editor's open failed: TypeError` and `the editor's save
  failed: ValueError`.
- [ ] **Step 8: The server.** In `src/vid2sub/web/server.py`:

```diff
diff --git a/src/vid2sub/web/server.py b/src/vid2sub/web/server.py
index 12deefc..3e5a06d 100644
--- a/src/vid2sub/web/server.py
+++ b/src/vid2sub/web/server.py
@@ -64,7 +64,10 @@ runs no inline script or style, and the CSP needs no `style-src` of its own.
 from __future__ import annotations
 
 import asyncio
+import base64
+import binascii
 import contextvars
+import hashlib
 import itertools
 import logging
 import os
@@ -79,6 +82,7 @@ from htmltools import HTMLDependency
 from shiny import Inputs, Outputs, Session, reactive
 from shinyreact import ReactApp, page_react, reactive_output
 
+from vid2sub.subs import naming
 from vid2sub.subs.edit import EditError
 from vid2sub.subs.glossary import GlossaryError
 from vid2sub.web import WWW, ops, runtime, views
@@ -107,6 +111,15 @@ MAX_IDS = 10_000  # source cues one retranslation may name: every cue of a long
 PICK_CUES = "pick the cues to retranslate"
 JOB_ID = re.compile(r"j[0-9a-f]{8}")  # jobs.Queue's ids
 NO_DEMO_HERE = "the demo here is vid2sub serve --demo's; this one is the Pages editor's"
+# The Pages editor's files on the wire (spec §21): each one's bytes as base64, by name.
+MAX_FILES = 64  # files one request hands over: BrowserBackend's MAX_FILES
+MAX_B64 = 4 * (64 * 2**20 + 2) // 3  # base64 characters of BrowserBackend's MAX_BYTES
+MAX_NAMES = 10_000  # file names in one folder's listing
+WRITES = 3  # times a Save merges again when the folder's sidecar changed while it was written
+WRITE_TIMEOUT = 300.0  # seconds the page has to write a Save's files, or to say why it couldn't
+BAD_FILES = "the page sent files the editor can't read: open the folder again"
+KEPT_CHANGING = "the sidecar kept changing while it was saved: nothing was saved, save again"
+OPEN_A_FOLDER = "open a folder: the browser editor reads no typed path"
 MAX_JOBS = 500  # paths one Start may queue
 TYPE_PATHS = "type each video's full path, one per line: nothing was queued"
 FINISHED = "that job had already finished"
@@ -169,6 +182,9 @@ class Editor:
         self.busy: reactive.Value[str | None] = reactive.value(None)
         self.progress: reactive.Value[dict[str, int] | None] = reactive.value(None)
         self._retranslating: object | None = None  # the running retranslation's token
+        # The Pages editor's: a Save's files wait for the page to write them (spec §21).
+        self.browser = rt.backend.capabilities().engine == "browser"
+        self._writing: tuple[object, asyncio.Future] | None = None  # (n, the page's answer)
         self._todo: deque[tuple[str, object]] = deque()
         self._worker: asyncio.Task | None = None
         self._ended = False
@@ -184,6 +200,8 @@ class Editor:
         """The tab closed: drop what waits, and close the episode once the running call ends."""
         self._ended = True
         self._todo.clear()
+        if self._writing is not None and not self._writing[1].done():
+            self._writing[1].set_result(None)  # a Save waiting on the page writes nothing
         if self._worker is None or self._worker.done():
             self._close(self.ep)
 
@@ -202,6 +220,9 @@ class Editor:
 
     async def _open(self, request: object) -> None:
         path = request.get("path") if isinstance(request, dict) else None
+        if self.browser:  # the browser editor reads no typed path, only a folder the person picks
+            await notice(self.session, "error", OPEN_A_FOLDER)
+            return
         if not isinstance(path, str) or not path.strip() or len(path) > MAX_PATH:
             await notice(self.session, "error", TYPE_A_PATH)
             return
@@ -214,6 +235,46 @@ class Editor:
             return
         await self._opened(ep)
 
+    async def _folder(self, request: object) -> None:
+        """The Pages editor's folder (spec §21): from its file names alone, each episode in it
+        and the files the page reads for it, in the `folder_listing` message."""
+        names = request.get("names") if isinstance(request, dict) else None
+        n = request.get("n") if isinstance(request, dict) else None
+        listing = getattr(self.rt.backend, "listing", None)
+        if listing is None or not isinstance(names, list) or len(names) > MAX_NAMES:
+            await notice(self.session, "error", BAD_FILES)
+            return
+        try:
+            found = listing(names)
+        except OpenError as err:
+            await notice(self.session, "error", str(err))
+            return
+        await shinyreact.send_message(self.session, "folder_listing", {
+            "n": n if type(n) is int else None,
+            "found": [{"name": f.name, "reads": list(f.reads), "problem": f.problem}
+                      for f in found]})
+
+    async def _open_files(self, request: object) -> None:
+        """Opens the episode whose files the page read from its folder (spec §21): the video's
+        name, size and quick hash (§8.3), the blob URL the page plays it from, and the other
+        files' bytes. Never the video's bytes."""
+        files = _files(request.get("files")) if isinstance(request, dict) else None
+        names = request.get("names") if isinstance(request, dict) else None
+        if not self.browser or files is None or not _names(names):
+            await notice(self.session, "error", BAD_FILES)
+            return
+        await self._set_busy("opening")
+        try:
+            ep = await runtime.blocking(
+                self.rt.backend.open, request.get("video"), size=request.get("size"),
+                quick_sha256=request.get("quick_sha256"), url=request.get("url"), files=files,
+                names=names)
+        except OpenError as err:  # each is fit to show, and echoes nothing the page sent
+            await self._set_busy(None)
+            await notice(self.session, "error", str(err))
+            return
+        await self._opened(ep)
+
     async def _demo(self, request: object) -> None:
         """The Pages editor's demo (spec §21, S50): the episode the site carries."""
         open_demo = getattr(self.rt.backend, "open_demo", None)
@@ -271,7 +332,14 @@ class Editor:
             return
         await self._set_busy("saving")
         try:
-            saved, result = await runtime.blocking(self.rt.backend.save, ep, formats=formats)
+            if self.browser:
+                done = await self._write_back(request, lambda files, names: runtime.blocking(
+                    self.rt.backend.save, ep, formats=formats, files=files, names=names))
+                if done is None:
+                    return
+                saved, result = done
+            else:
+                saved, result = await runtime.blocking(self.rt.backend.save, ep, formats=formats)
         except (SaveError, OpenError) as err:
             await self._set_busy(None)
             await notice(self.session, "error", str(err))
@@ -291,7 +359,15 @@ class Editor:
             return
         await self._set_busy("picking")
         try:
-            picked, result = await runtime.blocking(self.rt.backend.resolve, ep, track, rendition)
+            if self.browser:
+                done = await self._write_back(request, lambda files, names: runtime.blocking(
+                    self.rt.backend.resolve, ep, track, rendition, files=files, names=names))
+                if done is None:
+                    return
+                picked, result = done
+            else:
+                picked, result = await runtime.blocking(self.rt.backend.resolve, ep, track,
+                                                        rendition)
         except (SaveError, OpenError) as err:  # never echoes the track or the rendition
             await self._set_busy(None)
             await notice(self.session, "error", str(err))
@@ -300,6 +376,69 @@ class Editor:
         await self._publish(busy=None)
         await self._report("pick", picked, result)
 
+    async def _write_back(self, request: dict, act) -> tuple[Episode, SaveResult] | None:
+        """The Pages editor's Save or pick (spec §14.6, §21): `act(files, names)` merges on the
+        folder's files as the page read them (None where it can't read them again: Safari, the
+        demo), and the page writes the bytes that come back, or offers them as downloads. The
+        page reads the sidecar again just before it writes; if it changed, the page says so with
+        the files as they are now, and the merge runs again, up to WRITES times. The saved
+        episode is kept only once the page says its files are written, so a write that fails
+        leaves the edits unsaved, in the tab and its draft (Phase 4 Review Focus 1); edits sent
+        meanwhile wait their turn in this tab's queue. None when nothing was saved; the page has
+        said why."""
+        files, names = request.get("files"), request.get("names")
+        n = request.get("n")
+        for _ in range(WRITES):
+            if files is not None:
+                files = _files(files)
+                if files is None or not _names(names):
+                    await self._set_busy(None)
+                    await notice(self.session, "error", BAD_FILES)
+                    return None
+            saved, result, writes = await act(files, names)
+            if not writes:
+                return saved, result
+            sidecar = naming.sidecar_name(saved.video.name)
+            answer = await self._ask_to_write(n, saved, writes, sidecar, read=(
+                hashlib.sha256(files[sidecar]).hexdigest() if files and sidecar in files
+                else None))
+            if not isinstance(answer, dict) or answer.get("ok") is not True:
+                if isinstance(answer, dict) and answer.get("why") == "changed":
+                    files, names = answer.get("files"), answer.get("names")
+                    continue
+                if not self._ended:
+                    await self._set_busy(None)  # the page said why, in its own notice
+                return None
+            return saved, result
+        await self._set_busy(None)
+        await notice(self.session, "error", KEPT_CHANGING)
+        return None
+
+    async def _ask_to_write(self, n: object, ep: Episode, writes: dict[str, bytes], sidecar: str,
+                            read: str | None) -> object:
+        """Sends the page Save's files (`write_files`) and waits for its `written` answer."""
+        future = asyncio.get_running_loop().create_future()
+        self._writing = (n, future)
+        try:
+            await shinyreact.send_message(self.session, "write_files", {
+                "episode": ep.id, "n": n if type(n) is int else None, "sidecar": sidecar,
+                "read": read,
+                "files": [{"name": name, "data": base64.b64encode(data).decode("ascii")}
+                          for name, data in writes.items()]})
+            return await asyncio.wait_for(future, WRITE_TIMEOUT)
+        except TimeoutError:
+            return None
+        finally:
+            self._writing = None
+
+    def written(self, request: object) -> None:
+        """The page's answer to `write_files`: on the event loop, outside the tab's queue, which
+        the Save waiting for it holds."""
+        waiting = self._writing
+        if (waiting is not None and isinstance(request, dict) and request.get("n") == waiting[0]
+                and not waiting[1].done()):
+            waiting[1].set_result(request)
+
     async def _retranslate(self, request: object) -> None:
         """Retranslate (spec §13.4, §20): the source cues the request names, else (`ids` null)
         every stale or untranslated one. It blocks on the model's server, for minutes on a whole
@@ -420,6 +559,27 @@ def _full_paths(paths: object) -> bool:
                     and os.path.isabs(os.path.expanduser(p)) for p in paths))
 
 
+def _files(files: object) -> dict[str, bytes] | None:
+    """The page's files, base64 by name, as bytes; None if they aren't that, or too many or too
+    big (the backend checks the names)."""
+    if not isinstance(files, dict) or len(files) > MAX_FILES:
+        return None
+    out: dict[str, bytes] = {}
+    for name, data in files.items():
+        if not isinstance(name, str) or not isinstance(data, str) or len(data) > MAX_B64:
+            return None
+        try:
+            out[name] = base64.b64decode(data, validate=True)
+        except (binascii.Error, ValueError):
+            return None
+    return out
+
+
+def _names(names: object) -> bool:
+    return (isinstance(names, list) and len(names) <= MAX_NAMES
+            and all(isinstance(n, str) for n in names))
+
+
 def _cue_ids(ids: object) -> bool:
     """None (every stale or untranslated cue), or 1 to MAX_IDS cue ids of new_cue_id's shape."""
     return ids is None or (isinstance(ids, list) and 0 < len(ids) <= MAX_IDS
@@ -553,6 +713,21 @@ def server(input: Inputs, output: Outputs, session: Session) -> None:
     def _demo() -> None:
         editor.submit("demo", input.demo())
 
+    @reactive.effect
+    @reactive.event(input.folder)
+    def _folder() -> None:
+        editor.submit("folder", input.folder())
+
+    @reactive.effect
+    @reactive.event(input.open_files)
+    def _open_files() -> None:
+        editor.submit("open_files", input.open_files())
+
+    @reactive.effect
+    @reactive.event(input.written)
+    def _written() -> None:
+        editor.written(as_json(input.written()))
+
     @reactive.effect
     @reactive.event(input.playback)
     def _playback() -> None:
```

- [ ] **Step 9: Run the checks; they pass, and each guard fails without its fix.**
  `VID2SUB_REQUIRE_FFMPEG=1 uv run pytest tests/test_web_browser.py tests/test_web_server.py
  tests/test_pages_imports.py -q`: `47 passed`. Then, in turn: make `_ask_to_write`'s `return
  await asyncio.wait_for(future, WRITE_TIMEOUT)` read `return {"ok": True}` (the page's answer
  taken as yes): `FAILED …test_a_save_is_kept_only_once_the_page_says_its_files_are_written` and
  `FAILED …test_a_write_the_page_couldnt_make_leaves_the_edits_unsaved`; restore it, and make
  `if isinstance(answer, dict) and answer.get("why") == "changed":` read `if False:`: `FAILED
  …test_a_sidecar_that_changed_before_the_page_wrote_is_merged_again`; restore it. Then `make
  check`: `1097 passed, 2 skipped, 40 deselected` (twice), `Test Files  21 passed (21)`, `Tests
  100 passed (100)`, `All checks passed!`, `no leaks found`.
- [ ] **Step 10: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(web): 🤖 the browser editor's server lists a folder, opens an episode from its files, and keeps a Save only once the page has written it

Spec §21 and §14.6 (S47, S48) and the Phase 4 plan's Review Focus 1: the page holds the folder,
so its requests carry names and bytes, and its writes come back as an answer.

- `folder` {names, n}: BrowserBackend.listing, answered in the `folder_listing` message (each
  episode, the files to read, or why it can't open).
- `open_files` {video, size, quick_sha256, url, files, names, n}: each file's bytes as base64
  (at most 64 files, each at most BrowserBackend's 64 MiB), decoded strictly and handed to
  BrowserBackend.open with the page's quick hash and blob URL. Never the video's bytes. A typed
  `open` path is refused in the browser ("open a folder: the browser editor reads no typed
  path"), and files it can't read too ("the page sent files the editor can't read: open the
  folder again"), echoing nothing.
- Save and a pick, in the browser: the request carries the folder's files read again, or none
  (Safari's read-only folder, the demo). The backend's merge returns the bytes to write; the
  server sends them in `write_files` (sidecar first, and `read`, the SHA-256 of the sidecar the
  merge read), and waits, inside the tab's queue, for the page's `written` answer, which goes
  straight to the waiting Save, outside the queue. Only `ok` keeps the saved episode and reports
  what was written; any other answer leaves the episode as it was, unsaved, with its draft, and
  the page says why. `why: "changed"` (the page found the sidecar changed since it was read)
  carries the folder's files as they are now, and the merge runs again, up to three times, then
  "the sidecar kept changing while it was saved: nothing was saved, save again". Edits sent
  while a Save waits are applied after it, as in the local engine. A closed tab, or no answer in
  five minutes, saves nothing.
- tests/test_web_browser.py drives a tab as the page does. They failed first, "8 failed, 2
  passed", the server logging "the editor's save failed: ValueError" and "the editor's open
  failed: TypeError". With the wait taken out (the page's answer taken as yes), "kept only once
  the page says its files are written" and "a write the page couldn't make leaves the edits
  unsaved" fail; with "changed" taken as a failure, "a sidecar that changed before the page
  wrote is merged again" fails.

Docs read: Shiny 1.8.0's reactive.event and session messages; Python's base64.b64decode
(validate=True raises binascii.Error on a character outside the alphabet) and
asyncio.wait_for; the Phase 2 plan's Decision 18 (the crash draft, keyed by the heads).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-4.md Task 3
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/web/server.py tests/test_web_browser.py`, `git commit -F
  .git/COMMIT_MSG`, then `git log -1 --format='%(trailers)'` shows `Plan:`.

#### Round 3c: the page's half, and the Pages tests

- [ ] **Step 11: The Pages tests' shared helpers,** `tests/pagesite.py` (moved out of
  `tests/pages/test_pages_site.py`, which now imports them):

```python
"""What the Pages browser tests share (tests/pages/; Phase 4 Tasks 2 to 4): the built site, served
as Pages serves it (scripts/rangeserver.py: under /vid2sub/, answering Range requests, cached for
ten minutes), the console errors a page reports, and booting the editor, which Shinylive runs in
an iframe at <site>/app_<id>/ with Python in a Web Worker under Pyodide 0.27.7."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from playwright.sync_api import FrameLocator, Page, expect

REPO = Path(__file__).resolve().parents[1]
SITE = REPO / "_site"
PREFIX = "/vid2sub/"  # https://chendaniely.github.io/vid2sub/
BOOT = 90_000  # ms: the first visit downloads Pyodide and starts Python in the browser
RENDER = 30_000  # ms: every wait on Python's answer, slower in Pyodide than on the server


def _rangeserver():
    spec = importlib.util.spec_from_file_location("rangeserver",
                                                  REPO / "scripts" / "rangeserver.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def served(root: Path):
    """A server for `root`, as Pages serves the site, and its address."""
    server = _rangeserver().serve(root, prefix=PREFIX, quiet=True)
    return server, f"http://127.0.0.1:{server.server_address[1]}{PREFIX}"


def built() -> None:
    if not (SITE / "index.html").is_file():
        pytest.fail("_site/ isn't built: run make pages first")


class Errors:
    """Every console error and uncaught exception the page, its frames and workers report."""

    def __init__(self, page: Page):
        self.seen: list[str] = []
        page.on("console", lambda m: m.type == "error" and self.seen.append(m.text))
        page.on("pageerror", lambda e: self.seen.append(f"uncaught: {e}"))


def boot(page: Page, url: str) -> FrameLocator:
    """Load the site and wait for the editor: Shinylive runs the app in an iframe."""
    page.goto(url)
    app = page.frame_locator("iframe").first
    expect(app.get_by_test_id("engine")).to_have_text("Browser editor", timeout=BOOT)
    return app


def app_frame(page: Page):
    """The app's frame, to run a script in it."""
    return page.locator("iframe").first.element_handle().content_frame()
```
```diff
diff --git a/tests/pages/test_pages_site.py b/tests/pages/test_pages_site.py
index 1646129..d53631d 100644
--- a/tests/pages/test_pages_site.py
+++ b/tests/pages/test_pages_site.py
@@ -1,10 +1,9 @@
 """The Pages editor in Chromium, on the site `make pages` builds (spec §21, §22.7; S47, S50; the
 Phase 4 plan's Review Focus 3). Run with `make pages`, then `make pages-test`.
 
-The site is served as Pages serves it (scripts/rangeserver.py): under /vid2sub/, answering Range
-requests, and cached for ten minutes. Shinylive runs the app in an iframe at <site>/app_<id>/,
-with Python in a Web Worker under Pyodide 0.27.7, so each test boots Pyodide from the site's own
-copy; its first boot in a context takes several seconds. Each test fails on any console error.
+The site is served as Pages serves it (tests/pagesite.py), and each test boots Pyodide from the
+site's own copy; its first boot in a context takes several seconds. Each test fails on any
+console error.
 """
 
 import os
@@ -15,37 +14,17 @@ from pathlib import Path
 from urllib.parse import urlsplit
 
 import pytest
-from playwright.sync_api import FrameLocator, Page, expect
+from pagesite import BOOT, PREFIX, RENDER, SITE, Errors, app_frame, boot, built, served
+from playwright.sync_api import Page, expect
 
 pytestmark = pytest.mark.pages
 
-REPO = Path(__file__).resolve().parents[2]
-SITE = REPO / "_site"
-PREFIX = "/vid2sub/"  # https://chendaniely.github.io/vid2sub/
-BOOT = 90_000  # ms: the first visit downloads Pyodide and starts Python in the browser
-RENDER = 30_000  # ms: every wait on Python's answer, slower in Pyodide than on the server
 DEMO_EN = "I am delighted to be here, and I am\nparticularly delighted to be here on this"
 
 
-def _rangeserver():
-    import importlib.util
-
-    spec = importlib.util.spec_from_file_location("rangeserver",
-                                                  REPO / "scripts" / "rangeserver.py")
-    module = importlib.util.module_from_spec(spec)
-    spec.loader.exec_module(module)
-    return module
-
-
-def served(root: Path):
-    server = _rangeserver().serve(root, prefix=PREFIX, quiet=True)
-    return server, f"http://127.0.0.1:{server.server_address[1]}{PREFIX}"
-
-
 @pytest.fixture(scope="module")
 def site_url():
-    if not (SITE / "index.html").is_file():
-        pytest.fail("_site/ isn't built: run make pages first")
+    built()
     server, url = served(SITE)
     try:
         yield url
@@ -54,28 +33,11 @@ def site_url():
         server.server_close()
 
 
-class Errors:
-    """Every console error and uncaught exception the page, its frames and workers report."""
-
-    def __init__(self, page: Page):
-        self.seen: list[str] = []
-        page.on("console", lambda m: m.type == "error" and self.seen.append(m.text))
-        page.on("pageerror", lambda e: self.seen.append(f"uncaught: {e}"))
-
-
 @pytest.fixture
 def errors(page: Page) -> Errors:
     return Errors(page)
 
 
-def boot(page: Page, url: str) -> FrameLocator:
-    """Load the site and wait for the editor: Shinylive runs the app in an iframe."""
-    page.goto(url)
-    app = page.frame_locator("iframe").first
-    expect(app.get_by_test_id("engine")).to_have_text("Browser editor", timeout=BOOT)
-    return app
-
-
 def test_the_editor_starts_in_the_browser_with_no_install(page: Page, site_url, errors, capsys):
     began = time.monotonic()
     app = boot(page, site_url)
@@ -105,8 +67,7 @@ def test_the_demo_plays_with_its_captions_and_its_translation(page: Page, site_u
         "ここに来られて、とてもうれしく思います。この機会に来られたことは格別の喜びです。")
     media = app.get_by_test_id("media")
     media.evaluate("m => { m.muted = true; return m.play(); }")
-    frame = page.locator("iframe").first.element_handle().content_frame()
-    frame.wait_for_function("() => document.querySelector('[data-testid=media]').currentTime > 0.5",
+    app_frame(page).wait_for_function("() => document.querySelector('[data-testid=media]').currentTime > 0.5",
                             timeout=RENDER)
     src = urlsplit(media.evaluate("m => m.currentSrc"))
     assert src.path == f"{PREFIX}demo/jfk.mp4"  # the site's own copy
@@ -164,8 +125,7 @@ EXEMPT = {"index.html", "start.js", "shinylive-sw.js", ".nojekyll", "demo/jfk.mp
 
 
 def test_every_file_a_deploy_names_alike_is_revalidated_before_the_app_starts():
-    if not (SITE / "index.html").is_file():
-        pytest.fail("_site/ isn't built: run make pages first")
+    built()
     start = (SITE / "start.js").read_text(encoding="utf-8")
     listed = set(re.findall(r'"\./([^"]+)"', start.split("];")[0]))
     named_alike = {p.relative_to(SITE).as_posix() for p in SITE.rglob("*") if p.is_file()}
```

- [ ] **Step 12: Write the failing tests,** `tests/pages/test_pages_files.py`:

```python
"""Opening and saving a local folder in the Pages editor, in Chromium, on the built site (spec
§21, §14.6; S47, S48; the Phase 4 plan's Review Focus 1 and 2). Run with `make pages`, then
`make pages-test`.

Playwright can't click through showDirectoryPicker's dialog, so each test hands the page a real
directory handle instead: a folder in the site's origin-private file system (OPFS), filled with
the episode's files, which `window.showDirectoryPicker` returns (an init script, in every frame).
The page then lists, reads, hashes, plays and writes through the File System Access API as it
does on a person's disk. What this can't cover: the picker's dialog and the permission prompt,
a folder on a real disk (moved by the Finder, or on a network share), and Safari and Firefox
themselves; S48's path runs in Chromium with showDirectoryPicker taken away, through
<input webkitdirectory>. Those are the exit test's (Task 11). The episode is Phase 2's demo
(`web.demo.prepare`: the JFK clip in VP9 and Opus, which Chromium plays), as a person's folder.
"""

import base64
import re
import shutil
from pathlib import Path

import pytest
from episodes import write_track
from pagesite import RENDER, SITE, Errors, app_frame, boot, built, served
from playwright.sync_api import FrameLocator, Page, expect

from vid2sub import store
from vid2sub.cache import Cache
from vid2sub.config import Config
from vid2sub.engines.clients import KeyRing
from vid2sub.media.tools import Tools
from vid2sub.subs.rendition import cues_from_body
from vid2sub.web import demo
from vid2sub.web.backend import LocalBackend

pytestmark = [pytest.mark.pages, pytest.mark.media]
SIDECAR, EN = "jfk.vid2sub.jsonl", "jfk.en.srt"
FIRST = "I am delighted to be here, and I am\nparticularly delighted to be here on this"
# The picker, replaced in every frame before the page's own scripts run: the folder "show" in the
# origin-private file system, behind a handle whose permission a test can take back
# (`window.top.__deny`). Every other call goes to the real handle.
PICKER = """
window.showDirectoryPicker = async () => {
  const real = await (await navigator.storage.getDirectory()).getDirectoryHandle("show");
  const state = async () => (window.top.__deny ? "denied" : "granted");
  return {
    kind: "directory", name: real.name,
    entries: () => real.entries(),
    getFileHandle: (name, options) => real.getFileHandle(name, options),
    queryPermission: state, requestPermission: state,
  };
};
"""
NO_PICKER = "Object.defineProperty(window, 'showDirectoryPicker', { value: undefined });"
FILL = """async (files) => {
  const root = await navigator.storage.getDirectory();
  await root.removeEntry("show", { recursive: true }).catch(() => undefined);
  const dir = await root.getDirectoryHandle("show", { create: true });
  for (const [name, data] of Object.entries(files)) {
    const w = await (await dir.getFileHandle(name, { create: true })).createWritable();
    await w.write(Uint8Array.from(atob(data), (c) => c.charCodeAt(0)));
    await w.close();
  }
}"""
READ = """async () => {
  const dir = await (await navigator.storage.getDirectory()).getDirectoryHandle("show");
  const out = {};
  for await (const [name, h] of dir.entries()) {
    const bytes = new Uint8Array(await (await h.getFile()).arrayBuffer());
    let text = ""; for (const b of bytes) text += String.fromCharCode(b);
    out[name] = btoa(text);
  }
  return out;
}"""


@pytest.fixture(scope="module")
def site_url():
    built()
    server, url = served(SITE)
    try:
        yield url
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture
def episode(tmp_path) -> Path:
    """A person's folder: Phase 2's demo episode, its video muxed by ffmpeg."""
    copy = demo.prepare(Tools.find())
    folder = tmp_path / "show"
    shutil.copytree(copy, folder, ignore=shutil.ignore_patterns("tmp"))
    return folder


@pytest.fixture
def errors(page: Page) -> Errors:
    return Errors(page)


def b64(folder: Path) -> dict[str, str]:
    return {p.name: base64.b64encode(p.read_bytes()).decode() for p in folder.iterdir()
            if p.is_file()}


def fill(page: Page, folder: Path) -> None:
    app_frame(page).evaluate(FILL, b64(folder))


def read_back(page: Page, into: Path) -> dict[str, bytes]:
    """The OPFS folder's files, written into `into` beside nothing else."""
    files = {n: base64.b64decode(d) for n, d in app_frame(page).evaluate(READ).items()}
    into.mkdir(exist_ok=True)
    for name, data in files.items():
        (into / name).write_bytes(data)
    return files


def open_folder(app: FrameLocator) -> None:
    app.get_by_test_id("open-folder").click()
    app.get_by_test_id("found-episode").filter(has_text="jfk.mp4").click()
    expect(app.get_by_test_id("episode-name")).to_have_text("jfk.mp4", timeout=RENDER)


def edit_cue(page: Page, app: FrameLocator, k: int, text: str) -> None:
    rows = app.get_by_test_id("cue-row")
    rows.nth(k).get_by_test_id("cue-text").click()
    page.keyboard.press("Enter")
    app.get_by_test_id("cue-editor").fill(text)
    page.keyboard.press("ControlOrMeta+Enter")
    expect(rows.nth(k).get_by_test_id("cue-text")).to_have_text(text, timeout=RENDER)


def local_open(folder: Path):
    backend = LocalBackend(Config(), Tools.find(), KeyRing(environ={}),
                           Cache(folder.parent / "cache", max_bytes=10**9))
    return backend.open(str(folder / "jfk.mp4"))


def test_a_folder_opened_in_chrome_plays_from_a_blob_url_and_saves_next_to_the_video(
        page: Page, site_url, episode, tmp_path, errors):
    # S47: picked, listed, read, hashed and played in the page; saved through File System Access.
    page.context.add_init_script(PICKER)
    app = boot(page, site_url)
    fill(page, episode)
    open_folder(app)
    media = app.get_by_test_id("media")
    expect(media).to_have_attribute("src", re.compile(r"^blob:http://127\.0\.0\.1:\d+/"))
    media.evaluate("m => { m.muted = true; return m.play(); }")
    app_frame(page).wait_for_function(
        "() => document.querySelector('[data-testid=media]').currentTime > 0.5", timeout=RENDER)
    edit_cue(page, app, 0, "I am glad to be here.")
    expect(app.get_by_test_id("save-state")).to_have_text("Unsaved changes")
    app.get_by_test_id("save").click()
    expect(app.get_by_test_id("save-state")).to_have_text("All changes saved", timeout=RENDER)
    files = read_back(page, tmp_path / "after")
    assert set(files) == {"jfk.mp4", SIDECAR, EN, "jfk.ja.srt", "CREDITS.md"}
    assert files["jfk.mp4"] == (episode / "jfk.mp4").read_bytes()  # the video is never written
    there = local_open(tmp_path / "after")
    assert there.tracks.source[0].text == "I am glad to be here."
    assert b"I am glad to be here." in files[EN]
    assert errors.seen == []


def test_save_keeps_what_another_writer_added_since_the_folder_was_read(
        page: Page, site_url, episode, tmp_path, errors):
    # S47's "the sidecar re-read first" (spec §14.6): a CLI run translates while the episode is
    # open in the page; the page's Save merges, and both versions are in the folder.
    page.context.add_init_script(PICKER)
    app = boot(page, site_url)
    fill(page, episode)
    open_folder(app)
    edit_cue(page, app, 0, "I am glad to be here.")
    other = tmp_path / "other"
    shutil.copytree(episode, other)
    head = store.load(other / "jfk.mp4")[0].head("ja").rendition
    ja = store.load(other / "jfk.mp4")[0].renditions()[head]
    theirs = write_track(other / "jfk.mp4", "ja", [c.model_copy(update={"text": c.text + "!"})
                                                   for c in cues_from_body(ja.body)],
                         role="translation", parents=[head], replaces=head)
    fill(page, other)
    app.get_by_test_id("save").click()
    expect(app.get_by_test_id("save-state")).to_have_text("All changes saved", timeout=RENDER)
    files = read_back(page, tmp_path / "after")
    side = store.load(tmp_path / "after" / "jfk.mp4")[0]
    assert theirs.id in side.renditions() and side.head("ja").rendition == theirs.id
    assert local_open(tmp_path / "after").tracks.source[0].text == "I am glad to be here."
    assert SIDECAR in files and errors.seen == []


def test_a_folder_safari_can_only_read_is_saved_as_downloads(page: Page, site_url, episode,
                                                             tmp_path, errors):
    # S48: no showDirectoryPicker (Safari, Firefox): <input webkitdirectory> reads the folder,
    # and Save offers the sidecar and the subtitle files it wrote as downloads.
    page.context.add_init_script(NO_PICKER)
    app = boot(page, site_url)
    with page.expect_file_chooser() as chooser:
        app.get_by_test_id("open-folder").click()
    chooser.value.set_files(str(episode))
    app.get_by_test_id("found-episode").filter(has_text="jfk.mp4").click()
    expect(app.get_by_test_id("episode-name")).to_have_text("jfk.mp4", timeout=RENDER)
    edit_cue(page, app, 0, "I am glad to be here.")
    downloads = []
    page.on("download", lambda d: downloads.append(d))
    app.get_by_test_id("save").click()
    expect(app.get_by_test_id("save-state")).to_have_text("All changes saved", timeout=RENDER)
    page.wait_for_timeout(500)
    assert sorted(d.suggested_filename for d in downloads) == [EN, SIDECAR]
    for d in downloads:
        d.save_as(episode / d.suggested_filename)  # what the person does with them
    assert local_open(episode).tracks.source[0].text == "I am glad to be here."
    assert errors.seen == []


@pytest.mark.parametrize("lost", ["permission", "folder"])
def test_a_folder_lost_mid_edit_saves_nothing_says_why_and_keeps_the_edits(
        page: Page, site_url, episode, tmp_path, errors, lost):
    # why: Review Focus 1: the folder's permission taken back, or the folder moved, while an
    # episode is open: Save writes nothing half-way, says what happened and to open the folder
    # again, and the edits stay in the tab and its draft; opening it again offers the draft.
    page.context.add_init_script(PICKER)
    app = boot(page, site_url)
    fill(page, episode)
    open_folder(app)
    edit_cue(page, app, 0, "I am glad to be here.")
    before = read_back(page, tmp_path / "before")
    if lost == "permission":
        page.evaluate("() => { window.__deny = true; }")
        said = "vid2sub may no longer write to that folder, so nothing was saved"
    else:
        app_frame(page).evaluate(
            "async () => (await navigator.storage.getDirectory()).removeEntry('show', "
            "{ recursive: true })")
        said = "the folder isn't where it was (moved or renamed?), so nothing was saved"
    app.get_by_test_id("save").click()
    expect(app.get_by_test_id("notice").filter(has_text=said)).to_have_count(1, timeout=RENDER)
    expect(app.get_by_test_id("save-state")).to_have_text("Unsaved changes")
    expect(app.get_by_test_id("save")).to_be_enabled(timeout=RENDER)
    drafts = app_frame(page).evaluate(
        "() => Object.keys(localStorage).filter((k) => k.startsWith('vid2sub.draft.'))")
    assert len(drafts) == 1
    if lost == "permission":
        assert read_back(page, tmp_path / "after") == before  # nothing written half-way
        page.evaluate("() => { window.__deny = false; }")
    else:
        fill(page, episode)  # the folder is back where it was
    # A second tab, as after a crash: the draft is offered when the folder is opened again.
    again = page.context.new_page()
    seen = Errors(again)
    app = boot(again, site_url)
    open_folder(app)
    expect(app.get_by_test_id("draft")).to_be_visible(timeout=RENDER)
    app.get_by_test_id("draft-restore").click()
    expect(app.get_by_test_id("cue-text").first).to_have_text("I am glad to be here.",
                                                              timeout=RENDER)
    app.get_by_test_id("save").click()
    expect(app.get_by_test_id("save-state")).to_have_text("All changes saved", timeout=RENDER)
    read_back(again, tmp_path / "saved")
    assert local_open(tmp_path / "saved").tracks.source[0].text == "I am glad to be here."
    assert errors.seen == [] and seen.seen == []
```

- [ ] **Step 13: Run them; watch them fail.** `make pages` (the site as it is), then `uv run
  pytest -m pages tests/pages/test_pages_files.py -q -x`. Expected:
  `playwright._impl._errors.TimeoutError: Locator.click: Timeout 30000ms exceeded.`, `- waiting
  for locator("iframe").first.content_frame.get_by_test_id("open-folder")`, `1 failed`.
- [ ] **Step 14: The page's half,** `frontend/src/components/FolderPicker.tsx`:

```tsx
import { useRef } from "react";

import { type Folder, filesFolder, pickFolder, supportsDirectoryPicker } from "@/lib/folder";

const button = "rounded-md border border-input bg-background px-2 py-1 text-sm focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ring disabled:opacity-50";

/** One button, two mechanisms, as meanwhile's FolderPicker (src/viewer/components/FolderPicker.tsx
 * at f1279d9; Dan owns both): Chrome and Edge get showDirectoryPicker, asked to read and write,
 * since a file handle has no parent and Save writes next to the video (spec §21); Safari and
 * Firefox get <input webkitdirectory>, which reads only, so Save downloads. The person needn't
 * know which they get. A cancelled picker is no error. */
export function FolderPicker({ onPicked, onError, disabled }: {
  onPicked: (folder: Folder) => void;
  onError: (message: string) => void;
  disabled: boolean;
}) {
  const input = useRef<HTMLInputElement>(null);
  const modern = supportsDirectoryPicker();
  const click = async () => {
    if (!modern) {
      input.current?.click();
      return;
    }
    try {
      const folder = await pickFolder();
      if (folder) onPicked(folder);
    } catch {
      onError("the browser didn't open that folder");
    }
  };
  return (
    <>
      <button type="button" className={button} onClick={() => void click()} disabled={disabled} data-testid="open-folder">
        Open folder
      </button>
      {!modern && (
        <input
          ref={input}
          type="file"
          // Not a React prop: the DOM attribute is what matters (meanwhile's note).
          {...{ webkitdirectory: "", directory: "" }}
          multiple
          hidden
          data-testid="folder-input"
          onChange={(e) => {
            const files = e.target.files;
            if (files && files.length) onPicked(filesFolder(files));
            e.target.value = "";
          }}
        />
      )}
    </>
  );
}
```

  and in `frontend/src/types.ts`, `frontend/src/components/Editor.tsx` and
  `frontend/src/App.tsx`:

```diff
diff --git a/frontend/src/types.ts b/frontend/src/types.ts
index 7004fe6..31ab075 100644
--- a/frontend/src/types.ts
+++ b/frontend/src/types.ts
@@ -184,6 +184,17 @@ export type EditOp =
   | { op: "replace_all"; find: string; replace: string; tracks: string[] }
   | { op: "glossary_add"; term: string; translation: string };
 
+/** One episode in a picked folder (the browser editor, spec §21): the video's name, the files the
+ * page reads for it, the sidecar first, and why it can't open, if it can't (`folder_listing`). */
+export type FoundItem = { name: string; reads: string[]; problem: string | null };
+
+export type FolderListingMessage = { n: number | null; found: FoundItem[] };
+
+/** The `write_files` message (the browser editor's Save or pick): the files to write, the sidecar
+ * first, each as base64; `read`, the SHA-256 of the sidecar as the page last read it (null where
+ * it couldn't read it again), which the page checks just before it writes (spec §14.6). */
+export type WriteFilesMessage = { episode: string; n: number | null; sidecar: string; read: string | null; files: { name: string; data: string }[] };
+
 /** The `save_result` message: what a Save or a pick wrote, left alone or found in conflict. */
 export type SaveResultMessage = {
   episode: string;
```
```diff
diff --git a/frontend/src/components/Editor.tsx b/frontend/src/components/Editor.tsx
index 8b1e33c..369d53b 100644
--- a/frontend/src/components/Editor.tsx
+++ b/frontend/src/components/Editor.tsx
@@ -3,13 +3,15 @@ import { type FormEvent, type KeyboardEvent, useCallback, useEffect, useMemo, us
 import { indexAt, splitPoint, trackCues, wordAt } from "@/lib/cues";
 import { type Action, type KeyLike, actionFor } from "@/lib/keys";
 import { captionLines, type Showing } from "@/lib/overlay";
+import type { Folder } from "@/lib/folder";
 import { selectedIds, selectionRange } from "@/lib/retranslate";
-import type { Busy, EditOp, EpisodeView, Progress } from "@/types";
+import type { Busy, EditOp, EpisodeView, FoundItem, Progress } from "@/types";
 
 import { ConflictPicker } from "./ConflictPicker";
 import { type Cell, type Editing } from "./CueRow";
 import { CueList } from "./CueList";
 import { FindReplace } from "./FindReplace";
+import { FolderPicker } from "./FolderPicker";
 import { Player } from "./Player";
 import { Retranslate } from "./Retranslate";
 import { SaveBar } from "./SaveBar";
@@ -37,17 +39,26 @@ export type Saving = {
   onDiscard: () => void;
 };
 
-/** The editor (spec §20): the path box, or in the browser editor the demo (`onDemo`, spec §21),
- * then, once an episode is open, the player on the left and the cue list on the right, with the
- * edit bar, Retranslate (where the engine has models: `generate`) and find and replace. */
-export function Editor({ episode, busy, progress, pathInput, generate, onOpen, onDemo, onCantPlay, requests, saving }: {
+/** The browser editor's ways in (spec §21): a folder, an episode in it, or the demo. */
+export type Pages = {
+  onFolder: (folder: Folder) => void;
+  found: FoundItem[] | null;
+  onPick: (item: FoundItem) => void;
+  onDemo: () => void;
+  onError: (message: string) => void;
+};
+
+/** The editor (spec §20): the path box, or in the browser editor a folder and the demo (`pages`,
+ * spec §21), then, once an episode is open, the player on the left and the cue list on the right,
+ * with the edit bar, Retranslate (where the engine has models: `generate`) and find and replace. */
+export function Editor({ episode, busy, progress, pathInput, generate, onOpen, pages, onCantPlay, requests, saving }: {
   episode: EpisodeView | null;
   busy: Busy;
   progress: Progress;
   pathInput: boolean;
   generate: boolean;
   onOpen: (path: string) => void;
-  onDemo: (() => void) | null;
+  pages: Pages | null;
   onCantPlay: () => void;
   requests: Requests;
   saving: Saving;
@@ -55,7 +66,7 @@ export function Editor({ episode, busy, progress, pathInput, generate, onOpen, o
   return (
     <div className="flex h-full min-h-0 flex-col gap-3 p-4" data-testid="editor">
       {pathInput && <OpenForm busy={busy} onOpen={onOpen} />}
-      {onDemo && <PagesStart busy={busy} onDemo={onDemo} />}
+      {pages && <PagesStart busy={busy} pages={pages} />}
       {episode ? (
         <EpisodeEditor key={episode.id} episode={episode} busy={busy} progress={progress} generate={generate} requests={requests} saving={saving} onCantPlay={onCantPlay} />
       ) : (
@@ -65,15 +76,31 @@ export function Editor({ episode, busy, progress, pathInput, generate, onOpen, o
   );
 }
 
-/** The browser editor's way in (spec §21): the demo, a short public-domain clip with its
- * captions and a translation. */
-function PagesStart({ busy, onDemo }: { busy: Busy; onDemo: () => void }) {
+/** The browser editor's ways in (spec §21): a folder of videos vid2sub made subtitles for, with
+ * each episode in it to pick (or why it can't open, as plain text), and the demo, a short
+ * public-domain clip with its captions and a translation. */
+function PagesStart({ busy, pages }: { busy: Busy; pages: Pages }) {
   return (
-    <div className="flex flex-wrap items-center gap-2" data-testid="pages-start">
-      <button type="button" className={control} onClick={onDemo} disabled={busy === "opening"} data-testid="open-demo">
-        Open the demo
-      </button>
-      <span className="text-sm text-muted-foreground">a short public-domain clip, with its captions and a translation</span>
+    <div className="flex flex-col gap-2" data-testid="pages-start">
+      <div className="flex flex-wrap items-center gap-2">
+        <FolderPicker onPicked={pages.onFolder} onError={pages.onError} disabled={busy === "opening" || busy === "saving"} />
+        <button type="button" className={control} onClick={pages.onDemo} disabled={busy === "opening"} data-testid="open-demo">
+          Open the demo
+        </button>
+        <span className="text-sm text-muted-foreground">a folder of videos vid2sub made subtitles for, or a short public-domain clip</span>
+      </div>
+      {pages.found && (
+        <ul className="flex flex-wrap gap-2" aria-label="Episodes in the folder" data-testid="found">
+          {pages.found.length === 0 && <li className="text-sm text-muted-foreground">Nothing in that folder has vid2sub's subtitles.</li>}
+          {pages.found.map((item) => (
+            <li key={item.name}>
+              <button type="button" className={control} onClick={() => pages.onPick(item)} disabled={item.problem !== null || busy === "opening"} title={item.problem ?? undefined} data-testid="found-episode">
+                {item.name}{item.problem && ` — ${item.problem}`}
+              </button>
+            </li>
+          ))}
+        </ul>
+      )}
     </div>
   );
 }
```
```diff
diff --git a/frontend/src/App.tsx b/frontend/src/App.tsx
index 6694f65..aeed1bb 100644
--- a/frontend/src/App.tsx
+++ b/frontend/src/App.tsx
@@ -7,13 +7,19 @@ import { type DefaultsChange, SettingsDrawer } from "@/components/SettingsDrawer
 import { TopBar } from "@/components/TopBar";
 import { LOST_MESSAGES, type Lost, whyLost } from "@/lib/connection";
 import { type Draft, type DraftStep, addStep, clearDraft, draftKey, draftStorage, dropRetranslation, loadDraft, replayable } from "@/lib/draft";
+import { FAILURES, type Folder, FolderError, download, fromBase64, nearby, quickHash, readFiles, sha256Hex } from "@/lib/folder";
 import { type Shown, addNotice, dismissNotice } from "@/lib/notices";
 import { retranslateNotice } from "@/lib/retranslate";
 import { pacer } from "@/lib/sends";
 import { useSetShinyInput, useShinyInitialized, useShinyMessageHandler, useShinyOutputValue } from "@/sr";
-import type { Busy, Capabilities, EditOp, EndpointTestResult, EpisodeView, JobsView, Progress, RetranslateResultMessage, SaveResultMessage, SettingsView, Status } from "@/types";
+import type { Busy, Capabilities, EditOp, EndpointTestResult, EpisodeView, FolderListingMessage, FoundItem, JobsView, Progress, RetranslateResultMessage, SaveResultMessage, SettingsView, Status, WriteFilesMessage } from "@/types";
 
 type Ask = { episode: string; n: number };
+/** The browser editor's files for a Save or a pick: the folder's, read again, or none where the
+ * page can't read it again (a read-only folder, the demo). */
+type Fresh = { files: Record<string, string> | null; names: string[] | null };
+type OpenFiles = { video: string; size: number; quick_sha256: string; url: string; files: Record<string, string>; names: string[]; n: number };
+type Written = { episode: string; n: number | null; ok: boolean; why?: string; files?: Record<string, string>; names?: string[] };
 
 type JQueryLike = (target: Document) => {
   on(event: string, handler: () => void): unknown;
@@ -36,6 +42,9 @@ export default function App() {
   // twice is still two requests, and "event" sends it at once, never merged with the next.
   const setOpen = useSetShinyInput<{ path: string; n: number } | null>("open", null, { priority: "event", debounceMs: 0 });
   const setDemo = useSetShinyInput<{ n: number } | null>("demo", null, { priority: "event", debounceMs: 0 });
+  const setFolder = useSetShinyInput<{ names: string[]; n: number } | null>("folder", null, { priority: "event", debounceMs: 0 });
+  const setOpenFiles = useSetShinyInput<OpenFiles | null>("open_files", null, { priority: "event", debounceMs: 0 });
+  const setWritten = useSetShinyInput<Written | null>("written", null, { priority: "event", debounceMs: 0 });
   const setPlayback = useSetShinyInput<{ episode: string; n: number } | null>("playback", null, { priority: "event", debounceMs: 0 });
   const setEdit = useSetShinyInput<(Ask & { op: EditOp }) | null>("edit", null, { priority: "event", debounceMs: 0 });
   const setUndo = useSetShinyInput<Ask | null>("undo", null, { priority: "event", debounceMs: 0 });
@@ -89,6 +98,20 @@ export default function App() {
   // "Retranslate stale", for the notice.
   const asking = useRef(new Map<number, { track: string; stale: boolean }>());
   const episodeId = episode?.id ?? null;
+  // The browser editor's folder (spec §21, §6.9): its handle lives only here, in this tab's
+  // memory, never in storage, so a reload asks for it again. `source` is where the open episode
+  // came from, so a Save writes only into its own folder, and the demo's only downloads.
+  const folder = useRef<Folder | null>(null);
+  const source = useRef<{ folder: Folder | null; video: string } | null>(null);
+  const blob = useRef<string | null>(null);
+  const [found, setFound] = useState<FoundItem[] | null>(null);
+  const fail = (err: unknown) => setNotices((shown) => addNotice(shown, { kind: "error", text: FAILURES[err instanceof FolderError ? err.why : "write"] }, nextId.current++));
+  const fresh = useCallback(async (): Promise<Fresh> => {
+    const from = source.current;
+    if (!from?.folder?.writable) return { files: null, names: null };
+    const names = await from.folder.names();
+    return { files: await readFiles(from.folder, names.filter((n) => nearby(from.video, n))), names };
+  }, []);
   const requests = useMemo<Requests>(() => {
     const ask = (): Ask | null => (episodeId ? { episode: episodeId, n: ++sent.current } : null);
     const send = <T,>(set: (v: T) => void, value: T | null) => value && pace(() => set(value));
@@ -96,8 +119,14 @@ export default function App() {
       edit: (op) => { record({ edit: op }); const a = ask(); send(setEdit, a && { ...a, op }); },
       undo: () => { record({ undo: true }); send(setUndo, ask()); },
       redo: () => { record({ redo: true }); send(setRedo, ask()); },
-      save: (formats) => { const a = ask(); send(setSave, a && { ...a, formats }); },
-      resolve: (track, rendition) => { const a = ask(); send(setResolve, a && { ...a, track, rendition }); },
+      save: (formats) => {
+        const a = ask();
+        if (a) void fresh().then((f) => send(setSave, { ...a, formats, ...f }), fail);
+      },
+      resolve: (track, rendition) => {
+        const a = ask();
+        if (a) void fresh().then((f) => send(setResolve, { ...a, track, rendition, ...f }), fail);
+      },
       retranslate: (track, ids, allowCloud) => {
         const a = ask();
         if (!a) return;
@@ -106,7 +135,68 @@ export default function App() {
         send(setRetranslate, { ...a, track, ids, allow_cloud: allowCloud });
       },
     };
-  }, [episodeId, pace, record, setEdit, setUndo, setRedo, setSave, setResolve, setRetranslate]);
+  }, [episodeId, pace, record, setEdit, setUndo, setRedo, setSave, setResolve, setRetranslate, fresh]);
+
+  // A folder picked (spec §21): Python names its episodes from the names alone; the page then
+  // reads the files it names for one, hashes the video's two ends (§8.3), and plays the video
+  // from a blob URL, so its bytes never reach Python (Review Focus 2).
+  const onFolder = async (picked: Folder) => {
+    folder.current = picked;
+    setFound(null);
+    try {
+      const names = await picked.names();
+      pace(() => setFolder({ names, n: ++sent.current }));
+    } catch (err) {
+      fail(err);
+    }
+  };
+  useShinyMessageHandler("folder_listing", (data: FolderListingMessage) => setFound(data.found));
+  const onPick = async (item: FoundItem) => {
+    const from = folder.current;
+    if (!from) return;
+    try {
+      const video = await from.file(item.name);
+      const [quick, files, names] = await Promise.all([quickHash(video), readFiles(from, item.reads), from.names()]);
+      if (blob.current) URL.revokeObjectURL(blob.current);
+      blob.current = URL.createObjectURL(video);
+      source.current = { folder: from, video: item.name };
+      setFound(null);
+      pace(() => setOpenFiles({ video: item.name, size: video.size, quick_sha256: quick, url: blob.current ?? "", files, names, n: ++sent.current }));
+    } catch (err) {
+      fail(err);
+    }
+  };
+  const onDemo = () => {
+    source.current = { folder: null, video: "" };
+    setDemo({ n: ++sent.current });
+  };
+  // A Save's or a pick's files (spec §14.6): written next to the video where the folder is
+  // writable, the sidecar read again first, and if it changed since, sent back for Python to
+  // merge again; else offered as downloads (Safari, Firefox, the demo: S48).
+  useShinyMessageHandler("write_files", (data: WriteFilesMessage) => {
+    const answer = (x: Omit<Written, "episode" | "n">) => pace(() => setWritten({ episode: data.episode, n: data.n, ...x }));
+    const files = data.files.map((f) => ({ name: f.name, data: fromBase64(f.data) }));
+    const into = source.current?.folder;
+    if (!into?.writable) {
+      download(files);
+      answer({ ok: true });
+      return;
+    }
+    void (async () => {
+      try {
+        if (data.read !== null && (await sha256Hex(await into.file(data.sidecar))) !== data.read) {
+          const again = await fresh();
+          answer({ ok: false, why: "changed", files: again.files ?? {}, names: again.names ?? [] });
+          return;
+        }
+        await into.write(files);
+        answer({ ok: true });
+      } catch (err) {
+        fail(err);
+        answer({ ok: false, why: err instanceof FolderError ? err.why : "write" });
+      }
+    })();
+  });
   useShinyMessageHandler("retranslate_result", (data: RetranslateResultMessage) => {
     if (!episode || data.episode !== episode.id || data.n === null) return;
     const asked = asking.current.get(data.n);
@@ -257,7 +347,7 @@ export default function App() {
           pathInput={capabilities?.path_input ?? false}
           generate={generate}
           onOpen={(path) => setOpen({ path, n: ++sent.current })}
-          onDemo={capabilities?.engine === "browser" ? () => setDemo({ n: ++sent.current }) : null}
+          pages={capabilities?.engine === "browser" ? { onFolder: (f) => void onFolder(f), found, onPick: (item) => void onPick(item), onDemo, onError: (text) => setNotices((shown) => addNotice(shown, { kind: "error", text }, nextId.current++)) } : null}
           onCantPlay={() => episode && setPlayback({ episode: episode.id, n: ++sent.current })}
           requests={requests}
           saving={saving}
```

- [ ] **Step 15: Run the checks; they pass.** `cd frontend && npm run typecheck && npx vitest
  run`: `Test Files  21 passed (21)`, `Tests  100 passed (100)`. `make pages`, then `make
  pages-test`: `9 passed` (about 48 s). Then `make check`: `1097 passed, 2 skipped, 45
  deselected` (twice), `Test Files  21 passed (21)`, `Tests  100 passed (100)`, `All checks
  passed!`, `no leaks found`; and `make e2e`: `31 passed`.
- [ ] **Step 16: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(pages): 🤖 in the browser editor a person opens a local folder, edits, and saves next to the video in Chrome or downloads in Safari

Spec §21 and §14.6, S47 and S48, and the Phase 4 plan's Review Focus 1 and 2, the page's half:

- The start screen: Open folder (FolderPicker, after meanwhile's: showDirectoryPicker asked to
  read and write in Chrome and Edge, <input webkitdirectory> elsewhere) and Open the demo. A
  folder's names go to Python (`folder`); its episodes come back (`folder_listing`) as buttons,
  each that can't open saying why, as plain text. Picking one reads the files Python named, hashes
  the video's two ends (§8.3), makes a blob URL of it for the player and sends `open_files`: the
  video's bytes never reach Python, and only two MiB of it are read (Review Focus 2).
- The folder's handle lives in a ref, in this tab's memory: never in IndexedDB or localStorage
  (spec §6.9), so a new tab or a reload asks for the folder again. `source` remembers where the
  open episode came from, so a Save writes only into its own folder and the demo's only
  downloads.
- Save and a pick read the folder's files again first, where it is writable, and send them;
  `write_files` is answered with `written`: where the folder is writable, the sidecar is read
  again just before the write and, if its SHA-256 isn't the one the merge read, the files as they
  are now go back for Python to merge again (§14.6); else every file is written or none
  (writeAll). Where the folder is read-only (Safari, Firefox) or the episode is the demo, the
  files are offered as downloads (S48). A failure says what happened and to open the folder again
  (FAILURES), and the edits stay unsaved, with their draft.
- Editor's `onDemo` prop is now `pages` (onFolder, found, onPick, onDemo, onError); types gain
  FoundItem, FolderListingMessage and WriteFilesMessage.
- tests/pages/test_pages_files.py writes for real through a directory handle in the site's
  origin-private file system, which an init script hands the page as showDirectoryPicker's
  answer: S47's save lands next to the video (the local engine opens the folder and finds the
  edit; the video is never written) and keeps what another writer added before the Save; S48's
  Save, with showDirectoryPicker taken away, downloads the sidecar and the English SRT, which
  put next to the video hold the edit; and with the folder's permission taken back, or the folder
  removed, Save writes nothing, says why, keeps the edits and their draft, and a second tab that
  opens the folder again restores the draft and saves it. What it can't cover: the picker's
  dialog, the permission prompt, a folder on a real disk moved by the Finder, and Safari and
  Firefox themselves: Task 11's. They failed first, against a site built before this commit:
  "TimeoutError: Locator.click: Timeout 30000ms exceeded", waiting for get_by_test_id("open-folder").
- tests/pagesite.py: what the Pages tests share (the served site, the console errors, booting),
  moved out of tests/pages/test_pages_site.py.

Docs read: Playwright 1.64's BrowserContext.add_init_script (every frame, before the page's
scripts), Page.expect_file_chooser and FileChooser.set_files (a folder, for webkitdirectory), the
download event and Download.save_as; MDN on StorageManager.getDirectory (the origin-private
file system; its handles take createWritable) and URL.createObjectURL / revokeObjectURL.

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-4.md Task 3
Co-Authored-By: <the model's own line>
```

  `git add frontend/src/App.tsx frontend/src/components/Editor.tsx frontend/src/types.ts
  frontend/src/components/FolderPicker.tsx tests/pages/test_pages_site.py
  tests/pages/test_pages_files.py tests/pagesite.py`, `git commit -F .git/COMMIT_MSG`, then
  `git log -1 --format='%(trailers)'` shows `Plan:`.

#### Round 3d: the security review, and its fixes

- [ ] **Step 17: The security review.** One independent reviewer (a subagent) over
  `git diff $(cat .git/TASK_BASE) HEAD`, with `AGENTS.md`'s security checklist (secrets,
  permissions, network exposure, failing closed, injection, logging), the spec's §6, §14.6,
  §15.3 and §21, and Review Focus 1 and 2; read-only, each finding with file and line, why, the
  fix and a severity. At this listing's build it found one Critical and seven Important (below),
  and seven Minor, three of which are on the Phase-end list already, as planning rows. Each of
  the rest is fixed here, with a test that fails without it.
- [ ] **Step 18: Write the failing tests.** In `tests/test_browser_backend.py`,
  `tests/test_web_browser.py`, `frontend/src/lib/folder.test.ts` and
  `tests/pages/test_pages_files.py`:

```diff
diff --git a/tests/test_browser_backend.py b/tests/test_browser_backend.py
index 7a24e3d..1687d94 100644
--- a/tests/test_browser_backend.py
+++ b/tests/test_browser_backend.py
@@ -116,9 +116,22 @@ def test_a_folder_listing_names_each_episode_and_the_files_the_page_reads_for_it
 
 @pytest.mark.parametrize("bad", ["../etc/passwd", "a/b.srt", "a\\b.srt", "..", "", "x\0.srt",
                                  "bell\x07.srt", "x" * 256])
-def test_a_listing_with_a_name_that_isnt_a_files_own_is_refused(bad):
+def test_a_name_vid2sub_couldnt_stage_is_left_out_of_the_listing_not_the_folder(bad):
+    # why: one odd name elsewhere in a folder mustn't refuse its every episode (the Task 3
+    # security review); it is never staged, and never one of an episode's own.
+    names = [NAME, SIDECAR, bad]
+    assert BrowserBackend().listing(names) == [Found(NAME, (SIDECAR,))]
+
+
+def test_a_japanese_name_with_an_ideographic_space_is_a_name_like_any_other():
+    video = "名探偵\u3000コナン 第1話.mkv"
+    sidecar = "名探偵\u3000コナン 第1話.vid2sub.jsonl"
+    assert BrowserBackend().listing([video, sidecar, "メモ\u00a0.txt"]) == [Found(video, (sidecar,))]
+
+
+def test_a_listing_that_isnt_a_list_of_names_is_refused():
     with pytest.raises(OpenError, match=BAD_NAMES):
-        BrowserBackend().listing(["Show - S01E01.mkv", bad])
+        BrowserBackend().listing([NAME, 7])
 
 
 def test_opening_from_the_handed_over_bytes_gives_the_episode_the_local_engine_opens(video,
@@ -226,11 +239,14 @@ def test_a_download_builds_on_the_files_as_the_episode_last_saw_them(video, loca
     ep = edit(browser, open_in_browser(browser, video), op="set_text", cue=sid(0), text="一")
     ep = edit(browser, ep, op="glossary_add", term="東京", translation="Tokyo")
     first, _, writes = browser.save(ep, formats=["srt"])
-    assert list(writes) == [SIDECAR, JA, GLOSSARY]
+    # The whole set each time (spec §21: "downloads of the subtitle files and of the whole
+    # sidecar"), so a download the browser blocked can come again with the next Save.
+    assert list(writes) == [SIDECAR, EN, JA, GLOSSARY]
     ep = edit(browser, first, op="set_text", cue=sid(1), text="二")
     ep = edit(browser, ep, op="glossary_add", term="大阪", translation="Osaka")
     second, _, writes = browser.save(ep, formats=["srt"])
-    assert list(writes) == [SIDECAR, JA, GLOSSARY]
+    assert list(writes) == [SIDECAR, EN, JA, GLOSSARY]
+    assert list(browser.save(second, formats=["srt"])[2]) == [SIDECAR, EN, JA, GLOSSARY]
     assert dict(parse_glossary(writes[GLOSSARY].decode()).terms) == {"東京": "Tokyo",
                                                                      "大阪": "Osaka"}
     write_out(video, writes)
@@ -382,3 +398,18 @@ def test_the_demo_opens_from_the_files_bundled_with_the_site_and_plays_from_its_
     assert browser.video_url(ep.id) == "../demo/Show%20-%20S01E01.mkv"
     with pytest.raises(OpenError, match=NO_DEMO):
         BrowserBackend().open_demo()
+
+
+def test_a_video_whose_name_starts_with_a_dot_is_saved_whole(tmp_path, local):
+    # why: the Task 3 security review's Critical: the staging folder's read skipped every name
+    # starting with "." (to skip safe_write's temporary files), so `.clip.mkv`'s sidecar and
+    # subtitle files were left out of a Save's files while the Save said it had written them.
+    video = make_episode(tmp_path / "show", ".clip.mkv")
+    browser = BrowserBackend()
+    ep = edit(browser, open_in_browser(browser, video), op="set_text", cue=sid(0), text="朝")
+    files, names = read_again(video, browser)
+    saved, result, writes = browser.save(ep, formats=["srt"], files=files, names=names)
+    assert list(writes) == [".clip.vid2sub.jsonl", ".clip.ja.srt"]
+    assert result.written == (".clip.ja.srt",) and not saved.dirty
+    write_out(video, writes)
+    assert local.open(str(video)).tracks.source[0].text == "朝"
```
```diff
diff --git a/tests/test_web_browser.py b/tests/test_web_browser.py
index a041006..e56b480 100644
--- a/tests/test_web_browser.py
+++ b/tests/test_web_browser.py
@@ -308,7 +308,51 @@ def test_the_demos_save_hands_back_its_files_to_download(tab):
     tab.set(save={"episode": ep["id"], "n": 3, "formats": ["srt"], "files": None,
                   "names": None})
     asked = tab.until(lambda: tab.sent("write_files"))[0]
-    assert asked["read"] is None
-    assert [f["name"] for f in asked["files"]] == ["jfk.vid2sub.jsonl", "jfk.en.srt"]
+    assert asked["read"] is None and asked["seconds"] == server.WRITE_TIMEOUT
+    assert [f["name"] for f in asked["files"]] == ["jfk.vid2sub.jsonl", "jfk.en.srt",
+                                                   "jfk.ja.srt"]
     tab.set(written={"episode": ep["id"], "n": 3, "ok": True})
     tab.until(lambda: tab.sent("save_result"))
+
+
+@pytest.mark.media
+def test_the_sidecar_is_read_again_as_the_folder_spells_it(tab, tmp_path):
+    # why: on a case-blind disk the folder's `show - s01e01.vid2sub.jsonl` is the sidecar
+    # vid2sub writes as `Show - S01E01…`; without its hash the page would skip the re-read
+    # (spec §14.6) and write over it (the Task 3 security review).
+    video = make_episode(tmp_path / "show")
+    (video.parent / SIDECAR).rename(video.parent / SIDECAR.lower())
+    ep = edited(tab, opened(tab, video), "おはよう！", 2)
+    files, names = folder_files(video)
+    tab.set(save={"episode": ep["id"], "n": 3, "formats": ["srt"], "files": files,
+                  "names": names})
+    asked = tab.until(lambda: tab.sent("write_files"))[0]
+    lower = (video.parent / SIDECAR.lower()).read_bytes()
+    assert asked["sidecar"] == SIDECAR.lower()
+    assert asked["read"] == hashlib.sha256(lower).hexdigest()
+
+
+@pytest.mark.media
+def test_a_page_that_never_answers_saves_nothing_and_says_so(tab, tmp_path, monkeypatch):
+    monkeypatch.setattr(server, "WRITE_TIMEOUT", 0.5)
+    video = make_episode(tmp_path / "show")
+    ep = edited(tab, opened(tab, video), "おはよう！", 2)
+    files, names = folder_files(video)
+    tab.set(save={"episode": ep["id"], "n": 3, "formats": ["srt"], "files": files,
+                  "names": names})
+    said = tab.until(lambda: [n for n in tab.sent("notice") if n["text"] == server.WRITE_LATE])
+    assert said and tab.value("episode")["dirty"] is True and tab.sent("save_result") == []
+    assert tab.sent("write_files")[0]["seconds"] == 0.5
+
+
+@pytest.mark.media
+def test_a_changed_answer_without_the_folders_files_saves_nothing(tab, tmp_path):
+    video = make_episode(tmp_path / "show")
+    ep = edited(tab, opened(tab, video), "おはよう！", 2)
+    files, names = folder_files(video)
+    tab.set(save={"episode": ep["id"], "n": 3, "formats": ["srt"], "files": files,
+                  "names": names})
+    tab.until(lambda: tab.sent("write_files"))
+    tab.set(written={"episode": ep["id"], "n": 3, "ok": False, "why": "changed", "files": None})
+    tab.until(lambda: tab.value("busy") is None)
+    assert len(tab.sent("write_files")) == 1 and tab.value("episode")["dirty"] is True
```
```diff
diff --git a/frontend/src/lib/folder.test.ts b/frontend/src/lib/folder.test.ts
index 1a59725..29c1ab4 100644
--- a/frontend/src/lib/folder.test.ts
+++ b/frontend/src/lib/folder.test.ts
@@ -4,7 +4,7 @@
 // all or none. Node's environment: it has crypto.subtle, Blob and DOMException as browsers do.
 import { describe, expect, it } from "vitest";
 
-import { type DirectoryHandle, FolderError, MIB, filesFolder, fromBase64, nearby, quickHash, toBase64, writeAll } from "./folder";
+import { type DirectoryHandle, type Folder, FolderError, MIB, filesFolder, fromBase64, nearby, quickHash, toBase64, writeAll, writePlan } from "./folder";
 
 /** Byte k is k % 251, as the Python side of these cases has it. */
 const pattern = (n: number) => Uint8Array.from({ length: n }, (_, k) => k % 251);
@@ -41,6 +41,13 @@ describe("which files are a video's own", () => {
       expect(nearby(video, name)).toBe(false);
     }
   });
+
+  it("aren't another video's whose name starts with this one's", () => {
+    // why: a season's S01.mkv would read every S01.E02's files, past what a Save may hand over.
+    expect(nearby("S01.mkv", "S01.en.srt")).toBe(true);
+    expect(nearby("S01.mkv", "S01.E02.en.srt")).toBe(false);
+    expect(nearby("S01.mkv", "S01.E02.vid2sub.jsonl")).toBe(false);
+  });
 });
 
 describe("files on the wire", () => {
@@ -62,8 +69,9 @@ describe("a folder read through <input webkitdirectory> (Safari, Firefox)", () =
   });
 });
 
-/** A directory handle over a Map, recording what happens to each file. */
-function fakeFolder({ permission = "granted", request = "granted", missing = "" }: { permission?: string; request?: string; missing?: string } = {}) {
+/** A directory handle over a Map, recording what happens to each file: `create` makes an empty
+ * file at once, as the File System spec's getFileHandle does. */
+function fakeFolder({ permission = "granted", request = "granted", missing = "", failClose = "" }: { permission?: string; request?: string; missing?: string; failClose?: string } = {}) {
   const files = new Map<string, Uint8Array<ArrayBuffer>>([["a.vid2sub.jsonl", new Uint8Array([1])]]);
   const log: string[] = [];
   const dir = {
@@ -72,8 +80,14 @@ function fakeFolder({ permission = "granted", request = "granted", missing = ""
     async *entries() {},
     queryPermission: async () => permission,
     requestPermission: async () => { log.push("asked"); return request; },
-    async getFileHandle(name: string) {
+    async removeEntry(name: string) { files.delete(name); log.push(`remove ${name}`); },
+    async getFileHandle(name: string, options?: { create?: boolean }) {
       if (name === missing) throw new DOMException("gone", "NotFoundError");
+      if (!files.has(name)) {
+        if (!options?.create) throw new DOMException("no such file", "NotFoundError");
+        files.set(name, new Uint8Array());
+        log.push(`create ${name}`);
+      }
       return {
         kind: "file",
         name,
@@ -83,7 +97,11 @@ function fakeFolder({ permission = "granted", request = "granted", missing = ""
           log.push(`open ${name}`);
           return {
             write: async (data: Uint8Array<ArrayBuffer>) => { pending = data; },
-            close: async () => { if (pending) files.set(name, pending); log.push(`close ${name}`); },
+            close: async () => {
+              if (name === failClose) throw new DOMException("full", "QuotaExceededError");
+              if (pending) files.set(name, pending);
+              log.push(`close ${name}`);
+            },
             abort: async () => { log.push(`abort ${name}`); },
           };
         },
@@ -102,7 +120,7 @@ describe("writing a Save's files (Review Focus 1)", () => {
   it("opens every file, then puts them in place, the sidecar first", async () => {
     const { dir, files, log } = fakeFolder();
     await writeAll(dir, SAVE);
-    expect(log).toEqual(["open a.vid2sub.jsonl", "open a.en.srt", "close a.vid2sub.jsonl", "close a.en.srt"]);
+    expect(log).toEqual(["open a.vid2sub.jsonl", "create a.en.srt", "open a.en.srt", "close a.vid2sub.jsonl", "close a.en.srt"]);
     expect(files.get("a.vid2sub.jsonl")).toEqual(new Uint8Array([2]));
     expect(files.get("a.en.srt")).toEqual(new Uint8Array([3]));
   });
@@ -129,3 +147,37 @@ describe("writing a Save's files (Review Focus 1)", () => {
     expect(files.get("a.vid2sub.jsonl")).toEqual(new Uint8Array([1]));
   });
 });
+
+describe("a Save cut short (the Task 3 security review)", () => {
+  it("removes the file it had just created, and keeps the sidecar it had put in place", async () => {
+    // why: getFileHandle's create makes an empty file at once, which later Saves would call
+    // someone else's; the sidecar, closed first, holds the version the next Save builds on.
+    const { dir, files, log } = fakeFolder({ failClose: "a.en.srt" });
+    await expect(writeAll(dir, SAVE)).rejects.toEqual(new FolderError("write"));
+    expect(files.has("a.en.srt")).toBe(false);
+    expect(files.get("a.vid2sub.jsonl")).toEqual(new Uint8Array([2]));
+    expect(log.at(-1)).toBe("remove a.en.srt");
+  });
+});
+
+describe("what the page does with a Save's files", () => {
+  const writable = { writable: true } as Folder;
+  const readOnly = { writable: false } as Folder;
+  const message = { episode: "e1", read: "ab", files: [{ name: "jfk.vid2sub.jsonl" }, { name: "jfk.en.srt" }] };
+
+  it("writes into the episode's own folder, or downloads where it can't write", () => {
+    expect(writePlan({ episode: "e1", folder: writable, video: "jfk.mp4" }, message)).toEqual({ kind: "write", folder: writable });
+    expect(writePlan({ episode: "e1", folder: readOnly, video: "jfk.mp4" }, message)).toEqual({ kind: "download" });
+    expect(writePlan({ episode: "e1", folder: null, video: "" }, { ...message, read: null })).toEqual({ kind: "download" });
+  });
+
+  it("refuses another episode's files, an unread sidecar and a name not the video's own", () => {
+    // why: the person may open another episode, or the demo, while a Save is out; its files
+    // must never land in the folder now held (the Task 3 security review).
+    const source = { episode: "e1", folder: writable, video: "jfk.mp4" };
+    expect(writePlan({ ...source, episode: "e2" }, message)).toEqual({ kind: "refuse" });
+    expect(writePlan(null, message)).toEqual({ kind: "refuse" });
+    expect(writePlan(source, { ...message, read: null })).toEqual({ kind: "refuse" });
+    expect(writePlan(source, { ...message, files: [{ name: "other.vid2sub.jsonl" }] })).toEqual({ kind: "refuse" });
+  });
+});
```
```diff
diff --git a/tests/pages/test_pages_files.py b/tests/pages/test_pages_files.py
index 0f8b542..f96008b 100644
--- a/tests/pages/test_pages_files.py
+++ b/tests/pages/test_pages_files.py
@@ -191,7 +191,7 @@ def test_save_keeps_what_another_writer_added_since_the_folder_was_read(
 def test_a_folder_safari_can_only_read_is_saved_as_downloads(page: Page, site_url, episode,
                                                              tmp_path, errors):
     # S48: no showDirectoryPicker (Safari, Firefox): <input webkitdirectory> reads the folder,
-    # and Save offers the sidecar and the subtitle files it wrote as downloads.
+    # and Save offers the sidecar and the subtitle files as downloads.
     page.context.add_init_script(NO_PICKER)
     app = boot(page, site_url)
     with page.expect_file_chooser() as chooser:
@@ -204,8 +204,10 @@ def test_a_folder_safari_can_only_read_is_saved_as_downloads(page: Page, site_ur
     page.on("download", lambda d: downloads.append(d))
     app.get_by_test_id("save").click()
     expect(app.get_by_test_id("save-state")).to_have_text("All changes saved", timeout=RENDER)
-    page.wait_for_timeout(500)
-    assert sorted(d.suggested_filename for d in downloads) == [EN, SIDECAR]
+    page.wait_for_timeout(1000)  # the downloads come a quarter second apart
+    # The whole set: the sidecar and every subtitle file it projects, so a download the browser
+    # blocked comes again with the next Save.
+    assert sorted(d.suggested_filename for d in downloads) == [EN, "jfk.ja.srt", SIDECAR]
     for d in downloads:
         d.save_as(episode / d.suggested_filename)  # what the person does with them
     assert local_open(episode).tracks.source[0].text == "I am glad to be here."
@@ -217,7 +219,8 @@ def test_a_folder_lost_mid_edit_saves_nothing_says_why_and_keeps_the_edits(
         page: Page, site_url, episode, tmp_path, errors, lost):
     # why: Review Focus 1: the folder's permission taken back, or the folder moved, while an
     # episode is open: Save writes nothing half-way, says what happened and to open the folder
-    # again, and the edits stay in the tab and its draft; opening it again offers the draft.
+    # again, and the edits stay in the tab and its draft; with the folder back, the same tab
+    # saves them.
     page.context.add_init_script(PICKER)
     app = boot(page, site_url)
     fill(page, episode)
@@ -241,20 +244,15 @@ def test_a_folder_lost_mid_edit_saves_nothing_says_why_and_keeps_the_edits(
     assert len(drafts) == 1
     if lost == "permission":
         assert read_back(page, tmp_path / "after") == before  # nothing written half-way
-        page.evaluate("() => { window.__deny = false; }")
+        page.evaluate("() => { window.__deny = false; }")  # the person allows it again
     else:
-        fill(page, episode)  # the folder is back where it was
-    # A second tab, as after a crash: the draft is offered when the folder is opened again.
-    again = page.context.new_page()
-    seen = Errors(again)
-    app = boot(again, site_url)
-    open_folder(app)
-    expect(app.get_by_test_id("draft")).to_be_visible(timeout=RENDER)
-    app.get_by_test_id("draft-restore").click()
-    expect(app.get_by_test_id("cue-text").first).to_have_text("I am glad to be here.",
-                                                              timeout=RENDER)
+        fill(page, episode)  # the folder is back where it was, and the person picks it again
+        app.get_by_test_id("open-folder").click()
+        expect(app.get_by_test_id("found-episode")).to_have_count(1, timeout=RENDER)
+    # The same tab saves its edits there, the open episode's Save now aimed at that folder.
+    expect(app.get_by_test_id("save-state")).to_have_text("Unsaved changes")
     app.get_by_test_id("save").click()
     expect(app.get_by_test_id("save-state")).to_have_text("All changes saved", timeout=RENDER)
-    read_back(again, tmp_path / "saved")
+    read_back(page, tmp_path / "saved")
     assert local_open(tmp_path / "saved").tracks.source[0].text == "I am glad to be here."
-    assert errors.seen == [] and seen.seen == []
+    assert errors.seen == []
```

  Run them on the code as it is: `VID2SUB_REQUIRE_FFMPEG=1 uv run pytest
  tests/test_browser_backend.py tests/test_web_browser.py -q`: `15 failed, 30 passed`, namely
  the download's (not the whole set), the ideographic space's, the eight odd names' (each
  refused), the dot-named video's, the "changed" answer without files, the page that never
  answers, the demo's download and the sidecar's spelling. `cd frontend && npx vitest run
  src/lib/folder.test.ts`: `Tests  4 failed | 9 passed (13)`: `nearby`'s season case, the
  cut-short Save's removal, and both of `writePlan`'s.
- [ ] **Step 19: The fixes.** In `src/vid2sub/web/browser.py`, `src/vid2sub/web/server.py`,
  `frontend/src/lib/folder.ts`, `frontend/src/types.ts`, `frontend/src/components/Editor.tsx`,
  `frontend/src/App.tsx`, and the spec's §14.6 and §21 (the page hands Python the files' bytes,
  not text):

```diff
diff --git a/src/vid2sub/web/browser.py b/src/vid2sub/web/browser.py
index a636653..11dac89 100644
--- a/src/vid2sub/web/browser.py
+++ b/src/vid2sub/web/browser.py
@@ -39,6 +39,7 @@ from __future__ import annotations
 import re
 import tempfile
 import threading
+import unicodedata
 from collections.abc import Collection, Iterator, Mapping, Sequence
 from contextlib import contextmanager
 from dataclasses import dataclass, field, fields, replace
@@ -68,6 +69,7 @@ MAX_FILES = 64  # files one open or Save hands over: a sidecar, a glossary and s
 MAX_BYTES = 64 * 2**20  # bytes in each: a sidecar is about 400 KB plus 50 KB a version (§14.7)
 MAX_NAME = 255  # characters in a file name
 SHA256 = re.compile(r"[0-9a-f]{64}")
+TEMPORARY = re.compile(r"\..+\.[0-9a-f]{12}\.tmp")  # safe_write's: .<name>.<12 hex>.tmp
 # What URL.createObjectURL returns: blob:<the page's origin>/<a UUID> (File API).
 BLOB_URL = re.compile(r"blob:https?://[A-Za-z0-9.:\[\]-]+/[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}"
                       r"-[0-9A-Fa-f]{12}")
@@ -283,8 +285,15 @@ class BrowserBackend:
                 raise SaveError(str(err)) from None
             done, result = act(replace(ep, video=staged))
             after = _read(stage)
-        writes = {n: data for n, data in sorted(after.items(), key=lambda kv: kv[0] != sidecar)
-                  if before.get(n) != data}
+        if files is None:  # downloads: the whole set each time, so a blocked one can come again
+            own = {sidecar, naming.GLOSSARY_NAME, *done.sidecar.projections()}
+            keep = [n for n in after if n in own]
+        else:  # written into the folder: what changed
+            keep = [n for n in after if before.get(n) != after[n]]
+        writes = {n: after[n] for n in sorted(keep, key=lambda n: n != sidecar)}
+        lost = [n for n in (sidecar, *result.written) if n not in after]
+        if lost:  # never report a file written that the staging folder's read left out
+            raise SaveError(f"couldn't hand back {', '.join(lost)}: nothing was saved")
         return _browser(done, name, after), result, writes
 
     def _check_open(self, ep: Episode) -> None:
@@ -328,17 +337,21 @@ def browser_runtime(backend: BrowserBackend | None = None) -> BrowserRuntime:
 
 
 def _names(names: object, limit: int) -> list[str]:
+    """A folder's file names, skipping any vid2sub couldn't stage (a backslash, a control
+    character): none of those is an episode's own, so one doesn't refuse the folder."""
     if not isinstance(names, (list, tuple)) or len(names) > limit:
         raise OpenError(TOO_MANY)
-    if not all(_bare(n) for n in names):
+    if not all(isinstance(n, str) for n in names):
         raise OpenError(BAD_NAMES)
-    return list(names)
+    return [n for n in names if _bare(n)]
 
 
 def _bare(name: object) -> bool:
-    """A file's own name: no folder, no control character, at most MAX_NAME characters."""
+    """A file's own name: no folder, no control character or lone surrogate, at most MAX_NAME
+    characters. Any other character goes, the ideographic space of a Japanese name included."""
     return (isinstance(name, str) and 0 < len(name) <= MAX_NAME and name not in (".", "..")
-            and not any(ch in name for ch in "/\\\0") and name.isprintable())
+            and not any(ch in name for ch in "/\\")
+            and all(unicodedata.category(ch) not in ("Cc", "Cs") for ch in name))
 
 
 def _video_name(video: object) -> str:
@@ -401,8 +414,10 @@ def _staging(files: Mapping[str, bytes]) -> Iterator[Path]:
 
 
 def _read(stage: Path) -> dict[str, bytes]:
+    """Every file in the staging folder but safe_write's temporary ones: a video named
+    `.clip.mkv` has its files named `.clip.…` too."""
     return {p.name: p.read_bytes() for p in sorted(stage.iterdir())
-            if p.is_file() and not p.is_symlink() and not p.name.startswith(".")}
+            if p.is_file() and not p.is_symlink() and not TEMPORARY.fullmatch(p.name)}
 
 
 def _browser(ep: Episode, name: str, files: Mapping[str, bytes]) -> BrowserEpisode:
```
```diff
diff --git a/src/vid2sub/web/server.py b/src/vid2sub/web/server.py
index 3e5a06d..41fe142 100644
--- a/src/vid2sub/web/server.py
+++ b/src/vid2sub/web/server.py
@@ -119,6 +119,8 @@ WRITES = 3  # times a Save merges again when the folder's sidecar changed while
 WRITE_TIMEOUT = 300.0  # seconds the page has to write a Save's files, or to say why it couldn't
 BAD_FILES = "the page sent files the editor can't read: open the folder again"
 KEPT_CHANGING = "the sidecar kept changing while it was saved: nothing was saved, save again"
+WRITE_LATE = "the files weren't written within five minutes, so nothing was saved: save again"
+LATE = object()  # the page didn't answer within WRITE_TIMEOUT
 OPEN_A_FOLDER = "open a folder: the browser editor reads no typed path"
 MAX_JOBS = 500  # paths one Start may queue
 TYPE_PATHS = "type each video's full path, one per line: nothing was queued"
@@ -269,7 +271,7 @@ class Editor:
                 self.rt.backend.open, request.get("video"), size=request.get("size"),
                 quick_sha256=request.get("quick_sha256"), url=request.get("url"), files=files,
                 names=names)
-        except OpenError as err:  # each is fit to show, and echoes nothing the page sent
+        except OpenError as err:  # each is fit to show, plain text, with no path in it
             await self._set_busy(None)
             await notice(self.session, "error", str(err))
             return
@@ -398,16 +400,20 @@ class Editor:
             saved, result, writes = await act(files, names)
             if not writes:
                 return saved, result
+            # The sidecar as the folder spells it, which a case-blind disk may spell otherwise.
             sidecar = naming.sidecar_name(saved.video.name)
-            answer = await self._ask_to_write(n, saved, writes, sidecar, read=(
-                hashlib.sha256(files[sidecar]).hexdigest() if files and sidecar in files
-                else None))
+            on_disk = next((k for k in files or {} if k.casefold() == sidecar.casefold()), None)
+            answer = await self._ask_to_write(n, saved, writes, on_disk or sidecar, read=(
+                hashlib.sha256(files[on_disk]).hexdigest() if on_disk else None))
             if not isinstance(answer, dict) or answer.get("ok") is not True:
-                if isinstance(answer, dict) and answer.get("why") == "changed":
+                if (isinstance(answer, dict) and answer.get("why") == "changed"
+                        and isinstance(answer.get("files"), dict)):
                     files, names = answer.get("files"), answer.get("names")
                     continue
                 if not self._ended:
-                    await self._set_busy(None)  # the page said why, in its own notice
+                    await self._set_busy(None)
+                    if answer is LATE:  # else the page said why, in its own notice
+                        await notice(self.session, "error", WRITE_LATE)
                 return None
             return saved, result
         await self._set_busy(None)
@@ -416,18 +422,19 @@ class Editor:
 
     async def _ask_to_write(self, n: object, ep: Episode, writes: dict[str, bytes], sidecar: str,
                             read: str | None) -> object:
-        """Sends the page Save's files (`write_files`) and waits for its `written` answer."""
+        """Sends the page Save's files (`write_files`) and waits for its `written` answer; LATE
+        after WRITE_TIMEOUT seconds, which the page is told, so it starts no write too late."""
         future = asyncio.get_running_loop().create_future()
         self._writing = (n, future)
         try:
             await shinyreact.send_message(self.session, "write_files", {
                 "episode": ep.id, "n": n if type(n) is int else None, "sidecar": sidecar,
-                "read": read,
+                "read": read, "seconds": WRITE_TIMEOUT,
                 "files": [{"name": name, "data": base64.b64encode(data).decode("ascii")}
                           for name, data in writes.items()]})
             return await asyncio.wait_for(future, WRITE_TIMEOUT)
         except TimeoutError:
-            return None
+            return LATE
         finally:
             self._writing = None
 
```
```diff
diff --git a/frontend/src/lib/folder.ts b/frontend/src/lib/folder.ts
index 4e96ce7..8d8e5ad 100644
--- a/frontend/src/lib/folder.ts
+++ b/frontend/src/lib/folder.ts
@@ -13,7 +13,7 @@ export const GLOSSARY = "vid2sub.glossary.toml";
 
 /** Why a write failed, for the person: the folder's permission was taken back, or the folder
  * isn't where it was (moved, renamed or deleted), or anything else (Review Focus 1). */
-export type WriteFailure = "permission" | "gone" | "write";
+export type WriteFailure = "permission" | "gone" | "write" | "elsewhere" | "late";
 
 export class FolderError extends Error {
   constructor(readonly why: WriteFailure) {
@@ -25,6 +25,8 @@ export const FAILURES: Record<WriteFailure, string> = {
   permission: "vid2sub may no longer write to that folder, so nothing was saved: open the folder again to save your edits",
   gone: "the folder isn't where it was (moved or renamed?), so nothing was saved: open it again to save your edits",
   write: "the browser couldn't write to that folder, so nothing was saved: open it again to save your edits",
+  elsewhere: "the open episode changed while it was being saved, so nothing was saved: save again",
+  late: "the folder took too long to answer, so nothing was saved: save again",
 };
 
 /** A folder the page reads, and writes where the browser lets it. */
@@ -33,7 +35,8 @@ export interface Folder {
   readonly writable: boolean;
   names(): Promise<string[]>;
   file(name: string): Promise<File>;
-  write(files: readonly Written[]): Promise<void>;
+  /** Writes every file or none; `deadline` (performance.now()'s ms) stops it starting late. */
+  write(files: readonly Written[], deadline?: number): Promise<void>;
 }
 
 export type Written = { name: string; data: Uint8Array<ArrayBuffer> };
@@ -47,6 +50,7 @@ export interface DirectoryHandle {
   name: string;
   entries(): AsyncIterableIterator<[string, FileHandle | DirectoryHandle]>;
   getFileHandle(name: string, options?: { create?: boolean }): Promise<FileHandle>;
+  removeEntry(name: string): Promise<void>;
   queryPermission?(descriptor: { mode: "readwrite" }): Promise<Permission>;
   requestPermission?(descriptor: { mode: "readwrite" }): Promise<Permission>;
 }
@@ -98,33 +102,52 @@ export function handleFolder(dir: DirectoryHandle): Folder {
         throw new FolderError(why(err));
       }
     },
-    write: (files) => writeAll(dir, files),
+    write: (files, deadline) => writeAll(dir, files, deadline),
   };
 }
 
 /** Every file, or none: the folder's permission is checked (and asked again, while the Save's
  * click still counts), every file is opened for writing before any is written, and a failure
  * aborts the files not yet closed, whose writes the browser then throws away (createWritable
- * writes a swap file that only close() puts in place, MDN). The sidecar comes first, as Save
- * lists it, so a cut-short write leaves at most a subtitle file holding an earlier version,
- * which the next open recognises as vid2sub's own (spec §14.6). */
-export async function writeAll(dir: DirectoryHandle, files: readonly Written[]): Promise<void> {
+ * writes a swap file that only close() puts in place, MDN), and removes the ones this Save
+ * created, since getFileHandle's `create` makes an empty file at once. The sidecar comes first,
+ * as Save lists it, so a write cut short after it leaves at most a subtitle file holding an
+ * earlier version, which the next open recognises as vid2sub's own (spec §14.6). */
+export async function writeAll(dir: DirectoryHandle, files: readonly Written[], deadline?: number): Promise<void> {
   const writables: Writable[] = [];
+  const created: string[] = [];
+  // Aborts the writables from `from` on, and removes each file this Save created but didn't put
+  // in place (the first `closed` files are in place).
+  const undo = async (from: number, closed: number) => {
+    await Promise.all(writables.slice(from).map((w) => w.abort().catch(() => undefined)));
+    const placed = new Set(files.slice(0, closed).map((f) => f.name));
+    await Promise.all(created.filter((n) => !placed.has(n)).map((n) => dir.removeEntry(n).catch(() => undefined)));
+  };
   try {
     let state = await dir.queryPermission?.({ mode: "readwrite" });
     if (state === "prompt") state = await dir.requestPermission?.({ mode: "readwrite" });
     if (state !== undefined && state !== "granted") throw new FolderError("permission");
-    for (const f of files) writables.push(await (await dir.getFileHandle(f.name, { create: true })).createWritable());
+    // A permission prompt left open past Python's wait: the Save already counts as not saved.
+    if (deadline !== undefined && performance.now() > deadline) throw new FolderError("late");
+    for (const f of files) {
+      const there = await dir.getFileHandle(f.name).then(() => true, (err) => {
+        if (err instanceof DOMException && err.name === "NotFoundError") return false;
+        throw err;
+      });
+      const handle = await dir.getFileHandle(f.name, { create: true });
+      if (!there) created.push(f.name);
+      writables.push(await handle.createWritable());
+    }
     for (const [k, f] of files.entries()) await writables[k].write(f.data);
   } catch (err) {
-    await Promise.all(writables.map((w) => w.abort().catch(() => undefined)));
+    await undo(0, 0);
     throw err instanceof FolderError ? err : new FolderError(why(err));
   }
   for (const [k, w] of writables.entries()) {
     try {
       await w.close();
     } catch (err) {
-      await Promise.all(writables.slice(k + 1).map((v) => v.abort().catch(() => undefined)));
+      await undo(k + 1, k);
       throw new FolderError(why(err));
     }
   }
@@ -178,14 +201,33 @@ export async function sha256Hex(blob: Blob, digest: Digest = (d) => crypto.subtl
   return [...new Uint8Array(hash)].map((b) => b.toString(16).padStart(2, "0")).join("");
 }
 
-/** Whether a file might be one of the video's own (its sidecar, its subtitle files, the folder's
- * glossary): the page reads these for a Save, and Python takes the ones that are (BrowserBackend,
- * by its own rule) and refuses a Save whose folder lists one it wasn't handed. */
+/** Whether a file might be one of the video's own, in any case: its sidecar, a subtitle file
+ * named for it (`<stem>.<code>.srt` or `.ass`, the names vid2sub writes, spec §15.1) or the
+ * folder's glossary. The page reads these for a Save, and Python takes the ones that are
+ * (BrowserBackend, by its own list of codes) and refuses a Save whose folder lists one it
+ * wasn't handed. */
 export function nearby(video: string, name: string): boolean {
   const dot = video.lastIndexOf(".");
   const stem = (dot > 0 ? video.slice(0, dot) : video).toLowerCase();
   const lower = name.toLowerCase();
-  return lower === GLOSSARY || (lower.startsWith(`${stem}.`) && /\.(srt|ass|vid2sub\.jsonl)$/.test(lower));
+  if (lower === GLOSSARY || lower === `${stem}.vid2sub.jsonl`) return true;
+  return lower.startsWith(`${stem}.`) && /^[^.]+\.(srt|ass)$/.test(lower.slice(stem.length + 1));
+}
+
+/** Where a Save's files come from, as the page keeps it: the episode Python opened, the folder it
+ * was read from (none for the demo) and the video's name. */
+export type Source = { episode: string; folder: Folder | null; video: string };
+
+/** What the page does with a `write_files` message: writes into the episode's own folder, or
+ * offers downloads where that folder can't be written (Safari, Firefox, the demo), or refuses:
+ * when the files are another episode's than the one whose folder is held (the person opened
+ * another meanwhile), when a writable folder's sidecar wasn't read (nothing to compare it with
+ * before the write, spec §14.6), or when a file isn't one of the video's own. */
+export function writePlan(source: Source | null, message: { episode: string; read: string | null; files: readonly { name: string }[] }): { kind: "write"; folder: Folder } | { kind: "download" } | { kind: "refuse" } {
+  if (!source || source.episode !== message.episode) return { kind: "refuse" };
+  if (!source.folder?.writable) return { kind: "download" };
+  if (message.read === null || !message.files.every((f) => nearby(source.video, f.name))) return { kind: "refuse" };
+  return { kind: "write", folder: source.folder };
 }
 
 /** Bytes as base64, in pieces small enough for String.fromCharCode's arguments. */
@@ -207,9 +249,11 @@ export async function readFiles(folder: Folder, names: readonly string[]): Promi
 }
 
 /** Offers each file as a download (where the browser can't write the folder: Safari, Firefox,
- * the demo), through a blob URL revoked once the click has started it. */
-export function download(files: readonly Written[], doc: Document = document): void {
-  for (const f of files) {
+ * the demo), through a blob URL revoked once the click has started it, a quarter second apart:
+ * some browsers drop clicks that come together. */
+export async function download(files: readonly Written[], doc: Document = document, gap = 250): Promise<void> {
+  for (const [k, f] of files.entries()) {
+    if (k) await new Promise((done) => setTimeout(done, gap));
     const url = URL.createObjectURL(new Blob([f.data]));
     const a = doc.createElement("a");
     a.href = url;
```
```diff
diff --git a/frontend/src/types.ts b/frontend/src/types.ts
index 31ab075..c666492 100644
--- a/frontend/src/types.ts
+++ b/frontend/src/types.ts
@@ -191,9 +191,10 @@ export type FoundItem = { name: string; reads: string[]; problem: string | null
 export type FolderListingMessage = { n: number | null; found: FoundItem[] };
 
 /** The `write_files` message (the browser editor's Save or pick): the files to write, the sidecar
- * first, each as base64; `read`, the SHA-256 of the sidecar as the page last read it (null where
- * it couldn't read it again), which the page checks just before it writes (spec §14.6). */
-export type WriteFilesMessage = { episode: string; n: number | null; sidecar: string; read: string | null; files: { name: string; data: string }[] };
+ * first, each as base64; `sidecar`, its name as the folder spells it, and `read`, its SHA-256 as
+ * the page last read it (null where it couldn't read it again), which the page checks just
+ * before it writes (spec §14.6); `seconds`, how long Python waits for the answer. */
+export type WriteFilesMessage = { episode: string; n: number | null; sidecar: string; read: string | null; seconds: number; files: { name: string; data: string }[] };
 
 /** The `save_result` message: what a Save or a pick wrote, left alone or found in conflict. */
 export type SaveResultMessage = {
```
```diff
diff --git a/frontend/src/components/Editor.tsx b/frontend/src/components/Editor.tsx
index 369d53b..19ccf78 100644
--- a/frontend/src/components/Editor.tsx
+++ b/frontend/src/components/Editor.tsx
@@ -78,13 +78,14 @@ export function Editor({ episode, busy, progress, pathInput, generate, onOpen, p
 
 /** The browser editor's ways in (spec §21): a folder of videos vid2sub made subtitles for, with
  * each episode in it to pick (or why it can't open, as plain text), and the demo, a short
- * public-domain clip with its captions and a translation. */
+ * public-domain clip with its captions and a translation; none while the editor is busy, so a
+ * Save's files can't meet another episode. */
 function PagesStart({ busy, pages }: { busy: Busy; pages: Pages }) {
   return (
     <div className="flex flex-col gap-2" data-testid="pages-start">
       <div className="flex flex-wrap items-center gap-2">
-        <FolderPicker onPicked={pages.onFolder} onError={pages.onError} disabled={busy === "opening" || busy === "saving"} />
-        <button type="button" className={control} onClick={pages.onDemo} disabled={busy === "opening"} data-testid="open-demo">
+        <FolderPicker onPicked={pages.onFolder} onError={pages.onError} disabled={busy !== null} />
+        <button type="button" className={control} onClick={pages.onDemo} disabled={busy !== null} data-testid="open-demo">
           Open the demo
         </button>
         <span className="text-sm text-muted-foreground">a folder of videos vid2sub made subtitles for, or a short public-domain clip</span>
@@ -94,7 +95,7 @@ function PagesStart({ busy, pages }: { busy: Busy; pages: Pages }) {
           {pages.found.length === 0 && <li className="text-sm text-muted-foreground">Nothing in that folder has vid2sub's subtitles.</li>}
           {pages.found.map((item) => (
             <li key={item.name}>
-              <button type="button" className={control} onClick={() => pages.onPick(item)} disabled={item.problem !== null || busy === "opening"} title={item.problem ?? undefined} data-testid="found-episode">
+              <button type="button" className={control} onClick={() => pages.onPick(item)} disabled={item.problem !== null || busy !== null} title={item.problem ?? undefined} data-testid="found-episode">
                 {item.name}{item.problem && ` — ${item.problem}`}
               </button>
             </li>
```
```diff
diff --git a/frontend/src/App.tsx b/frontend/src/App.tsx
index aeed1bb..1e16a62 100644
--- a/frontend/src/App.tsx
+++ b/frontend/src/App.tsx
@@ -7,7 +7,7 @@ import { type DefaultsChange, SettingsDrawer } from "@/components/SettingsDrawer
 import { TopBar } from "@/components/TopBar";
 import { LOST_MESSAGES, type Lost, whyLost } from "@/lib/connection";
 import { type Draft, type DraftStep, addStep, clearDraft, draftKey, draftStorage, dropRetranslation, loadDraft, replayable } from "@/lib/draft";
-import { FAILURES, type Folder, FolderError, download, fromBase64, nearby, quickHash, readFiles, sha256Hex } from "@/lib/folder";
+import { FAILURES, type Folder, FolderError, type Source, download, fromBase64, nearby, quickHash, readFiles, sha256Hex, writePlan } from "@/lib/folder";
 import { type Shown, addNotice, dismissNotice } from "@/lib/notices";
 import { retranslateNotice } from "@/lib/retranslate";
 import { pacer } from "@/lib/sends";
@@ -100,9 +100,17 @@ export default function App() {
   const episodeId = episode?.id ?? null;
   // The browser editor's folder (spec §21, §6.9): its handle lives only here, in this tab's
   // memory, never in storage, so a reload asks for it again. `source` is where the open episode
-  // came from, so a Save writes only into its own folder, and the demo's only downloads.
+  // came from, bound to its id once Python has opened it (`pending` until then), so a Save writes
+  // only into its own folder, never one picked meanwhile, and the demo's only downloads.
   const folder = useRef<Folder | null>(null);
-  const source = useRef<{ folder: Folder | null; video: string } | null>(null);
+  const source = useRef<Source | null>(null);
+  const pending = useRef<Omit<Source, "episode"> | null>(null);
+  useEffect(() => {
+    if (episodeId && pending.current && source.current?.episode !== episodeId) {
+      source.current = { episode: episodeId, ...pending.current };
+      pending.current = null;
+    }
+  }, [episodeId]);
   const blob = useRef<string | null>(null);
   const [found, setFound] = useState<FoundItem[] | null>(null);
   const fail = (err: unknown) => setNotices((shown) => addNotice(shown, { kind: "error", text: FAILURES[err instanceof FolderError ? err.why : "write"] }, nextId.current++));
@@ -145,6 +153,10 @@ export default function App() {
     setFound(null);
     try {
       const names = await picked.names();
+      // The open episode's folder, picked again (it was moved, or its permission lapsed): its
+      // Saves go here now. Python refuses one whose sidecar is another video's.
+      const open = source.current;
+      if (open?.folder && names.includes(open.video)) source.current = { ...open, folder: picked };
       pace(() => setFolder({ names, n: ++sent.current }));
     } catch (err) {
       fail(err);
@@ -159,7 +171,7 @@ export default function App() {
       const [quick, files, names] = await Promise.all([quickHash(video), readFiles(from, item.reads), from.names()]);
       if (blob.current) URL.revokeObjectURL(blob.current);
       blob.current = URL.createObjectURL(video);
-      source.current = { folder: from, video: item.name };
+      pending.current = { folder: from, video: item.name };
       setFound(null);
       pace(() => setOpenFiles({ video: item.name, size: video.size, quick_sha256: quick, url: blob.current ?? "", files, names, n: ++sent.current }));
     } catch (err) {
@@ -167,29 +179,37 @@ export default function App() {
     }
   };
   const onDemo = () => {
-    source.current = { folder: null, video: "" };
+    pending.current = { folder: null, video: "" };
     setDemo({ n: ++sent.current });
   };
-  // A Save's or a pick's files (spec §14.6): written next to the video where the folder is
-  // writable, the sidecar read again first, and if it changed since, sent back for Python to
-  // merge again; else offered as downloads (Safari, Firefox, the demo: S48).
+  // A Save's or a pick's files (spec §14.6): written next to the video where the episode's
+  // folder is writable, the sidecar read again first, and if it changed since, sent back for
+  // Python to merge again; else offered as downloads (Safari, Firefox, the demo: S48); refused
+  // when they aren't the open episode's (writePlan). Nothing starts once Python has stopped
+  // waiting (`seconds`, less a margin).
   useShinyMessageHandler("write_files", (data: WriteFilesMessage) => {
     const answer = (x: Omit<Written, "episode" | "n">) => pace(() => setWritten({ episode: data.episode, n: data.n, ...x }));
+    const deadline = performance.now() + (data.seconds - 15) * 1000;
     const files = data.files.map((f) => ({ name: f.name, data: fromBase64(f.data) }));
-    const into = source.current?.folder;
-    if (!into?.writable) {
-      download(files);
-      answer({ ok: true });
+    const plan = writePlan(source.current, data);
+    if (plan.kind === "refuse") {
+      fail(new FolderError("elsewhere"));
+      answer({ ok: false, why: "elsewhere" });
+      return;
+    }
+    if (plan.kind === "download") {
+      void download(files).then(() => answer({ ok: true }));
       return;
     }
+    const into = plan.folder;
     void (async () => {
       try {
-        if (data.read !== null && (await sha256Hex(await into.file(data.sidecar))) !== data.read) {
+        if ((await sha256Hex(await into.file(data.sidecar))) !== data.read) {
           const again = await fresh();
           answer({ ok: false, why: "changed", files: again.files ?? {}, names: again.names ?? [] });
           return;
         }
-        await into.write(files);
+        await into.write(files, deadline);
         answer({ ok: true });
       } catch (err) {
         fail(err);
```
```diff
diff --git a/docs/superpowers/specs/2026-10-14-vid2sub-design.md b/docs/superpowers/specs/2026-10-14-vid2sub-design.md
index 900c088..16a6510 100644
--- a/docs/superpowers/specs/2026-10-14-vid2sub-design.md
+++ b/docs/superpowers/specs/2026-10-14-vid2sub-design.md
@@ -1039,8 +1039,8 @@ about to be written), then the subtitle files (§15.2). Unsaved edits live in th
   by id, keeping existing order and appending new records) and retry.
 - **A truncated last line** is ignored and reported. **Any other line that doesn't parse** stops
   the write: vid2sub never overwrites a sidecar it can't read, and tells the user.
-- In the Pages editor, the same logic runs in Python on text React hands it; React re-reads the
-  file before writing through the File System Access API (§21).
+- In the Pages editor, the same logic runs in Python on the files' bytes React hands it; React
+  re-reads the file before writing through the File System Access API (§21).
 
 ### 14.7 Size
 
@@ -1314,9 +1314,9 @@ Dan, 2026-10-14: the Pages site is a working subtitle editor with no install, pl
   'readwrite'})` in Chrome and Edge (a file handle has no parent, so the user picks **the
   folder**) and `<input webkitdirectory>` (read-only) in Safari and Firefox.
 - **Python runs in a Web Worker,** so file handles stay in React. React reads the sidecar,
-  subtitle and glossary files as text and hands them to Python; the video plays from a blob URL;
-  video bytes never enter Python (wasm32 has a 4 GB address space). Identity uses a quick hash
-  computed in JS (§8.3).
+  subtitle and glossary files and hands Python their bytes (base64 on the wire, so a projection's
+  hash is of the bytes on disk, §15.2); the video plays from a blob URL; video bytes never enter
+  Python (wasm32 has a 4 GB address space). Identity uses a quick hash computed in JS (§8.3).
 - **Saving:** in Chrome and Edge, Python returns the new file contents and React writes them next
   to the video, re-reading the sidecar first (§14.6). In Safari and Firefox, Save offers downloads
   of the subtitle files and of the whole sidecar.
```

- [ ] **Step 20: Run the checks; they pass, and each guard fails without its fix.** The browser
  tests: `VID2SUB_REQUIRE_FFMPEG=1 uv run pytest tests/test_browser_backend.py
  tests/test_web_browser.py -q`: `45 passed`. In turn: `_read`'s `not TEMPORARY.fullmatch(p.name)`
  made `not p.name.startswith(".")`: `SaveError: couldn't hand back .clip.vid2sub.jsonl,
  .clip.ja.srt: nothing was saved` (the new guard fails closed); the sidecar's `on_disk = next(…)`
  made `on_disk = sidecar if files and sidecar in files else None`: `FAILED
  …test_the_sidecar_is_read_again_as_the_folder_spells_it`; the `WRITE_LATE` notice taken out:
  `FAILED …test_a_page_that_never_answers_saves_nothing_and_says_so`. `cd frontend && npm run
  typecheck && npx vitest run`: `Test Files  21 passed (21)`, `Tests  104 passed (104)`. `make
  pages`, then `make pages-test`: `9 passed`. `make check`: `1103 passed, 2 skipped, 45
  deselected` (twice), `Test Files  21 passed (21)`, `Tests  104 passed (104)`, `All checks
  passed!`, `no leaks found`; `make e2e`: `31 passed`.
- [ ] **Step 21: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
fix(pages): 🤖 the security review's fixes: a dot-named video saves whole, a Save's files reach only its own folder, and a failed write leaves no empty file

The Tier 1 review of Task 3 (an independent subagent, AGENTS.md's security checklist) found one
Critical and seven Important; each is fixed here, with a test that failed without it:

- Critical, escaped from Task 1 (found by Task 3's security review): BrowserBackend's read of the
  staging folder skipped every name starting with "." to skip safe_write's temporary files, so
  `.clip.mkv`'s sidecar and subtitle files never came back while the Save said it had written
  them and the tab dropped its draft. It now skips only `.<name>.<12 hex>.tmp`, and a Save whose
  sidecar or written file the read left out fails ("couldn't hand back …: nothing was saved").
  With the old read: "SaveError: couldn't hand back .clip.vid2sub.jsonl, .clip.ja.srt".
- A Save's files reach only the episode's own folder: the page binds the folder to the episode
  once Python has opened it (no longer at the pick, nor at the demo's click), refuses a
  `write_files` for any other episode, a writable folder's Save with no sidecar read, and a file
  that isn't the video's own (writePlan, tested in Vitest), and the folder picker, the episode
  list and the demo are disabled while the editor is busy.
- The sidecar's re-read uses the folder's own spelling of it (a case-blind disk's
  `show - s01e01.vid2sub.jsonl`), so §14.6's compare isn't skipped: "FAILED
  …test_the_sidecar_is_read_again_as_the_folder_spells_it" without it.
- A page that doesn't answer within five minutes saves nothing and says so (WRITE_LATE); the
  page is told the wait (`seconds`) and starts no write after it, a permission prompt left open
  included: "FAILED …test_a_page_that_never_answers_saves_nothing_and_says_so" without the notice.
- A download Save offers the whole set each time (the sidecar, every subtitle file it projects,
  the glossary), so one the browser blocked comes again with the next Save; downloads go a
  quarter second apart.
- A Save cut short removes the files it created, since getFileHandle's create makes an empty file
  at once, which later Saves would take for someone else's: "expected true to be false" before.
- A folder name with an ideographic space, a no-break space or a joiner no longer refuses the
  folder; a name vid2sub couldn't stage (a separator, a control character) is left out of the
  listing rather than refusing it.
- Picking the open episode's folder again (moved, or its permission lapsed) aims its Save there;
  Python's header check still refuses another video's sidecar. The lost-folder Pages test now
  saves in the same tab.
- And from the review's Minor list: `nearby` reads `<stem>.<code>.srt|ass` and the sidecar
  exactly, not a season's every `S01.E…` file; a "changed" answer without the folder's files
  saves nothing; one comment no longer says a refusal echoes nothing the page sent.
- The spec's §14.6 and §21 said the page hands Python the files as text; it hands their bytes
  (base64 on the wire), so a projection's hash is of the bytes on disk (§15.2).

Left for the phase end (Minor, on its list): only the sidecar is compared before a write (a subtitle file
another program creates in that moment is written over; §14.6 asks for the sidecar only); after
a close fails past the sidecar, the notice says nothing was saved though the sidecar was; on a
case-sensitive disk, vid2sub's spelling beside a case variant of its own file makes a duplicate.
Not verified: Chrome's on-disk create, Safari's and Firefox's handling of several downloads, and
the tab's memory with a multi-gigabyte video (Task 11's exit test, by hand).

Docs read: the WHATWG File System standard's getFileHandle (create makes the entry at once) and
FileSystemDirectoryHandle.removeEntry (MDN); MDN's FileSystemHandle.requestPermission
(transient activation) and performance.now.

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-4.md Task 3
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/web/browser.py src/vid2sub/web/server.py tests/test_browser_backend.py
  tests/test_web_browser.py frontend/src/lib/folder.ts frontend/src/lib/folder.test.ts
  frontend/src/App.tsx frontend/src/types.ts frontend/src/components/Editor.tsx
  tests/pages/test_pages_files.py docs/superpowers/specs/2026-10-14-vid2sub-design.md`, `git
  commit -F .git/COMMIT_MSG`, then `git log -1 --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 22: Review, look forward, close.** The Tier 1 review from
  `$(cat .git/TASK_BASE)` (`AGENTS.md`, *Reviews*: Matt Pocock's `code-review`, two axes in two
  subagents, plus the security checklist, each item a line under `Rounds:`), at most one
  re-review. Worth checking, beyond what the build's own review found (Step 17): no folder
  handle reaches storage (`grep -rn "indexedDB\|localStorage\|sessionStorage\|caches\."
  frontend/src` finds only the draft's and the theme's storage); a Save can write only into the
  folder its episode came from; every refusal echoes nothing the page sent. The forward review
  over Tasks 4, 5, 10 and 11: Task 4's `Watch` replaces `tests/pagesite.py`'s `Errors` in every
  Pages test; Task 5's clip replaces the demo the files tests use as a person's folder (they need
  a video Chromium plays); Task 10's docs say how to open a folder and what Save does in each
  browser; Task 11's Steps 3 and 4 use Open folder, Save and the downloads. The docs this task
  made untrue are fixed in Step 19 (§14.6 and §21: the files' bytes, not text); S48's Proof
  gains `tests/pages/test_pages_files.py` (in Chromium, with `showDirectoryPicker` taken away).
  Then the close, its own commit, holding this plan with this task's boxes ticked and **Now** set
  to `Task 4: No frames, no network: the Pages test, open.`, the spec's S48 row set to `built`,
  with the message in `.git/CLOSE_MSG`:

```text
docs(plan): 🤖 close Task 3: Opening and saving local files in the browser

Drift: none
Rulings: none
Phase-end: none
Forward: none
Tier: 1
Rounds: <the reviews, and one line per security checklist item>
Findings: <the review's, and what became of each>

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-4.md Task 3
Co-Authored-By: <the model's own line>
```

  `git add docs/superpowers/plans/2026-10-23-vid2sub-phase-4.md
  docs/superpowers/specs/2026-10-14-vid2sub-design.md`, `git commit -F .git/CLOSE_MSG`.

***

### Task 4: No frames, no network: the Pages test

**Tier:** 1 · **Scenarios:** S49

**Why it is built this way** (read 2026-10-24):
- **The frame check is the page's first act.** Pages can't send `frame-ancestors` or
  `X-Frame-Options` (spec §6.9), so `pages/site/start.js` checks `window.top !== window.self`
  before it loads anything: in a frame it replaces the page with a sentence saying why, and loads
  no Shinylive, no Pyodide and no folder picker, so a page that framed the editor can't steer a
  person's clicks onto Open folder or Save. Shinylive's own iframe, which runs the app, is the
  page's child, not its parent, so it doesn't count; a direct load of an `app_<id>/` URL has no
  app behind it (Shinylive's service worker serves it only for a page that registered it). The
  check runs in any frame, the same origin's included, since `recordings` and `meanwhile` share
  `chendaniely.github.io`.
- **`?_shinylive-mode=` goes too.** Shinylive's exported page reads it to open its code editor and
  terminal (`runExportedApp`), which would put a Python console on this origin behind a link; the
  site is the editor app, so `start.js` drops the parameter before Shinylive reads it.
- **The Watch is recordings'** (spec §22.7 names it): `page.context.on("request")` sees the page,
  its frames, their workers and Shinylive's service worker (Playwright 1.64's BrowserContext
  `request` event), and a test fails on any request whose origin isn't the site's or whose path
  isn't under `/vid2sub/`. Every Pages test keeps one; a test proves the Watch itself sees a
  request that leaves.
- **The frame test frames the site from another local origin** (another port on `127.0.0.1`), as
  another site would, and checks the framed site asked for nothing but its page and `start.js`.

**Files:**
- Create: `tests/pages/test_pages_origin.py`
- Modify: `pages/site/start.js` (the frame check; `?_shinylive-mode=` dropped),
  `tests/pagesite.py` (`Watch` in place of `Errors`), `tests/pages/test_pages_site.py`,
  `tests/pages/test_pages_files.py`
- Modify at the close: this plan; the spec (S47 and S49 `built`)

**Interfaces:**
- Consumes: Task 2's site and `pages/site/start.js`; Tasks 2 and 3's Pages tests and
  `tests/pagesite.py`.
- Produces: `start.js`'s `FRAMED` text and the `framed` test id; `tests/pagesite.py`'s
  `Watch(page, site_url)` (`errors`, `outside`, `seen`, `assert_clean()`); for Task 7's
  `pages.yml` and CI: `make pages-test` needs a built `_site/` (`make pages`, with ffmpeg until
  Task 5), Playwright's Chromium (`uv run playwright install --with-deps chromium`) and ffmpeg
  for the files tests' episode; it serves the site itself, on `127.0.0.1`, and needs no network
  beyond the site.

The `make check` counts below come from a clone of the finished Phase 2 with only this phase's
Tasks 1 to 4; yours are higher once Phase 3 is in. What matters is no failure, ruff's
`All checks passed!` and gitleaks' `no leaks found`; the new tests' own counts are exact. Each
`diff` block applies with `git apply` from the repository's root (save it to a file first).

- [ ] **Step 0: Record the base:** `git rev-parse HEAD > .git/TASK_BASE`.
- [ ] **Step 1: Write the failing tests,** `tests/pages/test_pages_origin.py`:

```python
"""The Pages origin's rules, in Chromium, on the built site (spec §6.9, §22.7; S49): the editor
refuses to run inside a frame, checked in JS since Pages can't send frame-ancestors, and requests
nothing outside its own files. Run with `make pages`, then `make pages-test`.

Every Pages test watches every request the page, its frames, its workers and Shinylive's service
worker make (tests/pagesite.py's Watch, recordings' Watch, as spec §22.7 names it), and fails on
any that leaves the site or the site's /vid2sub/; these tests check the rules themselves.
"""

import re
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import pytest
from pagesite import BOOT, PREFIX, SITE, Watch, app_frame, boot, built, served
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.pages

FRAMED = ("vid2sub's editor doesn't run inside another page. Open "
          "https://chendaniely.github.io/vid2sub/ in a tab of its own.")


@pytest.fixture(scope="module")
def site_url():
    built()
    server, url = served(SITE)
    try:
        yield url
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture
def framer(tmp_path, site_url):
    """Another local origin (another port) whose page frames the editor, as another site on the
    web, or on chendaniely.github.io itself, could."""
    (tmp_path / "framer.html").write_text(
        f'<!doctype html><title>someone else</title><iframe src="{site_url}" width="800" '
        'height="600"></iframe>', encoding="utf-8")
    handler = partial(type("Quiet", (SimpleHTTPRequestHandler,),
                           {"log_message": lambda *a: None}), directory=str(tmp_path))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/framer.html"
    finally:
        server.shutdown()
        server.server_close()


def test_the_editor_refuses_to_run_inside_another_pages_frame(page: Page, site_url, framer):
    # why: S49 and spec §6.9: a page that framed the editor could steer a person's clicks onto
    # Open folder or Save. In a frame it says why and starts nothing: no Shinylive, no Pyodide.
    asked: list[str] = []
    page.context.on("request", lambda r: asked.append(r.url))
    page.goto(framer)
    inner = page.frame_locator("iframe").first
    expect(inner.get_by_test_id("framed")).to_have_text(FRAMED, timeout=BOOT)
    page.wait_for_timeout(1500)  # long enough for anything start.js would have started
    expect(inner.locator("iframe")).to_have_count(0)  # Shinylive's own frame never came
    site = urlsplit(site_url)
    from_site = sorted(urlsplit(u).path for u in asked if urlsplit(u).netloc == site.netloc)
    assert from_site == ["/vid2sub/", "/vid2sub/start.js"]


def test_out_of_a_frame_it_starts_and_every_request_stays_in_its_own_files(page: Page, site_url):
    # S49: the whole of a visit, the demo played and edited, through the site's own files only.
    watch = Watch(page, site_url)
    paths: list[str] = []
    page.context.on("request", lambda r: paths.append(urlsplit(r.url).path))
    app = boot(page, site_url)
    app.get_by_test_id("open-demo").click()
    expect(app.get_by_test_id("episode-name")).to_have_text("jfk.mp4", timeout=BOOT)
    app.get_by_test_id("media").evaluate("m => { m.muted = true; return m.play(); }")
    app_frame(page).wait_for_function(
        "() => document.querySelector('[data-testid=media]').currentTime > 0.5", timeout=BOOT)
    watch.assert_clean()
    assert watch.seen > 20  # the page, Shinylive, Pyodide, its packages, app.json, the video
    # The context sees the Web Worker's requests too: Pyodide loads its wheels there.
    assert any(p.endswith(".whl") for p in paths) and f"{PREFIX}demo/jfk.mp4" in paths


def test_the_watch_itself_sees_a_request_that_leaves_the_site(page: Page, site_url):
    # why: a watch that saw nothing would pass the tests above whatever the editor asked for.
    watch = Watch(page, site_url)
    boot(page, site_url)
    app_frame(page).evaluate("() => fetch('http://127.0.0.2:9/nothing').catch(() => null)")
    page.wait_for_timeout(500)
    assert watch.outside == ["http://127.0.0.2:9/nothing"]


def test_shinylives_code_editor_is_not_offered(page: Page, site_url):
    # The site is the editor app, not a playground: ?_shinylive-mode= is dropped before
    # Shinylive reads it, so a link can't open its code editor and terminal on this origin.
    watch = Watch(page, site_url)
    app = boot(page, site_url + "?_shinylive-mode=editor-terminal-viewer")
    assert "_shinylive-mode" not in page.url
    expect(app.get_by_test_id("open-demo")).to_be_visible()
    expect(page.locator(".shinylive-editor, .shinylive-terminal")).to_have_count(0)
    watch.assert_clean()


def test_the_page_loads_nothing_by_an_absolute_or_root_path():
    # A URL from the site's root, or another origin's, would leave /vid2sub/ on Pages.
    built()
    for name in ("index.html", "start.js"):
        text = (SITE / name).read_text(encoding="utf-8")
        loads = re.findall(r'(?:src=|href=|import\()"([^"]+)"|^  "([^"]+)",$', text, re.MULTILINE)
        loads = [a or b for a, b in loads]
        assert loads and all(u.startswith("./") for u in loads), (name, loads)
```

  and the Watch, in `tests/pagesite.py` and on every Pages test:

```diff
diff --git a/tests/pagesite.py b/tests/pagesite.py
index fde63a1..450d14b 100644
--- a/tests/pagesite.py
+++ b/tests/pagesite.py
@@ -1,12 +1,14 @@
 """What the Pages browser tests share (tests/pages/; Phase 4 Tasks 2 to 4): the built site, served
 as Pages serves it (scripts/rangeserver.py: under /vid2sub/, answering Range requests, cached for
-ten minutes), the console errors a page reports, and booting the editor, which Shinylive runs in
-an iframe at <site>/app_<id>/ with Python in a Web Worker under Pyodide 0.27.7."""
+ten minutes), the Watch every test keeps on a page (spec §22.7: any console error, and any request
+outside the site's own files, fails it), and booting the editor, which Shinylive runs in an iframe
+at <site>/app_<id>/ with Python in a Web Worker under Pyodide 0.27.7."""
 
 from __future__ import annotations
 
 import importlib.util
 from pathlib import Path
+from urllib.parse import urlsplit
 
 import pytest
 from playwright.sync_api import FrameLocator, Page, expect
@@ -37,13 +39,34 @@ def built() -> None:
         pytest.fail("_site/ isn't built: run make pages first")
 
 
-class Errors:
-    """Every console error and uncaught exception the page, its frames and workers report."""
-
-    def __init__(self, page: Page):
-        self.seen: list[str] = []
-        page.on("console", lambda m: m.type == "error" and self.seen.append(m.text))
-        page.on("pageerror", lambda e: self.seen.append(f"uncaught: {e}"))
+class Watch:
+    """Console errors, and every request that leaves the site's own files: another origin, or
+    the site's origin outside /vid2sub/ (a root-absolute URL, which Pages would answer from
+    another site). As recordings' Watch (packages/ui/tests/pages/test_pages_site.py at 8deb039),
+    which spec §22.7 names: the context sees the page, its frames, their workers and the service
+    worker. A blob: or data: URL is the page's own memory, never a request out (S49)."""
+
+    def __init__(self, page: Page, site_url: str):
+        self.site = urlsplit(site_url)
+        self.errors: list[str] = []
+        self.outside: list[str] = []
+        self.seen = 0
+        page.on("console", lambda m: m.type == "error" and self.errors.append(m.text))
+        page.on("pageerror", lambda e: self.errors.append(f"uncaught: {e}"))
+        page.context.on("request", self._request)
+
+    def _request(self, request) -> None:
+        url = urlsplit(request.url)
+        if url.scheme in ("data", "blob", "about"):
+            return
+        self.seen += 1
+        if url.netloc != self.site.netloc or not url.path.startswith(PREFIX):
+            self.outside.append(request.url)
+
+    def assert_clean(self) -> None:
+        assert self.seen > 0
+        assert not self.errors, f"console errors: {self.errors}"
+        assert not self.outside, f"requests outside the site: {self.outside}"
 
 
 def boot(page: Page, url: str) -> FrameLocator:
```
```diff
diff --git a/tests/pages/test_pages_site.py b/tests/pages/test_pages_site.py
index d53631d..df176c7 100644
--- a/tests/pages/test_pages_site.py
+++ b/tests/pages/test_pages_site.py
@@ -3,7 +3,7 @@ Phase 4 plan's Review Focus 3). Run with `make pages`, then `make pages-test`.
 
 The site is served as Pages serves it (tests/pagesite.py), and each test boots Pyodide from the
 site's own copy; its first boot in a context takes several seconds. Each test fails on any
-console error.
+console error, and on any request outside the site's own files (Phase 4 Task 4's Watch).
 """
 
 import os
@@ -14,7 +14,7 @@ from pathlib import Path
 from urllib.parse import urlsplit
 
 import pytest
-from pagesite import BOOT, PREFIX, RENDER, SITE, Errors, app_frame, boot, built, served
+from pagesite import BOOT, PREFIX, RENDER, SITE, Watch, app_frame, boot, built, served
 from playwright.sync_api import Page, expect
 
 pytestmark = pytest.mark.pages
@@ -34,11 +34,11 @@ def site_url():
 
 
 @pytest.fixture
-def errors(page: Page) -> Errors:
-    return Errors(page)
+def watch(page: Page, site_url) -> Watch:
+    return Watch(page, site_url)
 
 
-def test_the_editor_starts_in_the_browser_with_no_install(page: Page, site_url, errors, capsys):
+def test_the_editor_starts_in_the_browser_with_no_install(page: Page, site_url, watch, capsys):
     began = time.monotonic()
     app = boot(page, site_url)
     with capsys.disabled():
@@ -51,10 +51,10 @@ def test_the_editor_starts_in_the_browser_with_no_install(page: Page, site_url,
     # Hidden in Pages (spec §21): Jobs, the settings drawer, the path box, the engine status.
     for hidden in ("nav-jobs", "open-settings", "open-path", "status"):
         expect(app.get_by_test_id(hidden)).to_have_count(0)
-    assert errors.seen == []
+    watch.assert_clean()
 
 
-def test_the_demo_plays_with_its_captions_and_its_translation(page: Page, site_url, errors):
+def test_the_demo_plays_with_its_captions_and_its_translation(page: Page, site_url, watch):
     # S50: the site's demo (Phase 2's JFK clip until Phase 4 Task 5's), its video the site's
     # own file, its sidecar and subtitles bundled with the app.
     app = boot(page, site_url)
@@ -73,7 +73,7 @@ def test_the_demo_plays_with_its_captions_and_its_translation(page: Page, site_u
     assert src.path == f"{PREFIX}demo/jfk.mp4"  # the site's own copy
     expect(app.get_by_test_id("caption-line")).to_have_text(
         [DEMO_EN, re.compile("^ここに来られて")], timeout=RENDER)
-    assert errors.seen == []
+    watch.assert_clean()
 
 
 def deploy(root: Path, name: str, change) -> None:
@@ -85,8 +85,7 @@ def deploy(root: Path, name: str, change) -> None:
     os.utime(path, (later, later))
 
 
-def test_a_new_deploy_runs_whole_though_the_browser_cached_the_last_one(page: Page, tmp_path,
-                                                                        errors):
+def test_a_new_deploy_runs_whole_though_the_browser_cached_the_last_one(page: Page, tmp_path):
     # why: Review Focus 3: Pages caches each file for ten minutes, and Shinylive and Pyodide keep
     # their files' names from one deploy to the next, so a visitor's second visit took
     # shinylive.js, Pyodide's worker and its runtime from the cache, and only app.json afresh
@@ -97,6 +96,7 @@ def test_a_new_deploy_runs_whole_though_the_browser_cached_the_last_one(page: Pa
     root = tmp_path / "site"
     shutil.copytree(SITE, root)
     server, url = served(root)
+    watch = Watch(page, url)
     try:
         boot(page, url)
         assert page.evaluate("() => globalThis.__deploy") is None
@@ -111,7 +111,7 @@ def test_a_new_deploy_runs_whole_though_the_browser_cached_the_last_one(page: Pa
     finally:
         server.shutdown()
         server.server_close()
-    assert errors.seen == []
+    watch.assert_clean()
 
 
 # Files whose names carry their content's hash or their version can't be mixed across deploys:
```
```diff
diff --git a/tests/pages/test_pages_files.py b/tests/pages/test_pages_files.py
index f96008b..cb07cdc 100644
--- a/tests/pages/test_pages_files.py
+++ b/tests/pages/test_pages_files.py
@@ -20,7 +20,7 @@ from pathlib import Path
 
 import pytest
 from episodes import write_track
-from pagesite import RENDER, SITE, Errors, app_frame, boot, built, served
+from pagesite import RENDER, SITE, Watch, app_frame, boot, built, served
 from playwright.sync_api import FrameLocator, Page, expect
 
 from vid2sub import store
@@ -94,8 +94,8 @@ def episode(tmp_path) -> Path:
 
 
 @pytest.fixture
-def errors(page: Page) -> Errors:
-    return Errors(page)
+def watch(page: Page, site_url) -> Watch:
+    return Watch(page, site_url)
 
 
 def b64(folder: Path) -> dict[str, str]:
@@ -138,7 +138,7 @@ def local_open(folder: Path):
 
 
 def test_a_folder_opened_in_chrome_plays_from_a_blob_url_and_saves_next_to_the_video(
-        page: Page, site_url, episode, tmp_path, errors):
+        page: Page, site_url, episode, tmp_path, watch):
     # S47: picked, listed, read, hashed and played in the page; saved through File System Access.
     page.context.add_init_script(PICKER)
     app = boot(page, site_url)
@@ -159,11 +159,11 @@ def test_a_folder_opened_in_chrome_plays_from_a_blob_url_and_saves_next_to_the_v
     there = local_open(tmp_path / "after")
     assert there.tracks.source[0].text == "I am glad to be here."
     assert b"I am glad to be here." in files[EN]
-    assert errors.seen == []
+    watch.assert_clean()
 
 
 def test_save_keeps_what_another_writer_added_since_the_folder_was_read(
-        page: Page, site_url, episode, tmp_path, errors):
+        page: Page, site_url, episode, tmp_path, watch):
     # S47's "the sidecar re-read first" (spec §14.6): a CLI run translates while the episode is
     # open in the page; the page's Save merges, and both versions are in the folder.
     page.context.add_init_script(PICKER)
@@ -185,11 +185,12 @@ def test_save_keeps_what_another_writer_added_since_the_folder_was_read(
     side = store.load(tmp_path / "after" / "jfk.mp4")[0]
     assert theirs.id in side.renditions() and side.head("ja").rendition == theirs.id
     assert local_open(tmp_path / "after").tracks.source[0].text == "I am glad to be here."
-    assert SIDECAR in files and errors.seen == []
+    assert SIDECAR in files
+    watch.assert_clean()
 
 
 def test_a_folder_safari_can_only_read_is_saved_as_downloads(page: Page, site_url, episode,
-                                                             tmp_path, errors):
+                                                             tmp_path, watch):
     # S48: no showDirectoryPicker (Safari, Firefox): <input webkitdirectory> reads the folder,
     # and Save offers the sidecar and the subtitle files as downloads.
     page.context.add_init_script(NO_PICKER)
@@ -211,12 +212,12 @@ def test_a_folder_safari_can_only_read_is_saved_as_downloads(page: Page, site_ur
     for d in downloads:
         d.save_as(episode / d.suggested_filename)  # what the person does with them
     assert local_open(episode).tracks.source[0].text == "I am glad to be here."
-    assert errors.seen == []
+    watch.assert_clean()
 
 
 @pytest.mark.parametrize("lost", ["permission", "folder"])
 def test_a_folder_lost_mid_edit_saves_nothing_says_why_and_keeps_the_edits(
-        page: Page, site_url, episode, tmp_path, errors, lost):
+        page: Page, site_url, episode, tmp_path, watch, lost):
     # why: Review Focus 1: the folder's permission taken back, or the folder moved, while an
     # episode is open: Save writes nothing half-way, says what happened and to open the folder
     # again, and the edits stay in the tab and its draft; with the folder back, the same tab
@@ -255,4 +256,4 @@ def test_a_folder_lost_mid_edit_saves_nothing_says_why_and_keeps_the_edits(
     expect(app.get_by_test_id("save-state")).to_have_text("All changes saved", timeout=RENDER)
     read_back(page, tmp_path / "saved")
     assert local_open(tmp_path / "saved").tracks.source[0].text == "I am glad to be here."
-    assert errors.seen == []
+    watch.assert_clean()
```

- [ ] **Step 2: Run them; watch them fail.** `make pages`, then `make pages-test`. Expected:
  `2 failed, 12 passed`: the frame test, with `AssertionError: Locator expected to have text
  'vid2sub's editor doesn't run inside another page. Open
  https://chendaniely.github.io/vid2sub/ in a tab of its own.'`, and the mode test, with
  `AssertionError: assert '_shinylive-mode' not in 'http://127....minal-viewer'`. The Watch's
  own tests and every earlier Pages test pass with the Watch on: nothing they did left the site.
- [ ] **Step 3: The frame check,** `pages/site/start.js`:

```js
// Starts the Pages editor (spec §21), as Shinylive 0.10.15's export template does with its inline
// script, unless the page is inside a frame, and once the browser's cache can't mix two deploys.
//
// No frames (spec §6.9, S49): the editor shares chendaniely.github.io with other sites, and Pages
// can't send frame-ancestors or X-Frame-Options, so a page that framed the editor could dress it
// up and steer a person's clicks onto Open folder or Save. So this checks first, before anything
// else loads, and in a frame it says why and stops: no Shinylive, no Pyodide, no folder picker.
// Shinylive's own iframe, which runs the app beside this page, is this page's child, not its
// parent, so it doesn't count. The ?_shinylive-mode= switch to Shinylive's code editor goes too:
// this page is the editor app, not a playground (Phase 4 Task 4).
//
// One deploy at a time (the Phase 4 plan's Review Focus 3): Pages caches every file for ten
// minutes and Shinylive fetches app.json, its own scripts and Pyodide's under names that don't
// change from one deploy to the next, so a visitor who loaded the last deploy could run its
// Shinylive with this one's app.json. So each of those is asked for again first, "no-cache": the
// server answers 304 when it hasn't changed, and the cached copy the app then loads is this
// deploy's. Files whose names carry a hash or a version (Shinylive's chunks, Pyodide's wheels)
// can't be mixed. tests/pages/test_pages_site.py checks this list against the site.
export const REVALIDATE = [
  "./app.json",
  "./shinylive/load-shinylive-sw.js",
  "./shinylive/shinylive.js",
  "./shinylive/shinylive.css",
  "./shinylive/style-resets.css",
  "./shinylive/Editor.js",
  "./shinylive/Editor.css",
  "./shinylive/pyodide-worker.js",
  "./shinylive/pyodide/pyodide.asm.js",
  "./shinylive/pyodide/pyodide.asm.wasm",
  "./shinylive/pyodide/pyodide-lock.json",
  "./shinylive/pyodide/python_stdlib.zip",
];

export const FRAMED =
  "vid2sub's editor doesn't run inside another page. Open https://chendaniely.github.io/vid2sub/ in a tab of its own.";

if (window.top !== window.self) {
  const p = document.createElement("p");
  p.dataset.testid = "framed";
  p.textContent = FRAMED;
  document.body.replaceChildren(p);
} else {
  const url = new URL(window.location.href);
  if (url.searchParams.has("_shinylive-mode")) {
    url.searchParams.delete("_shinylive-mode");
    history.replaceState(null, "", url);
  }
  await Promise.all(REVALIDATE.map((u) => fetch(u, { cache: "no-cache" })));
  for (const href of ["./shinylive/style-resets.css", "./shinylive/shinylive.css"]) {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = href;
    document.head.append(link);
  }
  await import("./shinylive/load-shinylive-sw.js");
  const { runExportedApp } = await import("./shinylive/shinylive.js");
  runExportedApp({ id: "root", appEngine: "python", relPath: "" });
}
```

- [ ] **Step 4: Run the checks; they pass, and the frame test fails without the check.** `make
  pages`, then `make pages-test`: `14 passed`, about 60 s. Then in `_site/start.js` (the built
  copy) make `if (window.top !== window.self) {` read `if (false) {`, run `uv run pytest -m
  pages tests/pages -q -k frame`, and copy `pages/site/start.js` back over it: `E
  AssertionError: Locator expected to have text 'vid2sub's editor doesn't run inside another
  page. …'`, `1 failed`. Then `make check`: `1103 passed, 2 skipped, 50 deselected` (twice),
  `Test Files  21 passed (21)`, `Tests  104 passed (104)`, `All checks passed!`, `no leaks
  found`; and `make e2e`: `31 passed`.
- [ ] **Step 5: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(pages): 🤖 the Pages editor refuses to run inside a frame, and every Pages test fails on a request outside the site's own files

Spec §6.9, §22.7 and S49: the editor shares chendaniely.github.io with recordings and meanwhile,
and Pages can't send frame-ancestors, so it refuses to run in a frame, checked in JS, and touches
no network beyond its own files.

- pages/site/start.js checks `window.top !== window.self` before it loads anything: in a frame
  it replaces the page with one sentence (`framed`: "vid2sub's editor doesn't run inside another
  page. Open https://chendaniely.github.io/vid2sub/ in a tab of its own.") and loads no
  Shinylive, no Pyodide and no folder picker, so a framing page can't steer a person's clicks onto
  Open folder or Save. Shinylive's own iframe is this page's child, so it doesn't count, and an
  app_<id>/ URL loaded alone has no app behind it (Shinylive's service worker answers it only for
  the page that registered it: "Couldn't find parent page", in shinylive-sw.js 0.10.15). Any
  frame is refused, the same origin's included.
- start.js also drops ?_shinylive-mode= before Shinylive reads it (runExportedApp switches to its
  code editor and terminal on it): the site is the editor app, not a playground.
- tests/pagesite.py's Watch replaces Errors on every Pages test, as recordings' Watch (spec §22.7
  names it): console errors, and any request whose origin isn't the site's or whose path isn't
  under /vid2sub/ (blob: and data: are the page's own memory). Playwright's docs say only that a
  context's `request` event covers "any pages created through this context"; the visit test
  shows it sees the Web Worker's requests too (Pyodide's wheels).
- tests/pages/test_pages_origin.py: framed from another local origin (another port), the editor
  says why and the site is asked for nothing but its page and start.js, with no Shinylive frame;
  a whole visit (the demo opened and played) stays inside the site's files, over 20 requests;
  the Watch itself sees a fetch to 127.0.0.2 (a watch that saw nothing would pass the rest);
  ?_shinylive-mode= is dropped and the editor starts; the page and its loader load nothing by an
  absolute or root path.
- They failed first: "2 failed, 12 passed", "AssertionError: Locator expected to have text
  'vid2sub's editor doesn't run inside another page. …'" and "assert '_shinylive-mode' not in
  'http://127....minal-viewer'". With the frame check made `if (false) {` in the built start.js,
  the frame test fails the same way. make pages-test: 14 passed.

Docs read: Playwright 1.64's BrowserContext `request` event and route (service worker notes),
Page.frame_locator; MDN on Window.top, Window.self and Window.frameElement (null for a
cross-origin parent, so not used), and on X-Frame-Options and CSP frame-ancestors (ignored in a
<meta> element, so Pages can't send either); Shinylive 0.10.15's runExportedApp and
shinylive-sw.js.

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-4.md Task 4
Co-Authored-By: <the model's own line>
```

  `git add pages/site/start.js tests/pagesite.py tests/pages/test_pages_site.py
  tests/pages/test_pages_files.py tests/pages/test_pages_origin.py`, `git commit -F
  .git/COMMIT_MSG`, then `git log -1 --format='%(trailers)'` shows `Plan:`.

#### Round 4b: the security review, and its fixes

- [ ] **Step 6: The security review.** One independent reviewer (a subagent) over `git diff
  $(cat .git/TASK_BASE) HEAD` with `AGENTS.md`'s security checklist, spec §6.9, §22.7 and S49,
  free to write throwaway Playwright probes outside the repository. At this listing's build it
  found one Critical (a page on another origin that opened the editor with `window.open` could
  run Python in it through Shinylive's unchecked `openChannel` message, and send a person's
  subtitles away), two Important (the Watch didn't see WebSockets; a full Chrome asks for
  `/favicon.ico` at the origin's root) and three Minor (the `?webworker=0` parameter; the frame
  test's own list; the same-origin limit unsaid). Each is fixed here.
- [ ] **Step 7: Write the failing tests.** In `tests/pages/test_pages_origin.py` and
  `tests/pagesite.py`:

```diff
diff --git a/tests/pages/test_pages_origin.py b/tests/pages/test_pages_origin.py
index 8e8f17a..68e31e3 100644
--- a/tests/pages/test_pages_origin.py
+++ b/tests/pages/test_pages_origin.py
@@ -37,10 +37,15 @@ def site_url():
 @pytest.fixture
 def framer(tmp_path, site_url):
     """Another local origin (another port) whose page frames the editor, as another site on the
-    web, or on chendaniely.github.io itself, could."""
+    web could, and which can open it in a window of its own (`opener.html`). A page on
+    chendaniely.github.io itself is the editor's own origin, and can script it in a frame or
+    not: the JS check stops other origins (spec §6.10 gives the later "B" an origin of its
+    own for that reason)."""
     (tmp_path / "framer.html").write_text(
         f'<!doctype html><title>someone else</title><iframe src="{site_url}" width="800" '
         'height="600"></iframe>', encoding="utf-8")
+    (tmp_path / "opener.html").write_text("<!doctype html><title>someone else</title>",
+                                          encoding="utf-8")
     handler = partial(type("Quiet", (SimpleHTTPRequestHandler,),
                            {"log_message": lambda *a: None}), directory=str(tmp_path))
     server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
@@ -56,15 +61,45 @@ def test_the_editor_refuses_to_run_inside_another_pages_frame(page: Page, site_u
     # why: S49 and spec §6.9: a page that framed the editor could steer a person's clicks onto
     # Open folder or Save. In a frame it says why and starts nothing: no Shinylive, no Pyodide.
     asked: list[str] = []
+    errors: list[str] = []
     page.context.on("request", lambda r: asked.append(r.url))
+    page.on("console", lambda m: m.type == "error" and errors.append(m.text))
     page.goto(framer)
     inner = page.frame_locator("iframe").first
     expect(inner.get_by_test_id("framed")).to_have_text(FRAMED, timeout=BOOT)
     page.wait_for_timeout(1500)  # long enough for anything start.js would have started
     expect(inner.locator("iframe")).to_have_count(0)  # Shinylive's own frame never came
-    site = urlsplit(site_url)
-    from_site = sorted(urlsplit(u).path for u in asked if urlsplit(u).netloc == site.netloc)
-    assert from_site == ["/vid2sub/", "/vid2sub/start.js"]
+    site, other = urlsplit(site_url).netloc, urlsplit(framer).netloc
+    assert all(urlsplit(u).netloc in (site, other) for u in asked), asked
+    from_site = sorted(urlsplit(u).path for u in asked if urlsplit(u).netloc == site)
+    assert from_site == ["/vid2sub/", "/vid2sub/start.js"] and errors == []
+
+
+# Shinylive 0.10.15's top page runs `"<appName>" in _shiny_app_registry` in Python for an
+# "openChannel" message from any window (shinylive.js, ensureOpenChannelListener); this appName
+# would make that Python fetch from another host, and with it a person's subtitles.
+REACH_IN = 'x" in {} or __import__("js").fetch("http://127.0.0.2:9/leak") or "y'
+
+
+def test_a_page_that_opened_the_editor_cant_reach_into_it(page: Page, site_url, framer):
+    # why: the Task 4 security review's Critical: a page on another origin that opened the editor
+    # with window.open (Pages sends no Cross-Origin-Opener-Policy, so it keeps the reference)
+    # could post Shinylive an "openChannel" message that runs Python in the editor. start.js
+    # drops every message from another origin before Shinylive hears it.
+    opener = framer.replace("framer.html", "opener.html")
+    page.goto(opener)
+    with page.expect_popup() as popped:
+        page.evaluate("u => { window.editor = window.open(u); }", site_url)
+    editor = popped.value
+    app = editor.frame_locator("iframe").first
+    expect(app.get_by_test_id("engine")).to_have_text("Browser editor", timeout=BOOT)
+    asked: list[str] = []
+    page.context.on("request", lambda r: asked.append(r.url))
+    page.evaluate("name => window.editor.postMessage({ type: 'openChannel', appName: name, "
+                  "path: '/websocket/' }, '*')", REACH_IN)
+    editor.wait_for_timeout(3000)
+    assert [u for u in asked if "127.0.0.2" in u] == []
+    expect(app.get_by_test_id("open-demo")).to_be_visible()  # the editor still works
 
 
 def test_out_of_a_frame_it_starts_and_every_request_stays_in_its_own_files(page: Page, site_url):
@@ -84,31 +119,37 @@ def test_out_of_a_frame_it_starts_and_every_request_stays_in_its_own_files(page:
     assert any(p.endswith(".whl") for p in paths) and f"{PREFIX}demo/jfk.mp4" in paths
 
 
-def test_the_watch_itself_sees_a_request_that_leaves_the_site(page: Page, site_url):
-    # why: a watch that saw nothing would pass the tests above whatever the editor asked for.
+def test_the_watch_itself_sees_a_request_or_a_websocket_that_leaves_the_site(page: Page,
+                                                                            site_url):
+    # why: a watch that saw nothing would pass the tests above whatever the editor asked for;
+    # a WebSocket isn't a request Playwright's `request` event reports (the Task 4 review).
     watch = Watch(page, site_url)
     boot(page, site_url)
     app_frame(page).evaluate("() => fetch('http://127.0.0.2:9/nothing').catch(() => null)")
-    page.wait_for_timeout(500)
-    assert watch.outside == ["http://127.0.0.2:9/nothing"]
+    app_frame(page).evaluate("() => { new WebSocket('ws://127.0.0.2:9/socket'); }")
+    page.wait_for_timeout(1000)
+    assert sorted(watch.outside) == ["http://127.0.0.2:9/nothing", "ws://127.0.0.2:9/socket"]
 
 
 def test_shinylives_code_editor_is_not_offered(page: Page, site_url):
-    # The site is the editor app, not a playground: ?_shinylive-mode= is dropped before
-    # Shinylive reads it, so a link can't open its code editor and terminal on this origin.
+    # The site is the editor app, not a playground: the query string is dropped before Shinylive
+    # reads it, so a link can't open its code editor and terminal on this origin
+    # (?_shinylive-mode=) or move Python off its Web Worker (?webworker=0).
     watch = Watch(page, site_url)
-    app = boot(page, site_url + "?_shinylive-mode=editor-terminal-viewer")
-    assert "_shinylive-mode" not in page.url
+    app = boot(page, site_url + "?_shinylive-mode=editor-terminal-viewer&webworker=0")
+    assert urlsplit(page.url).query == ""
     expect(app.get_by_test_id("open-demo")).to_be_visible()
     expect(page.locator(".shinylive-editor, .shinylive-terminal")).to_have_count(0)
     watch.assert_clean()
 
 
 def test_the_page_loads_nothing_by_an_absolute_or_root_path():
-    # A URL from the site's root, or another origin's, would leave /vid2sub/ on Pages.
+    # A URL from the site's root, or another origin's, would leave /vid2sub/ on Pages. The page
+    # names its icon, or a browser asks for /favicon.ico, another site's file on Pages.
     built()
     for name in ("index.html", "start.js"):
         text = (SITE / name).read_text(encoding="utf-8")
         loads = re.findall(r'(?:src=|href=|import\()"([^"]+)"|^  "([^"]+)",$', text, re.MULTILINE)
         loads = [a or b for a, b in loads]
-        assert loads and all(u.startswith("./") for u in loads), (name, loads)
+        assert loads and all(u.startswith(("./", "data:")) for u in loads), (name, loads)
+    assert '<link rel="icon" href="data:," />' in (SITE / "index.html").read_text(encoding="utf-8")
```
```diff
diff --git a/tests/pagesite.py b/tests/pagesite.py
index 450d14b..f2f64bb 100644
--- a/tests/pagesite.py
+++ b/tests/pagesite.py
@@ -44,7 +44,9 @@ class Watch:
     the site's origin outside /vid2sub/ (a root-absolute URL, which Pages would answer from
     another site). As recordings' Watch (packages/ui/tests/pages/test_pages_site.py at 8deb039),
     which spec §22.7 names: the context sees the page, its frames, their workers and the service
-    worker. A blob: or data: URL is the page's own memory, never a request out (S49)."""
+    worker, and a WebSocket, which isn't a request to Playwright, is checked too (`websocket`).
+    A blob: or data: URL is the page's own memory, never a request out (S49). No request
+    listener sees a preconnect or WebRTC; nothing in the bundle uses either."""
 
     def __init__(self, page: Page, site_url: str):
         self.site = urlsplit(site_url)
@@ -53,15 +55,16 @@ class Watch:
         self.seen = 0
         page.on("console", lambda m: m.type == "error" and self.errors.append(m.text))
         page.on("pageerror", lambda e: self.errors.append(f"uncaught: {e}"))
-        page.context.on("request", self._request)
+        page.context.on("request", lambda r: self._url(r.url))
+        page.on("websocket", lambda ws: self._url(ws.url))
 
-    def _request(self, request) -> None:
-        url = urlsplit(request.url)
+    def _url(self, address: str) -> None:
+        url = urlsplit(address)
         if url.scheme in ("data", "blob", "about"):
             return
         self.seen += 1
         if url.netloc != self.site.netloc or not url.path.startswith(PREFIX):
-            self.outside.append(request.url)
+            self.outside.append(address)
 
     def assert_clean(self) -> None:
         assert self.seen > 0
```

  Run them on the site as it is: `uv run pytest -m pages tests/pages/test_pages_origin.py -q`:
  `3 failed, 3 passed`: `AssertionError: assert ['http://127.0.0.2:9/leak'] == []` (the opener
  reached in), `AssertionError: assert 'webworker=0' == ''` and the icon's assertion. The Watch's
  WebSocket test passes at once: the Watch's fix is in `tests/pagesite.py` itself.
- [ ] **Step 8: The fixes,** in `pages/site/start.js` and `pages/site/index.html`:

```diff
diff --git a/pages/site/start.js b/pages/site/start.js
index b9cd49a..0081ffa 100644
--- a/pages/site/start.js
+++ b/pages/site/start.js
@@ -6,8 +6,16 @@
 // up and steer a person's clicks onto Open folder or Save. So this checks first, before anything
 // else loads, and in a frame it says why and stops: no Shinylive, no Pyodide, no folder picker.
 // Shinylive's own iframe, which runs the app beside this page, is this page's child, not its
-// parent, so it doesn't count. The ?_shinylive-mode= switch to Shinylive's code editor goes too:
-// this page is the editor app, not a playground (Phase 4 Task 4).
+// parent, so it doesn't count. The check stops other origins; a page on chendaniely.github.io
+// itself is this page's origin and could script it anyway (§6.10 gives "B" an origin of its own).
+//
+// No other window may talk to it either: Shinylive's top-page listener runs Python on an
+// "openChannel" message from any window (shinylive.js, ensureOpenChannelListener), and a page on
+// another origin that opened this one with window.open keeps the reference (Pages sends no
+// Cross-Origin-Opener-Policy). So a listener registered before Shinylive's, capturing, drops
+// every message from another origin. And the query string goes before Shinylive reads it: this
+// page is the editor app, not a playground (?_shinylive-mode=, its code editor; ?webworker=0,
+// Python off its Web Worker) (Phase 4 Task 4 and its security review).
 //
 // One deploy at a time (the Phase 4 plan's Review Focus 3): Pages caches every file for ten
 // minutes and Shinylive fetches app.json, its own scripts and Pyodide's under names that don't
@@ -40,10 +48,11 @@ if (window.top !== window.self) {
   p.textContent = FRAMED;
   document.body.replaceChildren(p);
 } else {
-  const url = new URL(window.location.href);
-  if (url.searchParams.has("_shinylive-mode")) {
-    url.searchParams.delete("_shinylive-mode");
-    history.replaceState(null, "", url);
+  window.addEventListener("message", (event) => {
+    if (event.origin !== window.location.origin) event.stopImmediatePropagation();
+  }, true);
+  if (window.location.search) {
+    history.replaceState(null, "", window.location.pathname + window.location.hash);
   }
   await Promise.all(REVALIDATE.map((u) => fetch(u, { cache: "no-cache" })));
   for (const href of ["./shinylive/style-resets.css", "./shinylive/shinylive.css"]) {
```
```diff
diff --git a/pages/site/index.html b/pages/site/index.html
index 1ef669f..29e10d4 100644
--- a/pages/site/index.html
+++ b/pages/site/index.html
@@ -9,8 +9,11 @@
     <!-- Shinylive 0.10.15's export template, with its scripts and stylesheets loaded by
          start.js, which revalidates the deploy's files first (Phase 4 Task 2). -->
     <script src="./start.js" type="module"></script>
+    <!-- No icon file: a browser would ask for /favicon.ico, another site's file on Pages. -->
+    <link rel="icon" href="data:," />
   </head>
   <body>
+    <noscript><p>vid2sub's editor needs JavaScript, and runs only in a tab of its own.</p></noscript>
     <div style="height: 100vh; width: 100vw" id="root"></div>
   </body>
 </html>
```

- [ ] **Step 9: Run the checks; they pass.** `make pages`, then `uv run pytest -m pages
  tests/pages/test_pages_origin.py -q`: `6 passed`; `make pages-test`: `15 passed`, about 67 s;
  `make check`: `1103 passed, 2 skipped, 51 deselected` (twice), `Test Files  21 passed (21)`,
  `Tests  104 passed (104)`, `All checks passed!`, `no leaks found`; `make e2e`: `31 passed`.
- [ ] **Step 10: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
fix(pages): 🤖 the security review's fixes: no other window can reach into the editor, the Watch sees WebSockets, and the page asks for no icon outside the site

The Tier 1 review of Task 4 (an independent subagent, AGENTS.md's security checklist) found one
Critical, two Important and three Minor; each is fixed here:

- Critical (found by Task 4's security review): Shinylive 0.10.15's top page runs
  `"<appName>" in _shiny_app_registry` in Python for an "openChannel" message from any window
  (shinylive.js's ensureOpenChannelListener checks neither the origin nor the source, and pastes
  appName into the Python it runs). A page on another origin that opened the editor with
  window.open keeps the reference (Pages sends no Cross-Origin-Opener-Policy), so one message ran
  Python in the editor, which could send a person's subtitles anywhere: the reviewer's probe sent
  the open episode's first cue to 127.0.0.2. start.js now registers, before Shinylive loads, a
  capturing `message` listener that stops every message from another origin.
  test_a_page_that_opened_the_editor_cant_reach_into_it opens the editor from another local
  origin and posts the message; before the fix: "assert ['http://127.0.0.2:9/leak'] == []".
  Worth reporting upstream to Shinylive (not done: it's outside this repository).
- Important: the Watch didn't see WebSockets (not requests to Playwright); it now checks every
  WebSocket's URL too, and its own test opens one to 127.0.0.2.
- Important: a full Chrome asks for /favicon.ico at the origin's root, another site's file on
  Pages (the headless shell the tests run doesn't); index.html now names a `data:` icon, and the
  loader test requires it.
- Minor: the whole query string is dropped before Shinylive reads it (?webworker=0 moved Python
  onto the page's thread, against spec §21's Web Worker), not just ?_shinylive-mode=; the frame
  test checks every request is the framer's or the site's and that nothing errs; start.js and
  the test say the check stops other origins, while a page on chendaniely.github.io itself could
  script the editor anyway (spec §6.10's own origin for "B"); a <noscript> line says why a frame
  sandboxed without scripts is blank.

Not verified: Pages' real headers (no COOP; Access-Control-Allow-Origin), and the browser's
partitioning of Shinylive's service worker for a cross-site framer.

Docs read: Shinylive 0.10.15's shinylive.js (ensureOpenChannelListener; the webworker URL
parameter; runExportedApp always passing startFiles, so #code= and #gist= aren't reachable);
Playwright 1.64's Page `websocket` event and Page.expect_popup; MDN on Window.postMessage and
MessageEvent.origin, EventTarget.addEventListener's capture option and
Event.stopImmediatePropagation, Cross-Origin-Opener-Policy, and <link rel="icon">.

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-4.md Task 4
Co-Authored-By: <the model's own line>
```

  `git add pages/site/start.js pages/site/index.html tests/pagesite.py
  tests/pages/test_pages_origin.py`, `git commit -F .git/COMMIT_MSG`, then `git log -1
  --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 11: Review, look forward, close.** The Tier 1 review from
  `$(cat .git/TASK_BASE)` (`AGENTS.md`, *Reviews*: Matt Pocock's `code-review`, two axes in two
  subagents, plus the security checklist, each item a line under `Rounds:`), at most one
  re-review. Worth checking: nothing in `pages/site/` or `_site/index.html` loads by an absolute
  or root path; the frame check and the message filter run before any import; a Shinylive
  upgrade must re-check its window `message` listeners (`ensureOpenChannelListener`) against
  the filter, and the unchecked listener is worth reporting upstream (Dan's call: it's outside
  the repository). The forward review over Tasks 5, 7, 10
  and 11: Task 5's clip keeps the Watch clean (its video at `_site/demo/`); Task 7's `pages.yml`
  runs `make pages-test` on pull requests and before every deploy, with Playwright's Chromium
  and ffmpeg installed, and fails the deploy on any failure; Task 10's docs say the editor
  refuses to run in a frame; Task 11's Step 2 notes the browser console has no error. Then the
  close, its own commit, holding this plan with this task's boxes ticked and **Now** set to
  `Task 5: The demo clip, open.`, the spec's S47 and S49 rows set to `built` (S47's Proof the Pages
  tests in `tests/pages/` and the exit test; S49's `tests/pages/test_pages_origin.py` and every
  Pages test's Watch), with the message in `.git/CLOSE_MSG`:

```text
docs(plan): 🤖 close Task 4: No frames, no network: the Pages test

Drift: none
Rulings: none
Phase-end: none
Forward: none
Tier: 1
Rounds: <the reviews, and one line per security checklist item>
Findings: <the review's, and what became of each>

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-4.md Task 4
Co-Authored-By: <the model's own line>
```

  `git add docs/superpowers/plans/2026-10-23-vid2sub-phase-4.md
  docs/superpowers/specs/2026-10-14-vid2sub-design.md`, `git commit -F .git/CLOSE_MSG`.

***

### Task 5: The demo clip

**Tier:** 3 · **Scenarios:** S50 · Step 1 is **[Dan]**: choosing the public-domain clip

**Interfaces:**
- Consumes: Task 2's `build_pages.demo_folder()`, which makes `demo/` with `web.demo.prepare`
  (Phase 2's JFK clip muxed by ffmpeg, so `make pages` needs ffmpeg until this task); once the
  clip is committed, `demo/` is copied instead, and its sidecar's header names the clip. The tests
  that name `jfk.mp4`, `DEMO_EN` or the Japanese line, and `EXEMPT`'s `demo/jfk.mp4`, change with
  the clip; `tests/pages/test_pages_files.py` uses `prepare`'s VP9 and Opus episode as a
  person's folder and needs a video Chromium plays. The demo opens from the app bundle, plays
  from `../demo/<name>`, and its Save downloads (Task 3).

<!-- steps: written in the next pass -->

***

### Task 6: The Pyodide job

**Tier:** 3 · **Scenarios:** S53

Spec §22.6 and S53: the pure packages' tests run inside the real Pyodide 0.27.7 (Python 3.12.7,
pydantic 2.10.5), the version §21 pins through Shinylive 0.8.12, in CI's `pyodide` job and in
`make test-pyodide`.

**Why it is built this way** (read 2026-10-24):
- **Node with the `pyodide` npm package, not pyodide-build's `pyodide venv`.** Pyodide 0.27.7's
  "Building and testing Python packages out of tree" runs pytest through `pyodide venv`, which
  needs pyodide-build in a host Python matched to Pyodide's, plus Node. The npm package needs only
  the Node the frontend already pins (`frontend/.nvmrc`), and its lockfile pins the package by
  integrity: the smallest harness that runs on ubuntu-24.04, and the Node harness §22.6
  describes. It is a frontend dev dependency (the frontend's is the only npm project), and the
  ubuntu-24.04 runner needs nothing beyond checkout and setup-node.
- **Which tests:** every `tests/test_*.py` whose imports are the pure packages, the standard
  library and what the run installs. 19 files at this listing's build: `test_build`,
  `test_catalog`, `test_edit`, `test_formats`, `test_glossary`, `test_hostile_fixtures`,
  `test_langs`, `test_model`, `test_naming`, `test_parse_openai_qwen`, `test_parse_whispercpp`,
  `test_parse_words`, `test_readme`, `test_rendition`, `test_rules_lint`, `test_scripts`,
  `test_sidecar`, `test_text`, `test_translate_shape` (199 tests, the same 199 the host runs for
  them). They are picked by their imports, not listed, so a new pure test (Phase 3's parser test
  among them) joins without an edit; the floor job's list, by contrast, lacks `test_edit.py` and
  `test_hostile_fixtures.py` (see the close).
- **What Pyodide gets:** its own `micropip`, `pydantic` 2.10.5, `pytest` 8.1.1 and `jsonschema`
  (for `test_rendition.py`'s contract checks), loaded from its CDN and cached in
  `frontend/node_modules/pyodide`, as Pages has them; from PyPI through micropip, uv.lock's
  pysubs2, opencc-purepy and charset-normalizer (read from `uv.lock` inside Pyodide, so they
  follow the lock; Pyodide's own charset-normalizer is 3.3.2, below `pyproject.toml`'s `>=3.4`),
  and hypothesis 6.155.7: hypothesis 6.156.0 and later ship compiled wheels only, with none for
  Pyodide 0.27 (cp312, `pyodide_2024_0`), read from PyPI's JSON. micropip 0.9.0 checks each
  PyPI wheel's sha256 against the index's (`_validate_sha256_checksum`, in its source). Task 2
  vendors its own wheels for the site; this job doesn't use them.
- **Nothing is written into the checkout:** it is mounted at `/repo` (`mountNodeFS`), bytecode
  is off, and pytest and hypothesis work in `/tmp` inside Pyodide's memory.
- **Network:** Pyodide's CDN and PyPI, so `make check` leaves it out, as it leaves out `make e2e`;
  it runs by its own target. About 9 s with a cold package cache.

**Files:**
- Create: `frontend/scripts/pyodide-test.mjs`, `tests/pyodide_run.py`
- Modify: `Makefile` (`test-pyodide`), `.github/workflows/ci.yml` (the `pyodide` job); Task 1
  already added `pyodide` 0.27.7, exact, to `frontend/package.json` and its lock
- Modify at the close: this plan; the spec (S53)

**Interfaces:**
- Consumes: Phase 2 Task 12's `frontend/` (Node 22 from `.nvmrc`, `package-lock.json`, the
  Makefile's `$(NVM)` and `FRONTEND`); Phase 2 Task 21's pins (checkout v7.0.1, setup-node
  v7.1.0) and `make actionlint`; `uv.lock`'s `[[package]]` versions of pysubs2, opencc-purepy
  and charset-normalizer; the tests' imports.
- Produces:
  - `make test-pyodide`: `cd frontend && node scripts/pyodide-test.mjs`; exits with pytest's
    code. Arguments after the script go to pytest (`cd frontend && node scripts/pyodide-test.mjs
    -k wrap`).
  - CI job `pyodide` (ubuntu-24.04, 10 minutes, `contents: read`): checkout, setup-node from
    `frontend/.nvmrc`, `npm ci` in `frontend/`, `make test-pyodide`.
  - `tests/pyodide_run.py`: `pure(path) -> bool`, `imports(path) -> set[str]`, `async
    main(args) -> int`, `HYPOTHESIS = "hypothesis==6.155.7"`, `LOCKED`, `INSTALLED`, `PURE`.
  - The harness refuses any Pyodide but Task 1's devDependency `"pyodide": "0.27.7"`.

The `make check` counts below come from a clone with Phase 2's Tasks 2–16 and 21 only; yours
are higher. What matters is no failure, ruff's `All checks passed!` and gitleaks'
`no leaks found`; `make test-pyodide`'s file list grows with every pure test added since.

- [ ] **Step 0: Record the base:** `git rev-parse HEAD > .git/TASK_BASE`.
- [ ] **Step 1: Watch the target fail.** `make test-pyodide`. Expected (GNU make 3.81):
  ``make: *** No rule to make target `test-pyodide'.  Stop.``
- [ ] **Step 2: Check Pyodide is already a frontend dev dependency.** Task 1 added it:
  `grep '"pyodide": "0.27.7"' frontend/package.json` prints the line, and `cd frontend && npm ci`
  installs it.
- [ ] **Step 3: The harness,** `frontend/scripts/pyodide-test.mjs`:

```js
// Run the pure packages' tests inside Pyodide 0.27.7, the Pyodide the Pages editor runs on (spec
// §21's Shinylive 0.8.12 pin, §22.6, S53): Node with the pyodide npm package, the smallest harness
// that runs on CI's ubuntu-24.04 (no pyodide-build, no browser). The repository is mounted at
// /repo; tests/pyodide_run.py picks the test files, installs what they need and runs pytest.
// Pyodide's own packages (pydantic, pytest, micropip) come from its CDN and are cached in
// node_modules/pyodide; the rest come from PyPI through micropip. Run with `make test-pyodide`;
// extra arguments go to pytest.
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { loadPyodide, version } from "pyodide";

const PYODIDE = "0.27.7";
if (version !== PYODIDE) {
  console.error(`Pyodide ${PYODIDE} is required, as spec §21 pins it (found ${version})`);
  process.exit(1);
}

const repo = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const pyodide = await loadPyodide();
pyodide.mountNodeFS("/repo", repo);
await pyodide.loadPackage(["micropip", "pydantic", "pytest", "jsonschema"]);
pyodide.runPython(readFileSync(resolve(repo, "tests/pyodide_run.py"), "utf8"));
const code = await pyodide.globals.get("main")(pyodide.toPy(process.argv.slice(2)));
process.exit(code);
```

- [ ] **Step 4: What runs inside Pyodide,** `tests/pyodide_run.py` (not a test module: pytest on
  the host never collects it, and ruff lints it with the rest of `tests/`):

```python
"""Runs the pure packages' tests inside Pyodide: every tests/test_*.py that imports nothing of
vid2sub beyond vid2sub.subs, vid2sub.parse and vid2sub.catalog, and nothing else beyond the
standard library and what this run installs (spec §21, §22.6, S53).

Why: the Pages editor runs those packages in Pyodide 0.27.7 (Python 3.12.7, pydantic 2.10.5),
where a module the host has may be missing or behave differently, so their tests run there too.
The files are picked by their imports rather than listed, so a new pure test joins without an
edit. pydantic, pytest and jsonschema are Pyodide's own builds, as Pages has them; pysubs2,
opencc-purepy and charset-normalizer are uv.lock's versions from PyPI (Pyodide's
charset-normalizer is 3.3.2, older than pyproject.toml allows); hypothesis is pinned below.

Loaded by frontend/scripts/pyodide-test.mjs (`make test-pyodide`) with the repository mounted at
/repo; it is not a test module, and the host's pytest never collects it.
"""

from __future__ import annotations

import ast
import os
import sys
import tomllib
from pathlib import Path

import micropip
import pytest

REPO = Path("/repo")
PURE = ("vid2sub.subs", "vid2sub.parse", "vid2sub.catalog")
# What a picked file may import besides the standard library and the pure packages.
INSTALLED = {"pytest", "hypothesis", "pydantic", "pysubs2", "opencc_purepy",
             "charset_normalizer", "jsonschema"}
LOCKED = ("pysubs2", "opencc-purepy", "charset-normalizer")
# hypothesis 6.156.0 and later ship compiled wheels only, with none for Pyodide 0.27 (cp312,
# pyodide_2024_0); 6.155.7 is the newest pure-Python release.
HYPOTHESIS = "hypothesis==6.155.7"


def imports(path: Path) -> set[str]:
    """Every module `path` imports, at any depth; `from vid2sub import subs` counts as
    vid2sub.subs."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add(node.module)
            if node.module == "vid2sub":
                found |= {f"vid2sub.{alias.name}" for alias in node.names}
    return found


def allowed(module: str) -> bool:
    top = module.split(".")[0]
    if top == "vid2sub":
        return module == "vid2sub" or any(
            module == p or module.startswith(p + ".") for p in PURE)
    return top in sys.stdlib_module_names or top in INSTALLED


def pure(path: Path) -> bool:
    found = imports(path)
    return any(m.startswith("vid2sub.") for m in found) and all(allowed(m) for m in found)


async def main(args: list[str]) -> int:
    lock = tomllib.loads((REPO / "uv.lock").read_text(encoding="utf-8"))
    versions = {p["name"]: p["version"] for p in lock["package"]}
    await micropip.install([f"{name}=={versions[name]}" for name in LOCKED] + [HYPOTHESIS])
    files = sorted(p for p in (REPO / "tests").glob("test_*.py") if pure(p))
    print(f"Python {sys.version.split()[0]} in Pyodide: {len(files)} test files: "
          + " ".join(p.name for p in files), flush=True)
    sys.dont_write_bytecode = True  # nothing written into the mounted checkout
    sys.path.insert(0, str(REPO / "src"))
    os.makedirs("/tmp/run", exist_ok=True)
    os.chdir("/tmp/run")  # pytest's and hypothesis' working files stay in Pyodide's memory
    return int(pytest.main(["-c", str(REPO / "pyproject.toml"), "--rootdir", str(REPO),
                            "-p", "no:cacheprovider", *args, *map(str, files)]))
```

- [ ] **Step 5: The target.** In the `Makefile`, add `test-pyodide` to the `.PHONY:` line after
  `test-js`, and below the `test-js:` target's recipe add (the recipe line starts with a tab):

```make

test-pyodide: ## Run the pure packages' tests inside Pyodide 0.27.7, as Pages runs them (needs network)
	cd $(FRONTEND) && $(NVM) node scripts/pyodide-test.mjs
```

- [ ] **Step 6: The job.** In `.github/workflows/ci.yml`, insert above the line `  frontend:`
  (spec §23.2's order: `python`, `floor`, `pyodide`, `frontend`, `e2e`, `leaks`):

```yaml
  pyodide:
    # The pure packages' tests inside Pyodide 0.27.7, the Pages editor's (spec §21, §22.6, S53),
    # through Node and the pyodide npm package; Pyodide's packages come from its CDN, the rest
    # from PyPI (tests/pyodide_run.py).
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with: { persist-credentials: false }
      - uses: actions/setup-node@949feb2413d6458794dcd2491c4babbbce0c15c1 # v7.1.0
        with: { node-version-file: frontend/.nvmrc, cache: npm, cache-dependency-path: frontend/package-lock.json }
      - run: npm ci
        working-directory: frontend
      - run: make test-pyodide
```

- [ ] **Step 7: Run it; it passes.** `make test-pyodide`. Expected, among the package-loading
  lines (`Package pydantic-2.10.5-py3-none-any.whl loaded from
  https://cdn.jsdelivr.net/pyodide/v0.27.7/full/, caching the wheel in node_modules for future
  use.` and the like, on the first run):
  `Python 3.12.7 in Pyodide: 19 test files: test_build.py test_catalog.py test_edit.py ...
  test_translate_shape.py`, `platform emscripten -- Python 3.12.7, pytest-8.1.1, pluggy-1.5.0`,
  `rootdir: /repo`, `configfile: pyproject.toml`, `plugins: hypothesis-6.155.7`,
  `collected 199 items`, and `============================= 199 passed in 3.14s
  ==============================`. Then `git status --short` shows only this task's files: the
  run writes nothing into the checkout.
- [ ] **Step 8: Make a subs test fail; watch the run fail.** In `tests/test_text.py`, change
  `assert t.width("日本") == 4` to `assert t.width("日本") == 2`, run `make test-pyodide`, then
  `git checkout tests/test_text.py`. Expected: `E       AssertionError: assert 4 == 2`,
  `FAILED ../../repo/tests/test_text.py::test_wide_characters_count_two_and_latin_counts_one`,
  `======================== 1 failed, 198 passed in 4.77s =========================` and
  `make: *** [test-pyodide] Error 1`.
- [ ] **Step 9: Run the checks; they pass.** `make actionlint`, then `make check`. Expected:
  actionlint prints only its command line and exits 0; `955 passed, 2 skipped, 26 deselected`
  (twice), `Test Files  12 passed (12)`, `Tests  55 passed (55)`, `All checks passed!`,
  `no leaks found`.
- [ ] **Step 10: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
ci: 🤖 the pure packages' tests run inside Pyodide 0.27.7, the Pyodide the Pages editor runs on

Spec §22.6 and S53: CI's `pyodide` job, and `make test-pyodide` to run it anywhere, put the
tests of vid2sub.subs, vid2sub.parse and vid2sub.catalog through the real Pyodide 0.27.7
(Python 3.12.7, pydantic 2.10.5), the version spec §21 pins through Shinylive 0.8.12.

- The harness is Node with the pyodide npm package (0.27.7, exact, a frontend dev dependency,
  so the frontend's lockfile and .nvmrc pin it): frontend/scripts/pyodide-test.mjs refuses any
  other Pyodide, mounts the checkout at /repo, loads Pyodide's own micropip, pydantic, pytest and
  jsonschema, and runs tests/pyodide_run.py. Chosen over pyodide-build's `pyodide venv`, which
  needs pyodide-build in a host Python matched to Pyodide's and Node as well: this needs only the
  Node the frontend already has, which is what §22.6 describes.
- tests/pyodide_run.py picks every tests/test_*.py whose imports are the pure packages, the
  standard library and what the run installs (19 files today, test_edit.py and
  test_hostile_fixtures.py among them), so a new pure test joins without an edit; it installs
  uv.lock's pysubs2 1.9.0, opencc-purepy 1.4.4 and charset-normalizer 3.5.2 from PyPI through
  micropip (Pyodide ships charset-normalizer 3.3.2, below pyproject.toml's >=3.4), and
  hypothesis 6.155.7, the newest pure-Python release (from 6.156.0 hypothesis ships compiled
  wheels only, none for Pyodide 0.27, read from PyPI's JSON). micropip checks each wheel's sha256 against PyPI's
  (its _validate_sha256_checksum, read in micropip 0.9.0's source). Nothing is written into the
  checkout: no bytecode, and pytest and hypothesis work in /tmp inside Pyodide.
- make test-pyodide passes: "199 passed in 3.14s", about 9 s with a cold package cache, the
  same 199 tests the host runs for those files. With tests/test_text.py's `t.width("日本") == 4`
  changed to `== 2`, it fails: "FAILED ../../repo/tests/test_text.py::test_wide_characters_count_
  two_and_latin_counts_one", "1 failed, 198 passed", and make stops with
  "make: *** [test-pyodide] Error 1". It needs the network (Pyodide's CDN and PyPI), so make
  check leaves it out, as it does e2e.
- The job: ubuntu-24.04, contents: read, 10 minutes, checkout without credentials, setup-node
  from frontend/.nvmrc, npm ci, make test-pyodide. make actionlint: no findings.
- The lockfile change is pyodide and its one dependency, ws 8.22.0, written with npm 11.11.1
  (npm 10 also drops the lock's libc fields); npm audit still counts the same 8 findings.

Docs read: Pyodide 0.27.7's "Using Pyodide" (Node), JS API (loadPyodide, loadPackage,
mountNodeFS, runPython, globals, toPy), "Loading packages" (micropip from PyPI, deps), and
"Building and testing Python packages out of tree" (pyodide venv); pyodide 0.27.7's
pyodide-lock.json for the versions it ships.

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-4.md Task 6
Co-Authored-By: <the model's own line>
```

  `git add .github/workflows/ci.yml Makefile
  frontend/scripts/pyodide-test.mjs tests/pyodide_run.py`, `git commit -F .git/COMMIT_MSG`,
  then `git log -1 --format='%(trailers)'` shows `Plan:`.
- [ ] **Step 11: Review, look forward, close.** The Tier 3 self-review from
  `$(cat .git/TASK_BASE)` (*Standards*, *Spec*) plus `make check`, `make actionlint` and `make
  test-pyodide`. Worth checking: the job has `permissions`, `timeout-minutes` and
  `persist-credentials: false`, and its actions are the pins `ci.yml` already uses; the file list
  Step 7 printed holds every `tests/test_*.py` that imports only `vid2sub.subs`, `vid2sub.parse`
  or `vid2sub.catalog`. CI is the proof: the task closes once the run on its closing commit shows
  `pyodide` green. The forward review over Tasks 2, 7 and 10 (Task 2's Pages build vendors
  pysubs2, opencc-purepy and charset-normalizer as wheels: the versions this job installs are
  uv.lock's, so vendor those, and charset-normalizer from PyPI rather than Pyodide's 3.3.2, which
  is below `pyproject.toml`'s floor; Task 7's `pages.yml` can reuse this job's setup; Task 10's
  docs name `make test-pyodide`). The docs this task made untrue: spec §22.6 says "the `subs/`
  tests"; the job runs every pure package's tests, so make it "the pure packages' tests
  (`subs/`, `parse/`, `catalog.py`)". Then the close, its own commit, holding this plan with this
  task's boxes ticked and **Now** set to ``Task 7: `pages.yml`, open.``, and the spec's §22.6
  line and its S53 row set to `built`, its Proof
  reading ``CI's `pyodide` job (`make test-pyodide`)``, with the message in `.git/CLOSE_MSG`:

```text
docs(plan): 🤖 close Task 6: The Pyodide job

Drift: none
Rulings: none
Phase-end: none
Forward: none
Tier: 3
Rounds: self-review (Standards, Spec); make check; make actionlint; make test-pyodide
Findings: none

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-4.md Task 6
Co-Authored-By: <the model's own line>
```

  `git add docs/superpowers/plans/2026-10-23-vid2sub-phase-4.md
  docs/superpowers/specs/2026-10-14-vid2sub-design.md`, `git commit -F .git/CLOSE_MSG`.

***

### Task 7: `pages.yml`

**Tier:** 1 · **Scenarios:** S50, S51

**Interfaces:**
- Consumes: spec §23.3's triggers, with Decision 2's `workflow_run` in place of
  `release: published`. Task 8's `release.yml` is named `release` and runs on `v*` tag pushes
  only. `workflow_run` fires for any completed run of a workflow by that name, a fork's pull
  request included, so the deploy job runs only when `github.event.workflow_run.conclusion` is
  `success`, its `event` is `push`, and its `head_repository.full_name` is
  `github.repository`. It checks out `main`, never the triggering run's `head_sha`. The Tier 1
  review checks each condition, with a test over the workflow file. Read GitHub's docs on
  `workflow_run` and on environments' deployment branches, and say in the commit what you read.
- Consumes, from Tasks 2–4: the build job runs `make pages` (Node from `frontend/.nvmrc`,
  `npm ci`, uv, and ffmpeg until Task 5's clip), then `make pages-test` (after
  `uv run playwright install --with-deps chromium`), then uploads `_site/` with hidden files.
  Cache `.cache/shinylive/` keyed by `shinylive_local.ASSETS` (435 MB on a first download) and
  `.cache/wheels/` keyed by `uv.lock`. Review Focus 3's test is `test_pages_site.py`'s new-deploy
  test; that file's last test checks `start.js`'s `REVALIDATE` list against the built site.

<!-- steps: written in the next pass -->

***

### Task 8: `release.yml`

**Tier:** 1 · **Scenarios:** S52

Spec §23.4 and S52: a `v*` tag builds the frontend, then the wheel and the sdist with `www/`
inside, checks them against the tag, and publishes a GitHub Release with build-provenance
attestations; it never deploys Pages, and never replaces a published release's files (Review
Focus 4).

**Why it is built this way** (read 2026-10-24):
- **The frontend in both files.** Hatchling leaves out what `.gitignore` hides, and `www/ui.js`
  and `ui.css` are hidden build output. Listed as `artifacts` under `[tool.hatch.build]` (hatch's
  build configuration: "semantically equivalent to `include`", untouched by `exclude`), both
  targets carry them: built here, the sdist and the wheel (which `uv build` makes from the sdist,
  per uv's "Building distributions") both hold them, and neither did before.
- **A hatchling quirk the test must dodge:** hatchling drops every `.gitignore` pattern when one
  of them matches the project's own absolute path (`load_vcs_exclusion_patterns`, "validate
  project root is not excluded by vcs", in its source). The Python template's `var/` matches
  macOS's `/var/folders/…` temp folder, so a test that copied the whole `.gitignore` into
  pytest's `tmp_path` passed without the fix. The test's copy holds only the real file's two
  anchored frontend lines, which can't match an absolute path. A real release builds in
  `/home/runner/work/vid2sub/vid2sub`, which no pattern matches.
- **The build backend pinned by hash.** `pyproject.toml`'s `hatchling>=1.27` would let a release
  pick up whatever hatchling PyPI serves that day. `make dist` runs `uv build --no-sources --clear
  --build-constraints build-constraints.txt --require-hashes` (uv's "Build constraints": with
  `--require-hashes` the build requirements must match known hashes), and `make
  build-constraints` writes the file with `uv pip compile --generate-hashes`. With hatchling's
  hashes altered, the build stops with `Hash mismatch for hatchling==1.32.4`, even with
  hatchling in uv's cache. `--no-sources` is uv's packaging guide's advice for publishing;
  `--clear` empties `dist/` first, so no stale file goes out. uv 0.13.1, CI's pin, has all four.
- **The version: a check, not a version read from the tag.** Reading it from the tag needs a
  build plugin (hatch-vcs) or `uv version` rewriting `pyproject.toml` in CI, and leaves the
  committed version out of step with releases. A check is smaller: `scripts/release_check.py
  TAG` refuses a tag that isn't `v` + `pyproject.toml`'s version, and a package whose
  `vid2sub.__version__` (what `vid2sub --version` prints) differs from it; with `DIST`, it also
  refuses a `dist/` holding anything but that version's wheel and sdist, or either without the
  frontend. A suite test pins the two versions together, so they can't drift between releases.
  The first release is `v0.1.0.dev0` unless someone bumps both first (Task 12, step 9b, tags
  "the version that Task 8's check accepts").
- **Publishing that can't overwrite:** `gh release create` with assets first asks whether the
  tag has a published release and stops with "a release with the same tag name already exists"
  (cli/cli `pkg/cmd/release/create/create.go`, `publishedReleaseExists` in `http.go`); it then
  uploads only into the draft it creates, deleting that draft if an upload fails. Only `gh
  release upload --clobber` ("Delete and re-upload existing assets of the same name") or a
  release action's update mode would replace a file, and the test forbids both. `--verify-tag`
  stops it creating a tag. But gh's check doesn't see drafts, and deleting a tag turns its
  release into a draft (the same tag pushed again is Review Focus 4's case), so a step before the
  attestation lists every release, drafts included (`gh release list --limit 1000 --json
  tagName`), and stops on the tag; a failed lookup fails the step instead of reading as "no
  release" (round 8d). A re-run therefore makes no attestation for a release it can't publish.
- **Mistakes the workflow can stop, and what only Dan's settings can.** It refuses a tag that
  isn't on `main` (`git merge-base --is-ancestor "$GITHUB_SHA" origin/main`, checkout fetching
  all history) and a tag moved between build and publish (`git ls-remote` must still give
  `$GITHUB_SHA`, peeled, so an annotated tag counts). A tag pushed from a fork runs the fork's
  copy with the fork's token and touches nothing here. A commit carrying a modified
  `release.yml` can drop any of these checks; only repo settings stop that (immutable releases, a
  tag ruleset on `refs/tags/v*`, branch protection on `main`; the close lists them for Task 12's
  step 9b).
- **Attestations:** `actions/attest` v4.2.2. attest-build-provenance v4's README says it is now a
  wrapper over `actions/attest` and that new workflows should use `actions/attest`, whose default
  (no predicate, no SBOM) is SLSA build provenance. Its provenance example needs `id-token: write`
  and `attestations: write`; `artifact-metadata: write` is for storage records, which need
  `push-to-registry` and an organisation's repository, so it isn't asked for.
- **Permissions:** the build job (`contents: read`) runs the repository's code and npm's install
  scripts; the publish job alone has `contents: write`, `id-token: write` and `attestations:
  write`, and runs no repository code (no checkout): it downloads the run's `dist` artifact
  (download-artifact fails on a digest mismatch by default), attests and publishes.
- **The tag reaches a shell only as `"$TAG"`** (env): a ref name may hold `$(…)`, so no
  `${{ … }}` appears in a `run:` step.
- **Pages:** a release made with the GITHUB_TOKEN starts no workflow (GitHub's GITHUB_TOKEN docs:
  only `workflow_dispatch` and `repository_dispatch` are exempt), so `pages.yml` follows this
  workflow by its name, `release`, through `workflow_run` (Phase 4 Decision 2, Task 7). The name
  is pinned by the test.

**Files:**
- Create: `.github/workflows/release.yml`, `scripts/release_check.py`, `build-constraints.txt`,
  `tests/test_release.py`
- Modify: `pyproject.toml` (`[tool.hatch.build] artifacts`), `Makefile` (`dist`,
  `build-constraints`)
- Modify at the close: this plan; the spec (S52)

**Interfaces:**
- Consumes: Phase 2 Task 12's frontend build (`make build`, `npm ci` in `frontend/`, Node from
  `frontend/.nvmrc`); Phase 2 Task 21's pins and `make actionlint`; `pyproject.toml`'s
  `[project].version` and `src/vid2sub/__init__.py`'s `__version__`; PyYAML (the dev group's
  `pyyaml==6.0.3`) for the workflow tests.
- Produces:
  - `release.yml`, `name: release` (Task 7's `pages.yml` follows it by this name through
    `workflow_run`, Phase 4 Decision 2), on `push: tags: ["v*"]` only; jobs `build`
    (`contents: read`) and `publish` (`contents: write`, `id-token: write`, `attestations:
    write`), the run's artifact `dist` between them; it publishes a release named
    `vid2sub <version>` whose assets are `vid2sub-<version>-py3-none-any.whl` and
    `vid2sub-<version>.tar.gz`, each with a build-provenance attestation. It fails, before
    anything is made, on a tag that isn't the package's version, isn't on `main`, has a release
    already (published or draft) or moved during the run. Every run step is `shell: bash`
    (`-eo pipefail`).
  - `make dist`: the frontend, then the wheel and sdist into `dist/`, both with
    `vid2sub/web/www/ui.js` and `ui.css`; `make build-constraints`: re-pins hatchling and its
    dependencies, with hashes, in `build-constraints.txt`.
  - `scripts/release_check.py TAG [DIST]` (PEP 723, no dependencies; `uv run
    scripts/release_check.py …`): exit 0, 1 naming each problem on stderr (`release check:
    …`), 2 on a usage error; functions `versions(root)`, `tag_problems(tag, root=ROOT)`,
    `dist_problems(tag, dist)`, `main(argv)`. Task 12's step 9b tags what `tag_problems`
    accepts.
  - For Task 9's index: release assets are named as above; the wheel is the only `.whl`.

The `make check` counts below come from a clone with Phase 2's Tasks 2–16 and 21 and Phase 4's
Task 6 only; yours are higher. What matters is no failure, ruff's `All checks passed!` and
gitleaks' `no leaks found`. `tests/test_release.py`'s own counts are exact.

- [ ] **Step 0: Record the base:** `git rev-parse HEAD > .git/TASK_BASE`.

#### Round 8a: the frontend in both files, and the build backend pinned

- [ ] **Step 1: The targets, and the pinned build backend.** In the `Makefile`, add `dist` and
  `build-constraints` to the `.PHONY:` line after `build`, and below the `build:` target's recipe
  (`	cd $(FRONTEND) && $(NVM) npm run build`) add (recipe lines start with a tab):

```make

# tests/test_release.py builds with these same flags: change them together.
dist: build ## Build the wheel and sdist into dist/, the frontend inside, as release.yml does
	uv build --no-sources --clear --build-constraints build-constraints.txt --require-hashes

build-constraints: ## Re-pin make dist's build backend (hatchling) and its dependencies, with hashes
	echo 'hatchling>=1.27' | uv pip compile - --universal --python-version 3.12 --generate-hashes --output-file build-constraints.txt
```

  Then `make build-constraints`. It writes `build-constraints.txt`; on 2026-10-24 it was the
  file below (newer releases since give newer pins: commit what it writes):

```text
# This file was autogenerated by uv via the following command:
#    uv pip compile - --universal --python-version 3.12 --generate-hashes --output-file build-constraints.txt
hatchling==1.32.4 \
    --hash=sha256:08ecf7548fb48205e7f213d70c71e67b8271b7242093dc3f1da578b42c734a2c \
    --hash=sha256:c4468f73144c054d2aab4ef0f0378c43b9878bf07f8ffd6b79690e970d375f07
packaging==26.3 \
    --hash=sha256:94edc256424af38762eb31306eed28beb9f0efc50a8837492c9d6fd6004aed79 \
    --hash=sha256:d7193f7c8e4e93f444fde0262bf90af30e16fa0ad0ad44cb553c87339b23cd1c
    # via hatchling
pathspec==1.1.1 \
    --hash=sha256:17db5ecd524104a120e173814c90367a96a98d07c45b2e10c2f3919fff91bf5a \
    --hash=sha256:a00ce642f577bf7f473932318056212bc4f8bfdf53128c78bbd5af0b9b20b189
    # via hatchling
pluggy==1.7.0 \
    --hash=sha256:7dd7b0d8832ba3cb632c306926ded123429211b83641b35dc5c41ad2d34f9bec \
    --hash=sha256:d1eaa46ebb595891b860ab086b4d09c8588af65ebd4361b8e8f4bb8920b90ba8
    # via hatchling
tomlkit==0.15.2 \
    --hash=sha256:05562412163a3037b94497385fb7f9204c637bc605af7a48199e41cf2272f437 \
    --hash=sha256:83e32755ba1d20d9340bd069ee97e9f6232ba2346b63ffcba425de01f7e327a6
    # via hatchling
trove-classifiers==2026.9.21.13 \
    --hash=sha256:0a9ebc8d4e2f3e8a22848c5258033035bec17a3012ac3fea16dbaa764489eb71 \
    --hash=sha256:8b1ff4f9c191b1040b71c37f1e445ab99732911e3cd91de52838453a854d7a17
    # via hatchling
```

- [ ] **Step 2: Write the failing test,** `tests/test_release.py`:

```python
"""A release carries the editor and can't go out wrong (spec §23.4, S52): the wheel and the sdist
hold the built frontend, which git ignores. Each guard here fails without its fix (Phase 4 Task 8).

The build runs on a copy of the project, with stand-ins for www/ui.js and ui.css, the real
pyproject.toml and the .gitignore lines that hide them, so it needs no frontend build and leaves
the checkout alone; it is make dist's `uv build`, with the same flags, and needs the network the
first time (hatchling and its dependencies, hash-pinned in build-constraints.txt).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tarfile
import tomllib
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FRONTEND = ("vid2sub/web/www/ui.js", "vid2sub/web/www/ui.css")
# make dist's flags (Makefile): change them together.
BUILD = ("build", "--no-sources", "--clear", "--build-constraints", "build-constraints.txt",
         "--require-hashes")


def version() -> str:
    return tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "version"]


def build_copy(tmp: Path) -> Path:
    """The project's packaging files and src/ in `tmp`, with stand-in frontend files, built into
    `tmp`/dist as make dist builds; returns that folder."""
    project = tmp / "project"
    project.mkdir()
    for name in ("pyproject.toml", "README.md", "LICENSE", "build-constraints.txt"):
        shutil.copy2(REPO / name, project / name)
    # Only the real .gitignore's lines for the frontend's build output, which are what hide it:
    # hatchling drops every .gitignore pattern when one matches the project's own absolute path
    # (as `var/` matches macOS's /var/folders/ temp folder; hatchling's
    # load_vcs_exclusion_patterns), which would let this test pass without its fix. Anchored
    # lines can't match it.
    gitignore = (REPO / ".gitignore").read_text(encoding="utf-8").splitlines()
    hide = [line for line in gitignore if line.startswith("src/vid2sub/web/www/")]
    assert hide == ["src/vid2sub/web/www/ui.js", "src/vid2sub/web/www/ui.css"]
    (project / ".gitignore").write_text("\n".join(hide) + "\n", encoding="utf-8")
    shutil.copytree(REPO / "src", project / "src",
                    ignore=shutil.ignore_patterns("__pycache__", "ui.js", "ui.css"))
    www = project / "src/vid2sub/web/www"
    (www / "ui.js").write_text("// stand-in bundle\n", encoding="utf-8")
    (www / "ui.css").write_text("/* stand-in styles */\n", encoding="utf-8")
    uv = os.environ.get("UV") or shutil.which("uv")
    assert uv, "uv not found: run the tests with `uv run pytest`"
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    done = subprocess.run([uv, *BUILD, "--out-dir", str(tmp / "dist")], cwd=project, env=env,
                          check=False, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr[-3000:]
    return tmp / "dist"


def test_a_built_wheel_and_sdist_hold_the_built_frontend(tmp_path):
    # why: www/ui.js and ui.css are build output that .gitignore hides, and hatchling leaves out
    # what git ignores unless pyproject.toml lists it under `artifacts`; without them a release
    # installs a `vid2sub serve` with no editor (spec §23.5: "Release wheels already contain it").
    dist = build_copy(tmp_path)
    v = version()
    with zipfile.ZipFile(dist / f"vid2sub-{v}-py3-none-any.whl") as wheel:
        names = set(wheel.namelist())
        assert [f for f in FRONTEND if f not in names] == []
        assert wheel.read("vid2sub/web/www/ui.js") == b"// stand-in bundle\n"
    with tarfile.open(dist / f"vid2sub-{v}.tar.gz") as sdist:
        names = set(sdist.getnames())
    assert [f for f in FRONTEND if f"vid2sub-{v}/src/{f}" not in names] == []
```

- [ ] **Step 3: Run it; watch it fail.** `uv run pytest tests/test_release.py -q`. Expected:
  `FAILED tests/test_release.py::test_a_built_wheel_and_sdist_hold_the_built_frontend`, with
  `E           AssertionError: assert ['vid2sub/web...b/www/ui.css'] == []` and
  `Left contains 2 more items, first extra item: 'vid2sub/web/www/ui.js'`.
- [ ] **Step 4: List the frontend as artifacts.** In `pyproject.toml`, insert above the line
  `[tool.hatch.build.targets.wheel]`:

```toml
# The frontend is build output that .gitignore hides, and hatchling leaves out what git ignores;
# listed here, both the sdist and the wheel carry it (make dist builds it first; spec §23.4).
[tool.hatch.build]
artifacts = ["src/vid2sub/web/www/ui.js", "src/vid2sub/web/www/ui.css"]

```

- [ ] **Step 5: Run the checks; they pass.** First `uv run pytest tests/test_release.py -q`:
  `1 passed`. Then the real build, `make dist`, and look inside:

```bash
make dist
unzip -l dist/*.whl | grep 'www/ui'
tar -tzf dist/*.tar.gz | grep 'www/ui'
```

  Expected: `Successfully built dist/vid2sub-0.1.0.dev0.tar.gz` and `…-py3-none-any.whl`; the
  wheel lists `vid2sub/web/www/ui.css` and `vid2sub/web/www/ui.js`, the sdist
  `vid2sub-0.1.0.dev0/src/vid2sub/web/www/ui.css` and `ui.js`. Then the hash pin's guard: in
  `build-constraints.txt`, change the first character of both of hatchling's hashes, run
  `uv build --no-sources --clear --build-constraints build-constraints.txt --require-hashes`,
  then `git checkout build-constraints.txt` (or regenerate it). Expected: ``cause: Hash mismatch
  for `hatchling==<version>` ``, exit 2, even with hatchling in uv's cache. Then `make check`.
  Expected: `956 passed, 2 skipped, 26 deselected` (twice), `Test Files  12 passed (12)`,
  `Tests  55 passed (55)`, `All checks passed!`, `no leaks found`.
- [ ] **Step 6: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
build(release): 🤖 make dist builds a wheel and an sdist that carry the editor's frontend, with the build backend pinned by hash

Spec §23.4 and S52: a release's wheel and sdist hold www/ui.js and ui.css, so an install from
the index has an editor (§23.5: "Release wheels already contain it").

- pyproject.toml lists both as hatch `artifacts` under [tool.hatch.build], so the sdist and the
  wheel carry them though .gitignore hides them (built here: without it neither file held
  them; with it both do, the wheel built from the sdist as uv build does).
- make dist builds the frontend, then `uv build --no-sources --clear --build-constraints
  build-constraints.txt --require-hashes`: --no-sources as uv's packaging guide recommends for
  publishing, --clear so no stale file is released, and hatchling with its five dependencies
  pinned by hash (make build-constraints writes the file with `uv pip compile
  --generate-hashes`). With hatchling's two hashes altered, the build stops: "Hash mismatch for
  `hatchling==1.32.4`", even with hatchling in uv's cache.
- tests/test_release.py builds a copy of the project with stand-in frontend files, as make dist
  does, and checks both files. It failed before the artifacts line: "FAILED
  tests/test_release.py::test_a_built_wheel_and_sdist_hold_the_built_frontend" (ui.js and
  ui.css missing from the wheel). The copy's .gitignore holds only the real one's two frontend
  lines: hatchling drops every .gitignore pattern when one matches the project's own absolute
  path (hatchling's load_vcs_exclusion_patterns, read in its source), and the Python template's
  `var/` matches macOS's /var/folders/ temp folder, where the whole-file copy let the test pass
  without the fix.

Docs read: hatch's build configuration (artifacts: "semantically equivalent to include", not
affected by exclude; VCS ignore files respected) and its sdist and wheel builder pages; uv's
"Building distributions" concept page (the wheel is built from the sdist; --build-constraint
with --require-hashes) and packaging guide (--no-sources); uv 0.13.1's `uv build --help`
(--clear, --build-constraints, --require-hashes, --no-sources all present in CI's pinned uv).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-4.md Task 8
Co-Authored-By: <the model's own line>
```

  `git add pyproject.toml Makefile build-constraints.txt tests/test_release.py`, `git commit -F
  .git/COMMIT_MSG`, then `git log -1 --format='%(trailers)'` shows `Plan:`.

#### Round 8b: the release check

- [ ] **Step 7: Write the failing tests.** Replace `tests/test_release.py` with:

```python
"""A release carries the editor and can't go out wrong (spec §23.4, S52): the wheel and the sdist
hold the built frontend, which git ignores. Each guard here fails without its fix (Phase 4 Task 8).

The build runs on a copy of the project, with stand-ins for www/ui.js and ui.css, the real
pyproject.toml and the .gitignore lines that hide them, so it needs no frontend build and leaves
the checkout alone; it is make dist's `uv build`, with the same flags, and needs the network the
first time (hatchling and its dependencies, hash-pinned in build-constraints.txt).
"""

from __future__ import annotations

import importlib.util
import io
import os
import shutil
import subprocess
import tarfile
import tomllib
import zipfile
from pathlib import Path

import vid2sub

REPO = Path(__file__).resolve().parents[1]
FRONTEND = ("vid2sub/web/www/ui.js", "vid2sub/web/www/ui.css")
# make dist's flags (Makefile): change them together.
BUILD = ("build", "--no-sources", "--clear", "--build-constraints", "build-constraints.txt",
         "--require-hashes")


def release_check():
    spec = importlib.util.spec_from_file_location("release_check",
                                                  REPO / "scripts" / "release_check.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def version() -> str:
    return tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "version"]


def build_copy(tmp: Path) -> Path:
    """The project's packaging files and src/ in `tmp`, with stand-in frontend files, built into
    `tmp`/dist as make dist builds; returns that folder."""
    project = tmp / "project"
    project.mkdir()
    for name in ("pyproject.toml", "README.md", "LICENSE", "build-constraints.txt"):
        shutil.copy2(REPO / name, project / name)
    # Only the real .gitignore's lines for the frontend's build output, which are what hide it:
    # hatchling drops every .gitignore pattern when one matches the project's own absolute path
    # (as `var/` matches macOS's /var/folders/ temp folder; hatchling's
    # load_vcs_exclusion_patterns), which would let this test pass without its fix. Anchored
    # lines can't match it.
    gitignore = (REPO / ".gitignore").read_text(encoding="utf-8").splitlines()
    hide = [line for line in gitignore if line.startswith("src/vid2sub/web/www/")]
    assert hide == ["src/vid2sub/web/www/ui.js", "src/vid2sub/web/www/ui.css"]
    (project / ".gitignore").write_text("\n".join(hide) + "\n", encoding="utf-8")
    shutil.copytree(REPO / "src", project / "src",
                    ignore=shutil.ignore_patterns("__pycache__", "ui.js", "ui.css"))
    www = project / "src/vid2sub/web/www"
    (www / "ui.js").write_text("// stand-in bundle\n", encoding="utf-8")
    (www / "ui.css").write_text("/* stand-in styles */\n", encoding="utf-8")
    uv = os.environ.get("UV") or shutil.which("uv")
    assert uv, "uv not found: run the tests with `uv run pytest`"
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    done = subprocess.run([uv, *BUILD, "--out-dir", str(tmp / "dist")], cwd=project, env=env,
                          check=False, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr[-3000:]
    return tmp / "dist"


def test_a_built_wheel_and_sdist_hold_the_built_frontend(tmp_path):
    # why: www/ui.js and ui.css are build output that .gitignore hides, and hatchling leaves out
    # what git ignores unless pyproject.toml lists it under `artifacts`; without them a release
    # installs a `vid2sub serve` with no editor (spec §23.5: "Release wheels already contain it").
    dist = build_copy(tmp_path)
    v = version()
    with zipfile.ZipFile(dist / f"vid2sub-{v}-py3-none-any.whl") as wheel:
        names = set(wheel.namelist())
        assert [f for f in FRONTEND if f not in names] == []
        assert wheel.read("vid2sub/web/www/ui.js") == b"// stand-in bundle\n"
    with tarfile.open(dist / f"vid2sub-{v}.tar.gz") as sdist:
        names = set(sdist.getnames())
    assert [f for f in FRONTEND if f"vid2sub-{v}/src/{f}" not in names] == []


def test_the_package_version_is_the_same_in_pyproject_and_the_package():
    # why: the wheel is named for pyproject.toml's version and `vid2sub --version` prints
    # vid2sub.__version__, so a release whose two differ says the wrong one somewhere.
    assert vid2sub.__version__ == version()


def test_the_release_check_refuses_a_tag_that_isnt_the_package_version():
    # why: the tag names the release, and Task 9's index lists its wheel under the package's
    # version; a published release's files are never replaced, so a mismatch stops it first.
    check = release_check()
    v = version()
    assert check.tag_problems(f"v{v}") == []
    assert check.tag_problems("v9.9.9") == [f"the tag 'v9.9.9' isn't v{v}, pyproject.toml's version"]
    assert check.tag_problems(v) == [f"the tag {v!r} isn't v{v}, pyproject.toml's version"]


def test_the_release_check_refuses_a_package_whose_two_versions_differ(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "1.0.0"\n', encoding="utf-8")
    (tmp_path / "src/vid2sub").mkdir(parents=True)
    (tmp_path / "src/vid2sub/__init__.py").write_text('__version__ = "1.0.1"\n', encoding="utf-8")
    assert release_check().tag_problems("v1.0.0", root=tmp_path) == [
        "vid2sub.__version__ is '1.0.1', not pyproject.toml's '1.0.0'"]


def test_the_release_check_refuses_a_dist_without_the_frontend_or_with_other_files(tmp_path):
    with zipfile.ZipFile(tmp_path / "vid2sub-1.0.0-py3-none-any.whl", "w") as wheel:
        wheel.writestr("vid2sub/web/www/ui.js", "// built\n")  # no ui.css
    with tarfile.open(tmp_path / "vid2sub-1.0.0.tar.gz", "w:gz") as sdist:
        data = b"/* built */\n"
        info = tarfile.TarInfo("vid2sub-1.0.0/src/vid2sub/web/www/ui.css")
        info.size = len(data)
        sdist.addfile(info, io.BytesIO(data))  # no ui.js
    (tmp_path / "vid2sub-0.9.0-py3-none-any.whl").write_bytes(b"")  # a stale build
    (tmp_path / ".gitignore").write_text("*\n", encoding="utf-8")  # uv build writes this one
    assert release_check().dist_problems("v1.0.0", tmp_path) == [
        (f"{tmp_path} holds vid2sub-0.9.0-py3-none-any.whl, vid2sub-1.0.0-py3-none-any.whl, "
         "vid2sub-1.0.0.tar.gz, not just vid2sub-1.0.0-py3-none-any.whl and vid2sub-1.0.0.tar.gz"),
        "vid2sub-1.0.0-py3-none-any.whl lacks vid2sub/web/www/ui.css",
        "vid2sub-1.0.0.tar.gz lacks src/vid2sub/web/www/ui.js",
    ]
    assert release_check().dist_problems("v2.0.0", tmp_path)[0].endswith(
        "not just vid2sub-2.0.0-py3-none-any.whl and vid2sub-2.0.0.tar.gz")


def test_the_release_check_accepts_what_make_dist_builds(tmp_path):
    dist = build_copy(tmp_path)
    assert release_check().dist_problems(f"v{version()}", dist) == []


def test_the_release_check_exits_1_naming_each_problem(capsys):
    check = release_check()
    assert check.main(["v9.9.9"]) == 1
    assert capsys.readouterr().err == (
        f"release check: the tag 'v9.9.9' isn't v{version()}, pyproject.toml's version\n")
    assert check.main([f"v{version()}"]) == 0
    assert capsys.readouterr().out == f"release check: v{version()} names the package's version\n"
    assert check.main([]) == 2
```

- [ ] **Step 8: Run them; watch them fail.** `uv run pytest tests/test_release.py -q`.
  Expected: `5 failed, 2 passed`, each failure
  `FileNotFoundError: [Errno 2] No such file or directory: '…/scripts/release_check.py'`.
- [ ] **Step 9: Write the check,** `scripts/release_check.py`:

```python
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Checks a release against its tag before release.yml publishes it (spec §23.4, S52).

    uv run scripts/release_check.py v0.1.0         the tag names the package's version
    uv run scripts/release_check.py v0.1.0 dist    and dist/ holds just that version's wheel and
                                                   sdist, each with the built frontend

Why: a published release's files are never replaced (AGENTS.md: never overwrite an artifact), so
a wrong one has to be stopped before it goes out. The version is written twice, in
pyproject.toml (the wheel's name and metadata) and as vid2sub.__version__ (what `vid2sub
--version` prints), and the tag must name both; checking was chosen over reading the version
from the tag (Phase 4 Task 8), as the smaller change. The frontend, www/ui.js and ui.css, is
build output that git ignores and hatchling carries only as an artifact; a release without it
has no editor. Exits 0, 1 naming each problem, or 2 on a usage error.
"""

from __future__ import annotations

import ast
import sys
import tarfile
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ("vid2sub/web/www/ui.js", "vid2sub/web/www/ui.css")


def versions(root: Path) -> tuple[str, str | None]:
    """pyproject.toml's version and vid2sub.__version__, read without importing the package."""
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    package = None
    init = ast.parse((root / "src/vid2sub/__init__.py").read_text(encoding="utf-8"))
    for node in init.body:
        if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant)
                and any(isinstance(t, ast.Name) and t.id == "__version__" for t in node.targets)):
            package = node.value.value
    return pyproject["project"]["version"], package


def tag_problems(tag: str, root: Path = ROOT) -> list[str]:
    project, package = versions(root)
    problems = []
    if tag != f"v{project}":
        problems.append(f"the tag {tag!r} isn't v{project}, pyproject.toml's version")
    if package != project:
        problems.append(f"vid2sub.__version__ is {package!r}, not pyproject.toml's {project!r}")
    return problems


def dist_problems(tag: str, dist: Path) -> list[str]:
    version = tag.removeprefix("v")
    wheel = dist / f"vid2sub-{version}-py3-none-any.whl"
    sdist = dist / f"vid2sub-{version}.tar.gz"
    problems = []
    found = sorted(p.name for p in dist.iterdir() if p.name != ".gitignore") if dist.is_dir() else []
    if found != sorted([wheel.name, sdist.name]):
        problems.append(f"{dist} holds {', '.join(found) or 'nothing'}, not just {wheel.name} "
                        f"and {sdist.name}")
    if wheel.is_file():
        with zipfile.ZipFile(wheel) as z:
            names = set(z.namelist())
        problems += [f"{wheel.name} lacks {f}" for f in FRONTEND if f not in names]
    if sdist.is_file():
        with tarfile.open(sdist) as t:
            names = set(t.getnames())
        problems += [f"{sdist.name} lacks src/{f}" for f in FRONTEND
                     if f"vid2sub-{version}/src/{f}" not in names]
    return problems


def main(argv: list[str]) -> int:
    if len(argv) not in (1, 2):
        print("usage: release_check.py TAG [DIST]", file=sys.stderr)
        return 2
    tag = argv[0]
    problems = tag_problems(tag)
    if len(argv) == 2:
        problems += dist_problems(tag, Path(argv[1]))
    for problem in problems:
        print(f"release check: {problem}", file=sys.stderr)
    if problems:
        return 1
    held = f", and {argv[1]} holds its wheel and sdist with the frontend" if len(argv) == 2 else ""
    print(f"release check: {tag} names the package's version{held}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

- [ ] **Step 10: Run the checks; they pass.** `uv run pytest tests/test_release.py -q`: `7
  passed`. The guard: change `    if tag != f"v{project}":` to `    if False:`, rerun, then
  restore it. Expected: `FAILED
  tests/test_release.py::test_the_release_check_refuses_a_tag_that_isnt_the_package_version`,
  `FAILED tests/test_release.py::test_the_release_check_exits_1_naming_each_problem`, `2
  failed, 5 passed`. By hand: `uv run scripts/release_check.py v0.1.0.dev0` prints `release
  check: v0.1.0.dev0 names the package's version` (exit 0); `uv run scripts/release_check.py
  v0.1.0` prints `release check: the tag 'v0.1.0' isn't v0.1.0.dev0, pyproject.toml's version`
  (exit 1); `uv run scripts/release_check.py 'v$(touch /tmp/x)'` is refused the same way and
  creates nothing. Then `make check`. Expected: `962 passed, 2 skipped, 26 deselected` (twice),
  `Test Files  12 passed (12)`, `Tests  55 passed (55)`, `All checks passed!`, `no leaks found`.
- [ ] **Step 11: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
build(release): 🤖 a release whose tag isn't the package's version, or whose dist/ lacks the frontend, is refused before it goes out

Spec §23.4, S52, and Phase 4's Review Focus 4: a published release's files are never replaced,
so a wrong one is stopped first. scripts/release_check.py (a PEP 723 script with no
dependencies, run as `uv run scripts/release_check.py TAG [DIST]`) exits 1 naming each problem:

- the tag isn't `v` + pyproject.toml's version, or vid2sub.__version__ (what `vid2sub
  --version` prints) differs from it; both are read without importing the package. A check was
  chosen over reading the version from the tag (hatch-vcs or `uv version` in CI) as the smaller
  change: no new build plugin, and the committed version stays the released one;
- with DIST, that folder holds anything but that version's wheel and sdist (uv build's
  .gitignore aside), or either lacks www/ui.js or ui.css.

The tests failed before the script existed (FileNotFoundError for scripts/release_check.py, 5
failed), and with the tag comparison disabled (`if False:`) the two refusal tests fail
("FAILED tests/test_release.py::test_the_release_check_refuses_a_tag_that_isnt_the_package_
version", and the exit-code test). A tag such as `v$(touch /tmp/x)` reaches it as one argument
and is refused as text. A new suite test pins pyproject.toml's version to vid2sub.__version__,
so the two can't drift between releases.

Docs read: uv's guide on running scripts (PEP 723 inline metadata: the `dependencies` field is
required even when empty, and a script with it ignores the project's dependencies).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-4.md Task 8
Co-Authored-By: <the model's own line>
```

  `git add scripts/release_check.py tests/test_release.py`, `git commit -F .git/COMMIT_MSG`,
  then `git log -1 --format='%(trailers)'` shows `Plan:`.

#### Round 8c: `release.yml`

- [ ] **Step 12: Write the failing tests.** Replace `tests/test_release.py` with:

```python
"""A release carries the editor and can't go out wrong (spec §23.4, S52): the wheel and the sdist
hold the built frontend, which git ignores. Each guard here fails without its fix (Phase 4 Task 8).

The build runs on a copy of the project, with stand-ins for www/ui.js and ui.css, the real
pyproject.toml and the .gitignore lines that hide them, so it needs no frontend build and leaves
the checkout alone; it is make dist's `uv build`, with the same flags, and needs the network the
first time (hatchling and its dependencies, hash-pinned in build-constraints.txt).
"""

from __future__ import annotations

import importlib.util
import io
import os
import re
import shutil
import subprocess
import tarfile
import tomllib
import zipfile
from pathlib import Path

import yaml

import vid2sub

REPO = Path(__file__).resolve().parents[1]
FRONTEND = ("vid2sub/web/www/ui.js", "vid2sub/web/www/ui.css")
RELEASE = REPO / ".github/workflows/release.yml"
# make dist's flags (Makefile): change them together.
BUILD = ("build", "--no-sources", "--clear", "--build-constraints", "build-constraints.txt",
         "--require-hashes")


def release_check():
    spec = importlib.util.spec_from_file_location("release_check",
                                                  REPO / "scripts" / "release_check.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def version() -> str:
    return tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "version"]


def build_copy(tmp: Path) -> Path:
    """The project's packaging files and src/ in `tmp`, with stand-in frontend files, built into
    `tmp`/dist as make dist builds; returns that folder."""
    project = tmp / "project"
    project.mkdir()
    for name in ("pyproject.toml", "README.md", "LICENSE", "build-constraints.txt"):
        shutil.copy2(REPO / name, project / name)
    # Only the real .gitignore's lines for the frontend's build output, which are what hide it:
    # hatchling drops every .gitignore pattern when one matches the project's own absolute path
    # (as `var/` matches macOS's /var/folders/ temp folder; hatchling's
    # load_vcs_exclusion_patterns), which would let this test pass without its fix. Anchored
    # lines can't match it.
    gitignore = (REPO / ".gitignore").read_text(encoding="utf-8").splitlines()
    hide = [line for line in gitignore if line.startswith("src/vid2sub/web/www/")]
    assert hide == ["src/vid2sub/web/www/ui.js", "src/vid2sub/web/www/ui.css"]
    (project / ".gitignore").write_text("\n".join(hide) + "\n", encoding="utf-8")
    shutil.copytree(REPO / "src", project / "src",
                    ignore=shutil.ignore_patterns("__pycache__", "ui.js", "ui.css"))
    www = project / "src/vid2sub/web/www"
    (www / "ui.js").write_text("// stand-in bundle\n", encoding="utf-8")
    (www / "ui.css").write_text("/* stand-in styles */\n", encoding="utf-8")
    uv = os.environ.get("UV") or shutil.which("uv")
    assert uv, "uv not found: run the tests with `uv run pytest`"
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    done = subprocess.run([uv, *BUILD, "--out-dir", str(tmp / "dist")], cwd=project, env=env,
                          check=False, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr[-3000:]
    return tmp / "dist"


def test_a_built_wheel_and_sdist_hold_the_built_frontend(tmp_path):
    # why: www/ui.js and ui.css are build output that .gitignore hides, and hatchling leaves out
    # what git ignores unless pyproject.toml lists it under `artifacts`; without them a release
    # installs a `vid2sub serve` with no editor (spec §23.5: "Release wheels already contain it").
    dist = build_copy(tmp_path)
    v = version()
    with zipfile.ZipFile(dist / f"vid2sub-{v}-py3-none-any.whl") as wheel:
        names = set(wheel.namelist())
        assert [f for f in FRONTEND if f not in names] == []
        assert wheel.read("vid2sub/web/www/ui.js") == b"// stand-in bundle\n"
    with tarfile.open(dist / f"vid2sub-{v}.tar.gz") as sdist:
        names = set(sdist.getnames())
    assert [f for f in FRONTEND if f"vid2sub-{v}/src/{f}" not in names] == []


def test_the_package_version_is_the_same_in_pyproject_and_the_package():
    # why: the wheel is named for pyproject.toml's version and `vid2sub --version` prints
    # vid2sub.__version__, so a release whose two differ says the wrong one somewhere.
    assert vid2sub.__version__ == version()


def test_the_release_check_refuses_a_tag_that_isnt_the_package_version():
    # why: the tag names the release, and Task 9's index lists its wheel under the package's
    # version; a published release's files are never replaced, so a mismatch stops it first.
    check = release_check()
    v = version()
    assert check.tag_problems(f"v{v}") == []
    assert check.tag_problems("v9.9.9") == [f"the tag 'v9.9.9' isn't v{v}, pyproject.toml's version"]
    assert check.tag_problems(v) == [f"the tag {v!r} isn't v{v}, pyproject.toml's version"]


def test_the_release_check_refuses_a_package_whose_two_versions_differ(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "1.0.0"\n', encoding="utf-8")
    (tmp_path / "src/vid2sub").mkdir(parents=True)
    (tmp_path / "src/vid2sub/__init__.py").write_text('__version__ = "1.0.1"\n', encoding="utf-8")
    assert release_check().tag_problems("v1.0.0", root=tmp_path) == [
        "vid2sub.__version__ is '1.0.1', not pyproject.toml's '1.0.0'"]


def test_the_release_check_refuses_a_dist_without_the_frontend_or_with_other_files(tmp_path):
    with zipfile.ZipFile(tmp_path / "vid2sub-1.0.0-py3-none-any.whl", "w") as wheel:
        wheel.writestr("vid2sub/web/www/ui.js", "// built\n")  # no ui.css
    with tarfile.open(tmp_path / "vid2sub-1.0.0.tar.gz", "w:gz") as sdist:
        data = b"/* built */\n"
        info = tarfile.TarInfo("vid2sub-1.0.0/src/vid2sub/web/www/ui.css")
        info.size = len(data)
        sdist.addfile(info, io.BytesIO(data))  # no ui.js
    (tmp_path / "vid2sub-0.9.0-py3-none-any.whl").write_bytes(b"")  # a stale build
    (tmp_path / ".gitignore").write_text("*\n", encoding="utf-8")  # uv build writes this one
    assert release_check().dist_problems("v1.0.0", tmp_path) == [
        (f"{tmp_path} holds vid2sub-0.9.0-py3-none-any.whl, vid2sub-1.0.0-py3-none-any.whl, "
         "vid2sub-1.0.0.tar.gz, not just vid2sub-1.0.0-py3-none-any.whl and vid2sub-1.0.0.tar.gz"),
        "vid2sub-1.0.0-py3-none-any.whl lacks vid2sub/web/www/ui.css",
        "vid2sub-1.0.0.tar.gz lacks src/vid2sub/web/www/ui.js",
    ]
    assert release_check().dist_problems("v2.0.0", tmp_path)[0].endswith(
        "not just vid2sub-2.0.0-py3-none-any.whl and vid2sub-2.0.0.tar.gz")


def test_the_release_check_accepts_what_make_dist_builds(tmp_path):
    dist = build_copy(tmp_path)
    assert release_check().dist_problems(f"v{version()}", dist) == []


def test_the_release_check_exits_1_naming_each_problem(capsys):
    check = release_check()
    assert check.main(["v9.9.9"]) == 1
    assert capsys.readouterr().err == (
        f"release check: the tag 'v9.9.9' isn't v{version()}, pyproject.toml's version\n")
    assert check.main([f"v{version()}"]) == 0
    assert capsys.readouterr().out == f"release check: v{version()} names the package's version\n"
    assert check.main([]) == 2


def workflow() -> dict:
    return yaml.safe_load(RELEASE.read_text(encoding="utf-8"))


def steps(job: str) -> list[dict]:
    return workflow()["jobs"][job]["steps"]


def test_release_yml_is_named_release_and_runs_only_on_a_v_tag():
    # why: Task 7's pages.yml follows it by this name (workflow_run, Phase 4 Decision 2), and only
    # a tag Dan pushes makes a release (AGENTS.md: tags and releases are Dan's).
    wf = workflow()
    assert wf["name"] == "release"
    assert wf[True] == {"push": {"tags": ["v*"]}}  # PyYAML reads the key `on` as True


def test_only_the_publish_job_can_write():
    # why: the build job runs the repository's code and npm's install scripts, so it gets
    # nothing it could misuse; publishing needs these three and nothing else (spec §23.1).
    wf = workflow()
    assert wf["permissions"] == {"contents": "read"}
    assert set(wf["jobs"]) == {"build", "publish"}
    assert wf["jobs"]["build"]["permissions"] == {"contents": "read"}
    assert wf["jobs"]["publish"]["permissions"] == {
        "contents": "write", "id-token": "write", "attestations": "write"}
    assert not any("uses" in s and "checkout" in s["uses"] for s in steps("publish"))


def test_a_published_release_is_never_overwritten():
    # why: Review Focus 4. gh release create refuses a tag whose release is published ("a
    # release with the same tag name already exists", gh's release/create source) and never
    # uploads into an existing release; gh release upload --clobber, gh release edit or a
    # release action's update mode would replace a published wheel or sdist.
    text = RELEASE.read_text(encoding="utf-8")
    runs = [s.get("run", "") for job in ("build", "publish") for s in steps(job)]
    writes = [r for r in runs if "gh release create" in r]
    assert len(writes) == 1 and "--verify-tag" in writes[0]
    for forbidden in ("--clobber", "gh release upload", "gh release edit", "gh release delete",
                      "gh api", "overwrite:"):
        assert forbidden not in text, forbidden
    uses = {s["uses"].split("@")[0] for job in ("build", "publish") for s in steps(job)
            if "uses" in s}
    assert uses <= {"actions/checkout", "astral-sh/setup-uv", "actions/setup-node",
                    "actions/upload-artifact", "actions/download-artifact", "actions/attest"}
    names = [s.get("uses", s.get("run", "")) for s in steps("publish")]
    view = next(i for i, n in enumerate(names) if "gh release view" in n)
    attest = next(i for i, n in enumerate(names) if n.startswith("actions/attest@"))
    create = next(i for i, n in enumerate(names) if "gh release create" in n)
    assert view < attest < create  # an existing release stops the run before anything is made


def test_the_tag_is_checked_before_the_build_and_the_files_after():
    runs = [s.get("run", "") for s in steps("build")]
    tag = runs.index('uv run scripts/release_check.py "$TAG"')
    build = runs.index("make dist")
    files = runs.index('uv run scripts/release_check.py "$TAG" dist')
    assert tag < build < files


def test_every_action_is_pinned_and_no_run_step_expands_an_expression():
    # why: spec §23.1; and a tag name may hold `$(...)`, so it reaches a shell only through env.
    text = RELEASE.read_text(encoding="utf-8")
    for line in text.splitlines():
        if "uses:" in line:
            assert re.search(r"uses: [\w.-]+/[\w.-]+@[0-9a-f]{40} # v\d", line), line
    for job in ("build", "publish"):
        for s in steps(job):
            assert "${{" not in s.get("run", ""), s["run"]
            if s.get("uses", "").startswith("actions/checkout@"):
                assert s["with"]["persist-credentials"] is False
```

- [ ] **Step 13: Run them; watch them fail.** `uv run pytest tests/test_release.py -q`.
  Expected: `5 failed, 7 passed`, each failure `FileNotFoundError: [Errno 2] No such file or
  directory: '…/.github/workflows/release.yml'`.
- [ ] **Step 14: Write the workflow,** `.github/workflows/release.yml`:

```yaml
# Releases (spec §23.4, S52): on a v* tag, build the frontend, then the wheel and the sdist with
# www/ inside (make dist), check them against the tag, and publish a GitHub Release with
# build-provenance attestations. It never deploys Pages: pages.yml follows this workflow by its
# name (Phase 4 Decision 2), since a release made with the GITHUB_TOKEN starts no workflow itself.
# A release is never overwritten: a tag that has one fails here (Review Focus 4). Only the
# publish job can write, and it runs no code from the repository.
name: release
on:
  push:
    tags: ["v*"]
# One run per tag at a time, never cancelled midway.
concurrency:
  group: release-${{ github.ref }}
  cancel-in-progress: false
permissions:
  contents: read

jobs:
  build:
    runs-on: ubuntu-24.04
    timeout-minutes: 15
    permissions:
      contents: read
    env:
      UV_FROZEN: "1"
      TAG: ${{ github.ref_name }} # reaches a shell only as "$TAG"
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with: { persist-credentials: false }
      # No caches: a release is built from the tag's tree and pinned downloads only.
      - uses: astral-sh/setup-uv@1c37ad07a6a961277cf70c0d37d6f313000f5884 # v10.3.0
        with: { version: "0.13.1", enable-cache: false }
      - uses: actions/setup-node@949feb2413d6458794dcd2491c4babbbce0c15c1 # v7.1.0
        with: { node-version-file: frontend/.nvmrc, package-manager-cache: false }
      - name: the tag names the package's version
        run: uv run scripts/release_check.py "$TAG"
      - run: npm ci
        working-directory: frontend
      - run: make dist
      - name: dist/ holds the tag's wheel and sdist, each with the frontend
        run: uv run scripts/release_check.py "$TAG" dist
      - uses: actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9 # v7.0.2
        with:
          name: dist
          path: dist/vid2sub-*
          if-no-files-found: error
          retention-days: 7

  publish:
    needs: build
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    permissions:
      contents: write # create the release
      id-token: write # sign the attestations through Sigstore
      attestations: write # store them
    env:
      GH_TOKEN: ${{ github.token }}
      GH_REPO: ${{ github.repository }}
      TAG: ${{ github.ref_name }}
    steps:
      - uses: actions/download-artifact@9000827ccba6bdab643e8b6fd33ac0654aef8333 # v8.0.2
        with: { name: dist, path: dist }
      - name: the tag has no release yet
        run: |
          if gh release view "$TAG" > /dev/null 2>&1; then
            echo "::error::$TAG has a release already, and a release's files are never replaced: tag a new version"
            exit 1
          fi
      - uses: actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6 # v4.2.2
        with: { subject-path: dist/vid2sub-* }
      # gh release create refuses a tag whose release is published, and never uploads into one.
      - name: publish the release
        run: >-
          gh release create "$TAG" dist/vid2sub-* --verify-tag
          --title "vid2sub ${TAG#v}"
          --notes "vid2sub ${TAG#v}: the wheel and the sdist, each with a build-provenance
          attestation (gh attestation verify <file> --repo $GH_REPO). What changed is in
          CHANGELOG.md."
```

- [ ] **Step 15: Run the checks; they pass.** `uv run pytest tests/test_release.py -q`: `12
  passed`. `make actionlint`: its command line only, exit 0. The build job's steps, here, with
  Node 22:

```bash
export UV_FROZEN=1 TAG=v0.1.0.dev0
uv run scripts/release_check.py "$TAG"
(cd frontend && npm ci)
make dist
uv run scripts/release_check.py "$TAG" dist
unset UV_FROZEN TAG
```

  Expected: `release check: v0.1.0.dev0 names the package's version`, the two
  `Successfully built` lines, then `release check: v0.1.0.dev0 names the package's version, and
  dist holds its wheel and sdist with the frontend`. uv also prints ``warning: No lockfile found
  for Python script (ignoring `--frozen`)``: the check script has no dependencies and no lock,
  and UV_FROZEN stays for §23.1. The guards, each reverted after: with the publish step's first
  line changed to `gh release upload "$TAG" dist/vid2sub-* --clobber`, `FAILED
  tests/test_release.py::test_a_published_release_is_never_overwritten`; with the build job's
  `contents: read` changed to `contents: write`, `FAILED
  tests/test_release.py::test_only_the_publish_job_can_write`. Then `make check`. Expected:
  `967 passed, 2 skipped, 26 deselected` (twice), `Test Files  12 passed (12)`, `Tests  55
  passed (55)`, `All checks passed!`, `no leaks found`.
- [ ] **Step 16: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
ci(release): 🤖 a v* tag builds the wheel and sdist, checks them against the tag, and publishes a GitHub Release with build-provenance attestations, never over an existing one

Spec §23.4, S52, and Phase 4's Review Focus 4. release.yml, named `release` (Task 7's pages.yml
follows it by that name, Phase 4 Decision 2), runs on `push: tags: ["v*"]` only:

- build (contents: read): checkout without credentials; uv 0.13.1 and Node from .nvmrc, both
  with caching off, so a release is made from the tag's tree and pinned downloads only;
  `release_check.py "$TAG"` before anything is built; npm ci; make dist; `release_check.py
  "$TAG" dist`; dist/vid2sub-* uploaded as the run's `dist` artifact.
- publish (contents, id-token and attestations: write, and nothing else; no checkout, so no
  repository code runs with them): download `dist` (download-artifact fails on a digest
  mismatch by default); stop if `gh release view "$TAG"` finds a release, before anything is
  made; actions/attest, build provenance for both files; `gh release create "$TAG"
  dist/vid2sub-* --verify-tag`. gh release create refuses a tag whose release is published
  ("a release with the same tag name already exists", read in cli/cli's
  pkg/cmd/release/create/create.go) and uploads only into the draft it creates; --verify-tag
  stops it creating a tag. It never runs gh release upload, whose --clobber replaces assets.
- The tag reaches a shell only as "$TAG" (env), never as an expression in a run step.
- Every action is pinned by SHA with its version comment (git ls-remote): ci.yml's checkout,
  setup-uv, setup-node and upload-artifact, plus download-artifact v8.0.2 and actions/attest
  v4.2.2. attest-build-provenance v4's README says it is now a wrapper over actions/attest and
  that new workflows should use actions/attest, whose default is SLSA build provenance; its
  provenance example needs only id-token and attestations: write (artifact-metadata is for
  registry storage records, which need push-to-registry).

tests/test_release.py pins it: the name and trigger; only publish can write, exactly those three,
with no checkout; one gh release create with --verify-tag and no --clobber, gh release upload,
edit, delete, gh api or `overwrite:`, the actions an allowlist, and the release looked up
before the attestation and the create; the tag checked before make dist and the files after;
every action pinned and no `${{` in a run step. They failed with no release.yml
(FileNotFoundError, 5 failed); with the create swapped for `gh release upload "$TAG"
dist/vid2sub-* --clobber`, "FAILED tests/test_release.py::test_a_published_release_is_never_
overwritten"; with the build job given contents: write, "FAILED
tests/test_release.py::test_only_the_publish_job_can_write".

Run locally: the build job's steps with TAG=v0.1.0.dev0 ("release check: v0.1.0.dev0 names the
package's version, and dist holds its wheel and sdist with the frontend"; uv warns that it
ignores UV_FROZEN for a script, which has no lockfile); the publish job's two shell steps
against a stand-in gh: with no release, one create with both files, --verify-tag, the title and
notes as one argument each; with one, "::error::v0.1.0.dev0 has a release already" and exit 1.
make actionlint: no findings.

Docs read: actions/attest v4.2.2's README and action.yml; attest-build-provenance v4.2.2's and
v3.2.0's READMEs and action.yml; actions/download-artifact v8.0.2's README (name, path,
digest-mismatch); actions/upload-artifact v7.0.2's README; setup-uv v10.3.0's README
(enable-cache, off by default on tag pushes anyway); setup-node v7.1.0's README
(package-manager-cache); the gh manual for release create and `gh release create --help`
(gh 2.103.1; the ubuntu-24.04 image has 2.102.0); GitHub's GITHUB_TOKEN docs (events it
triggers start no workflow).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-4.md Task 8
Co-Authored-By: <the model's own line>
```

  `git add .github/workflows/release.yml tests/test_release.py`, `git commit -F
  .git/COMMIT_MSG`, then `git log -1 --format='%(trailers)'` shows `Plan:`.

#### Round 8d: the security review's fixes

When this listing was built, one independent Tier 1 reviewer went over rounds 8a–8c with
`AGENTS.md`'s security checklist. Its findings, each fixed in this round: the pre-check read
any `gh release view` failure as "no release", and gh release create doesn't see drafts, which
is what deleting a tag leaves (Important); the test passed with that step neutered
(Important); nothing stopped a tag made on the phase branch (Important, a judgement call); a tag
moved between build and publish (Minor); concurrency unpinned (Minor); the notes' verify command
named no signer workflow (Minor); the plan copy lacked Decision 2 (Minor, docs). Its one
re-review found the round sound, with one Minor gap (the stand-in gh ignored its arguments, so
`--exclude-drafts` passed), fixed in the test below. Repo settings it recommends for Dan are in
the close.

- [ ] **Step 17: Write the failing tests.** Replace `tests/test_release.py` with:

```python
"""A release carries the editor and can't go out wrong (spec §23.4, S52): the wheel and the sdist
hold the built frontend, which git ignores. Each guard here fails without its fix (Phase 4 Task 8).

The build runs on a copy of the project, with stand-ins for www/ui.js and ui.css, the real
pyproject.toml and the .gitignore lines that hide them, so it needs no frontend build and leaves
the checkout alone; it is make dist's `uv build`, with the same flags, and needs the network the
first time (hatchling and its dependencies, hash-pinned in build-constraints.txt).
"""

from __future__ import annotations

import importlib.util
import io
import os
import re
import shlex
import shutil
import subprocess
import tarfile
import tomllib
import zipfile
from pathlib import Path

import pytest
import yaml

import vid2sub

REPO = Path(__file__).resolve().parents[1]
FRONTEND = ("vid2sub/web/www/ui.js", "vid2sub/web/www/ui.css")
RELEASE = REPO / ".github/workflows/release.yml"
# make dist's flags (Makefile): change them together.
BUILD = ("build", "--no-sources", "--clear", "--build-constraints", "build-constraints.txt",
         "--require-hashes")


def release_check():
    spec = importlib.util.spec_from_file_location("release_check",
                                                  REPO / "scripts" / "release_check.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def version() -> str:
    return tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "version"]


def build_copy(tmp: Path) -> Path:
    """The project's packaging files and src/ in `tmp`, with stand-in frontend files, built into
    `tmp`/dist as make dist builds; returns that folder."""
    project = tmp / "project"
    project.mkdir()
    for name in ("pyproject.toml", "README.md", "LICENSE", "build-constraints.txt"):
        shutil.copy2(REPO / name, project / name)
    # Only the real .gitignore's lines for the frontend's build output, which are what hide it:
    # hatchling drops every .gitignore pattern when one matches the project's own absolute path
    # (as `var/` matches macOS's /var/folders/ temp folder; hatchling's
    # load_vcs_exclusion_patterns), which would let this test pass without its fix. Anchored
    # lines can't match it.
    gitignore = (REPO / ".gitignore").read_text(encoding="utf-8").splitlines()
    hide = [line for line in gitignore if line.startswith("src/vid2sub/web/www/")]
    assert hide == ["src/vid2sub/web/www/ui.js", "src/vid2sub/web/www/ui.css"]
    (project / ".gitignore").write_text("\n".join(hide) + "\n", encoding="utf-8")
    shutil.copytree(REPO / "src", project / "src",
                    ignore=shutil.ignore_patterns("__pycache__", "ui.js", "ui.css"))
    www = project / "src/vid2sub/web/www"
    (www / "ui.js").write_text("// stand-in bundle\n", encoding="utf-8")
    (www / "ui.css").write_text("/* stand-in styles */\n", encoding="utf-8")
    uv = os.environ.get("UV") or shutil.which("uv")
    assert uv, "uv not found: run the tests with `uv run pytest`"
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    done = subprocess.run([uv, *BUILD, "--out-dir", str(tmp / "dist")], cwd=project, env=env,
                          check=False, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr[-3000:]
    return tmp / "dist"


def test_a_built_wheel_and_sdist_hold_the_built_frontend(tmp_path):
    # why: www/ui.js and ui.css are build output that .gitignore hides, and hatchling leaves out
    # what git ignores unless pyproject.toml lists it under `artifacts`; without them a release
    # installs a `vid2sub serve` with no editor (spec §23.5: "Release wheels already contain it").
    dist = build_copy(tmp_path)
    v = version()
    with zipfile.ZipFile(dist / f"vid2sub-{v}-py3-none-any.whl") as wheel:
        names = set(wheel.namelist())
        assert [f for f in FRONTEND if f not in names] == []
        assert wheel.read("vid2sub/web/www/ui.js") == b"// stand-in bundle\n"
    with tarfile.open(dist / f"vid2sub-{v}.tar.gz") as sdist:
        names = set(sdist.getnames())
    assert [f for f in FRONTEND if f"vid2sub-{v}/src/{f}" not in names] == []


def test_the_package_version_is_the_same_in_pyproject_and_the_package():
    # why: the wheel is named for pyproject.toml's version and `vid2sub --version` prints
    # vid2sub.__version__, so a release whose two differ says the wrong one somewhere.
    assert vid2sub.__version__ == version()


def test_the_release_check_refuses_a_tag_that_isnt_the_package_version():
    # why: the tag names the release, and Task 9's index lists its wheel under the package's
    # version; a published release's files are never replaced, so a mismatch stops it first.
    check = release_check()
    v = version()
    assert check.tag_problems(f"v{v}") == []
    assert check.tag_problems("v9.9.9") == [f"the tag 'v9.9.9' isn't v{v}, pyproject.toml's version"]
    assert check.tag_problems(v) == [f"the tag {v!r} isn't v{v}, pyproject.toml's version"]


def test_the_release_check_refuses_a_package_whose_two_versions_differ(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "1.0.0"\n', encoding="utf-8")
    (tmp_path / "src/vid2sub").mkdir(parents=True)
    (tmp_path / "src/vid2sub/__init__.py").write_text('__version__ = "1.0.1"\n', encoding="utf-8")
    assert release_check().tag_problems("v1.0.0", root=tmp_path) == [
        "vid2sub.__version__ is '1.0.1', not pyproject.toml's '1.0.0'"]


def test_the_release_check_refuses_a_dist_without_the_frontend_or_with_other_files(tmp_path):
    with zipfile.ZipFile(tmp_path / "vid2sub-1.0.0-py3-none-any.whl", "w") as wheel:
        wheel.writestr("vid2sub/web/www/ui.js", "// built\n")  # no ui.css
    with tarfile.open(tmp_path / "vid2sub-1.0.0.tar.gz", "w:gz") as sdist:
        data = b"/* built */\n"
        info = tarfile.TarInfo("vid2sub-1.0.0/src/vid2sub/web/www/ui.css")
        info.size = len(data)
        sdist.addfile(info, io.BytesIO(data))  # no ui.js
    (tmp_path / "vid2sub-0.9.0-py3-none-any.whl").write_bytes(b"")  # a stale build
    (tmp_path / ".gitignore").write_text("*\n", encoding="utf-8")  # uv build writes this one
    assert release_check().dist_problems("v1.0.0", tmp_path) == [
        (f"{tmp_path} holds vid2sub-0.9.0-py3-none-any.whl, vid2sub-1.0.0-py3-none-any.whl, "
         "vid2sub-1.0.0.tar.gz, not just vid2sub-1.0.0-py3-none-any.whl and vid2sub-1.0.0.tar.gz"),
        "vid2sub-1.0.0-py3-none-any.whl lacks vid2sub/web/www/ui.css",
        "vid2sub-1.0.0.tar.gz lacks src/vid2sub/web/www/ui.js",
    ]
    assert release_check().dist_problems("v2.0.0", tmp_path)[0].endswith(
        "not just vid2sub-2.0.0-py3-none-any.whl and vid2sub-2.0.0.tar.gz")


def test_the_release_check_accepts_what_make_dist_builds(tmp_path):
    dist = build_copy(tmp_path)
    assert release_check().dist_problems(f"v{version()}", dist) == []


def test_the_release_check_exits_1_naming_each_problem(capsys):
    check = release_check()
    assert check.main(["v9.9.9"]) == 1
    assert capsys.readouterr().err == (
        f"release check: the tag 'v9.9.9' isn't v{version()}, pyproject.toml's version\n")
    assert check.main([f"v{version()}"]) == 0
    assert capsys.readouterr().out == f"release check: v{version()} names the package's version\n"
    assert check.main([]) == 2


def workflow() -> dict:
    return yaml.safe_load(RELEASE.read_text(encoding="utf-8"))


def steps(job: str) -> list[dict]:
    return workflow()["jobs"][job]["steps"]


def step(job: str, name: str) -> dict:
    return next(s for s in steps(job) if s.get("name") == name)


def git(cwd: Path, *args: str) -> str:
    """git in `cwd`, with no user or system configuration (no hooks, no signing)."""
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
           "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.invalid"}
    done = subprocess.run(["git", *args], cwd=cwd, env=env, check=True, capture_output=True,
                          text=True)
    return done.stdout.strip()


def run_step(script: str, cwd: Path, env: dict[str, str],
             gh: str | None = None) -> subprocess.CompletedProcess:
    """A run step's script as the runner runs it under `shell: bash`, with a stand-in `gh`
    whose body is `gh`, if given."""
    path = os.environ["PATH"]
    if gh is not None:
        bin_dir = cwd / "bin"
        bin_dir.mkdir(exist_ok=True)
        (bin_dir / "gh").write_text(f"#!/bin/bash\n{gh}\n", encoding="utf-8")
        (bin_dir / "gh").chmod(0o755)
        path = f"{bin_dir}{os.pathsep}{path}"
    full = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
            "PATH": path, **env}
    return subprocess.run(["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", script],
                          cwd=cwd, env=full, check=False, capture_output=True, text=True)


# The run steps are bash on ubuntu-24.04; the Linux and macOS jobs run these, not Windows'.
bash_steps = pytest.mark.skipif(os.name == "nt", reason="release.yml's run steps are bash")


def test_release_yml_is_named_release_and_runs_only_on_a_v_tag():
    # why: Task 7's pages.yml follows it by this name (workflow_run, Phase 4 Decision 2), and only
    # a tag Dan pushes makes a release (AGENTS.md: tags and releases are Dan's).
    wf = workflow()
    assert wf["name"] == "release"
    assert wf[True] == {"push": {"tags": ["v*"]}}  # PyYAML reads the key `on` as True
    # one run per tag at a time, never cancelled midway (a cancel could leave a draft behind)
    assert wf["concurrency"] == {"group": "release-${{ github.ref }}", "cancel-in-progress": False}
    assert wf["defaults"] == {"run": {"shell": "bash"}}  # -eo pipefail: a failing command fails


def test_only_the_publish_job_can_write():
    # why: the build job runs the repository's code and npm's install scripts, so it gets
    # nothing it could misuse; publishing needs these three and nothing else (spec §23.1).
    wf = workflow()
    assert wf["permissions"] == {"contents": "read"}
    assert set(wf["jobs"]) == {"build", "publish"}
    assert wf["jobs"]["build"]["permissions"] == {"contents": "read"}
    assert wf["jobs"]["publish"]["permissions"] == {
        "contents": "write", "id-token": "write", "attestations": "write"}
    assert not any("uses" in s and "checkout" in s["uses"] for s in steps("publish"))


def test_a_published_release_is_never_overwritten():
    # why: Review Focus 4. gh release create refuses a tag whose release is published ("a
    # release with the same tag name already exists", gh's release/create source) and uploads
    # only into the draft it makes, but it doesn't see drafts, and deleting a tag turns its
    # release into one: the step before it catches those. gh release upload --clobber, gh
    # release edit or a release action's update mode would replace a published wheel or sdist.
    text = RELEASE.read_text(encoding="utf-8")
    runs = [s.get("run", "") for job in ("build", "publish") for s in steps(job)]
    writes = [r for r in runs if "gh release create" in r]
    assert len(writes) == 1 and "--verify-tag" in writes[0]
    for forbidden in ("--clobber", "gh release upload", "gh release edit", "gh release delete",
                      "gh api", "overwrite:"):
        assert forbidden not in text, forbidden
    uses = {s["uses"].split("@")[0] for job in ("build", "publish") for s in steps(job)
            if "uses" in s}
    assert uses <= {"actions/checkout", "astral-sh/setup-uv", "actions/setup-node",
                    "actions/upload-artifact", "actions/download-artifact", "actions/attest"}
    order = [s.get("name") or s.get("uses", "").split("@")[0] for s in steps("publish")]
    assert order == ["actions/download-artifact", "the tag has no release yet",
                     "the tag still names the commit this run built", "actions/attest",
                     "publish the release"]  # nothing is made before both checks pass


@bash_steps
def test_a_tag_with_a_release_published_or_draft_stops_the_run_and_so_does_a_gh_error(tmp_path):
    script = step("publish", "the tag has no release yet")["run"]
    env = {"TAG": "v1.0.0", "GH_REPO": "owner/repo"}
    # the stand-in answers only this call: --exclude-drafts, or a lower limit, would fail it
    listing = '[ "$*" = "release list --limit 1000 --json tagName --jq .[].tagName" ] || exit 3; '
    listed = run_step(script, tmp_path, env, gh=listing + 'printf "v0.9.0\\nv1.0.0\\n"')
    assert listed.returncode == 1
    assert listed.stdout.startswith("::error::v1.0.0 has a release already (published or draft)")
    others = run_step(script, tmp_path, env,
                      gh=listing + 'printf "v1.0.0-rc1\\nv1.0.00\\nv0.9.0\\n"')
    assert (others.returncode, others.stdout) == (0, "")
    assert run_step(script, tmp_path, env, gh=listing).returncode == 0  # no release at all
    failed = run_step(script, tmp_path, env, gh='echo "HTTP 502" >&2; exit 1')
    assert failed.returncode != 0  # a lookup that fails never reads as "no release"


@bash_steps
def test_the_release_is_made_from_the_two_files_with_verify_tag(tmp_path):
    (tmp_path / "dist").mkdir()
    for name in ("vid2sub-1.0.0-py3-none-any.whl", "vid2sub-1.0.0.tar.gz"):
        (tmp_path / "dist" / name).write_bytes(b"")
    record = tmp_path / "argv"
    gh = f'for a in "$@"; do printf "%s\\0" "$a"; done > {shlex.quote(str(record))}'
    done = run_step(step("publish", "publish the release")["run"], tmp_path,
                    {"TAG": "v1.0.0", "GH_REPO": "owner/repo"}, gh=gh)
    assert done.returncode == 0, done.stderr
    argv = record.read_text(encoding="utf-8").split("\0")[:-1]
    assert argv[:3] == ["release", "create", "v1.0.0"]
    assert sorted(argv[3:5]) == ["dist/vid2sub-1.0.0-py3-none-any.whl", "dist/vid2sub-1.0.0.tar.gz"]
    assert argv[5:] == [
        "--verify-tag", "--title", "vid2sub 1.0.0", "--notes",
        ("vid2sub 1.0.0: the wheel and the sdist, each with a build-provenance attestation (gh "
         "attestation verify <file> --repo owner/repo --signer-workflow "
         "owner/repo/.github/workflows/release.yml). What changed is in CHANGELOG.md.")]


@bash_steps
def test_a_tag_off_main_is_refused(tmp_path):
    # why: a release is permanent and the index offers it to `uv tool upgrade`; Task 12's step 9b
    # tags main's merge commit, and this catches a tag made on the phase branch instead.
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "commit", "-q", "--allow-empty", "-m", "merged")
    merged = git(repo, "rev-parse", "HEAD")
    git(repo, "update-ref", "refs/remotes/origin/main", merged)
    git(repo, "switch", "-q", "-c", "phase-4")
    git(repo, "commit", "-q", "--allow-empty", "-m", "not merged")
    unmerged = git(repo, "rev-parse", "HEAD")
    script = step("build", "the tag is on main")["run"]
    assert run_step(script, repo, {"TAG": "v1.0.0", "GITHUB_SHA": merged}).returncode == 0
    refused = run_step(script, repo, {"TAG": "v1.0.0", "GITHUB_SHA": unmerged})
    assert refused.returncode == 1
    assert refused.stdout.startswith("::error::v1.0.0 isn't on main")


@bash_steps
def test_a_tag_moved_during_the_run_stops_it(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "commit", "-q", "--allow-empty", "-m", "built")
    built = git(repo, "rev-parse", "HEAD")
    git(repo, "tag", "-a", "v1.0.0", "-m", "vid2sub 1.0.0")  # annotated, as step 9b makes it
    git(repo, "commit", "-q", "--allow-empty", "-m", "later")
    later = git(repo, "rev-parse", "HEAD")
    script = step("publish", "the tag still names the commit this run built")["run"]
    env = {"TAG": "v1.0.0", "REPO_URL": str(repo)}
    assert run_step(script, tmp_path, {**env, "GITHUB_SHA": built}).returncode == 0
    moved = run_step(script, tmp_path, {**env, "GITHUB_SHA": later})
    assert moved.returncode == 1
    assert moved.stdout.startswith("::error::v1.0.0 no longer names")
    unread = run_step(script, tmp_path, {**env, "GITHUB_SHA": built,
                                         "REPO_URL": str(tmp_path / "missing")})
    assert unread.returncode != 0


def test_the_tag_is_checked_before_the_build_and_the_files_after():
    build = workflow()["jobs"]["build"]
    assert build["steps"][0]["with"]["fetch-depth"] == 0  # main's history, for the next check
    order = [s.get("name") or s.get("run") or s["uses"].split("@")[0] for s in build["steps"]]
    assert order.index("the tag names the package's version") < order.index("the tag is on main")
    assert order.index("the tag is on main") < order.index("npm ci") < order.index("make dist")
    assert order.index("make dist") < order.index(
        "dist/ holds the tag's wheel and sdist, each with the frontend")
    assert step("build", "the tag names the package's version")["run"] == (
        'uv run scripts/release_check.py "$TAG"')
    assert step("build", "dist/ holds the tag's wheel and sdist, each with the frontend")[
        "run"] == 'uv run scripts/release_check.py "$TAG" dist'


def test_every_action_is_pinned_and_no_run_step_expands_an_expression():
    # why: spec §23.1; and a tag name may hold `$(...)`, so it reaches a shell only through env.
    text = RELEASE.read_text(encoding="utf-8")
    for line in text.splitlines():
        if "uses:" in line:
            assert re.search(r"uses: [\w.-]+/[\w.-]+@[0-9a-f]{40} # v\d", line), line
    for job in ("build", "publish"):
        for s in steps(job):
            assert "${{" not in s.get("run", ""), s["run"]
            if s.get("uses", "").startswith("actions/checkout@"):
                assert s["with"]["persist-credentials"] is False
```

- [ ] **Step 18: Run them; watch them fail.** `uv run pytest tests/test_release.py -q`.
  Expected: `7 failed, 9 passed`: `FAILED
  tests/test_release.py::test_release_yml_is_named_release_and_runs_only_on_a_v_tag`,
  `…::test_a_published_release_is_never_overwritten`,
  `…::test_a_tag_with_a_release_published_or_draft_stops_the_run_and_so_does_a_gh_error`,
  `…::test_the_release_is_made_from_the_two_files_with_verify_tag`,
  `…::test_a_tag_off_main_is_refused - StopIteration`,
  `…::test_a_tag_moved_during_the_run_stops_it - StopIteration`,
  `…::test_the_tag_is_checked_before_the_build_and_the_files_after`.
- [ ] **Step 19: Fix the workflow.** Replace `.github/workflows/release.yml` with:

```yaml
# Releases (spec §23.4, S52): on a v* tag, build the frontend, then the wheel and the sdist with
# www/ inside (make dist), check them against the tag, and publish a GitHub Release with
# build-provenance attestations. It never deploys Pages: pages.yml follows this workflow by its
# name (Phase 4 Decision 2), since a release made with the GITHUB_TOKEN starts no workflow itself.
# A release is never overwritten: a tag that has one, published or draft, fails here (Review
# Focus 4). Only the publish job can write, and it runs no code from the repository.
name: release
on:
  push:
    tags: ["v*"]
# One run per tag at a time, never cancelled midway.
concurrency:
  group: release-${{ github.ref }}
  cancel-in-progress: false
permissions:
  contents: read
# Every run step as `bash --noprofile --norc -eo pipefail`: a failing command anywhere fails it.
defaults:
  run:
    shell: bash

jobs:
  build:
    runs-on: ubuntu-24.04
    timeout-minutes: 15
    permissions:
      contents: read
    env:
      UV_FROZEN: "1"
      TAG: ${{ github.ref_name }} # reaches a shell only as "$TAG"
    steps:
      # All of history, so the next steps can see main.
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with: { persist-credentials: false, fetch-depth: 0 }
      # No caches: a release is built from the tag's tree and pinned downloads only.
      - uses: astral-sh/setup-uv@1c37ad07a6a961277cf70c0d37d6f313000f5884 # v10.3.0
        with: { version: "0.13.1", enable-cache: false }
      - uses: actions/setup-node@949feb2413d6458794dcd2491c4babbbce0c15c1 # v7.1.0
        with: { node-version-file: frontend/.nvmrc, package-manager-cache: false }
      - name: the tag names the package's version
        run: uv run scripts/release_check.py "$TAG"
      - name: the tag is on main
        run: |
          git merge-base --is-ancestor "$GITHUB_SHA" origin/main || {
            echo "::error::$TAG isn't on main: tag main's merge commit (git tag -a $TAG origin/main)"
            exit 1
          }
      - run: npm ci
        working-directory: frontend
      - run: make dist
      - name: dist/ holds the tag's wheel and sdist, each with the frontend
        run: uv run scripts/release_check.py "$TAG" dist
      - uses: actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9 # v7.0.2
        with:
          name: dist
          path: dist/vid2sub-*
          if-no-files-found: error
          retention-days: 7

  publish:
    needs: build
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    permissions:
      contents: write # create the release
      id-token: write # sign the attestations through Sigstore
      attestations: write # store them
    env:
      GH_TOKEN: ${{ github.token }}
      GH_REPO: ${{ github.repository }}
      REPO_URL: ${{ github.server_url }}/${{ github.repository }}
      TAG: ${{ github.ref_name }}
    steps:
      - uses: actions/download-artifact@9000827ccba6bdab643e8b6fd33ac0654aef8333 # v8.0.2
        with: { name: dist, path: dist }
      # Drafts too: gh release create sees only a published release, and deleting a tag turns its
      # release into a draft. A gh error fails the step rather than reading as "no release".
      - name: the tag has no release yet
        run: |
          tags=$(gh release list --limit 1000 --json tagName --jq '.[].tagName')
          if grep -Fxq -- "$TAG" <<< "$tags"; then
            echo "::error::$TAG has a release already (published or draft), and a release's files are never replaced: tag a new version, or delete a draft that was never published"
            exit 1
          fi
      - name: the tag still names the commit this run built
        run: |
          refs=$(git ls-remote "$REPO_URL" "refs/tags/$TAG" "refs/tags/$TAG^{}")
          awk -v sha="$GITHUB_SHA" '$1 == sha { found = 1 } END { exit !found }' <<< "$refs" || {
            echo "::error::$TAG no longer names $GITHUB_SHA, the commit this run built"
            exit 1
          }
      - uses: actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6 # v4.2.2
        with: { subject-path: dist/vid2sub-* }
      # gh release create refuses a tag whose release is published, uploads only into the draft it
      # makes, and deletes that draft if an upload fails.
      - name: publish the release
        run: >-
          gh release create "$TAG" dist/vid2sub-* --verify-tag
          --title "vid2sub ${TAG#v}"
          --notes "vid2sub ${TAG#v}: the wheel and the sdist, each with a build-provenance
          attestation (gh attestation verify <file> --repo $GH_REPO --signer-workflow
          $GH_REPO/.github/workflows/release.yml). What changed is in CHANGELOG.md."
```

- [ ] **Step 20: Run the checks; they pass.** `uv run pytest tests/test_release.py -q`: `16
  passed` (on Windows the five bash-step tests skip; the Linux and macOS jobs run them). The
  guards, each reverted after:
  - the pre-check's two lines `tags=$(gh release list …)` and `if grep -Fxq -- "$TAG" <<<
    "$tags"; then` replaced by `if gh release view "$TAG" > /dev/null 2>&1; then`: `FAILED
    tests/test_release.py::test_a_tag_with_a_release_published_or_draft_stops_the_run_and_so_does_a_gh_error`;
  - `git merge-base --is-ancestor "$GITHUB_SHA" origin/main || {` changed to `… origin/main ||
    true || {`: `FAILED tests/test_release.py::test_a_tag_off_main_is_refused`;
  - the moved-tag step's `<<< "$refs" || {` changed to `<<< "$refs" || true || {`: `FAILED
    tests/test_release.py::test_a_tag_moved_during_the_run_stops_it`;
  - `cancel-in-progress: false` changed to `true`: `FAILED
    tests/test_release.py::test_release_yml_is_named_release_and_runs_only_on_a_v_tag`;
  - `--exclude-drafts` added to the pre-check's `gh release list`: `FAILED
    tests/test_release.py::test_a_tag_with_a_release_published_or_draft_stops_the_run_and_so_does_a_gh_error`
    (the stand-in gh answers only the exact call).

  Each prints `1 failed, 15 passed`. Then `make actionlint` (its command line only, exit 0) and
  `make check`. Expected: `971 passed, 2 skipped, 26 deselected` (twice), `Test Files  12
  passed (12)`, `Tests  55 passed (55)`, `All checks passed!`, `no leaks found`.
- [ ] **Step 21: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
fix(release): 🤖 release.yml stops on a draft as well as a published release, on a failed lookup, on a tag off main and on a tag moved mid-run

The Tier 1 security review's round (one independent reviewer, AGENTS.md's checklist), each
finding fixed here:

- Important: the pre-check read any `gh release view` failure as "no release", and gh release
  create sees only published releases, while deleting a tag turns its release into a draft. The
  step now lists every release, drafts included (`gh release list --limit 1000 --json tagName`),
  matches the tag as a whole line, and a gh error fails it. Every run step is
  `bash --noprofile --norc -eo pipefail` (`defaults: run: shell: bash`); the matches read
  here-strings, not pipes into `grep -q`, which pipefail could misread.
- Important: the test only found the step by name and passed with the step neutered. The tests
  now run each guarding step's script as the runner does, with a stand-in gh or a scratch git
  repository: a listed tag stops the run, a near miss (v1.0.0-rc1) doesn't, a gh error does;
  the create's arguments are exactly the tag, the two files, --verify-tag and one title and one
  notes argument. The stand-in answers only the exact list call, so --exclude-drafts (which
  reopens the draft hole) fails the test too. With the old lookup back, "FAILED tests/test_release.py::test_a_tag_with_a_
  release_published_or_draft_stops_the_run_and_so_does_a_gh_error".
- Important (a judgement call): nothing stopped a tag made on the phase branch, which would
  publish unmerged code for good. Checkout fetches all history, and `git merge-base
  --is-ancestor "$GITHUB_SHA" origin/main` runs before npm ci. Neutered with `|| true`, "FAILED
  tests/test_release.py::test_a_tag_off_main_is_refused".
- Minor: a tag moved between build and publish would hang the files on another commit. Before
  the attestation, `git ls-remote "$REPO_URL"` must still give $GITHUB_SHA for the tag (peeled,
  so an annotated tag counts); neutered, "FAILED tests/test_release.py::test_a_tag_moved_during_
  the_run_stops_it".
- Minor: concurrency ("never cancelled midway") wasn't pinned; it is, with the bash default
  (with cancel-in-progress true, the name-and-trigger test fails).
- Minor: the notes' verify command now names the signer workflow (`--signer-workflow
  <repo>/.github/workflows/release.yml`), as gh's attestation manual advises.
- Minor (docs): release.yml and the tests cite Phase 4 Decision 2, which this branch's plan
  copy lacked; a90afd7 brought the plan up to the main repository's.

Left to repo settings (Dan's), for the phase end's step 9b: immutable releases, a tag ruleset on
refs/tags/v* (creation, update and deletion by Dan only), branch protection on main. A modified
release.yml on a tagged commit can drop any check here; only those settings stop that.

Docs read: `gh release list --help` (drafts listed unless --exclude-drafts; JSON field tagName);
GitHub's workflow syntax for `defaults.run.shell` (`shell: bash` runs
`bash --noprofile --norc -eo pipefail {0}`, an unspecified one `bash -e {0}`); git's merge-base
manual (--is-ancestor: 0 if an ancestor, 1 if not, another non-zero on an error) and ls-remote
manual (patterns match a ref's tail).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-4.md Task 8
Co-Authored-By: <the model's own line>
```

  `git add .github/workflows/release.yml tests/test_release.py`, `git commit -F
  .git/COMMIT_MSG`, then `git log -1 --format='%(trailers)'` shows `Plan:`.
- [ ] **Step 22: Review, look forward, close.** The Tier 1 review from `$(cat .git/TASK_BASE)`
  (`AGENTS.md`, *Reviews*, with the security checklist; at most one re-review). Worth the
  reviewers' time: the GITHUB_TOKEN's permissions in each job and what code runs while they are
  held (the publish job has no checkout); what a tag pushed from a fork can do (nothing here: a
  fork's push runs the fork's copy with the fork's token) and what a tag on a commit off `main`
  does (refused before the build); that the tag reaches a shell only as `"$TAG"`; every action
  pinned by SHA (`git ls-remote`), uv 0.13.1, hatchling by hash, npm by the lockfile's
  integrity; that no path replaces a published release's files: a re-run, the same tag pushed
  again after a delete (its release is then a draft), a cancel mid-create, two runs at once;
  that a failed lookup never reads as "no release"; that each guard test fails without its
  fix. The checklist, as the listing's own review found it: secrets fine (none used;
  `GH_TOKEN` by reference, in the publish job only; checkout without credentials); permissions
  fine (build `contents: read`; publish exactly the three, no repository code); network
  exposure fine (nothing listens; outbound to GitHub, npm, PyPI for hash-pinned hatchling, the
  uv download, Sigstore); failing closed fine after round 8d; injection fine (env only, no
  `${{` in a run step, ref names can't hold `:` or a newline); logging fine (the tag, file
  names, `dist`; attestations go to the public Rekor log, as a public repo's should).
  CI can't run this workflow before a tag, so the first proof is Task 12's step 9c.

  The forward review over Tasks 7, 9, 10, 11 and 12:
  - Task 7's `pages.yml` follows `workflows: [release]`, so this workflow's `name: release`
    must not change; it deploys only when that run succeeded.
  - Task 9's index lists `vid2sub-<version>-py3-none-any.whl` from each release; a release
    holds only that wheel and the sdist, and the build refuses anything else in `dist/`.
  - Task 10's README and docs: `make dist`, `make build-constraints`, how a release is cut
    (bump both versions, merge, tag `main`), and verifying a download with
    `gh attestation verify <file> --repo chendaniely/vid2sub --signer-workflow
    chendaniely/vid2sub/.github/workflows/release.yml`.
  - Task 12's step 9b: tag `main`'s merge commit explicitly, `git fetch origin && git tag -a
    v<version> origin/main -m "vid2sub <version>"`, since a tag off `main` is refused; the
    version is what `scripts/release_check.py` accepts (both `pyproject.toml` and
    `vid2sub.__version__`; `0.1.0.dev0` unless bumped first). Its settings checklist gains,
    before the first tag: immutable releases (Settings → General → Releases), a tag ruleset on
    `refs/tags/v*` restricting creation, update and deletion to Dan, and branch protection on
    `main` requiring CI. Its step 9c's verify adds `--signer-workflow
    chendaniely/vid2sub/.github/workflows/release.yml`. If a run leaves a draft (a cancel or a
    failed clean-up), Dan deletes the draft and re-runs; the pre-check says so.

  The docs this task made untrue: spec §23.4's `release.yml` line gains "it refuses a tag that
  isn't the package's version or isn't on `main`, and a tag that has a release already". Then
  the close, its own commit, holding this plan with this task's boxes ticked and **Now** set to
  `Task 9: The install index and its smoke test, open.`, and the spec's §23.4 line and its S52
  row set to `built`, its Proof reading `tests/test_release.py; the release.yml and pages.yml
  runs on the first tag (Task 12, step 9c)`, with the message in `.git/CLOSE_MSG`:

```text
docs(plan): 🤖 close Task 8: `release.yml`

Drift: none
Rulings: none
Phase-end: none
Forward: none
Tier: 1
Rounds: <Matt's code-review, Standards and Spec in two subagents; any re-review>; the security
  checklist: secrets <fine / a finding>; permissions <…>; network exposure <…>; failing closed
  <…>; injection <…>; logging <…>
Findings: none

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-4.md Task 8
Co-Authored-By: <the model's own line>
```

  `git add docs/superpowers/plans/2026-10-23-vid2sub-phase-4.md
  docs/superpowers/specs/2026-10-14-vid2sub-design.md`, `git commit -F .git/CLOSE_MSG`.

***

### Task 9: The install index and its smoke test

**Tier:** 2 · **Scenarios:** S51

**Interfaces:**
- Consumes: Task 8's releases, whose assets are exactly `vid2sub-<version>-py3-none-any.whl`
  and `vid2sub-<version>.tar.gz`; Task 8 sets S52 to `built`, and the index keeps its "the index
  lists it" half true. Task 7's `pages.yml` runs the index build when `release` succeeds
  (Decision 2).

<!-- steps: written in the next pass -->

***

### Task 10: The README and the docs

**Tier:** 3

**Interfaces:**
- Consumes, from Tasks 2–4: the README gives `make pages`, `make pages-serve` and
  `make pages-test`; the Pages editor's **Open folder** (read and write in Chrome and Edge,
  read-only with downloads in Safari and Firefox); the demo; that the editor refuses to run in a
  frame; and that a reload asks for the folder again (handles are never kept).
  `docs/architecture.md` draws the Pages site (Task 1 drew `web.folder` and the browser backend).

<!-- steps: written in the next pass -->

***

### Task 11: The M4 exit test (with Dan)

**Tier:** 3 · **Scenarios:** S47, S48, S50 · **[Dan]**, on Dan's Mac

Spec §25's M4 exit test, the part that can run before the PR (Decision 1): Pages in Chrome and in
Safari, on the site `make pages` builds and `make pages-serve` serves on this machine, which is
the artifact `pages.yml` uploads. The live site, the first release and the install from the index
need `main`, a tag and a deploy, so they run after the merge, as Task 12's step 9. §29's M4
checks are recorded here (the Pyodide and Shinylive versions at build time; Safari's File System
Access status). The implementer prepares and records; Dan runs every step.

**Files:**
- Modify: `docs/superpowers/specs/2026-10-14-vid2sub-design.md` (§29's M4 results, the Scenarios
  rows, Open items)

**Interfaces:**
- Consumes: Task 2's `make pages` (the site in `_site/`) and `make pages-serve` (serves it under
  `/vid2sub/` with Range requests on `127.0.0.1`, as `recordings` does); Task 3's folder picker,
  Save and Download; Task 5's demo.

- [ ] **Step 0: Record the base:** `git rev-parse HEAD > .git/TASK_BASE`.
- [ ] **Step 1: List the [Dan] steps** (2 to 6 below), one line each, with the count, then present
  Step 2. Set **Now** to `waiting on Dan: Task 11, Step 2` in a wip commit
  (`chore(plan): 🤖 wip Task 11: waiting on Dan for the M4 exit test`; `Done so far:` the list,
  `Stopped at:` Step 2, `Tests:` `make check`, `make e2e` and `make pages-test` green at the
  base).
- [ ] **Step 2: [Dan] Build and serve the site:**

```bash
make pages
make pages-serve
```

  Expected: the terminal prints the address it serves. Open it in Chrome; the editor loads with
  no install, and the browser's console shows no error.
- [ ] **Step 3: [Dan] In Chrome, open a folder, edit and save (S47):** **Open folder**, pick the
  folder of an episode Phase 2's exit test used, allow read and write, and pick the episode from
  the list. Fix two source lines.
  Before saving, test the re-read: in a terminal, run `vid2sub serve`, open the same episode
  there, change one English line, and Save. Then Save in Chrome. Expected: both changes are kept:
  reopen the episode in either and see your two source fixes and the English line. The subtitle
  files next to the video are rewritten. Then, with the episode still open, move its folder in the
  Finder and Save: nothing is written, the notice says the folder isn't where it was, and the
  edits stay in the tab (Review Focus 1). Last, open a multi-gigabyte video's folder: it opens
  at once and plays, and the tab's memory in Activity Monitor stays flat (Review Focus 2).
- [ ] **Step 4: [Dan] In Safari, edit and download (S48):** open the same address in Safari and
  pick the folder (Safari reads it only). Fix one line, then **Download**. Expected: the sidecar
  and every subtitle file it projects download (and the glossary, if there is one), a quarter
  second apart; Safari may ask once to allow several downloads. Put them next to the video,
  replacing the old ones, and reopen the episode in Chrome: the fix is there.
- [ ] **Step 5: [Dan] The demo (S50):** from the start screen, open the demo. Expected: the
  public-domain clip plays with its captions and its translation.
- [ ] **Step 6: [Dan] Hand back the notes** from Steps 2–5, with Chrome's and Safari's versions.
- [ ] **Step 7: Record the results in the spec.**
  - §29's M4 bullet, dated: the Pyodide and Shinylive versions the build used (`make pages`
    prints them, Task 2), and Safari's File System Access status from Step 4.
  - Set S48 and S50 to `verified` where they passed.
  - S47 stays `built` until the live check (Task 12, step 9).
  - A failure caused by a bug is a new task, proposed to Dan; a result that would change the spec
    is the fifth stop.
- [ ] **Step 8: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
docs(spec): 🤖 M4's exit test results on the built site: <what passed, in one line>

<each result in a line: Chrome's save and the re-read, Safari's download, the demo, the browser
versions, the Pyodide and Shinylive versions; the rows set to verified; what waits for the live
check after the merge>

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-4.md Task 11
Co-Authored-By: <the model's own line>
```

  `git add docs/superpowers/specs/2026-10-14-vid2sub-design.md`, `git commit -F .git/COMMIT_MSG`,
  then `git log -1 --format='%(trailers)'` shows `Plan:`.
- [ ] **Step 9: Review, look forward, close.** The Tier 3 self-review from
  `$(cat .git/TASK_BASE)` (*Standards*, *Spec*) plus `make check`; the forward review over Task
  12's step 9 (what Steps 3 and 4 found changes what the live check looks for). Then the close,
  its own commit, holding this plan with this task's boxes ticked and **Now** set to
  `Phase end, step 1: The final whole-branch review.`, with the message in `.git/CLOSE_MSG`:

```text
docs(plan): 🤖 close Task 11: The M4 exit test (with Dan)

Drift: none
Rulings: none
Phase-end: none
Forward: none
Tier: 3
Rounds: self-review (Standards, Spec); make check
Findings: none

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-4.md Task 11
Co-Authored-By: <the model's own line>
```

  `git add docs/superpowers/plans/2026-10-23-vid2sub-phase-4.md
  docs/superpowers/specs/2026-10-14-vid2sub-design.md`, `git commit -F .git/CLOSE_MSG`.

***

### Task 12: Phase end

Each box is one step of plan-driven-development's phase end, run as its `references/phase-end.md`
gives it, in the project's root folder on `phase-4`. A step ends with its commit
(`docs(plan): 🤖 phase end step K: <what it did>`, trailer
`Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-4.md Phase end`), which ticks its box and
sets **Now** to `Phase end, step K+1: <its title>.` After a crash, resume at the first unticked
box; never re-run a ticked one.

If the hooks and `scripts/leakcheck.py` still don't exist by then (`AGENTS.md`'s interim line),
two steps differ: step 8's text scans run `gitleaks stdin` only, and the merge waits for Dan, as
every push does. Phase 4 is the last phase, so step 5 offers the spec's Later rows to Dan, and
step 9's results go out in a short PR of their own, since no phase start follows to carry the
status line's `merged` entry (Decision 1).

- [ ] **1. The final whole-branch review:** Matt Pocock's two-axis `code-review` from
  `git merge-base main HEAD`; then one fix dispatch and one scoped re-review (`AGENTS.md`,
  *Reviews*), with a ruling on whatever is left. Each fix is its own commit.
- [ ] **2. The rest of the ledger copied into the plan:** whatever
  `.superpowers/sdd/2026-10-23-vid2sub-phase-4/progress.md` holds that no closing commit carries,
  under the task it belongs to.
- [ ] **3. The phase-end council:** four read-only reviewers (goal fit and scenarios,
  reliability, security, simplicity) on the whole branch; their reports committed first, in
  `docs/superpowers/plans/2026-10-23-vid2sub-phase-4-end-council.md`; each claim checked against
  the code before Dan sees it; each finding a severity and a decision.
- [ ] **4. The phase-end list worked through:** each row of this plan's Phase-end list fixed in
  its own commit at the tier of what it touches, or moved to the spec's Later with a reason.
  Missing docs are written now; in `docs/architecture.md`, Phase 4's parts turn solid.
- [ ] **5. The forward look, at the last phase:** each row of the spec's Later (its Scenarios
  S54–S62 and §25's **Later** line) offered to Dan by *Asking Dan*: plan it, keep it optional, or
  drop it. Each answer is recorded on the Q&A page with his reason, and committed then.
- [ ] **6. The retro:** `docs/superpowers/plans/2026-10-23-vid2sub-phase-4-retro.md`, in four
  parts (departures from the plan, items carried forward, metrics per tier, starting over), from
  the closing commits:

```bash
base=$(git merge-base main HEAD)
git log --format='%h %s%n%b' --grep='close Task' "$base..HEAD"
git log --format='%h %s' --grep='reopen Task' --grep='escaped from Task' "$base..HEAD"
```

- [ ] **7. A dated `CHANGELOG.md` entry** for Phase 4, and the spec's status line set to
  `Phase 4 (M4) PR open (#N)`, its number filled in once step 8 opens the PR. The first
  release's version is set here too, in both `pyproject.toml` and `vid2sub.__version__`, since
  Task 8's check needs both to match the tag. The version is Dan's, asked by *Asking Dan*.
- [ ] **8. The PR:** superpowers:finishing-a-development-branch, its PR option. The title is
  `chore(repo): 🤖 merge Phase 4: Pages and releases`; the body summarises what each task built,
  the council's findings and what became of them, links the retro, lists every file no scan can
  read for Dan to check by eye, says that the live checks and the first release follow the merge
  (step 9), and ends with `Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-4.md Phase end`.
  The files no scan can read:

```bash
git log --format= --numstat origin/main..HEAD |
  awk '$1 == "-" { print "not scanned, check by eye: " $3 }'
```

  With the title in `.git/PR_TITLE` and the body in `.git/PR_BODY.md`, then, after Dan's OK to
  push and open it:

```bash
if cat .git/PR_TITLE .git/PR_BODY.md |
     gitleaks stdin --redact --no-banner --config .gitleaks.toml; then
  gh pr create --base main --head phase-4 \
    --title "$(cat .git/PR_TITLE)" --body-file .git/PR_BODY.md
else
  echo "STOP: the PR text has a finding; tell Dan its kind and where, never the matched text"
fi
```

  Attended: the PR waits for Dan's merge (a merge commit, never squash or rebase).
- [ ] **9. After the merge: the live site, the first release and the install (S47, S51, S52).**
  Tags, releases and repo settings are Dan's (`AGENTS.md`, *Stops*), so the agent lists these
  steps, presents them one at a time (*Asking Dan*), and runs only the read-only checks.
  - [ ] **9a. The live site:** `pages.yml`'s run on the merge commit is green, and
    `https://chendaniely.github.io/vid2sub/` serves the editor. **[Dan]** In Chrome, repeat Task
    11's Step 3 on the live site, without the re-read part (S47).
  - [ ] **9b. [Dan] The first release.** First the settings Task 8's review named (Settings →
    General, and Settings → Rules): turn on immutable releases; add a tag ruleset on
    `refs/tags/v*` so only you can create, move or delete those tags; and check that `main`'s
    ruleset from kickoff is on. Then tag `main` as GitHub has it, with step 7's version
    (`release.yml` refuses a tag off `main`, or one that doesn't match the package's version):
    `git fetch origin`, `git tag -a v<version> origin/main -m "vid2sub <version>"`, then
    `git push origin v<version>`.
  - [ ] **9c. The release and the index (S52):** `release.yml` and the `pages.yml` run its
    success starts (Decision 2) are green; then the read-only checks:

```bash
gh release view "v<version>" --json assets --jq '.assets[].name'
gh release download "v<version>" --pattern '*.whl' --dir .git/release-check
gh attestation verify .git/release-check/*.whl --repo chendaniely/vid2sub \
  --signer-workflow chendaniely/vid2sub/.github/workflows/release.yml
curl -fsS https://chendaniely.github.io/vid2sub/simple/vid2sub/ | grep -c '#sha256='
```

    Expected: the wheel and the sdist; the attestation verifies; the index lists the wheel with
    its `#sha256=` fragment (a count of at least 1). Then `rm -r .git/release-check`.
  - [ ] **9d. The install from the index (S51):** the post-deploy smoke job is green on all three
    operating systems. **[Dan]** On a clean machine (or a fresh user account) with uv:
    `uv tool install 'vid2sub[mac]' --index https://chendaniely.github.io/vid2sub/simple/`,
    then `vid2sub --version` and `vid2sub serve`. Expected: the release's version, and the
    editor opens, so the frontend came with the wheel.
  - [ ] **9e. The results PR:** from `main`, a branch `phase-4-live` holds one commit,
    `docs(spec): 🤖 M4's live results: <what passed>`, trailer
    `Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-4.md Phase end`. It sets S47, S51 and
    S52 to `verified` where they passed, sets the status line to `Phase 4 (M4) merged <sha>
    <date>`, records the release in §29's M4 bullet and adds the release to `CHANGELOG.md`.
    Then, after Dan's OK to push it, its PR, scanned and opened as step 8's was, waits for Dan's
    merge.

***

## Phase-end list

| Source task | Severity | File | Finding | Status |
|---|---|---|---|---|
| Task 3 (planning) | Minor | `frontend/src/lib/folder.ts` | Only the sidecar is compared before a write, so a subtitle file another program creates in that moment is written over (§14.6 asks for the sidecar only) | open |
| Task 3 (planning) | Minor | `frontend/src/lib/folder.ts` | After a close fails past the sidecar, the notice says nothing was saved, though the sidecar was | open |
| Task 3 (planning) | Minor | `src/vid2sub/web/browser.py` | On a case-sensitive disk, vid2sub's spelling beside a case variant of its own file makes a duplicate | open |
