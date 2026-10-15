"""The one place network clients are made and called (spec §6.4, §7.2; plan decision 11).

Only this module imports openai, httpx or chatlas (a test enforces it). Every client gets its
address and key passed explicitly, so the SDK never reads OPENAI_API_KEY or OPENAI_BASE_URL;
redirects are refused, so a 307 can't re-send audio or a key elsewhere; retries are vid2sub's own
(max_retries=0). A model that isn't local is used only when the run allows cloud models. Errors
become EngineErrors whose hints name the fix, with every key value redacted. A key goes only to
the endpoint it was declared with; a typed key only to an endpoint that allows one.
"""

from __future__ import annotations

import logging
import math
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import httpx
import openai
from chatlas import ChatOpenAI, ChatOpenAICompletions
from pydantic import BaseModel

from vid2sub.config import Config, Endpoint, ModelEntry, is_local
from vid2sub.engines.base import EngineError
from vid2sub.security import host_of, key_transport_ok, redact

QUIET = ("openai", "httpx", "httpcore", "chatlas")
REFUSAL_CODES = {"loading", "no_fit", "held_by_brake", "gate_down"}  # local-ai Phase 3


def quiet_libraries() -> None:
    for name in QUIET:
        logging.getLogger(name).setLevel(logging.WARNING)


@dataclass(frozen=True)
class RunPolicy:
    allow_cloud: bool = False


@dataclass
class KeyRing:
    typed: dict[str, str] = field(default_factory=dict)
    environ: Mapping[str, str] = field(default_factory=lambda: os.environ)

    def key_for(self, endpoint_name: str, endpoint: Endpoint) -> str | None:
        if endpoint.allow_typed_key and self.typed.get(endpoint_name):
            return self.typed[endpoint_name]
        if endpoint.key_env:
            return self.environ.get(endpoint.key_env) or None
        return None

    def secrets(self, config: Config) -> list[str]:
        values = list(self.typed.values())
        values += [self.environ.get(ep.key_env, "") for ep in config.endpoints.values()
                   if ep.key_env]
        return [v for v in values if v]


def check_allowed(name: str, entry: ModelEntry, config: Config, policy: RunPolicy) -> None:
    if not is_local(entry, config) and not policy.allow_cloud:
        raise EngineError("cloud_not_allowed",
                          f"{name} is a cloud model, and this run doesn't allow cloud models",
                          hint="add --allow-cloud to send audio or text to it")


def _require_safe_transport(ep: Endpoint) -> None:
    if not key_transport_ok(ep.base_url):
        raise EngineError("auth", "vid2sub won't send a key over plain http except to this "
                                  "machine or a Tailscale address",
                          hint="use https for this endpoint")


def _key(entry: ModelEntry, config: Config, keys: KeyRing) -> str:
    ep = config.endpoints[entry.endpoint]
    key = keys.key_for(entry.endpoint, ep)
    if ep.key_env and not key:
        raise EngineError("key_missing",
                          f"{ep.key_env} isn't set in the environment vid2sub started from",
                          hint=f"export {ep.key_env} in your shell (on Dan's Mac, ~/.secrets), "
                               "then start vid2sub again from that shell")
    if key:
        _require_safe_transport(ep)
    return key or "unused"


def _http(timeout: float) -> httpx.Client:
    return httpx.Client(follow_redirects=False, timeout=httpx.Timeout(timeout, connect=10.0))


def transcription_client(name: str, entry: ModelEntry, config: Config, policy: RunPolicy,
                         keys: KeyRing, *, timeout: float = 900) -> openai.OpenAI:
    check_allowed(name, entry, config, policy)
    ep = config.endpoints[entry.endpoint]
    return openai.OpenAI(api_key=_key(entry, config, keys), base_url=ep.base_url,
                         http_client=_http(timeout), max_retries=0)


def _json(response: Any) -> Any:
    try:
        return response.json()
    except Exception:  # noqa: BLE001 - any unreadable body is just "no JSON"
        return None


def _seconds(value: Any) -> float | None:
    """A finite, non-negative number of seconds, or None for anything else."""
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return None
    return seconds if math.isfinite(seconds) and seconds >= 0 else None


def _retry_after(response: Any) -> float | None:
    return _seconds(response.headers.get("retry-after"))


def map_error(err: Exception, *, key_env: str | None, secrets: list[str]) -> EngineError:
    message = redact(str(err), secrets)
    if isinstance(err, openai.APITimeoutError):
        return EngineError("server", "the server took too long to answer",
                           hint="it may be busy; vid2sub retries twice")
    if isinstance(err, openai.APIConnectionError):
        return EngineError("connection", "couldn't reach the server",
                           hint="is it running? For the Spark: is `make tunnel` running?")
    if isinstance(err, openai.AuthenticationError):
        hint = (f"{key_env} is wrong, or isn't exported in the shell vid2sub started from; "
                "restart vid2sub from one that exports it") if key_env else \
            "this server needs a key: set key_env for its endpoint in vid2sub.toml"
        return EngineError("auth", "the server refused the key (401)", hint=hint)
    if isinstance(err, openai.APIStatusError):
        status = err.status_code
        body = _json(err.response)
        error = body.get("error") if isinstance(body, dict) else None
        code = error.get("code") if isinstance(error, dict) else None
        if code in REFUSAL_CODES:
            return EngineError("refused", f"the Spark refused the request: {code}",
                               hint="local-ai's `make status` says why",
                               retry_after=_seconds(error.get("retry_after_s")))
        if 300 <= status < 400:
            return EngineError("bad_response",
                               f"the server redirected ({status}); vid2sub never follows a "
                               "redirect with a key", hint="set base_url to the final address")
        if status == 413:
            return EngineError("too_large", "the chunk was too large for this server (413)",
                               hint="this server's upload limit is below vid2sub's chunk size")
        if status == 429:
            retry = _retry_after(err.response)
            return EngineError("refused", "the server is busy (429)",
                               retry_after=retry if retry is not None else 30.0)
        if status >= 500:
            return EngineError("server", f"the server failed ({status})",
                               hint="vid2sub retries twice")
        return EngineError("bad_response", f"the server answered {status}: {message[:200]}")
    return EngineError("bad_response", message[:200])


def call_transcription(client: openai.OpenAI, *, key_env: str | None, secrets: list[str],
                       file: tuple[str, bytes, str], **params: Any
                       ) -> tuple[dict, Mapping[str, str]]:
    try:
        raw = client.audio.transcriptions.with_raw_response.create(file=file, **params)
    except openai.OpenAIError as err:
        raise map_error(err, key_env=key_env, secrets=secrets) from None
    response = raw.http_response
    try:
        data = response.json()
    except ValueError:
        raise EngineError("bad_response", "the server's answer wasn't JSON") from None
    if not isinstance(data, dict):
        raise EngineError("bad_response", "the server's answer wasn't a JSON object")
    return data, response.headers


def list_models(endpoint_name: str, endpoint: Endpoint, keys: KeyRing, *,
                timeout: float = 5.0) -> list[str]:
    key = keys.key_for(endpoint_name, endpoint)
    if key:
        _require_safe_transport(endpoint)
    client = openai.OpenAI(api_key=key or "unused", base_url=endpoint.base_url,
                           http_client=_http(timeout), max_retries=0)
    try:
        return [m.id for m in client.models.list()]
    except openai.OpenAIError as err:
        raise map_error(err, key_env=endpoint.key_env, secrets=[key] if key else []) from None
    finally:
        client.close()


def chat(name: str, entry: ModelEntry, config: Config, policy: RunPolicy, keys: KeyRing, *,
         system_prompt: str, timeout: float = 300):
    check_allowed(name, entry, config, policy)
    ep = config.endpoints[entry.endpoint]
    api = entry.api or ("responses" if host_of(ep.base_url) == "api.openai.com"
                        else "completions")
    factory = ChatOpenAI if api == "responses" else ChatOpenAICompletions
    return factory(model=entry.model, base_url=ep.base_url, api_key=_key(entry, config, keys),
                   system_prompt=system_prompt,
                   kwargs={"http_client": _http(timeout), "max_retries": 0})


def call_structured(chat_obj: Any, prompt: str, data_model: type[BaseModel], *,
                    extra_body: dict | None, key_env: str | None,
                    secrets: list[str]) -> BaseModel:
    kwargs = {"extra_body": extra_body} if extra_body else None
    try:
        return chat_obj.chat_structured(prompt, data_model=data_model, echo="none",
                                        kwargs=kwargs)
    except openai.OpenAIError as err:
        raise map_error(err, key_env=key_env, secrets=secrets) from None
