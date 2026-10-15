"""Where the speech is (spec §8.6).

Silero VAD v6 on onnxruntime, vendored from faster-whisper (torch-free). ffmpeg's silencedetect
is energy-only and fails under music; the silero-vad package needs torch (council, 2026-10-14).
Regions are in milliseconds on the decoded audio's timeline.
"""

from __future__ import annotations

import numpy as np

from vid2sub.media._vendor.silero import VadOptions, get_speech_timestamps

VAD_ID = "silero-v6@faster-whisper-1.2.1"


def speech_regions(samples: np.ndarray, *, threshold: float = 0.5, min_speech_ms: int = 250,
                   min_silence_ms: int = 500, pad_ms: int = 200) -> list[tuple[int, int]]:
    if len(samples) == 0:
        return []
    options = VadOptions(threshold=threshold, min_speech_duration_ms=min_speech_ms,
                         min_silence_duration_ms=min_silence_ms, speech_pad_ms=pad_ms)
    stamps = get_speech_timestamps(samples.astype(np.float32), options, sampling_rate=16_000)
    return [(round(s["start"] / 16), round(s["end"] / 16)) for s in stamps]
