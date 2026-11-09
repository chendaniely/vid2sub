"""The Shiny server for the React frontend: every output is JSON from a pure view function, and
every message goes through shinyreact's `send_message` (spec §19.1).

As recordings' shiny_app.py does (packages/ui/src/recordings_ui/shiny_app.py at 8deb039): the
server holds only reactive computation and returns JSON (the shinyreact-build-app skill), and
`ReactApp(...)` is called in this file. It reads the launch's parts from `runtime.current()`,
which `vid2sub serve` sets before importing this module. An unset input is a silent exception the
client treats as pending; an explicit null clears a pane (§19.1). Work that blocks (the endpoint
check here; opening, saving and retranslating later) runs off the event loop, through
`runtime.blocking` only. The server runs in Pages too (spec §3.3, §21), so this module imports,
at its top, only the pure packages, shiny, shinyreact, htmltools, pydantic and
`vid2sub.web.{episode, views, runtime, ops}`, and reaches local-only work through the configured
`Runtime` (Task 14 round 14a; `tests/test_pages_imports.py`). Shiny's reconnect
stays off: nothing here calls `session.allow_reconnect`, so a tab whose engine restarted asks for
the new link instead of retrying (Review Focus 5).

The editor (spec §20): each tab holds at most one open episode, in an `Editor`. Every call that
changes it (open here; edits, Save and picks later) runs one at a time, in the order the tab sent
them, in a task of the tab's own that holds no reactive lock while it waits on the disk or ffmpeg,
so a slow open never freezes another tab and no edit is lost to a Save running at the same time.
The backend returns a new frozen `Episode` each time, which the editor sets as the reactive value
the `episode` output reads. The player gets the video by a media token, or the playback audio
when the browser can't play the video's audio (Decision 2) or, as the page reports from
canPlayType and the video's own errors, the video itself (`playback`, spec §8.2, §8.8); its
tokens are revoked with the episode when the tab opens another or closes: the mount passes no
lifespan events on, so that happens in `session.on_ended`. Requests come from the browser, so
they are checked before use and never echoed (§6.3, §6.8).

The page is shinyreact's `page_react` (`www/ui.js` and `ui.css`), with `www/` also served at "/"
for the fonts, as ReactApp's own discovery mounts it. Its one change: Shiny 1.8.0 switches its busy
indicators on with an inline script, which the CSP's `script-src 'self'` blocks (§6.3), so the
same two lines are served as a file instead (checked in Chromium, spec §29). With that, the page
runs no inline script or style, and the CSP needs no `style-src` of its own.
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from pathlib import Path
from typing import Any, Literal

import shiny
import shinyreact
from htmltools import HTMLDependency
from shiny import Inputs, Outputs, Session, reactive
from shinyreact import ReactApp, page_react, reactive_output

from vid2sub.web import WWW, runtime, views
from vid2sub.web.episode import Episode, OpenError

# By name: a test may load this file as a module of another name.
log = logging.getLogger("vid2sub.web.server")

STATUS_EVERY = 60  # seconds between checks of the local endpoints
MAX_PATH = 4096  # characters in a typed path
TYPE_A_PATH = "type the video's full path to open it"
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


def page() -> Any:
    """The page, rendered once, when this module is imported. A per-request render makes htmltools
    create and remove a throwaway directory on every GET (`package_dir`), and spec §6.2 says no GET
    writes anything. The cost: a rebuilt `ui.js` (its mtime is the dependency's version) needs a
    restart, and until then it is served at the old URL, so a browser may keep its cached copy."""
    return page_react(*BUSY_INDICATORS, src_dir=WWW, title="vid2sub")


async def notice(session: Session, kind: Literal["info", "error"], text: str) -> None:
    """Tell the person something, as plain text (the frontend never renders it as markup)."""
    await shinyreact.send_message(session, "notice", {"kind": kind, "text": text})


class Editor:
    """One tab's episode. `submit` queues a request; one task per tab runs them in order, each to
    the end before the next, and publishes the episode the backend returned."""

    def __init__(self, rt: runtime.Runtime, session: Session):
        self.rt = rt
        self.session = session
        self.ep: Episode | None = None  # the truth; only the worker changes it
        self.media = runtime.Media(None, None)
        self.shown: reactive.Value[tuple[Episode, runtime.Media] | None] = reactive.value(None)
        self.busy: reactive.Value[str | None] = reactive.value(None)
        self._todo: deque[tuple[str, object]] = deque()
        self._worker: asyncio.Task | None = None
        self._ended = False

    def submit(self, kind: str, request: object) -> None:
        if self._ended:
            return
        self._todo.append((kind, request))
        if self._worker is None or self._worker.done():
            self._worker = asyncio.create_task(self._drain())

    async def end(self) -> None:
        """The tab closed: drop what waits, and close the episode once the running call ends."""
        self._ended = True
        self._todo.clear()
        if self._worker is None or self._worker.done():
            self._close(self.ep)

    async def _drain(self) -> None:
        while self._todo and not self._ended:
            kind, request = self._todo.popleft()
            try:
                await getattr(self, f"_{kind}")(request)
            except Exception as err:  # noqa: BLE001 - one failing must not stop the queue
                # The type only: a message or traceback can carry a path (spec §6.8).
                log.error("the editor's %s failed: %s", kind, type(err).__name__)
                await notice(self.session, "error", f"something went wrong ({kind}); see the log")
                await self._set_busy(None)
        if self._ended:
            self._close(self.ep)

    async def _open(self, request: object) -> None:
        path = request.get("path") if isinstance(request, dict) else None
        if not isinstance(path, str) or not path.strip() or len(path) > MAX_PATH:
            await notice(self.session, "error", TYPE_A_PATH)
            return
        await self._set_busy("opening")
        try:
            ep = await runtime.blocking(self.rt.backend.open, path)
        except OpenError as err:
            await self._set_busy(None)
            await notice(self.session, "error", str(err))
            return
        media = await runtime.blocking(self.rt.media_for, ep)
        old, self.ep, self.media = self.ep, ep, media
        if old is not None:
            self._close(old)
        await self._publish(busy=None)
        if media.problem:
            await notice(self.session, "error", media.problem)

    async def _playback(self, request: object) -> None:
        """The page found the browser can't play the video (spec §8.2: canPlayType, or the
        <video>'s error), so the video's token goes and the playback audio plays (§8.8)."""
        ep = self._named(request)
        if ep is None or self.media.video_url is None:  # nothing open, or the audio already
            return
        await self._set_busy("playback")
        self.rt.media.revoke_owner(ep.id)
        self.media = await runtime.blocking(self.rt.media_for, ep, audio_only=True)
        await self._publish(busy=None)
        if self.media.problem:
            await notice(self.session, "error", self.media.problem)

    def _named(self, request: object) -> Episode | None:
        """The open episode, when the request names it."""
        if (isinstance(request, dict) and self.ep is not None
                and request.get("episode") == self.ep.id):
            return self.ep
        return None

    def _close(self, ep: Episode | None) -> None:
        if ep is not None:
            self.rt.backend.close(ep.id)
            self.rt.media.revoke_owner(ep.id)

    async def _publish(self, *, busy: str | None) -> None:
        """Shows the episode as it is now: the reactive values change under Shiny's lock, and the
        flush sends the outputs, as an extended task's result does."""
        async with reactive.lock():
            self.shown.set(None if self.ep is None else (self.ep, self.media))
            self.busy.set(busy)
            await reactive.flush()

    async def _set_busy(self, busy: str | None) -> None:
        async with reactive.lock():
            self.busy.set(busy)
            await reactive.flush()


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
        return await runtime.blocking(rt.reachable)

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

    editor = Editor(rt, session)
    session.on_ended(editor.end)

    @reactive.effect
    @reactive.event(input.open)
    def _open() -> None:
        editor.submit("open", input.open())

    @reactive.effect
    @reactive.event(input.playback)
    def _playback() -> None:
        editor.submit("playback", input.playback())

    @reactive_output
    def episode():
        shown = editor.shown()
        if shown is None:
            return None  # an explicit null: nothing is open
        ep, media = shown
        return views.episode_view(ep, video_url=media.video_url, audio_url=media.audio_url)

    @reactive_output
    def busy():
        return editor.busy()


# bookmark_store="disable" is Shiny's default, said here so that no session state is written to
# disk or put in a URL (tests/test_web_server.py checks it).
app = ReactApp(server, ui=page(), static_assets={"/": WWW}, bookmark_store="disable")
app.sanitize_errors = True  # an output's error text may hold a key or a path (spec §6.8)
