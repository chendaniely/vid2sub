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
  `recordings`' `pages/app.py` does. These `Runtime` parts are local-only: `media_for` (Pages
  plays a blob URL), `reachable`, and, from Phase 2 Tasks 17–19, `retranslate`, `endpoint_models`
  and `job_context`. The server offers Retranslate, the settings drawer and the Jobs page only
  where `capabilities.generate` is true (Phase 2 Decision 23), so Pages calls none of the last
  three; its `session` (a `vid2sub.web.settings.Session`, bundled) still gives Save's default
  formats. This task says what each does in the browser.

<!-- steps: written in the next pass -->

***

### Task 2: The Pages build

**Tier:** 2 · **Scenarios:** S47, S50

**Interfaces:**
- Produces, for Task 11 and `pages.yml` (Task 7), as `recordings`' `Makefile` has them:
  `make pages` builds the site into `_site/` and prints the Pyodide and Shinylive versions it
  used; `make pages-serve` serves `_site/` under `/vid2sub/` with Range requests on `127.0.0.1`
  and prints the address; `make pages-test` runs the Pages Playwright tests (Task 4).
- Consumes: the versions Task 6's Pyodide job installs, which are `uv.lock`'s (pysubs2 1.9.0,
  opencc-purepy 1.4.4, charset-normalizer 3.5.2 when Task 6 was written). Vendor those wheels;
  take charset-normalizer from PyPI, not Pyodide 0.27.7's own 3.3.2, which is below
  `pyproject.toml`'s `>=3.4`.

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
- Modify: `frontend/package.json` and `frontend/package-lock.json` (`pyodide` 0.27.7, exact),
  `Makefile` (`test-pyodide`), `.github/workflows/ci.yml` (the `pyodide` job)
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
  - `frontend/package.json` devDependency `"pyodide": "0.27.7"`; the harness refuses any other
    version.

The `make check` counts below come from a clone with Phase 2's Tasks 2–16 and 21 only; yours
are higher. What matters is no failure, ruff's `All checks passed!` and gitleaks'
`no leaks found`; `make test-pyodide`'s file list grows with every pure test added since.

- [ ] **Step 0: Record the base:** `git rev-parse HEAD > .git/TASK_BASE`.
- [ ] **Step 1: Watch the target fail.** `make test-pyodide`. Expected (GNU make 3.81):
  ``make: *** No rule to make target `test-pyodide'.  Stop.``
- [ ] **Step 2: Add Pyodide to the frontend's dev dependencies.** With Node 22 (`nvm use 22`):

```bash
cd frontend && npx --yes npm@11.11.1 install --save-dev --save-exact pyodide@0.27.7 && cd ..
git diff --stat frontend/
```

  npm 11 because it wrote the lockfile: Node 22's npm 10 also drops the lock's `libc` fields.
  Expected: `frontend/package-lock.json | 36 ++++` and `frontend/package.json | 1 +`, 37
  insertions and nothing else. `package.json` gains, between `"jsdom"` and `"react"`:

```json
    "pyodide": "0.27.7",
```

  and the lockfile gains the same line in its root package's `devDependencies`, and these two
  entries (above `"node_modules/qs"` and `"node_modules/wsl-utils"`):

```json
    "node_modules/pyodide": {
      "version": "0.27.7",
      "resolved": "https://registry.npmjs.org/pyodide/-/pyodide-0.27.7.tgz",
      "integrity": "sha512-RUSVJlhQdfWfgO9hVHCiXoG+nVZQRS5D9FzgpLJ/VcgGBLSAKoPL8kTiOikxbHQm1kRISeWUBdulEgO26qpSRA==",
      "dev": true,
      "license": "MPL-2.0",
      "dependencies": {
        "ws": "^8.5.0"
      },
      "engines": {
        "node": ">=18.0.0"
      }
    },
```

```json
    "node_modules/ws": {
      "version": "8.22.0",
      "resolved": "https://registry.npmjs.org/ws/-/ws-8.22.0.tgz",
      "integrity": "sha512-Ydggc987+RO0AnWtZ/7Wq9FtNvcrL1b/RO0ud9mWjUPgDrsAAwQSF51sm2hm1XofbU/4jkpGEsLFsZZxU+1DOg==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=10.0.0"
      },
      "peerDependencies": {
        "bufferutil": "^4.0.1",
        "utf-8-validate": ">=5.0.2"
      },
      "peerDependenciesMeta": {
        "bufferutil": {
          "optional": true
        },
        "utf-8-validate": {
          "optional": true
        }
      }
    },
```

  If `ws` resolves newer by then, keep what npm wrote. Then `cd frontend && npm ci && npm audit
  | tail -1`: the audit count is unchanged by these two (8 at Phase 2's Task 21, fewer if the
  phase end upgraded).
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

  `git add .github/workflows/ci.yml Makefile frontend/package.json frontend/package-lock.json
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
