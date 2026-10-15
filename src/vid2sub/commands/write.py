"""`vid2sub write`: re-write subtitle files from the sidecar's current versions (spec §18.1)."""

from __future__ import annotations

import argparse

from vid2sub import exitcodes
from vid2sub.commands import _common
from vid2sub.commands._common import CommandError, Output, add_common
from vid2sub.commands.run import report, summary
from vid2sub.pipeline import InputResult, RunOptions, write_one


def add_parser(sub) -> None:
    p = sub.add_parser("write", help="write subtitle files again from the sidecar")
    p.add_argument("inputs", nargs="*", metavar="INPUT")
    p.add_argument("--from-file", metavar="LIST",
                   help="read inputs from a file, one per line (- for stdin)")
    p.add_argument("--recursive", action="store_true", help="look inside subfolders too")
    p.add_argument("--format", dest="formats", action="append", choices=["srt", "ass"])
    p.add_argument("--overwrite-foreign", action="store_true",
                   help="replace subtitle files vid2sub didn't write")
    add_common(p)
    p.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    out = Output(args.json)
    try:
        config = _common.load(args)
        inputs = _common.expand(args.inputs, recursive=args.recursive, from_file=args.from_file)
        if not inputs:
            raise CommandError(exitcodes.USAGE, "nothing to do",
                               "give a video, a folder, or --from-file")
        options = RunOptions(formats=args.formats or list(config.defaults.formats),
                             overwrite_foreign=args.overwrite_foreign)
        ctx = _common.new_context(config, options, out)
    except CommandError as err:
        return _common.fail(out, err)
    except KeyboardInterrupt:
        out.warn("vid2sub: stopped.")
        out.event("interrupted")
        return exitcodes.TEMPFAIL
    results: list[InputResult] = []
    code = exitcodes.OK
    try:
        for n, item in enumerate(inputs, 1):
            result = write_one(item, ctx)
            results.append(result)
            report(out, n, len(inputs), result)
    except KeyboardInterrupt:
        out.warn("vid2sub: stopped.")
        out.event("interrupted")
        code = exitcodes.TEMPFAIL
    finally:
        ctx.close()
    summary(out, results)
    if code == exitcodes.OK and any(r.status == "failed" for r in results):
        code = exitcodes.FAILED
    return code
