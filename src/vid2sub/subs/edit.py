"""Edit operations on an episode's source track and its translations (spec §13.5, §20).

Pure, so the editor's server (Phase 2) and the Pages editor in Pyodide (Phase 4) share one set of
edit rules (spec §20). Every operation returns new `Tracks` and leaves its input alone, so undo is
a stack of old values. Pairing follows spec §13.5: a split re-points translations to both halves,
a merge concatenates the translations of its parts, a delete takes the id out of every `src`, and
an insert is untranslated. A re-pointed or merged translation keeps its old `src_sha` (or none),
so `translate_shape.stale_ids` reads it as stale and no flag is stored. Times are clamped to the
neighbours, never pushed into them (§12.1), and translations follow their source cues unless
detached (§13.4); an edit that would make a translation track overlap is refused. Word ranges and
flags follow the Phase 2 plan's Decision 3: text and time edits keep `w`, split and insert drop
it, merge joins two; a text edit drops `halluc` and a time edit drops `est`, since a person has
now checked them; an edited translation is marked `edited` (Decision 4), as `store.align_ids`
marks one edited outside. A new cue's id comes from the caller, who draws it (the page, with
`crypto.getRandomValues`), so the same edits replayed make the same cues and a crash draft's later
edits to them still land (Decision 31, Dan's answer to the kickoff council); an id that isn't
`model.new_cue_id`'s shape, or is taken, is refused and nothing changes.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from vid2sub.subs.model import Cue, TrackError, check_track
from vid2sub.subs.text import canonical

SOURCE = "source"  # the name `replace_all` gives the source track
_NEW_ID = re.compile(r"c[0-9a-f]{8}")  # the shape model.new_cue_id makes


class EditError(ValueError):
    """An edit that can't be made; the reason is fit to show."""


@dataclass(frozen=True)
class Tracks:
    source: tuple[Cue, ...]
    translations: Mapping[str, tuple[Cue, ...]]  # target track key → cues


def follow(source: Sequence[Cue], translation: Sequence[Cue]) -> tuple[Cue, ...]:
    """Each cue that isn't `detached` takes the span of its `src` cues (spec §13.4).

    A cue none of whose `src` cues is in the source keeps its times."""
    by_id = {c.id: c for c in source}
    out = []
    for c in translation:
        spans = [by_id[i] for i in c.src or () if i in by_id]
        if c.detached or not spans:
            out.append(c)
            continue
        start, end = min(s.start_ms for s in spans), max(s.end_ms for s in spans)
        out.append(c if (start, end) == (c.start_ms, c.end_ms)
                   else c.model_copy(update={"start_ms": start, "end_ms": end}))
    return tuple(sorted(out, key=lambda c: (c.start_ms, c.end_ms)))


def set_text(t: Tracks, cue_id: str, text: str) -> Tracks:
    i = _at(t.source, cue_id)
    c = t.source[i]
    new = c.model_copy(update={"text": _text(text), "flags": _without(c.flags, "halluc")})
    return _done(_splice(t.source, i, 1, new), t.translations)


def set_translation_text(t: Tracks, track: str, cue_id: str, text: str) -> Tracks:
    cues = _track(t, track)
    i = _at(cues, cue_id)
    c = cues[i]
    new = c.model_copy(update={"text": _text(text), "flags": _with(c.flags, "edited")})
    return _done(t.source, {**t.translations, track: _splice(cues, i, 1, new)})


def set_times(t: Tracks, cue_id: str, *, start_ms: int | None = None,
              end_ms: int | None = None) -> Tracks:
    """Clamped to the neighbours: no earlier than the previous cue's end, no later than the next
    cue's start."""
    i = _at(t.source, cue_id)
    c = t.source[i]
    lo, hi = _bounds(t.source, i)
    start = _clamp(c.start_ms if start_ms is None else start_ms, lo, hi)
    end = _clamp(c.end_ms if end_ms is None else end_ms, lo, hi)
    if start >= end:
        raise EditError("a cue must start before it ends, in the gap between its neighbours")
    new = c.model_copy(update={"start_ms": start, "end_ms": end,
                               "flags": _without(c.flags, "est")})
    return _done(_splice(t.source, i, 1, new), t.translations)


def nudge(t: Tracks, cue_id: str, delta_ms: int, *,
          edge: Literal["start", "end", "both"] = "both") -> Tracks:
    """Moves one edge, or the whole cue as a block that stops at its neighbours."""
    i = _at(t.source, cue_id)
    c = t.source[i]
    if edge == "start":
        return set_times(t, cue_id, start_ms=c.start_ms + delta_ms)
    if edge == "end":
        return set_times(t, cue_id, end_ms=c.end_ms + delta_ms)
    if edge != "both":
        raise EditError("a nudge moves the start, the end or both")
    lo, hi = _bounds(t.source, i)
    delta = max(delta_ms, lo - c.start_ms)
    if hi is not None:
        delta = min(delta, hi - c.end_ms)
    return set_times(t, cue_id, start_ms=c.start_ms + delta, end_ms=c.end_ms + delta)


def split(t: Tracks, cue_id: str, *, at_char: int, at_ms: int, ids: tuple[str, str],
          taken: set[str]) -> tuple[Tracks, tuple[str, str]]:
    """Two new cues from one, both `from` it; translations of it point at both halves.

    The halves take `ids`, in order, and `taken` gains them."""
    i = _at(t.source, cue_id)
    c = t.source[i]
    left = canonical(c.text[:at_char]) if 0 < at_char < len(c.text) else ""
    right = canonical(c.text[at_char:]) if left else ""
    if not left or not right:
        raise EditError("split inside the text, so both halves have some")
    if not c.start_ms < at_ms < c.end_ms:
        raise EditError("split at a time inside the cue")
    if len(ids) != 2:
        raise EditError("a split needs two new ids")
    _claim(taken, *ids)
    a = Cue(id=ids[0], start_ms=c.start_ms, end_ms=at_ms, text=left, from_=(c.id,),
            flags=c.flags)
    b = Cue(id=ids[1], start_ms=at_ms, end_ms=c.end_ms, text=right, from_=(c.id,),
            flags=c.flags)
    pairs = {c.id: (a.id, b.id)}
    translations = {k: tuple(_repoint(x, pairs) for x in v) for k, v in t.translations.items()}
    return _done(_splice(t.source, i, 1, a, b), translations), (a.id, b.id)


def merge_next(t: Tracks, cue_id: str, *, new_id: str, joined_ids: Mapping[str, str],
               taken: set[str]) -> tuple[Tracks, str]:
    """One new cue from a cue and the next; the translations of either part become one.

    The merged cue takes `new_id`; a translation track whose cues for the two parts are joined
    into one new cue takes that cue's id from `joined_ids` (track key → id), and a track that
    needs one and has none is refused. `taken` gains every id given."""
    i = _at(t.source, cue_id)
    if i + 1 >= len(t.source):
        raise EditError("the last cue has no next cue to merge with")
    a, b = t.source[i], t.source[i + 1]
    pairs = {a.id: (new_id,), b.id: (new_id,)}
    for k, v in t.translations.items():
        if k not in joined_ids and len(_parts(v, pairs)) > 1:
            raise EditError(f"merging joins the {k} track's translations, which needs a new id")
    _claim(taken, new_id, *joined_ids.values())
    m = Cue(id=new_id, start_ms=a.start_ms, end_ms=b.end_ms,
            text=canonical(a.text + "\n" + b.text),
            w=(a.w[0], b.w[1]) if a.w and b.w else None, from_=(a.id, b.id),
            flags=tuple(sorted(set(a.flags) | set(b.flags))))
    translations = {k: _merge_translations(v, pairs, joined_ids.get(k))
                    for k, v in t.translations.items()}
    return _done(_splice(t.source, i, 2, m), translations), m.id


def insert(t: Tracks, *, start_ms: int, end_ms: int, text: str, new_id: str,
           taken: set[str]) -> tuple[Tracks, str]:
    """A new, untranslated cue in a gap, with the id `new_id` (which `taken` gains); its end is
    clamped to the next cue's start."""
    body = _text(text)
    i = sum(1 for c in t.source if c.start_ms <= start_ms)
    if i and t.source[i - 1].end_ms > start_ms:
        raise EditError("there is already a cue at that time")
    start = max(start_ms, 0)
    end = end_ms if i == len(t.source) else min(end_ms, t.source[i].start_ms)
    if start >= end:
        raise EditError("a cue must start before it ends, in the gap between its neighbours")
    _claim(taken, new_id)
    new = Cue(id=new_id, start_ms=start, end_ms=end, text=body)
    return _done(_splice(t.source, i, 0, new), t.translations), new.id


def delete(t: Tracks, cue_id: str) -> Tracks:
    """The id leaves every `src`; a translation left with none is deleted (spec §13.5)."""
    i = _at(t.source, cue_id)
    gone = {cue_id: ()}
    translations = {}
    for k, v in t.translations.items():
        kept = []
        for x in v:
            y = _repoint(x, gone)
            if x.src and not y.src:
                continue
            kept.append(y)
        translations[k] = tuple(kept)
    return _done(_splice(t.source, i, 1), translations)


def detach(t: Tracks, track: str, cue_id: str, detached: bool) -> Tracks:
    """A detached translation keeps its own times; reattached, it follows its source again."""
    cues = _track(t, track)
    i = _at(cues, cue_id)
    new = cues[i].model_copy(update={"detached": detached})
    return _done(t.source, {**t.translations, track: _splice(cues, i, 1, new)})


def replace_all(t: Tracks, find: str, replace: str, *,
                tracks: Sequence[str]) -> tuple[Tracks, int]:
    """Plain, case-sensitive text across the named tracks (`"source"` is the source track);
    returns how many were replaced. A source cue changed drops `halluc`; a translation is
    marked `edited`."""
    if not find:
        raise EditError("find needs some text")
    source, translations, count = t.source, dict(t.translations), 0
    for name in dict.fromkeys(tracks):
        if name == SOURCE:
            source, n = _replace_in(source, find, replace, lambda f: _without(f, "halluc"))
        else:
            translations[name], n = _replace_in(_track(t, name), find, replace,
                                                lambda f: _with(f, "edited"))
        count += n
    return _done(source, translations), count


def _done(source: Sequence[Cue], translations: Mapping[str, Sequence[Cue]]) -> Tracks:
    """Translations follow the new source, and every track keeps the invariants (spec §12.1)."""
    out = Tracks(tuple(source), {k: follow(source, v) for k, v in translations.items()})
    for name, cues in ((SOURCE, out.source), *out.translations.items()):
        try:
            check_track(cues)
        except TrackError as e:
            raise EditError(f"the {name} track would break: {e}") from None
    return out


def _claim(taken: set[str], *ids: str) -> None:
    """New cues' ids come from the caller, so each is checked: `model.new_cue_id`'s shape, none
    twice, none taken. All of them join `taken`, or none does."""
    if not all(isinstance(i, str) and _NEW_ID.fullmatch(i) for i in ids):
        raise EditError("a new cue's id is c and 8 lowercase hex digits")
    if len(set(ids)) < len(ids) or any(i in taken for i in ids):
        raise EditError("a new cue's id is already in use; try again")
    taken.update(ids)


def _parts(cues: Sequence[Cue], pairs: Mapping[str, tuple[str, ...]]) -> list[Cue]:
    return [c for c in cues if c.src and any(i in pairs for i in c.src)]


def _merge_translations(cues: Sequence[Cue], pairs: Mapping[str, tuple[str, ...]],
                        joined_id: str | None) -> tuple[Cue, ...]:
    parts = _parts(cues, pairs)
    if len(parts) < 2:
        return tuple(_repoint(c, pairs) for c in cues)
    joined = Cue(id=joined_id, start_ms=min(p.start_ms for p in parts),
                 end_ms=max(p.end_ms for p in parts),
                 text=canonical("\n".join(p.text for p in parts)),
                 src=_mapped([i for p in parts for i in p.src or ()], pairs),
                 from_=tuple(p.id for p in parts),
                 flags=tuple(sorted({f for p in parts for f in p.flags})))
    first = cues.index(parts[0])
    rest = [c for c in cues if c not in parts]
    return tuple(rest[:first]) + (joined,) + tuple(rest[first:])


def _repoint(c: Cue, pairs: Mapping[str, tuple[str, ...]]) -> Cue:
    if not c.src or not any(i in pairs for i in c.src):
        return c
    return c.model_copy(update={"src": _mapped(c.src, pairs)})


def _mapped(src: Sequence[str], pairs: Mapping[str, tuple[str, ...]]) -> tuple[str, ...]:
    out: list[str] = []
    for i in src:
        for j in pairs.get(i, (i,)):
            if j not in out:
                out.append(j)
    return tuple(out)


def _replace_in(cues: Sequence[Cue], find: str, replace: str,
                flags: Callable[[tuple[str, ...]], tuple[str, ...]]) -> tuple[tuple[Cue, ...], int]:
    out, count = [], 0
    for c in cues:
        n = c.text.count(find)
        if not n:
            out.append(c)
            continue
        text = canonical(c.text.replace(find, replace))
        if not text:
            raise EditError(f"replacing would leave cue {c.id} empty: delete it instead")
        count += n
        out.append(c.model_copy(update={"text": text, "flags": flags(c.flags)}))
    return tuple(out), count


def _at(cues: Sequence[Cue], cue_id: str) -> int:
    for i, c in enumerate(cues):
        if c.id == cue_id:
            return i
    raise EditError(f"there is no cue {cue_id}")


def _track(t: Tracks, track: str) -> tuple[Cue, ...]:
    if track not in t.translations:
        raise EditError(f"there is no {track} track")
    return t.translations[track]


def _text(text: str) -> str:
    out = canonical(text)
    if not out:
        raise EditError("a cue needs text: delete it instead")
    return out


def _bounds(cues: Sequence[Cue], i: int) -> tuple[int, int | None]:
    lo = cues[i - 1].end_ms if i > 0 else 0
    hi = cues[i + 1].start_ms if i + 1 < len(cues) else None
    return lo, hi


def _clamp(ms: int, lo: int, hi: int | None) -> int:
    ms = max(ms, lo)
    return ms if hi is None else min(ms, hi)


def _splice(cues: Sequence[Cue], i: int, n: int, *new: Cue) -> tuple[Cue, ...]:
    return (*cues[:i], *new, *cues[i + n:])


def _without(flags: tuple[str, ...], flag: str) -> tuple[str, ...]:
    return tuple(f for f in flags if f != flag)


def _with(flags: tuple[str, ...], flag: str) -> tuple[str, ...]:
    return flags if flag in flags else (*flags, flag)
