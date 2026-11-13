"""The settings drawer: the engine's configuration shown read-only, typed keys, the session's
defaults and Copy settings (spec §19.2, §5.3, §5.4; S35).

What vid2sub.toml fixes at launch (endpoints, key variable names, models, `local` flags) is shown,
never changed: the UI only chooses among them, and a URL can't be typed in (§6.4). A key is shown
by presence only. A typed key is taken only for an endpoint declared with `allow_typed_key =
true`, into the engine's `KeyRing` (held in memory for this run, scoped to that endpoint, whose
origin is fixed at launch, and dropped on exit, §5.3); it is never written, logged, put in a
notice or sent back, and the drawer says only "key entered for this session". The session's
defaults are targets and formats, held in the runtime for this launch and shared by every tab,
as the jobs and typed keys are; never written (§5.4): jobs read them when each starts, and an
episode opened afterwards starts Save's "ASS too" from them. Cue rules are shown read-only, as
built (§12.2): nothing in vid2sub.toml can hold them yet, so the session can't change them
(Phase 2 Decision 21). Copy settings is the `[defaults]` table as TOML, the only part the
session changes, which `vid2sub.toml` loads back as it is; it never holds a key. The server runs
in Pages too (§21), so this module imports only the standard library and the pure packages at
its top; the Pages editor has no endpoints (its capabilities say `generate: false`), and the
server offers none of this there.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

from vid2sub.subs import langs, naming
from vid2sub.subs.rules import RULES

if TYPE_CHECKING:  # local only: the Pages bundle has neither (spec §21)
    from vid2sub.config import Config
    from vid2sub.config import Defaults as ConfigDefaults
    from vid2sub.engines.clients import KeyRing

FORMATS = ("srt", "ass")
MAX_KEY = 1024  # characters in a typed key
MODELS_SHOWN = 100  # model names an endpoint's Test lists, before "and N more"
MAX_MODEL_NAME = 200  # characters of each, as a hostile server could send anything
KEY_ENTERED = "key entered for this session"
KEY_FORGOTTEN = "the typed key is forgotten"
NO_TYPED_KEY = "that endpoint doesn't take a typed key: set allow_typed_key for it in vid2sub.toml"
BAD_KEY = "a key is letters, digits and punctuation, with no spaces: nothing was kept"
NO_ENDPOINT = "there's no such endpoint in vid2sub.toml"
BAD_TARGETS = "pick one or more of the targets vid2sub knows"
BAD_FORMATS = "subtitles are srt, and ass too when asked for"


class BadSetting(ValueError):
    """A change the drawer sent that isn't valid; the message echoes nothing it sent."""


class EndpointError(Exception):
    """An endpoint's Test failed: the reason and its fix (`hint`) are fit to show, with every key
    redacted. The local runtime makes it from the engine's error, which Pages can't import."""

    def __init__(self, message: str, hint: str = ""):
        super().__init__(message)
        self.hint = hint


@dataclass(frozen=True)
class Defaults:
    """The session's defaults: the target tracks a job translates to, and the formats it and Save
    write (SRT always)."""

    targets: tuple[str, ...] = ("en",)
    formats: tuple[str, ...] = ("srt",)

    @classmethod
    def from_config(cls, defaults: ConfigDefaults) -> Defaults:
        return cls(tuple(defaults.targets), ("srt", "ass") if "ass" in defaults.formats
                   else ("srt",))


class Session:
    """This launch's session settings, shared by every tab: the defaults, and word of any change
    (a default or a typed key) for each tab to show it. Changed only on the event loop; a job's
    thread reads `defaults()`, a frozen value replaced whole, so it never sees half a change."""

    def __init__(self, defaults: Defaults | None = None):
        self._defaults = defaults if defaults is not None else Defaults()
        self._listeners: list[Callable[[], None]] = []

    def defaults(self) -> Defaults:
        return self._defaults

    def set_defaults(self, defaults: Defaults) -> None:
        self._defaults = defaults
        self.changed()

    def on_change(self, fn: Callable[[], None]) -> Callable[[], None]:
        """Calls `fn` after each change; returns what stops it (a tab that closed)."""
        self._listeners.append(fn)
        return lambda: self._listeners.remove(fn) if fn in self._listeners else None

    def changed(self) -> None:
        for fn in list(self._listeners):
            fn()


def change_defaults(current: Defaults, request: object) -> Defaults:
    """The defaults after the drawer's change: `{"targets": [track, …]}` (known target tracks,
    each once) or `{"formats": ["srt"] | ["srt", "ass"]}`, with the request's count `n`."""
    if not isinstance(request, dict) or set(request) - {"n"} not in ({"targets"}, {"formats"}):
        raise BadSetting("change one default at a time")
    if "targets" in request:
        targets = request["targets"]
        if (not isinstance(targets, list) or not 0 < len(targets) <= len(naming.TRACKS)
                or len(set(map(str, targets))) != len(targets)
                or any(not isinstance(t, str) or t not in naming.TRACKS for t in targets)):
            raise BadSetting(BAD_TARGETS)
        return Defaults(tuple(targets), current.formats)
    formats = request["formats"]
    if formats not in (["srt"], ["srt", "ass"]):
        raise BadSetting(BAD_FORMATS)
    return Defaults(current.targets, tuple(formats))


def enter_key(config: Config, keys: KeyRing, request: object) -> str:
    """Keeps a typed key for this run (§5.3), or with `"key": ""` forgets it: `{"endpoint":
    name, "key": str, "n": int}`. Only for an endpoint that allows one; BadSetting otherwise,
    and for a key that isn't one line of printable ASCII, up to MAX_KEY characters. Returns what
    to tell the person, which never holds the key."""
    if not isinstance(request, dict):
        raise BadSetting(NO_TYPED_KEY)
    name, key = request.get("endpoint"), request.get("key")
    endpoint = config.endpoints.get(name) if isinstance(name, str) else None
    if endpoint is None or not endpoint.allow_typed_key:
        raise BadSetting(NO_TYPED_KEY)
    if key == "":
        keys.typed.pop(name, None)
        return KEY_FORGOTTEN
    if (not isinstance(key, str) or len(key) > MAX_KEY
            or any(not "\x21" <= ch <= "\x7e" for ch in key)):
        raise BadSetting(BAD_KEY)
    keys.typed[name] = key
    return KEY_ENTERED


def models_shown(found: list[str]) -> tuple[list[str], int]:
    """What a Test lists from a server's `/v1/models`: at most MODELS_SHOWN names, each cut to
    MAX_MODEL_NAME characters, and how many more there were. The page shows them as text."""
    names = [str(m)[:MAX_MODEL_NAME] for m in found]
    return names[:MODELS_SHOWN], max(0, len(names) - MODELS_SHOWN)


def settings_view(config: Config, keys: KeyRing, defaults: Defaults) -> dict[str, Any]:
    """The drawer's JSON: endpoints and models as vid2sub.toml has them, keys by presence only,
    the session's defaults with the targets to choose from, the cue rules, and Copy settings."""
    from vid2sub.config import is_local  # here: the Pages bundle has no vid2sub.config
    from vid2sub.web.views import local_endpoints, track_label

    local = set(local_endpoints(config))
    endpoints = []
    for name, ep in config.endpoints.items():
        typed = bool(ep.allow_typed_key and keys.typed.get(name))
        if ep.key_env or ep.allow_typed_key:
            key = "present" if keys.key_for(name, ep) else "missing"
        else:
            key = "none"
        endpoints.append({"name": name, "base_url": ep.base_url, "local": name in local,
                          "key_env": ep.key_env, "key": key,
                          "allow_typed_key": ep.allow_typed_key, "typed": typed})
    models = [{"name": name, "task": m.task, "catalog": m.catalog, "endpoint": m.endpoint,
               "engine": m.engine, "model": m.model, "local": is_local(m, config)}
              for name, m in config.models.items()]
    return {
        "endpoints": endpoints,
        "models": models,
        "defaults": {"targets": list(defaults.targets), "formats": list(defaults.formats)},
        "targets": [{"key": key, "label": track_label(key)} for key in naming.TRACKS],
        "rules": [{"lang": lang, "label": langs.LANGS[lang].name if lang in langs.LANGS
                   else lang, **{k: v for k, v in asdict(rules).items()
                                 if k in ("max_width", "max_lines", "cps", "min_ms", "max_ms")}}
                  for lang, rules in RULES.items()],
        "toml": settings_toml(config, defaults),
    }


def settings_toml(config: Config, defaults: Defaults) -> str:
    """Copy settings (§5.4): vid2sub.toml's `[defaults]` table with the session's targets and
    formats, and the file's other defaults as they are, so it can replace the table whole. It
    holds no key: no endpoint is in it. Strings are written as TOML basic strings, which JSON's
    escapes are (every control character escaped, non-ASCII as it is)."""
    lines = ["[defaults]", f"targets = {_array(defaults.targets)}",
             f"formats = {_array(defaults.formats)}"]
    if config.defaults.youtube_dir is not None:
        lines.append(f"youtube_dir = {json.dumps(config.defaults.youtube_dir, ensure_ascii=False)}")
    lines.append(f"cache_max_gb = {config.defaults.cache_max_gb!r}")
    return "\n".join(lines) + "\n"


def _array(values: tuple[str, ...]) -> str:
    return "[" + ", ".join(json.dumps(v, ensure_ascii=False) for v in values) + "]"
