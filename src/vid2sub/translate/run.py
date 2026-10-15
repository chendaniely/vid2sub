"""Translating a track through chatlas (spec §13).

Batches of about 40 source cues, with read-only context either side, go to a fresh Chat each
(chat_structured adds turns to the Chat it's called on). The schema is built per batch so the
model can only name real cue ids; an answer that doesn't cover the batch exactly once, in order,
is split in half and retried, down to one cue at a time, and a cue that still fails stops the
track loudly. Items may cover several adjacent cues (Japanese→English reorders across cues).
Thinking is switched off through the model entry's `request_extra` (spec §13.1). The prompts
carry the glossary but never file names or titles.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from pydantic import BaseModel

from vid2sub.config import Config, ModelEntry
from vid2sub.engines import clients
from vid2sub.subs import langs, naming
from vid2sub.subs.glossary import Glossary
from vid2sub.subs.model import Cue
from vid2sub.subs.translate_shape import (
    Batch,
    Item,
    assemble,
    batch_model,
    item_limits,
    items_from,
    plan_batches,
    split_batch,
    validate_partition,
)

PROMPT_VERSION = "t1"
AskFn = Callable[[str, str, type[BaseModel]], BaseModel]


class TranslationFailed(RuntimeError):
    pass


_WRITTEN = {"zh": "Chinese"}  # Mandarin is spoken; the written target is Chinese


def _name(code: str) -> str:
    return langs.get(code).name if code in langs.LANGS else code


def system_prompt(source_lang: str, target_track: str, glossary: Glossary) -> str:
    info = naming.track(target_track)
    script = {"Hant": " in Traditional Chinese characters",
              "Hans": " in Simplified Chinese characters"}.get(info.script or "", "")
    target = _WRITTEN.get(info.lang, _name(info.lang))
    lines = [
        f"You translate subtitles from {_name(source_lang)} to {target}{script}.",
        ("Write natural, concise subtitle text a viewer can read quickly. Keep the meaning; drop "
         "filler if a line would be too long."),
        "Never add notes, explanations, romanisation or the original text.",
        "Answer only with the JSON the request asks for.",
    ]
    if glossary.description:
        lines.append(f"About this video: {glossary.description}")
    pairs = [(s, t) for s, t in glossary.terms if t]
    if pairs:
        lines.append("Use these translations for names and terms:")
        lines += [f"- {s} → {t}" for s, t in pairs]
    return "\n".join(lines)


def batch_prompt(batch: Batch, cues: Mapping[str, Cue], limits: Mapping[str, int]) -> str:
    def show(cid: str) -> str:
        return cues[cid].text.replace("\n", " ")

    parts: list[str] = []
    if batch.before:
        parts.append("Earlier lines, for context only (don't translate them):")
        parts += [f"[{cid}] {show(cid)}" for cid in batch.before]
    parts.append("Translate these lines. Return items in order. Each item lists the ids it "
                 "covers (one id, or several adjacent ids when a sentence runs across them) and "
                 "its translation. Cover every id exactly once. Keep each translation within the "
                 "character limit shown.")
    parts += [f"[{cid}] (max {limits[cid]} characters) {show(cid)}" for cid in batch.ids]
    if batch.after:
        parts.append("Later lines, for context only (don't translate them):")
        parts += [f"[{cid}] {show(cid)}" for cid in batch.after]
    return "\n".join(parts)


def make_ask(name: str, entry: ModelEntry, config: Config, policy: clients.RunPolicy,
             keys: clients.KeyRing) -> AskFn:
    key_env = config.endpoints[entry.endpoint].key_env
    secrets = keys.secrets(config)

    def ask(system: str, prompt: str, data_model: type[BaseModel]) -> BaseModel:
        chat = clients.chat(name, entry, config, policy, keys, system_prompt=system)
        return clients.call_structured(chat, prompt, data_model,
                                       extra_body=entry.request_extra or None,
                                       key_env=key_env, secrets=secrets)

    return ask


def _translate(batch: Batch, all_ids: Sequence[str], cues: Mapping[str, Cue],
               limits: Mapping[str, int], system: str, ask: AskFn, *, stage: int = 0) -> list[Item]:
    """Stage 0 is the whole batch, 1 a half (spec §13.2), 2 a single cue."""
    try:
        result = ask(system, batch_prompt(batch, cues, limits), batch_model(batch.ids))
        return validate_partition(items_from(result), batch.ids)
    except ValueError as err:  # a PartitionError or pydantic's or the JSON decoder's error
        if stage >= 2 or len(batch.ids) == 1:
            raise TranslationFailed(
                f"the model couldn't translate cue {batch.ids[0]} in the required shape") \
                from err
        if stage == 0:
            parts = split_batch(batch, all_ids)
        else:
            parts = plan_batches(all_ids, batch.ids, size=1)
        items: list[Item] = []
        for part in parts:
            items += _translate(part, all_ids, cues, limits, system, ask, stage=stage + 1)
        return items


def translate_cues(source: Sequence[Cue], *, source_lang: str, target_track: str,
                   glossary: Glossary, ask: AskFn, only: Sequence[str] | None = None,
                   taken: set[str] | None = None, batch_size: int = 40,
                   on_batch: Callable[[int, int], None] | None = None) -> list[Cue]:
    cues = {c.id: c for c in source}
    all_ids = [c.id for c in source]
    system = system_prompt(source_lang, target_track, glossary)
    limits = item_limits(source, target_track)
    batches = plan_batches(all_ids, only, size=batch_size)
    items: list[Item] = []
    for n, batch in enumerate(batches, 1):
        items += _translate(batch, all_ids, cues, limits, system, ask)
        if on_batch is not None:
            on_batch(n, len(batches))
    return assemble(items, cues, target_track, set() if taken is None else taken)
