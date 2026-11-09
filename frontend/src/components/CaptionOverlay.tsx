import { Fragment } from "react";

import { segments } from "@/lib/overlay";

/** The captions over the player, redrawn as playback moves and as cues change (spec §20). Each
 * line's `<i>` becomes an <i> element and everything else is a text node (spec §6.3): no other
 * element is made from a subtitle's text. */
export function CaptionOverlay({ lines }: { lines: string[] }) {
  return (
    <div className="pointer-events-none absolute inset-x-0 bottom-14 flex flex-col items-center gap-1 px-4" data-testid="captions">
      {lines.map((line, k) => (
        <p key={k} className="max-w-[90%] rounded-sm bg-black/75 px-2 py-0.5 text-center text-lg leading-snug whitespace-pre-line text-white" data-testid="caption-line">
          {segments(line).map((s, j) => (s.italic ? <i key={j}>{s.text}</i> : <Fragment key={j}>{s.text}</Fragment>))}
        </p>
      ))}
    </div>
  );
}
