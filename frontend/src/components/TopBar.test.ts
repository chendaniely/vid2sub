import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("./ThemeSwitch", () => ({ ThemeSwitch: () => null }));

import type { Status } from "@/types";

import { TopBar, endpointLabel } from "./TopBar";

describe("the top bar (spec §19.2)", () => {
  it("says which engine this is, from capabilities", () => {
    const caps = { engine: "local", generate: true, save: "disk", path_input: true } as const;
    expect(renderToStaticMarkup(createElement(TopBar, { capabilities: caps }))).toContain("Local engine");
    const browser = { ...caps, engine: "browser", save: "download" } as const;
    expect(renderToStaticMarkup(createElement(TopBar, { capabilities: browser }))).toContain("Browser editor");
  });

  it("names each endpoint's reach and key in words", () => {
    expect(endpointLabel({ name: "spark", local: true, key: "present", reachable: true })).toBe("spark: reachable, key set");
    expect(endpointLabel({ name: "spark", local: true, key: "missing", reachable: false })).toBe("spark: not reachable, key missing");
    expect(endpointLabel({ name: "spark", local: true, key: "none", reachable: null })).toBe("spark: checking…");
    expect(endpointLabel({ name: "openai", local: false, key: "present", reachable: null })).toBe("openai: cloud, key set");
  });

  it("shows an endpoint's name as text, never as markup", () => {
    const status: Status = { ffmpeg: true, endpoints: [{ name: "<img src=x onerror=alert(1)>", local: true, key: "none", reachable: true }] };
    const html = renderToStaticMarkup(createElement(TopBar, { status }));
    expect(html).not.toContain("<img");
    expect(html).toContain("&lt;img src=x onerror=alert(1)&gt;");
  });

  it("says when ffmpeg is missing", () => {
    expect(renderToStaticMarkup(createElement(TopBar, { status: { ffmpeg: false, endpoints: [] } }))).toContain("ffmpeg missing");
  });
});
