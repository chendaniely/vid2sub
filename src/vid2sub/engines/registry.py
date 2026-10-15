"""Engines built from `vid2sub.toml` model entries (spec §5.1, §9)."""

from __future__ import annotations

from vid2sub.config import Config, ConfigError
from vid2sub.engines.base import Engine
from vid2sub.engines.clients import KeyRing, RunPolicy
from vid2sub.engines.endpoint import EndpointEngine
from vid2sub.engines.qwen_mlx import QwenMLXEngine


def make_engine(name: str, config: Config, policy: RunPolicy, keys: KeyRing) -> Engine:
    entry = config.models.get(name)
    if entry is None:
        raise ConfigError(f"no model named {name!r} in vid2sub.toml")
    if entry.task != "transcribe":
        raise ConfigError(f"{name} is a translation model, not a transcription one")
    if entry.engine == "mlx-qwen3-asr":
        return QwenMLXEngine(name, entry)
    return EndpointEngine(name, entry, config, policy, keys)
