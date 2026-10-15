"""What the commands share: settings, inputs, output and the run context (spec §18).

Output is for people in a terminal, or JSON Lines for scripts (`--json`). Titles and paths reach
only an interactive terminal: piped plain output names inputs by number, and JSON carries
stages, counts and error kinds, never names (spec §6.8, §18.2). Folders expand to their videos in
episode order (`S01E02` before `S01E10`), others by natural name order after them.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, TextIO

from vid2sub import exitcodes
from vid2sub.config import Config, ConfigError, config_path, load_config
from vid2sub.engines.clients import KeyRing
from vid2sub.media.tools import Tools
from vid2sub.media.youtube import is_url
from vid2sub.pipeline import MEDIA_SUFFIXES, RunContext, RunOptions
from vid2sub.security import InputRefused, resolve_input

_EPISODE = re.compile(r"[Ss](\d{1,3})[ ._-]*[Ee](\d{1,4})")


class CommandError(Exception):
    def __init__(self, code: int, message: str, hint: str = ""):
        super().__init__(message)
        self.code = code
        self.hint = hint


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", metavar="PATH", help="the vid2sub.toml to use")
    parser.add_argument("--json", action="store_true",
                        help="JSON Lines events for scripts (never titles or paths)")


def load(args: argparse.Namespace) -> Config:
    try:
        return load_config(config_path(args.config))
    except ConfigError as err:
        raise CommandError(exitcodes.CONFIG, str(err),
                           "fix vid2sub.toml (`vid2sub config init` prints a starter)") from None


def check_model(config: Config, name: str | None, task: str, flag: str) -> None:
    """A model named on the command line must be in vid2sub.toml and do this task (exit 64).

    Checked before any input is touched, so a typo isn't a failure per episode (final review).
    """
    if name is None:
        return
    entry = config.models.get(name)
    if entry is None:
        raise CommandError(exitcodes.USAGE, f"{flag} {name}: there's no such model in "
                           "vid2sub.toml", "`vid2sub models` lists them")
    if entry.task != task:
        raise CommandError(exitcodes.USAGE, f"{flag} {name}: that's a {entry.task} model, and "
                           f"{flag} takes a {task} model", "`vid2sub models` lists them")


def episode_key(path: Path) -> tuple:
    natural = [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", path.name)]
    m = _EPISODE.search(path.name)
    return (0, int(m.group(1)), int(m.group(2)), natural) if m else (1, 0, 0, natural)


def _natural(text: str) -> list:
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", text)]


def _read_list(from_file: str) -> list[str]:
    try:
        text = sys.stdin.read() if from_file == "-" else Path(from_file).read_text(
            encoding="utf-8-sig")
    except (OSError, UnicodeError) as err:  # never err.filename (spec §6.8)
        strerror = getattr(err, "strerror", None)
        raise CommandError(
            exitcodes.USAGE,
            "couldn't read the list of inputs" + (f" ({strerror})" if strerror else ""),
            "give a readable UTF-8 text file, one input per line") from None
    return [line.strip() for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")]


def _is_hidden(path: Path, root: Path) -> bool:
    return any(part.startswith(".") or part == "@eaDir" for part in path.relative_to(root).parts)


def expand(inputs: Sequence[str], *, recursive: bool = False,
           from_file: str | None = None) -> list[str]:
    items = list(inputs)
    if from_file:
        items += _read_list(from_file)
    out: list[str] = []
    for item in items:
        if is_url(item):
            out.append(item)
            continue
        try:
            path = resolve_input(item)
        except InputRefused as err:  # its message names no path
            raise CommandError(exitcodes.USAGE, str(err)) from None
        if path.is_dir():
            found = path.rglob("*") if recursive else path.iterdir()
            videos = [f for f in found if f.is_file() and not _is_hidden(f, path)
                      and f.suffix.lower() in MEDIA_SUFFIXES]
            out += [str(f) for f in sorted(
                videos, key=lambda f: (_natural(str(f.parent)), episode_key(f)))]
        else:
            out.append(str(path))
    return out


def duration(value: str) -> float:
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([smh]?)", value.strip())
    if not m:
        raise argparse.ArgumentTypeError("use seconds, or a number with s, m or h (like 10m)")
    return float(m.group(1)) * {"": 1, "s": 1, "m": 60, "h": 3600}[m.group(2)]


def audio_track(value: str) -> int | str:
    return int(value) if value.isdigit() else value


class Output:
    def __init__(self, json_mode: bool, stream: TextIO | None = None, err: TextIO | None = None):
        self.json = json_mode
        self.stream = stream or sys.stdout
        self.err = err or sys.stderr
        self.tty = not json_mode and self.stream.isatty()

    def event(self, kind: str, /, **fields: Any) -> None:
        if self.json:
            self.stream.write(json.dumps({"event": kind, **fields}, ensure_ascii=False) + "\n")
            self.stream.flush()

    def say(self, text: str) -> None:
        if not self.json:
            print(text, file=self.stream, flush=True)

    def warn(self, text: str) -> None:
        print(text, file=self.err, flush=True)

    def progress(self, kind: str, fields: dict[str, Any]) -> None:
        if self.json:
            self.event(kind, **fields)
            return
        if not self.tty:
            return
        lines = {
            "stage": lambda f: f"  {f['stage']}…",
            "chunk": lambda f: f"  transcribing {f['index']}/{f['of']}",
            "batch": lambda f: f"  translating {f['index']}/{f['of']}",
            "waiting": lambda f: f"  waiting {f['seconds']} s ({f['kind']})…",
        }
        if kind in lines:
            self.say(lines[kind](fields))

    def name(self, title: str, n: int) -> str:
        return title if self.tty and title else f"input {n}"


def fail(output: Output, err: CommandError) -> int:
    output.warn(f"vid2sub: {err}" + (f"\n  → {err.hint}" if err.hint else ""))
    output.event("error", code=err.code)
    return err.code


def new_context(config: Config, options: RunOptions, output: Output) -> RunContext:
    return RunContext(config=config, tools=Tools.find(), keys=KeyRing(), options=options,
                      events=output.progress)
