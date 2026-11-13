import { describe, expect, it } from "vitest";

import { dropQueuedKeys, pageConnected } from "./shinyPage";

describe("what shiny.js has queued while there is no connection (spec §5.3)", () => {
  it("drops every queued message that carries a typed key, and keeps the rest", () => {
    const pending: unknown[] = [
      '{"method":"update","data":{"typed_key:shinyreact.default":{"endpoint":"lan","key":"x"}}}',
      '{"method":"update","data":{"edit:shinyreact.default":{"n":1}}}',
      '{"method":"update","data":{"typed_key:shinyreact.default":null}}',
    ];
    dropQueuedKeys({ $pendingMessages: pending });
    expect(pending).toEqual(['{"method":"update","data":{"edit:shinyreact.default":{"n":1}}}']);
  });

  it("does nothing, and never throws, where shiny.js's private field isn't there", () => {
    expect(() => dropQueuedKeys(undefined)).not.toThrow();
    expect(() => dropQueuedKeys({})).not.toThrow();
    expect(() => dropQueuedKeys({ $pendingMessages: "no" })).not.toThrow();
  });

  it("reads the connection from shinyapp, and assumes one where it can't tell", () => {
    expect(pageConnected({ isConnected: () => false })).toBe(false);
    expect(pageConnected({ isConnected: () => true })).toBe(true);
    expect(pageConnected(undefined)).toBe(true);
  });
});
