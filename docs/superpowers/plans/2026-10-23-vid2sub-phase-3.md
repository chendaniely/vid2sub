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
   under `/Volumes`, or from the CLI.
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
      `MAX_ENTRIES = 5000`; `MAX_PATH = 4096`
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
      takes seconds), so Task 2's server runs them off the event loop. It shows a `BrowseError`
      as a notice, renders `Entry.name` as plain text, and passes back only what the person
      typed or an `Entry.path` from an earlier listing, never a path read from a file (§6.5).
  - Decided here (the safe answer): links, junctions and other name-surrogate reparse points
    are never listed and never followed; a path through one is refused, whatever it points to.

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
  `751 passed, 2 skipped, 4 deselected` twice, `All checks passed!` and `no leaks found`.
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
  subtitle) fail; restore it. `make check`. Expected: `759 passed, 2 skipped, 4 deselected`
  twice, `All checks passed!` and `no leaks found`.
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
  the existing Windows CI job). `make check`. Expected: `772 passed, 5 skipped, 4 deselected`
  twice, `All checks passed!` and `no leaks found`.
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

- [ ] **Step 16: Review, look forward, close.** The Tier 1 review from `$(cat .git/TASK_BASE)`
  (`AGENTS.md`, *Reviews*, with the security checklist: secrets (none read: only names, types
  and flags); permissions (read-only: what is listed, and that nothing is opened or written);
  network exposure (no link is followed, so none leads to an SMB share; a UNC path only as
  typed or browsed); failing closed (every `OSError` a `BrowseError`; an entry that can't be
  read is hidden); injection (`..`, NUL, device paths and names, a drive inside a path, case
  and Unicode folding, a lone surrogate, very long input); logging (nothing logs; every reason
  is a fixed string with at most `strerror`)). Worth the reviewers' time: Windows (8.3 names,
  junctions, mapped and network drives), which only CI's Windows job runs. The forward review
  over Tasks 2, 10 and 11 and Phase 4: Task 2's Add screen calls `roots`, `listing` and `expand`
  off the event loop, renders `Entry.name` as text, passes back only typed text or an
  `Entry.path` and runs Review on `expand`'s paths; Task 10's Windows job runs this task's
  Windows-only tests; Task 11 documents what the browser shows and hides; Phase 4's Pages
  editor can sort a picked folder with `naming.episode_key` (pure). The docs this task made
  untrue: spec §6.5 doesn't yet say links are never followed: add "Links are never listed or
  followed, and every check runs on the names the disk returns (Phase 3 plan, Task 1)." after
  its in-app file browser bullet. Then the close, its own commit, holding this plan with this
  task's boxes ticked and **Now** set to `Task 2: The Add screen, open.`, and the spec's S38 row
  with "Phase and task" set to `Phase 3, Tasks 1–2`; S38 stays `planned` (its Add half is Task
  2's). The message, in `.git/CLOSE_MSG`:

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

**Interfaces:**
- Consumes: Task 1's `web.browse` (`roots`, `listing`, `expand`, `BrowseError`), called off the
  event loop, a `BrowseError` shown as a notice; `Entry.name` rendered as plain text; only text
  the person typed or an `Entry.path` from an earlier listing is sent back, never a path read from
  a file; `expand`'s output goes to Task 3's `review.prepare(…, keep_video=)`.

<!-- steps: written in the next pass -->

***

### Task 3: Sampling and suggestions for Review

**Tier:** 2 · **Scenarios:** S40

**Files:**
- Create: `src/vid2sub/review.py`
- Modify: `src/vid2sub/jobs.py` (`submit(…, runner=)`: a job's own runner, for Start),
  `src/vid2sub/pipeline.py` (`RunContext.engine` checks the cloud on every call)
- Test: `tests/test_review.py`, `tests/test_jobs.py`

**Interfaces:**
- Consumes: `detect.candidates`, `detect.choose_detector` (always `allow_cloud=False`),
  `detect.detect`, `detect.Detection`; `catalog.CATALOG`, `Candidate`, `suggest`;
  `pipeline.RunContext`, `RunOptions`, `Cancelled`, `run_one`; `media.probe.probe`,
  `pick_track`, `Probe`; `media.decode.decode_to_wav`, `read_wav`, `encode_flac`, `to_float`,
  `SAMPLES_PER_MS`; `media.vad.speech_regions`; `media.youtube.is_url`, `video_id`,
  `NotYouTube`; `subs.naming.target_track`, `track`; `subs.langs.LANGS`;
  `engines.clients.check_allowed`; Phase 2 Task 4's `jobs.Queue` and `Runner`. What `prepare`
  takes is Task 1's `browse.expand` output (full paths) or YouTube links.
- Produces:
  - `jobs.Queue.submit(self, inputs: Sequence[str], *, runner: Runner | None = None)
    -> list[str]`: a job submitted with `runner` is run by it, else by the queue's own; the
    runner is kept while the job waits or runs. Phase 2 Task 19's runner and every existing
    call are unchanged.
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
    - `prepare(inputs: Sequence[str], ctx: RunContext, *, keep_video: bool = False) -> Review`:
      blocks (ffprobe per file, each local server's model list); `allow_cloud` is always False
      and has no parameter
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
    - `start(review, queue: jobs.Queue, ctx: RunContext) -> list[str]` (every row that can
      run, in order, each with its own runner; nothing queued while `problems` isn't empty; a
      failed row left out; the job ids)
  - What Task 4 calls: `prepare` then `sample`, both off the event loop, with `on_row` hopping
    to the session's loop (it runs on the sampling thread, as Task 4's listeners do) and a
    `cancelled` that turns true when the person leaves Review or adds again; `choose`,
    `apply_to_all`, `set_allow_cloud` and `problems` on the loop (pure, fast); `start` with the
    runtime's `Queue` and its job `RunContext` (the one Phase 2 Task 19's runner wraps
    `run_one` with). The view of a row is Task 4's (never `path`; `detection.votes`,
    `detection.confidence`, `warning`, `hint`, `inherited`, `ask_zh_yue`); the box is drawn
    from `Review.allow_cloud` and never from settings.

- [ ] **Step 0: Record the base:** `git rev-parse HEAD > .git/TASK_BASE`.
- [ ] **Step 1: Write the failing test,** `tests/test_review.py`:

```python
"""Review (spec §10, §19.2, S40): sampling, suggestions, "apply to all", and Allow cloud."""

import shutil
import threading
from dataclasses import replace

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
```

- [ ] **Step 2: Run it; watch it fail.** `uv run pytest tests/test_review.py -q`. Expected:
  `E   ImportError: cannot import name 'review' from 'vid2sub' (…/src/vid2sub/__init__.py)` and
  `1 error`.
- [ ] **Step 3: Write the code,** `src/vid2sub/review.py`:

```python
"""The Review screen's backend: what was added, sampled and suggested (spec §10, §19.2, S40).

Adding files probes each in seconds (§10.1). The first two files of each folder are then sampled
in the background: decoded, their speech found, and three ~20 s windows of it language-identified
by the best detector on this machine or your own servers (§10.2–10.3, `detect.detect`); the votes
give a language, a confidence and a "mixed" flag. Whisper often labels Cantonese `zh`, so when
Whisper says `zh` the row asks "Mandarin or Cantonese?". The catalog's route then suggests a
transcription and a translation model (§10.4, §11.2) as M1's pipeline picks them: a model whose
server isn't answering is never passed over for the next one (§17.4), so it is suggested anyway,
greyed with its reason, and the queue waits for it when the job runs. Suggestions are local only:
**Allow cloud models for this run** starts unticked every time and nothing in `vid2sub.toml` or
the environment can tick it (§7.2), sampling sends no audio to a cloud detector, and a cloud model
is only ever the person's own pick, which Start refuses until the box is ticked. The rest of a
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


def prepare(inputs: Sequence[str], ctx: RunContext, *, keep_video: bool = False) -> Review:
    """One row per input: each file probed, each link ready to run. `inputs` are what the Add
    screen took (`browse.expand`'s paths) or YouTube links. Blocks: ffprobe, and the model list
    of each local server."""
    cands = tuple(detecting.candidates(ctx.config, ctx.keys))
    targets = tuple(naming.target_track(t) for t in ctx.config.defaults.targets)
    formats = tuple(ctx.config.defaults.formats)
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
  (`35 passed`), then the guard checks, then `make check`. **Guard checks** (spec §7.2, §17.4),
  each reverted and restored, each with `uv run pytest tests/test_review.py -q`: in
  `run_options`, drop `allow_cloud=review.allow_cloud` (the base's cloud leaks through:
  `FAILED …test_allow_cloud_starts_unticked_every_time_and_nothing_can_preset_it` and
  `…test_suggestions_are_local_and_a_cloud_pick_waits_for_the_box`); in `_sampled`, choose the
  detector with `allow_cloud=True` (`FAILED
  …test_with_no_local_detector_the_language_is_the_persons_and_no_audio_leaves`); in `_route`,
  suggest over `cands` instead of `hoped` (the Mac's Qwen replaces the Spark that's down:
  `FAILED …test_a_model_whose_server_is_down_is_still_suggested_and_marked_never_passed_over`);
  in `_route`, suggest with `allow_cloud=True` (`FAILED
  …test_suggestions_are_local_and_a_cloud_pick_waits_for_the_box`). `make check`. Expected:
  `807 passed, 5 skipped, 4 deselected` twice, `All checks passed!` and `no leaks found`.
- [ ] **Step 5: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(review): 🤖 Review samples the first two files of each folder, suggests local models, and the rest inherit

vid2sub.review (spec §10, §19.2, S40): prepare(inputs, ctx) gives one row
per input, each file probed (a link is ready at once, decided when it
runs) and the model pickers with whether each model can run now and why
not. sample(review, ctx, on_row=…) decodes the first two waiting files
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

The new tests failed first with: ImportError: cannot import name
'review' from 'vid2sub'. Guard checks, each reverted and restored:
run_options taking the cloud from the base options, a detector chosen
with the cloud allowed, a route over the real candidates (passing over
the server that's down), and suggestions allowed the cloud each make
their tests fail.

Docs read: none beyond the code (detect.detect, choose_detector and
candidates; catalog.suggest; pipeline._candidates_that_work's rule of
waiting for the route's pick; media.decode, vad and probe).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md Task 3
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/review.py tests/test_review.py`, `git commit -F .git/COMMIT_MSG`, then
  `git log -1 --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 6: Write the failing tests.** Append to `tests/test_jobs.py`, after two blank
  lines:

```python
# Phase 3, Task 3: Review's Start queues each file with its own options (S40)


def test_a_job_may_bring_its_own_runner(runner):
    ran = []

    def own(source, event, cancelled):
        ran.append(source)
        return InputResult(input=source, status="done")

    q = jobs.Queue(runner)
    (job,) = q.submit(["a.mkv"], runner=own)
    until(lambda: state(q, job) == "done")
    q.close()
    assert ran == ["a.mkv"] and runner.started == []
```

  In `tests/test_review.py`, add `import time` below `import threading`; replace
  `from vid2sub import review` with `from vid2sub import jobs, review`, and
  `from vid2sub.pipeline import RunContext, RunOptions` with
  `from vid2sub.pipeline import InputResult, RunContext, RunOptions`; then append, after two
  blank lines:

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
        seen.append((source, ctx.options.source_lang, ctx.options.model,
                     ctx.options.allow_cloud, ctx.chunk_cache is base.chunk_cache,
                     ctx.engines is base.engines))
        return InputResult(input=source, status="done")

    monkeypatch.setattr(review, "run_one", run_one)
    base = make_ctx()
    rv = reviewed(file_row(1, language="ja", transcribe="spark-turbo", translate="spark-gemma"),
                  file_row(2, language="ko", transcribe="openai-whisper",
                           translate="spark-gemma"),
                  file_row(3, state="failed", error="this file has no audio track"),
                  allow_cloud=True)
    default = []
    queue = jobs.Queue(lambda source, event, cancelled: default.append(source))
    ids = review.start(rv, queue, base)
    until(lambda: all(j.state == "done" for j in queue.jobs()))
    queue.close()
    assert len(ids) == 2 and default == []
    assert seen == [("/films/Show/Show S01E01.mkv", "ja", "spark-turbo", True, True, True),
                    ("/films/Show/Show S01E02.mkv", "ko", "openai-whisper", True, True, True)]


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

- [ ] **Step 7: Run them; watch them fail.** `uv run pytest tests/test_review.py
  tests/test_jobs.py -q -k "start or engine_made or own_runner"`. Expected:
  `E       TypeError: Queue.submit() got an unexpected keyword argument 'runner'`,
  `E       AttributeError: <module 'vid2sub.review' …> has no attribute 'run_one'`,
  `E           AttributeError: module 'vid2sub.review' has no attribute 'start'`,
  `E       Failed: DID NOT RAISE EngineError` (the cached cloud engine), and
  `4 failed, 2 passed, 44 deselected`.
- [ ] **Step 8: Write the code.** In `src/vid2sub/jobs.py`, in the module docstring, replace

```python
`submit`, `cancel` or `close`); one that raises is logged and the queue carries on. The log names
jobs by id and errors by kind, never an input, a title or a path (spec §6.8).
```

  with

```python
`submit`, `cancel` or `close`); one that raises is logged and the queue carries on. A job may bring
its own runner (Review's Start: each file with its own options, Phase 3 plan Task 3); others use
the queue's. The log names jobs by id and errors by kind, never an input, a title or a path (spec
§6.8).
```

  Below `self._runner = runner` in `__init__`, add
  `self._runners: dict[str, Runner] = {}  # a job's own runner, while it waits or runs`.
  Replace `submit` with:

```python
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
```

  In `cancel`, below `self._waiting.remove(job_id)`, add `self._runners.pop(job_id, None)`. In
  `close`, replace

```python
            while self._waiting:
                self._set(self._waiting.popleft(), state="cancelled")
```

  with

```python
            while self._waiting:
                job_id = self._waiting.popleft()
                self._runners.pop(job_id, None)
                self._set(job_id, state="cancelled")
```

  In `_work`, replace

```python
                source = self._jobs[job_id].input
            self._changed()
            final = self._run(job_id, source)
            with self._lock:
                self._set(job_id, **final)
                self._running = None
```

  with

```python
                source = self._jobs[job_id].input
                runner = self._runners.get(job_id, self._runner)
            self._changed()
            final = self._run(job_id, source, runner)
            with self._lock:
                self._set(job_id, **final)
                self._runners.pop(job_id, None)
                self._running = None
```

  and in `_run`, replace `def _run(self, job_id: str, source: str) -> dict[str, Any]:` with
  `def _run(self, job_id: str, source: str, runner: Runner) -> dict[str, Any]:` and
  `result = self._runner(source, event, self._stop.is_set)` with
  `result = runner(source, event, self._stop.is_set)`.

  In `src/vid2sub/pipeline.py`, replace `from vid2sub.engines.clients import KeyRing, RunPolicy`
  with `from vid2sub.engines.clients import KeyRing, RunPolicy, check_allowed`, and in
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


def start(review: Review, queue: jobs.Queue, ctx: RunContext) -> list[str]:
    """Start (§10.6): every row that can run, queued in order, each with its own options on top
    of `ctx.options`; a failed row is left out. Nothing is queued while any row has a problem.
    Returns the job ids."""
    found = problems(review)
    if found:
        n = len(found)
        raise ReviewError(f"{n} file{'s' if n != 1 else ''} still need{'' if n != 1 else 's'} a "
                          "choice: see the rows marked")
    ids = []
    for row in review.rows:
        if row.state != "failed":
            ids += queue.submit([row.path], runner=runner_for(
                ctx, run_options(review, row.id, ctx.options)))
    return ids


```

- [ ] **Step 9: Run the checks; they pass.** `uv run pytest tests/test_review.py
  tests/test_jobs.py -q` first (`50 passed`; run it ten times: the queue tests use threads),
  then the guard checks, then `make check`. **Guard checks**, each reverted and restored, each
  with `uv run pytest tests/test_review.py -q`: in `RunContext.engine`, replace the two lines
  `if entry is not None:` / `check_allowed(…)` with `pass` (`FAILED
  …test_an_engine_made_for_a_run_that_allowed_the_cloud_is_refused_to_one_that_doesnt`); in
  `start`, replace `if found:` with `if False:` (`FAILED
  …test_start_queues_nothing_while_any_row_has_a_problem`: the first row is queued before the
  second is refused). `make check`. Expected: `811 passed, 5 skipped, 4 deselected` twice,
  `All checks passed!` and `no leaks found`.
- [ ] **Step 10: Commit.** Write the message to `.git/COMMIT_MSG`:

```text
feat(review): 🤖 Start queues each file with its own options, and a cloud engine is refused to a run that didn't allow it

review.start(review, queue, ctx) queues every row that can run, in order,
each with run_options on top of the server's options, through
review.runner_for(ctx, options): run_one on a copy of the server's
RunContext that shares its engines and finished chunks (spec §8.9).
Nothing is queued while any row has a problem; a failed row is left out.
jobs.Queue.submit takes `runner=` for a job's own runner (the queue's
own otherwise), kept while the job waits or runs.

Per-job options meant one context's engine cache now serves runs that
differ in Allow cloud, and make_client checks the cloud only when an
engine is made: a cloud engine made for a run that ticked the box would
serve a later one that didn't (spec §7.2). RunContext.engine now runs
clients.check_allowed on every call.

The new tests failed first with: TypeError: Queue.submit() got an
unexpected keyword argument 'runner', AttributeError: module
'vid2sub.review' has no attribute 'start', and Failed: DID NOT RAISE
EngineError (the cached cloud engine). Guard checks, each reverted and
restored: without the check in RunContext.engine, and with start
ignoring the problems, their tests fail.

Docs read: none beyond the code (jobs.Queue, pipeline.RunContext and
clients.check_allowed and transcription_client, where the cloud check
ran only at construction).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md Task 3
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/jobs.py src/vid2sub/pipeline.py src/vid2sub/review.py tests/test_jobs.py
  tests/test_review.py`, `git commit -F .git/COMMIT_MSG`, then
  `git log -1 --format='%(trailers)'` shows `Plan:`.

- [ ] **Step 11: Review, look forward, close.** The Tier 2 review from `$(cat .git/TASK_BASE)`
  (`AGENTS.md`, *Reviews*). Worth the reviewers' time: that no path from sampling reaches a
  cloud model (detection, suggestion, `run_options`, and the engine cache now checked per run);
  that a model whose server is down is suggested, never passed over (§17.4); that `on_row`
  never replaces a row the person could already change. The forward review over Tasks 4, 5, 6
  and 8: Task 4 calls everything listed under *What Task 4 calls*, renders rows through its own
  view (never `Row.path`), and draws **Allow cloud** from `Review.allow_cloud`, never a setting;
  Task 5's pause and resume keep each job's own runner (`Queue._runners`); Task 6's Jobs page
  shows jobs Review queued like any other; Task 8 may show `model_choices`. The docs this task
  made untrue: none expected (grep `docs/` and `README.md` for "Review" and "allow cloud").
  Then the close, its own commit, holding this plan with this task's boxes ticked and **Now**
  set to `Task 4: The Review screen, open.`, and the spec's S40 row with "Phase and task" set to
  `Phase 3, Tasks 3–4`; S40 stays `planned` (its Playwright half is Task 4's). The message, in `.git/CLOSE_MSG`:

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

**Interfaces:**
- Consumes: Task 3's `vid2sub.review`. `prepare` then `sample` run off the event loop; `on_row`
  runs on the sampling thread, so the server hops to the session's loop and merges with
  `with_row`; `cancelled` turns true when the person leaves Review. `choose`, `apply_to_all`,
  `set_allow_cloud` and `problems` are pure and run on the loop. Start calls
  `review.start(review, queue, job_ctx)`, `job_ctx` being the `RunContext` Phase 2 Task 19's
  runner wraps. The view never includes `Row.path`; the Allow cloud box is drawn only from
  `Review.allow_cloud`.

<!-- steps: written in the next pass -->

***

### Task 5: The queue pauses and resumes

**Tier:** 2 · **Scenarios:** S41, S42

**Files:**
- Modify: `src/vid2sub/jobs.py` (the queue's states, Pause and Resume; keeping the machine awake)
- Test: `tests/test_jobs.py`, `tests/test_awake.py`

**Interfaces:**
- Consumes: `pipeline.Paused` (`.error`, an `EngineError` with `.kind` and `.hint`, raised by
  `run_one` once a connection error or a Spark refusal outlasts `RunOptions.wait_on_connection_s`),
  `pipeline.Cancelled`, `pipeline.run_one` and `RunContext.chunk_cache` (shared by every
  `dataclasses.replace` copy, so a resumed job's finished chunks are kept, spec §8.9);
  `awake.keep_awake` (M1); Task 3's `Queue.submit(…, runner=)`.
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
from fakes import FakeEngine
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
```

- [ ] **Step 2: Run it; watch it fail.** `uv run pytest tests/test_jobs.py -q`. Expected:
  `E   AttributeError: 'Queue' object has no attribute 'status'` (four times),
  `E       AttributeError: 'Queue' object has no attribute 'pause'` (three times), two
  `E               AssertionError: timed out waiting` (a lost connection fails the job instead of
  pausing the queue), and `9 failed, 12 passed`.
- [ ] **Step 3: Write the code.** Replace `src/vid2sub/jobs.py` (Task 3's, which no other task
  changes) with:

```python
"""The job queue: one worker thread runs submitted inputs one at a time (spec §17.1, S36, S41).

Jobs live in the engine's memory, owned by the engine rather than a browser tab, so closing a tab
cancels nothing and reopening shows the progress; when the engine exits the list is gone, and
finished results are already on disk (Dan, 2026-10-14). One worker runs one job at a time,
because the Spark's whisper serves one request at a time anyway. Cancel takes a queued job out of
the queue, or asks the running one to stop at its next check, between chunks or translation
batches (`pipeline.Cancelled`; the Phase 2 plan's Decision 7). Listeners are called after every
change of state, stage or progress, and when the queue pauses or resumes, on the thread that made
it (the worker, or the caller of `submit`, `cancel`, `pause`, `resume` or `close`); one that
raises is logged and the queue carries on. A job may bring its own runner (Review's Start: each
file with its own options, Phase 3 plan Task 3); others use the queue's.

The queue is running or paused (§17.1). A connection error (refused, reset, the tunnel down, the
laptop slept) that outlasts the runner's own wait (`pipeline.Paused`) pauses the whole queue with
its reason and fix, instead of failing every remaining episode in turn (§17.3, council); so does
the person's Pause, which stops the running job at its next check as Cancel would. Either way the
job goes back to the head of the queue, keeping its runner, stage and progress, and Resume runs it
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
            if job.state == "running":
                self._why = "cancel"
                self._stop.set()
                return True
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

    def on_change(self, fn: Callable[[], None]) -> None:
        with self._lock:
            self._listeners.append(fn)

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
                    self._set(job_id, state="queued")
                    self._waiting.appendleft(job_id)
                    if paused is not None:
                        self._status = paused
                else:
                    self._set(job_id, **(final or {"state": "cancelled"}))
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
  (`21 passed`; run it ten times, `for i in 1 2 3 4 5 6 7 8 9 10; do uv run pytest
  tests/test_jobs.py -q | tail -1; done`, each `21 passed`: these tests use threads), then the
  guard checks, then `make check`. **Guard checks**, each reverted and restored, each with
  `uv run pytest tests/test_jobs.py -q`: in `_work`, replace `self._waiting.appendleft(job_id)`
  with `self._waiting.append(job_id)` (the paused job goes to the back: `FAILED
  …test_a_dropped_connection_pauses_the_whole_queue_and_its_job_waits_first` and `…pause_stops…`);
  in `_run`, replace `except Paused as err:` with `except ZeroDivisionError as err:` (a lost
  connection fails one job after another: `5 failed`); in `_run`'s `Paused` branch, replace
  `if why == "cancel":` with `if False:` (`FAILED
  …test_a_cancelled_job_that_lost_its_connection_is_not_queued_again`). `make check`.
  Expected: `820 passed, 5 skipped, 4 deselected` twice, `All checks passed!` and
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
QueueStatus; listeners hear pause and resume. Other errors fail only
their job, with their hint, and the queue runs on.

The new tests failed first with: AttributeError: 'Queue' object has no
attribute 'status' (and 'pause'). Guard checks, each reverted and
restored: a paused job queued at the back, Paused treated as any other
error, and a cancelled job that lost its connection queued again each
make their tests fail. The queue tests passed ten runs in a row.

Docs read: none beyond the code (pipeline._retrying's Paused after
wait_on_connection_s, and run_one's chunk cache key).

Plan: docs/superpowers/plans/2026-10-23-vid2sub-phase-3.md Task 5
Co-Authored-By: <the model's own line>
```

  `git add src/vid2sub/jobs.py tests/test_jobs.py`, `git commit -F .git/COMMIT_MSG`, then
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
batches (`pipeline.Cancelled`; the Phase 2 plan's Decision 7). Listeners are called after every
change of state, stage or progress, and when the queue pauses or resumes, on the thread that made
it (the worker, or the caller of `submit`, `cancel`, `pause`, `resume` or `close`); one that
raises is logged and the queue carries on. A job may bring its own runner (Review's Start: each
file with its own options, Phase 3 plan Task 3); others use the queue's.

The queue is running or paused (§17.1). A connection error (refused, reset, the tunnel down, the
laptop slept) that outlasts the runner's own wait (`pipeline.Paused`) pauses the whole queue with
its reason and fix, instead of failing every remaining episode in turn (§17.3, council); so does
the person's Pause, which stops the running job at its next check as Cancel would. Either way the
job goes back to the head of the queue, keeping its runner, stage and progress, and Resume runs it
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
            if job.state == "running":
                self._why = "cancel"
                self._stop.set()
                return True
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

    def on_change(self, fn: Callable[[], None]) -> None:
        with self._lock:
            self._listeners.append(fn)

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
                        self._set(job_id, state="queued")
                        self._waiting.appendleft(job_id)
                        if paused is not None:
                            self._status = paused
                    else:
                        self._set(job_id, **(final or {"state": "cancelled"}))
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
  tests/test_jobs.py -q` first (`27 passed`; ten runs, each `27 passed`), then the guard
  checks, then `make check`. **Guard checks**, each reverted and restored, each with
  `uv run pytest tests/test_awake.py -q`: in `_work`, replace `self._let_sleep()  # outside the
  lock` with `pass  # outside the lock` (the machine is never let sleep while idle: `3 failed`);
  delete the line `self._hold_awake()` (`4 failed`). The real-helper test sees `caffeinate`
  running while a job runs and gone once the queue is idle (macOS; `systemd-inhibit` on Linux
  where it exists). `make check`. Expected: `824 passed, 5 skipped, 4 deselected` twice,
  `All checks passed!` and `no leaks found`.
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
  Task 19's server runner keeps `RunOptions.wait_on_connection_s` at M1's 10 minutes, so the
  banner appears only after that wait (Task 6 decides whether the web app's job context waits
  less, and may show the `waiting` events the queue ignores); Task 12's exit test drops the
  tunnel mid-season. The docs this task made untrue: none expected (grep `docs/` for "Resume"
  and "paused"). Then the close, its own commit, holding this plan with this task's boxes ticked
  and **Now** set to `Task 6: The Jobs page grows up, open.`, and the spec's rows S41 (with
  "Phase and task" `Phase 3, Tasks 5–6`) and S42 (`Phase 3, Task 5`) set to `built`. The
  message, in `.git/CLOSE_MSG`:

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

**Interfaces:**
- Consumes: Task 5's `Queue.pause() -> bool`, `resume() -> bool` and `status() -> QueueStatus`
  (`state`, `reason`, `hint`, `kind`). The banner shows `reason` and `hint` when `kind !=
  "paused"`; a requeued job shows `queued` with the stage and progress it stopped at. To decide
  here: Phase 2 Task 19's context keeps M1's `wait_on_connection_s = 600`, so a dropped tunnel
  shows the banner only after ten minutes; the server's context may wait less. `JobView` ignores
  `waiting` events.

<!-- steps: written in the next pass -->

***

### Task 7: The preview copy

**Tier:** 2 · **Scenarios:** S63

<!-- steps: written in the next pass -->

***

### Task 8: The Models page

**Tier:** 2 · **Scenarios:** S44

**Interfaces:**
- Consumes: Task 3's `review.model_choices(config, candidates, task)` and Task 9's
  `faster-whisper` candidate with its install reason.

<!-- steps: written in the next pass -->

***

### Task 9: The `faster-whisper` engine

**Tier:** 2 · **Scenarios:** S45

<!-- steps: written in the next pass -->

***

### Task 10: CI on Windows and Linux for `faster-whisper`

**Tier:** 3 · **Scenarios:** S45

**Interfaces:**
- Consumes: Task 9's `[whisper]` extra: a Windows and a Linux job run
  `uv sync --group dev --extra whisper`, so the engine's field check runs instead of skipping.
  Not `[nvidia]` (its wheels are 553 MB and 743 MB). Task 1's Windows-only tests (junction,
  hidden attribute, 8.3 short name) already run in the existing `windows-2022` job; Task 9 added
  its parser test to the floor job.

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
| Task 1 (planning review) | Minor | `src/vid2sub/web/browse.py` | A folder swapped for a link between the browser's check and the job opening the file (a shared NAS, a removable drive) is followed; the checks run on what the disk returned at listing time | open |
| Task 1 (planning review) | Minor | `src/vid2sub/web/browse.py` | `Library` and `AppData` are hidden in home on every OS, which hides more than it needs to on Linux | open |
| Task 1 (planning review) | Minor | `tests/test_browse.py` | The junction, hidden-attribute and 8.3 short-name tests run only on Windows CI, so a Mac or Linux run can't catch a break there | open |
