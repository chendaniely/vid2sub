import { useVirtualizer } from "@tanstack/react-virtual";
import { useCallback, useEffect, useRef } from "react";

import type { Row, SpokenWord } from "@/types";

import { CueRow } from "./CueRow";

/** The cue list (spec §20), one row per source cue. Only the rows on screen, and a few either
 * side, are in the page (Review Focus 3: about 2,000 cues for two hours), measured as they render
 * since a row's height follows its text; @tanstack/react-virtual places them, through React's
 * style props (the CSSOM, which the CSP allows), never a style attribute in the markup. While
 * playback is followed, the current row is scrolled into view. */
export function CueList({ rows, words, track, current, word, selected, follow, onPick }: {
  rows: readonly Row[];
  words: readonly SpokenWord[];
  track: string | null;
  current: number;
  word: number;
  selected: number;
  follow: boolean;
  onPick: (index: number) => void;
}) {
  const scroller = useRef<HTMLDivElement>(null);
  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scroller.current,
    estimateSize: () => 84,
    overscan: 6,
    getItemKey: useCallback((i: number) => rows[i].id, [rows]),
    useFlushSync: false, // React 19 warns of flushSync inside a render (TanStack's React docs)
  });

  useEffect(() => {
    if (follow && current >= 0) virtualizer.scrollToIndex(current, { align: "auto" });
  }, [follow, current, virtualizer]);
  useEffect(() => {
    if (selected >= 0) virtualizer.scrollToIndex(selected, { align: "auto" });
  }, [selected, virtualizer]);

  const items = virtualizer.getVirtualItems();
  return (
    <div
      ref={scroller}
      role="listbox"
      aria-label="Cues"
      tabIndex={0}
      aria-activedescendant={selected >= 0 && selected < rows.length ? `cue-${rows[selected].id}` : undefined}
      className="h-full min-h-0 overflow-y-auto rounded-lg border border-border bg-card focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
      data-testid="cue-list"
    >
      <div role="none" className="relative w-full" style={{ height: virtualizer.getTotalSize() }}>
        <div role="none" className="absolute top-0 left-0 w-full" style={{ transform: `translateY(${items[0]?.start ?? 0}px)` }}>
          {items.map((item) => (
            <div role="none" key={item.key} data-index={item.index} ref={virtualizer.measureElement}>
              <CueRow
                row={rows[item.index]}
                track={track}
                current={item.index === current}
                selected={item.index === selected}
                word={word}
                words={words}
                total={rows.length}
                onPick={() => onPick(item.index)}
              />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
