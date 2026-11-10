import { type FormEvent, type KeyboardEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { indexAt, splitPoint, trackCues, wordAt } from "@/lib/cues";
import { newCueIds, shownIds } from "@/lib/ids";
import { type Action, type KeyLike, actionFor } from "@/lib/keys";
import { captionLines, type Showing } from "@/lib/overlay";
import type { Busy, EditOp, EpisodeView } from "@/types";

import { type Cell, type Editing } from "./CueRow";
import { CueList } from "./CueList";
import { FindReplace } from "./FindReplace";
import { Player } from "./Player";

const SPEEDS = [0.75, 1, 1.25] as const; // the practice aids' playback rates (spec §20)
const INSERT_MS = 2000; // a new cue's length, where the gap allows
export const control = "rounded-md border border-input bg-background px-2 py-1 text-sm focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ring disabled:opacity-50";

/** What the editor asks the server for: every edit goes through its `apply` (spec §20). */
export type Requests = {
  edit: (op: EditOp) => void;
  undo: () => void;
  redo: () => void;
};

/** The editor (spec §20): the path box, then, once an episode is open, the player on the left
 * and the cue list on the right, with the edit bar and find and replace. */
export function Editor({ episode, busy, pathInput, onOpen, onCantPlay, requests }: {
  episode: EpisodeView | null;
  busy: Busy;
  pathInput: boolean;
  onOpen: (path: string) => void;
  onCantPlay: () => void;
  requests: Requests;
}) {
  return (
    <div className="flex h-full min-h-0 flex-col gap-3 p-4" data-testid="editor">
      {pathInput && <OpenForm busy={busy} onOpen={onOpen} />}
      {episode ? (
        <EpisodeEditor key={episode.id} episode={episode} busy={busy} requests={requests} onCantPlay={onCantPlay} />
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

function keyOf(e: KeyboardEvent): KeyLike {
  return { key: e.key, keyCode: e.keyCode, isComposing: e.nativeEvent.isComposing, ctrlKey: e.ctrlKey, metaKey: e.metaKey, shiftKey: e.shiftKey, altKey: e.altKey };
}

function EpisodeEditor({ episode, busy, requests, onCantPlay }: {
  episode: EpisodeView;
  busy: Busy;
  requests: Requests;
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
  const [sel, setSel] = useState<{ index: number; id: string | null }>({ index: -1, id: null });
  const [cell, setCell] = useState<Cell>("source");
  const [editing, setEditing] = useState<Editing | null>(null);
  const [finding, setFinding] = useState(false);
  const media = useRef<HTMLVideoElement | HTMLAudioElement | null>(null);
  const list = useRef<HTMLDivElement>(null);
  const editor = useRef<HTMLTextAreaElement>(null);
  const pending = useRef<string | null>(null); // an inserted cue's id, to select and edit

  const rows = episode.rows;
  const shownTrack = track && episode.tracks.some((t) => t.key === track) ? track : null;
  const trCues = useMemo(() => trackCues(rows, shownTrack), [rows, shownTrack]);
  const selected = sel.index;
  const row = selected >= 0 ? rows[selected] : undefined;

  // The rows change with every edit: the selection follows its cue, else stays at its place (a
  // split or merge replaces the cue's id); an inserted cue is selected and edited.
  useEffect(() => {
    if (pending.current) {
      const at = rows.findIndex((r) => r.id === pending.current);
      pending.current = null;
      if (at >= 0) {
        setSel({ index: at, id: rows[at].id });
        setCell("source");
        setEditing({ id: rows[at].id, cell: "source", trId: null, text: rows[at].text });
        return;
      }
    }
    setSel((s) => {
      const found = rows.findIndex((r) => r.id === s.id);
      if (found >= 0) return found === s.index ? s : { index: found, id: s.id };
      const index = Math.min(s.index, rows.length - 1);
      return { index, id: index >= 0 ? rows[index].id : null };
    });
    setEditing((e) => (e && rows.some((r) => r.id === e.id) ? e : null));
  }, [rows]);

  useEffect(() => {
    if (editing) editor.current?.focus();
  }, [editing?.id, editing?.cell]);

  // Called every frame while playing: state changes only when the cue, the word or the
  // translation playing changes, so the list re-renders a few times a second at most.
  const onTime = useCallback((ms: number) => {
    if (loop && media.current && ms >= loop.end_ms) {
      media.current.currentTime = loop.start_ms / 1000;
      return;
    }
    const at = indexAt(rows, ms);
    setCurrent(at);
    setWord(at >= 0 ? wordAt(episode.words, rows[at].w, ms) : -1);
    setTrAt(indexAt(trCues, ms));
  }, [loop, rows, trCues, episode.words]);

  const playhead = () => Math.round((media.current?.currentTime ?? 0) * 1000);
  const seekTo = (ms: number) => {
    if (media.current) media.current.currentTime = ms / 1000;
  };
  const select = (index: number, which: Cell = cell) => {
    if (index < 0 || index >= rows.length) return;
    setSel({ index, id: rows[index].id });
    setCell(which);
    seekTo(rows[index].start_ms + 1);
  };
  const focusList = () => list.current?.focus();

  const startEditing = (which: Cell) => {
    if (!row) return;
    if (which === "source") {
      setEditing({ id: row.id, cell: "source", trId: null, text: row.text });
      return;
    }
    const tr = shownTrack ? row.tr[shownTrack]?.cues[0] : undefined;
    if (tr) setEditing({ id: row.id, cell: "translation", trId: tr.id, text: tr.text });
  };
  const commit = (): boolean => {
    if (!editing || !row) return false;
    const before = editing.cell === "source" ? row.text : row.tr[shownTrack ?? ""]?.cues.find((c) => c.id === editing.trId)?.text;
    if (editing.text === before) return false;
    if (editing.cell === "source") requests.edit({ op: "set_text", cue: editing.id, text: editing.text });
    else if (shownTrack && editing.trId) requests.edit({ op: "set_translation_text", track: shownTrack, cue: editing.trId, text: editing.text });
    return true;
  };
  const stopEditing = () => {
    setEditing(null);
    focusList();
  };
  // Split at the caret in edit mode (committing the text first), else at the space nearest the
  // playhead's share of the cue; at the playhead when it is inside the cue, else at the caret's
  // share of the cue's time.
  const split = () => {
    if (!row) return;
    const ph = playhead();
    const inside = row.start_ms < ph && ph < row.end_ms;
    let text = row.text;
    let at: number;
    if (editing?.cell === "source") {
      commit();
      text = editing.text;
      at = editor.current?.selectionStart ?? Math.floor(text.length / 2);
      stopEditing();
    } else {
      at = splitPoint(text, inside ? (ph - row.start_ms) / (row.end_ms - row.start_ms) : 0.5);
    }
    const share = text.length ? at / text.length : 0.5;
    const at_ms = inside ? ph
      : Math.min(row.end_ms - 1, Math.max(row.start_ms + 1, Math.round(row.start_ms + (row.end_ms - row.start_ms) * share)));
    const [a, b] = newCueIds(2, shownIds(rows));
    requests.edit({ op: "split", cue: row.id, at_char: at, at_ms, ids: [a, b] });
  };
  const merge = () => {
    if (!row) return;
    if (editing) {
      commit();
      stopEditing();
    }
    // the merged cue's id, and one for each translation track, in case its two parts' cues join
    const tracks = episode.tracks.filter((t) => t.role !== "source").map((t) => t.key);
    const [id, ...joined] = newCueIds(1 + tracks.length, shownIds(rows));
    requests.edit({ op: "merge_next", cue: row.id, id, joined: Object.fromEntries(tracks.map((k, i) => [k, joined[i]])) });
  };
  const insert = () => {
    const ph = playhead();
    let start = ph;
    if (indexAt(rows, ph) >= 0 && row) start = row.end_ms;
    const next = rows.find((r) => r.start_ms > start);
    const end = Math.min(start + INSERT_MS, next ? next.start_ms : start + INSERT_MS);
    const [id] = newCueIds(1, shownIds(rows));
    pending.current = id;
    requests.edit({ op: "insert", start_ms: start, end_ms: end, text: "…", id });
  };

  const act = (a: Action) => {
    const m = media.current;
    switch (a.kind) {
      case "play-pause": if (m) void (m.paused ? m.play().catch(() => undefined) : m.pause()); return;
      case "back": if (m) m.currentTime = Math.max(0, m.currentTime - 2); return;
      case "pause": m?.pause(); return;
      case "play": if (m) void m.play().catch(() => undefined); return;
      case "previous": select(Math.max(0, selected - 1)); return;
      case "next": select(Math.min(rows.length - 1, selected + 1)); return;
      case "cell": if (a.cell === "source" || shownTrack) setCell(a.cell); return;
      case "set-start": if (row) requests.edit({ op: "set_times", cue: row.id, start_ms: playhead() }); return;
      case "set-end": if (row) requests.edit({ op: "set_times", cue: row.id, end_ms: playhead() }); return;
      case "nudge": if (row) requests.edit({ op: "nudge", cue: row.id, delta_ms: a.delta_ms, edge: "both" }); return;
      case "edit": startEditing(cell); return;
      case "undo": requests.undo(); return;
      case "redo": requests.redo(); return;
      case "commit": commit(); stopEditing(); return;
      case "split": if (editing?.cell !== "translation") split(); return;
      case "merge": merge(); return;
      case "cancel": stopEditing(); return;
    }
  };
  const onListKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.target !== e.currentTarget) return; // a text box inside handles its own keys
    const a = actionFor(keyOf(e), "navigate");
    if (!a) return;
    e.preventDefault();
    if (selected < 0 && (a.kind === "next" || a.kind === "previous")) {
      select(current >= 0 ? current : 0);
      return;
    }
    act(a);
  };
  const onEditKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    const a = actionFor(keyOf(e), "edit");
    if (!a) return;
    e.preventDefault();
    act(a);
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
  const noRow = !row;
  const tool = (label: string, keys: string, onClick: () => void, testid: string, disabled = noRow) => (
    <button type="button" className={control} onClick={onClick} disabled={disabled} aria-keyshortcuts={keys || undefined} title={keys ? `${label} (${keys})` : label} data-testid={testid}>
      {label}
    </button>
  );

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
          {finding && <FindReplace episode={episode} onEdit={requests.edit} onClose={() => setFinding(false)} />}
        </section>
        <section aria-label="Cue list" className="flex min-h-0 flex-col gap-2">
          <div role="toolbar" aria-label="Edit the selected cue" className="flex flex-wrap gap-1" data-testid="edit-bar">
            {tool("Edit", "Enter", () => startEditing(cell), "tool-edit")}
            {tool("Start to playhead", "[", () => act({ kind: "set-start" }), "tool-start")}
            {tool("End to playhead", "]", () => act({ kind: "set-end" }), "tool-end")}
            {tool("−100 ms", "Alt+ArrowLeft", () => act({ kind: "nudge", delta_ms: -100 }), "tool-earlier")}
            {tool("+100 ms", "Alt+ArrowRight", () => act({ kind: "nudge", delta_ms: 100 }), "tool-later")}
            {tool("Split", "Meta+Shift+S", split, "tool-split")}
            {tool("Merge with next", "Meta+M", merge, "tool-merge", noRow || selected >= rows.length - 1)}
            {tool("Insert", "", insert, "tool-insert", false)}
            {tool("Delete", "", () => row && requests.edit({ op: "delete", cue: row.id }), "tool-delete")}
            {tool("Undo", "Meta+Z", requests.undo, "tool-undo", !episode.can_undo)}
            {tool("Redo", "Meta+Shift+Z", requests.redo, "tool-redo", !episode.can_redo)}
            <button type="button" className={control} aria-pressed={finding} onClick={() => setFinding(!finding)} data-testid="tool-find">Find and replace</button>
          </div>
          <div className="min-h-0 flex-1">
            <CueList
              listRef={list}
              rows={rows}
              words={episode.words}
              track={shownTrack}
              current={current}
              word={word}
              selected={selected}
              cell={cell}
              editing={editing}
              follow={follow}
              onPick={(index, which) => select(index, which)}
              onKeyDown={onListKey}
              onDraft={(text) => setEditing((e) => (e ? { ...e, text } : e))}
              onEditKey={onEditKey}
              editorRef={editor}
            />
          </div>
        </section>
      </div>
    </div>
  );
}
