"""`vid2sub config`: print a starter vid2sub.toml, or where vid2sub looks for it (spec §5).

vid2sub never writes the settings file: `config init` prints it for you to save.
"""

from __future__ import annotations

import argparse
import sys

from vid2sub import exitcodes
from vid2sub.config import STARTER, config_path


def add_parser(sub) -> None:
    p = sub.add_parser("config", help="print a starter vid2sub.toml, or where it's read from")
    actions = p.add_subparsers(dest="action", metavar="ACTION", required=True,
                               parser_class=type(p))
    init = actions.add_parser("init", help="print a starter vid2sub.toml (save it yourself)")
    init.set_defaults(handler=_init)
    where = actions.add_parser("path", help="print where vid2sub looks for vid2sub.toml")
    where.add_argument("--config", metavar="PATH")
    where.set_defaults(handler=_path)


def _init(args: argparse.Namespace) -> int:
    sys.stdout.write(STARTER)
    return exitcodes.OK


def _path(args: argparse.Namespace) -> int:
    print(config_path(args.config))
    return exitcodes.OK
