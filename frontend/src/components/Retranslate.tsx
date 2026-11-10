import { useState } from "react";

import type { Busy, Progress } from "@/types";

const button = "rounded-md border border-input bg-background px-2 py-1 text-sm focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ring disabled:opacity-50";

/** Retranslate (spec §13.4, §20; S30): the selected cues, replaced even where a translation was
 * edited, since the person asked (Decision 8), or every stale or untranslated cue, never one a
 * person edited. **Allow cloud models** starts unticked, and unticks again after each request:
 * the cloud is allowed per retranslation, never by a setting (spec §7.2). The model's server can
 * take minutes over a whole episode, so while it works, the batches done so far are announced
 * politely (§19.3). */
export function Retranslate({ label, selected, busy, progress, pending, onSelected, onStale }: {
  label: string; // the translation track's name
  selected: number; // how many cues are selected
  busy: Busy;
  progress: Progress;
  pending: boolean; // a request was sent and its result isn't back (it may be waiting in the queue)
  onSelected: (allowCloud: boolean) => void;
  onStale: (allowCloud: boolean) => void;
}) {
  const [allowCloud, setAllowCloud] = useState(false);
  const working = busy === "retranslating";
  const unavailable = working || pending; // from the click until the result: one request per click
  const send = (run: (allowCloud: boolean) => void) => {
    run(allowCloud);
    setAllowCloud(false);
  };
  return (
    <div role="group" aria-label={`Retranslate ${label}`} className="flex flex-wrap items-center gap-2 text-sm" data-testid="retranslate">
      <button type="button" className={button} disabled={unavailable || selected === 0} onClick={() => send(onSelected)} data-testid="retranslate-selected">
        {selected > 1 ? `Retranslate ${selected} cues` : "Retranslate this cue"}
      </button>
      <button type="button" className={button} disabled={unavailable} onClick={() => send(onStale)} data-testid="retranslate-stale">
        Retranslate stale
      </button>
      <label className="flex items-center gap-1">
        <input type="checkbox" className="size-4 accent-(--primary)" checked={allowCloud} onChange={(e) => setAllowCloud(e.target.checked)} data-testid="allow-cloud" />
        Allow cloud models
      </label>
      <span role="status" aria-live="polite" className="text-muted-foreground" data-testid="retranslate-progress">
        {working ? (progress ? `Retranslating: ${progress.done} of ${progress.of} batches done…` : "Retranslating…") : pending ? "Waiting to retranslate…" : ""}
      </span>
    </div>
  );
}
