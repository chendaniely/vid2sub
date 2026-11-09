import { cn } from "@/lib/utils";
import { formatTime, wordSpans } from "@/lib/cues";
import type { Row, SpokenWord } from "@/types";

import { Flags } from "./Flags";

/** One source cue with its translation alongside (spec §20): number, times, source text, the
 * chosen track's translation and the flags. The current cue has the orange bar and
 * `aria-current`; in it the spoken word is marked, found in the text from the transcript's words.
 * Every string is a text node (spec §6.3). */
export function CueRow({ row, track, current, selected, word, words, total, onPick }: {
  row: Row;
  track: string | null;
  current: boolean;
  selected: boolean;
  word: number; // the spoken word's index in `words`, or -1
  words: readonly SpokenWord[];
  total: number;
  onPick: () => void;
}) {
  const cell = track ? row.tr[track] : undefined;
  const flags = [...row.flags, ...(cell?.flags ?? []), ...(cell?.cues.flatMap((c) => c.flags) ?? [])];
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
      onClick={onPick}
      className={cn(
        "grid cursor-pointer grid-cols-[2.5rem_1fr] gap-x-2 border-b border-l-4 border-b-border px-2 py-1.5",
        current ? "border-l-(--brand-orange)" : "border-l-transparent",
        selected && "bg-accent",
      )}
    >
      <span className="pt-0.5 text-xs text-muted-foreground tabular-nums">{row.n}</span>
      <div className="flex min-w-0 flex-col gap-0.5">
        <span className="font-mono text-xs text-muted-foreground">
          {formatTime(row.start_ms)} → {formatTime(row.end_ms)}
        </span>
        <SourceText row={row} word={current ? word : -1} words={words} />
        {cell && (
          <span className="whitespace-pre-line text-muted-foreground" data-testid="cue-translation">
            {cell.cues.length ? cell.cues.map((c) => c.text).join("\n") : "—"}
          </span>
        )}
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
