import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { Row } from "@/types";

import { CueRow } from "./CueRow";

const row: Row = {
  id: "ca0000001", n: 1, start_ms: 0, end_ms: 1000, text: "<b>bold</b> <img src=x onerror=alert(1)>", w: null, flags: [],
  tr: { en: { cues: [{ id: "cb0000001", start_ms: 0, end_ms: 1000, text: "<b>tr</b>", src: ["ca0000001"], detached: false, flags: [] }], flags: [] } },
};

describe("a cue's text, edited or not (spec §6.3)", () => {
  const props = { row, track: "en", current: false, selected: true, inRange: false, cell: "source" as const, trId: null, word: -1, words: [], total: 1, onPick: () => undefined, onDraft: () => undefined, onEditKey: () => undefined, editorRef: { current: null } };

  it("shows a cue and its translation as text, never as markup", () => {
    const html = renderToStaticMarkup(createElement(CueRow, { ...props, editing: null }));
    expect(html).not.toContain("<b>");
    expect(html).not.toContain("<img");
    expect(html).toContain("&lt;b&gt;bold&lt;/b&gt;");
    expect(html).toContain("&lt;b&gt;tr&lt;/b&gt;");
  });

  it("holds the text being edited as a text box's value", () => {
    const editing = { id: row.id, cell: "source" as const, trId: null, track: null, text: "<b>draft</b>" };
    const html = renderToStaticMarkup(createElement(CueRow, { ...props, editing }));
    expect(html).not.toContain("<b>draft");
    expect(html).toContain("&lt;b&gt;draft&lt;/b&gt;</textarea>");
  });
});
