import { type FormEvent, useCallback, useMemo, useRef, useState } from "react";

import { indexAt, trackCues, wordAt } from "@/lib/cues";
import { captionLines, type Showing } from "@/lib/overlay";
import type { Busy, EpisodeView } from "@/types";

import { CueList } from "./CueList";
import { Player } from "./Player";

const SPEEDS = [0.75, 1, 1.25] as const; // the practice aids' playback rates (spec §20)
const control = "rounded-md border border-input bg-background px-2 py-1 text-sm focus-visible:outline-2 focus-visible:outline-ring";

/** The editor (spec §20): the path box, then, once an episode is open, the player on the left
 * and the cue list on the right. */
export function Editor({ episode, busy, pathInput, onOpen, onCantPlay }: {
  episode: EpisodeView | null;
  busy: Busy;
  pathInput: boolean;
  onOpen: (path: string) => void;
  onCantPlay: () => void;
}) {
  return (
    <div className="flex h-full min-h-0 flex-col gap-3 p-4" data-testid="editor">
      {pathInput && <OpenForm busy={busy} onOpen={onOpen} />}
      {episode ? (
        <EpisodeEditor key={episode.id} episode={episode} busy={busy} onCantPlay={onCantPlay} />
      ) : (
        <p className="m-auto text-muted-foreground">Type the full path of a video vid2sub has made subtitles for, then Open.</p>
      )}
    </div>
  );
}

function OpenForm({ busy, onOpen }: { busy: Busy; onOpen: (path: string) => void }) {
  const [path, setPath] = useState("");
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (path.trim()) onOpen(path.trim());
  };
  return (
    <form className="flex items-center gap-2" onSubmit={submit} data-testid="open-form">
      <label htmlFor="open-path" className="text-sm font-bold">Video</label>
      <input id="open-path" className={`${control} min-w-0 flex-1 font-mono`} value={path} onChange={(e) => setPath(e.target.value)} placeholder="/full/path/to/Show - S01E01.mkv" spellCheck={false} autoComplete="off" data-testid="open-path" />
      <button type="submit" className="rounded-md bg-primary px-3 py-1 text-sm font-bold text-primary-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:opacity-60" disabled={busy === "opening"} data-testid="open-button">
        {busy === "opening" ? "Opening…" : "Open"}
      </button>
    </form>
  );
}

function EpisodeEditor({ episode, busy, onCantPlay }: {
  episode: EpisodeView;
  busy: Busy;
  onCantPlay: () => void;
}) {
  const translations = episode.tracks.filter((t) => t.role === "translation" && !t.in_conflict);
  const [track, setTrack] = useState<string | null>(translations[0]?.key ?? null);
  const [showing, setShowing] = useState<Showing>("both");
  const [follow, setFollow] = useState(true);
  const [loop, setLoop] = useState<{ start_ms: number; end_ms: number } | null>(null);
  const [rate, setRate] = useState<number>(1);
  const [current, setCurrent] = useState(-1);
  const [word, setWord] = useState(-1);
  const [trAt, setTrAt] = useState(-1);
  const [selected, setSelected] = useState(-1);
  const media = useRef<HTMLVideoElement | HTMLAudioElement | null>(null);

  const rows = episode.rows;
  const shownTrack = track && episode.tracks.some((t) => t.key === track) ? track : null;
  const trCues = useMemo(() => trackCues(rows, shownTrack), [rows, shownTrack]);

  // Called every frame while playing: state changes only when the cue, the word or the
  // translation playing changes, so the list re-renders a few times a second at most.
  const onTime = useCallback((ms: number) => {
    if (loop && media.current && ms >= loop.end_ms) {
      media.current.currentTime = loop.start_ms / 1000;
      return;
    }
    const row = indexAt(rows, ms);
    setCurrent(row);
    setWord(row >= 0 ? wordAt(episode.words, rows[row].w, ms) : -1);
    setTrAt(indexAt(trCues, ms));
  }, [loop, rows, trCues, episode.words]);

  const seek = (index: number) => {
    setSelected(index);
    if (media.current) media.current.currentTime = (rows[index].start_ms + 1) / 1000;
  };
  const toggleLoop = () => {
    const at = current >= 0 ? current : selected;
    setLoop(loop || at < 0 ? null : { start_ms: rows[at].start_ms, end_ms: rows[at].end_ms });
  };
  const changeRate = (value: number) => {
    setRate(value);
    if (media.current) media.current.playbackRate = value;
  };

  const lines = captionLines(showing, current >= 0 ? rows[current].text : null, trAt >= 0 ? trCues[trAt].text : null);
  const stale = translations.filter((t) => t.all_stale);
  const conflicted = episode.tracks.filter((t) => t.in_conflict);

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <header className="flex flex-col gap-1">
        <h1 className="truncate text-lg font-bold" data-testid="episode-name">{episode.video.name}</h1>
        {(episode.notes.length > 0 || stale.length > 0 || conflicted.length > 0) && (
          <ul role="status" className="flex flex-col gap-0.5 text-sm" data-testid="episode-notes">
            {episode.notes.map((note, k) => <li key={k}>{note}</li>)}
            {stale.map((t) => (
              <li key={`stale-${t.key}`}>Every {t.label} cue is stale: the glossary or the translation model changed since it was made, or a glossary term is waiting for Save.</li>
            ))}
            {conflicted.map((t) => (
              <li key={`conflict-${t.key}`} className="text-destructive">The {t.label} track has two versions: pick one before editing it.</li>
            ))}
          </ul>
        )}
      </header>
      <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 lg:grid-cols-[minmax(0,3fr)_minmax(22rem,2fr)]">
        <section aria-label="Player" className="flex min-h-0 flex-col gap-2">
          <Player video={episode.video} mediaRef={media} lines={lines} busy={busy} onTime={onTime} onCantPlay={onCantPlay} />
          <div className="flex flex-wrap items-center gap-3 text-sm" data-testid="practice">
            <label className="flex items-center gap-1">
              Captions
              <select className={control} value={showing} onChange={(e) => setShowing(e.target.value as Showing)} data-testid="showing">
                <option value="source">Source</option>
                <option value="translation">Translation</option>
                <option value="both">Both</option>
              </select>
            </label>
            {translations.length > 1 && (
              <label className="flex items-center gap-1">
                Translation
                <select className={control} value={shownTrack ?? ""} onChange={(e) => setTrack(e.target.value)} data-testid="track">
                  {translations.map((t) => <option key={t.key} value={t.key}>{t.label}</option>)}
                </select>
              </label>
            )}
            <label className="flex items-center gap-1">
              Speed
              <select className={control} value={rate} onChange={(e) => changeRate(Number(e.target.value))} data-testid="speed">
                {SPEEDS.map((s) => <option key={s} value={s}>{s}×</option>)}
              </select>
            </label>
            <button type="button" className={control} aria-pressed={loop !== null} onClick={toggleLoop} data-testid="loop">
              {loop ? "Looping this cue" : "Loop this cue"}
            </button>
            <label className="flex items-center gap-1">
              <input type="checkbox" checked={follow} onChange={(e) => setFollow(e.target.checked)} className="size-4 accent-(--primary)" data-testid="follow" />
              Follow playback
            </label>
          </div>
        </section>
        <section aria-label="Cue list" className="min-h-0">
          <CueList rows={rows} words={episode.words} track={shownTrack} current={current} word={word} selected={selected} follow={follow} onPick={seek} />
        </section>
      </div>
    </div>
  );
}
