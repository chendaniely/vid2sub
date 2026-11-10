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

  it("says a retranslation's track can't be edited and other edits apply when it finishes (Task 17, I-2)", () => {
    for (const busy of ["retranslating", null] as const) { // running, or waiting behind another call
      const html = renderToStaticMarkup(createElement(BusyNote, { busy, retranslating: "Japanese" }));
      expect(html).toContain("Retranslating the Japanese translation");
      expect(html).toContain("its lines can be edited when it finishes");
      expect(html).toContain("other edits apply then");
      expect(html).toContain('data-testid="retranslating-note"');
    }
    expect(renderToStaticMarkup(createElement(BusyNote, { busy: "retranslating", retranslating: null }))).toContain("other edits apply when it finishes");
  });

  it("says nothing when nothing is being made, or while another episode opens", () => {
    expect(renderToStaticMarkup(createElement(BusyNote, { busy: null }))).toBe("");
    // an edit made then names the old episode and is dropped: the note would say the reverse
    expect(renderToStaticMarkup(createElement(BusyNote, { busy: "opening" }))).toBe("");
  });
});
