"""`vid2sub models`: the catalog, and what's usable on this machine now (spec §11, §18.1)."""

from __future__ import annotations

import argparse

from vid2sub import detect as detecting
from vid2sub import exitcodes
from vid2sub.catalog import CATALOG, readme_table
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
    configured = set()
    for c in cands:
        entry = config.models[c.name]
        configured.add(c.catalog)
        title = CATALOG[c.catalog].title if c.catalog in CATALOG else "uncatalogued"
        out.event("model", name=c.name, catalog=c.catalog, task=entry.task,
                  available=c.available, reason=c.reason, cloud=c.cloud)
        mark = "✓" if c.available else "✗"
        out.say(f"{mark} {c.name}: {title} ({entry.task}{', cloud' if c.cloud else ''})"
                + (f" — {c.reason}" if c.reason else ""))
    for cid, entry in CATALOG.items():
        if cid not in configured:
            out.event("model", name=None, catalog=cid, task=entry.task, available=False,
                      reason="not in vid2sub.toml", cloud=entry.cloud)
            out.say(f"· {entry.title} ({entry.task}): not in vid2sub.toml")
    return exitcodes.OK
