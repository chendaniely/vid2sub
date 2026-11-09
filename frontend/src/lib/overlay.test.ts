import { describe, expect, it } from "vitest";

import { captionLines, segments } from "./overlay";

describe("the caption overlay's markup (spec §6.3)", () => {
  it("keeps <i> and nothing else", () => {
    expect(segments("red bold <i>italic</i>")).toEqual([
      { text: "red bold ", italic: false },
      { text: "italic", italic: true },
    ]);
  });

  it("shows every other tag, entity and brace as the characters it is", () => {
    for (const text of ["<script>window.__pwned = 1</script>after", "a link &lt;b&gt; &amp;", "{\\an8}braces", "<img src=x onerror=alert(1)>", "<b>x</b>", "<u>x</u>", "<i class=a>x"]) {
      expect(segments(text)).toEqual([{ text, italic: false }]);
    }
  });

  it("treats <I> as <i>, ignores a stray close or a nested open, and runs an open <i> to the end", () => {
    expect(segments("<I>a</I>b")).toEqual([{ text: "a", italic: true }, { text: "b", italic: false }]);
    expect(segments("a</i>b")).toEqual([{ text: "ab", italic: false }]);
    expect(segments("<i>a<i>b</i>c")).toEqual([{ text: "ab", italic: true }, { text: "c", italic: false }]);
    expect(segments("<i>a\nb")).toEqual([{ text: "a\nb", italic: true }]);
    expect(segments("<i></i>")).toEqual([]);
  });
});

describe("what the overlay shows", () => {
  it("shows the source, the translation or both, leaving out a part with no cue", () => {
    expect(captionLines("source", "おはよう", "Good morning")).toEqual(["おはよう"]);
    expect(captionLines("translation", "おはよう", "Good morning")).toEqual(["Good morning"]);
    expect(captionLines("both", "おはよう", "Good morning")).toEqual(["おはよう", "Good morning"]);
    expect(captionLines("both", null, "Good morning")).toEqual(["Good morning"]);
    expect(captionLines("both", null, null)).toEqual([]);
  });
});
