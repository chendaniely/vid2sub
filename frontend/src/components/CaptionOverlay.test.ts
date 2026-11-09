import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { CaptionOverlay } from "./CaptionOverlay";

describe("the caption overlay (spec §6.3)", () => {
  it("makes an <i> from <i> and text of everything else", () => {
    const html = renderToStaticMarkup(createElement(CaptionOverlay, {
      lines: ["red <i>italic</i>", "<script>window.__pwned = 1</script><img src=x onerror=alert(1)>"],
    }));
    expect(html).toContain("red <i>italic</i>");
    expect(html).toContain("&lt;script&gt;window.__pwned = 1&lt;/script&gt;&lt;img src=x onerror=alert(1)&gt;");
    expect(html).not.toMatch(/<(script|img)\b/);
  });
});
