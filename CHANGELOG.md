# Changelog

## 2026-10-23: plan-driven-development adopted

vid2sub now follows plan-driven-development (`AGENTS.md`). M1, the command line end to end, was
built and merged on 2026-10-15 (#2) before the workflow existed, and counts as Phase 1. Phases
2–4 are M2 (the editor), M3 (adding, reviewing, every platform) and M4 (Pages and releases), each
with its own plan and pull request.

The kickoff added `make check`, `make help`, `make test-utc`, `make leaks` and `make hooks`; the
spec's status line, Outline, Scenarios, Open items and Revisions; and `docs/architecture.md`. It
moved the playback audio and the cache from M3 into Phase 2, so the editor has sound for any
episode, and made M1's exit test Phase 2's first task.
