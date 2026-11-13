// The page's own Shiny connection, as far as a typed key needs it (spec §5.3). shiny.js queues
// every message sent while it has no socket in `shinyapp.$pendingMessages` (`$sendMsg`), and
// vid2sub never reconnects (Review Focus 5), so a key queued then would sit in the page's heap
// for good. This is the one place that reads that private field: through typed guards, so a
// shiny.js without it is a no-op, never a throw (Task 18 fix round 1, I-2).

type ShinyApp = { isConnected?: unknown; $pendingMessages?: unknown };

/** The page's `Shiny.shinyapp`, if there is one. */
export function shinyApp(): ShinyApp | undefined {
  return (window as unknown as { Shiny?: { shinyapp?: ShinyApp } }).Shiny?.shinyapp;
}

/** Whether shiny.js has a socket. Assumed true where it can't be told. */
export function pageConnected(app: ShinyApp | undefined = shinyApp()): boolean {
  return typeof app?.isConnected === "function" ? Boolean((app as { isConnected: () => unknown }).isConnected()) : true;
}

/** Removes every queued message that carries `typed_key` (a key, or the null that replaces it). */
export function dropQueuedKeys(app: ShinyApp | undefined = shinyApp()): void {
  const queue = app?.$pendingMessages;
  if (!Array.isArray(queue)) return;
  for (let i = queue.length - 1; i >= 0; i--) {
    if (typeof queue[i] === "string" && (queue[i] as string).includes("typed_key")) queue.splice(i, 1);
  }
}
