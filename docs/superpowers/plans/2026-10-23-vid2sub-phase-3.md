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

## Decisions made while planning (review these)

1. **The file browser never lists or follows a link,** and a typed path through one is refused
   (Task 1). Spec §6.5 doesn't mention links, and the CLI follows them. So a media folder linked
   into home (`~/Movies/Anime` pointing at a NAS share) is added from the app by its real path
   under `/Volumes`, or from the CLI. **This adds to the spec:** Task 1's close writes it, with
   Decisions 3 and 24, into §6.5, so it waits for Dan's yes at approval.
2. **The browser reaches only its roots** (home and mounted volumes) and typed UNC shares, so a
   Linux library under `/srv` is added from the CLI, not the app (Task 1). §6.5 limits what may be
   read; it doesn't promise that any typed path is accepted.
3. **`Library` and `AppData` stay hidden** in the home folder on every OS (Task 1). On Linux that
   hides more than it needs to (the Phase-end list).
4. **Suggestions never pick a cloud model,** and ticking **Allow cloud models for this run**
   changes no suggestion: a cloud model is only ever the person's own pick (Task 3, spec §7.2).
   Each run's engine is checked against that run's choice on every call, so an engine made for a
   run that allowed the cloud never serves one that didn't.
5. **An uncertain detection can still Start,** with its warning shown. Only "Mandarin or
   Cantonese?" and a row with no language block Start (Task 3, spec §10).
6. **The rest of a folder inherits** the sampled files' choices only when they agree (Task 3).
7. **YouTube links aren't sampled.** Their language and models are decided when they run, as
   `vid2sub run` does (Task 3).
8. **Pause stops the running job at its next check.** Resume redoes decode and VAD but keeps the
   finished chunks (Task 5, spec §8.9, §17.3).
9. **The machine may sleep while the queue is paused** (Task 5). §8.10 keeps it awake while the
   queue runs.
10. **`faster-whisper` on NVIDIA needs cuDNN 9 as well as cuBLAS 12,** as its README (1.2.1) says.
    The `[nvidia]` extra and `doctor` check both. **This changes the spec** (§4.2, §9.5 and S45
    name cuBLAS 12 only), so it waits for Dan's yes at approval (Task 9).
11. **float16 on CUDA,** faster-whisper's own choice; int8 on the CPU, as §9.5 says (Task 9).
12. **The demo offers Make preview copy too** (Task 7). Its own clip plays, so only an episode
    made inside its copy needs one, and that copy goes in the demo's own cache, inside its folder.
13. **The preview encode runs beside the tab's serial queue, not in it** (Task 7): edits and Saves
    carry on while a long episode encodes; only the switch to the finished copy waits its turn.
14. **The playback audio stays playable once the copy plays** (Task 7): its media token is kept,
    so a browser that fails on the copy after all plays the sound again.
15. **Make preview copy shows only where it can help** (Task 7): `capabilities.generate` is true
    (it runs ffmpeg), the video has a picture, and the browser plays H.264 and AAC in an MP4.
16. **The copy's encoder settings** (Task 7): the hardware encoders at 1500k; libx264 at its
    default CRF 23 with §8.8's `-preset veryfast`. A JSON file beside each copy names the encoder
    that made it.
17. **faster-whisper's first run with no network fails the episode at once** (Task 9), as
    `unavailable`, naming the download, its size and `vid2sub doctor`. A `connection` error would
    retry for `wait_on_connection_s` (M1's ten minutes in the CLI, 30 s in the app: Decision 23)
    and then pause the queue (§17.3). The cost:
    with the network down, each queued faster-whisper episode fails in turn, each at once, where
    a pause would hold them. A model already downloaded loads from its cache folder, so later runs
    never need the network.
18. **An NVIDIA GPU without cuBLAS 12 or cuDNN 9 runs faster-whisper on the CPU** (Task 9), in
    int8, with a warning naming what is missing and `vid2sub doctor`, not an error. It is the same
    model, so §17.4's no-fallback holds, but much slower. Linux is checked through the loader, as
    Windows is through `PATH` and `CUDA_PATH`; doctor's check is renamed `CUDA libraries`.
19. **English's Qwen3-ASR step tries the Spark's before the Mac's** (Task 9), as Cantonese's does:
    Phase 2 Task 20's routing already puts endpoints first, and Task 9 keeps it. **This changes
    the spec** (§11.2's English row reads `qwen3-asr-1.7b` (Mac), written before the Spark served
    Qwen), so it waits for Dan's yes at approval.
20. **faster-whisper's CI is a `whisper` job of its own** (Task 10): Ubuntu and Windows, Python
    3.12, the `whisper` extra, apart from the `python` matrix; `VID2SUB_REQUIRE_WHISPER=1` makes
    its field check fail there rather than skip. **This changes the spec** (§23.2's job list
    doesn't name it), so it waits for Dan's yes at approval.
21. **The demo's Add browses only its own folder,** which is also its home, rather than Add being
    hidden there (Task 2): the smaller option, and it needs no capability beyond Phase 2
    Decision 23's one gate.
22. **The demo's Review suggests its canned models** under the catalog entries they stand in
    for (Task 4), so its pickers name Whisper turbo and Gemma 4.
23. **The app's jobs retry a dropped connection for 30 s, then pause the queue** (Task 6,
    `runtime.APP_WAIT_S`); the CLI keeps M1's 600 s. §17.3 says connection errors "pause the
    whole queue … with a **Resume** button". The cost: a short overnight blip pauses the queue
    until someone presses Resume.
24. **Beside Decision 3:** a user's `Library` and `AppData` stay hidden under any `Users/<name>/`
    on any root (WSL's `/mnt/c`, a backup disk), not only in home; a disk's admin shares (`C$`,
    `ADMIN$`, `IPC$`) are refused, while a person's own `name$` media share is not (Task 1).
25. **Review ends with Discard, a new Add, Start, or closing the tab** (Task 4); switching screens
    keeps it.
26. **One list for the Models page, Review's pickers and `vid2sub models`** (Task 8):
    `review.models`. The CLI prints from it, grouped by task, and gives a catalog entry no model
    points at §11.1's reason, "add it to vid2sub.toml", instead of M1's "not in vid2sub.toml";
    its JSON fields are unchanged.
27. **The Models page checks when it opens and on Check again, never on a timer** (Task 8): a
    check asks each local server, so it isn't polled; an ask while one runs is dropped, and a
    failed check says "couldn't check the models; see the log", never the error's own text.

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

Each line's test joins its task's listing when the listings are rebuilt on the finished Phase 2,
before this plan goes to Dan for approval.

1. **A season on a NAS share that has gone to sleep, or drops mid-listing:** Browse waits off the
   event loop and says it's waiting for the share; other tabs stay responsive; a listing that
   fails says so and lists nothing stale. (Task 1's and Task 2's tests.)
2. **A row changed on the Review screen while sampling is still running:** the person's choice
   stands when that file's sample arrives; only rows they haven't touched take the suggestion or
   inherit. (Task 3's and Task 4's tests.)
3. **The laptop sleeps, or the tunnel drops, mid-chunk:** the chunk in flight counts as a
   connection error, so the whole queue pauses rather than failing the job, and Resume after
   waking carries on from that chunk; Pause pressed as a chunk finishes leaves one state, with no
   chunk run twice or lost. (Task 5's tests.)
4. **Sampling windows that land on an intro song, music or silence:** windows with no speech
   don't vote; when too few remain, the row says the language is uncertain rather than guessing
   with confidence. (Task 3's tests.)
5. **faster-whisper's first run with no network, or on an NVIDIA machine without cuDNN 9:** the
   first fails the episode at once, naming the download and `vid2sub doctor` in its hint, with no
   wait on the download; the second runs on the CPU with a warning naming what is missing and
   doctor (Decision 18); neither falls back to another model or the cloud (spec §17.4). (Task 9's
   tests.)

***

### Task 1: The in-app file browser

**Tier:** 1 · **Scenarios:** S38

**Files:**
- Create: `src/vid2sub/web/browse.py`
- Modify: `src/vid2sub/subs/naming.py` (`natural_key` and `episode_key`, moved from the CLI so the
  browser and, in Phase 4, the Pages editor share its sort), `src/vid2sub/commands/_common.py`
  (sorts with them), `src/vid2sub/security.py` (`_RESERVED` becomes `RESERVED_NAMES`, shared
  with the browser)
- Test: `tests/test_browse.py`, `tests/test_naming.py`

**Interfaces:**
- Consumes: `pipeline.MEDIA_SUFFIXES`; `security.RESERVED_NAMES`; M1's
  `commands._common.episode_key` and `_natural` (moved here).
- Produces:
  - `vid2sub.subs.naming.natural_key(text: str) -> list` (digit runs as numbers, the rest
    casefolded) and `episode_key(name: str) -> tuple` (files with `SxxEyy` first, by season and
    episode, then the rest in natural order); pure. `commands._common.expand` sorts with them;
    M1's `_common.episode_key(path)` and `_natural` are gone.
  - `vid2sub.web.browse`:
    - `SUBTITLE_SUFFIXES = frozenset({".srt", ".ass", ".ssa", ".vtt"})` (what `vid2sub import`
      reads); `HOUSEKEEPING` (casefolded: `@eadir`, `#recycle`, `$recycle.bin`, `system volume
      information`, `lost+found`); `CREDENTIALS` (below your home: `.ssh`, `.aws`, `.gnupg`,
      `.config/gh`, `.azure`, `.kube`, `.docker`, `.password-store`, `Library`, `AppData`);
      `PROFILE_FOLDERS = frozenset({"library", "appdata"})` (hidden in any `Users/<name>/` below
      a root too, round 1e); `MAX_ENTRIES = 5000`; `MAX_PATH = 4096`
    - `class BrowseError(Exception)`: a reason fit to show, never naming a path (spec §6.8)
    - `@dataclass(frozen=True) class Entry: name: str; path: str;
      kind: Literal["folder", "video", "subtitle"]` (`name` is shown as plain text; `path` is
      what the screen sends back to list or add)
    - `@dataclass(frozen=True) class Listing: path: str; parent: str | None;
      entries: tuple[Entry, ...]; truncated: bool = False` (`path` spelled as on the disk;
      `parent` None at a root or at a share's top; folders first in natural order, then videos
      and subtitles by `episode_key`; at most `MAX_ENTRIES`, `truncated` saying there were more)
    - `roots(*, home: Path | None = None, volumes: Sequence[Path] | None = None)
      -> tuple[Entry, ...]`: `Entry("Home", str(home), "folder")` first (left out when home is
      a disk's root), then each visible folder that isn't a link in `/Volumes`, `/media`,
      `/media/<you>`, `/run/media/<you>` and `/mnt`, or on Windows each of `os.listdrives()`
      (`Entry("C:", "C:\\", "folder")`)
    - `qualified(text: str, *, windows: bool) -> PurePath` and `place(text: str, *,
      roots: Sequence[Entry], home: str | PurePath, windows: bool) -> tuple[PurePath, str,
      tuple[str, ...]]` (pure: the refusals that need no disk; a typed `\\server\share` is its
      own root)
    - `listing(path: str, *, roots: Sequence[Entry] | None = None, home: Path | None = None)
      -> Listing`
    - `accept(path: str, *, roots: Sequence[Entry] | None = None, home: Path | None = None)
      -> Path` (a visible video or folder, spelled as on the disk)
    - `expand(paths: Sequence[str], *, roots: Sequence[Entry] | None = None,
      home: Path | None = None) -> list[str]` (what Add adds: each video once, in the order
      given; a folder's own videos, not its subfolders', in episode order; a folder past
      `MAX_ENTRIES` refused whole)
    - `roots`, `listing`, `accept` and `expand` block on the disk (a sleeping network share
      takes seconds), so Task 2's server runs them off the event loop. Given no `roots`,
      `listing`, `accept` and `expand` look only at the root a path can be in (your home, the
      one volume its path names, or its drive), never every mounted volume (round 1e). Task 2
      shows a `BrowseError` as a notice, renders `Entry.name` as plain text, and passes back
      only what the person typed or an `Entry.path` from an earlier listing, never a path read
      from a file (§6.5).
  - Decided here (the safe answer): links, junctions and other name-surrogate reparse points
    are never listed and never followed; a path through one is refused, whatever it points to.
    And (round 1e, proposed beside Decision 3): a user's `Library` and `AppData` are hidden in
    every `Users/<name>/` the browser reaches, not only in your home, and a disk's admin share
    (`C$`, `ADMIN$`, `IPC$`) is refused (round 1f).

- [ ] **Step 0: Record the base:** `git rev-parse HEAD > .git/TASK_BASE`.
- [ ] **Step 1: Write the failing tests.** Append to `tests/test_naming.py`, after two blank
  lines:

```python
def test_episodes_sort_by_season_and_episode_then_others_by_natural_name():
    found = ["Extras 10.mkv", "Show S01E10.mkv", "Extras 9.mkv", "show s01e02.mkv",
             "Show S02E01.mkv", "Show.S01.E01.mkv"]
    assert sorted(found, key=n.episode_key) == [
        "Show.S01.E01.mkv", "show s01e02.mkv", "Show S01E10.mkv", "Show S02E01.mkv",
        "Extras 9.mkv", "Extras 10.mkv"]


def test_a_natural_sort_never_trips_on_digits_that_are_not_ascii():
    assert sorted(["Season 2", "Season 1²", "Season 10", "season 1"], key=n.natural_key) == [
        "season 1", "Season 1²", "Season 2", "Season 10"]
```

  Then `tests/test_browse.py`:

```python
"""The in-app file browser (spec §6.5, S38): what it lists, what it hides, what it refuses."""

import os
import stat
import sys
from pathlib import Path

import pytest

from vid2sub.web import browse
from vid2sub.web.browse import BrowseError, Entry

needs_symlinks = pytest.mark.skipif(sys.platform == "win32",
                                    reason="symlinks need privileges on Windows")


def touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")
    return path


@pytest.fixture
def places(tmp_path):
    """A home folder and a mounted volume, with what each root list should show."""
    home = tmp_path / "home"
    volume = tmp_path / "Volumes" / "Media"
    for folder in (home / "Movies", volume / "TV"):
        folder.mkdir(parents=True)
    return home, volume, (Entry("Home", str(home), "folder"), Entry("Media", str(volume), "folder"))


def names(listing) -> list[str]:
    return [e.name for e in listing.entries]


@needs_symlinks
def test_the_roots_are_home_then_each_mounted_volume_and_never_a_link(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    volumes = tmp_path / "Volumes"
    (volumes / "Media").mkdir(parents=True)
    (volumes / ".timemachine").mkdir()
    touch(volumes / "notes.txt")
    (volumes / "Macintosh HD").symlink_to("/")  # the boot volume's entry is a link to /
    assert browse.roots(home=home, volumes=[volumes, tmp_path / "missing"]) == (
        Entry("Home", str(home), "folder"), Entry("Media", str(volumes / "Media"), "folder"))


def test_this_machines_roots_start_with_home_and_are_all_real_folders():
    found = browse.roots()
    assert found[0] == Entry("Home", str(Path.home()), "folder")
    for root in found[1:]:
        if os.name == "nt":  # a drive letter may have no disk in it: listdrives doesn't look
            assert root.name.endswith(":") and root.path == root.name + "\\"
        else:
            assert os.path.isdir(root.path) and not os.path.islink(root.path)


def test_a_folder_shows_only_folders_videos_and_subtitles(places):
    home, _, roots = places
    for name in ("Show S01E01.mkv", "Clip.MP4", "Show S01E01.en.srt", "Show S01E01.ja.ass",
                 "Show S01E01.ko.vtt", "notes.txt", "cover.jpg", "Show.nfo",
                 "Show S01E01.vid2sub.jsonl"):
        touch(home / "Movies" / name)
    (home / "Movies" / "Extras").mkdir()
    listing = browse.listing(str(home / "Movies"), roots=roots, home=home)
    assert [(e.name, e.kind) for e in listing.entries] == [
        ("Extras", "folder"), ("Show S01E01.en.srt", "subtitle"),
        ("Show S01E01.ja.ass", "subtitle"), ("Show S01E01.ko.vtt", "subtitle"),
        ("Show S01E01.mkv", "video"), ("Clip.MP4", "video")]
    assert listing.entries[0].path == str(home / "Movies" / "Extras")
    assert listing.path == str(home / "Movies") and listing.parent == str(home)
    assert listing.truncated is False


def test_a_season_is_sorted_by_sxxeyy_after_its_folders_in_natural_order(places):
    home, volume, roots = places
    season = volume / "TV" / "Show"
    for name in ("Show S01E10.mkv", "Show S01E02.mkv", "Show s01e01.mkv", "Show S02E01.mkv",
                 "Behind the scenes.mkv"):
        touch(season / name)
    for name in ("Season 10", "Season 2", "season 1", "Season 1²"):
        (season / name).mkdir()
    assert names(browse.listing(str(season), roots=roots, home=home)) == [
        "season 1", "Season 1²", "Season 2", "Season 10", "Show s01e01.mkv",
        "Show S01E02.mkv", "Show S01E10.mkv", "Show S02E01.mkv", "Behind the scenes.mkv"]


def test_dotfiles_and_the_folders_that_hold_credentials_are_hidden(places):
    home, volume, roots = places
    for name in (".ssh", ".aws", ".gnupg", ".config/gh", "Library", "AppData", "@eaDir",
                 "$RECYCLE.BIN"):
        (home / name).mkdir(parents=True)
    touch(home / ".hidden.mkv")
    (volume / "Library").mkdir()  # a media library on a volume is not a credential folder
    assert names(browse.listing(str(home), roots=roots, home=home)) == ["Movies"]
    assert names(browse.listing(str(volume), roots=roots, home=home)) == ["Library", "TV"]


@pytest.mark.parametrize("inside", [".ssh", ".config/gh", "Library", "library", "AppData",
                                    "@eaDir", ".config"])
def test_a_hidden_or_credential_folder_is_refused_even_when_typed(places, inside):
    home, _, roots = places
    (home / inside).mkdir(parents=True, exist_ok=True)
    with pytest.raises(BrowseError) as err:
        browse.listing(str(home / inside), roots=roots, home=home)
    assert str(home) not in str(err.value) and inside not in str(err.value)


@needs_symlinks
def test_a_link_is_never_listed_and_never_followed(places, tmp_path):
    home, volume, roots = places
    outside = tmp_path / "outside"
    outside.mkdir()
    touch(outside / "Leak S01E01.mkv")
    (home / ".ssh").mkdir()
    movies = home / "Movies"
    touch(movies / "Real.mkv")
    (movies / "To outside").symlink_to(outside)
    (movies / "To ssh").symlink_to(home / ".ssh")
    (movies / "To TV").symlink_to(volume / "TV")
    (movies / "Link.mkv").symlink_to(movies / "Real.mkv")
    assert names(browse.listing(str(movies), roots=roots, home=home)) == ["Real.mkv"]
    for link in ("To outside", "To ssh", "To TV"):
        with pytest.raises(BrowseError, match="link"):
            browse.listing(str(movies / link), roots=roots, home=home)


def test_a_path_outside_every_root_is_refused_without_naming_it(places, tmp_path):
    _, _, roots = places
    elsewhere = tmp_path / "Elsewhere"
    elsewhere.mkdir()
    with pytest.raises(BrowseError) as err:
        browse.listing(str(elsewhere), roots=roots, home=tmp_path / "home")
    assert "home folder" in str(err.value) and "Elsewhere" not in str(err.value)


@pytest.mark.parametrize("typed", ["Movies", "home/Movies", "", "/a/../b", "/x\x00y",
                                   "/" + "a" * 5000])
def test_a_path_that_isnt_fully_qualified_is_refused(places, typed):
    home, _, roots = places
    with pytest.raises(BrowseError):
        browse.listing(typed, roots=roots, home=home)


def test_a_path_from_home_may_start_with_a_tilde(places):
    home, _, roots = places
    assert browse.listing("~/Movies", roots=roots, home=home).path == str(home / "Movies")


@pytest.mark.parametrize("typed", [r"C:Videos", r"\Videos", r"\\?\C:\Videos",
                                   r"\\.\PhysicalDrive0", r"//?/C:/Videos", r"\\nas",
                                   r"C:\Videos\..\Windows"])
def test_windows_paths_must_be_fully_qualified_and_never_a_device(typed):
    with pytest.raises(BrowseError):
        browse.qualified(typed, windows=True)


def test_a_windows_network_share_is_its_own_root_when_the_person_types_it():
    roots = (Entry("Home", r"C:\Users\someone", "folder"), Entry("C:", "C:\\", "folder"))
    path, root, below = browse.place(r"\\nas\media\TV\Show", roots=roots,
                                     home=r"C:\Users\someone", windows=True)
    assert (str(path), root, below) == (r"\\nas\media\TV\Show", "\\\\nas\\media\\", ("TV", "Show"))
    assert browse.place(r"c:\users\SOMEONE\Videos", roots=roots, home=r"C:\Users\someone",
                        windows=True)[1:] == (r"C:\Users\someone", ("Videos",))
    with pytest.raises(BrowseError):
        browse.place(r"C:\Users\someone\AppData\Roaming", roots=roots, home=r"C:\Users\someone",
                     windows=True)


@pytest.mark.skipif(sys.platform != "darwin", reason="the hidden flag is a macOS file flag")
def test_a_folder_the_system_marks_hidden_is_hidden(places):
    home, _, roots = places
    secret = home / "Keychains"
    secret.mkdir()
    os.chflags(secret, stat.UF_HIDDEN)
    assert names(browse.listing(str(home), roots=roots, home=home)) == ["Movies"]
    with pytest.raises(BrowseError, match="hidden"):
        browse.listing(str(secret), roots=roots, home=home)


@pytest.mark.skipif(os.name == "nt" or os.geteuid() == 0,
                    reason="POSIX permissions, which root ignores")
def test_a_folder_vid2sub_cannot_read_says_so_without_its_path(places):
    home, _, roots = places
    locked = home / "Locked"
    locked.mkdir(mode=0o000)
    try:
        with pytest.raises(BrowseError, match="isn't allowed") as err:
            browse.listing(str(locked), roots=roots, home=home)
        assert "Locked" not in str(err.value)
    finally:
        locked.chmod(0o700)


def test_a_missing_folder_or_a_file_is_not_a_folder_to_list(places):
    home, _, roots = places
    touch(home / "Movies" / "a.mkv")
    for typed in (home / "Gone", home / "Movies" / "a.mkv"):
        with pytest.raises(BrowseError, match="no folder"):
            browse.listing(str(typed), roots=roots, home=home)


def test_a_root_has_no_parent(places):
    home, volume, roots = places
    assert browse.listing(str(home), roots=roots, home=home).parent is None
    assert browse.listing(str(volume), roots=roots, home=home).parent is None


def test_a_huge_folder_is_cut_at_the_cap_and_says_so(places, monkeypatch):
    home, _, roots = places
    monkeypatch.setattr(browse, "MAX_ENTRIES", 3)
    for n in range(1, 6):
        touch(home / "Movies" / f"Show S01E0{n}.mkv")
    listing = browse.listing(str(home / "Movies"), roots=roots, home=home)
    assert names(listing) == ["Show S01E01.mkv", "Show S01E02.mkv", "Show S01E03.mkv"]
    assert listing.truncated is True
```

- [ ] **Step 2: Run it; watch it fail.** `uv run pytest tests/test_naming.py -q`. Expected:
  `E       AttributeError: module 'vid2sub.subs.naming' has no attribute 'episode_key'`, the same
  for `natural_key`, and `2 failed, 5 passed`. Then `uv run pytest tests/test_browse.py -q`.
  Expected: `E   ImportError: cannot import name 'browse' from 'vid2sub.web'
  (…/src/vid2sub/web/__init__.py)` and `1 error`.
- [ ] **Step 3: Write the code.** In `src/vid2sub/subs/naming.py`, replace

```python
(council, 2026-10-14); `yue` stays in the sidecar. Cantonese is Traditional only in v1 (plan
decision 7).
"""

from __future__ import annotations

from dataclasses import dataclass
```

  with

```python
(council, 2026-10-14); `yue` stays in the sidecar. Cantonese is Traditional only in v1 (plan
decision 7). A season's files sort by `SxxEyy`, others by natural name order (spec §10, §18.1);
the CLI, the file browser and, from Phase 4, the Pages editor share one sort, so it lives here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
```

  Below `SIDECAR_SUFFIX = ".vid2sub.jsonl"`, add:

```python
_EPISODE = re.compile(r"[Ss](\d{1,3})[ ._-]*[Ee](\d{1,4})")
_DIGITS = re.compile(r"(\d+)")
```

  At the end of the file, after two blank lines, add:

```python
def natural_key(text: str) -> list:
    """`Season 2` before `Season 10`. The split's odd parts are its digit runs, so only they
    become numbers (`str.isdigit` also passes `²`, which `int` refuses)."""
    return [int(part) if i % 2 else part.casefold()
            for i, part in enumerate(_DIGITS.split(text))]


def episode_key(name: str) -> tuple:
    """`S01E02` before `S01E10`, every episode before the files with no `SxxEyy`."""
    m = _EPISODE.search(name)
    natural = natural_key(name)
    return (0, int(m.group(1)), int(m.group(2)), natural) if m else (1, 0, 0, natural)
```

  In `src/vid2sub/commands/_common.py`, replace

```python
from vid2sub.security import InputRefused, resolve_input

_EPISODE = re.compile(r"[Ss](\d{1,3})[ ._-]*[Ee](\d{1,4})")
```

  with

```python
from vid2sub.security import InputRefused, resolve_input
from vid2sub.subs.naming import episode_key, natural_key
```

  delete the two functions below `check_model` (with their blank lines),

```python
def episode_key(path: Path) -> tuple:
    natural = [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", path.name)]
    m = _EPISODE.search(path.name)
    return (0, int(m.group(1)), int(m.group(2)), natural) if m else (1, 0, 0, natural)


def _natural(text: str) -> list:
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", text)]
```

  and in `expand`, replace
  `videos, key=lambda f: (_natural(str(f.parent)), episode_key(f)))]` with
  `videos, key=lambda f: (natural_key(str(f.parent)), episode_key(f.name)))]`. (`re` stays
  imported: `duration` uses it.) Then `src/vid2sub/web/browse.py`:

```python
"""The in-app file browser: your home folder and mounted volumes, folders, videos and subtitles
(spec §6.5, S38).

The engine is a local server that lists directories, so what it lists is a security boundary
(spec §6). It lists only your home folder and mounted volumes (what's in `/Volumes` on a Mac, the
drive letters on Windows, what's in `/media`, `/run/media/<you>` and `/mnt` on Linux), shows only
folders, videos and subtitle files, and hides dotfiles, the folders that hold credentials
(`.ssh`, `.aws`, `.gnupg`, `.config/gh` …, and `Library` and `AppData` in your home), Synology's
and Windows' housekeeping folders, and any folder the system marks hidden; a hidden folder typed
in full is refused too. A path must be fully qualified (spec §6.5): the server's own folder means
nothing to the person typing; `~` stands for your home, as the editor's open allows. A Windows
network path (`\\\\server\\share`) is listed when the person types it or browses to it, and
nowhere else, since a UNC path read from a file's contents leaks the NTLM hash (§6.5). Links
(symlinks, and Windows junctions) are never listed and never followed, so no link can lead outside
your folders, into a hidden one, or to a share nobody typed (decided in the Phase 3 plan, Task 1);
that is why the boot volume's `/Volumes` entry, a link to `/`, is not a root. A season's files sort
by `SxxEyy`, others by natural name order (§10). Reasons name no path (§6.8). Everything here
blocks on the disk, and a sleeping network share can take seconds, so the server calls it off the
event loop.
"""

from __future__ import annotations

import os
import stat
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath
from typing import Literal

from vid2sub.pipeline import MEDIA_SUFFIXES
from vid2sub.subs.naming import episode_key, natural_key

SUBTITLE_SUFFIXES = frozenset({".srt", ".ass", ".ssa", ".vtt"})  # what `vid2sub import` reads
HOUSEKEEPING = frozenset({"@eadir", "#recycle", "$recycle.bin", "system volume information",
                          "lost+found"})  # casefolded: Synology, Windows and ext4 folders
CREDENTIALS = (".ssh", ".aws", ".gnupg", ".config/gh", ".azure", ".kube", ".docker",
               ".password-store", "Library", "AppData")  # in your home
MAX_ENTRIES = 5000
MAX_PATH = 4096
_HIDDEN_ATTRIBUTES = stat.FILE_ATTRIBUTE_HIDDEN | stat.FILE_ATTRIBUTE_SYSTEM
_JUNCTION = getattr(stat, "IO_REPARSE_TAG_MOUNT_POINT", 0xA0000003)  # defined on Windows only
_FOLD = sys.platform in ("darwin", "win32")  # case-insensitive by default
Kind = Literal["folder", "video", "subtitle"]


class BrowseError(Exception):
    """A path the browser won't list or add; the reason names no path (spec §6.8)."""


@dataclass(frozen=True)
class Entry:
    name: str  # the bare name, shown as text
    path: str  # the full path: what the screen sends back to list or add
    kind: Kind


@dataclass(frozen=True)
class Listing:
    path: str
    parent: str | None  # None at a root, or at the top of a network share
    entries: tuple[Entry, ...]  # folders first, then videos and subtitles by SxxEyy
    truncated: bool = False  # more than MAX_ENTRIES: the rest aren't shown


def roots(*, home: Path | None = None,
          volumes: Sequence[Path] | None = None) -> tuple[Entry, ...]:
    """Your home first, then each mounted volume: each folder in `volumes` (by default
    `/Volumes`, `/media`, `/media/<you>`, `/run/media/<you>` and `/mnt`), or on Windows each
    drive letter. A link, a hidden folder or a file there is not a volume."""
    home = home or Path.home()
    found = [Entry("Home", str(home), "folder")]
    if volumes is None and os.name == "nt":
        found += [Entry(d.rstrip("\\"), d, "folder") for d in os.listdrives()]
        return tuple(found)
    if volumes is None:
        user = home.name
        volumes = [Path("/Volumes"), Path("/media"), Path("/media") / user,
                   Path("/run/media") / user, Path("/mnt")]
    seen = {str(home)}
    for parent in volumes:
        try:
            with os.scandir(parent) as it:
                mounts = sorted((e for e in it if _visible_folder(e)),
                                key=lambda e: natural_key(e.name))
        except OSError:
            continue
        for e in mounts:
            if e.path not in seen and e.path not in {str(v) for v in volumes}:
                seen.add(e.path)
                found.append(Entry(e.name, e.path, "folder"))
    return tuple(found)


_all_roots = roots  # `listing` takes a `roots` argument, which hides the function's name


def qualified(text: str, *, windows: bool) -> PurePath:
    """The path as the person gave it, refused unless fully qualified: from `/`, from a drive
    (`C:\\`), or a network share (`\\\\server\\share`), never a device path, never with `..`."""
    if not text or len(text) > MAX_PATH or "\x00" in text:
        raise BrowseError("give the folder's full path")
    path: PurePath = PureWindowsPath(text) if windows else PurePosixPath(text)
    if windows:
        if path.drive.startswith(("\\\\?\\", "\\\\.\\")):
            raise BrowseError("vid2sub doesn't open device paths")
        if not (path.drive and path.root):
            raise BrowseError("give the full path, from the drive (C:\\…) or the share "
                              "(\\\\server\\share\\…)")
    elif not path.root:
        raise BrowseError("give the full path, starting with /")
    if ".." in path.parts:
        raise BrowseError("give the path without ..")
    return path


def place(text: str, *, roots: Sequence[Entry], home: str | PurePath,
          windows: bool) -> tuple[PurePath, str, tuple[str, ...]]:
    """Where a path is: the path, the root it's in (a network share the person typed is its own
    root), and its parts below that root. Refuses a path in no root, and one below a hidden
    folder or a folder that holds credentials. Pure: it touches no disk."""
    flavour = PureWindowsPath if windows else PurePosixPath
    home_path = flavour(home)
    if text == "~" or text.startswith(("~/", "~\\")):
        text = str(home_path) + text[1:]
    path = qualified(text, windows=windows)
    best: tuple[str, tuple[str, ...]] | None = None
    for root in roots:
        below = _below(path, flavour(root.path))
        if below is not None and (best is None or len(below) < len(best[1])):
            best = (root.path, below)
    if best is None:
        if not (windows and path.drive.startswith("\\\\")):
            raise BrowseError("vid2sub browses your home folder, your drives and network "
                              "shares only")
        best = (path.anchor, path.parts[1:])
    for part in best[1]:
        if _hidden_name(part):
            raise BrowseError("vid2sub doesn't show hidden folders")
    in_home = _below(path, home_path)
    if in_home is not None and _holds_credentials(in_home):
        raise BrowseError("vid2sub doesn't show the folders that hold credentials")
    return path, best[0], best[1]


def listing(path: str, *, roots: Sequence[Entry] | None = None,
            home: Path | None = None) -> Listing:
    """One folder's folders, videos and subtitle files, never a link or anything hidden."""
    home = home or Path.home()
    folder, below = _walk(path, _all_roots(home=home) if roots is None else roots, home)
    if not stat.S_ISDIR(_lstat(folder).st_mode):
        raise BrowseError("there's no folder there")
    in_home = _below(PurePath(folder), PurePath(home))
    folders: list[Entry] = []
    files: list[Entry] = []
    try:
        with os.scandir(folder) as it:
            for e in it:  # a link is neither a folder nor a file when it isn't followed
                if _visible_folder(e):
                    if in_home is None or not _holds_credentials((*in_home, e.name)):
                        folders.append(Entry(e.name, e.path, "folder"))
                elif not _hidden_name(e.name) and e.is_file(follow_symlinks=False):
                    kind = _file_kind(e.name)
                    if kind is not None:
                        files.append(Entry(e.name, e.path, kind))
    except OSError as err:
        raise _refusal(err) from None
    folders.sort(key=lambda e: natural_key(e.name))
    files.sort(key=lambda e: episode_key(e.name))
    entries = folders + files
    return Listing(str(folder), None if not below else str(folder.parent),
                   tuple(entries[:MAX_ENTRIES]), len(entries) > MAX_ENTRIES)


def _below(path: PurePath, root: PurePath) -> tuple[str, ...] | None:
    """The parts of `path` below `root`, or None when it isn't inside it."""
    def key(part: str) -> str:
        return part.casefold() if _FOLD or isinstance(path, PureWindowsPath) else part

    n = len(root.parts)
    if len(path.parts) < n or [key(p) for p in path.parts[:n]] != [key(p) for p in root.parts]:
        return None
    return path.parts[n:]


def _hidden_name(name: str) -> bool:
    return name.startswith(".") or name.casefold() in HOUSEKEEPING


def _holds_credentials(below_home: Sequence[str]) -> bool:
    parts = [p.casefold() for p in below_home]
    return any(parts[:len(c)] == c for c in (
        [p.casefold() for p in folder.split("/")] for folder in CREDENTIALS))


def _flagged_hidden(st: os.stat_result) -> bool:
    """A folder the system hides: macOS' hidden flag (`~/Library`), Windows' hidden or system
    attribute."""
    return bool(getattr(st, "st_flags", 0) & stat.UF_HIDDEN
                or getattr(st, "st_file_attributes", 0) & _HIDDEN_ATTRIBUTES)


def _is_link(st: os.stat_result) -> bool:
    return stat.S_ISLNK(st.st_mode) or (
        getattr(st, "st_reparse_tag", 0) == _JUNCTION)


def _visible_folder(e: os.DirEntry) -> bool:
    try:
        return (not _hidden_name(e.name) and e.is_dir(follow_symlinks=False)
                and not e.is_junction() and not _flagged_hidden(e.stat(follow_symlinks=False)))
    except OSError:
        return False


def _file_kind(name: str) -> Kind | None:
    suffix = os.path.splitext(name)[1].lower()
    if suffix in MEDIA_SUFFIXES:
        return "video"
    if suffix in SUBTITLE_SUFFIXES:
        return "subtitle"
    return None


def _refusal(err: OSError) -> BrowseError:
    """A disk error as a reason fit to show: never `err.filename`, a full path (spec §6.8)."""
    if isinstance(err, PermissionError):
        return BrowseError("vid2sub isn't allowed to read this folder")
    if isinstance(err, (FileNotFoundError, NotADirectoryError)):
        return BrowseError("there's no folder there")
    return BrowseError("couldn't read this folder" + (f" ({err.strerror})" if err.strerror
                                                      else ""))


def _lstat(path: Path) -> os.stat_result:
    try:
        return os.lstat(path)
    except OSError as err:
        raise _refusal(err) from None


def _walk(text: str, roots: Sequence[Entry], home: Path) -> tuple[Path, tuple[str, ...]]:
    """The path and its parts below its root, checked down from the root one part at a time
    without following anything: a link, a junction or a folder the system hides is refused."""
    _, root, below = place(text, roots=roots, home=home, windows=os.name == "nt")
    here = Path(root)
    for part in below:
        here = here / part
        st = _lstat(here)
        if _is_link(st):
            raise BrowseError("vid2sub doesn't follow links: browse to the folder it points to")
        if stat.S_ISDIR(st.st_mode) and _flagged_hidden(st):
            raise BrowseError("vid2sub doesn't show hidden folders")
    return here, below
```

- [ ] **Step 4: Run the checks; they pass.** `uv run pytest tests/test_browse.py
  tests/test_naming.py -q` first (`41 passed`), then the guard checks, then `make check`.
  **Guard checks** (spec §22.1), each reverted and restored, each with
  `uv run pytest tests/test_browse.py -q`: in `_walk`, replace `if _is_link(st):` with
  `if False:` (`FAILED …test_a_link_is_never_listed_and_never_followed`); in `_visible_folder`,
  replace `e.is_dir(follow_symlinks=False)` with `e.is_dir()` (three tests fail, the roots and
  the link ones); in `listing`, replace `elif not _hidden_name(e.name) and e.is_file` with
  `elif e.is_file` (`FAILED …test_dotfiles_and_the_folders_that_hold_credentials_are_hidden`);
  take `"Library", ` out of `CREDENTIALS` (three tests fail); in `qualified`, replace
  `if path.drive.startswith(("\\\\?\\", "\\\\.\\")):` with `if False:` (two
  `…never_a_device` cases fail); in `_flagged_hidden`, drop
  `getattr(st, "st_flags", 0) & stat.UF_HIDDEN or ` (on macOS,
  `FAILED …test_a_folder_the_system_marks_hidden_is_hidden`). `make check`. Expected:
  `1073 passed, 2 skipped, 36 deselected` twice, `Test Files  19 passed (19)` and
  `Tests  88 passed (88)`, `All checks passed!` and `no leaks found`.
- [ ] **Step 5: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(web): 🤖 the file browser lists home and mounted volumes, only folders, videos and subtitles

vid2sub.web.browse (spec §6.5, S38): roots() is your home, then each
folder in /Volumes, /media, /media/<you>, /run/media/<you> and /mnt, or
each drive letter on Windows (os.listdrives); listing(path) shows one
folder's folders, then its videos and subtitle files by SxxEyy. Dotfiles,
Synology's and Windows' housekeeping folders, the folders that hold
credentials (.ssh, .aws, .gnupg, .config/gh … and Library and AppData in
your home) and folders the system marks hidden (macOS' UF_HIDDEN,
Windows' hidden and system attributes) are neither shown nor listed when
typed. A path must be fully qualified; `~` is your home, as the editor's
open allows; a Windows device path (\\?\, \\.\) is refused, and a UNC
share the person types is its own root. Links and junctions are never
listed and never followed (the safe answer, decided here), so the boot
volume's /Volumes link to / is no root. Reasons never name a path.

naming.episode_key and natural_key move here from commands/_common, so
the CLI and the browser share one sort; natural_key splits on digit runs
by position, since str.isdigit passes "²", which int refuses: M1's sort
crashed on a folder named "Season 1²" (escaped from M1 Task 32, found
while moving it).

The new tests failed first with: ImportError: cannot import name 'browse'
from 'vid2sub.web'. Guard checks, each reverted and restored: following a
link on the way down, a folder entry that follows links, a file entry
that follows links, the dotfile rule, the credential list without
Library, the device-path refusal and macOS' hidden flag each make their
tests fail.

Docs read: Python's os docs (os.listdrives: Windows, 3.12, doesn't test
access; DirEntry.is_junction 3.12; DirEntry.stat(follow_symlinks=False)
needs no system call on Windows; os.lstat opens symlinks and junctions
without following them; st_flags, st_file_attributes, st_reparse_tag);
the stat module (UF_HIDDEN and FILE_ATTRIBUTE_* everywhere,
IO_REPARSE_TAG_MOUNT_POINT on Windows only); pathlib's PureWindowsPath
drive, root and anchor for UNC and device paths.

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md Task 1
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/web/browse.py tests/test_browse.py src/vid2sub/subs/naming.py
  src/vid2sub/commands/_common.py tests/test_naming.py`, `git commit -F .git/COMMIT_MSG`, then
  `git log -1 --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 6: Write the failing test.** Append to `tests/test_browse.py`, after two blank
  lines:

```python
# Adding: what the Add screen adds from the browser or a typed path (spec §10, §19.2)


@needs_symlinks
def test_adding_gives_each_video_once_and_each_folders_videos_in_episode_order(places,
                                                                              tmp_path):
    home, _, roots = places
    season = home / "Movies" / "Show"
    for name in ("Show S01E02.mkv", "Show S01E01.mkv", "Show S01E01.en.srt",
                 ".Show S01E03.mkv", "notes.txt", "Extras/Bonus.mkv"):
        touch(season / name)
    (season / "Show S01E04.mkv").symlink_to(touch(tmp_path / "outside.mkv"))
    film = touch(home / "Movies" / "Film.mp4")
    found = browse.expand([str(season), str(film), str(season / "Show S01E01.mkv")],
                          roots=roots, home=home)
    assert found == [str(season / "Show S01E01.mkv"), str(season / "Show S01E02.mkv"),
                     str(film)]


@pytest.mark.parametrize("bad", ["Movies/notes.txt", "Movies/Show.en.srt", "Movies/.Clip.mkv",
                                 ".ssh/Clip.mkv", "Movies/Gone.mkv"])
def test_adding_anything_but_a_visible_video_or_folder_is_refused(places, bad):
    home, _, roots = places
    for name in ("Movies/notes.txt", "Movies/Show.en.srt", "Movies/.Clip.mkv", ".ssh/Clip.mkv"):
        touch(home / name)
    with pytest.raises(BrowseError) as err:
        browse.accept(str(home / bad), roots=roots, home=home)
    assert str(home) not in str(err.value)


@needs_symlinks
def test_a_video_added_through_a_link_is_refused(places, tmp_path):
    home, _, roots = places
    (home / "Movies" / "Clip.mkv").symlink_to(touch(tmp_path / "outside.mkv"))
    with pytest.raises(BrowseError, match="link"):
        browse.accept(str(home / "Movies" / "Clip.mkv"), roots=roots, home=home)


def test_a_folder_too_big_to_add_at_once_is_refused(places, monkeypatch):
    home, _, roots = places
    monkeypatch.setattr(browse, "MAX_ENTRIES", 2)
    for n in range(1, 4):
        touch(home / "Movies" / f"Show S01E0{n}.mkv")
    with pytest.raises(BrowseError, match="too many"):
        browse.expand([str(home / "Movies")], roots=roots, home=home)
```

- [ ] **Step 7: Run it; watch it fail.** `uv run pytest tests/test_browse.py -q`. Expected:
  `E           AttributeError: module 'vid2sub.web.browse' has no attribute 'accept'` (six
  times), the same for `expand`, and `8 failed, 34 passed`.
- [ ] **Step 8: Write the code,** in `src/vid2sub/web/browse.py`. In the module docstring,
  replace

```python
by `SxxEyy`, others by natural name order (§10). Reasons name no path (§6.8). Everything here
blocks on the disk, and a sleeping network share can take seconds, so the server calls it off the
event loop.
```

  with

```python
by `SxxEyy`, others by natural name order (§10). What the Add screen adds, browsed or typed, goes
through the same checks, and a folder adds its videos in episode order (§19.2). Reasons name no
path (§6.8). Everything here blocks on the disk, and a sleeping network share can take seconds,
so the server calls it off the event loop.
```

  Above `def _below(path: PurePath, root: PurePath) -> tuple[str, ...] | None:`, add:

```python
def accept(path: str, *, roots: Sequence[Entry] | None = None,
           home: Path | None = None) -> Path:
    """A video or a folder the person typed or picked, to add: checked as `listing` checks a
    folder, so whatever the browser wouldn't show can't be added by typing it."""
    home = home or Path.home()
    target, _ = _walk(path, _all_roots(home=home) if roots is None else roots, home)
    st = _lstat(target)
    if stat.S_ISDIR(st.st_mode) or (stat.S_ISREG(st.st_mode)
                                    and _file_kind(target.name) == "video"):
        return target
    raise BrowseError("that isn't a video or a folder vid2sub can add")


def expand(paths: Sequence[str], *, roots: Sequence[Entry] | None = None,
           home: Path | None = None) -> list[str]:
    """What Add adds, each once, in the order given: a video as it is, and a folder's videos
    (not its subfolders') in episode order, never a link or a hidden file (spec §19.2)."""
    out: list[str] = []
    seen: set[str] = set()
    for text in paths:
        target = accept(text, roots=roots, home=home)
        if stat.S_ISDIR(_lstat(target).st_mode):
            found = listing(str(target), roots=roots, home=home)
            if found.truncated:
                raise BrowseError("that folder has too many files to add at once: add its "
                                  "seasons one at a time")
            items = [e.path for e in found.entries if e.kind == "video"]
        else:
            items = [str(target)]
        for item in items:
            if os.path.normcase(item) not in seen:
                seen.add(os.path.normcase(item))
                out.append(item)
    return out


```

- [ ] **Step 9: Run the checks; they pass.** `uv run pytest tests/test_browse.py -q` first
  (`42 passed`), then the guard check, then `make check`. **Guard check:** in `accept`, replace
  the `if stat.S_ISDIR(st.st_mode) or (…):` condition with `if True:`; two
  `test_adding_anything_but_a_visible_video_or_folder_is_refused` cases (the text file and the
  subtitle) fail; restore it. `make check`. Expected:
  `1081 passed, 2 skipped, 36 deselected` twice, `Test Files  19 passed (19)` and
  `Tests  88 passed (88)`, `All checks passed!` and `no leaks found`.
- [ ] **Step 10: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(web): 🤖 Add takes a video or a folder's videos in episode order, checked as the browser checks

browse.accept(path) takes a video or a folder the person typed or picked,
through the same walk as listing: fully qualified, in a root or a typed
share, nothing hidden or holding credentials on the way, no link
followed; a file must be a video. browse.expand(paths) is what the Add
screen adds: each video once, in the order given, and each folder's
videos (not its subfolders') in episode order, never a link or a hidden
file; a folder past MAX_ENTRIES is refused rather than added in part.

The new tests failed first with: AttributeError: module
'vid2sub.web.browse' has no attribute 'accept'. With accept taking any
file, the tests adding a text file and a subtitle file fail.

Docs read: none beyond the code (Task 1's walk and listing; spec §19.2's
"Folders add their videos sorted by SxxEyy").

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md Task 1
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/web/browse.py tests/test_browse.py`, `git commit -F .git/COMMIT_MSG`,
  then `git log -1 --format='%(trailers)'` shows `Plan:`.

  **Round 1c** is the fix round from the independent Tier 1 security review that ran over
  Steps 1–10 when this listing was built (one subagent, `AGENTS.md`'s checklist). It found two
  Important holes, both in how Windows reads a typed name: a drive inside a path
  (`D:\C:\x`) made the walk jump drives, because pathlib reads `C:` as a drive; and a short
  name (`SSH~1`), a trailing dot or space, or a stream (`AppData::$INDEX_ALLOCATION`) opened a
  folder whose typed name passed the checks. The fix walks the names the disk returns. Steps
  11–15 build it; the implementer's own review still runs at Step 16.

- [ ] **Step 11: Write the failing tests.** Replace `tests/test_browse.py` with (the Windows
  names, the disk's spellings, and the junction, hidden-attribute and short-name tests that run
  on Windows, where the symlink tests skip, as the suite's others do):

```python
"""The in-app file browser (spec §6.5, S38): what it lists, what it hides, what it refuses."""

import os
import stat
import sys
from pathlib import Path

import pytest

from vid2sub.web import browse
from vid2sub.web.browse import BrowseError, Entry

needs_symlinks = pytest.mark.skipif(sys.platform == "win32",
                                    reason="symlinks need privileges on Windows")


def touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")
    return path


@pytest.fixture
def places(tmp_path):
    """A home folder and a mounted volume, with what each root list should show."""
    home = tmp_path / "home"
    volume = tmp_path / "Volumes" / "Media"
    for folder in (home / "Movies", volume / "TV"):
        folder.mkdir(parents=True)
    return home, volume, (Entry("Home", str(home), "folder"), Entry("Media", str(volume), "folder"))


def names(listing) -> list[str]:
    return [e.name for e in listing.entries]


@needs_symlinks
def test_the_roots_are_home_then_each_mounted_volume_and_never_a_link(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    volumes = tmp_path / "Volumes"
    (volumes / "Media").mkdir(parents=True)
    (volumes / ".timemachine").mkdir()
    touch(volumes / "notes.txt")
    (volumes / "Macintosh HD").symlink_to("/")  # the boot volume's entry is a link to /
    assert browse.roots(home=home, volumes=[volumes, tmp_path / "missing"]) == (
        Entry("Home", str(home), "folder"), Entry("Media", str(volumes / "Media"), "folder"))


def test_this_machines_roots_start_with_home_and_are_all_real_folders():
    found = browse.roots()
    assert found[0] == Entry("Home", str(Path.home()), "folder")
    for root in found[1:]:
        if os.name == "nt":  # a drive letter may have no disk in it: listdrives doesn't look
            assert root.name.endswith(":") and root.path == root.name + "\\"
        else:
            assert os.path.isdir(root.path) and not os.path.islink(root.path)


def test_a_folder_shows_only_folders_videos_and_subtitles(places):
    home, _, roots = places
    for name in ("Show S01E01.mkv", "Clip.MP4", "Show S01E01.en.srt", "Show S01E01.ja.ass",
                 "Show S01E01.ko.vtt", "notes.txt", "cover.jpg", "Show.nfo",
                 "Show S01E01.vid2sub.jsonl"):
        touch(home / "Movies" / name)
    (home / "Movies" / "Extras").mkdir()
    listing = browse.listing(str(home / "Movies"), roots=roots, home=home)
    assert [(e.name, e.kind) for e in listing.entries] == [
        ("Extras", "folder"), ("Show S01E01.en.srt", "subtitle"),
        ("Show S01E01.ja.ass", "subtitle"), ("Show S01E01.ko.vtt", "subtitle"),
        ("Show S01E01.mkv", "video"), ("Clip.MP4", "video")]
    assert listing.entries[0].path == str(home / "Movies" / "Extras")
    assert listing.path == str(home / "Movies") and listing.parent == str(home)
    assert listing.truncated is False


def test_a_season_is_sorted_by_sxxeyy_after_its_folders_in_natural_order(places):
    home, volume, roots = places
    season = volume / "TV" / "Show"
    for name in ("Show S01E10.mkv", "Show S01E02.mkv", "Show s01e01.mkv", "Show S02E01.mkv",
                 "Behind the scenes.mkv"):
        touch(season / name)
    for name in ("Season 10", "Season 2", "season 1", "Season 1²"):
        (season / name).mkdir()
    assert names(browse.listing(str(season), roots=roots, home=home)) == [
        "season 1", "Season 1²", "Season 2", "Season 10", "Show s01e01.mkv",
        "Show S01E02.mkv", "Show S01E10.mkv", "Show S02E01.mkv", "Behind the scenes.mkv"]


def test_dotfiles_and_the_folders_that_hold_credentials_are_hidden(places):
    home, volume, roots = places
    for name in (".ssh", ".aws", ".gnupg", ".config/gh", "Library", "AppData", "@eaDir",
                 "$RECYCLE.BIN"):
        (home / name).mkdir(parents=True)
    touch(home / ".hidden.mkv")
    (volume / "Library").mkdir()  # a media library on a volume is not a credential folder
    assert names(browse.listing(str(home), roots=roots, home=home)) == ["Movies"]
    assert names(browse.listing(str(volume), roots=roots, home=home)) == ["Library", "TV"]


@pytest.mark.parametrize("inside", [".ssh", ".config/gh", "Library", "library", "AppData",
                                    "@eaDir", ".config"])
def test_a_hidden_or_credential_folder_is_refused_even_when_typed(places, inside):
    home, _, roots = places
    (home / inside).mkdir(parents=True, exist_ok=True)
    with pytest.raises(BrowseError) as err:
        browse.listing(str(home / inside), roots=roots, home=home)
    assert str(home) not in str(err.value) and inside not in str(err.value)


@needs_symlinks
def test_a_link_is_never_listed_and_never_followed(places, tmp_path):
    home, volume, roots = places
    outside = tmp_path / "outside"
    outside.mkdir()
    touch(outside / "Leak S01E01.mkv")
    (home / ".ssh").mkdir()
    movies = home / "Movies"
    touch(movies / "Real.mkv")
    (movies / "To outside").symlink_to(outside)
    (movies / "To ssh").symlink_to(home / ".ssh")
    (movies / "To TV").symlink_to(volume / "TV")
    (movies / "Link.mkv").symlink_to(movies / "Real.mkv")
    assert names(browse.listing(str(movies), roots=roots, home=home)) == ["Real.mkv"]
    for link in ("To outside", "To ssh", "To TV"):
        with pytest.raises(BrowseError, match="link"):
            browse.listing(str(movies / link), roots=roots, home=home)


def test_a_path_outside_every_root_is_refused_without_naming_it(places, tmp_path):
    _, _, roots = places
    elsewhere = tmp_path / "Elsewhere"
    elsewhere.mkdir()
    with pytest.raises(BrowseError) as err:
        browse.listing(str(elsewhere), roots=roots, home=tmp_path / "home")
    assert "home folder" in str(err.value) and "Elsewhere" not in str(err.value)


@pytest.mark.parametrize("typed", ["Movies", "home/Movies", "", "/a/../b", "/x\x00y",
                                   "/" + "a" * 5000])
def test_a_path_that_isnt_fully_qualified_is_refused(places, typed):
    home, _, roots = places
    with pytest.raises(BrowseError):
        browse.listing(typed, roots=roots, home=home)


def test_a_path_from_home_may_start_with_a_tilde(places):
    home, _, roots = places
    assert browse.listing("~/Movies", roots=roots, home=home).path == str(home / "Movies")


@pytest.mark.parametrize("typed", [r"C:Videos", r"\Videos", r"\\?\C:\Videos",
                                   r"\\.\PhysicalDrive0", r"//?/C:/Videos", r"\\nas",
                                   r"C:\Videos\..\Windows"])
def test_windows_paths_must_be_fully_qualified_and_never_a_device(typed):
    with pytest.raises(BrowseError):
        browse.qualified(typed, windows=True)


def test_a_windows_network_share_is_its_own_root_when_the_person_types_it():
    roots = (Entry("Home", r"C:\Users\someone", "folder"), Entry("C:", "C:\\", "folder"))
    path, root, below = browse.place(r"\\nas\media\TV\Show", roots=roots,
                                     home=r"C:\Users\someone", windows=True)
    assert (str(path), root, below) == (r"\\nas\media\TV\Show", "\\\\nas\\media\\", ("TV", "Show"))
    assert browse.place(r"c:\users\SOMEONE\Videos", roots=roots, home=r"C:\Users\someone",
                        windows=True)[1:] == (r"C:\Users\someone", ("Videos",))
    with pytest.raises(BrowseError):
        browse.place(r"C:\Users\someone\AppData\Roaming", roots=roots, home=r"C:\Users\someone",
                     windows=True)


@pytest.mark.skipif(sys.platform != "darwin", reason="the hidden flag is a macOS file flag")
def test_a_folder_the_system_marks_hidden_is_hidden(places):
    home, _, roots = places
    secret = home / "Keychains"
    secret.mkdir()
    os.chflags(secret, stat.UF_HIDDEN)
    assert names(browse.listing(str(home), roots=roots, home=home)) == ["Movies"]
    with pytest.raises(BrowseError, match="hidden"):
        browse.listing(str(secret), roots=roots, home=home)


@pytest.mark.skipif(os.name == "nt" or os.geteuid() == 0,
                    reason="POSIX permissions, which root ignores")
def test_a_folder_vid2sub_cannot_read_says_so_without_its_path(places):
    home, _, roots = places
    locked = home / "Locked"
    locked.mkdir(mode=0o000)
    try:
        with pytest.raises(BrowseError, match="isn't allowed") as err:
            browse.listing(str(locked), roots=roots, home=home)
        assert "Locked" not in str(err.value)
    finally:
        locked.chmod(0o700)


def test_a_missing_folder_or_a_file_is_not_a_folder_to_list(places):
    home, _, roots = places
    touch(home / "Movies" / "a.mkv")
    for typed in (home / "Gone", home / "Movies" / "a.mkv"):
        with pytest.raises(BrowseError, match="no folder"):
            browse.listing(str(typed), roots=roots, home=home)


def test_a_root_has_no_parent(places):
    home, volume, roots = places
    assert browse.listing(str(home), roots=roots, home=home).parent is None
    assert browse.listing(str(volume), roots=roots, home=home).parent is None


def test_a_huge_folder_is_cut_at_the_cap_and_says_so(places, monkeypatch):
    home, _, roots = places
    monkeypatch.setattr(browse, "MAX_ENTRIES", 3)
    for n in range(1, 6):
        touch(home / "Movies" / f"Show S01E0{n}.mkv")
    listing = browse.listing(str(home / "Movies"), roots=roots, home=home)
    assert names(listing) == ["Show S01E01.mkv", "Show S01E02.mkv", "Show S01E03.mkv"]
    assert listing.truncated is True


# Names Windows would read another way, and names as the disk spells them (security review)


@pytest.mark.parametrize("typed", [r"D:\C:\Videos", r"C:\Users\someone\C:\AppData",
                                   r"\\nas\media\C:\TV", r"C:\Videos\clip.mkv:stream",
                                   r"C:\Videos\CON", r"C:\Videos\nul.mkv", r"C:\Videos\COM1 .txt",
                                   r"C:\Users\someone\AppData.", r"C:\Users\someone\AppData "])
def test_a_windows_name_that_windows_reads_as_something_else_is_refused(typed):
    with pytest.raises(BrowseError):
        browse.qualified(typed, windows=True)


def test_a_lone_surrogate_is_refused_as_a_path(places):
    home, _, roots = places
    with pytest.raises(BrowseError):
        browse.listing(str(home) + "/Movies/\ud800", roots=roots, home=home)


def test_a_home_at_the_root_of_the_disk_is_not_a_root(tmp_path):
    assert browse.roots(home=Path(Path.cwd().anchor), volumes=[tmp_path / "none"]) == ()


def case_insensitive(folder: Path) -> bool:
    return (folder.parent / folder.name.swapcase()).exists()


def test_a_typed_path_comes_back_spelled_as_on_disk_and_is_added_once(places):
    home, _, roots = places
    film = touch(home / "Movies" / "Film.mkv")
    if not case_insensitive(home / "Movies"):
        pytest.skip("needs a case-insensitive disk, as macOS and Windows have by default")
    assert browse.listing(str(home / "movies"), roots=roots, home=home).path == str(
        home / "Movies")
    assert browse.expand([str(film), str(home / "MOVIES" / "film.MKV")], roots=roots,
                         home=home) == [str(film)]


windows_only = pytest.mark.skipif(os.name != "nt", reason="Windows' own names and links")


@windows_only
def test_a_windows_short_name_for_a_hidden_folder_reaches_nothing(places):
    import ctypes
    home, _, roots = places
    secret = home / ".gnupg"
    secret.mkdir()
    buffer = ctypes.create_unicode_buffer(32768)
    ctypes.windll.kernel32.GetShortPathNameW(str(secret), buffer, len(buffer))
    short = buffer.value.rsplit("\\", 1)[-1]
    if not short or short == secret.name:
        pytest.skip("this volume makes no short names")
    with pytest.raises(BrowseError):
        browse.listing(str(home / short), roots=roots, home=home)


@windows_only
def test_a_windows_junction_is_never_listed_and_never_followed(places, tmp_path):
    import _winapi
    home, _, roots = places
    outside = tmp_path / "outside"
    touch(outside / "Leak S01E01.mkv")
    _winapi.CreateJunction(str(outside), str(home / "Movies" / "Jump"))
    assert names(browse.listing(str(home / "Movies"), roots=roots, home=home)) == []
    with pytest.raises(BrowseError, match="link"):
        browse.listing(str(home / "Movies" / "Jump"), roots=roots, home=home)


@windows_only
def test_a_folder_windows_marks_hidden_is_hidden(places):
    import ctypes
    home, _, roots = places
    secret = home / "Secrets"
    secret.mkdir()
    assert ctypes.windll.kernel32.SetFileAttributesW(str(secret), stat.FILE_ATTRIBUTE_HIDDEN)
    assert names(browse.listing(str(home), roots=roots, home=home)) == ["Movies"]
    with pytest.raises(BrowseError, match="hidden"):
        browse.listing(str(secret), roots=roots, home=home)


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS keeps either Unicode form")
def test_a_folder_typed_in_the_other_unicode_form_is_found(tmp_path):
    import unicodedata
    home = tmp_path / unicodedata.normalize("NFC", "Café")
    (home / unicodedata.normalize("NFC", "Séries")).mkdir(parents=True)
    roots = (Entry("Home", str(home), "folder"),)
    typed = unicodedata.normalize("NFD", str(home / "Séries"))
    assert browse.listing(typed, roots=roots, home=home).path == unicodedata.normalize(
        "NFC", str(home / "Séries"))


# Adding: what the Add screen adds from the browser or a typed path (spec §10, §19.2)


@needs_symlinks
def test_adding_gives_each_video_once_and_each_folders_videos_in_episode_order(places,
                                                                              tmp_path):
    home, _, roots = places
    season = home / "Movies" / "Show"
    for name in ("Show S01E02.mkv", "Show S01E01.mkv", "Show S01E01.en.srt",
                 ".Show S01E03.mkv", "notes.txt", "Extras/Bonus.mkv"):
        touch(season / name)
    (season / "Show S01E04.mkv").symlink_to(touch(tmp_path / "outside.mkv"))
    film = touch(home / "Movies" / "Film.mp4")
    found = browse.expand([str(season), str(film), str(season / "Show S01E01.mkv")],
                          roots=roots, home=home)
    assert found == [str(season / "Show S01E01.mkv"), str(season / "Show S01E02.mkv"),
                     str(film)]


@pytest.mark.parametrize("bad", ["Movies/notes.txt", "Movies/Show.en.srt", "Movies/.Clip.mkv",
                                 ".ssh/Clip.mkv", "Movies/Gone.mkv"])
def test_adding_anything_but_a_visible_video_or_folder_is_refused(places, bad):
    home, _, roots = places
    for name in ("Movies/notes.txt", "Movies/Show.en.srt", "Movies/.Clip.mkv", ".ssh/Clip.mkv"):
        touch(home / name)
    with pytest.raises(BrowseError) as err:
        browse.accept(str(home / bad), roots=roots, home=home)
    assert str(home) not in str(err.value)


@needs_symlinks
def test_a_video_added_through_a_link_is_refused(places, tmp_path):
    home, _, roots = places
    (home / "Movies" / "Clip.mkv").symlink_to(touch(tmp_path / "outside.mkv"))
    with pytest.raises(BrowseError, match="link"):
        browse.accept(str(home / "Movies" / "Clip.mkv"), roots=roots, home=home)


def test_a_folder_too_big_to_add_at_once_is_refused(places, monkeypatch):
    home, _, roots = places
    monkeypatch.setattr(browse, "MAX_ENTRIES", 2)
    for n in range(1, 4):
        touch(home / "Movies" / f"Show S01E0{n}.mkv")
    with pytest.raises(BrowseError, match="too many"):
        browse.expand([str(home / "Movies")], roots=roots, home=home)
```

- [ ] **Step 12: Run it; watch it fail.** `uv run pytest tests/test_browse.py -q`. Expected:
  `E       Failed: DID NOT RAISE BrowseError` nine times (the Windows names),
  `E           UnicodeEncodeError: 'utf-8' codec can't encode character '\ud800' …`, the home at
  the disk's root still listed (`Left contains one more item: Entry(name='Home', path='/',
  kind='folder')`), the listing's path spelled as typed (`…/home/movies` against
  `…/home/Movies`), the other Unicode form refused (`BrowseError: vid2sub browses your home
  folder, your drives and network shares only`), and `13 failed, 42 passed, 3 skipped` (the
  three Windows tests skip on macOS and Linux).
- [ ] **Step 13: Write the code.** In `src/vid2sub/security.py`, rename `_RESERVED` to
  `RESERVED_NAMES` (its definition, and its one use in `safe_component`). Replace
  `src/vid2sub/web/browse.py` with:

```python
"""The in-app file browser: your home folder and mounted volumes, folders, videos and subtitles
(spec §6.5, S38).

The engine is a local server that lists directories, so what it lists is a security boundary
(spec §6). It lists only your home folder and mounted volumes (what's in `/Volumes` on a Mac, the
drive letters on Windows, what's in `/media`, `/run/media/<you>` and `/mnt` on Linux), shows only
folders, videos and subtitle files, and hides dotfiles, the folders that hold credentials
(`.ssh`, `.aws`, `.gnupg`, `.config/gh` …, and `Library` and `AppData` in your home), Synology's
and Windows' housekeeping folders, and any folder the system marks hidden; a hidden folder typed
in full is refused too. A path must be fully qualified (spec §6.5): the server's own folder means
nothing to the person typing; `~` stands for your home, as the editor's open allows. Every check
runs on the names the disk returns, walked down from the root one folder at a time, never on the
names as typed, so a Windows short name (`SSH~1`), a trailing dot or a stream (`name:stream`), a
second drive inside a path, a device name (`CON`) or the other Unicode form can't reach a folder
the browser wouldn't show; a path comes back spelled as on the disk. A Windows network path
(`\\\\server\\share`) is its own root: the caller passes only what the person typed or a path
from an earlier listing, never one read from a file, since a UNC path read from a file's contents
leaks the NTLM hash (§6.5). Links (symlinks, Windows junctions and other name-surrogate reparse
points) are never listed and never followed, so no link can lead outside your folders, into a
hidden one, or to a share nobody typed (decided in the Phase 3 plan, Task 1); that is why the boot
volume's `/Volumes` entry, a link to `/`, is not a root, nor is a home that is a disk's root. A
season's files sort by `SxxEyy`, others by natural name order (§10). What the Add screen adds,
browsed or typed, goes through the same checks, and a folder adds its videos in episode order
(§19.2). Reasons name no path (§6.8). Everything here blocks on the disk, and a sleeping network
share can take seconds, so the server calls it off the event loop.
"""

from __future__ import annotations

import os
import stat
import sys
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath
from typing import Literal

from vid2sub.pipeline import MEDIA_SUFFIXES
from vid2sub.security import RESERVED_NAMES
from vid2sub.subs.naming import episode_key, natural_key

SUBTITLE_SUFFIXES = frozenset({".srt", ".ass", ".ssa", ".vtt"})  # what `vid2sub import` reads
HOUSEKEEPING = frozenset({"@eadir", "#recycle", "$recycle.bin", "system volume information",
                          "lost+found"})  # casefolded: Synology, Windows and ext4 folders
CREDENTIALS = (".ssh", ".aws", ".gnupg", ".config/gh", ".azure", ".kube", ".docker",
               ".password-store", "Library", "AppData")  # in your home
MAX_ENTRIES = 5000
MAX_PATH = 4096
_HIDDEN_ATTRIBUTES = stat.FILE_ATTRIBUTE_HIDDEN | stat.FILE_ATTRIBUTE_SYSTEM
_NAME_SURROGATE = 0x20000000  # a reparse tag's bit for links: symlinks, junctions, WSL links
_FOLD = sys.platform in ("darwin", "win32")  # case-insensitive by default
Kind = Literal["folder", "video", "subtitle"]


class BrowseError(Exception):
    """A path the browser won't list or add; the reason names no path (spec §6.8)."""


@dataclass(frozen=True)
class Entry:
    name: str  # the bare name, shown as text
    path: str  # the full path: what the screen sends back to list or add
    kind: Kind


@dataclass(frozen=True)
class Listing:
    path: str
    parent: str | None  # None at a root, or at the top of a network share
    entries: tuple[Entry, ...]  # folders first, then videos and subtitles by SxxEyy
    truncated: bool = False  # more than MAX_ENTRIES: the rest aren't shown


def roots(*, home: Path | None = None,
          volumes: Sequence[Path] | None = None) -> tuple[Entry, ...]:
    """Your home first, then each mounted volume: each folder in `volumes` (by default
    `/Volumes`, `/media`, `/media/<you>`, `/run/media/<you>` and `/mnt`), or on Windows each
    drive letter. A link, a hidden folder or a file there is not a volume."""
    home = home or Path.home()
    found = [Entry("Home", str(home), "folder")] if len(home.parts) > 1 else []
    if volumes is None and os.name == "nt":
        found += [Entry(d.rstrip("\\"), d, "folder") for d in os.listdrives()]
        return tuple(found)
    if volumes is None:
        user = home.name
        volumes = [Path("/Volumes"), Path("/media"), Path("/media") / user,
                   Path("/run/media") / user, Path("/mnt")]
    seen = {str(home)}
    for parent in volumes:
        try:
            with os.scandir(parent) as it:
                mounts = sorted((e for e in it if _visible_folder(e)),
                                key=lambda e: natural_key(e.name))
        except OSError:
            continue
        for e in mounts:
            if e.path not in seen and e.path not in {str(v) for v in volumes}:
                seen.add(e.path)
                found.append(Entry(e.name, e.path, "folder"))
    return tuple(found)


_all_roots = roots  # `listing` takes a `roots` argument, which hides the function's name


def qualified(text: str, *, windows: bool) -> PurePath:
    """The path as the person gave it, refused unless fully qualified: from `/`, from a drive
    (`C:\\`), or a network share (`\\\\server\\share`), never a device path, never with `..`."""
    if not text or len(text) > MAX_PATH or "\x00" in text:
        raise BrowseError("give the folder's full path")
    path: PurePath = PureWindowsPath(text) if windows else PurePosixPath(text)
    if windows:
        if path.drive.startswith(("\\\\?\\", "\\\\.\\")):
            raise BrowseError("vid2sub doesn't open device paths")
        if not (path.drive and path.root):
            raise BrowseError("give the full path, from the drive (C:\\…) or the share "
                              "(\\\\server\\share\\…)")
        for part in path.parts[1:]:
            if ":" in part or part.endswith((".", " ")) and part not in (".", ".."):
                raise BrowseError("that isn't a name Windows gives a folder or a file")
            if part.split(".")[0].rstrip(" ").upper() in RESERVED_NAMES:
                raise BrowseError("vid2sub doesn't open device names")
    elif not path.root:
        raise BrowseError("give the full path, starting with /")
    if ".." in path.parts:
        raise BrowseError("give the path without ..")
    return path


def place(text: str, *, roots: Sequence[Entry], home: str | PurePath,
          windows: bool) -> tuple[PurePath, str, tuple[str, ...]]:
    """Where a path is: the path, the root it's in (a network share the person typed is its own
    root), and its parts below that root. Refuses a path in no root, and one below a hidden
    folder or a folder that holds credentials. Pure: it touches no disk."""
    flavour = PureWindowsPath if windows else PurePosixPath
    home_path = flavour(home)
    if text == "~" or text.startswith(("~/", "~\\")):
        text = str(home_path) + text[1:]
    path = qualified(text, windows=windows)
    best: tuple[str, tuple[str, ...]] | None = None
    for root in roots:
        below = _below(path, flavour(root.path))
        if below is not None and (best is None or len(below) < len(best[1])):
            best = (root.path, below)
    if best is None:
        if not (windows and path.drive.startswith("\\\\")):
            raise BrowseError("vid2sub browses your home folder, your drives and network "
                              "shares only")
        best = (path.anchor, path.parts[1:])
    for part in best[1]:
        if _hidden_name(part):
            raise BrowseError("vid2sub doesn't show hidden folders")
    in_home = _below(path, home_path)
    if in_home is not None and _holds_credentials(in_home):
        raise BrowseError("vid2sub doesn't show the folders that hold credentials")
    return path, best[0], best[1]


def listing(path: str, *, roots: Sequence[Entry] | None = None,
            home: Path | None = None) -> Listing:
    """One folder's folders, videos and subtitle files, never a link or anything hidden."""
    home = home or Path.home()
    folder, below, last = _walk(path, _all_roots(home=home) if roots is None else roots, home)
    if not (last.is_dir(follow_symlinks=False) if last is not None
            else stat.S_ISDIR(_lstat(folder).st_mode)):
        raise BrowseError("there's no folder there")
    in_home = _below(PurePath(folder), PurePath(home))
    folders: list[Entry] = []
    files: list[Entry] = []
    try:
        with os.scandir(folder) as it:
            for e in it:  # a link is neither a folder nor a file when it isn't followed
                if _visible_folder(e):
                    if in_home is None or not _holds_credentials((*in_home, e.name)):
                        folders.append(Entry(e.name, e.path, "folder"))
                elif (not _hidden_name(e.name) and e.is_file(follow_symlinks=False)
                      and not _is_link_entry(e)):
                    kind = _file_kind(e.name)
                    if kind is not None:
                        files.append(Entry(e.name, e.path, kind))
    except OSError as err:
        raise _refusal(err) from None
    folders.sort(key=lambda e: natural_key(e.name))
    files.sort(key=lambda e: episode_key(e.name))
    entries = folders + files
    return Listing(str(folder), None if not below else str(folder.parent),
                   tuple(entries[:MAX_ENTRIES]), len(entries) > MAX_ENTRIES)


def accept(path: str, *, roots: Sequence[Entry] | None = None,
           home: Path | None = None) -> Path:
    """A video or a folder the person typed or picked, to add: checked as `listing` checks a
    folder, so whatever the browser wouldn't show can't be added by typing it."""
    home = home or Path.home()
    target, _, last = _walk(path, _all_roots(home=home) if roots is None else roots, home)
    if last is None or last.is_dir(follow_symlinks=False) or (
            last.is_file(follow_symlinks=False) and _file_kind(last.name) == "video"):
        return target
    raise BrowseError("that isn't a video or a folder vid2sub can add")


def expand(paths: Sequence[str], *, roots: Sequence[Entry] | None = None,
           home: Path | None = None) -> list[str]:
    """What Add adds, each once, in the order given: a video as it is, and a folder's videos
    (not its subfolders') in episode order, never a link or a hidden file (spec §19.2)."""
    out: list[str] = []
    seen: set[str] = set()
    for text in paths:
        target = accept(text, roots=roots, home=home)
        if stat.S_ISDIR(_lstat(target).st_mode):
            found = listing(str(target), roots=roots, home=home)
            if found.truncated:
                raise BrowseError("that folder has too many files to add at once: add its "
                                  "seasons one at a time")
            items = [e.path for e in found.entries if e.kind == "video"]
        else:
            items = [str(target)]
        for item in items:
            if os.path.normcase(item) not in seen:
                seen.add(os.path.normcase(item))
                out.append(item)
    return out


def _key(name: str, *, fold: bool) -> str:
    """A name as a case-insensitive disk compares it: either Unicode form, any case."""
    return unicodedata.normalize("NFC", name).casefold() if fold else name


def _below(path: PurePath, root: PurePath) -> tuple[str, ...] | None:
    """The parts of `path` below `root`, or None when it isn't inside it."""
    fold = _FOLD or isinstance(path, PureWindowsPath)
    n = len(root.parts)
    if len(path.parts) < n or ([_key(p, fold=fold) for p in path.parts[:n]]
                               != [_key(p, fold=fold) for p in root.parts]):
        return None
    return path.parts[n:]


def _hidden_name(name: str) -> bool:
    return name.startswith(".") or name.casefold() in HOUSEKEEPING


def _holds_credentials(below_home: Sequence[str]) -> bool:
    parts = [p.casefold() for p in below_home]
    return any(parts[:len(c)] == c for c in (
        [p.casefold() for p in folder.split("/")] for folder in CREDENTIALS))


def _flagged_hidden(st: os.stat_result) -> bool:
    """A folder the system hides: macOS' hidden flag (`~/Library`), Windows' hidden or system
    attribute."""
    return bool(getattr(st, "st_flags", 0) & stat.UF_HIDDEN
                or getattr(st, "st_file_attributes", 0) & _HIDDEN_ATTRIBUTES)


def _is_link(st: os.stat_result) -> bool:
    return stat.S_ISLNK(st.st_mode) or bool(getattr(st, "st_reparse_tag", 0) & _NAME_SURROGATE)


def _is_link_entry(e: os.DirEntry) -> bool:
    """A symlink, a junction, or on Windows any other link-like reparse point (a WSL link);
    Windows' entries carry their reparse tag without a system call."""
    return e.is_symlink() or e.is_junction() or (
        os.name == "nt" and _is_link(e.stat(follow_symlinks=False)))


def _visible_folder(e: os.DirEntry) -> bool:
    try:
        return (not _hidden_name(e.name) and e.is_dir(follow_symlinks=False)
                and not _is_link_entry(e) and not _flagged_hidden(e.stat(follow_symlinks=False)))
    except OSError:
        return False


def _file_kind(name: str) -> Kind | None:
    suffix = os.path.splitext(name)[1].lower()
    if suffix in MEDIA_SUFFIXES:
        return "video"
    if suffix in SUBTITLE_SUFFIXES:
        return "subtitle"
    return None


def _refusal(err: OSError) -> BrowseError:
    """A disk error as a reason fit to show: never `err.filename`, a full path (spec §6.8)."""
    if isinstance(err, PermissionError):
        return BrowseError("vid2sub isn't allowed to read this folder")
    if isinstance(err, (FileNotFoundError, NotADirectoryError)):
        return BrowseError("there's no folder there")
    return BrowseError("couldn't read this folder" + (f" ({err.strerror})" if err.strerror
                                                      else ""))


def _lstat(path: Path) -> os.stat_result:
    try:
        return os.lstat(path)
    except OSError as err:
        raise _refusal(err) from None


def _entry(folder: Path, part: str) -> os.DirEntry:
    """The entry in `folder` the disk names `part`: the same name, else on a case-insensitive
    disk the same name in another case or Unicode form. An alias the disk would also open (a
    Windows short name) isn't an entry's name, so it isn't found."""
    fold = _FOLD
    near = None
    try:
        with os.scandir(folder) as it:
            for e in it:
                if e.name == part:
                    return e
                if near is None and fold and _key(e.name, fold=True) == _key(part, fold=True):
                    near = e
    except OSError as err:
        raise _refusal(err) from None
    if near is None:
        raise BrowseError("there's no folder there")
    return near


def _walk(text: str, roots: Sequence[Entry], home: Path
          ) -> tuple[Path, tuple[str, ...], os.DirEntry | None]:
    """The path spelled as on the disk, its names below its root, and the last one's entry
    (None at a root), found down from the root one name at a time without following anything:
    a hidden or credential folder, a link or a folder the system hides is refused by the name
    the disk returns."""
    _, root, below = place(text, roots=roots, home=home, windows=os.name == "nt")
    here, names, last = Path(root), [], None
    for part in below:
        last = _entry(here, part)
        here = here / last.name
        names.append(last.name)
        if _hidden_name(last.name):
            raise BrowseError("vid2sub doesn't show hidden folders")
        in_home = _below(PurePath(here), PurePath(home))
        if in_home is not None and _holds_credentials(in_home):
            raise BrowseError("vid2sub doesn't show the folders that hold credentials")
        try:
            if _is_link_entry(last):
                raise BrowseError("vid2sub doesn't follow links: browse to the folder it "
                                  "points to")
            if last.is_dir(follow_symlinks=False) and _flagged_hidden(
                    last.stat(follow_symlinks=False)):
                raise BrowseError("vid2sub doesn't show hidden folders")
        except OSError as err:
            raise _refusal(err) from None
    return here, tuple(names), last
```

- [ ] **Step 14: Run the checks; they pass.** `uv run pytest tests/test_browse.py
  tests/test_security.py -q` first (`76 passed, 4 skipped`), then the guard checks, then
  `make check`. **Guard checks**, each reverted and restored, each with
  `uv run pytest tests/test_browse.py -q`: in `qualified`, replace `if ":" in part or
  part.endswith` with `if part.endswith` (four Windows names pass: `4 failed`); in `_walk`,
  replace `here = here / last.name` with `here = here / part` (the two disk-spelling tests
  fail); replace `if part.split(".")[0].rstrip(" ").upper() in RESERVED_NAMES:` with
  `if False:` (`3 failed`); in `roots`, replace `"folder")] if len(home.parts) > 1 else []`
  with `"folder")]` (`FAILED …test_a_home_at_the_root_of_the_disk_is_not_a_root`); in `_walk`,
  replace `if _is_link_entry(last):` with `if False:` (both link tests fail). The short-name
  test is the guard for walking the disk's names on Windows; it runs only there (Task 10's and
  the existing Windows CI job). `make check`. Expected:
  `1094 passed, 5 skipped, 36 deselected` twice, `Test Files  19 passed (19)` and
  `Tests  88 passed (88)`, `All checks passed!` and `no leaks found`.
- [ ] **Step 15: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
fix(web): 🤖 the browser checks the names the disk returns, so no Windows alias reaches a hidden folder

The Tier 1 security review (one independent reviewer, AGENTS.md's
checklist) found two Important holes, both in how Windows reads a typed
name. A drive inside a path (D:\C:\x) made the walk jump to C:'s current
folder, since pathlib reads "C:" as a drive; and a short name (SSH~1), a
trailing dot or space, or a stream (AppData::$INDEX_ALLOCATION) opened a
dot folder whose typed name passed the checks. Now the walk finds each
name among its folder's entries (os.scandir) and checks the name the disk
returns: a short name is no entry's name, so it reaches nothing, and the
path comes back spelled as on the disk, which also adds a file typed in
two cases once and finds a folder typed in the other Unicode form on
macOS. On Windows, `qualified` refuses a ":" after the drive, a name
ending in a dot or a space, and device names (CON, NUL.mkv, COM1),
through security.RESERVED_NAMES (renamed from _RESERVED to share it).
Any name-surrogate reparse point (a WSL link, not only symlinks and
junctions) counts as a link. A home that is a disk's root isn't a root.
Symlink tests skip on Windows, as the suite's others do; Windows CI runs
the junction, hidden-attribute and short-name tests instead.

Found and fixed: Important 1 (a drive inside a path), Important 2 (names
Windows aliases), and Minor 5, 6, 7, 8, 9 and 11 (docstring). Recorded for
the phase end: Minor 3 (a folder swapped for a link between the check
and the use), Minor 10 (Library and AppData are hidden on every system),
Minor 12 (junctions and attributes are tested on Windows CI only).

The new tests failed first with: Failed: DID NOT RAISE BrowseError (the
Windows names), UnicodeEncodeError: 'utf-8' codec can't encode character
'\ud800', and the listing's path spelled as typed (home/movies). Guard
checks, each reverted and restored: without the ":" refusal, four
Windows names pass; with the walk joining the typed name, the disk
spelling tests fail; without the device names, three pass; with a home
at the root kept, its test fails; without the link check in the walk,
both link tests fail.

Docs read: Python's os docs (os.lstat and DirEntry on Windows reparse
points; st_reparse_tag), Microsoft's reparse-tag layout (the
name-surrogate bit, 0x20000000), unicodedata.normalize.

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md Task 1
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/security.py src/vid2sub/web/browse.py tests/test_browse.py`,
  `git commit -F .git/COMMIT_MSG`, then `git log -1 --format='%(trailers)'` shows `Plan:`.

  **Round 1d** adds Review Focus 1's listing half (a season on a NAS share that sleeps or drops
  off the network while it's listed): the test pins what `listing` already does, so it passes at
  once; its guard check shows it would catch the error escaping.

- [ ] **Step 16: Write the test.** In `tests/test_browse.py`, replace

```python
import os
import stat
```

  with

```python
import errno
import os
import stat
```

  and append, after two blank lines:

```python
# Review Focus 1: a network share that stops answering while it's listed (spec §6.5)


def test_a_share_that_drops_mid_listing_says_so_and_lists_nothing_it_had_read(places,
                                                                              monkeypatch):
    home, _, roots = places
    season = home / "Movies" / "Show"
    for n in range(1, 4):
        touch(season / f"Show S01E0{n}.mkv")
    real = os.scandir

    class Dropping:
        """The folder's first entry, then the share stops answering, as a NAS that sleeps or
        drops off the network mid-listing does."""

        def __init__(self, entries):
            self.entries = entries

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self.entries.close()

        def __iter__(self):
            yield next(self.entries)
            raise OSError(errno.ETIMEDOUT, os.strerror(errno.ETIMEDOUT))

    def scandir(path):
        found = real(path)
        return Dropping(found) if os.fspath(path) == str(season) else found

    monkeypatch.setattr(browse.os, "scandir", scandir)
    with pytest.raises(BrowseError, match="couldn't read this folder") as err:
        browse.listing(str(season), roots=roots, home=home)
    assert "Show" not in str(err.value) and str(home) not in str(err.value)
```

- [ ] **Step 17: Run it; it passes, pinning what the code does.** `uv run pytest
  tests/test_browse.py -q`. Expected: `56 passed, 3 skipped`. **Guard check:** in `listing`,
  replace the `except OSError as err:` just above `folders.sort(key=lambda e:
  natural_key(e.name))` with `except ZeroDivisionError as err:`; `uv run pytest
  tests/test_browse.py -q -k drops_mid_listing` fails with
  `E       TimeoutError: [Errno 60] Operation timed out` (Linux: `[Errno 110] Connection timed
  out`); restore it.
- [ ] **Step 18: Run the checks; they pass.** `make check`. Expected: `1095 passed, 5 skipped,
  36 deselected` twice, `Test Files  19 passed (19)` and `Tests  88 passed (88)`,
  `All checks passed!` and `no leaks found`.
- [ ] **Step 19: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
test(web): 🤖 a share that stops answering mid-listing says so, and the browser lists nothing it had read

Review Focus 1's listing half (Phase 3 plan): a season on a NAS share
that sleeps or drops off the network while it's listed. The new test
lets os.scandir return the folder's first entry, then fail as a share
that stopped answering does (ETIMEDOUT); listing raises BrowseError
("couldn't read this folder (Operation timed out)"), naming no path,
and returns no partial listing, so the screen (Task 2) has nothing
stale to show.

It pins behaviour the code already has: listing's `except OSError`
turns the error into a reason fit to show. With that clause made to
catch nothing, the test fails with: TimeoutError: [Errno 60] Operation
timed out.

Docs read: Python's os.scandir (an iterator; errors may be raised while
iterating, not only when it's opened) and os.strerror.

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md Task 1
Co-Authored-By: <the model's own line>
```

  `git add tests/test_browse.py`, `git commit -F .git/COMMIT_MSG`, then
  `git log -1 --format='%(trailers)'` shows `Plan:`.


  **Round 1e** is the fix round from the independent Tier 1 security review that ran over Steps
  1–19 when this listing was rebuilt on Phase 2's finished code (one subagent, `AGENTS.md`'s
  checklist). It found one Critical: `Library` and `AppData` were hidden only under your home's
  own spelling, and Linux can't read Windows' hidden attribute, so a Windows disk under WSL's
  `/mnt/c` listed `Users/<name>/AppData` down to `Credentials`. One Important: with no roots
  given, every call scanned and stat'ed every mounted volume, so one dead mount held up all
  browsing. Five Minor: a folder's own Windows device names, an incomplete and mutable reserved
  list, a linked root that `accept` took, names that aren't valid Unicode, and the check against
  use, which was already on the phase-end list. Steps 20–24 fix the first six.

- [ ] **Step 20: Write the failing tests.** Append to `tests/test_browse.py`, after two blank
  lines:

```python
# The Tier 1 security review of the rebuild: profiles on other roots, hidden shares, names a
# disk returns that Windows or Unicode would read otherwise, roots, and only the root needed


@pytest.mark.parametrize("profile", ["Users/someone/AppData/Local/Temp",
                                     "Users/someone/Library/Keychains", "users/SOMEONE/appdata"])
def test_a_users_library_and_appdata_stay_hidden_on_every_root_not_only_in_home(places,
                                                                               profile):
    home, volume, roots = places
    for folder in ("Users/someone/AppData/Local/Temp", "Users/someone/Library/Keychains",
                   "Users/someone/Videos"):
        (volume / folder).mkdir(parents=True)
    touch(volume / "Users/someone/AppData/Local/Temp/clip.mkv")
    assert names(browse.listing(str(volume / "Users" / "someone"), roots=roots,
                                home=home)) == ["Videos"]
    with pytest.raises(BrowseError, match="credentials"):
        browse.listing(str(volume / profile), roots=roots, home=home)
    with pytest.raises(BrowseError, match="credentials"):
        browse.expand([str(volume / "Users/someone/AppData/Local/Temp")], roots=roots, home=home)


@pytest.mark.parametrize("typed", [r"\\localhost\C$\Users\someone", r"\\nas\ADMIN$\x",
                                   "\\\\nas\\IPC$\\"])
def test_a_hidden_windows_share_is_refused(typed):
    with pytest.raises(BrowseError, match="hidden shares"):
        browse.qualified(typed, windows=True)


@pytest.mark.parametrize("typed", [r"C:\Videos\COM¹.mkv", r"C:\Videos\CONIN$",
                                   r"C:\Videos\lpt³ .txt"])
def test_every_device_name_windows_reserves_is_refused(typed):
    with pytest.raises(BrowseError, match="device names"):
        browse.qualified(typed, windows=True)


@windows_only
def test_a_name_in_a_folder_that_windows_would_read_otherwise_is_not_listed(places):
    home, _, roots = places
    movies = home / "Movies"
    touch(movies / "Show S01E01.mkv")
    for name in ("nul.mkv", "CON.mp4"):  # made through \\?\, as WSL or an NFS share can
        with open("\\\\?\\" + str(movies / name), "wb"):
            pass
    os.mkdir("\\\\?\\" + str(movies / "Extras."))
    assert names(browse.listing(str(movies), roots=roots, home=home)) == ["Show S01E01.mkv"]


@pytest.mark.skipif(sys.platform != "linux", reason="a Linux disk holds names that aren't UTF-8")
def test_a_name_that_isnt_valid_unicode_is_not_listed(places):
    home, _, roots = places
    movies = home / "Movies"
    touch(movies / "Show S01E01.mkv")
    with open(os.fsencode(movies) + b"/Show S01E02 \xff.mkv", "wb"):
        pass
    assert names(browse.listing(str(movies), roots=roots, home=home)) == ["Show S01E01.mkv"]


@needs_symlinks
def test_a_root_that_is_a_link_is_neither_listed_nor_added(tmp_path):
    real = tmp_path / "real"
    touch(real / "Film.mkv")
    home = tmp_path / "linkhome"
    home.symlink_to(real)
    roots = (Entry("Home", str(home), "folder"),)
    with pytest.raises(BrowseError):
        browse.listing("~", roots=roots, home=home)
    with pytest.raises(BrowseError):
        browse.expand(["~"], roots=roots, home=home)


def test_with_no_roots_given_a_path_in_home_touches_no_volume(places, monkeypatch):
    home, _, _ = places
    touch(home / "Movies" / "Film.mkv")
    scanned: list[str] = []
    real = os.scandir

    def scandir(path):
        scanned.append(os.fspath(path))
        return real(path)

    monkeypatch.setattr(browse.os, "scandir", scandir)
    assert names(browse.listing(str(home / "Movies"), home=home)) == ["Film.mkv"]
    assert browse.expand(["~/Movies"], home=home) == [str(home / "Movies" / "Film.mkv")]
    assert scanned and all(p.startswith(str(home)) for p in scanned)  # no /Volumes, no /mnt


@needs_symlinks
def test_with_no_roots_given_a_path_on_a_volume_looks_at_that_volume_alone(tmp_path,
                                                                           monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    volumes = tmp_path / "Volumes"
    touch(volumes / "Media" / "TV" / "Show S01E01.mkv")
    (volumes / "Asleep").mkdir()  # a mount that would hang if anything looked at it
    (volumes / "Boot").symlink_to(home)
    monkeypatch.setattr(browse, "_volume_parents", lambda home: [volumes])
    looked: list[str] = []
    real = browse._visible_folder
    monkeypatch.setattr(browse, "_visible_folder", lambda e: looked.append(e.name) or real(e))
    assert names(browse.listing(str(volumes / "Media" / "TV"), home=home)) == ["Show S01E01.mkv"]
    assert "Asleep" not in looked
    for outside in (volumes, volumes / "Boot"):  # the volumes' folder, and a link, are no root
        with pytest.raises(BrowseError, match="home folder"):
            browse.listing(str(outside), home=home)
```

- [ ] **Step 21: Run them; watch them fail.** `uv run pytest tests/test_browse.py -q`. Expected:
  the volume's `Users/someone` still listing `AppData` and `Library`
  (`E       AssertionError: assert ['AppData', '...ry', 'Videos'] == ['Videos']`, three times),
  `E       Failed: DID NOT RAISE BrowseError` seven times (the profiles typed, the hidden shares,
  `COM¹`, `CONIN$`, `lpt³`, the linked root added), `has no attribute '_volume_parents'`, the
  listing of home seen scanning `/Volumes`, `/media` and `/mnt`, and `12 failed, 56 passed,
  5 skipped` (the Windows-only and Linux-only tests skip on macOS).
- [ ] **Step 22: Write the code.** In `src/vid2sub/security.py`, replace

```python
RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
             *(f"LPT{i}" for i in range(1, 10))}
```

  with

```python
# Windows' device names, even with an extension: Python 3.13's ntpath._reserved_names.
RESERVED_NAMES = frozenset({"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$",
                            *(f"{port}{n}" for port in ("COM", "LPT")
                              for n in (*"123456789", "¹", "²", "³"))})
```

  Then replace `src/vid2sub/web/browse.py` with:

```python
"""The in-app file browser: your home folder and mounted volumes, folders, videos and subtitles
(spec §6.5, S38).

The engine is a local server that lists directories, so what it lists is a security boundary
(spec §6). It lists only your home folder and mounted volumes (what's in `/Volumes` on a Mac, the
drive letters on Windows, what's in `/media`, `/run/media/<you>` and `/mnt` on Linux), shows only
folders, videos and subtitle files, and hides dotfiles, the folders that hold credentials
(`.ssh`, `.aws`, `.gnupg`, `.config/gh` …, and `Library` and `AppData` in your home), Synology's
and Windows' housekeeping folders, and any folder the system marks hidden; a hidden folder typed
in full is refused too. A path must be fully qualified (spec §6.5): the server's own folder means
nothing to the person typing; `~` stands for your home, as the editor's open allows. Every check
runs on the names the disk returns, walked down from the root one folder at a time, never on the
names as typed, so a Windows short name (`SSH~1`), a trailing dot or a stream (`name:stream`), a
second drive inside a path, a device name (`CON`) or the other Unicode form can't reach a folder
the browser wouldn't show; a path comes back spelled as on the disk. A Windows network path
(`\\\\server\\share`) is its own root: the caller passes only what the person typed or a path
from an earlier listing, never one read from a file, since a UNC path read from a file's contents
leaks the NTLM hash (§6.5). Links (symlinks, Windows junctions and other name-surrogate reparse
points) are never listed and never followed, so no link can lead outside your folders, into a
hidden one, or to a share nobody typed (decided in the Phase 3 plan, Task 1); that is why the boot
volume's `/Volumes` entry, a link to `/`, is not a root, nor is a home that is a disk's root.
`Library` and `AppData` stay hidden in every user's profile the browser can reach (`Users/<name>/`
on a Windows disk, a Mac's backup or clone, `/mnt/c` under WSL), not only in your home, since an
OS flag that hides them may be off or, on Linux, unreadable; a share whose name ends in `$` (`C$`,
`ADMIN$`) is a hidden one and refused; on Windows, a name in a folder that Windows would read as a
device or a stream isn't listed; and a name that isn't valid Unicode isn't listed (the security
review). On Linux, Windows' hidden attribute can't be read, so `ProgramData` and the like show on
a mounted Windows disk. A season's files sort by `SxxEyy`, others by natural name order (§10).
What the Add screen adds, browsed or typed, goes through the same checks, and a folder adds its
videos in episode order (§19.2). Reasons name no path (§6.8). Everything here blocks on the
disk, and a sleeping network share can take seconds, so the server calls it off the event loop.
Given no roots, `listing`, `accept` and `expand` look only at the root a path can be in (your
home, or the one volume it names), never every mounted volume, so a sleeping or dead mount
elsewhere holds nothing up.
"""

from __future__ import annotations

import os
import stat
import sys
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath
from typing import Literal

from vid2sub.pipeline import MEDIA_SUFFIXES
from vid2sub.security import RESERVED_NAMES
from vid2sub.subs.naming import episode_key, natural_key

SUBTITLE_SUFFIXES = frozenset({".srt", ".ass", ".ssa", ".vtt"})  # what `vid2sub import` reads
HOUSEKEEPING = frozenset({"@eadir", "#recycle", "$recycle.bin", "system volume information",
                          "lost+found"})  # casefolded: Synology, Windows and ext4 folders
CREDENTIALS = (".ssh", ".aws", ".gnupg", ".config/gh", ".azure", ".kube", ".docker",
               ".password-store", "Library", "AppData")  # in your home
PROFILE_FOLDERS = frozenset({"library", "appdata"})  # casefolded: in any Users/<name>/ too
MAX_ENTRIES = 5000
MAX_PATH = 4096
_HIDDEN_ATTRIBUTES = stat.FILE_ATTRIBUTE_HIDDEN | stat.FILE_ATTRIBUTE_SYSTEM
_NAME_SURROGATE = 0x20000000  # a reparse tag's bit for links: symlinks, junctions, WSL links
_FOLD = sys.platform in ("darwin", "win32")  # case-insensitive by default
Kind = Literal["folder", "video", "subtitle"]


class BrowseError(Exception):
    """A path the browser won't list or add; the reason names no path (spec §6.8)."""


@dataclass(frozen=True)
class Entry:
    name: str  # the bare name, shown as text
    path: str  # the full path: what the screen sends back to list or add
    kind: Kind


@dataclass(frozen=True)
class Listing:
    path: str
    parent: str | None  # None at a root, or at the top of a network share
    entries: tuple[Entry, ...]  # folders first, then videos and subtitles by SxxEyy
    truncated: bool = False  # more than MAX_ENTRIES: the rest aren't shown


def roots(*, home: Path | None = None,
          volumes: Sequence[Path] | None = None) -> tuple[Entry, ...]:
    """Your home first, then each mounted volume: each folder in `volumes` (by default
    `/Volumes`, `/media`, `/media/<you>`, `/run/media/<you>` and `/mnt`), or on Windows each
    drive letter. A link, a hidden folder or a file there is not a volume."""
    home = home or Path.home()
    found = [Entry("Home", str(home), "folder")] if len(home.parts) > 1 else []
    if volumes is None and os.name == "nt":
        found += [Entry(d.rstrip("\\"), d, "folder") for d in os.listdrives()]
        return tuple(found)
    if volumes is None:
        volumes = _volume_parents(home)
    seen = {str(home)}
    for parent in volumes:
        try:
            with os.scandir(parent) as it:
                mounts = sorted((e for e in it if _visible_folder(e)),
                                key=lambda e: natural_key(e.name))
        except OSError:
            continue
        for e in mounts:
            if e.path not in seen and e.path not in {str(v) for v in volumes}:
                seen.add(e.path)
                found.append(Entry(e.name, e.path, "folder"))
    return tuple(found)


def _volume_parents(home: Path) -> list[Path]:
    """Where mounted volumes are: `/Volumes` (a Mac), `/media`, `/media/<you>`,
    `/run/media/<you>` and `/mnt` (Linux)."""
    return [Path("/Volumes"), Path("/media"), Path("/media") / home.name,
            Path("/run/media") / home.name, Path("/mnt")]


def _roots_near(text: str, home: Path) -> tuple[Entry, ...]:
    """The roots `text` can be in, found without scanning every mounted volume (the security
    review): your home, and the one volume its path names, checked as `roots` checks a volume,
    or on Windows its drive. A path that isn't qualified gets your home alone, and `place`
    refuses it with its reason."""
    found = [Entry("Home", str(home), "folder")] if len(home.parts) > 1 else []
    windows = os.name == "nt"
    try:
        path = qualified(_tilde(text, home, windows=windows), windows=windows)
    except BrowseError:
        return tuple(found)
    if windows:
        if len(path.drive) == 2:  # a drive letter; a typed share is its own root
            drive = path.drive.upper()
            found.append(Entry(drive, drive + "\\", "folder"))
        return tuple(found)
    parents = _volume_parents(home)
    for parent in parents:
        below = _below(path, PurePosixPath(parent))
        if not below or parent / below[0] in parents or str(parent / below[0]) == str(home):
            continue
        try:
            mount = _entry(parent, below[0])  # one scan of the parent: no other mount is touched
        except BrowseError:
            continue
        if _visible_folder(mount):
            found.append(Entry(mount.name, mount.path, "folder"))
    return tuple(found)


def qualified(text: str, *, windows: bool) -> PurePath:
    """The path as the person gave it, refused unless fully qualified: from `/`, from a drive
    (`C:\\`), or a network share (`\\\\server\\share`), never a device path, never with `..`."""
    if not text or len(text) > MAX_PATH or "\x00" in text:
        raise BrowseError("give the folder's full path")
    path: PurePath = PureWindowsPath(text) if windows else PurePosixPath(text)
    if windows:
        if path.drive.startswith(("\\\\?\\", "\\\\.\\")):
            raise BrowseError("vid2sub doesn't open device paths")
        if not (path.drive and path.root):
            raise BrowseError("give the full path, from the drive (C:\\…) or the share "
                              "(\\\\server\\share\\…)")
        if path.drive.startswith("\\\\") and path.drive.endswith("$"):
            raise BrowseError("vid2sub doesn't open hidden shares (C$, ADMIN$ …)")
        for part in path.parts[1:]:
            refused = _windows_refusal(part)
            if refused:
                raise BrowseError(refused)
    elif not path.root:
        raise BrowseError("give the full path, starting with /")
    if ".." in path.parts:
        raise BrowseError("give the path without ..")
    return path


def place(text: str, *, roots: Sequence[Entry], home: str | PurePath,
          windows: bool) -> tuple[PurePath, str, tuple[str, ...]]:
    """Where a path is: the path, the root it's in (a network share the person typed is its own
    root), and its parts below that root. Refuses a path in no root, and one below a hidden
    folder or a folder that holds credentials. Pure: it touches no disk."""
    flavour = PureWindowsPath if windows else PurePosixPath
    home_path = flavour(home)
    path = qualified(_tilde(text, home, windows=windows), windows=windows)
    best: tuple[str, tuple[str, ...]] | None = None
    for root in roots:
        below = _below(path, flavour(root.path))
        if below is not None and (best is None or len(below) < len(best[1])):
            best = (root.path, below)
    if best is None:
        if not (windows and path.drive.startswith("\\\\")):
            raise BrowseError("vid2sub browses your home folder, your drives and network "
                              "shares only")
        best = (path.anchor, path.parts[1:])
    for part in best[1]:
        if _hidden_name(part):
            raise BrowseError("vid2sub doesn't show hidden folders")
    in_home = _below(path, home_path)
    if (in_home is not None and _holds_credentials(in_home)) or _in_a_profile(best[1]):
        raise BrowseError("vid2sub doesn't show the folders that hold credentials")
    return path, best[0], best[1]


def listing(path: str, *, roots: Sequence[Entry] | None = None,
            home: Path | None = None) -> Listing:
    """One folder's folders, videos and subtitle files, never a link or anything hidden."""
    home = home or Path.home()
    folder, below, last = _walk(path, _roots_near(path, home) if roots is None else roots, home)
    if not (last.is_dir(follow_symlinks=False) if last is not None
            else stat.S_ISDIR(_lstat(folder).st_mode)):
        raise BrowseError("there's no folder there")
    in_home = _below(PurePath(folder), PurePath(home))
    folders: list[Entry] = []
    files: list[Entry] = []
    try:
        with os.scandir(folder) as it:
            for e in it:  # a link is neither a folder nor a file when it isn't followed
                if not _listable(e.name):
                    continue
                if _visible_folder(e):
                    if not ((in_home is not None and _holds_credentials((*in_home, e.name)))
                            or _in_a_profile((*below, e.name))):
                        folders.append(Entry(e.name, e.path, "folder"))
                elif (not _hidden_name(e.name) and e.is_file(follow_symlinks=False)
                      and not _is_link_entry(e)):
                    kind = _file_kind(e.name)
                    if kind is not None:
                        files.append(Entry(e.name, e.path, kind))
    except OSError as err:
        raise _refusal(err) from None
    folders.sort(key=lambda e: natural_key(e.name))
    files.sort(key=lambda e: episode_key(e.name))
    entries = folders + files
    return Listing(str(folder), None if not below else str(folder.parent),
                   tuple(entries[:MAX_ENTRIES]), len(entries) > MAX_ENTRIES)


def accept(path: str, *, roots: Sequence[Entry] | None = None,
           home: Path | None = None) -> Path:
    """A video or a folder the person typed or picked, to add: checked as `listing` checks a
    folder, so whatever the browser wouldn't show can't be added by typing it."""
    home = home or Path.home()
    target, _, last = _walk(path, _roots_near(path, home) if roots is None else roots, home)
    if last is None:  # a root: a folder, as `listing` checks it, never a link
        if stat.S_ISDIR(_lstat(target).st_mode):
            return target
    elif last.is_dir(follow_symlinks=False) or (
            last.is_file(follow_symlinks=False) and _file_kind(last.name) == "video"):
        return target
    raise BrowseError("that isn't a video or a folder vid2sub can add")


def expand(paths: Sequence[str], *, roots: Sequence[Entry] | None = None,
           home: Path | None = None) -> list[str]:
    """What Add adds, each once, in the order given: a video as it is, and a folder's videos
    (not its subfolders') in episode order, never a link or a hidden file (spec §19.2)."""
    out: list[str] = []
    seen: set[str] = set()
    for text in paths:
        target = accept(text, roots=roots, home=home)
        if stat.S_ISDIR(_lstat(target).st_mode):
            found = listing(str(target), roots=roots, home=home)
            if found.truncated:
                raise BrowseError("that folder has too many files to add at once: add its "
                                  "seasons one at a time")
            items = [e.path for e in found.entries if e.kind == "video"]
        else:
            items = [str(target)]
        for item in items:
            if os.path.normcase(item) not in seen:
                seen.add(os.path.normcase(item))
                out.append(item)
    return out


def _key(name: str, *, fold: bool) -> str:
    """A name as a case-insensitive disk compares it: either Unicode form, any case."""
    return unicodedata.normalize("NFC", name).casefold() if fold else name


def _below(path: PurePath, root: PurePath) -> tuple[str, ...] | None:
    """The parts of `path` below `root`, or None when it isn't inside it."""
    fold = _FOLD or isinstance(path, PureWindowsPath)
    n = len(root.parts)
    if len(path.parts) < n or ([_key(p, fold=fold) for p in path.parts[:n]]
                               != [_key(p, fold=fold) for p in root.parts]):
        return None
    return path.parts[n:]


def _tilde(text: str, home: str | PurePath, *, windows: bool) -> str:
    """`~` and `~/…` as your home, as the editor's open allows."""
    if text == "~" or text.startswith(("~/", "~\\")):
        return str(PureWindowsPath(home) if windows else PurePosixPath(home)) + text[1:]
    return text


def _windows_refusal(name: str) -> str | None:
    """Why Windows would read a name as something other than a folder or a file of that name:
    a stream (`name:stream`), a trailing dot or space it drops, or a device (`CON`, `NUL.mkv`,
    `COM¹`), as Python 3.13's `ntpath.isreserved` decides; None for a plain name."""
    if ":" in name or name.endswith((".", " ")) and name not in (".", ".."):
        return "that isn't a name Windows gives a folder or a file"
    if name.split(".")[0].rstrip(" ").upper() in RESERVED_NAMES:
        return "vid2sub doesn't open device names"
    return None


def _listable(name: str) -> bool:
    """A name the browser can show and send back: valid Unicode (a disk can hold names that
    aren't), and on Windows one that names what it says (`_windows_refusal`)."""
    try:
        name.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return os.name != "nt" or _windows_refusal(name) is None


def _in_a_profile(below_root: Sequence[str]) -> bool:
    """A user's `Library` or `AppData` anywhere below a root (`Users/<name>/AppData` on a
    Windows disk, a Mac's backup, WSL's `/mnt/c`), where no hidden flag may be there to read."""
    parts = [p.casefold() for p in below_root]
    return any(parts[i] == "users" and parts[i + 2] in PROFILE_FOLDERS
               for i in range(len(parts) - 2))


def _hidden_name(name: str) -> bool:
    return name.startswith(".") or name.casefold() in HOUSEKEEPING


def _holds_credentials(below_home: Sequence[str]) -> bool:
    parts = [p.casefold() for p in below_home]
    return any(parts[:len(c)] == c for c in (
        [p.casefold() for p in folder.split("/")] for folder in CREDENTIALS))


def _flagged_hidden(st: os.stat_result) -> bool:
    """A folder the system hides: macOS' hidden flag (`~/Library`), Windows' hidden or system
    attribute."""
    return bool(getattr(st, "st_flags", 0) & stat.UF_HIDDEN
                or getattr(st, "st_file_attributes", 0) & _HIDDEN_ATTRIBUTES)


def _is_link(st: os.stat_result) -> bool:
    return stat.S_ISLNK(st.st_mode) or bool(getattr(st, "st_reparse_tag", 0) & _NAME_SURROGATE)


def _is_link_entry(e: os.DirEntry) -> bool:
    """A symlink, a junction, or on Windows any other link-like reparse point (a WSL link);
    Windows' entries carry their reparse tag without a system call."""
    return e.is_symlink() or e.is_junction() or (
        os.name == "nt" and _is_link(e.stat(follow_symlinks=False)))


def _visible_folder(e: os.DirEntry) -> bool:
    try:
        return (not _hidden_name(e.name) and e.is_dir(follow_symlinks=False)
                and not _is_link_entry(e) and not _flagged_hidden(e.stat(follow_symlinks=False)))
    except OSError:
        return False


def _file_kind(name: str) -> Kind | None:
    suffix = os.path.splitext(name)[1].lower()
    if suffix in MEDIA_SUFFIXES:
        return "video"
    if suffix in SUBTITLE_SUFFIXES:
        return "subtitle"
    return None


def _refusal(err: OSError) -> BrowseError:
    """A disk error as a reason fit to show: never `err.filename`, a full path (spec §6.8)."""
    if isinstance(err, PermissionError):
        return BrowseError("vid2sub isn't allowed to read this folder")
    if isinstance(err, (FileNotFoundError, NotADirectoryError)):
        return BrowseError("there's no folder there")
    return BrowseError("couldn't read this folder" + (f" ({err.strerror})" if err.strerror
                                                      else ""))


def _lstat(path: Path) -> os.stat_result:
    try:
        return os.lstat(path)
    except OSError as err:
        raise _refusal(err) from None


def _entry(folder: Path, part: str) -> os.DirEntry:
    """The entry in `folder` the disk names `part`: the same name, else on a case-insensitive
    disk the same name in another case or Unicode form. An alias the disk would also open (a
    Windows short name) isn't an entry's name, so it isn't found."""
    fold = _FOLD
    near = None
    try:
        with os.scandir(folder) as it:
            for e in it:
                if e.name == part:
                    return e
                if near is None and fold and _key(e.name, fold=True) == _key(part, fold=True):
                    near = e
    except OSError as err:
        raise _refusal(err) from None
    if near is None:
        raise BrowseError("there's no folder there")
    return near


def _walk(text: str, roots: Sequence[Entry], home: Path
          ) -> tuple[Path, tuple[str, ...], os.DirEntry | None]:
    """The path spelled as on the disk, its names below its root, and the last one's entry
    (None at a root), found down from the root one name at a time without following anything:
    a hidden or credential folder, a link or a folder the system hides is refused by the name
    the disk returns."""
    _, root, below = place(text, roots=roots, home=home, windows=os.name == "nt")
    here, names, last = Path(root), [], None
    for part in below:
        last = _entry(here, part)
        here = here / last.name
        names.append(last.name)
        if _hidden_name(last.name):
            raise BrowseError("vid2sub doesn't show hidden folders")
        in_home = _below(PurePath(here), PurePath(home))
        if (in_home is not None and _holds_credentials(in_home)) or _in_a_profile(names):
            raise BrowseError("vid2sub doesn't show the folders that hold credentials")
        try:
            if _is_link_entry(last):
                raise BrowseError("vid2sub doesn't follow links: browse to the folder it "
                                  "points to")
            if last.is_dir(follow_symlinks=False) and _flagged_hidden(
                    last.stat(follow_symlinks=False)):
                raise BrowseError("vid2sub doesn't show hidden folders")
        except OSError as err:
            raise _refusal(err) from None
    return here, tuple(names), last
```

- [ ] **Step 23: Run the checks; they pass.** `uv run pytest tests/test_browse.py
  tests/test_security.py -q` first (`89 passed, 6 skipped`), then the guard checks, then
  `make check`. **Guard checks**, each reverted and restored, each with
  `uv run pytest tests/test_browse.py -q`: make `_in_a_profile` return `False` (the three
  profile cases fail); replace `if path.drive.startswith("\\\\") and path.drive.endswith("$"):`
  with `if False:` (the three hidden-share cases fail); in `accept`, replace the root's
  `if stat.S_ISDIR(_lstat(target).st_mode):` / `return target` with a bare `return target`
  (`FAILED …test_a_root_that_is_a_link_is_neither_listed_nor_added`); in `listing`, replace
  `_roots_near(path, home) if roots is None` with
  `_roots_near.__globals__["roots"](home=home) if roots is None` (every volume scanned: both
  `…with_no_roots_given…` tests fail); in `_roots_near`, replace
  `if not below or parent / below[0] in parents or str(parent / below[0]) == str(home):` /
  `continue` with a bare `continue` (`FAILED …looks_at_that_volume_alone`); in
  `security.py`, replace `for n in (*"123456789", "¹", "²", "³"))})` with
  `for n in "123456789")})` (the `COM¹` and `lpt³` cases fail). The Windows-only test (names
  made through `\\?\`) and the Linux-only one (a name with the byte `0xff`) run on CI only.
  `make check`. Expected: `1107 passed, 7 skipped, 36 deselected` twice,
  `Test Files  19 passed (19)` and `Tests  88 passed (88)`, `All checks passed!` and
  `no leaks found`.
- [ ] **Step 24: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
fix(web): 🤖 the browser hides every user's Library and AppData, refuses hidden shares, and looks only at the root a path is in

The Tier 1 security review of the rebuild (one independent reviewer,
AGENTS.md's checklist) found one Critical, one Important and five Minor.

Critical 1: Library and AppData were hidden only under your home's own
spelling, and Linux can't read Windows' hidden attribute, so a Windows
disk under WSL's /mnt/c, a dual-boot disk under /media or a Mac's
backup under /Volumes listed Users/<name>/AppData and Library, down to
Credentials and Keychains, and Add took a video from AppData's Temp.
Now a user's Library or AppData below any root is hidden in listings
and refused when typed or walked (PROFILE_FOLDERS, _in_a_profile), and
a share whose name ends in $ (C$, ADMIN$, IPC$) is refused as hidden.
A volume's own top-level Library still shows.

Important 2: with no roots given, listing, accept and expand scanned
every mounted volume, and stat'ed each, on every call, so one sleeping
or dead mount held up a listing of ~/Movies. Now they look only at the
root a path can be in (_roots_near): your home, the one volume the
path names (one scan of /Volumes or /mnt, one stat of that mount), or
on Windows its drive.

Minor 3: on Windows a folder's own entries that Windows reads as a
device or a stream (nul.mkv, CON.mp4, a trailing dot) are no longer
listed, by the rule qualified applies to a typed name (one helper).
Minor 4: security.RESERVED_NAMES is now Python 3.13's
ntpath._reserved_names, frozen (CONIN$, CONOUT$, COM¹²³, LPT¹²³ added),
which safe_component shares. Minor 5: accept refuses a root that is a
link, as listing does. Minor 6: a name that isn't valid Unicode (Linux
bytes, an unpaired surrogate) isn't listed, so a listing always encodes.
Minor 7 (a folder swapped for a link between the check and the job) is
already on the phase-end list; recorded there too: safe_component
doesn't strip a space before its reserved-name lookup ("CON .x"), which
predates this task.

The new tests failed first with (12 failed): the volume's
Users/someone listing showing ['AppData', 'Library', 'Videos'],
Failed: DID NOT RAISE BrowseError (the profiles typed, the hidden
shares, COM¹, CONIN$, lpt³, the linked root added), and the volume
scan seen in a listing of home. Guard checks, each reverted and
restored: without _in_a_profile, without the hidden-share refusal,
without the root check in accept, with listing scanning every volume
again, with _roots_near finding no volume, and with the old reserved
names, their tests fail. The Windows-only test (names made through
\\?\) and the Linux-only one (a name with the byte 0xff) run on CI.

Docs read: Python 3.14's ntpath.isreserved and _reserved_names (3.13+;
CI's 3.12 lacks them, hence vid2sub's own copy), os.scandir and
DirEntry (names decoded with surrogateescape on POSIX), pathlib's
PureWindowsPath.drive for UNC paths; Microsoft's "Naming Files, Paths,
and Namespaces" as ntpath cites it.

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md Task 1
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/web/browse.py src/vid2sub/security.py tests/test_browse.py`,
  `git commit -F .git/COMMIT_MSG`, then `git log -1 --format='%(trailers)'` shows `Plan:`.

  **Round 1f** holds the one re-review's fixes (`AGENTS.md`'s cap for Tier 1: one-line fixes
  made directly, the rest to the phase-end list). Refusing every `$` share refused a person's
  own hidden media share too, so only a disk's admin shares are refused, read as Windows reads
  the name (without trailing dots); and the Windows-only test removes the names it makes.

- [ ] **Step 25: Change the tests.** In `tests/test_browse.py`, replace `import errno` with
  `import contextlib` / `import errno` (two lines); replace

```python
@pytest.mark.parametrize("typed", [r"\\localhost\C$\Users\someone", r"\\nas\ADMIN$\x",
                                   "\\\\nas\\IPC$\\"])
def test_a_hidden_windows_share_is_refused(typed):
    with pytest.raises(BrowseError, match="hidden shares"):
        browse.qualified(typed, windows=True)
```

  with

```python
@pytest.mark.parametrize("typed", [r"\\localhost\C$\Users\someone", r"\\nas\ADMIN$\x",
                                   "\\\\nas\\IPC$\\", r"\\localhost\c$.\Users"])
def test_a_disks_admin_share_is_refused_and_a_hidden_media_share_is_not(typed):
    with pytest.raises(BrowseError, match="admin shares"):
        browse.qualified(typed, windows=True)
    assert str(browse.qualified(r"\\nas\media$\TV", windows=True)) == r"\\nas\media$\TV"
```

  and replace

```python
    for name in ("nul.mkv", "CON.mp4"):  # made through \\?\, as WSL or an NFS share can
        with open("\\\\?\\" + str(movies / name), "wb"):
            pass
    os.mkdir("\\\\?\\" + str(movies / "Extras."))
    assert names(browse.listing(str(movies), roots=roots, home=home)) == ["Show S01E01.mkv"]
```

  with

```python
    odd = ["\\\\?\\" + str(movies / name) for name in ("nul.mkv", "CON.mp4", "Extras.")]
    try:
        for made in odd[:2]:  # made through \\?\, as WSL or an NFS share can
            with open(made, "wb"):
                pass
        os.mkdir(odd[2])
        assert names(browse.listing(str(movies), roots=roots, home=home)) == ["Show S01E01.mkv"]
    finally:  # only a \\?\ path removes them, so pytest's own clean-up can't
        for made in odd[:2]:
            with contextlib.suppress(OSError):
                os.remove(made)
        with contextlib.suppress(OSError):
            os.rmdir(odd[2])
```

- [ ] **Step 26: Run them; watch them fail.** `uv run pytest tests/test_browse.py -q`.
  Expected: `E       AssertionError: Regex pattern did not match.` three times (the reason still
  says "hidden shares"), `E       Failed: DID NOT RAISE BrowseError` (`\\localhost\c$.\Users`),
  and `4 failed, 65 passed, 5 skipped`.
- [ ] **Step 27: Write the code.** In `src/vid2sub/web/browse.py`, below `import os`, add
  `import re`; in the module docstring, replace

```python
OS flag that hides them may be off or, on Linux, unreadable; a share whose name ends in `$` (`C$`,
`ADMIN$`) is a hidden one and refused; on Windows, a name in a folder that Windows would read as a
device or a stream isn't listed; and a name that isn't valid Unicode isn't listed (the security
review). On Linux, Windows' hidden attribute can't be read, so `ProgramData` and the like show on
a mounted Windows disk. A season's files sort by `SxxEyy`, others by natural name order (§10).
```

  with

```python
OS flag that hides them may be off or, on Linux, unreadable; a disk's admin share (`C$`, `ADMIN$`,
`IPC$`), another way to the whole disk, is refused; on Windows, a name in a folder that Windows
would read as a device or a stream isn't listed; and a name that isn't valid Unicode isn't listed
(the security review). On Linux, Windows' hidden attribute can't be read, so `ProgramData` and
the like show on a mounted Windows disk. A season's files sort by `SxxEyy`, others by natural
name order (§10).
```

  and in `qualified`, replace

```python
        if path.drive.startswith("\\\\") and path.drive.endswith("$"):
            raise BrowseError("vid2sub doesn't open hidden shares (C$, ADMIN$ …)")
```

  with

```python
        share = path.drive.rsplit("\\", 1)[-1].rstrip(". ").upper()  # Windows drops the dots
        if path.drive.startswith("\\\\") and re.fullmatch(r"([A-Z]|ADMIN|IPC)\$", share):
            raise BrowseError("vid2sub doesn't open a disk's admin shares (C$, ADMIN$, IPC$)")
```

- [ ] **Step 28: Run the checks; they pass.** `uv run pytest tests/test_browse.py -q` first
  (`69 passed, 5 skipped`), then the guard check, then `make check`. **Guard check:** replace
  `.rstrip(". ").upper()  # Windows drops the dots` with `.upper()` (the `c$.` case fails);
  restore it. `make check`. Expected: `1108 passed, 7 skipped, 36 deselected` twice,
  `Test Files  19 passed (19)` and `Tests  88 passed (88)`, `All checks passed!` and
  `no leaks found`.
- [ ] **Step 29: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
fix(web): 🤖 only a disk's admin shares are refused, its trailing dots dropped, and the Windows test cleans up

The one re-review of round 1e (AGENTS.md's cap for Tier 1) found the
fixes held, with Minor points left. Two are fixed here, as the cap
allows. Refusing every share whose name ends in $ also refused a
person's own hidden media share (\\nas\media$), narrowing spec §6.5's
"UNC paths when typed"; now only a disk's admin shares are refused
(a drive letter's, ADMIN$, IPC$), which are the other way to the whole
disk, and the share's name is read as Windows reads it, without its
trailing dots and spaces (\\localhost\c$.\ is C$). The Windows-only test
removes the names it makes through \\?\, which nothing else can.

Recorded for the phase end instead: a root that is itself a Users or a
profile share (a mount of //pc/Users) still lists AppData; a volume's
name or a walked name that isn't valid Unicode can still reach a path.

The changed test failed first with: Regex pattern did not match
(the old "hidden shares" reason) and DID NOT RAISE BrowseError
(\\localhost\c$.\Users). Guard check, reverted and restored: reading the
share's name with its dots, the c$. case fails.

Docs read: Microsoft's "Naming Files, Paths, and Namespaces" (trailing
dots and spaces dropped), as Python's ntpath cites it; pathlib's
PureWindowsPath.drive for a UNC path (\\server\share).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md Task 1
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/web/browse.py tests/test_browse.py`, `git commit -F .git/COMMIT_MSG`,
  then `git log -1 --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 30: Review, look forward, close.** The Tier 1 review from `$(cat .git/TASK_BASE)`
  (`AGENTS.md`, *Reviews*, with the security checklist: secrets (none read: only names, types
  and flags; no credential folder listed under any root, a user's `Library` and `AppData` on
  another disk included); permissions (read-only: what is listed, and that nothing is opened
  or written); network exposure (no link is followed, so none leads to an SMB share; a UNC
  path only as typed or browsed, never a disk's admin share; only the volume a path names is
  touched, so a dead mount elsewhere holds nothing up); failing closed (every `OSError` a
  `BrowseError`; an entry that can't be read is hidden; a root that is a link is refused);
  injection (`..`, NUL, device paths and every name Windows reserves, typed or on the disk, a
  drive inside a path, case and Unicode folding, a lone surrogate typed or a name that isn't
  Unicode on the disk, very long input); logging (nothing logs; every reason is a fixed string
  with at most `strerror`)). Rounds 1c, 1e and 1f are earlier reviews' fixes; this review is
  the implementer's own. Worth the reviewers' time: Windows (8.3 names, junctions, mapped and
  network drives, `\\?\` names in a folder), which only CI's Windows job runs. The forward
  review over Tasks 2, 10 and 11 and Phase 4: Task 2's runtime passes its own `browse_roots`
  (None outside the demo, so `listing` and `expand` look only at the root a path is in) and
  lists the places with `roots()`, off the event loop; it renders `Entry.name` as text, passes
  back only typed text or an `Entry.path`, and runs Add on `expand`'s paths; Task 10's Windows
  job runs this task's Windows-only tests, and its Linux job the undecodable-name one; Task 11
  documents what the browser shows and hides; Phase 4's Pages editor can sort a picked folder
  with `naming.episode_key` (pure). The docs this task made untrue: spec §6.5 doesn't yet say
  links are never followed: add "Links are never listed or followed, and every check runs on
  the names the disk returns; a user's `Library` and `AppData` stay hidden on every disk
  (Phase 3 plan, Task 1)." after its in-app file browser bullet. Its four Minor findings are on
  the Phase-end list already, as planning rows. Then the close, its own commit, holding this plan
  with this task's boxes ticked and **Now** set to `Task 2: The Add screen, open.`, and the spec's
  S38 row with "Phase and task" set to `Phase 3, Tasks 1–2`; S38 stays `planned` (its Add half is
  Task 2's). The message, in `.git/CLOSE_MSG`:

```text
docs(plan): 🤖 close Task 1: The in-app file browser

Drift: none
Rulings: none
Phase-end: none
Forward: none
Tier: 1
Rounds: none
Findings: none

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md Task 1
Co-Authored-By: <the model's own line>
```

  `git add docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md
  docs/superpowers/specs/2026-10-14-vid2sub-design.md`, `git commit -F .git/CLOSE_MSG`.

***

### Task 2: The Add screen

**Tier:** 2 · **Scenarios:** S38, S39

**Files:**
- Create: `frontend/src/components/AddPage.tsx`, `frontend/src/lib/browse.ts`,
  `tests/e2e/fake_youtube.py`
- Modify: `src/vid2sub/jobs.py` (`submit(…, runner=)`), `src/vid2sub/web/episode.py`
  (`AddError`), `src/vid2sub/web/runtime.py` (the browser's places, `roots`, `listing`, `expand`,
  `add`, `job_guard`), `src/vid2sub/web/views.py` (`browse_view`, `places_view`,
  `browse_failed`; a YouTube job's name), `src/vid2sub/web/server.py` (`browse` and `add`),
  `src/vid2sub/web/demo.py` (its one place and its guard), `frontend/src/types.ts`,
  `frontend/src/App.tsx`, `tests/e2e/conftest.py` (`command=`)
- Test: `tests/test_jobs.py`, `tests/test_web_add.py`, `frontend/src/lib/browse.test.ts`,
  `tests/e2e/test_add.py`

**Interfaces:**
- Consumes: Task 1's `web.browse` (`roots`, `listing`, `expand`, `Entry`, `Listing`,
  `BrowseError`); M1's `media.youtube` (`is_url`, `video_id`, `canonical_url`, `NotYouTube`,
  and `download(…, runner=)`, the seam the browser test fakes yt-dlp through); Phase 2 Task 19's
  `runtime.job_runner(ctx, session)`, `Runtime.job_context` and `Runtime.session`, and its
  `Queue.on_change` listeners, which already refresh every tab's `jobs` output.
- Produces:
  - `jobs.Queue.submit(self, inputs: Sequence[str], *, runner: Runner | None = None)
    -> list[str]`: a job submitted with `runner` is run by it, else by the queue's own; the
    runner is kept while the job waits or runs, and dropped once it ends or is cancelled. (Moved
    here from Task 3, whose Start uses it too: Add's YouTube link that keeps its video needs a
    runner of its own.)
  - `web.episode.AddError(Exception)`: a folder the browser won't list, or something Add won't
    take; fit to show, naming no path. Pure, so the server catches it in Pages too.
  - `web.runtime.Runtime`, new fields `browse_home: Path | None = None` (the browser's home;
    None is yours), `browse_roots: tuple[Entry, ...] | None = None` (None: `browse.roots`'s
    home and mounted volumes) and `job_guard: Callable[[Runner], Runner] | None = None` (wraps a
    job's own runner as the queue's own is wrapped: the demo's `only_inside`), and methods, each
    blocking on the disk, so called through `runtime.blocking`:
    - `roots() -> tuple[Entry, ...]` (the places: `browse_roots`, else `browse.roots`);
      `listing(path: str) -> Listing` (`browse.listing` with `roots=browse_roots`, so outside
      the demo it looks only at the root the path is in; `AddError` for a `BrowseError`);
    - `expand(paths: Sequence[str], links: Sequence[str]) -> list[str]`: `browse.expand(paths)`,
      then each link as `youtube.canonical_url(video_id(link))`, each once (`AddError` for the
      first that can't be added);
    - `add(inputs: Sequence[str], *, keep_video: bool) -> list[str]`: queues them, with the
      queue's own runner, or with `keep_video` a runner of their own (`job_runner` on the job
      context with `keep_video=True`, through `job_guard`). Task 4 replaces this hand-off with
      Review.
  - `web.views`: `browse_view(listing) -> {"path", "parent", "entries": [{"name", "path",
    "kind"}], "truncated", "error": None}`, `places_view(roots)` (the same, `path` and `parent`
    None) and `browse_failed(reason)` (`path` and `parent` None, `entries` [], `error` the
    reason). `jobs_view` names a YouTube job `YouTube video <id>`, never by its title, and its
    `can_open` is false (the editor opens a file by its path, which the job doesn't report).
  - The server (local only: `capabilities.generate`; Pages ignores both inputs):
    - input `browse`: `{"path": str | null, "n": int}` (null: the places) → message
      `browse_result`: `{"n": int | null, "path": str | null, "parent": str | null,
      "entries": [{"name": str, "path": str, "kind": "folder" | "video" | "subtitle"}],
      "truncated": bool, "error": str | null}`. One listing runs at a time per tab, in a task of
      its own through `runtime.blocking`; a newer request waits in its place, and an older
      waiting one is dropped, unanswered.
    - input `add`: `{"paths": [str], "links": [str], "keep_video": bool, "n": int}` (at most
      `MAX_JOBS` paths and `MAX_LINKS = 20` links, each one line of at most `MAX_PATH`
      characters) → message `add_result`: `{"n": int | null, "added": int, "error": str |
      null}`, after `rt.expand` (off the loop) and `rt.add`. Errors: `ADD_WHAT`, `NO_VIDEOS`,
      `TOO_MANY` (more than `MAX_JOBS` videos), `STOPPING`, or the runtime's `AddError`; none
      echoes what was sent.
  - The page: an **Add** screen beside Editor and Jobs (`nav-add`), shown only where
    `capabilities.generate` is true. `AddPage({browse: BrowseState, onBrowse(path: string |
    null), onAdd(request: AddRequest), adding: boolean, error: string | null})`;
    `lib/browse.ts`: `BrowseState`, `NOT_ASKED`, `asked(state, n, path)`, `answered(state,
    result)` (only the last request's answer; a failure shows no entries), `AddRequest`,
    `addRequest(picked, typed, link, keepVideo)` and `canAdd(request)`. Test ids:
    `add-page`, `browse-places`, `browse-up`, `browse-path`, `browse-pick-here`,
    `browse-waiting`, `browse-error`, `browse-list`, `browse-entry` (`data-kind`),
    `browse-pick`, `browse-open`, `browse-name`, `add-paths`, `add-link`, `add-keep-video`,
    `add-start`, `add-picked`, `add-error`. A finished Add opens the Jobs page.
  - `tests/e2e/conftest.py`: `start_server(…, command=None)` and `launch(…, command=None)`
    run vid2sub through a launcher instead of `python -m vid2sub`; `tests/e2e/fake_youtube.py
    CLIP serve …` is one, answering yt-dlp with CLIP.
  - Decided here (proposed): **the demo's file browser has one place, the demo's own folder,**
    which is also its home, rather than Add being hidden there. It needs no new capability
    (Decision 23), and the demo shows Add working; every job's runner in the demo, a YouTube
    link's own included, runs only its clip.
  - What Task 4 calls: the `add` input's hand-off (`rt.add`) becomes `review.prepare` and
    `sample`, and a finished Add opens Review instead of Jobs.

- [ ] **Step 0: Record the base:** `git rev-parse HEAD > .git/TASK_BASE`.
- [ ] **Step 1: Write the failing test.** Append to `tests/test_jobs.py`, after two blank lines:

```python
# Phase 3, Task 2: a job may bring its own runner (Add's link that keeps its video; Review's Start)


def test_a_job_may_bring_its_own_runner_and_the_rest_use_the_queues(runner):
    ran = []

    def own(source, event, cancelled):
        ran.append(source)
        return InputResult(input=source, status="done")

    q = jobs.Queue(runner)
    (mine,) = q.submit(["a.mkv"], runner=own)
    (theirs,) = q.submit(["b.mkv"])
    until(lambda: state(q, mine) == "done" and state(q, theirs) == "running")
    runner.gate("b.mkv").set()
    until(lambda: state(q, theirs) == "done")
    q.close()
    assert ran == ["a.mkv"] and runner.started == ["b.mkv"]
    assert q._runners == {}  # nothing kept once a job has run
```

- [ ] **Step 2: Run it; watch it fail.** `uv run pytest tests/test_jobs.py -q`. Expected:
  `E       TypeError: Queue.submit() got an unexpected keyword argument 'runner'` and
  `1 failed, 13 passed`.
- [ ] **Step 3: Write the code.** Replace `src/vid2sub/jobs.py` with:

```python
"""The job queue: one worker thread runs submitted inputs one at a time (spec §17.1, S36).

Jobs live in the engine's memory, owned by the engine rather than a browser tab, so closing a tab
cancels nothing and reopening shows the progress; when the engine exits the list is gone, and
finished results are already on disk (Dan, 2026-10-14). One worker runs one job at a time,
because the Spark's whisper serves one request at a time anyway. Cancel takes a queued job out of
the queue, or asks the running one to stop at its next check, between chunks or translation
batches (`pipeline.Cancelled`; the Phase 2 plan's Decision 7), and says it is `stopping` until
then, so every tab can tell. Listeners are called after every
change of state, stage or progress, on the thread that made it (the worker, or the caller of
`submit`, `cancel` or `close`); one that raises is logged and the queue carries on, and one
can stop listening (a tab that closed). A job may bring its own runner (Add's YouTube link that
keeps its video, Review's Start with each file's own options: the Phase 3 plan, Tasks 2 and 3);
others use the queue's. The log names jobs by id and errors by kind, never an input, a title or a
path (spec §6.8).
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
    stopping: bool = False  # the running job was asked to stop: before its next chunk or batch


class Queue:
    def __init__(self, runner: Runner):
        self._runner = runner
        self._runners: dict[str, Runner] = {}  # a job's own runner, while it waits or runs
        self._lock = threading.Condition()
        self._jobs: dict[str, JobView] = {}  # in the order they were submitted
        self._waiting: deque[str] = deque()
        self._running: str | None = None
        self._stop = threading.Event()  # set: the running job should stop
        self._listeners: list[Callable[[], None]] = []
        self._closed = False
        self._worker = threading.Thread(target=self._work, name="vid2sub-jobs", daemon=True)
        self._worker.start()

    def submit(self, inputs: Sequence[str], *, runner: Runner | None = None) -> list[str]:
        """Queues each input, run by `runner` when given, else by the queue's own."""
        with self._lock:
            if self._closed:
                raise RuntimeError("the job queue is closed")
            ids = []
            for source in inputs:
                job_id = self._new_id()
                self._jobs[job_id] = JobView(job_id, source, "queued")
                if runner is not None:
                    self._runners[job_id] = runner
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
            if job.state == "running":  # it stops at its next check; every tab can say so
                self._stop.set()
                self._set(job_id, stopping=True)
            else:
                self._waiting.remove(job_id)
                self._runners.pop(job_id, None)
                self._set(job_id, state="cancelled")
        self._changed()
        return True

    def jobs(self) -> list[JobView]:
        with self._lock:
            return list(self._jobs.values())

    def on_change(self, fn: Callable[[], None]) -> Callable[[], None]:
        """Calls `fn` after every change; returns what stops it (a tab that closed)."""
        with self._lock:
            self._listeners.append(fn)

        def stop() -> None:
            with self._lock:
                if fn in self._listeners:
                    self._listeners.remove(fn)

        return stop

    def close(self, timeout: float = 5.0) -> None:
        """Cancels every queued job and the running one, then waits up to `timeout` seconds
        for the worker to stop."""
        with self._lock:
            self._closed = True
            while self._waiting:
                job_id = self._waiting.popleft()
                self._runners.pop(job_id, None)
                self._set(job_id, state="cancelled")
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
                runner = self._runners.get(job_id, self._runner)
            self._changed()
            final = self._run(job_id, source, runner)
            with self._lock:
                self._set(job_id, stopping=False, **final)
                self._runners.pop(job_id, None)
                self._running = None
            self._changed()

    def _run(self, job_id: str, source: str, runner: Runner) -> dict[str, Any]:
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
            result = runner(source, event, self._stop.is_set)
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

- [ ] **Step 4: Run the checks; they pass.** `uv run pytest tests/test_jobs.py -q` five times
  (`14 passed` each: the queue tests use threads), then the guard checks, then `make check`.
  **Guard checks**, each reverted and restored, each with `uv run pytest tests/test_jobs.py -q
  -k own_runner`: in `_work`, replace `runner = self._runners.get(job_id, self._runner)` with
  `runner = self._runner` (`FAILED …test_a_job_may_bring_its_own_runner_and_the_rest_use_the_queues`);
  delete the `self._runners.pop(job_id, None)` just above `self._running = None` in `_work`
  (the same test fails: the runner is kept after its job ran). `make check`. Expected:
  `1109 passed, 7 skipped, 36 deselected` twice, `Test Files  19 passed (19)` and
  `Tests  88 passed (88)`, `All checks passed!` and `no leaks found`.
- [ ] **Step 5: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(jobs): 🤖 a job may bring its own runner, which the queue keeps only while the job waits or runs

jobs.Queue.submit(inputs, runner=) queues each input to be run by
`runner`, else by the queue's own, as before. Add needs it now (Phase 3
Task 2: a YouTube link with keep video runs with keep_video set, while
everything else runs as the queue's own runner runs it), and Review's
Start later (Task 3: each file with its own options). The runner is
dropped once its job ends, is cancelled while queued, or the queue
closes; Phase 2's callers and its stopping flag are unchanged.

The new test failed first with: TypeError: Queue.submit() got an
unexpected keyword argument 'runner'. Guard checks, each reverted and
restored: running every job with the queue's own runner, and keeping a
runner after its job ran, each make it fail. The queue tests passed five
runs in a row.

Docs read: none beyond the code (Phase 2's jobs.Queue, with Task 19's
stopping and stoppable listeners).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md Task 2
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/jobs.py tests/test_jobs.py`, `git commit -F .git/COMMIT_MSG`, then
  `git log -1 --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 6: Write the failing tests,** `tests/test_web_add.py`:

```python
"""The Add screen's server (spec §19.2, §6.5, §8.1; S38, S39; Review Focus 1): the file browser's
places and folders, off the event loop, so a sleeping share keeps only its own tab waiting and a
listing that fails shows nothing stale; Add takes picked and typed paths through the browser's
checks and YouTube links as their canonical URLs, and queues them, a link keeping its whole video
when asked; the demo browses only its own folder and runs only its clip; Pages has no Add."""

import dataclasses
import json
import threading
import time

import pytest
from starlette.testclient import TestClient
from test_web_server import (  # noqa: F401 - fresh_reactive_lock is autouse
    BASE,
    JSON,
    PAGE,
    PORT,
    TOKEN,
    Tab,
    fresh_reactive_lock,
    tab,
)
from test_web_settings import Browser

from vid2sub import pipeline
from vid2sub.cache import Cache
from vid2sub.config import Config
from vid2sub.engines.clients import KeyRing
from vid2sub.jobs import JobView
from vid2sub.media.tools import Tools
from vid2sub.pipeline import InputResult
from vid2sub.web import browse, demo, runtime, server, views
from vid2sub.web.app import create_app
from vid2sub.web.browse import BrowseError, Entry
from vid2sub.web.episode import AddError

LINK = "https://youtu.be/dQw4w9WgXcQ?t=42"
CANONICAL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def touch(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")
    return path


@pytest.fixture
def places(tmp_path):
    """A home with a season and a film in it, and a mounted volume."""
    home, volume = tmp_path / "home", tmp_path / "Volumes" / "Media"
    season = home / "TV" / "Show"
    for name in ("Show S01E02.mkv", "Show S01E01.mkv", "Show S01E01.en.srt", ".Show S01E03.mkv",
                 "notes.txt"):
        touch(season / name)
    (season / "Extras").mkdir()
    touch(home / "Film.mp4")
    (home / ".ssh").mkdir()
    volume.mkdir(parents=True)
    return home, volume, season


@pytest.fixture
def ran(monkeypatch):
    """What each job ran: its source and whether it keeps the video (pipeline.run_one faked)."""
    seen: list[tuple[str, bool]] = []

    def run_one(source, ctx):
        seen.append((source, ctx.options.keep_video))
        return InputResult(input=source, status="done")

    monkeypatch.setattr(pipeline, "run_one", run_one)
    return seen


@pytest.fixture
def rt(tmp_path, places, ran):
    home, volume, _ = places
    made = runtime.build(Config(), tools=Tools(None, None, None), keys=KeyRing(environ={}),
                         cache=Cache(tmp_path / "cache", max_bytes=0))
    made = dataclasses.replace(made, browse_home=home, browse_roots=(
        Entry("Home", str(home), "folder"), Entry("Media", str(volume), "folder")))
    runtime.configure(made)
    yield made
    runtime.configure(None)
    made.queue.close()


def client_for(rt):
    c = TestClient(create_app(rt, token=TOKEN, port=PORT, shiny_app=server.app), base_url=BASE)
    c.__enter__()
    assert c.post("/auth", content=json.dumps({"token": TOKEN}),
                  headers={**JSON, **PAGE}).status_code == 204
    return c


@pytest.fixture
def client(rt):
    c = client_for(rt)
    yield c
    c.__exit__(None, None, None)


def said(t: Tab, kind: str) -> list[dict]:
    """The tab's `kind` messages, in the order they came."""
    return [m["custom"]["shinyReactMessage"]["data"] for m in t.messages
            if m.get("custom", {}).get("shinyReactMessage", {}).get("id") == kind]


def answer(t: Tab, kind: str, n: int) -> dict:
    return t.until(lambda t: next((d for d in said(t, kind) if d["n"] == n), None))


# ---- browsing ----------------------------------------------------------------------------------


def test_browse_starts_at_the_places_and_lists_only_folders_videos_and_subtitles(client, places):
    home, volume, season = places
    with tab(client, set()) as t:
        t.set(browse={"path": None, "n": 1})
        assert answer(t, "browse_result", 1) == {
            "n": 1, "path": None, "parent": None, "truncated": False, "error": None,
            "entries": [{"name": "Home", "path": str(home), "kind": "folder"},
                        {"name": "Media", "path": str(volume), "kind": "folder"}]}
        t.set(browse={"path": str(season), "n": 2})
        found = answer(t, "browse_result", 2)
    assert (found["path"], found["parent"], found["error"]) == (str(season), str(home / "TV"),
                                                                None)
    assert [(e["name"], e["kind"]) for e in found["entries"]] == [
        ("Extras", "folder"), ("Show S01E01.en.srt", "subtitle"), ("Show S01E01.mkv", "video"),
        ("Show S01E02.mkv", "video")]


def test_a_folder_the_browser_wont_list_says_why_and_names_nothing(client, places):
    home, _, _ = places
    results = []
    with tab(client, set()) as t:  # one at a time: a request sent while one runs may be dropped
        for n, path in enumerate([str(home / ".ssh"), "relative/secret-folder", "/" + "a" * 5000,
                                  7, str(home.parent / "elsewhere-secret")], 1):
            t.set(browse={"path": path, "n": n})
            results.append(answer(t, "browse_result", n))
    assert all(r["entries"] == [] and r["error"] for r in results)
    assert "secret" not in json.dumps(results) and str(home) not in json.dumps(results)


def test_a_sleeping_share_keeps_only_its_tab_waiting_and_a_listing_that_fails_shows_nothing(
        client, places, monkeypatch):
    home, _, season = places
    asleep, woke = threading.Event(), threading.Event()
    real = browse.listing
    behind: list[bool] = []  # for each of this tab's later listings: did it wait for the share?

    def listing(path, **kwargs):
        if path.endswith("NAS"):
            asleep.set()
            assert woke.wait(20)
            raise BrowseError("couldn't read this folder (Operation timed out)")
        if path in (str(home), str(season)):
            behind.append(woke.is_set())
        return real(path, **kwargs)

    monkeypatch.setattr(browse, "listing", listing)
    with tab(client, set()) as a, tab(client, set()) as b:
        a.set(browse={"path": str(home / "NAS"), "n": 1})
        assert asleep.wait(10)
        b.set(browse={"path": str(home / "TV"), "n": 1})  # another tab, answered meanwhile
        assert answer(b, "browse_result", 1)["path"] == str(home / "TV")
        a.set(browse={"path": str(home), "n": 2})  # these wait behind the share: one at a time
        a.set(browse={"path": str(season), "n": 3})
        time.sleep(0.5)  # time for them to reach the server; the right code runs neither yet
        assert said(a, "browse_result") == []
        woke.set()
        failed = answer(a, "browse_result", 1)
        latest = answer(a, "browse_result", 3)
    assert failed == {"n": 1, "path": None, "parent": None, "entries": [], "truncated": False,
                      "error": "couldn't read this folder (Operation timed out)"}
    assert latest["path"] == str(season) and said(a, "browse_result")[-1] is latest
    assert behind and all(behind)  # none ran beside the sleeping one; n 2 may have been dropped


# ---- adding ------------------------------------------------------------------------------------


def test_add_queues_each_video_once_in_episode_order_and_a_link_as_its_canonical_url(
        client, rt, places, ran):
    home, _, season = places
    with tab(client, {"jobs"}) as t:
        t.set(add={"n": 1, "paths": [str(season), str(home / "Film.mp4"),
                                     str(season / "Show S01E01.mkv")],
                   "links": [LINK], "keep_video": False})
        assert answer(t, "add_result", 1) == {"n": 1, "added": 4, "error": None}
        t.until(lambda t: len(ran) == 4)
        t.set(add={"n": 2, "paths": [], "links": [LINK], "keep_video": True})
        assert answer(t, "add_result", 2) == {"n": 2, "added": 1, "error": None}
        t.until(lambda t: len(ran) == 5)
    assert ran == [(str(season / "Show S01E01.mkv"), False),
                   (str(season / "Show S01E02.mkv"), False), (str(home / "Film.mp4"), False),
                   (CANONICAL, False), (CANONICAL, True)]
    assert [j.input for j in rt.queue.jobs()] == [s for s, _ in ran]


@pytest.mark.parametrize("request_", [
    {"paths": ["relative/secret.mkv"], "links": [], "keep_video": False},
    {"paths": ["~/.ssh/secret.mkv"], "links": [], "keep_video": False},
    {"paths": ["~/TV/Show/notes.txt"], "links": [], "keep_video": False},
    {"paths": [], "links": ["https://vimeo.com/secret"], "keep_video": False},
    {"paths": [], "links": ["https://youtube.com/watch?v=secret"], "keep_video": False},
    {"paths": ["~/TV/Show/Extras"], "links": [], "keep_video": False},
    {"paths": [], "links": [], "keep_video": False},
    {"paths": "~/TV/Show", "links": [], "keep_video": False},
    {"paths": ["~/TV/Show"], "links": [], "keep_video": "yes"},
    {"paths": ["~/TV/Show\n/secret"], "links": [], "keep_video": False},
])
def test_anything_add_cannot_take_is_refused_whole_naming_nothing(client, rt, request_):
    with tab(client, set()) as t:
        t.set(add={"n": 1, **request_})
        result = answer(t, "add_result", 1)
    assert result["added"] == 0 and result["error"]
    assert "secret" not in result["error"] and rt.queue.jobs() == []


def test_the_pages_editor_has_no_add(rt):
    pages = dataclasses.replace(rt, backend=Browser(rt.backend))
    runtime.configure(pages)
    c = client_for(pages)
    try:
        with tab(c, set()) as t:
            t.set(browse={"path": None, "n": 1})
            t.set(add={"n": 2, "paths": [str(rt.browse_home)], "links": [], "keep_video": False})
            t.set(open={"path": "/nowhere/x.mkv", "n": 3})  # something it does answer
            t.until(lambda t: t.notices())
            assert said(t, "browse_result") == [] and said(t, "add_result") == []
    finally:
        c.__exit__(None, None, None)
    assert rt.queue.jobs() == []


def test_a_youtube_job_is_named_by_its_video_and_never_opens_by_its_link():
    done = InputResult(input=CANONICAL, status="done", title="A talk",
                       written=["A talk [dQw4w9WgXcQ].en.srt"])
    (job,) = views.jobs_view([JobView("j00000001", CANONICAL, "done", "write", None, done)])["jobs"]
    assert (job["name"], job["path"], job["can_open"]) == ("YouTube video dQw4w9WgXcQ",
                                                           CANONICAL, False)
    assert job["written"] == ["A talk [dQw4w9WgXcQ].en.srt"]


# ---- the runtime -------------------------------------------------------------------------------


def test_the_runtime_turns_the_browsers_refusals_into_add_errors(rt, places):
    home, _, season = places
    with pytest.raises(AddError, match="hidden"):
        rt.listing(str(home / ".ssh"))
    with pytest.raises(AddError, match="isn't a video"):
        rt.expand([str(season / "notes.txt")], [])
    with pytest.raises(AddError, match="one YouTube video"):
        rt.expand([], ["https://www.youtube.com/watch?v=short"])
    assert rt.expand([str(season / "Show S01E01.mkv")], [LINK, CANONICAL]) == [
        str(season / "Show S01E01.mkv"), CANONICAL]


@pytest.mark.media
def test_the_demo_browses_only_its_own_folder_and_a_link_it_adds_is_refused(tmp_path):
    tools = Tools.find()
    copy = demo.prepare(tools)
    rt = demo.runtime_for(copy, tools)
    try:
        assert rt.roots() == (Entry("Demo", str(copy), "folder"),)
        assert [e.name for e in rt.listing(str(copy)).entries if e.kind == "video"] == ["jfk.mp4"]
        with pytest.raises(AddError):
            rt.listing(str(tmp_path))  # anywhere else, home included, is no place of the demo's
        assert rt.expand(["~"], []) == [str(copy / demo.VIDEO)]
        rt.add([CANONICAL], keep_video=True)  # a runner of its own, which the guard wraps
        deadline = time.monotonic() + 30
        while (refused := rt.queue.jobs()[0]).state not in ("done", "failed"):
            assert time.monotonic() < deadline, "timed out waiting"
            time.sleep(0.01)
    finally:
        rt.queue.close()
    assert refused.state == "failed" and refused.result.reason == demo.DEMO_ONLY
```

- [ ] **Step 7: Run them; watch them fail.** `uv run pytest tests/test_web_add.py -q`. Expected:
  `E   ImportError: cannot import name 'AddError' from 'vid2sub.web.episode'
  (…/src/vid2sub/web/episode.py)` and `1 error`.
- [ ] **Step 8: Write the code.** In `src/vid2sub/web/episode.py`, above `@dataclass(frozen=True)`
  / `class SaveResult:`, add:

```python
class AddError(Exception):
    """A folder the file browser won't list, or something Add won't take: the reason is fit to
    show and names no path (spec §6.5, §6.8). The local runtime makes it from the browser's own
    `BrowseError` and a link that names no YouTube video, which the server can't import in
    Pages (Phase 3 Task 2)."""


```

  In `src/vid2sub/web/runtime.py`, in the module docstring, replace

```python
(§8.9). Nothing here presets `allow_cloud` (§7.2): a job never uses a cloud model in Phase 2.

The server runs in Pages too (spec §3.3, §21), so this module imports nothing the Pages bundle
lacks at its top: `build()` imports the local parts (the backend, the queue, ffmpeg's tools, the
cache, the network client) when it runs, and the server reaches local-only work through the
`Runtime` (`reachable`, `media_for`, `retranslate`, `endpoint_models`). Every call that blocks goes through
```

  with

```python
(§8.9). Nothing here presets `allow_cloud` (§7.2): a job never uses a cloud model in Phase 2.
The Add screen's file browser (Phase 3 Task 2, spec §6.5) lists your home and mounted volumes
through `roots`, `listing` and `expand`, which turn the browser's refusals into the pure
`AddError`; the demo's runtime gives it only the demo's folder (`browse_roots`, `browse_home`),
and its `job_guard` wraps every job's runner, so a job that brings its own runner (a YouTube link
that keeps its video) still runs only the demo's clip.

The server runs in Pages too (spec §3.3, §21), so this module imports nothing the Pages bundle
lacks at its top: `build()` imports the local parts (the backend, the queue, ffmpeg's tools, the
cache, the network client) when it runs, and the server reaches local-only work through the
`Runtime` (`reachable`, `media_for`, `retranslate`, `endpoint_models`, `roots`, `listing`,
`expand`, `add`). Every call that blocks goes through
```

  Below `from dataclasses import dataclass, field`, add `from pathlib import Path`; below
  `    from vid2sub.web.backend import LocalBackend` (in the `TYPE_CHECKING` block), add
  `    from vid2sub.web.browse import Entry, Listing`; below
  `    job_context: RunContext | None = None  # what each job's run_one runs on (job_runner)`, add:

```python
    browse_home: Path | None = None  # the file browser's home: None is yours (spec §6.5)
    browse_roots: tuple[Entry, ...] | None = None  # None: your home and mounted volumes
    job_guard: Callable[[Runner], Runner] | None = None  # wraps a job's own runner (the demo's)
```

  and above `    def media_for(self, ep: Episode, *, audio_only: bool = False) -> Media:`, add:

```python
    def roots(self) -> tuple[Entry, ...]:
        """The file browser's places (spec §6.5): your home and each mounted volume, or only the
        demo's folder in the demo. Blocks on the disk (a sleeping share): call it through
        `blocking`."""
        from vid2sub.web import browse

        if self.browse_roots is not None:
            return self.browse_roots
        return browse.roots(home=self.browse_home)

    def listing(self, path: str) -> Listing:
        """One folder's folders, videos and subtitle files (`browse.listing`), or `AddError`,
        whose reason names no path, for a folder the browser won't list. Outside the demo the
        browser finds the one root the path is in, so a dead mount elsewhere holds nothing up.
        Blocks on the disk: call it through `blocking`."""
        from vid2sub.web import browse
        from vid2sub.web.episode import AddError

        try:
            return browse.listing(path, roots=self.browse_roots, home=self.browse_home)
        except browse.BrowseError as err:
            raise AddError(str(err)) from None

    def expand(self, paths: Sequence[str], links: Sequence[str]) -> list[str]:
        """What Add takes (spec §19.2): each path the person typed or picked, through
        `browse.expand` (a video once, a folder's own videos in episode order, nothing the
        browser wouldn't show), then each YouTube link as its canonical URL, which names the
        one video and nothing else (§6.7). `AddError`, naming nothing, for the first that can't
        be added. Blocks on the disk: call it through `blocking`."""
        from vid2sub.media import youtube
        from vid2sub.web import browse
        from vid2sub.web.episode import AddError

        try:
            found = browse.expand(paths, roots=self.browse_roots, home=self.browse_home)
        except browse.BrowseError as err:
            raise AddError(str(err)) from None
        for link in links:
            try:
                url = youtube.canonical_url(youtube.video_id(link))
            except youtube.NotYouTube as err:
                raise AddError(str(err)) from None
            if url not in found:
                found.append(url)
        return found

    def add(self, inputs: Sequence[str], *, keep_video: bool) -> list[str]:
        """Queues what Add took, each as `vid2sub run` would run it, with the session's targets
        and formats as it starts (`job_runner`); a YouTube link keeps its whole video when
        **keep video** is ticked (spec §8.1), through a runner of its own, which `job_guard`
        wraps as the queue's own is wrapped (the demo's: only its clip). The job ids;
        RuntimeError once the queue is closed."""
        runner = None
        if keep_video and self.job_context is not None:
            ctx = self.job_context
            runner = job_runner(dataclasses.replace(
                ctx, options=dataclasses.replace(ctx.options, keep_video=True)), self.session)
            if self.job_guard is not None:
                runner = self.job_guard(runner)
        return self.queue.submit(inputs, runner=runner)

```

  In `src/vid2sub/web/views.py`, in the module docstring, replace
  `a cloud endpoint is never contacted (as `vid2sub doctor` decides). The server runs in Pages too`
  with

```python
a cloud endpoint is never contacted (as `vid2sub doctor` decides). The Add screen's file browser
shows a folder's entries by bare name and full path (Phase 3 Task 2, §6.5). The server runs in
Pages too
```

  Below `    from vid2sub.jobs import JobView` (in the `TYPE_CHECKING` block), add
  `    from vid2sub.web.browse import Entry, Listing`. In `jobs_view`, replace

```python
    notes; `stopping` while a cancelled job finishes its chunk (Decision 7). A job opens in the
    editor once it is done and its subtitles are there."""
    out = []
    for j in jobs:
        r = j.result
        finished = r is not None and r.status in ("done", "skipped")
        out.append({"id": j.id, "name": PurePath(j.input).name or j.input, "path": j.input,
```

  with

```python
    notes; `stopping` while a cancelled job finishes its chunk (Decision 7). A job opens in the
    editor once it is done and its subtitles are there. A YouTube link (Phase 3's Add) is named
    by its video's id, never a title (§6.8), and doesn't open by its link."""
    from vid2sub.media import youtube  # here: the Pages editor has no jobs, and no yt-dlp

    out = []
    for j in jobs:
        r = j.result
        finished = r is not None and r.status in ("done", "skipped")
        link = youtube.is_url(j.input)
        out.append({"id": j.id, "name": _link_name(j.input) if link else
                    PurePath(j.input).name or j.input, "path": j.input,
```

  replace `                    "can_open": j.state == "done" and finished})` with
  `                    "can_open": j.state == "done" and finished and not link})`, and above
  `def capabilities_view(caps: Capabilities) -> dict[str, Any]:`, add:

```python
def _link_name(url: str) -> str:
    from vid2sub.media import youtube

    try:
        return f"YouTube video {youtube.video_id(url)}"
    except youtube.NotYouTube:
        return "YouTube link"


def browse_view(listing: Listing) -> dict[str, Any]:
    """A folder in the Add screen's file browser (spec §6.5, S38): each entry's bare name, which
    the page shows as plain text, its kind, and its full path, which is all the page sends back
    to list or add (§6.5: a path from a listing, or one the person typed); in `browse.listing`'s
    order, folders first, then videos and subtitles by `SxxEyy`. `path` is spelled as on the
    disk; `parent` is None at a root or a share's top, where Up goes back to the places."""
    return {"path": listing.path, "parent": listing.parent,
            "entries": [{"name": e.name, "path": e.path, "kind": e.kind}
                        for e in listing.entries],
            "truncated": listing.truncated, "error": None}


def places_view(roots: Sequence[Entry]) -> dict[str, Any]:
    """The file browser's places, where it starts: your home, then each mounted volume (`path`
    None)."""
    return {"path": None, "parent": None,
            "entries": [{"name": e.name, "path": e.path, "kind": e.kind} for e in roots],
            "truncated": False, "error": None}


def browse_failed(reason: str) -> dict[str, Any]:
    """A folder that couldn't be listed: its reason, which names no path (§6.8), and no
    entries, so the page shows nothing stale (Review Focus 1)."""
    return {"path": None, "parent": None, "entries": [], "truncated": False, "error": reason}


```

  In `src/vid2sub/web/server.py`, in the module docstring, below
  `listeners on the worker thread, so each tab's hands the change to its own loop.`, add (after
  a blank line):

```python
The Add screen (§19.2, §6.5; S38, S39; Phase 3 Task 2), the local engine's alone: `browse` asks
for the file browser's places or one folder, answered by the `browse_result` message, and `add`
takes the entries picked, the paths typed and a YouTube link with **keep video**, which the
runtime checks as the browser checks a folder and queues (`add_result`). Both wait on the disk, a
sleeping network share for seconds, so each runs in a task of the tab's own through
`runtime.blocking`; a tab lists one folder at a time, and only the newest request waits behind it
(Review Focus 1).
```

  Replace
  `from vid2sub.web.episode import Episode, OpenError, RetranslateError, SaveError, SaveResult`
  with

```python
from vid2sub.web.episode import (
    AddError,
    Episode,
    OpenError,
    RetranslateError,
    SaveError,
    SaveResult,
)
```

  below `STOPPING = "vid2sub is stopping: nothing was queued"`, add:

```python
MAX_LINKS = 20  # YouTube links one Add may take
TYPE_A_FOLDER = "type the folder's full path"
ADD_WHAT = ("pick or type the videos and folders to add, or paste a YouTube link: nothing was "
            "added")
NO_VIDEOS = "there are no videos there: nothing was added"
TOO_MANY = f"that's more than {MAX_JOBS} videos: add fewer at once"
```

  above `def _cue_ids(ids: object) -> bool:`, add:

```python
def _typed(values: object, most: int) -> bool:
    """A list of at most `most` texts, each one line of 1 to MAX_PATH characters: what Add
    takes, before the runtime checks each as the file browser does."""
    return (isinstance(values, list) and len(values) <= most
            and all(isinstance(v, str) and 0 < len(v) <= MAX_PATH
                    and not any(ch in v for ch in "\r\n\0") for v in values))


```

  and in `server`, above `    @reactive_output` / `    def episode():`, add:

```python
    # Add (spec §19.2, §6.5; S38, S39), the local engine's alone: Pages has no file browser.
    # Browsing and adding wait on the disk, a sleeping network share for seconds, so each runs in
    # a task of this tab's own, through `runtime.blocking`, holding no reactive lock: the page
    # says it's waiting, and other tabs, and this one's other work, carry on (Review Focus 1). One
    # listing runs at a time per tab; a newer request waits in its place and older waiting ones
    # are dropped, since the page shows only the folder it asked for last, so a sleeping share
    # never holds more than one of the blocking pool's threads per tab. Only what the person
    # typed, or a path from a listing this engine sent, comes back (§6.5); the runtime checks
    # each as the browser does, and its reasons name no path (§6.8).
    browsing: dict[str, Any] = {"task": None, "next": None}
    adding: set[asyncio.Task] = set()

    @reactive.effect
    @reactive.event(input.browse)
    def _browse() -> None:
        request = as_json(input.browse())
        if not local or not isinstance(request, dict):
            return
        browsing["next"] = request
        if browsing["task"] is None or browsing["task"].done():
            browsing["task"] = asyncio.create_task(browse_latest())

    async def browse_latest() -> None:
        while browsing["next"] is not None:
            request, browsing["next"] = browsing["next"], None
            try:
                await browse_one(request)
            except Exception as err:  # noqa: BLE001 - one listing failing must not stop the next
                log.error("a listing failed: %s", type(err).__name__)

    async def browse_one(request: dict) -> None:
        path, n = request.get("path"), request.get("n")
        n = n if type(n) is int else None
        if path is not None and not (isinstance(path, str) and 0 < len(path) <= MAX_PATH):
            view = views.browse_failed(TYPE_A_FOLDER)  # never echoes what was sent
        else:
            try:
                view = (views.places_view(await runtime.blocking(rt.roots)) if path is None
                        else views.browse_view(await runtime.blocking(rt.listing, path)))
            except AddError as err:
                view = views.browse_failed(str(err))
        await shinyreact.send_message(session, "browse_result", {"n": n, **view})

    @reactive.effect
    @reactive.event(input.add)
    def _add() -> None:
        request = as_json(input.add())
        if not local or not isinstance(request, dict):
            return
        task = asyncio.create_task(add_one(request))
        adding.add(task)  # kept until it ends: the loop holds only a weak reference
        task.add_done_callback(adding.discard)

    async def add_one(request: dict) -> None:
        try:
            await add_from(request)
        except Exception as err:  # noqa: BLE001 - one Add failing must not stop the session
            log.error("an add failed: %s", type(err).__name__)

    async def add_from(request: dict) -> None:
        n = request.get("n")
        n = n if type(n) is int else None
        paths, links, keep = request.get("paths"), request.get("links"), request.get("keep_video")
        added, error = 0, None
        if not (_typed(paths, MAX_JOBS) and _typed(links, MAX_LINKS) and isinstance(keep, bool)
                and (paths or links)):
            error = ADD_WHAT  # never echoes what was sent
        else:
            try:
                inputs = await runtime.blocking(rt.expand, paths, links)
            except AddError as err:
                error = str(err)
            else:
                if not inputs:
                    error = NO_VIDEOS
                elif len(inputs) > MAX_JOBS:
                    error = TOO_MANY
                else:
                    try:
                        added = len(rt.add(inputs, keep_video=keep))
                    except RuntimeError:  # closed: the engine is stopping
                        error = STOPPING
        await shinyreact.send_message(session, "add_result",
                                      {"n": n, "added": added, "error": error})

```

  In `src/vid2sub/web/demo.py`, in the module docstring, replace
  `episodes in its copy, and its runtime reads no vid2sub.toml and no key from the environment.`
  with

```python
episodes in its copy, and its runtime reads no vid2sub.toml and no key from the environment. Its
Add screen's file browser has one place, the demo's own folder, which is also its home, so
nothing of yours is listed, and every job's runner, a YouTube link's own included, runs only the
demo's clip (the Phase 3 plan, Task 2).
```

  below `from dataclasses import replace`, add `from functools import partial`; below
  `from vid2sub.web.backend import Episode, LocalBackend, OpenError`, add
  `from vid2sub.web.browse import Entry`; in `runtime_for`'s docstring, replace
  `    writes, it writes in the demo's folder."""` with
  `    writes, it writes in the demo's folder. Add browses only the copy (Phase 3 Task 2)."""`;
  and replace `    return replace(built, backend=backend)` with:

```python
    return replace(built, backend=backend, browse_home=copy,
                   browse_roots=(Entry("Demo", str(copy), "folder"),),
                   job_guard=partial(only_inside, copy))
```

- [ ] **Step 9: Run the checks; they pass.** `uv run pytest tests/test_web_add.py
  tests/test_pages_imports.py -q` first (`23 passed`; three times: the browsing test uses
  threads), then the guard checks, then `make check`. **Guard checks**, each reverted and
  restored: in `runtime_for`, replace `job_guard=partial(only_inside, copy))` with
  `job_guard=None)` (`uv run pytest tests/test_web_add.py -q -k demo`: the link's job fails
  with "deno isn't installed…" instead of the demo's refusal); delete
  `browse_roots=(Entry("Demo", str(copy), "folder"),),` (the same test fails: the demo lists
  your home and volumes); in `_browse`, replace
  `if browsing["task"] is None or browsing["task"].done():` with `if True:`
  (`uv run pytest tests/test_web_add.py -q -k sleeping`: a listing runs beside the sleeping
  one). `make check`. Expected: `1127 passed, 7 skipped, 36 deselected` twice,
  `Test Files  19 passed (19)` and `Tests  88 passed (88)`, `All checks passed!` and
  `no leaks found`.
- [ ] **Step 10: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(web): 🤖 Add browses the places and a folder off the event loop, and queues what is picked, typed or linked

The server's half of the Add screen (spec §19.2, §6.5, §8.1; S38, S39).
`browse` asks for the places (your home and mounted volumes) or one
folder, answered by the `browse_result` message: entries by bare name,
kind and full path, in browse.listing's order. `add` takes picked and
typed paths, through browse.expand's checks, and YouTube links, as their
canonical URLs, and queues them; a link with keep video runs with a
runner of its own (keep_video set), which the runtime's job_guard wraps.
Both run in a task of the tab's own through runtime.blocking, so a
sleeping NAS share keeps only that tab waiting (Review Focus 1); a tab
lists one folder at a time and only its newest request waits behind
it, so a sleeping share holds at most one of the blocking pool's
threads per tab. A listing that fails sends its reason and no entries.
The runtime turns BrowseError and NotYouTube into the pure
web.episode.AddError, which the server catches without importing them
(Pages). The Jobs page names a YouTube job by its video's id, never its
title, and doesn't offer to open it by its link.

The demo's browser has one place, its own folder, which is also its
home (proposed as a Decision: smaller than hiding Add, and no new
capability, Decision 23), and its job_guard is only_inside, so a link's
own runner runs only the demo's clip too.

The new tests failed first with: ImportError: cannot import name
'AddError' from 'vid2sub.web.episode'. Guard checks, each reverted and
restored: without the demo's guard the link's job fails for want of
deno instead of the demo's refusal; without the demo's one place its
browser lists your home; a listing per request instead of one at a time
runs beside the sleeping one.

Docs read: shiny 1.8.0's source (reactive.event fires per changed
value; an input's JSON arrays arrive as tuples, hence as_json),
shinyreact 0.1.0's send_message (module-resolved id, a
shinyReactMessage), Python's asyncio.create_task (keep a reference to
the task) and asyncio.to_thread; yt-dlp 2026.8.19's YoutubeDL
(bv*+ba/b is its default "bestvideo*+bestaudio/best").

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md Task 2
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/web/episode.py src/vid2sub/web/runtime.py src/vid2sub/web/views.py
  src/vid2sub/web/server.py src/vid2sub/web/demo.py tests/test_web_add.py`,
  `git commit -F .git/COMMIT_MSG`, then `git log -1 --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 11: Write the failing tests.** `frontend/src/lib/browse.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import type { BrowseResult } from "@/types";

import { NOT_ASKED, addRequest, answered, asked, canAdd } from "./browse";

const SEASON: BrowseResult = {
  n: 2, path: "/Volumes/NAS/TV/Show", parent: "/Volumes/NAS/TV", truncated: false, error: null,
  entries: [{ name: "Show S01E01.mkv", path: "/Volumes/NAS/TV/Show/Show S01E01.mkv", kind: "video" }],
};

describe("the file browser waits for the folder it asked for last (Review Focus 1)", () => {
  it("says it's waiting until that folder comes, and drops an answer to an older request", () => {
    let state = asked(NOT_ASKED, 1, null);
    state = asked(state, 2, "/Volumes/NAS/TV/Show");
    expect(state.waiting).toBe(true);
    expect(answered(state, { ...SEASON, n: 1, path: null })).toBe(state);
    state = answered(state, SEASON);
    expect(state.waiting).toBe(false);
    expect(state.shown).toEqual(SEASON);
  });

  it("shows a listing that failed as its reason alone, never the folder shown before it", () => {
    let state = answered(asked(NOT_ASKED, 2, "/Volumes/NAS/TV/Show"), SEASON);
    state = asked(state, 3, "/Volumes/NAS/TV/Other");
    expect(state.waiting).toBe(true);
    state = answered(state, { ...SEASON, n: 3, entries: SEASON.entries, error: "couldn't read this folder (Operation timed out)" });
    expect(state.shown?.entries).toEqual([]);
    expect(state.shown?.error).toBe("couldn't read this folder (Operation timed out)");
  });
});

describe("what Add sends (spec §19.2, §6.5)", () => {
  it("is the picked paths, then each typed path once, and the YouTube link", () => {
    expect(addRequest(["/TV/Show"], "  /TV/Show\n\n/films/Film.mp4 \n", " https://youtu.be/dQw4w9WgXcQ ", true)).toEqual({
      paths: ["/TV/Show", "/films/Film.mp4"], links: ["https://youtu.be/dQw4w9WgXcQ"], keep_video: true,
    });
    expect(canAdd(addRequest([], " \n", "", false))).toBe(false);
    expect(canAdd(addRequest([], "", "https://youtu.be/dQw4w9WgXcQ", false))).toBe(true);
  });
});
```

  Then the browser tests. In `tests/e2e/conftest.py`, in the module docstring, replace
  `` `start_server(..., toml=...)` serves a vid2sub.toml instead of the demo. `` with

```python
`start_server(..., toml=...)` serves a vid2sub.toml instead of the demo, and `command=` runs
vid2sub through a launcher (`fake_youtube.py`, which fakes yt-dlp) instead of `python -m vid2sub`.
```

  replace

```python
def start_server(tmp: Path, *args: str, port: int = 0, toml: str | None = None) -> Server:
    """`vid2sub serve --no-browser --demo` on `port` (0: any free one), up and answering; with
    `toml`, that vid2sub.toml instead of the demo."""
```

  with

```python
def start_server(tmp: Path, *args: str, port: int = 0, toml: str | None = None,
                 command: list[str] | None = None) -> Server:
    """`vid2sub serve --no-browser --demo` on `port` (0: any free one), up and answering; with
    `toml`, that vid2sub.toml instead of the demo; with `command`, run by it, not
    `python -m vid2sub`."""
```

  replace

```python
            [sys.executable, "-m", "vid2sub", "serve", "--no-browser", "--port", str(port),
             *which, *args],
```

  with

```python
            [*(command or [sys.executable, "-m", "vid2sub"]), "serve", "--no-browser",
             "--port", str(port), *which, *args],
```

  and in `launch`, replace

```python
    """Starts another server, `launch(tmp, *args, port=0, toml=None)`, stopped at the end."""
    started: list[Server] = []

    def run(tmp: Path, *args: str, port: int = 0, toml: str | None = None) -> Server:
        started.append(start_server(tmp, *args, port=port, toml=toml))
```

  with

```python
    """Starts another server, `launch(tmp, *args, port=0, toml=None, command=None)`, stopped at
    the end."""
    started: list[Server] = []

    def run(tmp: Path, *args: str, port: int = 0, toml: str | None = None,
            command: list[str] | None = None) -> Server:
        started.append(start_server(tmp, *args, port=port, toml=toml, command=command))
```

  `tests/e2e/fake_youtube.py`:

```python
"""`vid2sub serve` with yt-dlp answered by a local fake, so a browser test adds a YouTube link
without reaching YouTube (spec §8.1, §6.7; S39; tests never touch the network).

M1's seam, as tests/test_youtube.py uses it: `youtube.download(…, runner=)` runs yt-dlp through
`runner`. Here `download` is wrapped so the real one runs, its safe naming and its move into the
YouTube folder included, with a runner that writes CLIP (a video with picture and sound) as the
download when yt-dlp is asked for video and audio (`-f bv*+ba/b`, **keep video**), else that
clip's sound alone; and it says which format it was asked for in ASKED, a file beside CLIP. deno,
which yt-dlp needs for YouTube, is never run, so a machine without it passes too.

    python tests/e2e/fake_youtube.py CLIP serve --no-browser --port 0 --config vid2sub.toml
"""

import dataclasses
import json
import shutil
import subprocess
import sys
from pathlib import Path

from vid2sub.cli import main
from vid2sub.media import youtube

VIDEO_AND_AUDIO = "bv*+ba/b"
TITLE = "A talk at a college"


def fake_yt_dlp(clip: Path):
    def run(args, *, cwd, timeout, **_):
        asked = args[args.index("-f") + 1]
        clip.with_name("ASKED").write_text(asked, encoding="utf-8")
        vid = youtube.video_id(args[-1])
        if asked == VIDEO_AND_AUDIO:
            out = cwd / f"{vid}.mkv"
            shutil.copyfile(clip, out)
        else:
            out = cwd / f"{vid}.m4a"
            subprocess.run([shutil.which("ffmpeg"), "-nostdin", "-v", "error", "-y", "-i",
                            str(clip), "-vn", "-c:a", "copy", str(out)], check=True)
        line = json.dumps({"id": vid, "title": TITLE, "upload_date": "19620912",
                           "filepath": str(out)})
        return subprocess.CompletedProcess(args, 0, stdout=line.encode() + b"\n", stderr=b"")

    return run


def wrap(clip: Path):
    real = youtube.download

    def download(url, *, out_dir, scratch, keep_video, tools, runner=None, timeout=3600):
        tools = dataclasses.replace(tools, deno=tools.deno or "/deno/is/never/run")
        return real(url, out_dir=out_dir, scratch=scratch, keep_video=keep_video, tools=tools,
                    runner=fake_yt_dlp(clip), timeout=timeout)

    return download


if __name__ == "__main__":
    youtube.download = wrap(Path(sys.argv[1]))
    sys.exit(main(sys.argv[2:]))
```

  `tests/e2e/test_add.py`:

```python
"""The Add screen in Chromium (spec §19.2, §6.5, §8.1; S38, S39): the file browser starts at the
places, opens a folder with its folders first and its episodes in `SxxEyy` order, shows only
folders, videos and subtitles, and adds what is picked; a YouTube link with **keep video** ticked
lands whole in the YouTube folder. Against `vid2sub serve --demo`, whose browser has only the
demo's folder, and against a vid2sub.toml served with yt-dlp faked (`fake_youtube.py`, M1's
`download(…, runner=)` seam) and a fake whisper.cpp server, so nothing reaches YouTube or a model.
Run with `make e2e`."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from fakes import FakeServer
from helpers import SPEECH, make_clip
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e

HERE = Path(__file__).parent
WORDS = {"language": "english", "language_probabilities": {"en": 0.99},
         "segments": [{"text": " We meet at a college.", "start": 0.0, "end": 2.0,
                       "words": [{"word": " We", "start": 0.0, "end": 0.5, "probability": 0.9},
                                 {"word": " meet", "start": 0.5, "end": 1.0,
                                  "probability": 0.9},
                                 {"word": " at", "start": 1.0, "end": 1.2, "probability": 0.9},
                                 {"word": " a", "start": 1.2, "end": 1.4, "probability": 0.9},
                                 {"word": " college.", "start": 1.4, "end": 2.0,
                                  "probability": 0.9}]}]}


def open_add(page):
    page.get_by_test_id("nav-add").click()
    expect(page.get_by_test_id("add-page")).to_be_visible()


def test_the_demo_browses_its_own_folder_in_episode_order_and_adds_its_clip(page, server):
    copy = next(server.tmp.glob("vid2sub-demo-*/demo"))
    for name in ("Show S01E10.mkv", "Show S01E02.mkv", ".hidden.mkv", "notes.txt"):
        (copy / name).write_bytes(b"x")
    (copy / "Extras").mkdir()
    open_add(page)
    entries = page.get_by_test_id("browse-entry")
    expect(entries).to_have_count(1)  # the places: the demo's own folder, nothing of yours
    expect(entries.first).to_contain_text("Demo")
    entries.first.get_by_test_id("browse-open").click()
    expect(page.get_by_test_id("browse-path")).to_have_text(str(copy))
    expect(entries).to_have_text([
        "Extrasfolder", "Show S01E02.mkvvideo", "Show S01E10.mkvvideo", "jfk.en.srtsubtitles",
        "jfk.ja.srtsubtitles", "jfk.mp4video"])
    page.get_by_label("Pick jfk.mp4").check()
    expect(page.get_by_test_id("add-picked")).to_have_text("1 picked")
    page.get_by_test_id("add-start").click()
    expect(page.get_by_test_id("jobs-page")).to_be_visible()
    job = page.get_by_test_id("job")
    expect(job).to_have_count(1)
    expect(job.first).to_have_attribute("data-state", "done", timeout=30_000)
    page.get_by_test_id("nav-add").click()
    page.get_by_test_id("add-paths").fill("/somewhere/else.mkv")
    page.get_by_test_id("add-start").click()
    expect(page.get_by_test_id("add-error")).to_have_text(
        "vid2sub browses your home folder, your drives and network shares only")


TOML = """
[defaults]
youtube_dir = {youtube}
targets = ["en"]

[endpoints.spark]
base_url = "{url}"

[models.spark-turbo]
catalog = "whisper-large-v3-turbo"
endpoint = "spark"
model = "turbo"
parser = "whisper.cpp"
local = true
"""


def test_a_youtube_link_with_keep_video_ticked_lands_whole_in_the_youtube_folder(
        launch, open_page, tmp_path):
    (tmp_path / "clips").mkdir()
    clip = make_clip(tmp_path / "clips", "talk.mkv", seconds=14, speech=SPEECH,
                     audio_langs=("eng",))
    youtube = tmp_path / "YouTube"

    def whisper(req):
        if req.path.endswith("/models"):
            return 200, {"object": "list", "data": [{"id": "turbo", "object": "model"}]}, {}
        return 200, WORDS, {}

    with FakeServer(responder=whisper) as spark:
        server = launch(tmp_path / "server",
                        toml=TOML.format(youtube=json.dumps(str(youtube)), url=spark.url),
                        command=[sys.executable, str(HERE / "fake_youtube.py"), str(clip)])
        watched = open_page(server)
        page = watched.page
        open_add(page)
        page.get_by_test_id("add-link").fill("https://youtu.be/dQw4w9WgXcQ?si=shared")
        page.get_by_test_id("add-keep-video").check()
        page.get_by_test_id("add-start").click()
        job = page.get_by_test_id("job")
        expect(job).to_have_count(1)
        expect(job.first).to_contain_text("YouTube video dQw4w9WgXcQ")
        expect(job.first).to_have_attribute("data-state", "done", timeout=60_000)
    landed = youtube / "A talk at a college [dQw4w9WgXcQ].mkv"
    assert clip.with_name("ASKED").read_text(encoding="utf-8") == "bv*+ba/b"
    streams = json.loads(subprocess.run(
        [shutil.which("ffprobe"), "-v", "error", "-show_streams", "-of", "json", str(landed)],
        check=True, capture_output=True).stdout)["streams"]
    assert {s["codec_type"] for s in streams} == {"video", "audio"}  # the whole video
    assert landed.with_name("A talk at a college [dQw4w9WgXcQ].en.srt").is_file()
    assert watched.errors == [] and watched.violations() == []
```

- [ ] **Step 12: Run them; watch them fail.** `make test-js`. Expected: its typecheck stops at
  `src/lib/browse.test.ts(3,15): error TS2305: Module '"@/types"' has no exported member
  'BrowseResult'.` and `src/lib/browse.test.ts(5,64): error TS2307: Cannot find module
  './browse' or its corresponding type declarations.` Then `make e2e` (it builds the frontend
  first). Expected: both new tests fail with
  `E           playwright._impl._errors.TimeoutError: Locator.click: Timeout 30000ms exceeded.`,
  `waiting for get_by_test_id("nav-add")`, and `2 failed, 31 passed, 1139 deselected`.
- [ ] **Step 13: Write the code.** In `frontend/src/types.ts`, above
  `/** The \`endpoint_test_result\` message: what an endpoint's /v1/models said, or why it failed. */`,
  add:

```ts
/** An entry in the Add screen's file browser (views.browse_view; spec §6.5, S38): `name` is shown
 * as plain text; `path` is what the page sends back to list or add, and nothing else is. */
export type BrowseEntry = { name: string; path: string; kind: "folder" | "video" | "subtitle" };

/** The `browse_result` message: the folder request `n` asked for (`path` null: the places), with
 * `parent` null at a root, or why it couldn't be listed (`error`), with no entries. */
export type BrowseResult = {
  n: number | null;
  path: string | null;
  parent: string | null;
  entries: BrowseEntry[];
  truncated: boolean;
  error: string | null;
};

/** The `add_result` message: how many jobs request `n` queued, or why nothing was added. */
export type AddResultMessage = { n: number | null; added: number; error: string | null };

```

  `frontend/src/lib/browse.ts`:

```ts
// The Add screen's file browser and its request (spec §19.2, §6.5; S38, S39): which folder the
// page asked for last, whether it is still waiting for it (a network share can take seconds to
// wake: Review Focus 1), and what it shows. Only the answer to the last request is shown, so a
// slow folder never replaces the one the person moved on to, and a listing that failed shows its
// reason and no entries, never the folder shown before it. What Add sends back is only what the
// person typed or a path from a listing the engine sent (§6.5).

import { typedPaths } from "@/lib/jobs";
import type { BrowseResult } from "@/types";

export type BrowseState = {
  asked: number | null; // the request whose answer is wanted
  path: string | null; // the folder asked for (null: the places)
  waiting: boolean;
  shown: BrowseResult | null;
};

export const NOT_ASKED: BrowseState = { asked: null, path: null, waiting: false, shown: null };

/** The page asked for `path` (null: the places) as request `n`. */
export function asked(state: BrowseState, n: number, path: string | null): BrowseState {
  return { ...state, asked: n, path, waiting: true };
}

/** The engine answered: shown only when it answers the last request; a failure shows nothing
 * stale. */
export function answered(state: BrowseState, result: BrowseResult): BrowseState {
  if (result.n !== state.asked) return state;
  const shown = result.error ? { ...result, entries: [], truncated: false } : result;
  return { ...state, waiting: false, shown };
}

export type AddRequest = { paths: string[]; links: string[]; keep_video: boolean };

/** What Add sends: the picked entries' paths, then each typed path, and the YouTube link. */
export function addRequest(picked: readonly string[], typed: string, link: string, keepVideo: boolean): AddRequest {
  const paths = [...picked, ...typedPaths(typed).filter((p) => !picked.includes(p))];
  const url = link.trim();
  return { paths, links: url ? [url] : [], keep_video: keepVideo };
}

/** Whether there is anything to add. */
export function canAdd(request: AddRequest): boolean {
  return request.paths.length > 0 || request.links.length > 0;
}
```

  `frontend/src/components/AddPage.tsx`:

```tsx
import { type FormEvent, useEffect, useState } from "react";

import { type AddRequest, type BrowseState, addRequest, canAdd } from "@/lib/browse";

const button = "rounded-md border border-input bg-background px-2 py-1 text-sm focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ring disabled:opacity-50";
const field = "rounded-md border border-input bg-background px-2 py-1 font-mono text-sm focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ring";

/** The Add screen (spec §19.2, §6.5; S38, S39), the local engine's alone: pick videos and
 * folders in the in-app file browser, type full paths, or paste a YouTube link, with **keep
 * video** to keep the whole video rather than its audio (§8.1). The browser starts at the places
 * (your home folder and mounted volumes) and shows only folders, videos and subtitle files,
 * folders first and a season's episodes in `SxxEyy` order; while a folder is on its way it says
 * it's waiting (a sleeping network share can take seconds), and a folder that couldn't be read
 * shows why and nothing else (Review Focus 1). A folder adds its own videos, not its
 * subfolders'. Names and reasons are plain text (§6.3); only a path from a listing, or one the
 * person typed, is sent back (§6.5). Every control is a native button, checkbox or field, so it
 * all works from the keyboard. */
export function AddPage({ browse, onBrowse, onAdd, adding, error }: {
  browse: BrowseState;
  onBrowse: (path: string | null) => void;
  onAdd: (request: AddRequest) => void;
  adding: boolean;
  error: string | null;
}) {
  const [picked, setPicked] = useState<string[]>([]);
  const [typed, setTyped] = useState("");
  const [link, setLink] = useState("");
  const [keepVideo, setKeepVideo] = useState(false);
  useEffect(() => {
    if (browse.asked === null) onBrowse(null); // the places, the first time Add is shown
  }, [browse.asked, onBrowse]);
  const shown = browse.waiting ? null : browse.shown;
  const here = shown && !shown.error ? shown.path : null; // the folder shown, as the disk spells it
  const request = addRequest(picked, typed, link, keepVideo);
  const toggle = (path: string) => setPicked((p) => (p.includes(path) ? p.filter((x) => x !== path) : [...p, path]));
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (canAdd(request) && !adding) onAdd(request);
  };
  return (
    <form className="flex h-full min-h-0 flex-col gap-4 overflow-y-auto p-4" onSubmit={submit} data-testid="add-page">
      <section aria-labelledby="browse-heading" className="flex flex-col gap-2">
        <h2 id="browse-heading" className="text-sm font-bold">Browse</h2>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <button type="button" className={button} onClick={() => onBrowse(null)} data-testid="browse-places">Places</button>
          <button type="button" className={button} onClick={() => onBrowse(browse.shown?.parent ?? null)} disabled={browse.path === null} data-testid="browse-up">Up</button>
          <span className="font-mono break-all" data-testid="browse-path">{here ?? browse.path ?? "Your home folder and drives"}</span>
          {here && (
            <label className="ml-auto flex items-center gap-1">
              <input type="checkbox" checked={picked.includes(here)} onChange={() => toggle(here)} data-testid="browse-pick-here" />
              Add this folder's videos
            </label>
          )}
        </div>
        {browse.waiting && (
          <p role="status" className="text-muted-foreground" data-testid="browse-waiting">Waiting for the folder… a network share can take a few seconds to wake.</p>
        )}
        {shown?.error && <p role="alert" className="text-destructive" data-testid="browse-error">{shown.error}</p>}
        {shown && !shown.error && (shown.entries.length === 0 ? (
          <p className="text-muted-foreground">No folders, videos or subtitles here.</p>
        ) : (
          <ul aria-label="In this folder" className="flex flex-col rounded-md border border-border bg-card text-sm" data-testid="browse-list">
            {shown.entries.map((e) => (
              <li key={e.path} className="flex items-center gap-2 border-b border-border px-2 py-1 last:border-b-0" data-testid="browse-entry" data-kind={e.kind}>
                {e.kind === "subtitle" ? (
                  <span className="w-4" aria-hidden="true" />
                ) : (
                  <input type="checkbox" aria-label={`Pick ${e.name}`} checked={picked.includes(e.path)} onChange={() => toggle(e.path)} data-testid="browse-pick" />
                )}
                {e.kind === "folder" ? (
                  <button type="button" className="break-all text-left font-bold underline-offset-2 hover:underline focus-visible:outline-2 focus-visible:outline-ring" onClick={() => onBrowse(e.path)} data-testid="browse-open">{e.name}</button>
                ) : (
                  <span className={`break-all ${e.kind === "subtitle" ? "text-muted-foreground" : ""}`} data-testid="browse-name">{e.name}</span>
                )}
                <span className="ml-auto text-muted-foreground">{e.kind === "folder" ? "folder" : e.kind === "video" ? "video" : "subtitles"}</span>
              </li>
            ))}
          </ul>
        ))}
        {shown?.truncated && <p className="text-muted-foreground">This folder has more entries than vid2sub shows: only the first are listed.</p>}
      </section>
      <section className="flex flex-col gap-2">
        <label htmlFor="add-paths" className="text-sm font-bold">Or type full paths, one a line</label>
        <textarea id="add-paths" rows={3} className={field} value={typed} onChange={(e) => setTyped(e.target.value)} placeholder="/full/path/to/a season folder" spellCheck={false} data-testid="add-paths" />
      </section>
      <section className="flex flex-col gap-2">
        <label htmlFor="add-link" className="text-sm font-bold">Or a YouTube link</label>
        <input id="add-link" type="text" inputMode="url" className={field} value={link} onChange={(e) => setLink(e.target.value)} placeholder="https://www.youtube.com/watch?v=…" spellCheck={false} autoComplete="off" data-testid="add-link" />
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={keepVideo} onChange={(e) => setKeepVideo(e.target.checked)} data-testid="add-keep-video" />
          Keep the video, not only its audio
        </label>
      </section>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <button type="submit" className="rounded-md bg-primary px-3 py-1 font-bold text-primary-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:opacity-50" disabled={!canAdd(request) || adding} data-testid="add-start">
          {adding ? "Adding…" : "Add"}
        </button>
        <span className="text-muted-foreground" data-testid="add-picked">{picked.length === 1 ? "1 picked" : `${picked.length} picked`}</span>
        {picked.length > 0 && <button type="button" className={button} onClick={() => setPicked([])}>Clear</button>}
        <span className="text-muted-foreground">They run one at a time, with the session's targets and formats (Settings).</span>
      </div>
      {error && <p role="alert" className="text-destructive" data-testid="add-error">{error}</p>}
    </form>
  );
}
```

  In `frontend/src/App.tsx`, above
  `import { Editor, type Requests, type Saving } from "@/components/Editor";`, add
  `import { AddPage } from "@/components/AddPage";`; above
  `import { LOST_MESSAGES, type Lost, whyLost } from "@/lib/connection";`, add
  `import { type AddRequest, type BrowseState, NOT_ASKED, answered, asked } from "@/lib/browse";`;
  in the `import type { … } from "@/types";` line, add `AddResultMessage, BrowseResult, ` before
  `Busy`; below `type Ask = { episode: string; n: number };`, add (after a blank line)
  `const SCREENS = { editor: "Editor", add: "Add", jobs: "Jobs" } as const;`; below the
  `setJobCancel` line, add:

```tsx
  const setBrowse = useSetShinyInput<{ path: string | null; n: number } | null>("browse", null, { priority: "event", debounceMs: 0 });
  const setAdd = useSetShinyInput<(AddRequest & { n: number }) | null>("add", null, { priority: "event", debounceMs: 0 });
```

  replace

```tsx
  // The Jobs page (spec §19.2, S36), where the engine makes subtitles (`generate`; Pages hides
  // it, §21). The editor stays mounted while it shows, so the player keeps its place.
  const [screen, setScreen] = useState<"editor" | "jobs">("editor");
```

  with

```tsx
  // The Add screen and the Jobs page (spec §19.2; S36, S38, S39), where the engine makes subtitles
  // (`generate`; Pages hides both, §21). The editor stays mounted while they show, so the player
  // keeps its place.
  const [screen, setScreen] = useState<"editor" | "add" | "jobs">("editor");
```

  below `onOpenJob` (after its closing `};`), add, after a blank line:

```tsx
  // Add (Phase 3): the file browser shows the answer to the folder it asked for last, and says
  // it's waiting until then (a sleeping network share, Review Focus 1); a finished Add opens the
  // Jobs page, and one that took nothing says why on the Add screen.
  const [browse, setBrowseState] = useState<BrowseState>(NOT_ASKED);
  useShinyMessageHandler("browse_result", (r: BrowseResult) => setBrowseState((s) => answered(s, r)));
  const onBrowse = useCallback((path: string | null) => {
    const n = ++sent.current;
    setBrowseState((s) => asked(s, n, path));
    pace(() => setBrowse({ path, n }));
  }, [pace, setBrowse]);
  const [adding, setAdding] = useState<number | null>(null);
  const [addError, setAddError] = useState<string | null>(null);
  useShinyMessageHandler("add_result", (r: AddResultMessage) => {
    if (r?.n !== adding) return;
    setAdding(null);
    setAddError(r.error);
    if (!r.error) setScreen("jobs");
  });
  const onAdd = (request: AddRequest) => {
    const n = ++sent.current;
    setAdding(n);
    setAddError(null);
    pace(() => setAdd({ ...request, n }));
  };
```

  replace `{(["editor", "jobs"] as const).map((s) => (` with
  `{(["editor", "add", "jobs"] as const).map((s) => (`, and
  `{s === "editor" ? "Editor" : "Jobs"}` with `{SCREENS[s]}`; above
  `{generate && screen === "jobs" && (`, add:

```tsx
      {generate && screen === "add" && (
        <section aria-label="Add" className="min-h-0 flex-1">
          <AddPage browse={browse} onBrowse={onBrowse} onAdd={onAdd} adding={adding !== null} error={addError} />
        </section>
      )}
```

  and replace `hidden={generate && screen === "jobs"}` with `hidden={generate && screen !== "editor"}`.
- [ ] **Step 14: Run the checks; they pass.** `make test-js` first (`Test Files  20 passed
  (20)`, `Tests  91 passed (91)`), then `make check`, then `make e2e`. Expected: `make check`:
  `1127 passed, 7 skipped, 38 deselected` twice, `Test Files  20 passed (20)` and
  `Tests  91 passed (91)`, `All checks passed!` and `no leaks found`; `make e2e`:
  `33 passed, 1139 deselected`. **Guard check:** in `lib/browse.ts`'s `answered`, delete
  `if (result.n !== state.asked) return state;` (`make test-js`: the older answer replaces the
  folder asked for last: `Tests  1 failed | 90 passed (91)`); restore it.
- [ ] **Step 15: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(ui): 🤖 the Add screen browses home and the volumes, says when a share is waking, and adds a link with its video

The page's half of Add (spec §19.2, §6.5, §8.1; S38, S39). An Add screen
beside Editor and Jobs, where generate is true: Browse starts at the
places, opens a folder (folders first, then its videos and subtitle
files in SxxEyy order, as the engine sends them), goes Up to the parent
or the places, and picks videos and folders with checkboxes, the
folder shown included; full paths can be typed, one a line, and a
YouTube link pasted with "Keep the video, not only its audio". While a
folder is on its way the page says it's waiting (a network share can
take seconds to wake); only the answer to the request sent last is
shown, and one that failed shows its reason and no entries, never the
folder before it (Review Focus 1). A finished Add opens the Jobs page;
one that took nothing says why. Every control is a native button,
checkbox or field, so it works from the keyboard; names and reasons are
plain text (§6.3), and only a listing's paths or typed text go back.

The browser tests: the demo browses only its own folder (its one place),
in episode order, hides dotfiles, its sidecar and anything that isn't a
video or a subtitle, adds its clip, which runs to done, and refuses a
typed path anywhere else. S39 runs vid2sub through
tests/e2e/fake_youtube.py, which answers yt-dlp through M1's
download(…, runner=) seam with a local clip, and a fake whisper.cpp
server: the link with keep video ticked asks yt-dlp for bv*+ba/b, and
"A talk at a college [dQw4w9WgXcQ].mkv" lands in the YouTube folder
with its picture and sound, its .en.srt beside it. Nothing reaches
YouTube or a model. conftest's start_server and launch take command=.

The new tests failed first with: error TS2307: Cannot find module
'./browse' (make test-js's typecheck), and in Chromium, Locator.click:
Timeout 30000ms exceeded, waiting for get_by_test_id("nav-add"). Guard check, reverted and
restored: with `answered` taking any answer, the browse test fails.

Docs read: React 19.2.8's types (useCallback, useEffect); MDN on ARIA
live regions (role="status" is polite, role="alert" assertive) and on
inputmode; Playwright 1.64.1's Python API (get_by_label, Locator.check,
to_have_text with a list of texts); shinyreact 0.1.0's
useShinyMessageHandler (a message with no handler is dropped, so both
handlers live in App).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md Task 2
Co-Authored-By: <the model's own line>
```

  `git add frontend/src/types.ts frontend/src/lib/browse.ts frontend/src/lib/browse.test.ts
  frontend/src/components/AddPage.tsx frontend/src/App.tsx tests/e2e/conftest.py
  tests/e2e/fake_youtube.py tests/e2e/test_add.py`, `git commit -F .git/COMMIT_MSG`, then
  `git log -1 --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 16: Review, look forward, close.** The Tier 2 review from `$(cat .git/TASK_BASE)`
  (`AGENTS.md`, *Reviews*). Worth the reviewers' time: that only a listing's paths and typed
  text reach `rt.expand` (§6.5) and every refusal names nothing (§6.8); that a sleeping share
  holds at most one blocking thread per tab and never the reactive lock; that the demo lists
  nothing outside its folder and runs nothing but its clip, a link's own runner included. The
  forward review over Tasks 3, 4, 6 and 11: Task 3's `start` submits with `runner=` (built here,
  so Task 3 no longer adds it) and wraps each row's runner in the runtime's `job_guard`; Task
  4 replaces `add`'s hand-off (`rt.add`) with `prepare` and `sample`, and a finished Add opens
  Review; Task 6's Jobs page names a YouTube job by its video; Task 11 documents the Add screen
  and the demo's one place. The docs this task made untrue: none expected (grep `README.md`
  and `docs/` for "Add" and "Browse"; the README's screens list gains Add in Task 11). Then the
  close, its own commit, holding this plan with this task's boxes ticked and **Now** set to
  `Task 3: Sampling and suggestions for Review, open.`, and the spec's rows S38 (`Phase 3,
  Tasks 1–2`, proof `tests/test_browse.py`; Playwright) and S39 (`Phase 3, Task 2`, proof
  `tests/e2e/test_add.py`) set to `built`. The message, in `.git/CLOSE_MSG`:

```text
docs(plan): 🤖 close Task 2: The Add screen

Drift: none
Rulings: none
Phase-end: none
Forward: none
Tier: 2
Rounds: none
Findings: none

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md Task 2
Co-Authored-By: <the model's own line>
```

  `git add docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md
  docs/superpowers/specs/2026-10-14-vid2sub-design.md`, `git commit -F .git/CLOSE_MSG`.

***

### Task 3: Sampling and suggestions for Review

**Tier:** 2 · **Scenarios:** S40

**Files:**
- Create: `src/vid2sub/review.py`
- Modify: `src/vid2sub/pipeline.py` (`RunContext.engine` checks the cloud on every call)
- Test: `tests/test_review.py`

**Interfaces:**
- Consumes: `detect.candidates`, `detect.choose_detector` (always `allow_cloud=False`),
  `detect.detect`, `detect.Detection`; `catalog.CATALOG`, `Candidate`, `suggest`;
  `pipeline.RunContext`, `RunOptions`, `Cancelled`, `run_one`; `media.probe.probe`,
  `pick_track`, `Probe`; `media.decode.decode_to_wav`, `read_wav`, `encode_flac`, `to_float`,
  `SAMPLES_PER_MS`; `media.vad.speech_regions`; `media.youtube.is_url`, `video_id`,
  `NotYouTube`; `subs.naming.target_track`, `track`; `subs.langs.LANGS`;
  `engines.clients.check_allowed`; Phase 2 Task 4's `jobs.Queue` and `Runner`, with Task 2's
  `Queue.submit(…, runner=)`; Phase 2 Task 18's `web.settings.Session` defaults, which Task 4
  passes as `targets` and `formats`. What `prepare` takes is Task 1's `browse.expand` output
  (full paths) or YouTube links, through Task 2's `Runtime.expand`.
- Produces:
  - `pipeline.RunContext.engine(name)` runs `clients.check_allowed` on every call, so an engine
    made for a run that allowed the cloud is refused to a copy of the context whose run
    doesn't (spec §7.2): per-job options share one engine cache.
  - `vid2sub.review`:
    - `RowState = Literal["waiting", "sampling", "ready", "failed"]`; `FIELDS` (`language`,
      `transcribe`, `translate`, `targets`, `formats`, `script`, `audio_track`);
      `SHARED_FIELDS` (the same without `audio_track`: what "apply to all" copies);
      `SAMPLED_PER_FOLDER = 2`; `FORMATS = ("srt", "ass")`
    - `class ReviewError(ValueError)`: a choice or a Start refused; fit to show, echoing nothing
    - `@dataclass(frozen=True) class ModelChoice: name: str; title: str; good_for: str;
      available: bool; reason: str = ""; cloud: bool = False` (a picker's entry: the model's
      name in `vid2sub.toml`, the catalog's title and one-liner, and why it can't run now)
    - `@dataclass(frozen=True) class Row: id: str; path: str; name: str; folder: str;
      link: bool = False; state: RowState = "waiting"; sampled: bool = False;
      inherited: bool = False; duration_ms: int | None = None; probe: Probe | None = None;
      audio_track: int | None = None; detection: Detection | None = None;
      language: str | None = None; ask_zh_yue: bool = False; transcribe: str | None = None;
      translate: str | None = None; targets: tuple[str, ...] = ();
      formats: tuple[str, ...] = (); script: str | None = None; keep_video: bool = False;
      warning: str = ""; error: str = ""; hint: str = ""`, and the property
      `audio_index -> int | None` (the person's track, else §8.4's pick for the language).
      `id` is `r1`, `r2`… in the order added, what the screen sends back; `path` never reaches
      a log or the view; `name` is the bare file name, or `YouTube video <id>`;
      `ask_zh_yue` is "Mandarin or Cantonese?" (language None until answered)
    - `@dataclass(frozen=True) class Review: rows: tuple[Row, ...];
      candidates: tuple[Candidate, ...] = (); transcribers: tuple[ModelChoice, ...] = ();
      translators: tuple[ModelChoice, ...] = (); allow_cloud: bool = False`
    - `model_choices(config: Config, candidates: Sequence[Candidate],
      task: Literal["transcribe", "translate"]) -> tuple[ModelChoice, ...]` (Task 8's Models
      page can show the same)
    - `prepare(inputs: Sequence[str], ctx: RunContext, *, keep_video: bool = False,
      targets: Sequence[str] | None = None, formats: Sequence[str] | None = None) -> Review`:
      blocks (ffprobe per file, each local server's model list); each row starts with `targets`
      and `formats` (the session's defaults; `vid2sub.toml`'s when None); the candidates are
      `ctx.candidates` when the context brings them (the demo's canned context), else
      `detect.candidates`; `allow_cloud` is always False and has no parameter
    - `sample(review: Review, ctx: RunContext, *, on_row: Callable[[Row], None] | None = None,
      cancelled: Callable[[], bool] = <never>) -> Review`: blocks for seconds per sampled file;
      `on_row` runs on the calling thread after each change (`sampling`, then `ready`), and
      only rows that weren't ready change, so the screen merges each with `with_row` and keeps
      the person's choices; raises `pipeline.Cancelled` before the next file when `cancelled()`
    - `with_row(review, row: Row) -> Review`; `choose(review, row_id: str, **changes) -> Review`
      (a language change answers "Mandarin or Cantonese?" and suggests that language's models
      unless they are in the same call; Cantonese drops any script); `apply_to_all(review,
      row_id: str, field: str) -> Review`; `set_allow_cloud(review, allowed: bool) -> Review`
      (the box, the only setter); `problems(review) -> dict[str, str]` (row id → what stops
      Start; empty means it can go); all pure
    - `run_options(review, row_id: str, base: RunOptions) -> RunOptions` (the row's choices on
      the server's options; `allow_cloud` from the review's box alone)
    - `runner_for(ctx: RunContext, options: RunOptions) -> jobs.Runner` (`run_one` on
      `dataclasses.replace(ctx, options=…, events=…, cancelled=…)`, sharing the context's
      engines and finished chunks, spec §8.9)
    - `start(review, queue: jobs.Queue, ctx: RunContext, *, guard: Callable[[jobs.Runner],
      jobs.Runner] | None = None) -> list[str]` (every row that can run, in order, each with
      its own runner, wrapped by `guard` when given (the runtime's `job_guard`); nothing queued
      while `problems` isn't empty; a failed row left out; the job ids). A row's targets and
      formats win over the session's: its runner is `runner_for`'s, never `job_runner`'s
  - What Task 4 calls: `prepare` then `sample`, both off the event loop, with `on_row` hopping
    to the session's loop (it runs on the sampling thread, as Task 4's listeners do) and a
    `cancelled` that turns true when the person leaves Review or adds again; `choose`,
    `apply_to_all`, `set_allow_cloud` and `problems` on the loop (pure, fast); `start` with the
    runtime's `Queue` and its job `RunContext`, `Runtime.job_context` (the one Phase 2 Task
    19's `runtime.job_runner(ctx, session)` wraps `run_one` with; in the demo it is the canned
    context, and its runner runs only the demo's own clip; Pages offers no Review). The view of
    a row is Task 4's (never `path`; `detection.votes`, `detection.confidence`, `warning`,
    `hint`, `inherited`, `ask_zh_yue`); the box is drawn from `Review.allow_cloud` and never
    from settings. `vid2sub.review` imports the pipeline, so it isn't in the Pages bundle: Task
    4's server reaches all of it through the runtime, which seeds `prepare` with the session's
    defaults and passes `guard=job_guard` to `start`.


- [ ] **Step 0: Record the base:** `git rev-parse HEAD > .git/TASK_BASE`.
- [ ] **Step 1: Write the failing test,** `tests/test_review.py`:

```python
"""Review (spec §10, §19.2, S40): sampling, suggestions, "apply to all", and Allow cloud."""

import shutil
import threading
from dataclasses import replace
from queue import SimpleQueue

import pytest
from fakes import FakeEngine
from helpers import SPEECH, make_clip

from vid2sub import detect as detecting
from vid2sub import review
from vid2sub.catalog import Candidate
from vid2sub.config import Config, ConfigError, Endpoint, ModelEntry, load_config
from vid2sub.engines.base import EngineError
from vid2sub.engines.clients import KeyRing
from vid2sub.media.probe import AudioTrack, Probe
from vid2sub.media.tools import Tools
from vid2sub.pipeline import RunContext, RunOptions
from vid2sub.review import ReviewError, Row

LINK = "https://youtu.be/dQw4w9WgXcQ"
CONFIG = Config(
    endpoints={"spark": Endpoint(base_url="http://127.0.0.1:9/v1"),
               "openai": Endpoint(base_url="https://api.openai.com/v1", key_env="OPENAI_API_KEY")},
    models={"spark-turbo": ModelEntry(catalog="whisper-large-v3-turbo", endpoint="spark",
                                      model="whisper-large-v3-turbo", parser="whisper.cpp",
                                      local=True),
            "spark-gemma": ModelEntry(catalog="gemma-4-26b-a4b", endpoint="spark",
                                      model="gemma-4-26b-a4b", task="translate", local=True),
            "mac-qwen": ModelEntry(catalog="qwen3-asr-1.7b", engine="mlx-qwen3-asr"),
            "openai-whisper": ModelEntry(catalog="openai-whisper-1", endpoint="openai",
                                         model="whisper-1", parser="openai"),
            "openai-gpt": ModelEntry(catalog="openai-gpt", endpoint="openai", model="gpt-5",
                                     task="translate")})
DOWN = "couldn't reach the server (is it running? For the Spark: is `make tunnel` running?)"
CANDIDATES = [
    Candidate("spark-turbo", "whisper-large-v3-turbo", "endpoint", True),
    Candidate("spark-gemma", "gemma-4-26b-a4b", "endpoint", True),
    Candidate("mac-qwen", "qwen3-asr-1.7b", "in-process", False,
              "install vid2sub[mac] on an Apple Silicon Mac"),
    Candidate("openai-whisper", "openai-whisper-1", "endpoint", True, cloud=True),
    Candidate("openai-gpt", "openai-gpt", "endpoint", True, cloud=True),
]
PROBE = Probe(duration_ms=1_440_000, container="matroska,webm", video_codec="h264",
              audio=(AudioTrack(0, 1, "aac", 2, "ja", "jpn", True, 0),
                     AudioTrack(1, 2, "aac", 2, "en", "eng", False, 0)), min_start_ms=0)


@pytest.fixture
def candidates(monkeypatch):
    found = list(CANDIDATES)
    monkeypatch.setattr(detecting, "candidates", lambda config, keys, **kw: list(found))
    return found


def make_ctx(engine=None, **options):
    ctx = RunContext(config=CONFIG, tools=Tools.find(), keys=KeyRing(environ={}),
                     options=RunOptions(**options))
    ctx.engines["spark-turbo"] = engine or FakeEngine(detect={"ja": 0.9})
    return ctx


def file_row(n, **fields) -> Row:
    defaults = {"id": f"r{n}", "path": f"/films/Show/Show S01E0{n}.mkv",
                "name": f"Show S01E0{n}.mkv", "folder": "/films/Show", "state": "ready",
                "probe": PROBE, "targets": ("en",), "formats": ("srt",)}
    return Row(**{**defaults, **fields})


def reviewed(*rows, **fields) -> review.Review:
    return review.Review(rows=rows, candidates=tuple(CANDIDATES),
                         transcribers=review.model_choices(CONFIG, CANDIDATES, "transcribe"),
                         translators=review.model_choices(CONFIG, CANDIDATES, "translate"),
                         **fields)


def row(rv: review.Review, rid: str) -> Row:
    return next(r for r in rv.rows if r.id == rid)


# Adding and probing (spec §10.1)


def test_a_link_waits_for_its_run_and_every_model_says_whether_it_can_run_now(candidates):
    rv = review.prepare([LINK], make_ctx(), keep_video=True)
    (link,) = rv.rows
    assert (link.id, link.name, link.link, link.state, link.keep_video) == (
        "r1", "YouTube video dQw4w9WgXcQ", True, "ready", True)
    assert (link.language, link.transcribe, link.targets, link.formats) == (None, None, ("en",),
                                                                           ("srt",))
    assert [(c.name, c.available, c.reason, c.cloud) for c in rv.transcribers] == [
        ("spark-turbo", True, "", False),
        ("mac-qwen", False, "install vid2sub[mac] on an Apple Silicon Mac", False),
        ("openai-whisper", True, "", True)]
    assert rv.transcribers[0].title == "Whisper large-v3-turbo"
    assert [c.name for c in rv.translators] == ["spark-gemma", "openai-gpt"]


def test_rows_start_with_the_sessions_targets_and_formats_and_a_context_may_bring_its_models(
        monkeypatch):
    monkeypatch.setattr(detecting, "candidates", lambda *a, **k: pytest.fail("asked again"))
    ctx = make_ctx()
    ctx.candidates = list(CANDIDATES)  # the demo's canned context brings its own
    (link,) = review.prepare([LINK], ctx, targets=["ja", "zh-Hant"], formats=["srt", "ass"]).rows
    assert (link.targets, link.formats) == (("ja", "zh-Hant"), ("srt", "ass"))


def test_a_link_that_names_no_youtube_video_fails_its_row(candidates):
    (bad,) = review.prepare(["https://youtube.com/watch?v=short"], make_ctx()).rows
    assert bad.state == "failed" and "one YouTube video" in bad.error


@pytest.mark.media
def test_adding_probes_each_file_and_waits_to_sample_it(tmp_path, candidates):
    clip = make_clip(tmp_path, "Show - S01E01.mkv", seconds=3)
    (r1,) = review.prepare([str(clip)], make_ctx()).rows
    assert (r1.name, r1.folder, r1.state) == ("Show - S01E01.mkv", str(tmp_path), "waiting")
    assert 2900 < r1.duration_ms < 3200 and r1.audio_index == 0


@pytest.mark.media
def test_a_file_that_cannot_be_probed_fails_its_row_without_naming_it(tmp_path, candidates):
    fake = tmp_path / "Secret Show.mkv"
    fake.write_text("not a video", encoding="utf-8")
    (r1,) = review.prepare([str(fake)], make_ctx()).rows
    assert r1.state == "failed" and r1.error and "Secret" not in r1.error + r1.hint


# Sampling (spec §10.2–10.4)


@pytest.fixture
def season(tmp_path):
    clip = make_clip(tmp_path, "clip.mkv", seconds=14, speech=SPEECH)
    paths = []
    for folder, n in (("Show", 1), ("Show", 2), ("Show", 3), ("Other", 1)):
        (tmp_path / folder).mkdir(exist_ok=True)
        paths.append(str(shutil.copy(clip, tmp_path / folder / f"{folder} S01E0{n}.mkv")))
    return paths


@pytest.mark.media
def test_the_first_two_files_of_each_folder_are_sampled_and_the_rest_inherit(season,
                                                                            candidates):
    engine = FakeEngine(detect={"ja": 0.9})
    ctx = make_ctx(engine)
    heard = []
    rv = review.sample(review.prepare(season, ctx), ctx,
                       on_row=lambda r: heard.append((r.id, r.state,
                                                      threading.current_thread().name)))
    assert [(i, s) for i, s, _ in heard] == [
        ("r1", "sampling"), ("r1", "ready"), ("r2", "sampling"), ("r2", "ready"),
        ("r3", "ready"), ("r4", "sampling"), ("r4", "ready")]
    assert {t for _, _, t in heard} == {threading.current_thread().name}
    assert [(r.sampled, r.inherited) for r in rv.rows] == [
        (True, False), (True, False), (False, True), (True, False)]
    assert all((r.state, r.language, r.transcribe, r.translate) == (
        "ready", "ja", "spark-turbo", "spark-gemma") for r in rv.rows)
    assert row(rv, "r1").detection.votes == ("ja", "ja", "ja")
    assert row(rv, "r3").detection is None
    assert [c[0] for c in engine.calls] == ["detect"] * 9  # three windows, three files
    assert review.problems(rv) == {}


@pytest.mark.media
def test_whisper_hearing_chinese_asks_mandarin_or_cantonese_and_the_answer_suggests(season,
                                                                                  candidates):
    ctx = make_ctx(FakeEngine(detect={"zh": 0.9}))
    rv = review.sample(review.prepare(season[:3], ctx), ctx)
    assert all((r.language, r.ask_zh_yue, r.transcribe) == (None, True, None) for r in rv.rows)
    assert "Mandarin or Cantonese" in row(rv, "r3").warning and row(rv, "r3").inherited
    assert review.problems(rv) == {f"r{n}": "Mandarin or Cantonese? Pick one" for n in (1, 2, 3)}
    rv = review.apply_to_all(review.choose(rv, "r1", language="yue"), "r1", "language")
    assert all((r.language, r.ask_zh_yue, r.transcribe) == ("yue", False, "spark-turbo")
               for r in rv.rows)
    assert "weak on Cantonese" in row(rv, "r2").warning
    assert review.problems(rv) == {}


@pytest.mark.media
def test_sampled_files_that_disagree_leave_the_rest_of_the_folder_to_the_person(season,
                                                                              candidates):
    ctx = make_ctx(FakeEngine(detect=[{"ja": 0.9}] * 3 + [{"en": 0.9}] * 3))
    rv = review.sample(review.prepare(season[:3], ctx), ctx)
    assert [r.language for r in rv.rows] == ["ja", "en", None]
    assert not row(rv, "r3").inherited and "don't agree" in row(rv, "r3").warning
    assert review.problems(rv) == {"r3": "pick the language"}


@pytest.mark.media
def test_with_no_local_detector_the_language_is_the_persons_and_no_audio_leaves(season,
                                                                              candidates):
    candidates[:] = [replace(c, available=False, reason="SPARK down")
                     if c.name.startswith("spark") else c for c in CANDIDATES]
    cloud = FakeEngine(name="openai", detect={"ja": 0.9})
    ctx = make_ctx()
    ctx.engines["openai-whisper"] = cloud
    rv = review.sample(review.prepare(season[:1], ctx), ctx)
    assert row(rv, "r1").language is None and "pick" in row(rv, "r1").warning
    assert cloud.calls == []


class DroppingEngine(FakeEngine):
    def detect_language(self, chunk):
        self.calls.append(("detect", chunk.index))
        raise EngineError("connection", "couldn't reach the server",
                          hint="is `make tunnel` running?")


@pytest.mark.media
def test_a_detector_that_drops_leaves_the_language_to_the_person_with_the_fix(season,
                                                                            candidates):
    ctx = make_ctx(DroppingEngine())
    rv = review.sample(review.prepare(season[:1], ctx), ctx)
    assert (row(rv, "r1").state, row(rv, "r1").language) == ("ready", None)
    assert "couldn't reach the server" in row(rv, "r1").warning
    assert "make tunnel" in row(rv, "r1").hint


@pytest.mark.media
def test_a_cancelled_sampling_stops_before_the_next_file(season, candidates):
    from vid2sub.pipeline import Cancelled
    engine = FakeEngine(detect={"ja": 0.9})
    ctx = make_ctx(engine)
    with pytest.raises(Cancelled):
        review.sample(review.prepare(season, ctx), ctx, cancelled=lambda: bool(engine.calls))
    assert len(engine.calls) == 3


# Suggestions (spec §10.4, §11.2, §17.4)


def test_a_model_whose_server_is_down_is_still_suggested_and_marked_never_passed_over():
    down = [replace(c, available=False, reason=DOWN, unreachable=True)
            if c.name.startswith("spark") else c for c in CANDIDATES]
    down[2] = replace(down[2], available=True, reason="")  # the Mac's Qwen could run now
    rv = review.Review(rows=(file_row(1, targets=("ja",)),), candidates=tuple(down),
                       transcribers=review.model_choices(CONFIG, down, "transcribe"),
                       translators=review.model_choices(CONFIG, down, "translate"))
    rv = review.choose(rv, "r1", language="en")
    assert (row(rv, "r1").transcribe, row(rv, "r1").translate) == ("spark-turbo", "spark-gemma")
    assert "spark-turbo can't run now" in row(rv, "r1").warning and "make tunnel" in row(
        rv, "r1").warning
    assert rv.transcribers[0] == review.ModelChoice(
        "spark-turbo", "Whisper large-v3-turbo", rv.transcribers[0].good_for, False, DOWN)


def test_an_english_episode_with_english_targets_needs_no_translation_model():
    rv = review.choose(reviewed(file_row(1)), "r1", language="en")
    assert row(rv, "r1").translate is None
    assert review.problems(rv) == {}


# Allow cloud (spec §7.2)


def test_allow_cloud_starts_unticked_every_time_and_nothing_can_preset_it(candidates,
                                                                          monkeypatch):
    monkeypatch.setenv("VID2SUB_ALLOW_CLOUD", "1")
    ctx = make_ctx(allow_cloud=True)  # even a context that allows the cloud
    rv = review.prepare([LINK], ctx)
    assert rv.allow_cloud is False
    assert review.run_options(rv, "r1", ctx.options).allow_cloud is False
    rv = review.set_allow_cloud(rv, True)
    assert review.run_options(rv, "r1", RunOptions()).allow_cloud is True
    assert review.prepare([LINK], ctx).allow_cloud is False  # the next review starts unticked


@pytest.mark.parametrize("toml", ["allow_cloud = true\n", "[defaults]\nallow_cloud = true\n",
                                  "[privacy]\nallow_cloud = true\n",
                                  "[server]\nallow_cloud = true\n"])
def test_no_config_key_can_tick_allow_cloud(tmp_path, toml):
    path = tmp_path / "vid2sub.toml"
    path.write_text(toml, encoding="utf-8")
    with pytest.raises(ConfigError, match="allow_cloud"):
        load_config(path)


def test_suggestions_are_local_and_a_cloud_pick_waits_for_the_box():
    local_down = [replace(c, available=False, reason="SPARK_API_KEY isn't set")
                  if c.name.startswith("spark") else c for c in CANDIDATES]
    rv = review.Review(rows=(file_row(1),), candidates=tuple(local_down),
                       transcribers=review.model_choices(CONFIG, local_down, "transcribe"),
                       translators=review.model_choices(CONFIG, local_down, "translate"))
    rv = review.choose(rv, "r1", language="ja")
    assert row(rv, "r1").transcribe is None and row(rv, "r1").translate is None
    assert review.problems(rv) == {"r1": "pick a transcription model"}
    rv = review.choose(rv, "r1", transcribe="openai-whisper", translate="openai-gpt")
    assert review.problems(rv) == {"r1": "openai-whisper is a cloud model: tick Allow cloud "
                                         "models for this run, or pick a local one"}
    rv = review.set_allow_cloud(rv, True)
    assert review.problems(rv) == {}
    assert review.run_options(rv, "r1", RunOptions()).allow_cloud is True


# Choosing and "apply to all" (spec §10.5, §19.2)


def test_apply_to_all_copies_one_rows_choice_to_every_ready_row():
    rv = reviewed(file_row(1, language="ja", transcribe="spark-turbo", translate="spark-gemma"),
                  file_row(2, language="ja", transcribe="spark-turbo", translate="spark-gemma"),
                  file_row(3, state="sampling"), file_row(4, state="failed", error="no audio"))
    rv = review.choose(rv, "r1", targets=["en", "zh-Hant"], formats=["srt", "ass"])
    for field in ("targets", "formats"):
        rv = review.apply_to_all(rv, "r1", field)
    assert [(r.targets, r.formats) for r in rv.rows] == [
        (("en", "zh-Hant"), ("srt", "ass")), (("en", "zh-Hant"), ("srt", "ass")),
        (("en",), ("srt",)), (("en",), ("srt",))]


def test_choosing_a_language_suggests_its_models_unless_they_are_chosen_too():
    rv = reviewed(file_row(1, language="ja", transcribe="spark-turbo", translate="spark-gemma"))
    rv = review.choose(rv, "r1", language="ko", transcribe="openai-whisper")
    assert (row(rv, "r1").language, row(rv, "r1").transcribe) == ("ko", "openai-whisper")
    assert review.choose(rv, "r1", audio_track=1).rows[0].audio_index == 1


@pytest.mark.parametrize("changes", [
    {"language": "xx-secret"}, {"language": None}, {"transcribe": "spark-gemma"},
    {"translate": "spark-turbo"}, {"targets": ["xx-secret"]}, {"targets": "en"},
    {"formats": []}, {"formats": ["xx-secret"]}, {"script": "xx-secret"},
    {"audio_track": 7}, {"audio_track": True}, {"glossary": "xx-secret"}])
def test_a_choice_that_cannot_be_made_is_refused_without_echoing_it(changes):
    rv = reviewed(file_row(1, language="ja", transcribe="spark-turbo", translate="spark-gemma"))
    with pytest.raises(ReviewError) as err:
        review.choose(rv, "r1", **changes)
    assert "xx-secret" not in str(err.value) and "glossary" not in str(err.value)


def test_cantonese_takes_no_script_and_choosing_it_drops_one():
    rv = reviewed(file_row(1, language="zh", script="hant", transcribe="spark-turbo",
                           translate="spark-gemma"))
    assert row(review.choose(rv, "r1", language="yue"), "r1").script is None
    with pytest.raises(ReviewError):
        review.choose(review.choose(rv, "r1", language="yue"), "r1", script="hans")


def test_a_row_still_sampling_or_unknown_cannot_be_changed():
    rv = reviewed(file_row(1, state="sampling"))
    with pytest.raises(ReviewError, match="still being sampled"):
        review.choose(rv, "r1", language="ja")
    with pytest.raises(ReviewError, match="no such file"):
        review.choose(rv, "r9", language="ja")


def test_run_options_carry_each_rows_choices_on_top_of_the_base():
    rv = reviewed(file_row(1, language="zh", script="hant", transcribe="spark-turbo",
                           translate="spark-gemma", targets=("en", "ja"),
                           formats=("srt", "ass"), audio_track=1))
    opts = review.run_options(rv, "r1", RunOptions(wait_on_connection_s=60, skip_existing=True))
    assert (opts.source_lang, opts.model, opts.translate_model, opts.script, opts.targets,
            opts.formats, opts.audio_track, opts.allow_cloud, opts.wait_on_connection_s,
            opts.skip_existing) == ("zh", "spark-turbo", "spark-gemma", "hant", ["en", "ja"],
                                    ["srt", "ass"], 1, False, 60, True)
    with pytest.raises(ReviewError, match="pick the language"):
        review.run_options(reviewed(file_row(1)), "r1", RunOptions())


# Review Focus 2: a row the person changes while sampling runs on (spec §10.5)


@pytest.mark.media
def test_a_row_changed_while_sampling_runs_on_keeps_the_persons_choice(season, candidates):
    ctx = make_ctx(FakeEngine(detect={"ja": 0.9}))
    shown = review.prepare(season, ctx)  # what the screen holds, changed only by its loop
    arrived: SimpleQueue[Row] = SimpleQueue()
    changed = threading.Event()

    def on_row(r: Row) -> None:  # the sampling thread: the row is handed to the screen's loop
        arrived.put(r)
        if (r.id, r.state) == ("r2", "sampling"):
            assert changed.wait(10)  # r2 samples on while the person changes r1

    sampler = threading.Thread(target=review.sample, args=(shown, ctx),
                               kwargs={"on_row": on_row})
    sampler.start()
    while row(shown, "r1").state != "ready":
        shown = review.with_row(shown, arrived.get(timeout=10))
    shown = review.choose(shown, "r1", language="ko", transcribe="openai-whisper")
    changed.set()
    sampler.join(30)
    while not arrived.empty():
        shown = review.with_row(shown, arrived.get())
    assert (row(shown, "r1").language, row(shown, "r1").transcribe) == ("ko", "openai-whisper")
    assert [(r.id, r.state, r.language, r.inherited) for r in shown.rows[1:]] == [
        ("r2", "ready", "ja", False), ("r3", "ready", "ja", True), ("r4", "ready", "ja", False)]


# Review Focus 4: windows that land on music or silence (spec §10.2–10.3)


@pytest.mark.media
def test_a_file_with_no_speech_asks_the_detector_nothing_and_leaves_the_language_open(
        tmp_path, candidates):
    engine = FakeEngine(detect={"ja": 0.9})
    ctx = make_ctx(engine)
    tone = make_clip(tmp_path, "Theme S01E01.mkv", seconds=14)  # a sine tone: no speech in it
    rv = review.sample(review.prepare([str(tone)], ctx), ctx)
    assert engine.calls == []  # no window, so no vote
    assert row(rv, "r1").language is None
    assert row(rv, "r1").warning == "no language could be detected"
    assert review.problems(rv) == {"r1": "pick the language"}


@pytest.mark.media
def test_windows_that_hear_no_speech_dont_vote_and_one_vote_left_says_it_is_unsure(
        season, candidates):
    ctx = make_ctx(FakeEngine(detect=[{}, {}, {"ja": 0.9}]))
    rv = review.sample(review.prepare(season[:1], ctx), ctx)
    found = row(rv, "r1").detection
    assert (found.votes, found.confidence, found.uncertain) == ((None, None, "ja"), 0.3, True)
    assert row(rv, "r1").warning.startswith("only 30% sure it's ja")
    assert review.problems(rv) == {}  # an uncertain detection can still Start (Decision 5)
```

- [ ] **Step 2: Run it; watch it fail.** `uv run pytest tests/test_review.py -q`. Expected:
  `E   ImportError: cannot import name 'review' from 'vid2sub' (…/src/vid2sub/__init__.py)` and
  `1 error`.
- [ ] **Step 3: Write the code,** `src/vid2sub/review.py`:

```python
"""The Review screen's backend: what was added, sampled and suggested (spec §10, §19.2, S40).

Adding files probes each in seconds (§10.1), and each row starts with the session's targets and
formats, which the settings drawer changes (§5.4). The first two files of each folder are then
sampled in the background: decoded, their speech found, and three ~20 s windows of it
language-identified by the best detector on this machine or your own servers (§10.2–10.3,
`detect.detect`); the votes give a language, a confidence and a "mixed" flag; a file with no speech
gives no window and no vote, and the row leaves the language to the person. Whisper often labels
Cantonese `zh`, so when Whisper says `zh` the row asks "Mandarin or Cantonese?". The catalog's route
then suggests a transcription and a translation model (§10.4, §11.2) as M1's pipeline picks them: a
model whose server isn't answering is never passed over for the next one (§17.4), so it is suggested
anyway, greyed with its reason, and the queue waits for it when the job runs. Suggestions are local
only: **Allow cloud models for this run** starts unticked every time and nothing in `vid2sub.toml`
or the environment can tick it (§7.2), sampling sends no audio to a cloud detector, and a cloud
model is only ever the person's own pick, which Start refuses until the box is ticked. The rest of a
folder inherits its sampled files' choices when they agree (§10.5), as M1's runs inherit two
confident votes; when they don't, the person picks. A YouTube link isn't sampled: its language and
models are decided when it runs, as `vid2sub run` decides them. Each change makes a new `Review`
(they are frozen), so a reactive value holding one sees it, and `choose`, `apply_to_all` and
`problems` are pure. Rows are named `r1`, `r2`… for the screen, never by path; a choice that can't
be made is refused without echoing it, and nothing here logs (§6.8).
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal

from vid2sub import detect as detecting
from vid2sub.catalog import CATALOG, Candidate, suggest
from vid2sub.config import Config, ConfigError
from vid2sub.detect import Detection
from vid2sub.engines.base import EngineError
from vid2sub.media import youtube
from vid2sub.media.decode import SAMPLES_PER_MS, decode_to_wav, encode_flac, read_wav, to_float
from vid2sub.media.probe import Probe, ProbeError, pick_track, probe
from vid2sub.media.tools import ToolFailed, ToolMissing
from vid2sub.media.vad import speech_regions
from vid2sub.pipeline import Cancelled, RunContext, RunOptions
from vid2sub.subs import langs, naming

RowState = Literal["waiting", "sampling", "ready", "failed"]
FIELDS = ("language", "transcribe", "translate", "targets", "formats", "script", "audio_track")
SHARED_FIELDS = ("language", "transcribe", "translate", "targets", "formats", "script")
SAMPLED_PER_FOLDER = 2
FORMATS = ("srt", "ass")


class ReviewError(ValueError):
    """A choice, or a Start, that can't be made; the reason is fit to show and echoes nothing."""


@dataclass(frozen=True)
class ModelChoice:
    name: str  # the model's name in vid2sub.toml
    title: str  # the catalog's title, or the name for a model the catalog doesn't know
    good_for: str  # the catalog's one-liner
    available: bool
    reason: str = ""  # why it can't run now ("install vid2sub[mac]…", the server's error)
    cloud: bool = False


@dataclass(frozen=True)
class Row:
    id: str  # r1, r2… in the order added: what the screen sends back
    path: str  # the file's full path, or the link: for the queue, never for a log
    name: str  # the bare file name, or "YouTube video <id>"
    folder: str  # the file's folder: rows that inherit from each other
    link: bool = False
    state: RowState = "waiting"
    sampled: bool = False  # one of the first two files of its folder
    inherited: bool = False  # its language and models came from its folder's sampled files
    duration_ms: int | None = None
    probe: Probe | None = None
    audio_track: int | None = None  # the person's pick; None: §8.4's pick for the language
    detection: Detection | None = None
    language: str | None = None
    ask_zh_yue: bool = False  # Whisper heard `zh`: "Mandarin or Cantonese?"
    transcribe: str | None = None
    translate: str | None = None
    targets: tuple[str, ...] = ()
    formats: tuple[str, ...] = ()
    script: str | None = None  # Mandarin only: "hant" or "hans"; None for the default
    keep_video: bool = False  # a link: keep the whole video, not only its audio
    warning: str = ""  # an uncertain detection, a weak or unavailable model
    error: str = ""  # why it can't run (state "failed")
    hint: str = ""  # the fix, for the warning or the error

    @property
    def audio_index(self) -> int | None:
        """The audio track the job will use: the person's pick, else the language's (§8.4)."""
        if self.probe is None:
            return None
        return pick_track(self.probe, self.language, self.audio_track).index


@dataclass(frozen=True)
class Review:
    rows: tuple[Row, ...]
    candidates: tuple[Candidate, ...] = ()
    transcribers: tuple[ModelChoice, ...] = ()  # the pickers: every configured model
    translators: tuple[ModelChoice, ...] = ()
    allow_cloud: bool = False  # "Allow cloud models for this run": unticked every time (§7.2)


def _never() -> bool:
    return False


def model_choices(config: Config, candidates: Sequence[Candidate],
                  task: Literal["transcribe", "translate"]) -> tuple[ModelChoice, ...]:
    """Every configured model for `task`, in `vid2sub.toml`'s order, with whether it can run now
    and why not (spec §10.4)."""
    out = []
    for c in candidates:
        if config.models[c.name].task != task:
            continue
        entry = CATALOG.get(c.catalog or "")
        out.append(ModelChoice(c.name, entry.title if entry else c.name,
                               entry.good_for if entry else "", c.available, c.reason,
                               _is_cloud(c)))
    return tuple(out)


def prepare(inputs: Sequence[str], ctx: RunContext, *, keep_video: bool = False,
            targets: Sequence[str] | None = None,
            formats: Sequence[str] | None = None) -> Review:
    """One row per input: each file probed, each link ready to run. `inputs` are what the Add
    screen took (`browse.expand`'s paths) or YouTube links. Each row starts with `targets` and
    `formats`, the session's defaults that the settings drawer changes (§5.4), else
    `vid2sub.toml`'s. The models are the context's own candidates where it has them (the demo's
    canned ones), else each configured model checked now. Blocks: ffprobe, and the model list
    of each local server."""
    cands = tuple(ctx.candidates if ctx.candidates is not None
                  else detecting.candidates(ctx.config, ctx.keys))
    targets = tuple(naming.target_track(t)
                    for t in (ctx.config.defaults.targets if targets is None else targets))
    formats = tuple(ctx.config.defaults.formats if formats is None else formats)
    rows = []
    for n, source in enumerate(inputs, 1):
        base = Row(f"r{n}", source, "", "", targets=targets, formats=formats)
        rows.append(_link(base, keep_video) if youtube.is_url(source) else _probed(base, ctx))
    return Review(tuple(rows), cands, model_choices(ctx.config, cands, "transcribe"),
                  model_choices(ctx.config, cands, "translate"))


def sample(review: Review, ctx: RunContext, *, on_row: Callable[[Row], None] | None = None,
           cancelled: Callable[[], bool] = _never) -> Review:
    """Samples the first two waiting files of each folder and lets the rest inherit (§10.2–10.5).

    Blocks for seconds per file (ffmpeg, the VAD, three detections), so the server runs it off
    the event loop. `on_row(row)` is called on this calling thread each time a row changes
    (sampling, then ready), so the screen merges each with `with_row`; only rows that aren't
    ready change, so a choice the person made meanwhile is kept. `cancelled` is checked before
    each file; when it says so, Cancelled is raised and the rows not reached stay waiting.
    """
    rows = {r.id: r for r in review.rows}
    folders: dict[str, list[str]] = {}
    for r in review.rows:
        if r.state == "waiting":
            folders.setdefault(r.folder, []).append(r.id)

    def changed(new: Row) -> None:
        rows[new.id] = new
        if on_row is not None:
            on_row(new)

    for ids in folders.values():
        picked, rest = ids[:SAMPLED_PER_FOLDER], ids[SAMPLED_PER_FOLDER:]
        for rid in picked:
            if cancelled():
                raise Cancelled()
            changed(replace(rows[rid], state="sampling", sampled=True))
            changed(_sampled(rows[rid], review, ctx))
        for rid in rest:
            changed(_inherit(rows[rid], [rows[i] for i in picked]))
    return replace(review, rows=tuple(rows[r.id] for r in review.rows))


def with_row(review: Review, row: Row) -> Review:
    """The review with `row` in place of the row with its id."""
    if not any(r.id == row.id for r in review.rows):
        raise ReviewError("there's no such file in this review")
    return replace(review, rows=tuple(row if r.id == row.id else r for r in review.rows))


def choose(review: Review, row_id: str, **changes: Any) -> Review:
    """The person's choices for one row, each checked (they come from the browser). Choosing a
    language answers "Mandarin or Cantonese?" and suggests its models, unless they are chosen in
    the same call; Cantonese takes no script."""
    row = _ready(review, row_id)
    if not set(changes) <= set(FIELDS):
        raise ReviewError("there's no such choice")
    checked = {field: _check(review, row, field, value) for field, value in changes.items()}
    new = replace(row, **checked)
    if "language" in checked:
        new = replace(new, ask_zh_yue=False,
                      script=None if new.language == "yue" else new.script)
        new = _suggested(new, review, transcribe="transcribe" not in checked,
                         translate="translate" not in checked)
    elif "targets" in checked and "translate" not in checked and new.translate is None:
        new = _suggested(new, review, transcribe=False, translate=True)
    return with_row(review, new)


def apply_to_all(review: Review, row_id: str, field: str) -> Review:
    """Copies one row's choice to every other ready row ("apply to all", §10.5); a row it can't
    apply to (a script, for a Cantonese row) keeps its own."""
    if field not in SHARED_FIELDS:
        raise ReviewError("that choice can't be applied to every file")
    value = getattr(_ready(review, row_id), field)
    if field == "language" and value is None:
        raise ReviewError("this file has no language to apply yet")
    for other in review.rows:
        if other.id == row_id or other.state != "ready":
            continue
        try:
            review = choose(review, other.id, **{field: value})
        except ReviewError:
            continue
    return review


def set_allow_cloud(review: Review, allowed: bool) -> Review:
    """The **Allow cloud models for this run** box: the only way the run may use a cloud model."""
    return replace(review, allow_cloud=allowed is True)


def problems(review: Review) -> dict[str, str]:
    """What stops Start, by row id: empty when every row can run. A failed row isn't started, so
    it isn't a problem here; its error is on the row."""
    out = {}
    for row in review.rows:
        problem = _problem(review, row)
        if problem:
            out[row.id] = problem
    return out


def run_options(review: Review, row_id: str, base: RunOptions) -> RunOptions:
    """The job's options: the row's choices on top of `base` (the server's own options), with
    the cloud allowed only when this review's box is ticked."""
    row = _row(review, row_id)
    if row.state == "failed":
        raise ReviewError(row.error or "this file can't run")
    problem = _problem(review, row)
    if problem:
        raise ReviewError(problem)
    return replace(base, source_lang=row.language, targets=list(row.targets),
                   formats=list(row.formats), model=row.transcribe,
                   translate_model=row.translate, script=row.script,
                   audio_track=row.audio_track, keep_video=row.keep_video,
                   allow_cloud=review.allow_cloud)


def _is_cloud(c: Candidate) -> bool:
    return c.cloud or (c.catalog in CATALOG and CATALOG[c.catalog].cloud)


def _link(row: Row, keep_video: bool) -> Row:
    try:
        name = f"YouTube video {youtube.video_id(row.path)}"
    except youtube.NotYouTube as err:
        return replace(row, name="YouTube link", state="failed", error=str(err))
    return replace(row, name=name, link=True, state="ready", keep_video=keep_video)


def _probed(row: Row, ctx: RunContext) -> Row:
    path = Path(row.path)
    row = replace(row, name=path.name, folder=str(path.parent))
    try:
        with tempfile.TemporaryDirectory(prefix="vid2sub-") as scratch:
            p = probe(path, ctx.tools, scratch=Path(scratch))
    except (ProbeError, ToolMissing) as err:
        return replace(row, state="failed", error=str(err))
    except ToolFailed:
        return replace(row, state="failed", error="ffprobe couldn't read this file",
                       hint="check that it plays in a media player")
    except OSError as err:  # never err.filename (spec §6.8)
        return replace(row, state="failed", error="couldn't read this file"
                       + (f" ({err.strerror})" if err.strerror else ""))
    return replace(row, duration_ms=p.duration_ms, probe=p)


def _sampled(row: Row, review: Review, ctx: RunContext) -> Row:
    """One file decoded, its speech found and three windows identified (§10.2–10.3)."""
    detector = detecting.choose_detector(review.candidates, allow_cloud=False)
    if detector is None:
        return replace(row, state="ready",
                       warning="no model on this machine or your servers can detect the "
                               "language now: pick it",
                       hint="`vid2sub models` says why each can't run")
    try:
        with tempfile.TemporaryDirectory(prefix="vid2sub-") as tmp:
            scratch = Path(tmp)
            wav = scratch / "audio.wav"
            decode_to_wav(Path(row.path), pick_track(row.probe, None, row.audio_track), wav,
                          ctx.tools, scratch=scratch, duration_ms=row.probe.duration_ms)
            samples = read_wav(wav)
            found = detecting.detect(ctx.engine(detector), samples,
                                     speech_regions(to_float(samples)),
                                     len(samples) // SAMPLES_PER_MS,
                                     encode=lambda s: encode_flac(s, ctx.tools, scratch=scratch))
    except EngineError as err:
        return replace(row, state="ready", warning=f"couldn't detect the language: {err}",
                       hint=err.hint or "pick the language")
    except (ToolFailed, ToolMissing, ProbeError, ConfigError) as err:
        return replace(row, state="failed", error=f"couldn't sample this file ({err})"
                       if not isinstance(err, ToolFailed) else "ffmpeg couldn't decode this file",
                       hint="check that it plays in a media player")
    except OSError as err:  # never err.filename (spec §6.8)
        return replace(row, state="failed", error="couldn't read this file"
                       + (f" ({err.strerror})" if err.strerror else ""))
    row = replace(row, state="ready", detection=found, ask_zh_yue=found.ambiguous_zh_yue,
                  language=None if found.ambiguous_zh_yue else found.language)
    if row.language is None:
        return replace(row, warning=found.reason())
    return _suggested(row, review, transcribe=True, translate=True, also=found.reason())


def _inherit(row: Row, sampled: Sequence[Row]) -> Row:
    """The rest of a folder takes its sampled files' language and models when they agree."""
    first = sampled[0]
    answers = {(s.language, s.ask_zh_yue) for s in sampled}
    if all(s.state == "ready" for s in sampled) and len(answers) == 1 and (
            first.language or first.ask_zh_yue):
        return replace(row, state="ready", inherited=True, language=first.language,
                       ask_zh_yue=first.ask_zh_yue, transcribe=first.transcribe,
                       translate=first.translate, warning=first.warning, hint=first.hint)
    heard = sorted({s.language for s in sampled if s.language})
    reason = ("the sampled files in this folder don't agree on a language: pick one"
              if len(heard) > 1 else
              "no language was found in this folder's sampled files: pick one")
    return replace(row, state="ready", warning=reason)


def _route(lang: str, cands: Sequence[Candidate], task: str) -> tuple[str | None, str]:
    """The route's pick were every server answering (§17.4: never the next one down), and what
    to say about it: a weak pairing, or why it can't run now."""
    hoped = [replace(c, available=True, reason="") if c.unreachable else c for c in cands]
    s = suggest(lang, hoped, task, allow_cloud=False)
    if s.model is None:
        return None, f"no local {task} model can run now: pick one"
    notes = [s.warning] if s.warning else []
    real = next(c for c in cands if c.name == s.model)
    if not real.available:
        notes.append(f"{s.model} can't run now: {real.reason}")
    return s.model, "; ".join(notes)


def _needs_translation(row: Row) -> bool:
    return any(naming.track(t).lang != row.language for t in row.targets)


def _suggested(row: Row, review: Review, *, transcribe: bool, translate: bool,
               also: str = "") -> Row:
    notes = [also] if also else []
    changes: dict[str, Any] = {}
    if transcribe:
        changes["transcribe"], note = _route(row.language, review.candidates, "transcribe")
        notes.append(note)
    if translate:
        changes["translate"], note = (_route(row.language, review.candidates, "translate")
                                      if _needs_translation(row) else (None, ""))
        notes.append(note)
    return replace(row, **changes, warning="; ".join(n for n in notes if n))


def _row(review: Review, row_id: str) -> Row:
    for row in review.rows:
        if row.id == row_id:
            return row
    raise ReviewError("there's no such file in this review")


def _ready(review: Review, row_id: str) -> Row:
    row = _row(review, row_id)
    if row.state in ("waiting", "sampling"):
        raise ReviewError("this file is still being sampled")
    if row.state == "failed":
        raise ReviewError("this file can't run: " + (row.error or "it failed"))
    return row


def _names(choices: Sequence[ModelChoice]) -> set[str]:
    return {c.name for c in choices}


def _check(review: Review, row: Row, field: str, value: Any) -> Any:
    """One choice from the browser, checked; refused without echoing it (spec §6.8)."""
    if field == "language":
        if not isinstance(value, str) or value not in langs.LANGS:
            raise ReviewError("that isn't a language vid2sub knows")
        return value
    if field in ("transcribe", "translate"):
        choices = review.transcribers if field == "transcribe" else review.translators
        if field == "translate" and value is None:
            return None
        if not isinstance(value, str) or value not in _names(choices):
            raise ReviewError(f"that isn't a {field} model in vid2sub.toml")
        return value
    if field == "targets":
        if not isinstance(value, (list, tuple)) or not all(isinstance(t, str) for t in value):
            raise ReviewError("targets are a list of languages")
        try:
            return tuple(dict.fromkeys(naming.target_track(t) for t in value))
        except naming.UnknownTrack:
            raise ReviewError("one of the targets isn't a language vid2sub writes") from None
    if field == "formats":
        if (not isinstance(value, (list, tuple)) or not value
                or not all(isinstance(f, str) and f in FORMATS for f in value)):
            raise ReviewError("formats are srt, ass or both")
        return tuple(dict.fromkeys(value))
    if field == "script":
        if value not in (None, "hant", "hans"):
            raise ReviewError("the script is hant (Traditional) or hans (Simplified)")
        language = row.language
        if value is not None and language == "yue":
            raise ReviewError("Cantonese subtitles are always in Traditional characters")
        return value
    # audio_track
    tracks = len(row.probe.audio) if row.probe else 0
    if value is not None and (isinstance(value, bool) or not isinstance(value, int)
                              or not 0 <= value < tracks):
        raise ReviewError("that file has no such audio track")
    return value


def _problem(review: Review, row: Row) -> str:
    if row.state == "failed":
        return ""
    if row.state in ("waiting", "sampling"):
        return "still being sampled"
    if row.ask_zh_yue:
        return "Mandarin or Cantonese? Pick one"
    if not row.link and row.language is None:
        return "pick the language"
    if not row.link and row.transcribe is None:
        return "pick a transcription model"
    if not row.link and row.translate is None and _needs_translation(row):
        return "pick a translation model, or no targets"
    cloud = {c.name for c in review.candidates if _is_cloud(c)}
    for name in (row.transcribe, row.translate):
        if name in cloud and not review.allow_cloud:
            return (f"{name} is a cloud model: tick Allow cloud models for this run, or pick a "
                    "local one")
    return ""
```

- [ ] **Step 4: Run the checks; they pass.** `uv run pytest tests/test_review.py -q` first
  (`39 passed`; three times: the Review Focus 2 test samples on a thread), then the guard
  checks, then `make check`. **Guard checks** (spec §7.2, §17.4), each reverted and restored,
  each with `uv run pytest tests/test_review.py -q`: in `run_options`, drop
  `allow_cloud=review.allow_cloud` (the base's cloud leaks through:
  `FAILED …test_allow_cloud_starts_unticked_every_time_and_nothing_can_preset_it` and
  `…test_suggestions_are_local_and_a_cloud_pick_waits_for_the_box`); in `_sampled`, choose the
  detector with `allow_cloud=True` (`FAILED
  …test_with_no_local_detector_the_language_is_the_persons_and_no_audio_leaves`); in `_route`,
  suggest over `cands` instead of `hoped` (the Mac's Qwen replaces the Spark that's down:
  `FAILED …test_a_model_whose_server_is_down_is_still_suggested_and_marked_never_passed_over`);
  in `_route`, suggest with `allow_cloud=True` (`FAILED
  …test_suggestions_are_local_and_a_cloud_pick_waits_for_the_box`); in `prepare`, take the
  candidates from `detecting.candidates(ctx.config, ctx.keys)` alone, and separately start
  every row with `ctx.config.defaults.targets` (each:
  `FAILED …test_rows_start_with_the_sessions_targets_and_formats_and_a_context_may_bring_its_models`).
  The Review Focus 2 and 4 tests pin what the code already does: sampling only ever sends a
  row that wasn't ready, which the person can't change, so their choice stands as later rows
  merge; a file with no speech gives no window and no vote; windows that hear nothing vote
  `None`, so one vote left is "only 30% sure". `make check`. Expected: `1166 passed, 7 skipped,
  38 deselected` twice, `Test Files  20 passed (20)` and `Tests  91 passed (91)`,
  `All checks passed!` and `no leaks found`.
- [ ] **Step 5: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(review): 🤖 Review samples the first two files of each folder, suggests local models, and the rest inherit

vid2sub.review (spec §10, §19.2, S40): prepare(inputs, ctx, targets=,
formats=) gives one row per input, each file probed (a link is ready at
once, decided when it runs), each starting with the session's targets and
formats (the settings drawer's, §5.4; vid2sub.toml's when none are
given), and the model pickers with whether each model can run now and
why not; a context that brings its own candidates (the demo's canned
models) isn't asked again. sample(review, ctx, on_row=…) decodes the first two waiting files
of each folder, finds their speech and identifies three windows with the
best local detector (detect.detect), then lets the rest of the folder
inherit when the sampled files agree; on_row runs on the calling thread
for each change, so the screen merges rows with with_row. Whisper's `zh`
asks "Mandarin or Cantonese?". Suggestions follow the catalog's route as
M1 picks it, a model whose server isn't answering is suggested anyway
with its reason (never the next one down, §17.4), and they are local
only: Allow cloud starts unticked in every Review, sampling never sends
audio to a cloud detector, a cloud model is only the person's pick, and
run_options takes the cloud from the review's box alone, never from the
server's options. choose and apply_to_all check every value from the
browser and echo none; problems says what stops Start.

Review Focus 2 and 4's halves here pin what the code already does: a
row the person changes while sampling runs on keeps their choice as the
later rows arrive and merge (sampling only ever sends a row that wasn't
ready, which the person can't change); a file with no speech gives no
window, asks the detector nothing and leaves the language to the person;
windows that hear nothing don't vote, so one vote left reads "only 30%
sure", uncertain but startable (Decision 5).

The new tests failed first with: ImportError: cannot import name
'review' from 'vid2sub'. Guard checks, each reverted and restored:
run_options taking the cloud from the base options, a detector chosen
with the cloud allowed, a route over the real candidates (passing over
the server that's down), suggestions allowed the cloud, prepare asking
for candidates a context brought, and rows starting with vid2sub.toml's
targets whatever the session's are, each make their tests fail.

Docs read: none beyond the code (detect.detect, choose_detector and
candidates; catalog.suggest; pipeline._candidates_that_work's rule of
waiting for the route's pick; media.decode, vad and probe; Phase 2's
web.settings.Session and runtime.job_runner, whose session defaults
Review's rows now start from).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md Task 3
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/review.py tests/test_review.py`, `git commit -F .git/COMMIT_MSG`, then
  `git log -1 --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 6: Write the failing tests.** In `tests/test_review.py`, add `import time` below
  `import threading`; replace `from vid2sub import review` with
  `from vid2sub import jobs, review`, and `from vid2sub.pipeline import RunContext, RunOptions`
  with `from vid2sub.pipeline import InputResult, RunContext, RunOptions`; then append, after
  two blank lines:

```python
# Start (spec §10.6, §7.2)


def until(check, timeout=5.0):
    end = time.monotonic() + timeout
    while not check():
        if time.monotonic() > end:
            raise AssertionError("timed out waiting")
        time.sleep(0.005)


def test_start_queues_each_row_with_its_own_options_on_the_shared_context(monkeypatch):
    seen = []

    def run_one(source, ctx):
        seen.append((source, ctx.options.source_lang, ctx.options.model, ctx.options.targets,
                     ctx.options.formats, ctx.options.allow_cloud,
                     ctx.chunk_cache is base.chunk_cache, ctx.engines is base.engines))
        return InputResult(input=source, status="done")

    monkeypatch.setattr(review, "run_one", run_one)
    base = make_ctx(targets=["ko"], formats=["ass"])  # as the session's would be: the row wins
    rv = reviewed(file_row(1, language="ja", transcribe="spark-turbo", translate="spark-gemma"),
                  file_row(2, language="ko", transcribe="openai-whisper",
                           translate="spark-gemma", targets=("en", "ja"),
                           formats=("srt", "ass")),
                  file_row(3, state="failed", error="this file has no audio track"),
                  allow_cloud=True)
    default = []
    queue = jobs.Queue(lambda source, event, cancelled: default.append(source))
    ids = review.start(rv, queue, base)
    until(lambda: all(j.state == "done" for j in queue.jobs()))
    queue.close()
    assert len(ids) == 2 and default == []
    assert seen == [
        ("/films/Show/Show S01E01.mkv", "ja", "spark-turbo", ["en"], ["srt"], True, True, True),
        ("/films/Show/Show S01E02.mkv", "ko", "openai-whisper", ["en", "ja"], ["srt", "ass"],
         True, True, True)]


def test_start_runs_each_row_through_the_runtimes_guard(monkeypatch):
    monkeypatch.setattr(review, "run_one", lambda source, ctx: InputResult(input=source,
                                                                           status="done"))
    guarded = []

    def guard(runner):
        def refuse(source, events, cancelled):  # as the demo's only_inside refuses
            guarded.append(source)
            return InputResult(input=source, status="failed", reason="the demo runs only its clip")
        return refuse

    rv = reviewed(file_row(1, language="ja", transcribe="spark-turbo", translate="spark-gemma"))
    queue = jobs.Queue(lambda source, event, cancelled: InputResult(input=source, status="done"))
    review.start(rv, queue, make_ctx(), guard=guard)
    until(lambda: queue.jobs()[0].state == "failed")
    queue.close()
    assert guarded == ["/films/Show/Show S01E01.mkv"]


def test_start_queues_nothing_while_any_row_has_a_problem():
    rv = reviewed(file_row(1, language="ja", transcribe="spark-turbo", translate="spark-gemma"),
                  file_row(2))
    queue = jobs.Queue(lambda source, event, cancelled: None)
    with pytest.raises(ReviewError, match="1 file"):
        review.start(rv, queue, make_ctx())
    queue.close()
    assert queue.jobs() == []


def test_an_engine_made_for_a_run_that_allowed_the_cloud_is_refused_to_one_that_doesnt():
    ctx = RunContext(config=CONFIG, tools=Tools.find(),
                     keys=KeyRing(environ={"OPENAI_API_KEY": "fake"}),
                     options=RunOptions(allow_cloud=True))
    ctx.engine("openai-whisper")
    later = replace(ctx, options=RunOptions(allow_cloud=False))
    with pytest.raises(EngineError) as err:
        later.engine("openai-whisper")
    assert err.value.kind == "cloud_not_allowed"
```

- [ ] **Step 7: Run them; watch them fail.** `uv run pytest tests/test_review.py -q -k
  "start or engine_made"`. Expected:
  `E       AttributeError: <module 'vid2sub.review' …> has no attribute 'run_one'` (twice),
  `E           AttributeError: module 'vid2sub.review' has no attribute 'start'`,
  `E       Failed: DID NOT RAISE EngineError` (the cached cloud engine), and
  `4 failed, 2 passed, 37 deselected`.
- [ ] **Step 8: Write the code.** In `src/vid2sub/pipeline.py`, replace
  `from vid2sub.engines.clients import KeyRing, RunPolicy` with
  `from vid2sub.engines.clients import KeyRing, RunPolicy, check_allowed`, and in
  `class RunContext`, replace

```python
    def engine(self, name: str) -> Engine:
        if name not in self.engines:
```

  with

```python
    def engine(self, name: str) -> Engine:
        """The model's engine, made once and shared by this context's copies. The cloud check
        runs on every call: a copy made for another job may not allow the cloud (spec §7.2),
        and an engine already made would otherwise skip `make_client`'s check."""
        entry = self.config.models.get(name)
        if entry is not None:
            check_allowed(name, entry, self.config, self.policy)
        if name not in self.engines:
```

  In `src/vid2sub/review.py`, in the module docstring, replace

```python
`problems` are pure. Rows are named `r1`, `r2`… for the screen, never by path; a choice that can't
be made is refused without echoing it, and nothing here logs (§6.8).
```

  with

```python
`problems` are pure. Start queues each row with its own options (`start`). Rows are named `r1`,
`r2`… for the screen, never by path; a choice that can't be made is refused without echoing it,
and nothing here logs (§6.8).
```

  Below `from vid2sub import detect as detecting`, add `from vid2sub import jobs`; replace
  `from vid2sub.pipeline import Cancelled, RunContext, RunOptions` with
  `from vid2sub.pipeline import Cancelled, RunContext, RunOptions, run_one`; and above
  `def _is_cloud(c: Candidate) -> bool:`, add:

```python
def runner_for(ctx: RunContext, options: RunOptions) -> jobs.Runner:
    """A job's runner: `run_one` with these options, on a copy of the server's context that
    shares its engines and finished chunks (spec §8.9)."""
    def run(source: str, events, cancelled) -> Any:
        return run_one(source, replace(ctx, options=options, events=events,
                                       cancelled=cancelled))
    return run


def start(review: Review, queue: jobs.Queue, ctx: RunContext, *,
          guard: Callable[[jobs.Runner], jobs.Runner] | None = None) -> list[str]:
    """Start (§10.6): every row that can run, queued in order, each with its own options on top
    of `ctx.options` (the row's targets and formats, not the session's as a job of the queue's
    own would take them); a failed row is left out. Nothing is queued while any row has a
    problem. `guard` wraps each row's runner (the demo's: only its clip). Returns the job ids."""
    found = problems(review)
    if found:
        n = len(found)
        raise ReviewError(f"{n} file{'s' if n != 1 else ''} still need{'' if n != 1 else 's'} a "
                          "choice: see the rows marked")
    ids = []
    for row in review.rows:
        if row.state != "failed":
            runner = runner_for(ctx, run_options(review, row.id, ctx.options))
            ids += queue.submit([row.path], runner=guard(runner) if guard else runner)
    return ids


```

- [ ] **Step 9: Run the checks; they pass.** `uv run pytest tests/test_review.py
  tests/test_jobs.py -q` first (`57 passed`; run it five times: the queue tests use threads),
  then the guard checks, then `make check`. **Guard checks**, each reverted and restored, each
  with `uv run pytest tests/test_review.py -q`: in `RunContext.engine`, replace the two lines
  `if entry is not None:` / `check_allowed(…)` with `pass` (`FAILED
  …test_an_engine_made_for_a_run_that_allowed_the_cloud_is_refused_to_one_that_doesnt`); in
  `start`, replace `if found:` with `if False:` (`FAILED
  …test_start_queues_nothing_while_any_row_has_a_problem`: the first row is queued before the
  second is refused); in `start`, submit `runner=runner` instead of
  `runner=guard(runner) if guard else runner` (`FAILED
  …test_start_runs_each_row_through_the_runtimes_guard`). `make check`. Expected:
  `1170 passed, 7 skipped, 38 deselected` twice, `Test Files  20 passed (20)` and
  `Tests  91 passed (91)`, `All checks passed!` and `no leaks found`.
- [ ] **Step 10: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(review): 🤖 Start queues each file with its own options, and a cloud engine is refused to a run that didn't allow it

review.start(review, queue, ctx, guard=) queues every row that can run,
in order, each with run_options on top of the server's options, through
review.runner_for(ctx, options): run_one on a copy of the server's
RunContext that shares its engines and finished chunks (spec §8.9),
submitted with Queue.submit(…, runner=) (Task 2's). The row's targets
and formats win: a runner of its own never takes the session's as the
queue's own runner does. `guard` wraps each row's runner (the runtime's
job_guard: the demo's only_inside). Nothing is queued while any row has
a problem; a failed row is left out.

Per-job options meant one context's engine cache now serves runs that
differ in Allow cloud, and make_client checks the cloud only when an
engine is made: a cloud engine made for a run that ticked the box would
serve a later one that didn't (spec §7.2). RunContext.engine now runs
clients.check_allowed on every call.

The new tests failed first with: AttributeError: module
'vid2sub.review' has no attribute 'start', and Failed: DID NOT RAISE
EngineError (the cached cloud engine). Guard checks, each reverted and
restored: without the check in RunContext.engine, with start ignoring
the problems, and with start skipping the guard, their tests fail.

Docs read: none beyond the code (jobs.Queue with Task 2's runner=,
pipeline.RunContext and clients.check_allowed and transcription_client,
where the cloud check ran only at construction; Phase 2's
runtime.job_runner, whose session defaults a row's own runner skips).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md Task 3
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/pipeline.py src/vid2sub/review.py tests/test_review.py`,
  `git commit -F .git/COMMIT_MSG`, then `git log -1 --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 11: Review, look forward, close.** The Tier 2 review from `$(cat .git/TASK_BASE)`
  (`AGENTS.md`, *Reviews*). Worth the reviewers' time: that no path from sampling reaches a
  cloud model (detection, suggestion, `run_options`, and the engine cache now checked per run);
  that a model whose server is down is suggested, never passed over (§17.4); that `on_row`
  never replaces a row the person could already change. The forward review over Tasks 4, 5, 6
  and 8: Task 4 calls everything listed under *What Task 4 calls*, through the runtime,
  renders rows through its own view (never `Row.path`), and draws **Allow cloud** from
  `Review.allow_cloud`, never a setting; Task 5's pause and resume keep each job's own runner
  (`Queue._runners`, Task 2's); Task 6's Jobs page shows jobs Review queued like any other;
  Task 8 may show `model_choices`. The docs this task made untrue: none expected (grep `docs/`
  and `README.md` for "Review" and "allow cloud"). Then the close, its own commit, holding this
  plan with this task's boxes ticked and **Now** set to `Task 4: The Review screen, open.`, and
  the spec's S40 row with "Phase and task" set to `Phase 3, Tasks 3–4`; S40 stays `planned`
  (its Playwright half is Task 4's). The message, in `.git/CLOSE_MSG`:

```text
docs(plan): 🤖 close Task 3: Sampling and suggestions for Review

Drift: none
Rulings: none
Phase-end: none
Forward: none
Tier: 2
Rounds: none
Findings: none

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md Task 3
Co-Authored-By: <the model's own line>
```

  `git add docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md
  docs/superpowers/specs/2026-10-14-vid2sub-design.md`, `git commit -F .git/CLOSE_MSG`.

***

### Task 4: The Review screen

**Tier:** 2 · **Scenarios:** S40

**Files:**
- Create: `frontend/src/components/ReviewPage.tsx`, `frontend/src/lib/review.ts`
- Modify: `src/vid2sub/web/episode.py` (`ReviewRefused`), `src/vid2sub/web/runtime.py` (Review's
  methods; Task 2's `add` goes), `src/vid2sub/web/views.py` (`review_view`),
  `src/vid2sub/web/server.py` (`Reviewer`; Add hands to Review; Review's inputs, output and
  message), `src/vid2sub/web/demo.py` (`CANNED_MODELS`), `frontend/src/types.ts`,
  `frontend/src/App.tsx`, `frontend/src/components/AddPage.tsx` (its note)
- Test: `tests/test_web_review.py`, `tests/test_web_add.py`, `frontend/src/lib/review.test.ts`,
  `tests/e2e/test_review.py`, `tests/e2e/test_add.py`

**Interfaces:**
- Consumes: Task 3's `vid2sub.review`, reached only through the runtime, since it imports the
  pipeline and isn't in the Pages bundle. `prepare` then `sample` run off the event loop; `on_row`
  runs on the sampling thread, so the server hops to the session's loop and merges with
  `with_row`; `cancelled` turns true when the person discards the review, adds again, starts it
  or closes the tab. `choose`, `apply_to_all`, `set_allow_cloud` and `problems` are pure and run
  on the loop. Start calls `review.start(review, queue, runtime.job_context,
  guard=runtime.job_guard)`. Task 2's `add` input, whose hand-off becomes Review. Add and Review
  show only where `capabilities.generate` is true (Phase 2 Decision 23).
- Produces:
  - `web.episode.ReviewRefused(Exception)`: a choice or a Start refused; fit to show, echoing
    nothing. Pure.
  - `web.runtime.Runtime` methods (Task 2's `add` is gone): `prepare(inputs, *, keep_video)
    -> Review` (rows start with the session's targets and formats; blocks: call through
    `blocking`); `sample(rv, *, on_row, cancelled) -> Review | None` (None once cancelled;
    blocks); `with_row(rv, row)`, `choose(rv, row_id, changes: dict)`, `apply_to_all(rv, row_id,
    field)`, `allow_cloud(rv, allowed)`, `problems(rv)` (pure; `ReviewRefused` from the first
    three refusing); `start_review(rv) -> list[str]` (`ReviewRefused` while a row has a problem;
    RuntimeError once the queue is closed).
  - `web.views.review_view(review, problems) -> dict`: `{"rows": [{"id", "name", "folder" (the
    bare folder name), "link", "state", "sampled", "inherited", "duration_ms", "audio":
    [{"index", "label"}], "audio_index", "detection": {"language", "confidence", "votes",
    "mixed"} | null, "language", "ask_zh_yue", "transcribe", "translate", "targets",
    "formats", "script", "keep_video", "warning", "error", "hint", "problem"}],
    "transcribers": [{"name", "title", "good_for", "available", "reason", "cloud"}],
    "translators": [...], "languages": [{"code", "name"}], "targets": [{"key", "label"}],
    "allow_cloud": bool, "can_start": bool}`; never a path.
  - The server (local only), one `Reviewer` per tab:
    - `add` (Task 2's) now begins a review of what it took and answers `add_result` with
      `added` the number of inputs; nothing is queued until Start.
    - output `review`: null, `{"preparing": true}` while Add's files are read, or
      `review_view`'s.
    - inputs `review_choose`: `{"row": str, "changes": {field: value}, "n": int}`;
      `review_apply`: `{"row": str, "field": str, "n": int}`; `review_cloud`: `{"allowed":
      bool, "n": int}`; `review_start`: `{"n": int}`; `review_discard`: `{"n": int}`. A refused
      one sends a `notice`, echoing nothing (`PICK_A_CHOICE` for a malformed request).
    - message `review_started`: `{"n": int | null, "jobs": int}`, after which `review` is null.
  - The page: a **Review** screen (`nav-review`); a finished Add opens it, and
    `review_started` opens Jobs. `ReviewPage({review: ReviewView | null, preparing: boolean,
    onChoose(row, changes), onApply(row, field), onCloud(allowed), onStart(), onDiscard()})`;
    `lib/review.ts`: `duration`, `heard`, `choiceLabel`, `toggled`, `Changes`, `withPending` (a
    choice shows at once until the engine's review comes back) and `isReview`. Test ids:
    `review-page`, `review-preparing`, `review-cloud`, `review-waiting`, `review-discard`,
    `review-start`, `review-rows`, `review-row` (`data-state`, `data-row`), `review-name`,
    `review-inherited`, `review-heard`, `review-error`, `review-audio`, `review-language`,
    `review-transcribe`, `review-translate`, `review-script`, `review-target-<key>`,
    `review-ass`, `review-all-<field>`, `review-warning`, `review-hint`, `review-problem`.
  - Decided here (proposed): **the demo's Review suggests its canned models,** under the catalog
    entries they stand in for (Whisper large-v3-turbo and Gemma 4, `demo.CANNED_MODELS`), so it
    samples and suggests without asking a server; its picker titles name those entries.
  - Decided here: leaving Review means Discard (or a newer Add, Start or closing the tab);
    switching screens keeps the review and its sampling.

- [ ] **Step 0: Record the base:** `git rev-parse HEAD > .git/TASK_BASE`.
- [ ] **Step 1: Write the failing tests,** `tests/test_web_review.py`:

```python
"""The Review screen's server (spec §10, §19.2, §7.2; S40; Review Focus 2): Add opens a review
whose rows fill in as the first two files of each folder are sampled off the event loop, named
by their files, never their paths; a row the person changed keeps their choice when later rows
arrive; Discard or a newer Add stops the sampling, and its late rows land nowhere; **Allow cloud
models for this run** starts unticked in every review; Start queues each row with its own options
and opens the Jobs page; Pages has no Review."""

import dataclasses
import json
import shutil
import threading
import time

import pytest
from fakes import FakeEngine
from helpers import SPEECH, make_clip
from starlette.testclient import TestClient
from test_web_server import (  # noqa: F401 - fresh_reactive_lock is autouse
    BASE,
    JSON,
    PAGE,
    PORT,
    TOKEN,
    Tab,
    fresh_reactive_lock,
    tab,
)
from test_web_settings import Browser

from vid2sub import review as reviewing
from vid2sub.cache import Cache
from vid2sub.catalog import Candidate
from vid2sub.config import Config
from vid2sub.engines.clients import KeyRing
from vid2sub.media.tools import Tools
from vid2sub.pipeline import InputResult, RunContext, RunOptions
from vid2sub.web import runtime, server
from vid2sub.web.app import create_app
from vid2sub.web.browse import Entry
from vid2sub.web.settings import Defaults, Session

LINK = "https://youtu.be/dQw4w9WgXcQ"
OTHER = "https://youtu.be/-abcdefghij"
CONFIG = Config.model_validate({
    "endpoints": {"spark": {"base_url": "http://127.0.0.1:9/v1"},
                  "openai": {"base_url": "https://api.openai.com/v1",
                             "key_env": "OPENAI_TEST_KEY"}},
    "models": {
        "spark-turbo": {"catalog": "whisper-large-v3-turbo", "endpoint": "spark",
                        "model": "turbo", "parser": "whisper.cpp", "local": True},
        "spark-gemma": {"catalog": "gemma-4-26b-a4b", "endpoint": "spark", "model": "gemma",
                        "task": "translate", "local": True},
        "openai-whisper": {"catalog": "openai-whisper-1", "endpoint": "openai",
                           "model": "whisper-1", "parser": "openai"},
    },
})
CANDIDATES = [Candidate("spark-turbo", "whisper-large-v3-turbo", "endpoint", True),
              Candidate("spark-gemma", "gemma-4-26b-a4b", "endpoint", True),
              Candidate("openai-whisper", "openai-whisper-1", "endpoint", True, cloud=True)]


class Held(FakeEngine):
    """Hears Japanese; the first window of the file `hold` (counted from 1) waits for `go`."""

    def __init__(self, hold: int | None = None):
        super().__init__(detect={"ja": 0.9})
        self.hold, self.go, self.held = hold, threading.Event(), threading.Event()

    def detect_language(self, chunk):
        if self.hold is not None and len(self.calls) == 3 * (self.hold - 1):
            self.held.set()
            assert self.go.wait(20)
        return super().detect_language(chunk)


@pytest.fixture
def engine():
    return Held()


@pytest.fixture
def rt(tmp_path, engine):
    home = tmp_path / "home"
    home.mkdir()
    ctx = RunContext(config=CONFIG, tools=Tools.find(), keys=KeyRing(environ={}),
                     options=RunOptions(), engines={"spark-turbo": engine},
                     candidates=list(CANDIDATES))
    made = runtime.build(CONFIG, tools=Tools.find(), keys=KeyRing(environ={}),
                         cache=Cache(tmp_path / "cache", max_bytes=0),
                         session=Session(Defaults(("en",), ("srt",))), job_context=ctx)
    made = dataclasses.replace(made, browse_home=home,
                               browse_roots=(Entry("Home", str(home), "folder"),))
    runtime.configure(made)
    yield made
    engine.go.set()
    runtime.configure(None)
    made.queue.close()


def client_for(rt):
    c = TestClient(create_app(rt, token=TOKEN, port=PORT, shiny_app=server.app), base_url=BASE)
    c.__enter__()
    assert c.post("/auth", content=json.dumps({"token": TOKEN}),
                  headers={**JSON, **PAGE}).status_code == 204
    return c


@pytest.fixture
def client(rt):
    c = client_for(rt)
    yield c
    c.__exit__(None, None, None)


@pytest.fixture
def season(rt):
    """Three episodes of one show, in the browser's home."""
    folder = rt.browse_home / "Show"
    folder.mkdir()
    clip = make_clip(folder, "clip.mkv", seconds=14, speech=SPEECH)
    for n in (1, 2, 3):
        shutil.copy(clip, folder / f"Show S01E0{n}.mkv")
    clip.unlink()
    return folder


def said(t: Tab, kind: str) -> list[dict]:
    return [m["custom"]["shinyReactMessage"]["data"] for m in t.messages
            if m.get("custom", {}).get("shinyReactMessage", {}).get("id") == kind]


def shown(t: Tab) -> dict | None:
    """The review shown now: None, {"preparing": True}, or the review's view."""
    return t.value("review") if t.has("review") else None


def rows(t: Tab) -> list[dict]:
    view = shown(t)
    return view["rows"] if view and "rows" in view else []


def ready(t: Tab, n: int):
    """The review's view once `n` rows are there and none is waiting or being sampled."""
    found = rows(t)
    return (len(found) == n and all(r["state"] in ("ready", "failed") for r in found)
            and shown(t))


def add(t: Tab, n: int, *, paths=(), links=(), keep_video=False) -> None:
    t.set(add={"n": n, "paths": list(paths), "links": list(links), "keep_video": keep_video})
    t.until(lambda t: any(d["n"] == n for d in said(t, "add_result")))


# ---- sampling ----------------------------------------------------------------------------------


@pytest.mark.media
def test_add_opens_a_review_that_fills_in_as_files_are_sampled_and_names_no_path(client, rt,
                                                                                 season):
    with tab(client, {"review"}) as t:
        add(t, 1, paths=[str(season)])
        view = t.until(lambda t: ready(t, 3))
    assert [(r["id"], r["name"], r["sampled"], r["inherited"], r["language"], r["transcribe"],
             r["translate"], r["targets"]) for r in view["rows"]] == [
        ("r1", "Show S01E01.mkv", True, False, "ja", "spark-turbo", "spark-gemma", ["en"]),
        ("r2", "Show S01E02.mkv", True, False, "ja", "spark-turbo", "spark-gemma", ["en"]),
        ("r3", "Show S01E03.mkv", False, True, "ja", "spark-turbo", "spark-gemma", ["en"])]
    first = view["rows"][0]
    assert first["detection"] == {"language": "ja", "confidence": 0.9,
                                  "votes": ["ja", "ja", "ja"], "mixed": False}
    assert first["audio"] == [{"index": 0, "label": "1: Japanese, aac, mono"}]
    assert first["folder"] == "Show" and 13_000 < first["duration_ms"] < 15_000
    assert [c["name"] for c in view["transcribers"]] == ["spark-turbo", "openai-whisper"]
    assert view["transcribers"][1]["cloud"] is True and view["allow_cloud"] is False
    assert view["can_start"] is True and all(r["problem"] is None for r in view["rows"])
    assert str(rt.browse_home) not in json.dumps(view)  # names, never paths (§6.8)


@pytest.mark.media
def test_a_row_changed_while_sampling_runs_on_keeps_the_persons_choice(client, rt, season,
                                                                       engine):
    engine.hold = 2  # the second file's sample waits until the person has changed the first
    with tab(client, {"review"}) as t:
        add(t, 1, paths=[str(season)])
        assert engine.held.wait(30)
        t.until(lambda t: rows(t) and rows(t)[0]["state"] == "ready")
        t.set(review_choose={"n": 2, "row": "r1",
                             "changes": {"language": "ko", "targets": ["en", "ja"]}})
        t.until(lambda t: rows(t)[0]["language"] == "ko")
        engine.go.set()
        view = t.until(lambda t: ready(t, 3))
    first, second, third = view["rows"]
    assert (first["language"], first["targets"]) == ("ko", ["en", "ja"])  # the person's
    assert (second["language"], third["language"], third["inherited"]) == ("ja", "ja", True)


@pytest.mark.media
def test_discard_or_a_new_add_stops_the_sampling_and_its_late_rows_land_nowhere(client, rt,
                                                                                season, engine):
    engine.hold = 1  # the first file's sample waits
    with tab(client, {"review"}) as t:
        add(t, 1, paths=[str(season)])
        assert engine.held.wait(30)
        t.set(review_discard={"n": 2})
        t.until(lambda t: t.has("review") and shown(t) is None)
        add(t, 3, links=[LINK])  # a new review, while the old sampling is still running
        t.until(lambda t: [r["name"] for r in rows(t)] == ["YouTube video dQw4w9WgXcQ"])
        engine.go.set()  # the old sample finishes now: its rows must not land in the new review
        t.until(lambda t: len(engine.calls) >= 3)
        time.sleep(0.5)  # time for its rows to hop to the loop, were they going to land
        assert [r["name"] for r in rows(t)] == ["YouTube video dQw4w9WgXcQ"]
    assert len(engine.calls) == 3  # stopped before its next file: one file's three windows


# ---- the person's choices and Start ------------------------------------------------------------


def test_allow_cloud_starts_unticked_in_every_review_and_only_its_box_ticks_it(client, rt):
    with tab(client, {"review"}) as t:
        add(t, 1, links=[LINK])
        t.until(lambda t: rows(t))
        assert shown(t)["allow_cloud"] is False
        t.set(review_cloud={"n": 2, "allowed": True})
        t.until(lambda t: shown(t)["allow_cloud"] is True)
        add(t, 3, links=[OTHER])  # the next review starts unticked, whatever the last one had
        t.until(lambda t: [r["name"] for r in rows(t)] == ["YouTube video -abcdefghij"])
        assert shown(t)["allow_cloud"] is False
        t.set(review_cloud={"n": 4, "allowed": "yes"})
        t.until(lambda t: t.notices())
        assert shown(t)["allow_cloud"] is False


def test_start_queues_each_row_with_its_own_options_and_opens_the_jobs_page(client, rt,
                                                                           monkeypatch):
    ran: list[tuple] = []

    def run_one(source, ctx):
        o = ctx.options
        ran.append((source, o.targets, o.formats, o.keep_video, o.allow_cloud))
        return InputResult(input=source, status="done")

    monkeypatch.setattr(reviewing, "run_one", run_one)
    rt.session.set_defaults(Defaults(("ko",), ("srt",)))  # the drawer's, as Add happens
    with tab(client, {"review"}) as t:
        add(t, 1, links=[LINK, OTHER], keep_video=True)
        t.until(lambda t: len(rows(t)) == 2)
        assert [r["targets"] for r in rows(t)] == [["ko"], ["ko"]]  # the session's, not toml's
        t.set(review_choose={"n": 2, "row": "r1",
                             "changes": {"targets": ["en", "ja"], "formats": ["srt", "ass"]}})
        t.until(lambda t: rows(t)[0]["targets"] == ["en", "ja"])
        t.set(review_apply={"n": 3, "row": "r1", "field": "targets"})
        t.until(lambda t: rows(t)[1]["targets"] == ["en", "ja"])
        rt.session.set_defaults(Defaults(("zh-Hant",), ("srt",)))  # changed again: rows win
        t.set(review_start={"n": 4})
        t.until(lambda t: said(t, "review_started"))
        assert said(t, "review_started") == [{"n": 4, "jobs": 2}]
        t.until(lambda t: t.has("review") and shown(t) is None)  # the review is done
    assert [j.input for j in rt.queue.jobs()] == ["https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                                                  "https://www.youtube.com/watch?v=-abcdefghij"]
    deadline = time.monotonic() + 10
    while len(ran) < 2:
        assert time.monotonic() < deadline, "timed out waiting"
        time.sleep(0.01)
    assert ran == [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", ["en", "ja"], ["srt", "ass"], True, False),
        ("https://www.youtube.com/watch?v=-abcdefghij", ["en", "ja"], ["srt"], True, False)]


def test_a_choice_that_cant_be_made_says_so_and_echoes_nothing(client, rt):
    with tab(client, {"review"}) as t:
        add(t, 1, links=[LINK])
        t.until(lambda t: rows(t))
        for n, request in enumerate([
                {"row": "r1", "changes": {"language": "xx-secret"}},
                {"row": "r9-secret", "changes": {"language": "ja"}},
                {"row": "r1", "changes": {"glossary-secret": "x"}},
                {"row": "r1", "changes": "secret"}], 2):
            t.set(review_choose={"n": n, **request})
        t.set(review_apply={"n": 6, "row": "r1", "field": "secret"})
        t.until(lambda t: len(t.notices()) == 5)
        assert "secret" not in json.dumps(t.notices())
        assert rows(t)[0]["language"] is None


def test_the_pages_editor_has_no_review(rt):
    pages = dataclasses.replace(rt, backend=Browser(rt.backend))
    runtime.configure(pages)
    c = client_for(pages)
    try:
        with tab(c, {"review"}) as t:
            t.until(lambda t: t.has("review"))
            t.set(add={"n": 1, "paths": [], "links": [LINK], "keep_video": False})
            t.set(review_start={"n": 2})
            t.set(open={"path": "/nowhere/x.mkv", "n": 3})  # something it does answer
            t.until(lambda t: t.notices())
            assert shown(t) is None and said(t, "add_result") == []
    finally:
        c.__exit__(None, None, None)
    assert rt.queue.jobs() == []
```

  In `tests/test_web_add.py`, in the module docstring, replace
  `checks and YouTube links as their canonical URLs, and queues them, a link keeping its whole video`
  / `when asked; the demo browses only its own folder and runs only its clip; Pages has no Add."""`
  with

```python
checks and YouTube links as their canonical URLs, and hands them to Review (Task 4), a link
keeping its whole video when asked; the demo browses only its own folder and runs only its clip;
Pages has no Add."""
```

  replace the whole of
  `test_add_queues_each_video_once_in_episode_order_and_a_link_as_its_canonical_url` with:

```python
def reviewed(t: Tab) -> list[dict] | None:
    """The review's rows, once a review (not its "preparing" placeholder) is shown."""
    shown = t.value("review") if t.has("review") else None
    return shown["rows"] if shown and "rows" in shown else None


def test_add_reviews_each_video_once_in_episode_order_and_a_link_as_its_canonical_url(
        client, rt, places, ran):
    home, _, season = places
    with tab(client, {"review"}) as t:
        t.set(add={"n": 1, "paths": [str(season), str(home / "Film.mp4"),
                                     str(season / "Show S01E01.mkv")],
                   "links": [LINK], "keep_video": False})
        assert answer(t, "add_result", 1) == {"n": 1, "added": 4, "error": None}
        rows = t.until(lambda t: (r := reviewed(t)) and len(r) == 4 and r)
        assert [(r["name"], r["link"], r["keep_video"]) for r in rows] == [
            ("Show S01E01.mkv", False, False), ("Show S01E02.mkv", False, False),
            ("Film.mp4", False, False), ("YouTube video dQw4w9WgXcQ", True, False)]
        t.set(add={"n": 2, "paths": [], "links": [LINK], "keep_video": True})
        assert answer(t, "add_result", 2) == {"n": 2, "added": 1, "error": None}
        rows = t.until(lambda t: (r := reviewed(t)) and len(r) == 1 and r)
        assert (rows[0]["name"], rows[0]["keep_video"]) == ("YouTube video dQw4w9WgXcQ", True)
        assert str(home) not in json.dumps(t.value("review"))  # names, never paths (§6.8)
    assert ran == [] and rt.queue.jobs() == []  # nothing runs until Review's Start


```

  and in the demo's test, rename
  `test_the_demo_browses_only_its_own_folder_and_a_link_it_adds_is_refused` to
  `test_the_demo_browses_only_its_own_folder_and_a_link_it_starts_is_refused` and replace
  `        rt.add([CANONICAL], keep_video=True)  # a runner of its own, which the guard wraps` with
  `        rt.start_review(rt.prepare([CANONICAL], keep_video=True))  # its own runner, guarded`.
- [ ] **Step 2: Run them; watch them fail.** `uv run pytest tests/test_web_review.py
  tests/test_web_add.py -q`. Expected: `E       AssertionError: timed out; the tab saw […]` (no
  `review` output yet), the demo's test failing on `start_review`, and `9 failed, 16 passed`.
- [ ] **Step 3: Write the code.** In `src/vid2sub/web/episode.py`, above
  `@dataclass(frozen=True)` / `class SaveResult:`, add:

```python
class ReviewRefused(Exception):
    """A choice, "apply to all" or a Start on the Review screen that can't be made: the reason is
    fit to show and echoes nothing (spec §6.8). The local runtime makes it from the core's
    `review.ReviewError`, which the server can't import in Pages (Phase 3 Task 4)."""


```

  In `src/vid2sub/web/runtime.py`, in the module docstring, replace the paragraph from
  `The Add screen's file browser (Phase 3 Task 2, spec §6.5) lists your home and mounted volumes`
  to `that keeps its video) still runs only the demo's clip.` with:

```python
The Add screen's file browser (Phase 3 Task 2, spec §6.5) lists your home and mounted volumes
through `roots`, `listing` and `expand`, which turn the browser's refusals into the pure
`AddError`; the demo's runtime gives it only the demo's folder (`browse_roots`, `browse_home`).
Review (Phase 3 Task 4, §10) runs on the job context through `prepare`, `sample`, `with_row`,
`choose`, `apply_to_all`, `allow_cloud`, `problems` and `start_review`, which turn the core's
refusals into the pure `ReviewRefused`: its rows start with the session's targets and formats,
each row's job brings its own runner with the row's options, and `job_guard` wraps it, so in the
demo a job still runs only the demo's clip.
```

  and replace
  `` `Runtime` (`reachable`, `media_for`, `retranslate`, `endpoint_models`, `roots`, `listing`, ``
  / `` `expand`, `add`). Every call that blocks goes through `` with
  `` `Runtime` (`reachable`, `media_for`, `retranslate`, `endpoint_models`, the browser's and ``
  / `` Review's). Every call that blocks goes through ``. Replace
  `from typing import TYPE_CHECKING` with `from typing import TYPE_CHECKING, Any`; below
  `    from vid2sub.pipeline import Event, InputResult, RunContext` (in the `TYPE_CHECKING`
  block), add `    from vid2sub.review import Review, Row`; and replace the whole `add` method
  (from `    def add(self, inputs: Sequence[str], *, keep_video: bool) -> list[str]:` to the line
  above `    def media_for`) with:

```python
    def prepare(self, inputs: Sequence[str], *, keep_video: bool) -> Review:
        """Review's rows for what Add took (`review.prepare` on the job context), each starting
        with the session's targets and formats as they are now (§5.4); `allow_cloud` starts
        unticked (§7.2). Blocks on ffprobe and each local server's model list: call it through
        `blocking`."""
        from vid2sub import review

        defaults = self.session.defaults()
        return review.prepare(inputs, self.job_context, keep_video=keep_video,
                              targets=defaults.targets, formats=defaults.formats)

    def sample(self, rv: Review, *, on_row: Callable[[Row], None],
               cancelled: Callable[[], bool]) -> Review | None:
        """`review.sample` on the job context, or None once `cancelled()` (the person added
        again, discarded the review or closed the tab). Blocks for seconds per file: call it
        through `blocking`; `on_row` runs on that thread."""
        from vid2sub import review
        from vid2sub.pipeline import Cancelled

        try:
            return review.sample(rv, self.job_context, on_row=on_row, cancelled=cancelled)
        except Cancelled:
            return None

    def with_row(self, rv: Review, row: Row) -> Review:
        """A sampled row merged into the review (`review.with_row`). Pure and fast."""
        from vid2sub import review

        return review.with_row(rv, row)

    def choose(self, rv: Review, row_id: str, changes: dict[str, Any]) -> Review:
        """The person's choices for one row (`review.choose`); `ReviewRefused` for one that
        can't be made. Pure and fast: called on the event loop."""
        from vid2sub import review
        from vid2sub.web.episode import ReviewRefused

        try:
            return review.choose(rv, row_id, **changes)
        except review.ReviewError as err:
            raise ReviewRefused(str(err)) from None

    def apply_to_all(self, rv: Review, row_id: str, field: str) -> Review:
        """One row's choice copied to every ready row ("apply to all", §10.5)."""
        from vid2sub import review
        from vid2sub.web.episode import ReviewRefused

        try:
            return review.apply_to_all(rv, row_id, field)
        except review.ReviewError as err:
            raise ReviewRefused(str(err)) from None

    def allow_cloud(self, rv: Review, allowed: bool) -> Review:
        """The **Allow cloud models for this run** box: its only setter (§7.2)."""
        from vid2sub import review

        return review.set_allow_cloud(rv, allowed)

    def problems(self, rv: Review) -> dict[str, str]:
        """What stops Start, by row id; empty when it can go."""
        from vid2sub import review

        return review.problems(rv)

    def start_review(self, rv: Review) -> list[str]:
        """Start (§10.6): each row that can run, queued with its own options on the job
        context, its runner wrapped by `job_guard` (the demo's: only its clip), so the row's
        targets and formats win over the session's. `ReviewRefused` while a row has a problem;
        RuntimeError once the queue is closed."""
        from vid2sub import review
        from vid2sub.web.episode import ReviewRefused

        try:
            return review.start(rv, self.queue, self.job_context, guard=self.job_guard)
        except review.ReviewError as err:
            raise ReviewRefused(str(err)) from None

```

  In `src/vid2sub/web/views.py`, in the module docstring, replace
  `shows a folder's entries by bare name and full path (Phase 3 Task 2, §6.5). The server runs in`
  / `Pages too` with

```python
shows a folder's entries by bare name and full path (Phase 3 Task 2, §6.5); the Review screen
shows each row by bare name, never its path (Task 4, §10). The server runs in Pages too
```

  below `    from vid2sub.jobs import JobView` (in the `TYPE_CHECKING` block), add
  `    from vid2sub.media.probe import AudioTrack` and
  `    from vid2sub.review import ModelChoice, Review`; and above
  `def capabilities_view(caps: Capabilities) -> dict[str, Any]:`, add:

```python
def review_view(review: Review, problems: Mapping[str, str]) -> dict[str, Any]:
    """The Review screen (spec §10, §19.2, S40): one row per file, in the order added, by its
    bare name (a link by its video's id), never its path (§6.8); its duration, its audio tracks
    (language, codec, channels) and the one the job will use (§8.4); the detected language with
    its confidence and votes, or "Mandarin or Cantonese?"; the transcription and translation
    models, targets, formats and Chinese script chosen; whether it was sampled or inherited; its
    warning, error and fix; and what stops it starting (`problems`). The pickers list every
    configured model with the catalog's one-liner, greyed with the reason where it can't run now
    (§10.4); the languages are those vid2sub transcribes, and the targets those it writes.
    **Allow cloud models for this run** is the review's own box, `allow_cloud`, which starts
    unticked in every review (§7.2); nothing else sets it."""
    rows = []
    for r in review.rows:
        found = r.detection
        rows.append({
            "id": r.id, "name": r.name, "folder": PurePath(r.folder).name if r.folder else "",
            "link": r.link, "state": r.state, "sampled": r.sampled, "inherited": r.inherited,
            "duration_ms": r.duration_ms,
            "audio": [{"index": t.index, "label": _audio_label(t)}
                      for t in (r.probe.audio if r.probe else ())],
            "audio_index": r.audio_index,
            "detection": None if found is None else {
                "language": found.language, "confidence": found.confidence,
                "votes": list(found.votes), "mixed": found.mixed},
            "language": r.language, "ask_zh_yue": r.ask_zh_yue, "transcribe": r.transcribe,
            "translate": r.translate, "targets": list(r.targets), "formats": list(r.formats),
            "script": r.script, "keep_video": r.keep_video, "warning": r.warning or None,
            "error": r.error or None, "hint": r.hint or None,
            "problem": problems.get(r.id)})
    return {
        "rows": rows,
        "transcribers": [_choice(c) for c in review.transcribers],
        "translators": [_choice(c) for c in review.translators],
        "languages": [{"code": code, "name": lang.name} for code, lang in langs.LANGS.items()],
        "targets": [{"key": key, "label": track_label(key)} for key in naming.TRACKS],
        "allow_cloud": review.allow_cloud,
        "can_start": not problems and any(r.state != "failed" for r in review.rows),
    }


def _choice(c: ModelChoice) -> dict[str, Any]:
    return {"name": c.name, "title": c.title, "good_for": c.good_for, "available": c.available,
            "reason": c.reason or None, "cloud": c.cloud}


def _audio_label(t: AudioTrack) -> str:
    """An audio track as the Review screen lists it (§8.4): its language, codec and channels."""
    known = t.language if t.language not in (None, "und") else None  # "und": undetermined
    name = langs.LANGS[known].name if known in langs.LANGS else (known or "no language tag")
    channels = {1: "mono", 2: "stereo"}.get(t.channels or 0,
                                            f"{t.channels} channels" if t.channels else "")
    return ", ".join(p for p in (f"{t.index + 1}: {name}", t.codec, channels) if p)


```

  In `src/vid2sub/web/server.py`, in the module docstring, replace

```python
runtime checks as the browser checks a folder and queues (`add_result`). Both wait on the disk, a
sleeping network share for seconds, so each runs in a task of the tab's own through
`runtime.blocking`; a tab lists one folder at a time, and only the newest request waits behind it
(Review Focus 1).
```

  with

```python
runtime checks as the browser checks a folder (`add_result`) and Review takes. Both wait on the
disk, a sleeping network share for seconds, so each runs in a task of the tab's own through
`runtime.blocking`; a tab lists one folder at a time, and only the newest request waits behind it
(Review Focus 1).

Review (§10, §19.2; S40; Phase 3 Task 4) is one per tab, a `Reviewer`: Add's videos probed and
their first two per folder sampled off the event loop, each sampled row hopping back to the loop
from the sampling thread and merged, so the `review` output fills in as it goes; the person's
choices (`review_choose`, `review_apply`, `review_cloud`), pure and fast, in their inputs' own
effects; `review_start`, which queues each row with its own options and tells the page
(`review_started`); and `review_discard`. A newer Add, Discard, Start or the tab closing stops
the sampling before its next file, and drops what it still sends. **Allow cloud models for this
run** is the review's own, unticked in every new review (§7.2). The view never holds a path.
```

  in the `from vid2sub.web.episode import (…)` block, add `    ReviewRefused,` below
  `    RetranslateError,`; below
  `TOO_MANY = f"that's more than {MAX_JOBS} videos: add fewer at once"`, add
  `PICK_A_CHOICE = "pick a file and a choice for it"`; above
  `def _full_paths(paths: object) -> bool:`, add:

```python
class Reviewer:
    """One tab's Review (spec §10, §19.2; S40): the rows Add made, sampled in the background,
    and the person's choices. The review is a frozen value changed only on this loop: by the
    sampling's rows, which hop here from the thread they're made on, and by the person's choices,
    which are pure and fast, so they run in the input's own effect. Sampling only ever sends a
    row that isn't ready, which the person can't change, so a choice they made stands when later
    rows arrive (Review Focus 2). A newer Add, Discard, Start or the tab closing ends the review:
    its sampling stops before its next file, and anything it sends after that is dropped, so an
    old review's rows (named `r1`, `r2`… as every review's are) never land in a new one."""

    def __init__(self, rt: runtime.Runtime, session: Session):
        self.rt = rt
        self.session = session
        self.review: Any = None  # the truth, a `review.Review`; changed only on this loop
        self.shown: reactive.Value[Any] = reactive.value(None)
        self.preparing: reactive.Value[bool] = reactive.value(False)
        self._current: object | None = None  # the review the running sampling belongs to
        self._tasks: set[asyncio.Task] = set()

    def begin(self, inputs: list[str], *, keep_video: bool) -> None:
        """A new review of what Add took; the one before it ends. Called on this loop."""
        self.end()
        token = self._current = object()
        task = asyncio.create_task(self._run(token, inputs, keep_video))
        self._tasks.add(task)  # kept until it ends: the loop holds only a weak reference
        task.add_done_callback(self._tasks.discard)

    def end(self) -> None:
        """Discard, Start or the tab closed: sampling stops before its next file, and what it
        sends from now on is dropped."""
        self._current = None
        self.review = None

    async def _run(self, token: object, inputs: list[str], keep_video: bool) -> None:
        try:
            await self._show(None, preparing=True)
            rv = await runtime.blocking(self.rt.prepare, inputs, keep_video=keep_video)
            if self._current is not token:
                return
            await self._show(rv)
            loop = asyncio.get_running_loop()

            def on_row(row: Any) -> None:  # on the sampling thread
                asyncio.run_coroutine_threadsafe(self._arrived(token, row), loop)

            await runtime.blocking(self.rt.sample, rv, on_row=on_row,
                                   cancelled=lambda: self._current is not token)
        except Exception as err:  # noqa: BLE001 - a review failing must not stop the session
            log.error("a review failed: %s", type(err).__name__)  # the type only (§6.8)
            if self._current is token:
                self.end()
                await self._show(None)
                await notice(self.session, "error", "something went wrong (review); see the log")

    async def _arrived(self, token: object, row: Any) -> None:
        """A sampled row, merged on this loop while its review is still the one shown."""
        if self._current is token and self.review is not None:
            await self._show(self.rt.with_row(self.review, row))

    async def change(self, kind: str, request: object) -> None:
        """A choice, "apply to all" or the Allow cloud box, on the review shown; in the input's
        effect, so the page's changes land in the order it sent them."""
        if self.review is None or not isinstance(request, dict):
            return
        try:
            if kind == "choose":
                row, changes = request.get("row"), request.get("changes")
                if not (isinstance(row, str) and isinstance(changes, dict)):
                    raise ReviewRefused(PICK_A_CHOICE)
                rv = self.rt.choose(self.review, row, changes)
            elif kind == "apply":
                row, field = request.get("row"), request.get("field")
                if not (isinstance(row, str) and isinstance(field, str)):
                    raise ReviewRefused(PICK_A_CHOICE)
                rv = self.rt.apply_to_all(self.review, row, field)
            else:
                allowed = request.get("allowed")
                if not isinstance(allowed, bool):
                    raise ReviewRefused(PICK_A_CHOICE)
                rv = self.rt.allow_cloud(self.review, allowed)
        except ReviewRefused as err:  # fit to show, and echoes nothing; the page's controls
            await notice(self.session, "error", str(err))  # show the review's own choices
            return
        self.review = rv
        self.shown.set(rv)

    async def start(self, request: object) -> None:
        """Start: every row that can run queued, each with its own options; then the review is
        done and the page opens the Jobs page (`review_started`)."""
        if self.review is None:
            return
        n = request.get("n") if isinstance(request, dict) else None
        try:
            ids = self.rt.start_review(self.review)
        except ReviewRefused as err:
            await notice(self.session, "error", str(err))
            return
        except RuntimeError:  # closed: the engine is stopping
            await notice(self.session, "error", STOPPING)
            return
        self.discard()
        await shinyreact.send_message(self.session, "review_started",
                                      {"n": n if type(n) is int else None, "jobs": len(ids)})

    def discard(self) -> None:
        """Discard: the review ends and the screen empties."""
        self.end()
        self.preparing.set(False)
        self.shown.set(None)

    async def _show(self, rv: Any, *, preparing: bool = False) -> None:
        """Shows `rv` from a task or a hop from a thread: under Shiny's lock, then flushed."""
        self.review = rv
        async with reactive.lock():
            self.preparing.set(preparing)
            self.shown.set(rv)
            await reactive.flush()


```

  and in `server`, replace

```python
                else:
                    try:
                        added = len(rt.add(inputs, keep_video=keep))
                    except RuntimeError:  # closed: the engine is stopping
                        error = STOPPING
        await shinyreact.send_message(session, "add_result",
                                      {"n": n, "added": added, "error": error})
```

  with:

```python
                else:
                    reviewer.begin(inputs, keep_video=keep)  # Review comes next (Task 4)
                    added = len(inputs)
        await shinyreact.send_message(session, "add_result",
                                      {"n": n, "added": added, "error": error})

    # Review (spec §10, §19.2; S40), the local engine's alone, one per tab: what Add took,
    # sampled in the background, the person's choices, and Start, which queues each row with its
    # own options. The choices are pure and fast, so each runs in its input's own effect.
    reviewer = Reviewer(rt, session)
    session.on_ended(reviewer.end)

    @reactive_output
    def review():
        rv = reviewer.shown()
        if rv is None:
            return {"preparing": True} if reviewer.preparing() else None
        return views.review_view(rv, rt.problems(rv))

    @reactive.effect
    @reactive.event(input.review_choose)
    async def _review_choose() -> None:
        if local:
            await reviewer.change("choose", as_json(input.review_choose()))

    @reactive.effect
    @reactive.event(input.review_apply)
    async def _review_apply() -> None:
        if local:
            await reviewer.change("apply", as_json(input.review_apply()))

    @reactive.effect
    @reactive.event(input.review_cloud)
    async def _review_cloud() -> None:
        if local:
            await reviewer.change("cloud", as_json(input.review_cloud()))

    @reactive.effect
    @reactive.event(input.review_start)
    async def _review_start() -> None:
        if local:
            await reviewer.start(as_json(input.review_start()))

    @reactive.effect
    @reactive.event(input.review_discard)
    def _review_discard() -> None:
        if local:
            reviewer.discard()

```

  In `src/vid2sub/web/demo.py`, in the module docstring, replace
  `demo's clip (the Phase 3 plan, Task 2).` with

```python
demo's clip (the Phase 3 plan, Task 2). Its Review samples with the canned engine and suggests
the canned models, which stand in for Whisper large-v3-turbo and Gemma 4 (`CANNED_MODELS`, Task
4), so nothing is asked of a server.
```

  below `from vid2sub.cache import Cache`, add `from vid2sub.catalog import Candidate`; above
  `DEMO_ONLY = "the demo runs only its own clip"`, add:

```python
# What the demo's Review can suggest: the canned models, under the catalog entries they stand in
# for, so detection picks the canned engine and the route suggests it (Phase 3 Task 4).
CANNED_MODELS = (Candidate("canned", "whisper-large-v3-turbo", "endpoint", True),
                 Candidate(CANNED_JA, "gemma-4-26b-a4b", "endpoint", True))
```

  and in `runtime_for`, replace `                      ask_for=lambda *args, **kwargs: canned_ask)`
  with `                      ask_for=lambda *args, **kwargs: canned_ask,` /
  `                      candidates=list(CANNED_MODELS))`.
- [ ] **Step 4: Run the checks; they pass.** `uv run pytest tests/test_web_review.py
  tests/test_web_add.py -q` first (`25 passed`; five times, once under `TZ=UTC`: sampling runs
  on threads), then the guard checks, then `make check`. **Guard checks**, each reverted and
  restored, each with `uv run pytest tests/test_web_review.py -q` unless named: in
  `Reviewer._arrived`, replace `if self._current is token and self.review is not None:` with
  `if self.review is not None:` (an old review's row lands in the new one:
  `FAILED …test_discard_or_a_new_add_stops_the_sampling_and_its_late_rows_land_nowhere`); in
  `Reviewer._run`, sample with `cancelled=lambda: False` (the same test: the sampling goes on to
  the next file); in `Runtime.prepare`, drop `targets=defaults.targets, formats=defaults.formats`
  (`FAILED …test_start_queues_each_row_with_its_own_options_and_opens_the_jobs_page`: rows start
  with vid2sub.toml's targets); in `Runtime.start_review`, drop `guard=self.job_guard`
  (`uv run pytest tests/test_web_add.py -q -k demo`: the demo's link reaches yt-dlp, "deno isn't
  installed…"). `make check`. Expected: `1177 passed, 7 skipped, 38 deselected` twice,
  `Test Files  20 passed (20)` and `Tests  91 passed (91)`, `All checks passed!` and
  `no leaks found`. (`make e2e` waits for round 4b: Task 2's browser tests now meet Review.)
- [ ] **Step 5: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(web): 🤖 Add opens a review that fills in as files are sampled, keeps the person's choices, and Start queues each row

The server's half of Review (spec §10, §19.2, §7.2; S40). Add no longer
queues: it hands what it took to a Reviewer, one per tab, which probes
the files and samples the first two of each folder off the event loop
(runtime.prepare and sample, review.prepare and sample on the job
context), each sampled row hopping back to the loop from the sampling
thread and merged, so the `review` output fills in as it goes; a
{"preparing": true} placeholder shows meanwhile. Rows start with the
session's targets and formats. The person's choices (review_choose,
review_apply, review_cloud) are pure and fast, so they run in their
inputs' own effects, in order; a refused one says why and echoes
nothing. review_start queues every row with its own options (the row's
targets and formats win over the session's), each runner through the
runtime's job_guard, empties the review and sends review_started;
review_discard empties it. A newer Add, Discard, Start or the tab
closing stops the sampling before its next file and drops what it still
sends, so an old review's r1 never lands in a new one. Allow cloud is
the review's own and starts unticked in every review; nothing else
ticks it (§7.2). The view (views.review_view) names files and folders
by their bare names, never a path (§6.8). The core's refusals reach the
server as the pure ReviewRefused, since vid2sub.review isn't in the
Pages bundle; Pages has no Review.

The demo's job context brings its canned models as candidates, under
the catalog entries they stand in for (Whisper large-v3-turbo and
Gemma 4), so its Review samples with the canned engine and suggests
them, asking no server (proposed as a Decision).

Task 2's Add tests now expect a review instead of jobs, and the demo's
guarded link goes through Review's Start.

The new tests failed first with: AssertionError: timed out (no review
output), seven times, and Task 2's two changed tests likewise. Guard
checks, each reverted and restored: merging a row whatever review it
came from, or sampling with no cancel, lets an old review's row land in
a new one; prepare without the session's targets starts rows with
vid2sub.toml's; start without the job guard lets the demo's link reach
yt-dlp.

Docs read: shiny 1.8.0's source (an effect may set a reactive value; a
value set from a task needs reactive.lock and a flush, as Phase 2's
Editor does), Python's asyncio.run_coroutine_threadsafe; shinyreact
0.1.0's send_message.

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md Task 4
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/web/demo.py src/vid2sub/web/episode.py src/vid2sub/web/runtime.py
  src/vid2sub/web/server.py src/vid2sub/web/views.py tests/test_web_add.py
  tests/test_web_review.py`, `git commit -F .git/COMMIT_MSG`, then
  `git log -1 --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 6: Write the failing tests.** `frontend/src/lib/review.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import type { ReviewRow } from "@/types";

import { choiceLabel, duration, heard, isReview, toggled, withPending } from "./review";

const LANGS = [{ code: "ja", name: "Japanese" }, { code: "zh", name: "Mandarin" }, { code: "yue", name: "Cantonese" }];
const ROW: ReviewRow = {
  id: "r1", name: "Show S01E01.mkv", folder: "Show", link: false, state: "ready", sampled: true, inherited: false,
  duration_ms: 1_440_000, audio: [], audio_index: 0, detection: { language: "ja", confidence: 0.9, votes: ["ja", "ja", "ja"], mixed: false },
  language: "ja", ask_zh_yue: false, transcribe: "spark-turbo", translate: "spark-gemma", targets: ["en"], formats: ["srt"],
  script: null, keep_video: false, warning: null, error: null, hint: null, problem: null,
};

describe("a Review row in words (spec §10, §19.2)", () => {
  it("says how long a file is", () => {
    expect(duration(1_440_000)).toBe("24:00");
    expect(duration(3_723_400)).toBe("1:02:03");
    expect(duration(null)).toBe("");
  });

  it("says what its samples heard and how sure, or what it waits for", () => {
    expect(heard(ROW, LANGS)).toBe("Japanese, 90% sure");
    expect(heard({ ...ROW, detection: { ...ROW.detection!, mixed: true, votes: ["ja", null, "zh"] } }, LANGS)).toBe("Japanese, 90% sure; the samples disagree (ja, ?, zh)");
    expect(heard({ ...ROW, ask_zh_yue: true, language: null }, LANGS)).toBe("Mandarin or Cantonese?");
    expect(heard({ ...ROW, state: "sampling" }, LANGS)).toBe("sampling…");
    expect(heard({ ...ROW, detection: null, inherited: true }, LANGS)).toBe("Japanese, like the files sampled in this folder");
    expect(heard({ ...ROW, detection: { language: null, confidence: 0, votes: [], mixed: false }, language: null }, LANGS)).toBe("no speech heard");
    expect(heard({ ...ROW, link: true }, LANGS)).toBe("decided when it runs");
  });

  it("names a model with its title, greyed with why it can't run but still there", () => {
    expect(choiceLabel({ name: "spark-turbo", title: "Whisper large-v3-turbo", good_for: "", available: true, reason: null, cloud: false })).toBe("spark-turbo: Whisper large-v3-turbo");
    expect(choiceLabel({ name: "openai-whisper", title: "OpenAI whisper-1", good_for: "", available: false, reason: "OPENAI_API_KEY isn't set", cloud: true })).toBe("openai-whisper: OpenAI whisper-1 (cloud), can't run now");
  });

  it("ticks and unticks targets in the targets' order, down to none", () => {
    const order = ["en", "ja", "zh-Hant"];
    expect(toggled(["en"], "zh-Hant", true, order)).toEqual(["en", "zh-Hant"]);
    expect(toggled(["en"], "en", false, order)).toEqual([]);
  });

  it("shows a choice on its way to the engine, the audio track by its index", () => {
    expect(withPending(ROW, { language: "ko", audio_track: 1 })).toEqual({ ...ROW, language: "ko", audio_index: 1 });
    expect(withPending(ROW, undefined)).toBe(ROW);
  });

  it("tells a review from its placeholder", () => {
    expect(isReview({ preparing: true })).toBe(false);
    expect(isReview(null)).toBe(false);
  });
});
```

  `tests/e2e/test_review.py`:

```python
"""The Review screen in Chromium (spec §10, §19.2, §7.2; S40): a season added through the file
browser opens Review, where the first two files of the folder are sampled and the third inherits,
each row says what was heard and how sure and suggests models, "Apply to all" copies one row's
choice to the rest, Start runs them all, and **Allow cloud models for this run** starts unticked
in every review. Against `vid2sub serve --demo`, whose canned engine samples and transcribes and
whose canned translation makes the Japanese, on copies of its own clip. Run with `make e2e`."""

import shutil

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def add_folder(page, copy, folder: str) -> None:
    page.get_by_test_id("nav-add").click()
    page.get_by_test_id("browse-places").click()  # the browser shows the folder seen last
    page.get_by_test_id("browse-entry").first.get_by_test_id("browse-open").click()
    expect(page.get_by_test_id("browse-path")).to_have_text(str(copy))
    page.get_by_test_id("browse-list").get_by_text(folder, exact=True).click()
    page.get_by_test_id("browse-pick-here").check()
    page.get_by_test_id("add-start").click()
    expect(page.get_by_test_id("review-page")).to_be_visible()


def test_a_season_is_sampled_suggested_applied_to_all_and_started(page, server):
    copy = next(server.tmp.glob("vid2sub-demo-*/demo"))
    season = copy / "Season"
    season.mkdir()
    for n in (1, 2, 3):
        shutil.copy(copy / "jfk.mp4", season / f"Talk S01E0{n}.mp4")
    add_folder(page, copy, "Season")
    rows = page.get_by_test_id("review-row")
    expect(rows).to_have_count(3)
    for k in range(3):
        expect(rows.nth(k)).to_have_attribute("data-state", "ready", timeout=60_000)
    expect(rows.get_by_test_id("review-name")).to_have_text(
        ["Talk S01E01.mp4", "Talk S01E02.mp4", "Talk S01E03.mp4"])
    expect(rows.get_by_test_id("review-heard")).to_have_text(
        ["English, 100% sure", "English, 100% sure",
         "English, like the files sampled in this folder"])
    expect(rows.nth(2).get_by_test_id("review-inherited")).to_be_visible()
    for k in range(3):
        expect(rows.nth(k).get_by_test_id("review-transcribe")).to_have_value("canned")
        expect(rows.nth(k).get_by_test_id("review-translate")).to_have_value("canned-ja")
    expect(page.get_by_test_id("review-cloud")).not_to_be_checked()
    first = rows.first
    first.get_by_test_id("review-ass").check()
    expect(first.get_by_test_id("review-ass")).to_be_checked()
    first.get_by_test_id("review-all-formats").click()
    for k in range(3):
        expect(rows.nth(k).get_by_test_id("review-ass")).to_be_checked()
    page.get_by_test_id("review-start").click()
    expect(page.get_by_test_id("jobs-page")).to_be_visible()
    jobs = page.get_by_test_id("job")
    expect(jobs).to_have_count(3)
    for k in range(3):
        expect(jobs.nth(k)).to_have_attribute("data-state", "done", timeout=60_000)
    expect(jobs.first.get_by_test_id("job-line")).to_contain_text("Talk S01E01.ja.ass")
    assert (season / "Talk S01E03.ja.ass").is_file() and (season / "Talk S01E03.ja.srt").is_file()


def test_allow_cloud_starts_unticked_in_every_review(page, server):
    copy = next(server.tmp.glob("vid2sub-demo-*/demo"))
    (copy / "Again").mkdir()
    shutil.copy(copy / "jfk.mp4", copy / "Again" / "Talk.mp4")
    add_folder(page, copy, "Again")
    cloud = page.get_by_test_id("review-cloud")
    expect(cloud).not_to_be_checked()
    cloud.check()
    expect(cloud).to_be_checked()  # the engine's review says so, not only the page
    page.get_by_test_id("review-discard").click()
    expect(page.get_by_text("Nothing to review: add videos first.")).to_be_visible()
    add_folder(page, copy, "Again")
    expect(page.get_by_test_id("review-row")).to_have_count(1)
    expect(page.get_by_test_id("review-cloud")).not_to_be_checked()
```

  Replace `tests/e2e/test_add.py` with (Add now opens Review, whose Start opens Jobs):

```python
"""The Add screen in Chromium (spec §19.2, §6.5, §8.1; S38, S39): the file browser starts at the
places, opens a folder with its folders first and its episodes in `SxxEyy` order, shows only
folders, videos and subtitles, and adds what is picked, which Review then starts (Task 4); a
YouTube link with **keep video** ticked lands whole in the YouTube folder. Against `vid2sub serve --demo`, whose browser has only the
demo's folder, and against a vid2sub.toml served with yt-dlp faked (`fake_youtube.py`, M1's
`download(…, runner=)` seam) and a fake whisper.cpp server, so nothing reaches YouTube or a model.
Run with `make e2e`."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from fakes import FakeServer
from helpers import SPEECH, make_clip
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e

HERE = Path(__file__).parent
WORDS = {"language": "english", "language_probabilities": {"en": 0.99},
         "segments": [{"text": " We meet at a college.", "start": 0.0, "end": 2.0,
                       "words": [{"word": " We", "start": 0.0, "end": 0.5, "probability": 0.9},
                                 {"word": " meet", "start": 0.5, "end": 1.0,
                                  "probability": 0.9},
                                 {"word": " at", "start": 1.0, "end": 1.2, "probability": 0.9},
                                 {"word": " a", "start": 1.2, "end": 1.4, "probability": 0.9},
                                 {"word": " college.", "start": 1.4, "end": 2.0,
                                  "probability": 0.9}]}]}


def open_add(page):
    page.get_by_test_id("nav-add").click()
    expect(page.get_by_test_id("add-page")).to_be_visible()


def start_review(page, rows: int) -> None:
    """Review opens once Add is done; Start, once every row is ready, opens the Jobs page."""
    expect(page.get_by_test_id("review-page")).to_be_visible()
    expect(page.get_by_test_id("review-row")).to_have_count(rows, timeout=30_000)
    expect(page.get_by_test_id("review-start")).to_be_enabled(timeout=30_000)
    page.get_by_test_id("review-start").click()
    expect(page.get_by_test_id("jobs-page")).to_be_visible()


def test_the_demo_browses_its_own_folder_in_episode_order_and_adds_its_clip(page, server):
    copy = next(server.tmp.glob("vid2sub-demo-*/demo"))
    for name in ("Show S01E10.mkv", "Show S01E02.mkv", ".hidden.mkv", "notes.txt"):
        (copy / name).write_bytes(b"x")
    (copy / "Extras").mkdir()
    open_add(page)
    entries = page.get_by_test_id("browse-entry")
    expect(entries).to_have_count(1)  # the places: the demo's own folder, nothing of yours
    expect(entries.first).to_contain_text("Demo")
    entries.first.get_by_test_id("browse-open").click()
    expect(page.get_by_test_id("browse-path")).to_have_text(str(copy))
    expect(entries).to_have_text([
        "Extrasfolder", "Show S01E02.mkvvideo", "Show S01E10.mkvvideo", "jfk.en.srtsubtitles",
        "jfk.ja.srtsubtitles", "jfk.mp4video"])
    page.get_by_label("Pick jfk.mp4").check()
    expect(page.get_by_test_id("add-picked")).to_have_text("1 picked")
    page.get_by_test_id("add-start").click()
    start_review(page, 1)
    job = page.get_by_test_id("job")
    expect(job).to_have_count(1)
    expect(job.first).to_have_attribute("data-state", "done", timeout=30_000)
    page.get_by_test_id("nav-add").click()
    page.get_by_test_id("add-paths").fill("/somewhere/else.mkv")
    page.get_by_test_id("add-start").click()
    expect(page.get_by_test_id("add-error")).to_have_text(
        "vid2sub browses your home folder, your drives and network shares only")


TOML = """
[defaults]
youtube_dir = {youtube}
targets = ["en"]

[endpoints.spark]
base_url = "{url}"

[models.spark-turbo]
catalog = "whisper-large-v3-turbo"
endpoint = "spark"
model = "turbo"
parser = "whisper.cpp"
local = true
"""


def test_a_youtube_link_with_keep_video_ticked_lands_whole_in_the_youtube_folder(
        launch, open_page, tmp_path):
    (tmp_path / "clips").mkdir()
    clip = make_clip(tmp_path / "clips", "talk.mkv", seconds=14, speech=SPEECH,
                     audio_langs=("eng",))
    youtube = tmp_path / "YouTube"

    def whisper(req):
        if req.path.endswith("/models"):
            return 200, {"object": "list", "data": [{"id": "turbo", "object": "model"}]}, {}
        return 200, WORDS, {}

    with FakeServer(responder=whisper) as spark:
        server = launch(tmp_path / "server",
                        toml=TOML.format(youtube=json.dumps(str(youtube)), url=spark.url),
                        command=[sys.executable, str(HERE / "fake_youtube.py"), str(clip)])
        watched = open_page(server)
        page = watched.page
        open_add(page)
        page.get_by_test_id("add-link").fill("https://youtu.be/dQw4w9WgXcQ?si=shared")
        page.get_by_test_id("add-keep-video").check()
        page.get_by_test_id("add-start").click()
        start_review(page, 1)
        expect(page.get_by_test_id("job")).to_have_count(1)
        job = page.get_by_test_id("job")
        expect(job).to_have_count(1)
        expect(job.first).to_contain_text("YouTube video dQw4w9WgXcQ")
        expect(job.first).to_have_attribute("data-state", "done", timeout=60_000)
    landed = youtube / "A talk at a college [dQw4w9WgXcQ].mkv"
    assert clip.with_name("ASKED").read_text(encoding="utf-8") == "bv*+ba/b"
    streams = json.loads(subprocess.run(
        [shutil.which("ffprobe"), "-v", "error", "-show_streams", "-of", "json", str(landed)],
        check=True, capture_output=True).stdout)["streams"]
    assert {s["codec_type"] for s in streams} == {"video", "audio"}  # the whole video
    assert landed.with_name("A talk at a college [dQw4w9WgXcQ].en.srt").is_file()
    assert watched.errors == [] and watched.violations() == []
```

- [ ] **Step 7: Run them; watch them fail.** `make test-js`. Expected: its typecheck stops at
  `src/lib/review.test.ts(3,15): error TS2305: Module '"@/types"' has no exported member
  'ReviewRow'.` and `src/lib/review.test.ts(5,78): error TS2307: Cannot find module './review'
  or its corresponding type declarations.` Then `make build` and `uv run pytest -m e2e
  tests/e2e/test_review.py tests/e2e/test_add.py -q`. Expected:
  `E       AssertionError: Locator expected to be visible`, `waiting for
  get_by_test_id("review-page")`, four times, and `4 failed`.
- [ ] **Step 8: Write the code.** In `frontend/src/types.ts`, above
  `/** The \`endpoint_test_result\` message: what an endpoint's /v1/models said, or why it failed. */`,
  add:

```ts
/** A model a Review picker offers (review.model_choices; spec §10.4): its name in vid2sub.toml,
 * the catalog's title and one-liner, and why it can't run now, greyed but still pickable. */
export type ModelChoice = { name: string; title: string; good_for: string; available: boolean; reason: string | null; cloud: boolean };

/** One Review row (views.review_view; spec §10, §19.2): a file by its bare name, never its path. */
export type ReviewRow = {
  id: string;
  name: string;
  folder: string;
  link: boolean;
  state: "waiting" | "sampling" | "ready" | "failed";
  sampled: boolean;
  inherited: boolean;
  duration_ms: number | null;
  audio: { index: number; label: string }[];
  audio_index: number | null;
  detection: { language: string | null; confidence: number; votes: (string | null)[]; mixed: boolean } | null;
  language: string | null;
  ask_zh_yue: boolean;
  transcribe: string | null;
  translate: string | null;
  targets: string[];
  formats: ("srt" | "ass")[];
  script: "hant" | "hans" | null;
  keep_video: boolean;
  warning: string | null;
  error: string | null;
  hint: string | null;
  problem: string | null; // what stops Start, for this row
};

/** The `review` output: the review, `{preparing: true}` while Add's files are read, or null. */
export type ReviewView = {
  rows: ReviewRow[];
  transcribers: ModelChoice[];
  translators: ModelChoice[];
  languages: { code: string; name: string }[];
  targets: { key: string; label: string }[];
  allow_cloud: boolean; // the review's own box: unticked in every new review (spec §7.2)
  can_start: boolean;
};
export type ReviewOutput = ReviewView | { preparing: true } | null;

/** The `review_started` message: Start queued `jobs` jobs for request `n`. */
export type ReviewStartedMessage = { n: number | null; jobs: number };

```

  `frontend/src/lib/review.ts`:

```ts
// The Review screen's words (spec §10, §19.2; S40): a file's length, what was heard in its samples
// and how sure, a model as a picker shows it (greyed with why it can't run now, never passed
// over: §17.4), a row's targets ticked or unticked, and a row as the page shows it while a choice
// is on its way to the engine. A row is named by its file, never its path.

import type { ModelChoice, ReviewOutput, ReviewRow, ReviewView } from "@/types";

/** 23:45, or 1:02:03 for an hour or more. */
export function duration(ms: number | null): string {
  if (ms === null) return "";
  const s = Math.round(ms / 1000);
  const two = (n: number) => String(n).padStart(2, "0");
  return s >= 3600 ? `${Math.floor(s / 3600)}:${two(Math.floor((s % 3600) / 60))}:${two(s % 60)}` : `${Math.floor(s / 60)}:${two(s % 60)}`;
}

/** What the samples heard: "Japanese, 90% sure", "Mandarin or Cantonese?", or why not. */
export function heard(row: ReviewRow, languages: ReviewView["languages"]): string {
  const name = (code: string | null) => languages.find((l) => l.code === code)?.name ?? code ?? "?";
  if (row.link) return "decided when it runs";
  if (row.state === "waiting") return "waiting to be sampled";
  if (row.state === "sampling") return "sampling…";
  if (row.ask_zh_yue) return "Mandarin or Cantonese?";
  const d = row.detection;
  if (row.inherited) return `${name(row.language)}, like the files sampled in this folder`;
  if (!d) return row.language ? name(row.language) : "not detected";
  if (!d.language) return "no speech heard";
  const sure = `${name(d.language)}, ${Math.round(d.confidence * 100)}% sure`;
  return d.mixed ? `${sure}; the samples disagree (${d.votes.map((v) => v ?? "?").join(", ")})` : sure;
}

/** A model as its picker lists it. */
export function choiceLabel(c: ModelChoice): string {
  const cloud = c.cloud ? " (cloud)" : "";
  return c.available ? `${c.name}: ${c.title}${cloud}` : `${c.name}: ${c.title}${cloud}, can't run now`;
}

/** The targets with `key` ticked or unticked, in `order`; none means captions only. */
export function toggled(targets: readonly string[], key: string, on: boolean, order: readonly string[]): string[] {
  const next = new Set(targets);
  if (on) next.add(key);
  else next.delete(key);
  return order.filter((k) => next.has(k));
}

/** A choice as `review_choose` sends it: a row's fields, the audio track as its index. */
export type Changes = Record<string, string | number | string[] | null>;

/** The row as the page shows it until the engine's review comes back with the choice applied, so
 * a control doesn't spring back to the old value meanwhile; the engine's answer replaces it. */
export function withPending(row: ReviewRow, changes: Changes | undefined): ReviewRow {
  if (!changes) return row;
  const { audio_track, ...rest } = changes;
  return { ...row, ...rest, ...(audio_track !== undefined ? { audio_index: audio_track as number } : {}) } as ReviewRow;
}

export function isReview(out: ReviewOutput | undefined): out is ReviewView {
  return Boolean(out && "rows" in out);
}
```

  `frontend/src/components/ReviewPage.tsx`:

```tsx
import { type ReactNode, useEffect, useState } from "react";

import { type Changes, choiceLabel, duration, heard, toggled, withPending } from "@/lib/review";
import type { ModelChoice, ReviewRow, ReviewView } from "@/types";

const button = "rounded-md border border-input bg-background px-2 py-1 text-sm focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ring disabled:opacity-50";
const select = "rounded-md border border-input bg-background px-1 py-0.5 text-sm focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ring disabled:opacity-50";
const toAll = "text-xs underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-ring disabled:opacity-50";

export type { Changes };

/** The Review screen (spec §10, §19.2; S40): one row per file Add took, by its bare name, with
 * its length, its audio track, what its samples heard and how sure ("Mandarin or Cantonese?" when
 * Whisper heard `zh`), the transcription and translation models (each with the catalog's title,
 * greyed with why it can't run now), its targets, its formats and, for Mandarin, its script.
 * Rows fill in as the first two files of each folder are sampled; the rest inherit and say so.
 * Each choice has "Apply to all". **Allow cloud models for this run** is drawn only from the
 * review, which starts it unticked every time (§7.2); a choice shows at once, and the engine's
 * review replaces it when it comes back. Start queues every row that can run and
 * opens the Jobs page; a row that can't says why, and Start waits. Names, warnings and reasons
 * are plain text (§6.3); every control is native, so it all works from the keyboard. */
export function ReviewPage({ review, preparing, onChoose, onApply, onCloud, onStart, onDiscard }: {
  review: ReviewView | null;
  preparing: boolean;
  onChoose: (row: string, changes: Changes) => void;
  onApply: (row: string, field: string) => void;
  onCloud: (allowed: boolean) => void;
  onStart: () => void;
  onDiscard: () => void;
}) {
  const [pending, setPending] = useState<{ cloud?: boolean; rows: Record<string, Changes> }>({ rows: {} });
  useEffect(() => setPending({ rows: {} }), [review]); // the engine's answer replaces what was shown
  if (!review) {
    return (
      <div className="p-4 text-muted-foreground" data-testid="review-page">
        {preparing ? <p role="status" data-testid="review-preparing">Reading the files…</p> : <p>Nothing to review: add videos first.</p>}
      </div>
    );
  }
  const stopping = review.rows.filter((r) => r.problem).length;
  const choose = (row: string, changes: Changes) => {
    setPending((p) => ({ ...p, rows: { ...p.rows, [row]: { ...p.rows[row], ...changes } } }));
    onChoose(row, changes);
  };
  const cloud = (allowed: boolean) => {
    setPending((p) => ({ ...p, cloud: allowed }));
    onCloud(allowed);
  };
  return (
    <div className="flex h-full min-h-0 flex-col gap-3 overflow-y-auto p-4" data-testid="review-page">
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={pending.cloud ?? review.allow_cloud} onChange={(e) => cloud(e.target.checked)} data-testid="review-cloud" />
          Allow cloud models for this run
        </label>
        <span className="ml-auto flex items-center gap-2">
          {stopping > 0 && <span className="text-muted-foreground" data-testid="review-waiting">{stopping === 1 ? "1 file needs a choice" : `${stopping} files need a choice`}</span>}
          <button type="button" className={button} onClick={onDiscard} data-testid="review-discard">Discard</button>
          <button type="button" className="rounded-md bg-primary px-3 py-1 font-bold text-primary-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:opacity-50" onClick={onStart} disabled={!review.can_start} data-testid="review-start">Start</button>
        </span>
      </div>
      <ol aria-label="Files to review" className="flex flex-col gap-2" data-testid="review-rows">
        {review.rows.map((row) => <RowCard key={row.id} row={withPending(row, pending.rows[row.id])} review={review} onChoose={choose} onApply={onApply} />)}
      </ol>
    </div>
  );
}

function RowCard({ row, review, onChoose, onApply }: {
  row: ReviewRow;
  review: ReviewView;
  onChoose: (row: string, changes: Changes) => void;
  onApply: (row: string, field: string) => void;
}) {
  const ready = row.state === "ready";
  const choose = (changes: Changes) => onChoose(row.id, changes);
  const all = (field: string, label: string) => (
    <button type="button" className={toAll} onClick={() => onApply(row.id, field)} disabled={!ready} aria-label={`Apply ${label} to all files`} data-testid={`review-all-${field}`}>Apply to all</button>
  );
  const id = (field: string) => `review-${row.id}-${field}`;
  return (
    <li className="flex flex-col gap-2 rounded-md border border-border bg-card p-2 text-sm" data-testid="review-row" data-state={row.state} data-row={row.id}>
      <div className="flex flex-wrap items-baseline gap-2">
        <span className="font-bold break-all" data-testid="review-name">{row.name}</span>
        {row.folder && <span className="text-muted-foreground">in {row.folder}</span>}
        {row.duration_ms !== null && <span className="text-muted-foreground">{duration(row.duration_ms)}</span>}
        {row.sampled && <span className="rounded bg-muted px-1 text-xs">sampled</span>}
        {row.inherited && <span className="rounded bg-muted px-1 text-xs" data-testid="review-inherited">inherited</span>}
        <span className="text-muted-foreground" data-testid="review-heard">{heard(row, review.languages)}</span>
      </div>
      {row.state === "failed" ? (
        <p className="text-destructive" data-testid="review-error">can't run: {row.error ?? "it failed"}</p>
      ) : (
        <div className="grid grid-cols-[repeat(auto-fit,minmax(14rem,1fr))] gap-2">
          {!row.link && row.audio.length > 1 && (
            <Field label="Audio track" htmlFor={id("audio")}>
              <select id={id("audio")} className={select} value={row.audio_index ?? ""} disabled={!ready} onChange={(e) => choose({ audio_track: Number(e.target.value) })} data-testid="review-audio">
                {row.audio.map((a) => <option key={a.index} value={a.index}>{a.label}</option>)}
              </select>
            </Field>
          )}
          {!row.link && (
            <Field label={row.ask_zh_yue ? "Mandarin or Cantonese?" : "Language"} htmlFor={id("language")} extra={all("language", "the language")}>
              <select id={id("language")} className={select} value={row.language ?? ""} disabled={!ready} onChange={(e) => choose({ language: e.target.value })} data-testid="review-language">
                <option value="" disabled>Pick one</option>
                {(row.ask_zh_yue ? review.languages.filter((l) => l.code === "zh" || l.code === "yue") : review.languages).map((l) => <option key={l.code} value={l.code}>{l.name}</option>)}
              </select>
            </Field>
          )}
          {!row.link && (
            <Field label="Transcription model" htmlFor={id("transcribe")} extra={all("transcribe", "the transcription model")} note={note(review.transcribers, row.transcribe)}>
              <Picker id={id("transcribe")} choices={review.transcribers} value={row.transcribe} disabled={!ready} onPick={(name) => choose({ transcribe: name })} testId="review-transcribe" />
            </Field>
          )}
          {!row.link && (
            <Field label="Translation model" htmlFor={id("translate")} extra={all("translate", "the translation model")} note={note(review.translators, row.translate)}>
              <Picker id={id("translate")} choices={review.translators} value={row.translate} disabled={!ready} none="None" onPick={(name) => choose({ translate: name })} testId="review-translate" />
            </Field>
          )}
          {!row.link && row.language === "zh" && (
            <Field label="Chinese script" htmlFor={id("script")} extra={all("script", "the script")}>
              <select id={id("script")} className={select} value={row.script ?? ""} disabled={!ready} onChange={(e) => choose({ script: e.target.value || null })} data-testid="review-script">
                <option value="">Simplified (the default)</option>
                <option value="hant">Traditional</option>
                <option value="hans">Simplified</option>
              </select>
            </Field>
          )}
          <fieldset className="flex flex-col gap-1" disabled={!ready}>
            <legend className="text-xs font-bold">Subtitles in</legend>
            <span className="flex flex-wrap gap-x-3">
              {review.targets.map((t) => (
                <label key={t.key} className="flex items-center gap-1">
                  <input type="checkbox" checked={row.targets.includes(t.key)} onChange={(e) => choose({ targets: toggled(row.targets, t.key, e.target.checked, review.targets.map((x) => x.key)) })} data-testid={`review-target-${t.key}`} />
                  {t.label}
                </label>
              ))}
            </span>
            {all("targets", "the targets")}
          </fieldset>
          <fieldset className="flex flex-col gap-1" disabled={!ready}>
            <legend className="text-xs font-bold">Formats</legend>
            <span className="flex gap-3">
              <label className="flex items-center gap-1"><input type="checkbox" checked disabled /> SRT</label>
              <label className="flex items-center gap-1">
                <input type="checkbox" checked={row.formats.includes("ass")} onChange={(e) => choose({ formats: e.target.checked ? ["srt", "ass"] : ["srt"] })} data-testid="review-ass" /> ASS too
              </label>
            </span>
            {all("formats", "the formats")}
          </fieldset>
        </div>
      )}
      {row.link && <p className="text-muted-foreground">{row.keep_video ? "Keeps the whole video." : "Keeps the audio only."} Its language and models are chosen when it runs, as <code>vid2sub run</code> chooses them.</p>}
      {row.warning && <p className="text-muted-foreground" data-testid="review-warning">{row.warning}</p>}
      {row.hint && <p data-testid="review-hint">→ {row.hint}</p>}
      {row.problem && <p className="font-bold text-destructive" data-testid="review-problem">{row.problem}</p>}
    </li>
  );
}

function note(choices: readonly ModelChoice[], value: string | null): string | null {
  const c = choices.find((x) => x.name === value);
  if (!c) return null;
  return c.available ? c.good_for || null : `can't run now: ${c.reason ?? "unknown"}`;
}

function Field({ label, htmlFor, extra, note: text, children }: {
  label: string; htmlFor: string; extra?: ReactNode; note?: string | null; children: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={htmlFor} className="text-xs font-bold">{label}</label>
      {children}
      {text && <span className="text-xs text-muted-foreground">{text}</span>}
      {extra}
    </div>
  );
}

function Picker({ id, choices, value, disabled, none, onPick, testId }: {
  id: string; choices: readonly ModelChoice[]; value: string | null; disabled: boolean; none?: string;
  onPick: (name: string | null) => void; testId: string;
}) {
  return (
    <select id={id} className={select} value={value ?? ""} disabled={disabled} onChange={(e) => onPick(e.target.value || null)} data-testid={testId}>
      {none ? <option value="">{none}</option> : <option value="" disabled>Pick one</option>}
      {choices.map((c) => <option key={c.name} value={c.name} className={c.available ? "" : "text-muted-foreground"}>{choiceLabel(c)}</option>)}
    </select>
  );
}
```

  In `frontend/src/components/AddPage.tsx`, replace
  `<span className="text-muted-foreground">They run one at a time, with the session's targets and formats (Settings).</span>`
  with
  `<span className="text-muted-foreground">Review comes next: what was heard in each file, and the models it suggests.</span>`.
  Replace `frontend/src/App.tsx` with:

```tsx
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { AddPage } from "@/components/AddPage";
import { Editor, type Requests, type Saving } from "@/components/Editor";
import { JobsPage } from "@/components/JobsPage";
import { ReviewPage } from "@/components/ReviewPage";
import { resultNotices } from "@/components/SaveBar";
import { type DefaultsChange, SettingsDrawer } from "@/components/SettingsDrawer";
import { TopBar } from "@/components/TopBar";
import { type AddRequest, type BrowseState, NOT_ASKED, answered, asked } from "@/lib/browse";
import { LOST_MESSAGES, type Lost, whyLost } from "@/lib/connection";
import { type Draft, type DraftStep, addStep, clearDraft, draftKey, draftStorage, dropRetranslation, loadDraft, replayable } from "@/lib/draft";
import { type Shown, addNotice, dismissNotice } from "@/lib/notices";
import { retranslateNotice } from "@/lib/retranslate";
import { type Changes, isReview } from "@/lib/review";
import { pacer } from "@/lib/sends";
import { useSetShinyInput, useShinyInitialized, useShinyMessageHandler, useShinyOutputValue } from "@/sr";
import type { AddResultMessage, BrowseResult, Busy, Capabilities, EditOp, EndpointTestResult, EpisodeView, JobsView, Progress, RetranslateResultMessage, ReviewOutput, ReviewStartedMessage, SaveResultMessage, SettingsView, Status } from "@/types";

type Ask = { episode: string; n: number };

const SCREENS = { editor: "Editor", add: "Add", review: "Review", jobs: "Jobs" } as const;
type Screen = keyof typeof SCREENS;

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
  const episode = useShinyOutputValue<EpisodeView | null>("episode");
  const busy = useShinyOutputValue<Busy>("busy");
  const progress = useShinyOutputValue<Progress>("progress");
  const settings = useShinyOutputValue<SettingsView | null>("settings");
  const jobs = useShinyOutputValue<JobsView | null>("jobs");
  const reviewOut = useShinyOutputValue<ReviewOutput>("review");
  // Every input is set from here too. Each request carries a count, so the same path asked for
  // twice is still two requests, and "event" sends it at once, never merged with the next.
  const setOpen = useSetShinyInput<{ path: string; n: number } | null>("open", null, { priority: "event", debounceMs: 0 });
  const setPlayback = useSetShinyInput<{ episode: string; n: number } | null>("playback", null, { priority: "event", debounceMs: 0 });
  const setEdit = useSetShinyInput<(Ask & { op: EditOp }) | null>("edit", null, { priority: "event", debounceMs: 0 });
  const setUndo = useSetShinyInput<Ask | null>("undo", null, { priority: "event", debounceMs: 0 });
  const setRedo = useSetShinyInput<Ask | null>("redo", null, { priority: "event", debounceMs: 0 });
  const setSave = useSetShinyInput<(Ask & { formats: ("srt" | "ass")[] }) | null>("save", null, { priority: "event", debounceMs: 0 });
  const setResolve = useSetShinyInput<(Ask & { track: string; rendition: string }) | null>("resolve", null, { priority: "event", debounceMs: 0 });
  const setRetranslate = useSetShinyInput<(Ask & { track: string; ids: string[] | null; allow_cloud: boolean }) | null>("retranslate", null, { priority: "event", debounceMs: 0 });
  const setTypedKey = useSetShinyInput<{ endpoint: string; key: string; n: number } | null>("typed_key", null, { priority: "event", debounceMs: 0 });
  const setEndpointTest = useSetShinyInput<{ endpoint: string; n: number } | null>("endpoint_test", null, { priority: "event", debounceMs: 0 });
  const setDefaults = useSetShinyInput<(DefaultsChange & { n: number }) | null>("session_defaults", null, { priority: "event", debounceMs: 0 });
  const setJobsSubmit = useSetShinyInput<{ paths: string[]; n: number } | null>("jobs_submit", null, { priority: "event", debounceMs: 0 });
  const setJobCancel = useSetShinyInput<{ job: string; n: number } | null>("job_cancel", null, { priority: "event", debounceMs: 0 });
  const setBrowse = useSetShinyInput<{ path: string | null; n: number } | null>("browse", null, { priority: "event", debounceMs: 0 });
  const setAdd = useSetShinyInput<(AddRequest & { n: number }) | null>("add", null, { priority: "event", debounceMs: 0 });
  const setReviewChoose = useSetShinyInput<{ row: string; changes: Changes; n: number } | null>("review_choose", null, { priority: "event", debounceMs: 0 });
  const setReviewApply = useSetShinyInput<{ row: string; field: string; n: number } | null>("review_apply", null, { priority: "event", debounceMs: 0 });
  const setReviewCloud = useSetShinyInput<{ allowed: boolean; n: number } | null>("review_cloud", null, { priority: "event", debounceMs: 0 });
  const setReviewStart = useSetShinyInput<{ n: number } | null>("review_start", null, { priority: "event", debounceMs: 0 });
  const setReviewDiscard = useSetShinyInput<{ n: number } | null>("review_discard", null, { priority: "event", debounceMs: 0 });
  const sent = useRef(0);
  // One request per task, in order: shinyreact's debounce keeps only the last value set in a task.
  const pace = useMemo(() => pacer(), []);

  // The crash-recovery draft (spec §14.5, S34): every edit, undo and redo is also written to
  // localStorage under the heads the episode was opened at, and offered back when it is opened
  // again. When a Save or a pick moves the heads, the draft goes with them while edits are still
  // unsaved (a pick keeps the other tracks' edits), and is cleared once everything is saved.
  const [offer, setOffer] = useState<Draft | null>(null);
  const drafted = useRef<{ id: string; key: string } | null>(null);
  useEffect(() => {
    if (!episode) {
      drafted.current = null;
      return;
    }
    const key = draftKey(episode.heads);
    const was = drafted.current;
    const store = draftStorage();
    if (was?.id === episode.id && was.key !== key) {
      const kept = loadDraft(store, was.key);
      clearDraft(store, was.key);
      if (kept && episode.dirty) for (const step of kept.steps) addStep(store, key, step, new Date(kept.at));
    }
    if (was?.id !== episode.id) setOffer(loadDraft(store, key));
    drafted.current = { id: episode.id, key };
  }, [episode]);
  const record = useCallback((step: DraftStep) => {
    const at = drafted.current;
    if (!at) return;
    if (offer) { // editing again without restoring: the old draft is discarded
      clearDraft(draftStorage(), at.key);
      setOffer(null);
    }
    addStep(draftStorage(), at.key, step);
  }, [offer]);

  // A retranslation goes in the draft as a marker only (never replayed: a restored draft asks no
  // model), dropped when the server says it changed nothing; `asking` remembers which were
  // "Retranslate stale", for the notice.
  const asking = useRef(new Map<number, { track: string; stale: boolean }>());
  const episodeId = episode?.id ?? null;
  const requests = useMemo<Requests>(() => {
    const ask = (): Ask | null => (episodeId ? { episode: episodeId, n: ++sent.current } : null);
    const send = <T,>(set: (v: T) => void, value: T | null) => value && pace(() => set(value));
    return {
      edit: (op) => { record({ edit: op }); const a = ask(); send(setEdit, a && { ...a, op }); },
      undo: () => { record({ undo: true }); send(setUndo, ask()); },
      redo: () => { record({ redo: true }); send(setRedo, ask()); },
      save: (formats) => { const a = ask(); send(setSave, a && { ...a, formats }); },
      resolve: (track, rendition) => { const a = ask(); send(setResolve, a && { ...a, track, rendition }); },
      retranslate: (track, ids, allowCloud) => {
        const a = ask();
        if (!a) return;
        record({ retranslate: a.n });
        asking.current.set(a.n, { track, stale: ids === null });
        send(setRetranslate, { ...a, track, ids, allow_cloud: allowCloud });
      },
    };
  }, [episodeId, pace, record, setEdit, setUndo, setRedo, setSave, setResolve, setRetranslate]);
  useShinyMessageHandler("retranslate_result", (data: RetranslateResultMessage) => {
    if (!episode || data.episode !== episode.id || data.n === null) return;
    const asked = asking.current.get(data.n);
    asking.current.delete(data.n);
    if (data.changed === 0 && drafted.current) dropRetranslation(draftStorage(), drafted.current.key, data.n);
    if (!asked) return;
    const label = episode.tracks.find((t) => t.key === asked.track)?.label ?? asked.track;
    const n = retranslateNotice(data.changed, label, asked.stale);
    if (n) setNotices((shown) => addNotice(shown, n, nextId.current++));
  });

  const [conflictsFound, setConflictsFound] = useState(0);
  useShinyMessageHandler("save_result", (data: SaveResultMessage) => {
    if (!episode || data.episode !== episode.id) return;
    for (const n of resultNotices(data, episode.tracks)) setNotices((shown) => addNotice(shown, n, nextId.current++));
    if (data.conflicts.length) setConflictsFound((k) => k + 1);
  });
  const offered = offer ? replayable(offer.steps).length : 0; // the steps Restore would send
  const saving: Saving = {
    draft: offer && offered ? { at: offer.at, steps: offered } : null,
    conflictsFound,
    onRestore: () => {
      const steps = offer?.steps ?? [];
      if (drafted.current) clearDraft(draftStorage(), drafted.current.key);
      setOffer(null);
      for (const step of replayable(steps)) {
        if ("edit" in step) requests.edit(step.edit);
        else if ("undo" in step) requests.undo();
        else if ("redo" in step) requests.redo();
      }
    },
    onDiscard: () => {
      if (drafted.current) clearDraft(draftStorage(), drafted.current.key);
      setOffer(null);
    },
  };

  // The settings drawer (spec §19.2, S35). A typed key is sent once, and null straight after, in
  // a task of its own: Shiny's input map on the server, its copy in the page, and shinyreact's
  // keep each input's last value, and the null replaces the key in all three (§5.3). It is never
  // kept anywhere else in the page: not in state, storage, the draft or a notice.
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [tests, setTests] = useState<Record<string, EndpointTestResult | "testing">>({});
  useShinyMessageHandler("endpoint_test_result", (r: EndpointTestResult) => {
    if (typeof r?.endpoint === "string") setTests((t) => ({ ...t, [r.endpoint]: r }));
  });
  const onTypedKey = (endpoint: string, key: string) => {
    const n = ++sent.current;
    pace(() => setTypedKey({ endpoint, key, n }));
    pace(() => setTypedKey(null));
  };
  const onTest = (endpoint: string) => {
    setTests((t) => ({ ...t, [endpoint]: "testing" }));
    const n = ++sent.current;
    pace(() => setEndpointTest({ endpoint, n }));
  };
  const onDefaults = (change: DefaultsChange) => {
    const n = ++sent.current;
    pace(() => setDefaults({ ...change, n }));
  };

  // Add, Review and the Jobs page (spec §19.2; S36, S38–S40), where the engine makes subtitles
  // (`generate`; Pages hides them, §21). The editor stays mounted while they show, so the player
  // keeps its place.
  const [screen, setScreen] = useState<Screen>("editor");
  const generate = capabilities?.generate ?? false;
  const onSubmitJobs = (paths: string[]) => {
    const n = ++sent.current;
    pace(() => setJobsSubmit({ paths, n }));
  };
  const onCancelJob = (job: string) => {
    const n = ++sent.current;
    pace(() => setJobCancel({ job, n }));
  };
  const onOpenJob = (path: string) => {
    setOpen({ path, n: ++sent.current });
    setScreen("editor");
  };

  // Add (Phase 3): the file browser shows the answer to the folder it asked for last, and says
  // it's waiting until then (a sleeping network share, Review Focus 1); a finished Add opens
  // Review, and one that took nothing says why on the Add screen.
  const [browse, setBrowseState] = useState<BrowseState>(NOT_ASKED);
  useShinyMessageHandler("browse_result", (r: BrowseResult) => setBrowseState((s) => answered(s, r)));
  const onBrowse = useCallback((path: string | null) => {
    const n = ++sent.current;
    setBrowseState((s) => asked(s, n, path));
    pace(() => setBrowse({ path, n }));
  }, [pace, setBrowse]);
  const [adding, setAdding] = useState<number | null>(null);
  const [addError, setAddError] = useState<string | null>(null);
  useShinyMessageHandler("add_result", (r: AddResultMessage) => {
    if (r?.n !== adding) return;
    setAdding(null);
    setAddError(r.error);
    if (!r.error) setScreen("review");
  });
  const onAdd = (request: AddRequest) => {
    const n = ++sent.current;
    setAdding(n);
    setAddError(null);
    pace(() => setAdd({ ...request, n }));
  };

  // Review (Phase 3, S40): the server's review of what Add took, choices sent one per task in
  // order; Start opens the Jobs page once the server says it queued them.
  const reviewing = {
    onChoose: (row: string, changes: Changes) => { const n = ++sent.current; pace(() => setReviewChoose({ row, changes, n })); },
    onApply: (row: string, field: string) => { const n = ++sent.current; pace(() => setReviewApply({ row, field, n })); },
    onCloud: (allowed: boolean) => { const n = ++sent.current; pace(() => setReviewCloud({ allowed, n })); },
    onStart: () => { const n = ++sent.current; pace(() => setReviewStart({ n })); },
    onDiscard: () => { const n = ++sent.current; pace(() => setReviewDiscard({ n })); },
  };
  useShinyMessageHandler("review_started", (_: ReviewStartedMessage) => setScreen("jobs"));

  // Closing the tab with unsaved edits warns first (S34): listened for only while there are
  // some, as MDN advises; preventDefault, and returnValue for older browsers.
  const dirty = episode?.dirty ?? false;
  useEffect(() => {
    if (!dirty) return;
    const warn = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = true;
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);
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
      <TopBar capabilities={capabilities} status={status} onSettings={capabilities?.generate ? () => setSettingsOpen(true) : undefined} />
      <SettingsDrawer open={settingsOpen && Boolean(settings)} onClose={() => setSettingsOpen(false)} connected={lost === null} settings={settings ?? null}
        tests={tests} onTest={onTest} onTypedKey={onTypedKey} onDefaults={onDefaults} />
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
      {generate && (
        <nav aria-label="Screens" className="flex gap-1 border-b border-border bg-card px-4 text-sm">
          {(["editor", "add", "review", "jobs"] as const).map((s) => (
            <button key={s} type="button" aria-current={screen === s ? "page" : undefined} onClick={() => setScreen(s)}
              className={`border-b-2 px-2 py-1.5 focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ring ${screen === s ? "border-(--brand-orange) font-bold" : "border-transparent"}`} data-testid={`nav-${s}`}>
              {SCREENS[s]}
            </button>
          ))}
        </nav>
      )}
      {generate && screen === "add" && (
        <section aria-label="Add" className="min-h-0 flex-1">
          <AddPage browse={browse} onBrowse={onBrowse} onAdd={onAdd} adding={adding !== null} error={addError} />
        </section>
      )}
      {generate && screen === "review" && (
        <section aria-label="Review" className="min-h-0 flex-1">
          <ReviewPage review={isReview(reviewOut) ? reviewOut : null} preparing={Boolean(reviewOut && "preparing" in reviewOut)} {...reviewing} />
        </section>
      )}
      {generate && screen === "jobs" && (
        <section aria-label="Jobs" className="min-h-0 flex-1">
          <JobsPage jobs={jobs?.jobs ?? []} onSubmit={onSubmitJobs} onCancel={onCancelJob} onOpen={onOpenJob} />
        </section>
      )}
      <main className="min-h-0 flex-1" hidden={generate && screen !== "editor"} data-testid="main">
        <Editor
          episode={episode ?? null}
          busy={busy ?? null}
          progress={progress ?? null}
          pathInput={capabilities?.path_input ?? false}
          generate={generate}
          onOpen={(path) => setOpen({ path, n: ++sent.current })}
          onCantPlay={() => episode && setPlayback({ episode: episode.id, n: ++sent.current })}
          requests={requests}
          saving={saving}
        />
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

- [ ] **Step 9: Run the checks; they pass.** `make test-js` first (`Test Files  21 passed (21)`,
  `Tests  97 passed (97)`), then `make check` and `make e2e`. Expected: `make check`:
  `1177 passed, 7 skipped, 40 deselected` twice, `Test Files  21 passed (21)` and
  `Tests  97 passed (97)`, `All checks passed!` and `no leaks found`; `make e2e`:
  `35 passed, 1189 deselected`. The Allow cloud browser test pins what the engine's review does:
  the page holds no box of its own beyond a choice on its way.
- [ ] **Step 10: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(ui): 🤖 the Review screen shows each file's samples, suggestions and choices, applies one to all, and starts them

The page's half of Review (spec §10, §19.2, §7.2; S40). A Review screen
beside Editor, Add and Jobs, where generate is true; a finished Add
opens it, saying "Reading the files…" until the engine's review comes.
One card per file, by its bare name, with its folder and length, its
audio track (when it has more than one), what its samples heard and how
sure ("Mandarin or Cantonese?" when Whisper heard zh; "like the files
sampled in this folder" when it inherited), the transcription and
translation models with the catalog's titles (greyed with why one can't
run now, but still pickable), its targets, SRT and ASS too, and for
Mandarin its script, each with "Apply to all"; its warning, fix and what
stops Start. A YouTube row says its language and models are chosen when
it runs. Allow cloud models for this run is drawn from the engine's
review, unticked in every new one; Start, enabled only when every row
can run, opens the Jobs page once the engine says it queued them;
Discard empties the screen. A choice shows at once and the engine's
review replaces it when it comes back, so a control doesn't spring back
meanwhile. Every control is native, so it works from the keyboard;
every name and reason is plain text. The Add screen now says Review
comes next.

The browser tests: a season of three copies of the demo's clip, added
through the browser, is sampled (two) and inherited (one), heard as
English, 100% sure, suggested the canned models, ASS ticked on one and
applied to all, and started: three jobs done, each writing its .ja.ass.
Allow cloud ticked in one review is unticked in the next. Task 2's Add
tests go through Review's Start.

The new tests failed first with: error TS2307: Cannot find module
'./review' (make test-js's typecheck), and in Chromium, Locator expected
to be visible, waiting for get_by_test_id("review-page") (four times).
The Allow cloud browser test pins what the engine's review already
does: the page holds no box of its own.

Docs read: React 19.2.8's types (useState, useEffect); MDN on
<fieldset disabled> (it disables every control inside), <select> and
<label for>; Playwright 1.64.1's Python API (to_have_value,
to_be_enabled, to_be_checked; Locator.check fails when the box doesn't
stay checked, which is why a choice shows at once).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md Task 4
Co-Authored-By: <the model's own line>
```

  `git add frontend/src/App.tsx frontend/src/components/AddPage.tsx frontend/src/types.ts
  frontend/src/components/ReviewPage.tsx frontend/src/lib/review.ts
  frontend/src/lib/review.test.ts tests/e2e/test_add.py tests/e2e/test_review.py`,
  `git commit -F .git/COMMIT_MSG`, then `git log -1 --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 11: Review, look forward, close.** The Tier 2 review from `$(cat .git/TASK_BASE)`
  (`AGENTS.md`, *Reviews*). Worth the reviewers' time: that no path reaches the view (§6.8) and
  every choice from the page is checked by the core and echoed nowhere; that a late row from an
  ended review never lands in a new one; that Allow cloud is drawn only from the review, which
  starts it unticked (§7.2); that the row's targets and formats, not the session's, reach each
  job. The forward review over Tasks 6, 8, 11 and 12: Task 6's Jobs page shows Review's jobs like
  any other; Task 8's Models page may reuse `review.model_choices` and `choiceLabel`; Task 11
  documents Add, Review, Discard and the demo's canned suggestions; Task 12's Step 4 runs this
  screen. The docs this task made untrue: none expected (grep `README.md` and `docs/` for
  "Review"). Then the close, its own commit, holding this plan with this task's boxes ticked and
  **Now** set to `Task 5: The queue pauses and resumes, open.`, and the spec's S40 row set to
  `built`, its proof `tests/test_review.py`; `tests/test_web_review.py`;
  `tests/e2e/test_review.py`. The message, in `.git/CLOSE_MSG`:

```text
docs(plan): 🤖 close Task 4: The Review screen

Drift: none
Rulings: none
Phase-end: none
Forward: none
Tier: 2
Rounds: none
Findings: none

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md Task 4
Co-Authored-By: <the model's own line>
```

  `git add docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md
  docs/superpowers/specs/2026-10-14-vid2sub-design.md`, `git commit -F .git/CLOSE_MSG`.

***

### Task 5: The queue pauses and resumes

**Tier:** 2 · **Scenarios:** S41, S42

**Files:**
- Modify: `src/vid2sub/jobs.py` (the queue's states, Pause and Resume; keeping the machine awake),
  `tests/fakes.py` (`FakeServer`'s responder may return None to drop the connection)
- Test: `tests/test_jobs.py`, `tests/test_awake.py`

**Interfaces:**
- Consumes: `pipeline.Paused` (`.error`, an `EngineError` with `.kind` and `.hint`, raised by
  `run_one` once a connection error or a Spark refusal outlasts `RunOptions.wait_on_connection_s`),
  `pipeline.Cancelled`, `pipeline.run_one` and `RunContext.chunk_cache` (shared by every
  `dataclasses.replace` copy, so a resumed job's finished chunks are kept, spec §8.9);
  `awake.keep_awake` (M1); Task 2's `Queue.submit(…, runner=)`; Phase 2 Task 19's
  `Queue.on_change(fn) -> stop` and `JobView.stopping` (set when Cancel is asked of the running
  job, cleared when it ends). Pause and Resume tell the same listeners; `stopping` is Cancel's
  alone, so Pause leaves it false and a requeued job always has it false.
- Produces (`vid2sub.jobs`):
  - `QueueState = Literal["running", "paused"]`; `Awake = Callable[[],
    contextlib.AbstractContextManager]`
  - `@dataclass(frozen=True) class QueueStatus: state: QueueState = "running";
    reason: str | None = None; hint: str | None = None; kind: str | None = None` (`reason` is
    the connection error's message, fit to show, and None for the person's Pause; `hint` its fix
    (spec §17.3); `kind` is `"paused"` for the person's Pause, else the error's kind,
    `"connection"` or `"refused"`: safe to log)
  - `Queue.__init__(self, runner: Runner, *, awake: Awake = keep_awake)`
  - `Queue.pause(self) -> bool` (False if already paused, or closed); `Queue.resume(self) ->
    bool` (False if it wasn't paused); `Queue.status(self) -> QueueStatus`
  - A runner that raises `Paused` pauses the whole queue with the error's reason, hint and
    kind; the person's `pause()` asks the running job to stop at its next check (its
    `cancelled()` turns true, as for Cancel). Either way the job goes back to the head of the
    queue as `queued`, keeping its own runner, stage and progress, and nothing starts until
    `resume()`, which runs it again from the chunk that failed (its runner's shared chunk cache),
    with the same model. Cancel beats Pause; a job cancelled while it lost its connection stays
    cancelled; `close()` works while paused. Other errors fail only their job, as before.
    Listeners also fire on pause and resume (on the thread that made the change).
    `JobView.stopping` stays Cancel's alone: Pause never sets it, and a requeued job has it
    false. `Queue.on_change(fn)` still returns its stop function (Phase 2 Task 19).
  - The machine is kept awake (`awake()` entered on the worker thread) from the first job after
    an idle spell until nothing waits, the queue pauses or it closes; a helper that won't start
    is logged by kind and the queue runs on.
  - What Task 6 calls: `queue.pause()` and `queue.resume()` from the Pause and Resume buttons
    (cheap: on the event loop), and `queue.status()` beside `queue.jobs()` in the `jobs` output
    (the banner shows `reason` and `hint` when `kind != "paused"`); listeners as Phase 2 Task 19
    uses them, hopping to the session's loop.

- [ ] **Step 0: Record the base:** `git rev-parse HEAD > .git/TASK_BASE`.
- [ ] **Step 1: Write the failing tests.** In `tests/test_jobs.py`, replace

```python
import pytest

from vid2sub import jobs
from vid2sub.pipeline import Cancelled, InputResult
```

  with

```python
import pytest
from fakes import FakeEngine, FakeServer
from helpers import SPEECH, make_clip

from vid2sub import jobs
from vid2sub.config import Config, Endpoint, ModelEntry
from vid2sub.engines.base import EngineError
from vid2sub.engines.clients import KeyRing
from vid2sub.media.tools import Tools
from vid2sub.pipeline import Cancelled, InputResult, Paused, RunContext, RunOptions, run_one
```

  and append, after two blank lines:

```python
# Phase 3, Task 5: a dropped connection pauses the whole queue; Resume carries on (S41, §17.3)


DOWN = EngineError("connection", "couldn't reach the server",
                   hint="is it running? For the Spark: is `make tunnel` running?")


class Dropping:
    """A runner whose first try at each input in `drops` loses the connection for good."""

    def __init__(self, drops=()):
        self.drops = set(drops)
        self.tries: list[str] = []

    def __call__(self, source, event, cancelled):
        self.tries.append(source)
        if source in self.drops:
            self.drops.discard(source)
            event("chunk", {"index": 7, "of": 11})
            raise Paused(DOWN)
        return InputResult(input=source, status="done")


def test_a_dropped_connection_pauses_the_whole_queue_and_its_job_waits_first():
    runner = Dropping({"a.mkv"})
    q = jobs.Queue(runner)
    q.submit(["a.mkv", "b.mkv"])
    until(lambda: q.status().state == "paused")
    assert q.status() == jobs.QueueStatus("paused", "couldn't reach the server",
                                          DOWN.hint, "connection")
    assert [(j.state, j.progress) for j in q.jobs()] == [("queued", (7, 11)), ("queued", None)]
    assert runner.tries == ["a.mkv"]
    assert q.resume() is True and q.resume() is False
    until(lambda: all(j.state == "done" for j in q.jobs()))
    assert runner.tries == ["a.mkv", "a.mkv", "b.mkv"] and q.status().state == "running"
    q.close()


def test_any_other_error_fails_only_its_job_and_the_queue_runs_on():
    failed = InputResult(input="a.mkv", status="failed", reason="the server refused the key (401)",
                         hint="SPARK_API_KEY is wrong", kind="auth")

    def run(source, event, cancelled):
        return failed if source == "a.mkv" else InputResult(input=source, status="done")

    q = jobs.Queue(run)
    first, second = q.submit(["a.mkv", "b.mkv"])
    until(lambda: state(q, second) == "done")
    assert state(q, first) == "failed" and view(q, first).hint == "SPARK_API_KEY is wrong"
    assert q.status().state == "running"
    q.close()


def test_pause_stops_the_running_job_at_its_next_check_and_resume_runs_it_again(queue, runner):
    first, second = queue.submit(["a.mkv", "b.mkv"])
    until(lambda: state(queue, first) == "running")
    assert queue.pause() is True and queue.pause() is False
    until(lambda: state(queue, first) == "queued")
    assert queue.status() == jobs.QueueStatus("paused", kind="paused")
    assert runner.started == ["a.mkv"] and state(queue, second) == "queued"
    queue.resume()
    until(lambda: runner.started == ["a.mkv", "a.mkv"])
    runner.gate("a.mkv").set()
    runner.gate("b.mkv").set()
    until(lambda: all(j.state == "done" for j in queue.jobs()))


def test_a_paused_idle_queue_starts_nothing_until_resume(queue, runner):
    queue.pause()
    (job,) = queue.submit(["a.mkv"])
    time.sleep(0.05)
    assert state(queue, job) == "queued" and runner.started == []
    queue.resume()
    until(lambda: state(queue, job) == "running")


def test_cancel_beats_pause_for_the_running_job(queue, runner):
    (job,) = queue.submit(["a.mkv"])
    until(lambda: state(queue, job) == "running")
    queue.cancel(job)
    queue.pause()
    until(lambda: state(queue, job) == "cancelled")
    assert runner.started == ["a.mkv"]


def test_a_cancelled_job_that_lost_its_connection_is_not_queued_again():
    gate = threading.Event()

    def run(source, event, cancelled):
        gate.wait(5)
        raise Paused(DOWN)

    q = jobs.Queue(run)
    (job,) = q.submit(["a.mkv"])
    until(lambda: state(q, job) == "running")
    q.cancel(job)
    gate.set()
    until(lambda: state(q, job) == "cancelled")
    assert q.status().state == "running"
    q.close()


def test_listeners_hear_the_queue_pause_and_resume():
    heard = []
    q = jobs.Queue(Dropping({"a.mkv"}))
    q.on_change(lambda: heard.append(q.status().state))
    q.submit(["a.mkv"])
    until(lambda: "paused" in heard)
    q.resume()
    until(lambda: q.jobs()[0].state == "done")
    q.close()
    assert heard.index("paused") < len(heard) - 1 and heard[-1] == "running"


def test_closing_a_paused_queue_cancels_everything():
    q = jobs.Queue(Dropping({"a.mkv"}))
    q.submit(["a.mkv", "b.mkv"])
    until(lambda: q.status().state == "paused")
    q.close()
    assert [j.state for j in q.jobs()] == ["cancelled", "cancelled"]
    assert not q._worker.is_alive()


class Flaky(FakeEngine):
    """Short chunks; chunk 1 can't reach its server until `down` is cleared."""

    max_chunk_s = 5.0

    def __init__(self):
        super().__init__()
        self.down = True

    def transcribe(self, chunk, *, language, prompt):
        if chunk.index == 1 and self.down:
            self.calls.append(("transcribe", chunk.index, language, prompt))
            raise DOWN
        return super().transcribe(chunk, language=language, prompt=prompt)


@pytest.mark.media
def test_resume_restarts_from_the_failed_chunk_with_the_same_model(tmp_path):
    clip = make_clip(tmp_path, "Show - S01E01.mkv", seconds=14, speech=SPEECH)
    config = Config(endpoints={"spark": Endpoint(base_url="http://127.0.0.1:9/v1")},
                    models={"fake": ModelEntry(catalog="whisper-large-v3-turbo", endpoint="spark",
                                               model="fake", parser="whisper.cpp", local=True)})
    engine = Flaky()
    ctx = RunContext(config=config, tools=Tools.find(), keys=KeyRing(environ={}),
                     options=RunOptions(source_lang="ja", model="fake", targets=[],
                                        wait_on_connection_s=0),
                     sleep=lambda seconds: None)
    ctx.engines["fake"] = engine
    q = jobs.Queue(lambda source, events, cancelled: run_one(
        source, dataclasses.replace(ctx, events=events, cancelled=cancelled)))
    (job,) = q.submit([str(clip)])
    until(lambda: q.status().state == "paused", timeout=30)
    before = [c[1] for c in engine.calls]
    assert before == [0, 1] and view(q, job).state == "queued"
    engine.down = False
    q.resume()
    until(lambda: state(q, job) == "done", timeout=30)
    q.close()
    after = [c[1] for c in engine.calls][len(before):]
    assert after[0] == 1 and 0 not in after and len(after) >= 2
    assert set(ctx.engines) == {"fake"} and view(q, job).result.status == "done"


# Review Focus 3: the laptop sleeps, or the tunnel drops, mid-chunk; Pause as a chunk finishes


WORDS = {"language": "english", "language_probabilities": {"en": 0.99},
         "segments": [{"text": " We meet.", "start": 0.0, "end": 1.0,
                       "words": [{"word": " We", "start": 0.0, "end": 0.5, "probability": 0.9},
                                 {"word": " meet.", "start": 0.5, "end": 1.0,
                                  "probability": 0.9}]}]}


class Held(FakeEngine):
    """Short chunks; chunk 1 waits in flight until the test lets it finish."""

    max_chunk_s = 5.0

    def __init__(self):
        super().__init__()
        self.in_flight, self.finish = threading.Event(), threading.Event()

    def transcribe(self, chunk, *, language, prompt):
        if chunk.index == 1:
            self.in_flight.set()
            assert self.finish.wait(10)
        return super().transcribe(chunk, language=language, prompt=prompt)


@pytest.mark.media
def test_pause_pressed_as_a_chunk_finishes_runs_no_chunk_twice_and_loses_none(tmp_path):
    clip = make_clip(tmp_path, "Show - S01E01.mkv", seconds=14, speech=SPEECH)
    config = Config(endpoints={"spark": Endpoint(base_url="http://127.0.0.1:9/v1")},
                    models={"fake": ModelEntry(catalog="whisper-large-v3-turbo", endpoint="spark",
                                               model="fake", parser="whisper.cpp", local=True)})
    engine = Held()
    ctx = RunContext(config=config, tools=Tools.find(), keys=KeyRing(environ={}),
                     options=RunOptions(source_lang="ja", model="fake", targets=[]),
                     engines={"fake": engine})
    q = jobs.Queue(lambda source, events, cancelled: run_one(
        source, dataclasses.replace(ctx, events=events, cancelled=cancelled)))
    (job,) = q.submit([str(clip)])
    assert engine.in_flight.wait(30)
    assert q.pause() is True  # as chunk 1 is in flight: it finishes, and the job stops after it
    assert view(q, job).stopping is False  # stopping is Cancel's alone
    engine.finish.set()
    until(lambda: state(q, job) == "queued", timeout=30)
    assert q.status().kind == "paused" and view(q, job).stopping is False  # Cancel's alone
    stopped = [c[1] for c in engine.calls]
    assert stopped == [0, 1]
    q.resume()
    until(lambda: state(q, job) == "done", timeout=30)
    q.close()
    ran = [c[1] for c in engine.calls]
    assert ran == list(range(len(ran))) and len(ran) > 2  # each chunk once, in order


@pytest.mark.media
def test_a_tunnel_that_drops_mid_chunk_pauses_the_queue_and_resume_sends_that_chunk_again(
        tmp_path):
    clip = make_clip(tmp_path, "Show - S01E01.mkv", seconds=14, speech=SPEECH)
    up = threading.Event()

    def whisper(req):
        if not up.is_set():
            return None  # the connection drops with the chunk in flight: no answer at all
        return 200, WORDS, {}

    with FakeServer(responder=whisper) as spark:
        config = Config(endpoints={"spark": Endpoint(base_url=spark.url)},
                        models={"turbo": ModelEntry(catalog="whisper-large-v3-turbo",
                                                    endpoint="spark", model="turbo",
                                                    parser="whisper.cpp", local=True)})
        ctx = RunContext(config=config, tools=Tools.find(), keys=KeyRing(environ={}),
                         options=RunOptions(source_lang="en", model="turbo", targets=[],
                                            wait_on_connection_s=0),
                         sleep=lambda seconds: None)
        q = jobs.Queue(lambda source, events, cancelled: run_one(
            source, dataclasses.replace(ctx, events=events, cancelled=cancelled)))
        (job,) = q.submit([str(clip)])
        until(lambda: q.status().state == "paused", timeout=30)
        assert (q.status().kind, view(q, job).state) == ("connection", "queued")  # not failed
        up.set()  # the tunnel is back
        q.resume()
        until(lambda: state(q, job) == "done", timeout=30)
        q.close()
        uploads = [r.form()["file"][0] for r in spark.requests if r.path.endswith("/transcriptions")]
    assert uploads == ["chunk-0000.flac", "chunk-0000.flac"]  # the chunk in flight, sent again
    assert view(q, job).result.status == "done"
```

  In `tests/fakes.py`, replace

```python
                if server.responder is not None:
                    status, payload, headers = server.responder(req)
```

  with

```python
                if server.responder is not None:
                    answer = server.responder(req)
                    if answer is None:  # the connection drops mid-request: no answer at all
                        self.close_connection = True
                        return
                    status, payload, headers = answer
```

  and in `FakeServer`'s docstring, replace
  `"""Scripted responses `(status, json-or-bytes, headers)`, or a `responder(request)`."""` with

```python
    """Scripted responses `(status, json-or-bytes, headers)`, or a `responder(request)`, which
    may return None to drop the connection with no answer (a tunnel that dies mid-request)."""
```

- [ ] **Step 2: Run it; watch it fail.** `uv run pytest tests/test_jobs.py -q`. Expected:
  `AttributeError: 'Queue' object has no attribute 'status'` (five times),
  `E       AttributeError: 'Queue' object has no attribute 'pause'` (four times), two
  `E               AssertionError: timed out waiting` (a lost connection fails the job instead of
  pausing the queue: the dropped tunnel's test among them), and `11 failed, 14 passed`.
- [ ] **Step 3: Write the code.** Replace `src/vid2sub/jobs.py` with:

```python
"""The job queue: one worker thread runs submitted inputs one at a time (spec §17.1, S36, S41).

Jobs live in the engine's memory, owned by the engine rather than a browser tab, so closing a tab
cancels nothing and reopening shows the progress; when the engine exits the list is gone, and
finished results are already on disk (Dan, 2026-10-14). One worker runs one job at a time,
because the Spark's whisper serves one request at a time anyway. Cancel takes a queued job out of
the queue, or asks the running one to stop at its next check, between chunks or translation
batches (`pipeline.Cancelled`; the Phase 2 plan's Decision 7), and says it is `stopping` until
then, so every tab can tell. Listeners are called after every change of state, stage or
progress, and when the queue pauses or resumes, on the thread that made it (the worker, or the
caller of `submit`, `cancel`, `pause`, `resume` or `close`); one that raises is logged and the
queue carries on, and one can stop listening (a tab that closed). A job may bring its own runner
(Add's YouTube link that keeps its video, Review's Start with each file's own options: the Phase
3 plan, Tasks 2 and 3); others use the queue's.

The queue is running or paused (§17.1). A connection error (refused, reset, the tunnel down, the
laptop slept) that outlasts the runner's own wait (`pipeline.Paused`) pauses the whole queue with
its reason and fix, instead of failing every remaining episode in turn (§17.3, council); so does
the person's Pause, which stops the running job at its next check as Cancel would but never says
it is `stopping`, which is Cancel's alone. Either way the job goes back to the head of the queue,
keeping its runner, stage and progress, and Resume runs it
again: its runner shares one context's finished chunks (§8.9), so it restarts from the chunk that
failed, with the same model, never another one or the cloud (§17.4). Any other error fails only its
job, with the hint that names the fix (§17.3). The log names jobs by id and errors by kind, never
an input, a title or a path (§6.8).
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

from vid2sub.pipeline import Cancelled, Event, InputResult, Paused

log = logging.getLogger(__name__)

JobState = Literal["queued", "running", "done", "failed", "cancelled"]
QueueState = Literal["running", "paused"]
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
    stopping: bool = False  # Cancel asked the running job to stop: before its next chunk or batch


@dataclass(frozen=True)
class QueueStatus:
    state: QueueState = "running"
    reason: str | None = None  # why it paused, fit to show; None for the person's Pause
    hint: str | None = None  # the fix, for a connection error (§17.3)
    kind: str | None = None  # "paused" for the person's Pause, else the error's kind; safe to log


class Queue:
    def __init__(self, runner: Runner):
        self._runner = runner
        self._runners: dict[str, Runner] = {}  # a job's own runner, while it waits or runs
        self._lock = threading.Condition()
        self._jobs: dict[str, JobView] = {}  # in the order they were submitted
        self._waiting: deque[str] = deque()
        self._running: str | None = None
        self._stop = threading.Event()  # set: the running job should stop
        self._why: Literal["cancel", "pause"] | None = None  # why it was asked to stop
        self._status = QueueStatus()
        self._listeners: list[Callable[[], None]] = []
        self._closed = False
        self._worker = threading.Thread(target=self._work, name="vid2sub-jobs", daemon=True)
        self._worker.start()

    def submit(self, inputs: Sequence[str], *, runner: Runner | None = None) -> list[str]:
        """Queues each input, run by `runner` when given, else by the queue's own."""
        with self._lock:
            if self._closed:
                raise RuntimeError("the job queue is closed")
            ids = []
            for source in inputs:
                job_id = self._new_id()
                self._jobs[job_id] = JobView(job_id, source, "queued")
                if runner is not None:
                    self._runners[job_id] = runner
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
            if job.state == "running":  # it stops at its next check; every tab can say so
                self._why = "cancel"
                self._stop.set()
                self._set(job_id, stopping=True)
            else:
                self._waiting.remove(job_id)
                self._runners.pop(job_id, None)
                self._set(job_id, state="cancelled")
        self._changed()
        return True

    def pause(self) -> bool:
        """The person's Pause: no job starts until Resume, and the running one stops at its next
        check and goes back to the head of the queue. False if already paused, or closed."""
        with self._lock:
            if self._closed or self._status.state == "paused":
                return False
            self._status = QueueStatus("paused", kind="paused")
            if self._running is not None and self._why is None:
                self._why = "pause"
                self._stop.set()
            self._lock.notify()
        self._changed()
        return True

    def resume(self) -> bool:
        """Runs the queue again from the job at its head. False if it wasn't paused."""
        with self._lock:
            if self._closed or self._status.state != "paused":
                return False
            self._status = QueueStatus()
            self._lock.notify()
        self._changed()
        return True

    def status(self) -> QueueStatus:
        with self._lock:
            return self._status

    def jobs(self) -> list[JobView]:
        with self._lock:
            return list(self._jobs.values())

    def on_change(self, fn: Callable[[], None]) -> Callable[[], None]:
        """Calls `fn` after every change; returns what stops it (a tab that closed)."""
        with self._lock:
            self._listeners.append(fn)

        def stop() -> None:
            with self._lock:
                if fn in self._listeners:
                    self._listeners.remove(fn)

        return stop

    def close(self, timeout: float = 5.0) -> None:
        """Cancels every queued job and the running one, then waits up to `timeout` seconds
        for the worker to stop."""
        with self._lock:
            self._closed = True
            while self._waiting:
                job_id = self._waiting.popleft()
                self._runners.pop(job_id, None)
                self._set(job_id, state="cancelled")
            if self._running is not None:
                self._why = "cancel"
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

    def _ready(self) -> bool:
        """Called with the lock held: a job is waiting and the queue isn't paused."""
        return bool(self._waiting) and self._status.state == "running"

    def _work(self) -> None:
        while True:
            with self._lock:
                while not self._closed and not self._ready():
                    self._lock.wait()
                if self._closed:
                    return
                job_id = self._waiting.popleft()
                self._running = job_id
                self._stop.clear()
                self._why = None
                self._set(job_id, state="running")
                source = self._jobs[job_id].input
                runner = self._runners.get(job_id, self._runner)
            self._changed()
            final = self._run(job_id, source, runner)
            with self._lock:
                paused = final.pop("pause", None)
                if final.pop("again", False) and not self._closed:
                    self._set(job_id, state="queued", stopping=False)
                    self._waiting.appendleft(job_id)
                    if paused is not None:
                        self._status = paused
                else:
                    self._set(job_id, stopping=False, **(final or {"state": "cancelled"}))
                    self._runners.pop(job_id, None)
                self._running = None
            self._changed()

    def _run(self, job_id: str, source: str, runner: Runner) -> dict[str, Any]:
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
            result = runner(source, event, self._stop.is_set)
        except Cancelled:
            with self._lock:
                why = self._why
            if why == "pause":
                log.info("job %s paused", job_id)
                return {"again": True}
            log.info("job %s cancelled", job_id)
            return {"state": "cancelled"}
        except Paused as err:
            with self._lock:
                why = self._why
            if why == "cancel":
                log.info("job %s cancelled", job_id)
                return {"state": "cancelled"}
            log.info("job %s paused the queue: %s", job_id, err.error.kind)
            return {"again": True, "pause": QueueStatus("paused", str(err),
                                                        err.error.hint or None, err.error.kind)}
        except Exception as err:  # noqa: BLE001 - a bug fails one job, not the queue (§17.3)
            log.error("job %s failed: %s", job_id, type(err).__name__)
            return {"state": "failed", "hint": None}
        if result.status == "failed":
            log.info("job %s failed: %s", job_id, result.kind or "failed")
        state = "failed" if result.status == "failed" else "done"
        return {"state": state, "result": result, "hint": result.hint or None}
```

- [ ] **Step 4: Run the checks; they pass.** `uv run pytest tests/test_jobs.py -q` first
  (`25 passed`; run it ten times, `for i in 1 2 3 4 5 6 7 8 9 10; do uv run pytest
  tests/test_jobs.py -q | tail -1; done`, each `25 passed`: these tests use threads), then the
  guard checks, then `make check`. **Guard checks**, each reverted and restored, each with
  `uv run pytest tests/test_jobs.py -q`: in `_work`, replace `self._waiting.appendleft(job_id)`
  with `self._waiting.append(job_id)` (the paused job goes to the back: `FAILED
  …test_a_dropped_connection_pauses_the_whole_queue_and_its_job_waits_first` and `…pause_stops…`);
  in `_run`, replace `except Paused as err:` with `except ZeroDivisionError as err:` (a lost
  connection fails one job after another: `6 failed`, the dropped tunnel's test among them); in
  `_run`'s `Paused` branch, replace `if why == "cancel":` with `if False:` (`FAILED
  …test_a_cancelled_job_that_lost_its_connection_is_not_queued_again`); in `pause`, add
  `self._set(self._running, stopping=True)` below `self._stop.set()` (`FAILED
  …test_pause_pressed_as_a_chunk_finishes_runs_no_chunk_twice_and_loses_none`: stopping is
  Cancel's alone). `make check`. Expected: `1188 passed, 7 skipped, 40 deselected` twice,
  `Test Files  21 passed (21)` and `Tests  97 passed (97)`, `All checks passed!` and
  `no leaks found`.
- [ ] **Step 5: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(jobs): 🤖 a dropped connection pauses the whole queue, and Resume carries on from the chunk that failed

The queue is running or paused (spec §17.1, S41). A run that raises
pipeline.Paused (a connection error or a Spark refusal that outlasted
its wait_on_connection) pauses the whole queue with the error's reason,
hint and kind, instead of failing each remaining episode in turn
(§17.3); Queue.pause() is the person's Pause, which stops the running job
at its next check as Cancel would. Either way the job goes back to the
head of the queue with its runner, stage and progress, and no job starts
until Queue.resume(). The job's runner shares one RunContext's finished
chunks (§8.9), so a resumed job asks only from the chunk that failed,
of the same model (§17.4). Cancel beats Pause; a job cancelled while it
lost its connection stays cancelled. Queue.status() returns a frozen
QueueStatus; the listeners Queue.on_change registers (Phase 2 Task 19,
each stoppable) hear pause and resume. JobView.stopping stays Cancel's
alone: Pause never sets it, and a requeued job has it false. Other
errors fail only their job, with their hint, and the queue runs on.

Review Focus 3: a whisper.cpp fake on a real socket drops the connection
with chunk 0 in flight (no answer at all, as a tunnel that dies or a
laptop that sleeps does; tests/fakes.FakeServer's responder may now
return None for that): openai's APIConnectionError reaches the
pipeline as a connection error, so the queue pauses and the job waits
as queued rather than failing, and Resume sends that chunk again. Pause
pressed while chunk 1 is in flight lets it finish and stops the job
before chunk 2; Resume runs from chunk 2, each chunk once.

The new tests failed first with: AttributeError: 'Queue' object has no
attribute 'status' (and 'pause'), and two timed out waiting (a lost
connection failed the job instead of pausing the queue). Guard checks,
each reverted and restored: a paused job queued at the back, Paused
treated as any other error (six tests fail, the dropped tunnel's
included), a cancelled job that lost its connection queued again, and
Pause marking the job stopping, each make their tests fail. The queue
tests passed ten runs in a row.

Docs read: none beyond the code (pipeline._retrying's Paused after
wait_on_connection_s, run_one's chunk cache key; clients.map_error,
where openai's APIConnectionError, its wrap of httpx's
RemoteProtocolError, becomes a "connection" EngineError); Python's
http.server (a handler that returns without writing closes the
connection when close_connection is set).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md Task 5
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/jobs.py tests/test_jobs.py tests/fakes.py`, `git commit -F
  .git/COMMIT_MSG`, then
  `git log -1 --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 6: Write the failing test.** Replace `tests/test_awake.py` with (M1's two tests
  first, unchanged):

```python
import contextlib
import logging
import sys
import threading
import time

import pytest

from vid2sub import jobs
from vid2sub.awake import keep_awake
from vid2sub.pipeline import Cancelled, InputResult


def test_keeping_awake_starts_and_stops_cleanly():
    with keep_awake():
        pass


@pytest.mark.skipif(sys.platform not in ("darwin", "linux"), reason="needs a helper process")
def test_the_helper_process_has_exited_when_the_block_ends():
    with keep_awake() as helper:
        pass
    if sys.platform == "darwin":
        assert helper is not None
    if helper is not None:  # None on a Linux machine without systemd-inhibit
        assert helper.poll() is not None


# Phase 3, Task 5: the queue keeps the machine awake until it finishes (S42, spec §8.10)


def until(check, timeout=5.0):
    end = time.monotonic() + timeout
    while not check():
        if time.monotonic() > end:
            raise AssertionError("timed out waiting")
        time.sleep(0.005)


class Gated:
    """A runner that waits for the test to let each input finish."""

    def __init__(self):
        self.gates: dict[str, threading.Event] = {}

    def gate(self, source):
        return self.gates.setdefault(source, threading.Event())

    def __call__(self, source, event, cancelled):
        while not self.gate(source).wait(0.005):
            if cancelled():
                raise Cancelled()
        return InputResult(input=source, status="done")


class Awake:
    """Records when the queue keeps the machine awake, and on which thread."""

    def __init__(self):
        self.events: list[tuple[str, str]] = []

    @contextlib.contextmanager
    def __call__(self):
        self.events.append(("awake", threading.current_thread().name))
        try:
            yield
        finally:
            self.events.append(("asleep", threading.current_thread().name))

    def kinds(self):
        return [kind for kind, _ in self.events]


def test_the_queue_keeps_the_machine_awake_until_its_last_job_ends():
    runner, awake = Gated(), Awake()
    q = jobs.Queue(runner, awake=awake)
    assert awake.kinds() == []
    q.submit(["a.mkv", "b.mkv"])
    until(lambda: q.jobs()[0].state == "running")
    runner.gate("a.mkv").set()
    until(lambda: q.jobs()[1].state == "running")
    assert awake.kinds() == ["awake"]  # held from the first job through the next
    runner.gate("b.mkv").set()
    until(lambda: awake.kinds() == ["awake", "asleep"])
    q.submit(["c.mkv"])
    until(lambda: awake.kinds() == ["awake", "asleep", "awake"])
    q.close()
    assert awake.kinds() == ["awake", "asleep", "awake", "asleep"]
    assert {thread for _, thread in awake.events} == {"vid2sub-jobs"}


def test_a_paused_queue_lets_the_machine_sleep_until_resume():
    runner, awake = Gated(), Awake()
    q = jobs.Queue(runner, awake=awake)
    q.submit(["a.mkv"])
    until(lambda: q.jobs()[0].state == "running")
    q.pause()
    until(lambda: awake.kinds() == ["awake", "asleep"])
    q.resume()
    until(lambda: awake.kinds() == ["awake", "asleep", "awake"])
    runner.gate("a.mkv").set()
    until(lambda: q.jobs()[0].state == "done")
    until(lambda: awake.kinds()[-1] == "asleep")
    q.close()


def test_a_helper_that_will_not_start_never_stops_the_queue(caplog):
    def broken():
        raise OSError("/usr/bin/caffeinate: not permitted")

    caplog.set_level(logging.ERROR, logger="vid2sub.jobs")
    runner = Gated()
    q = jobs.Queue(runner, awake=broken)
    q.submit(["a.mkv"])
    runner.gate("a.mkv").set()
    until(lambda: q.jobs()[0].state == "done")
    q.close()
    assert "OSError" in caplog.text and "caffeinate" not in caplog.text


@pytest.mark.skipif(sys.platform not in ("darwin", "linux"), reason="needs a helper process")
def test_the_real_helper_runs_while_a_job_runs_and_stops_when_the_queue_is_idle():
    helpers = []

    @contextlib.contextmanager
    def recorded():
        with keep_awake() as helper:
            helpers.append(helper)
            yield helper

    runner = Gated()
    q = jobs.Queue(runner, awake=recorded)
    q.submit(["a.mkv"])
    until(lambda: q.jobs()[0].state == "running")
    (helper,) = helpers
    if helper is None:  # a Linux machine without systemd-inhibit
        pytest.skip("no helper process here")
    assert helper.poll() is None
    runner.gate("a.mkv").set()
    until(lambda: helper.poll() is not None)
    q.close()
```

- [ ] **Step 7: Run it; watch it fail.** `uv run pytest tests/test_awake.py -q`. Expected:
  `E       TypeError: Queue.__init__() got an unexpected keyword argument 'awake'` four times,
  and `4 failed, 2 passed`.
- [ ] **Step 8: Write the code.** Replace `src/vid2sub/jobs.py` with:

```python
"""The job queue: one worker thread runs submitted inputs one at a time (spec §17.1, S36, S41,
S42).

Jobs live in the engine's memory, owned by the engine rather than a browser tab, so closing a tab
cancels nothing and reopening shows the progress; when the engine exits the list is gone, and
finished results are already on disk (Dan, 2026-10-14). One worker runs one job at a time,
because the Spark's whisper serves one request at a time anyway. Cancel takes a queued job out of
the queue, or asks the running one to stop at its next check, between chunks or translation
batches (`pipeline.Cancelled`; the Phase 2 plan's Decision 7), and says it is `stopping` until
then, so every tab can tell. Listeners are called after every change of state, stage or
progress, and when the queue pauses or resumes, on the thread that made it (the worker, or the
caller of `submit`, `cancel`, `pause`, `resume` or `close`); one that raises is logged and the
queue carries on, and one can stop listening (a tab that closed). A job may bring its own runner
(Add's YouTube link that keeps its video, Review's Start with each file's own options: the Phase
3 plan, Tasks 2 and 3); others use the queue's.

The queue is running or paused (§17.1). A connection error (refused, reset, the tunnel down, the
laptop slept) that outlasts the runner's own wait (`pipeline.Paused`) pauses the whole queue with
its reason and fix, instead of failing every remaining episode in turn (§17.3, council); so does
the person's Pause, which stops the running job at its next check as Cancel would but never says
it is `stopping`, which is Cancel's alone. Either way the job goes back to the head of the queue,
keeping its runner, stage and progress, and Resume runs it
again: its runner shares one context's finished chunks (§8.9), so it restarts from the chunk that
failed, with the same model, never another one or the cloud (§17.4). Any other error fails only its
job, with the hint that names the fix (§17.3). While the queue has work and isn't paused, the
machine is kept awake (§8.10, `awake.keep_awake`, entered and left on the worker thread, as
Windows' SetThreadExecutionState requires); a helper that won't start is logged and never stops
the queue. The log names jobs by id and errors by kind, never an input, a title or a path (§6.8).
"""

from __future__ import annotations

import contextlib
import dataclasses
import logging
import secrets
import threading
from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from vid2sub.awake import keep_awake
from vid2sub.pipeline import Cancelled, Event, InputResult, Paused

log = logging.getLogger(__name__)

JobState = Literal["queued", "running", "done", "failed", "cancelled"]
QueueState = Literal["running", "paused"]
Runner = Callable[[str, Event, Callable[[], bool]], InputResult]
Awake = Callable[[], contextlib.AbstractContextManager]
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
    stopping: bool = False  # Cancel asked the running job to stop: before its next chunk or batch


@dataclass(frozen=True)
class QueueStatus:
    state: QueueState = "running"
    reason: str | None = None  # why it paused, fit to show; None for the person's Pause
    hint: str | None = None  # the fix, for a connection error (§17.3)
    kind: str | None = None  # "paused" for the person's Pause, else the error's kind; safe to log


class Queue:
    def __init__(self, runner: Runner, *, awake: Awake = keep_awake):
        self._runner = runner
        self._runners: dict[str, Runner] = {}  # a job's own runner, while it waits or runs
        self._awake = awake
        self._held: contextlib.AbstractContextManager | None = None  # the worker's only
        self._lock = threading.Condition()
        self._jobs: dict[str, JobView] = {}  # in the order they were submitted
        self._waiting: deque[str] = deque()
        self._running: str | None = None
        self._stop = threading.Event()  # set: the running job should stop
        self._why: Literal["cancel", "pause"] | None = None  # why it was asked to stop
        self._status = QueueStatus()
        self._listeners: list[Callable[[], None]] = []
        self._closed = False
        self._worker = threading.Thread(target=self._work, name="vid2sub-jobs", daemon=True)
        self._worker.start()

    def submit(self, inputs: Sequence[str], *, runner: Runner | None = None) -> list[str]:
        """Queues each input, run by `runner` when given, else by the queue's own."""
        with self._lock:
            if self._closed:
                raise RuntimeError("the job queue is closed")
            ids = []
            for source in inputs:
                job_id = self._new_id()
                self._jobs[job_id] = JobView(job_id, source, "queued")
                if runner is not None:
                    self._runners[job_id] = runner
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
            if job.state == "running":  # it stops at its next check; every tab can say so
                self._why = "cancel"
                self._stop.set()
                self._set(job_id, stopping=True)
            else:
                self._waiting.remove(job_id)
                self._runners.pop(job_id, None)
                self._set(job_id, state="cancelled")
        self._changed()
        return True

    def pause(self) -> bool:
        """The person's Pause: no job starts until Resume, and the running one stops at its next
        check and goes back to the head of the queue. False if already paused, or closed."""
        with self._lock:
            if self._closed or self._status.state == "paused":
                return False
            self._status = QueueStatus("paused", kind="paused")
            if self._running is not None and self._why is None:
                self._why = "pause"
                self._stop.set()
            self._lock.notify()
        self._changed()
        return True

    def resume(self) -> bool:
        """Runs the queue again from the job at its head. False if it wasn't paused."""
        with self._lock:
            if self._closed or self._status.state != "paused":
                return False
            self._status = QueueStatus()
            self._lock.notify()
        self._changed()
        return True

    def status(self) -> QueueStatus:
        with self._lock:
            return self._status

    def jobs(self) -> list[JobView]:
        with self._lock:
            return list(self._jobs.values())

    def on_change(self, fn: Callable[[], None]) -> Callable[[], None]:
        """Calls `fn` after every change; returns what stops it (a tab that closed)."""
        with self._lock:
            self._listeners.append(fn)

        def stop() -> None:
            with self._lock:
                if fn in self._listeners:
                    self._listeners.remove(fn)

        return stop

    def close(self, timeout: float = 5.0) -> None:
        """Cancels every queued job and the running one, then waits up to `timeout` seconds
        for the worker to stop."""
        with self._lock:
            self._closed = True
            while self._waiting:
                job_id = self._waiting.popleft()
                self._runners.pop(job_id, None)
                self._set(job_id, state="cancelled")
            if self._running is not None:
                self._why = "cancel"
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

    def _ready(self) -> bool:
        """Called with the lock held: a job is waiting and the queue isn't paused."""
        return bool(self._waiting) and self._status.state == "running"

    def _hold_awake(self) -> None:
        """Keeps the machine awake from here until the queue is idle or paused (§8.10)."""
        if self._held is not None:
            return
        try:
            held = self._awake()
            held.__enter__()
        except Exception as err:  # noqa: BLE001 - sleeping is better than not working at all
            log.error("couldn't keep the machine awake: %s", type(err).__name__)
            held = contextlib.nullcontext()
        self._held = held

    def _let_sleep(self) -> None:
        if self._held is None:
            return
        held, self._held = self._held, None
        try:
            held.__exit__(None, None, None)
        except Exception as err:  # noqa: BLE001
            log.error("couldn't stop keeping the machine awake: %s", type(err).__name__)

    def _work(self) -> None:
        try:
            while True:
                with self._lock:
                    ready, closed = self._ready(), self._closed
                if closed:
                    return
                if not ready:
                    self._let_sleep()  # outside the lock: stopping the helper can take seconds
                    with self._lock:
                        while not self._closed and not self._ready():
                            self._lock.wait()
                    continue
                self._hold_awake()
                with self._lock:
                    if self._closed or not self._ready():
                        continue
                    job_id = self._waiting.popleft()
                    self._running = job_id
                    self._stop.clear()
                    self._why = None
                    self._set(job_id, state="running")
                    source = self._jobs[job_id].input
                    runner = self._runners.get(job_id, self._runner)
                self._changed()
                final = self._run(job_id, source, runner)
                with self._lock:
                    paused = final.pop("pause", None)
                    if final.pop("again", False) and not self._closed:
                        self._set(job_id, state="queued", stopping=False)
                        self._waiting.appendleft(job_id)
                        if paused is not None:
                            self._status = paused
                    else:
                        self._set(job_id, stopping=False, **(final or {"state": "cancelled"}))
                        self._runners.pop(job_id, None)
                    self._running = None
                self._changed()
        finally:
            self._let_sleep()

    def _run(self, job_id: str, source: str, runner: Runner) -> dict[str, Any]:
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
            result = runner(source, event, self._stop.is_set)
        except Cancelled:
            with self._lock:
                why = self._why
            if why == "pause":
                log.info("job %s paused", job_id)
                return {"again": True}
            log.info("job %s cancelled", job_id)
            return {"state": "cancelled"}
        except Paused as err:
            with self._lock:
                why = self._why
            if why == "cancel":
                log.info("job %s cancelled", job_id)
                return {"state": "cancelled"}
            log.info("job %s paused the queue: %s", job_id, err.error.kind)
            return {"again": True, "pause": QueueStatus("paused", str(err),
                                                        err.error.hint or None, err.error.kind)}
        except Exception as err:  # noqa: BLE001 - a bug fails one job, not the queue (§17.3)
            log.error("job %s failed: %s", job_id, type(err).__name__)
            return {"state": "failed", "hint": None}
        if result.status == "failed":
            log.info("job %s failed: %s", job_id, result.kind or "failed")
        state = "failed" if result.status == "failed" else "done"
        return {"state": state, "result": result, "hint": result.hint or None}
```

- [ ] **Step 9: Run the checks; they pass.** `uv run pytest tests/test_awake.py
  tests/test_jobs.py -q` first (`31 passed`; ten runs, each `31 passed`), then the guard
  checks, then `make check`. **Guard checks**, each reverted and restored, each with
  `uv run pytest tests/test_awake.py -q`: in `_work`, replace `self._let_sleep()  # outside the
  lock` with `pass  # outside the lock` (the machine is never let sleep while idle: `3 failed`);
  delete the line `self._hold_awake()` (`4 failed`). The real-helper test sees `caffeinate`
  running while a job runs and gone once the queue is idle (macOS; `systemd-inhibit` on Linux
  where it exists). `make check`. Expected: `1192 passed, 7 skipped, 40 deselected` twice,
  `Test Files  21 passed (21)` and `Tests  97 passed (97)`, `All checks passed!` and
  `no leaks found`.
- [ ] **Step 10: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(jobs): 🤖 the queue keeps the machine awake while it has work, and lets it sleep when idle or paused

S42, spec §8.10: Queue(runner, awake=keep_awake) enters awake.keep_awake
when it starts a job after being idle, holds it from job to job, and
leaves it once nothing is waiting or the queue is paused (and on close),
all on the worker thread, since Windows' SetThreadExecutionState holds
only for the thread that set it; caffeinate (macOS) and systemd-inhibit
(Linux) are the helpers M1's `vid2sub run` already uses. A helper that
won't start is logged by kind and the queue runs on regardless. The
helper is stopped outside the queue's lock, since stopping it can take
seconds.

The new tests failed first with: TypeError: Queue.__init__() got an
unexpected keyword argument 'awake'. Guard checks, each reverted and
restored: without letting the machine sleep when idle, three tests fail;
without holding it awake, four fail. The real-helper test sees
caffeinate running while a job runs and gone once the queue is idle. The
queue and awake tests passed ten runs in a row.

Docs read: none beyond the code (awake.keep_awake; Microsoft's
SetThreadExecutionState sets the calling thread's execution state).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md Task 5
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/jobs.py tests/test_awake.py`, `git commit -F .git/COMMIT_MSG`, then
  `git log -1 --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 11: Review, look forward, close.** The Tier 2 review from `$(cat .git/TASK_BASE)`
  (`AGENTS.md`, *Reviews*). Worth the reviewers' time: the worker loop's races (a Pause or a
  Cancel arriving as the job finishes, a `Paused` while closing), that the keep-awake context is
  entered and left only on the worker thread, and that a resumed job uses the runner it was
  submitted with, so never another model or the cloud (§17.4). The forward review over Tasks 6
  and 12: Task 6's Pause and Resume buttons call `pause()` and `resume()`, the paused banner
  reads `status()`, and its tests drive the queue through a runner that raises `Paused`; Phase 2
  Task 19's job context keeps `RunOptions.wait_on_connection_s` at M1's 10 minutes, so the
  banner would appear only after that wait (Task 6 sets the web app's to 30 seconds); Task
  12's exit test drops the tunnel mid-season. The docs this task made untrue: none expected (grep
  `docs/` for "Resume" and "paused"). Then the close, its own commit, holding this plan with this
  task's boxes ticked and **Now** set to `Task 6: The Jobs page grows up, open.`, and the spec's
  rows S41 (with "Phase and task" `Phase 3, Tasks 5–6`) and S42 (`Phase 3, Task 5`) set to `built`.
  The message, in `.git/CLOSE_MSG`:

```text
docs(plan): 🤖 close Task 5: The queue pauses and resumes

Drift: none
Rulings: none
Phase-end: none
Forward: none
Tier: 2
Rounds: none
Findings: none

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md Task 5
Co-Authored-By: <the model's own line>
```

  `git add docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md
  docs/superpowers/specs/2026-10-14-vid2sub-design.md`, `git commit -F .git/CLOSE_MSG`.

***

### Task 6: The Jobs page grows up

**Tier:** 2 · **Scenarios:** S41

**Files:**
- Modify: `src/vid2sub/web/runtime.py` (`APP_WAIT_S`), `src/vid2sub/web/views.py` (`jobs_view`'s
  `queue`), `src/vid2sub/web/server.py` (`queue_pause`, `queue_resume`), `frontend/src/types.ts`,
  `frontend/src/lib/jobs.ts`, `frontend/src/components/JobsPage.tsx`, `frontend/src/App.tsx`
- Test: `tests/test_web_jobs.py`, `frontend/src/lib/jobs.test.ts`,
  `frontend/src/components/JobsPage.test.ts`, `tests/e2e/test_jobs.py`

**Interfaces:**
- Consumes: Task 5's `Queue.pause() -> bool`, `resume() -> bool` and `status() -> QueueStatus`
  (`state`, `reason`, `hint`, `kind`), its listeners (Phase 2 Task 19's `on_change`, which
  already refresh every tab's `jobs` output), and a requeued job's kept stage and progress.
  `JobView` ignores `waiting` events, as before.
- Produces:
  - `web.runtime.APP_WAIT_S = 30.0`: the job context `runtime.build` makes has
    `RunOptions(wait_on_connection_s=APP_WAIT_S)`; a caller's own context (the demo's, a test's)
    is unchanged, and the CLI keeps M1's 600.
  - `web.views.jobs_view(jobs, status: QueueStatus | None = None)` adds `"queue": {"state":
    "running" | "paused", "reason": str | null, "hint": str | null, "kind": str | null}` (the
    running queue's when `status` is None).
  - The server (local only): the `jobs` output passes `rt.queue.status()`; inputs
    `queue_pause`: `{"n": int}` and `queue_resume`: `{"n": int}` call `pause()` and `resume()`
    (a repeat is a no-op: every tab shows the state). Pages ignores both.
  - The page: `JobsPage({jobs, queue: QueueState, onSubmit, onCancel, onOpen, onPause,
    onResume})`; `QueueState` in `types.ts`; `lib/jobs.ts`: `jobLine` says a requeued job is
    `waiting: stopped at <stage> <i>/<n>`, `pausedLine(queue)`, and `announcement(jobs, queue?)`
    announces the pause first. Test ids: `queue-pause` (while jobs wait or run),
    `queue-paused` (the banner, `data-kind`), `queue-reason`, `queue-hint` (only when `kind !=
    "paused"`), `queue-resume`.
  - Decided here (proposed): **the app's jobs retry a dropped connection for 30 seconds, then
    pause the queue** with its reason, fix and Resume, where the CLI keeps M1's ten minutes. Spec
    §17.3: "Connection errors pause the whole queue … with a Resume button, instead of failing
    every remaining episode in turn"; the app has a person and that button, the CLI's wait is for
    a terminal nobody watches, and the M3 exit test (Task 12, Step 5) expects the banner within a
    minute of the tunnel stopping. The cost: an overnight run's short drop pauses until someone
    presses Resume. The `waiting` events stay unshown: half a minute needs no countdown.

- [ ] **Step 0: Record the base:** `git rev-parse HEAD > .git/TASK_BASE`.
- [ ] **Step 1: Write the failing tests.** In `tests/test_web_jobs.py`, below
  `from vid2sub.config import Config`, add `from vid2sub.engines.base import EngineError`;
  replace `from vid2sub.jobs import JobView` with `from vid2sub.jobs import JobView, QueueStatus`,
  and `from vid2sub.pipeline import Cancelled, InputResult` with
  `from vid2sub.pipeline import Cancelled, InputResult, Paused`; in
  `test_the_jobs_view_names_each_job_by_its_file_with_its_stage_and_progress`, replace the
  expected view's last line,
  `         "written": [], "notes": [], "stopping": False, "can_open": False}]}`, with:

```python
         "written": [], "notes": [], "stopping": False, "can_open": False}],
        "queue": {"state": "running", "reason": None, "hint": None, "kind": None}}
```

  in `test_paths_typed_into_the_box_become_jobs_whose_progress_reaches_every_tab`, replace
  `        assert a.value("jobs") == {"jobs": []}` with
  `        assert a.value("jobs")["jobs"] == []`; in `test_the_pages_editor_has_no_jobs`, below
  `            t.set(job_cancel={"n": 2, "job": "j00000001"})`, add
  `            t.set(queue_pause={"n": 4})`, and replace its last line,
  `    assert rt.queue.jobs() == []`, with
  `    assert rt.queue.jobs() == [] and rt.queue.status().state == "running"`; then append, after
  two blank lines:

```python
# ---- Phase 3, Task 6: the queue pauses and resumes from the page (S41, spec §17.3) -------------

DOWN = EngineError("connection", "couldn't reach the server",
                   hint="is it running? For the Spark: is `make tunnel` running?")


def test_the_jobs_view_carries_the_queues_state_and_a_paused_job_where_it_stopped():
    view = views.jobs_view([JobView("j00000001", "/films/a.mkv", "queued", "transcribe", (7, 11))],
                           QueueStatus("paused", "couldn't reach the server", DOWN.hint,
                                       "connection"))
    assert view["queue"] == {"state": "paused", "reason": "couldn't reach the server",
                             "hint": DOWN.hint, "kind": "connection"}
    (job,) = view["jobs"]
    assert (job["state"], job["stage"], job["progress"], job["stopping"]) == (
        "queued", "transcribe", [7, 11], False)


def queue_of(t: Tab) -> dict | None:
    return t.value("jobs")["queue"] if t.has("jobs") and t.value("jobs") else None


def test_pause_and_resume_reach_the_queue_and_every_tab_hears_them(client, rt, gated):
    with tab(client, OUTPUTS) as a, tab(client, OUTPUTS) as b:
        a.until(lambda t: t.has("jobs"))
        a.set(jobs_submit={"n": 1, "paths": ["/films/a.mkv", "/films/b.mkv"]})
        b.until(lambda t: listed(t) and listed(t)[0]["state"] == "running")
        a.set(queue_pause={"n": 2})
        paused = b.until(lambda t: queue_of(t)["state"] == "paused"
                         and listed(t)[0]["state"] == "queued" and listed(t))
        assert queue_of(b) == {"state": "paused", "reason": None, "hint": None, "kind": "paused"}
        assert (paused[0]["progress"], paused[0]["stopping"]) == ([1, 2], False)  # where it stopped
        a.set(queue_resume={"n": 3})
        b.until(lambda t: queue_of(t)["state"] == "running" and listed(t)[0]["state"] == "running")
        gated.gate("/films/a.mkv").set()
        gated.gate("/films/b.mkv").set()
        b.until(lambda t: [j["state"] for j in listed(t)] == ["done", "done"])
    assert gated.gates.keys() == {"/films/a.mkv", "/films/b.mkv"}


def test_a_connection_that_stays_down_pauses_the_queue_with_its_reason_and_fix(tmp_path):
    tries: list[str] = []

    def dropping(source, events, cancelled):
        tries.append(source)
        if len(tries) == 1:
            events("chunk", {"index": 3, "of": 9})
            raise Paused(DOWN)
        return InputResult(input=source, status="done")

    made = runtime.build(Config(), tools=Tools(None, None, None), keys=KeyRing(environ={}),
                         cache=Cache(tmp_path / "cache", max_bytes=0), runner=dropping)
    runtime.configure(made)
    c = client_for(made)
    try:
        with tab(c, OUTPUTS) as t:
            t.until(lambda t: t.has("jobs"))
            t.set(jobs_submit={"n": 1, "paths": ["/films/a.mkv"]})
            t.until(lambda t: queue_of(t) and queue_of(t)["state"] == "paused")
            assert queue_of(t) == {"state": "paused", "reason": "couldn't reach the server",
                                   "hint": DOWN.hint, "kind": "connection"}
            assert [(j["state"], j["progress"]) for j in listed(t)] == [("queued", [3, 9])]
            t.set(queue_resume={"n": 2})
            t.until(lambda t: listed(t)[0]["state"] == "done")
    finally:
        c.__exit__(None, None, None)
        runtime.configure(None)
        made.queue.close()
    assert tries == ["/films/a.mkv", "/films/a.mkv"]


def test_the_apps_jobs_retry_a_dropped_connection_for_half_a_minute_then_pause(tmp_path):
    made = runtime.build(Config(), tools=Tools(None, None, None), keys=KeyRing(environ={}),
                         cache=Cache(tmp_path / "cache", max_bytes=0))
    try:
        assert made.job_context.options.wait_on_connection_s == runtime.APP_WAIT_S == 30.0
        assert pipeline.RunOptions().wait_on_connection_s == 600.0  # the CLI keeps M1's ten minutes
    finally:
        made.queue.close()
```

- [ ] **Step 2: Run them; watch them fail.** `uv run pytest tests/test_web_jobs.py -q`.
  Expected: `E       TypeError: jobs_view() takes 1 positional argument but 2 were given`,
  `E       KeyError: 'queue'` (twice), the view without its queue (`Right contains 1 more
  item:` `{'queue': {'hint': None, 'kind': None, 'reason': None, 'state': 'running'}}`),
  `E           AttributeError: module 'vid2sub.web.runtime' has no attribute 'APP_WAIT_S'`
  (the half-minute wait isn't there yet), and `5 failed, 8 passed`.
- [ ] **Step 3: Write the code.** In `src/vid2sub/web/runtime.py`, in the module docstring,
  below `` (§8.9). Nothing here presets `allow_cloud` (§7.2): a job never uses a cloud model in Phase 2. ``,
  add:

```python
A dropped connection is retried for `APP_WAIT_S`, then pauses the whole queue with its reason and
**Resume** (§17.3): the app has a person and a button, where the CLI's ten minutes are for a
terminal nobody watches (Phase 3 Task 6).
```

  below `PLAYBACK_TIMEOUT = 3600.0  # seconds: a two-hour episode's audio, read from a slow network share`,
  add
  `APP_WAIT_S = 30.0  # seconds a job retries a dropped connection before the queue pauses (§17.3)`;
  in `build`'s docstring, replace

```python
    context with M1's options (the route's models, the language detected, no cloud, ten minutes
    for a dropped connection), unless the caller gives its own; the queue runs `runner`, else
    `job_runner` on that context."""
```

  with

```python
    context with M1's options (the route's models, the language detected, no cloud) but
    `APP_WAIT_S` for a dropped connection, unless the caller gives its own; the queue runs
    `runner`, else `job_runner` on that context."""
```

  and replace
  `        job_context = RunContext(config=config, tools=tools, keys=keys, options=RunOptions())`
  with:

```python
        job_context = RunContext(config=config, tools=tools, keys=keys,
                                 options=RunOptions(wait_on_connection_s=APP_WAIT_S))
```

  In `src/vid2sub/web/views.py`, replace `    from vid2sub.jobs import JobView` (in the
  `TYPE_CHECKING` block) with `    from vid2sub.jobs import JobView, QueueStatus`; replace
  `def jobs_view(jobs: Sequence[JobView]) -> dict[str, Any]:` with
  `def jobs_view(jobs: Sequence[JobView], status: QueueStatus | None = None) -> dict[str, Any]:`;
  in its docstring, replace
  `    by its video's id, never a title (§6.8), and doesn't open by its link."""` with:

```python
    by its video's id, never a title (§6.8), and doesn't open by its link. `queue` is the queue's
    state (§17.1): running, or paused, by the person (`kind` "paused") or by a connection that
    stayed down, with its reason and fix (§17.3; Phase 3 Task 6); a job a pause sent back is
    `queued` with the stage and progress it stopped at."""
```

  and replace its last line, `    return {"jobs": out}`, with:

```python
    queue = {"state": "running", "reason": None, "hint": None, "kind": None}
    if status is not None:
        queue = {"state": status.state, "reason": status.reason, "hint": status.hint,
                 "kind": status.kind}
    return {"jobs": out, "queue": queue}
```

  In `src/vid2sub/web/server.py`, in the module docstring, replace

```python
asks the running one to stop before its next chunk or batch (Decision 7). The queue tells its
listeners on the worker thread, so each tab's hands the change to its own loop.
```

  with

```python
asks the running one to stop before its next chunk or batch (Decision 7). `queue_pause` and
`queue_resume` (Phase 3 Task 6) pause the whole queue, the running job stopping at its next
check, and run it again; the `jobs` output carries the queue's state, and a connection that
stayed down pauses it too, with the reason and the fix (§17.3). The queue tells its listeners on
the worker thread, so each tab's hands the change to its own loop.
```

  replace `        return views.jobs_view(rt.queue.jobs())` with
  `        return views.jobs_view(rt.queue.jobs(), rt.queue.status())`, and above
  `    @reactive.effect` / `    @reactive.event(input.job_cancel)`, add:

```python
    @reactive.effect
    @reactive.event(input.queue_pause)
    def _queue_pause() -> None:
        if local:
            rt.queue.pause()  # False when already paused: nothing to say, every tab shows it

    @reactive.effect
    @reactive.event(input.queue_resume)
    def _queue_resume() -> None:
        if local:
            rt.queue.resume()

```

- [ ] **Step 4: Run the checks; they pass.** `uv run pytest tests/test_web_jobs.py -q` first
  (`13 passed`; three times: the queue runs on a thread), then the guard checks, then
  `make check`. **Guard checks**, each reverted and restored, each with
  `uv run pytest tests/test_web_jobs.py -q`: in `build`, make the job context with
  `options=RunOptions()` (`FAILED
  …test_the_apps_jobs_retry_a_dropped_connection_for_half_a_minute_then_pause`); in
  `_queue_pause`, replace `rt.queue.pause()` with `pass` (`FAILED
  …test_pause_and_resume_reach_the_queue_and_every_tab_hears_them`). `make check`. Expected:
  `1196 passed, 7 skipped, 40 deselected` twice, `Test Files  21 passed (21)` and
  `Tests  97 passed (97)`, `All checks passed!` and `no leaks found`.
- [ ] **Step 5: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(web): 🤖 the Jobs page's server pauses and resumes the queue, says why it paused, and waits half a minute for a dropped connection

The server's half of the Jobs page growing up (spec §17.1, §17.3; S41).
The `jobs` output carries the queue's state (views.jobs_view(jobs,
status): running, or paused by the person, kind "paused", or by a
connection that stayed down, with its reason and fix); a job a pause
sent back is queued with the stage and progress it stopped at.
`queue_pause` and `queue_resume` call Queue.pause and resume; every tab
hears the change through the queue's listeners. Pages ignores both.

The app's job context retries a dropped connection for APP_WAIT_S, 30
seconds, then pauses the whole queue with Resume, where the CLI keeps
M1's ten minutes (--wait-on-connection): spec §17.3 asks a connection
error to pause the queue with a Resume button, and the app has a person
and that button, where the CLI's wait is for a terminal nobody watches;
the M3 exit test (Task 12, Step 5) expects the banner within a minute of
the tunnel stopping. Proposed as a Decision: an overnight run's short
drop now pauses until someone presses Resume.

The new tests failed first with: TypeError: jobs_view() takes 1
positional argument but 2 were given, KeyError: 'queue' (twice), and the
job context's wait still 600.0. Guard checks, each reverted and
restored: the job context with M1's options, and queue_pause doing
nothing, each make their tests fail.

Docs read: none beyond the code (Task 5's Queue.pause, resume and
status; pipeline._retrying, which raises Paused once its waits pass
wait_on_connection_s; Phase 2's jobs listeners in server.py).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md Task 6
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/web/runtime.py src/vid2sub/web/server.py src/vid2sub/web/views.py
  tests/test_web_jobs.py`, `git commit -F .git/COMMIT_MSG`, then
  `git log -1 --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 6: Write the failing tests.** Replace `frontend/src/lib/jobs.test.ts` with:

```ts
import { describe, expect, it } from "vitest";

import type { JobItem } from "@/types";

import { announcement, jobLine, pausedLine, typedPaths } from "./jobs";

const JOB: JobItem = { id: "j00000001", name: "a.mkv", path: "/films/a.mkv", state: "queued", stage: null, progress: null, status: null, reason: null, hint: null, written: [], notes: [], stopping: false, can_open: false };

describe("a job in words (spec §19.2: \"transcribing 7/11\")", () => {
  it("names the stage and the chunk or batch it is on", () => {
    expect(jobLine(JOB)).toBe("waiting");
    expect(jobLine({ ...JOB, state: "running" })).toBe("starting");
    expect(jobLine({ ...JOB, state: "running", stage: "decode" })).toBe("decoding the audio");
    expect(jobLine({ ...JOB, state: "running", stage: "transcribe", progress: [7, 11] })).toBe("transcribing 7/11");
    expect(jobLine({ ...JOB, state: "running", stage: "translate", progress: [1, 2] })).toBe("translating 1/2");
    expect(jobLine({ ...JOB, state: "running", stage: "something-new" })).toBe("something-new");
    expect(jobLine({ ...JOB, stage: "transcribe", progress: [7, 11] })).toBe("waiting: stopped at transcribing 7/11");
  });

  it("says what a finished job did, why one failed, and that one was cancelled", () => {
    expect(jobLine({ ...JOB, state: "done", status: "done", written: ["a.en.srt", "a.ja.srt"] })).toBe("done: wrote a.en.srt, a.ja.srt");
    expect(jobLine({ ...JOB, state: "done", status: "done" })).toBe("done: the subtitles were up to date");
    expect(jobLine({ ...JOB, state: "done", status: "uncertain", reason: "ja or zh?" })).toBe("the language is unclear: ja or zh?");
    expect(jobLine({ ...JOB, state: "failed", status: "failed", reason: "couldn't reach the server" })).toBe("failed: couldn't reach the server");
    expect(jobLine({ ...JOB, state: "failed" })).toBe("failed: see the log");
    expect(jobLine({ ...JOB, state: "cancelled" })).toBe("cancelled");
  });
});

describe("what the polite live region says (spec §19.3, S37)", () => {
  it("is the running job, else the one that finished last", () => {
    const running = { ...JOB, id: "j2", name: "b.mkv", state: "running" as const, stage: "transcribe", progress: [2, 3] as [number, number] };
    const done = { ...JOB, state: "done" as const, status: "done", written: ["a.en.srt"] };
    expect(announcement([done, running])).toBe("b.mkv: transcribing 2/3");
    expect(announcement([done, { ...JOB, id: "j3", name: "c.mkv" }])).toBe("a.mkv: done: wrote a.en.srt");
    expect(announcement([JOB])).toBe("");
  });

  it("is the pause, when the queue is paused (S41)", () => {
    const running = { ...JOB, state: "running" as const, stage: "transcribe", progress: [2, 3] as [number, number] };
    const down = { state: "paused" as const, reason: "couldn't reach the server", hint: "is `make tunnel` running?", kind: "connection" };
    expect(announcement([running], down)).toBe("The queue is paused. couldn't reach the server");
    expect(announcement([running], { state: "paused", reason: null, hint: null, kind: "paused" })).toBe("The queue is paused. nothing starts until you resume");
    expect(announcement([running], { state: "running", reason: null, hint: null, kind: null })).toBe("a.mkv: transcribing 2/3");
  });
});

describe("the paused banner (spec §17.3, S41)", () => {
  it("says why the queue paused itself, or that the person paused it", () => {
    expect(pausedLine({ state: "paused", reason: "couldn't reach the server", hint: "is `make tunnel` running?", kind: "connection" })).toBe("Paused: couldn't reach the server");
    expect(pausedLine({ state: "paused", reason: null, hint: null, kind: "paused" })).toBe("Paused: nothing starts until you resume");
    expect(pausedLine({ state: "running", reason: null, hint: null, kind: null })).toBe("");
  });
});

describe("the paths box", () => {
  it("takes one path a line, trimmed, blank lines left out", () => {
    expect(typedPaths("  /films/a.mkv \n\n/films/b c.mkv\r\n")).toEqual(["/films/a.mkv", "/films/b c.mkv"]);
    expect(typedPaths("   ")).toEqual([]);
  });
});
```

  Replace `frontend/src/components/JobsPage.test.ts` with:

```ts
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { JobItem, QueueState } from "@/types";

import { JobsPage } from "./JobsPage";

const JOB: JobItem = { id: "j00000001", name: "<img src=x>.mkv", path: "/films/<img src=x>.mkv", state: "running", stage: "transcribe", progress: [7, 11], status: null, reason: null, hint: null, written: [], notes: [], stopping: false, can_open: false };

const RUNNING: QueueState = { state: "running", reason: null, hint: null, kind: null };

function render(jobs: JobItem[], queue: QueueState = RUNNING): string {
  const noop = () => undefined;
  return renderToStaticMarkup(createElement(JobsPage, { jobs, queue, onSubmit: noop, onCancel: noop, onOpen: noop, onPause: noop, onResume: noop }));
}

describe("the Jobs page (spec §19.2, §19.3; S36)", () => {
  it("shows a running job's stage and chunk, with a bar and Cancel, and announces it politely", () => {
    const html = render([JOB]);
    expect(html).toContain("transcribing 7/11");
    expect(html).toMatch(/<progress[^>]*value="7"[^>]*max="11"/);
    expect(html).toContain('data-testid="job-cancel"');
    expect(html).toMatch(/role="status" aria-live="polite"[^>]*data-testid="jobs-announce">&lt;img src=x&gt;\.mkv: transcribing 7\/11</);
  });

  it("shows names, reasons and hints as text, never markup", () => {
    const html = render([{ ...JOB, state: "failed", reason: "<b>down</b>", hint: "is `make tunnel` running?" }]);
    expect(html).not.toContain("<img");
    expect(html).not.toContain("<b>");
    expect(html).toContain("failed: &lt;b&gt;down&lt;/b&gt;");
    expect(html).toContain("→ is `make tunnel` running?");
  });

  it("offers Open in editor only for a job that is done, and Cancel only while it can stop", () => {
    const done = render([{ ...JOB, state: "done", status: "done", progress: null, can_open: true }]);
    expect(done).toContain('data-testid="job-open"');
    expect(done).not.toContain('data-testid="job-cancel"');
    expect(render([{ ...JOB, state: "cancelled" }])).not.toContain('data-testid="job-cancel"');
    expect(render([{ ...JOB, state: "queued", stage: null, progress: null }])).toContain('data-testid="job-cancel"');
  });

  it("says a cancelled job is stopping, as the engine says, until it stops", () => {
    const html = render([{ ...JOB, stopping: true }]);
    expect(html).toMatch(/data-stopping="true"/);
    expect(html).toMatch(/<button[^>]*disabled=""[^>]*data-testid="job-cancel">Stopping…</);
  });

  it("offers Pause while jobs wait or run, and a paused queue's banner says why, with Resume (S41)", () => {
    expect(render([JOB])).toContain('data-testid="queue-pause"');
    expect(render([{ ...JOB, state: "done", status: "done" }])).not.toContain('data-testid="queue-pause"');
    const down = render([{ ...JOB, state: "queued" }], { state: "paused", reason: "couldn't <b>reach</b> the server", hint: "is `make tunnel` running?", kind: "connection" });
    expect(down).toContain("Paused: couldn&#x27;t &lt;b&gt;reach&lt;/b&gt; the server");
    expect(down).toContain("→ is `make tunnel` running?");
    expect(down).toContain('data-testid="queue-resume"');
    expect(down).not.toContain('data-testid="queue-pause"');
    expect(down).toContain("waiting: stopped at transcribing 7/11");
    const mine = render([JOB], { state: "paused", reason: null, hint: null, kind: "paused" });
    expect(mine).toContain("Paused: nothing starts until you resume");
    expect(mine).not.toContain('data-testid="queue-hint"');
    expect(mine).toMatch(/data-testid="jobs-announce">The queue is paused\. nothing starts until you resume</);
  });

  it("says there are no jobs yet", () => {
    expect(render([])).toContain("No jobs yet.");
  });
});
```

  In `tests/e2e/test_jobs.py`, replace the module docstring with:

```python
"""The Jobs page in Chromium (spec §17, §19.2, §19.3; S36, S37, S41; the plan's Decision 7): paths
typed into a box become jobs; per-stage and per-chunk progress ("transcribing 1/2") is shown and
announced politely; Cancel takes a queued job out, and stops the running one between chunks,
after the chunk the server is transcribing; Pause does the same for the whole queue, which waits,
saying so, until Resume carries on from the next chunk (Phase 3 Task 6); a finished job opens in
the editor. Against `vid2sub serve --demo` (its canned engine, on its own clip only) and against
a vid2sub.toml whose transcription endpoint is a fake whisper.cpp server that holds a chunk until
the test lets it go. Run with `make e2e`."""
```

  and append, after two blank lines:

```python
def test_pause_stops_after_the_chunk_in_flight_and_resume_carries_on_from_the_next(
        launch, open_page, tmp_path):
    held, go = threading.Event(), threading.Event()

    def whisper(req):
        if req.path.endswith("/models"):
            return 200, {"object": "list", "data": [{"id": "qwen", "object": "model"}]}, {}
        if req.form()["file"][0] == "chunk-0000.flac":
            held.set()
            assert go.wait(60)
        return 200, WORDS, {}

    clip = long_clip(tmp_path / "videos")
    with FakeServer(responder=whisper) as spark:
        server = launch(tmp_path / "server", toml=TOML.format(url=spark.url))
        watched = open_page(server)
        page = watched.page
        open_jobs(page)
        start(page, clip)
        job = page.get_by_test_id("job")
        expect(job.get_by_test_id("job-line")).to_have_text("transcribing 1/2", timeout=60_000)
        assert held.wait(30)
        page.get_by_test_id("queue-pause").click()
        banner = page.get_by_test_id("queue-paused")
        expect(banner).to_have_attribute("data-kind", "paused")
        expect(page.get_by_test_id("queue-reason")).to_have_text(
            "Paused: nothing starts until you resume")
        expect(page.get_by_test_id("jobs-announce")).to_have_text(
            "The queue is paused. nothing starts until you resume")
        expect(job).to_have_attribute("data-state", "running")  # chunk 1's answer is awaited
        go.set()
        expect(job).to_have_attribute("data-state", "queued", timeout=30_000)
        expect(job.get_by_test_id("job-line")).to_have_text(  # the chunk it carries on from
            "waiting: stopped at transcribing 2/2")
        page.get_by_test_id("queue-resume").click()
        expect(banner).to_have_count(0)
        expect(job).to_have_attribute("data-state", "done", timeout=60_000)
        uploads = [r.form()["file"][0] for r in spark.requests if r.path.endswith("/transcriptions")]
    chunks = [u for u in uploads if not u.startswith("chunk-9")]  # 9000-9002: detection's
    assert chunks == ["chunk-0000.flac", "chunk-0001.flac"]  # none twice, none lost
    assert watched.errors == [] and watched.violations() == []
```

- [ ] **Step 7: Run them; watch them fail.** `make test-js`. Expected: its typecheck stops at
  `src/components/JobsPage.test.ts(5,24): error TS2305: Module '"@/types"' has no exported
  member 'QueueState'.` and `src/lib/jobs.test.ts(5,33): error TS2305: Module '"./jobs"' has no
  exported member 'pausedLine'.` Then `make build` and `uv run pytest -m e2e
  tests/e2e/test_jobs.py -q -k pause`. Expected:
  `E           playwright._impl._errors.TimeoutError: Locator.click: Timeout 30000ms exceeded.`,
  `waiting for get_by_test_id("queue-pause")`, and `1 failed, 2 deselected`.
- [ ] **Step 8: Write the code.** In `frontend/src/types.ts`, replace

```ts
/** The `jobs` output, or null where there are no jobs (the Pages editor). */
export type JobsView = { jobs: JobItem[] };
```

  with

```ts
/** The queue's state (views.jobs_view; spec §17.1, §17.3): paused by the person (`kind` "paused")
 * or by a connection that stayed down, with its reason and fix. */
export type QueueState = { state: "running" | "paused"; reason: string | null; hint: string | null; kind: string | null };

/** The `jobs` output, or null where there are no jobs (the Pages editor). */
export type JobsView = { jobs: JobItem[]; queue: QueueState };
```

  Replace `frontend/src/lib/jobs.ts` with:

```ts
// The Jobs page's words (spec §17.2, §19.2, §19.3; S36, S41): each job's stage, with the chunk or
// translation batch it is on ("transcribing 7/11"), where a job a pause sent back stopped, what a
// finished one did, why one failed (its hint is shown beside it), the paused banner, and the one
// line the polite live region announces: the pause, else the running job, else the one that
// finished last. Paths are typed one a line.

import type { JobItem, QueueState } from "@/types";

const STAGES: Record<string, string> = {
  probe: "reading the video",
  hash: "checking the video",
  download: "downloading",
  detect: "detecting the language",
  decode: "decoding the audio",
  speech: "finding speech",
  transcribe: "transcribing",
  translate: "translating",
};

function stageLine(j: JobItem): string {
  const stage = STAGES[j.stage ?? ""] ?? j.stage ?? "";
  return j.progress ? `${stage} ${j.progress[0]}/${j.progress[1]}` : stage;
}

export function jobLine(j: JobItem): string {
  switch (j.state) {
    case "queued": return j.stage ? `waiting: stopped at ${stageLine(j)}` : "waiting";
    case "running": return j.stage ? stageLine(j) : "starting";
    case "done":
      if (j.status === "uncertain") return `the language is unclear: ${j.reason ?? ""}`.trim();
      if (j.status === "skipped") return "skipped: its subtitles are already there";
      return j.written.length ? `done: wrote ${j.written.join(", ")}` : "done: the subtitles were up to date";
    case "failed": return `failed: ${j.reason ?? "see the log"}`;
    case "cancelled": return "cancelled";
  }
}

/** The paused banner's words: the person's Pause, or why the queue paused itself (§17.3). */
export function pausedLine(queue: QueueState): string {
  if (queue.state !== "paused") return "";
  return queue.kind === "paused" ? "Paused: nothing starts until you resume" : `Paused: ${queue.reason ?? "the server stopped answering"}`;
}

export function announcement(jobs: readonly JobItem[], queue?: QueueState): string {
  if (queue?.state === "paused") return `The queue is paused. ${pausedLine(queue).replace(/^Paused: /, "")}`.trim();
  const running = jobs.find((j) => j.state === "running");
  const shown = running ?? [...jobs].reverse().find((j) => j.state !== "queued");
  return shown ? `${shown.name}: ${jobLine(shown)}` : "";
}

export function typedPaths(text: string): string[] {
  return text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
}
```

  Replace `frontend/src/components/JobsPage.tsx` with:

```tsx
import { type FormEvent, useState } from "react";

import { announcement, jobLine, pausedLine, typedPaths } from "@/lib/jobs";
import type { JobItem, QueueState } from "@/types";

const button = "rounded-md border border-input bg-background px-2 py-1 text-sm focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ring disabled:opacity-50";

/** The minimal Jobs page (spec §19.2, S36): full paths typed into a box, one a line, become jobs
 * on the engine's queue, which runs one at a time (§17.1). Each job shows its stage and the chunk
 * or translation batch it is on ("transcribing 7/11"), with a bar for the chunks; the running job,
 * else the last to finish, is announced in a polite live region (§19.3, S37). Cancel takes a
 * queued job out, or stops the running one before its next chunk or batch (Decision 7), so it
 * says "Stopping…" until then, in every tab (the engine's `stopping`). A failed job shows its reason and the fix (§17.3); a finished one
 * opens in the editor. The jobs are the engine's, so every tab shows them and closing a tab
 * cancels nothing. Every name and reason is plain text (§6.3). Pause stops the running job at its
 * next chunk and starts nothing until Resume; a connection that stays down pauses the queue too,
 * and the banner says why and how to fix it, with Resume (§17.3, S41); a job a pause sent back
 * waits, saying where it stopped. The live region announces the pause. */
export function JobsPage({ jobs, queue, onSubmit, onCancel, onOpen, onPause, onResume }: {
  jobs: readonly JobItem[];
  queue: QueueState;
  onSubmit: (paths: string[]) => void;
  onCancel: (id: string) => void;
  onOpen: (path: string) => void;
  onPause: () => void;
  onResume: () => void;
}) {
  const [text, setText] = useState("");
  const [stopping, setStopping] = useState<ReadonlySet<string>>(new Set());
  const submit = (e: FormEvent) => {
    e.preventDefault();
    const paths = typedPaths(text);
    if (!paths.length) return;
    onSubmit(paths);
    setText("");
  };
  const cancel = (id: string) => {
    setStopping((s) => new Set(s).add(id));
    onCancel(id);
  };
  return (
    <div className="flex h-full min-h-0 flex-col gap-3 overflow-y-auto p-4" data-testid="jobs-page">
      <form className="flex flex-col gap-2" onSubmit={submit}>
        <label htmlFor="jobs-paths" className="text-sm font-bold">Videos to make subtitles for: one full path a line</label>
        <textarea id="jobs-paths" rows={3} className="rounded-md border border-input bg-background px-2 py-1 font-mono text-sm focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ring" value={text} onChange={(e) => setText(e.target.value)} placeholder="/full/path/to/Show - S01E01.mkv" spellCheck={false} data-testid="jobs-paths" />
        <div className="flex items-center gap-2 text-sm">
          <button type="submit" className="rounded-md bg-primary px-3 py-1 font-bold text-primary-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:opacity-50" disabled={!typedPaths(text).length} data-testid="jobs-start">Start</button>
          <span className="text-muted-foreground">They run one at a time, with the session's targets and formats (Settings). Closing this tab cancels nothing.</span>
        </div>
      </form>
      {queue.state === "paused" ? (
        <div className="flex flex-wrap items-center gap-2 rounded-md border-l-4 border-(--brand-orange) bg-card p-2 text-sm" data-testid="queue-paused" data-kind={queue.kind ?? undefined}>
          <span className="font-bold" data-testid="queue-reason">{pausedLine(queue)}</span>
          {queue.kind !== "paused" && queue.hint && <span data-testid="queue-hint">→ {queue.hint}</span>}
          <button type="button" className={`${button} ml-auto font-bold`} onClick={onResume} data-testid="queue-resume">Resume</button>
        </div>
      ) : (
        jobs.some((j) => j.state === "queued" || j.state === "running") && (
          <div className="flex justify-end">
            <button type="button" className={button} onClick={onPause} data-testid="queue-pause">Pause</button>
          </div>
        )
      )}
      <p role="status" aria-live="polite" className="sr-only" data-testid="jobs-announce">{announcement(jobs, queue)}</p>
      {jobs.length === 0 ? (
        <p className="text-muted-foreground">No jobs yet.</p>
      ) : (
        <ol aria-label="Jobs" className="flex flex-col gap-2" data-testid="jobs-list">
          {jobs.map((j) => {
            const asked = j.stopping || stopping.has(j.id); // the engine's word, or this tab's click
            return (
            <li key={j.id} className="flex flex-col gap-1 rounded-md border border-border bg-card p-2 text-sm" data-testid="job" data-state={j.state} data-stopping={j.stopping || undefined}>
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-bold break-all">{j.name}</span>
                <span className={j.state === "failed" ? "text-destructive" : "text-muted-foreground"} data-testid="job-line">{jobLine(j)}</span>
                <span className="ml-auto flex gap-2">
                  {(j.state === "queued" || j.state === "running") && (
                    <button type="button" className={button} onClick={() => cancel(j.id)} disabled={asked} data-testid="job-cancel">
                      {asked ? "Stopping…" : "Cancel"}
                    </button>
                  )}
                  {j.can_open && <button type="button" className={button} onClick={() => onOpen(j.path)} data-testid="job-open">Open in editor</button>}
                </span>
              </div>
              {j.state === "running" && j.progress && (
                <progress className="h-1.5 w-full accent-(--brand-orange)" value={j.progress[0]} max={j.progress[1]} aria-label={`${j.name}: ${jobLine(j)}`} />
              )}
              {j.hint && <span data-testid="job-hint">→ {j.hint}</span>}
              {j.notes.map((note, k) => <span key={k} className="text-muted-foreground">{note}</span>)}
            </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
```

  In `frontend/src/App.tsx`, in the `import type { … } from "@/types";` line, add
  `QueueState, ` before `ReviewOutput`; below
  `type Screen = keyof typeof SCREENS;`, add
  `const RUNNING: QueueState = { state: "running", reason: null, hint: null, kind: null };`;
  below the `setJobCancel` line, add:

```tsx
  const setQueuePause = useSetShinyInput<{ n: number } | null>("queue_pause", null, { priority: "event", debounceMs: 0 });
  const setQueueResume = useSetShinyInput<{ n: number } | null>("queue_resume", null, { priority: "event", debounceMs: 0 });
```

  and replace
  `          <JobsPage jobs={jobs?.jobs ?? []} onSubmit={onSubmitJobs} onCancel={onCancelJob} onOpen={onOpenJob} />`
  with:

```tsx
          <JobsPage jobs={jobs?.jobs ?? []} queue={jobs?.queue ?? RUNNING} onSubmit={onSubmitJobs} onCancel={onCancelJob} onOpen={onOpenJob}
            onPause={() => { const n = ++sent.current; pace(() => setQueuePause({ n })); }}
            onResume={() => { const n = ++sent.current; pace(() => setQueueResume({ n })); }} />
```

- [ ] **Step 9: Run the checks; they pass.** `make test-js` first (`Test Files  21 passed (21)`,
  `Tests  100 passed (100)`), then `make check` and `make e2e`. Expected: `make check`:
  `1196 passed, 7 skipped, 41 deselected` twice, `Test Files  21 passed (21)` and
  `Tests  100 passed (100)`, `All checks passed!` and `no leaks found`; `make e2e`:
  `36 passed, 1208 deselected`. (A paused job says the chunk it carries on from: the pipeline
  reports chunk 2 of 2 just before the check that stops it.)
- [ ] **Step 10: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(ui): 🤖 the Jobs page pauses and resumes the queue, and its banner says why the queue paused and how to fix it

The page's half (spec §17.3, §19.2, §19.3; S41). While jobs wait or run,
Pause stops the running job at its next chunk and starts nothing until
Resume. A paused queue shows a banner, its bar NYC orange: "Paused:
nothing starts until you resume" for the person's Pause, else the
reason the queue paused itself ("Paused: couldn't reach the server")
with its fix ("→ is `make tunnel` running?"), and Resume. A job a pause
sent back says where it carries on from ("waiting: stopped at
transcribing 2/2"). The polite live region announces the pause ("The
queue is paused. …") ahead of any job (§19.3, S37). Names, reasons and
hints are plain text; Pause and Resume are buttons, so the keyboard
reaches them.

The browser test: a two-chunk talk on a fake whisper.cpp server that
holds chunk 0; Pause while it's in flight; the banner and the
announcement say paused, the job finishes its chunk and waits, Resume
carries on: the server saw chunk 0 and chunk 1 once each.

The new tests failed first with: error TS2305: Module '"./jobs"' has no
exported member 'pausedLine' (make test-js's typecheck), and in
Chromium, Locator.click: Timeout 30000ms exceeded, waiting for
get_by_test_id("queue-pause").

Docs read: MDN on ARIA live regions (role="status", polite: the pause
waits for the reader to finish); React 19.2.8's types; Playwright
1.64.1's Python API (to_have_count(0) for the banner gone).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md Task 6
Co-Authored-By: <the model's own line>
```

  `git add frontend/src/App.tsx frontend/src/components/JobsPage.test.ts
  frontend/src/components/JobsPage.tsx frontend/src/lib/jobs.test.ts frontend/src/lib/jobs.ts
  frontend/src/types.ts tests/e2e/test_jobs.py`, `git commit -F .git/COMMIT_MSG`, then
  `git log -1 --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 11: Review, look forward, close.** The Tier 2 review from `$(cat .git/TASK_BASE)`
  (`AGENTS.md`, *Reviews*). Worth the reviewers' time: that the banner shows a reason and hint
  only for a pause the queue made itself, as plain text; that every tab sees the same state; that
  the 30 seconds apply to the app's own job context only. The forward review over Tasks 11 and
  12: Task 11 documents Pause, Resume, the banner and the half-minute wait; Task 12's Step 5
  sees the banner about 30 seconds after the tunnel stops. The docs this task made untrue: none
  expected (grep `README.md` and `docs/` for "Resume" and "paused"). Then the close, its own
  commit, holding this plan with this task's boxes ticked and **Now** set to `Task 7: The preview
  copy, open.`, and the spec's S41 row's proof extended with `tests/test_web_jobs.py`;
  `tests/e2e/test_jobs.py`. The message, in `.git/CLOSE_MSG`:

```text
docs(plan): 🤖 close Task 6: The Jobs page grows up

Drift: none
Rulings: none
Phase-end: none
Forward: none
Tier: 2
Rounds: none
Findings: none

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md Task 6
Co-Authored-By: <the model's own line>
```

  `git add docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md
  docs/superpowers/specs/2026-10-14-vid2sub-design.md`, `git commit -F .git/CLOSE_MSG`.

***

### Task 7: The preview copy

**Tier:** 2 · **Scenarios:** S63

Spec §8.8 and S63: while the editor plays an episode's sound alone, **Make preview copy** makes an
H.264 480p MP4 with AAC stereo, through a hardware encoder that works here (VideoToolbox, NVENC,
Quick Sync), else `libx264 -preset veryfast`, into the cache (§8.9), and the player then plays it
with its picture through `/media/` (§6.3).

**Why it is built this way** (read 2026-10-24):
- **What Phase 2 left:** the playback audio (`media.preview.playback_audio`, cached under the
  video's `quick_sha256`) plays when the browser can't play the video (Phase 2 Decisions 2 and
  15); `Player.tsx` said the copy with the picture was this task's.
- **Each hardware encoder is tried for real** on three frames of a generated picture, written to
  ffmpeg's null muxer, before it is chosen: `ffmpeg -encoders` lists `h264_videotoolbox`,
  `h264_nvenc` or `h264_qsv` wherever ffmpeg was built with them, whether or not the machine has
  the hardware or its driver. VideoToolbox's `-allow_sw` defaults to false (`ffmpeg -h
  encoder=h264_videotoolbox`), so without the hardware it fails instead of encoding in software.
  An encoder that passes its trial and then fails on the episode gives way to libx264, and
  `preview-a<N>.json` beside the copy names the encoder that made it.
- **The picture:** `-map 0:V:0` (capital V: never cover art, ffmpeg's stream specifiers), scaled
  to 480 lines or fewer and never up (`scale=-2:'trunc(min(480,ih)/2)*2'`: an even height, the
  width following the shape), 8-bit 4:2:0 (`yuv420p`, or `nv12` for VideoToolbox and Quick
  Sync), so a 10-bit source still gives a copy every H.264 browser decodes. The hardware
  encoders take a 1500k bit rate; libx264 its default CRF 23 at spec §8.8's `-preset veryfast`.
  The audio, metadata and chapters are handled as the playback audio's are.
- **Progress and stopping:** ffmpeg's `-progress pipe:1` writes `out_time_us=` lines every half
  second. `media.tools.stream_tool` runs it as `run_tool` runs every tool (spec §6.7) and hands
  each line on as it comes; its readers are threads of its own, so neither pipe stalls ffmpeg,
  and it checks the caller's `cancelled` and its deadline five times a second even while ffmpeg
  is quiet (a sleeping network share), killing ffmpeg on either. Its stdin is a pipe closed at
  once, not `os.devnull`: Popen opens `os.devnull` for writing too, and the demo's audit hook
  (`web.demo.isolate`) refuses that, so the demo couldn't make a copy (found by this task's
  Playwright test). ffmpeg writes to a temporary name in the entry's folder, removed unless the
  whole copy is renamed into place: a tab closed mid-encode leaves nothing in the cache.
- **The encode never holds up the tab.** A long episode takes minutes, so the server runs it in
  a task of the tab's own, through `runtime.blocking`, outside the tab's serial queue: edits and
  Saves go on meanwhile. Only the switch to the copy waits its turn in the queue (`previewed`, a
  step no input reaches), and the copy's media token is issued then, only if the episode is still
  open. The task is held by the editor: asyncio keeps only a weak reference to a task.
- **The playback audio's token stays** once the copy plays, so a browser that fails on the copy
  after all plays the sound again. The button is offered only where the engine makes things
  (`capabilities.generate`, Phase 2 Decision 23: it runs ffmpeg), the video has a picture, and
  this browser plays H.264 and AAC in an MP4 (canPlayType, as Phase 2 Decision 15 asks it about
  the video).
- **The demo offers it too.** Its own clip (VP9 and Opus) plays, so only an episode made in its
  copy needs a preview copy, as the browser tests make one; the copy goes in the demo's own
  cache, inside its folder.
- **An episode whose copy is in the cache** gets it with the playback audio, so it plays with its
  picture the next time it is opened.

**Files:**
- Modify: `src/vid2sub/media/preview.py` (the preview copy beside the playback audio),
  `src/vid2sub/media/tools.py` (`stream_tool`, `Cancelled`), `src/vid2sub/web/episode.py`
  (`PreviewError`), `src/vid2sub/web/runtime.py` (`Media`'s preview fields, `Preview`,
  `make_preview`, `media_for`), `src/vid2sub/web/views.py` (`episode_view`'s preview fields),
  `src/vid2sub/web/server.py` (the `preview` input and output), `frontend/src/lib/playable.ts`,
  `frontend/src/types.ts`, `frontend/src/components/Player.tsx`,
  `frontend/src/components/Editor.tsx`, `frontend/src/App.tsx`, `README.md`,
  `docs/architecture.md`
- Create: `tests/test_preview.py`, `frontend/src/components/Player.test.ts`,
  `tests/e2e/test_preview.py`
- Test: `tests/test_tools.py`, `tests/test_views.py`, `tests/test_web_server.py`,
  `frontend/src/lib/playable.test.ts`
- Modify at the close: this plan; the spec (S63)
- Shared with Tasks 1–6: `episode.py`, `runtime.py`, `server.py`, `App.tsx` and `types.ts`
  (Tasks 2, 4 and 6 add their screens there); the anchors below are as those tasks leave them.

**Interfaces:**
- Consumes: Phase 2's `media.preview.playback_audio`, `cache.Cache` (`folder`, `evict`),
  `media.tools.run_tool`, `input_args`, `Tools`, `ToolFailed`, `ToolMissing`,
  `security.child_env`; `web.runtime.Runtime.media_for`, `Media`, `blocking`;
  `web.media.MediaTokens.issue` and `revoke_owner`; `server.Editor` (`submit`, `_drain`,
  `_named`, `_close`, `_publish`) and its `playback` input; `views.episode_view`;
  `Capabilities.generate`; `frontend/src/lib/playable.ts`'s `canPlay`; `Player.tsx`,
  `Editor.tsx`, `App.tsx`; `tests/helpers.make_clip`, `tests/episodes.make_episode`; the e2e
  `page`, `server` and `watch` fixtures.
- Produces:
  - `vid2sub.media.tools`: `class Cancelled(Exception)`; `STDERR_KEPT = 4000`;
    `stream_tool(args, *, cwd: Path, timeout: float, on_line: Callable[[str], None],
    cancelled: Callable[[], bool] = lambda: False) -> None` (each stdout line, stripped;
    `Cancelled` or `ToolFailed`, the child killed first; stdin a pipe closed at once)
  - `vid2sub.media.preview`: `HARDWARE = ("h264_videotoolbox", "h264_nvenc", "h264_qsv")`,
    `SOFTWARE = "libx264"`, `ENCODERS: dict[str, tuple[str, tuple[str, ...]]]` (name → picture
    format, options), `SCALE`, `TRIAL`, `TRIAL_TIMEOUT = 30.0`, `class NoEncoder(RuntimeError)`,
    `@dataclass(frozen=True) class PreviewCopy: path: Path; encoder: str`,
    `listed_encoders(listing: str) -> frozenset[str]`, `encoders_to_try(listed, works) ->
    tuple[str, ...]`, `works_here(tools, name, *, cwd) -> bool`, `pick_encoders(tools, *, cwd)
    -> tuple[str, ...]`, `cached_preview(cache, *, key, audio_index) -> PreviewCopy | None`,
    `preview_copy(video, *, key, audio_index, tools, cache, timeout, on_progress=None,
    cancelled=None, encoders=None) -> PreviewCopy` (`<cache>/<key>/preview-a<N>.mp4` and
    `preview-a<N>.json`, `{"encoder": name}`); `playback_audio` unchanged
  - `vid2sub.web.episode.PreviewError(Exception)` (pure; fit to show, naming no path)
  - `vid2sub.web.runtime`: `PREVIEW_TIMEOUT = 4 * 3600.0`, `NO_PREVIEW`; `Media` gains
    `preview_url: str | None = None` and `preview_encoder: str | None = None`;
    `@dataclass(frozen=True) class Preview: path: Path; encoder: str`;
    `Runtime.make_preview(ep, *, on_progress=None, cancelled=None) -> Preview | None` (None
    when cancelled; `PreviewError` otherwise); `media_for(ep, audio_only=...)` adds a cached
    copy's `preview_url` and `preview_encoder` to the playback audio
  - `views.episode_view(ep, *, video_url, audio_url, preview_url=None, preview_encoder=None,
    default_formats=("srt",))`: `video` gains `preview_url` and `preview_encoder`
  - The Shiny server: input `preview` (`{"episode", "n"}`); output `preview`
    (`{"episode", "done_ms", "of_ms"}` while a copy is made, else null); the notices
    `the preview copy is ready (<encoder>)` and `couldn't make a preview copy: <reason>`
  - Frontend: `types.ts`'s `EpisodeView["video"]` gains `preview_url: string | null` and
    `preview_encoder: string | null`; `PreviewProgress = { episode: string; done_ms: number;
    of_ms: number } | null`; `playable.ts`'s `canPlayPreview(ask)`, `previewPercent({done_ms,
    of_ms})` and `encoderLabel(name)`; `Player` takes `generate`, `preview` and
    `onMakePreview`; test ids `make-preview`, `preview-progress` and `preview-note`
  - For Phase 4: the Pages editor's view has `preview_url` and `preview_encoder` null, and
    `generate` is false there, so it never offers the button.

The counts below are the assembled Phase 3's, with Tasks 1–6 in before this task.

- [ ] **Step 0: Record the base:** `git rev-parse HEAD > .git/TASK_BASE`.

#### Round 7a: the copy, made and reused

- [ ] **Step 1: Write the failing tests,** `tests/test_preview.py`:

```python
"""The preview copy (spec §8.8, S63): an H.264 480p MP4 with AAC stereo, from a hardware encoder
when one works here, else libx264, made into the cache and reused (§8.9).

The choice is tested against fake `ffmpeg -encoders` listings; the copy itself is made for real,
with libx264 (every ffmpeg vid2sub supports has it), from short clips made with ffmpeg's lavfi.
"""

import json
import os
import subprocess

import numpy as np
import pytest
from helpers import make_clip

from vid2sub.cache import Cache
from vid2sub.media import preview
from vid2sub.media.tools import Cancelled, ToolFailed, Tools

KEY = "a" * 64

# `ffmpeg -hide_banner -encoders`, cut down: its legend, then one line per encoder.
LEGEND = """Encoders:
 V..... = Video
 A..... = Audio
 S..... = Subtitle
 .F.... = Frame-level multithreading
 ------
"""
LINUX = LEGEND + """\
 V....D libx264              libx264 H.264 / AVC / MPEG-4 AVC / MPEG-4 part 10 (codec h264)
 V....D h264_nvenc           NVIDIA NVENC H.264 encoder (codec h264)
 V..... h264_qsv             H.264 / AVC / MPEG-4 AVC / MPEG-4 part 10 (Intel Quick Sync Video acceleration) (codec h264)
 V....D h264_vaapi           H.264/AVC (VAAPI) (codec h264)
 A....D aac                  AAC (Advanced Audio Coding)
"""
MAC = LEGEND + """\
 V....D libx264              libx264 H.264 / AVC / MPEG-4 AVC / MPEG-4 part 10 (codec h264)
 V....D h264_videotoolbox    VideoToolbox H.264 Encoder (codec h264)
 A....D aac                  AAC (Advanced Audio Coding)
"""


def test_the_video_encoders_are_read_from_ffmpegs_listing():
    found = preview.listed_encoders(LINUX)
    assert {"libx264", "h264_nvenc", "h264_qsv", "h264_vaapi"} <= found
    assert "aac" not in found and "=" not in found


def test_a_hardware_encoder_that_works_here_comes_first_then_libx264():
    tried = []

    def works(name):
        tried.append(name)
        return True

    assert preview.encoders_to_try(preview.listed_encoders(LINUX), works) == ("h264_nvenc",
                                                                              "libx264")
    assert tried == ["h264_nvenc"]  # the first that works is enough; libx264 needs no trial
    assert preview.encoders_to_try(preview.listed_encoders(MAC), works) == (
        "h264_videotoolbox", "libx264")


def test_a_listed_hardware_encoder_that_fails_its_trial_is_passed_over():
    tried = []

    def only_qsv(name):
        tried.append(name)
        return name == "h264_qsv"

    listed = preview.listed_encoders(LINUX)
    assert preview.encoders_to_try(listed, only_qsv) == ("h264_qsv", "libx264")
    assert tried == ["h264_nvenc", "h264_qsv"]  # VAAPI isn't one spec §8.8 names
    assert preview.encoders_to_try(listed, lambda name: False) == ("libx264",)


def test_an_ffmpeg_with_no_h264_encoder_says_so():
    with pytest.raises(preview.NoEncoder, match="H.264"):
        preview.encoders_to_try(preview.listed_encoders(LEGEND), lambda name: True)
    # a hardware encoder alone will do
    listed = preview.listed_encoders(LEGEND + " V....D h264_nvenc  NVIDIA NVENC H.264 encoder\n")
    assert preview.encoders_to_try(listed, lambda name: True) == ("h264_nvenc",)


# The copy, made for real ---------------------------------------------------------------------


def ffprobe(tools: Tools, path) -> dict:
    return json.loads(subprocess.run(
        [tools.ffprobe, "-v", "error", "-show_format", "-show_streams", "-show_chapters",
         "-of", "json", str(path)], capture_output=True, check=True).stdout)


def loudest_hz(tools: Tools, path) -> float:
    pcm = subprocess.run([tools.ffmpeg, "-v", "error", "-i", str(path), "-map", "0:a:0", "-ac",
                          "1", "-ar", "16000", "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    samples = np.frombuffer(pcm, dtype="<i2").astype(np.float64)
    spectrum = np.abs(np.fft.rfft(samples))
    return float(np.fft.rfftfreq(len(samples), 1 / 16_000)[spectrum.argmax()])


def hd_clip(directory, name="Show - S01E01.mkv", seconds=2.0):
    """A 1280x720 clip with two AC-3 tracks (440 Hz, then 550 Hz), a title and a chapter."""
    tools = Tools.find()
    meta = directory / "chapters.ffmetadata"
    meta.write_text(f";FFMETADATA1\ntitle=Secret Show Title\n[CHAPTER]\nTIMEBASE=1/1000\n"
                    f"START=0\nEND={int(seconds * 1000)}\ntitle=Secret Chapter\n",
                    encoding="utf-8")
    out = directory / name
    subprocess.run([tools.ffmpeg, "-nostdin", "-v", "error", "-y",
                    "-f", "lavfi", "-i", f"testsrc=size=1280x720:rate=25:duration={seconds}",
                    "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
                    "-f", "lavfi", "-i", f"sine=frequency=550:duration={seconds}",
                    "-f", "ffmetadata", "-i", str(meta),
                    "-map", "0:v", "-map", "1:a", "-map", "2:a", "-map_metadata", "3",
                    "-map_chapters", "3", "-c:v", "mpeg4", "-c:a", "ac3", str(out)], check=True)
    return out


@pytest.fixture
def cache(tmp_path) -> Cache:
    return Cache(tmp_path / "cache", max_bytes=10**9)


def make(video, cache, audio_index=0, **kwargs):
    kwargs.setdefault("encoders", ("libx264",))
    return preview.preview_copy(video, key=KEY, audio_index=audio_index, tools=Tools.find(),
                                cache=cache, timeout=120, **kwargs)


@pytest.mark.media
def test_a_video_becomes_h264_480p_with_aac_stereo_in_mp4_and_no_title_or_chapters(tmp_path,
                                                                                  cache):
    tools = Tools.find()
    copy = make(hd_clip(tmp_path), cache)
    assert copy == preview.PreviewCopy(cache.root / KEY / "preview-a0.mp4", "libx264")
    info = ffprobe(tools, copy.path)
    assert "mp4" in info["format"]["format_name"].split(",")
    picture, sound = info["streams"]
    assert (picture["codec_name"], picture["pix_fmt"]) == ("h264", "yuv420p")
    assert (picture["width"], picture["height"]) == (854, 480)
    assert (sound["codec_name"], sound["channels"]) == ("aac", 2)
    assert "Secret" not in json.dumps(info) and info["chapters"] == []
    assert sorted(p.name for p in copy.path.parent.iterdir()) == ["preview-a0.json",
                                                                 "preview-a0.mp4"]


@pytest.mark.media
def test_a_small_video_is_never_scaled_up(tmp_path, cache):
    small = make_clip(tmp_path, "Show - S01E02.mkv", seconds=2.0, audio_codec="ac3")
    picture = ffprobe(Tools.find(), make(small, cache).path)["streams"][0]
    assert (picture["width"], picture["height"]) == (160, 120)


@pytest.mark.media
def test_the_chosen_audio_track_is_the_one_kept(tmp_path, cache):
    copy = make(hd_clip(tmp_path), cache, audio_index=1)
    assert copy.path.name == "preview-a1.mp4"
    assert abs(loudest_hz(Tools.find(), copy.path) - 550) < 5


@pytest.mark.media
def test_progress_is_reported_as_the_encode_goes_and_reaches_the_end(tmp_path, cache):
    seen = []
    make(hd_clip(tmp_path), cache, on_progress=seen.append)
    assert seen and seen == sorted(seen) and all(isinstance(ms, int) for ms in seen)
    assert 1800 <= seen[-1] <= 2100


@pytest.mark.media
def test_a_copy_is_made_once_then_reused_with_the_encoder_that_made_it(tmp_path, cache,
                                                                      monkeypatch):
    video = hd_clip(tmp_path)
    assert preview.cached_preview(cache, key=KEY, audio_index=0) is None
    first = make(video, cache)
    runs = []
    monkeypatch.setattr(preview, "stream_tool", lambda *a, **kw: runs.append(a))
    os.utime(cache.root / KEY, (1_000, 1_000))
    assert make(video, cache, encoders=None) == first and runs == []
    assert preview.cached_preview(cache, key=KEY, audio_index=0) == first
    assert (cache.root / KEY).stat().st_mtime > 1_000  # reusing it marks the entry used


@pytest.mark.media
def test_a_hardware_encoder_that_fails_on_the_file_falls_back_to_libx264(tmp_path, cache,
                                                                        monkeypatch):
    # It passed its trial, then failed on the real file: libx264 makes the copy, and says so.
    monkeypatch.setitem(preview.ENCODERS, "h264_nvenc", ("yuv420p", ("-c:v", "no_such_encoder")))
    copy = make(hd_clip(tmp_path), cache, encoders=("h264_nvenc", "libx264"))
    assert copy.encoder == "libx264"
    assert ffprobe(Tools.find(), copy.path)["streams"][0]["codec_name"] == "h264"
    assert json.loads((copy.path.parent / "preview-a0.json").read_text(encoding="utf-8")) == {
        "encoder": "libx264"}


@pytest.mark.media
def test_an_encoder_is_tried_for_real_on_a_tiny_input_before_it_is_chosen(tmp_path,
                                                                         monkeypatch):
    tools = Tools.find()
    assert preview.works_here(tools, "libx264", cwd=tmp_path)
    monkeypatch.setitem(preview.ENCODERS, "h264_nvenc", ("yuv420p", ("-c:v", "no_such_encoder")))
    assert not preview.works_here(tools, "h264_nvenc", cwd=tmp_path)
    assert preview.pick_encoders(tools, cwd=tmp_path)[-1] == "libx264"
    assert list(tmp_path.iterdir()) == []  # a trial writes nothing


@pytest.mark.media
def test_cancelling_mid_encode_leaves_nothing_in_the_cache(tmp_path, cache):
    stop = []
    with pytest.raises(Cancelled):
        make(hd_clip(tmp_path, seconds=20.0), cache, on_progress=stop.append,
             cancelled=lambda: bool(stop))
    assert list((cache.root / KEY).iterdir()) == []


@pytest.mark.media
def test_a_file_ffmpeg_cannot_read_leaves_nothing_in_the_cache(tmp_path, cache):
    bad = tmp_path / "Show - S01E03.mkv"
    bad.write_bytes(b"not a video")
    with pytest.raises(ToolFailed):
        make(bad, cache)
    assert list((cache.root / KEY).iterdir()) == []


@pytest.mark.media
def test_making_one_evicts_older_entries_but_never_its_own(tmp_path):
    cache = Cache(tmp_path / "cache", max_bytes=1)
    old = cache.folder("b" * 64)
    (old / "preview-a0.mp4").write_bytes(b"x" * 1000)
    os.utime(old, (1_000, 1_000))
    copy = make(make_clip(tmp_path, seconds=2.0), cache)
    assert copy.path.is_file() and not old.exists()


def test_a_record_naming_an_encoder_vid2sub_does_not_use_reads_as_unknown(cache):
    folder = cache.folder(KEY)
    (folder / "preview-a0.mp4").write_bytes(b"x")
    (folder / "preview-a0.json").write_text('{"encoder": "<b>x</b>"}', encoding="utf-8")
    assert preview.cached_preview(cache, key=KEY, audio_index=0).encoder == "unknown"
    (folder / "preview-a0.json").write_text("not json", encoding="utf-8")
    assert preview.cached_preview(cache, key=KEY, audio_index=0).encoder == "unknown"


def test_a_negative_track_index_is_refused(cache, tmp_path):
    with pytest.raises(ValueError, match="audio track"):
        make(tmp_path / "x.mkv", cache, -1)
```

  In `tests/test_tools.py`, below `import sys` add `import time`, and append, after two blank
  lines:

```python
# Phase 3, Task 7: a long run, read as it goes (the preview copy's progress, spec §8.8)

TICKS = "import sys, time\nfor i in range(3):\n    print(f'tick={i}', flush=True)\n"
FAILS = "import sys; sys.stderr.write('bad' * 3000); sys.exit(3)"


def test_a_streamed_tool_hands_over_each_line_as_it_comes(tmp_path):
    lines = []
    t.stream_tool([sys.executable, "-c", TICKS], cwd=tmp_path, timeout=30, on_line=lines.append)
    assert lines == ["tick=0", "tick=1", "tick=2"]


def test_a_streamed_tool_sees_no_keys_and_no_stdin(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "should-not-leak")
    lines = []
    script = "import os, sys; print('OPENAI_API_KEY' in os.environ); print(repr(sys.stdin.read()))"
    t.stream_tool([sys.executable, "-c", script], cwd=tmp_path, timeout=30,
                  on_line=lines.append)
    assert lines == ["False", "''"]


def test_a_streamed_tool_that_fails_raises_with_its_stderr(tmp_path):
    with pytest.raises(t.ToolFailed) as err:
        t.stream_tool([sys.executable, "-c", FAILS], cwd=tmp_path, timeout=30, on_line=print)
    assert err.value.returncode == 3 and err.value.stderr.endswith("bad")
    assert len(err.value.stderr) <= 4000


def test_a_streamed_tool_is_stopped_when_its_caller_cancels(tmp_path):
    started = time.monotonic()
    lines = []
    with pytest.raises(t.Cancelled):
        t.stream_tool([sys.executable, "-c", TICKS + "time.sleep(60)"], cwd=tmp_path,
                      timeout=120, on_line=lines.append, cancelled=lambda: bool(lines))
    assert time.monotonic() - started < 10


def test_a_streamed_tool_that_goes_quiet_past_its_timeout_is_stopped(tmp_path):
    started = time.monotonic()
    with pytest.raises(t.ToolFailed, match="exit -1") as err:
        t.stream_tool([sys.executable, "-c", "import time; time.sleep(60)"], cwd=tmp_path,
                      timeout=1, on_line=print)
    assert "timed out" in err.value.stderr and time.monotonic() - started < 10


def test_a_streamed_tool_refuses_a_relative_executable(tmp_path):
    with pytest.raises(ValueError, match="absolute"):
        t.stream_tool(["ffmpeg", "-version"], cwd=tmp_path, timeout=5, on_line=print)
```

- [ ] **Step 2: Run them; watch them fail.** `uv run pytest tests/test_preview.py -q`. Expected:
  `E   ImportError: cannot import name 'Cancelled' from 'vid2sub.media.tools'
  (…/src/vid2sub/media/tools.py)` and `1 error`. `uv run pytest tests/test_tools.py -q`.
  Expected: `E           AttributeError: module 'vid2sub.media.tools' has no attribute
  'stream_tool'` and `6 failed, 15 passed, 1 skipped`.
- [ ] **Step 3: Write the code.** The hook blocks shell commands that name `src/vid2sub/media/`:
  write and edit both files with the file tools. Replace `src/vid2sub/media/preview.py` with:

```python
"""The playback audio and the preview copy: what the editor plays when a browser can't play an
episode itself (spec §8.8), made on demand into the cache (§8.9) and reused after that.

The playback audio: a browser plays neither AC-3, E-AC-3, DTS nor TrueHD, and silent playback is
worse than none (§8.2), so the editor plays this `.m4a` instead, the first time an episode needs
it (Dan, 2026-10-14; Q&A item 13 brought it into Phase 2, S43). Only the chosen audio track is
kept, with no video, subtitles, data, metadata or chapters, so the show's title never reaches the
file, as with chunks (§7.3); `+faststart` puts the index first so playback starts before the
whole file is read. ffmpeg writes to a temporary name in the entry's folder and the result is
renamed into place, so a half-made file is never served, and an entry being made is never evicted.

The preview copy (Phase 3 Task 7, S63), made when the person asks (**Make preview copy**), has the
picture too: H.264 at 480 lines or fewer (never scaled up; an even height, the width following the
picture's shape; 8-bit 4:2:0, which every browser that plays H.264 decodes) with the chosen audio
track as AAC stereo, in an MP4, kept as bare as the playback audio. ffmpeg's hardware encoders
come first where this ffmpeg lists them, in spec §8.8's order (VideoToolbox, NVENC, Quick Sync),
each tried for real on a tiny generated picture first, since a listed encoder still fails on a
machine without the hardware or its driver; else libx264 `-preset veryfast`. An encoder that
passed its trial and then fails on the episode gives way to libx264, and a record beside the copy
names the encoder that made it. A long episode takes minutes, so the copy reports how far ffmpeg
has got (its `-progress` lines) and stops when its caller asks; as with the playback audio,
ffmpeg writes to a temporary name that is removed unless the whole copy is renamed into place.
"""

from __future__ import annotations

import json
import os
import re
import secrets
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from pathlib import Path

from vid2sub.cache import Cache
from vid2sub.media.tools import ToolFailed, Tools, input_args, run_tool, stream_tool

HARDWARE = ("h264_videotoolbox", "h264_nvenc", "h264_qsv")  # spec §8.8, in its order
SOFTWARE = "libx264"
# Each encoder's picture format, then its options: a bit rate that suits 480p for the hardware
# ones, and libx264 at spec §8.8's `-preset veryfast` with its default quality. Quick Sync and
# VideoToolbox take nv12; both formats are 8-bit 4:2:0.
ENCODERS: dict[str, tuple[str, tuple[str, ...]]] = {
    "h264_videotoolbox": ("nv12", ("-c:v", "h264_videotoolbox", "-b:v", "1500k")),
    "h264_nvenc": ("yuv420p", ("-c:v", "h264_nvenc", "-preset", "p4", "-b:v", "1500k")),
    "h264_qsv": ("nv12", ("-c:v", "h264_qsv", "-preset", "veryfast", "-b:v", "1500k")),
    "libx264": ("yuv420p", ("-c:v", "libx264", "-preset", "veryfast", "-crf", "23")),
}
SCALE = "scale=-2:'trunc(min(480,ih)/2)*2'"  # 480 lines at most, never more than it has
TRIAL = "color=c=black:s=320x240:r=10:d=0.3"  # three frames, larger than any encoder's minimum
TRIAL_TIMEOUT = 30.0
_LISTED = re.compile(r"^\s*V\S{5}\s+(\w+)", re.MULTILINE)  # ` V....D libx264  …`


class NoEncoder(RuntimeError):
    """This ffmpeg lists none of the H.264 encoders vid2sub uses."""


@dataclass(frozen=True)
class PreviewCopy:
    path: Path
    encoder: str  # a key of ENCODERS, or "unknown" when the record beside it can't be read


def _check_track(audio_index: int) -> None:
    if isinstance(audio_index, bool) or not isinstance(audio_index, int) or audio_index < 0:
        raise ValueError("an audio track is a number from 0")


def playback_audio(video: Path, *, key: str, audio_index: int, tools: Tools, cache: Cache,
                   timeout: float) -> Path:
    """`audio_index` counts audio tracks only (ffmpeg's `a:N`, `probe.AudioTrack.index`)."""
    _check_track(audio_index)
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


def listed_encoders(listing: str) -> frozenset[str]:
    """The video encoders `ffmpeg -encoders` lists (its legend lines name none)."""
    return frozenset(_LISTED.findall(listing))


def encoders_to_try(listed: Collection[str], works: Callable[[str], bool]) -> tuple[str, ...]:
    """The first listed hardware encoder that `works` here, then libx264 if listed; `works` is
    asked about each hardware encoder in turn until one passes, never about libx264."""
    hardware = next((name for name in HARDWARE if name in listed and works(name)), None)
    found = tuple(name for name in (hardware, SOFTWARE) if name is not None and name in listed)
    if not found:
        raise NoEncoder("this ffmpeg has no H.264 encoder vid2sub can use (libx264, "
                        "VideoToolbox, NVENC or Quick Sync)")
    return found


def works_here(tools: Tools, name: str, *, cwd: Path) -> bool:
    """Whether encoder `name` encodes a tiny generated picture here, writing nothing."""
    pix, options = ENCODERS[name]
    try:
        run_tool([tools.need("ffmpeg"), "-nostdin", "-hide_banner", "-loglevel", "error",
                  "-f", "lavfi", "-i", TRIAL, "-vf", f"format={pix}", *options,
                  "-f", "null", "-"], cwd=cwd, timeout=TRIAL_TIMEOUT)
    except ToolFailed:
        return False
    return True


def pick_encoders(tools: Tools, *, cwd: Path) -> tuple[str, ...]:
    """What this ffmpeg lists, each hardware encoder tried for real (`encoders_to_try`)."""
    listing = run_tool([tools.need("ffmpeg"), "-nostdin", "-hide_banner", "-encoders"],
                       cwd=cwd, timeout=TRIAL_TIMEOUT).stdout.decode("utf-8", errors="replace")
    return encoders_to_try(listed_encoders(listing),
                           lambda name: works_here(tools, name, cwd=cwd))


def cached_preview(cache: Cache, *, key: str, audio_index: int) -> PreviewCopy | None:
    """The copy made for this video and track, if there is one (marking its entry used)."""
    _check_track(audio_index)
    folder = cache.folder(key)
    out = folder / f"preview-a{audio_index}.mp4"
    if not out.is_file():
        return None
    try:
        record = json.loads((folder / f"preview-a{audio_index}.json").read_text(
            encoding="utf-8"))
        encoder = record.get("encoder") if isinstance(record, dict) else None
    except (OSError, ValueError):
        encoder = None
    return PreviewCopy(out, encoder if isinstance(encoder, str) and encoder in ENCODERS
                       else "unknown")


def _progress_lines(on_progress: Callable[[int], None] | None) -> Callable[[str], None]:
    """Reads ffmpeg's `-progress` lines (`key=value`), handing on `out_time_us` in ms each time
    it grows; it is "N/A" before the first frame."""
    reached = -1

    def line(text: str) -> None:
        nonlocal reached
        field, _, value = text.partition("=")
        if field == "out_time_us" and value.isdigit() and on_progress is not None:
            done = int(value) // 1000
            if done > reached:
                reached = done
                on_progress(done)

    return line


def preview_copy(video: Path, *, key: str, audio_index: int, tools: Tools, cache: Cache,
                 timeout: float, on_progress: Callable[[int], None] | None = None,
                 cancelled: Callable[[], bool] | None = None,
                 encoders: Sequence[str] | None = None) -> PreviewCopy:
    """The copy for `video` and its audio track `audio_index`, made unless the cache has it.
    `encoders`: the ones to try, in turn; by default `pick_encoders`'. `on_progress` gets how
    far the encode has got, in ms of the episode, each time that grows; `cancelled` is asked a
    few times a second, and its true stops the encode (`tools.Cancelled`). Blocks for minutes
    on a long episode."""
    found = cached_preview(cache, key=key, audio_index=audio_index)
    if found is not None:
        return found
    folder = cache.folder(key)
    ffmpeg = tools.need("ffmpeg")
    todo = tuple(encoders) if encoders is not None else pick_encoders(tools, cwd=folder)
    if not todo:
        raise NoEncoder("no H.264 encoder to try")
    failed: ToolFailed | None = None
    for name in todo:
        pix, options = ENCODERS[name]
        tmp = folder / f".preview-a{audio_index}-{secrets.token_hex(4)}.part"
        record = tmp.with_suffix(".json")
        line = _progress_lines(on_progress)  # from 0 again for each encoder tried
        try:
            stream_tool([ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-nostats",
                         "-progress", "pipe:1", *input_args(video),
                         "-map", "0:V:0", "-map", f"0:a:{audio_index}",
                         "-vf", f"{SCALE},format={pix}", *options,
                         "-ac", "2", "-c:a", "aac", "-b:a", "160k", "-sn", "-dn",
                         "-map_metadata", "-1", "-map_chapters", "-1", "-fflags", "+bitexact",
                         "-movflags", "+faststart", "-f", "mp4", str(tmp)],
                        cwd=folder, timeout=timeout, on_line=line,
                        cancelled=cancelled or (lambda: False))
            record.write_text(json.dumps({"encoder": name}), encoding="utf-8")
            os.replace(record, folder / f"preview-a{audio_index}.json")
            os.replace(tmp, folder / f"preview-a{audio_index}.mp4")
        except ToolFailed as err:
            failed = err
            continue
        finally:
            tmp.unlink(missing_ok=True)
            record.unlink(missing_ok=True)
        cache.evict(keep=key)
        return PreviewCopy(folder / f"preview-a{audio_index}.mp4", name)
    assert failed is not None
    raise failed
```

  In `src/vid2sub/media/tools.py`, replace the module docstring and imports, from its first line
  down to `from pathlib import Path`, with:

```python
"""Finding and running ffmpeg, ffprobe and deno (spec §6.7, §4.2).

Every child process runs through `run_tool`, or `stream_tool` for a long run read as it goes (the
preview copy's progress, Phase 3 Task 7): an absolute executable (never found in the current
directory, which Windows would otherwise search first), an argument list with no shell, `cwd` set
to the job's scratch folder, an allowlisted environment so it never inherits a key, and a
timeout. ffmpeg and ffprobe read input only through the `file` protocol and a demuxer allowlist,
so a playlist disguised as `.mp4` can neither fetch URLs nor read other files. Homebrew's folders
are a fallback because launchd's PATH doesn't include them (an audio-router lesson).
`stream_tool` reads the child's output on threads of its own, so neither pipe can fill and stall
it, and checks its caller's `cancelled` and its deadline a few times a second even while the
child is quiet (an episode on a sleeping network share); either one kills the child.
"""

from __future__ import annotations

import os
import queue
import re
import subprocess
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
```

  Below the `ToolFailed` class (its last line is
  `        super().__init__(f"{tool} failed (exit {returncode})")`), add, after two blank lines:

```python
class Cancelled(Exception):
    """A tool stopped because its caller asked it to (`stream_tool`'s `cancelled`)."""
```

  and above `def input_args(path: Path) -> list[str]:` add:

```python
STDERR_KEPT = 4000  # characters of a failed tool's stderr kept for its error, as run_tool keeps


def stream_tool(args: Sequence[str], *, cwd: Path, timeout: float,
                on_line: Callable[[str], None],
                cancelled: Callable[[], bool] = lambda: False) -> None:
    """Runs a tool as `run_tool` does, handing each line of its stdout to `on_line` as it comes
    (stripped). Cancelled when `cancelled()` turns true, ToolFailed when it exits non-zero or
    outlives `timeout`; either way the child is killed first."""
    if not os.path.isabs(args[0]):
        raise ValueError("stream_tool needs an absolute executable path")
    name = Path(args[0]).name
    # stdin is a pipe closed at once, so the child reads nothing from it; not os.devnull, which
    # Popen opens for writing too, and the demo's audit hook refuses that (web.demo.isolate).
    proc = subprocess.Popen(list(args), cwd=cwd, env=child_env(), stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
    proc.stdin.close()
    lines: queue.Queue[bytes | None] = queue.Queue()
    err = bytearray()

    def read_out() -> None:
        for line in iter(proc.stdout.readline, b""):
            lines.put(line)
        lines.put(None)

    def read_err() -> None:
        for chunk in iter(lambda: proc.stderr.read(4096), b""):
            err.extend(chunk)
            del err[:-STDERR_KEPT * 4]  # bytes: a UTF-8 character is at most four

    readers = [threading.Thread(target=read_out, daemon=True),
               threading.Thread(target=read_err, daemon=True)]
    for r in readers:
        r.start()
    deadline = time.monotonic() + timeout
    try:
        while True:
            if cancelled():
                raise Cancelled(f"{name} was stopped")
            if time.monotonic() > deadline:
                raise ToolFailed(name, -1, f"timed out after {timeout:.0f} s")
            try:
                line = lines.get(timeout=0.2)
            except queue.Empty:
                continue
            if line is None:
                break
            on_line(line.decode("utf-8", errors="replace").strip())
        try:  # its output has ended; let it finish, within the time it has left
            proc.wait(timeout=max(0.0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            raise ToolFailed(name, -1, f"timed out after {timeout:.0f} s") from None
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait()
        for r in readers:  # the child's end of each pipe is closed now, so each reader ends
            r.join(timeout=5)
        proc.stdout.close()
        proc.stderr.close()
    if proc.returncode != 0:
        raise ToolFailed(name, proc.returncode,
                         err.decode("utf-8", errors="replace")[-STDERR_KEPT:])


```

- [ ] **Step 4: Run the checks; they pass.** `VID2SUB_REQUIRE_FFMPEG=1 uv run pytest
  tests/test_preview.py tests/test_playback.py tests/test_tools.py -q` first (`43 passed, 1
  skipped`; on this Mac the cancel test stops a 20 s 720p encode at its first progress line), then
  the guard checks, then `make check`. **Guard checks**, each with the file tools, reverted and
  restored, each with `VID2SUB_REQUIRE_FFMPEG=1 uv run pytest tests/test_preview.py -q`: in
  `preview_copy`'s `finally`, take out `tmp.unlink(missing_ok=True)` (`FAILED
  …test_cancelling_mid_encode_leaves_nothing_in_the_cache`: a `.preview-a0-….part` stays); in
  `encoders_to_try`, replace `if name in listed and works(name)), None)` with
  `if name in listed), None)` (`2 failed`: the two choice tests); in `preview_copy`, replace
  `            continue` with `            raise` (`FAILED
  …test_a_hardware_encoder_that_fails_on_the_file_falls_back_to_libx264`, `ToolFailed: ffmpeg
  failed (exit 8)`). `make check`. Expected: `1218 passed, 7 skipped, 41 deselected` twice,
  `Test Files  21 passed (21)`, `Tests  100 passed (100)`, `All checks passed!` and
  `no leaks found`.
- [ ] **Step 5: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(media): 🤖 a preview copy is H.264 480p with AAC stereo, from a hardware encoder that works here, else libx264

vid2sub.media.preview.preview_copy (spec §8.8, §8.9; S63) makes
<cache>/<quick_sha256>/preview-a<N>.mp4: the first real video stream
(0:V:0, never cover art) scaled to 480 lines or fewer, never up, at an even
height with the width kept to its shape, 8-bit 4:2:0, and the chosen audio
track as AAC stereo 160k, in an MP4 with +faststart and no subtitles, data,
metadata or chapters. pick_encoders reads `ffmpeg -encoders`
(listed_encoders) and tries each listed hardware encoder in spec §8.8's
order (h264_videotoolbox, h264_nvenc, h264_qsv) for real on three frames of
a generated picture written to the null muxer (works_here), since a listed
encoder still fails without its hardware or driver; the first that works
comes before libx264 -preset veryfast -crf 23 (encoders_to_try, which a
fake listing tests). One that passes its trial and fails on the episode
gives way to libx264, and preview-a<N>.json names the encoder that made the
copy (cached_preview reads it back; a name vid2sub doesn't use reads as
"unknown"). The copy is made once, then reused, marking its entry used.

ffmpeg writes to a temporary name in the entry's folder, removed unless the
whole copy is renamed into place, so a cancelled or failed encode leaves
nothing in the cache. media.tools.stream_tool runs it as run_tool runs
every tool (absolute path, no shell, allowlisted environment) and hands
each stdout line on as it comes: the copy reports ffmpeg's -progress
out_time_us in ms. Its readers are threads of its own,
so neither pipe stalls the child, and it checks its caller's `cancelled`
and its deadline five times a second even while ffmpeg is quiet; either
kills the child (tools.Cancelled, or ToolFailed "timed out"). The
playback audio's code is unchanged; its track check is shared.

The new tests failed first with: ImportError: cannot import name
'Cancelled' from 'vid2sub.media.tools', and AttributeError: module
'vid2sub.media.tools' has no attribute 'stream_tool' (6 failed, 15
passed, 1 skipped). Guard checks, each reverted and restored: without the
finally's unlink of the temporary file, the cancelled encode leaves a
.part in the cache (test_cancelling_mid_encode_leaves_nothing_in_the_cache
fails); without the trial, a listed encoder that can't run is chosen (two
choice tests fail); re-raising a failed encode instead of trying the next
encoder fails the libx264 fallback test with ToolFailed (exit 8).

Docs read: ffmpeg's codec documentation (ffmpeg-codecs.html: NVENC's
-preset p1 to p7, default p4, -b:v; QSV's -preset veryfast…veryslow;
libx264's -preset and -crf); `ffmpeg -h encoder=h264_videotoolbox` and
`-h encoder=libx264` on ffmpeg 9.0.2 (Homebrew): VideoToolbox takes nv12
or yuv420p and -allow_sw defaults to false, so without the hardware it
fails rather than encoding in software; libx264's -preset defaults to
medium. ffmpeg.html: -progress url ("program-friendly progress
information", written periodically and at the end), -stats_period
(default 0.5 s), -nostats, and the stream specifier 'V' ("only matches
video streams which are not attached pictures, video thumbnails or cover
arts"). The scale filter's -2 width and min(480,ih) height were checked
on ffmpeg 9.0.2 by the tests (1280x720 becomes 854x480, 160x120 stays);
the fetched filters page didn't reach the scale section.

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md Task 7
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/media/preview.py src/vid2sub/media/tools.py tests/test_preview.py
  tests/test_tools.py` (when this listing was built the hook let `git add` name the path; if it
  blocks it, say so and stop rather than rephrasing the command), `git commit -F
  .git/COMMIT_MSG`, then `git log -1 --format='%(trailers)'` shows `Plan:`.

#### Round 7b: the server makes the copy without holding up the tab

- [ ] **Step 6: Write the failing tests.** In `tests/test_web_server.py`, below
  `from vid2sub.web.backend import LocalBackend` add
  `from vid2sub.web.episode import Capabilities, PreviewError`, and append, after two blank lines:

```python
# ---- the editor: the preview copy (Phase 3, Task 7) ---------------------------------------------


PREVIEW_OUTPUTS = {"episode", "busy", "preview"}


@pytest.fixture
def libx264_only(monkeypatch):
    """No hardware encoder is tried, so every machine makes the same copy."""
    from vid2sub.media import preview

    monkeypatch.setattr(preview, "HARDWARE", ())


def sound_only(t: Tab, video) -> dict:
    """Opens `video` and says, as the page does, that the browser can't play it: the episode
    once the playback audio is in."""
    ep = opened_in(t, video)
    t.set(playback={"episode": ep["id"], "n": 2})
    return t.until(lambda t: opened(t)["video"]["audio_url"] and opened(t))


def previews_seen(t: Tab) -> list:
    return [m["values"]["preview"] for m in t.messages if "preview" in m.get("values", {})]


@pytest.mark.media
def test_make_preview_copy_makes_a_copy_the_player_gets_by_a_media_token(
        media_client, media_rt, tmp_path, libx264_only):
    # Spec §8.8, S63: asked for while the sound plays alone; the copy goes in the cache, keyed
    # by the video's quick hash (§8.9), and the player gets it through /media/ (§6.3).
    video = make_episode(tmp_path / "Secret Show")
    with tab(media_client, PREVIEW_OUTPUTS) as t:
        ep = sound_only(t, video)
        assert (ep["video"]["preview_url"], ep["video"]["preview_encoder"]) == (None, None)
        t.set(preview={"episode": ep["id"], "n": 3})
        made = t.until(lambda t: opened(t)["video"]["preview_url"] and opened(t))["video"]
        copy = media_rt.media.resolve(made["preview_url"].removeprefix("/media/"))
        assert copy is not None and copy.name == "preview-a0.mp4"
        assert copy.parent.parent == tmp_path / "cache" and made["preview_encoder"] == "libx264"
        # the sound stays playable too, for a browser that can't play the copy either
        assert media_rt.media.resolve(made["audio_url"].removeprefix("/media/")) is not None
        t.until(lambda t: previews_seen(t)[-1] is None and len(previews_seen(t)) > 2)
        making = [p for p in previews_seen(t) if p is not None]
        assert making and {p["episode"] for p in making} == {ep["id"]}
        assert all(p["of_ms"] == opened(t)["video"]["duration_ms"] for p in making)
        assert t.notices() == [{"kind": "info", "text": "the preview copy is ready (libx264)"}]
        everything = json.dumps(t.messages)
        assert "Secret Show" not in everything and str(tmp_path) not in everything


@pytest.mark.media
def test_an_episode_whose_copy_was_made_before_gets_it_with_the_playback_audio(
        media_client, media_rt, tmp_path, libx264_only):
    video = make_episode(tmp_path / "ep")
    with tab(media_client, PREVIEW_OUTPUTS) as t:
        ep = sound_only(t, video)
        t.set(preview={"episode": ep["id"], "n": 3})
        t.until(lambda t: opened(t)["video"]["preview_url"])
    with tab(media_client, PREVIEW_OUTPUTS) as t:
        again = sound_only(t, video)["video"]
        assert again["preview_encoder"] == "libx264"
        assert media_rt.media.resolve(again["preview_url"].removeprefix("/media/")).name == (
            "preview-a0.mp4")


@pytest.mark.media
def test_a_copy_is_made_only_while_the_sound_plays_alone_and_only_where_jobs_can_run(
        media_client, media_rt, tmp_path, monkeypatch):
    asked = []
    monkeypatch.setattr(runtime.Runtime, "make_preview",
                        lambda self, ep, **kwargs: asked.append(ep.id))
    video = make_episode(tmp_path / "ep")
    with tab(media_client, PREVIEW_OUTPUTS) as t:
        ep = opened_in(t, video)  # the browser plays the video itself: there is nothing to do
        t.set(preview={"episode": ep["id"], "n": 2})
        t.set(preview={"episode": "e" + "0" * 16, "n": 3})
        t.set(preview="<img src=x>")
        time.sleep(0.5)
        monkeypatch.setattr(LocalBackend, "capabilities",
                            lambda self: Capabilities("local", False, "disk", True))
        t.set(playback={"episode": ep["id"], "n": 4})
        t.until(lambda t: opened(t)["video"]["audio_url"])
        t.set(preview={"episode": ep["id"], "n": 5})  # as in Pages, where generate is false
        time.sleep(0.5)
        assert asked == [] and t.notices() == [] and "<img" not in json.dumps(t.messages)


@pytest.mark.media
def test_closing_the_tab_mid_encode_stops_it_and_a_second_ask_meanwhile_is_ignored(
        media_client, media_rt, tmp_path, monkeypatch):
    asked, stopped = [], threading.Event()

    def slow(self, ep, *, on_progress=None, cancelled=None):
        asked.append(ep.id)
        on_progress(500)
        deadline = time.monotonic() + 20
        while not cancelled() and time.monotonic() < deadline:
            time.sleep(0.02)
        if cancelled():
            stopped.set()

    monkeypatch.setattr(runtime.Runtime, "make_preview", slow)
    video = make_episode(tmp_path / "ep")
    with tab(media_client, PREVIEW_OUTPUTS) as t:
        ep = sound_only(t, video)
        t.set(preview={"episode": ep["id"], "n": 3})
        shown = t.until(lambda t: t.has("preview") and (t.value("preview") or {}).get("done_ms"))
        assert shown == 500
        t.set(preview={"episode": ep["id"], "n": 4})
        time.sleep(0.3)
    assert stopped.wait(10) and asked == [ep["id"]]


@pytest.mark.media
def test_a_copy_that_cant_be_made_is_a_notice_and_the_sound_plays_on(media_client, media_rt,
                                                                     tmp_path, monkeypatch):
    def fails(self, ep, **kwargs):
        raise PreviewError("this ffmpeg has no H.264 encoder vid2sub can use")

    monkeypatch.setattr(runtime.Runtime, "make_preview", fails)
    video = make_episode(tmp_path / "ep")
    with tab(media_client, PREVIEW_OUTPUTS) as t:
        ep = sound_only(t, video)
        t.set(preview={"episode": ep["id"], "n": 3})
        (notice,) = t.until(lambda t: t.notices())
        assert notice == {"kind": "error", "text": "couldn't make a preview copy: this ffmpeg "
                                                   "has no H.264 encoder vid2sub can use"}
        t.until(lambda t: previews_seen(t) and previews_seen(t)[-1] is None)
        assert opened(t)["video"]["audio_url"] == ep["video"]["audio_url"]
        assert opened(t)["video"]["preview_url"] is None


@pytest.mark.media
def test_the_runtime_names_no_path_when_ffmpeg_fails_and_gives_nothing_when_stopped(
        media_rt, tmp_path):
    ep = media_rt.backend.open(str(make_episode(tmp_path / "Secret Show")))
    ep.video.write_bytes(b"not a video any more")
    with pytest.raises(PreviewError) as err:
        media_rt.make_preview(ep)
    assert str(err.value) == "ffmpeg couldn't make a preview copy of this video"
    assert media_rt.make_preview(ep, cancelled=lambda: True) is None
```

  In `tests/test_views.py`, replace

```python
                          "audio_url": "/media/abc", "playable_audio": True, "container": "",
                          "video_codec": None, "audio_codec": ""}
```

  with

```python
                          "audio_url": "/media/abc", "playable_audio": True, "container": "",
                          "video_codec": None, "audio_codec": "", "preview_url": None,
                          "preview_encoder": None}
```

  and above `def test_a_view_is_plain_json():` add:

```python
def test_the_video_carries_its_preview_copy_and_the_encoder_that_made_it():
    # Spec §8.8 (Phase 3, Task 7): the copy by its media token, never its path in the cache.
    video = views.episode_view(episode(), video_url=None, audio_url="/media/a",
                               preview_url="/media/p", preview_encoder="libx264")["video"]
    assert (video["audio_url"], video["preview_url"], video["preview_encoder"]) == (
        "/media/a", "/media/p", "libx264")


```

- [ ] **Step 7: Run them; watch them fail.** `uv run pytest tests/test_web_server.py -q`.
  Expected: `E   ImportError: cannot import name 'PreviewError' from 'vid2sub.web.episode'
  (…/src/vid2sub/web/episode.py)` and `1 error`. `uv run pytest tests/test_views.py -q`.
  Expected: `E       TypeError: episode_view() got an unexpected keyword argument
  'preview_url'` and `2 failed, 23 passed`.
- [ ] **Step 8: Write the code.** In `src/vid2sub/web/episode.py`, above
  `@dataclass(frozen=True)` / `class SaveResult:`, add:

```python
class PreviewError(Exception):
    """A preview copy that couldn't be made (spec §8.8): ffmpeg missing, with no H.264 encoder,
    or failing on the video. The reason is fit to show and names no path; the local runtime
    makes it from ffmpeg's own errors, which the server can't import in Pages (Phase 3 Task 7)."""


```

  In `src/vid2sub/web/runtime.py`, replace

```python
`Runtime` (`reachable`, `media_for`, `retranslate`, `endpoint_models`, the browser's and
Review's). Every call that blocks goes through
`blocking`, never a thread or an executor of the server's own: a worker thread here, inline in
Pyodide, which has no threads (Task 14 round 14a, decided with the coordinator 2026-10-24).
"""
```

  with

```python
`Runtime` (`reachable`, `media_for`, `make_preview`, `retranslate`, `endpoint_models`, the
browser's and Review's). Every call that blocks goes through `blocking`, never a thread or an
executor of the server's own: a worker thread here, inline in Pyodide, which has no threads (Task
14 round 14a, decided with the coordinator 2026-10-24). The preview copy (spec §8.8, Phase 3 Task
7) is made into the cache, as the playback audio is, and an episode whose copy is there already
gets it with the playback audio.
"""
```

  (in the module docstring; `from pathlib import Path` is already imported, for Task 2's
  browser); and below the `APP_WAIT_S = 30.0 …` line (Task 6's) add:

```python
PREVIEW_TIMEOUT = 4 * 3600.0  # seconds: a two-hour episode's picture, through libx264, likewise
NO_PREVIEW = "ffmpeg couldn't make a preview copy of this video"
```

  In `src/vid2sub/web/runtime.py`, replace

```python
    video_url: str | None
    audio_url: str | None
    problem: str | None = None
```

  with

```python
    video_url: str | None
    audio_url: str | None
    problem: str | None = None
    preview_url: str | None = None  # the preview copy, once made (spec §8.8)
    preview_encoder: str | None = None  # the ffmpeg encoder that made it
```

  and above `@dataclass(frozen=True)` / `class Runtime:` add:

```python
@dataclass(frozen=True)
class Preview:
    """A preview copy `make_preview` made: the file, for a media token, and its encoder."""

    path: Path
    encoder: str


```

  In `Runtime.media_for`, replace

```python
        from vid2sub.media.preview import playback_audio
        from vid2sub.media.tools import ToolFailed, ToolMissing
```

  with

```python
        from vid2sub.media.preview import cached_preview, playback_audio
        from vid2sub.media.tools import ToolFailed, ToolMissing
```

  and replace

```python
            return Media(None, f"/media/{self.media.issue(audio, owner=ep.id)}")
```

  with

```python
            media = Media(None, f"/media/{self.media.issue(audio, owner=ep.id)}")
            copy = cached_preview(self.backend.cache, key=ep.header.video.quick_sha256,
                                  audio_index=ep.audio_index)
            if copy is None:
                return media
            return dataclasses.replace(
                media, preview_url=f"/media/{self.media.issue(copy.path, owner=ep.id)}",
                preview_encoder=copy.encoder)
```

  Then below `media_for`'s last line (`                         "couldn't make a copy it can
  play")`) add, after one blank line:

```python
    def make_preview(self, ep: Episode, *, on_progress: Callable[[int], None] | None = None,
                     cancelled: Callable[[], bool] | None = None) -> Preview | None:
        """**Make preview copy** (spec §8.8, S63): the episode's H.264 480p copy with its audio
        track as AAC stereo, made into the cache under the video's quick hash unless it is there
        (`media.preview.preview_copy`). Blocks on ffmpeg for minutes: call it through `blocking`;
        `on_progress` (ms done) runs on that thread, and `cancelled` turning true stops ffmpeg
        and gives None, leaving nothing in the cache. ffmpeg's errors become `PreviewError`,
        naming no path (§6.8). The server issues the copy's media token itself, once it knows
        the episode is still open."""
        from vid2sub.media.preview import NoEncoder, preview_copy
        from vid2sub.media.tools import Cancelled, ToolFailed, ToolMissing
        from vid2sub.web.episode import PreviewError

        try:
            copy = preview_copy(ep.video, key=ep.header.video.quick_sha256,
                                audio_index=ep.audio_index, tools=self.backend.tools,
                                cache=self.backend.cache, timeout=PREVIEW_TIMEOUT,
                                on_progress=on_progress, cancelled=cancelled)
        except Cancelled:
            return None
        except (ToolMissing, NoEncoder) as err:  # their messages name a tool, never a path
            raise PreviewError(str(err)) from None
        except (ToolFailed, OSError, ValueError):
            raise PreviewError(NO_PREVIEW) from None
        return Preview(copy.path, copy.encoder)
```

  In `src/vid2sub/web/views.py`, replace

```python
def episode_view(ep: Episode, *, video_url: str | None, audio_url: str | None,
                 default_formats: Sequence[str] = ("srt",)) -> dict[str, Any]:
    return {
        "id": ep.id,
        "video": {"name": ep.video.name, "duration_ms": ep.header.video.duration_ms,
                  "url": video_url, "audio_url": audio_url, "playable_audio": ep.playable_audio,
                  "container": ep.streams.container, "video_codec": ep.streams.video_codec,
                  "audio_codec": ep.streams.audio_codec},
```

  with

```python
def episode_view(ep: Episode, *, video_url: str | None, audio_url: str | None,
                 preview_url: str | None = None, preview_encoder: str | None = None,
                 default_formats: Sequence[str] = ("srt",)) -> dict[str, Any]:
    """`preview_url` is the preview copy (spec §8.8), once made, and `preview_encoder` the
    ffmpeg encoder that made it (Phase 3 Task 7)."""
    return {
        "id": ep.id,
        "video": {"name": ep.video.name, "duration_ms": ep.header.video.duration_ms,
                  "url": video_url, "audio_url": audio_url, "playable_audio": ep.playable_audio,
                  "container": ep.streams.container, "video_codec": ep.streams.video_codec,
                  "audio_codec": ep.streams.audio_codec, "preview_url": preview_url,
                  "preview_encoder": preview_encoder},
```

  In `src/vid2sub/web/server.py`:

  replace

```python
The settings drawer (§19.2, S35) is `web.settings`'s:
```

  with

```python
**Make preview copy** (spec §8.8, S63; Phase 3 Task 7) is offered while the sound plays alone,
only where the engine makes things (`capabilities.generate`; the button runs ffmpeg). The encode
takes minutes on a long episode, so it runs in a task of its own, through `runtime.blocking`, and
never holds up the tab's other requests: edits and Saves go on meanwhile. Its progress is the
`preview` output, handed back to the loop from the worker thread, and shown only while that
encode runs. Once it is done, the switch to the copy waits its turn in the tab's queue, and its
media token is issued only if the episode is still open; the playback audio's token stays, for a
browser that can't play the copy either. Closing the tab, or opening another episode, stops the
encode, which leaves nothing in the cache. One copy at a time per tab.

The settings drawer (§19.2, S35) is `web.settings`'s:
```

  replace

```python
    AddError,
    Episode,
    OpenError,
    RetranslateError,
```

  with

```python
    AddError,
    Episode,
    OpenError,
    PreviewError,
    RetranslateError,
```

  replace

```python
        self.progress: reactive.Value[dict[str, int] | None] = reactive.value(None)
        self._retranslating: object | None = None  # the running retranslation's token
```

  with

```python
        self.progress: reactive.Value[dict[str, int] | None] = reactive.value(None)
        self.preview: reactive.Value[dict[str, Any] | None] = reactive.value(None)
        self._retranslating: object | None = None  # the running retranslation's token
        self._making: tuple[str, list[bool]] | None = None  # the copy being made: episode, stop
        self._making_task: asyncio.Task | None = None
```

  replace

```python
    def submit(self, kind: str, request: object) -> None:
        if self._ended:
            return
        self._todo.append((kind, as_json(request)))
        if self._worker is None or self._worker.done():
            self._worker = asyncio.create_task(self._drain())

    async def end(self) -> None:
        """The tab closed: drop what waits, and close the episode once the running call ends."""
        self._ended = True
        self._todo.clear()
        if self._worker is None or self._worker.done():
            self._close(self.ep)
```

  with

```python
    def submit(self, kind: str, request: object) -> None:
        self._queue(kind, as_json(request))

    def _queue(self, kind: str, request: object) -> None:
        """Queues the handler `_<kind>`: what the browser sent (`submit`), or the editor's own
        next step (`previewed`), which no input reaches."""
        if self._ended:
            return
        self._todo.append((kind, request))
        if self._worker is None or self._worker.done():
            self._worker = asyncio.create_task(self._drain())

    async def end(self) -> None:
        """The tab closed: drop what waits, stop a preview copy being made, and close the
        episode once the running call ends."""
        self._ended = True
        self._todo.clear()
        self._stop_preview(None)
        if self._worker is None or self._worker.done():
            self._close(self.ep)
```

  replace

```python
    def _named(self, request: object) -> Episode | None:
```

  with

```python
    async def _preview(self, request: object) -> None:
        """**Make preview copy** (spec §8.8, S63): only while the sound plays alone (the playback
        audio is in and no copy is yet), only where the engine makes things, and one at a time.
        The encode runs in a task of its own, so this tab's other requests go on meanwhile."""
        ep = self._named(request)
        if (ep is None or self._making is not None or self.media.audio_url is None
                or self.media.preview_url is not None
                or not self.rt.backend.capabilities().generate):
            return
        making = self._making = (ep.id, [False])
        # Held here: the event loop keeps only a weak reference to a task (asyncio's docs).
        self._making_task = asyncio.create_task(self._make_preview(ep, making))

    async def _make_preview(self, ep: Episode, making: tuple[str, list[bool]]) -> None:
        loop = asyncio.get_running_loop()
        of = ep.header.video.duration_ms
        stop = making[1]

        def on_progress(done: int) -> None:  # on the thread `blocking` runs it on
            asyncio.run_coroutine_threadsafe(self._preview_progress(making, done, of), loop)

        await self._preview_progress(making, 0, of)
        problem = None
        try:
            made = await runtime.blocking(self.rt.make_preview, ep, on_progress=on_progress,
                                          cancelled=lambda: stop[0])
        except PreviewError as err:
            made, problem = None, f"couldn't make a preview copy: {err}"
        except Exception as err:  # noqa: BLE001 - a failed copy must not stop the tab
            log.error("the preview copy failed: %s", type(err).__name__)
            made, problem = None, "couldn't make a preview copy; see the log"
        finally:
            if self._making is making:
                self._making = None
        if self._ended:
            return
        async with reactive.lock():
            self.preview.set(None)
            await reactive.flush()
        if problem and not stop[0]:
            await notice(self.session, "error", problem)
        elif made is not None and not stop[0]:
            self._queue("previewed", (ep.id, made))

    async def _preview_progress(self, making: tuple[str, list[bool]], done: int,
                                of: int) -> None:
        """How far the copy has got: shown while that encode still runs, so a late one never
        shows after it ended."""
        if self._making is not making or self._ended:
            return
        async with reactive.lock():
            self.preview.set({"episode": making[0], "done_ms": done, "of_ms": of})
            await reactive.flush()

    async def _previewed(self, made: tuple[str, runtime.Preview]) -> None:
        """The copy is made: the player gets it by a media token, if the episode is still the
        one open and still plays its sound alone."""
        episode, copy = made
        if self.ep is None or self.ep.id != episode or self.media.audio_url is None:
            return
        try:
            url = f"/media/{self.rt.media.issue(copy.path, owner=episode)}"
        except ValueError as err:  # never the path: issue's messages name none
            await notice(self.session, "error", f"the browser can't be given the copy: {err}")
            return
        self.media = runtime.Media(self.media.video_url, self.media.audio_url, self.media.problem,
                                   url, copy.encoder)
        await self._publish(busy=None)
        await notice(self.session, "info", f"the preview copy is ready ({copy.encoder})")

    def _stop_preview(self, episode: str | None) -> None:
        """Stops the copy being made for `episode` (None: whichever it is)."""
        if self._making is not None and episode in (None, self._making[0]):
            self._making[1][0] = True

    def _named(self, request: object) -> Episode | None:
```

  replace

```python
    def _close(self, ep: Episode | None) -> None:
        if ep is not None:
            self.rt.backend.close(ep.id)
            self.rt.media.revoke_owner(ep.id)
```

  with

```python
    def _close(self, ep: Episode | None) -> None:
        if ep is not None:
            self._stop_preview(ep.id)
            self.rt.backend.close(ep.id)
            self.rt.media.revoke_owner(ep.id)
```

  replace

```python
    @reactive.effect
    @reactive.event(input.edit)
    def _edit() -> None:
```

  with

```python
    @reactive.effect
    @reactive.event(input.preview)
    def _preview() -> None:
        editor.submit("preview", input.preview())

    @reactive.effect
    @reactive.event(input.edit)
    def _edit() -> None:
```

  replace

```python
        return views.episode_view(ep, video_url=media.video_url, audio_url=media.audio_url,
                                  default_formats=rt.session.defaults().formats)
```

  with

```python
        return views.episode_view(ep, video_url=media.video_url, audio_url=media.audio_url,
                                  preview_url=media.preview_url,
                                  preview_encoder=media.preview_encoder,
                                  default_formats=rt.session.defaults().formats)
```

  replace

```python
    @reactive_output
    def progress():
        return editor.progress()
```

  with

```python
    @reactive_output
    def progress():
        return editor.progress()

    @reactive_output
    def preview():
        return editor.preview()
```

- [ ] **Step 9: Run the checks; they pass.** `VID2SUB_REQUIRE_FFMPEG=1 uv run pytest
  tests/test_web_server.py tests/test_views.py tests/test_pages_imports.py -q` first (`66
  passed`), then the guard checks, then `make check`. **Guard checks**, each reverted and
  restored, each with `uv run pytest tests/test_web_server.py -q`: take out both
  `self._stop_preview(…)` lines (in `end` and `_close`) (`FAILED
  …test_closing_the_tab_mid_encode_stops_it_and_a_second_ask_meanwhile_is_ignored`: `where False
  = wait(10)`); in `_preview`, take out `or not self.rt.backend.capabilities().generate` (`FAILED
  …test_a_copy_is_made_only_while_the_sound_plays_alone_and_only_where_jobs_can_run`: `asked`
  holds the episode's id). `make check`. Expected: `1225 passed, 7 skipped, 41 deselected`
  twice, `Test Files  21 passed (21)`, `Tests  100 passed (100)`, `All checks passed!` and
  `no leaks found`.
- [ ] **Step 10: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(web): 🤖 the editor makes a preview copy when asked, without holding up the tab, and the player gets it by a media token

The `preview` input ({"episode", "n"}) asks for **Make preview copy**
(spec §8.8, §20; S63). Editor._preview takes it only while the sound plays
alone (the playback audio is in and no copy is yet), only where the engine
makes things (capabilities.generate, Phase 2 Decision 23: the button runs
ffmpeg), and one copy at a time per tab; anything else is ignored, echoing
nothing. The encode runs in a task of the tab's own, held by the editor
(asyncio keeps only a weak reference to a task), through runtime.blocking,
so the tab's edits and Saves go on meanwhile. Runtime.make_preview runs
media.preview.preview_copy into the cache under the video's quick hash
(§8.9) and turns ffmpeg's errors into the pure web.episode.PreviewError,
naming no path (§6.8); cancelled, it gives None. Its progress is the new
`preview` output ({"episode", "done_ms", "of_ms"}, else null), handed back
to the loop from the worker thread (run_coroutine_threadsafe) and shown
only while that encode runs. Once made, the switch waits its turn in the
tab's queue (`previewed`, a step no input reaches), the copy's media token
is issued only if the episode is still open, and a notice says it is ready
and which encoder made it; the playback audio's token stays, for a browser
that can't play the copy either. Closing the tab or opening another episode
stops the encode, which leaves nothing in the cache. An episode whose copy
is in the cache gets it with the playback audio (Runtime.media_for).
runtime.Media gains preview_url and preview_encoder; episode_view's video
gains the same two fields.

The new tests failed first with: ImportError: cannot import name
'PreviewError' from 'vid2sub.web.episode'. Guard checks, each reverted
and restored: with both _stop_preview calls taken out, closing the tab
leaves the encode running (the closing-tab test fails: the stop never
comes); without the capabilities.generate check, a copy is asked for
where generate is false (the only-while test fails with the episode's id
in `asked`).

Docs read: Python 3.14's asyncio docs (create_task: "Save a reference to
the result of this function, to avoid a task disappearing
mid-execution"; run_coroutine_threadsafe: "Submit a coroutine to the
given event loop. Thread-safe"); the Phase 2 server's own patterns for
both (Tasks 17 and 19).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md Task 7
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/web/episode.py src/vid2sub/web/runtime.py src/vid2sub/web/server.py
  src/vid2sub/web/views.py tests/test_views.py tests/test_web_server.py`, `git commit -F
  .git/COMMIT_MSG`, then `git log -1 --format='%(trailers)'` shows `Plan:`.

#### Round 7c: Make preview copy in the player

- [ ] **Step 11: Write the failing tests.** In `frontend/src/lib/playable.test.ts`, replace
  `import { canPlay, mediaTypes } from "./playable";` with
  `import { canPlay, canPlayPreview, encoderLabel, mediaTypes, previewPercent } from "./playable";`
  and append:

```ts
describe("the preview copy (spec §8.8, S63)", () => {
  it("is offered only to a browser that plays H.264 and AAC in an MP4", () => {
    expect(canPlayPreview(browser("video/mp4", 'video/mp4; codecs="avc1.640028"', 'audio/mp4; codecs="mp4a.40.2"'))).toBe(true);
    expect(canPlayPreview(browser("video/mp4", 'audio/mp4; codecs="mp4a.40.2"'))).toBe(false); // no H.264
    expect(canPlayPreview(browser("video/mp4", 'video/mp4; codecs="avc1.640028"'))).toBe(false); // no AAC
  });

  it("counts how far it has got in whole percent, never past 100", () => {
    expect(previewPercent({ done_ms: 0, of_ms: 2000 })).toBe(0);
    expect(previewPercent({ done_ms: 999, of_ms: 2000 })).toBe(49);
    expect(previewPercent({ done_ms: 2100, of_ms: 2000 })).toBe(100);
    expect(previewPercent({ done_ms: 500, of_ms: 0 })).toBe(0);
  });

  it("names the encoder that made it in words", () => {
    expect(encoderLabel("h264_videotoolbox")).toBe("VideoToolbox");
    expect(encoderLabel("h264_nvenc")).toBe("NVENC");
    expect(encoderLabel("h264_qsv")).toBe("Quick Sync");
    expect(encoderLabel("libx264")).toBe("libx264");
    expect(encoderLabel("unknown")).toBe("an unknown encoder");
    expect(encoderLabel(null)).toBe("an unknown encoder");
  });
});
```

  `frontend/src/components/Player.test.ts`:

```ts
import { createElement, createRef } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { EpisodeView, PreviewProgress } from "@/types";

import { Player } from "./Player";

const SOUND_ONLY: EpisodeView["video"] = {
  name: "Clip.mp4", duration_ms: 2000, url: null, audio_url: "/media/a", playable_audio: true,
  container: "mov,mp4,m4a,3gp,3g2,mj2", video_codec: "mpeg4", audio_codec: "opus",
  preview_url: null, preview_encoder: null,
};

/** The browser's answer to canPlayType: "probably" for everything, or "" for H.264. */
function browser(h264: boolean) {
  vi.spyOn(HTMLMediaElement.prototype, "canPlayType").mockImplementation(
    (type: string) => (!h264 && type.includes("avc1") ? "" : "probably") as CanPlayTypeResult);
}

function player(video: EpisodeView["video"], { generate = true, preview = null as PreviewProgress } = {}) {
  return renderToStaticMarkup(createElement(Player, {
    video, mediaRef: createRef<HTMLVideoElement | HTMLAudioElement>(), lines: [], busy: null,
    generate, preview, onTime: () => undefined, onCantPlay: () => undefined, onMakePreview: () => undefined,
  }));
}

afterEach(() => vi.restoreAllMocks());

describe("Make preview copy in the player (spec §8.8, §20; S63)", () => {
  it("is offered while the sound plays alone, where the engine makes things and the browser plays H.264", () => {
    browser(true);
    const html = player(SOUND_ONLY);
    expect(html).toContain('data-testid="make-preview"');
    expect(html).toContain("Make preview copy");
  });

  it("isn't offered without generate, to a browser that can't play H.264, or with no picture to copy", () => {
    browser(true);
    expect(player(SOUND_ONLY, { generate: false })).not.toContain("make-preview");
    expect(player({ ...SOUND_ONLY, video_codec: null })).not.toContain("make-preview");
    vi.restoreAllMocks();
    browser(false);
    expect(player(SOUND_ONLY)).not.toContain("make-preview");
  });

  it("shows how far the copy has got while it is made", () => {
    browser(true);
    const html = player(SOUND_ONLY, { preview: { episode: "e1", done_ms: 500, of_ms: 2000 } });
    expect(html).toContain('data-testid="preview-progress"');
    expect(html).toContain("Making a preview copy… 25%");
    expect(html).not.toContain("make-preview");
  });

  it("plays the copy once it is made, naming the encoder that made it", () => {
    browser(true);
    const html = player({ ...SOUND_ONLY, preview_url: "/media/p", preview_encoder: "h264_videotoolbox" });
    expect(html).toMatch(/<video[^>]*src="\/media\/p"/);
    expect(html).toContain("Preview copy, made with VideoToolbox");
    expect(html).not.toContain("make-preview");
  });

  it("keeps the sound for a browser that can't play the copy either", () => {
    browser(false);
    const html = player({ ...SOUND_ONLY, preview_url: "/media/p", preview_encoder: "libx264" });
    expect(html).toMatch(/<audio[^>]*src="\/media\/a"/);
  });
});
```

  and `tests/e2e/test_preview.py`:

```python
"""Make preview copy in Chromium, against `vid2sub serve --demo` (spec §8.8, §20; S63): a video the
browser can't decode plays its sound alone, the person asks for a preview copy, and the copy
plays with its picture, by a media token, from the demo's own cache. The demo offers the button
too: its own clip plays, so only an episode made in its copy needs it, and the copy is written in
the demo's folder (Phase 3 Task 7). Run with `make e2e`."""

import re
from pathlib import Path

import pytest
from episodes import make_episode
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e

H264 = 'video/mp4; codecs="avc1.640028"'
NO_H264 = """
const ask = HTMLMediaElement.prototype.canPlayType;
HTMLMediaElement.prototype.canPlayType = function (type) {
  return type.includes("avc1") ? "" : ask.call(this, type);
};
"""


def demo_copy(server) -> Path:
    return next(server.tmp.glob("vid2sub-demo-*/demo"))


def sound_only(page, server):
    """Opens an MP4 of MPEG-4 Part 2, which Chromium can't decode, with Opus, which it plays."""
    video = make_episode(demo_copy(server) / "mpeg4", name="Clip.mp4", audio_codec="libopus")
    page.get_by_test_id("open-path").fill(str(video))
    page.get_by_test_id("open-button").click()
    expect(page.get_by_test_id("audio-only")).to_have_text(
        "Playing the sound only: this browser can't play the video itself.")


def test_make_preview_copy_plays_the_episode_with_its_picture(page, server, watch):
    if page.evaluate(f"() => document.createElement('video').canPlayType('{H264}')") == "":
        pytest.skip("this Chromium plays no H.264, so it is offered no preview copy")
    sound_only(page, server)
    page.get_by_test_id("make-preview").click()
    expect(page.get_by_test_id("preview-note")).to_have_text(
        re.compile(r"^Preview copy, made with (VideoToolbox|NVENC|Quick Sync|libx264)$"),
        timeout=60_000)
    media = page.get_by_test_id("media")
    assert media.evaluate("m => m.tagName") == "VIDEO"
    expect(media).to_have_attribute("src", re.compile(r"^/media/[A-Za-z0-9_-]{43}$"))
    media.evaluate("m => { m.muted = true; return m.play(); }")
    page.wait_for_function(
        "() => document.querySelector('[data-testid=media]').currentTime > 0.3")
    assert media.evaluate("m => m.videoWidth") == 160  # the picture, never scaled up
    expect(page.get_by_test_id("make-preview")).to_have_count(0)
    (copy,) = (demo_copy(server).parent / "cache").glob("*/preview-a0.mp4")
    assert copy.stat().st_size > 0
    expect(page.get_by_role("status").get_by_text("the preview copy is ready")).to_be_visible()


def test_a_browser_that_plays_no_h264_is_offered_no_copy(page, server):
    page.add_init_script(script=NO_H264)
    page.reload()
    sound_only(page, server)
    expect(page.get_by_test_id("media")).to_have_attribute("src", re.compile("^/media/"))
    expect(page.get_by_test_id("make-preview")).to_have_count(0)
```

- [ ] **Step 12: Run them; watch them fail.** `cd frontend && npx vitest run
  src/lib/playable.test.ts src/components/Player.test.ts`. Expected: `→ canPlayPreview is not a
  function` (and `previewPercent`, `encoderLabel`), `AssertionError: expected '<div
  class="relative flex min-h-48 fl…' to contain 'data-testid="make-preview"'`, and
  `Tests  6 failed | 9 passed (15)`.
- [ ] **Step 13: Write the code.** Append to `frontend/src/lib/playable.ts`:

```ts
// The preview copy (spec §8.8, S63; Phase 3 Task 7): H.264 and AAC in an MP4, as ffprobe names
// them, so it is asked about as the video is. A browser that can't play it is offered no copy.
const PREVIEW: Video = { name: "preview.mp4", container: "mov,mp4,m4a,3gp,3g2,mj2", video_codec: "h264", audio_codec: "aac" };

/** Whether this browser would play a preview copy. */
export function canPlayPreview(ask: Ask): boolean {
  return canPlay(ask, PREVIEW);
}

/** How far a copy being made has got, in whole percent of the episode (0 to 100). */
export function previewPercent(p: { done_ms: number; of_ms: number }): number {
  return p.of_ms > 0 ? Math.min(100, Math.floor((p.done_ms * 100) / p.of_ms)) : 0;
}

const ENCODERS: Record<string, string> = {
  h264_videotoolbox: "VideoToolbox",
  h264_nvenc: "NVENC",
  h264_qsv: "Quick Sync",
  libx264: "libx264",
};

/** The ffmpeg encoder that made a copy, in words. */
export function encoderLabel(name: string | null): string {
  return (name && ENCODERS[name]) || "an unknown encoder";
}
```

  In `frontend/src/types.ts`, replace

```ts
/** The `episode` output: views.episode_view. `video.url` plays the video; `audio_url` the
 * playback audio when the browser can't play the video's audio (Decision 2), or the video itself
 * (spec §8.2: asked with canPlayType about ffprobe's container and codec names). No path, ever. */
```

  with

```ts
/** The `episode` output: views.episode_view. `video.url` plays the video; `audio_url` the
 * playback audio when the browser can't play the video's audio (Decision 2), or the video itself
 * (spec §8.2: asked with canPlayType about ffprobe's container and codec names); `preview_url`
 * the preview copy once made (§8.8), with the ffmpeg encoder that made it. No path, ever. */
```

  and in it replace

```ts
    video_codec: string | null;
    audio_codec: string;
  };
  source: string;
```

  with

```ts
    video_codec: string | null;
    audio_codec: string;
    preview_url: string | null;
    preview_encoder: string | null;
  };
  source: string;
```

  and below `export type Progress = { done: number; of: number } | null;` add:

```ts

/** The `preview` output: how far the preview copy being made has got, in ms of the episode's
 * `of_ms` (spec §8.8), or null when none is being made. */
export type PreviewProgress = { episode: string; done_ms: number; of_ms: number } | null;
```

  Replace `frontend/src/components/Player.tsx` with:

```tsx
import { type RefObject, useEffect, useRef, useState } from "react";

import { canPlay, canPlayPreview, encoderLabel, previewPercent } from "@/lib/playable";
import type { Busy, EpisodeView, PreviewProgress } from "@/types";

import { CaptionOverlay } from "./CaptionOverlay";

/** The player (spec §20): the video by its media token when the browser can play it, else the
 * playback audio with no picture (§8.8; Decision 2), with the caption overlay over it. Whether it
 * can is the browser's to say (§8.2): canPlayType is asked about the probe's container and codecs
 * before the video loads, and a MEDIA_ERR_DECODE or MEDIA_ERR_SRC_NOT_SUPPORTED, or a picture
 * with no size once its metadata is in, says so too; then `onCantPlay` asks the server for the
 * playback audio, once. While the sound plays alone, **Make preview copy** (S63; Phase 3 Task 7)
 * asks for an H.264 copy with the picture, offered only where the engine makes things
 * (`generate`), the video has a picture and this browser plays H.264 and AAC; `preview` says how
 * far it has got. Once made, the copy plays from where the sound was, and if the browser fails on
 * it after all, the sound plays again. While it plays it reports the time every frame, so the cue
 * list, the spoken word and the captions keep up; paused, it reports each seek. */
export function Player({ video, mediaRef, lines, busy, generate, preview, onTime, onCantPlay, onMakePreview }: {
  video: EpisodeView["video"];
  mediaRef: RefObject<HTMLVideoElement | HTMLAudioElement | null>;
  lines: string[];
  busy: Busy;
  generate: boolean;
  preview: PreviewProgress;
  onTime: (ms: number) => void;
  onCantPlay: () => void;
  onMakePreview: () => void;
}) {
  const report = useRef(onTime);
  report.current = onTime;
  const at = useRef(0); // seconds: where playback is, so the copy can start from there
  const [failed, setFailed] = useState(false);
  const [copyFailed, setCopyFailed] = useState(false);
  const asked = useRef(false);
  const cantPlay = () => {
    if (asked.current) return;
    asked.current = true;
    onCantPlay();
  };
  const ask = (t: string) => document.createElement("video").canPlayType(t);
  // Asked once per video URL, before anything loads.
  const [plays] = useState(() => !video.url || canPlay(ask, video));
  const [copyPlays] = useState(() => canPlayPreview(ask));
  const showVideo = video.url !== null && plays;
  const showCopy = !showVideo && video.preview_url !== null && copyPlays && !copyFailed;
  const src = showVideo ? video.url : showCopy ? video.preview_url : video.audio_url;
  const offer = generate && copyPlays && video.video_codec !== null && video.preview_url === null;

  useEffect(() => {
    if (video.url && !plays) cantPlay();
  }, [video.url, plays]);

  useEffect(() => {
    const media = mediaRef.current;
    if (!media) return;
    let frame = 0;
    const now = () => {
      at.current = media.currentTime;
      report.current(media.currentTime * 1000);
    };
    const tick = () => {
      now();
      if (!media.paused && !media.ended) frame = requestAnimationFrame(tick);
    };
    const play = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(tick);
    };
    const events = ["seeked", "timeupdate", "loadedmetadata", "pause"] as const;
    media.addEventListener("play", play);
    for (const e of events) media.addEventListener(e, now);
    return () => {
      cancelAnimationFrame(frame);
      media.removeEventListener("play", play);
      for (const e of events) media.removeEventListener(e, now);
    };
  }, [mediaRef, src]);

  const onVideoError = (e: { currentTarget: HTMLVideoElement }) => {
    const code = e.currentTarget.error?.code;
    if (code === MediaError.MEDIA_ERR_DECODE || code === MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED) cantPlay();
    else setFailed(true);
  };
  const onVideoMetadata = (e: { currentTarget: HTMLVideoElement }) => {
    // A picture the browser can't decode can still leave the sound playing, with no error.
    if (video.video_codec && e.currentTarget.videoWidth === 0) cantPlay();
  };
  const onCopyMetadata = (e: { currentTarget: HTMLVideoElement }) => {
    if (e.currentTarget.videoWidth === 0) setCopyFailed(true);
    else if (at.current > 0) e.currentTarget.currentTime = at.current; // where the sound was
  };

  const box = "relative flex min-h-48 flex-1 items-center justify-center overflow-hidden rounded-lg bg-black";
  if (!src) {
    const making = busy === "playback" || (video.url !== null && !plays);
    return (
      <div className={box} data-testid="player">
        <p className="p-4 text-center text-white/80" data-testid="audio-only">
          {making ? "This browser can't play the video itself, so vid2sub is making a copy of its sound…" : "Nothing to play."}
        </p>
      </div>
    );
  }
  return (
    <div className={box} data-testid="player">
      {showVideo || showCopy ? (
        <video
          key={src}
          ref={mediaRef as RefObject<HTMLVideoElement>}
          src={src ?? undefined}
          controls
          playsInline
          preload="metadata"
          className="max-h-full w-full"
          data-testid="media"
          onError={showCopy ? () => setCopyFailed(true) : onVideoError}
          onLoadedMetadata={showCopy ? onCopyMetadata : onVideoMetadata}
        />
      ) : (
        <div className="flex w-full flex-col items-center gap-3 p-4">
          <p className="text-center text-sm text-white/80" data-testid="audio-only">
            {video.playable_audio
              ? "Playing the sound only: this browser can't play the video itself."
              : "Playing the sound only: the browser can't play this video's own audio track."}
          </p>
          <audio ref={mediaRef as RefObject<HTMLAudioElement>} src={video.audio_url ?? undefined} controls preload="metadata" className="w-full" data-testid="media" onError={() => setFailed(true)} />
          {offer && (preview ? (
            <div className="flex w-full flex-col items-center gap-1 text-sm text-white/80">
              <progress className="w-full" value={preview.done_ms} max={Math.max(preview.of_ms, 1)} aria-label="Making a preview copy" data-testid="preview-progress" />
              <span>{`Making a preview copy… ${previewPercent(preview)}%`}</span>
            </div>
          ) : (
            <button type="button" onClick={onMakePreview} data-testid="make-preview"
              className="rounded-md bg-primary px-3 py-1 text-sm font-bold text-primary-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring">
              Make preview copy
            </button>
          ))}
        </div>
      )}
      {showCopy && (
        <p className="absolute top-2 left-2 rounded bg-black/60 px-2 py-0.5 text-xs text-white/80" data-testid="preview-note">
          {`Preview copy, made with ${encoderLabel(video.preview_encoder)}`}
        </p>
      )}
      {failed && (
        <p role="alert" className="absolute inset-x-0 top-0 bg-card px-3 py-2 text-sm text-destructive" data-testid="media-error">
          The browser can't play this file.
        </p>
      )}
      <CaptionOverlay lines={lines} />
    </div>
  );
}
```

  In `frontend/src/components/Editor.tsx`, make six replacements:

  replace

```tsx
import type { Busy, EditOp, EpisodeView, Progress } from "@/types";
```

  with

```tsx
import type { Busy, EditOp, EpisodeView, PreviewProgress, Progress } from "@/types";
```

  replace

```tsx
/** The editor (spec §20): the path box, then, once an episode is open, the player on the left
 * and the cue list on the right, with the edit bar, Retranslate (where the engine has models:
 * `generate`) and find and replace. */
export function Editor({ episode, busy, progress, pathInput, generate, onOpen, onCantPlay, requests, saving }: {
  episode: EpisodeView | null;
  busy: Busy;
  progress: Progress;
  pathInput: boolean;
  generate: boolean;
  onOpen: (path: string) => void;
  onCantPlay: () => void;
  requests: Requests;
  saving: Saving;
}) {
```

  with

```tsx
/** The editor (spec §20): the path box, then, once an episode is open, the player on the left
 * and the cue list on the right, with the edit bar, Retranslate and Make preview copy (where the
 * engine makes things: `generate`) and find and replace. */
export function Editor({ episode, busy, progress, preview, pathInput, generate, onOpen, onCantPlay, onMakePreview, requests, saving }: {
  episode: EpisodeView | null;
  busy: Busy;
  progress: Progress;
  preview: PreviewProgress;
  pathInput: boolean;
  generate: boolean;
  onOpen: (path: string) => void;
  onCantPlay: () => void;
  onMakePreview: () => void;
  requests: Requests;
  saving: Saving;
}) {
```

  replace

```tsx
        <EpisodeEditor key={episode.id} episode={episode} busy={busy} progress={progress} generate={generate} requests={requests} saving={saving} onCantPlay={onCantPlay} />
```

  with

```tsx
        <EpisodeEditor key={episode.id} episode={episode} busy={busy} progress={progress} generate={generate} requests={requests} saving={saving} onCantPlay={onCantPlay}
          preview={preview?.episode === episode.id ? preview : null} onMakePreview={onMakePreview} />
```

  replace

```tsx
function EpisodeEditor({ episode, busy, progress, generate, requests, saving, onCantPlay }: {
  episode: EpisodeView;
  busy: Busy;
  progress: Progress;
  generate: boolean;
  requests: Requests;
  saving: Saving;
  onCantPlay: () => void;
}) {
```

  with

```tsx
function EpisodeEditor({ episode, busy, progress, generate, requests, saving, onCantPlay, preview, onMakePreview }: {
  episode: EpisodeView;
  busy: Busy;
  progress: Progress;
  generate: boolean;
  requests: Requests;
  saving: Saving;
  onCantPlay: () => void;
  preview: PreviewProgress;
  onMakePreview: () => void;
}) {
```

  replace

```tsx
  const changeRate = (value: number) => {
    setRate(value);
    if (media.current) media.current.playbackRate = value;
  };
```

  with

```tsx
  const changeRate = (value: number) => {
    setRate(value);
    if (media.current) media.current.playbackRate = value;
  };
  // The preview copy plays in a new element (spec §8.8), which starts at 1×: keep the rate chosen.
  useEffect(() => {
    if (media.current) media.current.playbackRate = rate;
  }, [episode.video.preview_url]);
```

  replace

```tsx
          <Player video={episode.video} mediaRef={media} lines={lines} busy={busy} onTime={onTime} onCantPlay={onCantPlay} />
```

  with

```tsx
          <Player video={episode.video} mediaRef={media} lines={lines} busy={busy} generate={generate} preview={preview}
            onTime={onTime} onCantPlay={onCantPlay} onMakePreview={onMakePreview} />
```

  In `frontend/src/App.tsx`, make five replacements:

  replace

```tsx
import type { AddResultMessage, BrowseResult, Busy, Capabilities, EditOp, EndpointTestResult, EpisodeView, JobsView, Progress, RetranslateResultMessage, QueueState, ReviewOutput, ReviewStartedMessage, SaveResultMessage, SettingsView, Status } from "@/types";
```

  with

```tsx
import type { AddResultMessage, BrowseResult, Busy, Capabilities, EditOp, EndpointTestResult, EpisodeView, JobsView, PreviewProgress, Progress, RetranslateResultMessage, QueueState, ReviewOutput, ReviewStartedMessage, SaveResultMessage, SettingsView, Status } from "@/types";
```

  replace

```tsx
  const progress = useShinyOutputValue<Progress>("progress");
```

  with

```tsx
  const progress = useShinyOutputValue<Progress>("progress");
  const preview = useShinyOutputValue<PreviewProgress>("preview");
```

  replace

```tsx
  const setPlayback = useSetShinyInput<{ episode: string; n: number } | null>("playback", null, { priority: "event", debounceMs: 0 });
```

  with

```tsx
  const setPlayback = useSetShinyInput<{ episode: string; n: number } | null>("playback", null, { priority: "event", debounceMs: 0 });
  const setPreview = useSetShinyInput<{ episode: string; n: number } | null>("preview", null, { priority: "event", debounceMs: 0 });
```

  replace

```tsx
          progress={progress ?? null}
```

  with

```tsx
          progress={progress ?? null}
          preview={preview ?? null}
```

  replace

```tsx
          onCantPlay={() => episode && setPlayback({ episode: episode.id, n: ++sent.current })}
```

  with

```tsx
          onCantPlay={() => episode && setPlayback({ episode: episode.id, n: ++sent.current })}
          onMakePreview={() => episode && setPreview({ episode: episode.id, n: ++sent.current })}
```

  In `README.md`, replace

```bash
vid2sub cache clear                                   # empty the cache of playback audio
```

  with

```bash
vid2sub cache clear                                   # empty the cache of playback audio and preview copies
```

  and replace

```markdown
the video, the editor plays the playback audio instead, with no picture: an AAC copy of the
sound, made on demand and kept in vid2sub's cache (`[defaults] cache_max_gb` caps it; `vid2sub
cache clear` empties it).
```

  with

```markdown
the video, the editor plays the playback audio instead, with no picture: an AAC copy of the
sound, made on demand and kept in vid2sub's cache (`[defaults] cache_max_gb` caps it; `vid2sub
cache clear` empties it). **Make preview copy**, under it, makes a copy with the picture too
(H.264 at 480p with AAC, through VideoToolbox, NVENC or Quick Sync where the machine has one,
else libx264), which plays from where the sound was; it takes a few minutes for a long episode,
goes in the same cache, and is reused the next time the episode is opened.
```

  In `docs/architecture.md`, replace

```text
      media["/media/{token}<br/>video or playback audio,<br/>never a path (MediaTokens)"]
```

  with

```text
      media["/media/{token}<br/>video, playback audio or preview copy,<br/>never a path (MediaTokens)"]
```

- [ ] **Step 14: Run the checks; they pass.** `cd frontend && npm run typecheck && npx vitest
  run` first (`Test Files  22 passed (22)`, `Tests  108 passed (108)`), then the guard check, then
  `make build`, `make check` and `make e2e`. **Guard check**, reverted and restored: in
  `Player.tsx`, replace `const offer = generate && copyPlays` with `const offer = copyPlays`
  (`npx vitest run src/components/Player.test.ts`: `× … isn't offered without generate, to a
  browser that can't play H.264, or with no picture to copy`, `Tests  1 failed | 4 passed (5)`).
  `make check`. Expected: `1225 passed, 7 skipped, 43 deselected` twice,
  `Test Files  22 passed (22)`, `Tests  108 passed (108)`, `All checks passed!` and
  `no leaks found`. `make e2e`.
  Expected: `38 passed`; in a Chromium with no H.264 the picture test skips (`this Chromium plays
  no H.264, so it is offered no preview copy`).
- [ ] **Step 15: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(frontend): 🤖 Make preview copy plays the episode with its picture where the browser can't play the video

The player (spec §8.8, §20; S63), while it plays the sound alone, offers
**Make preview copy**: only where the engine makes things (`generate`), the
video has a picture, and this browser plays H.264 and AAC in an MP4
(playable.canPlayPreview asks canPlayType about the copy as the video is
asked about, Phase 2 Decision 15). Pressed, it sends the `preview` input;
while the copy is made, a <progress> and "Making a preview copy… N%"
(playable.previewPercent) replace it, from the `preview` output, which App
subscribes like every output (shinyreact 0.1.0). Once the episode has
`preview_url`, the copy plays in a <video>, from where the sound was, with
"Preview copy, made with <encoder>" (playable.encoderLabel: VideoToolbox,
NVENC, Quick Sync, libx264); if the browser fails on it after all (an
error, or a picture with no size), the sound plays again. The editor keeps
the chosen playback rate on the new element. The demo offers the button
too: its own VP9 clip plays, so only an episode made in its copy needs it,
and the copy is written in the demo's own cache, inside its folder.

The README says what Make preview copy does and that `vid2sub cache clear`
empties preview copies too; docs/architecture.md's /media/ node serves the
preview copy as well.

The new tests failed first with: TypeError: canPlayPreview is not a
function (and previewPercent, encoderLabel), and AssertionError: expected
'<div class="relative flex min-h-48 fl…' to contain
'data-testid="make-preview"'. Guard check, reverted and restored: with
`generate &&` taken out of the offer, the Vitest test that a Pages editor
is offered no button fails. In Playwright 1.64's Chromium on macOS the
copy (made with VideoToolbox here) plays with its 160-pixel picture; a
Chromium that plays no H.264 is offered no copy (canPlayType stubbed),
and the picture test skips in one.

Docs read: MDN's HTMLMediaElement.canPlayType ("" means "The media
cannot be played on the current device") and HTMLVideoElement.videoWidth
(0 while readyState is HAVE_NOTHING); RFC 6381's codecs parameter
(avc1.640028, mp4a.40.2), as Phase 2's playable.ts names them.

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md Task 7
Co-Authored-By: <the model's own line>
```

  `git add frontend/src/App.tsx frontend/src/components/Editor.tsx
  frontend/src/components/Player.tsx frontend/src/components/Player.test.ts
  frontend/src/lib/playable.ts frontend/src/lib/playable.test.ts frontend/src/types.ts
  tests/e2e/test_preview.py README.md docs/architecture.md`, `git commit -F .git/COMMIT_MSG`,
  then `git log -1 --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 16: Review, look forward, close.** The Tier 2 review from `$(cat .git/TASK_BASE)`
  (`AGENTS.md`, *Reviews*). Worth the reviewers' time: that a tab closed, or another episode
  opened, mid-encode stops ffmpeg and leaves nothing in the cache; that no error, notice or log
  line names a path (§6.8); that the copy is served only by a token issued while its episode is
  open (§6.3, §6.5); that the server still imports only what Pages has and starts no thread
  itself (`tests/test_pages_imports.py`); that the demo still writes only inside its folder. The
  forward review over Task 11 (the README's editor section names Make preview copy; this task
  wrote its sentence), Task 12 (S63 isn't among its rows) and Phase 4's Tasks 1–4 (the browser
  backend's view carries `preview_url` and `preview_encoder` as null; `generate` is false there,
  so no button). The docs this task made untrue: `Player.tsx`'s comment (rewritten here), the
  README's cache line and `docs/architecture.md`'s `/media/` node (both above). Two tabs asking
  for one episode's copy at once is already a planning row on the Phase-end list. Then the close,
  its own commit, holding this plan with this task's boxes ticked and **Now** set to `Task 8: The
  Models page, open.`, and the spec's S63 row with "Phase and task" set to `Phase 3, Task 7`, its
  Proof to `` `tests/test_preview.py`; Playwright (`tests/e2e/test_preview.py`) ``, and its status
  to `built`. The message, in `.git/CLOSE_MSG`:

```text
docs(plan): 🤖 close Task 7: The preview copy

Drift: none
Rulings: none
Phase-end: none
Forward: none
Tier: 2
Rounds: none
Findings: none

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md Task 7
Co-Authored-By: <the model's own line>
```

  `git add docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md
  docs/superpowers/specs/2026-10-14-vid2sub-design.md`, `git commit -F .git/CLOSE_MSG`.

***

### Task 8: The Models page

**Tier:** 2 · **Scenarios:** S44

Spec §11.1, §19.2 and S44: the Models page shows the catalog, each model marked usable on this
machine now or why not; catalog models with no configured entry are shown greyed with "add it to
vid2sub.toml".

**Why it is built this way** (read 2026-10-24):
- **One list for the page and the CLI.** `vid2sub models` (M1) already reported these facts: each
  configured model usable now or why not, then the catalog's other entries. `review.models` now
  holds them, on Task 3's `model_choices`, so the Models page, Review's pickers and the CLI say
  the same thing; the CLI prints from it, grouped by task. §11.1's words for an entry no model
  points at, "add it to vid2sub.toml", replace M1's "not in vid2sub.toml". `ModelChoice` stays as
  Task 3 made it (Task 3's tests compare it whole), so the CLI takes each model's catalog id from
  its candidate.
- **The candidates** are the job context's own where it has them: the demo's canned models, under
  the catalog entries they stand in for, so the demo's page names Whisper large-v3-turbo and
  Gemma 4 (Decision 22). Otherwise `detect.candidates` checks each configured model now: each
  local server is asked for its model list, a cloud one is only checked for its key, and an
  in-process engine for its extra. Task 9's `faster-whisper` candidate comes the same way,
  `in-process`, and without the extra unavailable with "install vid2sub[whisper]
  (vid2sub[nvidia] for an NVIDIA GPU)"; nothing here changes for it, and this task's Vitest
  names that reason as data.
- **Asked for, not polled.** A check asks each local server, so the page asks when it opens and
  on **Check again** (`models_check`), and the server runs the check as the tab's extended task
  through `runtime.blocking`, off the event loop (shiny's `ExtendedTask` queues a call made while
  one runs, so the server drops an ask while a check runs). The page keeps the last lists while
  the next check runs. A check that fails says "couldn't check the models; see the log", never
  the error's own text.
- **Only where the engine makes things** (`capabilities.generate`, Phase 2 Decision 23), like
  Add, Review and Jobs: the Pages editor has no Models page, and its `models` output is null.
- **Nothing on it names a path, a token or a key** (§6.8): models go by their names in
  vid2sub.toml and the catalog's titles; a reason names at most a key's environment variable,
  as the top bar does. Usable or not is said in words, not by colour alone (§19.3).

**Files:**
- Modify: `src/vid2sub/review.py` (`NOT_CONFIGURED`, `CatalogModel`, `Models`, `models`),
  `src/vid2sub/commands/models.py` (prints from `review.models`), `src/vid2sub/web/runtime.py`
  (`Runtime.models`), `src/vid2sub/web/views.py` (`models_view`), `src/vid2sub/web/server.py`
  (the `models_check` input and the `models` output), `frontend/src/types.ts`,
  `frontend/src/App.tsx`
- Create: `tests/test_models.py`, `tests/test_web_models.py`, `frontend/src/lib/models.ts`,
  `frontend/src/lib/models.test.ts`, `frontend/src/components/ModelsPage.tsx`,
  `frontend/src/components/ModelsPage.test.ts`, `tests/e2e/test_models.py`
- Modify at the close: this plan; the spec (S44)

**Interfaces:**
- Consumes: Task 3's `review.model_choices(config, candidates, task)` and `ModelChoice`;
  `catalog.CATALOG` (`title`, `task`, `good_for`, `install`, `cloud`) and `Candidate`;
  `detect.candidates(config, keys)`; `RunContext.candidates` (the demo's `CANNED_MODELS`,
  Decision 22); `runtime.blocking`; `Capabilities.generate`; the frontend's `choiceLabel` and
  `ModelChoice` (Task 4); App.tsx's `sent` and `pace`; `tests/fakes.FakeServer`,
  `test_web_review.client_for`, `test_web_settings.Browser`; the e2e `page`, `server`, `launch`
  and `open_page` fixtures. Task 9's `faster-whisper` candidate, once Task 9 adds it: `in-process`,
  and without the extra unavailable with "install vid2sub[whisper] (vid2sub[nvidia] for an NVIDIA
  GPU)".
- Produces:
  - `vid2sub.review`: `NOT_CONFIGURED = "add it to vid2sub.toml"`;
    `CatalogModel(id, title, task, good_for, install, cloud, reason=NOT_CONFIGURED)` (frozen);
    `Models(transcribers: tuple[ModelChoice, ...], translators: tuple[ModelChoice, ...],
    unconfigured: tuple[CatalogModel, ...])` (frozen); `models(config, candidates) -> Models`.
  - `vid2sub models` prints from `review.models`: configured models grouped by task, then the
    catalog's other entries with reason "add it to vid2sub.toml"; its JSON events keep their
    fields (`name`, `catalog`, `task`, `available`, `reason`, `cloud`).
  - `web.runtime.Runtime.models() -> Models` (blocks; through `blocking`).
  - `web.views.models_view(found: Models | None, *, checking: bool, error: str | None = None)
    -> dict`: `{checking, error, transcribers, translators, unconfigured}`, each configured model
    as Review's pickers have it, each unconfigured entry `{id, title, task, good_for, install,
    cloud, reason}`.
  - `web.server`: the `models_check` input (`{n}`), the `models` output (null until asked, and
    in Pages), `MODELS_FAILED = "couldn't check the models; see the log"`.
  - Frontend: `types.ts`'s `CatalogModel` and `ModelsView`; `lib/models.ts`'s `why`, `Section`,
    `sections` and `summary`; `components/ModelsPage.tsx`'s `ModelsPage({ models, onCheck })`;
    App's `models` screen (`nav-models`), which sends `models_check` each time it opens. Test
    ids: `models-page`, `models-status`, `models-check`, `models-error`, `models-transcribe`,
    `models-translate`, `model` (with `data-usable`), `model-label`, `model-why`,
    `catalog-model`, `catalog-title`, `catalog-why`.

- [ ] **Step 0: Record the base:** `git rev-parse HEAD > .git/TASK_BASE`.
- [ ] **Step 1: Write the failing tests,** `tests/test_models.py`:

```python
"""The models as the Models page and `vid2sub models` both list them (spec §11.1, §18.1, §19.2;
S44): every configured model by task, in vid2sub.toml's order, with whether it can run now and
why not, then each catalog entry no model points at, greyed with "add it to vid2sub.toml". One
function, `review.models`, gives both, so the page and the CLI can't disagree."""

import json

import pytest

from vid2sub import detect as detecting
from vid2sub import review
from vid2sub.catalog import CATALOG, Candidate
from vid2sub.cli import main
from vid2sub.config import Config

CONFIG = Config.model_validate({
    "endpoints": {"spark": {"base_url": "http://127.0.0.1:9/v1"},
                  "openai": {"base_url": "https://api.openai.com/v1",
                             "key_env": "OPENAI_TEST_KEY"}},
    "models": {
        "spark-turbo": {"catalog": "whisper-large-v3-turbo", "endpoint": "spark",
                        "model": "turbo", "parser": "whisper.cpp", "local": True},
        "mac-qwen": {"catalog": "qwen3-asr-1.7b", "engine": "mlx-qwen3-asr"},
        "openai-whisper": {"catalog": "openai-whisper-1", "endpoint": "openai",
                           "model": "whisper-1", "parser": "openai"},
        "spark-gemma": {"catalog": "gemma-4-26b-a4b", "endpoint": "spark", "model": "gemma",
                        "task": "translate", "local": True},
        "lan-llm": {"endpoint": "spark", "model": "llama", "task": "translate", "local": True},
    },
})
DOWN = "couldn't connect to the server (is `make tunnel` running?)"
CANDIDATES = [
    Candidate("spark-turbo", "whisper-large-v3-turbo", "endpoint", False, DOWN, unreachable=True),
    Candidate("mac-qwen", "qwen3-asr-1.7b", "in-process", False,
              "install vid2sub[mac] on an Apple Silicon Mac"),
    Candidate("openai-whisper", "openai-whisper-1", "endpoint", False,
              "OPENAI_TEST_KEY isn't set", cloud=True),
    Candidate("spark-gemma", "gemma-4-26b-a4b", "endpoint", True),
    Candidate("lan-llm", None, "endpoint", True),
]
UNCONFIGURED = ["qwen3-asr-0.6b", "whisper-large-v3", "qwen3.8-27b", "local-llm", "openai-gpt"]


def test_each_configured_model_is_listed_by_task_with_whether_it_can_run_now_and_why_not():
    found = review.models(CONFIG, CANDIDATES)
    assert [(m.name, m.title, m.available, m.reason, m.cloud) for m in found.transcribers] == [
        ("spark-turbo", "Whisper large-v3-turbo", False, DOWN, False),
        ("mac-qwen", "Qwen3-ASR 1.7B + ForcedAligner 0.6B", False,
         "install vid2sub[mac] on an Apple Silicon Mac", False),
        ("openai-whisper", "OpenAI whisper-1", False, "OPENAI_TEST_KEY isn't set", True)]
    # a model the catalog doesn't know goes by its own name
    assert [(m.name, m.title, m.available) for m in found.translators] == [
        ("spark-gemma", "Gemma 4 26B-A4B", True), ("lan-llm", "lan-llm", True)]
    assert found.transcribers == review.model_choices(CONFIG, CANDIDATES, "transcribe")


def test_each_catalog_entry_no_model_points_at_is_greyed_with_add_it_to_vid2sub_toml():
    found = review.models(CONFIG, CANDIDATES)
    assert [e.id for e in found.unconfigured] == UNCONFIGURED  # the catalog's own order
    for e in found.unconfigured:
        entry = CATALOG[e.id]
        assert (e.title, e.task, e.good_for, e.install, e.cloud) == (
            entry.title, entry.task, entry.good_for, entry.install, entry.cloud)
        assert e.reason == review.NOT_CONFIGURED == "add it to vid2sub.toml"


@pytest.fixture
def toml(tmp_path, monkeypatch):
    cfg = tmp_path / "vid2sub.toml"
    cfg.write_text("""
[endpoints.spark]
base_url = "http://127.0.0.1:9/v1"

[models.spark-turbo]
catalog = "whisper-large-v3-turbo"
endpoint = "spark"
model = "turbo"
parser = "whisper.cpp"
local = true

[models.spark-gemma]
catalog = "gemma-4-26b-a4b"
endpoint = "spark"
model = "gemma"
task = "translate"
local = true
""", encoding="utf-8")
    monkeypatch.setattr(detecting, "candidates", lambda config, keys, **kw: [
        Candidate("spark-turbo", "whisper-large-v3-turbo", "endpoint", False, DOWN),
        Candidate("spark-gemma", "gemma-4-26b-a4b", "endpoint", True)])
    return cfg


def test_vid2sub_models_lists_what_review_models_finds_in_its_order(toml, capsys):
    assert main(["models", "--config", str(toml), "--json"]) == 0
    rows = [e for e in map(json.loads, capsys.readouterr().out.splitlines())
            if e.get("event") == "model"]
    assert [(r["name"], r["catalog"], r["task"], r["available"], r["reason"]) for r in rows] == [
        ("spark-turbo", "whisper-large-v3-turbo", "transcribe", False, DOWN),
        ("spark-gemma", "gemma-4-26b-a4b", "translate", True, ""),
        *((None, cid, CATALOG[cid].task, False, "add it to vid2sub.toml")
          for cid in ["qwen3-asr-1.7b", "qwen3-asr-0.6b", "whisper-large-v3",
                      "openai-whisper-1", "qwen3.8-27b", "local-llm", "openai-gpt"])]


def test_vid2sub_models_says_in_words_what_can_run_and_what_to_add(toml, capsys):
    assert main(["models", "--config", str(toml)]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[:2] == [f"✗ spark-turbo: Whisper large-v3-turbo (transcribe) — {DOWN}",
                         "✓ spark-gemma: Gemma 4 26B-A4B (translate)"]
    assert "· Whisper large-v3 (transcribe): add it to vid2sub.toml" in lines
```

  and `tests/test_web_models.py`:

```python
"""The Models page's server (spec §11.1, §19.2, §6.8; S44): the `models` output is null until the
page asks (`models_check`, sent when the Models screen opens and by **Check again**); the check
runs off the event loop and says so meanwhile, then lists every configured model by task, usable
now or why not, and the catalog's other entries greyed with "add it to vid2sub.toml"; a runtime
whose job context has its own candidates (the demo's) lists those, under the catalog titles they
stand in for, and any other asks each local server and checks each cloud key now; nothing on the
page names a path, a token or a key; and Pages has no Models page."""

import dataclasses
import json
import threading

import pytest
from fakes import FakeServer
from test_models import CANDIDATES, CONFIG, DOWN, UNCONFIGURED
from test_web_review import client_for
from test_web_server import (  # noqa: F401 - fresh_reactive_lock is autouse
    TOKEN,
    fresh_reactive_lock,
    tab,
)
from test_web_settings import Browser

from vid2sub import detect as detecting
from vid2sub import review as reviewing
from vid2sub.cache import Cache
from vid2sub.config import Config
from vid2sub.engines.clients import KeyRing
from vid2sub.media.tools import Tools
from vid2sub.pipeline import RunContext, RunOptions
from vid2sub.web import demo, runtime, views

KEY = "k" * 40  # low entropy, plainly not a real key


def built(tmp_path, config=CONFIG, *, candidates=None, keys=None):
    keys = keys or KeyRing(environ={})
    ctx = RunContext(config=config, tools=Tools.find(), keys=keys, options=RunOptions(),
                     candidates=candidates)
    return runtime.build(config, tools=Tools.find(), keys=keys,
                         cache=Cache(tmp_path / "cache", max_bytes=0), job_context=ctx)


@pytest.fixture
def rt(tmp_path):
    made = built(tmp_path, candidates=list(CANDIDATES))
    runtime.configure(made)
    yield made
    runtime.configure(None)
    made.queue.close()


@pytest.fixture
def client(rt):
    c = client_for(rt)
    yield c
    c.__exit__(None, None, None)


# ---- the runtime and the view ------------------------------------------------------------------


def test_the_runtime_lists_its_job_contexts_own_candidates_as_review_models_does(rt):
    assert rt.models() == reviewing.models(CONFIG, CANDIDATES)


def test_the_demos_canned_models_go_by_the_catalog_titles_they_stand_in_for(tmp_path):
    rt = built(tmp_path, demo.JOB_CONFIG, candidates=list(demo.CANNED_MODELS))
    try:
        found = rt.models()
    finally:
        rt.queue.close()
    assert [(m.name, m.title, m.available) for m in found.transcribers] == [
        ("canned", "Whisper large-v3-turbo", True)]
    assert [(m.name, m.title, m.available) for m in found.translators] == [
        ("canned-ja", "Gemma 4 26B-A4B", True)]


def test_without_candidates_of_its_own_the_runtime_asks_each_server_and_checks_each_key_now(
        tmp_path, monkeypatch):
    monkeypatch.setattr(detecting, "mlx_available", lambda: False)
    asked = []

    def spark(req):
        asked.append(req.path)
        return 200, {"object": "list", "data": [
            {"id": "turbo", "object": "model", "created": 0, "owned_by": "spark"}]}, {}

    with FakeServer(responder=spark) as srv:
        config = Config.model_validate({**CONFIG.model_dump(), "endpoints": {
            "spark": {"base_url": srv.url},
            "openai": {"base_url": "https://api.openai.com/v1", "key_env": "OPENAI_TEST_KEY"}}})
        rt = built(tmp_path, config, keys=KeyRing(environ={"OPENAI_TEST_KEY": KEY}))
        try:
            found = rt.models()
        finally:
            rt.queue.close()
    assert asked == ["/v1/models"]  # once for the endpoint; the cloud one is never contacted
    assert [(m.name, m.available, m.reason) for m in found.transcribers] == [
        ("spark-turbo", True, ""),
        ("mac-qwen", False, "install vid2sub[mac] on an Apple Silicon Mac"),
        ("openai-whisper", True, "")]
    assert [(m.name, m.available, m.reason) for m in found.translators] == [
        ("spark-gemma", False, "the server doesn't list gemma"),
        ("lan-llm", False, "the server doesn't list llama")]
    shown = json.dumps(views.models_view(found, checking=False))
    assert KEY not in shown and "OPENAI_TEST_KEY" not in shown


def test_the_view_lists_each_task_then_the_catalogs_other_entries_and_names_no_path(rt):
    view = views.models_view(rt.models(), checking=False)
    assert view["checking"] is False and view["error"] is None
    assert view["transcribers"][0] == {
        "name": "spark-turbo", "title": "Whisper large-v3-turbo",
        "good_for": "English → English captions, quick drafts", "available": False,
        "reason": DOWN, "cloud": False}
    assert [(c["name"], c["available"], c["reason"]) for c in view["translators"]] == [
        ("spark-gemma", True, None), ("lan-llm", True, None)]
    assert [e["id"] for e in view["unconfigured"]] == UNCONFIGURED
    assert view["unconfigured"][0] == {
        "id": "qwen3-asr-0.6b", "title": "Qwen3-ASR 0.6B + ForcedAligner 0.6B",
        "task": "transcribe", "good_for": "the same languages as the 1.7B, lighter and faster",
        "install": "vid2sub[mac]", "cloud": False, "reason": "add it to vid2sub.toml"}
    assert views.models_view(None, checking=True) == {
        "checking": True, "error": None, "transcribers": [], "translators": [],
        "unconfigured": []}


# ---- the server --------------------------------------------------------------------------------


def models(t) -> dict | None:
    return t.value("models") if t.has("models") else None


def test_the_models_output_waits_to_be_asked_then_checks_off_the_loop_and_lists_them(
        client, rt, monkeypatch):
    held, go, calls = threading.Event(), threading.Event(), []
    real = reviewing.models

    def slow(config, candidates):
        calls.append(1)
        held.set()
        assert go.wait(20)
        return real(config, candidates)

    monkeypatch.setattr(reviewing, "models", slow)
    with tab(client, {"models"}) as t:
        t.until(lambda t: t.has("models"))
        assert models(t) is None  # nothing is asked of a server until the page opens
        t.set(models_check={"n": 1})
        assert held.wait(20)
        view = t.until(lambda t: (models(t) or {}).get("checking") and models(t))
        assert view["transcribers"] == [] and view["unconfigured"] == []
        t.set(models_check={"n": 2})  # a second ask while one runs is dropped
        go.set()
        view = t.until(lambda t: models(t) and not models(t)["checking"] and models(t))
    assert calls == [1]  # the second ask, sent while the first ran, was dropped
    assert [c["name"] for c in view["transcribers"]] == ["spark-turbo", "mac-qwen",
                                                         "openai-whisper"]
    assert [e["id"] for e in view["unconfigured"]] == UNCONFIGURED
    assert TOKEN not in json.dumps(view)


def test_check_again_asks_again_and_the_page_shows_what_it_found_then(client, rt, monkeypatch):
    found = iter([CANDIDATES, [dataclasses.replace(c, available=True, reason="")
                               for c in CANDIDATES]])
    monkeypatch.setattr(reviewing, "models",
                        lambda config, cands, real=reviewing.models: real(config, next(found)))
    with tab(client, {"models"}) as t:
        t.set(models_check={"n": 1})
        first = t.until(lambda t: models(t) and not models(t)["checking"] and models(t))
        t.set(models_check={"n": 2})
        again = t.until(lambda t: models(t) and models(t)["transcribers"][0]["available"]
                        and not models(t)["checking"] and models(t))
    assert first["transcribers"][0]["reason"] == DOWN and again["transcribers"][0]["reason"] is None


def test_a_check_that_fails_says_so_and_names_nothing(client, rt, monkeypatch):
    def broken(config, candidates):
        raise RuntimeError(f"{TOKEN} /Users/someone/vid2sub.toml")

    monkeypatch.setattr(reviewing, "models", broken)
    with tab(client, {"models"}) as t:
        t.set(models_check={"n": 1})
        view = t.until(lambda t: models(t) and models(t)["error"] and models(t))
    assert view["error"] == "couldn't check the models; see the log"
    assert view["checking"] is False and TOKEN not in json.dumps(view)
    assert "/Users/someone" not in json.dumps(view)


def test_the_pages_editor_has_no_models_page(rt, monkeypatch):
    called = []
    monkeypatch.setattr(reviewing, "models", lambda *args: called.append(args))
    pages = dataclasses.replace(rt, backend=Browser(rt.backend))
    runtime.configure(pages)
    c = client_for(pages)
    try:
        with tab(c, {"models"}) as t:
            t.until(lambda t: t.has("models"))
            t.set(models_check={"n": 1})
            t.set(open={"path": "/nowhere/x.mkv", "n": 2})  # something it does answer
            t.until(lambda t: t.notices())
            assert models(t) is None
    finally:
        c.__exit__(None, None, None)
    assert called == []
```

- [ ] **Step 2: Run them; watch them fail.** `uv run pytest tests/test_models.py
  tests/test_web_models.py -q`. Expected: `E       AttributeError: module 'vid2sub.review' has no
  attribute 'models'`, the same for `Runtime` and `views.models_view`, `vid2sub models` still
  saying `not in vid2sub.toml`, and `12 failed`.
- [ ] **Step 3: Write the code.**
  In `src/vid2sub/review.py`, replace

```python
and nothing here logs (§6.8).
```

  with

```python
and nothing here logs (§6.8). The Models page and `vid2sub models` list the same models as the
pickers, with the catalog's entries no model points at (`models`, §11.1; Phase 3 Task 8).
```

  Then below the line `FORMATS = ("srt", "ass")`, add:

```python
NOT_CONFIGURED = "add it to vid2sub.toml"  # a catalog entry no model points at (spec §11.1)
```

  Then below the line `cloud: bool = False`, add:

```python


@dataclass(frozen=True)
class CatalogModel:
    """A catalog entry that no model in vid2sub.toml points at (spec §11.1): shown greyed, with
    what it is good for, how to install it, and `reason`."""

    id: str
    title: str
    task: Literal["transcribe", "translate"]
    good_for: str
    install: str
    cloud: bool
    reason: str = NOT_CONFIGURED


@dataclass(frozen=True)
class Models:
    """The Models page and `vid2sub models` (spec §11.1, §18.1, §19.2; S44): every configured
    model by task, as Review's pickers list them, then the catalog's other entries."""

    transcribers: tuple[ModelChoice, ...]
    translators: tuple[ModelChoice, ...]
    unconfigured: tuple[CatalogModel, ...]
```

  Then below the line `return tuple(out)`, add:

```python


def models(config: Config, candidates: Sequence[Candidate]) -> Models:
    """What the Models page and `vid2sub models` list (spec §11.1, §18.1, §19.2; S44): every
    configured model by task, in `vid2sub.toml`'s order, with whether it can run now and why not
    (`model_choices`, so Review's pickers say the same), then each catalog entry no model points
    at, in the catalog's order, greyed with "add it to vid2sub.toml"."""
    configured = {c.catalog for c in candidates}
    return Models(model_choices(config, candidates, "transcribe"),
                  model_choices(config, candidates, "translate"),
                  tuple(CatalogModel(e.id, e.title, e.task, e.good_for, e.install, e.cloud)
                        for e in CATALOG.values() if e.id not in configured))
```

  Replace `src/vid2sub/commands/models.py` with:

```python
"""`vid2sub models`: the catalog, and what's usable on this machine now (spec §11, §18.1).

The models come from `review.models`, as the app's Models page has them (Phase 3 Task 8), so the
two can't disagree: every configured model by task, with whether it can run now and why not, then
each catalog entry no model points at, with "add it to vid2sub.toml" (§11.1).
"""

from __future__ import annotations

import argparse

from vid2sub import detect as detecting
from vid2sub import exitcodes, review
from vid2sub.catalog import readme_table
from vid2sub.commands import _common
from vid2sub.commands._common import CommandError, Output, add_common
from vid2sub.engines.clients import KeyRing, quiet_libraries


def add_parser(sub) -> None:
    p = sub.add_parser("models", help="list models and whether each can run now")
    p.add_argument("--markdown", action="store_true", help="print the README's model table")
    p.add_argument("--offline", action="store_true", help="don't contact any server")
    add_common(p)
    p.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    if args.markdown:
        print(readme_table(), end="")
        return exitcodes.OK
    out = Output(args.json)
    quiet_libraries()
    try:
        config = _common.load(args)
    except CommandError as err:
        return _common.fail(out, err)
    cands = detecting.candidates(config, KeyRing(), probe_endpoints=not args.offline)
    found = review.models(config, cands)
    catalog = {c.name: c.catalog for c in cands}
    for task, choices in (("transcribe", found.transcribers), ("translate", found.translators)):
        for m in choices:
            out.event("model", name=m.name, catalog=catalog[m.name], task=task,
                      available=m.available, reason=m.reason, cloud=m.cloud)
            mark = "✓" if m.available else "✗"
            out.say(f"{mark} {m.name}: {m.title} ({task}{', cloud' if m.cloud else ''})"
                    + (f" — {m.reason}" if m.reason else ""))
    for e in found.unconfigured:
        out.event("model", name=None, catalog=e.id, task=e.task, available=False,
                  reason=e.reason, cloud=e.cloud)
        out.say(f"· {e.title} ({e.task}): {e.reason}")
    return exitcodes.OK
```

  In `src/vid2sub/web/runtime.py`, replace

```python
demo a job still runs only the demo's clip.
```

  with

```python
demo a job still runs only the demo's clip. The Models page (Phase 3 Task 8, §11.1) lists the job
context's models through `models`, as Review's pickers and `vid2sub models` do.
```

  Then replace

```python
    from vid2sub.review import Review, Row
```

  with

```python
    from vid2sub.review import Models, Review, Row
```

  Then below these lines

```python
            return review.start(rv, self.queue, self.job_context, guard=self.job_guard)
        except review.ReviewError as err:
            raise ReviewRefused(str(err)) from None
```

  add:

```python

    def models(self) -> Models:
        """The Models page (spec §11.1, §19.2, S44): `review.models` on the job context, as
        Review's pickers and `vid2sub models` list them: its own candidates where it has them
        (the demo's canned ones), else each configured model checked now, each local server
        asked for its model list and each cloud one checked for its key only. Blocks on each
        local server: call it through `blocking`."""
        from vid2sub import detect, review

        ctx = self.job_context
        config, keys = (ctx.config, ctx.keys) if ctx is not None else (self.config, self.keys)
        cands = (ctx.candidates if ctx is not None and ctx.candidates is not None
                 else detect.candidates(config, keys))
        return review.models(config, cands)
```

  In `src/vid2sub/web/views.py`, replace

```python
shows each row by bare name, never its path (Task 4, §10). The server runs in Pages too
```

  with

```python
shows each row by bare name, never its path (Task 4, §10); the Models page lists the models by
name and the catalog's titles (Task 8, §11.1). The server runs in Pages too
```

  Then replace

```python
    from vid2sub.review import ModelChoice, Review
```

  with

```python
    from vid2sub.review import ModelChoice, Models, Review
```

  Then below the line `"reason": c.reason or None, "cloud": c.cloud}`, add:

```python


def models_view(found: Models | None, *, checking: bool,
                error: str | None = None) -> dict[str, Any]:
    """The Models page (spec §11.1, §19.2, S44): every configured model by task, as Review's
    pickers list them, usable now or with why not, then each catalog entry no model points at,
    with how to install it and "add it to vid2sub.toml" (`review.models`). `checking`: a check
    is running, and the lists are the last one's (none before the first). Names, titles and
    reasons only: never a path, a token or a key (§6.8)."""
    return {
        "checking": checking,
        "error": error,
        "transcribers": [_choice(c) for c in found.transcribers] if found else [],
        "translators": [_choice(c) for c in found.translators] if found else [],
        "unconfigured": [{"id": e.id, "title": e.title, "task": e.task, "good_for": e.good_for,
                          "install": e.install, "cloud": e.cloud, "reason": e.reason}
                         for e in found.unconfigured] if found else [],
    }
```

  In `src/vid2sub/web/server.py`, below these lines

```python
run** is the review's own, unticked in every new review (§7.2). The view never holds a path.
```

  add:

```python

The Models page (§11.1, §19.2; S44; Phase 3 Task 8), the local engine's alone, is the `models`
output: null until the page asks (`models_check`, when it opens and on **Check again**), then
every configured model by task, usable now or why not, and the catalog's other entries, from the
runtime's `models`, which asks each local server for its list, so it runs off the event loop as
an extended task of the tab's own.
```

  Then below the line `PICK_A_CHOICE = "pick a file and a choice for it"`, add:

```python
MODELS_FAILED = "couldn't check the models; see the log"
```

  Then below the line `reviewer.discard()`, add:

```python

    # The Models page (spec §11.1, §19.2; S44), the local engine's alone: checked when the page
    # opens and on Check again (`models_check`), as this session's extended task, off the event
    # loop and outside Shiny's reactive lock; an ask while a check runs is dropped, since the page
    # shows that one. The page keeps the last check's lists while the next runs.
    checked: reactive.Value[tuple[Any, str | None]] = reactive.value((None, None))

    @reactive.extended_task
    async def check_models() -> tuple[Any, str | None]:
        try:
            return await runtime.blocking(rt.models), None
        except Exception as err:  # noqa: BLE001 - a failed check must not stop the session
            log.error("the models check failed: %s", type(err).__name__)
            return None, MODELS_FAILED

    @reactive.effect
    @reactive.event(input.models_check)
    def _models_check() -> None:
        if local and check_models.status() != "running":
            check_models.invoke()

    @reactive.effect
    def _keep_the_models() -> None:
        if check_models.status() == "success":
            checked.set(check_models.result())

    @reactive_output
    def models():
        status = check_models.status()
        if not local or status == "initial":
            return None
        found, error = checked()
        return views.models_view(found, checking=status == "running", error=error)
```

- [ ] **Step 4: Run the checks; they pass.** `uv run pytest tests/test_models.py
  tests/test_web_models.py tests/test_review.py tests/test_cli_more.py tests/test_spark_qwen.py
  -q` first (`71 passed`), then the guard checks, then `make check`. **Guard checks**, each with
  the file tools in `src/vid2sub/web/server.py`, reverted and restored, each with
  `uv run pytest tests/test_web_models.py -q`: replace
  `            return await runtime.blocking(rt.models), None` with
  `            return rt.models(), None` (`FAILED
  …test_the_models_output_waits_to_be_asked_then_checks_off_the_loop_and_lists_them`,
  `AssertionError: timed out`: the check holds the loop, so the page never says it is checking);
  replace `            return None, MODELS_FAILED` with `            return None, str(err)`
  (`FAILED …test_a_check_that_fails_says_so_and_names_nothing`: the token and the path show);
  replace `        if local and check_models.status() != "running":` with
  `        if check_models.status() != "running":` (`FAILED
  …test_the_pages_editor_has_no_models_page`: Pages checked the models); replace it with
  `        if local:` (`FAILED
  …test_the_models_output_waits_to_be_asked_then_checks_off_the_loop_and_lists_them`,
  `Left contains one more item: 1`: a second check ran). `make check`. Expected:
  `1237 passed, 7 skipped, 43 deselected` twice, `Test Files  22 passed (22)`,
  `Tests  108 passed (108)`, `All checks passed!` and `no leaks found`.
- [ ] **Step 5: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(web): 🤖 the Models page's server lists every configured model usable now or why not, and the catalog's other entries, as vid2sub models does

review.models gives the Models page and vid2sub models one list (spec
§11.1, §18.1, §19.2; S44): every configured model by task, in
vid2sub.toml's order, through Task 3's model_choices, so Review's
pickers say the same, then each catalog entry no model points at,
greyed with "add it to vid2sub.toml" (§11.1's words; M1's CLI said "not
in vid2sub.toml"). vid2sub models now prints from it, grouped by task.
Runtime.models runs it on the job context: the demo's canned
candidates, under the catalog titles they stand in for (Decision 22),
else each configured model checked now. The server's models output is
null until the page asks (models_check); the check runs as the
session's extended task, through runtime.blocking; an ask while one
runs is dropped; a check that fails says so without echoing its error
(§6.8). Pages has no Models page.

The new tests failed first: "AttributeError: module 'vid2sub.review'
has no attribute 'models'" (12 failed). Guard checks, each reverted and
restored: without runtime.blocking the check holds the loop and the
page never says it is checking (the server test times out); with the
error's own text the token and the path show; without `local` the
Pages editor checks the models; without the running check a second ask
runs a second check.

Docs read: shiny 1.8.0's reactive/_extended_task.py (invoke queues a
call made while one runs; status and result are reactive values).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md Task 8
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/review.py src/vid2sub/commands/models.py src/vid2sub/web/runtime.py
  src/vid2sub/web/views.py src/vid2sub/web/server.py tests/test_models.py
  tests/test_web_models.py`, `git commit -F .git/COMMIT_MSG`, then
  `git log -1 --format='%(trailers)'` shows `Plan:`.
- [ ] **Step 6: Write the failing tests,** `frontend/src/lib/models.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import type { ModelChoice, ModelsView } from "@/types";

import { sections, summary, why } from "./models";

const TURBO: ModelChoice = { name: "spark-turbo", title: "Whisper large-v3-turbo", good_for: "English → English captions, quick drafts", available: true, reason: null, cloud: false };
const WHISPER: ModelChoice = { name: "local-whisper", title: "Whisper large-v3-turbo", good_for: "", available: false, reason: "install vid2sub[whisper] (vid2sub[nvidia] for an NVIDIA GPU)", cloud: false };
const GEMMA: ModelChoice = { name: "spark-gemma", title: "Gemma 4 26B-A4B", good_for: "", available: false, reason: null, cloud: false };
const VIEW: NonNullable<ModelsView> = {
  checking: false,
  error: null,
  transcribers: [TURBO, WHISPER],
  translators: [GEMMA],
  unconfigured: [
    { id: "qwen3-asr-0.6b", title: "Qwen3-ASR 0.6B + ForcedAligner 0.6B", task: "transcribe", good_for: "", install: "vid2sub[mac]", cloud: false, reason: "add it to vid2sub.toml" },
    { id: "openai-gpt", title: "OpenAI GPT", task: "translate", good_for: "", install: "an OpenAI key", cloud: true, reason: "add it to vid2sub.toml" },
  ],
};

describe("the Models page in words (spec §11.1, §19.2; S44)", () => {
  it("says a model is usable now, or gives the engine's reason why not", () => {
    expect(why(TURBO)).toBe("usable now");
    expect(why(WHISPER)).toBe("install vid2sub[whisper] (vid2sub[nvidia] for an NVIDIA GPU)");
    expect(why(GEMMA)).toBe("can't run now");
  });

  it("puts each task's configured models first, then the catalog's entries for that task", () => {
    expect(sections(VIEW).map((s) => [s.heading, s.configured.map((c) => c.name), s.unconfigured.map((e) => e.id)])).toEqual([
      ["Transcription", ["spark-turbo", "local-whisper"], ["qwen3-asr-0.6b"]],
      ["Translation", ["spark-gemma"], ["openai-gpt"]],
    ]);
  });

  it("counts what can run now, and says when it is checking", () => {
    expect(summary(VIEW)).toBe("1 of 3 configured models can run now");
    expect(summary({ ...VIEW, transcribers: [TURBO], translators: [] })).toBe("1 of 1 configured model can run now");
    expect(summary({ ...VIEW, transcribers: [], translators: [] })).toBe("no models in vid2sub.toml yet");
    expect(summary({ ...VIEW, checking: true })).toBe("checking what can run now…");
    expect(summary(null)).toBe("checking what can run now…");
  });
});
```

  `frontend/src/components/ModelsPage.test.ts`:

```ts
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { ModelsView } from "@/types";

import { ModelsPage } from "./ModelsPage";

const VIEW: NonNullable<ModelsView> = {
  checking: false,
  error: null,
  transcribers: [
    { name: "spark-turbo", title: "Whisper large-v3-turbo", good_for: "English → English captions, quick drafts", available: true, reason: null, cloud: false },
    { name: "<b>mine</b>", title: "<b>mine</b>", good_for: "", available: false, reason: "<img src=x> isn't answering", cloud: false },
  ],
  translators: [{ name: "openai", title: "OpenAI GPT", good_for: "", available: false, reason: "OPENAI_API_KEY isn't set", cloud: true }],
  unconfigured: [{ id: "whisper-large-v3", title: "Whisper large-v3", task: "transcribe", good_for: "99 languages", install: "a whisper.cpp server", cloud: false, reason: "add it to vid2sub.toml" }],
};

function render(models: ModelsView): string {
  return renderToStaticMarkup(createElement(ModelsPage, { models, onCheck: () => undefined }));
}

describe("the Models page (spec §11.1, §19.2; S44)", () => {
  it("marks each configured model usable now or says why not, in words", () => {
    const html = render(VIEW);
    expect(html).toMatch(/data-usable="yes"[^>]*>.*spark-turbo: Whisper large-v3-turbo<\/span> — <span data-testid="model-why">usable now</);
    expect(html).toContain("openai: OpenAI GPT (cloud), can&#x27;t run now</span> — <span data-testid=\"model-why\">OPENAI_API_KEY isn&#x27;t set<");
    expect(html).toMatch(/role="status" aria-live="polite" data-testid="models-status">1 of 3 configured models can run now</);
  });

  it("greys each catalog entry no model points at, with how to install it and what to do", () => {
    const html = render(VIEW);
    expect(html).toMatch(/text-muted-foreground" data-testid="catalog-model"><span data-testid="catalog-title">Whisper large-v3<\/span> — <span data-testid="catalog-why">add it to vid2sub.toml</);
    expect(html).toContain("99 languages. Install: a whisper.cpp server");
  });

  it("shows names and reasons as text, never markup", () => {
    const html = render(VIEW);
    expect(html).not.toContain("<b>");
    expect(html).not.toContain("<img");
    expect(html).toContain("&lt;img src=x&gt; isn&#x27;t answering");
  });

  it("says it is checking, keeps the last lists meanwhile, and says when a check failed", () => {
    expect(render(null)).toContain("checking what can run now…");
    expect(render(null)).toMatch(/disabled=""[^>]*data-testid="models-check"/);
    const checking = render({ ...VIEW, checking: true });
    expect(checking).toContain("checking what can run now…");
    expect(checking).toContain("spark-turbo: Whisper large-v3-turbo");
    expect(render({ ...VIEW, error: "couldn't check the models; see the log" })).toMatch(/role="alert"[^>]*>couldn&#x27;t check the models; see the log</);
  });
});
```

  and `tests/e2e/test_models.py`:

```python
"""The Models page in Chromium (spec §11.1, §19.2, §6.8; S44): the catalog, each model marked usable
now or why not. Against `vid2sub serve --demo`, whose canned models stand in for Whisper
large-v3-turbo and Gemma 4 (the Phase 3 plan's Decision 22), and against a vid2sub.toml whose
endpoint is a fake server on this machine serving one of its two models, beside a cloud model
whose key isn't set: each configured model says it is usable now or why not, each catalog entry
no model points at is greyed with "add it to vid2sub.toml", **Check again** asks again, and the
page names no path. Run with `make e2e`."""

import pytest
from fakes import FakeServer
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e

TOML = """
[endpoints.spark]
base_url = "{url}"

[endpoints.openai]
base_url = "https://api.openai.com/v1"
key_env = "VID2SUB_E2E_OPENAI_KEY"

[models.spark-turbo]
catalog = "whisper-large-v3-turbo"
endpoint = "spark"
model = "turbo"
parser = "whisper.cpp"
local = true

[models.openai-whisper]
catalog = "openai-whisper-1"
endpoint = "openai"
model = "whisper-1"
parser = "openai"

[models.spark-gemma]
catalog = "gemma-4-26b-a4b"
endpoint = "spark"
model = "gemma"
task = "translate"
local = true
"""


def open_models(page) -> None:
    page.get_by_test_id("nav-models").click()
    expect(page.get_by_test_id("models-page")).to_be_visible()
    expect(page.get_by_test_id("models-check")).to_be_enabled()  # the first check is done


def test_the_demos_models_page_names_whisper_turbo_and_gemma_4_usable_and_greys_the_rest(
        page, server):
    open_models(page)
    models = page.get_by_test_id("model")
    expect(models.get_by_test_id("model-label")).to_have_text(
        ["canned: Whisper large-v3-turbo", "canned-ja: Gemma 4 26B-A4B"])
    expect(models.get_by_test_id("model-why")).to_have_text(["usable now", "usable now"])
    expect(page.get_by_test_id("models-status")).to_have_text(
        "2 of 2 configured models can run now")
    others = page.get_by_test_id("catalog-model")
    expect(others.get_by_test_id("catalog-title")).to_have_text([
        "Qwen3-ASR 1.7B + ForcedAligner 0.6B", "Qwen3-ASR 0.6B + ForcedAligner 0.6B",
        "Whisper large-v3", "OpenAI whisper-1 (cloud)", "Qwen3.8 27B", "A local chat model",
        "OpenAI GPT (cloud)"])
    expect(others.get_by_test_id("catalog-why")).to_have_text(["add it to vid2sub.toml"] * 7)
    assert str(server.tmp) not in page.content()  # the demo's folder is nowhere on the page


def test_each_configured_model_says_usable_now_or_why_not_and_check_again_asks_again(
        launch, open_page, tmp_path):
    served = ["turbo"]

    def spark(req):
        if req.path.endswith("/models"):
            return 200, {"object": "list", "data": [
                {"id": i, "object": "model", "created": 0, "owned_by": "test"}
                for i in served]}, {}
        return 404, {}, {}

    with FakeServer(responder=spark) as fake:
        server = launch(tmp_path / "server", toml=TOML.format(url=fake.url))
        watched = open_page(server)
        page = watched.page
        open_models(page)
        models = page.get_by_test_id("model")
        expect(models.get_by_test_id("model-label")).to_have_text([
            "spark-turbo: Whisper large-v3-turbo",
            "openai-whisper: OpenAI whisper-1 (cloud), can't run now",
            "spark-gemma: Gemma 4 26B-A4B, can't run now"])
        expect(models.get_by_test_id("model-why")).to_have_text([
            "usable now", "VID2SUB_E2E_OPENAI_KEY isn't set", "the server doesn't list gemma"])
        expect(models.nth(0)).to_have_attribute("data-usable", "yes")
        expect(page.get_by_test_id("models-transcribe").get_by_test_id("catalog-title")) \
            .to_have_text(["Qwen3-ASR 1.7B + ForcedAligner 0.6B",
                           "Qwen3-ASR 0.6B + ForcedAligner 0.6B", "Whisper large-v3"])
        served.append("gemma")  # the server loads Gemma: Check again asks it again
        page.get_by_test_id("models-check").click()
        expect(models.nth(2).get_by_test_id("model-why")).to_have_text("usable now")
        expect(page.get_by_test_id("models-status")).to_have_text(
            "2 of 3 configured models can run now")
        assert str(tmp_path) not in page.content()
    assert watched.errors == [], f"console errors: {watched.errors}"
    assert watched.violations() == []
```

- [ ] **Step 7: Run them; watch them fail.** `make test-js`. Expected: its typecheck stops at
  `src/components/ModelsPage.test.ts(5,15): error TS2305: Module '"@/types"' has no exported
  member 'ModelsView'.` and `src/components/ModelsPage.test.ts(7,28): error TS2307: Cannot find
  module './ModelsPage' or its corresponding type declarations.` (and the same two for
  `src/lib/models.test.ts`). `make build`, then `uv run pytest tests/e2e/test_models.py -q -m
  e2e`. Expected: `E           playwright._impl._errors.TimeoutError: Locator.click: Timeout
  30000ms exceeded.`, waiting for `get_by_test_id("nav-models")`, and `2 failed`.
- [ ] **Step 8: Write the code,** `frontend/src/lib/models.ts`:

```ts
// The Models page's words (spec §11.1, §19.2; S44): each configured model usable now or why not
// (a server not answering, a key not set, an extra not installed: the engine's own reason), each
// task's models with the catalog's entries no model points at, and how many can run now. A model
// goes by its name in vid2sub.toml and the catalog's title, never a path.

import type { CatalogModel, ModelChoice, ModelsView } from "@/types";

/** "usable now", or the engine's reason it can't run. */
export function why(c: ModelChoice): string {
  return c.available ? "usable now" : (c.reason ?? "can't run now");
}

export type Section = { task: "transcribe" | "translate"; heading: string; configured: ModelChoice[]; unconfigured: CatalogModel[] };

/** Transcription, then translation: each task's configured models in vid2sub.toml's order, then
 * the catalog's entries for it that no model points at. */
export function sections(view: NonNullable<ModelsView>): Section[] {
  const others = (task: Section["task"]) => view.unconfigured.filter((e) => e.task === task);
  return [
    { task: "transcribe", heading: "Transcription", configured: view.transcribers, unconfigured: others("transcribe") },
    { task: "translate", heading: "Translation", configured: view.translators, unconfigured: others("translate") },
  ];
}

/** The page's status line: what the last check found, or that a check is running. */
export function summary(view: ModelsView): string {
  if (!view || view.checking) return "checking what can run now…";
  const all = [...view.transcribers, ...view.translators];
  if (!all.length) return "no models in vid2sub.toml yet";
  const usable = all.filter((c) => c.available).length;
  return `${usable} of ${all.length} configured ${all.length === 1 ? "model" : "models"} can run now`;
}
```

  `frontend/src/components/ModelsPage.tsx`:

```tsx
import { sections, summary, why } from "@/lib/models";
import { choiceLabel } from "@/lib/review";
import type { ModelsView } from "@/types";

const button = "rounded-md border border-input bg-background px-2 py-1 text-sm focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ring disabled:opacity-50";

/** The Models page (spec §11.1, §19.2; S44): the catalog, each model marked usable on this machine
 * now or why not. Every model in vid2sub.toml, by task, as Review's pickers name it, with the
 * catalog's one-liner and either "usable now" or the engine's reason it can't run; then, greyed,
 * each catalog entry no model points at, with how to install it and "add it to vid2sub.toml"
 * (§11.1). The engine checks when the page opens and on **Check again**; while it does, the page
 * says so politely and keeps the last lists. Usable or not is said in words, not by colour alone
 * (§19.3); names, titles and reasons are plain text (§6.3), and none is a path or a key (§6.8). */
export function ModelsPage({ models, onCheck }: { models: ModelsView; onCheck: () => void }) {
  return (
    <div className="flex h-full min-h-0 flex-col gap-3 overflow-y-auto p-4" data-testid="models-page">
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <span role="status" aria-live="polite" data-testid="models-status">{summary(models)}</span>
        <button type="button" className={`${button} ml-auto`} onClick={onCheck} disabled={!models || models.checking} data-testid="models-check">Check again</button>
      </div>
      {models?.error && <p role="alert" className="text-sm text-destructive" data-testid="models-error">{models.error}</p>}
      {models && sections(models).map((s) => (
        <section key={s.task} aria-labelledby={`models-${s.task}`} className="flex flex-col gap-1" data-testid={`models-${s.task}`}>
          <h2 id={`models-${s.task}`} className="text-sm font-bold">{s.heading}</h2>
          <ul className="flex flex-col gap-1">
            {s.configured.map((c) => (
              <li key={c.name} className="rounded-md border border-border bg-card p-2 text-sm" data-testid="model" data-usable={c.available ? "yes" : "no"}>
                <span aria-hidden="true">{c.available ? "✓ " : "✗ "}</span>
                <span className="font-bold" data-testid="model-label">{choiceLabel(c)}</span>
                {" — "}
                <span data-testid="model-why">{why(c)}</span>
                {c.good_for && <span className="block text-muted-foreground">{c.good_for}</span>}
              </li>
            ))}
            {s.unconfigured.map((e) => (
              <li key={e.id} className="rounded-md border border-dashed border-border p-2 text-sm text-muted-foreground" data-testid="catalog-model">
                <span data-testid="catalog-title">{e.title}{e.cloud ? " (cloud)" : ""}</span>
                {" — "}
                <span data-testid="catalog-why">{e.reason}</span>
                <span className="block">{e.good_for ? `${e.good_for}. ` : ""}Install: {e.install}</span>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
```

  In `frontend/src/types.ts`, below the line
  `export type ReviewStartedMessage = { n: number | null; jobs: number };`, add:

```ts

/** A catalog entry no model in vid2sub.toml points at (views.models_view; spec §11.1): shown
 * greyed, with how to install it and `reason`, "add it to vid2sub.toml". */
export type CatalogModel = { id: string; title: string; task: "transcribe" | "translate"; good_for: string; install: string; cloud: boolean; reason: string };

/** The `models` output (views.models_view; spec §11.1, §19.2; S44): every configured model by
 * task, as Review's pickers list them, then the catalog's other entries; `checking` while the
 * engine checks, with the last lists kept; null until the page first asks, and in Pages. */
export type ModelsView = { checking: boolean; error: string | null; transcribers: ModelChoice[]; translators: ModelChoice[]; unconfigured: CatalogModel[] } | null;
```

  In `frontend/src/App.tsx`, below the line
  `import { JobsPage } from "@/components/JobsPage";`, add:

```tsx
import { ModelsPage } from "@/components/ModelsPage";
```

  Then replace

```tsx
import type { AddResultMessage, BrowseResult, Busy, Capabilities, EditOp, EndpointTestResult, EpisodeView, JobsView, PreviewProgress, Progress, RetranslateResultMessage, QueueState, ReviewOutput, ReviewStartedMessage, SaveResultMessage, SettingsView, Status } from "@/types";
```

  with

```tsx
import type { AddResultMessage, BrowseResult, Busy, Capabilities, EditOp, EndpointTestResult, EpisodeView, JobsView, ModelsView, PreviewProgress, Progress, RetranslateResultMessage, QueueState, ReviewOutput, ReviewStartedMessage, SaveResultMessage, SettingsView, Status } from "@/types";
```

  Then replace

```tsx
const SCREENS = { editor: "Editor", add: "Add", review: "Review", jobs: "Jobs" } as const;
```

  with

```tsx
const SCREENS = { editor: "Editor", add: "Add", review: "Review", jobs: "Jobs", models: "Models" } as const;
```

  Then below the line `const reviewOut = useShinyOutputValue<ReviewOutput>("review");`, add:

```tsx
  const modelsOut = useShinyOutputValue<ModelsView>("models");
```

  Then below these lines

```tsx
  const setReviewDiscard = useSetShinyInput<{ n: number } | null>("review_discard", null, { priority: "event", debounceMs: 0 });
```

  add:

```tsx
  const setModelsCheck = useSetShinyInput<{ n: number } | null>("models_check", null, { priority: "event", debounceMs: 0 });
```

  Then replace

```tsx
  // Add, Review and the Jobs page (spec §19.2; S36, S38–S40), where the engine makes subtitles
  // (`generate`; Pages hides them, §21). The editor stays mounted while they show, so the player
  // keeps its place.
```

  with

```tsx
  // Add, Review, the Jobs page and Models (spec §19.2; S36, S38–S40, S44), where the engine
  // makes subtitles (`generate`; Pages hides them, §21). The editor stays mounted while they
  // show, so the player keeps its place.
```

  Then below these lines

```tsx
  useShinyMessageHandler("review_started", (_: ReviewStartedMessage) => setScreen("jobs"));
```

  add:

```tsx

  // Models (Phase 3, S44): the engine checks what can run now each time the page opens, and on
  // Check again.
  const checkModels = () => { const n = ++sent.current; pace(() => setModelsCheck({ n })); };
  const show = (s: Screen) => {
    setScreen(s);
    if (s === "models") checkModels();
  };
```

  Then replace

```tsx
          {(["editor", "add", "review", "jobs"] as const).map((s) => (
            <button key={s} type="button" aria-current={screen === s ? "page" : undefined} onClick={() => setScreen(s)}
```

  with

```tsx
          {(["editor", "add", "review", "jobs", "models"] as const).map((s) => (
            <button key={s} type="button" aria-current={screen === s ? "page" : undefined} onClick={() => show(s)}
```

  Then below these lines

```tsx
            onResume={() => { const n = ++sent.current; pace(() => setQueueResume({ n })); }} />
        </section>
      )}
```

  add:

```tsx
      {generate && screen === "models" && (
        <section aria-label="Models" className="min-h-0 flex-1">
          <ModelsPage models={modelsOut ?? null} onCheck={checkModels} />
        </section>
      )}
```

- [ ] **Step 9: Run the checks; they pass.** `make check`. Expected:
  `1237 passed, 7 skipped, 45 deselected` twice, `Test Files  24 passed (24)`,
  `Tests  115 passed (115)`, `All checks passed!` and `no leaks found`. `make e2e`. Expected:
  `40 passed, 1249 deselected`.
- [ ] **Step 10: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(ui): 🤖 the Models page marks each configured model usable now or why not, and greys the catalog's other entries with what to add

The Models screen (spec §11.1, §19.2; S44), beside Add, Review and Jobs
where the engine makes things: each task's models as Review's pickers
name them (choiceLabel), with the catalog's one-liner and "usable now"
or the engine's reason, then each catalog entry no model points at,
greyed, with how to install it and "add it to vid2sub.toml". The page
asks each time it opens and on Check again, says so politely while the
engine checks, keeps the last lists meanwhile, and shows a failed check
as an alert. Usable or not is said in words, never colour alone
(§19.3); names and reasons are plain text (§6.3).

The new tests failed first: "src/components/ModelsPage.test.ts(5,15):
error TS2305: Module '"@/types"' has no exported member 'ModelsView'."
from make test-js, and the Playwright tests timed out waiting for
get_by_test_id("nav-models") (2 failed).

Docs read: Playwright for Python's expect (to_have_text with a list
matches each element in order; to_be_enabled); React's
renderToStaticMarkup (react-dom/server) for the component tests.

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md Task 8
Co-Authored-By: <the model's own line>
```

  `git add frontend/src/lib/models.ts frontend/src/lib/models.test.ts
  frontend/src/components/ModelsPage.tsx frontend/src/components/ModelsPage.test.ts
  frontend/src/types.ts frontend/src/App.tsx tests/e2e/test_models.py`,
  `git commit -F .git/COMMIT_MSG`, then `git log -1 --format='%(trailers)'` shows `Plan:`.
- [ ] **Step 11: Review, look forward, close.** The Tier 2 review from `$(cat .git/TASK_BASE)`
  (`AGENTS.md`, *Reviews*). Worth the reviewers' time: that nothing on the page, in a reason or
  in the failed check's notice names a path, a token or a key (§6.8); that the check never runs
  on the event loop or in Pages; that the server still imports only what Pages has
  (`tests/test_pages_imports.py`). The forward review over Task 9 (its candidate shows here as
  any candidate does), Task 11 (the README's Models page; the architecture diagram's Phase 3
  screens) and Task 12; the docs this task made untrue (no doc quotes `vid2sub models`' old "not
  in vid2sub.toml"). Then the close, its own commit, holding this plan with this task's boxes
  ticked and **Now** set to ``Task 9: The `faster-whisper` engine, open.``, and the spec's S44 row
  with "Phase and task" set to `Phase 3, Task 8`, its Proof to `` `tests/test_models.py`;
  `tests/test_web_models.py`; Playwright (`tests/e2e/test_models.py`) ``, and its status to
  `built`. The message, in `.git/CLOSE_MSG`:

```text
docs(plan): 🤖 close Task 8: The Models page

Drift: none
Rulings: none
Phase-end: none
Forward: none
Tier: 2
Rounds: none
Findings: none

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md Task 8
Co-Authored-By: <the model's own line>
```

  `git add docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md
  docs/superpowers/specs/2026-10-14-vid2sub-design.md`, `git commit -F .git/CLOSE_MSG`.

***

### Task 9: The `faster-whisper` engine

**Tier:** 2 · **Scenarios:** S45

Rebuilt on the finished Phase 2 (2026-10-24): the listing below replayed as written, with its
counts and lock lines as run there, then Review Focus 5's round (Steps 16–20) and a pin of
English's route against Phase 2 Task 20's Qwen3-ASR on the Spark (Steps 21–23).

**Why it is built this way** (read 2026-10-24):
- **No test downloads a model:** the WhisperModel is a fake whose Segment, Word and
  TranscriptionInfo have faster-whisper 1.2.1's fields (`faster_whisper/transcribe.py` at the
  v1.2.1 tag, still PyPI's newest, released 2025-10-31); with the `whisper` extra installed, a
  test checks them against the real dataclasses.
- **A first run with no network fails at once, and fails the episode.** faster-whisper 1.2.1's
  `download_model` calls `huggingface_hub.snapshot_download` and catches nothing; with no
  network huggingface_hub 2.2 gives up through its own timeouts (10 s, `HF_HUB_ETAG_TIMEOUT`)
  with `LocalEntryNotFoundError`, a `FileNotFoundError`. The engine turns that into an
  `unavailable` error naming the download, its size and `vid2sub doctor`: a `connection` error
  would make the pipeline retry for `wait_on_connection_s` (ten minutes in the CLI, 30 s in the
  app: Task 6) and then pause the queue.
  A model already downloaded is loaded from its cache folder, so later runs never ask the
  network (`WhisperModel` takes a directory as it is).
- **The GPU's libraries are looked for before the GPU is chosen,** on Linux too: CTranslate2
  loads cuBLAS through `dlopen("libcublas.so.12")` (`LoadLibraryA("cublas64_12.dll")` on Windows,
  after `CUDA_PATH`'s `bin`), and links cuDNN's `libcudnn.so` shim, which loads its parts only
  when first used. So a GPU without them runs on the CPU in int8, with a warning naming what is
  missing and `vid2sub doctor`, rather than failing in the library mid-episode; a library that
  fails anyway is named, never its message, which can hold a path.
- **English keeps a plain `qwen3-asr-1.7b` step,** so the Spark's Qwen3-ASR (Phase 2 Task 20,
  `parser = "qwen3-asr"`) comes before the Mac's, as §11.2 has it for Cantonese; English's
  "(Mac)" in §11.2 predates the Spark serving it (Decision 19, a spec change).
- **Not checked here:** no NVIDIA GPU, so the Linux and Windows library names are from the
  sources above, not a real load; Task 12's manual run checks them.

**Files:**
- Create: `src/vid2sub/parse/fasterwhisper.py`, `src/vid2sub/engines/faster_whisper.py`
- Modify: `src/vid2sub/config.py` (`engine = "faster-whisper"`), `src/vid2sub/engines/registry.py`,
  `src/vid2sub/catalog.py` (the Whisper entries' `default_model`, `runs_on` and `install`;
  English's route in §11.2's order, now that this machine can run turbo),
  `src/vid2sub/detect.py` (`whisper_available`, the engine's candidates),
  `src/vid2sub/commands/doctor.py` (faster-whisper and the GPU's libraries), `pyproject.toml`
  and `uv.lock` (the `whisper` and `nvidia` extras), `src/vid2sub/example.toml` and
  `vid2sub.example.toml` (a commented entry), `README.md` (`make readme`), `tests/README.md`
  (`VID2SUB_LIVE_WHISPER`), `.github/workflows/ci.yml` (the floor job runs the new parser's
  tests)
- Test: `tests/test_parse_fasterwhisper.py`, `tests/test_faster_whisper_engine.py`,
  `tests/test_catalog.py`, `tests/test_detect.py`, `tests/test_doctor_config.py`
- Modify at the close: this plan; the spec (S45's "Phase and task"); `docs/architecture.md`
  (faster-whisper drawn as built)

**Interfaces:**
- Consumes: the Engine protocol (`engines.base.Engine`, `Chunk.float32`, `ChunkResult`,
  `EngineError`, `ModelStamp`); `parse.ParsedChunk`, `ParseError`, `parse.words.ms`,
  `tokens_to_words`; `subs.langs.LANGS`; `catalog.CATALOG`; `config.ModelEntry`,
  `is_local`; `detect.candidates`; `commands.doctor.Check`; `pipeline.run_one`,
  `RunContext`, `RunOptions` (the no-fallback test). From faster-whisper 1.2.1:
  `WhisperModel(model_size_or_path, device=, compute_type=)`, `WhisperModel.transcribe(audio,
  language=, initial_prompt=, word_timestamps=, vad_filter=) -> (generator of Segment,
  TranscriptionInfo)`, `WhisperModel.detect_language(audio) -> (language, probability,
  [(language, probability), …])`, `faster_whisper.utils.download_model(size_or_id,
  local_files_only=True)`; `ctranslate2.get_cuda_device_count()`.
- Produces:
  - `vid2sub.parse.fasterwhisper.parse_faster_whisper(data: Any) -> ParsedChunk` (pure): `data`
    is `{"language", "language_probability", "all_language_probs", "segments": [{"start",
    "end", "text", "avg_logprob", "compression_ratio", "no_speech_prob", "words": [{"start",
    "end", "word", "probability"}]}]}` (times in seconds); `ParseError` for any other shape
  - `vid2sub.engines.faster_whisper` (as Step 18 leaves it): `WINDOWS_LIBRARIES =
    ("cublas64_12.dll", "cudnn64_9.dll")`, `LINUX_LIBRARIES = ("libcublas.so.12",
    "libcudnn_ops.so.9", "libcudnn_cnn.so.9")`; `can_load(library: str) -> bool` (ctypes);
    `missing_cuda_libraries(environ=os.environ, *, platform=sys.platform) -> list[str]` (on
    Windows the DLLs no folder on PATH or `CUDA_PATH`'s `bin` holds; on Linux the libraries
    the loader can't open; elsewhere `[]`); `cuda_devices() -> int`;
    `device_for(devices: int, missing: Sequence[str]) -> tuple[str, str]` (`("cuda",
    "float16")` or `("cpu", "int8")`); `model_path(model: str) -> str | None` (the cached
    snapshot's folder, never the network); `hf_revision(model: str) -> str`; `FIRST_RUN`,
    `GPU_FIX`, `DOCTOR`, `INSTALL`;
    `class FasterWhisperEngine: __init__(self, name: str, entry: ModelEntry, *,
    model_factory: Callable[..., Any] | None = None)`, `name = "faster-whisper"`,
    `supports_prompt = True`, `max_chunk_s` from the catalog (300), `model_id` (the entry's
    `model`, else the catalog's `default_model`: `large-v3` or `large-v3-turbo`), and the
    protocol's `transcribe`, `detect_language`, `stamp`, `close`; `device` (`"cuda"` or
    `"cpu"` once loaded). Every failure is an `EngineError("unavailable", …)`: "faster-whisper
    couldn't download its model, which its first run needs" (hint `FIRST_RUN`), "faster-whisper
    couldn't load the GPU's cuDNN 9 library" (or cuBLAS 12; hint `GPU_FIX`), else what failed
    and the exception's type (hint `DOCTOR`)
  - `config.ModelEntry.engine: Literal["mlx-qwen3-asr", "faster-whisper"] | None`; a
    faster-whisper entry's catalog must be a local Whisper model; it is local (in-process)
  - `catalog.CatalogEntry.default_model` for `whisper-large-v3` (`"large-v3"`) and
    `whisper-large-v3-turbo` (`"large-v3-turbo"`)
  - `catalog.Step = str | tuple[str, Literal["endpoint", "in-process"]]`: a route step is a
    catalog id (anywhere, endpoints first, as before) or a catalog id and where it runs.
    English's route is turbo on an endpoint (the Spark) → `qwen3-asr-1.7b` (anywhere,
    endpoints first: the Spark's, then the Mac's; Decision 19) → turbo in-process (faster-whisper) →
    `whisper-large-v3` → `qwen3-asr-0.6b` → OpenAI, §11.2's order on every system; the other rows
    are M1's, which already follow §11.2
  - `detect.whisper_available() -> bool`; `detect.candidates` gives a faster-whisper model as
    an `in-process` candidate, unavailable with "install vid2sub[whisper] (vid2sub[nvidia] for
    an NVIDIA GPU)" without the extra
  - `commands.doctor._whisper(environ, *, platform: str = sys.platform) -> list[Check]`:
    `faster-whisper` (installed, else how to install; not shown on a Mac without it),
    `NVIDIA GPU` (none seen: the CPU) or `CUDA libraries` (as Step 18 names it: "cuBLAS 12 and
    cuDNN 9 found; N NVIDIA GPU(s) seen", or the missing libraries with `CUDA_FIX` on Windows
    or `LINUX_CUDA_FIX`, and the LD_LIBRARY_PATH note on Linux); every one a warning
  - Extras: `whisper = ["faster-whisper>=1.2.1"]`; `nvidia` adds `nvidia-cublas-cu12>=12.4` and
    `nvidia-cudnn-cu12>=9,<10` on Windows and Linux
  - What Task 10 needs: a CI job on Windows and Linux that runs `uv sync --group dev --extra
    whisper` (so the field check against the real library runs, not skips) and the suite; the
    real model stays out of CI (`VID2SUB_LIVE_WHISPER=1` is opt-in, about 1.6 GB on first run).

The counts below are the assembled Phase 3's, with Tasks 1–8 in before this task.

- [ ] **Step 0: Record the base:** `git rev-parse HEAD > .git/TASK_BASE`.
- [ ] **Step 1: Write the failing test,** `tests/test_parse_fasterwhisper.py`:

```python
"""faster-whisper's segments, as the engine hands them over, into vid2sub's words (spec §9.2).

Shaped like faster-whisper 1.2.1's Segment, Word and TranscriptionInfo (transcribe.py): times in
seconds, each word's text with Whisper's leading space, `all_language_probs` only when the
language was detected.
"""

import pytest

from vid2sub.parse import ParseError
from vid2sub.parse.fasterwhisper import parse_faster_whisper


def word(text, start, end, p=0.9):
    return {"word": text, "start": start, "end": end, "probability": p}


def segment(text, start, end, words):
    return {"start": start, "end": end, "text": text, "avg_logprob": -0.2,
            "compression_ratio": 1.3, "no_speech_prob": 0.01, "words": words}


EN = {"language": "en", "language_probability": 0.98,
      "all_language_probs": [["en", 0.98], ["de", 0.01]],
      "segments": [segment(" Hello, world.", 0.0, 2.0,
                           [word(" Hello,", 0.0, 0.42, 0.95), word(" world.", 0.5, 0.95)])]}


def test_segments_become_words_in_milliseconds_with_whispers_leading_spaces():
    parsed = parse_faster_whisper(EN)
    assert (parsed.language, parsed.language_probs) == ("en", {"en": 0.98, "de": 0.01})
    (seg,) = parsed.segments
    assert [(w.text, w.start_ms, w.end_ms, w.prob) for w in seg.words] == [
        (" Hello,", 0, 420, 0.95), (" world.", 500, 950, 0.9)]
    assert (seg.text, seg.start_ms, seg.end_ms) == (" Hello, world.", 0, 2000)
    assert (seg.avg_logprob, seg.compression_ratio, seg.no_speech_prob) == (-0.2, 1.3, 0.01)


def test_cjk_words_stand_alone_and_closing_punctuation_joins_the_word_before():
    data = {"language": "ja", "language_probability": 1.0, "all_language_probs": None,
            "segments": [segment("こんにちは。", 0.0, 1.2,
                                 [word("こん", 0.0, 0.4), word("にちは", 0.4, 1.0),
                                  word("。", 1.0, 1.1)])]}
    (seg,) = parse_faster_whisper(data).segments
    assert [w.text for w in seg.words] == ["こん", "にちは。"]
    assert seg.text == "".join(w.text for w in seg.words) == "こんにちは。"


def test_a_language_given_to_the_model_has_only_its_own_probability():
    data = {**EN, "language": "ja", "language_probability": 1, "all_language_probs": None}
    assert parse_faster_whisper(data).language_probs == {"ja": 1.0}


def test_a_language_vid2sub_does_not_know_is_no_language_but_its_votes_are_kept():
    data = {**EN, "language": "fr", "all_language_probs": [["fr", 0.9], ["en", 0.1]]}
    parsed = parse_faster_whisper(data)
    assert parsed.language is None and parsed.language_probs == {"fr": 0.9, "en": 0.1}


def test_times_are_rounded_once_to_whole_milliseconds():
    data = {**EN, "segments": [segment(" Hi.", 0.1 + 0.2, 1.0000000000000002,
                                       [word(" Hi.", 0.30000000000000004, 0.7004)])]}
    (seg,) = parse_faster_whisper(data).segments
    assert (seg.start_ms, seg.end_ms, seg.words[0].start_ms, seg.words[0].end_ms) == (
        300, 1000, 300, 700)


@pytest.mark.parametrize("words", [None, []])
def test_a_segment_without_words_is_unaligned_and_keeps_its_text(words):
    data = {**EN, "segments": [segment(" Music.", 3.0, 5.0, words)]}
    (seg,) = parse_faster_whisper(data).segments
    assert (seg.words, seg.text, seg.start_ms, seg.end_ms) == ((), " Music.", 3000, 5000)


def test_a_word_with_a_broken_character_makes_its_segment_unaligned():
    data = {**EN, "segments": [segment("你好", 0.0, 1.0, [word("�", 0.0, 0.5),
                                                          word("好", 0.5, 1.0)])]}
    (seg,) = parse_faster_whisper(data).segments
    assert seg.words == () and seg.text == "你好"


def test_a_word_with_no_time_sits_at_the_previous_words_end():
    data = {**EN, "segments": [segment(" Hello, world.", 0.0, 2.0,
                                       [word(" Hello,", 0.0, 0.42), word(" world.", None, None)])]}
    (seg,) = parse_faster_whisper(data).segments
    assert [(w.start_ms, w.end_ms, w.timed) for w in seg.words] == [(0, 420, True),
                                                                   (420, 420, False)]


def test_a_segment_ending_before_it_starts_ends_where_it_starts():
    data = {**EN, "segments": [segment(" Hi.", 2.0, 1.5, [word(" Hi.", 2.0, 2.0)])]}
    (seg,) = parse_faster_whisper(data).segments
    assert (seg.start_ms, seg.end_ms) == (2000, 2000)


def test_no_speech_is_no_segments():
    data = {**EN, "segments": []}
    assert parse_faster_whisper(data).segments == ()


@pytest.mark.parametrize("data", [
    None, [], {"language": "en"}, {"segments": "nope"}, {"segments": ["nope"]},
    {**EN, "all_language_probs": "nope"}, {**EN, "all_language_probs": [["en"]]},
    {**EN, "all_language_probs": [["en", "high"]]}])
def test_anything_else_is_refused_as_not_faster_whispers(data):
    with pytest.raises(ParseError):
        parse_faster_whisper(data)
```

- [ ] **Step 2: Run it; watch it fail.** `uv run pytest tests/test_parse_fasterwhisper.py -q`.
  Expected: `E   ModuleNotFoundError: No module named 'vid2sub.parse.fasterwhisper'` and
  `1 error`.
- [ ] **Step 3: Write the code,** `src/vid2sub/parse/fasterwhisper.py`:

```python
"""faster-whisper's segments → a ParsedChunk (spec §9.2, §9.5).

The engine hands over plain data, read from faster-whisper 1.2.1's Segment, Word and
TranscriptionInfo: each segment's start, end, text, avg_logprob, compression_ratio and
no_speech_prob, and its words (`word`, `start`, `end`, `probability`; `word_timestamps=True`),
times in seconds; with the run's `language` and, only when the model detected it,
`all_language_probs` (each language and its probability). A word keeps Whisper's leading space;
the words are merged as whisper.cpp's are (`tokens_to_words`), so a CJK character stands alone and
closing punctuation joins the word before it. A segment the model gave no words, or one with
U+FFFD in a word, is unaligned rather than wrong. Pure, like every parser (spec §3.2).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from vid2sub.parse import ParsedChunk, ParseError
from vid2sub.parse.words import ms, tokens_to_words
from vid2sub.subs import langs
from vid2sub.subs.model import Segment


def _probabilities(data: Mapping[str, Any], language: Any) -> dict[str, float]:
    pairs = data.get("all_language_probs")
    if pairs is None:
        p = data.get("language_probability")
        if isinstance(language, str) and language and isinstance(p, (int, float)) \
                and not isinstance(p, bool) and math.isfinite(p):
            return {language: float(p)}
        return {}
    if not isinstance(pairs, (list, tuple)):
        raise ParseError("all_language_probs is not a list")
    probs = {}
    for pair in pairs:
        if (not isinstance(pair, (list, tuple)) or len(pair) != 2 or not isinstance(pair[0], str)
                or isinstance(pair[1], bool) or not isinstance(pair[1], (int, float))):
            raise ParseError("all_language_probs holds something that isn't a language and "
                             "its probability")
        probs[pair[0]] = float(pair[1])
    return probs


def parse_faster_whisper(data: Any) -> ParsedChunk:
    if not isinstance(data, Mapping) or not isinstance(data.get("segments"), list):
        raise ParseError("not faster-whisper's segments")
    raw = data.get("language")
    probs = _probabilities(data, raw)
    language = raw if raw in langs.LANGS else None
    segments = []
    for seg in data["segments"]:
        if not isinstance(seg, Mapping):
            raise ParseError("a faster-whisper segment is not an object")
        s_start = ms(seg.get("start")) or 0
        s_end = ms(seg.get("end"))
        s_end = s_start if s_end is None or s_end < s_start else s_end
        tokens = [(str(w.get("word", "")), ms(w.get("start")), ms(w.get("end")),
                   w.get("probability"))
                  for w in seg.get("words") or [] if isinstance(w, Mapping)]
        words = tokens_to_words(tokens, start_ms=s_start)
        if any("�" in w.text for w in words):
            words = []
        text = "".join(w.text for w in words) if words else str(seg.get("text", ""))
        segments.append(Segment(text=text, start_ms=s_start, end_ms=s_end, words=tuple(words),
                                avg_logprob=seg.get("avg_logprob"),
                                no_speech_prob=seg.get("no_speech_prob"),
                                compression_ratio=seg.get("compression_ratio")))
    return ParsedChunk(tuple(segments), language, probs)
```

  In `.github/workflows/ci.yml`'s `floor` job, replace the line
  `tests/test_parse_openai_qwen.py tests/test_catalog.py` with the two lines
  `tests/test_parse_openai_qwen.py tests/test_parse_fasterwhisper.py` and
  `tests/test_catalog.py` (same indentation).
- [ ] **Step 4: Run the checks; they pass.** `uv run pytest tests/test_parse_fasterwhisper.py
  tests/test_purity.py -q` first (`20 passed`), then the guard checks, then `make check`.
  **Guard checks**, each reverted and restored: add `import threading` below `import math` in
  the parser (`uv run pytest tests/test_purity.py -q`: `FAILED
  …test_pure_modules_import_only_the_standard_library_pydantic_and_subtitle_libraries`);
  replace `if any("�" in w.text for w in words):` with `if False:` (`FAILED
  …test_a_word_with_a_broken_character_makes_its_segment_unaligned`). `make check`. Expected:
  `1256 passed, 7 skipped, 45 deselected` twice, `Test Files  24 passed (24)`,
  `Tests  115 passed (115)`, `All checks passed!` and `no leaks found`.
- [ ] **Step 5: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(parse): 🤖 faster-whisper's segments and words parse into vid2sub's words, purely

vid2sub.parse.fasterwhisper.parse_faster_whisper (spec §9.2, §9.5) takes
the plain data the engine will hand over, read from faster-whisper
1.2.1's Segment (start, end, text, avg_logprob, compression_ratio,
no_speech_prob, words), Word (start, end, word, probability) and
TranscriptionInfo (language, language_probability, all_language_probs,
the last only when the language was detected). Times in seconds become
integer milliseconds rounded once; words keep Whisper's leading space and
are merged as whisper.cpp's are, so CJK characters stand alone and
closing punctuation joins the word before; a segment with no words, or a
U+FFFD in a word, is unaligned. A language vid2sub doesn't know is no
language, but its probabilities are kept. CI's floor job (Python 3.12,
pydantic 2.10.5) runs the new tests with the other pure ones.

The new tests failed first with: ModuleNotFoundError: No module named
'vid2sub.parse.fasterwhisper'. With `import threading` added to the
parser, test_purity fails; without the U+FFFD rule, its test fails.

Docs read: faster-whisper 1.2.1 on PyPI (released 2025-10-31; needs
ctranslate2>=4,<5) and its source, faster_whisper/transcribe.py at the
v1.2.1 tag (the Word, Segment and TranscriptionInfo dataclasses; transcribe
returns a generator of segments and the info) and README.md (word.word,
word.start, word.end; the generator runs the model as it is read).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md Task 9
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/parse/fasterwhisper.py tests/test_parse_fasterwhisper.py
  .github/workflows/ci.yml`, `git commit -F .git/COMMIT_MSG`, then
  `git log -1 --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 6: Write the failing tests,** `tests/test_faster_whisper_engine.py`:

```python
"""faster-whisper in-process (spec §9.5, S45), against a fake model shaped like 1.2.1's.

No test here downloads a model: the WhisperModel is a fake whose segments, words and info have
faster-whisper 1.2.1's fields (faster_whisper/transcribe.py), and a test checks those fields
against the real library when the `whisper` extra is installed.
"""

import dataclasses
import os
import sys
from dataclasses import dataclass
from typing import ClassVar

import numpy as np
import pytest

from vid2sub.config import Config, ConfigError, Endpoint, ModelEntry, is_local, load_config
from vid2sub.engines import faster_whisper as fw
from vid2sub.engines.base import Chunk, EngineError
from vid2sub.engines.clients import KeyRing, RunPolicy
from vid2sub.engines.registry import make_engine

TURBO = ModelEntry(catalog="whisper-large-v3-turbo", engine="faster-whisper")


@dataclass
class Word:
    start: float
    end: float
    word: str
    probability: float


@dataclass
class Segment:
    id: int
    seek: int
    start: float
    end: float
    text: str
    tokens: list
    avg_logprob: float
    compression_ratio: float
    no_speech_prob: float
    words: list | None
    temperature: float | None


@dataclass
class TranscriptionInfo:
    language: str
    language_probability: float
    duration: float
    duration_after_vad: float
    all_language_probs: list | None
    transcription_options: object
    vad_options: object


def hello(start=0.0):
    return Segment(0, 0, start, start + 1.0, " Hello, world.", [50364], -0.2, 1.3, 0.01,
                   [Word(start, start + 0.42, " Hello,", 0.95),
                    Word(start + 0.5, start + 0.95, " world.", 0.9)], 0.0)


class FakeModel:
    """Records what the engine asks; its segments are a generator, as faster-whisper's are."""

    made: ClassVar[list[tuple[tuple, dict]]] = []

    def __init__(self, *args, **kwargs):
        FakeModel.made.append((args, kwargs))
        self.calls: list[tuple[np.ndarray, dict]] = []
        self.read = 0

    def transcribe(self, audio, **kwargs):
        self.calls.append((audio, kwargs))

        def segments():
            self.read += 1
            yield hello()

        probs = None if kwargs.get("language") else [("ja", 0.97), ("zh", 0.02)]
        return segments(), TranscriptionInfo(kwargs.get("language") or "ja", 1.0, 1.0, 1.0,
                                             probs, None, None)

    def detect_language(self, audio=None, **kwargs):
        self.calls.append((audio, kwargs))
        return "ja", 0.97, [("ja", 0.97), ("zh", 0.02), ("en", 0.01)]


@pytest.fixture(autouse=True)
def no_gpu(monkeypatch):
    FakeModel.made = []
    monkeypatch.setattr(fw, "cuda_devices", lambda: 0)
    monkeypatch.setattr(fw, "hf_revision", lambda model: "0123456789abcdef")


def chunk(seconds=1.0):
    return Chunk(index=0, samples=np.zeros(int(16_000 * seconds), dtype=np.int16),
                 encode=lambda s: b"")


def engine(entry=TURBO):
    return fw.FasterWhisperEngine("local-turbo", entry, model_factory=FakeModel)


def test_the_engine_asks_for_words_with_no_vad_and_gives_the_language_and_the_prompt():
    e = engine()
    result = e.transcribe(chunk(), language="ja", prompt="工藤新一.")
    (model,) = [e._model]
    ((audio, kwargs),) = model.calls
    assert kwargs == {"language": "ja", "initial_prompt": "工藤新一.", "word_timestamps": True,
                      "vad_filter": False}
    assert audio.dtype == np.float32 and audio.shape == (16_000,)
    assert model.read == 1  # the generator was read: that is when faster-whisper transcribes
    (seg,) = result.parsed.segments
    assert [w.text for w in seg.words] == [" Hello,", " world."] and seg.end_ms == 1000
    assert result.parsed.language == "ja" and result.parsed.language_probs == {"ja": 1.0}


def test_no_prompt_is_no_initial_prompt_and_no_language_is_detected_by_the_model():
    e = engine()
    result = e.transcribe(chunk(), language=None, prompt="")
    assert e._model.calls[0][1]["initial_prompt"] is None
    assert e._model.calls[0][1]["language"] is None
    assert result.parsed.language_probs == {"ja": 0.97, "zh": 0.02}


def test_detecting_the_language_gives_every_languages_probability():
    e = engine()
    assert e.detect_language(chunk()) == {"ja": 0.97, "zh": 0.02, "en": 0.01}
    assert e._model.calls[0][0].dtype == np.float32


def test_the_catalog_entry_picks_the_ctranslate2_conversion_unless_the_entry_names_one():
    assert engine(ModelEntry(catalog="whisper-large-v3", engine="faster-whisper")).model_id \
        == "large-v3"
    assert engine(TURBO).model_id == "large-v3-turbo"
    assert engine(ModelEntry(engine="faster-whisper")).model_id == "large-v3-turbo"
    named = ModelEntry(catalog="whisper-large-v3", engine="faster-whisper",
                       model="Systran/faster-whisper-large-v3")
    assert engine(named).model_id == "Systran/faster-whisper-large-v3"


def test_on_the_cpu_the_model_runs_in_int8(monkeypatch):
    engine().transcribe(chunk(), language="en", prompt="")
    assert FakeModel.made == [(("large-v3-turbo",), {"device": "cpu", "compute_type": "int8"})]


def test_on_an_nvidia_gpu_with_its_libraries_the_model_runs_in_float16(monkeypatch):
    monkeypatch.setattr(fw, "cuda_devices", lambda: 1)
    monkeypatch.setattr(fw, "missing_cuda_libraries", list)
    engine().transcribe(chunk(), language="en", prompt="")
    assert FakeModel.made[0][1] == {"device": "cuda", "compute_type": "float16"}


def test_an_nvidia_gpu_without_cublas_on_path_leaves_the_model_on_the_cpu(monkeypatch):
    monkeypatch.setattr(fw, "cuda_devices", lambda: 1)
    monkeypatch.setattr(fw, "missing_cuda_libraries", lambda: ["cublas64_12.dll"])
    engine().transcribe(chunk(), language="en", prompt="")
    assert FakeModel.made[0][1] == {"device": "cpu", "compute_type": "int8"}


def test_cuda_libraries_are_looked_for_on_path_and_only_on_windows(tmp_path):
    first, second = tmp_path / "a", tmp_path / "b"
    first.mkdir()
    second.mkdir()
    environ = {"PATH": os.pathsep.join([str(first), "", str(second)])}
    assert fw.missing_cuda_libraries(environ, windows=True) == ["cublas64_12.dll",
                                                                "cudnn64_9.dll"]
    (second / "cublas64_12.dll").write_bytes(b"")
    (first / "cudnn64_9.dll").write_bytes(b"")
    assert fw.missing_cuda_libraries(environ, windows=True) == []
    assert fw.missing_cuda_libraries({"PATH": ""}, windows=False) == []


def test_the_model_is_loaded_once_and_released_on_close():
    e = engine()
    e.transcribe(chunk(), language="en", prompt="")
    e.detect_language(chunk())
    assert len(FakeModel.made) == 1
    e.close()
    e.transcribe(chunk(), language="en", prompt="")
    assert len(FakeModel.made) == 2


def test_the_stamp_names_the_model_and_its_snapshot():
    stamp = engine().stamp()
    assert (stamp.engine, stamp.model, stamp.label) == ("faster-whisper", "large-v3-turbo",
                                                       "large-v3-turbo@0123456789ab")


def test_without_the_whisper_extra_the_engine_says_how_to_install_it(monkeypatch):
    monkeypatch.setitem(sys.modules, "faster_whisper", None)
    with pytest.raises(EngineError) as err:
        fw.FasterWhisperEngine("w", TURBO).transcribe(chunk(), language="en", prompt="")
    assert err.value.kind == "unavailable" and "vid2sub[whisper]" in err.value.hint


def test_a_model_that_cannot_load_is_unavailable_and_names_no_path():
    def broken(*args, **kwargs):
        raise OSError("disk full at /private/models")

    e = fw.FasterWhisperEngine("w", TURBO, model_factory=broken)
    with pytest.raises(EngineError) as err:
        e.transcribe(chunk(), language="en", prompt="")
    assert err.value.kind == "unavailable" and "/private" not in str(err.value)


def test_a_model_that_fails_on_a_chunk_fails_it_without_its_message():
    class Failing(FakeModel):
        def transcribe(self, audio, **kwargs):
            raise RuntimeError("Library cublas64_12.dll is not found in C:\\Users\\someone")

    e = fw.FasterWhisperEngine("w", TURBO, model_factory=Failing)
    with pytest.raises(EngineError) as err:
        e.transcribe(chunk(), language="en", prompt="")
    assert err.value.kind == "unavailable" and "someone" not in str(err.value)
    assert "vid2sub doctor" in err.value.hint


def test_engines_are_built_from_the_config_entry():
    cfg = Config(endpoints={"spark": Endpoint(base_url="http://127.0.0.1:9/v1")},
                 models={"local-turbo": TURBO})
    built = make_engine("local-turbo", cfg, RunPolicy(), KeyRing())
    assert isinstance(built, fw.FasterWhisperEngine) and built.name == "faster-whisper"
    assert built.max_chunk_s == 300.0 and built.supports_prompt


def test_a_faster_whisper_model_in_vid2sub_toml_is_local_and_in_process(tmp_path):
    path = tmp_path / "vid2sub.toml"
    path.write_text('[models.local-turbo]\ncatalog = "whisper-large-v3-turbo"\n'
                    'engine = "faster-whisper"\n', encoding="utf-8")
    config = load_config(path)
    assert config.models["local-turbo"] == TURBO and is_local(TURBO, config)


@pytest.mark.parametrize("catalog", ["qwen3-asr-1.7b", "openai-whisper-1"])
def test_faster_whisper_runs_only_the_local_whisper_models(tmp_path, catalog):
    path = tmp_path / "vid2sub.toml"
    path.write_text(f'[models.x]\ncatalog = "{catalog}"\nengine = "faster-whisper"\n',
                    encoding="utf-8")
    with pytest.raises(ConfigError, match="faster-whisper"):
        load_config(path)


def test_the_fakes_have_the_fields_of_the_installed_faster_whisper():
    transcribe = pytest.importorskip("faster_whisper.transcribe")
    for fake, real in ((Word, transcribe.Word), (Segment, transcribe.Segment),
                       (TranscriptionInfo, transcribe.TranscriptionInfo)):
        assert [f.name for f in dataclasses.fields(fake)] == [
            f.name for f in dataclasses.fields(real)]


@pytest.mark.live
@pytest.mark.skipif(os.environ.get("VID2SUB_LIVE_WHISPER") != "1",
                    reason="needs VID2SUB_LIVE_WHISPER=1 and the whisper extra")
def test_faster_whisper_transcribes_real_speech_with_word_times():
    from helpers import SPEECH

    from vid2sub.media.decode import read_wav
    samples = read_wav(SPEECH)
    result = fw.FasterWhisperEngine("w", TURBO).transcribe(
        Chunk(index=0, samples=samples, encode=lambda s: b""), language="en", prompt="")
    words = [w for s in result.parsed.segments for w in s.words]
    assert len(words) > 10 and words[-1].end_ms > 5000
```

  Append to `tests/test_catalog.py`, after two blank lines:

```python
# Phase 3, Task 9: spec §11.2's order on every system, faster-whisper included


def machine(*, mac: bool, spark: bool, large: bool = True):
    """The Spark's turbo, faster-whisper's large-v3 (when `large`) and turbo on this machine,
    and the Mac's Qwen3-ASR when `mac`."""
    found = [cand("spark-turbo", "whisper-large-v3-turbo", available=spark,
                  reason="" if spark else "couldn't reach the server"),
             cand("local-turbo", "whisper-large-v3-turbo", kind="in-process")]
    if large:
        found.append(cand("local-large", "whisper-large-v3", kind="in-process"))
    if mac:
        found.append(cand("mac-qwen", "qwen3-asr-1.7b", kind="in-process"))
    return found


@pytest.mark.parametrize("lang, mac, spark, large, picked", [
    pytest.param("en", True, False, True, "mac-qwen", id="english-on-a-mac-with-the-spark-down"),
    pytest.param("en", True, True, True, "spark-turbo", id="english-with-the-spark-up"),
    pytest.param("en", False, False, True, "local-turbo", id="english-on-windows-or-linux"),
    pytest.param("yue", True, False, True, "mac-qwen", id="cantonese-on-a-mac"),
    pytest.param("yue", False, False, True, "local-large", id="cantonese-on-windows-or-linux"),
    pytest.param("zh", True, False, True, "mac-qwen", id="mandarin-on-a-mac"),
    pytest.param("zh", False, False, True, "local-large", id="mandarin-on-windows-or-linux"),
    pytest.param("zh", False, True, False, "spark-turbo", id="mandarin-turbo-on-the-spark"),
    pytest.param("zh", False, False, False, "local-turbo", id="mandarin-turbo-on-this-machine"),
    pytest.param("ja", True, False, True, "local-large", id="japanese-large-v3-first"),
    pytest.param("ja", True, False, False, "mac-qwen", id="japanese-then-qwen"),
    pytest.param("ja", False, True, False, "spark-turbo", id="japanese-turbo-on-the-spark"),
    pytest.param("ja", False, False, False, "local-turbo", id="japanese-turbo-on-this-machine"),
])
def test_the_routes_follow_the_spec_on_every_system(lang, mac, spark, large, picked):
    found = suggest(lang, machine(mac=mac, spark=spark, large=large), "transcribe",
                    allow_cloud=False)
    assert found.model == picked
```

  Append to `tests/test_detect.py`, after two blank lines:

```python
def test_faster_whisper_can_run_here_only_with_its_extra(monkeypatch):
    cfg = Config(models={"local-turbo": ModelEntry(catalog="whisper-large-v3-turbo",
                                                   engine="faster-whisper")})
    monkeypatch.setattr(d, "whisper_available", lambda: False)
    (cand,) = d.candidates(cfg, KeyRing(environ={}))
    assert (cand.kind, cand.available, cand.cloud) == ("in-process", False, False)
    assert "vid2sub[whisper]" in cand.reason
    monkeypatch.setattr(d, "whisper_available", lambda: True)
    assert d.candidates(cfg, KeyRing(environ={}))[0].available
```

- [ ] **Step 7: Run them; watch them fail.** `uv run pytest tests/test_faster_whisper_engine.py
  -q`. Expected: `E   ImportError: cannot import name 'faster_whisper' from 'vid2sub.engines'
  (…/src/vid2sub/engines/__init__.py)` and `1 error`. `uv run pytest tests/test_detect.py -q`.
  Expected: `pydantic_core._pydantic_core.ValidationError: 1 validation error for ModelEntry`
  (`Input should be 'mlx-qwen3-asr'`) and `1 failed, 11 passed`. `uv run pytest
  tests/test_catalog.py -q`. Expected: `FAILED tests/test_catalog.py::
  test_the_routes_follow_the_spec_on_every_system[english-on-a-mac-with-the-spark-down]`,
  `E       AssertionError: assert 'local-turbo' == 'mac-qwen'` and `1 failed, 25 passed` (the
  other twelve cases, every §11.2 row on a Mac and on Windows or Linux, pass already).
- [ ] **Step 8: Write the code.** In `pyproject.toml`, below the `mac = [...]` line in
  `[project.optional-dependencies]`, add:

```toml
# Whisper large-v3 and large-v3-turbo in-process through faster-whisper, on the CPU (spec §9.5).
whisper = ["faster-whisper>=1.2.1"]
# The same on an NVIDIA GPU: the CUDA 12 cuBLAS and cuDNN 9 runtime wheels faster-whisper's README
# names (Windows and Linux; their folders must be on PATH, or LD_LIBRARY_PATH, as doctor says).
nvidia = [
    "faster-whisper>=1.2.1",
    "nvidia-cublas-cu12>=12.4; sys_platform == 'win32' or sys_platform == 'linux'",
    "nvidia-cudnn-cu12>=9,<10; sys_platform == 'win32' or sys_platform == 'linux'",
]
```

  then `uv lock` (expected: `Added av v19.0.2`, `Added ctranslate2 v4.8.3`, `Added
  faster-whisper v1.2.1`, `Added nvidia-cublas-cu12 v12.9.2.10`, `Added nvidia-cuda-nvrtc-cu12
  v12.9.86`, `Added nvidia-cudnn-cu12 v9.27.0.42`, `Added tokenizers v0.23.3`; the lock file has
  `win_amd64` and `manylinux_2_27_x86_64` wheels for both NVIDIA packages, 553 MB and 743 MB on
  Windows). `uv sync --group dev` installs none of them: CI and `make check` run without the
  extras.

  `src/vid2sub/engines/faster_whisper.py`:

```python
"""Whisper in-process through faster-whisper, for Windows and Linux (spec §9.5, S45).

CTranslate2 conversions of Whisper large-v3 and large-v3-turbo: faster-whisper's `large-v3` and
`large-v3-turbo` from the catalog entry, or the converted model's Hugging Face id in the entry's
`model`. Words come from `word_timestamps=True`; `vad_filter=False`, since vid2sub's own VAD has
already chosen the speech (§8.6). On an NVIDIA GPU the model runs in float16, and otherwise on the
CPU in int8 (§9.5). CUDA on Windows needs the cuBLAS 12 DLLs on PATH (and cuDNN 9, which
faster-whisper's README names too): without them the GPU isn't used, and `vid2sub doctor` says
how to fix it. The import is lazy and the model is loaded once, on first use, and released by
`close` (§9.1; mlx imports cost seconds, an audio-router lesson). The revision in the version
stamp is the model's Hugging Face snapshot, read from the local cache only (§9.6). A failure is
named only by kind: the library's message can hold a path (§6.8).
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from vid2sub.catalog import CATALOG
from vid2sub.config import ModelEntry
from vid2sub.engines.base import Chunk, ChunkResult, EngineError, ModelStamp
from vid2sub.parse.fasterwhisper import parse_faster_whisper

CUDA_LIBRARIES = ("cublas64_12.dll", "cudnn64_9.dll")  # what CTranslate2 loads on Windows
DEFAULT_CATALOG = "whisper-large-v3-turbo"
INSTALL = "install vid2sub[whisper] (vid2sub[nvidia] for an NVIDIA GPU)"
DOCTOR = "`vid2sub doctor` checks the model's files and the GPU's libraries"


def missing_cuda_libraries(environ: Mapping[str, str] = os.environ, *,
                           windows: bool = os.name == "nt") -> list[str]:
    """The CUDA DLLs CTranslate2 needs that no folder on PATH holds: Windows only, where the
    DLLs must be on PATH; elsewhere the loader finds them, or fails at load, so none here."""
    if not windows:
        return []
    folders = [f for f in environ.get("PATH", "").split(os.pathsep) if f]
    return [lib for lib in CUDA_LIBRARIES
            if not any(os.path.isfile(os.path.join(f, lib)) for f in folders)]


def cuda_devices() -> int:
    """How many NVIDIA GPUs CTranslate2 sees (0 without the extra or a GPU)."""
    try:
        import ctranslate2
    except ImportError:
        return 0
    try:
        return int(ctranslate2.get_cuda_device_count())
    except Exception:  # noqa: BLE001 - no driver is no GPU
        return 0


def device_for(devices: int, missing: Sequence[str]) -> tuple[str, str]:
    """The device and compute type: an NVIDIA GPU in float16 when CTranslate2 sees one and its
    libraries are there, else the CPU in int8 (spec §9.5)."""
    return ("cuda", "float16") if devices > 0 and not missing else ("cpu", "int8")


def hf_revision(model: str) -> str:
    """The cached snapshot's hash, so a model update changes the version (§9.6), as the Qwen
    engine's hf_revision does; faster-whisper's own download_model maps a size to its repo."""
    try:
        from faster_whisper.utils import download_model

        path = Path(download_model(model, local_files_only=True))
        return path.name[:12] if path.name else "unknown"
    except Exception:  # noqa: BLE001 - an unstamped rendition beats a failed one
        return "unknown"


def _plain(segments: Any, info: Any) -> dict[str, Any]:
    """faster-whisper's Segment, Word and TranscriptionInfo as the parser's plain data. Reading
    `segments` runs the model: it is a generator."""
    return {
        "language": getattr(info, "language", None),
        "language_probability": getattr(info, "language_probability", None),
        "all_language_probs": getattr(info, "all_language_probs", None),
        "segments": [{"start": s.start, "end": s.end, "text": s.text,
                      "avg_logprob": s.avg_logprob, "compression_ratio": s.compression_ratio,
                      "no_speech_prob": s.no_speech_prob,
                      "words": [{"start": w.start, "end": w.end, "word": w.word,
                                 "probability": w.probability} for w in s.words or []]}
                     for s in segments],
    }


class FasterWhisperEngine:
    """One caller at a time: the model isn't documented as thread-safe."""

    name = "faster-whisper"
    supports_prompt = True

    def __init__(self, name: str, entry: ModelEntry, *,
                 model_factory: Callable[..., Any] | None = None):
        catalog = CATALOG.get(entry.catalog or DEFAULT_CATALOG)
        self.model_name = name
        self.model_id = (entry.model or (catalog.default_model if catalog else None)
                         or "large-v3-turbo")
        self.max_chunk_s = catalog.max_chunk_s if catalog else 300.0
        self._factory = model_factory
        self._model: Any = None

    def _load(self) -> Any:
        if self._model is None:
            factory = self._factory
            if factory is None:
                try:
                    from faster_whisper import WhisperModel
                except ImportError:
                    raise EngineError("unavailable", "faster-whisper isn't installed",
                                      hint=INSTALL) from None
                factory = WhisperModel
            device, compute = device_for(cuda_devices(), missing_cuda_libraries())
            try:
                self._model = factory(self.model_id, device=device, compute_type=compute)
            except Exception as err:  # noqa: BLE001 - any load failure: the model can't run
                raise EngineError(
                    "unavailable", f"faster-whisper couldn't load its model ({type(err).__name__})",
                    hint="check the network for the first download and free disk space; "
                         + DOCTOR) from None
        return self._model

    def transcribe(self, chunk: Chunk, *, language: str | None, prompt: str) -> ChunkResult:
        model = self._load()
        try:
            segments, info = model.transcribe(chunk.float32, language=language,
                                              initial_prompt=prompt or None,
                                              word_timestamps=True, vad_filter=False)
            data = _plain(segments, info)
        except Exception as err:  # noqa: BLE001 - CTranslate2 raises RuntimeError and others
            raise EngineError("unavailable",
                              f"faster-whisper failed on this chunk ({type(err).__name__})",
                              hint=DOCTOR) from None
        return ChunkResult(parse_faster_whisper(data))

    def detect_language(self, chunk: Chunk) -> dict[str, float]:
        model = self._load()
        try:
            language, probability, every = model.detect_language(chunk.float32)
        except Exception as err:  # noqa: BLE001 - as transcribe
            raise EngineError("unavailable",
                              f"faster-whisper couldn't detect the language ({type(err).__name__})",
                              hint=DOCTOR) from None
        return {str(code): float(p) for code, p in (every or [(language, probability)])}

    def stamp(self) -> ModelStamp:
        return ModelStamp(self.name, self.model_id, hf_revision(self.model_id))

    def close(self) -> None:
        self._model = None
```

  In `src/vid2sub/config.py`, replace
  `engine: Literal["mlx-qwen3-asr"] | None = None` with
  `engine: Literal["mlx-qwen3-asr", "faster-whisper"] | None = None`, and in `_validate`
  replace

```python
        if m.engine is not None:
            if m.task != "transcribe":
                raise ConfigError(f"{where}: in-process engines only transcribe")
            continue
```

  with

```python
        if m.engine is not None:
            if m.task != "transcribe":
                raise ConfigError(f"{where}: in-process engines only transcribe")
            if m.engine == "faster-whisper" and m.catalog is not None and (
                    CATALOG[m.catalog].family != "whisper" or CATALOG[m.catalog].cloud):
                raise ConfigError(f"{where}: faster-whisper runs whisper-large-v3 or "
                                  "whisper-large-v3-turbo")
            continue
```

  In `src/vid2sub/engines/registry.py`, below `from vid2sub.engines.endpoint import
  EndpointEngine`, add `from vid2sub.engines.faster_whisper import FasterWhisperEngine`, and
  below `return QwenMLXEngine(name, entry)`, add:

```python
    if entry.engine == "faster-whisper":
        return FasterWhisperEngine(name, entry)
```

  In `src/vid2sub/catalog.py`, in `class CatalogEntry`, replace
  `default_model: str | None = None` with

```python
    default_model: str | None = None  # an in-process engine's model when the entry names none
```

  In the `whisper-large-v3` entry, replace

```python
        runs_on="Windows/Linux (faster-whisper, M3); the Spark if local-ai adds it",
        install="a whisper.cpp server, or vid2sub[whisper] from M3",
        languages=("ja", "en", "zh", "ko", "yue")),
```

  with

```python
        runs_on="Windows/Linux (faster-whisper); the Spark if local-ai adds it",
        install="a whisper.cpp server, or vid2sub[whisper] (vid2sub[nvidia] for an NVIDIA GPU)",
        languages=("ja", "en", "zh", "ko", "yue"), default_model="large-v3"),
```

  and in the `whisper-large-v3-turbo` entry, replace

```python
        runs_on="the Spark (always loaded); Windows/Linux from M3",
        install="the Spark's endpoint, or vid2sub[whisper] from M3",
        languages=("en", "ja", "zh", "ko")),
```

  with

```python
        runs_on="the Spark (always loaded); Windows/Linux (faster-whisper)",
        install="the Spark's endpoint, or vid2sub[whisper] (vid2sub[nvidia] for an NVIDIA GPU)",
        languages=("en", "ja", "zh", "ko"), default_model="large-v3-turbo"),
```

  In the module docstring, replace

```python
`[models.*]` entries point at catalog ids. Routing is an ordered preference per source language:
the first model available now wins, and among equals the Spark's (an endpoint) wins over the
Mac's (in-process). The Spark's translation default is Gemma 4, resident with two slots; the only
Qwen chat model there is Dan's coder (council, 2026-10-14). Pure.
```

  with

```python
`[models.*]` entries point at catalog ids. Routing is an ordered preference per source language:
the first model available now wins, and among equals the Spark's (an endpoint) wins over this
machine's (in-process). A step can name where its model runs: English takes turbo on the Spark,
then the Mac's Qwen3-ASR, then turbo through faster-whisper on this machine, as §11.2 orders it.
The Spark's translation default is Gemma 4, resident with two slots; the only Qwen chat model
there is Dan's coder (council, 2026-10-14). Pure.
```

  Replace `TRANSCRIBE_ROUTES: dict[str, tuple[str, ...]] = {` with the two lines

```python
Step = str | tuple[str, Literal["endpoint", "in-process"]]  # a catalog id, anywhere or there only
TRANSCRIBE_ROUTES: dict[str, tuple[Step, ...]] = {
```

  replace English's route,

```python
    "en": ("whisper-large-v3-turbo", "qwen3-asr-1.7b", "whisper-large-v3", "qwen3-asr-0.6b",
           "openai-whisper-1"),
```

  with

```python
    "en": (("whisper-large-v3-turbo", "endpoint"), "qwen3-asr-1.7b",
           ("whisper-large-v3-turbo", "in-process"), "whisper-large-v3", "qwen3-asr-0.6b",
           "openai-whisper-1"),
```

  replace `TRANSLATE_ROUTE: tuple[str, ...] = (` with `TRANSLATE_ROUTE: tuple[Step, ...] = (`,
  and in `suggest`, replace

```python
    considered: list[tuple[str, str]] = []
    off_route = tuple(
        (o.name, f"not in the {task} route for {lang}; choose it with --model")
        for o in candidates if o.catalog not in route)
    for cid in route:
        matches = sorted((c for c in candidates if c.catalog == cid),
                         key=lambda c: 0 if c.kind == "endpoint" else 1)
```

  with

```python
    considered: list[tuple[str, str]] = []
    steps = [(s, None) if isinstance(s, str) else s for s in route]
    off_route = tuple(
        (o.name, f"not in the {task} route for {lang}; choose it with --model")
        for o in candidates if o.catalog not in {cid for cid, _ in steps})
    for cid, where in steps:
        matches = sorted((c for c in candidates
                          if c.catalog == cid and where in (None, c.kind)),
                         key=lambda c: 0 if c.kind == "endpoint" else 1)
```

  then `make readme` (the README's model table follows). In `src/vid2sub/detect.py`, above
  `def mlx_available() -> bool:`, add:

```python
def whisper_available() -> bool:
    return importlib.util.find_spec("faster_whisper") is not None


```

  and in `candidates`, below the `mlx-qwen3-asr` branch's `continue`, add:

```python
        if m.engine == "faster-whisper":
            ok = whisper_available()
            out.append(Candidate(name, m.catalog, "in-process", ok,
                                 "" if ok else "install vid2sub[whisper] (vid2sub[nvidia] for "
                                               "an NVIDIA GPU)"))
            continue
```

  In both `src/vid2sub/example.toml` and `vid2sub.example.toml` (they stay identical), below
  the `[models.mac-qwen]` entry's `engine = "mlx-qwen3-asr"` line, add:

```toml

# Whisper on this machine (Windows, Linux): install vid2sub[whisper], or vid2sub[nvidia] for an
# NVIDIA GPU. catalog = "whisper-large-v3" for Japanese; turbo for English.
# [models.local-whisper]
# catalog = "whisper-large-v3-turbo"
# engine = "faster-whisper"
```

  In `tests/README.md`, above the `VID2SUB_LIVE_SPARK=1` item, add:

```markdown
  - `VID2SUB_LIVE_WHISPER=1` with `uv sync --extra whisper`: faster-whisper's large-v3-turbo on
    the speech fixture, on the CPU or an NVIDIA GPU (downloads about 1.6 GB on first run).
```

- [ ] **Step 9: Run the checks; they pass.** `uv run pytest tests/test_faster_whisper_engine.py
  tests/test_detect.py tests/test_config.py tests/test_catalog.py tests/test_readme.py
  tests/test_qwen_engine.py -q` first (`90 passed, 1 skipped, 2 deselected`: the field check
  skips without the extra). Then once with the extra: `uv sync --group dev --extra whisper`
  (it installs faster-whisper 1.2.1, ctranslate2 4.8.3 and huggingface-hub 2.2.0, among
  others), `uv run --no-sync pytest tests/test_faster_whisper_engine.py -q` (`18 passed, 1
  deselected`: the fakes have faster-whisper 1.2.1's fields), then `uv sync --group dev` to go
  back. Then the
  guard checks, each reverted and restored, each with `uv run pytest
  tests/test_faster_whisper_engine.py -q`: in `config._validate`, replace `if m.engine ==
  "faster-whisper" and m.catalog is not None and (` with `if False and (` (a Qwen or a cloud
  catalog entry runs on faster-whisper: `2 failed`); in `device_for`, replace
  `if devices > 0 and not missing else` with `if devices > 0 else` (`FAILED
  …test_an_nvidia_gpu_without_cublas_on_path_leaves_the_model_on_the_cpu`); replace
  `vad_filter=False)` with `vad_filter=True)` (`FAILED
  …test_the_engine_asks_for_words_with_no_vad_and_gives_the_language_and_the_prompt`); put
  English's M1 route back (`uv run pytest tests/test_catalog.py -q`: `FAILED
  …[english-on-a-mac-with-the-spark-down]`). `make check`. Expected:
  `1287 passed, 8 skipped, 46 deselected` twice, `Test Files  24 passed (24)`,
  `Tests  115 passed (115)`, `All checks passed!` and `no leaks found`.
  The live test isn't run here: `VID2SUB_LIVE_WHISPER=1 make live` on a
  machine with the extra, which Task 12's manual run covers.
- [ ] **Step 10: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(engines): 🤖 faster-whisper transcribes in-process with word times, on the CPU in int8 or an NVIDIA GPU

vid2sub.engines.faster_whisper (spec §9.5, S45): FasterWhisperEngine is
the third in-process engine behind the Engine protocol, named
"faster-whisper". It loads faster-whisper's WhisperModel once, lazily,
with the catalog entry's CTranslate2 conversion (large-v3 or
large-v3-turbo, catalog.default_model) unless the entry's `model` names
one; transcribes each chunk's 16 kHz float32 samples with
word_timestamps=True, vad_filter=False, the language and the glossary
prompt as initial_prompt; reads the segment generator into plain data for
parse_faster_whisper; detects the language with every language's
probability; and stamps model@<snapshot>, read from the local Hugging
Face cache only (§9.6). It runs on an NVIDIA GPU in float16 when
CTranslate2 sees one and, on Windows, cuBLAS 12 and cuDNN 9 are on PATH,
and otherwise on the CPU in int8; a failure is named by kind only, with
doctor in its hint. vid2sub.toml takes `engine = "faster-whisper"` for
the local Whisper catalog models only; detect.candidates says it can run
when faster-whisper is installed, else "install vid2sub[whisper]". The
`whisper` extra is faster-whisper>=1.2.1; `nvidia` adds the CUDA 12
cuBLAS and cuDNN 9 runtime wheels on Windows and Linux (uv lock:
faster-whisper 1.2.1, ctranslate2 4.8.3, nvidia-cublas-cu12 12.9.2.10,
nvidia-cudnn-cu12 9.27.0.42 and its nvidia-cuda-nvrtc-cu12 12.9.86, each
with Windows and Linux wheels; huggingface-hub resolves to 2.2.0). The
catalog's Whisper entries and the README's table say so; the starter
vid2sub.toml shows the entry; tests/README names VID2SUB_LIVE_WHISPER=1.

With turbo now on this machine too, English's route follows §11.2:
turbo on the Spark, then the Mac's Qwen3-ASR, then faster-whisper's
turbo. The route named turbo once, so this machine's turbo came before
Qwen; a step can now name where its model runs (catalog.Step). The other
rows already follow §11.2: Cantonese and Mandarin take Qwen (the Spark,
then the Mac) before large-v3 and turbo; Japanese takes large-v3, then
Qwen, then turbo (the Spark's, then this machine's).

No test downloads a model: a fake WhisperModel has 1.2.1's Segment, Word
and TranscriptionInfo fields, and with the whisper extra installed
(uv sync --extra whisper) a test checked them against the real dataclasses
and passed. The live test, VID2SUB_LIVE_WHISPER=1, was not run here.

The new tests failed first with: ImportError: cannot import name
'faster_whisper' from 'vid2sub.engines', and test_the_routes_follow_the_
spec_on_every_system[english-on-a-mac-with-the-spark-down] with
AssertionError: assert 'local-turbo' == 'mac-qwen'. Guard checks, each
reverted and restored: without the config's rule a Qwen or cloud catalog
entry runs on faster-whisper; a GPU taken without its libraries;
vad_filter=True; English's M1 route: each makes its test fail.

Docs read: faster-whisper 1.2.1's transcribe.py (WhisperModel's
__init__(model_size_or_path, device, compute_type, …) and transcribe(audio,
language, initial_prompt, word_timestamps, vad_filter, …) signatures;
detect_language returns the language, its probability and every
language's; audio is a 16 kHz float array), utils.py (_MODELS: large-v3 is
Systran/faster-whisper-large-v3, large-v3-turbo is
mobiuslabsgmbh/faster-whisper-large-v3-turbo; download_model with
local_files_only=True returns the cached snapshot) and README.md (GPU:
cuBLAS for CUDA 12 and cuDNN 9; on Windows the libraries go in a folder on
PATH; the pip wheels nvidia-cublas-cu12 and nvidia-cudnn-cu12==9.*; CPU in
int8); CTranslate2 4.8 docs (get_cuda_device_count() returns the visible
GPUs; the Windows and Linux wheels run on the GPU with CUDA 12); spec
§11.2's routing table.

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md Task 9
Co-Authored-By: <the model's own line>
```

  `git add README.md pyproject.toml uv.lock src/vid2sub/catalog.py src/vid2sub/config.py
  src/vid2sub/detect.py src/vid2sub/engines/registry.py src/vid2sub/engines/faster_whisper.py
  src/vid2sub/example.toml vid2sub.example.toml tests/README.md tests/test_catalog.py
  tests/test_detect.py tests/test_faster_whisper_engine.py`, `git commit -F .git/COMMIT_MSG`, then
  `git log -1 --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 11: Write the failing test.** Append to `tests/test_doctor_config.py`, after two
  blank lines:

```python
# Phase 3, Task 9: faster-whisper, and the GPU's libraries on Windows (spec §9.5, S45)


@pytest.fixture
def whisper(monkeypatch):
    """faster-whisper installed, and as many NVIDIA GPUs as the test says."""
    from vid2sub import detect
    from vid2sub.engines import faster_whisper as fw

    def set_up(installed=True, gpus=0):
        monkeypatch.setattr(detect, "whisper_available", lambda: installed)
        monkeypatch.setattr(fw, "cuda_devices", lambda: gpus)
    return set_up


def by_name(checks):
    return {c.name: c for c in checks}


def test_doctor_says_how_to_install_faster_whisper_on_windows_and_linux(whisper):
    whisper(installed=False)
    for platform in ("win32", "linux"):
        (check,) = doctor._whisper({}, platform=platform)
        assert (check.name, check.ok, check.essential) == ("faster-whisper", False, False)
        assert "vid2sub[whisper]" in check.hint and "vid2sub[nvidia]" in check.hint
    assert doctor._whisper({}, platform="darwin") == []  # a Mac has Qwen3-ASR (vid2sub[mac])


def test_without_an_nvidia_gpu_doctor_says_faster_whisper_runs_on_the_cpu(whisper):
    whisper(gpus=0)
    checks = by_name(doctor._whisper({}, platform="win32"))
    assert checks["faster-whisper"].ok and checks["NVIDIA GPU"].ok
    assert "CPU" in checks["NVIDIA GPU"].detail


def test_a_windows_gpu_without_cublas_on_path_is_a_warning_that_says_how_to_fix_it(whisper,
                                                                                  tmp_path):
    whisper(gpus=1)
    checks = by_name(doctor._whisper({"PATH": str(tmp_path)}, platform="win32"))
    cublas = checks["cuBLAS 12"]
    assert (cublas.ok, cublas.essential) == (False, False)
    assert "cublas64_12.dll" in cublas.detail and "CPU" in cublas.detail
    assert "PATH" in cublas.hint and "vid2sub[nvidia]" in cublas.hint
    for dll in ("cublas64_12.dll", "cudnn64_9.dll"):
        (tmp_path / dll).write_bytes(b"")
    assert by_name(doctor._whisper({"PATH": str(tmp_path)}, platform="win32"))["cuBLAS 12"].ok


def test_on_linux_the_gpu_is_reported_without_a_path_check(whisper):
    whisper(gpus=2)
    checks = by_name(doctor._whisper({"PATH": ""}, platform="linux"))
    assert checks["cuBLAS 12"].ok and "2 NVIDIA GPU" in checks["cuBLAS 12"].detail
```

- [ ] **Step 12: Run it; watch it fail.** `uv run pytest tests/test_doctor_config.py -q`.
  Expected: `E       AttributeError: module 'vid2sub.commands.doctor' has no attribute
  '_whisper'` (four times) and `4 failed, 7 passed`.
- [ ] **Step 13: Write the code,** in `src/vid2sub/commands/doctor.py`. In the module docstring,
  replace

```python
Python, ffmpeg and ffprobe are essential; deno (YouTube), yt-dlp's age and the Mac extra are
warnings. Endpoints serving local models are asked for their model list (not with --offline);
cloud endpoints are never contacted. Keys are reported by presence only, never their values. A
check's hint is its fix, shown only when it fails; a note is advice shown either way (final
review: a passing Python printed "needs Python 3.12 or later"). The cache's size is shown
against its cap, never its path (spec §18.1, §6.8).
```

  with

```python
Python, ffmpeg and ffprobe are essential; deno (YouTube), yt-dlp's age, the Mac extra and, on
Windows and Linux, faster-whisper and the NVIDIA GPU's libraries are warnings: CUDA on Windows
needs the cuBLAS 12 DLLs on PATH, and without them faster-whisper runs on the CPU (spec §9.5).
Endpoints serving local models are asked for their model list (not with --offline); cloud
endpoints are never contacted. Keys are reported by presence only, never their values. A check's
hint is its fix, shown only when it fails; a note is advice shown either way (final review: a
passing Python printed "needs Python 3.12 or later"). The cache's size is shown against its cap,
never its path (spec §18.1, §6.8).
```

  Below `from vid2sub.engines import clients`, add
  `from vid2sub.engines import faster_whisper as fw`. In `checks`, below the `if sys.platform ==
  "darwin":` block (the `mlx-qwen3-asr` check), add `    out += _whisper(environ)` at the
  block's own indentation. Above `def _cache(config: Config) -> Check:`, add:

```python
CUDA_FIX = ("put the CUDA 12 cuBLAS and cuDNN 9 DLLs on PATH: install vid2sub[nvidia] and add "
            "the bin folders of its nvidia-cublas-cu12 and nvidia-cudnn-cu12 packages to PATH, "
            "or install NVIDIA's CUDA 12 toolkit and cuDNN 9; then start vid2sub again")


def _whisper(environ: Mapping[str, str], *, platform: str = sys.platform) -> list[Check]:
    """faster-whisper, on Windows and Linux (anywhere it's installed), and the GPU it would use."""
    installed = detecting.whisper_available()
    if not installed:
        if platform == "darwin":
            return []
        return [Check("faster-whisper", False, "not installed",
                      "for Whisper on this machine: install vid2sub[whisper] (vid2sub[nvidia] "
                      "for an NVIDIA GPU)", essential=False)]
    out = [Check("faster-whisper", True, "installed", essential=False)]
    gpus = fw.cuda_devices()
    if gpus == 0:
        out.append(Check("NVIDIA GPU", True, "none seen: faster-whisper runs on the CPU (int8)",
                         essential=False))
        return out
    missing = fw.missing_cuda_libraries(environ, windows=platform == "win32")
    if missing:
        out.append(Check("cuBLAS 12", False, f"{', '.join(missing)} not on PATH: faster-whisper "
                         "runs on the CPU", CUDA_FIX, essential=False))
    else:
        out.append(Check(
            "cuBLAS 12", True, f"{gpus} NVIDIA GPU(s) seen", essential=False,
            note="" if platform == "win32" else "CTranslate2 loads cuBLAS 12 and cuDNN 9 from "
                 "LD_LIBRARY_PATH, which must be set before vid2sub starts"))
    return out


```

- [ ] **Step 14: Run the checks; they pass.** `uv run pytest tests/test_doctor_config.py -q`
  first (`11 passed`), then the guard check, then `make check`. **Guard check:** in `_whisper`,
  replace `missing = fw.missing_cuda_libraries(environ, windows=platform == "win32")` with
  `missing = []`; `FAILED
  …test_a_windows_gpu_without_cublas_on_path_is_a_warning_that_says_how_to_fix_it`; restore it.
  `make check`. Expected:
  `1291 passed, 8 skipped, 46 deselected` twice, `Test Files  24 passed (24)`,
  `Tests  115 passed (115)`, `All checks passed!` and `no leaks found`.
- [ ] **Step 15: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(cli): 🤖 vid2sub doctor checks faster-whisper and, on Windows, that cuBLAS 12 is on PATH for the GPU

doctor (spec §9.5, §18.1) gains, on Windows and Linux (and anywhere
faster-whisper is installed): whether faster-whisper is installed (else
"install vid2sub[whisper] (vid2sub[nvidia] for an NVIDIA GPU)"); with no
NVIDIA GPU, that it runs on the CPU in int8; with one on Windows, whether
cublas64_12.dll and cudnn64_9.dll are in a folder on PATH, and if not, a
warning that it runs on the CPU and how to fix it (the [nvidia] wheels'
bin folders on PATH, or NVIDIA's CUDA 12 toolkit and cuDNN 9, then a
restart); on Linux, the GPUs seen, with a note that CTranslate2 reads
LD_LIBRARY_PATH, set before vid2sub starts. Every one is a warning, never
essential. The check runs on the same functions the engine uses to pick
its device (faster_whisper.cuda_devices and missing_cuda_libraries).

The new tests failed first with: AttributeError: module
'vid2sub.commands.doctor' has no attribute '_whisper'. With the PATH check
taken out, the Windows test fails.

Docs read: faster-whisper 1.2.1's README (on Windows the cuBLAS and cuDNN
libraries go in a folder on PATH; on Linux the pip wheels need
LD_LIBRARY_PATH set before Python starts).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md Task 9
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/commands/doctor.py tests/test_doctor_config.py`,
  `git commit -F .git/COMMIT_MSG`, then `git log -1 --format='%(trailers)'` shows `Plan:`.

#### Round 9d: Review Focus 5, a first run with no network or a GPU without cuDNN 9

- [ ] **Step 16: Write the failing tests.** In `tests/test_faster_whisper_engine.py`, replace
  `import dataclasses` (its first import) with the two lines `import ctypes.util` and
  `import dataclasses`; in the `no_gpu` fixture, below its
  `monkeypatch.setattr(fw, "hf_revision", lambda model: "0123456789abcdef")` line, add:

```python
    monkeypatch.setattr(fw, "model_path", lambda model: None)  # not downloaded yet
```

  replace

```python
def test_cuda_libraries_are_looked_for_on_path_and_only_on_windows(tmp_path):
    first, second = tmp_path / "a", tmp_path / "b"
    first.mkdir()
    second.mkdir()
    environ = {"PATH": os.pathsep.join([str(first), "", str(second)])}
    assert fw.missing_cuda_libraries(environ, windows=True) == ["cublas64_12.dll",
                                                                "cudnn64_9.dll"]
    (second / "cublas64_12.dll").write_bytes(b"")
    (first / "cudnn64_9.dll").write_bytes(b"")
    assert fw.missing_cuda_libraries(environ, windows=True) == []
    assert fw.missing_cuda_libraries({"PATH": ""}, windows=False) == []
```

  with

```python
def test_cuda_libraries_on_windows_are_looked_for_on_path_and_in_cuda_path(tmp_path):
    first, second, toolkit = tmp_path / "a", tmp_path / "b", tmp_path / "CUDA" / "v12.9"
    for folder in (first, second, toolkit / "bin"):
        folder.mkdir(parents=True)
    environ = {"PATH": os.pathsep.join([str(first), "", str(second)])}
    assert fw.missing_cuda_libraries(environ, platform="win32") == ["cublas64_12.dll",
                                                                    "cudnn64_9.dll"]
    (toolkit / "bin" / "cublas64_12.dll").write_bytes(b"")  # where CTranslate2 looks too
    (first / "cudnn64_9.dll").write_bytes(b"")
    assert fw.missing_cuda_libraries(environ, platform="win32") == ["cublas64_12.dll"]
    assert fw.missing_cuda_libraries({**environ, "CUDA_PATH": str(toolkit)},
                                     platform="win32") == []
    assert fw.missing_cuda_libraries({"PATH": ""}, platform="darwin") == []
```

  and append, after two blank lines:

```python
# Review Focus 5: a first run with no network, or an NVIDIA GPU without cuDNN 9 (spec §17.4)


def no_network(*args, **kwargs):
    """What WhisperModel raises on a first run with no network: huggingface_hub 2.2's
    LocalEntryNotFoundError, a FileNotFoundError, whose message can name the cache's folder."""
    raise FileNotFoundError("An error happened while trying to locate the files on the Hub and we "
                            "cannot find the appropriate snapshot folder on the local disk "
                            "(/home/someone/.cache/huggingface)")


def test_a_first_run_with_no_network_fails_at_once_naming_the_download_and_doctor():
    tries = []

    def offline(*args, **kwargs):
        tries.append(args)
        no_network()

    e = fw.FasterWhisperEngine("w", TURBO, model_factory=offline)
    with pytest.raises(EngineError) as err:
        e.transcribe(chunk(), language="en", prompt="")
    # "unavailable" fails the episode: a "connection" error would wait up to ten minutes.
    assert err.value.kind == "unavailable" and len(tries) == 1
    assert str(err.value) == ("faster-whisper couldn't download its model, which its first run "
                              "needs")
    assert "1.6 GB" in err.value.hint and "vid2sub doctor" in err.value.hint
    assert "someone" not in str(err.value) + err.value.hint


def test_a_downloaded_model_loads_from_its_folder_without_asking_the_network(monkeypatch):
    monkeypatch.setattr(fw, "model_path", lambda model: "/hf/snapshots/0123456789abcdef")
    engine().transcribe(chunk(), language="en", prompt="")
    assert FakeModel.made[0][0] == ("/hf/snapshots/0123456789abcdef",)


def test_a_downloaded_model_that_cannot_load_says_so_and_never_blames_the_network(monkeypatch):
    monkeypatch.setattr(fw, "model_path", lambda model: "/hf/snapshots/0123456789abcdef")

    def broken(*args, **kwargs):
        raise RuntimeError("Unable to open file 'model.bin' in model '/hf/snapshots/0123'")

    with pytest.raises(EngineError) as err:
        fw.FasterWhisperEngine("w", TURBO, model_factory=broken).transcribe(
            chunk(), language="en", prompt="")
    assert str(err.value) == "faster-whisper couldn't load its model (RuntimeError)"
    assert "vid2sub doctor" in err.value.hint and "/hf" not in err.value.hint


def test_cuda_libraries_on_linux_are_those_the_loader_can_open(monkeypatch):
    asked = []

    def can_load(library):
        asked.append(library)
        return library == "libcublas.so.12"

    monkeypatch.setattr(fw, "can_load", can_load)
    assert fw.missing_cuda_libraries({}, platform="linux") == ["libcudnn_ops.so.9",
                                                               "libcudnn_cnn.so.9"]
    assert asked == list(fw.LINUX_LIBRARIES)
    monkeypatch.setattr(fw, "can_load", lambda library: True)
    assert fw.missing_cuda_libraries({}, platform="linux") == []


def test_the_loader_check_opens_a_real_library_and_refuses_a_missing_one():
    assert not fw.can_load("libvid2sub-no-such-library.so.1")
    found = ctypes.util.find_library("c") or ctypes.util.find_library("msvcrt")
    if found is None:
        pytest.skip("no C library the loader can name here")
    assert fw.can_load(found)


def test_an_nvidia_gpu_without_cudnn_9_runs_on_the_cpu_and_says_why(monkeypatch, caplog):
    monkeypatch.setattr(fw, "cuda_devices", lambda: 1)
    monkeypatch.setattr(fw, "missing_cuda_libraries", lambda: ["libcudnn_ops.so.9"])
    with caplog.at_level("WARNING", logger="vid2sub.engines.faster_whisper"):
        e = engine()
        e.transcribe(chunk(), language="en", prompt="")
    assert FakeModel.made[0][1] == {"device": "cpu", "compute_type": "int8"} and e.device == "cpu"
    assert "libcudnn_ops.so.9" in caplog.text and "vid2sub doctor" in caplog.text


def test_without_an_nvidia_gpu_its_libraries_are_never_looked_for(monkeypatch):
    def looked():
        raise AssertionError("looked for CUDA's libraries with no GPU")

    monkeypatch.setattr(fw, "missing_cuda_libraries", looked)
    engine().transcribe(chunk(), language="en", prompt="")


@pytest.mark.parametrize("message, library", [
    ("Unable to load any of {libcudnn_ops.so.9.1.0, libcudnn_ops.so.9} (/home/someone)",
     "cuDNN 9"),
    ("Library cublas64_12.dll is not found or cannot be loaded (C:\\Users\\someone)",
     "cuBLAS 12")])
def test_a_gpu_library_that_fails_names_the_library_and_doctor_never_the_message(message,
                                                                               library):
    class Failing(FakeModel):
        def transcribe(self, audio, **kwargs):
            raise RuntimeError(message)

    with pytest.raises(EngineError) as err:
        fw.FasterWhisperEngine("w", TURBO, model_factory=Failing).transcribe(
            chunk(), language="en", prompt="")
    assert err.value.kind == "unavailable"
    assert str(err.value) == f"faster-whisper couldn't load the GPU's {library} library"
    assert "vid2sub doctor" in err.value.hint and "someone" not in err.value.hint


@pytest.mark.media
def test_a_first_run_with_no_network_fails_the_episode_and_nothing_falls_back(tmp_path,
                                                                              monkeypatch):
    # Spec §17.4: the episode fails at once, saying why and naming doctor; no other model is
    # tried, the cloud included, though this run allows it, and nothing waits.
    from fakes import FakeEngine
    from helpers import SPEECH, make_clip

    from vid2sub import detect, pipeline
    from vid2sub.media.tools import Tools

    clip = make_clip(tmp_path, "Show - S01E01.mkv", seconds=14, speech=SPEECH)
    cfg = Config(endpoints={"openai": Endpoint(base_url="https://api.openai.com/v1",
                                               key_env="OPENAI_TEST_KEY")},
                 models={"local-turbo": TURBO,
                         "cloud": ModelEntry(catalog="openai-whisper-1", endpoint="openai",
                                             model="whisper-1", parser="openai")})
    monkeypatch.setattr(detect, "whisper_available", lambda: True)
    sleeps, cloud = [], FakeEngine(name="openai", language="en")
    ctx = pipeline.RunContext(config=cfg, tools=Tools.find(),
                              keys=KeyRing(environ={"OPENAI_TEST_KEY": "k" * 40}),
                              options=pipeline.RunOptions(source_lang="en", targets=[],
                                                          allow_cloud=True),
                              sleep=sleeps.append)
    ctx.engines.update({"local-turbo": fw.FasterWhisperEngine("local-turbo", TURBO,
                                                              model_factory=no_network),
                        "cloud": cloud})
    result = pipeline.run_one(str(clip), ctx)
    assert (result.status, result.kind) == ("failed", "unavailable")
    assert "download" in result.reason and "vid2sub doctor" in result.hint
    assert cloud.calls == [] and sleeps == []
    assert not clip.with_name("Show - S01E01.en.srt").exists()
```

  In `tests/test_doctor_config.py`, replace

```python
    cublas = checks["cuBLAS 12"]
    assert (cublas.ok, cublas.essential) == (False, False)
    assert "cublas64_12.dll" in cublas.detail and "CPU" in cublas.detail
    assert "PATH" in cublas.hint and "vid2sub[nvidia]" in cublas.hint
    for dll in ("cublas64_12.dll", "cudnn64_9.dll"):
        (tmp_path / dll).write_bytes(b"")
    assert by_name(doctor._whisper({"PATH": str(tmp_path)}, platform="win32"))["cuBLAS 12"].ok
```

  with

```python
    cuda = checks["CUDA libraries"]
    assert (cuda.ok, cuda.essential) == (False, False)
    assert "cublas64_12.dll" in cuda.detail and "CPU" in cuda.detail
    assert "PATH" in cuda.hint and "vid2sub[nvidia]" in cuda.hint
    for dll in ("cublas64_12.dll", "cudnn64_9.dll"):
        (tmp_path / dll).write_bytes(b"")
    found = by_name(doctor._whisper({"PATH": str(tmp_path)}, platform="win32"))["CUDA libraries"]
    assert found.ok and "cuBLAS 12 and cuDNN 9 found" in found.detail
```

  and replace

```python
def test_on_linux_the_gpu_is_reported_without_a_path_check(whisper):
    whisper(gpus=2)
    checks = by_name(doctor._whisper({"PATH": ""}, platform="linux"))
    assert checks["cuBLAS 12"].ok and "2 NVIDIA GPU" in checks["cuBLAS 12"].detail
```

  with

```python
def test_on_linux_the_libraries_are_those_the_loader_can_open(whisper, monkeypatch):
    # Review Focus 5: a GPU without cuDNN 9 is a warning that says how to fix it.
    from vid2sub.engines import faster_whisper as fw

    whisper(gpus=2)
    monkeypatch.setattr(fw, "can_load", lambda library: True)
    cuda = by_name(doctor._whisper({"PATH": ""}, platform="linux"))["CUDA libraries"]
    assert cuda.ok and "2 NVIDIA GPU" in cuda.detail and "LD_LIBRARY_PATH" in cuda.note
    monkeypatch.setattr(fw, "can_load", lambda library: library == "libcublas.so.12")
    cuda = by_name(doctor._whisper({"PATH": ""}, platform="linux"))["CUDA libraries"]
    assert (cuda.ok, cuda.essential) == (False, False)
    assert "libcudnn_ops.so.9" in cuda.detail and "CPU" in cuda.detail
    assert "LD_LIBRARY_PATH" in cuda.hint and "vid2sub[nvidia]" in cuda.hint
```

- [ ] **Step 17: Run them; watch them fail.** `uv run pytest tests/test_faster_whisper_engine.py
  -q`. Expected: `E       AttributeError: <module 'vid2sub.engines.faster_whisper' from
  '…/src/vid2sub/engines/faster_whisper.py'> has no attribute 'model_path'` (in the fixture,
  so every test) and `1 deselected, 28 errors`. `uv run pytest tests/test_doctor_config.py -q`.
  Expected: `E       KeyError: 'CUDA libraries'` and `2 failed, 9 passed`.
- [ ] **Step 18: Write the code.** Replace `src/vid2sub/engines/faster_whisper.py` with:

```python
"""Whisper in-process through faster-whisper, for Windows and Linux (spec §9.5, S45).

CTranslate2 conversions of Whisper large-v3 and large-v3-turbo: faster-whisper's `large-v3` and
`large-v3-turbo` from the catalog entry, or the converted model's Hugging Face id in the entry's
`model`. Words come from `word_timestamps=True`; `vad_filter=False`, since vid2sub's own VAD has
already chosen the speech (§8.6). On an NVIDIA GPU the model runs in float16, and otherwise on the
CPU in int8 (§9.5). CUDA needs the cuBLAS 12 and cuDNN 9 libraries, as faster-whisper's README
says: on Windows in a folder on PATH (or CUDA_PATH's `bin`, where CTranslate2 also looks for
cuBLAS), on Linux where the loader finds them (LD_LIBRARY_PATH). They are looked for before the
GPU is chosen, so a GPU without them runs on the CPU, with a warning that names what is missing
and `vid2sub doctor`, rather than failing mid-episode in the library (Review Focus 5). The import
is lazy and the model is loaded once, on first use, and released by `close` (§9.1; mlx imports
cost seconds, an audio-router lesson). A model already in the local Hugging Face cache is loaded
from its folder, never asking the network; the first run downloads it (1.6 GB for turbo, 3.1 GB
for large-v3), and with no network that fails at once, through huggingface_hub's own timeouts,
as an `unavailable` error that fails the episode: never a `connection` error, which would wait
for ten minutes, and never another model or the cloud (§17.4). The revision in the version stamp
is the model's Hugging Face snapshot, read from the local cache only (§9.6). A failure is named by
its cause (the download, a GPU library, the model) and never by the library's message, which can
hold a path (§6.8).
"""

from __future__ import annotations

import ctypes
import logging
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from vid2sub.catalog import CATALOG
from vid2sub.config import ModelEntry
from vid2sub.engines.base import Chunk, ChunkResult, EngineError, ModelStamp
from vid2sub.parse.fasterwhisper import parse_faster_whisper

log = logging.getLogger("vid2sub.engines.faster_whisper")

WINDOWS_LIBRARIES = ("cublas64_12.dll", "cudnn64_9.dll")  # what CTranslate2 loads on Windows
# On Linux: cuBLAS 12, and the cuDNN 9 parts Whisper's convolutions need, which cuDNN's own
# libcudnn.so.9 loads only when they are first used.
LINUX_LIBRARIES = ("libcublas.so.12", "libcudnn_ops.so.9", "libcudnn_cnn.so.9")
DEFAULT_CATALOG = "whisper-large-v3-turbo"
INSTALL = "install vid2sub[whisper] (vid2sub[nvidia] for an NVIDIA GPU)"
DOCTOR = "`vid2sub doctor` checks the model's files and the GPU's libraries"
FIRST_RUN = ("its first run downloads the model from Hugging Face (1.6 GB for large-v3-turbo, "
             "3.1 GB for large-v3): check the network and the free disk space, then run again; "
             + DOCTOR)
GPU_FIX = ("`vid2sub doctor` says how to put the CUDA 12 cuBLAS and cuDNN 9 libraries where "
           "faster-whisper finds them")
_GPU_LIBRARIES = (("cudnn", "cuDNN 9"), ("cublas", "cuBLAS 12"))


def can_load(library: str) -> bool:
    """Whether the dynamic loader finds and opens `library` by its name, as CTranslate2's own
    dlopen does (LD_LIBRARY_PATH, then the loader's cache)."""
    try:
        ctypes.CDLL(library)
    except OSError:
        return False
    return True


def missing_cuda_libraries(environ: Mapping[str, str] = os.environ, *,
                           platform: str = sys.platform) -> list[str]:
    """The CUDA libraries CTranslate2 needs that it wouldn't find: on Windows, those no folder
    on PATH or CUDA_PATH's `bin` holds (`environ`'s); on Linux, those the loader can't open in
    this process; elsewhere none (no CUDA)."""
    if platform == "win32":
        folders = [f for f in environ.get("PATH", "").split(os.pathsep) if f]
        if environ.get("CUDA_PATH"):
            folders.append(os.path.join(environ["CUDA_PATH"], "bin"))
        return [lib for lib in WINDOWS_LIBRARIES
                if not any(os.path.isfile(os.path.join(f, lib)) for f in folders)]
    if platform.startswith("linux"):
        return [lib for lib in LINUX_LIBRARIES if not can_load(lib)]
    return []


def cuda_devices() -> int:
    """How many NVIDIA GPUs CTranslate2 sees (0 without the extra or a GPU)."""
    try:
        import ctranslate2
    except ImportError:
        return 0
    try:
        return int(ctranslate2.get_cuda_device_count())
    except Exception:  # noqa: BLE001 - no driver is no GPU
        return 0


def device_for(devices: int, missing: Sequence[str]) -> tuple[str, str]:
    """The device and compute type: an NVIDIA GPU in float16 when CTranslate2 sees one and its
    libraries are there, else the CPU in int8 (spec §9.5)."""
    return ("cuda", "float16") if devices > 0 and not missing else ("cpu", "int8")


def model_path(model: str) -> str | None:
    """The model's folder in the local Hugging Face cache, if it has been downloaded; never asks
    the network. faster-whisper's own download_model maps a size to its repo."""
    try:
        from faster_whisper.utils import download_model

        return str(download_model(model, local_files_only=True))
    except Exception:  # noqa: BLE001 - not installed, not downloaded, or not a model's name
        return None


def hf_revision(model: str) -> str:
    """The cached snapshot's hash, so a model update changes the version (§9.6), as the Qwen
    engine's hf_revision does."""
    path = model_path(model)
    name = Path(path).name if path else ""
    return name[:12] if name else "unknown"


def _plain(segments: Any, info: Any) -> dict[str, Any]:
    """faster-whisper's Segment, Word and TranscriptionInfo as the parser's plain data. Reading
    `segments` runs the model: it is a generator."""
    return {
        "language": getattr(info, "language", None),
        "language_probability": getattr(info, "language_probability", None),
        "all_language_probs": getattr(info, "all_language_probs", None),
        "segments": [{"start": s.start, "end": s.end, "text": s.text,
                      "avg_logprob": s.avg_logprob, "compression_ratio": s.compression_ratio,
                      "no_speech_prob": s.no_speech_prob,
                      "words": [{"start": w.start, "end": w.end, "word": w.word,
                                 "probability": w.probability} for w in s.words or []]}
                     for s in segments],
    }


def _failure(err: Exception, doing: str, *, first_run: bool = False) -> EngineError:
    """The engine's error for `err`, named by its cause: a GPU library, the first download, or
    what failed and the exception's type. The library's message is read, never shown."""
    text = str(err).lower()
    library = next((name for key, name in _GPU_LIBRARIES if key in text), None)
    if library is not None:
        return EngineError("unavailable", f"faster-whisper couldn't load the GPU's {library} "
                           "library", hint=GPU_FIX)
    if first_run:
        return EngineError("unavailable", "faster-whisper couldn't download its model, which "
                           "its first run needs", hint=FIRST_RUN)
    return EngineError("unavailable", f"faster-whisper {doing} ({type(err).__name__})",
                       hint=DOCTOR)


class FasterWhisperEngine:
    """One caller at a time: the model isn't documented as thread-safe."""

    name = "faster-whisper"
    supports_prompt = True

    def __init__(self, name: str, entry: ModelEntry, *,
                 model_factory: Callable[..., Any] | None = None):
        catalog = CATALOG.get(entry.catalog or DEFAULT_CATALOG)
        self.model_name = name
        self.model_id = (entry.model or (catalog.default_model if catalog else None)
                         or "large-v3-turbo")
        self.max_chunk_s = catalog.max_chunk_s if catalog else 300.0
        self.device: str | None = None  # "cuda" or "cpu", once the model is loaded
        self._factory = model_factory
        self._model: Any = None

    def _load(self) -> Any:
        if self._model is None:
            factory = self._factory
            if factory is None:
                try:
                    from faster_whisper import WhisperModel
                except ImportError:
                    raise EngineError("unavailable", "faster-whisper isn't installed",
                                      hint=INSTALL) from None
                factory = WhisperModel
            devices = cuda_devices()
            missing = missing_cuda_libraries() if devices else []
            if missing:
                log.warning("faster-whisper runs on the CPU: %s not found; `vid2sub doctor` "
                            "says how to fix it", ", ".join(missing))
            device, compute = device_for(devices, missing)
            downloaded = model_path(self.model_id)
            try:
                self._model = factory(downloaded or self.model_id, device=device,
                                      compute_type=compute)
            except Exception as err:  # noqa: BLE001 - any load failure: the model can't run
                raise _failure(err, "couldn't load its model",
                               first_run=downloaded is None) from None
            self.device = device
        return self._model

    def transcribe(self, chunk: Chunk, *, language: str | None, prompt: str) -> ChunkResult:
        model = self._load()
        try:
            segments, info = model.transcribe(chunk.float32, language=language,
                                              initial_prompt=prompt or None,
                                              word_timestamps=True, vad_filter=False)
            data = _plain(segments, info)
        except Exception as err:  # noqa: BLE001 - CTranslate2 raises RuntimeError and others
            raise _failure(err, "failed on this chunk") from None
        return ChunkResult(parse_faster_whisper(data))

    def detect_language(self, chunk: Chunk) -> dict[str, float]:
        model = self._load()
        try:
            language, probability, every = model.detect_language(chunk.float32)
        except Exception as err:  # noqa: BLE001 - as transcribe
            raise _failure(err, "couldn't detect the language") from None
        return {str(code): float(p) for code, p in (every or [(language, probability)])}

    def stamp(self) -> ModelStamp:
        return ModelStamp(self.name, self.model_id, hf_revision(self.model_id))

    def close(self) -> None:
        self._model = None
```

  In `src/vid2sub/commands/doctor.py`, in the module docstring replace

```python
Windows and Linux, faster-whisper and the NVIDIA GPU's libraries are warnings: CUDA on Windows
needs the cuBLAS 12 DLLs on PATH, and without them faster-whisper runs on the CPU (spec §9.5).
```

  with

```python
Windows and Linux, faster-whisper and the NVIDIA GPU's libraries are warnings: CUDA needs the
cuBLAS 12 and cuDNN 9 libraries, on Windows on PATH and on Linux where the loader finds them
(LD_LIBRARY_PATH), and without them faster-whisper runs on the CPU (spec §9.5; Review Focus 5).
```

  below `CUDA_FIX`'s last line,

```python
            "or install NVIDIA's CUDA 12 toolkit and cuDNN 9; then start vid2sub again")
```

  add

```python
LINUX_CUDA_FIX = ("install vid2sub[nvidia] and set LD_LIBRARY_PATH to the lib folders of its "
                  "nvidia-cublas-cu12 and nvidia-cudnn-cu12 packages before vid2sub starts (as "
                  "faster-whisper's README shows), or install NVIDIA's CUDA 12 toolkit and cuDNN 9")
```

  and in `_whisper` replace

```python
    missing = fw.missing_cuda_libraries(environ, windows=platform == "win32")
    if missing:
        out.append(Check("cuBLAS 12", False, f"{', '.join(missing)} not on PATH: faster-whisper "
                         "runs on the CPU", CUDA_FIX, essential=False))
    else:
        out.append(Check(
            "cuBLAS 12", True, f"{gpus} NVIDIA GPU(s) seen", essential=False,
            note="" if platform == "win32" else "CTranslate2 loads cuBLAS 12 and cuDNN 9 from "
                 "LD_LIBRARY_PATH, which must be set before vid2sub starts"))
    return out
```

  with

```python
    windows = platform == "win32"
    missing = fw.missing_cuda_libraries(environ, platform=platform)
    if missing:
        where = "on PATH" if windows else "where the loader looks"
        out.append(Check("CUDA libraries", False, f"{', '.join(missing)} not {where}: "
                         "faster-whisper runs on the CPU", CUDA_FIX if windows else LINUX_CUDA_FIX,
                         essential=False))
    else:
        out.append(Check(
            "CUDA libraries", True, f"cuBLAS 12 and cuDNN 9 found; {gpus} NVIDIA GPU(s) seen",
            essential=False,
            note="" if windows else "CTranslate2 loads cuBLAS 12 and cuDNN 9 from "
                 "LD_LIBRARY_PATH, which must be set before vid2sub starts"))
    return out
```

- [ ] **Step 19: Run the checks; they pass.** `uv run pytest tests/test_faster_whisper_engine.py
  tests/test_doctor_config.py -q` first (`38 passed, 1 skipped, 1 deselected`), then once with
  the extra and no network: `uv sync --group dev --extra whisper`, then `HF_HOME=<an empty
  folder> HF_HUB_OFFLINE=1 uv run --no-sync python -c "…"` making a `FasterWhisperEngine` for
  `whisper-large-v3-turbo` with the real `WhisperModel` and transcribing one second of silence
  (expected, in well under a second: `EngineError unavailable faster-whisper couldn't download
  its model, which its first run needs`, and `model_path` gives `None`); `uv run --no-sync pytest
  tests/test_faster_whisper_engine.py tests/test_doctor_config.py -q` (`39 passed, 1
  deselected`); then `uv sync --group dev` to go back. Then the guard checks, each reverted and
  restored, each with `uv run pytest tests/test_faster_whisper_engine.py -q`: in `_load`,
  replace `first_run=downloaded is None) from None` with `first_run=False) from None` (`2
  failed`: the two no-network tests); in `_failure`, make the download's error
  `EngineError("connection", …)` (`3 failed`: the episode test waits and pauses); in
  `missing_cuda_libraries`, return `[]` for Linux (`FAILED
  …test_cuda_libraries_on_linux_are_those_the_loader_can_open`); in `_load`, pass
  `self.model_id` instead of `downloaded or self.model_id` (`FAILED
  …test_a_downloaded_model_loads_from_its_folder_without_asking_the_network`). `make check`.
  Expected: `1301 passed, 8 skipped, 46 deselected` twice, `Test Files  24 passed (24)`,
  `Tests  115 passed (115)`, `All checks passed!` and `no leaks found`.
- [ ] **Step 20: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
fix(engines): 🤖 faster-whisper's first run with no network, or a GPU without cuDNN 9, fails at once naming the cause and doctor

Review Focus 5 (spec §9.5, §17.4). A model already in the local Hugging
Face cache (faster_whisper.model_path: download_model with
local_files_only=True) is loaded from its folder, so a later run never asks
the network. A first run that can't download it fails at once as
"faster-whisper couldn't download its model, which its first run needs",
with a hint naming the size (1.6 GB for large-v3-turbo, 3.1 GB for
large-v3), the network, the free disk space and `vid2sub doctor`. It is an
`unavailable` error, so the pipeline fails the episode: a `connection`
error would wait up to wait_on_connection_s (ten minutes) and then pause
the queue, which is the hang this item names, and nothing falls back to
another model or the cloud, even where the run allows the cloud. With no
network, huggingface_hub 2.2 gives up through its own timeouts (10 s for
the metadata request, HF_HUB_ETAG_TIMEOUT); run here with HF_HUB_OFFLINE=1
and the real faster-whisper 1.2.1, the engine failed in well under a
second with that message.

The GPU's libraries are looked for before the GPU is chosen, on Linux too:
the loader must open libcublas.so.12, libcudnn_ops.so.9 and
libcudnn_cnn.so.9 (faster_whisper.can_load, ctypes, as CTranslate2's
dlopen finds them through LD_LIBRARY_PATH); on Windows, cublas64_12.dll
and cudnn64_9.dll on PATH or in CUDA_PATH's bin, where CTranslate2 also
looks for cuBLAS. Without them the model runs on the CPU in int8, with a
warning naming what is missing and `vid2sub doctor`, rather than failing
in the library mid-episode; with no GPU, they aren't looked for. A GPU
library that fails anyway is named ("faster-whisper couldn't load the
GPU's cuDNN 9 library", or cuBLAS 12), its hint pointing at doctor; the
library's message, which can hold a path, is never shown. missing_cuda_
libraries takes `platform` (sys.platform) in place of `windows`. doctor's
GPU check is now "CUDA libraries", on Linux as on Windows, with the
LD_LIBRARY_PATH fix there.

The new tests failed first with: AttributeError: <module
'vid2sub.engines.faster_whisper' …> has no attribute 'model_path' (1
deselected, 28 errors), and KeyError: 'CUDA libraries' (2 failed, 9
passed). Guard checks, each reverted and restored: with first_run=False,
the no-network tests fail; with the download failure a "connection"
error, the episode test fails (it waits and pauses); with Linux's loader
check taken out, its test fails; loading by name instead of the cached
folder fails the cached-model test.

Docs read: faster-whisper 1.2.1's utils.py (download_model calls
huggingface_hub.snapshot_download with local_files_only and catches
nothing) and transcribe.py (WhisperModel loads a directory as it is,
else download_model); its README's GPU section ("cuBLAS for CUDA 12",
"cuDNN 9 for CUDA 12"; on Linux the pip wheels need LD_LIBRARY_PATH
set before Python starts; on Windows the libraries go in a folder on
PATH; the latest ctranslate2 supports only CUDA 12 and cuDNN 9);
CTranslate2's src/cuda/cublas_stub.cc (dlopen("libcublas.so.12"), or
LoadLibraryA("cublas64_12.dll") after CUDA_PATH's bin, throwing "Library
… is not found or cannot be loaded") and CMakeLists.txt ("libcudnn.so is
a shim layer that dynamically loads the correct library at runtime");
CTranslate2's installation page, which still says cuDNN 8 for CUDA 12,
behind faster-whisper's README; huggingface_hub 2.2.0's constants
(HF_HUB_ETAG_TIMEOUT 10, HF_HUB_DOWNLOAD_TIMEOUT 10) and its offline
error (LocalEntryNotFoundError, a FileNotFoundError); the sizes of
model.bin in Systran/faster-whisper-large-v3 (3,087,284,237 bytes) and
mobiuslabsgmbh/faster-whisper-large-v3-turbo (1,617,884,929 bytes) from
the Hugging Face API. Not checked here: no NVIDIA GPU, so the library
names are from the sources above, not a real load.

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md Task 9
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/engines/faster_whisper.py src/vid2sub/commands/doctor.py
  tests/test_faster_whisper_engine.py tests/test_doctor_config.py`, `git commit -F
  .git/COMMIT_MSG`, then `git log -1 --format='%(trailers)'` shows `Plan:`.

#### Round 9e: English's route and the Spark's Qwen3-ASR

- [ ] **Step 21: Write the test** (it pins what Step 8 built, so it passes at once). Append to
  `tests/test_catalog.py`, after two blank lines:

```python
@pytest.mark.parametrize("lang", ["en", "yue", "zh"])
def test_the_sparks_qwen3_asr_comes_before_the_macs_wherever_qwen_is_on_the_route(lang):
    # Phase 2 Task 20 put Qwen3-ASR on the Spark (parser = "qwen3-asr"): §11.2 names it "Spark,
    # then Mac" for Cantonese, and English's "(Mac)" predates it, so the Spark's comes first.
    found = machine(mac=True, spark=False) + [cand("spark-qwen", "qwen3-asr-1.7b")]
    assert suggest(lang, found, "transcribe", allow_cloud=False).model == "spark-qwen"
```

- [ ] **Step 22: Run it, and check that it pins the reading.** `uv run pytest
  tests/test_catalog.py -q` (`29 passed`). **Guard check**, reverted and restored: in
  `catalog.TRANSCRIBE_ROUTES["en"]`, replace the plain `"qwen3-asr-1.7b",` step with
  `("qwen3-asr-1.7b", "in-process"),` (`FAILED
  …test_the_sparks_qwen3_asr_comes_before_the_macs_wherever_qwen_is_on_the_route[en]`).
  `uv run ruff check src tests`: `All checks passed!`.
- [ ] **Step 23: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
test(catalog): 🤖 the Spark's Qwen3-ASR comes before the Mac's for English, Cantonese and Mandarin

Phase 2 Task 20 put Qwen3-ASR on the Spark (parser = "qwen3-asr"). Spec
§11.2 names Cantonese's Qwen3-ASR "Spark, then Mac"; English's
"qwen3-asr-1.7b (Mac)" was written before the Spark served it. English's
route keeps qwen3-asr-1.7b as a plain step (anywhere, endpoints first),
so the Spark's Qwen comes before the Mac's there too, as it does for
Cantonese and Mandarin; this test pins that reading. With English's
step narrowed to ("qwen3-asr-1.7b", "in-process"), its English case fails
(FAILED …[en]: 'mac-qwen' == 'spark-qwen').

Docs read: spec §11.2's routing table; the Phase 2 plan's Task 20
(the Spark's Qwen3-ASR endpoint and its example entry).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md Task 9
Co-Authored-By: <the model's own line>
```

  `git add tests/test_catalog.py`, `git commit -F .git/COMMIT_MSG`, then
  `git log -1 --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 24: Review, look forward, close.** The Tier 2 review from `$(cat .git/TASK_BASE)`
  (`AGENTS.md`, *Reviews*). Worth the reviewers' time: that the fakes match the real library
  (the field check, run with the extra); that a GPU without its libraries means
  the CPU, never a crash or a silent wrong device (the warning names what is missing); that a
  first run with no network fails the episode at once, naming the download and doctor, and that
  nothing falls back to another model or the cloud (Review Focus 5, §17.4); that no failure
  message carries a path (§6.8); that the parser stays pure. The forward review over Tasks 8,
  10, 11 and 12: Task 8's Models page shows the faster-whisper candidates and their install
  reason; Task 10's CI job installs the `whisper` extra on Windows and Linux, runs the suite
  (the field check then runs) and keeps the real model out; Task 11's README gains the per-OS
  install and the NVIDIA notes (cuBLAS 12 and cuDNN 9: on PATH on Windows, LD_LIBRARY_PATH on
  Linux; §23.5); Task 12's manual run uses `VID2SUB_LIVE_WHISPER=1` or a real season, and reads
  doctor's `CUDA libraries` check. The docs this task made untrue: the spec's §4.2 says
  `[nvidia]` adds "the CUDA 12 cuBLAS runtime wheels" and §9.5 names only cuBLAS 12 on PATH; the
  extra and doctor also need cuDNN 9, as faster-whisper's README says, and Linux needs
  LD_LIBRARY_PATH. That changes the spec, so it waits on Dan (the plan's Decision 10); once
  approved, §4.2 and §9.5 name cuDNN 9 in this close, and if not, it is the fifth stop
  (`AGENTS.md`, *Stops*). Then the close, its own commit, holding this plan with this task's
  boxes ticked and **Now** set to `Task 10: CI on Windows and Linux for faster-whisper, open.`;
  `docs/architecture.md`'s first diagram drawing faster-whisper as built (the node
  `fw["In-process engine<br/>faster-whisper (Windows, Linux)"]`, the edge `core --> fw`, and
  `fw` out of the `planned` class); and the spec's S45 row with "Phase and task" set to
  `Phase 3, Tasks 9–10, 12` (S45 stays `planned`: its proof is CI and one manual run). The
  message, in `.git/CLOSE_MSG`:

```text
docs(plan): 🤖 close Task 9: The faster-whisper engine

Drift: none
Rulings: none
Phase-end: none
Forward: none
Tier: 2
Rounds: none
Findings: none

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md Task 9
Co-Authored-By: <the model's own line>
```

  `git add docs/architecture.md docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md
  docs/superpowers/specs/2026-10-14-vid2sub-design.md`, `git commit -F .git/CLOSE_MSG`.

***

### Task 10: CI on Windows and Linux for `faster-whisper`

**Tier:** 3 · **Scenarios:** S45

Spec §23.2 and S45 ("CI passes on all three systems"): a `whisper` job runs the suite on Windows
and Linux with Task 9's `whisper` extra, so the engine's field check runs against the real
faster-whisper there instead of skipping.

**Why it is built this way** (read 2026-10-24):
- **A job of its own,** not another dimension of the `python` matrix: the python job's six
  entries stay as they are, and the two whisper entries (ubuntu-24.04 and windows-2022, Python
  3.12) are the only ones that install ctranslate2, PyAV and tokenizers. Not the `nvidia` extra:
  its wheels are 553 MB and 743 MB, and GitHub's standard runners have no GPU. macOS keeps
  Qwen3-ASR (`[mac]`); faster-whisper is Windows' and Linux's.
- **A skip there is a failure.** `pytest.importorskip` would let the field check skip silently if
  the extra didn't install, so the job sets `VID2SUB_REQUIRE_WHISPER=1`, which makes the field
  check, and a new check of the signatures the engine calls (`WhisperModel(device=,
  compute_type=)`, `transcribe(language=, initial_prompt=, word_timestamps=, vad_filter=)`,
  `download_model(local_files_only=)`, `ctranslate2.get_cuda_device_count`), import the library
  or fail, as `VID2SUB_REQUIRE_FFMPEG=1` does for media tests.
- **`uv run --extra whisper pytest`,** so the run keeps the extra the sync installed: uv's `run`
  syncs before it runs (inexactly, unless `--exact`), and naming the extra says what it needs.
- **The real model stays out** of every job: `VID2SUB_LIVE_WHISPER` is opt-in (Task 12's manual
  run), and no test downloads a model.
- **Phase 3 Task 1's Windows-only tests** (the junction, the hidden attribute, the 8.3 short
  name, `\\?\` names in a folder: `skipif(os.name != "nt")`) run in the existing `python` job,
  whose windows-2022 entries run the whole suite (`uv run --python ${{ matrix.python }}
  pytest`), and in the new job's Windows entry too; its Linux-only test (a name that isn't valid
  Unicode) runs in the python job's Ubuntu entries. A test pins that the python job keeps
  running the whole suite on Windows.
- **What only a real run shows:** that the Windows and Linux wheels install from the lock
  (ctranslate2 4.8.3, av 19.0.2, tokenizers 0.23.3, huggingface-hub 2.2.0), that the suite
  passes on both with the extra, and the jobs' time. Here the workflow is proven by
  `make actionlint` and by `tests/test_ci_workflow.py`, which reads it as Actions does (PyYAML,
  the dev group's `pyyaml==6.0.3`), and the job's two commands were run on macOS with the extra.

**Files:**
- Modify: `.github/workflows/ci.yml` (the `whisper` job), `tests/test_faster_whisper_engine.py`
  (`installed_faster_whisper`, the signature check), `tests/README.md`
  (`VID2SUB_REQUIRE_WHISPER`), the spec (§23.2's job list, Decision 20)
- Create: `tests/test_ci_workflow.py`
- Modify at the close: this plan

**Interfaces:**
- Consumes: Task 9's `whisper` extra and `tests/test_faster_whisper_engine.py` (its field
  check, `fw.cuda_devices`); Phase 2 Task 21's pins (checkout v7.0.1, setup-uv v10.3.0 with uv
  0.13.1) and `make actionlint`; the python job's ffmpeg steps.
- Produces:
  - CI job `whisper`: matrix `os: [ubuntu-24.04, windows-2022]`, `fail-fast: false`, 30
    minutes, `contents: read`; env `UV_FROZEN=1`, `VID2SUB_REQUIRE_FFMPEG=1`,
    `VID2SUB_REQUIRE_WHISPER=1`; steps: checkout (`persist-credentials: false`), setup-uv,
    ffmpeg (apt on Linux, choco on Windows), `uv sync --group dev --extra whisper --python
    3.12`, `uv run --python 3.12 --extra whisper pytest`.
  - `VID2SUB_REQUIRE_WHISPER=1`: faster-whisper's field and signature checks fail instead of
    skipping without the extra (`installed_faster_whisper()` in the engine's test module).
  - `tests/test_ci_workflow.py`: what Phase 4's workflow tasks can extend (pins, timeouts,
    read-only permissions and token-free checkouts across every job).
- For Task 12's Step 8: the run's job list shows `whisper (ubuntu-24.04)` and
  `whisper (windows-2022)`.

The counts below are the assembled Phase 3's, with Tasks 1–9 in before this task.

- [ ] **Step 0: Record the base:** `git rev-parse HEAD > .git/TASK_BASE`.
- [ ] **Step 1: Write the failing test,** `tests/test_ci_workflow.py`:

```python
"""CI's workflow, read as GitHub Actions reads it (spec §23.1, §23.2; S45; Phase 3 Task 10).

GitHub Actions can't run here, so this pins what only a real run would otherwise show missing:
faster-whisper's own job, on Windows and Linux, installs the `whisper` extra (never `nvidia`, whose
wheels are 553 MB and 743 MB) and fails where the field check against the real library would
skip; the real model stays out of CI; the python job still runs the whole suite on Windows (Phase
3 Task 1's junction, hidden-attribute and 8.3 short-name tests run only there); and every job keeps
§23.1's hardening. `make actionlint` checks the file's syntax and expressions.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"
PINNED = re.compile(r"^[\w.-]+/[\w.-]+@[0-9a-f]{40} # v\d+(\.\d+)*$")


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def runs(job: dict) -> list[str]:
    return [step["run"] for step in job["steps"] if "run" in step]


def test_faster_whisper_has_a_job_on_windows_and_linux(workflow):
    job = workflow["jobs"]["whisper"]
    assert job["strategy"]["matrix"]["os"] == ["ubuntu-24.04", "windows-2022"]
    assert job["runs-on"] == "${{ matrix.os }}"
    assert job["strategy"]["fail-fast"] is False


def test_the_whisper_job_installs_the_whisper_extra_and_never_the_nvidia_one(workflow):
    job = workflow["jobs"]["whisper"]
    assert "uv sync --group dev --extra whisper --python 3.12" in runs(job)
    assert "uv run --python 3.12 --extra whisper pytest" in runs(job)
    every = [run for each in workflow["jobs"].values() for run in runs(each)]
    assert not [run for run in every if "nvidia" in run or "--all-extras" in run]


def test_the_whisper_job_fails_where_the_field_check_would_skip(workflow):
    env = workflow["jobs"]["whisper"]["env"]
    assert env == {"UV_FROZEN": "1", "VID2SUB_REQUIRE_FFMPEG": "1",
                   "VID2SUB_REQUIRE_WHISPER": "1"}


def test_the_real_model_never_runs_in_ci(workflow):
    for name, job in workflow["jobs"].items():
        assert not [k for k in job.get("env", {}) if k.startswith("VID2SUB_LIVE")], name
        assert not [run for run in runs(job) if "VID2SUB_LIVE" in run or "-m live" in run], name


def test_the_python_job_runs_the_whole_suite_on_windows_too(workflow):
    # Phase 3 Task 1's Windows-only tests (skipped elsewhere) run in this job's Windows entries.
    job = workflow["jobs"]["python"]
    assert "windows-2022" in job["strategy"]["matrix"]["os"]
    assert "uv run --python ${{ matrix.python }} pytest" in runs(job)


def test_every_action_is_pinned_by_its_commit_with_its_version_beside_it():
    uses = re.findall(r"uses: (.+)$", WORKFLOW.read_text(encoding="utf-8"), flags=re.MULTILINE)
    assert uses and [u for u in uses if not PINNED.fullmatch(u.strip())] == []


def test_every_job_has_a_timeout_and_reads_only_and_no_checkout_keeps_its_token(workflow):
    assert workflow["permissions"] == {"contents": "read"}
    for name, job in workflow["jobs"].items():
        assert isinstance(job.get("timeout-minutes"), int), name
        assert job.get("permissions", {"contents": "read"}) == {"contents": "read"}, name
        for step in job["steps"]:
            if step.get("uses", "").startswith("actions/checkout@"):
                assert step["with"]["persist-credentials"] is False, name
```

  In `tests/test_faster_whisper_engine.py`, replace

```python
import ctypes.util
import dataclasses
import os
```

  with

```python
import ctypes.util
import dataclasses
import importlib
import inspect
import os
```

  and replace

```python
def test_the_fakes_have_the_fields_of_the_installed_faster_whisper():
    transcribe = pytest.importorskip("faster_whisper.transcribe")
```

  with

```python
def installed_faster_whisper():
    """faster-whisper's transcribe module: a skip without the `whisper` extra, but a failure where
    VID2SUB_REQUIRE_WHISPER=1 says it is installed (CI's whisper job, Phase 3 Task 10), since a
    skipped field check checks nothing."""
    if os.environ.get("VID2SUB_REQUIRE_WHISPER") == "1":
        return importlib.import_module("faster_whisper.transcribe")
    return pytest.importorskip("faster_whisper.transcribe")


def test_with_whisper_required_a_missing_library_fails_rather_than_skips(monkeypatch):
    monkeypatch.setitem(sys.modules, "faster_whisper", None)
    monkeypatch.setitem(sys.modules, "faster_whisper.transcribe", None)
    monkeypatch.delenv("VID2SUB_REQUIRE_WHISPER", raising=False)
    with pytest.raises(pytest.skip.Exception):
        installed_faster_whisper()
    monkeypatch.setenv("VID2SUB_REQUIRE_WHISPER", "1")
    with pytest.raises(ImportError):
        installed_faster_whisper()


def test_the_engine_calls_the_installed_faster_whisper_as_its_signatures_allow():
    transcribe = installed_faster_whisper()
    from faster_whisper.utils import download_model

    def takes(fn) -> set[str]:
        return set(inspect.signature(fn).parameters)

    assert {"device", "compute_type"} <= takes(transcribe.WhisperModel.__init__)
    assert {"language", "initial_prompt", "word_timestamps", "vad_filter"} <= takes(
        transcribe.WhisperModel.transcribe)
    assert "local_files_only" in takes(download_model)
    assert fw.cuda_devices() >= 0  # CTranslate2 answers, with no GPU as with one


def test_the_fakes_have_the_fields_of_the_installed_faster_whisper():
    transcribe = installed_faster_whisper()
```

- [ ] **Step 2: Run them; watch them fail.** `uv run pytest tests/test_ci_workflow.py -q`.
  Expected: `E       KeyError: 'whisper'` (three times) and `3 failed, 4 passed`.
  `VID2SUB_REQUIRE_WHISPER=1 uv run pytest tests/test_faster_whisper_engine.py -q` (the extra
  not installed). Expected: `E   ModuleNotFoundError: No module named 'faster_whisper'` and
  `FAILED …test_the_engine_calls_the_installed_faster_whisper_as_its_signatures_allow`,
  `FAILED …test_the_fakes_have_the_fields_of_the_installed_faster_whisper`: the guard works
  before the job exists.
- [ ] **Step 3: Write the job.** In `.github/workflows/ci.yml`, above the line `  floor:`, add:

```yaml
  whisper:
    # faster-whisper on Windows and Linux (spec §9.5, S45): the suite with the `whisper` extra, so
    # the engine's field check runs against the real library (VID2SUB_REQUIRE_WHISPER=1 fails it
    # where it would skip). Not the `nvidia` extra: its wheels are 553 MB and 743 MB, and the
    # runners have no GPU. The real model stays out (VID2SUB_LIVE_WHISPER is opt-in).
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-24.04, windows-2022]
    runs-on: ${{ matrix.os }}
    timeout-minutes: 30
    permissions:
      contents: read
    env:
      UV_FROZEN: "1"
      VID2SUB_REQUIRE_FFMPEG: "1"
      VID2SUB_REQUIRE_WHISPER: "1"
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with: { persist-credentials: false }
      - uses: astral-sh/setup-uv@1c37ad07a6a961277cf70c0d37d6f313000f5884 # v10.3.0
        with: { version: "0.13.1" }
      - name: ffmpeg (Linux)
        if: runner.os == 'Linux'
        run: sudo apt-get update && sudo apt-get install -y ffmpeg
      - name: ffmpeg (Windows)
        if: runner.os == 'Windows'
        run: choco install ffmpeg -y --no-progress
      - run: uv sync --group dev --extra whisper --python 3.12
      - run: uv run --python 3.12 --extra whisper pytest

```

  In `tests/README.md`, below the `make check` item (its second line is
  `  gitleaks. It runs no browser or live test.`), add:

```markdown
- faster-whisper's field and signature checks (`tests/test_faster_whisper_engine.py`) need the
  `whisper` extra (`uv sync --group dev --extra whisper`); they skip without it unless
  `VID2SUB_REQUIRE_WHISPER=1`, which CI's `whisper` job (Windows and Linux) sets. No test downloads
  the model; only the live test below does.
```

  In the spec, `docs/superpowers/specs/2026-10-14-vid2sub-design.md`, §23.2 (Decision 20),
  replace

```markdown
`frontend` (typecheck, Vitest, build), `e2e`, `leaks`.
```

  with

```markdown
`frontend` (typecheck, Vitest, build), `e2e`, `leaks`, and `whisper` (Ubuntu and Windows ×
Python 3.12, with the `whisper` extra, so faster-whisper's field check runs instead of skipping).
```

- [ ] **Step 4: Run the checks; they pass.** `uv run pytest tests/test_ci_workflow.py
  tests/test_faster_whisper_engine.py -q` first (`35 passed, 2 skipped, 1 deselected`), then
  `make actionlint` (no output, exit 0), then the job's own commands with the extra:
  `uv sync --group dev --extra whisper`, then `VID2SUB_REQUIRE_FFMPEG=1
  VID2SUB_REQUIRE_WHISPER=1 UV_FROZEN=1 uv run --extra whisper pytest -q`
  (`1314 passed, 7 skipped, 46 deselected` here on macOS: both checks run), then
  `uv sync --group dev` to go
  back. **Guard checks**, each reverted and restored, each with `uv run pytest
  tests/test_ci_workflow.py -q`: take the job's `VID2SUB_REQUIRE_WHISPER: "1"` line out (`FAILED
  …test_the_whisper_job_fails_where_the_field_check_would_skip`); make its sync
  `--extra nvidia` (`FAILED
  …test_the_whisper_job_installs_the_whisper_extra_and_never_the_nvidia_one`). `make check`.
  Expected: `1312 passed, 9 skipped, 46 deselected` twice, `Test Files  24 passed (24)`,
  `Tests  115 passed (115)`, `All checks passed!` and `no leaks found`.
- [ ] **Step 5: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
ci: 🤖 faster-whisper's tests run on Windows and Linux with the whisper extra, and fail there rather than skip

ci.yml gains the `whisper` job (spec §9.5, §23.2; S45): ubuntu-24.04 and
windows-2022, Python 3.12, `uv sync --group dev --extra whisper`, then
the whole suite through `uv run --extra whisper pytest`, with ffmpeg as
the python job installs it. VID2SUB_REQUIRE_WHISPER=1 makes the engine's
field check, and a new signature check (WhisperModel takes device and
compute_type; transcribe takes language, initial_prompt, word_timestamps
and vad_filter; download_model takes local_files_only; CTranslate2 counts
its GPUs), fail where faster-whisper isn't installed instead of skipping,
as VID2SUB_REQUIRE_FFMPEG does for media tests. Not the `nvidia` extra:
its cuBLAS and cuDNN wheels are 553 MB and 743 MB, and the runners have
no GPU. The real model stays out: VID2SUB_LIVE_WHISPER is opt-in. The job
keeps §23.1's hardening: actions pinned by commit with their versions,
contents: read, persist-credentials: false, a timeout, UV_FROZEN=1.

tests/test_ci_workflow.py reads the workflow as Actions does (PyYAML):
the job, its matrix, the extra and never `nvidia` in any job's run steps,
its env, no live test anywhere, the python job still running the whole
suite on windows-2022 (where Phase 3 Task 1's Windows-only tests run),
and every job's pins, timeout, read-only permissions and checkouts that
keep no token. tests/README.md names VID2SUB_REQUIRE_WHISPER, and the
spec's §23.2 names the job (Decision 20).

The new tests failed first with: KeyError: 'whisper' (3 failed, 4
passed); with the variable set and no extra, the field and signature
checks fail with ModuleNotFoundError: No module named 'faster_whisper'.
Guard checks, each reverted and restored: without the job's
VID2SUB_REQUIRE_WHISPER, or with --extra nvidia, its test fails. The job's
two commands, run here (macOS) with the extra, pass the suite with both
checks running: 1143 passed, 2 skipped. `make actionlint` passes. Only a
real run shows the Windows and Linux wheels installing (ctranslate2
4.8.3, av 19.0.2, tokenizers 0.23.3) and the suite passing there.

Docs read: GitHub's "GitHub-hosted runners" reference (ubuntu-24.04 and
windows-2022 are current labels, 4 CPUs and 16 GB); setup-uv's README
(`version` pins uv; caching defaults to on for GitHub-hosted runners);
`uv run --help` 0.13 (--extra; run syncs inexactly unless --exact).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md Task 10
Co-Authored-By: <the model's own line>
```

  `git add .github/workflows/ci.yml tests/test_ci_workflow.py
  tests/test_faster_whisper_engine.py tests/README.md
  docs/superpowers/specs/2026-10-14-vid2sub-design.md`, `git commit -F .git/COMMIT_MSG`, then
  `git log -1 --format='%(trailers)'` shows `Plan:`.
- [ ] **Step 6: Review, look forward, close.** The Tier 3 self-review from
  `$(cat .git/TASK_BASE)` (*Standards*, *Spec*) plus `make check` and `make actionlint`; the
  forward review over Task 11 (the README names the job only through `tests/README.md`) and
  Task 12 (its Step 8 looks for this job's two entries in the run). Then the close, its own commit,
  holding this plan with this task's boxes ticked and **Now** set to `Task 11: The docs, open.`,
  with the message in `.git/CLOSE_MSG`:

```text
docs(plan): 🤖 close Task 10: CI on Windows and Linux for faster-whisper

Drift: none
Rulings: none
Phase-end: none
Forward: none
Tier: 3
Rounds: self-review (Standards, Spec); make check; make actionlint
Findings: none

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md Task 10
Co-Authored-By: <the model's own line>
```

  `git add docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md`, `git commit -F
  .git/CLOSE_MSG`.

***

### Task 11: The docs

**Tier:** 3

The README, `tests/README.md` and `docs/architecture.md` brought up to what Phase 3 built (spec
§23.5's README contents; AGENTS.md, *Docs and security*). The CHANGELOG is the phase end's (its
step 7), so it is left alone.

**Why it is written this way** (read 2026-10-24):
- **Decision 10 waits on Dan.** faster-whisper's README asks for cuBLAS for CUDA 12 and cuDNN 9
  for CUDA 12; the spec (§4.2, §9.5, S45) names cuBLAS 12 only. The README's GPU paragraph says
  what the code does (Task 9: `[nvidia]` installs both; doctor's **CUDA libraries** check looks
  for both, on `PATH` on Windows and through the loader, `LD_LIBRARY_PATH`, on Linux) and names
  the Decision, so it reads true once Dan says yes; a no changes the code and this paragraph
  together.
- **The README names what a person sees**, not the plan: Add's places and what the browser hides
  (Decisions 1–3 and 24), Review's sampling, suggestions and choices (Decisions 4–7 and 25), the
  queue's Pause and Resume, its banner and the 30-second wait (Decisions 8, 9 and 23), the Models
  page, and the demo's one place and canned suggestions (Decisions 21 and 22). Only Decision 10
  is cited by number, since it may still change.
- **Task 7 wrote the Make preview copy sentence and the `cache clear` line, and Tasks 9 and 10
  `tests/README.md`'s `VID2SUB_LIVE_WHISPER` and `VID2SUB_REQUIRE_WHISPER`;** this task checks
  them and adds what is still missing: Add's YouTube test fakes yt-dlp, and which browser tests
  run on one system only.
- **The diagrams draw Phase 3's parts solid**, and a script checks every name they use against
  the code, as Phase 2 Task 22's did, now over the whole page.

**Files:**
- Modify: `README.md`, `tests/README.md`, `docs/architecture.md`
- Modify at the close: this plan

**Interfaces:**
- Consumes: Task 7's README sentence on **Make preview copy** and its `cache clear` line, already
  written; Task 9's NVIDIA notes, which the README still needs (cuBLAS 12 and cuDNN 9, Decision
  10: on `PATH` on Windows, through `LD_LIBRARY_PATH` on Linux; §23.5), the `whisper` and
  `nvidia` extras, the starter's `[models.local-whisper]` and doctor's **CUDA libraries** check;
  Task 8's Models page; Task 10's `whisper` job. From Tasks 1–6, the README documents: Add (the
  browser's places, and what it hides: Decisions 1–3 and 24); Review (Discard, **Apply to all**,
  and **Allow cloud models for this run** unticked every time); Pause, Resume, the banner and the
  30-second wait (Decision 23); the demo's one place and its canned suggestions (Decisions 21 and
  22).
- Produces: none (docs only).

- [ ] **Step 0: Record the base:** `git rev-parse HEAD > .git/TASK_BASE`.
- [ ] **Step 1: The README.**
  In `README.md`, replace

```markdown
Status: Phase 1 (M1, the command line) and Phase 2 (M2, the web editor) are built; the spec's
status line says which have merged.
```

  with

```markdown
Status: Phase 1 (M1, the command line), Phase 2 (M2, the web editor) and Phase 3 (M3: adding
and reviewing seasons in the app, and Windows and Linux) are built; the spec's status line says
which have merged.
```

  Then replace

```markdown
uv tool install --editable '.[mac]'   # on a Mac: Qwen3-ASR in-process
uv tool install --editable .          # elsewhere
```

  with

```markdown
uv tool install --editable '.[mac]'      # on a Mac: Qwen3-ASR in-process
uv tool install --editable '.[whisper]'  # on Windows or Linux: Whisper in-process
uv tool install --editable '.[nvidia]'   # the same, on an NVIDIA GPU
uv tool install --editable .             # only your own servers (the Spark, OpenAI)
```

  Then replace

```markdown
environment instead: `uv sync --extra mac` and `uv run vid2sub …`.
```

  with

```markdown
environment instead: `uv sync --extra mac` (or `--extra whisper`, `--extra nvidia`) and
`uv run vid2sub …`.

**Whisper on Windows and Linux** (`[whisper]`) runs Whisper large-v3 or large-v3-turbo through
faster-whisper, on the CPU (int8) or, with `[nvidia]`, on an NVIDIA GPU (float16). The GPU needs
CUDA 12's cuBLAS and cuDNN 9 (the Phase 3 plan's Decision 10): `[nvidia]` installs both as Python
packages, and they must be where faster-whisper finds them before vid2sub starts, their `bin`
folders on `PATH` on Windows and their `lib` folders in `LD_LIBRARY_PATH` on Linux, as
faster-whisper's README shows; NVIDIA's CUDA 12 toolkit and cuDNN 9 serve as well. Without them
vid2sub runs on the CPU and says what is missing, and `vid2sub doctor`'s **CUDA libraries** check
names it and the fix. The first run downloads the model from Hugging Face (1.6 GB for
large-v3-turbo, 3.1 GB for large-v3); with no network then, the episode fails at once, naming the
download, and later runs load the model from its cache.
```

  Then below these lines

```markdown
  the starter's `[models.spark-qwen]`: Cantonese and Mandarin then go to the Spark first.
```

  add:

```markdown
- **Whisper on this machine** (Windows, Linux, with `[whisper]` or `[nvidia]`): uncomment the
  starter's `[models.local-whisper]` (`engine = "faster-whisper"`); its `catalog` is turbo, for
  English, and `whisper-large-v3` suits Japanese.
```

  Then replace

```markdown
**Jobs**, beside **Editor** under the top bar, makes subtitles for videos already on this
machine, as `vid2sub run` does: type their full paths, one a line, then **Start**. Jobs run one
at a time, with the session's languages and formats and never a cloud model, and each shows its
stage and chunk ("transcribing 7/11"). **Cancel** takes a waiting job out, or stops the running
one before its next chunk or translation batch. The jobs belong to the engine, so every tab
shows them and closing a tab cancels nothing; **Open in editor** opens a finished one. In the
demo, jobs run only on the demo's own clip.
```

  with

```markdown
**Add**, beside **Editor** under the top bar, takes what to make subtitles for: videos and
folders picked in its file browser, full paths typed in, or a YouTube link, with **keep video**
to keep the whole video rather than its audio (in `[defaults] youtube_dir`, else a `vid2sub`
folder in your Videos folder). The browser starts at your home folder and the mounted volumes
(`/Volumes` on a Mac, the drive letters on Windows, `/media`, `/run/media/<you>` and `/mnt` on
Linux) and shows only folders, videos and subtitle files, a season in `SxxEyy` order. It hides
dotfiles, the folders that hold credentials (`.ssh`, `.aws`, `.gnupg`, `.config/gh` …),
`Library` and `AppData` in every user's folder, and folders the system marks hidden. It never
lists or follows a link, so a media folder linked into your home is added by its real path
(under `/Volumes`, say) or from the CLI. It reaches only your home, the volumes and a Windows
network path (`\\server\share`) you type; a library elsewhere, such as `/srv`, is added from the
CLI. A folder adds its own videos, not its subfolders'. A sleeping network share can take a few
seconds to answer, and the browser says it is waiting.
```

  Then replace

```markdown
Retranslate, Settings and Jobs need an engine that makes subtitles, so the Pages editor
(Phase 4) leaves them out.
```

  with

```markdown
**Review** then shows a row per file. The first two files of each folder are sampled in the
background: three 20-second windows of speech give the language and how sure ("Mandarin or
Cantonese?" when Whisper heard Chinese), and a transcription and a translation model are
suggested as `vid2sub run` would pick them, never a cloud one. The rest of the folder takes the
sampled files' choices when they agree. Change any row's language, audio track, models,
languages to translate to, formats or script; **Apply to all** copies that choice to every row.
A row whose language is uncertain can still start, with its warning; only "Mandarin or
Cantonese?" or a row with no language waits for you. **Allow cloud models for this run** starts
unticked in every review, and a cloud model is only ever your own pick. **Start** queues every
row and opens **Jobs**; **Discard** drops the review, which otherwise stays while you switch
screens, until a new Add, Start or closing the tab. A YouTube link isn't sampled: its language
and models are decided when it runs.

**Jobs** runs them one at a time, each with its row's choices; it also takes full paths typed
into its box, one a line, which run as `vid2sub run` would, with the session's languages and
formats and never a cloud model. Each job shows its stage and chunk ("transcribing 7/11").
**Cancel** takes a waiting job out, or stops the running one before its next chunk or
translation batch. **Pause** stops the running job at its next chunk and starts nothing until
**Resume**. When a server stops answering (the Spark's tunnel down, the laptop asleep), the job
retries for 30 seconds, then the whole queue pauses, with a banner saying why and how to fix it,
rather than failing every remaining episode in turn (the CLI waits ten minutes); **Resume**
carries on from the chunk that failed. While the queue has work and isn't paused, vid2sub keeps
the computer awake; paused or idle, it lets it sleep. The jobs belong to the engine, so every tab
shows them and closing a tab cancels nothing; **Open in editor** opens a finished one.

**Models** shows the catalog, each model in `vid2sub.toml` marked usable on this machine now or
why not (a server not answering, a key not set, an extra not installed), as `vid2sub models`
says; catalog models `vid2sub.toml` doesn't name are greyed, with "add it to vid2sub.toml". It
checks each time it opens, and on **Check again**.

In the demo, Add browses only the demo's own folder, Review suggests the demo's canned models
under the names they stand in for (Whisper large-v3-turbo and Gemma 4), and jobs run only on the
demo's own clip.

Retranslate, **Make preview copy**, Settings, Add, Review, Jobs and Models need an engine that
makes subtitles, so the Pages editor (Phase 4) leaves them out.
```

- [ ] **Step 2: `tests/README.md`.**
  In `tests/README.md`, replace

```markdown
  fake servers on this machine. Each test starts its own server on a free port, with its own
```

  with

```markdown
  fake servers on this machine (Add's YouTube test runs vid2sub through
  `tests/e2e/fake_youtube.py`, which fakes yt-dlp, so no test reaches YouTube). Each test starts
  its own server on a free port, with its own
```

  Then below the line `and keeps them when the job fails.`, add:

```markdown
- Some of the file browser's tests (`tests/test_browse.py`) run on one system only: junctions,
  the hidden attribute, 8.3 short names and `\\?\` names on Windows; the hidden flag and the
  other Unicode form on macOS; a name that isn't valid Unicode on Linux. CI's `python` job runs
  the whole suite on all three, so each runs there.
```

- [ ] **Step 3: `docs/architecture.md`.**
  In `docs/architecture.md`, replace

```markdown
the page and runs the editor and the Jobs page. With `--demo`, `web.demo.runtime_for` builds the
same parts around a `DemoBackend` that opens only its copy's episode, with a canned engine and
translation, and `isolate()`'s audit hook refuses any write outside the copy and any connection
beyond this machine.
```

  with

```markdown
the page and runs the editor, Add, Review, the Jobs page and Models. With `--demo`,
`web.demo.runtime_for` builds the same parts around a `DemoBackend` that opens only its copy's
episode, with a canned engine and translation, and `isolate()`'s audit hook refuses any write
outside the copy and any connection beyond this machine. Its Add browses only the copy, and its
Review suggests the canned models.
```

  Then replace

```markdown
tab's requests one at a time, in order; the job queue is the engine's, shared by every tab.
```

  with

```markdown
tab's requests one at a time, in order; the job queue is the engine's, shared by every tab, and
pauses and resumes as a whole. Phase 3's screens reach the core the same way: Add's file browser
(`web.browse`, which lists only home and mounted volumes, spec §6.5), each tab's `Reviewer`
(`vid2sub.review`: sampling, suggestions and Start, each row queued with its own runner), the
preview copy (`media.preview`, beside the playback audio) and the Models page (`review.models`,
as `vid2sub models` lists them). faster-whisper is an in-process engine behind the Engine
protocol, as `mlx-qwen3-asr` is.
```

  Then replace

```markdown
    editor["Editor, per tab<br/>open, edit, undo, redo, save,<br/>resolve, retranslate: in order"]
    views["web.views<br/>episode_view · jobs_view: plain JSON"]
```

  with

```markdown
    editor["Editor, per tab<br/>open, edit, undo, redo, save,<br/>resolve, retranslate: in order;<br/>a preview copy beside them"]
    reviewer["Reviewer, per tab<br/>Add's videos sampled off the loop;<br/>choices, Start"]
    views["web.views<br/>episode_view · jobs_view · browse_view ·<br/>review_view · models_view: plain JSON"]
```

  Then replace

```markdown
    queue["jobs.Queue<br/>one worker thread, one job at a time"]
```

  with

```markdown
    queue["jobs.Queue<br/>one worker thread, one job at a time;<br/>pause · resume · keep awake"]
    browse["web.browse<br/>home and mounted volumes:<br/>folders, videos, subtitles"]
    review["vid2sub.review<br/>prepare · sample · start · models"]
    preview["media.preview<br/>playback audio · preview copy"]
```

  Then below the line `server --> editor`, add:

```markdown
  server --> reviewer
```

  Then replace

```markdown
  server -->|"jobs_submit · job_cancel"| runtime
```

  with

```markdown
  server -->|"jobs_submit · job_cancel ·<br/>queue_pause · queue_resume ·<br/>browse · add · models_check"| runtime
  reviewer -->|"runtime.blocking"| runtime
```

  Then below the line `runtime --> backend & queue & tokens & keys`, add:

```markdown
  runtime --> browse & review & preview
  review -->|"each row's own runner"| queue
```

- [ ] **Step 4: Check them.** The model table and the targets, as Phase 2 Task 22 checked them:

```bash
cp README.md .git/README.edited && make readme && cmp README.md .git/README.edited && echo "model table unchanged"
diff <(grep -oE '^make [a-z0-9-]+' README.md | cut -d' ' -f2 | sort) <(make help | awk '{print $1}' | sort) && echo "every target named"
```

  Expected: `model table unchanged` and `every target named`. Then every name the architecture
  page uses is in the code, the planned parts are the only dashed arrows, and no doc still says
  what Phase 3 changed:

```bash
uv run python - <<'PY'
import importlib, re
from pathlib import Path
text = Path("docs/architecture.md").read_text(encoding="utf-8")
missing = []
names = set(re.findall(r"\b(?:vid2sub|web|jobs|engines|pipeline|runtime|review|media)(?:\.\w+)+",
                       text)) - {"vid2sub.jsonl"}  # the sidecar's suffix
for name in sorted(names):
    parts = name.split(".")
    parts = parts[1:] if parts[0] == "vid2sub" else parts
    parts = (["web"] if parts[0] == "runtime" else []) + parts
    for i in range(len(parts), 0, -1):
        try:
            obj = importlib.import_module("vid2sub." + ".".join(parts[:i]))
        except ImportError:
            continue
        for attr in parts[i:]:
            obj = getattr(obj, attr, None)
        break
    else:
        obj = None
    if obj is None:
        missing.append(name)
src = "\n".join(p.read_text(encoding="utf-8") for p in Path("src/vid2sub").rglob("*.py"))
missing += [w for w in ("HostGuard", "WriteGuard", "TokenGuard", "class Editor", "class Reviewer",
                        "def isolate", "def browse_view", "def review_view", "def models_view",
                        "input.jobs_submit", "input.job_cancel", "input.queue_pause",
                        "input.queue_resume", "input.browse", "input.add", "input.models_check",
                        "def keep_awake", "def preview_copy", "def make_preview", '"/healthz"',
                        "/media/{token}")
            if w not in src]
print("missing:", missing)
PY
grep -c -- '-\.->' docs/architecture.md
grep -n -e 'not in vid2sub.toml' -e 'from M3' -e '(Phase 3)' -e 'unverified' README.md \
  tests/README.md docs/architecture.md src/vid2sub/example.toml vid2sub.example.toml
grep -n 'not yet' README.md tests/README.md docs/architecture.md
```

  Expected: `missing: []` (with a name misspelt, say `web.browsee`, it prints
  `missing: ['web.browsee']`), then `2` (the dashed arrows to the Spark's Qwen3-ASR and to
  Pages), nothing from the first `grep`, and from the second only `README.md:230:durations) are
  shown, not yet changeable.` (the cue rules, which Phase 3 didn't touch). The diagrams render on
  GitHub's view of the file; this listing's were rendered with mermaid 11.4.1 in Chromium. Then
  `make check`. Expected: `1312 passed, 9 skipped, 46 deselected` twice,
  `Test Files  24 passed (24)`, `Tests  115 passed (115)`, `All checks passed!` and
  `no leaks found`.
- [ ] **Step 5: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
docs: 🤖 the README covers Add, Review, Pause and Resume, the Models page and Whisper on Windows and Linux, and the diagrams draw Phase 3's parts

README.md: the status line names Phase 3; Install adds the whisper and
nvidia extras, and what the GPU needs: CUDA 12's cuBLAS and cuDNN 9
(the Phase 3 plan's Decision 10, which waits on Dan), on PATH on Windows
and in LD_LIBRARY_PATH on Linux, as doctor's CUDA libraries check says,
with the CPU otherwise and the first run's download (spec §9.5, §23.5);
Configure adds the starter's [models.local-whisper]. The editor section
adds Add (the browser's places, what it hides, links never followed,
roots only: Decisions 1-3 and 24), Review (sampling, local suggestions,
inheriting, Apply to all, an uncertain row still starting, Allow cloud
unticked every time, Discard: Decisions 4-7 and 25), Jobs with Pause,
Resume, the banner and the 30-second wait (Decisions 8, 9 and 23), the
Models page (S44), and the demo's one place and canned suggestions
(Decisions 21 and 22); Pages leaves all of them out. Task 7's Make
preview copy sentence and cache clear line were already there.

tests/README.md: VID2SUB_REQUIRE_WHISPER and VID2SUB_LIVE_WHISPER were
already named (Tasks 9 and 10); it now says Add's YouTube test fakes
yt-dlp, and which browser tests run on one system only.

docs/architecture.md: Phase 3's parts drawn solid: Add's file browser
(web.browse), each tab's Reviewer and vid2sub.review, the queue's pause,
resume and keep-awake, the preview copy (media.preview) and the Models
page's input; faster-whisper was already solid (Task 9). A script
imported every dotted name on the page and found every function,
class, input and route it names in the code (75 found, none missing);
mermaid 11.4.1 rendered all three diagrams in Chromium (the first with
its two planned edges dashed).

Grepped README.md, tests/README.md, docs/architecture.md, AGENTS.md and
the starter configs for the names Phase 3 changed ("not in
vid2sub.toml", doctor's old cuBLAS check, "from M3", "(Phase 3)") and
for "not yet", "planned", "Phase 3" and "unverified": none left where
Phase 3 built the thing (the README's cue rules are still shown, not
yet changeable; the CHANGELOG is the phase end's).

Docs read: faster-whisper 1.2.1's README (GPU: cuBLAS for CUDA 12 and
cuDNN 9; the pip wheels, on Linux through LD_LIBRARY_PATH; on Windows a
folder on PATH), as Task 9's commits cite it.

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md Task 11
Co-Authored-By: <the model's own line>
```

  `git add README.md tests/README.md docs/architecture.md`, `git commit -F .git/COMMIT_MSG`,
  then `git log -1 --format='%(trailers)'` shows `Plan:`.
- [ ] **Step 6: Review, look forward, close.** The Tier 3 self-review from
  `$(cat .git/TASK_BASE)` (*Standards*, *Spec*) plus `make check`; the forward review over Task
  12 (its Steps 2 and 7 install and configure as the README now says) and Phase 4 (its install
  index and README carry the same install lines). Then the close, its own commit, holding this
  plan with this task's boxes ticked and **Now** set to `Task 12: The M3 exit test (with Dan),
  open.`, with the message in `.git/CLOSE_MSG`:

```text
docs(plan): 🤖 close Task 11: The docs

Drift: none
Rulings: none
Phase-end: none
Forward: none
Tier: 3
Rounds: none
Findings: none

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md Task 11
Co-Authored-By: <the model's own line>
```

  `git add docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md`, `git commit -F
  .git/CLOSE_MSG`.

***

### Task 12: The M3 exit test (with Dan)

**Tier:** 3 · **Scenarios:** S38, S40, S41, S42, S45 · **[Dan]**, on Dan's Mac and one Windows or
Linux machine

Spec §25's M3 exit test ("add a season folder, review it, run it unattended; the Windows and Linux
path passes CI and one manual run"), plus §29's M3 check (CUDA's libraries for faster-whisper on
Windows). The implementer prepares and records; Dan runs every step on his media and machines.

**Files:**
- Modify: `docs/superpowers/specs/2026-10-14-vid2sub-design.md` (§29's M3 results, the Scenarios
  rows, Open items)

**Interfaces:** none (no code).

- [ ] **Step 0: Record the base:** `git rev-parse HEAD > .git/TASK_BASE`.
- [ ] **Step 1: List the [Dan] steps** (2 to 7 below), one line each, with the count, then present
  Step 2. Set **Now** to `waiting on Dan: Task 12, Step 2` in a wip commit
  (`chore(plan): 🤖 wip Task 12: waiting on Dan for the M3 exit test`; `Done so far:` the list,
  `Stopped at:` Step 2, `Tests:` `make check` and `make e2e` green at the base).
- [ ] **Step 2: [Dan] Start the app on the Mac:**

```bash
uv tool install --editable '.[mac]'
(cd frontend && npm ci && npm run build)
vid2sub serve
```

  Expected: the browser opens on the app through the launch link.
- [ ] **Step 3: [Dan] Add a season folder through Browse (S38):** pick a season on a mounted
  volume (the NAS share under `/Volumes`), not one typed into the box. Expected: the browser
  starts at home and the mounted volumes; it shows only folders, videos and subtitles; no dotfile
  or credential folder appears in home; the season's episodes are listed in `SxxEyy` order.
  Add, and Review opens.
- [ ] **Step 4: [Dan] Review it (S40):** expected: the first two files are sampled, each row shows
  a detected language with its confidence and a suggested transcription and translation model,
  and the rest of the folder inherits their choices where they agree. Change one row's target and
  use **Apply to all**. **Allow cloud models for this run** is unticked; leave it so. Start: the
  Jobs page lists the season's episodes.
- [ ] **Step 5: [Dan] Drop the connection once (S41):** while an episode is transcribing on the
  Spark, stop the tunnel to it (local-ai's), wait a minute, then start it again. Turning the Wi-Fi
  off would also drop the NAS share, which is a different failure. Expected: about 30 seconds
  after the tunnel stops (Decision 23), the whole queue pauses with a banner giving the reason
  and **Resume**, and no job is marked failed. After
  **Resume**, the job carries on from the chunk that failed (its progress doesn't start again at
  1), and the queue moves on.
- [ ] **Step 6: [Dan] Leave it running overnight (S42):** before leaving it, run
  `pmset -g assertions | grep -i caffeinate`. Expected: a `PreventUserIdleSystemSleep` line. In
  the morning: every episode has its subtitles next to it, and the same command prints nothing
  once the queue has finished.
- [ ] **Step 7: [Dan] One manual run on Windows or Linux (S45),** on whichever machine you have.
  Note its OS, and whether it has an NVIDIA GPU. In a checkout of the `phase-3` branch:

```bash
uv tool install --editable '.[whisper]'      # '.[nvidia]' instead on a machine with an NVIDIA GPU
vid2sub doctor
vid2sub config path
```

  Then put a `vid2sub.toml` where `config path` says. It needs the commented
  `[models.local-whisper]` entry from `vid2sub config init`, with its three lines uncommented.
  Then:

```bash
vid2sub models
vid2sub run <a short English video> --from en --to none --model local-whisper
```

  Expected: `doctor` says faster-whisper runs on the CPU, or, with an NVIDIA GPU, its `CUDA
  libraries` check says it found cuBLAS 12 and cuDNN 9 (or names what is missing and how to
  install it). `models` prints `✓ local-whisper: Whisper large-v3-turbo (transcribe)` (Task 8),
  and each other catalog entry ending `add it to vid2sub.toml`. The run writes the `.en.srt` next
  to the video; the first run downloads the model (about 1.6 GB). Note what `doctor` printed, and
  how long the run took.
- [ ] **Step 8: Check CI's Windows and Linux path:** the newest run on `phase-3` has Task 10's
  Windows and Linux faster-whisper jobs green, and every other job too:

```bash
gh run list --branch phase-3 --workflow ci.yml --limit 3
gh run view "$(gh run list --branch phase-3 --workflow ci.yml --limit 1 --json databaseId --jq '.[0].databaseId')"
```

  Expected: the newest run's conclusion is `success`, and its job list includes Task 10's
  `whisper (ubuntu-24.04)` and `whisper (windows-2022)`.
- [ ] **Step 9: Record the results in the spec.** §29's M3 bullet gets Step 7's result, dated:
  the OS, CPU or NVIDIA, and what `doctor`'s `CUDA libraries` check said. Set S38, S40, S41, S42
  and S45 to `verified` where they passed. A failure caused by a bug is a new task, proposed to
  Dan; a result that would change the spec is the fifth stop.
- [ ] **Step 10: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
docs(spec): 🤖 M3's exit test results: <what passed, in one line>

<each result in a line: the browse, the review, the pause and resume, the night's run, the
Windows or Linux run and what doctor said, CI; the rows set to verified; anything still pending
and why>

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md Task 12
Co-Authored-By: <the model's own line>
```

  `git add docs/superpowers/specs/2026-10-14-vid2sub-design.md`, `git commit -F .git/COMMIT_MSG`,
  then `git log -1 --format='%(trailers)'` shows `Plan:`.
- [ ] **Step 11: Review, look forward, close.** The Tier 3 self-review from
  `$(cat .git/TASK_BASE)` (*Standards*, *Spec*) plus `make check`; the forward review over the
  Phase 4 plan (Step 7's install steps are what Phase 4's install index and README describe).
  Then the close, its own commit, holding this plan with this task's boxes ticked and **Now** set
  to `Phase end, step 1: The final whole-branch review.`, with the message in `.git/CLOSE_MSG`:

```text
docs(plan): 🤖 close Task 12: The M3 exit test (with Dan)

Drift: none
Rulings: none
Phase-end: none
Forward: none
Tier: 3
Rounds: self-review (Standards, Spec); make check
Findings: none

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md Task 12
Co-Authored-By: <the model's own line>
```

  `git add docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md
  docs/superpowers/specs/2026-10-14-vid2sub-design.md`, `git commit -F .git/CLOSE_MSG`.

***

### Task 13: Phase end

Each box is one step of plan-driven-development's phase end, run as its `references/phase-end.md`
gives it, in the project's root folder on `phase-3`. A step ends with its commit
(`docs(plan): 🤖 phase end step K: <what it did>`, trailer
`Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md Phase end`), which ticks its box and
sets **Now** to `Phase end, step K+1: <its title>.` After a crash, resume at the first unticked
box; never re-run a ticked one.

If the hooks and `scripts/leakcheck.py` still don't exist by then (`AGENTS.md`'s interim line),
two steps differ: step 8's text scans run `gitleaks stdin` only, and the merge waits for Dan, as
every push does.

- [ ] **1. The final whole-branch review:** Matt Pocock's two-axis `code-review` from
  `git merge-base main HEAD`; then one fix dispatch and one scoped re-review (`AGENTS.md`,
  *Reviews*), with a ruling on whatever is left. Each fix is its own commit.
- [ ] **2. The rest of the ledger copied into the plan:** whatever
  `.superpowers/sdd/2026-10-23-vid2sub-phase-3/progress.md` holds that no closing commit carries,
  under the task it belongs to.
- [ ] **3. The phase-end council:** four read-only reviewers (goal fit and scenarios,
  reliability, security, simplicity) on the whole branch; their reports committed first, in
  `docs/superpowers/plans/2026-10-23-vid2sub-phase-3-end-council.md`; each claim checked against
  the code before Dan sees it; each finding a severity and a decision.
- [ ] **4. The phase-end list worked through:** each row of this plan's Phase-end list fixed in
  its own commit at the tier of what it touches, or moved to the spec's Later with a reason.
  Missing docs are written now; in `docs/architecture.md`, Phase 3's parts turn solid.
- [ ] **5. The forward look:** the Phase 4 plan rewritten to fit what was built (every listing
  that consumes a Phase 2 or Phase 3 interface checked against the code).
- [ ] **6. The retro:** `docs/superpowers/plans/2026-10-23-vid2sub-phase-3-retro.md`, in four
  parts (departures from the plan, items carried forward, metrics per tier, starting over), from
  the closing commits:

```bash
base=$(git merge-base main HEAD)
git log --format='%h %s%n%b' --grep='close Task' "$base..HEAD"
git log --format='%h %s' --grep='reopen Task' --grep='escaped from Task' "$base..HEAD"
```

  Then the retuning rules set Phase 4's tiers, written into its plan and the retro.
- [ ] **7. A dated `CHANGELOG.md` entry** for Phase 3, and the spec's status line set to
  `Phase 3 (M3) PR open (#N)`, its number filled in once step 8 opens the PR.
- [ ] **8. The PR:** superpowers:finishing-a-development-branch, its PR option. The title is
  `chore(repo): 🤖 merge Phase 3: adding, reviewing, and every platform`; the body summarises what
  each task built, the council's findings and what became of them, links the retro, lists every
  file no scan can read for Dan to check by eye, and ends with
  `Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md Phase end`. The files no scan can
  read:

```bash
git log --format= --numstat origin/main..HEAD |
  awk '$1 == "-" { print "not scanned, check by eye: " $3 }'
```

  With the title in `.git/PR_TITLE` and the body in `.git/PR_BODY.md`, then, after Dan's OK to
  push and open it:

```bash
if cat .git/PR_TITLE .git/PR_BODY.md |
     gitleaks stdin --redact --no-banner --config .gitleaks.toml; then
  gh pr create --base main --head phase-3 \
    --title "$(cat .git/PR_TITLE)" --body-file .git/PR_BODY.md
else
  echo "STOP: the PR text has a finding; tell Dan its kind and where, never the matched text"
fi
```

  Attended: the PR waits for Dan's merge (a merge commit, never squash or rebase).
- [ ] **9. After the merge:** the Pages site arrives in Phase 4, so there is still no live site to
  check; the status line's `merged` entry comes with Phase 4's start.

***

## Phase-end list

| Source task | Severity | File | Finding | Status |
|---|---|---|---|---|
| Task 1 (planning review) | Minor | `src/vid2sub/web/browse.py` | A folder swapped for a link between the browser's check and the job opening the file (a shared NAS, a removable drive) is followed; the checks run on what the disk returned at listing time | open |
| Task 1 (planning review) | Minor | `src/vid2sub/web/browse.py` | `Library` and `AppData` are hidden in home on every OS, which hides more than it needs to on Linux | open |
| Task 1 (planning review) | Minor | `tests/test_browse.py` | The junction, hidden-attribute and 8.3 short-name tests run only on Windows CI, so a Mac or Linux run can't catch a break there | open |
| Task 1 (planning) | Minor | `src/vid2sub/security.py` | `safe_component` doesn't strip a space before its reserved-name lookup, so `CON .x [id]` passes where `qualified` refuses it (predates the task); one shared helper | open |
| Task 1 (planning) | Minor | `src/vid2sub/web/browse.py` | A home that is itself a link can't be browsed or added, since a root that is a link is refused | open |
| Task 1 (planning) | Minor | `src/vid2sub/web/browse.py` | A root that is itself a `Users` or profile share (`//pc/Users` mounted under `/mnt`, a drive mapped onto a profile) still lists `AppData` where no hidden flag can be read; `_in_a_profile` could also look at the root's own parts | open |
| Task 1 (planning) | Minor | `src/vid2sub/web/browse.py` | A volume's name, or a typed name the walk finds, that isn't valid Unicode can still reach `Entry.path` or `Listing.path`; one `_listable` check on mount names and in `_walk` | open |
| Task 2 (planning) | Minor | `src/vid2sub/web/views.py` | A finished YouTube job doesn't open in the editor (`can_open` false), since the job doesn't report the downloaded file's path | open |
| Task 6 (planning) | Minor | `src/vid2sub/pipeline.py` | Resume re-detects the language (three windows) of a job whose language wasn't chosen, as decode and VAD are redone (Decision 8); Review's jobs have theirs chosen, so only the Jobs page's typed paths pay it | open |
| Task 7 (planning) | Minor | `src/vid2sub/web/server.py` | Two tabs that ask for one episode's preview copy at once encode it twice (each into its own temporary name; the later rename wins), doubling the wait; a per-video lock in the runtime would share one encode | open |
