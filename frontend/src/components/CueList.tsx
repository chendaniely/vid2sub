import { useVirtualizer } from "@tanstack/react-virtual";
import { type KeyboardEvent, type RefObject, useCallback, useEffect } from "react";

import { activeDescendant } from "@/lib/cues";
import type { Row, SpokenWord } from "@/types";

import { type Cell, CueRow, type Editing } from "./CueRow";

/** The cue list (spec §20), one row per source cue, and navigate mode's home: with focus here,
 * the keyboard model's navigate keys act (`onKeyDown`). Only the rows on screen, and a few either
 * side, are in the page (Review Focus 3: about 2,000 cues for two hours), measured as they render
 * since a row's height follows its text; @tanstack/react-virtual places them, through React's
 * style props (the CSSOM, which the CSP allows), never a style attribute in the markup. The
 * selected row is scrolled into view, and while playback is followed so is the current one. */
export function CueList({ listRef, rows, words, track, current, word, selected, cell, trId, editing, follow, onPick, onKeyDown, onDraft, onEditKey, editorRef }: {
  listRef: RefObject<HTMLDivElement | null>;
  rows: readonly Row[];
  words: readonly SpokenWord[];
  track: string | null;
  current: number;
  word: number;
  selected: number;
  cell: Cell;
  trId: string | null;
  editing: Editing | null;
  follow: boolean;
  onPick: (index: number, cell: Cell, trId?: string) => void;
  onKeyDown: (e: KeyboardEvent<HTMLDivElement>) => void;
  onDraft: (text: string) => void;
  onEditKey: (e: KeyboardEvent<HTMLTextAreaElement>) => void;
  editorRef: RefObject<HTMLTextAreaElement | null>;
}) {
  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => listRef.current,
    estimateSize: () => 84,
    overscan: 6,
    getItemKey: useCallback((i: number) => rows[i].id, [rows]),
    useFlushSync: false, // React 19 warns of flushSync inside a render (TanStack's React docs)
  });

  useEffect(() => {
    if (follow && current >= 0 && !editing) virtualizer.scrollToIndex(current, { align: "auto" });
  }, [follow, current, editing, virtualizer]);
  useEffect(() => {
    if (selected >= 0) virtualizer.scrollToIndex(selected, { align: "auto" });
  }, [selected, virtualizer]);

  const items = virtualizer.getVirtualItems();
  return (
    <div
      ref={listRef}
      role="listbox"
      aria-label="Cues: arrows to move, Enter to edit, Space to play"
      tabIndex={0}
      aria-activedescendant={activeDescendant(rows, selected, items.map((item) => item.index))}
      onKeyDown={onKeyDown}
      className="h-full min-h-0 overflow-y-auto rounded-lg border border-border bg-card focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
      data-testid="cue-list"
    >
      <div role="none" className="relative w-full" style={{ height: virtualizer.getTotalSize() }}>
        <div role="none" className="absolute top-0 left-0 w-full" style={{ transform: `translateY(${items[0]?.start ?? 0}px)` }}>
          {items.map((item) => {
            const row = rows[item.index];
            return (
              <div role="none" key={item.key} data-index={item.index} ref={virtualizer.measureElement}>
                <CueRow
                  row={row}
                  track={track}
                  current={item.index === current}
                  selected={item.index === selected}
                  cell={cell}
                  trId={trId}
                  editing={editing?.id === row.id ? editing : null}
                  word={word}
                  words={words}
                  total={rows.length}
                  onPick={(which, id) => onPick(item.index, which, id)}
                  onDraft={onDraft}
                  onEditKey={onEditKey}
                  editorRef={editorRef}
                />
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
