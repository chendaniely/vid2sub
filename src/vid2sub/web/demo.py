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
Python audit hook (`isolate`) refuses, once the demo is set up and while it runs, the file
writes Python audits outside the demo's folder, reads of files in the person's home folder
outside the demo, Python and vid2sub themselves, and the connections, sends and name lookups
Python audits that go beyond this machine. The demo's backend opens only episodes in its copy,
and its runtime reads no vid2sub.toml and no key from the environment.

What it can't see (Task 13's Spec review; the first four were accepted in the plan, the rest
were tried):
- child processes: ffmpeg, ffprobe and the browser opener, which the demo starts only on its
  own files;
- native code, and events Python doesn't audit: `os.mknod` and `os.mkfifo` (both made a file
  outside), `os.stat`, and listing the home folder (names are read, not files);
- changes through an already open descriptor: `os.fchmod` and `os.utime` on a descriptor opened
  read-only;
- a relative path, which the open event gives without the descriptor it is relative to
  (`shutil.rmtree`'s walk): only absolute reads are checked, and a bare-name create through a
  `dir_fd` passes when the working directory is inside the folder;
- another spelling of a home path on a case-insensitive disk;
- everything before `isolate`: `prepare` and the imports.
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
from vid2sub.config import Config, ModelEntry
from vid2sub.engines.base import ChunkResult, EngineError, ModelStamp
from vid2sub.engines.clients import KeyRing, RunPolicy
from vid2sub.media.identity import full_sha256, identify
from vid2sub.media.probe import probe
from vid2sub.media.tools import Tools, input_args, run_tool
from vid2sub.parse import ParsedChunk
from vid2sub.security import safe_write
from vid2sub.store import header_for, now, sidecar_path
from vid2sub.subs.model import Segment, Word
from vid2sub.subs.sidecar import IdentityRecord, Sidecar, parse_sidecar, serialize
from vid2sub.translate.run import AskFn
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
# into cues, line breaks as spaces) with its Japanese. A sentence across two cues is one item,
# short enough to stay one: two Japanese lines hold 26 full-width characters, and over that
# Phase 2's Task 26 would split it back over the two cues (spec §13.4).
JAPANESE: tuple[tuple[tuple[str, ...], str], ...] = (
    (("I am delighted to be here, and I am particularly delighted to be here on this",
      "occasion."), "ここに来られて光栄です。"),
    (("We meet at a college noted for knowledge,",),
     "私たちが集うのは、知識で知られる大学、"),
    (("in a city noted for progress, in a state noted for strength,",),
     "進歩で知られる都市、力強さで知られる州です。"),
)
NO_TRANSLATION = "（訳はありません）"
# The model the canned sidecar's Japanese was made with (scripts/demo_sidecar.py), so the demo's
# own track isn't stale for want of the model (spec §13.4); it is in no vid2sub.toml.
CANNED_JA = "canned-ja"
CANNED_ENTRY = ModelEntry(model=CANNED_JA, task="translate", local=True)


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
                  *input_args(CLIP), "-map", "0:v", "-map", "1:a", "-shortest",
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
    safe_write(path, serialize(Sidecar(header, tuple(records))).encode("utf-8"), overwrite=True)
    return copy


class DemoBackend(LocalBackend):
    """LocalBackend, opening only episodes in the demo's copy, and retranslating with the canned
    translation (`CANNED_JA`, the model the demo's sidecar was made with), which sends nothing
    anywhere: the demo has no vid2sub.toml, so no endpoint or model of its own (Task 17)."""

    def __init__(self, copy: Path, tools: Tools, cache: Cache):
        super().__init__(Config(), tools, KeyRing(environ={}), cache)
        self.copy = copy.resolve()

    def _translator(self, lang: str, model: str | None, allow_cloud: bool
                    ) -> tuple[str, ModelEntry]:
        if model not in (None, CANNED_JA):
            raise EngineError("unavailable", "the demo translates only with its canned model")
        return CANNED_JA, CANNED_ENTRY

    def _ask(self, name: str, entry: ModelEntry, policy: RunPolicy) -> AskFn:
        return canned_ask

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
    # os.lchflags raises os.chflags; the xattr calls are Linux's; sqlite3.connect's one argument
    # is the database path (":memory:" is refused too, which nothing in the demo uses).
    "os.chflags": ((0, None),), "os.setxattr": ((0, None),), "os.removexattr": ((0, None),),
    "sqlite3.connect": ((0, None),),
}
_SENDS = ("socket.connect", "socket.sendto", "socket.sendmsg")  # (socket, address)
_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
_LOOPBACK = {"127.0.0.1", "::1", "localhost"}
_state: dict = {"folder": None, "home": None, "reads": (), "given": (), "tempdir": None}


def isolate(folder: Path, *, home: Path | None = None) -> None:
    """Refuse, from now on in this process, the audited writes outside `folder`, absolute reads
    in `home` (the person's home folder) outside `folder` and Python's and vid2sub's own files,
    and the audited connections, sends and name lookups beyond this machine (the module
    docstring lists what the hook can't see). Temporary files go in `folder/tmp` (scratch,
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
    # Only Python's own roots may be reached by a path as written (a venv's symlink to uv's
    # cache), never a link inside the demo's folder.
    _state["given"] = tuple(os.path.realpath(p) for p in (sys.prefix, sys.base_prefix))
    sys.dont_write_bytecode = True
    if not _state.get("installed"):
        sys.addaudithook(_hook)
        _state["installed"] = True
    atexit.register(release)  # atexit runs last-in first: before prepare's removal of `folder`


def release() -> None:
    if _state["folder"] is not None:
        tempfile.tempdir = _state["tempdir"]
    _state["folder"] = None


def _inside(path: str, roots: Sequence[str], *, given: Sequence[str] = ()) -> bool:
    """Whether `path`, symlinks resolved, is in one of `roots`, or the path as written is in one
    of `given` (a read through a venv's symlink to uv's cache)."""
    def under(p: str, rs: Sequence[str]) -> bool:
        return any(p == r or p.startswith(r.rstrip(os.sep) + os.sep) for r in rs)

    return under(os.path.realpath(path), roots) or (bool(given) and under(os.path.abspath(path),
                                                                          given))


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
    """Refuse a write outside the folder."""
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
            # The null device, by the raw argument and for opens only: subprocess opens it
            # read-write for DEVNULL (the browser opener's stdio), and a write there goes nowhere.
            if args[0] == os.devnull:
                return
            _refuse_write(_target(args[0], None))
            return
        # A read by a bare name is relative to a dir_fd the event doesn't carry (shutil.rmtree's
        # walk), so only absolute paths are checked; vid2sub itself opens only those.
        raw = args[0]
        if not isinstance(raw, (str, bytes, os.PathLike)) or not os.path.isabs(os.fsdecode(raw)):
            return
        path = os.fsdecode(raw)
        outside_python = not _inside(path, _state["reads"], given=_state["given"])
        if _inside(path, [_state["home"]]) and outside_python:
            raise DemoIsolationError("the demo reads nothing of yours")
    elif event in _WRITES:
        for at, fd_at in _WRITES[event]:
            if len(args) > at:
                dir_fd = args[fd_at] if fd_at is not None and len(args) > fd_at else None
                _refuse_write(_target(args[at], dir_fd))
    elif event in _SENDS and len(args) > 1:
        address = args[1]  # None: sendmsg on a connected socket, which has its peer already
        if address is not None and not (isinstance(address, tuple) and address
                                        and address[0] in _LOOPBACK):
            raise DemoIsolationError("the demo connects to nothing beyond this machine")
    elif event in ("socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyaddr",
                   "socket.getnameinfo") and args:
        host = args[0][0] if event == "socket.getnameinfo" and isinstance(args[0], tuple) \
            else args[0]
        host = host.decode() if isinstance(host, bytes) else host
        if host is not None and host not in _LOOPBACK:
            raise DemoIsolationError("the demo looks up no other machine")
