"""`vid2sub detect`: the Review table without running anything (spec §10, §18.1)."""

from __future__ import annotations

import argparse

from vid2sub import exitcodes
from vid2sub.commands import _common
from vid2sub.commands._common import CommandError, Output, add_common, audio_track
from vid2sub.engines.clients import quiet_libraries
from vid2sub.pipeline import Paused, RunOptions, detect_one
from vid2sub.subs import langs


def add_parser(sub) -> None:
    p = sub.add_parser("detect", help="detect each file's language and the models run would use")
    p.add_argument("inputs", nargs="*", metavar="INPUT")
    p.add_argument("--from-file", metavar="LIST")
    p.add_argument("--recursive", action="store_true")
    p.add_argument("--from", dest="source_lang", default="auto", metavar="LANG")
    p.add_argument("--audio-track", type=audio_track, metavar="N|LANG")
    p.add_argument("--allow-cloud", action="store_true")
    add_common(p)
    p.set_defaults(handler=run)


def _clock(ms: int) -> str:
    s = ms // 1000
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}"


def run(args: argparse.Namespace) -> int:
    out = Output(args.json)
    quiet_libraries()
    try:
        config = _common.load(args)
        source = None if args.source_lang == "auto" else args.source_lang
        if source is not None:
            try:
                langs.get(source)
            except langs.UnknownLanguage as err:
                raise CommandError(exitcodes.USAGE, str(err)) from None
        inputs = _common.expand(args.inputs, recursive=args.recursive, from_file=args.from_file)
    except CommandError as err:
        return _common.fail(out, err)
    options = RunOptions(source_lang=source, audio_track=args.audio_track,
                         allow_cloud=args.allow_cloud)
    ctx = _common.new_context(config, options, out)
    failed = False
    code = exitcodes.OK
    try:
        for n, item in enumerate(inputs, 1):
            r = detect_one(item, ctx)
            d = r.detection
            out.event("detect", index=n, duration_ms=r.duration_ms, tracks=len(r.tracks),
                      language=(d.language if d else source), confidence=d.confidence if d else None,
                      uncertain=d.uncertain if d else False,
                      transcribe=r.transcribe.model if r.transcribe else None,
                      translate=r.translate.model if r.translate else None, kind=r.kind)
            out.say(f"{out.name(r.title, n)}  {_clock(r.duration_ms)}  audio: "
                    f"{'; '.join(r.tracks) or '?'}")
            if r.error:
                failed = True
                out.say(f"  ✗ {r.error if out.tty else r.kind}" + (f" → {r.hint}" if r.hint
                                                                     else ""))
                continue
            if d:
                out.say(f"  language: {d.language or '?'} ({d.confidence:.0%}, {d.detector})")
                if d.uncertain:
                    out.say(f"  ? {d.reason()} → run with --from LANG")
            for label, s in (("transcribe", r.transcribe), ("translate", r.translate)):
                if s is not None:
                    out.say(f"  {label}: {s.model or 'nothing usable'}"
                            + (f" ({s.warning})" if s.warning else ""))
    except Paused as err:
        out.warn(f"vid2sub: paused: {err}" + (f" ({err.error.hint})" if err.error.hint else ""))
        out.warn("  → when it's back, run the same command again")
        out.event("paused", kind=err.error.kind)
        code = exitcodes.TEMPFAIL
    except KeyboardInterrupt:
        out.warn("vid2sub: stopped.")
        out.event("interrupted")
        code = exitcodes.TEMPFAIL
    finally:
        ctx.close()
    if code == exitcodes.OK and failed:
        code = exitcodes.FAILED
    return code
