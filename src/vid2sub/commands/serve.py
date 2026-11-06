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
inherits the engine's keys. The folder goes when the engine stops, on Ctrl-C and SIGTERM too:
uvicorn re-raises the signal after its own shutdown, and SIGTERM's default action would skip
`finally`, so it becomes a normal exit with status 143 (recordings' __main__ does the same;
Windows' Ctrl-Break likewise). Shutdown waits at most 3 seconds for open responses, since a paused video holds its
stream open. uvicorn's access log is off and it trusts no proxy headers, since none is in front of
it; the openai, httpx and chatlas loggers stay at WARNING, as for every command (§6.8, §6.2).
Without the built frontend (`www/ui.js`), serve refuses before it reads or binds anything (§18,
§23.5). The web modules are imported only when serve runs, so other commands don't load them, and
the Shiny app only once `runtime.configure()` has run, as recordings imports it.
"""

from __future__ import annotations

import argparse
import atexit
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from vid2sub import exitcodes
from vid2sub.commands._common import CommandError, Output, fail, load
from vid2sub.web import WWW

if TYPE_CHECKING:
    import uvicorn
    from starlette.types import ASGIApp

HOST = "127.0.0.1"
GRACE = 3  # seconds a shutdown waits for open responses before it cancels them
# The signals uvicorn re-raises after its shutdown whose default action skips `finally` and
# atexit: SIGTERM everywhere, Ctrl-Break on Windows. SIGINT raises KeyboardInterrupt already.
_EXIT_SIGNALS = [signal.SIGTERM] + ([signal.SIGBREAK] if hasattr(signal, "SIGBREAK") else [])
# SIGHUP (the terminal window closing) has no handler in uvicorn; it is sent down SIGTERM's path.
_HANGUP = getattr(signal, "SIGHUP", None)  # Windows has none
# What the browser opener needs from a desktop session on top of security.child_env(): a minimal
# environment (spec §6.7) so it never inherits keys, but not so minimal that it can't find a
# display. The names webbrowser.py reads: XDG_CURRENT_DESKTOP, GNOME_DESKTOP_SESSION_ID,
# KDE_FULL_SESSION, DISPLAY, WAYLAND_DISPLAY, TERM, BROWSER, and PROGRAMFILES(x86), PROGRAMFILES on
# Windows; the rest are what xdg-open and the browsers it starts use to reach the session.
_BROWSER_ENV = (
    "DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY", "XDG_RUNTIME_DIR", "XDG_CURRENT_DESKTOP",
    "XDG_SESSION_TYPE", "XDG_DATA_DIRS", "XDG_CONFIG_DIRS", "DBUS_SESSION_BUS_ADDRESS",
    "DESKTOP_SESSION", "GNOME_DESKTOP_SESSION_ID", "KDE_FULL_SESSION", "BROWSER", "TERM",
    "PROGRAMFILES", "PROGRAMFILES(x86)",
)
_OPEN_BROWSER = "import sys, webbrowser; sys.exit(not webbrowser.open(sys.argv[1]))"


def add_parser(sub) -> None:
    p = sub.add_parser("serve", help="start the editor in your browser")
    p.add_argument("--port", type=_port, metavar="N",
                   help="the port on 127.0.0.1 (default: [server] port in vid2sub.toml, 8765; "
                        "0 takes any free port)")
    p.add_argument("--no-browser", action="store_true",
                   help="print the link to open, but don't open a browser")
    p.add_argument("--config", metavar="PATH", help="the vid2sub.toml to use")
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
    from vid2sub.engines.clients import quiet_libraries
    from vid2sub.web import auth, runtime
    from vid2sub.web.app import create_app

    quiet_libraries()  # OPENAI_LOG and CHATLAS_LOG are ignored (§6.8)
    out = Output(False)
    try:
        if not (WWW / "ui.js").is_file():
            raise CommandError(exitcodes.UNAVAILABLE, "build the frontend first",
                               "make build (it needs Node 22 or later), then vid2sub serve")
        config = load(args)
        sock = bind(config.server.port if args.port is None else args.port)
    except CommandError as err:
        return fail(out, err)
    rt = None
    try:
        rt = runtime.build(config)
        runtime.configure(rt)
        token = auth.new_token()
        app = create_app(rt, token=token, port=sock.getsockname()[1], shiny_app=shiny_app())
    except BaseException:  # a bug: leave nothing running behind the traceback
        sock.close()
        if rt is not None:
            rt.queue.close()
        raise
    browser = config.server.open_browser and not args.no_browser
    return serve(app, sock, token=token, open_browser=browser, out=out)


def serve(app: ASGIApp, sock: socket.socket, *, token: str, open_browser: bool,
          out: Output) -> int:
    """Run `app` on the listening `sock` until Ctrl-C or SIGTERM, with the link printed and, if
    asked, the browser opened on the redirect file. Blocks; call it from the main thread."""
    import uvicorn

    from vid2sub.web import auth

    port = sock.getsockname()[1]
    previous = {sig: signal.signal(sig, _exit_on_signal) for sig in _EXIT_SIGNALS}
    if _HANGUP is not None:
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
        uvicorn.Server(uvicorn_config(app)).run(sockets=[sock])
    except KeyboardInterrupt:
        pass
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
    sys.exit(128 + signum)


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
