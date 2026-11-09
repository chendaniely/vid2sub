import type { Notice } from "@/types";

/** A notice on screen, with an id to dismiss it by. */
export type Shown = Notice & { id: number };

export const MAX_SHOWN = 3;

/** The notices after one more arrives: newest last, at most MAX_SHOWN, and a notice that repeats
 * the newest one isn't shown twice. Anything that isn't a well-formed notice is ignored, since it
 * comes over the wire. */
export function addNotice(shown: Shown[], notice: unknown, id: number): Shown[] {
  if (!isNotice(notice)) return shown;
  const last = shown[shown.length - 1];
  if (last && last.kind === notice.kind && last.text === notice.text) return shown;
  return [...shown, { kind: notice.kind, text: notice.text, id }].slice(-MAX_SHOWN);
}

export function dismissNotice(shown: Shown[], id: number): Shown[] {
  return shown.filter((n) => n.id !== id);
}

function isNotice(value: unknown): value is Notice {
  if (typeof value !== "object" || value === null) return false;
  const { kind, text } = value as Record<string, unknown>;
  return (kind === "info" || kind === "error") && typeof text === "string";
}
