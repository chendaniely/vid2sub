import type { Busy } from "@/types";

/** A line under the header while the playback audio is made (spec §8.8). An edit made now waits
 * in the tab's queue behind it, so it shows nothing until the sound is ready. Not while another
 * episode opens: the edit then names the old episode, and is dropped (the re-review's R-2). */
export function BusyNote({ busy }: { busy: Busy }) {
  if (busy !== "playback") return null;
  return (
    <p role="status" className="text-sm text-muted-foreground" data-testid="busy-note">
      Making the playback audio: edits made now apply when the sound is ready.
    </p>
  );
}
