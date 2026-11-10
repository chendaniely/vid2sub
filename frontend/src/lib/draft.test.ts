import { describe, expect, it } from "vitest";

import { addStep, clearDraft, draftKey, type DraftStorage, dropStep, headsKey, heard, loadDraft, moveDraft, offersFor, tabId } from "./draft";

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

  it("says when a Restore is over, and how many of its steps the server refused", () => {
    const start = { from: "k", waiting: [7, 8, 9], refused: 0, total: 3 };
    expect(heard(start, 3, true)).toBeNull(); // not one of its steps
    const one = heard(start, 7, true);
    const two = one && heard(one, 8, false);
    expect(two).toEqual({ from: "k", waiting: [9], refused: 1, total: 3 });
    expect(two && heard(two, 9, true)).toEqual({ from: "k", waiting: [], refused: 1, total: 3 });
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
