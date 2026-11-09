// The caption overlay's text: a cue's text with `<i>` and `</i>` as the only markup, everything
// else shown as the characters it is (spec §6.3). M1's parser keeps only `<i>` of a subtitle's
// markup, but an SRT edited elsewhere comes back as text, so a `<script>`, `&lt;` or an ASS brace
// can be in it: none of it becomes an element or an entity. The overlay makes React elements from
// these segments; never dangerouslySetInnerHTML.

/** A run of the caption: its text and whether it is in italics. */
export type Segment = { text: string; italic: boolean };

const TAG = /<(\/?)i>/gi;

/** The caption's runs, in order, with empty ones left out. An `</i>` with no `<i>` open, or an
 * `<i>` inside one, changes nothing; an `<i>` never closed runs to the end. */
export function segments(text: string): Segment[] {
  const out: Segment[] = [];
  let italic = false;
  let at = 0;
  const push = (end: number) => {
    const part = text.slice(at, end);
    if (!part) return;
    const last = out[out.length - 1];
    if (last && last.italic === italic) last.text += part;
    else out.push({ text: part, italic });
  };
  for (const m of text.matchAll(TAG)) {
    push(m.index);
    at = m.index + m[0].length;
    italic = m[1] !== "/";
  }
  push(text.length);
  return out;
}

/** What the overlay shows for a row: the source, the translation or both (spec §20). */
export type Showing = "source" | "translation" | "both";

/** The caption lines for one moment: the source cue's text and the translation's, as chosen;
 * a part with no cue at that moment is left out. */
export function captionLines(showing: Showing, source: string | null, translation: string | null): string[] {
  const lines: string[] = [];
  if (showing !== "translation" && source) lines.push(source);
  if (showing !== "source" && translation) lines.push(translation);
  return lines;
}
