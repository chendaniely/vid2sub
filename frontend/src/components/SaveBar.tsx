import { useState } from "react";

import type { Busy, Notice, SaveResultMessage, TrackInfo } from "@/types";

const button = "rounded-md border border-input bg-background px-2 py-1 text-sm focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ring disabled:opacity-50";

/** The command that replaces a subtitle file vid2sub didn't write, run in the video's folder:
 * Save never does it from the UI (spec §6.6; Decision 32), and asking file by file is the Later
 * table's S64. It keeps its placeholder: a name from the disk can hold `$(…)`, backticks or
 * quotes, which a shell expands even inside double quotes, so no file name ever goes into a line
 * a person might paste; the video is named beside it, as plain text. */
export const OVERWRITE_COMMAND = "vid2sub write <video> --overwrite-foreign";

/** What a Save or a pick did, as notices: what was written, each file left alone (someone
 * else's, or changed outside since: §15.3) with the command that replaces it, each track in
 * conflict, and the notes, as text. */
export function resultNotices(r: SaveResultMessage, tracks: readonly TrackInfo[], video: string): Notice[] {
  const label = (key: string) => tracks.find((t) => t.key === key)?.label ?? key;
  const out: Notice[] = [];
  const wrote = r.written.length ? `: wrote ${r.written.join(", ")}` : "";
  // a pick that left the track in conflict (a version arrived since) says only so, below
  if (r.kind === "pick") { if (!r.conflicts.length) out.push({ kind: "info", text: `Kept the version you picked${wrote}` }); }
  else if (wrote || !r.conflicts.length) out.push({ kind: "info", text: `Saved${wrote}` });
  if (r.foreign.length) {
    const one = r.foreign.length === 1;
    out.push({ kind: "info", text: `Left ${r.foreign.join(", ")} alone: vid2sub didn't write ${one ? "it" : "them"}, or ${one ? "it was" : "they were"} changed outside vid2sub since. To replace a file vid2sub didn't write, run ${OVERWRITE_COMMAND} in the video's folder (the video: ${video})` });
  }
  for (const note of r.notes) out.push({ kind: "info", text: note.charAt(0).toUpperCase() + note.slice(1) });
  for (const key of r.conflicts) out.push({ kind: "error", text: `${label(key)} has two versions: pick the one to keep` });
  return out;
}

/** Save (spec §14.5) and the drafts a crashed tab left (S34). Save writes a version of each
 * changed track and then the subtitle files: SRT always, ASS too when ticked, as the episode was
 * written before unless the person changes it. Every tab's draft found for the versions this
 * episode was opened at is offered back, each with its time, to restore; Discard sets them aside
 * here and drops this tab's own (Decision 31). */
export function SaveBar({ dirty, busy, formats, drafts, onSave, onRestore, onDiscard }: {
  dirty: boolean;
  busy: Busy;
  formats: readonly string[];
  drafts: readonly { key: string; at: string; steps: number }[];
  onSave: (formats: ("srt" | "ass")[]) => void;
  onRestore: (key: string) => void;
  onDiscard: () => void;
}) {
  const [ass, setAss] = useState(formats.includes("ass"));
  const saving = busy === "saving" || busy === "picking";
  return (
    <div className="flex flex-col gap-1" data-testid="save-bar">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <button
          type="button"
          className="rounded-md bg-primary px-3 py-1 font-bold text-primary-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:opacity-50"
          onClick={() => onSave(ass ? ["srt", "ass"] : ["srt"])}
          disabled={saving}
          data-testid="save"
        >
          {busy === "saving" ? "Saving…" : "Save"}
        </button>
        <label className="flex items-center gap-1">
          <input type="checkbox" className="size-4 accent-(--primary)" checked={ass} onChange={(e) => setAss(e.target.checked)} data-testid="save-ass" />
          ASS too
        </label>
        <span role="status" className="text-muted-foreground" data-testid="save-state">
          {dirty ? "Unsaved changes" : "All changes saved"}
        </span>
      </div>
      {drafts.length > 0 && (
        <div role="alert" className="flex flex-col gap-1 rounded-md border border-border bg-card px-3 py-2 text-sm" data-testid="drafts">
          {drafts.map((d) => (
            <div key={d.key} className="flex flex-wrap items-center gap-2" data-testid="draft">
              <span>
                {d.steps} unsaved {d.steps === 1 ? "edit" : "edits"} from {new Date(d.at).toLocaleString()} were kept in this browser.
              </span>
              <button type="button" className={button} onClick={() => onRestore(d.key)} data-testid="draft-restore">Restore them</button>
            </div>
          ))}
          <div>
            <button type="button" className={button} onClick={onDiscard} data-testid="draft-discard">Discard</button>
          </div>
        </div>
      )}
    </div>
  );
}
