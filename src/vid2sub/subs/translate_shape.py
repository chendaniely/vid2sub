"""The shape of translation: batches, per-batch schemas, partitions and staleness (spec §13).

Pure, so the CLI, the editor (M2) and Pages (M4) share it. A batch is a run of source cues that
are contiguous in the track, with read-only context on both sides. The model answers with items,
each covering one or more adjacent source cues, because Japanese→English often reorders across
cues. The schema is built per batch with the batch's ids as a Literal, so llama.cpp's grammar can
only produce real ids; the partition check then makes sure every id is covered once, in order.
A translation records its source cues' ids and a hash of their text, so a source edit marks it
stale.

An item is split back over its source cues when it won't fit two lines, its cues are more than
`SPLIT_GAP_MS` apart, or it would be on screen longer than the longest duration (spec §13.4;
Dan, Q&A item 36, after M1's exit test showed 218-character English cues and one shown for 31 s
across a 27-second silence). Each cue gets a part in proportion to its share of the source text,
cut where the text may break: sentence and clause ends are preferred, weighed against the
distance from that mark (`BREAK_COST`). Each part is timed to its own cue and records only that
cue, so it goes stale on its own. With fewer places to break than cues, the parts go to runs of
cues between the widest gaps; text with nowhere to break stays whole (Dan, Q&A item 40). Reading
speed never splits a cue: `max_chars` is only asked of the model, and a cue that reads too fast
is a lint (§12.2; Dan, Q&A item 39). A part still too long for two lines is filled into more
lines of the width, never cut (§13.4; Dan, Q&A item 41).
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from itertools import pairwise
from typing import Literal

from pydantic import BaseModel, Field, create_model

from vid2sub.subs import langs, naming
from vid2sub.subs.model import Cue, new_cue_id
from vid2sub.subs.rules import CueRules, reading_chars, rules_for, width_chars
from vid2sub.subs.text import (
    CLAUSE_END,
    SENTENCE_END,
    breaks,
    canonical,
    fill,
    strip_line_ends,
    unwrap,
    width,
    wrap,
)

SPLIT_GAP_MS = 1000  # source cues further apart than this never share a translation cue
# What a cut costs at each kind of break, on top of its distance from where the source's
# proportions put it (in parts' average lengths): a sentence end just under half a part away
# still beats a word break exactly there, a clause end just under a quarter of a part away.
BREAK_COST = {"sentence": 0.0, "clause": 0.25, "word": 0.5}
_UNFIT = 1000.0  # a part that won't fit two lines: chosen only when no cut avoids one
_CLOSERS = "\"'”’」』）)]】》〉"  # closing quotes and brackets after a sentence's end


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


def _kind(left: str) -> str:
    """The break after `left`: a sentence's end, a clause's, or only a word's."""
    last = left.rstrip().rstrip(_CLOSERS)[-1:]
    if last and last in SENTENCE_END:
        return "sentence"
    return "clause" if last and last in CLAUSE_END else "word"


def _groups(cues: Sequence[Cue], count: int) -> list[list[Cue]]:
    """`cues` in at most `count` runs, cut at the widest gaps first: one cue a run when the text
    has places enough to break."""
    gaps = sorted(range(1, len(cues)), key=lambda i: -(cues[i].start_ms - cues[i - 1].end_ms))
    cuts = sorted(gaps[:count - 1])
    return [list(cues[a:b]) for a, b in zip([0, *cuts], [*cuts, len(cues)], strict=True)]


def _cut(text: str, weights: Sequence[int], rules: CueRules) -> list[str]:
    """`text` in len(weights) parts, each as near its share of `weights` as the breaks allow
    (the text has at least len(weights) - 1 places to break). The cuts are chosen together, by
    dynamic programming over the break points: first so every part fits two lines where any
    choice can, then by each cut's distance from its mark, in parts' average lengths, plus its
    BREAK_COST."""
    points = breaks(text)
    n = len(weights)
    size = len(text) / n
    marks = [len(text) * sum(weights[:k + 1]) / (sum(weights) or 1) for k in range(n - 1)]
    kinds = [BREAK_COST[_kind(text[:end])] for end, _ in points]
    widest = rules.max_lines * rules.max_width + 1  # two full lines and the space between

    @cache
    def unfit(start: int, end: int) -> float:
        part = text[start:end]
        if width(part) > widest or not wrap(part, rules.max_width, rules.max_lines):
            return _UNFIT
        return 0.0

    def step(k: int, j: int) -> float:
        return abs(points[j][0] - marks[k]) / size + kinds[j]

    # best[j]: the cheapest first cuts whose last is at points[j], as (cost, their indices)
    best = {j: (step(0, j) + unfit(0, end), (j,)) for j, (end, _) in enumerate(points)}
    for k in range(1, n - 1):
        following: dict[int, tuple[float, tuple[int, ...]]] = {}
        for j, (end, _) in enumerate(points):
            options = [(cost + step(k, j) + unfit(points[i][1], end), path + (j,))
                       for i, (cost, path) in best.items() if i < j]
            if options:
                following[j] = min(options)
        best = following
    _, path = min((cost + unfit(points[p[-1]][1], len(text)), p) for cost, p in best.values())
    starts = [0] + [points[j][1] for j in path]
    ends = [points[j][0] for j in path] + [len(text)]
    return [text[a:b].strip() for a, b in zip(starts, ends, strict=True)]


def _too_big(text: str, cues: Sequence[Cue], rules: CueRules) -> bool:
    """Too much for one subtitle: more than two lines, across a silence, or too long on screen."""
    return (wrap(text, rules.max_width, rules.max_lines) is None
            or any(b.start_ms - a.end_ms > SPLIT_GAP_MS for a, b in pairwise(cues))
            or cues[-1].end_ms - cues[0].start_ms > rules.max_ms)


def split_items(items: Sequence[Item], source: Mapping[str, Cue],
                target_track: str) -> list[Item]:
    """Each item longer than two lines, spread over cues more than SPLIT_GAP_MS apart or longer
    than the longest duration, split back over its source cues: one item per cue, or, when the
    text has fewer places to break than it has cues, per run of cues between the widest gaps.
    Text that can't break at all stays one item."""
    _, rules, _ = _target(target_track)
    out: list[Item] = []
    for it in items:
        cues = [source[cid] for cid in it.src]
        text = unwrap(it.text)
        groups = _groups(cues, len(breaks(text)) + 1)
        if len(cues) < 2 or len(groups) < 2 or not _too_big(text, cues, rules):
            out.append(it)
            continue
        parts = _cut(text, [sum(reading_chars(c.text) for c in g) for g in groups], rules)
        out += [Item(tuple(c.id for c in g), part)
                for g, part in zip(groups, parts, strict=True)]
    return out


def src_sha(texts: Sequence[str]) -> str:
    return hashlib.sha256("\x1f".join(texts).encode()).hexdigest()[:12]


def assemble(items: Sequence[Item], source: Mapping[str, Cue], target_track: str,
             taken: set[str]) -> list[Cue]:
    info, rules, _ = _target(target_track)
    out = []
    for it in items:
        srcs = [source[cid] for cid in it.src]
        text = canonical(it.text)
        lines = wrap(text, rules.max_width, rules.max_lines) or fill(text, rules.max_width)
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
