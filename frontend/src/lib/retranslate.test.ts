import { describe, expect, it } from "vitest";

import type { Row } from "@/types";

import { retranslateNotice, selectedIds, selectionRange } from "./retranslate";

const row = (id: string): Row => ({ id, n: 1, start_ms: 0, end_ms: 1, text: id, w: null, flags: [], tr: {} });
const ROWS = ["c00000001", "c00000002", "c00000003", "c00000004"].map(row);

describe("what Retranslate names (spec §20)", () => {
  it("is the selected cue, or every cue from the anchor to it, either way round", () => {
    expect(selectionRange(ROWS, 1, null)).toEqual([1, 1]);
    expect(selectionRange(ROWS, 1, "c00000004")).toEqual([1, 3]);
    expect(selectionRange(ROWS, 3, "c00000002")).toEqual([1, 3]);
    expect(selectedIds(ROWS, [1, 3])).toEqual(["c00000002", "c00000003", "c00000004"]);
  });

  it("is nothing with no cue selected, and only the selected cue once the anchor's cue is gone", () => {
    expect(selectionRange(ROWS, -1, "c00000002")).toBeNull();
    expect(selectionRange(ROWS, 2, "c0000dead")).toEqual([2, 2]);
    expect(selectedIds(ROWS, null)).toEqual([]);
  });
});

describe("what a retranslation says", () => {
  it("counts the cues it changed, or says nothing was stale", () => {
    expect(retranslateNotice(2, "Japanese", true)).toEqual({ kind: "info", text: "Retranslated 2 Japanese cues" });
    expect(retranslateNotice(1, "Japanese", false)).toEqual({ kind: "info", text: "Retranslated 1 Japanese cue" });
    expect(retranslateNotice(0, "Japanese", true)).toEqual({ kind: "info", text: "Nothing to retranslate: no Japanese cue is stale or untranslated, apart from those you edited" });
  });

  it("leaves a failed request to the server's own notice", () => {
    expect(retranslateNotice(0, "Japanese", false)).toBeNull();
  });
});
