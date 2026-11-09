// What the page says when its websocket to the engine closes (Review Focus 5). Shiny's own
// reconnect stays off, so the page never retries by itself. It asks the engine for "/" once, with
// its cookie: a 401 means the engine was restarted and this page's cookie is from the old launch,
// so the person must open the new link; no answer means vid2sub isn't running; any other answer
// means the engine is up, and a reload carries on. A refused websocket handshake reaches the
// browser as an HTTP 403 (close code 1006), never 1008, so the close code can't tell these apart.

/** auth.SIGN_IN_AGAIN, as the engine says it to a request without its cookie. */
export const SIGN_IN_AGAIN = "open the link vid2sub printed when it started";

export type Lost = "signed-out" | "stopped" | "dropped";

export const LOST_MESSAGES: Record<Lost, string> = {
  "signed-out": `vid2sub was restarted, so this page is signed out: ${SIGN_IN_AGAIN}.`,
  stopped: "vid2sub isn't running. Start it again, then open the link it prints.",
  dropped: "The connection to vid2sub closed. Reload the page to carry on.",
};

type Fetch = (input: string, init: RequestInit) => Promise<{ status: number }>;

/** Asks the engine once why the connection closed. */
export async function whyLost(fetchFn: Fetch): Promise<Lost> {
  try {
    const r = await fetchFn("/", { cache: "no-store", credentials: "same-origin" });
    return r.status === 401 ? "signed-out" : "dropped";
  } catch {
    return "stopped";
  }
}
