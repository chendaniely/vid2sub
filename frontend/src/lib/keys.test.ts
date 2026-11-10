import { describe, expect, it } from "vitest";

import { type KeyLike, actionFor } from "./keys";

const press = (key: string, more: Partial<KeyLike> = {}): KeyLike => ({
  key, ctrlKey: false, metaKey: false, shiftKey: false, altKey: false, ...more,
});

describe("navigate mode (spec §20)", () => {
  it("plays, shuttles, moves between cues and cells, and sets times to the playhead", () => {
    expect(actionFor(press(" "), "navigate")).toEqual({ kind: "play-pause" });
    expect(actionFor(press("j"), "navigate")).toEqual({ kind: "back" });
    expect(actionFor(press("K"), "navigate")).toEqual({ kind: "pause" }); // Caps Lock on
    expect(actionFor(press("l"), "navigate")).toEqual({ kind: "play" });
    expect(actionFor(press("ArrowUp"), "navigate")).toEqual({ kind: "previous" });
    expect(actionFor(press("ArrowDown"), "navigate")).toEqual({ kind: "next" });
    expect(actionFor(press("ArrowLeft"), "navigate")).toEqual({ kind: "cell", cell: "source" });
    expect(actionFor(press("ArrowRight"), "navigate")).toEqual({ kind: "cell", cell: "translation" });
    expect(actionFor(press("["), "navigate")).toEqual({ kind: "set-start" });
    expect(actionFor(press("]"), "navigate")).toEqual({ kind: "set-end" });
    expect(actionFor(press("Enter"), "navigate")).toEqual({ kind: "edit" });
  });

  it("nudges 100 ms with Alt and 500 ms with Alt and Shift", () => {
    expect(actionFor(press("ArrowLeft", { altKey: true }), "navigate")).toEqual({ kind: "nudge", delta_ms: -100 });
    expect(actionFor(press("ArrowRight", { altKey: true }), "navigate")).toEqual({ kind: "nudge", delta_ms: 100 });
    expect(actionFor(press("ArrowRight", { altKey: true, shiftKey: true }), "navigate")).toEqual({ kind: "nudge", delta_ms: 500 });
  });

  it("undoes and redoes with Ctrl or ⌘", () => {
    expect(actionFor(press("z", { metaKey: true }), "navigate")).toEqual({ kind: "undo" });
    expect(actionFor(press("z", { ctrlKey: true }), "navigate")).toEqual({ kind: "undo" });
    expect(actionFor(press("Z", { metaKey: true, shiftKey: true }), "navigate")).toEqual({ kind: "redo" });
    expect(actionFor(press("y", { ctrlKey: true }), "navigate")).toEqual({ kind: "redo" });
  });

  it("leaves every other key to the browser", () => {
    for (const k of [press("a"), press("Tab"), press("Escape"), press("s", { metaKey: true }), press("ArrowUp", { altKey: true })]) {
      expect(actionFor(k, "navigate")).toBeNull();
    }
  });
});

describe("edit mode (spec §20)", () => {
  it("lets typing go to the text: only Ctrl or ⌘ chords act, and Esc", () => {
    for (const k of [" ", "j", "Enter", "[", "ArrowUp", "a"]) expect(actionFor(press(k), "edit")).toBeNull();
    expect(actionFor(press("ArrowLeft", { altKey: true }), "edit")).toBeNull();
    expect(actionFor(press("z", { metaKey: true }), "edit")).toBeNull(); // the text box's own undo
    expect(actionFor(press("Escape"), "edit")).toEqual({ kind: "cancel" });
  });

  it("commits with ⌘↵, splits at the caret with ⌘⇧S and merges with ⌘M", () => {
    expect(actionFor(press("Enter", { metaKey: true }), "edit")).toEqual({ kind: "commit" });
    expect(actionFor(press("Enter", { ctrlKey: true }), "edit")).toEqual({ kind: "commit" });
    expect(actionFor(press("S", { metaKey: true, shiftKey: true }), "edit")).toEqual({ kind: "split" });
    expect(actionFor(press("m", { ctrlKey: true }), "edit")).toEqual({ kind: "merge" });
    expect(actionFor(press("s", { metaKey: true }), "edit")).toBeNull();
  });
});

describe("an input method's keys (S33)", () => {
  it("are never an action while a composition runs, whatever the key", () => {
    for (const mode of ["navigate", "edit"] as const) {
      expect(actionFor(press("Enter", { isComposing: true }), mode)).toBeNull();
      expect(actionFor(press("Enter", { metaKey: true, isComposing: true }), mode)).toBeNull();
      expect(actionFor(press("Escape", { isComposing: true }), mode)).toBeNull();
      // compositionstart can come after the keydown, with isComposing still false: keyCode 229
      expect(actionFor(press("Enter", { keyCode: 229 }), mode)).toBeNull();
      expect(actionFor(press("Process", { keyCode: 229 }), mode)).toBeNull();
    }
  });
});
