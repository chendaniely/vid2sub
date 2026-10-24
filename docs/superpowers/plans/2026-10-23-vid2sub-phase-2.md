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

<!-- steps: written in the next pass -->

***

### Task 2: Edit operations

**Tier:** 2 · **Scenarios:** S28

**Files:**
- Create: `src/vid2sub/subs/edit.py`
- Test: `tests/test_edit.py`

**Interfaces:**
- Consumes: `vid2sub.subs.model.Cue`, `new_cue_id(taken)`, `check_track(cues)`;
  `vid2sub.subs.text.canonical(text)`.
- Produces (pure; every function returns a new `Tracks` and never mutates its input):
  - `class EditError(ValueError)`
  - `@dataclass(frozen=True) class Tracks: source: tuple[Cue, ...]; translations:
    Mapping[str, tuple[Cue, ...]]` (target track key → cues)
  - `follow(source: Sequence[Cue], translation: Sequence[Cue]) -> tuple[Cue, ...]`: each cue
    that isn't `detached` takes the span of its `src` cues.
  - `set_text(t, cue_id: str, text: str) -> Tracks`
  - `set_translation_text(t, track: str, cue_id: str, text: str) -> Tracks` (adds `edited`)
  - `set_times(t, cue_id: str, *, start_ms: int | None = None, end_ms: int | None = None)
    -> Tracks` (clamped to the neighbours; `EditError` if nothing is left)
  - `nudge(t, cue_id: str, delta_ms: int, *, edge: Literal["start", "end", "both"] = "both")
    -> Tracks`
  - `split(t, cue_id: str, *, at_char: int, at_ms: int, taken: set[str])
    -> tuple[Tracks, tuple[str, str]]`
  - `merge_next(t, cue_id: str, *, taken: set[str]) -> tuple[Tracks, str]`
  - `insert(t, *, start_ms: int, end_ms: int, text: str, taken: set[str])
    -> tuple[Tracks, str]`
  - `delete(t, cue_id: str) -> Tracks`
  - `detach(t, track: str, cue_id: str, detached: bool) -> Tracks`
  - `replace_all(t, find: str, replace: str, *, tracks: Sequence[str]) -> tuple[Tracks, int]`
    (`"source"` names the source track; returns the count replaced)

<!-- steps: written in the next pass -->

***

### Task 3: The cache and the playback audio

**Tier:** 2 · **Scenarios:** S43, S46

**Files:**
- Create: `src/vid2sub/cache.py`, `src/vid2sub/media/preview.py`,
  `src/vid2sub/commands/cache.py`
- Modify: `src/vid2sub/cli.py` (register `cache`), `src/vid2sub/commands/doctor.py` (cache size)
- Test: `tests/test_cache.py`, `tests/test_playback.py`

**Interfaces:**
- Consumes: `vid2sub.media.tools.Tools`, `run_tool`, `input_args`; `vid2sub.config.Config`
  (`defaults.cache_max_gb`); `platformdirs.user_cache_dir`.
- Produces:
  - `cache.default_root() -> Path` (the platform cache directory + `vid2sub`, spec §8.9)
  - `class Cache: __init__(self, root: Path, *, max_bytes: int)`; `folder(self, key: str) -> Path`
    (`key` is a 64-hex `quick_sha256`; creates the folder 0700 and marks it used);
    `size(self) -> int`; `evict(self, *, keep: str | None = None) -> int` (least recently used
    first, never `keep`; returns bytes freed); `clear(self) -> int` (removes only 64-hex
    folders; returns bytes freed)
  - `preview.playback_audio(video: Path, *, key: str, audio_index: int, tools: Tools, cache: Cache,
    timeout: float) -> Path` (AAC stereo `.m4a`, made once per key and track, metadata stripped)
  - `vid2sub cache clear [--json]`

<!-- steps: written in the next pass -->

***

### Task 4: The job queue

**Tier:** 2 · **Scenarios:** S36

**Files:**
- Create: `src/vid2sub/jobs.py`
- Modify: `src/vid2sub/pipeline.py` (`RunContext.cancelled`, `Cancelled`, checks between chunks
  and batches)
- Test: `tests/test_jobs.py`, `tests/test_pipeline.py` (cancellation)

**Interfaces:**
- Consumes: `pipeline.run_one(source, ctx) -> InputResult`, `pipeline.Event`,
  `pipeline.InputResult`.
- Produces:
  - `pipeline.Cancelled(Exception)`; `RunContext.cancelled: Callable[[], bool]` (default: never)
  - `jobs.JobState = Literal["queued", "running", "done", "failed", "cancelled"]`
  - `@dataclass(frozen=True) class JobView: id: str; input: str; state: JobState;
    stage: str | None; progress: tuple[int, int] | None; result: InputResult | None;
    hint: str | None`
  - `Runner = Callable[[str, Event, Callable[[], bool]], InputResult]`
  - `class Queue: __init__(self, runner: Runner)`; `submit(self, inputs: Sequence[str])
    -> list[str]`; `cancel(self, job_id: str) -> bool`; `jobs(self) -> list[JobView]`;
    `on_change(self, fn: Callable[[], None]) -> None`; `close(self, timeout: float = 5.0) -> None`.
    One worker thread runs one job at a time (spec §17.1).

<!-- steps: written in the next pass -->

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

**Interfaces:**
- Produces: `guards.LOCAL_HOSTS`; `class HostGuard: __init__(self, app: ASGIApp,
  allowed: frozenset[str])`; `class WriteGuard: __init__(self, app: ASGIApp,
  allowed: frozenset[str])`; `guards.CSP: str`; `guards.MEDIA_HEADERS: dict[str, str]`

<!-- steps: written in the next pass -->

***

### Task 9: The launch token

**Tier:** 1 · **Scenarios:** S23, S24

**Files:**
- Create: `src/vid2sub/web/auth.py`, `src/vid2sub/web/static/auth.html`,
  `src/vid2sub/web/static/auth.js`
- Test: `tests/test_web_auth.py`

**Interfaces:**
- Produces: `auth.new_token() -> str`; `auth.cookie_name(port: int) -> str`
  (`vid2sub-<port>`); `auth.write_redirect(url: str) -> Path` (mode 0600 in a 0700 temp folder);
  `class TokenGuard: __init__(self, app: ASGIApp, *, token: str, port: int)` (every HTTP route and
  websocket needs the cookie except `/auth`, `/auth.js` and `/healthz`);
  `auth.routes(token: str, port: int) -> list[BaseRoute]` (`GET /auth`, `POST /auth`,
  `GET /auth.js`)

<!-- steps: written in the next pass -->

***

### Task 10: Media tokens and `/media/{token}`

**Tier:** 1 · **Scenarios:** S27, S43

**Files:**
- Create: `src/vid2sub/web/media.py`
- Test: `tests/test_web_media.py`

**Interfaces:**
- Produces: `class MediaTokens: issue(self, path: Path, *, owner: str) -> str` (records
  `(st_dev, st_ino, st_size)`); `resolve(self, token: str) -> Path | None` (None when unknown,
  revoked, or the file was swapped); `revoke_owner(self, owner: str) -> None`;
  `media.route(tokens: MediaTokens) -> BaseRoute` (`GET /media/{token}`: Range, `inline`)

<!-- steps: written in the next pass -->

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

**Tier:** 2 · **Scenarios:** S22 · Step 1 is **[Dan]**, on the Spark once local-ai serves
Qwen3-ASR with its forced aligner

<!-- steps: written in the next pass -->

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

<!-- steps: written in the next pass -->

***

### Task 24: Phase end

<!-- steps: written in the next pass -->

***

## Phase-end list

| Source task | Severity | File | Finding | Status |
|---|---|---|---|---|
