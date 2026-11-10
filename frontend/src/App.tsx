import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Editor, type Requests, type Saving } from "@/components/Editor";
import { resultNotices } from "@/components/SaveBar";
import { TopBar } from "@/components/TopBar";
import { LOST_MESSAGES, type Lost, whyLost } from "@/lib/connection";
import { type DraftStep, type Offer, type Replay, addStep, clearDraft, draftKey, draftStorage, dropStep, heard, loadDraft, moveDraft, offersFor, tabId, tabStorage } from "@/lib/draft";
import { randomHex } from "@/lib/ids";
import { type Shown, addNotice, dismissNotice } from "@/lib/notices";
import { pacer } from "@/lib/sends";
import { useSetShinyInput, useShinyInitialized, useShinyMessageHandler, useShinyOutputValue } from "@/sr";
import type { AppliedMessage, Busy, Capabilities, EditOp, EpisodeView, SaveResultMessage, Status } from "@/types";

type Ask = { episode: string; n: number };
type Step = { edit: EditOp } | { undo: true } | { redo: true };

type JQueryLike = (target: Document) => {
  on(event: string, handler: () => void): unknown;
  off(event: string, handler: () => void): unknown;
};

export default function App() {
  const initialized = useShinyInitialized();
  // Every output is subscribed here, and every message handler lives here: shinyreact 0.1.0
  // drops a message that has no handler, and an output that unmounts logs "Output <id> not found"
  // for each later value (recordings' App.tsx). A new output or message gets a line here too.
  const capabilities = useShinyOutputValue<Capabilities>("capabilities");
  const status = useShinyOutputValue<Status>("status");
  const episode = useShinyOutputValue<EpisodeView | null>("episode");
  const busy = useShinyOutputValue<Busy>("busy");
  // Every input is set from here too. Each request carries a count, so the same path asked for
  // twice is still two requests. `debounceMs: 0` is still a trailing timer: two values set in one
  // task send only the last.
  const setOpen = useSetShinyInput<{ path: string; n: number } | null>("open", null, { priority: "event", debounceMs: 0 });
  const setPlayback = useSetShinyInput<{ episode: string; n: number } | null>("playback", null, { priority: "event", debounceMs: 0 });
  const setEdit = useSetShinyInput<(Ask & { op: EditOp }) | null>("edit", null, { priority: "event", debounceMs: 0 });
  const setUndo = useSetShinyInput<Ask | null>("undo", null, { priority: "event", debounceMs: 0 });
  const setRedo = useSetShinyInput<Ask | null>("redo", null, { priority: "event", debounceMs: 0 });
  const setSave = useSetShinyInput<(Ask & { formats: ("srt" | "ass")[] }) | null>("save", null, { priority: "event", debounceMs: 0 });
  const setResolve = useSetShinyInput<(Ask & { track: string; rendition: string }) | null>("resolve", null, { priority: "event", debounceMs: 0 });
  const sent = useRef(0);
  // One request per task, in order: shinyreact's debounce keeps only the last value set in a task.
  const pace = useMemo(() => pacer(), []);

  // The crash-recovery draft (spec §14.5, S34; Decision 31): every edit, undo and redo is also
  // written to localStorage as sent, under the heads the episode was opened at and this tab's id,
  // and the server's word that it refused one takes it out again. Opening an episode offers every
  // tab's draft for its heads. Restoring one replays it through the server's rules and clears it
  // only once every step was done again; otherwise it is kept and the editor says how many steps
  // failed. This tab's own draft starts again then, or when the person edits or discards instead
  // of restoring. When a Save or a pick moves the heads, this tab's draft goes with them while
  // edits are still unsaved (a pick keeps the other tracks' edits), and is cleared once
  // everything is saved; no other tab's draft is ever touched by it.
  const tab = useMemo(() => tabId(tabStorage()), []);
  const [offers, setOffers] = useState<Offer[]>([]);
  const offering = useRef(false); // offers are up and this tab's old draft not yet dropped
  const drafted = useRef<{ id: string; key: string; heads: Record<string, string> } | null>(null);
  const replaying = useRef<Replay | null>(null);
  useEffect(() => {
    if (!episode) {
      drafted.current = null;
      return;
    }
    const key = draftKey(episode.heads, tab);
    const was = drafted.current;
    const store = draftStorage();
    if (was?.id === episode.id && was.key !== key) {
      if (episode.dirty) moveDraft(store, was.key, key);
      else clearDraft(store, was.key);
    }
    if (was?.id !== episode.id) {
      const found = offersFor(store, episode.heads);
      offering.current = found.length > 0;
      setOffers(found);
    }
    drafted.current = { id: episode.id, key, heads: episode.heads };
  }, [episode, tab]);
  const dropOffers = useCallback(() => { // editing or discarding instead: this tab starts afresh
    if (!offering.current) return;
    offering.current = false;
    setOffers([]);
    if (drafted.current) clearDraft(draftStorage(), drafted.current.key);
  }, []);

  const episodeId = episode?.id ?? null;
  const steps = useMemo(() => {
    const ask = (): Ask | null => (episodeId ? { episode: episodeId, n: ++sent.current } : null);
    // Sends one edit, undo or redo, and keeps it in the draft as sent; returns its request's count.
    return (step: Step): number | null => {
      const a = ask();
      if (!a) return null;
      if (drafted.current) addStep(draftStorage(), drafted.current.key, { ...step, n: a.n } as DraftStep);
      if ("edit" in step) pace(() => setEdit({ ...a, op: step.edit }));
      else if ("undo" in step) pace(() => setUndo(a));
      else pace(() => setRedo(a));
      return a.n;
    };
  }, [episodeId, pace, setEdit, setUndo, setRedo]);
  const requests = useMemo<Requests>(() => {
    const ask = (): Ask | null => (episodeId ? { episode: episodeId, n: ++sent.current } : null);
    const send = <T,>(set: (v: T) => void, value: T | null) => value && pace(() => set(value));
    return {
      edit: (op) => { dropOffers(); steps({ edit: op }); },
      undo: () => { dropOffers(); steps({ undo: true }); },
      redo: () => { dropOffers(); steps({ redo: true }); },
      save: (formats) => { const a = ask(); send(setSave, a && { ...a, formats }); },
      resolve: (track, rendition) => { const a = ask(); send(setResolve, a && { ...a, track, rendition }); },
    };
  }, [episodeId, pace, dropOffers, steps, setSave, setResolve]);

  useShinyMessageHandler("applied", (data: AppliedMessage) => {
    if (!episode || data.episode !== episode.id) return;
    if (!data.ok && drafted.current) dropStep(draftStorage(), drafted.current.key, data.n);
    const now = replaying.current && heard(replaying.current, data.n, data.ok);
    if (!now) return;
    replaying.current = now.waiting.length ? now : null;
    if (now.waiting.length) return;
    if (!now.refused) clearDraft(draftStorage(), now.from);
    else setNotices((shown) => addNotice(shown, { kind: "error", text: `${now.refused} restored ${now.refused === 1 ? "step" : "steps"} of ${now.total} couldn't be replayed: the draft is kept` }, nextId.current++));
  });

  const [conflictsFound, setConflictsFound] = useState(0);
  useShinyMessageHandler("save_result", (data: SaveResultMessage) => {
    if (!episode || data.episode !== episode.id) return;
    for (const n of resultNotices(data, episode.tracks, episode.video.name)) setNotices((shown) => addNotice(shown, n, nextId.current++));
    if (data.conflicts.length) setConflictsFound((k) => k + 1);
  });
  const saving: Saving = {
    drafts: offers.map((o) => ({ key: o.key, at: o.draft.at, steps: o.draft.steps.length })),
    conflictsFound,
    onRestore: (key) => {
      const at = drafted.current;
      const store = draftStorage();
      const draft = loadDraft(store, key);
      if (!at || !draft) return;
      offering.current = false;
      setOffers([]);
      let from = key;
      if (key === at.key) { // this tab's own (a reload): set aside until the server has redone it
        from = draftKey(at.heads, `t${randomHex(4)}`);
        moveDraft(store, key, from);
      } else {
        clearDraft(store, at.key);
      }
      const sent: number[] = [];
      for (const step of draft.steps) {
        const { n: _, ...asSent } = step;
        const n = steps(asSent as Step);
        if (n !== null) sent.push(n);
      }
      if (sent.length) replaying.current = { from, waiting: sent, refused: 0, total: sent.length };
      else clearDraft(store, from);
    },
    onDiscard: dropOffers,
  };

  // Closing the tab with unsaved edits warns first (S34): listened for only while there are
  // some, as MDN advises; preventDefault, and returnValue for older browsers.
  const dirty = episode?.dirty ?? false;
  useEffect(() => {
    if (!dirty) return;
    const warn = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = true;
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);
  const [notices, setNotices] = useState<Shown[]>([]);
  const nextId = useRef(1);
  useShinyMessageHandler("notice", (data: unknown) => {
    setNotices((shown) => addNotice(shown, data, nextId.current++));
  });

  // The websocket closed: ask the engine once why, and say so; never reconnect (Review Focus 5).
  const [lost, setLost] = useState<Lost | null>(null);
  const check = useCallback(() => {
    void whyLost((input, init) => window.fetch(input, init)).then(setLost);
  }, []);
  useEffect(() => {
    // Shiny triggers shiny:disconnected through jQuery, which addEventListener never sees.
    const $ = (window as unknown as { jQuery?: JQueryLike }).jQuery;
    if (!$) return;
    $(document).on("shiny:disconnected", check);
    return () => void $(document).off("shiny:disconnected", check);
  }, [check]);

  if (!initialized && lost === null) return null; // no flash of empty defaults while connecting
  return (
    <div className="flex h-dvh flex-col" data-testid="app">
      <TopBar capabilities={capabilities} status={status} />
      {lost && (
        // Above Shiny's grey disconnected overlay (z-index 99998), which ignores the pointer.
        <div role="alert" data-testid="lost" className="relative z-[99999] flex items-center gap-3 border-b border-destructive bg-card px-4 py-2 text-destructive">
          <span>{LOST_MESSAGES[lost]}</span>
          {lost === "stopped" && (
            <button type="button" className="underline" onClick={check} data-testid="check-again">Check again</button>
          )}
          {lost === "dropped" && (
            <button type="button" className="underline" onClick={() => window.location.reload()}>Reload</button>
          )}
        </div>
      )}
      <main className="min-h-0 flex-1" data-testid="main">
        <Editor
          episode={episode ?? null}
          busy={busy ?? null}
          pathInput={capabilities?.path_input ?? false}
          onOpen={(path) => setOpen({ path, n: ++sent.current })}
          onCantPlay={() => episode && setPlayback({ episode: episode.id, n: ++sent.current })}
          requests={requests}
          saving={saving}
        />
      </main>
      <section aria-label="Notices" className="fixed right-4 bottom-4 z-[99999] flex w-80 flex-col gap-2">
        <div role="status" aria-live="polite" className="flex flex-col gap-2">
          {notices.filter((n) => n.kind === "info").map((n) => <NoticeCard key={n.id} notice={n} onDismiss={setNotices} />)}
        </div>
        <div role="alert" className="flex flex-col gap-2">
          {notices.filter((n) => n.kind === "error").map((n) => <NoticeCard key={n.id} notice={n} onDismiss={setNotices} />)}
        </div>
      </section>
    </div>
  );
}

function NoticeCard({ notice, onDismiss }: { notice: Shown; onDismiss: (f: (s: Shown[]) => Shown[]) => void }) {
  return (
    <div className={`flex items-start gap-2 rounded-lg border bg-card p-3 text-sm shadow ${notice.kind === "error" ? "border-destructive text-destructive" : "border-border"}`} data-testid="notice">
      {/* Plain text: a notice can carry a file name or a server's error (spec §6.3). */}
      <span className="flex-1">{notice.text}</span>
      <button type="button" aria-label="Dismiss" onClick={() => onDismiss((s) => dismissNotice(s, notice.id))}>×</button>
    </div>
  );
}
