import json
from datetime import datetime
from pathlib import Path

from jsonschema import Draft202012Validator

from vid2sub.subs.model import Cue, Segment, Transcript, Word
from vid2sub.subs.rendition import (
    cues_body,
    cues_from_body,
    transcript_body,
    transcript_from_body,
)

CONTRACTS = Path(__file__).parent / "contracts"
T = Transcript(language="ja", language_probs={"ja": 0.97}, segments=(
    Segment(text="こんにちは", start_ms=1000, end_ms=2000, avg_logprob=-0.2,
            words=(Word(text="こん", start_ms=1000, end_ms=1500, prob=0.9),
                   Word(text="にちは", start_ms=1500, end_ms=1500, timed=False))),
    Segment(text="lost timings", start_ms=3000, end_ms=4000),
))


def body():
    return transcript_body(T, engine="whisper.cpp", model="whisper-large-v3-turbo",
                           version="whisper-large-v3-turbo@unknown+v1234abcd+p00000000",
                           created_at="2026-10-14T12:00:00Z",
                           inputs={"audio_sha256": "aa", "audio_track": 1}, meta={"vad": "x"})


def test_a_transcript_body_is_a_valid_recordings_rendition():
    b = body()
    Draft202012Validator(json.loads((CONTRACTS / "recordings-rendition.schema.json").read_text())
                         ).validate(b)
    Draft202012Validator(json.loads(
        (CONTRACTS / "recordings-transcript-payload.schema.json").read_text())
    ).validate(b["payload"])
    assert datetime.fromisoformat(b["created_at"]).tzinfo is not None
    assert b["inputs"]["audio_track"] == "1"
    assert b["payload"]["segments"][0]["start"] == 1.0


def test_a_transcript_body_reads_back_with_word_probabilities_and_untimed_words():
    assert transcript_from_body(body()) == T


def test_a_cues_body_round_trips():
    cues = [Cue(id="c1", start_ms=0, end_ms=900, text="Hi", w=(0, 1)),
            Cue(id="c2", start_ms=1000, end_ms=1900, text="There", src=("s1", "s2"), src_sha="x")]
    b = cues_body(cues, language="en", script=None, engine="vid2sub", model=None,
                  version="cues@1", created_at="2026-10-14T12:00:00Z", inputs={}, meta={},
                  glossary_sha="g1")
    assert b["schema"] == "vid2sub/cues@1" and b["payload"]["glossary_sha"] == "g1"
    assert cues_from_body(b) == cues
