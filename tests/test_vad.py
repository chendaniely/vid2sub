from importlib.resources import files

import numpy as np
from helpers import speech_with_gaps

from vid2sub.media.decode import read_wav, to_float
from vid2sub.media.vad import speech_regions


def overlaps(region, window):
    return region[0] < window[1] and window[0] < region[1]


def test_speech_is_found_where_it_is_and_nowhere_else(tmp_path):
    samples = to_float(read_wav(speech_with_gaps(tmp_path)))
    regions = speech_regions(samples)
    assert regions
    speech_windows = [(2500, 11500), (14500, 21500)]
    for r in regions:
        assert any(r[0] >= w[0] and r[1] <= w[1] for w in speech_windows), r
    for window in speech_windows:
        covered = sum(min(r[1], window[1]) - max(r[0], window[0])
                      for r in regions if overlaps(r, window))
        assert covered > 0.5 * (window[1] - window[0] - 1000)


def test_silence_has_no_speech():
    assert speech_regions(np.zeros(16_000 * 5, dtype=np.float32)) == []


def test_the_silero_vad_model_ships_with_its_mit_licence():
    licence = files("vid2sub.media._vendor").joinpath("LICENSE-silero-vad")
    assert licence.is_file()
    text = licence.read_text(encoding="utf-8")
    assert text.startswith("MIT License") and "Copyright (c) 2020-present Silero Team" in text
