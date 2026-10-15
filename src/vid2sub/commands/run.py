"""`vid2sub run`: subtitles for videos, folders and YouTube links (spec §18.1).

One input at a time, the machine kept awake. A dropped connection that doesn't come back within
--wait-on-connection, or Ctrl-C, exits 75: re-running the same command with --skip-existing
carries on. Inputs whose language was uncertain are listed at the end with the command that would
run them.
"""

from __future__ import annotations

import argparse
import shlex
from pathlib import Path

from vid2sub import exitcodes
from vid2sub.awake import keep_awake
from vid2sub.commands import _common
from vid2sub.commands._common import CommandError, Output, add_common, audio_track, duration
from vid2sub.config import Config
from vid2sub.engines.clients import quiet_libraries
from vid2sub.pipeline import InputResult, Paused, RunOptions, StopRun, run_one
from vid2sub.subs import langs, naming

SYMBOL = {"done": "✓", "skipped": "–", "failed": "✗", "uncertain": "?", "planned": "·"}


def add_parser(sub) -> None:
    p = sub.add_parser("run", help="make subtitles for videos, folders or YouTube links")
    p.add_argument("inputs", nargs="*", metavar="INPUT",
                   help="a video, a folder of videos, or a YouTube link")
    p.add_argument("--from-file", metavar="LIST",
                   help="read inputs from a file, one per line (- for stdin)")
    p.add_argument("--recursive", action="store_true", help="look inside subfolders too")
    p.add_argument("--from", dest="source_lang", default="auto", metavar="LANG",
                   help="the spoken language: en, ja, zh, yue, ko, or auto (the default)")
    p.add_argument("--to", dest="targets", nargs="+", metavar="LANG",
                   help="languages to translate into (default from vid2sub.toml; `none` for "
                        "captions in the spoken language only)")
    p.add_argument("--model", help="the transcription model, by its name in vid2sub.toml")
    p.add_argument("--translate-model", help="the translation model, by its name in vid2sub.toml")
    p.add_argument("--format", dest="formats", action="append", choices=["srt", "ass"])
    p.add_argument("--script", choices=["hant", "hans"],
                   help="Traditional or Simplified characters for Mandarin")
    p.add_argument("--glossary", type=Path, metavar="FILE")
    p.add_argument("--audio-track", type=audio_track, metavar="N|LANG")
    p.add_argument("--keep-video", action="store_true",
                   help="YouTube: keep the video too, not only the audio")
    p.add_argument("--skip-existing", action="store_true",
                   help="skip languages whose subtitle files already exist")
    p.add_argument("--overwrite-foreign", action="store_true",
                   help="replace subtitle files vid2sub didn't write")
    p.add_argument("--replace-edited", action="store_true",
                   help="let a new version replace one you edited")
    p.add_argument("--allow-cloud", action="store_true",
                   help="allow cloud models for this run (audio or text leaves this machine)")
    p.add_argument("--dry-run", action="store_true", help="say what would happen, write nothing")
    p.add_argument("--on-uncertain", choices=["proceed", "skip", "stop"], default="skip",
                   help="when the language is unclear: carry on, skip that file (default), or "
                        "stop")
    p.add_argument("--wait-on-connection", type=duration, default=600.0, metavar="DURATION",
                   help="how long to wait for a dropped connection (default 10m)")
    add_common(p)
    p.set_defaults(handler=run)


def options_from(args: argparse.Namespace, config: Config) -> RunOptions:
    """The run's options, with contradictions and unknown models refused before any input."""
    source = None if args.source_lang == "auto" else args.source_lang
    if source is not None:
        langs.get(source)
    if source == "yue" and args.script:
        raise CommandError(exitcodes.USAGE, "--script is for Mandarin; Cantonese subtitles are "
                           "always in Traditional characters", "leave out --script")
    _common.check_model(config, args.model, "transcribe", "--model")
    _common.check_model(config, args.translate_model, "translate", "--translate-model")
    if args.targets == ["none"]:
        targets: list[str] = []
    else:
        targets = [naming.target_track(t) for t in (args.targets or config.defaults.targets)]
    return RunOptions(
        source_lang=source, targets=targets, formats=args.formats or list(config.defaults.formats),
        model=args.model, translate_model=args.translate_model, script=args.script,
        glossary=args.glossary, audio_track=args.audio_track, keep_video=args.keep_video,
        skip_existing=args.skip_existing, overwrite_foreign=args.overwrite_foreign,
        allow_cloud=args.allow_cloud, dry_run=args.dry_run, on_uncertain=args.on_uncertain,
        wait_on_connection_s=args.wait_on_connection, replace_edited=args.replace_edited)


def report(out: Output, n: int, total: int, r: InputResult) -> None:
    out.event("result", index=n, status=r.status, kind=r.kind, written=len(r.written),
              foreign=len(r.foreign), kept=len(r.kept))
    line = f"{SYMBOL[r.status]} {out.name(r.title, n)} ({n}/{total}): {r.status}"
    if r.written:
        line += f", wrote {len(r.written)} file{'s' if len(r.written) != 1 else ''}"
    out.say(line)
    if out.tty:
        for name in r.written:
            out.say(f"    {name}")
        for key, value in r.plan.items():
            out.say(f"    {key}: {value}")
    if r.reason:
        out.say(f"    {r.reason if out.tty else (r.kind or r.status)}")
    if r.hint:
        out.say(f"    → {r.hint}")
    if r.foreign:
        out.say(f"    left {len(r.foreign)} file(s) alone that vid2sub didn't write or that you "
                "edited (--overwrite-foreign replaces only ones vid2sub didn't write)")
    if r.kept:
        out.say(f"    kept your edited {', '.join(r.kept)} "
                "(--replace-edited switches to the new version)")
    for note in r.notes:
        out.say(f"    {note}")


def summary(out: Output, results: list[InputResult]) -> None:
    counts = {status: sum(r.status == status for r in results) for status in SYMBOL}
    out.event("summary", **counts)
    out.say(" · ".join(f"{v} {k}" for k, v in counts.items() if v) or "nothing ran")
    again = [r for r in results if r.status in ("uncertain", "failed")]
    if again and out.tty:
        out.say("To run these again:")
        for r in again:
            extra = " --from LANG" if r.status == "uncertain" else ""
            out.say(f"  vid2sub run {shlex.quote(r.input)}{extra}")


def _interrupted(out: Output) -> int:
    out.warn("vid2sub: stopped. Run the same command with --skip-existing to carry on.")
    out.event("interrupted")
    return exitcodes.TEMPFAIL


def run(args: argparse.Namespace) -> int:
    out = Output(args.json)
    quiet_libraries()
    try:
        config = _common.load(args)
        try:
            options = options_from(args, config)
        except (langs.UnknownLanguage, naming.UnknownTrack) as err:
            raise CommandError(exitcodes.USAGE, str(err)) from None
        inputs = _common.expand(args.inputs, recursive=args.recursive, from_file=args.from_file)
        if not inputs:
            raise CommandError(exitcodes.USAGE, "nothing to do",
                               "give a video, a folder, a YouTube link, or --from-file")
        ctx = _common.new_context(config, options, out)
    except CommandError as err:
        return _common.fail(out, err)
    except KeyboardInterrupt:
        return _interrupted(out)
    results: list[InputResult] = []
    code = exitcodes.OK
    try:
        with keep_awake():
            for n, item in enumerate(inputs, 1):
                out.event("input", index=n, of=len(inputs))
                result = run_one(item, ctx)
                results.append(result)
                report(out, n, len(inputs), result)
    except Paused as err:
        out.warn(f"vid2sub: paused: {err}" + (f" ({err.error.hint})" if err.error.hint else ""))
        out.warn("  → when it's back, run the same command with --skip-existing to carry on")
        out.event("paused", kind=err.error.kind)
        code = exitcodes.TEMPFAIL
    except StopRun as err:
        out.warn(f"vid2sub: stopped: {err}")
        out.event("stopped")
        code = exitcodes.FAILED
    except KeyboardInterrupt:
        out.warn("vid2sub: stopped. Run the same command with --skip-existing to carry on.")
        out.event("interrupted")
        code = exitcodes.TEMPFAIL
    finally:
        ctx.close()
    summary(out, results)
    if code == exitcodes.OK and any(r.status == "failed" for r in results):
        code = exitcodes.FAILED
    return code
