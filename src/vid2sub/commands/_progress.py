"""The progress a run shows: in a terminal a bar per input, elsewhere its plain lines (§18.2, S66).

Why: an episode takes minutes and a season hours, and M1 printed a line per chunk; Dan asked for
a bar with stats instead (Q&A item 34; the Phase 2 plan's Decision 38). Each input gets one bar,
redrawn in place on one line with a carriage return and the erase-line code (`ESC [2K`, xterm's
and ECMA-48's EL): its name, the stage, chunk or batch n/N with a simple bar, the stage's elapsed
time, its speed in × real time (audio seconds done ÷ wall seconds: transcription only, whose chunk
events say where on the audio each chunk ends) and its time left (the average time per chunk or
batch so far × those left). A finished stage leaves its own line above the bar. The bar is erased
before any other output, so nothing is drawn over it, and cut to the terminal's width, wide
characters counted twice, since a wrapped line can't be redrawn in place; a control character in
a name is shown as `?`. It is redrawn on each event, with no timer thread. Only a terminal gets the
bar (`live`), because titles reach nothing else (§6.8): output that isn't a terminal gets the same
lines with no bar, no codes and no name, before M1's line per input, and `--json` keeps its events
(Dan's answer to Q&A item 34, "plain lines when piped"). The standard library only, as Decision 38
asks; the clock and the width are injected, so tests need neither sleeps nor a terminal.
"""

from __future__ import annotations

import shutil
import unicodedata
from collections.abc import Callable
from time import monotonic
from typing import Any, TextIO

ERASE = "\r\x1b[2K"  # back to the line's start, then erase the whole line
CELLS = 10  # the bar's width, in characters
# Each stage's words while it runs and once it has finished.
STAGES = {
    "download": ("downloading", "downloaded"),
    "probe": ("probing", "probed"),
    "decode": ("decoding", "decoded"),
    "speech": ("finding speech", "found speech"),
    "detect": ("detecting the language", "detected the language"),
    "transcribe": ("transcribing", "transcribed"),
    "translate": ("translating", "translated"),
    "hash": ("hashing the video", "hashed the video"),
}
UNITS = {"transcribe": ("chunk", "chunks"), "translate": ("batch", "batches")}


def clock_text(seconds: float) -> str:
    """`m:ss`, or `h:mm:ss` from an hour."""
    s = max(0, int(seconds))
    if s >= 3600:
        return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}"
    return f"{s // 60}:{s % 60:02d}"


def _cells(ch: str) -> int:
    """The columns a character takes: two if East Asian wide or fullwidth, none for a mark."""
    if unicodedata.category(ch) in ("Mn", "Me", "Cf"):
        return 0
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


def _width(text: str) -> int:
    return sum(_cells(ch) for ch in text)


def _cut(text: str, cells: int) -> str:
    """The longest start of `text` that fits in `cells` columns."""
    out: list[str] = []
    used = 0
    for ch in text:
        used += _cells(ch)
        if used > cells:
            break
        out.append(ch)
    return "".join(out)


def _columns() -> int:
    return shutil.get_terminal_size().columns


class Bar:
    """One input at a time on `stream`, fed the pipeline's progress events; with `live` False,
    only the lines above the bar are written."""

    def __init__(self, stream: TextIO, *, clock: Callable[[], float] | None = None,
                 columns: Callable[[], int] | None = None, live: bool = True):
        self._stream = stream
        self._live = live
        self._clock = clock or monotonic
        self._columns = columns or _columns
        self._name = ""
        self._stage: str | None = None
        self._since = 0.0
        self._done = self._total = 0
        self._heard_ms: int | None = 0  # the audio the finished chunks cover
        self._until_ms: int | None = 0  # where the chunk in progress ends
        self._drawn = False

    def start(self, name: str) -> None:
        self.clear()
        self._name = "".join("?" if unicodedata.category(ch) == "Cc" else ch for ch in name)
        self._stage = None

    def event(self, kind: str, fields: dict[str, Any]) -> None:
        now = self._clock()
        if kind == "stage":
            self._begin(fields["stage"], now)
        elif kind in ("chunk", "batch"):
            stage = "transcribe" if kind == "chunk" else "translate"
            if self._stage != stage:
                self._begin(stage, now)
            # A chunk's event comes as it starts, a batch's once it has finished.
            self._done = fields["index"] - (1 if kind == "chunk" else 0)
            self._total = fields["of"]
            if kind == "chunk":
                self._heard_ms, self._until_ms = self._until_ms, fields.get("until_ms")
        elif kind == "waiting":
            self._line(f"waiting {fields['seconds']} s ({fields['kind']})…")
        else:
            return
        self._draw(now)

    def finish(self, ok: bool) -> None:
        """The input is over: its last stage leaves a line if it finished, and the bar goes."""
        if ok and self._stage is not None:
            self._line(self._finished(self._clock()))
        self.clear()
        self._name, self._stage = "", None

    def clear(self) -> None:
        if self._drawn:
            self._write(ERASE)
            self._drawn = False

    def _begin(self, stage: str, now: float) -> None:
        if self._stage is not None:
            self._line(self._finished(now))
        self._stage, self._since = stage, now
        self._done = self._total = 0
        self._heard_ms = self._until_ms = 0

    def _finished(self, now: float) -> str:
        took = now - self._since
        words = STAGES.get(self._stage, (self._stage, f"{self._stage} done"))[1]
        if self._stage in UNITS and self._total:
            one, many = UNITS[self._stage]
            words += f" {self._total} {one if self._total == 1 else many}"
        line = f"{words} in {clock_text(took)}"
        if self._until_ms and took > 0:
            line += f", {self._until_ms / 1000 / took:.1f}× real time"
        return line

    def _draw(self, now: float) -> None:
        if self._stage is None or not self._live:
            return
        elapsed = now - self._since
        doing = STAGES.get(self._stage, (self._stage, ""))[0]
        if self._total:
            filled = CELLS * self._done // self._total
            doing += (f" {UNITS[self._stage][0]} {min(self._done + 1, self._total)}/{self._total}"
                      f" [{'#' * filled}{'-' * (CELLS - filled)}]")
        parts = [doing, clock_text(elapsed)]
        if self._heard_ms and elapsed > 0:
            parts.append(f"{self._heard_ms / 1000 / elapsed:.1f}×")
        if self._done and self._total:
            parts.append(f"{clock_text(elapsed / self._done * (self._total - self._done))} left")
        line = " · ".join(parts)
        width = self._columns() - 1  # never the last column, where some terminals wrap
        if self._name:
            room = width - _width(line) - 3
            name = self._name
            if _width(name) > room:
                name = _cut(name, room - 1).rstrip() + "…"
            line = f"{name} · {line}"
        self._write(ERASE + _cut(line, width))
        self._drawn = True

    def _line(self, text: str) -> None:
        self.clear()
        self._write(f"  {text}\n")

    def _write(self, text: str) -> None:
        self._stream.write(text)
        self._stream.flush()
