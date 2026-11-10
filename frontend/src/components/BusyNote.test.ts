import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { BusyNote } from "./BusyNote";

describe("what an edit made while the sound is being made does (S-7)", () => {
  it("says edits made now apply when the sound is ready", () => {
    const html = renderToStaticMarkup(createElement(BusyNote, { busy: "playback" }));
    expect(html).toContain("apply when the sound is ready");
    expect(html).toContain('role="status"');
  });

  it("says nothing when nothing is being made", () => {
    expect(renderToStaticMarkup(createElement(BusyNote, { busy: null }))).toBe("");
  });
});
