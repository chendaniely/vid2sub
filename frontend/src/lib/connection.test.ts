import { describe, expect, it, vi } from "vitest";

import { LOST_MESSAGES, SIGN_IN_AGAIN, whyLost } from "./connection";

describe("a lost connection (Review Focus 5)", () => {
  it("asks for / once, with the cookie and nothing cached", async () => {
    const fetchFn = vi.fn(async () => ({ status: 200 }));
    await whyLost(fetchFn);
    expect(fetchFn).toHaveBeenCalledTimes(1);
    expect(fetchFn).toHaveBeenCalledWith("/", { cache: "no-store", credentials: "same-origin" });
  });

  it("a 401 means the engine restarted: open the new link", async () => {
    expect(await whyLost(async () => ({ status: 401 }))).toBe("signed-out");
    expect(LOST_MESSAGES["signed-out"]).toContain(SIGN_IN_AGAIN);
  });

  it("no answer means vid2sub isn't running", async () => {
    expect(await whyLost(async () => { throw new TypeError("Failed to fetch"); })).toBe("stopped");
  });

  it("any other answer means the engine is up: reload", async () => {
    expect(await whyLost(async () => ({ status: 200 }))).toBe("dropped");
  });

  it("says what the engine says to a page without its cookie", () => {
    expect(SIGN_IN_AGAIN).toBe("open the link vid2sub printed when it started");
  });
});
