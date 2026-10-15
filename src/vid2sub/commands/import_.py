"""`vid2sub import`: make an existing SRT or ASS a track of a video (spec §15.4, §18.1)."""

from __future__ import annotations

import argparse

from vid2sub import exitcodes
from vid2sub.commands import _common
from vid2sub.commands._common import CommandError, Output, add_common
from vid2sub.commands.run import report
from vid2sub.pipeline import RunOptions, import_one


def add_parser(sub) -> None:
    p = sub.add_parser("import", help="use an existing SRT or ASS file as a video's subtitles")
    p.add_argument("subfile", metavar="SUBFILE")
    p.add_argument("--video", required=True, metavar="VIDEO")
    p.add_argument("--lang", metavar="LANG",
                   help="the subtitle's language (default: from its file name)")
    add_common(p)
    p.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    out = Output(args.json)
    try:
        config = _common.load(args)
        ctx = _common.new_context(config, RunOptions(), out)
    except CommandError as err:
        return _common.fail(out, err)
    except KeyboardInterrupt:
        out.warn("vid2sub: stopped.")
        out.event("interrupted")
        return exitcodes.TEMPFAIL
    try:
        result = import_one(args.subfile, args.video, args.lang, ctx)
    except KeyboardInterrupt:
        out.warn("vid2sub: stopped.")
        out.event("interrupted")
        return exitcodes.TEMPFAIL
    finally:
        ctx.close()
    report(out, 1, 1, result)
    return exitcodes.FAILED if result.status == "failed" else exitcodes.OK
