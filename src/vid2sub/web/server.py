"""The Shiny server for the React frontend: every output is JSON from a pure view function, and
every message goes through shinyreact's `send_message` (spec §19.1).

As recordings' shiny_app.py does (packages/ui/src/recordings_ui/shiny_app.py at 8deb039): the
server holds only reactive computation and returns JSON (the shinyreact-build-app skill), and
`ReactApp(...)` is called in this file. It reads the launch's parts from `runtime.current()`,
which `vid2sub serve` sets before importing this module. An unset input is a silent exception the
client treats as pending; an explicit null clears a pane (§19.1). Work that blocks (the endpoint
check here; opening, saving and retranslating later) runs off the event loop. Shiny's reconnect
stays off: nothing here calls `session.allow_reconnect`, so a tab whose engine restarted asks for
the new link instead of retrying (Review Focus 5).

The page is shinyreact's `page_react` (`www/ui.js` and `ui.css`), with `www/` also served at "/"
for the fonts, as ReactApp's own discovery mounts it. Its one change: Shiny 1.8.0 switches its busy
indicators on with an inline script, which the CSP's `script-src 'self'` blocks (§6.3), so the
same two lines are served as a file instead (checked in Chromium, spec §29). With that, the page
runs no inline script or style, and the CSP needs no `style-src` of its own.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Literal

import shiny
import shinyreact
from htmltools import HTMLDependency
from shiny import Inputs, Outputs, Session, reactive
from shinyreact import ReactApp, page_react, reactive_output

from vid2sub.config import Config
from vid2sub.engines import clients
from vid2sub.engines.base import EngineError
from vid2sub.engines.clients import KeyRing
from vid2sub.web import WWW, runtime, views

# By name: a test may load this file as a module of another name.
log = logging.getLogger("vid2sub.web.server")

STATUS_EVERY = 60  # seconds between checks of the local endpoints
# htmltools keeps the highest version of a dependency per name. Shiny's own version with a local
# label (1.8.0+vid2sub, which PEP 440 sorts above 1.8.0) makes this one replace Shiny's
# shiny-busy-indicators: its stylesheet, without the inline script in its head. The second
# dependency is that script, as a file. tests/test_web_server.py checks the rendered page, so a
# Shiny or htmltools upgrade that stops this winning fails there.
BUSY_INDICATORS = [
    HTMLDependency(
        "shiny-busy-indicators",
        f"{shiny.__version__}+vid2sub",
        source={"package": "shiny", "subdir": "www/shared/busy-indicators"},
        stylesheet={"href": "busy-indicators.css"},
        all_files=True,
    ),
    HTMLDependency(
        "vid2sub-busy-indicators",
        "1",
        source={"subdir": str(Path(__file__).parent / "static" / "busy")},
        script={"src": "busy-indicators.js"},
    ),
]


def page(request: Any) -> Any:
    """The page, built per request, so a rebuilt `ui.js` is fetched without a restart (its mtime
    is the dependency's version, as in ReactApp's own discovery)."""
    return page_react(*BUSY_INDICATORS, src_dir=WWW, title="vid2sub")


async def notice(session: Session, kind: Literal["info", "error"], text: str) -> None:
    """Tell the person something, as plain text (the frontend never renders it as markup)."""
    await shinyreact.send_message(session, "notice", {"kind": kind, "text": text})


def reachable(config: Config, keys: KeyRing) -> dict[str, bool]:
    """Whether each local endpoint answers its model list. Blocks on the network: run it off the
    event loop. Cloud endpoints are never contacted."""
    found = {}
    for name in views.local_endpoints(config):
        try:
            clients.list_models(name, config.endpoints[name], keys, timeout=3.0)
            found[name] = True
        except EngineError:
            found[name] = False
    return found


def server(input: Inputs, output: Outputs, session: Session) -> None:
    rt = runtime.current()

    @reactive_output
    def capabilities():
        return views.capabilities_view(rt.backend.capabilities())

    # The endpoint check runs as this session's extended task, off the event loop and outside
    # Shiny's reactive lock, now and every STATUS_EVERY seconds. The status keeps showing the last
    # result while the next check runs.
    found = reactive.value({})

    @reactive.extended_task
    async def check() -> dict[str, bool]:
        return await asyncio.to_thread(reachable, rt.config, rt.keys)

    @reactive.effect
    def _check_every_minute() -> None:
        reactive.invalidate_later(STATUS_EVERY)
        check.invoke()

    @reactive.effect
    def _keep_the_last_check() -> None:
        if check.status() == "success":
            found.set(check.result())

    @reactive_output
    def status():
        return views.status_view(rt.config, rt.keys, found(),
                                 ffmpeg=bool(rt.backend.tools.ffmpeg))


# bookmark_store="disable" is Shiny's default, said here so that no session state is written to
# disk or put in a URL (tests/test_web_server.py checks it).
app = ReactApp(server, ui=page, static_assets={"/": WWW}, bookmark_store="disable")
