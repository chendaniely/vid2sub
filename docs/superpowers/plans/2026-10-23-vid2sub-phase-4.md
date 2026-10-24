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

**Interfaces:**
- Consumes: Phase 2's Pages-safe server (Phase 2 Task 14, round 14a): `vid2sub.web.server` and
  `views` import only what the bundle has; the types they share are in `vid2sub.web.episode`; the
  local runtime is configured, not imported, and `runtime.blocking` is the one place blocking
  calls run. `blocking` already runs inline when `runtime.INLINE` (`sys.platform ==
  "emscripten"`), which Phase 2 couldn't check in Pyodide; this task checks it first. So Pages
  configures a `Runtime` holding a `BrowserBackend` before importing the server, as
  `recordings`' `pages/app.py` does. Two `Runtime` methods are local-only: `media_for` (Pages
  plays a blob URL) and `reachable`. This task says what each does in the browser.

<!-- steps: written in the next pass -->

***

### Task 2: The Pages build

**Tier:** 2 · **Scenarios:** S47, S50

**Interfaces:**
- Produces, for Task 11 and `pages.yml` (Task 7), as `recordings`' `Makefile` has them:
  `make pages` builds the site into `_site/` and prints the Pyodide and Shinylive versions it
  used; `make pages-serve` serves `_site/` under `/vid2sub/` with Range requests on `127.0.0.1`
  and prints the address; `make pages-test` runs the Pages Playwright tests (Task 4).

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

**Interfaces:**
- Consumes: spec §23.3's triggers, with Decision 2's `workflow_run` in place of
  `release: published`. Task 8's `release.yml` is named `release` and runs on `v*` tag pushes
  only. `workflow_run` fires for any completed run of a workflow by that name, a fork's pull
  request included, so the deploy job runs only when `github.event.workflow_run.conclusion` is
  `success`, its `event` is `push`, and its `head_repository.full_name` is
  `github.repository`. It checks out `main`, never the triggering run's `head_sha`. The Tier 1
  review checks each condition, with a test over the workflow file. Read GitHub's docs on
  `workflow_run` and on environments' deployment branches, and say in the commit what you read.

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
  folder of an episode Phase 2's exit test used, and allow read and write. Fix two source lines.
  Before saving, test the re-read: in a terminal, run `vid2sub serve`, open the same episode
  there, change one English line, and Save. Then Save in Chrome. Expected: both changes are kept:
  reopen the episode in either and see your two source fixes and the English line. The subtitle
  files next to the video are rewritten.
- [ ] **Step 4: [Dan] In Safari, edit and download (S48):** open the same address in Safari and
  pick the folder (Safari reads it only). Fix one line, then **Download**. Expected: the subtitle
  files and the sidecar download. Put them next to the video, replacing the old ones, and reopen
  the episode in Chrome: the fix is there.
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
  `Phase 4 (M4) PR open (#N)`, its number filled in once step 8 opens the PR.
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
  - [ ] **9b. [Dan] The first release:** on `main`'s merge commit, tag the version that Task 8's
    check accepts (the tag must match the package's version), and push the tag:
    `git tag -a v<version> -m "vid2sub <version>"`, then `git push origin v<version>`.
  - [ ] **9c. The release and the index (S52):** `release.yml` and the `pages.yml` run its
    success starts (Decision 2) are green; then the read-only checks:

```bash
gh release view "v<version>" --json assets --jq '.assets[].name'
gh release download "v<version>" --pattern '*.whl' --dir .git/release-check
gh attestation verify .git/release-check/*.whl --repo chendaniely/vid2sub
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
