"""`vid2sub.toml`: endpoints, models, privacy and defaults (spec §5).

The user writes it; vid2sub never does, and it refuses key values: only the names of environment
variables that hold keys (council, 2026-10-14: a file that might hold a key must not be named to
get past Dan's `.env` hooks). Unknown keys are refused at load, naming the key (an audio-router
lesson). A model is local only if it runs in-process, or says `local = true` and its endpoint's
host is in `privacy.local_hosts` (spec §7.2: llama-swap or Ollama can pass a request to a hosted
model on localhost, so the flag is per model). Keys travel over plain http only to this machine
or the tailnet. The key scan recognises common key prefixes and key-shaped table keys; it is a
backstop, not a guarantee. `privacy.local_hosts` is trust the user grants: any host listed there
counts as local.
"""

from __future__ import annotations

import os
import re
import tomllib
from collections.abc import Mapping
from importlib.resources import files
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from vid2sub.catalog import CATALOG
from vid2sub.security import host_of, key_transport_ok
from vid2sub.subs import naming

ENV_NAME = re.compile(r"^[A-Z_][A-Z0-9_]*$")
KEY_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]{0,31}$")
SECRET_PREFIXES = ("sk-", "sk_", "hf_", "ghp_", "gho_", "github_pat_", "xoxb-", "xoxp-",
                   "AKIA", "-----BEGIN")
HOLDS_NAMES = ("vid2sub.toml holds only the names of environment variables (key_env)")


class ConfigError(ValueError):
    pass


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Server(_M):
    port: int = Field(8765, ge=1, le=65535)
    open_browser: bool = True


class Privacy(_M):
    local_hosts: list[str] = Field(default_factory=lambda: ["127.0.0.1", "localhost", "::1"])


class Endpoint(_M):
    base_url: str
    key_env: str | None = None
    allow_typed_key: bool = False


class ModelEntry(_M):
    catalog: str | None = None
    endpoint: str | None = None
    engine: Literal["mlx-qwen3-asr"] | None = None
    model: str | None = None
    parser: Literal["whisper.cpp", "openai"] | None = None
    task: Literal["transcribe", "translate"] = "transcribe"
    local: bool = False
    concurrency: int = Field(1, ge=1, le=8)
    request_extra: dict[str, Any] = Field(default_factory=dict)
    api: Literal["completions", "responses"] | None = None


class Defaults(_M):
    targets: list[str] = Field(default_factory=lambda: ["en"])
    formats: list[Literal["srt", "ass"]] = Field(default_factory=lambda: ["srt"])
    youtube_dir: str | None = None
    cache_max_gb: float = Field(20, gt=0)


class Config(_M):
    server: Server = Field(default_factory=Server)
    privacy: Privacy = Field(default_factory=Privacy)
    endpoints: dict[str, Endpoint] = Field(default_factory=dict)
    models: dict[str, ModelEntry] = Field(default_factory=dict)
    defaults: Defaults = Field(default_factory=Defaults)


def _where(loc: tuple[Any, ...]) -> str:
    """Render a location from the file without echoing any table name that is not key-shaped."""
    out = ""
    for part in loc:
        if isinstance(part, int):
            out += f"[{part}]"
            continue
        name = str(part) if KEY_NAME.fullmatch(str(part)) else "<key>"
        out += f".{name}" if out else name
    return out or "the top level"


def _scan(obj: Any, loc: tuple[Any, ...] = ()) -> None:
    """Refuse any string, or table key, that looks like a key; names where, never what."""
    if isinstance(obj, str):
        if obj.startswith(SECRET_PREFIXES):
            raise ConfigError(f"{_where(loc)} looks like a key; {HOLDS_NAMES}")
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).startswith(SECRET_PREFIXES):
                raise ConfigError(f"a key in {_where(loc)} looks like a key; {HOLDS_NAMES}")
            _scan(v, (*loc, k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _scan(v, (*loc, i))


def _local_hosts(config: Config) -> set[str]:
    return {h.lower() for h in config.privacy.local_hosts}


def _validate(config: Config) -> Config:
    for name, ep in config.endpoints.items():
        label = _where((name,))
        parts = urlsplit(ep.base_url)
        if parts.scheme not in ("http", "https"):
            raise ConfigError(f"endpoints.{label}.base_url must start with http:// or https://")
        if parts.username is not None or parts.password is not None:
            raise ConfigError(f"endpoints.{label}.base_url must not contain a user name or "
                              "password; put the key in an environment variable named by key_env")
        if ep.key_env is not None and not ENV_NAME.fullmatch(ep.key_env):
            raise ConfigError(f"endpoints.{label}.key_env must be an environment variable name "
                              "like SPARK_API_KEY, never a key")
        if (ep.key_env or ep.allow_typed_key) and not key_transport_ok(ep.base_url):
            raise ConfigError(f"endpoints.{label}: a key goes over plain http only to this "
                              "machine or a Tailscale address; use https")
    for name, m in config.models.items():
        where = f"models.{_where((name,))}"
        if (m.endpoint is None) == (m.engine is None):
            raise ConfigError(f"{where} needs exactly one of `endpoint` or `engine`")
        if m.catalog is not None:
            if m.catalog not in CATALOG:
                raise ConfigError(f"{where}.catalog: not a catalog id "
                                  "(run `vid2sub models` to list them)")
            if CATALOG[m.catalog].task != m.task:
                raise ConfigError(f"{where}: {m.catalog} is a {CATALOG[m.catalog].task} model, "
                                  f"but task is {m.task}")
        if m.engine is not None:
            if m.task != "transcribe":
                raise ConfigError(f"{where}: in-process engines only transcribe")
            continue
        if m.endpoint not in config.endpoints:
            raise ConfigError(f"{where}.endpoint: no endpoint by that name in [endpoints]")
        if not m.model:
            raise ConfigError(f"{where}.model: the name the server knows the model by")
        if m.task == "transcribe" and m.parser is None:
            raise ConfigError(f"{where}.parser: whisper.cpp or openai")
        if m.local and host_of(config.endpoints[m.endpoint].base_url) not in _local_hosts(config):
            raise ConfigError(f"{where}.local: its endpoint's host isn't in privacy.local_hosts")
    for i, target in enumerate(config.defaults.targets):
        try:
            naming.target_track(target)
        except naming.UnknownTrack:
            raise ConfigError(f"defaults.targets[{i}]: not a known target track") from None
    return config


def is_local(entry: ModelEntry, config: Config) -> bool:
    if entry.engine is not None:
        return True
    ep = config.endpoints.get(entry.endpoint or "")
    return bool(entry.local and ep and host_of(ep.base_url) in _local_hosts(config))


def config_path(explicit: str | None = None,
                environ: Mapping[str, str] = os.environ) -> Path:
    if explicit:
        return Path(explicit).expanduser()
    if environ.get("VID2SUB_CONFIG"):
        return Path(environ["VID2SUB_CONFIG"]).expanduser()
    if os.name == "nt":
        appdata = environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(appdata) / "vid2sub" / "vid2sub.toml"
    xdg = environ.get("XDG_CONFIG_HOME") or ""
    # The XDG spec says a relative XDG_CONFIG_HOME is invalid, so it is ignored.
    base = Path(xdg) if xdg and Path(xdg).is_absolute() else Path.home() / ".config"
    return base / "vid2sub" / "vid2sub.toml"


def _from_pydantic(err: ValidationError) -> str:
    first = err.errors()[0]
    loc = tuple(first["loc"])
    if first["type"] == "extra_forbidden":
        if loc and KEY_NAME.fullmatch(str(loc[-1])):
            return f"{_where(loc)}: {first['msg']}"
        return f"an unknown key in {_where(loc[:-1])}: {first['msg']}"
    return f"{_where(loc)}: {first['msg']}"


def load_config(path: Path) -> Config:
    if not path.exists():
        return Config()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as err:
        raise ConfigError(f"{path.name}: {err}") from None
    _scan(data)
    try:
        config = Config.model_validate(data)
    except ValidationError as err:
        raise ConfigError(_from_pydantic(err)) from None
    return _validate(config)


STARTER = files("vid2sub").joinpath("example.toml").read_text(encoding="utf-8")
