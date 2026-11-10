import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { EpisodeView } from "@/types";

import { ConflictPicker } from "./ConflictPicker";

const episode = {
  tracks: [{ key: "en", label: "English", role: "translation", head_by: null, in_conflict: true, all_stale: false }],
  conflicts: { en: [
    { rendition: "r_0000000000000001", by: "editor", at: null, cue_count: 2 },
    { rendition: "r_0000000000000002", by: "external", at: null, cue_count: 3 },
  ] },
  differences: { en: { cues: [
    { start_ms: 3600, end_ms: 6600, texts: ["<img src=x onerror=alert(1)>", "How's it going?"] },
    { start_ms: 7200, end_ms: 10200, texts: [null, "Yes, I'm fine"] },
  ], more: 12 } },
} as unknown as EpisodeView;

describe("the conflict picker (spec §14.4, S32)", () => {
  it("numbers the versions and shows each one's text where they differ, as text", () => {
    const html = renderToStaticMarkup(createElement(ConflictPicker, { episode, open: false, onClose: () => {}, onPick: () => {} }));
    expect(html).toContain("Version 1: Saved in the editor: 2 cues");
    expect(html).toContain("Version 2: Edited outside vid2sub: 3 cues");
    expect(html).toContain("&lt;img src=x onerror=alert(1)&gt;");
    expect(html).not.toContain("<img");
    expect(html).toContain("(not in this version)");
    expect(html).toContain("and 12 more cues differ");
  });
});
