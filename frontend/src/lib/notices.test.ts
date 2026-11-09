import { describe, expect, it } from "vitest";

import { MAX_SHOWN, addNotice, dismissNotice } from "./notices";

describe("notices", () => {
  it("shows the newest last and keeps at most three", () => {
    let shown = addNotice([], { kind: "info", text: "one" }, 1);
    for (const [i, text] of ["two", "three", "four"].entries()) {
      shown = addNotice(shown, { kind: "info", text }, i + 2);
    }
    expect(MAX_SHOWN).toBe(3);
    expect(shown.map((n) => n.text)).toEqual(["two", "three", "four"]);
  });

  it("doesn't show the same notice twice in a row", () => {
    const once = addNotice([], { kind: "error", text: "couldn't save" }, 1);
    expect(addNotice(once, { kind: "error", text: "couldn't save" }, 2)).toBe(once);
    expect(addNotice(once, { kind: "info", text: "couldn't save" }, 2)).toHaveLength(2);
  });

  it("ignores anything that isn't a notice, since it comes over the wire", () => {
    for (const junk of [null, "text", { kind: "warn", text: "x" }, { kind: "info", text: 3 }]) {
      expect(addNotice([], junk, 1)).toEqual([]);
    }
  });

  it("keeps only the fields it shows", () => {
    const [n] = addNotice([], { kind: "info", text: "ok", html: "<b>x</b>" }, 7);
    expect(n).toEqual({ kind: "info", text: "ok", id: 7 });
  });

  it("dismisses by id", () => {
    const shown = addNotice(addNotice([], { kind: "info", text: "a" }, 1), { kind: "info", text: "b" }, 2);
    expect(dismissNotice(shown, 1).map((n) => n.text)).toEqual(["b"]);
  });
});
