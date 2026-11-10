import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { Retranslate } from "./Retranslate";

const props = { label: "Japanese", selected: 1, busy: null, progress: null, pending: false, onSelected: () => undefined, onStale: () => undefined };
const html = (over: object) => renderToStaticMarkup(createElement(Retranslate, { ...props, ...over } as Parameters<typeof Retranslate>[0]));
const disabled = (markup: string, id: string) => new RegExp(`<button[^>]*disabled=""[^>]*data-testid="${id}"`).test(markup);

describe("when Retranslate can be pressed (Task 17's Spec review, I-1)", () => {
  it("can be, with a cue selected and nothing under way", () => {
    expect(disabled(html({}), "retranslate-selected")).toBe(false);
    expect(disabled(html({}), "retranslate-stale")).toBe(false);
    expect(disabled(html({ selected: 0 }), "retranslate-selected")).toBe(true);
  });

  it("can't be from the click until the result, before `busy` arrives or after", () => {
    const waiting = html({ pending: true });
    expect(disabled(waiting, "retranslate-selected") && disabled(waiting, "retranslate-stale")).toBe(true);
    expect(waiting).toContain("Waiting to retranslate…");
  });

  it("can't be while the server is retranslating, whatever the page has pending", () => {
    const running = html({ busy: "retranslating", progress: { done: 1, of: 3 } });
    expect(disabled(running, "retranslate-selected") && disabled(running, "retranslate-stale")).toBe(true);
    expect(running).toContain("Retranslating: 1 of 3 batches done…");
  });
});
