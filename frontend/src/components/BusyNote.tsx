import type { Busy } from "@/types";

/** Lines under the header about what the tab's queue is doing, since an edit made now waits in it.
 * While the playback audio is made (spec §8.8) edits show nothing until the sound is ready; not
 * while another episode opens: the edit then names the old episode, and is dropped (the
 * re-review's R-2). While a retranslation is pending or running (`retranslating`: the track's
 * name, null where the server is busy with one this page has no name for) the track's lines
 * can't be edited, since the run replaces them and an edit sent meanwhile would be refused and
 * its text lost, and every other edit applies when it finishes (Task 17's Spec review, C-3, I-2).
 */
export function BusyNote({ busy, retranslating }: { busy: Busy; retranslating?: string | null }) {
  // not while another episode opens: an edit made then names the old one and is dropped
  const waiting = retranslating !== undefined && retranslating !== null && busy !== "opening";
  return (
    <>
      {busy === "playback" && (
        <p role="status" className="text-sm text-muted-foreground" data-testid="busy-note">
          Making the playback audio: edits made now apply when the sound is ready.
        </p>
      )}
      {(waiting || busy === "retranslating") && (
        <p role="status" className="text-sm text-muted-foreground" data-testid="retranslating-note">
          {waiting
            ? `Retranslating the ${retranslating} translation: its lines can be edited when it finishes; other edits apply then.`
            : "Retranslating: other edits apply when it finishes."}
        </p>
      )}
    </>
  );
}
