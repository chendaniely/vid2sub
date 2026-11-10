import { afterEach, describe, expect, it, vi } from "vitest";

import type { Row } from "@/types";

import { newCueIds, randomHex, shownIds } from "./ids";

afterEach(() => vi.restoreAllMocks());

describe("new cues' ids, drawn by the page (Decision 31)", () => {
  it("have the shape the server's new_cue_id makes", () => {
    for (const id of newCueIds(20, new Set())) expect(id).toMatch(/^c[0-9a-f]{8}$/);
    expect(randomHex(4)).toMatch(/^[0-9a-f]{8}$/);
  });

  it("come from crypto.getRandomValues, and are drawn again when one is known or drawn twice", () => {
    const draws = [[0, 0, 0, 1], [0, 0, 0, 1], [0, 0, 0, 2], [0, 0, 0, 3]];
    const spy = vi.spyOn(crypto, "getRandomValues").mockImplementation((a) => {
      (a as Uint8Array).set(draws.shift() ?? [9, 9, 9, 9]);
      return a;
    });
    expect(newCueIds(2, new Set(["c00000002"]))).toEqual(["c00000001", "c00000003"]);
    expect(spy).toHaveBeenCalledTimes(4);
  });

  it("know every id the view shows, translations' included", () => {
    const row = { id: "ca0000001", tr: { en: { cues: [{ id: "cb0000001" }], flags: [] }, ja: { cues: [], flags: ["untranslated"] } } };
    expect(shownIds([row as unknown as Row])).toEqual(new Set(["ca0000001", "cb0000001"]));
  });
});
