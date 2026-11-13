"""`vid2sub serve`: start the local web app on 127.0.0.1 and open the browser through the launch
token's redirect file (spec §18.1, §6.1, §19.1).

The engine binds 127.0.0.1 only (§6.1), on `--port`, else `[server] port` (8765); 0 takes any free
port. The socket is bound and listening before anything is printed or opened, so the link names
the real port and a browser that loads it early waits instead of being refused. Each launch makes
a new token. Its link (`/auth#t=<token>`) is printed only to a terminal, for opening by hand: when
the output goes to a file or a pipe, which may be a log other people can read, the redirect
file's path is printed instead. The browser, unless `--no-browser` or `[server] open_browser =
false`, is opened on that redirect file (mode 0600 in a private folder), so `ps` shows only its
path. A browser that doesn't come back doesn't hold up the engine: it is opened from a thread, as
Jupyter does, and by a helper process with the §6.7 environment, so the opener never
inherits the engine's keys. The folder goes when the engine stops, on Ctrl-C and SIGTERM too.
Until uvicorn's own handlers are in, those signals only note themselves and ask uvicorn to
stop: a handler that raised (Python's own Ctrl-C handler, or `sys.exit`) could be dropped, since
Python discards an exception raised inside a weakref callback or a `__del__`, and the engine then
served on (CI, 2026-11-11; Task 18). uvicorn's handlers take over while it serves and hand the
signals back when it stops; asyncio then waits for the worker threads a Test, a retranslation
or the playback audio may hold (up to minutes), so from that point the signals raise again, as
before: a further Ctrl-C ends the wait (Task 18 fix round 1, I-3; a raise lost to a weakref
callback there costs only that one press). SIGTERM then ends in a normal exit with status 143,
so `finally` and atexit run (recordings' __main__ exits so too; Windows' Ctrl-Break likewise),
and Ctrl-C in status 0.
Shutdown waits at most 3 seconds for open responses, since a
paused video holds its stream open. uvicorn's access log is off and it trusts no proxy
headers, since none is in front of it; the openai, httpx and chatlas loggers stay at WARNING,
as for every command (§6.8, §6.2).
Without the built frontend (`www/ui.js`), serve refuses before it reads or binds anything (§18,
§23.5). `--demo` serves a fresh copy of the demo instead, reading no vid2sub.toml and no key,
and, once it is set up, guarded against writes, reads and connections beyond it, as far as
Python audits them (`vid2sub.web.demo`, spec §22.7). The web
modules are imported only when serve runs, so other commands don't load them, and the Shiny app
only once `runtime.configure()` has run, as recordings imports it.
"""

from __future__ import annotations

import argparse
import atexit
import contextlib
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

from vid2sub import exitcodes
from vid2sub.commands._common import CommandError, Output, fail, load
from vid2sub.web import WWW

if TYPE_CHECKING:
    import uvicorn
    from starlette.types import ASGIApp

    from vid2sub.media.tools import Tools

HOST = "127.0.0.1"
GRACE = 3  # seconds a shutdown waits for open responses before it cancels them
# The signals that end in status 128 + the signal, through `finally` and atexit, where their
# default action would skip both: SIGTERM everywhere, Ctrl-Break on Windows. Ctrl-C ends in 0.
_EXIT_SIGNALS = [signal.SIGTERM] + ([signal.SIGBREAK] if hasattr(signal, "SIGBREAK") else [])
_STOP_SIGNALS = [signal.SIGINT, *_EXIT_SIGNALS]  # only noted until uvicorn hands them back
# SIGHUP (the terminal window closing) has no handler in uvicorn; it is sent down SIGTERM's path,
# unless it was ignored on entry: `nohup vid2sub serve &` asks to outlive its terminal.
_HANGUP = getattr(signal, "SIGHUP", None)  # Windows has none
# What the browser opener gets on top of security.child_env(): a minimal environment (spec §6.7),
# so it never inherits keys, but enough to reach a desktop session. webbrowser.py reads
# XDG_CURRENT_DESKTOP, GNOME_DESKTOP_SESSION_ID, KDE_FULL_SESSION, DISPLAY, WAYLAND_DISPLAY and
# BROWSER, and on Windows PROGRAMFILES and PROGRAMFILES(x86). The others are for what xdg-open and
# a browser it starts look up (the session bus, the XDG directories, KDE's version, input methods).
# A browser this helper starts, as opposed to one already running, keeps this environment for its
# whole life. No Linux desktop has been tried; TERM is left out on purpose (it makes webbrowser
# register console browsers, which cannot work with DEVNULL stdio).
_BROWSER_ENV = (
    "DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY", "XDG_RUNTIME_DIR", "XDG_CURRENT_DESKTOP",
    "XDG_SESSION_TYPE", "XDG_DATA_DIRS", "XDG_CONFIG_DIRS", "XDG_DATA_HOME", "XDG_CONFIG_HOME",
    "DBUS_SESSION_BUS_ADDRESS", "DESKTOP_SESSION", "GNOME_DESKTOP_SESSION_ID",
    "KDE_FULL_SESSION", "KDE_SESSION_VERSION", "GTK_IM_MODULE", "QT_IM_MODULE", "XMODIFIERS",
    "BROWSER", "PROGRAMFILES", "PROGRAMFILES(x86)",
)
_OPEN_BROWSER = "import sys, webbrowser; sys.exit(not webbrowser.open(sys.argv[1]))"


def add_parser(sub) -> None:
    p = sub.add_parser("serve", help="start the editor in your browser")
    p.add_argument("--port", type=_port, metavar="N",
                   help="the port on 127.0.0.1 (default: [server] port in vid2sub.toml, 8765; "
                        "0 takes any free port)")
    p.add_argument("--no-browser", action="store_true",
                   help="print the link to open, but don't open a browser")
    which = p.add_mutually_exclusive_group()
    which.add_argument("--config", metavar="PATH", help="the vid2sub.toml to use")
    which.add_argument("--demo", action="store_true",
                       help="serve a fresh copy of the demo episode, reading no vid2sub.toml, "
                            "with a guard against writes, reads and connections beyond it")
    p.set_defaults(handler=run)


def _port(value: str) -> int:
    if not (value.isascii() and value.isdigit()) or int(value) > 65535:
        raise argparse.ArgumentTypeError("a port is a number from 0 to 65535")
    return int(value)


def shiny_app() -> ASGIApp:
    """The Shiny app, imported now: its module makes it at import, from `www/`, and its server
    reads `runtime.current()`."""
    from vid2sub.web.server import app

    return app


def bind(port: int) -> socket.socket:
    """A socket listening on 127.0.0.1 and `port` (0: any free one); CommandError (69) if the
    port can't be had."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if os.name != "nt":  # on Windows, SO_REUSEADDR would let another program share the port
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((HOST, port))
        sock.listen(128)
    except OSError as err:
        sock.close()
        raise CommandError(exitcodes.UNAVAILABLE,
                           f"port {port} can't be used on {HOST}"
                           + (f" ({err.strerror})" if err.strerror else ""),
                           "is vid2sub already running? Pick another port with --port N, "
                           "or --port 0 for any free one") from None
    return sock


def run(args: argparse.Namespace) -> int:
    from vid2sub.config import Config
    from vid2sub.engines.clients import quiet_libraries
    from vid2sub.web import auth, demo, runtime
    from vid2sub.web.app import create_app

    quiet_libraries()  # OPENAI_LOG and CHATLAS_LOG are ignored (§6.8)
    out = Output(False)
    try:
        if not (WWW / "ui.js").is_file():
            raise CommandError(exitcodes.UNAVAILABLE, "build the frontend first",
                               "make build (it needs Node 22 or later), then vid2sub serve")
        made = _demo() if args.demo else None
        config = Config() if args.demo else load(args)  # the demo reads no vid2sub.toml
        sock = bind(config.server.port if args.port is None else args.port)
    except CommandError as err:
        return fail(out, err)
    rt = None
    try:
        rt = demo.runtime_for(*made) if made else runtime.build(config)
        runtime.configure(rt)
        token = auth.new_token()
        app = create_app(rt, token=token, port=sock.getsockname()[1], shiny_app=shiny_app())
        if made:
            demo.isolate(made[0].parent)  # from here on, the demo touches nothing else
    except BaseException:  # a bug: leave nothing running behind the traceback
        sock.close()
        if rt is not None:
            rt.queue.close()
        raise
    browser = config.server.open_browser and not args.no_browser
    return serve(app, sock, token=token, open_browser=browser, out=out)


def _demo() -> tuple[Path, Tools]:
    """The demo's fresh copy (spec §22.7), and the tools that made its video."""
    from vid2sub.media.tools import ToolFailed, ToolMissing, Tools
    from vid2sub.web import demo

    tools = Tools.find()
    try:
        return demo.prepare(tools), tools
    except demo.DemoMissing as err:
        raise CommandError(exitcodes.UNAVAILABLE, str(err)) from None
    except ToolMissing:
        raise CommandError(exitcodes.UNAVAILABLE, "the demo needs ffmpeg",
                           "install ffmpeg 6 or later (vid2sub doctor checks it)") from None
    except ToolFailed:
        raise CommandError(exitcodes.UNAVAILABLE, "ffmpeg couldn't make the demo's video",
                           "it needs ffmpeg built with libvpx and libopus") from None


def serve(app: ASGIApp, sock: socket.socket, *, token: str, open_browser: bool,
          out: Output) -> int:
    """Run `app` on the listening `sock` until Ctrl-C or SIGTERM, with the link printed and, if
    asked, the browser opened on the redirect file. Blocks; call it from the main thread."""
    import uvicorn

    from vid2sub.web import auth

    port = sock.getsockname()[1]
    class Server(uvicorn.Server):
        @contextlib.contextmanager
        def capture_signals(self) -> Iterator[None]:
            """uvicorn's, and when it has handed the signals back (and replayed any it caught
            to `note`), a further Ctrl-C or SIGTERM raises again, so it can end asyncio's wait
            for worker threads (uvicorn 0.54 `serve`; Python 3.14 `Runner.close`)."""
            with super().capture_signals():
                yield
            if threading.current_thread() is threading.main_thread():
                signal.signal(signal.SIGINT, signal.default_int_handler)
                for sig in _EXIT_SIGNALS:
                    signal.signal(sig, _exit_on_signal)

    server = Server(uvicorn_config(app))
    seen: list[int] = []

    def note(signum: int, frame: object) -> None:
        """Note the signal and ask uvicorn to stop, as its own handler does; never raise."""
        seen.append(signum)
        if server.should_exit and signum == signal.SIGINT:
            server.force_exit = True  # a second Ctrl-C stops waiting for open responses
        server.should_exit = True

    previous = {sig: signal.signal(sig, note) for sig in _STOP_SIGNALS}
    if _HANGUP is not None and signal.getsignal(_HANGUP) is not signal.SIG_IGN:
        previous[_HANGUP] = signal.signal(_HANGUP, _hangup_as_sigterm)
    page: Path | None = None
    try:
        link = auth.auth_url(port, token)
        page = auth.write_redirect(link)
        atexit.register(shutil.rmtree, page.parent, ignore_errors=True)  # if `finally` never runs
        out.say(f"vid2sub is running on {HOST}, port {port}.")
        if out.tty:
            out.say("Open the editor with this link (it works until vid2sub stops):")
            out.say(f"  {link}")
        else:  # a file or a pipe: the link would put the token where others may read it
            out.say("Open the editor by opening this file in a browser (it works until vid2sub "
                    "stops):")
            out.say(f"  {page}")
        out.say("Ctrl-C stops vid2sub.")
        if open_browser:
            threading.Thread(target=_open, args=(page, out), name="vid2sub-browser",
                             daemon=True).start()
        try:
            server.run(sockets=[sock])  # its handlers hand each signal back to `note` as it ends
        except KeyboardInterrupt:  # a further Ctrl-C while asyncio waited for worker threads
            pass
        ended_by = next((sig for sig in seen if sig in _EXIT_SIGNALS), None)
        if ended_by is not None:
            raise SystemExit(128 + ended_by)
    finally:
        if page is not None:
            shutil.rmtree(page.parent, ignore_errors=True)
        sock.close()
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    return exitcodes.OK


def uvicorn_config(app: ASGIApp) -> uvicorn.Config:
    """No access log (§6.8), no proxy headers believed (no proxy is in front of the engine, and
    X-Forwarded-Proto would change the scheme the guards compare Origin with), no Server header,
    only uvicorn's warnings, and a shutdown that waits GRACE seconds for open responses."""
    import uvicorn

    return uvicorn.Config(app, access_log=False, proxy_headers=False, server_header=False,
                          log_level="warning", lifespan="on", timeout_graceful_shutdown=GRACE)


def _exit_on_signal(signum: int, frame: object) -> None:
    raise SystemExit(128 + signum)  # through `finally` and atexit, which the default action skips


def _hangup_as_sigterm(signum: int, frame: object) -> None:
    signal.raise_signal(signal.SIGTERM)  # uvicorn shuts down gracefully, then SIGTERM exits 143


def _open(page: Path, out: Output) -> None:
    """Open `page` in the browser from a helper process with the §6.7 environment, since
    `webbrowser` would start the opener with every variable the engine holds, keys included."""
    from vid2sub.security import child_env

    env = {**child_env(), **{k: os.environ[k] for k in _BROWSER_ENV if k in os.environ}}
    try:
        opened = subprocess.run(
            [sys.executable, "-I", "-c", _OPEN_BROWSER, page.as_uri()], check=False, env=env,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ).returncode == 0
    except OSError:
        opened = False
    if not opened:
        out.warn("vid2sub couldn't open a browser: open what it printed above by hand")
