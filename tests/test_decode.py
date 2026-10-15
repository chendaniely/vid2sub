import json
import subprocess

import numpy as np
import pytest
from helpers import make_clip

from vid2sub.media.decode import SAMPLE_RATE, decode_to_wav, encode_flac, read_wav, to_float
from vid2sub.media.probe import probe
from vid2sub.media.tools import Tools

pytestmark = pytest.mark.media


def test_decoding_gives_16khz_mono_samples_of_the_chosen_track(tmp_path):
    clip = make_clip(tmp_path, seconds=3.0, audio_langs=("jpn", "eng"))
    tools = Tools.find()
    p = probe(clip, tools, scratch=tmp_path)
    out = tmp_path / "audio.wav"
    decode_to_wav(clip, p.audio[1], out, tools, scratch=tmp_path, duration_ms=p.duration_ms)
    samples = read_wav(out)
    assert samples.dtype == np.int16
    assert abs(len(samples) - 3 * SAMPLE_RATE) < SAMPLE_RATE // 10
    assert to_float(samples).dtype == np.float32


def test_an_encoded_chunk_is_flac_with_no_metadata_even_when_the_video_has_a_title(tmp_path):
    clip = make_clip(tmp_path, seconds=2.0, title="Secret Show Title")
    tools = Tools.find()
    p = probe(clip, tools, scratch=tmp_path)
    wav = tmp_path / "audio.wav"
    decode_to_wav(clip, p.audio[0], wav, tools, scratch=tmp_path, duration_ms=p.duration_ms)
    flac = encode_flac(read_wav(wav), tools, scratch=tmp_path)
    assert flac.startswith(b"fLaC")
    path = tmp_path / "chunk.flac"
    path.write_bytes(flac)
    info = json.loads(subprocess.run(
        [tools.ffprobe, "-v", "error", "-show_format", "-of", "json", str(path)],
        capture_output=True, check=True).stdout)
    assert "Secret" not in json.dumps(info)
    assert not (info["format"].get("tags") or {}).get("title")
