"""Decode once to 16 kHz mono, and encode chunks as metadata-free FLAC (spec §8.5, §7.3).

Every stage reads the same 16 kHz mono PCM WAV (an audio-router lesson: one waveform, one
timeline), written to the job's scratch folder and deleted with it. Chunks are encoded from raw
PCM with `-map_metadata -1 -fflags +bitexact`: ffmpeg otherwise copies an MKV's title into the
FLAC, and the Spark's whisper-server logs ffmpeg's report, metadata tags included (council,
2026-10-14).
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

from vid2sub.media.probe import AudioTrack
from vid2sub.media.tools import Tools, input_args, run_tool

SAMPLE_RATE = 16_000
SAMPLES_PER_MS = SAMPLE_RATE // 1000


def decode_to_wav(path: Path, track: AudioTrack, out: Path, tools: Tools, *, scratch: Path,
                  duration_ms: int) -> None:
    timeout = max(120.0, duration_ms / 1000 * 0.5)
    run_tool([tools.need("ffmpeg"), "-nostdin", "-v", "error", *input_args(path),
              "-map", f"0:{track.stream_index}", "-ac", "1", "-ar", str(SAMPLE_RATE),
              "-c:a", "pcm_s16le", "-map_metadata", "-1", "-fflags", "+bitexact", "-y",
              str(out)], cwd=scratch, timeout=timeout)


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        if (w.getnchannels(), w.getframerate(), w.getsampwidth()) != (1, SAMPLE_RATE, 2):
            raise ValueError("expected 16 kHz mono 16-bit PCM")
        frames = w.readframes(w.getnframes())
    return np.frombuffer(frames, dtype="<i2").copy()


def to_float(samples: np.ndarray) -> np.ndarray:
    return samples.astype(np.float32) / 32768.0


def encode_flac(samples: np.ndarray, tools: Tools, *, scratch: Path) -> bytes:
    proc = run_tool([tools.need("ffmpeg"), "-v", "error", "-f", "s16le", "-ar", str(SAMPLE_RATE),
                     "-ac", "1", "-protocol_whitelist", "pipe", "-i", "pipe:0",
                     "-map_metadata", "-1", "-fflags", "+bitexact", "-c:a", "flac", "-f", "flac",
                     "pipe:1"], cwd=scratch, timeout=120,
                    stdin=samples.astype("<i2").tobytes())
    return proc.stdout
