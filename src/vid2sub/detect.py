"""Detecting the language from samples of speech, and finding what can run now (spec §10).

Three ~20 s windows are taken at 10%, 50% and 80% of the speech found (skipping theme songs and
intros); each is language-identified and the votes give a language, a confidence and a "mixed"
flag. Whisper often labels Cantonese as `zh`, so a Whisper `zh` is ambiguous and needs the user
(or `--from`). The best detector is Qwen3-ASR (97.9% language-ID accuracy in Qwen's benchmark),
then a local Whisper, then a cloud one if the run allows it. Candidates say which configured
models can run right now, and why the others can't: local endpoints are asked for their model
list; cloud ones are only checked for a key, never contacted.
"""

from __future__ import annotations

import importlib.util
import platform
import sys
from collections import Counter, defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np

from vid2sub.catalog import CATALOG, Candidate
from vid2sub.config import Config, is_local
from vid2sub.engines import clients
from vid2sub.engines.base import Chunk, Engine, EngineError
from vid2sub.media.decode import SAMPLES_PER_MS

WHISPER_ENGINES = frozenset({"whisper.cpp", "openai", "faster-whisper"})
CONFIDENT = 0.6


@dataclass(frozen=True)
class Detection:
    language: str | None
    confidence: float
    votes: tuple[str | None, ...]
    ambiguous_zh_yue: bool
    mixed: bool
    detector: str

    @property
    def uncertain(self) -> bool:
        return (self.language is None or self.confidence < CONFIDENT or self.ambiguous_zh_yue
                or self.mixed)

    def reason(self) -> str:
        if self.language is None:
            return "no language could be detected"
        if self.ambiguous_zh_yue:
            return "Whisper heard Chinese: is it Mandarin or Cantonese?"
        if self.mixed:
            return "the samples disagree: " + ", ".join(v or "?" for v in self.votes)
        if self.confidence < CONFIDENT:
            return f"only {self.confidence:.0%} sure it's {self.language}"
        return ""


def sample_windows(speech: Sequence[tuple[int, int]], duration_ms: int, *,
                   positions: Sequence[float] = (0.1, 0.5, 0.8),
                   window_ms: int = 20_000) -> list[tuple[int, int]]:
    total = sum(e - s for s, e in speech)
    if total == 0:
        return []
    windows = []
    for position in positions:
        target, acc, t = position * total, 0, speech[-1][0]
        for s, e in sorted(speech):
            if acc + (e - s) >= target:
                t = s + int(target - acc)
                break
            acc += e - s
        start = max(0, min(t, duration_ms - window_ms))
        windows.append((start, min(duration_ms, start + window_ms)))
    return windows


def detect(engine: Engine, samples: np.ndarray, speech: Sequence[tuple[int, int]],
           duration_ms: int, *, encode: Callable[[np.ndarray], bytes]) -> Detection:
    votes: list[str | None] = []
    totals: dict[str, float] = defaultdict(float)
    for i, (s, e) in enumerate(sample_windows(speech, duration_ms)):
        chunk = Chunk(9000 + i, samples[s * SAMPLES_PER_MS:e * SAMPLES_PER_MS], encode)
        probs = engine.detect_language(chunk)
        if not probs:
            votes.append(None)
            continue
        votes.append(max(probs, key=probs.__getitem__))
        for lang, p in probs.items():
            totals[lang] += p
    counted = Counter(v for v in votes if v)
    if not counted:
        return Detection(None, 0.0, tuple(votes), False, False, engine.name)
    language = counted.most_common(1)[0][0]
    return Detection(language, round(totals[language] / len(votes), 3), tuple(votes),
                     engine.name in WHISPER_ENGINES and language == "zh", len(counted) > 1,
                     engine.name)


def mlx_available() -> bool:
    return (sys.platform == "darwin" and platform.machine() == "arm64"
            and importlib.util.find_spec("mlx_qwen3_asr") is not None)


def candidates(config: Config, keys: clients.KeyRing, *,
               probe_endpoints: bool = True) -> list[Candidate]:
    served: dict[str, tuple[bool, str, set[str]]] = {}
    out: list[Candidate] = []
    for name, m in config.models.items():
        if m.engine == "mlx-qwen3-asr":
            ok = mlx_available()
            out.append(Candidate(name, m.catalog, "in-process", ok,
                                 "" if ok else "install vid2sub[mac] on an Apple Silicon Mac"))
            continue
        ep = config.endpoints[m.endpoint]
        if not is_local(m, config):
            ok = bool(keys.key_for(m.endpoint, ep)) or not ep.key_env
            out.append(Candidate(name, m.catalog, "endpoint", ok,
                                 "" if ok else f"{ep.key_env} isn't set", cloud=True))
            continue
        if not probe_endpoints:
            out.append(Candidate(name, m.catalog, "endpoint", True))
            continue
        if m.endpoint not in served:
            try:
                served[m.endpoint] = (True, "", set(clients.list_models(m.endpoint, ep, keys)))
            except EngineError as err:
                reason = f"{err} ({err.hint})" if err.hint else str(err)
                served[m.endpoint] = (False, reason, set())
        ok, reason, ids = served[m.endpoint]
        if ok and ids and m.model not in ids:
            ok, reason = False, f"the server doesn't list {m.model}"
        out.append(Candidate(name, m.catalog, "endpoint", ok, reason))
    return out


def _is_cloud(c: Candidate) -> bool:
    return c.cloud or CATALOG[c.catalog].cloud


def choose_detector(cands: Sequence[Candidate], *, allow_cloud: bool) -> str | None:
    usable = [c for c in cands if c.available and c.catalog in CATALOG
              and CATALOG[c.catalog].task == "transcribe"
              and (allow_cloud or not _is_cloud(c))]
    for family in ("qwen3-asr", "whisper"):
        found = sorted((c for c in usable if CATALOG[c.catalog].family == family),
                       key=lambda c: (_is_cloud(c), 0 if c.kind == "endpoint" else 1))
        if found:
            return found[0].name
    return None
