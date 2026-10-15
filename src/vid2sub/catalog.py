"""The model catalog and its routing (spec §11).

Data, not code: each model family's languages, strengths, weak spots, where it runs and how to
install it. The UI's pickers and the README's model table come from it. `vid2sub.toml`'s
`[models.*]` entries point at catalog ids. Routing is an ordered preference per source language:
the first model available now wins, and among equals the Spark's (an endpoint) wins over the
Mac's (in-process). The Spark's translation default is Gemma 4, resident with two slots; the only
Qwen chat model there is Dan's coder (council, 2026-10-14). Pure.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from vid2sub.subs import langs


@dataclass(frozen=True)
class CatalogEntry:
    id: str
    task: Literal["transcribe", "translate"]
    title: str
    good_for: str
    weak: str
    runs_on: str
    install: str
    languages: tuple[str, ...] = ()
    max_chunk_s: float = 300.0
    supports_prompt: bool = True
    family: str = "whisper"
    cloud: bool = False
    default_model: str | None = None


CATALOG: dict[str, CatalogEntry] = {e.id: e for e in (
    CatalogEntry(
        "qwen3-asr-1.7b", "transcribe", "Qwen3-ASR 1.7B + ForcedAligner 0.6B",
        good_for="Mandarin and Cantonese by a wide margin (Qwen's numbers: WenetSpeech-Yue long "
                 "8.85 vs Whisper large-v3's 46.64); strong English; Hong Kong and Guangdong "
                 "accents; vocabulary context",
        weak="Japanese is supported but has no published benchmark",
        runs_on="Mac (mlx-qwen3-asr); the Spark once local-ai serves it",
        install="vid2sub[mac]", languages=("zh", "yue", "en", "ja", "ko"), max_chunk_s=180,
        family="qwen3-asr", default_model="Qwen/Qwen3-ASR-1.7B"),
    CatalogEntry(
        "qwen3-asr-0.6b", "transcribe", "Qwen3-ASR 0.6B + ForcedAligner 0.6B",
        good_for="the same languages as the 1.7B, lighter and faster",
        weak="less accurate than the 1.7B", runs_on="Mac (mlx-qwen3-asr)",
        install="vid2sub[mac]", languages=("zh", "yue", "en", "ja", "ko"), max_chunk_s=180,
        family="qwen3-asr", default_model="Qwen/Qwen3-ASR-0.6B"),
    CatalogEntry(
        "whisper-large-v3", "transcribe", "Whisper large-v3",
        good_for="Japanese (until compared with Qwen3-ASR), 99 languages, vocabulary prompt",
        weak="slower than turbo; poor on Cantonese",
        runs_on="Windows/Linux (faster-whisper, M3); the Spark if local-ai adds it",
        install="a whisper.cpp server, or vid2sub[whisper] from M3",
        languages=("ja", "en", "zh", "ko", "yue")),
    CatalogEntry(
        "whisper-large-v3-turbo", "transcribe", "Whisper large-v3-turbo",
        good_for="English → English captions, quick drafts",
        weak="weaker on Cantonese and tonal languages; no translate task",
        runs_on="the Spark (always loaded); Windows/Linux from M3",
        install="the Spark's endpoint, or vid2sub[whisper] from M3",
        languages=("en", "ja", "zh", "ko")),
    CatalogEntry(
        "openai-whisper-1", "transcribe", "OpenAI whisper-1",
        good_for="a cloud fallback in any language",
        weak="25 MB per request (vid2sub's chunks fit); the audio leaves your machine",
        runs_on="OpenAI", install="an OpenAI key", languages=("en", "ja", "zh", "ko"),
        cloud=True),
    CatalogEntry(
        "gemma-4-26b-a4b", "translate", "Gemma 4 26B-A4B",
        good_for="Japanese → English, general translation; always loaded on the Spark, two slots",
        weak="", runs_on="the Spark", install="the Spark's endpoint", family="llm"),
    CatalogEntry(
        "qwen3.8-27b", "translate", "Qwen3.8 27B",
        good_for="Mandarin and Cantonese → English",
        weak="on the Spark it's Dan's coder: loads on demand, one slot, 41 GiB",
        runs_on="the Spark", install="the Spark's endpoint", family="llm"),
    CatalogEntry(
        "local-llm", "translate", "A local chat model",
        good_for="translation on your own machine (LM Studio, Ollama, vLLM)",
        weak="quality depends on the model you load", runs_on="your machine",
        install="any OpenAI-compatible server", family="llm"),
    CatalogEntry(
        "openai-gpt", "translate", "OpenAI GPT",
        good_for="a cloud fallback for translation", weak="the text leaves your machine",
        runs_on="OpenAI", install="an OpenAI key", family="llm", cloud=True),
)}

TRANSCRIBE_ROUTES: dict[str, tuple[str, ...]] = {
    "yue": ("qwen3-asr-1.7b", "qwen3-asr-0.6b", "whisper-large-v3", "whisper-large-v3-turbo",
            "openai-whisper-1"),
    "zh": ("qwen3-asr-1.7b", "qwen3-asr-0.6b", "whisper-large-v3", "whisper-large-v3-turbo",
           "openai-whisper-1"),
    "ja": ("whisper-large-v3", "qwen3-asr-1.7b", "whisper-large-v3-turbo", "qwen3-asr-0.6b",
           "openai-whisper-1"),
    "en": ("whisper-large-v3-turbo", "qwen3-asr-1.7b", "whisper-large-v3", "qwen3-asr-0.6b",
           "openai-whisper-1"),
    "ko": ("whisper-large-v3", "qwen3-asr-1.7b", "whisper-large-v3-turbo", "openai-whisper-1"),
}
TRANSLATE_ROUTE: tuple[str, ...] = ("gemma-4-26b-a4b", "local-llm", "openai-gpt")
WEAK: frozenset[tuple[str, str]] = frozenset({
    ("yue", "whisper-large-v3"), ("yue", "whisper-large-v3-turbo"),
    ("zh", "whisper-large-v3-turbo"),
})


@dataclass(frozen=True)
class Candidate:
    name: str
    catalog: str | None
    kind: Literal["endpoint", "in-process"]
    available: bool
    reason: str = ""
    cloud: bool = False
    unreachable: bool = False  # the server didn't answer: waiting may help, unlike a missing key


@dataclass(frozen=True)
class Suggestion:
    model: str | None
    catalog: str | None
    warning: str = ""
    considered: tuple[tuple[str, str], ...] = ()


def suggest(lang: str, candidates: Sequence[Candidate], task: str, *,
            allow_cloud: bool) -> Suggestion:
    if task == "transcribe":
        route = TRANSCRIBE_ROUTES.get(lang, TRANSCRIBE_ROUTES["en"])
    elif task == "translate":
        route = TRANSLATE_ROUTE
    else:
        raise ValueError(f"unknown task {task!r}; known: transcribe, translate")
    no_route = ""
    if task == "transcribe" and lang not in TRANSCRIBE_ROUTES:
        no_route = f"no route for {lang}; using the English route"
    considered: list[tuple[str, str]] = []
    off_route = tuple(
        (o.name, f"not in the {task} route for {lang}; choose it with --model")
        for o in candidates if o.catalog not in route)
    for cid in route:
        matches = sorted((c for c in candidates if c.catalog == cid),
                         key=lambda c: 0 if c.kind == "endpoint" else 1)
        for c in matches:
            if not c.available:
                considered.append((c.name, c.reason))
                continue
            if (c.cloud or CATALOG[cid].cloud) and not allow_cloud:
                considered.append((c.name, "a cloud model: needs --allow-cloud"))
                continue
            notes = []
            if no_route:
                notes.append(no_route)
            if (lang, cid) in WEAK and lang in langs.LANGS:
                notes.append(f"{CATALOG[cid].title} is weak on {langs.get(lang).name}")
            return Suggestion(c.name, cid, "; ".join(notes), tuple(considered) + off_route)
    return Suggestion(None, None, "no usable model", tuple(considered) + off_route)


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def readme_table() -> str:
    rows = ["| Model | Task | Good for | Weak spots | Runs on |", "|---|---|---|---|---|"]
    for e in CATALOG.values():
        cells = (e.title, e.task, e.good_for, e.weak or "—", e.runs_on)
        rows.append("| " + " | ".join(_cell(c) for c in cells) + " |")
    return "\n".join(rows) + "\n"
