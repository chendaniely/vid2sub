// New cues' ids, drawn by the page (the Phase 2 plan's Decision 31, Dan's answer to the kickoff
// council): a split, a merge or an insert sends the ids of the cues it makes, so the crash draft,
// replayed, makes the same cues and every later edit to them still lands. They have
// model.new_cue_id's shape, c and 8 lowercase hex digits, from crypto.getRandomValues; the server
// refuses one already taken, so a draw that meets an id the page can't see costs only a retry.

import type { Row } from "@/types";

/** `bytes` random bytes, as lowercase hex. */
export function randomHex(bytes: number): string {
  return Array.from(crypto.getRandomValues(new Uint8Array(bytes)), (b) => b.toString(16).padStart(2, "0")).join("");
}

/** `n` new cue ids: none of them in `known`, none twice. */
export function newCueIds(n: number, known: ReadonlySet<string>): string[] {
  const out: string[] = [];
  while (out.length < n) {
    const id = `c${randomHex(4)}`;
    if (!known.has(id) && !out.includes(id)) out.push(id);
  }
  return out;
}

/** Every cue id the view shows: the rows' own and their translations'. */
export function shownIds(rows: readonly Row[]): Set<string> {
  const out = new Set<string>();
  for (const row of rows) {
    out.add(row.id);
    for (const cell of Object.values(row.tr)) for (const c of cell.cues) out.add(c.id);
  }
  return out;
}
