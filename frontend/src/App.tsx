import { useCallback, useEffect, useRef, useState } from "react";

import { TopBar } from "@/components/TopBar";
import { LOST_MESSAGES, type Lost, whyLost } from "@/lib/connection";
import { type Shown, addNotice, dismissNotice } from "@/lib/notices";
import { useShinyInitialized, useShinyMessageHandler, useShinyOutputValue } from "@/sr";
import type { Capabilities, Status } from "@/types";

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
      <main className="flex flex-1 items-center justify-center text-muted-foreground" data-testid="main">
        <p>The editor opens here.</p>
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
