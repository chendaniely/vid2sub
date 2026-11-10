import { describe, expect, it, vi } from "vitest";

import { pacer } from "./sends";

describe("sending requests one per task", () => {
  it("runs each queued send in a task of its own, in order", () => {
    const tasks: (() => void)[] = [];
    const send = pacer((run) => void tasks.push(run));
    const sent: string[] = [];
    send(() => sent.push("set_text"));
    send(() => sent.push("split"));
    expect(sent).toEqual([]); // nothing in the task that queued them
    tasks.shift()!();
    expect(sent).toEqual(["set_text"]);
    expect(tasks).toHaveLength(1);
    tasks.shift()!();
    expect(sent).toEqual(["set_text", "split"]);
    tasks.shift()!(); // the queue is empty: it stops scheduling
    expect(tasks).toHaveLength(0);
    send(() => sent.push("undo"));
    tasks.shift()!();
    expect(sent).toEqual(["set_text", "split", "undo"]);
  });

  it("keeps two sends apart even when the setter debounces with setTimeout(0)", async () => {
    // shinyreact's debounce, as in its bundle: a trailing setTimeout that keeps the last value
    const delivered: number[] = [];
    let timer: ReturnType<typeof setTimeout> | null = null;
    const setter = (v: number) => {
      if (timer !== null) clearTimeout(timer);
      timer = setTimeout(() => { timer = null; delivered.push(v); }, 0);
    };
    // (waited for, not slept on: a loaded machine runs timers late, never out of order)
    const settled = { timeout: 2000, interval: 10 };
    for (const v of [1, 2, 3]) setter(v); // why the pacer exists: set in one task, two are lost
    await vi.waitFor(() => expect(delivered).toEqual([3]), settled);
    delivered.length = 0;
    const send = pacer();
    for (const v of [1, 2, 3]) send(() => setter(v));
    await vi.waitFor(() => expect(delivered).toEqual([1, 2, 3]), settled);
  });
});
