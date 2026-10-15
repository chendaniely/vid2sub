"""Chunking the audio for transcription, and deciding which chunk owns each word (spec §8.7).

Speech regions are grouped into chunks no longer than the engine allows (300 s for Whisper, 180
for Qwen's aligner), with 0.5 s of padding either side, and cut in the middle of a silence; a
silence over 10 s always starts a new chunk, so long music isn't sent at all. The chunks' cores
tile the whole timeline (the first starts at 0, the last runs to the end), and a word belongs to
the chunk whose core contains its midpoint, so a word on a boundary is kept exactly once. Inside
a chunk, non-speech longer than 2 s is replaced with silence, which stops Whisper inventing lines
over music.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass

import numpy as np

from vid2sub.media.decode import SAMPLES_PER_MS
from vid2sub.subs.model import Segment, shift_segment


@dataclass(frozen=True)
class ChunkPlan:
    index: int
    start_ms: int  # the first sample sent, padding included
    end_ms: int
    core_start_ms: int
    core_end_ms: int
    last: bool

    def owns(self, mid_ms: int) -> bool:
        return self.core_start_ms <= mid_ms and (mid_ms < self.core_end_ms or self.last)

    def plan_hash(self) -> str:
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()[:12]


def _merge(speech: Sequence[tuple[int, int]], duration_ms: int) -> list[tuple[int, int]]:
    regions = sorted((max(0, s), min(duration_ms, e)) for s, e in speech
                     if min(duration_ms, e) > max(0, s))
    merged: list[tuple[int, int]] = []
    for s, e in regions:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged


def plan_chunks(speech: Sequence[tuple[int, int]], duration_ms: int, max_chunk_s: float, *,
                pad_ms: int = 500, max_gap_ms: int = 10_000) -> list[ChunkPlan]:
    limit = int(max_chunk_s * 1000) - 2 * pad_ms
    if limit <= 0:
        raise ValueError("max_chunk_s is too small for the padding")
    merged = _merge(speech, duration_ms)
    if not merged:
        return []
    pieces: list[tuple[int, int]] = []
    for s, e in merged:
        while e - s > limit:
            pieces.append((s, s + limit))
            s += limit
        pieces.append((s, e))
    groups: list[tuple[int, int]] = []
    g_start, g_end = pieces[0]
    for s, e in pieces[1:]:
        if e - g_start <= limit and s - g_end <= max_gap_ms:
            g_end = e
            continue
        groups.append((g_start, g_end))
        g_start, g_end = s, e
    groups.append((g_start, g_end))
    plans = []
    for i, (gs, ge) in enumerate(groups):
        core_start = 0 if i == 0 else (groups[i - 1][1] + gs) // 2
        core_end = duration_ms if i == len(groups) - 1 else (ge + groups[i + 1][0]) // 2
        plans.append(ChunkPlan(i, max(0, gs - pad_ms), min(duration_ms, ge + pad_ms),
                               core_start, core_end, last=i == len(groups) - 1))
    return plans


def chunk_samples(samples: np.ndarray, plan: ChunkPlan, speech: Sequence[tuple[int, int]], *,
                  fill_gap_ms: int = 2000, keep_ms: int = 200) -> np.ndarray:
    out = samples[plan.start_ms * SAMPLES_PER_MS: plan.end_ms * SAMPLES_PER_MS].copy()
    spans = sorted((max(plan.start_ms, s - keep_ms), min(plan.end_ms, e + keep_ms))
                   for s, e in speech if e > plan.start_ms and s < plan.end_ms)
    t = plan.start_ms
    for s, e in spans + [(plan.end_ms, plan.end_ms)]:
        if s - t > fill_gap_ms:
            out[(t - plan.start_ms) * SAMPLES_PER_MS:(s - plan.start_ms) * SAMPLES_PER_MS] = 0
        t = max(t, e)
    return out


def place(plan: ChunkPlan, segments: Sequence[Segment]) -> list[Segment]:
    out = []
    for seg in segments:
        g = shift_segment(seg, plan.start_ms)
        if g.words:
            kept = tuple(w for w in g.words if plan.owns((w.start_ms + w.end_ms) // 2))
            if kept:
                out.append(g.model_copy(update={
                    "words": kept, "text": "".join(w.text for w in kept),
                    "start_ms": kept[0].start_ms, "end_ms": max(w.end_ms for w in kept)}))
        elif plan.owns((g.start_ms + g.end_ms) // 2):
            out.append(g)
    return out
