import { type FormEvent, type KeyboardEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { canonicalOffset, indexAt, splitPoint, trackCues, wordAt } from "@/lib/cues";
import { newCueIds, shownIds } from "@/lib/ids";
import { type Action, BIG_NUDGE_MS, type KeyLike, NUDGE_MS, actionFor } from "@/lib/keys";
import { captionLines, type Showing } from "@/lib/overlay";
import { selectedIds, selectionRange } from "@/lib/retranslate";
import type { Busy, EditOp, EpisodeView, Progress } from "@/types";

import { BusyNote } from "./BusyNote";
import { ConflictPicker } from "./ConflictPicker";
import { type Cell, type Editing } from "./CueRow";
import { CueList } from "./CueList";
import { FindReplace } from "./FindReplace";
import { Player } from "./Player";
import { Retranslate } from "./Retranslate";
import { SaveBar } from "./SaveBar";

const SPEEDS = [0.75, 1, 1.25] as const; // the practice aids' playback rates (spec §20)
const INSERT_MS = 2000; // a new cue's length, where the gap allows
export const control = "rounded-md border border-input bg-background px-2 py-1 text-sm focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ring disabled:opacity-50";

/** What the editor asks the server for: every edit goes through its `apply` (spec §20). */
export type Requests = {
  edit: (op: EditOp) => void;
  undo: () => void;
  redo: () => void;
  save: (formats: ("srt" | "ass")[]) => void;
  resolve: (track: string, rendition: string) => void;
  retranslate: (track: string, ids: string[] | null, allowCloud: boolean) => void; // null: stale
};

/** Saving's state, from App: the drafts tabs left for these versions (S34, Decision 31), and a
 * count that goes up each time a Save or a pick finds a track in conflict, which opens the
 * picker. */
export type Saving = {
  drafts: { key: string; at: string; steps: number }[];
  conflictsFound: number;
  onTyping: (typing: boolean) => void;
  onRestore: (key: string) => void;
  onDiscard: () => void;
};

/** The editor (spec §20): the path box, then, once an episode is open, the player on the left
 * and the cue list on the right, with the edit bar, Retranslate (where the engine has models:
 * `generate`) and find and replace. */
export function Editor({ episode, busy, progress, retranslating, pathInput, generate, onOpen, onCantPlay, requests, saving }: {
  episode: EpisodeView | null;
  busy: Busy;
  progress: Progress;
  retranslating: string[]; // the tracks with a retranslation sent and not yet answered
  pathInput: boolean;
  generate: boolean;
  onOpen: (path: string) => void;
  onCantPlay: () => void;
  requests: Requests;
  saving: Saving;
}) {
  return (
    <div className="flex h-full min-h-0 flex-col gap-3 p-4" data-testid="editor">
      {pathInput && <OpenForm busy={busy} onOpen={onOpen} />}
      {episode ? (
        <EpisodeEditor key={episode.id} episode={episode} busy={busy} progress={progress} retranslating={retranslating} generate={generate} requests={requests} saving={saving} onCantPlay={onCantPlay} />
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

function EpisodeEditor({ episode, busy, progress, retranslating, generate, requests, saving, onCantPlay }: {
  episode: EpisodeView;
  busy: Busy;
  progress: Progress;
  retranslating: string[];
  generate: boolean;
  requests: Requests;
  saving: Saving;
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
  const [anchor, setAnchor] = useState<string | null>(null); // where a Shift selection started
  const [cell, setCell] = useState<Cell>("source");
  const [trId, setTrId] = useState<string | null>(null); // the chosen translation cue of the row
  const [editing, setEditing] = useState<Editing | null>(null);
  const [finding, setFinding] = useState(false);
  const conflicted = episode.tracks.filter((t) => t.in_conflict);
  const [picking, setPicking] = useState(conflicted.length > 0); // open at once on a torn episode
  const media = useRef<HTMLVideoElement | HTMLAudioElement | null>(null);
  const list = useRef<HTMLDivElement>(null);
  const editor = useRef<HTMLTextAreaElement>(null);
  const pending = useRef<string | null>(null); // an inserted cue's id, to select and edit
  const editingNow = useRef<Editing | null>(null); // `editing`, for effects that must not re-run
  editingNow.current = editing;

  const rows = episode.rows;
  const shownTrack = track && episode.tracks.some((t) => t.key === track) ? track : null;
  const trCues = useMemo(() => trackCues(rows, shownTrack), [rows, shownTrack]);
  const selected = sel.index;
  const row = selected >= 0 && selected < rows.length ? rows[selected] : undefined;
  const range = selectionRange(rows, selected, anchor);

  // The rows change with every edit: the selection follows its cue, else stays at its place (a
  // split or merge replaces the cue's id); an inserted cue is selected and edited.
  useEffect(() => {
    if (pending.current) {
      const at = rows.findIndex((r) => r.id === pending.current);
      if (at >= 0) { // (until it shows: a draft's own edit can come back first)
        pending.current = null;
        // Only when no box is open: an insert answered late (while the sound is made, minutes)
        // must not replace a draft opened since (the re-review's R-1).
        if (!editingNow.current) {
          setSel({ index: at, id: rows[at].id });
          setCell("source");
          setTrId(null);
          setEditing({ id: rows[at].id, cell: "source", trId: null, track: null, text: rows[at].text });
          return;
        }
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

  useEffect(() => {
    if (saving.conflictsFound > 0) setPicking(true);
  }, [saving.conflictsFound]);

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

  // The rows or the translation's cues changed (an edit, undo or redo): current, word and trAt
  // are indexes into them, so they are found again from the playhead. Until this runs, the render
  // below reads them safely (the Spec review's S-1: a delete once blanked the page). The same
  // holds after a Save or a pick, which replace the rows.
  const seen = useRef({ rows, trCues });
  useEffect(() => {
    if (seen.current.rows === rows && seen.current.trCues === trCues) return;
    seen.current = { rows, trCues };
    onTime(Math.round((media.current?.currentTime ?? 0) * 1000));
  }, [rows, trCues, onTime]);

  const playhead = () => Math.round((media.current?.currentTime ?? 0) * 1000);
  const seekTo = (ms: number) => {
    if (media.current) media.current.currentTime = ms / 1000;
  };
  const select = (index: number, which: Cell = cell, chosen: string | null = null, extend = false) => {
    if (index < 0 || index >= rows.length) return;
    setAnchor(extend ? (anchor ?? sel.id) : null);
    // Moving off the cell being edited commits its draft: Esc is the only way out that discards.
    if (editing && !(rows[index].id === editing.id && which === editing.cell && (chosen ?? editing.trId) === editing.trId)) {
      commit();
      setEditing(null);
    }
    setSel({ index, id: rows[index].id });
    setCell(which);
    setTrId(chosen);
    seekTo(rows[index].start_ms + 1);
  };
  const focusList = () => list.current?.focus();

  const startEditing = (which: Cell) => {
    if (!row) return;
    // A retranslation of this track replaces its lines: a box opened now would lose its text
    // (the note above says why). Nothing opens, and focus stays where it was.
    if (which === "translation" && shownTrack && retranslating.includes(shownTrack)) return;
    const open = which === "source" ? { cell: which, trId: null as string | null }
      : shownTrack ? { cell: which, trId: row.tr[shownTrack]?.cues.find((c) => c.id === trId)?.id ?? row.tr[shownTrack]?.cues[0]?.id ?? null } : null;
    if (!open || (which === "translation" && !open.trId)) return;
    if (editing) {
      if (editing.id === row.id && editing.cell === open.cell && editing.trId === open.trId) {
        editor.current?.focus(); // already open: its draft stays
        return;
      }
      commit(); // another cell: the draft is not thrown away
    }
    const text = which === "source" ? row.text : row.tr[shownTrack ?? ""]?.cues.find((c) => c.id === open.trId)?.text ?? "";
    setEditing({ id: row.id, cell: which, trId: open.trId, track: which === "source" ? null : shownTrack, text });
  };
  // The cue being edited, which is not always the selected one.
  const editedRow = () => (editing ? rows.find((r) => r.id === editing.id) : undefined);
  const commit = (): boolean => {
    const target = editedRow();
    if (!editing || !target) return false;
    const before = editing.cell === "source" ? target.text : target.tr[editing.track ?? ""]?.cues.find((c) => c.id === editing.trId)?.text;
    if (editing.text === before) return false;
    if (editing.cell === "source") requests.edit({ op: "set_text", cue: editing.id, text: editing.text });
    else if (editing.track && editing.trId) requests.edit({ op: "set_translation_text", track: editing.track, cue: editing.trId, text: editing.text });
    return true;
  };
  // A box whose text differs from its cue is an unsaved edit the server has not seen (the Spec
  // review's C-1): Save counts it, commits it first, and closing the tab warns of it.
  const boxText = (() => {
    const target = editedRow();
    if (!editing || !target) return undefined;
    return editing.cell === "source" ? target.text : target.tr[editing.track ?? ""]?.cues.find((c) => c.id === editing.trId)?.text;
  })();
  const typing = editing !== null && boxText !== undefined && editing.text !== boxText;
  const { onTyping } = saving;
  useEffect(() => {
    onTyping(typing);
    return () => onTyping(false);
  }, [typing, onTyping]);
  // Moving off the box to Save or to the picker commits its draft, as moving to another cell does.
  const flushBox = () => {
    if (!editing) return;
    commit();
    setEditing(null);
  };
  const stopEditing = () => {
    setEditing(null);
    focusList();
  };
  // Split at the caret in edit mode (committing the text first), else at the space nearest the
  // playhead's share of the cue; at the playhead when it is inside the cue, else at the caret's
  // share of the cue's time. Always the cue being edited, and counted as the server counts.
  const split = () => {
    const target = editedRow() ?? row;
    if (!target) return;
    const ph = playhead();
    const inside = target.start_ms < ph && ph < target.end_ms;
    let length = Array.from(target.text).length;
    let at: number;
    if (editing?.cell === "source") {
      const caret = editor.current?.selectionStart ?? Math.floor(editing.text.length / 2);
      at = canonicalOffset(editing.text, caret);
      length = canonicalOffset(editing.text, editing.text.length);
      commit();
      stopEditing();
    } else {
      if (editing) {
        commit();
        stopEditing();
      }
      at = splitPoint(target.text, inside ? (ph - target.start_ms) / (target.end_ms - target.start_ms) : 0.5);
    }
    const share = length ? at / length : 0.5;
    const at_ms = inside ? ph
      : Math.min(target.end_ms - 1, Math.max(target.start_ms + 1, Math.round(target.start_ms + (target.end_ms - target.start_ms) * share)));
    const [a, b] = newCueIds(2, shownIds(rows));
    requests.edit({ op: "split", cue: target.id, at_char: at, at_ms, ids: [a, b] });
  };
  const merge = () => {
    const target = editedRow() ?? row;
    if (!target) return;
    if (editing) {
      commit();
      stopEditing();
    }
    // the merged cue's id, and one for each translation track, in case its two parts' cues join
    const tracks = episode.tracks.filter((t) => t.role !== "source").map((t) => t.key);
    const [id, ...joined] = newCueIds(1 + tracks.length, shownIds(rows));
    requests.edit({ op: "merge_next", cue: target.id, id, joined: Object.fromEntries(tracks.map((k, i) => [k, joined[i]])) });
  };
  const insert = () => {
    if (editing) {
      commit(); // a draft is committed, never replaced by the new cue's box
      setEditing(null);
    }
    const ph = playhead();
    let start = ph;
    if (indexAt(rows, ph) >= 0 && row) start = row.end_ms;
    const next = rows.find((r) => r.start_ms > start);
    const end = Math.min(start + INSERT_MS, next ? next.start_ms : start + INSERT_MS);
    const [id] = newCueIds(1, shownIds(rows));
    pending.current = id;
    requests.edit({ op: "insert", start_ms: start, end_ms: end, text: "…", id });
  };

  // ←/→ choose the source or the translation cell; on a translation cell holding several cues,
  // → moves to the next one and ← back to the one before (the Spec review's S-8).
  const chooseCell = (which: Cell) => {
    const cues = shownTrack && row ? row.tr[shownTrack]?.cues ?? [] : [];
    if (which === "translation" && !shownTrack) return;
    if (cell === "translation" && cues.length > 1) {
      const at = Math.max(0, cues.findIndex((c) => c.id === (trId ?? cues[0].id)));
      const to = at + (which === "translation" ? 1 : -1);
      if (to >= 0 && to < cues.length) {
        setTrId(cues[to].id);
        return;
      }
      if (which === "translation") return;
    }
    setCell(which);
    setTrId(null);
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
      case "extend": select(Math.min(rows.length - 1, Math.max(0, selected + a.by)), cell, null, true); return;
      case "cell": chooseCell(a.cell); return;
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
    if (selected < 0 && (a.kind === "next" || a.kind === "previous" || a.kind === "extend")) {
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
    const at = rows[current] ? current : selected;
    setLoop(loop || !rows[at] ? null : { start_ms: rows[at].start_ms, end_ms: rows[at].end_ms });
  };
  const changeRate = (value: number) => {
    setRate(value);
    if (media.current) media.current.playbackRate = value;
  };

  // (current and trAt can name a cue an edit has just removed, until the effect above runs; a
  // track gone into conflict has no cues until it is picked, which reads the same way)
  const lines = captionLines(showing, rows[current]?.text ?? null, trCues[trAt]?.text ?? null);
  const stale = translations.filter((t) => t.all_stale);
  const noRow = !row;
  const tool = (label: string, keys: string, onClick: () => void, testid: string, disabled = noRow) => (
    <button type="button" className={control} onClick={onClick} disabled={disabled} aria-keyshortcuts={keys || undefined} title={keys ? `${label} (${keys})` : label} data-testid={testid}>
      {label}
    </button>
  );

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <header className="flex flex-col gap-1">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <h1 className="truncate text-lg font-bold" data-testid="episode-name">{episode.video.name}</h1>
          <SaveBar dirty={episode.dirty || typing} busy={busy} formats={episode.formats} drafts={saving.drafts}
            onSave={(formats) => { flushBox(); requests.save(formats); }} onRestore={saving.onRestore} onDiscard={saving.onDiscard} />
        </div>
        {(episode.notes.length > 0 || stale.length > 0 || conflicted.length > 0) && (
          <ul role="status" className="flex flex-col gap-0.5 text-sm" data-testid="episode-notes">
            {episode.notes.map((note, k) => <li key={k}>{note}</li>)}
            {stale.map((t) => (
              <li key={`stale-${t.key}`}>
                Every {t.label} cue is stale: the glossary or the translation model changed since it was made, or a glossary term is waiting for Save.
                {generate && " Retranslate stale redoes them all, except those you edited."}
              </li>
            ))}
            {conflicted.map((t) => (
              <li key={`conflict-${t.key}`} className="flex flex-wrap items-center gap-2 text-destructive">
                The {t.label} track has two versions: pick one before editing it.
                <button type="button" className={control} onClick={() => { flushBox(); setPicking(true); }} data-testid="pick-version">Pick a version</button>
              </li>
            ))}
          </ul>
        )}
        <BusyNote busy={busy} retranslating={retranslating.length ? (episode.tracks.find((t) => t.key === retranslating[0])?.label ?? retranslating[0]) : null} />
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
          <ConflictPicker episode={episode} open={picking && conflicted.length > 0} onClose={() => setPicking(false)}
            onPick={(track, rendition) => { requests.resolve(track, rendition); setPicking(false); }} />
        </section>
        <section aria-label="Cue list" className="flex min-h-0 flex-col gap-2">
          {generate && shownTrack && (
            <Retranslate
              key={shownTrack} // another track's box starts unticked too (Decision 33)
              label={translations.find((t) => t.key === shownTrack)?.label ?? shownTrack}
              selected={range ? range[1] - range[0] + 1 : 0}
              busy={busy}
              progress={progress}
              pending={retranslating.length > 0}
              onSelected={(allowCloud) => { flushBox(); requests.retranslate(shownTrack, selectedIds(rows, range), allowCloud); }}
              onStale={(allowCloud) => { flushBox(); requests.retranslate(shownTrack, null, allowCloud); }}
            />
          )}
          <div role="toolbar" aria-label="Edit the selected cue" className="flex flex-wrap gap-1" data-testid="edit-bar">
            {tool("Edit", "Enter", () => startEditing(cell), "tool-edit")}
            {editing && tool("Commit", "Meta+Enter", () => act({ kind: "commit" }), "tool-commit", false)}
            {editing && tool("Cancel", "Escape", () => act({ kind: "cancel" }), "tool-cancel", false)}
            {tool("Start to playhead", "[", () => act({ kind: "set-start" }), "tool-start")}
            {tool("End to playhead", "]", () => act({ kind: "set-end" }), "tool-end")}
            {tool("−500 ms", "Alt+Shift+ArrowLeft", () => act({ kind: "nudge", delta_ms: -BIG_NUDGE_MS }), "tool-earlier-500")}
            {tool("−100 ms", "Alt+ArrowLeft", () => act({ kind: "nudge", delta_ms: -NUDGE_MS }), "tool-earlier")}
            {tool("+100 ms", "Alt+ArrowRight", () => act({ kind: "nudge", delta_ms: NUDGE_MS }), "tool-later")}
            {tool("+500 ms", "Alt+Shift+ArrowRight", () => act({ kind: "nudge", delta_ms: BIG_NUDGE_MS }), "tool-later-500")}
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
              range={range}
              cell={cell}
              trId={trId}
              editing={editing}
              follow={follow}
              onPick={(index, which, extend, id) => select(index, which, id ?? null, extend)}
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
