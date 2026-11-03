"""`vid2sub cache clear`: empty the cache of playback audio and preview copies (spec §8.9, §18.1).

Everything in the cache can be made again, so clearing it asks nothing. Only vid2sub's own entry
folders are removed (`cache.Cache.clear`). The output gives the bytes freed and never the
cache's path, in `--json` or not (spec §6.8).
"""

from __future__ import annotations

import argparse

from vid2sub import cache as caching
from vid2sub import exitcodes
from vid2sub.commands._common import Output


def add_parser(sub) -> None:
    p = sub.add_parser("cache", help="manage the cache of playback audio and preview copies")
    actions = p.add_subparsers(dest="action", metavar="ACTION", required=True,
                               parser_class=type(p))
    clear = actions.add_parser("clear", help="remove everything in the cache")
    clear.add_argument("--json", action="store_true",
                       help="JSON Lines events for scripts (never paths)")
    clear.set_defaults(handler=_clear)


def _clear(args: argparse.Namespace) -> int:
    out = Output(args.json)
    freed = caching.Cache(caching.default_root(), max_bytes=0).clear()
    out.event("cache_cleared", bytes=freed)
    out.say(f"cleared {freed / 1_000_000:.1f} MB from the cache")
    return exitcodes.OK
