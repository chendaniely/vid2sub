// What Retranslate names and says (spec §13.4, §20; S30). It names the selected cue, or the
// selection: every cue from the anchor (where Shift+click or Shift+↑/↓ started) to the selected
// one. "Retranslate stale" names none, and the server redoes every stale or untranslated cue,
// never one a person edited. The server says whether it ran and how many translation cues
// changed: nothing changed on a stale request that ran means nothing was stale; a request that
// failed has the server's own notice.

import type { Notice, Row } from "@/types";

/** The selected rows, [first, last], or null with none selected. */
export function selectionRange(rows: readonly Row[], selected: number, anchor: string | null): [number, number] | null {
  if (selected < 0 || selected >= rows.length) return null;
  const at = anchor === null ? -1 : rows.findIndex((r) => r.id === anchor);
  if (at < 0) return [selected, selected];
  return [Math.min(at, selected), Math.max(at, selected)];
}

/** The source cue ids of the selected rows, in order. */
export function selectedIds(rows: readonly Row[], range: [number, number] | null): string[] {
  return range ? rows.slice(range[0], range[1] + 1).map((r) => r.id) : [];
}

/** The notice for a retranslation that came back, or null when the server's error says it. */
export function retranslateNotice({ ok, changed, added }: { ok: boolean; changed: number; added: number }, label: string, stale: boolean): Notice | null {
  if (!ok) return null;
  if (changed > 0 && added === 0) return { kind: "info", text: `Dropped ${changed} ${label} ${changed === 1 ? "cue: its source cue is" : "cues: their source cues are"} gone` };
  if (changed > 0) return { kind: "info", text: `Retranslated ${changed} ${label} ${changed === 1 ? "cue" : "cues"}` };
  if (stale) return { kind: "info", text: `Nothing to retranslate: no ${label} cue is stale or untranslated, apart from those you edited` };
  return null;
}
