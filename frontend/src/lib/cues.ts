// Finding what plays now, and showing times (spec §20). The cue list and the caption overlay
// follow playback many times a second over up to about 2,000 cues (Review Focus 3), so every
// lookup is a binary search over cues sorted by start, which spec §12.1 guarantees.

import type { Row, SpokenWord, TrCue } from "@/types";

type Timed = { start_ms: number; end_ms: number };

/** The index of the item playing at `ms` (start ≤ ms < end), else -1. `items` are sorted by
 * start and never overlap. */
export function indexAt(items: readonly Timed[], ms: number): number {
  let lo = 0;
  let hi = items.length - 1;
  let found = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (items[mid].start_ms <= ms) {
      found = mid;
      lo = mid + 1;
    } else {
      hi = mid - 1;
    }
  }
  return found >= 0 && ms < items[found].end_ms ? found : -1;
}

/** The index in `words` of the word spoken at `ms`, among the row's own words ([i, j)), else -1. */
export function wordAt(words: readonly SpokenWord[], range: readonly [number, number] | null, ms: number): number {
  if (!range) return -1;
  const [i, j] = range;
  const k = indexAt(words.slice(i, j), ms);
  return k < 0 ? -1 : i + k;
}

/** Where each of the row's words is in its text, found in order: [start, end) character offsets,
 * or null for a word the text no longer has (a person edited it), and for every word after it. */
export function wordSpans(text: string, words: readonly SpokenWord[]): (readonly [number, number] | null)[] {
  const out: (readonly [number, number] | null)[] = [];
  let at = 0;
  let lost = false;
  for (const w of words) {
    const word = w.text.trim();
    const k = lost || !word ? -1 : text.indexOf(word, at);
    if (k < 0) {
      lost = lost || Boolean(word);
      out.push(null);
      continue;
    }
    out.push([k, k + word.length]);
    at = k + word.length;
  }
  return out;
}

/** A translation track's cues in time order, each once (one can span several rows). */
export function trackCues(rows: readonly Row[], track: string | null): TrCue[] {
  if (!track) return [];
  const seen = new Set<string>();
  const out: TrCue[] = [];
  for (const row of rows) {
    for (const c of row.tr[track]?.cues ?? []) {
      if (!seen.has(c.id)) {
        seen.add(c.id);
        out.push(c);
      }
    }
  }
  return out.sort((a, b) => a.start_ms - b.start_ms || a.end_ms - b.end_ms);
}

/** A time as m:ss.mmm, or h:mm:ss.mmm from an hour. */
export function formatTime(ms: number): string {
  const total = Math.max(0, Math.round(ms));
  const h = Math.floor(total / 3_600_000);
  const m = Math.floor(total / 60_000) % 60;
  const s = Math.floor(total / 1000) % 60;
  const frac = String(total % 1000).padStart(3, "0");
  const ss = String(s).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${ss}.${frac}` : `${m}:${ss}.${frac}`;
}
