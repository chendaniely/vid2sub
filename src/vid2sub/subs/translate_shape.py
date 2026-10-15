"""The shape of translation: batches, per-batch schemas, partitions and staleness (spec §13).

Pure, so the CLI, the editor (M2) and Pages (M4) share it. A batch is a run of source cues that
are contiguous in the track, with read-only context on both sides. The model answers with items,
each covering one or more adjacent source cues, because Japanese→English often reorders across
cues. The schema is built per batch with the batch's ids as a Literal, so llama.cpp's grammar can
only produce real ids; the partition check then makes sure every id is covered once, in order.
A translation records its source cues' ids and a hash of their text, so a source edit marks it
stale.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field, create_model

from vid2sub.subs import langs, naming
from vid2sub.subs.model import Cue, new_cue_id
from vid2sub.subs.rules import rules_for, width_chars
from vid2sub.subs.text import canonical, strip_line_ends, wrap


@dataclass(frozen=True)
class Batch:
    ids: tuple[str, ...]
    before: tuple[str, ...]
    after: tuple[str, ...]


@dataclass(frozen=True)
class Item:
    src: tuple[str, ...]
    text: str


class PartitionError(ValueError):
    pass


def plan_batches(all_ids: Sequence[str], selected: Sequence[str] | None = None, *,
                 size: int = 40, context: int = 5) -> list[Batch]:
    order = {cid: i for i, cid in enumerate(all_ids)}
    wanted = None if selected is None else set(selected)
    chosen = [cid for cid in all_ids if wanted is None or cid in wanted]
    runs: list[list[str]] = []
    cur: list[str] = []
    for cid in chosen:
        if cur and order[cid] != order[cur[-1]] + 1:
            runs.append(cur)
            cur = []
        cur.append(cid)
    if cur:
        runs.append(cur)
    batches = []
    for run in runs:
        for k in range(0, len(run), size):
            part = run[k:k + size]
            first, last = order[part[0]], order[part[-1]]
            batches.append(Batch(tuple(part), tuple(all_ids[max(0, first - context):first]),
                                 tuple(all_ids[last + 1:last + 1 + context])))
    return batches


def split_batch(batch: Batch, all_ids: Sequence[str], *, context: int = 5) -> list[Batch]:
    if len(batch.ids) <= 1:
        return [batch]
    mid = math.ceil(len(batch.ids) / 2)
    return (plan_batches(all_ids, batch.ids[:mid], size=mid, context=context)
            + plan_batches(all_ids, batch.ids[mid:], size=mid, context=context))


def batch_model(ids: Sequence[str]) -> type[BaseModel]:
    src = Literal[tuple(ids)]  # type: ignore[valid-type]
    item = create_model("TranslationItem", src=(list[src], Field(min_length=1)),
                        text=(str, ...))
    return create_model("TranslationBatch", items=(list[item], Field(min_length=1)))


def items_from(result: BaseModel) -> list[Item]:
    return [Item(tuple(it.src), it.text) for it in result.items]  # type: ignore[attr-defined]


def validate_partition(items: Sequence[Item], ids: Sequence[str]) -> list[Item]:
    flat = [cid for it in items for cid in it.src]
    if flat != list(ids):
        raise PartitionError("the items don't cover the batch's cues exactly once, in order")
    if any(not canonical(it.text) for it in items):
        raise PartitionError("a translation item is empty")
    return list(items)


def _target(target_track: str):
    info = naming.track(target_track)
    cjk = info.lang in langs.LANGS and langs.get(info.lang).cjk
    return info, rules_for(info.lang), cjk


def item_limits(cues: Sequence[Cue], target_track: str) -> dict[str, int]:
    _, rules, cjk = _target(target_track)
    by_width = rules.max_lines * width_chars(rules, cjk)
    return {c.id: max(1, int(min(by_width, rules.cps * (c.end_ms - c.start_ms) / 1000)))
            for c in cues}


def src_sha(texts: Sequence[str]) -> str:
    return hashlib.sha256("\x1f".join(texts).encode()).hexdigest()[:12]


def assemble(items: Sequence[Item], source: Mapping[str, Cue], target_track: str,
             taken: set[str]) -> list[Cue]:
    info, rules, _ = _target(target_track)
    out = []
    for it in items:
        srcs = [source[cid] for cid in it.src]
        text = canonical(it.text)
        lines = wrap(text, rules.max_width, rules.max_lines) or [text.replace("\n", " ")]
        if info.lang in ("zh", "yue"):
            lines = strip_line_ends(lines)
        out.append(Cue(id=new_cue_id(taken), start_ms=srcs[0].start_ms,
                       end_ms=srcs[-1].end_ms, text="\n".join(lines), src=it.src,
                       src_sha=src_sha([c.text for c in srcs])))
    return out


def stale_ids(translation: Sequence[Cue], source: Mapping[str, Cue]) -> set[str]:
    stale = set()
    for c in translation:
        gone = not c.src or any(cid not in source for cid in c.src)
        if gone or c.src_sha != src_sha([source[cid].text for cid in c.src]):
            stale.add(c.id)
    return stale


def untranslated(source_ids: Sequence[str], translation: Sequence[Cue]) -> list[str]:
    covered = {cid for c in translation for cid in (c.src or ())}
    return [cid for cid in source_ids if cid not in covered]
