import type { KeyboardEvent, RefObject } from "react";

import { formatTime, wordSpans } from "@/lib/cues";
import { cn } from "@/lib/utils";
import type { Row, SpokenWord } from "@/types";

import { Flags } from "./Flags";

export type Cell = "source" | "translation";

/** The cell being edited: the source cue, or the translation cue `trId`, and the text so far. */
export type Editing = { id: string; cell: Cell; trId: string | null; text: string };

/** One source cue with its translation alongside (spec §20): number, times, source text, the
 * chosen track's translation and the flags. The current cue has the orange bar and
 * `aria-current`; in it the spoken word is marked, found in the text from the transcript's words.
 * The selected row's selected cell is outlined, and in edit mode it is a text box. Every string is
 * a text node or a text box's value (spec §6.3). */
export function CueRow({ row, track, current, selected, cell, editing, word, words, total, onPick, onDraft, onEditKey, editorRef }: {
  row: Row;
  track: string | null;
  current: boolean;
  selected: boolean;
  cell: Cell;
  editing: Editing | null; // only when this row is being edited
  word: number; // the spoken word's index in `words`, or -1
  words: readonly SpokenWord[];
  total: number;
  onPick: (cell: Cell) => void;
  onDraft: (text: string) => void;
  onEditKey: (e: KeyboardEvent<HTMLTextAreaElement>) => void;
  editorRef: RefObject<HTMLTextAreaElement | null>;
}) {
  const tr = track ? row.tr[track] : undefined;
  const flags = [...row.flags, ...(tr?.flags ?? []), ...(tr?.cues.flatMap((c) => c.flags) ?? [])];
  const marked = (which: Cell) => selected && cell === which && !editing;
  const box = (which: Cell) => (
    <textarea
      ref={editorRef}
      value={editing?.text ?? ""}
      rows={Math.max(2, (editing?.text ?? "").split("\n").length)}
      onChange={(e) => onDraft(e.target.value)}
      onKeyDown={onEditKey}
      onClick={(e) => e.stopPropagation()}
      aria-label={`${which === "source" ? "Cue" : "Translation of cue"} ${row.n}: ⌘↵ to commit, Esc to cancel`}
      className="w-full resize-none rounded-sm border border-input bg-background px-1 font-sans text-foreground focus-visible:outline-2 focus-visible:outline-ring"
      data-testid="cue-editor"
    />
  );
  return (
    <div
      role="option"
      id={`cue-${row.id}`}
      aria-selected={selected}
      aria-current={current ? "true" : undefined}
      aria-setsize={total}
      aria-posinset={row.n}
      data-testid="cue-row"
      data-cue={row.id}
      onClick={() => onPick("source")}
      className={cn(
        "grid cursor-pointer grid-cols-[2.5rem_1fr] gap-x-2 border-b border-l-4 border-b-border px-2 py-1.5",
        current ? "border-l-(--brand-orange)" : "border-l-transparent",
        selected && "bg-accent",
      )}
    >
      <span className="pt-0.5 text-xs text-muted-foreground tabular-nums">{row.n}</span>
      <div className="flex min-w-0 flex-col gap-0.5">
        <span className="font-mono text-xs text-muted-foreground" data-testid="cue-times">
          {formatTime(row.start_ms)} → {formatTime(row.end_ms)}
        </span>
        {editing?.cell === "source" ? box("source") : (
          <span data-selected={marked("source") || undefined} className={cn("rounded-sm", marked("source") && "outline-2 outline-ring")}>
            <SourceText row={row} word={current ? word : -1} words={words} />
          </span>
        )}
        {tr && (editing?.cell === "translation" ? box("translation") : (
          <span onClick={(e) => { e.stopPropagation(); onPick("translation"); }} data-selected={marked("translation") || undefined} className={cn("rounded-sm whitespace-pre-line text-muted-foreground", marked("translation") && "outline-2 outline-ring")} data-testid="cue-translation">
            {tr.cues.length ? tr.cues.map((c) => c.text).join("\n") : "—"}
          </span>
        ))}
        <Flags flags={flags} />
      </div>
    </div>
  );
}

function SourceText({ row, word, words }: { row: Row; word: number; words: readonly SpokenWord[] }) {
  const span = word >= 0 && row.w ? wordSpans(row.text, words.slice(row.w[0], row.w[1]))[word - row.w[0]] : null;
  if (!span) return <span className="whitespace-pre-line" data-testid="cue-text">{row.text}</span>;
  const [start, end] = span;
  return (
    <span className="whitespace-pre-line" data-testid="cue-text">
      {row.text.slice(0, start)}
      <mark className="rounded-sm bg-primary px-0.5 text-primary-foreground" data-testid="spoken-word">{row.text.slice(start, end)}</mark>
      {row.text.slice(end)}
    </span>
  );
}
