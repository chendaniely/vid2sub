// The tab's crash-recovery draft (spec §14.5, S34): unsaved edits live in the tab, and every
// request that changes the episode is also written to localStorage, so a tab that crashes or is
// closed can offer them back when the episode is opened again. The draft is the edits, undos and
// redos as they were sent, each with its request's number, replayed through the server's rules
// on Restore, so the rules exist once (§20). An edit that makes cues carries their ids (Decision
// 31, Dan's answer to the kickoff council), so the replay makes the same cues and the edits made
// to them land too; a step the server refused is dropped, so the draft holds only what was done,
// and a restored draft is cleared only once the server has done every step of it again. Each tab
// keeps its own draft, keyed by the heads the episode was opened at and the tab's id, held in
// sessionStorage: two tabs on one episode never write each other's, and opening an episode
// offers every tab's draft for its heads; restoring another tab's draft clears it (Decision 36).
// A Save or a pick moves the heads: the offers are worked out again for the new heads, so a draft
// is only ever offered on the versions its edits were made against, and this tab's own draft
// comes across (followHeads), less the steps a Save wrote (trimSaved). Every storage call is
// wrapped in try/catch: a private window or blocked site data throws, and the editor must work
// without it.

import { randomHex } from "@/lib/ids";
import type { EditOp } from "@/types";

export type DraftStep = ({ edit: EditOp } | { undo: true } | { redo: true }) & { n: number };
export type Draft = { v: 1; at: string; steps: DraftStep[] };
export type Offer = { key: string; draft: Draft };
export type DraftStorage = Pick<Storage, "getItem" | "setItem" | "removeItem" | "key" | "length">;
export type TabStorage = Pick<Storage, "getItem" | "setItem">;
/** A Restore under way: the draft it replays, and the requests whose answers are still due. */
export type Replay = { from: string; waiting: number[]; refused: number; total: number };

const PREFIX = "vid2sub.draft.";
const TAB = "vid2sub.tab";
const TAB_ID = /^t[0-9a-f]{8}$/;
let pageTab: string | null = null; // where sessionStorage is forbidden: this page's own

/** Every draft's key for these heads (track → rendition id) starts with this, in a fixed order. */
export function headsKey(heads: Record<string, string>): string {
  return `${PREFIX}${Object.keys(heads).sort().map((k) => `${k}=${heads[k]}`).join(",")};`;
}

/** One tab's draft for these heads. */
export function draftKey(heads: Record<string, string>, tab: string): string {
  return headsKey(heads) + tab;
}

/** localStorage, or null where the browser forbids it. */
export function draftStorage(): DraftStorage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

/** sessionStorage, which lives as long as the tab and survives a reload, or null. */
export function tabStorage(): TabStorage | null {
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

/** This tab's id, `t` and 8 hex digits: kept in sessionStorage, else made for this page. */
export function tabId(storage: TabStorage | null): string {
  try {
    const kept = storage?.getItem(TAB);
    if (kept && TAB_ID.test(kept)) return kept;
    if (storage) {
      const made = `t${randomHex(4)}`;
      storage.setItem(TAB, made);
      return made;
    }
  } catch {
    /* forbidden: an id for this page only */
  }
  pageTab ??= `t${randomHex(4)}`;
  return pageTab;
}

/** The draft under `key`, or null: none, junk, or storage that throws. */
export function loadDraft(storage: DraftStorage | null, key: string): Draft | null {
  try {
    const raw = storage?.getItem(key);
    if (!raw) return null;
    const draft = JSON.parse(raw) as Partial<Draft>;
    if (draft.v !== 1 || typeof draft.at !== "string" || !Array.isArray(draft.steps)) return null;
    if (!draft.steps.every((s) => typeof s?.n === "number")) return null;
    return draft.steps.length ? (draft as Draft) : null;
  } catch {
    return null;
  }
}

/** Every tab's draft for these heads, oldest first. */
export function offersFor(storage: DraftStorage | null, heads: Record<string, string>): Offer[] {
  const prefix = headsKey(heads);
  const out: Offer[] = [];
  try {
    for (let i = 0; storage && i < storage.length; i++) {
      const key = storage.key(i);
      const draft = key?.startsWith(prefix) ? loadDraft(storage, key) : null;
      if (key && draft) out.push({ key, draft });
    }
  } catch {
    return [];
  }
  return out.sort((a, b) => a.draft.at.localeCompare(b.draft.at));
}

/** Adds one step to the draft under `key`, started now if there is none. */
export function addStep(storage: DraftStorage | null, key: string, step: DraftStep, now: Date = new Date()): void {
  try {
    const draft = loadDraft(storage, key) ?? { v: 1, at: now.toISOString(), steps: [] };
    storage?.setItem(key, JSON.stringify({ ...draft, steps: [...draft.steps, step] }));
  } catch {
    /* full or forbidden: the edit still reaches the server, only the crash copy is lost */
  }
}

/** Takes request `n`'s step out: the server refused it, so it changed nothing to replay. */
export function dropStep(storage: DraftStorage | null, key: string, n: number): void {
  try {
    const draft = loadDraft(storage, key);
    if (!draft) return;
    const steps = draft.steps.filter((s) => s.n !== n);
    if (steps.length === draft.steps.length) return;
    if (steps.length) storage?.setItem(key, JSON.stringify({ ...draft, steps }));
    else storage?.removeItem(key);
  } catch {
    /* forbidden: there is no draft to change */
  }
}

/** Moves the draft under `from` to `to`, replacing whatever was there. */
export function moveDraft(storage: DraftStorage | null, from: string, to: string): void {
  try {
    const draft = loadDraft(storage, from);
    storage?.removeItem(from);
    if (draft) storage?.setItem(to, JSON.stringify(draft));
  } catch {
    /* forbidden: there is no draft to move */
  }
}

export function clearDraft(storage: DraftStorage | null, key: string): void {
  try {
    storage?.removeItem(key);
  } catch {
    /* nothing to clear where storage is forbidden */
  }
}

/** Takes out the steps with request count `upTo` or below: a Save wrote them. A draft with
 * nothing left is removed. Steps sent behind the Save (a higher count) stay (Decision 31). */
export function trimSaved(storage: DraftStorage | null, key: string, upTo: number): void {
  try {
    const draft = loadDraft(storage, key);
    if (!draft) return;
    const steps = draft.steps.filter((s) => s.n > upTo);
    if (steps.length === draft.steps.length) return;
    if (steps.length) storage?.setItem(key, JSON.stringify({ ...draft, steps }));
    else storage?.removeItem(key);
  } catch {
    /* forbidden: there is no draft to trim */
  }
}

/** The heads moved (a Save or a pick) from the key `from` to `to`: this tab's draft goes with
 * them, whole, then less what a Save has written (`savedUpTo`, 0 while none has been heard of).
 * An edit sent while the Save ran is in the draft by then and stays in it. */
export function followHeads(storage: DraftStorage | null, from: string, to: string, savedUpTo: number): void {
  if (from !== to) moveDraft(storage, from, to);
  trimSaved(storage, to, savedUpTo);
}

/** The Restore after the server's answer to request `n`, or null when `n` isn't one of its
 * steps. It is over once nothing is waiting: clean if nothing was refused. */
export function heard(replay: Replay, n: number, ok: boolean): Replay | null {
  if (!replay.waiting.includes(n)) return null;
  return { ...replay, waiting: replay.waiting.filter((w) => w !== n), refused: replay.refused + (ok ? 0 : 1) };
}
