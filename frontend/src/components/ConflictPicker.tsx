import { useState } from "react";

import type { EpisodeView, Version } from "@/types";

import { Dialog } from "./ui/dialog";

const BY: Record<string, string> = {
  editor: "saved in the editor",
  external: "edited outside vid2sub",
  auto: "made by vid2sub",
  import: "imported",
  user: "picked by you",
};

/** A version in words: who made it, when, and how many cues it has. */
export function versionLabel(v: Version): string {
  const who = v.by ? (BY[v.by] ?? v.by) : "saved";
  const when = v.at ? `, ${new Date(v.at).toLocaleString()}` : "";
  return `${who[0].toUpperCase()}${who.slice(1)}${when}: ${v.cue_count} ${v.cue_count === 1 ? "cue" : "cues"}`;
}

/** The conflict picker (spec §14.4, S32): a track whose versions diverged (two tabs, or a tab
 * and a CLI run or an outside edit) shows each version, and the person keeps one, which the
 * server's `resolve` makes the head and writes. The native <dialog> (Decision 13): modal, the
 * page behind inert, Esc closes it, focus comes back. */
export function ConflictPicker({ episode, open, onClose, onPick }: {
  episode: EpisodeView;
  open: boolean;
  onClose: () => void;
  onPick: (track: string, rendition: string) => void;
}) {
  const tracks = episode.tracks.filter((t) => t.in_conflict && episode.conflicts[t.key]?.length);
  const [chosen, setChosen] = useState<Record<string, string>>({});
  return (
    <Dialog open={open} onClose={onClose} title="Pick a version" className="w-[32rem] max-w-[calc(100vw-2rem)]">
      <div className="flex flex-col gap-4 text-sm" data-testid="conflict-picker">
        <p>
          These tracks were saved twice from the same version, by another tab, a command or an edit outside vid2sub.
          Both versions are kept in the sidecar; pick the one to keep editing and write.
        </p>
        {tracks.map((t) => (
          <fieldset key={t.key} className="flex flex-col gap-2 rounded-md border border-border p-3">
            <legend className="px-1 font-bold">{t.label}</legend>
            {episode.conflicts[t.key].map((v) => (
              <label key={v.rendition} className="flex items-center gap-2" data-testid="version">
                <input
                  type="radio"
                  name={`version-${t.key}`}
                  value={v.rendition}
                  checked={chosen[t.key] === v.rendition}
                  onChange={() => setChosen({ ...chosen, [t.key]: v.rendition })}
                  className="size-4 accent-(--primary)"
                />
                {versionLabel(v)}
              </label>
            ))}
            <button
              type="button"
              className="self-start rounded-md bg-primary px-3 py-1 font-bold text-primary-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:opacity-50"
              disabled={!chosen[t.key]}
              onClick={() => onPick(t.key, chosen[t.key])}
              data-testid={`keep-${t.key}`}
            >
              Keep this version
            </button>
          </fieldset>
        ))}
        <button type="button" className="self-end rounded-md border border-input px-3 py-1 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring" onClick={onClose} data-testid="picker-close">
          Not now
        </button>
      </div>
    </Dialog>
  );
}
