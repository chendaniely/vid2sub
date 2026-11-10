import { describe, expect, it } from "vitest";

import type { Row } from "@/types";

import { activeDescendant, countMatches, formatTime, indexAt, splitPoint, trackCues, wordAt, wordSpans } from "./cues";

const cues = [
  { start_ms: 0, end_ms: 1000 },
  { start_ms: 1500, end_ms: 3000 },
  { start_ms: 3000, end_ms: 4000 },
];

describe("what plays now (spec §20)", () => {
  it("finds the cue whose span holds the time, start included and end excluded", () => {
    expect(indexAt(cues, 0)).toBe(0);
    expect(indexAt(cues, 999)).toBe(0);
    expect(indexAt(cues, 1000)).toBe(-1); // a gap
    expect(indexAt(cues, 3000)).toBe(2); // one cue ends as the next starts
    expect(indexAt(cues, 4000)).toBe(-1);
    expect(indexAt([], 10)).toBe(-1);
  });

  it("finds a cue among 2,000 in a few steps", () => {
    const many = Array.from({ length: 2000 }, (_, i) => ({ start_ms: i * 3600, end_ms: i * 3600 + 3000 }));
    expect(indexAt(many, 1999 * 3600 + 10)).toBe(1999);
    expect(indexAt(many, 1234 * 3600 + 3100)).toBe(-1);
  });

  it("finds the spoken word among the row's own words only", () => {
    const words = [
      { start_ms: 0, end_ms: 400, text: " I" },
      { start_ms: 400, end_ms: 900, text: " am" },
      { start_ms: 900, end_ms: 1400, text: " here" },
    ];
    expect(wordAt(words, [1, 3], 450)).toBe(1);
    expect(wordAt(words, [1, 3], 100)).toBe(-1); // word 0 is another row's
    expect(wordAt(words, null, 450)).toBe(-1);
  });
});

describe("where each word is in a cue's text", () => {
  it("finds the words in order, past line breaks and punctuation", () => {
    const words = [" I", " am", " here,", " and"].map((text) => ({ start_ms: 0, end_ms: 1, text }));
    expect(wordSpans("I am here,\nand", words)).toEqual([[0, 1], [2, 4], [5, 10], [11, 14]]);
  });

  it("finds words with no spaces between them", () => {
    const words = ["おは", "よう"].map((text) => ({ start_ms: 0, end_ms: 1, text }));
    expect(wordSpans("おはよう", words)).toEqual([[0, 2], [2, 4]]);
  });

  it("stops at a word the text no longer has", () => {
    const words = [" I", " am", " here"].map((text) => ({ start_ms: 0, end_ms: 1, text }));
    expect(wordSpans("I was here", words)).toEqual([[0, 1], null, null]);
  });
});

describe("a translation track's cues", () => {
  const row = (id: string, tr: { id: string; start_ms: number; end_ms: number }[]): Row => ({
    id, n: 1, start_ms: 0, end_ms: 1, text: "", w: null, flags: [],
    tr: { en: { cues: tr.map((c) => ({ ...c, text: c.id, src: [], detached: false, flags: [] })), flags: [] } },
  });

  it("lists each cue once, in time order", () => {
    const a = { id: "a", start_ms: 0, end_ms: 2000 };
    const b = { id: "b", start_ms: 2000, end_ms: 3000 };
    expect(trackCues([row("1", [a]), row("2", [b]), row("3", [])], "en").map((c) => c.id)).toEqual(["a", "b"]);
    expect(trackCues([row("1", [a])], null)).toEqual([]);
    expect(trackCues([row("1", [a])], "ja")).toEqual([]);
  });
});

describe("times", () => {
  it("are minutes, seconds and milliseconds, with hours from an hour", () => {
    expect(formatTime(0)).toBe("0:00.000");
    expect(formatTime(3600)).toBe("0:03.600");
    expect(formatTime(61_005)).toBe("1:01.005");
    expect(formatTime(7_199_999)).toBe("1:59:59.999");
  });
});

describe("where a split falls without a caret", () => {
  it("is the space nearest the share of the text, never an end", () => {
    expect(splitPoint("I am here and there", 0.5)).toBe(9); // "I am here| and there"
    expect(splitPoint("I am here and there", 0.1)).toBe(1);
    expect(splitPoint("おはようございます", 0.5)).toBe(5); // no space: the point itself
    expect(splitPoint("ab", 0)).toBe(1);
    expect(splitPoint("ab", 1)).toBe(1);
  });
});

describe("counting what find would replace", () => {
  const rows: Row[] = [
    { id: "a", n: 1, start_ms: 0, end_ms: 1, text: "delighted, delighted", w: null, flags: [], tr: { en: { cues: [{ id: "x", start_ms: 0, end_ms: 2, text: "delighted", src: ["a", "b"], detached: false, flags: [] }], flags: [] } } },
    { id: "b", n: 2, start_ms: 1, end_ms: 2, text: "here", w: null, flags: [], tr: { en: { cues: [], flags: [] } } },
  ];

  it("counts each match in the chosen tracks, a translation spanning rows once", () => {
    expect(countMatches(rows, "ja", ["ja", "en"], "delighted")).toBe(3);
    expect(countMatches(rows, "ja", ["en"], "delighted")).toBe(1);
    expect(countMatches(rows, "ja", ["ja"], "Delighted")).toBe(0); // case-sensitive, as replace_all
    expect(countMatches(rows, "ja", ["ja"], "")).toBe(0);
  });
});

describe("the cue list's active descendant (S-13)", () => {
  const rows = [{ id: "ca0000001" }, { id: "ca0000002" }, { id: "ca0000003" }];

  it("names the selected row only while the row is in the page", () => {
    expect(activeDescendant(rows, 1, [0, 1, 2])).toBe("cue-ca0000002");
    expect(activeDescendant(rows, 2, [0, 1])).toBeUndefined(); // scrolled away: virtualised out
    expect(activeDescendant(rows, -1, [0, 1, 2])).toBeUndefined();
    expect(activeDescendant(rows, 3, [0, 1, 2, 3])).toBeUndefined();
  });
});
