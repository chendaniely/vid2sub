import io
import json
import re
import sys

import pytest
from fakes import FakeEngine, fake_make_ask
from helpers import SPEECH, make_clip
from test_cli_run import CONFIG

from vid2sub import pipeline
from vid2sub.catalog import Candidate
from vid2sub.cli import main
from vid2sub.commands import _common, _progress
from vid2sub.commands._common import Output

ERASE = "\r\x1b[2K"
VIDEO = "/videos/Show/Show - S01E01.mkv"


class Terminal(io.StringIO):
    """Output that goes to an interactive terminal."""

    def isatty(self) -> bool:
        return True


class Clock:
    """A clock the test moves by hand, so nothing sleeps."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def screen(text: str) -> list[str]:
    """The lines a terminal shows after `text`: CR goes back to the line's start, ESC [2K blanks
    the line, and a character overwrites the one under the cursor."""
    lines: list[str] = []
    line: list[str] = []
    col = 0
    for part in re.split(r"(\r|\n|\x1b\[2K)", text):
        if part == "\r":
            col = 0
        elif part == "\n":
            lines.append("".join(line).rstrip())
            line, col = [], 0
        elif part == "\x1b[2K":
            line = [" "] * col
        else:
            for ch in part:
                line[col:col + 1] = [ch]
                col += 1
    if "".join(line).strip():
        lines.append("".join(line).rstrip())
    return lines


def terminal(columns: int = 100) -> tuple[Output, Terminal, Clock]:
    """An Output whose stdout and stderr are one terminal, `columns` wide."""
    tty, clock = Terminal(), Clock()
    return Output(False, tty, tty, clock=clock, columns=lambda: columns), tty, clock


def at(out: Output, clock: Clock, seconds: float, event: str, /, **fields) -> None:
    """The pipeline's `event` with its `fields`, `seconds` into the run."""
    clock.now = seconds
    out.progress(event, fields)


def bar(tty: Terminal) -> str:
    return screen(tty.getvalue())[-1]


def test_the_bar_shows_the_name_the_stage_and_the_chunk_with_elapsed_speed_and_time_left():
    out, tty, clock = terminal()
    out.begin(VIDEO, 1)
    at(out, clock, 0, "stage", stage="decode")
    assert bar(tty) == "Show - S01E01.mkv · decoding · 0:00"
    at(out, clock, 50, "chunk", index=1, of=11, until_ms=77_000)
    assert bar(tty) == "Show - S01E01.mkv · transcribing chunk 1/11 [----------] · 0:00"
    for i in range(2, 6):
        at(out, clock, 50 + 32.5 * (i - 1), "chunk", index=i, of=11, until_ms=77_000 * i)
    # 4 chunks (308 s of audio) in 130 s: 2.4× real time, and 7 more at 32.5 s each.
    assert bar(tty) == ("Show - S01E01.mkv · transcribing chunk 5/11 [###-------] · 2:10 · 2.4× · "
                        "3:47 left")


def test_translation_shows_the_batch_and_time_left_but_no_speed():
    out, tty, clock = terminal()
    out.begin(VIDEO, 1)
    at(out, clock, 0, "stage", stage="translate")
    assert bar(tty) == "Show - S01E01.mkv · translating · 0:00"
    at(out, clock, 20, "batch", index=1, of=5)
    assert bar(tty) == "Show - S01E01.mkv · translating batch 2/5 [##--------] · 0:20 · 1:20 left"
    at(out, clock, 100, "batch", index=5, of=5)
    assert bar(tty) == "Show - S01E01.mkv · translating batch 5/5 [##########] · 1:40 · 0:00 left"


def test_the_bar_is_erased_and_redrawn_in_place_on_one_line():
    out, tty, clock = terminal()
    out.begin(VIDEO, 1)
    at(out, clock, 0, "chunk", index=1, of=2, until_ms=60_000)
    at(out, clock, 3, "chunk", index=2, of=2, until_ms=90_000)
    assert tty.getvalue() == (
        ERASE + "Show - S01E01.mkv · transcribing chunk 1/2 [----------] · 0:00"
        + ERASE + "Show - S01E01.mkv · transcribing chunk 2/2 [#####-----] · 0:03 · 20.0× · "
        "0:03 left")


def test_a_finished_stage_leaves_its_own_line_above_the_bar():
    out, tty, clock = terminal()
    out.begin(VIDEO, 1)
    at(out, clock, 0, "stage", stage="decode")
    at(out, clock, 42, "stage", stage="speech")
    assert screen(tty.getvalue()) == ["  decoded in 0:42",
                                      "Show - S01E01.mkv · finding speech · 0:00"]
    for i in range(1, 12):
        at(out, clock, 50 + 30 * (i - 1), "chunk", index=i, of=11,
           until_ms=851_000 if i == 11 else 77_000 * i)
    clock.now = 420
    out.end(True)
    # 851 s of audio transcribed in 370 s.
    assert screen(tty.getvalue()) == ["  decoded in 0:42", "  found speech in 0:08",
                                      "  transcribed 11 chunks in 6:10, 2.3× real time"]


def test_the_bar_is_cleared_before_a_warning_or_the_summary_so_nothing_is_drawn_over():
    out, tty, clock = terminal()
    out.begin(VIDEO, 1)
    at(out, clock, 0, "chunk", index=1, of=3, until_ms=60_000)
    out.warn("vid2sub: paused: the model server isn't reachable")
    out.say("1 failed")
    assert tty.getvalue() == (
        ERASE + "Show - S01E01.mkv · transcribing chunk 1/3 [----------] · 0:00"
        + ERASE + "vid2sub: paused: the model server isn't reachable\n1 failed\n")


def test_a_stage_that_failed_leaves_no_line_and_its_bar_goes():
    out, tty, clock = terminal()
    out.begin(VIDEO, 1)
    at(out, clock, 0, "stage", stage="probe")
    at(out, clock, 1, "stage", stage="decode")
    clock.now = 3
    out.end(False)
    assert screen(tty.getvalue()) == ["  probed in 0:01"]
    assert tty.getvalue().endswith(ERASE)


def test_a_wait_for_the_server_is_a_line_above_the_bar():
    out, tty, clock = terminal()
    out.begin(VIDEO, 1)
    at(out, clock, 0, "stage", stage="translate")
    at(out, clock, 1, "waiting", kind="connection", seconds=5)
    assert screen(tty.getvalue()) == ["  waiting 5 s (connection)…",
                                      "Show - S01E01.mkv · translating · 0:01"]


@pytest.mark.parametrize(("name", "shown"), [
    ("Detective Conan - S01E05 - The Case.mkv", "Detective Conan - S0…"),
    ("名探偵コナン 第1話 江戸川コナン誕生.mkv", "名探偵コナン 第1話…"),  # two columns each
], ids=["latin", "wide"])
def test_a_long_name_is_cut_so_the_bar_fits_on_one_line(name, shown):
    out, tty, clock = terminal(columns=40)
    out.begin(f"/videos/{name}", 1)
    at(out, clock, 0, "stage", stage="decode")
    assert tty.getvalue() == ERASE + f"{shown} · decoding · 0:00"


def test_a_control_character_in_a_name_never_reaches_the_terminal():
    out, tty, clock = terminal()
    out.begin("/videos/Show\x1b[2J\r\n - S01E01.mkv", 1)
    at(out, clock, 0, "stage", stage="decode")
    assert tty.getvalue() == ERASE + "Show?[2J?? - S01E01.mkv · decoding · 0:00"


def test_output_that_isnt_a_terminal_gets_each_finished_stages_line_but_no_bar_or_name():
    pipe, clock = io.StringIO(), Clock()
    out = Output(False, pipe, pipe, clock=clock, columns=lambda: 100)
    out.begin(VIDEO, 1)
    at(out, clock, 0, "stage", stage="decode")
    at(out, clock, 5, "chunk", index=1, of=2, until_ms=60_000)
    at(out, clock, 8, "chunk", index=2, of=2, until_ms=90_000)
    at(out, clock, 9, "waiting", kind="connection", seconds=5)
    clock.now = 12
    out.end(True)
    out.say("✓ input 1 (1/1): done, wrote 1 file")
    # 90 s of audio in 7 s.
    assert pipe.getvalue() == ("  decoded in 0:05\n  waiting 5 s (connection)…\n"
                               "  transcribed 2 chunks in 0:07, 12.9× real time\n"
                               "✓ input 1 (1/1): done, wrote 1 file\n")


@pytest.fixture
def clip(tmp_path, monkeypatch):
    """A 14 s episode, the fake engines, a 120-column terminal and a clock that stands still."""
    cfg = tmp_path / "vid2sub.toml"
    cfg.write_text(CONFIG)
    real = _common.new_context

    def with_fakes(config, options, output):
        ctx = real(config, options, output)
        ctx.engines["fake"] = FakeEngine()
        ctx.candidates = [Candidate("fake", "whisper-large-v3-turbo", "endpoint", True),
                          Candidate("gemma", "gemma-4-26b-a4b", "endpoint", True)]
        return ctx

    monkeypatch.setattr(_common, "new_context", with_fakes)
    monkeypatch.setattr(pipeline, "make_ask", fake_make_ask)
    monkeypatch.setattr(_progress, "monotonic", lambda: 0.0)
    monkeypatch.setenv("COLUMNS", "120")
    return make_clip(tmp_path, "Show - S01E01.mkv", seconds=14, speech=SPEECH), cfg


def run_in(stdout, monkeypatch, *args: str) -> int:
    monkeypatch.setattr(sys, "stdout", stdout)
    return main(list(args))


@pytest.mark.media
def test_a_run_in_a_terminal_shows_a_bar_with_the_title_and_a_line_per_finished_stage(
        clip, monkeypatch):
    video, cfg = clip
    tty = Terminal()
    assert run_in(tty, monkeypatch, "run", str(video), "--from", "ja", "--to", "none",
                  "--config", str(cfg)) == 0
    assert ERASE + "Show - S01E01.mkv · transcribing chunk 1/1 [----------] · 0:00" \
        in tty.getvalue()
    assert screen(tty.getvalue()) == [
        "  probed in 0:00", "  decoded in 0:00", "  found speech in 0:00",
        "  transcribed 1 chunk in 0:00", "  hashed the video in 0:00",
        "✓ Show - S01E01.mkv (1/1): done, wrote 1 file", "    Show - S01E01.ja.srt", "1 done"]


@pytest.mark.media
def test_translate_in_a_terminal_shows_a_bar_for_its_batches(clip, monkeypatch):
    video, cfg = clip
    assert main(["run", str(video), "--from", "ja", "--to", "none", "--config", str(cfg)]) == 0
    tty = Terminal()
    assert run_in(tty, monkeypatch, "translate", str(video), "--to", "en",
                  "--config", str(cfg)) == 0
    assert ERASE + "Show - S01E01.mkv · translating · 0:00" in tty.getvalue()
    assert screen(tty.getvalue()) == [
        "  translated 1 batch in 0:00", "✓ Show - S01E01.mkv (1/1): done, wrote 1 file",
        "    Show - S01E01.en.srt", "1 done"]


@pytest.mark.media
def test_a_run_piped_elsewhere_prints_a_plain_line_per_finished_stage_and_no_title(clip, capsys):
    video, cfg = clip
    assert main(["run", str(video), "--from", "ja", "--to", "none", "--config", str(cfg)]) == 0
    assert capsys.readouterr().out == (
        "  probed in 0:00\n  decoded in 0:00\n  found speech in 0:00\n"
        "  transcribed 1 chunk in 0:00\n  hashed the video in 0:00\n"
        "✓ input 1 (1/1): done, wrote 1 file\n1 done\n")


@pytest.mark.media
def test_json_in_a_terminal_is_unchanged_and_its_chunk_events_carry_only_numbers(clip,
                                                                                 monkeypatch):
    video, cfg = clip
    tty = Terminal()
    assert run_in(tty, monkeypatch, "run", str(video), "--from", "ja", "--to", "none",
                  "--config", str(cfg), "--json") == 0
    out = tty.getvalue()
    assert "\r" not in out and "\x1b" not in out and "Show - S01E01" not in out
    events = [json.loads(line) for line in out.splitlines()]
    assert [e["event"] for e in events] == [
        "input", "stage", "stage", "stage", "chunk", "stage", "result", "summary"]
    [chunk] = [e for e in events if e["event"] == "chunk"]
    assert {k: type(v) for k, v in chunk.items()} == {
        "event": str, "index": int, "of": int, "until_ms": int}
    assert abs(chunk["until_ms"] - 14_000) < 500  # one chunk: the whole 14 s of audio
