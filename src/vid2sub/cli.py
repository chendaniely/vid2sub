"""vid2sub's command line (spec §18).

vid2sub is a CLI application in its own right: everything that makes, translates or writes
subtitles is a command here, and the web app (M2) calls the same core. `vid2sub` with no
arguments prints help. Each command is a module in `vid2sub.commands` whose `add_parser`
registers it and sets `handler`. Usage errors exit 64, not argparse's 2 (sysexits, §18.2).
"""

from __future__ import annotations

import argparse
import importlib
import sys
from collections.abc import Sequence

from vid2sub import __version__, exitcodes

COMMAND_MODULES: list[str] = []


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # type: ignore[override]
        self.print_usage(sys.stderr)
        self.exit(exitcodes.USAGE, f"{self.prog}: error: {message}\n")


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="vid2sub",
        description="Subtitles for videos and YouTube, made on your own machine.",
    )
    parser.add_argument("--version", action="version", version=f"vid2sub {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND", parser_class=_Parser)
    for name in COMMAND_MODULES:
        importlib.import_module(f"vid2sub.commands.{name}").add_parser(sub)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return exitcodes.OK
    return int(args.handler(args))
