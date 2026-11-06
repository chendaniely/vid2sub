"""`vid2sub serve`: start the local web app on 127.0.0.1 and open the browser through the launch
token's redirect file (spec §18.1, §6.1, §19.1).

The engine binds 127.0.0.1 only (§6.1), on `--port`, else `[server] port` (8765); 0 takes any free
port. The socket is bound and listening before anything is printed or opened, so the link names
the real port and a browser that loads it early waits instead of being refused. Each launch makes
a new token. Its link (`/auth#t=<token>`) is printed to the terminal for opening by hand, and the
browser, unless `--no-browser` or `[server] open_browser = false`, is opened on a redirect file
holding it (mode 0600 in a private folder), so `ps` shows only that file's path. A browser that
doesn't come back doesn't hold up the engine: it is opened from a thread, as Jupyter does. The
folder goes when the engine stops, on Ctrl-C and SIGTERM too: uvicorn re-raises the signal after
its own shutdown, and SIGTERM's default action would skip `finally`, so it becomes a normal exit
with status 143 (recordings' __main__ does the same). uvicorn's access log is off and it trusts
no proxy headers, since none is in front of it (§6.8, §6.2); the token goes to no log. Without
the built frontend (`www/ui.js`), serve refuses before it reads or binds anything (§18, §23.5).
The Shiny app is imported only once `runtime.configure()` has run, as recordings imports it.
"""

from __future__ import annotations

import argparse
import atexit
import os
import shutil
import signal
import socket
import sys
import threading
import webbrowser
from pathlib import Path

import uvicorn
from starlette.types import ASGIApp

from vid2sub import exitcodes
from vid2sub.commands._common import CommandError, Output, fail, load
from vid2sub.web import auth, runtime
from vid2sub.web.app import WWW, create_app

HOST = "127.0.0.1"


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
    if not value.isdigit() or int(value) > 65535:
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
    out = Output(False)
    try:
        if not (WWW / "ui.js").is_file():
            raise CommandError(exitcodes.UNAVAILABLE, "build the frontend first",
                               "make build (it needs Node 22 or later), then vid2sub serve")
        config = load(args)
        sock = bind(config.server.port if args.port is None else args.port)
    except CommandError as err:
        return fail(out, err)
    rt = runtime.build(config)
    runtime.configure(rt)
    port = sock.getsockname()[1]
    token = auth.new_token()
    app = create_app(rt, token=token, port=port, shiny_app=shiny_app())
    browser = config.server.open_browser and not args.no_browser
    return serve(app, sock, token=token, open_browser=browser, out=out)


def serve(app: ASGIApp, sock: socket.socket, *, token: str, open_browser: bool,
          out: Output) -> int:
    """Run `app` on the listening `sock` until Ctrl-C or SIGTERM, with the link printed and, if
    asked, the browser opened on the redirect file. Blocks; call it from the main thread."""
    port = sock.getsockname()[1]
    link = auth.auth_url(port, token)
    page = auth.write_redirect(link)
    atexit.register(shutil.rmtree, page.parent, ignore_errors=True)  # if `finally` never runs
    previous = signal.signal(signal.SIGTERM, _exit_on_sigterm)
    try:
        out.say(f"vid2sub is running on {HOST}, port {port}. Open the editor with this link "
                "(it works until vid2sub stops):")
        out.say(f"  {link}")
        out.say("Ctrl-C stops vid2sub.")
        if open_browser:
            threading.Thread(target=_open, args=(page, out), name="vid2sub-browser",
                             daemon=True).start()
        uvicorn.Server(uvicorn_config(app)).run(sockets=[sock])
    except KeyboardInterrupt:
        pass
    finally:
        signal.signal(signal.SIGTERM, previous)
        shutil.rmtree(page.parent, ignore_errors=True)
        sock.close()
    return exitcodes.OK


def uvicorn_config(app: ASGIApp) -> uvicorn.Config:
    """No access log (§6.8), no proxy headers believed (no proxy is in front of the engine, and
    X-Forwarded-Proto would change the scheme the guards compare Origin with), no Server header,
    and only warnings from uvicorn itself: the terminal shows vid2sub's lines."""
    return uvicorn.Config(app, access_log=False, proxy_headers=False, server_header=False,
                          log_level="warning", lifespan="on")


def _exit_on_sigterm(signum: int, frame: object) -> None:
    sys.exit(128 + signal.SIGTERM)


def _open(page: Path, out: Output) -> None:
    try:
        opened = webbrowser.open(page.as_uri())
    except webbrowser.Error:
        opened = False
    if not opened:
        out.warn("vid2sub couldn't open a browser: open the link above by hand")
