// The editor's keyboard model, verbatim from spec §20, safe with CJK input methods.
//
// Navigate mode (the default): Space plays or pauses, J/K/L shuttle (J back two seconds, K
// pause, L play), ↑/↓ the previous or next cue, ←/→ the source or the translation cell, `[` and
// `]` set the cue's start or end to the playhead, Alt+←/→ nudge it 100 ms (500 ms with Shift),
// Enter edits the selected cell, Ctrl/⌘+Z undoes and Ctrl/⌘+Shift+Z (or Ctrl+Y) redoes. Edit
// mode: typing goes to the text and only Ctrl/⌘ chords act (⌘↵ commit, ⌘⇧S split at the caret,
// ⌘M merge with the next cue); Esc returns to navigate mode. Ctrl and ⌘ are the same chord on
// every system. A keydown that is part of an IME composition (`isComposing`, or keyCode 229, which
// is all a browser sets when compositionstart comes after the keydown: MDN's keydown page) is
// never an action, so committing a candidate with Enter does nothing but commit it (S33).

export type Mode = "navigate" | "edit";

export type Action =
  | { kind: "play-pause" }
  | { kind: "back" }
  | { kind: "pause" }
  | { kind: "play" }
  | { kind: "previous" }
  | { kind: "next" }
  | { kind: "cell"; cell: "source" | "translation" }
  | { kind: "set-start" }
  | { kind: "set-end" }
  | { kind: "nudge"; delta_ms: number }
  | { kind: "edit" }
  | { kind: "undo" }
  | { kind: "redo" }
  | { kind: "commit" }
  | { kind: "split" }
  | { kind: "merge" }
  | { kind: "cancel" };

/** What a keydown needs to say: React's and the DOM's KeyboardEvent both have it. */
export type KeyLike = {
  key: string;
  keyCode?: number;
  isComposing?: boolean;
  ctrlKey: boolean;
  metaKey: boolean;
  shiftKey: boolean;
  altKey: boolean;
};

export const NUDGE_MS = 100;
export const BIG_NUDGE_MS = 500;

/** The action a keydown asks for in `mode`, or null (let the browser have it). */
export function actionFor(e: KeyLike, mode: Mode): Action | null {
  if (e.isComposing || e.keyCode === 229) return null;
  const chord = e.ctrlKey || e.metaKey;
  const key = e.key.length === 1 ? e.key.toLowerCase() : e.key;
  if (mode === "edit") {
    if (e.key === "Escape") return { kind: "cancel" };
    if (!chord || e.altKey) return null;
    if (key === "Enter") return { kind: "commit" };
    if (key === "s" && e.shiftKey) return { kind: "split" };
    if (key === "m" && !e.shiftKey) return { kind: "merge" };
    return null;
  }
  if (chord) {
    if (e.altKey) return null;
    if (key === "z") return e.shiftKey ? { kind: "redo" } : { kind: "undo" };
    if (key === "y" && e.ctrlKey && !e.shiftKey) return { kind: "redo" };
    return null;
  }
  if (e.altKey) {
    const step = e.shiftKey ? BIG_NUDGE_MS : NUDGE_MS;
    if (key === "ArrowLeft") return { kind: "nudge", delta_ms: -step };
    if (key === "ArrowRight") return { kind: "nudge", delta_ms: step };
    return null;
  }
  switch (key) {
    case " ": return { kind: "play-pause" };
    case "j": return e.shiftKey ? null : { kind: "back" };
    case "k": return e.shiftKey ? null : { kind: "pause" };
    case "l": return e.shiftKey ? null : { kind: "play" };
    case "ArrowUp": return { kind: "previous" };
    case "ArrowDown": return { kind: "next" };
    case "ArrowLeft": return { kind: "cell", cell: "source" };
    case "ArrowRight": return { kind: "cell", cell: "translation" };
    case "[": return { kind: "set-start" };
    case "]": return { kind: "set-end" };
    case "Enter": return e.shiftKey ? null : { kind: "edit" };
    default: return null;
  }
}
