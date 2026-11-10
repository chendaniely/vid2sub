import { type FormEvent, useState } from "react";

import { countMatches } from "@/lib/cues";
import type { EditOp, EpisodeView } from "@/types";

const field = "rounded-md border border-input bg-background px-2 py-1 text-sm focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ring";
const button = "rounded-md border border-input bg-background px-2 py-1 text-sm focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ring disabled:opacity-50";

/** Find and replace across tracks, with "add to glossary" (spec §20, §16): plain, case-sensitive
 * text, replaced through the server's `replace_all` as one undoable edit; a glossary term waits
 * for Save, which writes it (Decision 5). The count is of the matches in the chosen tracks as the
 * cue list has them now. Not a modal: the cue list stays usable beside it. */
export function FindReplace({ episode, onEdit, onClose }: {
  episode: EpisodeView;
  onEdit: (op: EditOp) => void;
  onClose: () => void;
}) {
  const tracks = episode.tracks.filter((t) => !t.in_conflict);
  const [find, setFind] = useState("");
  const [replace, setReplace] = useState("");
  const [chosen, setChosen] = useState<string[]>(tracks.map((t) => t.key));
  const [term, setTerm] = useState("");
  const [translation, setTranslation] = useState("");
  const names = chosen.map((key) => (key === episode.source ? "source" : key));
  const count = find ? countMatches(episode.rows, episode.source, chosen, find) : 0;
  const adds = Object.entries(episode.glossary_adds);

  // Replace all is a button, never the form's submit: Enter in a field must not run it, and with
  // Replace empty it deletes every match across the episode (the Spec review's S-6).
  const replaceAll = () => {
    if (find && names.length) onEdit({ op: "replace_all", find, replace, tracks: names });
  };
  const addTerm = (e: FormEvent) => {
    e.preventDefault();
    if (term.trim() && translation.trim()) {
      onEdit({ op: "glossary_add", term: term.trim(), translation: translation.trim() });
      setTerm("");
      setTranslation("");
    }
  };
  return (
    <section aria-label="Find and replace" className="flex flex-col gap-3 rounded-lg border border-border bg-card p-3 text-sm" data-testid="find-replace">
      <form className="flex flex-col gap-2" onSubmit={(e) => e.preventDefault()}>
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-1">Find <input className={field} value={find} onChange={(e) => setFind(e.target.value)} data-testid="find" /></label>
          <label className="flex items-center gap-1">Replace with <input className={field} value={replace} onChange={(e) => setReplace(e.target.value)} data-testid="replace" /></label>
          <span aria-live="polite" data-testid="match-count">{find ? `${count} ${count === 1 ? "match" : "matches"}` : ""}</span>
        </div>
        <fieldset className="flex flex-wrap items-center gap-3">
          <legend className="sr-only">In these tracks</legend>
          {tracks.map((t) => (
            <label key={t.key} className="flex items-center gap-1">
              <input type="checkbox" className="size-4 accent-(--primary)" checked={chosen.includes(t.key)}
                onChange={(e) => setChosen(e.target.checked ? [...chosen, t.key] : chosen.filter((k) => k !== t.key))} data-testid={`find-track-${t.key}`} />
              {t.label}
            </label>
          ))}
          <button type="button" className={button} onClick={replaceAll} disabled={!find || !names.length || !count} data-testid="replace-all">Replace all</button>
          <button type="button" className={button} onClick={onClose}>Close</button>
        </fieldset>
      </form>
      <form className="flex flex-wrap items-center gap-2" onSubmit={addTerm} aria-label="Add to glossary">
        <span className="font-bold">Add to glossary</span>
        <label className="flex items-center gap-1">Term <input className={field} value={term} onChange={(e) => setTerm(e.target.value)} data-testid="glossary-term" /></label>
        <label className="flex items-center gap-1">Translation <input className={field} value={translation} onChange={(e) => setTranslation(e.target.value)} data-testid="glossary-translation" /></label>
        <button type="submit" className={button} disabled={!term.trim() || !translation.trim()} data-testid="glossary-add">Add</button>
      </form>
      {adds.length > 0 && (
        <ul className="flex flex-col gap-0.5" aria-label="Glossary terms waiting for Save" data-testid="glossary-adds">
          {adds.map(([t, tr]) => <li key={t}>{t} → {tr} <span className="text-muted-foreground">(written at Save)</span></li>)}
        </ul>
      )}
    </section>
  );
}
