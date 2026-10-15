"""Qwen3-ASR with its forced aligner, in-process on Apple Silicon (spec §9.4).

Through mlx-qwen3-asr (the `mac` extra, macOS 14+). The best model here for Mandarin and
Cantonese. Its aligner works in 180 s pieces, so chunks are at most 180 s. Qwen3-ASR takes a
vocabulary context (council correction, 2026-10-14), so the glossary goes in as `context`. The
import is lazy: mlx imports take tens of seconds (an audio-router lesson).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from vid2sub.catalog import CATALOG
from vid2sub.config import ModelEntry
from vid2sub.engines.base import Chunk, ChunkResult, EngineError, ModelStamp
from vid2sub.parse.qwen import parse_qwen
from vid2sub.subs import langs

SAMPLE_RATE = 16_000


def hf_revision(repo: str) -> str:
    """The cached snapshot's hash, so a model update changes the version.

    Copied from audio-router's model_revision (stages/transcribe.py at 64612df)."""
    try:
        from huggingface_hub import snapshot_download

        path = Path(snapshot_download(repo, local_files_only=True))
        return path.name[:12] if path.name else "unknown"
    except Exception:  # noqa: BLE001 - an unstamped rendition beats a failed one
        return "unknown"


class QwenMLXEngine:
    """One caller at a time: the Session isn't documented as thread-safe."""

    name = "qwen3-asr"
    max_chunk_s = 180.0
    supports_prompt = True

    def __init__(self, name: str, entry: ModelEntry, *,
                 transcribe_fn: Callable | None = None):
        catalog = CATALOG.get(entry.catalog or "qwen3-asr-1.7b")
        self.model_name = name
        self.model_id = (entry.model or (catalog.default_model if catalog else None)
                         or "Qwen/Qwen3-ASR-1.7B")
        self._fn = transcribe_fn

    def _transcribe(self) -> Callable:
        if self._fn is None:
            try:
                from mlx_qwen3_asr import ForcedAligner, Session
            except ImportError:
                raise EngineError("unavailable", "mlx-qwen3-asr isn't installed",
                                  hint="on an Apple Silicon Mac (macOS 14+), install "
                                       "vid2sub[mac]") from None
            # One Session and one aligner per engine: the package's module-level transcribe()
            # measured as slow on a second call as on the first (task 27 live run).
            try:
                session = Session(self.model_id)
                aligner = ForcedAligner()
            except Exception as err:
                raise EngineError(
                    "unavailable", "Qwen3-ASR couldn't load its model",
                    hint="check the network for the first download and free disk space; on an "
                         "Apple Silicon Mac (macOS 14+) with vid2sub[mac]") from err

            def run(audio, *, model, **kw):
                return session.transcribe(audio, forced_aligner=aligner, **kw)

            self._fn = run
        return self._fn

    def transcribe(self, chunk: Chunk, *, language: str | None, prompt: str) -> ChunkResult:
        try:
            name = langs.get(language).qwen if language else None
        except langs.UnknownLanguage:
            raise EngineError("unavailable", "Qwen3-ASR has no name for that language") from None
        result = self._transcribe()(
            (chunk.float32, SAMPLE_RATE), model=self.model_id, language=name,
            context=prompt or "", return_timestamps=True, verbose=False)
        data = {"text": getattr(result, "text", ""), "language": getattr(result, "language", ""),
                "segments": getattr(result, "segments", None) or []}
        return ChunkResult(parse_qwen(data, duration_ms=chunk.duration_ms))

    def detect_language(self, chunk: Chunk) -> dict[str, float]:
        result = self._transcribe()((chunk.float32, SAMPLE_RATE), model=self.model_id,
                                    language=None, return_timestamps=False, verbose=False)
        code = langs.from_qwen(getattr(result, "language", "") or "")
        return {code: 1.0} if code else {}

    def stamp(self) -> ModelStamp:
        return ModelStamp(self.name, self.model_id, hf_revision(self.model_id))

    def close(self) -> None:
        self._fn = None
