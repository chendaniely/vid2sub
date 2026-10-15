"""The endpoint engine: any OpenAI-shaped /v1/audio/transcriptions server (spec §9.3).

The Spark's whisper.cpp behind llama-swap, OpenAI, or a local whisper.cpp server. The entry's
`parser` picks the response shape. Requests ask for `verbose_json`, send the language and prompt
when given, and the chunk as `chunk-NNNN.flac`. If the server says which model answered
(local-ai Phase 3's `x-spark-model`), a different model from the one asked for fails the chunk:
vid2sub never accepts a substitute (spec §9.6, §17.4). The Spark reports no model revision
today, so stamps say `unknown`.
"""

from __future__ import annotations

from vid2sub.catalog import CATALOG
from vid2sub.config import Config, ModelEntry
from vid2sub.engines import clients
from vid2sub.engines.base import Chunk, ChunkResult, EngineError, ModelStamp
from vid2sub.parse import ParseError
from vid2sub.parse.openai import parse_openai
from vid2sub.parse.whispercpp import parse_whispercpp


class EndpointEngine:
    def __init__(self, name: str, entry: ModelEntry, config: Config,
                 policy: clients.RunPolicy, keys: clients.KeyRing):
        self.model_name = name
        self.entry = entry
        self.name = entry.parser or "openai"
        catalog = CATALOG.get(entry.catalog or "")
        self.max_chunk_s = catalog.max_chunk_s if catalog else 300.0
        self.supports_prompt = catalog.supports_prompt if catalog else True
        self._key_env = config.endpoints[entry.endpoint].key_env
        self._secrets = keys.secrets(config)
        self._client = clients.transcription_client(name, entry, config, policy, keys)

    def _post(self, chunk: Chunk, *, language: str | None, prompt: str) -> ChunkResult:
        params: dict = {"model": self.entry.model, "response_format": "verbose_json"}
        if language:
            params["language"] = language
        if prompt and self.supports_prompt:
            params["prompt"] = prompt
        if self.entry.parser == "openai":
            params["timestamp_granularities"] = ["word", "segment"]
        data, headers = clients.call_transcription(
            self._client, key_env=self._key_env, secrets=self._secrets,
            file=(chunk.upload_name, chunk.flac(), "audio/flac"), **params)
        answered = headers.get("x-spark-model")
        if answered and answered != self.entry.model:
            raise EngineError("bad_response",
                              f"asked for {self.entry.model} but {answered} answered",
                              hint="vid2sub never accepts a substitute model")
        try:
            parsed = (parse_whispercpp(data) if self.entry.parser == "whisper.cpp"
                      else parse_openai(data))
        except ParseError as err:
            raise EngineError("bad_response", str(err)) from None
        return ChunkResult(parsed, answered)

    def transcribe(self, chunk: Chunk, *, language: str | None, prompt: str) -> ChunkResult:
        return self._post(chunk, language=language, prompt=prompt)

    def detect_language(self, chunk: Chunk) -> dict[str, float]:
        parsed = self._post(chunk, language=None, prompt="").parsed
        if parsed.language_probs:
            return dict(parsed.language_probs)
        return {parsed.language: 1.0} if parsed.language else {}

    def stamp(self) -> ModelStamp:
        return ModelStamp(self.name, self.entry.model or "", "unknown")

    def close(self) -> None:
        self._client.close()
