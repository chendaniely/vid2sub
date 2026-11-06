"""The app shell: `/auth`, `/healthz` and `/media/{token}`, with the Shiny app mounted at "/"
last, and the whole engine wrapped in the guards (spec §19.1, §6.1, §6.2).

As recordings' create_app does (packages/ui/src/recordings_ui/app.py at 8deb039): a FastAPI app
whose own routes win because the Shiny mount comes after them, and guards around everything,
the Shiny app and its websocket included. vid2sub adds the launch token, so the order is
`HostGuard(WriteGuard(TokenGuard(api)))`: a wrong name is refused before anything else, every
response carries the security headers, and only then is the cookie asked for. The one name
allowed is 127.0.0.1, which the engine binds and its link names; the cookie belongs to that name,
so a request to localhost could never sign in anyway. FastAPI's own pages (`/docs`, `/redoc`,
`/openapi.json`) are off: they load scripts from a CDN, and the engine makes no third-party
requests (§6.3). `/healthz` says only `{"ok": true}` (§6.1). The Shiny app is passed in, made by
its own module once `runtime.configure()` has run; the mount doesn't pass lifespan events on, so
anything that must happen at shutdown goes in this app's lifespan. Stopping the engine closes the
job queue, which cancels what waits and asks the running job to stop (§17.1).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.types import ASGIApp

from vid2sub.web import auth, media
from vid2sub.web.guards import HostGuard, WriteGuard
from vid2sub.web.runtime import Runtime

HOSTS = frozenset({"127.0.0.1"})  # the one name the engine answers to (spec §6.1, §6.2)


def create_app(rt: Runtime, *, token: str, port: int, shiny_app: ASGIApp) -> ASGIApp:
    @asynccontextmanager
    async def lifespan(_api: FastAPI) -> AsyncIterator[None]:
        yield
        await asyncio.to_thread(rt.queue.close)  # bounded (5 s), and off the event loop

    api = FastAPI(title="vid2sub", docs_url=None, redoc_url=None, openapi_url=None,
                  lifespan=lifespan)

    @api.get("/healthz")  # GET only: auth.OPEN_ROUTES opens exactly GET /healthz
    def healthz() -> dict:
        return {"ok": True}

    api.router.routes.extend([*auth.routes(token, port), media.route(rt.media)])
    api.mount("/", shiny_app)  # last, so the routes above win
    return HostGuard(WriteGuard(auth.TokenGuard(api, token=token, port=port), HOSTS), HOSTS)
