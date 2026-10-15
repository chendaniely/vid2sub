"""Rendition bodies: transcripts in recordings' envelope, cue tracks in vid2sub's (spec §14.3).

A transcript body is byte-compatible with recordings' `recordings/rendition@1` and its
TranscriptPayload (seconds, no extra fields), so recordings can import it; word probabilities,
untimed words and per-segment statistics live in `meta`. `inputs` is `dict[str, str]`, so every
value is stringified. Cue tracks use `vid2sub/cues@1` with the same field names.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from vid2sub.subs.model import Cue, Segment, Transcript, Word

TRANSCRIPT_SCHEMA = "recordings/rendition@1"
CUES_SCHEMA = "vid2sub/cues@1"


def _s(ms: int) -> float:
    return round(ms / 1000, 3)


def _ms(seconds: float) -> int:
    return round(seconds * 1000)


def transcript_body(t: Transcript, *, engine: str, model: str | None, version: str,
                    created_at: str, inputs: dict[str, Any], meta: dict[str, Any]) -> dict:
    segments, probs, untimed, stats = [], [], [], []
    index = 0
    for seg in t.segments:
        words = []
        for w in seg.words:
            words.append({"word": w.text, "start": _s(w.start_ms), "end": _s(w.end_ms)})
            probs.append(w.prob)
            if not w.timed:
                untimed.append(index)
            index += 1
        segments.append({"start": _s(seg.start_ms), "end": _s(seg.end_ms), "speaker": None,
                         "speaker_name": None, "embedding_key": None, "text": seg.text,
                         "words": words})
        stats.append({"avg_logprob": seg.avg_logprob, "no_speech_prob": seg.no_speech_prob,
                      "compression_ratio": seg.compression_ratio})
    return {
        "schema": TRANSCRIPT_SCHEMA, "kind": "transcript", "engine": engine, "model": model,
        "version": version, "created_at": created_at,
        "inputs": {k: str(v) for k, v in inputs.items()},
        "meta": {**meta, "word_prob": probs, "untimed_words": untimed, "segment_stats": stats,
                 "language_probs": dict(t.language_probs)},
        "payload": {"language": t.language, "segments": segments},
    }


def transcript_from_body(body: dict) -> Transcript:
    meta = body.get("meta", {})
    probs = meta.get("word_prob", [])
    untimed = set(meta.get("untimed_words", []))
    stats = meta.get("segment_stats", [])
    segments = []
    index = 0
    for k, seg in enumerate(body["payload"]["segments"]):
        words = []
        for w in seg.get("words", []):
            words.append(Word(text=w["word"], start_ms=_ms(w["start"]), end_ms=_ms(w["end"]),
                              prob=probs[index] if index < len(probs) else None,
                              timed=index not in untimed))
            index += 1
        st = stats[k] if k < len(stats) else {}
        segments.append(Segment(text=seg["text"], start_ms=_ms(seg["start"]),
                                end_ms=_ms(seg["end"]), words=tuple(words), **st))
    return Transcript(language=body["payload"]["language"], segments=tuple(segments),
                      language_probs=meta.get("language_probs", {}))


def cues_body(cues: Sequence[Cue], *, language: str, script: str | None, engine: str,
              model: str | None, version: str, created_at: str, inputs: dict[str, Any],
              meta: dict[str, Any], glossary_sha: str | None = None) -> dict:
    payload: dict[str, Any] = {"language": language, "script": script,
                               "cues": [c.dump() for c in cues]}
    if glossary_sha:
        payload["glossary_sha"] = glossary_sha
    return {"schema": CUES_SCHEMA, "kind": "cues", "engine": engine, "model": model,
            "version": version, "created_at": created_at,
            "inputs": {k: str(v) for k, v in inputs.items()}, "meta": dict(meta),
            "payload": payload}


def cues_from_body(body: dict) -> list[Cue]:
    return [Cue.model_validate(c) for c in body["payload"]["cues"]]


def body_track_language(body: dict) -> tuple[str, str | None]:
    return body["payload"]["language"], body["payload"].get("script")
