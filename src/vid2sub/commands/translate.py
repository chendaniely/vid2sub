"""`vid2sub translate`: translate videos that already have a sidecar (spec §18.1).

Why: a person adds a language later without transcribing again. Without --stale-only every cue is
translated afresh; a track a person edited is still kept unless --replace-edited (spec §14.4).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from vid2sub import exitcodes
from vid2sub.awake import keep_awake
from vid2sub.commands import _common
from vid2sub.commands._common import CommandError, Output, add_common
from vid2sub.commands.run import report, summary
from vid2sub.engines.clients import quiet_libraries
from vid2sub.pipeline import InputResult, Paused, RunOptions, StopRun, translate_one
from vid2sub.subs import naming


def add_parser(sub) -> None:
    p = sub.add_parser("translate", help="translate videos that already have subtitles")
    p.add_argument("inputs", nargs="*", metavar="INPUT")
    p.add_argument("--from-file", metavar="LIST",
                   help="read inputs from a file, one per line (- for stdin)")
    p.add_argument("--recursive", action="store_true", help="look inside subfolders too")
    p.add_argument("--to", dest="targets", nargs="+", required=True, metavar="LANG")
    p.add_argument("--stale-only", action="store_true",
                   help="only cues whose source changed, and new ones")
    p.add_argument("--translate-model", help="the translation model, by its name in vid2sub.toml")
    p.add_argument("--glossary", type=Path, metavar="FILE")
    p.add_argument("--format", dest="formats", action="append", choices=["srt", "ass"])
    p.add_argument("--overwrite-foreign", action="store_true",
                   help="replace subtitle files vid2sub didn't write")
    p.add_argument("--replace-edited", action="store_true",
                   help="let a new version replace one you edited")
    p.add_argument("--allow-cloud", action="store_true",
                   help="allow cloud models for this run (text leaves this machine)")
    add_common(p)
    p.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    out = Output(args.json)
    quiet_libraries()
    try:
        config = _common.load(args)
        try:
            targets = [naming.target_track(t) for t in args.targets]
        except naming.UnknownTrack as err:
            raise CommandError(exitcodes.USAGE, str(err)) from None
        inputs = _common.expand(args.inputs, recursive=args.recursive, from_file=args.from_file)
        if not inputs:
            raise CommandError(exitcodes.USAGE, "nothing to do",
                               "give a video, a folder, or --from-file")
        options = RunOptions(targets=targets,
                             formats=args.formats or list(config.defaults.formats),
                             translate_model=args.translate_model, glossary=args.glossary,
                             overwrite_foreign=args.overwrite_foreign,
                             replace_edited=args.replace_edited, allow_cloud=args.allow_cloud)
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
        with keep_awake():
            for n, item in enumerate(inputs, 1):
                out.event("input", index=n, of=len(inputs))
                result = translate_one(item, ctx, fresh=not args.stale_only)
                results.append(result)
                report(out, n, len(inputs), result)
    except Paused as err:
        out.warn(f"vid2sub: paused: {err}" + (f" ({err.error.hint})" if err.error.hint else ""))
        out.warn("  → when it's back, run the same command again")
        out.event("paused", kind=err.error.kind)
        code = exitcodes.TEMPFAIL
    except StopRun as err:
        out.warn(f"vid2sub: stopped: {err}")
        out.event("stopped")
        code = exitcodes.FAILED
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
