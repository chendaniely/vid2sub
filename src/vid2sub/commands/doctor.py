"""`vid2sub doctor`: is everything vid2sub needs here? (spec §18.1)

Python, ffmpeg and ffprobe are essential; deno (YouTube), yt-dlp's age and the Mac extra are
warnings. Endpoints serving local models are asked for their model list (not with --offline);
cloud endpoints are never contacted. Keys are reported by presence only, never their values.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass

from vid2sub import __version__, exitcodes
from vid2sub import detect as detecting
from vid2sub.commands._common import Output
from vid2sub.config import Config, ConfigError, config_path, is_local, load_config
from vid2sub.engines import clients
from vid2sub.engines.base import EngineError
from vid2sub.media.tools import Tools, version


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str
    hint: str = ""
    essential: bool = True


def add_parser(sub) -> None:
    p = sub.add_parser("doctor", help="check that everything vid2sub needs is here")
    p.add_argument("--config", metavar="PATH")
    p.add_argument("--json", action="store_true")
    p.add_argument("--offline", action="store_true", help="don't contact any server")
    p.set_defaults(handler=run)


def _tool(tools: Tools, name: str, minimum: tuple[int, ...], essential: bool, hint: str) -> Check:
    exe = getattr(tools, name)
    if not exe:
        return Check(name, False, "not found", hint, essential)
    found = version(exe)
    if found is None:  # a build whose version isn't major.minor (git builds): not an error
        soft = (f"couldn't read its version; vid2sub needs {name} "
                f"{'.'.join(map(str, minimum))} or later")
        return Check(name, True, "unknown version", soft, essential)
    ok = found >= minimum
    return Check(name, ok, ".".join(map(str, found)), "" if ok else hint, essential)


def _ytdlp() -> Check:
    try:
        from yt_dlp.version import __version__ as v
    except ImportError:
        return Check("yt-dlp", False, "not installed", "reinstall vid2sub", essential=False)
    try:
        age = (dt.date.today() - dt.date(*map(int, v.split(".")[:3]))).days
    except ValueError:
        return Check("yt-dlp", True, v, essential=False)
    ok = age <= 90
    return Check("yt-dlp", ok, f"{v} ({age} days old)",
                 "" if ok else "uv tool upgrade vid2sub --upgrade-package yt-dlp",
                 essential=False)


def checks(config_arg: str | None, environ: Mapping[str, str] = os.environ,
           tools: Tools | None = None, *, offline: bool = False) -> tuple[list[Check], bool]:
    """All checks, and whether the config loaded."""
    tools = tools or Tools.find()
    out = [Check("python", sys.version_info >= (3, 12), sys.version.split()[0],
                 "vid2sub needs Python 3.12 or later"),
           Check("vid2sub", True, __version__),
           _tool(tools, "ffmpeg", (6,), True, "install ffmpeg 6 or later"),
           _tool(tools, "ffprobe", (6,), True, "ffprobe comes with ffmpeg 6 or later"),
           _tool(tools, "deno", (2, 3), False, "install deno 2.3+ for YouTube (https://deno.com)"),
           _ytdlp()]
    if sys.platform == "darwin":
        ok = detecting.mlx_available()
        out.append(Check("mlx-qwen3-asr", ok, "installed" if ok else "not installed",
                         "" if ok else "for Qwen3-ASR on this Mac: install vid2sub[mac]",
                         essential=False))
    path = config_path(config_arg, environ)
    try:
        config = load_config(path)
    except ConfigError as err:
        out.append(Check("vid2sub.toml", False, str(err), "fix it, or start from "
                         "`vid2sub config init`"))
        return out, False
    out.append(Check("vid2sub.toml", True, "found" if path.exists() else "not found: defaults",
                     "" if path.exists() else "`vid2sub config init` prints a starter",
                     essential=False))
    out += _endpoints(config, environ, offline)
    return out, True


def _endpoints(config: Config, environ: Mapping[str, str], offline: bool) -> list[Check]:
    keys = clients.KeyRing(environ=environ)
    out = []
    for name, ep in config.endpoints.items():
        if ep.key_env:
            present = bool(environ.get(ep.key_env))
            out.append(Check(f"key {ep.key_env}", present, "set" if present else "not set",
                             "" if present else f"export {ep.key_env} in your shell",
                             essential=False))
        local = any(m.endpoint == name and is_local(m, config) for m in config.models.values())
        if not local or offline:
            reason = "cloud: not contacted" if not local else "not contacted (--offline)"
            out.append(Check(f"endpoint {name}", True, reason, essential=False))
            continue
        try:
            served = clients.list_models(name, ep, keys)
            out.append(Check(f"endpoint {name}", True, f"serves {len(served)} model(s)",
                             essential=False))
        except EngineError as err:
            out.append(Check(f"endpoint {name}", False, str(err), err.hint, essential=False))
    return out


def run(args: argparse.Namespace) -> int:
    out = Output(args.json)
    clients.quiet_libraries()
    results, config_ok = checks(args.config, offline=args.offline)
    for c in results:
        out.event("check", check=c.name, ok=c.ok, essential=c.essential,
                  detail=c.detail if c.name != "vid2sub.toml" else ("ok" if c.ok else "invalid"))
        if out.json:
            continue
        mark = "✓" if c.ok else ("✗" if c.essential else "!")
        out.say(f"{mark} {c.name}: {c.detail}" + (f" → {c.hint}" if c.hint else ""))
    if not config_ok:
        return exitcodes.CONFIG
    if any(c.essential and not c.ok for c in results):
        return exitcodes.UNAVAILABLE
    return exitcodes.OK
