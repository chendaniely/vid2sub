"""The engine's running parts, made once per launch by `vid2sub serve` and read by the Shiny
server (spec §19.1), and the one way the server runs a call that blocks.

As recordings' runtime does: Shiny's app object is made when its module is imported, and its
server function runs once per browser session, so the server finds the backend, the job queue
and the media tokens here (`current()`), and `serve` calls `configure()` before it imports the
Shiny app. There is one of each per launch: the backend holds the open episodes, the queue holds
the jobs, which belong to the engine rather than a tab (spec §17.1), the media tokens die
with the engine (the Phase 2 plan's Decision 1), and the session's settings (`session`: the
defaults the drawer changes, never written, §5.4) and typed keys (in `keys`) are this launch's,
shared by every tab and gone when it exits. Until the Jobs page gives the queue the
pipeline (S36), a job that somehow reaches it fails without running anything.

The server runs in Pages too (spec §3.3, §21), so this module imports nothing the Pages bundle
lacks at its top: `build()` imports the local parts (the backend, the queue, ffmpeg's tools, the
cache, the network client) when it runs, and the server reaches local-only work through the
`Runtime` (`reachable`, `media_for`, `retranslate`, `endpoint_models`). Every call that blocks
goes through `blocking`, never a thread or an executor of the server's own: a worker thread
here, inline in Pyodide, which has no threads (Task 14 round 14a, decided with the coordinator
2026-10-24).
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from vid2sub.web.settings import Defaults, EndpointError, Session

if TYPE_CHECKING:
    from vid2sub.cache import Cache
    from vid2sub.config import Config
    from vid2sub.engines.clients import KeyRing
    from vid2sub.jobs import Queue
    from vid2sub.media.tools import Tools
    from vid2sub.pipeline import Event, InputResult
    from vid2sub.web.backend import LocalBackend
    from vid2sub.web.episode import Episode
    from vid2sub.web.media import MediaTokens

ALLOW_CLOUD = "tick Allow cloud models, then retranslate again"
TEST_TIMEOUT = 10.0  # seconds a settings drawer Test waits for an endpoint's model list
PLAYBACK_TIMEOUT = 3600.0  # seconds: a two-hour episode's audio, read from a slow network share
INLINE = sys.platform == "emscripten"  # Pyodide: no threads, so a blocking call runs inline


def _editor_words(hint: str) -> str:
    """The catalog's reasons in a "no usable translation model" hint name the CLI's flags
    (`catalog.suggest`); the editor has no `--model` and no `--allow-cloud`, but a box (Task 7
    re-review, M2). The CLI's hints for a timeout or a 5xx say "vid2sub retries twice"; the
    editor never retries, so those words go, and a hint they leave empty is "retranslate
    again"; one that was empty stays so (Task 17's Spec review, I-3; its re-review, N-3)."""
    words = (hint.replace("; choose it with --model", "")
             .replace("needs --allow-cloud", "needs Allow cloud models ticked")
             .replace("; vid2sub retries twice", "").replace("vid2sub retries twice", ""))
    return words.strip() or ("retranslate again" if hint else "")


async def blocking[**P, R](fn: Callable[P, R], /, *args: P.args, **kwargs: P.kwargs) -> R:
    """`fn(*args, **kwargs)` off the event loop, awaited: in a worker thread (`asyncio.to_thread`,
    which carries the caller's context, Shiny's session included), or inline where there are no
    threads (Pyodide)."""
    if INLINE:
        return fn(*args, **kwargs)
    return await asyncio.to_thread(fn, *args, **kwargs)


@dataclass(frozen=True)
class Media:
    """What the player plays an episode by: `/media/<token>` URLs, or a problem fit to show."""

    video_url: str | None
    audio_url: str | None
    problem: str | None = None


@dataclass(frozen=True)
class Runtime:
    backend: LocalBackend
    queue: Queue
    media: MediaTokens
    config: Config
    keys: KeyRing
    session: Session = field(default_factory=Session)  # this launch's settings (spec §5.4)

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

    def retranslate(self, ep: Episode, track: str, *, ids: Sequence[str] | None,
                    allow_cloud: bool, on_batch: Callable[[int, int], None] | None = None
                    ) -> Episode:
        """The backend's retranslate, with the engine's errors (`EngineError`, and
        `TranslationFailed` for an answer in the wrong shape) made the pure `RetranslateError`,
        message and hint, so the server catches it without importing them (Pages has neither).
        `EditError`, `OpenError` and `GlossaryError` pass through: they are pure already. Blocks
        on the model's server: call it through `blocking`; `on_batch` runs on that thread. A
        cloud model this call doesn't allow says to tick the editor's box (spec §7.2)."""
        from vid2sub.engines.base import EngineError
        from vid2sub.translate.run import TranslationFailed
        from vid2sub.web.episode import RetranslateError

        try:
            return self.backend.retranslate(ep, track, ids=ids, allow_cloud=allow_cloud,
                                            on_batch=on_batch)
        except EngineError as err:  # the CLI's hint names a flag; the editor has a box
            hint = ALLOW_CLOUD if err.kind == "cloud_not_allowed" else _editor_words(err.hint)
            raise RetranslateError(str(err), hint) from None
        except TranslationFailed as err:
            raise RetranslateError(str(err), "retranslate again, or pick fewer cues") from None

    def endpoint_models(self, name: str) -> list[str]:
        """The models endpoint `name` serves, from its `/v1/models` (the settings drawer's
        Test), asked through the one client factory, only at the endpoint's own origin, with
        its key and no redirect followed (§6.4). Any endpoint, cloud ones too: the person asked,
        and a model list carries nothing of theirs. EndpointError, with every key redacted, when
        it fails. Blocks on the network: call it through `blocking`."""
        from vid2sub.engines import clients
        from vid2sub.engines.base import EngineError
        from vid2sub.security import redact

        try:
            return clients.list_models(name, self.config.endpoints[name], self.keys,
                                       timeout=TEST_TIMEOUT)
        except EngineError as err:
            values = self.keys.secrets(self.config)
            raise EndpointError(redact(str(err), values), redact(err.hint, values)) from None

    def media_for(self, ep: Episode, *, audio_only: bool = False) -> Media:
        """The video by a media token when the browser can play its audio; else, or with
        `audio_only` (the browser said it can't play the video, spec §8.2), the playback audio
        (spec §8.8; Decision 2), made into the cache under the video's quick hash the first time,
        which blocks on ffmpeg: call it through `blocking`. Tokens are owned by the episode's id,
        so closing it revokes them."""
        from vid2sub.media.preview import playback_audio
        from vid2sub.media.tools import ToolFailed, ToolMissing

        if ep.playable_audio and not audio_only:
            try:
                return Media(f"/media/{self.media.issue(ep.video, owner=ep.id)}", None)
            except ValueError as err:  # never the path: issue's messages name none
                return Media(None, None, f"the browser can't be given this video: {err}")
        try:
            audio = playback_audio(ep.video, key=ep.header.video.quick_sha256,
                                   audio_index=ep.audio_index, tools=self.backend.tools,
                                   cache=self.backend.cache, timeout=PLAYBACK_TIMEOUT)
            return Media(None, f"/media/{self.media.issue(audio, owner=ep.id)}")
        except ToolMissing as err:
            return Media(None, None, f"the browser can't play this video's audio, and {err}")
        except (ToolFailed, OSError, ValueError):
            return Media(None, None, "the browser can't play this video's audio, and ffmpeg "
                         "couldn't make a copy it can play")


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
                   media=MediaTokens(), config=config, keys=keys,
                   session=Session(Defaults.from_config(config.defaults)))


def _no_jobs(source: str, events: Event, cancelled: Callable[[], bool]) -> InputResult:
    raise RuntimeError("this engine has no job runner")
