"""A show's glossary: names and terms with their preferred translations (spec §16).

`vid2sub.glossary.toml` sits in the show's folder. Its source terms become Whisper's prompt (a
comma-joined list, never instructions, an audio-router lesson) or Qwen3-ASR's context; its
description and pairs go into the translator's system prompt; its hash goes into translation
versions so a glossary edit marks translations stale. The editor's Save adds terms to it by
appending lines to its `[terms]`, never by writing it out again, so the person's comments and
layout survive (it is their file, spec §16); the result must read back as the old glossary plus
the new terms, or nothing is written (Phase 2 plan, Task 6).

A chunk prompt is the vocabulary first, then the previous chunk's last words (spec §8.7), within
a character budget. Whisper's prompt window is 224 tokens and it keeps the end of a prompt:
whisper.cpp's rolling context takes the last n_text_ctx/2 tokens, so the front, where the
vocabulary is, is what gets cut. Chinese and Japanese often cost more than one token per
character, so their budget is 100 characters (600 otherwise). The vocabulary is kept whole, up to
the budget, and the tail is trimmed to whatever room is left, as faster-whisper keeps its
hotwords and trims its previous text (final review; checked against whisper.cpp's
src/whisper.cpp, faster-whisper's transcribe.py and OpenAI's speech-to-text guide).
"""

from __future__ import annotations

import hashlib
import json
import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass


class GlossaryError(ValueError):
    pass


@dataclass(frozen=True)
class Glossary:
    description: str = ""
    terms: tuple[tuple[str, str], ...] = ()

    @property
    def empty(self) -> bool:
        return not self.description and not self.terms

    def sha(self) -> str:
        if self.empty:
            return ""
        blob = json.dumps({"description": self.description,
                           "terms": [list(t) for t in self.terms]},
                          ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(blob.encode()).hexdigest()[:8]

    def source_terms(self) -> list[str]:
        return [source for source, _ in self.terms]


EMPTY_GLOSSARY = Glossary()


def parse_glossary(text: str) -> Glossary:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as err:
        raise GlossaryError(f"the glossary isn't valid TOML: {err}") from None
    unknown = set(data) - {"description", "terms"}
    if unknown:
        raise GlossaryError(f"unknown glossary key(s): {', '.join(sorted(unknown))}")
    description = data.get("description", "")
    terms = data.get("terms", {})
    if (not isinstance(description, str) or not isinstance(terms, dict)
            or not all(isinstance(k, str) and isinstance(v, str) for k, v in terms.items())):
        raise GlossaryError('the glossary needs `description` as text and `[terms]` as '
                            '"source" = "translation" pairs')
    return Glossary(description.strip(),
                    tuple((k.strip(), v.strip()) for k, v in terms.items() if k.strip()))


def add_terms(text: str, adds: Mapping[str, str]) -> tuple[str, list[str]]:
    """`text` (a glossary file's, or "" for none) with `adds` appended to its `[terms]`, and the
    terms it already had with another translation: those keep the file's translation.

    A layout that appending can't extend (an inline `terms = {...}` table) raises GlossaryError
    rather than being rewritten."""
    current = parse_glossary(text) if text.strip() else EMPTY_GLOSSARY
    have = dict(current.terms)
    new: dict[str, str] = {}
    kept: list[str] = []
    for term, translation in adds.items():
        term, translation = term.strip(), translation.strip()
        if not term or not translation:
            raise GlossaryError("a glossary term and its translation both need text")
        if term in have:
            if have[term] != translation:
                kept.append(term)
            continue
        new[term] = translation
    if not new:
        return text, kept
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = "".join(f"{_toml_string(k)} = {_toml_string(v)}{nl}" for k, v in new.items())
    base = text if not text or text.endswith("\n") else text + nl
    expected = Glossary(current.description, current.terms + tuple(new.items()))
    for candidate in (base + lines, base + (nl if base else "") + "[terms]" + nl + lines):
        try:
            if parse_glossary(candidate) == expected:
                return candidate, kept
        except GlossaryError:
            continue
    raise GlossaryError("the glossary's layout can't take new terms without being rewritten; "
                        "add them by hand")


def _toml_string(s: str) -> str:
    """A TOML basic string: quotes, backslashes and control characters escaped."""
    out = []
    for ch in s:
        if ch in '"\\':
            out.append("\\" + ch)
        elif ord(ch) < 0x20 or ord(ch) == 0x7F:
            out.append(f"\\u{ord(ch):04X}")
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'


# vocabulary_prompt and prompt_sha are copied from audio-router,
# src/audio_router/archive/stages/transcribe.py at 64612df.
def vocabulary_prompt(terms: Iterable[str] | None) -> str:
    """Whisper's `initial_prompt` as a plain sentence.

    Whisper conditions on it as if it were preceding transcript text, so a comma-joined list of
    the exact spellings is enough; phrasing it as instructions is how the model starts
    transcribing the instructions."""
    cleaned = [t.strip() for t in (terms or []) if t and t.strip()]
    return ", ".join(cleaned) + "." if cleaned else ""


def prompt_sha(prompt: str) -> str:
    return hashlib.sha256(prompt.encode()).hexdigest()[:8] if prompt else ""


CJK_PROMPT_CHARS = 100
PROMPT_CHARS = 600
TAIL_CHARS = 200


def chunk_prompt(glossary: Glossary, previous_tail: str, *, cjk: bool) -> str:
    """The vocabulary (cut to the budget if it must be), then as much of the tail as fits."""
    budget = CJK_PROMPT_CHARS if cjk else PROMPT_CHARS
    vocab = vocabulary_prompt(glossary.source_terms())[:budget]
    room = budget - len(vocab) - (1 if vocab else 0)
    tail = previous_tail.strip()
    tail = tail[-min(TAIL_CHARS, room):] if room > 0 and tail else ""
    return f"{vocab} {tail}" if vocab and tail else (vocab or tail)
