"""The engine's running parts, made once per launch by `vid2sub serve` and read by the Shiny
server (spec §19.1).

As recordings' runtime does: Shiny's app object is made when its module is imported, and its
server function runs once per browser session, so the server finds the backend, the job queue
and the media tokens here (`current()`), and `serve` calls `configure()` before it imports the
Shiny app. There is one of each per launch: the backend holds the open episodes, the queue holds
the jobs, which belong to the engine rather than a tab (spec §17.1), and the media tokens die
with the engine (the Phase 2 plan's Decision 1). Until the Jobs page gives the queue the
pipeline (S36), a job that somehow reaches it fails without running anything.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from vid2sub import cache as caching
from vid2sub.cache import Cache
from vid2sub.config import Config
from vid2sub.engines.clients import KeyRing
from vid2sub.jobs import Queue
from vid2sub.media.tools import Tools
from vid2sub.pipeline import Event, InputResult
from vid2sub.web.backend import LocalBackend
from vid2sub.web.media import MediaTokens


@dataclass(frozen=True)
class Runtime:
    backend: LocalBackend
    queue: Queue
    media: MediaTokens
    config: Config
    keys: KeyRing


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
    tools = tools if tools is not None else Tools.find()
    keys = keys if keys is not None else KeyRing()
    cache = cache if cache is not None else caching.from_config(config)
    return Runtime(backend=LocalBackend(config, tools, keys, cache), queue=Queue(_no_jobs),
                   media=MediaTokens(), config=config, keys=keys)


def _no_jobs(source: str, events: Event, cancelled: Callable[[], bool]) -> InputResult:
    raise RuntimeError("this engine has no job runner")
