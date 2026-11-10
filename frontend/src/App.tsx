import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Editor, type Requests, type Saving } from "@/components/Editor";
import { resultNotices } from "@/components/SaveBar";
import { TopBar } from "@/components/TopBar";
import { LOST_MESSAGES, type Lost, whyLost } from "@/lib/connection";
import { type DraftStep, type Offer, type Replay, addStep, clearDraft, draftKey, draftStorage, dropStep, followHeads, heard, loadDraft, moveDraft, offersFor, replayable, tabId, tabStorage, trimSaved } from "@/lib/draft";
import { randomHex } from "@/lib/ids";
import { type Shown, addNotice, dismissNotice } from "@/lib/notices";
import { retranslateNotice } from "@/lib/retranslate";
import { pacer } from "@/lib/sends";
import { useSetShinyInput, useShinyInitialized, useShinyMessageHandler, useShinyOutputValue } from "@/sr";
import type { AppliedMessage, Busy, Capabilities, EditOp, EpisodeView, Progress, RetranslateResultMessage, SaveResultMessage, Status } from "@/types";

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
  const progress = useShinyOutputValue<Progress>("progress");
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
  const setRetranslate = useSetShinyInput<(Ask & { track: string; ids: string[] | null; allow_cloud: boolean }) | null>("retranslate", null, { priority: "event", debounceMs: 0 });
  const sent = useRef(0);
  // One request per task, in order: shinyreact's debounce keeps only the last value set in a task.
  const pace = useMemo(() => pacer(), []);

  // The crash-recovery draft (spec §14.5, S34; Decision 31): every edit, undo and redo is also
  // written to localStorage as sent, under the heads the episode was opened at and this tab's id,
  // and the server's word that it refused one takes it out again. Opening an episode offers every
  // tab's draft for its heads. Restoring one replays it through the server's rules and clears it
  // only once every step was done again; otherwise it is kept and the editor says how many steps
  // failed. This tab's own draft starts again then, or when the person edits or discards instead
  // of restoring. When a Save or a pick moves the heads, this tab's draft always goes with them;
  // a Save then takes out the steps it wrote (a pick writes none, and keeps the other tracks'
  // edits). A draft on offer is the exception: a Save that moves the heads clears it (it was made
  // on versions that are gone), a Save that changed nothing leaves it on offer (Q&A item 51). No
  // other tab's draft is ever touched by it.
  const tab = useMemo(() => tabId(tabStorage()), []);
  const [offers, setOffers] = useState<Offer[]>([]);
  const offering = useRef(false); // offers are up and this tab's old draft not yet dropped
  const drafted = useRef<{ id: string; key: string; heads: Record<string, string> } | null>(null);
  const replaying = useRef<Replay | null>(null);
  const saveSent = useRef<number | null>(null); // the count of the Save in flight
  const saveInFlight = useRef(false); // a Save was sent and its result is not yet acted on
  const saved = useRef(0); // the count of the last Save heard to have written (steps up to it are in a version)
  useEffect(() => {
    if (!episode) {
      drafted.current = null;
      return;
    }
    const key = draftKey(episode.heads, tab);
    const was = drafted.current;
    const store = draftStorage();
    if (was?.id === episode.id && was.key !== key) {
      // A Save or a pick moved the heads: this tab's draft goes with them, less what a Save has
      // written (a Save's own result trims it too, whichever arrives first), and what is on offer
      // is worked out again for the new heads (the Spec review's C-2, C-3).
      if (offering.current) {
        // A draft on offer is from an earlier page, whose request counts mean nothing here, so
        // no Save's count trims it. A Save that moved the heads under it clears it (it was made
        // on versions that are gone); a pick carries it.
        if (saveInFlight.current) clearDraft(store, was.key);
        else moveDraft(store, was.key, key);
      } else {
        followHeads(store, was.key, key, saved.current);
      }
      if (offering.current) {
        const found = offersFor(store, episode.heads);
        offering.current = found.length > 0;
        setOffers(found);
      }
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

  // A retranslation goes in the draft as a marker only (never replayed: a restored draft asks no
  // model), dropped when the server says it changed nothing; `asking` remembers which were
  // "Retranslate stale", for the notice.
  const asking = useRef(new Map<number, { track: string; stale: boolean }>());
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
      save: (formats) => {
        const a = ask();
        if (a) {
          saveSent.current = a.n;
          saveInFlight.current = true;
        }
        send(setSave, a && { ...a, formats });
      },
      resolve: (track, rendition) => {
        saveInFlight.current = false; // a pick is not a Save's heads
        const a = ask();
        send(setResolve, a && { ...a, track, rendition });
      },
      retranslate: (track, ids, allowCloud) => {
        const a = ask();
        if (!a) return;
        dropOffers();
        if (drafted.current) addStep(draftStorage(), drafted.current.key, { retranslate: true, n: a.n });
        asking.current.set(a.n, { track, stale: ids === null });
        send(setRetranslate, { ...a, track, ids, allow_cloud: allowCloud });
      },
    };
  }, [episodeId, pace, dropOffers, steps, setSave, setResolve, setRetranslate]);
  useShinyMessageHandler("retranslate_result", (data: RetranslateResultMessage) => {
    if (!episode || data.episode !== episode.id || data.n === null) return;
    const asked = asking.current.get(data.n);
    asking.current.delete(data.n);
    if (data.changed === 0 && drafted.current) dropStep(draftStorage(), drafted.current.key, data.n);
    if (!asked) return;
    const label = episode.tracks.find((t) => t.key === asked.track)?.label ?? asked.track;
    const n = retranslateNotice(data.changed, label, asked.stale);
    if (n) setNotices((shown) => addNotice(shown, n, nextId.current++));
  });

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
  const [savesHeard, setSavesHeard] = useState(0);
  const [typing, setTyping] = useState(false); // a box open whose text isn't committed (C-1)
  useShinyMessageHandler("save_result", (data: SaveResultMessage) => {
    if (!episode || data.episode !== episode.id) return;
    for (const n of resultNotices(data, episode.tracks, episode.video.name)) setNotices((shown) => addNotice(shown, n, nextId.current++));
    if (data.conflicts.length) setConflictsFound((k) => k + 1);
    const at = drafted.current;
    if (data.kind !== "save" || !at) return;
    // What this Save wrote is no longer unsaved: the steps up to its count leave the draft, and
    // the ones sent behind it stay. A draft on offer holds steps from an earlier page, not this
    // Save's: it is left alone here (the effect on the heads clears it if they moved).
    saved.current = Math.max(saved.current, saveSent.current ?? 0);
    if (!offering.current) trimSaved(draftStorage(), at.key, saved.current);
    setSavesHeard((k) => k + 1);
  });
  // Declared after the effect on the episode, so that once the episode this Save made has been
  // seen (it is published before the result is sent), the Save no longer counts as in flight.
  useEffect(() => {
    if (savesHeard > 0) saveInFlight.current = false;
  }, [savesHeard]);
  const saving: Saving = {
    // the steps Restore would send, for each draft that has any
    drafts: offers.map((o) => ({ key: o.key, at: o.draft.at, steps: replayable(o.draft.steps).length })).filter((d) => d.steps > 0),
    conflictsFound,
    onTyping: setTyping,
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
      for (const step of replayable(draft.steps)) {
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
  const dirty = (episode?.dirty ?? false) || typing;
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
    // A refused Save sends no result, only a notice: it no longer moves the heads.
    if ((data as { kind?: unknown } | null)?.kind === "error") saveInFlight.current = false;
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
          progress={progress ?? null}
          pathInput={capabilities?.path_input ?? false}
          generate={capabilities?.generate ?? false}
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
