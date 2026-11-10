// Sends the editor's requests one per task, in order. shinyreact debounces each input with a
// trailing setTimeout (useSetShinyInput's debounceMs; 0 still waits for the next task), so two
// values set in one task reach the server as the last one only: a commit and a split sent
// together, or a draft replayed, would lose all but one. Each queued send runs in a task of its
// own, after the debounce timer the one before it started, since timers of equal delay run in
// the order they were set (HTML's timer initialisation steps).

export type Schedule = (run: () => void) => void;

const nextTask: Schedule = (run) => void setTimeout(run, 0);

/** A function that queues `send` to run in a later task, after every send queued before it. */
export function pacer(schedule: Schedule = nextTask): (send: () => void) => void {
  const queue: (() => void)[] = [];
  let running = false;
  const pump = () => {
    const next = queue.shift();
    if (!next) {
      running = false;
      return;
    }
    next();
    schedule(pump);
  };
  return (send) => {
    queue.push(send);
    if (!running) {
      running = true;
      schedule(pump);
    }
  };
}
