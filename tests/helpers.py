"""Helpers shared by tests (importable because pyproject sets pythonpath = ["tests"])."""

import shutil
import subprocess
import wave
from pathlib import Path

import numpy as np


def make_clip(directory: Path, name: str = "clip.mkv", *, seconds: float = 4.0,
              audio_delay: float = 0.0, audio_langs=("jpn",), default_audio: int = 0,
              title: str | None = None, speech: Path | None = None) -> Path:
    """A small video made with ffmpeg's lavfi sources: a test pattern, one sine-wave audio track
    per language (or `speech` for the first), an optional audio delay and title."""
    ffmpeg = shutil.which("ffmpeg")
    assert ffmpeg, "ffmpeg is needed for media tests"
    args = [ffmpeg, "-nostdin", "-v", "error", "-y",
            "-f", "lavfi", "-i", f"testsrc=size=160x120:rate=10:duration={seconds}"]
    for k, _ in enumerate(audio_langs):
        if audio_delay:
            args += ["-itsoffset", str(audio_delay)]
        if speech is not None and k == 0:
            args += ["-i", str(speech)]
        else:
            args += ["-f", "lavfi", "-i", f"sine=frequency={440 + 110 * k}:duration={seconds}"]
    args += ["-map", "0:v"]
    for k in range(len(audio_langs)):
        args += ["-map", f"{k + 1}:a"]
    args += ["-c:v", "mpeg4", "-c:a", "aac"]
    for k, lang in enumerate(audio_langs):
        args += [f"-metadata:s:a:{k}", f"language={lang}",
                 f"-disposition:a:{k}", "default" if k == default_audio else "0"]
    if title:
        args += ["-metadata", f"title={title}"]
    out = directory / name
    subprocess.run(args + [str(out)], check=True)
    return out


SPEECH = Path(__file__).parent / "fixtures" / "speech" / "jfk-14s.wav"


def speech_with_gaps(directory: Path) -> Path:
    """3 s silence, 8 s speech, 4 s silence, 6 s speech, 2 s silence (23 s, 16 kHz mono)."""
    with wave.open(str(SPEECH), "rb") as w:
        speech = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
    rate = 16_000
    silence = lambda s: np.zeros(int(s * rate), dtype="<i2")
    audio = np.concatenate([silence(3), speech[: 8 * rate], silence(4),
                            speech[8 * rate: 14 * rate], silence(2)])
    out = directory / "gaps.wav"
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(audio.tobytes())
    return out
