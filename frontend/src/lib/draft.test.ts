import { describe, expect, it } from "vitest";

import { addStep, clearDraft, draftKey, type DraftStep, type DraftStorage, dropStep, followHeads, headsKey, heard, loadDraft, moveDraft, offersFor, replayable, tabId, trimSaved, UNDO_STEPS } from "./draft";

function memory(): DraftStorage & { data: Map<string, string> } {
  const data = new Map<string, string>();
  return {
    data,
    getItem: (k) => data.get(k) ?? null,
    setItem: (k, v) => void data.set(k, v),
    removeItem: (k) => void data.delete(k),
    key: (i) => [...data.keys()][i] ?? null,
    get length() {
      return data.size;
    },
  };
}

const throwing: DraftStorage = {
  getItem: () => { throw new DOMException("denied", "SecurityError"); },
  setItem: () => { throw new DOMException("full", "QuotaExceededError"); },
  removeItem: () => { throw new DOMException("denied", "SecurityError"); },
  key: () => { throw new DOMException("denied", "SecurityError"); },
  get length(): number { throw new DOMException("denied", "SecurityError"); },
};

const AT = new Date("2026-10-24T09:30:00Z");
const HEADS = { en: "r_1", ja: "r_2" };
const EDIT = { edit: { op: "set_text", cue: "c0000000a", text: "occasion!" }, n: 4 } as const;
const INSERT = { edit: { op: "insert", start_ms: 4700, end_ms: 4900, text: "…", id: "c0000000b" }, n: 5 } as const;

describe("the crash-recovery draft (spec §14.5, S34)", () => {
  it("is keyed by the episode's heads, whatever their order, and the tab's id", () => {
    expect(draftKey({ ja: "r_2", en: "r_1" }, "t0000000a")).toBe("vid2sub.draft.en=r_1,ja=r_2;t0000000a");
    expect(draftKey(HEADS, "t0000000a")).toBe(draftKey({ ja: "r_2", en: "r_1" }, "t0000000a"));
    expect(draftKey(HEADS, "t0000000a")).not.toBe(draftKey(HEADS, "t0000000b"));
    expect(headsKey({ en: "r_1", ja: "r_3" })).not.toBe(headsKey(HEADS));
  });

  it("keeps each step as sent, in order, from when the first was made", () => {
    const s = memory();
    const key = draftKey(HEADS, "t0000000a");
    expect(loadDraft(s, key)).toBeNull();
    addStep(s, key, EDIT, AT);
    addStep(s, key, { undo: true, n: 6 }, new Date("2026-10-24T10:00:00Z"));
    addStep(s, key, INSERT);
    expect(loadDraft(s, key)).toEqual({ v: 1, at: "2026-10-24T09:30:00.000Z", steps: [EDIT, { undo: true, n: 6 }, INSERT] });
    clearDraft(s, key);
    expect(loadDraft(s, key)).toBeNull();
  });

  it("drops a step the server refused, and the draft once nothing is left", () => {
    const s = memory();
    const key = draftKey(HEADS, "t0000000a");
    addStep(s, key, EDIT, AT);
    addStep(s, key, INSERT, AT);
    dropStep(s, key, 5);
    expect(loadDraft(s, key)?.steps).toEqual([EDIT]);
    dropStep(s, key, 99);
    expect(loadDraft(s, key)?.steps).toEqual([EDIT]);
    dropStep(s, key, 4);
    expect(s.data.has(key)).toBe(false);
  });

  it("offers every tab's draft for the heads, oldest first, and no other heads' (Decision 31)", () => {
    const s = memory();
    addStep(s, draftKey(HEADS, "t0000000b"), INSERT, new Date("2026-10-24T11:00:00Z"));
    addStep(s, draftKey(HEADS, "t0000000a"), EDIT, AT);
    addStep(s, draftKey({ en: "r_1", ja: "r_3" }, "t0000000a"), EDIT, AT);
    s.data.set(`${headsKey(HEADS)}t0000000c`, "not json");
    expect(offersFor(s, HEADS).map((o) => o.key)).toEqual([draftKey(HEADS, "t0000000a"), draftKey(HEADS, "t0000000b")]);
    expect(offersFor(s, { en: "r_9" })).toEqual([]);
  });

  it("moves a draft to another key, replacing what was there", () => {
    const s = memory();
    const [from, to] = [draftKey(HEADS, "t0000000a"), draftKey({ en: "r_1", ja: "r_3" }, "t0000000a")];
    addStep(s, from, EDIT, AT);
    addStep(s, to, INSERT, AT);
    moveDraft(s, from, to);
    expect(s.data.has(from)).toBe(false);
    expect(loadDraft(s, to)?.steps).toEqual([EDIT]);
  });

  it("gives a tab one id for as long as it lives, kept in sessionStorage", () => {
    const session = memory();
    const id = tabId(session);
    expect(id).toMatch(/^t[0-9a-f]{8}$/);
    expect(tabId(session)).toBe(id);
    expect(tabId(memory())).not.toBe(id);
    expect(tabId(null)).toBe(tabId(throwing)); // forbidden: one id for the page
  });

  describe("a Restore, one step at a time, stopping at the first that no longer does what it did (Q&A item 54)", () => {
    const [a, b, c] = [EDIT, INSERT, { undo: true, n: 6 } as const] as DraftStep[];
    const start = { from: "k", next: [b, c], waiting: 7, done: 0, total: 3 };

    it("sends the next step once the one waited for took, and is clean after the last", () => {
      expect(heard(start, 3, true)).toBeNull(); // not the step it waits for
      const one = heard(start, 7, true);
      expect(one).toEqual({ replay: { from: "k", next: [c], waiting: null, done: 1, total: 3 }, send: b, end: null });
      const two = one && heard({ ...one.replay, waiting: 8 }, 8, true);
      expect(two).toEqual({ replay: { from: "k", next: [], waiting: null, done: 2, total: 3 }, send: c, end: null });
      const last = two && heard({ ...two.replay, waiting: 9 }, 9, true);
      expect(last).toEqual({ replay: { from: "k", next: [], waiting: null, done: 3, total: 3 }, send: null, end: "clean" });
    });

    it("stops at a step the server refused or that changed nothing, sending no more", () => {
      // `took` is false for both: the page passes ok && changed
      expect(heard(start, 7, false)).toEqual({ replay: { from: "k", next: [b, c], waiting: null, done: 0, total: 3 }, send: null, end: "stopped" });
      const later = heard({ ...start, next: [c], waiting: 8, done: 1 }, 8, false);
      expect(later).toEqual({ replay: { from: "k", next: [c], waiting: null, done: 1, total: 3 }, send: null, end: "stopped" });
      expect(a).toBe(EDIT);
    });
  });

  it("ignores junk and an empty draft", () => {
    const s = memory();
    for (const raw of ["not json", "{}", '{"v":2,"at":"x","steps":[]}', '{"v":1,"at":"x","steps":[]}', '{"v":1,"at":"x","steps":[{"undo":true}]}', "null"]) {
      s.data.set("k", raw);
      expect(loadDraft(s, "k")).toBeNull();
    }
  });

  it("never throws where storage is forbidden or full", () => {
    expect(() => addStep(throwing, "k", EDIT)).not.toThrow();
    expect(loadDraft(throwing, "k")).toBeNull();
    expect(offersFor(throwing, HEADS)).toEqual([]);
    expect(() => dropStep(throwing, "k", 4)).not.toThrow();
    expect(() => moveDraft(throwing, "k", "j")).not.toThrow();
    expect(() => clearDraft(throwing, "k")).not.toThrow();
    expect(loadDraft(null, "k")).toBeNull();
    expect(() => addStep(null, "k", EDIT)).not.toThrow();
  });
});

describe("the draft across a Save or a pick (the Task 16 Spec review's C-3, I-1)", () => {
  const OLD = draftKey(HEADS, "t0000000a");
  const NEW = draftKey({ en: "r_1", ja: "r_3" }, "t0000000a");
  const NUDGE = { edit: { op: "nudge", cue: "c0000000a", delta_ms: 100, edge: "both" }, n: 7 } as const;

  it("takes out the steps a Save wrote and keeps the ones sent behind it", () => {
    const s = memory();
    addStep(s, OLD, EDIT, AT); // n 4
    addStep(s, OLD, { undo: true, n: 6 }, AT);
    addStep(s, OLD, NUDGE, AT); // sent after the Save, n 7
    trimSaved(s, OLD, 6);
    expect(loadDraft(s, OLD)?.steps).toEqual([NUDGE]);
    trimSaved(s, OLD, 6);
    expect(loadDraft(s, OLD)?.steps).toEqual([NUDGE]);
    trimSaved(s, OLD, 7);
    expect(s.data.has(OLD)).toBe(false);
  });

  it("carries an edit sent while the Save ran to the new heads, whichever of the two news came first", () => {
    // the episode first (the Save's result not heard yet): everything comes across, then the
    // result trims what the Save wrote
    const first = memory();
    addStep(first, OLD, EDIT, AT);
    addStep(first, OLD, NUDGE, AT);
    followHeads(first, OLD, NEW, 0);
    expect(first.data.has(OLD)).toBe(false);
    expect(loadDraft(first, NEW)?.steps).toEqual([EDIT, NUDGE]);
    trimSaved(first, NEW, 6);
    expect(loadDraft(first, NEW)?.steps).toEqual([NUDGE]);
    // the result first, then the episode (both in one batch is this order too): the Save's steps
    // are gone before the draft moves, so a nudge it wrote is not applied a second time
    const second = memory();
    addStep(second, OLD, EDIT, AT);
    addStep(second, OLD, NUDGE, AT);
    trimSaved(second, OLD, 6);
    followHeads(second, OLD, NEW, 6);
    expect(loadDraft(second, NEW)?.steps).toEqual([NUDGE]);
  });

  it("leaves nothing under either key once everything was written", () => {
    const s = memory();
    addStep(s, OLD, EDIT, AT);
    followHeads(s, OLD, NEW, 4);
    expect(s.data.size).toBe(0);
  });

  it("never throws where storage is forbidden", () => {
    expect(() => trimSaved(throwing, "k", 3)).not.toThrow();
    expect(() => followHeads(throwing, "k", "j", 3)).not.toThrow();
    expect(() => followHeads(null, "k", "j", 3)).not.toThrow();
  });
});

describe("a retranslation in the draft (Task 17)", () => {
  const EDIT2 = { edit: { op: "set_text", cue: "c0000000b", text: "We meet." }, n: 8 } as const;
  const RT = { retranslate: true, n: 3 } as const;
  const UNDO = { undo: true, n: 9 } as const;
  const REDO = { redo: true, n: 10 } as const;
  // the ids the opened episode has: EDIT's cue, and the cues of EDIT2's and INSERT's targets come
  // from the edits themselves or are unknown (a retranslation made them)
  const KNOWN = new Set(["c0000000a", "c0000000b"]);
  const NEW_CUE = { edit: { op: "set_translation_text", track: "ja", cue: "c0000000f", text: "新訳" }, n: 20 } as const;

  it("is never replayed, so a restored draft never asks a model again", () => {
    expect(replayable([EDIT, RT, EDIT2], KNOWN)).toEqual([EDIT, EDIT2]);
  });

  it("still takes the undo that undid it, and the redo that redid it, so neither lands elsewhere", () => {
    const steps: DraftStep[] = [EDIT, RT, UNDO, EDIT2];
    expect(replayable(steps, KNOWN)).toEqual([EDIT, EDIT2]);
    expect(replayable([EDIT, RT, UNDO, REDO], KNOWN)).toEqual([EDIT]);
    expect(replayable([RT, EDIT, UNDO, { undo: true, n: 11 }, { undo: true, n: 12 }], KNOWN)).toEqual([EDIT, UNDO]);
    expect(replayable([EDIT, UNDO, REDO], KNOWN)).toEqual([EDIT, UNDO, REDO]);
    // a new edit clears what redo could bring back, on the server as here
    expect(replayable([RT, UNDO, EDIT2, REDO], KNOWN)).toEqual([EDIT2]);
  });

  it("follows the server's undo history only as far back as it keeps, 200 steps", () => {
    // E0, a retranslation, then E1 to E199, then 201 undos: the server keeps 200 steps, so E0
    // can't be undone and stays; Restore must keep it too (Task 17's review).
    const edits = Array.from({ length: 199 }, (_, i) => ({ edit: { op: "set_text", cue: "c0000000a", text: `${i + 1}` }, n: 100 + i }) as DraftStep);
    const undos = Array.from({ length: 201 }, (_, i) => ({ undo: true, n: 400 + i }) as DraftStep);
    const sent = replayable([EDIT, RT, ...edits, ...undos], KNOWN);
    expect(sent.filter((s) => "edit" in s)).toHaveLength(200);
    expect(sent.filter((s) => "undo" in s)).toHaveLength(199); // E199 to E1; never E0
    expect(UNDO_STEPS).toBe(200);
  });

  it("leaves out an edit to a cue the opened episode doesn't have, and the undo that took it back (Task 17's Spec review, C-2)", () => {
    // an edit, a retranslation, an edit to the cue it made, that edit undone: the undo would land
    // on the first edit if the second were not left out
    expect(replayable([EDIT, RT, NEW_CUE, { undo: true, n: 21 }], KNOWN)).toEqual([EDIT]);
    expect(replayable([EDIT, RT, NEW_CUE, { undo: true, n: 21 }, { redo: true, n: 22 }], KNOWN)).toEqual([EDIT]);
    expect(replayable([RT, NEW_CUE, EDIT2], KNOWN)).toEqual([EDIT2]);
  });

  it("knows the cues an edit it sends makes, so later edits to them are sent", () => {
    const made = { edit: { op: "insert", start_ms: 1, end_ms: 2, text: "…", id: "c0000000f" }, n: 19 } as const;
    expect(replayable([made, NEW_CUE], KNOWN)).toEqual([made, NEW_CUE]);
    // but not the cues of an edit that wasn't sent
    const skipped = { edit: { op: "split", cue: "c0000000e", at_char: 1, at_ms: 5, ids: ["c00000010", "c00000011"] }, n: 18 } as DraftStep;
    const onSplit = { edit: { op: "set_text", cue: "c00000010", text: "x" }, n: 19 } as DraftStep;
    expect(replayable([skipped, onSplit], KNOWN)).toEqual([]);
  });

  it("is dropped when the server says it changed nothing, and only that one", () => {
    const s = memory();
    const key = draftKey(HEADS, "t0000000a");
    for (const step of [EDIT, RT, { retranslate: true, n: 5 }, EDIT2] as DraftStep[]) addStep(s, key, step, AT);
    dropStep(s, key, 3);
    expect(loadDraft(s, key)?.steps).toEqual([EDIT, { retranslate: true, n: 5 }, EDIT2]);
    dropStep(s, key, 9);
    expect(loadDraft(s, key)?.steps).toEqual([EDIT, { retranslate: true, n: 5 }, EDIT2]);
    expect(() => dropStep(throwing, key, 5)).not.toThrow();
  });
});
