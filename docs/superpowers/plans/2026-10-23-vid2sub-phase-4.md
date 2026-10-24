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

<!-- written with the listings -->

***

### Task 1: The browser backend

**Tier:** 2 · **Scenarios:** S47

**Interfaces:**
- Consumes: Phase 2's Pages-safe server (Phase 2 Task 14, round 14a): `vid2sub.web.server` and
  `views` import only what the bundle has; the types they share are in `vid2sub.web.episode`; the
  local runtime is configured, not imported, and `runtime.blocking` is the one place blocking
  calls run, so Pages configures a `Runtime` holding a `BrowserBackend` and an inline `blocking`
  before importing the server, as `recordings`' `pages/app.py` does.

<!-- steps: written in the next pass -->

***

### Task 2: The Pages build

**Tier:** 2 · **Scenarios:** S47, S50

<!-- steps: written in the next pass -->

***

### Task 3: Opening and saving local files in the browser

**Tier:** 1 · **Scenarios:** S47, S48

<!-- steps: written in the next pass -->

***

### Task 4: No frames, no network: the Pages test

**Tier:** 1 · **Scenarios:** S49

<!-- steps: written in the next pass -->

***

### Task 5: The demo clip

**Tier:** 3 · **Scenarios:** S50 · Step 1 is **[Dan]**: choosing the public-domain clip

<!-- steps: written in the next pass -->

***

### Task 6: The Pyodide job

**Tier:** 3 · **Scenarios:** S53

<!-- steps: written in the next pass -->

***

### Task 7: `pages.yml`

**Tier:** 1 · **Scenarios:** S50, S51

<!-- steps: written in the next pass -->

***

### Task 8: `release.yml`

**Tier:** 1 · **Scenarios:** S52

**Interfaces:**
- Consumes: the frontend build (Phase 2 Task 12). Hatchling leaves the git-ignored
  `src/vid2sub/web/www/ui.js` and `ui.css` out of a wheel, so the build needs them listed as
  `artifacts` in `pyproject.toml`, and `npm ci && npm run build` runs before `uv build`.

<!-- steps: written in the next pass -->

***

### Task 9: The install index and its smoke test

**Tier:** 2 · **Scenarios:** S51

<!-- steps: written in the next pass -->

***

### Task 10: The README and the docs

**Tier:** 3

<!-- steps: written in the next pass -->

***

### Task 11: The M4 exit test and the first release (with Dan)

**Tier:** 3 · **Scenarios:** S47, S48, S51, S52 · **[Dan]**

<!-- steps: written in the next pass -->

***

### Task 12: Phase end

<!-- steps: written in the next pass -->

***

## Phase-end list

| Source task | Severity | File | Finding | Status |
|---|---|---|---|---|
