# vid2sub Phase 3 (M3): adding, reviewing, and every platform — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking. Every rule for running a task is in `AGENTS.md`; this
> plan never restates them.

**Goal:** add a season folder or a YouTube link from the app, review the suggested languages and
models, and run it unattended, pausing on a dropped connection and resuming where it stopped; play
any episode through a preview copy; and transcribe on Windows and Linux with `faster-whisper`.

**Architecture:** the Add, Review and Models screens are new views over the core M1 already has
(`detect.py`, `catalog.py`, the pipeline) and Phase 2's job queue, which gains pause and resume.
The in-app file browser is a backend listing with spec §6.5's rules. `faster-whisper` is a third
in-process engine behind the Engine protocol, with a pure parser.

**Tech Stack:** as Phase 2's, plus `faster-whisper` (the `[whisper]` and `[nvidia]` extras) and
ffmpeg's H.264 encoders (VideoToolbox, NVENC, QSV, else `libx264`).

**Spec:** `docs/superpowers/specs/2026-10-14-vid2sub-design.md`

**Now:** Task 1: The in-app file browser, open. (Phase 3 starts after Phase 2's PR merges; its
listings are run and revised at its phase start.)

## Global Constraints

Phase 2's Global Constraints, in full (`docs/superpowers/plans/2026-10-23-vid2sub-phase-2.md`),
plus:

- The file browser lists home and mounted volumes (`/Volumes`, drive letters, `/media`, `/mnt`),
  shows only folders, video and subtitle files, and hides dotfiles and credential folders
  (`.ssh`, `.aws`, `.gnupg`, `.config/gh`, …); accepted paths are fully qualified; UNC paths only
  when typed or browsed to (spec §6.5).
- **Allow cloud models for this run** starts unticked every time; no config key or environment
  variable can preset it (spec §7.2).
- Never fall back to another model or to the cloud when a model fails (spec §17.4).

## Review Focus

<!-- written with the listings -->

***

### Task 1: The in-app file browser

**Tier:** 1 · **Scenarios:** S38

<!-- steps: written in the next pass -->

***

### Task 2: The Add screen

**Tier:** 2 · **Scenarios:** S38, S39

<!-- steps: written in the next pass -->

***

### Task 3: Sampling and suggestions for Review

**Tier:** 2 · **Scenarios:** S40

<!-- steps: written in the next pass -->

***

### Task 4: The Review screen

**Tier:** 2 · **Scenarios:** S40

<!-- steps: written in the next pass -->

***

### Task 5: The queue pauses and resumes

**Tier:** 2 · **Scenarios:** S41, S42

<!-- steps: written in the next pass -->

***

### Task 6: The Jobs page grows up

**Tier:** 2 · **Scenarios:** S41

<!-- steps: written in the next pass -->

***

### Task 7: The preview copy

**Tier:** 2 · **Scenarios:** S63

<!-- steps: written in the next pass -->

***

### Task 8: The Models page

**Tier:** 2 · **Scenarios:** S44

<!-- steps: written in the next pass -->

***

### Task 9: The `faster-whisper` engine

**Tier:** 2 · **Scenarios:** S45

<!-- steps: written in the next pass -->

***

### Task 10: CI on Windows and Linux for `faster-whisper`

**Tier:** 3 · **Scenarios:** S45

<!-- steps: written in the next pass -->

***

### Task 11: The docs

**Tier:** 3

<!-- steps: written in the next pass -->

***

### Task 12: The M3 exit test (with Dan)

**Tier:** 3 · **Scenarios:** S38, S40, S41, S45 · **[Dan]**

<!-- steps: written in the next pass -->

***

### Task 13: Phase end

<!-- steps: written in the next pass -->

***

## Phase-end list

| Source task | Severity | File | Finding | Status |
|---|---|---|---|---|
