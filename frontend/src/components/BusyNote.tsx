import type { Busy } from "@/types";

/** A line under the header while the editor is busy (spec §8.8). An edit made now waits in the
 * tab's queue behind the open or the playback audio, so it shows nothing until that ends. */
export function BusyNote({ busy }: { busy: Busy }) {
  if (!busy) return null;
  return (
    <p role="status" className="text-sm text-muted-foreground" data-testid="busy-note">
      {busy === "playback"
        ? "Making the playback audio: edits made now apply when the sound is ready."
        : "Opening: edits made now apply when it has opened."}
    </p>
  );
}
