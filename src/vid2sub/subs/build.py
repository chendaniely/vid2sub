"""Cues from words (spec §12).

Words are grouped into phrases at sentence ends and pauses, then packed greedily into cues that
fit two lines and seven seconds, preferring to cut after clause punctuation. Timing is then fixed
up: overlaps removed, gaps under half a second closed to two frames, short cues stretched to the
minimum and fast ones into the following gap. A segment whose words lost their times (Whisper's
temperature fallback, an audio-router lesson) is spread over its own span in proportion to
characters and flagged `est`. Suspected hallucinations are flagged `halluc`, never removed.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from itertools import pairwise

from vid2sub.subs import langs
from vid2sub.subs.lint import looks_hallucinated
from vid2sub.subs.model import Cue, Segment, Transcript, Word, new_cue_id
from vid2sub.subs.rules import CueRules, cps, reading_chars
from vid2sub.subs.text import CLAUSE_END, SENTENCE_END, canonical, strip_line_ends, wrap

HALLUC_COMPRESSION = 2.4  # Whisper's own thresholds
HALLUC_NO_SPEECH = 0.6
HALLUC_LOGPROB = -1.0
_TRAILING_QUOTES = "\"'”’」』)）"


@dataclass
class _Draft:
    start: int
    end: int
    text: str
    w: tuple[int, int] | None
    flags: set[str] = field(default_factory=set)


def _cjk(lang: str) -> bool:
    return lang in langs.LANGS and langs.get(lang).cjk


def _join(words: Sequence[Word]) -> str:
    return "".join(w.text for w in words).strip()


def _lines(text: str, rules: CueRules, lang: str) -> str:
    lines = wrap(text, rules.max_width, rules.max_lines) or [text]
    if lang in ("zh", "yue"):
        lines = strip_line_ends(lines)
    return "\n".join(lines)


def _fits(words: Sequence[Word], rules: CueRules) -> bool:
    return (words[-1].end_ms - words[0].start_ms <= rules.max_ms
            and wrap(_join(words), rules.max_width, rules.max_lines) is not None)


def _ends(word: Word, chars: frozenset[str]) -> bool:
    text = word.text.rstrip().rstrip(_TRAILING_QUOTES)
    return bool(text) and text[-1] in chars


Item = tuple[int, Word]


def _phrases(items: list[Item], rules: CueRules) -> list[list[Item]]:
    phrases: list[list[Item]] = []
    cur: list[Item] = []
    for item in items:
        if cur:
            prev = cur[-1][1]
            if item[1].start_ms - prev.end_ms > rules.pause_ms or _ends(prev, SENTENCE_END):
                phrases.append(cur)
                cur = []
        cur.append(item)
    if cur:
        phrases.append(cur)
    return phrases


def _pack(phrase: list[Item], rules: CueRules) -> list[list[Item]]:
    groups: list[list[Item]] = []
    cur: list[Item] = []
    for item in phrase:
        candidate = cur + [item]
        if not cur or _fits([w for _, w in candidate], rules):
            cur = candidate
            continue
        lowest = max(len(cur) // 2, 1)
        cut = next((i for i in range(len(cur) - 1, lowest - 1, -1)
                    if _ends(cur[i - 1][1], CLAUSE_END)), None)
        if cut is not None:
            groups.append(cur[:cut])
            cur = cur[cut:] + [item]
            if not _fits([w for _, w in cur], rules):
                groups.append(cur[:-1])
                cur = [item]
        else:
            groups.append(cur)
            cur = [item]
    if cur:
        groups.append(cur)
    return groups


def _unaligned(seg: Segment, rules: CueRules, lang: str) -> list[_Draft]:
    text = canonical(seg.text).replace("\n", " ").strip()
    if not text:
        return []
    cjk = _cjk(lang)
    tokens = list(text) if cjk else text.split(" ")
    joiner = "" if cjk else " "
    runs: list[list[str]] = []
    cur: list[str] = []
    for tok in tokens:
        candidate = cur + [tok]
        if cur and wrap(joiner.join(candidate), rules.max_width, rules.max_lines) is None:
            runs.append(cur)
            cur = [tok]
        else:
            cur = candidate
    if cur:
        runs.append(cur)
    span = max(seg.end_ms - seg.start_ms, 1)
    total_chars = sum(reading_chars(joiner.join(r)) for r in runs) or 1

    def too_long(run: list[str]) -> bool:
        return span * reading_chars(joiner.join(run)) / total_chars > rules.max_ms

    todo = runs
    runs = []
    while todo:
        run = todo.pop(0)
        if len(run) > 1 and too_long(run):
            half = len(run) // 2
            todo[:0] = [run[:half], run[half:]]
        else:
            runs.append(run)
    pieces = [p.strip() for p in (joiner.join(r) for r in runs) if p.strip()]
    total = sum(reading_chars(p) for p in pieces) or 1
    drafts: list[_Draft] = []
    t = seg.start_ms
    for i, piece in enumerate(pieces):
        last = i == len(pieces) - 1
        end = seg.end_ms if last else t + round(span * reading_chars(piece) / total)
        drafts.append(_Draft(t, max(end, t + 1), _lines(piece, rules, lang), None, {"est"}))
        t = end
    return drafts


def _in_speech(t: int, speech: Sequence[tuple[int, int]]) -> bool:
    return any(s <= t < e for s, e in speech)


def _suspect(draft: _Draft, seg: Segment, words: Sequence[Word], lang: str,
             speech: Sequence[tuple[int, int]] | None) -> bool:
    if looks_hallucinated(draft.text, lang):
        return True
    if seg.compression_ratio is not None and seg.compression_ratio > HALLUC_COMPRESSION:
        return True
    if (seg.no_speech_prob is not None and seg.avg_logprob is not None
            and seg.no_speech_prob > HALLUC_NO_SPEECH and seg.avg_logprob < HALLUC_LOGPROB):
        return True
    if speech is not None:
        if not words:
            return not _in_speech((draft.start + draft.end) // 2, speech)
        outside = sum(1 for w in words if not _in_speech((w.start_ms + w.end_ms) // 2, speech))
        return outside * 2 > len(words)
    return False


def _fix_timing(drafts: list[_Draft], rules: CueRules) -> None:
    drafts.sort(key=lambda d: (d.start, d.end))
    for i, d in enumerate(drafts):
        nxt = drafts[i + 1].start if i + 1 < len(drafts) else None
        limit = nxt - rules.min_gap_ms if nxt is not None else None
        if nxt is not None and limit is not None and (
                d.end > limit or nxt - d.end < rules.close_gap_ms):
            d.end = limit
        if d.end - d.start < rules.min_ms:
            want = d.start + rules.min_ms
            d.end = want if limit is None else max(d.end, min(want, limit))
        if cps(d.text, d.end - d.start) > rules.cps:
            want = d.start + min(rules.max_ms, round(reading_chars(d.text) * 1000 / rules.cps))
            d.end = max(d.end, want if limit is None else min(want, limit))
        if d.end <= d.start:
            d.end = d.start + 1
    for d in drafts:  # last: only ever shortens, so gaps only grow
        d.end = min(d.end, d.start + rules.max_ms)


def _untangle(drafts: list[_Draft], rules: CueRules) -> None:
    """Last resort for cues that start together: keep the minimum gap between neighbours."""
    for a, b in pairwise(drafts):
        if b.start < a.end + rules.min_gap_ms:
            if b.start - rules.min_gap_ms > a.start:
                a.end = b.start - rules.min_gap_ms
            else:
                b.start = a.end + rules.min_gap_ms
        b.end = max(b.end, b.start + 1)


def build_cues(transcript: Transcript, rules: CueRules, *,
               speech: Sequence[tuple[int, int]] | None = None,
               taken: set[str] | None = None) -> list[Cue]:
    lang = transcript.language
    drafts: list[_Draft] = []
    index = 0
    for seg in transcript.segments:
        if not seg.words:
            for d in _unaligned(seg, rules, lang):
                if _suspect(d, seg, (), lang, speech):
                    d.flags.add("halluc")
                drafts.append(d)
            continue
        items = [(index + k, w) for k, w in enumerate(seg.words)]
        index += len(seg.words)
        for phrase in _phrases(items, rules):
            for group in _pack(phrase, rules):
                ws = [w for _, w in group]
                text = _lines(_join(ws), rules, lang)
                d = _Draft(ws[0].start_ms, max(ws[-1].end_ms, ws[0].start_ms + 1), text,
                           (group[0][0], group[-1][0] + 1))
                if _suspect(d, seg, ws, lang, speech):
                    d.flags.add("halluc")
                drafts.append(d)
    drafts = [d for d in drafts if d.text.strip()]
    _fix_timing(drafts, rules)
    _untangle(drafts, rules)
    taken = set() if taken is None else taken
    return [Cue(id=new_cue_id(taken), start_ms=d.start, end_ms=d.end, text=d.text, w=d.w,
                flags=tuple(sorted(d.flags))) for d in drafts]
