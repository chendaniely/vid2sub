import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { SettingsView } from "@/types";

import { SettingsDrawer } from "./SettingsDrawer";

const VIEW: SettingsView = {
  endpoints: [
    { name: "<b>spark</b>", base_url: "http://127.0.0.1:9/v1", local: true, key_env: "SPARK_API_KEY", key: "present", allow_typed_key: false, typed: false },
    { name: "lan", base_url: "http://127.0.0.1:10/v1", local: false, key_env: null, key: "present", allow_typed_key: true, typed: true },
  ],
  models: [{ name: "lan-gemma", task: "translate", catalog: null, endpoint: "lan", engine: null, model: "g", local: false }],
  defaults: { targets: ["en"], formats: ["srt"] },
  targets: [{ key: "en", label: "English" }, { key: "ja", label: "Japanese" }],
  rules: [{ lang: "en", label: "English", max_width: 42, max_lines: 2, cps: 20, min_ms: 833, max_ms: 7000 }],
  toml: '[defaults]\ntargets = ["en"]\nformats = ["srt"]\ncache_max_gb = 20.0\n',
};

function render(view: SettingsView = VIEW): string {
  const noop = () => undefined;
  return renderToStaticMarkup(createElement(SettingsDrawer, { open: true, onClose: noop, connected: true, settings: view, tests: { lan: { endpoint: "lan", n: 1, ok: true, models: ["<img src=x>"], more: 0, error: null } }, onTest: noop, onTypedKey: noop, onDefaults: noop }));
}

describe("the settings drawer (spec §19.2, S35)", () => {
  it("is the native dialog at the right edge (Decision 13)", () => {
    expect(render()).toMatch(/<dialog[^>]*data-side="right"/);
  });

  it("shows the endpoints, the models and every server's answer as text, never markup", () => {
    const html = render();
    expect(html).toContain("&lt;b&gt;spark&lt;/b&gt;");
    expect(html).toContain("&lt;img src=x&gt;");
    expect(html).not.toContain("<img");
    expect(html).toContain("lan-gemma");
  });

  it("offers a typed key only where vid2sub.toml allows one, in a field the browser won't keep", () => {
    const html = render();
    expect(html.match(/type="password"/g)).toHaveLength(1);
    expect(html).toMatch(/<input[^>]*type="password"[^>]*autoComplete="off"|<input[^>]*autoComplete="off"[^>]*type="password"/i);
    expect(html).toContain("key entered for this session");
    // review round 18c: no form to submit, password managers asked to leave it, no value attribute
    expect(html).not.toContain("<form");
    expect(html).toMatch(/<input[^>]*data-1p-ignore=""[^>]*data-lpignore="true"[^>]*data-bwignore=""/);
    expect(html).not.toMatch(/<input[^>]*type="password"[^>]*value=/);
    expect(html).toContain('data-testid="typed-key-lan"');
    expect(html).not.toContain('data-testid="typed-key-&lt;b&gt;spark&lt;/b&gt;"');
  });

  it("shows the cue rules read-only, saying they can't be changed yet, and Copy settings", () => {
    const html = render();
    expect(html).toContain("Cue rules can&#x27;t be changed yet.");
    expect(html).toContain("cache_max_gb = 20.0");
  });
});
