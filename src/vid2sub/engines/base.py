"""The transcription engine protocol (spec §9.1).

Every engine takes one chunk and returns a ParsedChunk in vid2sub's word shape. Endpoints upload
the chunk as FLAC named `chunk-NNNN.flac` (spec §7.3); in-process engines take the samples. Errors
are EngineErrors with a kind and a hint that names the fix: a connection error or a Spark refusal
pauses the run so it can resume; a server error is retried; anything else fails the input.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal, Protocol

import numpy as np

from vid2sub.media.decode import SAMPLES_PER_MS, to_float
from vid2sub.parse import ParsedChunk

ErrorKind = Literal["connection", "auth", "too_large", "server", "refused", "bad_response",
                    "unavailable", "cloud_not_allowed", "key_missing"]


class EngineError(RuntimeError):
    def __init__(self, kind: ErrorKind, message: str, *, hint: str = "",
                 retry_after: float | None = None):
        super().__init__(message)
        self.kind = kind
        self.hint = hint
        self.retry_after = retry_after


@dataclass(frozen=True)
class ModelStamp:
    engine: str
    model: str
    revision: str = "unknown"

    @property
    def label(self) -> str:
        return f"{self.model.split('/')[-1]}@{self.revision[:12]}"


@dataclass
class Chunk:
    index: int
    samples: np.ndarray  # int16, 16 kHz mono
    encode: Callable[[np.ndarray], bytes]
    _flac: bytes | None = field(default=None, repr=False)

    def flac(self) -> bytes:
        if self._flac is None:
            self._flac = self.encode(self.samples)
        return self._flac

    @property
    def float32(self) -> np.ndarray:
        return to_float(self.samples)

    @property
    def duration_ms(self) -> int:
        return len(self.samples) // SAMPLES_PER_MS

    @property
    def upload_name(self) -> str:
        return f"chunk-{self.index:04d}.flac"


@dataclass(frozen=True)
class ChunkResult:
    parsed: ParsedChunk
    answered_model: str | None = None


class Engine(Protocol):
    name: str
    max_chunk_s: float
    supports_prompt: bool

    def transcribe(self, chunk: Chunk, *, language: str | None, prompt: str) -> ChunkResult: ...

    def detect_language(self, chunk: Chunk) -> dict[str, float]: ...

    def stamp(self) -> ModelStamp: ...

    def close(self) -> None: ...
