"""The engine's running parts, made once per launch by `vid2sub serve` and read by the Shiny
server (spec §19.1), and the one way the server runs a call that blocks.

As recordings' runtime does: Shiny's app object is made when its module is imported, and its
server function runs once per browser session, so the server finds the backend, the job queue
and the media tokens here (`current()`), and `serve` calls `configure()` before it imports the
Shiny app. There is one of each per launch: the backend holds the open episodes, the queue holds
the jobs, which belong to the engine rather than a tab (spec §17.1), and the media tokens die
with the engine (the Phase 2 plan's Decision 1). Until the Jobs page gives the queue the
pipeline (S36), a job that somehow reaches it fails without running anything.

The server runs in Pages too (spec §3.3, §21), so this module imports nothing the Pages bundle
lacks at its top: `build()` imports the local parts (the backend, the queue, ffmpeg's tools, the
cache, the network client) when it runs, and the server reaches local-only work through the
`Runtime` (`reachable`). Every call that blocks goes through `blocking`, never a
thread or an executor of the server's own: a worker thread here, inline in Pyodide, which has no
threads (Task 14 round 14a, decided with the coordinator 2026-10-24).
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vid2sub.cache import Cache
    from vid2sub.config import Config
    from vid2sub.engines.clients import KeyRing
    from vid2sub.jobs import Queue
    from vid2sub.media.tools import Tools
    from vid2sub.pipeline import Event, InputResult
    from vid2sub.web.backend import LocalBackend
    from vid2sub.web.media import MediaTokens

INLINE = sys.platform == "emscripten"  # Pyodide: no threads, so a blocking call runs inline


async def blocking[**P, R](fn: Callable[P, R], /, *args: P.args, **kwargs: P.kwargs) -> R:
    """`fn(*args, **kwargs)` off the event loop, awaited: in a worker thread (`asyncio.to_thread`,
    which carries the caller's context, Shiny's session included), or inline where there are no
    threads (Pyodide)."""
    if INLINE:
        return fn(*args, **kwargs)
    return await asyncio.to_thread(fn, *args, **kwargs)


@dataclass(frozen=True)
class Runtime:
    backend: LocalBackend
    queue: Queue
    media: MediaTokens
    config: Config
    keys: KeyRing

    def reachable(self) -> dict[str, bool]:
        """Whether each local endpoint answers its model list. Blocks on the network: call it
        through `blocking`. Cloud endpoints are never contacted."""
        from vid2sub.engines import clients
        from vid2sub.engines.base import EngineError
        from vid2sub.web.views import local_endpoints

        found = {}
        for name in local_endpoints(self.config):
            try:
                clients.list_models(name, self.config.endpoints[name], self.keys, timeout=3.0)
                found[name] = True
            except EngineError:
                found[name] = False
        return found


_current: Runtime | None = None


def configure(rt: Runtime | None) -> None:
    """Make `rt` the launch's runtime; None forgets it (tests)."""
    global _current
    _current = rt


def current() -> Runtime:
    if _current is None:
        raise RuntimeError("vid2sub.web.runtime.configure() was not called")
    return _current


def build(config: Config, *, tools: Tools | None = None, keys: KeyRing | None = None,
          cache: Cache | None = None) -> Runtime:
    """One launch's parts: the tools found on PATH, the keys from the environment, and the cache
    that `[defaults] cache_max_gb` caps, unless the caller gives its own."""
    from vid2sub import cache as caching
    from vid2sub.engines.clients import KeyRing
    from vid2sub.jobs import Queue
    from vid2sub.media.tools import Tools
    from vid2sub.web.backend import LocalBackend
    from vid2sub.web.media import MediaTokens

    tools = tools if tools is not None else Tools.find()
    keys = keys if keys is not None else KeyRing()
    cache = cache if cache is not None else caching.from_config(config)
    return Runtime(backend=LocalBackend(config, tools, keys, cache), queue=Queue(_no_jobs),
                   media=MediaTokens(), config=config, keys=keys)


def _no_jobs(source: str, events: Event, cancelled: Callable[[], bool]) -> InputResult:
    raise RuntimeError("this engine has no job runner")
