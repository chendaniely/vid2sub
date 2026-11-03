"""The job queue: one worker thread runs submitted inputs one at a time (spec §17.1, S36).

Jobs live in the engine's memory, owned by the engine rather than a browser tab, so closing a tab
cancels nothing and reopening shows the progress; when the engine exits the list is gone, and
finished results are already on disk (Dan, 2026-10-14). One worker runs one job at a time,
because the Spark's whisper serves one request at a time anyway. Cancel takes a queued job out of
the queue, or asks the running one to stop at its next check, between chunks or translation
batches (`pipeline.Cancelled`; the Phase 2 plan's Decision 7). Listeners are called after every
change of state, stage or progress, on the thread that made it (the worker, or the caller of
`submit`, `cancel` or `close`); one that raises is logged and the queue carries on. The log names
jobs by id and errors by kind, never an input, a title or a path (spec §6.8).
"""

from __future__ import annotations

import dataclasses
import logging
import secrets
import threading
from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from vid2sub.pipeline import Cancelled, Event, InputResult

log = logging.getLogger(__name__)

JobState = Literal["queued", "running", "done", "failed", "cancelled"]
Runner = Callable[[str, Event, Callable[[], bool]], InputResult]
_IMPLIED_STAGE = {"chunk": "transcribe", "batch": "translate"}


@dataclass(frozen=True)
class JobView:
    id: str
    input: str
    state: JobState
    stage: str | None = None
    progress: tuple[int, int] | None = None  # (index, of): a chunk or a translation batch
    result: InputResult | None = None
    hint: str | None = None


class Queue:
    def __init__(self, runner: Runner):
        self._runner = runner
        self._lock = threading.Condition()
        self._jobs: dict[str, JobView] = {}  # in the order they were submitted
        self._waiting: deque[str] = deque()
        self._running: str | None = None
        self._stop = threading.Event()  # set: the running job should stop
        self._listeners: list[Callable[[], None]] = []
        self._closed = False
        self._worker = threading.Thread(target=self._work, name="vid2sub-jobs", daemon=True)
        self._worker.start()

    def submit(self, inputs: Sequence[str]) -> list[str]:
        with self._lock:
            if self._closed:
                raise RuntimeError("the job queue is closed")
            ids = []
            for source in inputs:
                job_id = self._new_id()
                self._jobs[job_id] = JobView(job_id, source, "queued")
                self._waiting.append(job_id)
                ids.append(job_id)
            self._lock.notify()
        self._changed()
        return ids

    def cancel(self, job_id: str) -> bool:
        """True if the job was queued (now cancelled) or running (now asked to stop)."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.state not in ("queued", "running"):
                return False
            if job.state == "running":
                self._stop.set()
                return True
            self._waiting.remove(job_id)
            self._set(job_id, state="cancelled")
        self._changed()
        return True

    def jobs(self) -> list[JobView]:
        with self._lock:
            return list(self._jobs.values())

    def on_change(self, fn: Callable[[], None]) -> None:
        with self._lock:
            self._listeners.append(fn)

    def close(self, timeout: float = 5.0) -> None:
        """Cancels every queued job and the running one, then waits up to `timeout` seconds
        for the worker to stop."""
        with self._lock:
            self._closed = True
            while self._waiting:
                self._set(self._waiting.popleft(), state="cancelled")
            if self._running is not None:
                self._stop.set()
            self._lock.notify()
        self._changed()
        self._worker.join(timeout)

    def _new_id(self) -> str:
        while True:
            job_id = "j" + secrets.token_hex(4)
            if job_id not in self._jobs:
                return job_id

    def _set(self, job_id: str, **changes: Any) -> None:
        """Called with the lock held."""
        self._jobs[job_id] = dataclasses.replace(self._jobs[job_id], **changes)

    def _changed(self) -> None:
        with self._lock:
            listeners = list(self._listeners)
        for fn in listeners:
            try:
                fn()
            except Exception as err:  # noqa: BLE001 - a listener's bug never stops the queue
                log.error("a job listener raised %s", type(err).__name__)

    def _work(self) -> None:
        while True:
            with self._lock:
                while not self._waiting and not self._closed:
                    self._lock.wait()
                if not self._waiting:
                    return
                job_id = self._waiting.popleft()
                self._running = job_id
                self._stop.clear()
                self._set(job_id, state="running")
                source = self._jobs[job_id].input
            self._changed()
            final = self._run(job_id, source)
            with self._lock:
                self._set(job_id, **final)
                self._running = None
            self._changed()

    def _run(self, job_id: str, source: str) -> dict[str, Any]:
        def event(kind: str, fields: dict[str, Any]) -> None:
            if kind == "stage":
                changes = {"stage": fields.get("stage"), "progress": None}
            elif kind in _IMPLIED_STAGE:
                changes = {"stage": _IMPLIED_STAGE[kind],
                           "progress": (fields.get("index"), fields.get("of"))}
            else:
                return
            with self._lock:
                self._set(job_id, **changes)
            self._changed()

        try:
            result = self._runner(source, event, self._stop.is_set)
        except Cancelled:
            log.info("job %s cancelled", job_id)
            return {"state": "cancelled"}
        except Exception as err:  # noqa: BLE001 - a bug fails one job, not the queue (§17.3)
            log.error("job %s failed: %s", job_id, type(err).__name__)
            return {"state": "failed", "hint": None}
        if result.status == "failed":
            log.info("job %s failed: %s", job_id, result.kind or "failed")
        state = "failed" if result.status == "failed" else "done"
        return {"state": state, "result": result, "hint": result.hint or None}
