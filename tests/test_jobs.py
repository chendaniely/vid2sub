import dataclasses
import logging
import threading
import time

import pytest

from vid2sub import jobs
from vid2sub.pipeline import Cancelled, InputResult


def until(check, timeout=5.0):
    end = time.monotonic() + timeout
    while not check():
        if time.monotonic() > end:
            raise AssertionError("timed out waiting")
        time.sleep(0.005)


class Runner:
    """A fake runner: each job reports stages and progress, then waits for the test to let it
    finish, checking for a cancel while it waits."""

    def __init__(self, results=None):
        self.results = results or {}
        self.started: list[str] = []
        self.running = 0
        self.most_at_once = 0
        self.gates: dict[str, threading.Event] = {}
        self.lock = threading.Lock()

    def gate(self, source: str) -> threading.Event:
        with self.lock:
            return self.gates.setdefault(source, threading.Event())

    def __call__(self, source, event, cancelled):
        with self.lock:
            self.started.append(source)
            self.running += 1
            self.most_at_once = max(self.most_at_once, self.running)
        try:
            event("stage", {"stage": "decode"})
            event("chunk", {"index": 1, "of": 3})
            event("chunk", {"index": 2, "of": 3})
            event("waiting", {"kind": "connection", "seconds": 5})
            while not self.gate(source).wait(0.005):
                if cancelled():
                    raise Cancelled()
            outcome = self.results.get(source, InputResult(input=source, status="done"))
            if isinstance(outcome, BaseException):
                raise outcome
            return outcome
        finally:
            with self.lock:
                self.running -= 1


@pytest.fixture
def runner():
    return Runner()


@pytest.fixture
def queue(runner):
    q = jobs.Queue(runner)
    yield q
    for gate in list(runner.gates.values()):
        gate.set()
    q.close()


def view(queue, job_id) -> jobs.JobView:
    return next(j for j in queue.jobs() if j.id == job_id)


def state(queue, job_id) -> str:
    return view(queue, job_id).state


def test_jobs_run_one_at_a_time_in_the_order_they_were_submitted(queue, runner):
    ids = queue.submit(["a.mkv", "b.mkv", "c.mkv"])
    assert len(set(ids)) == 3
    assert [j.input for j in queue.jobs()] == ["a.mkv", "b.mkv", "c.mkv"]
    for source in ("a.mkv", "b.mkv", "c.mkv"):
        runner.gate(source).set()
    until(lambda: all(j.state == "done" for j in queue.jobs()))
    assert runner.started == ["a.mkv", "b.mkv", "c.mkv"] and runner.most_at_once == 1


def test_a_running_job_shows_its_stage_and_progress(queue, runner):
    (job,) = queue.submit(["a.mkv"])
    until(lambda: view(queue, job).progress == (2, 3))
    assert view(queue, job).state == "running"
    assert view(queue, job).stage == "transcribe"
    runner.gate("a.mkv").set()
    until(lambda: state(queue, job) == "done")
    assert view(queue, job).result == InputResult(input="a.mkv", status="done")


def test_a_new_stage_clears_the_progress_and_a_batch_means_translating():
    seen = []

    def run(source, event, cancelled):
        event("chunk", {"index": 3, "of": 3})
        event("stage", {"stage": "write"})
        seen.append(q.jobs()[0])
        event("batch", {"index": 1, "of": 2})
        seen.append(q.jobs()[0])
        return InputResult(input=source, status="done")

    q = jobs.Queue(run)
    q.submit(["a.mkv"])
    until(lambda: q.jobs()[0].state == "done")
    q.close()
    assert [(v.stage, v.progress) for v in seen] == [("write", None), ("translate", (1, 2))]


def test_cancelling_a_queued_job_takes_it_out_of_the_queue(queue, runner):
    first, second = queue.submit(["a.mkv", "b.mkv"])
    until(lambda: state(queue, first) == "running")
    assert queue.cancel(second) is True
    assert state(queue, second) == "cancelled"
    runner.gate("a.mkv").set()
    until(lambda: state(queue, first) == "done")
    assert runner.started == ["a.mkv"]


def test_cancelling_the_running_job_stops_it_and_the_next_one_starts(queue, runner):
    first, second = queue.submit(["a.mkv", "b.mkv"])
    until(lambda: state(queue, first) == "running")
    assert queue.cancel(first) is True
    until(lambda: state(queue, first) == "cancelled")
    until(lambda: state(queue, second) == "running")
    runner.gate("b.mkv").set()
    until(lambda: state(queue, second) == "done")


def test_a_finished_or_unknown_job_cannot_be_cancelled(queue, runner):
    (job,) = queue.submit(["a.mkv"])
    runner.gate("a.mkv").set()
    until(lambda: state(queue, job) == "done")
    assert queue.cancel(job) is False
    assert queue.cancel("nope") is False
    assert state(queue, job) == "done"


def test_a_failed_input_fails_its_job_with_the_hint_that_names_the_fix():
    failed = InputResult(input="a.mkv", status="failed", reason="refused",
                         hint="is `make tunnel` running?")
    runner = Runner({"a.mkv": failed})
    q = jobs.Queue(runner)
    (job,) = q.submit(["a.mkv"])
    runner.gate("a.mkv").set()
    until(lambda: state(q, job) == "failed")
    assert view(q, job).hint == "is `make tunnel` running?" and view(q, job).result is failed
    q.close()


def test_a_runner_that_raises_fails_only_its_job_and_logs_only_the_error_kind(caplog):
    runner = Runner({"/films/Secret Show.mkv": RuntimeError("/films/Secret Show.mkv")})
    q = jobs.Queue(runner)
    caplog.set_level(logging.DEBUG, logger="vid2sub.jobs")
    bad, good = q.submit(["/films/Secret Show.mkv", "b.mkv"])
    runner.gate("/films/Secret Show.mkv").set()
    runner.gate("b.mkv").set()
    until(lambda: state(q, good) == "done")
    assert state(q, bad) == "failed" and view(q, bad).hint is None
    assert "RuntimeError" in caplog.text and "Secret" not in caplog.text
    q.close()


def test_listeners_hear_every_change_and_one_that_raises_is_ignored(queue, runner, caplog):
    heard = []

    def broken():
        raise ValueError("a listener's bug")

    def listener():
        (j,) = queue.jobs()
        heard.append((threading.current_thread().name, (j.state, j.stage, j.progress)))

    queue.on_change(broken)
    queue.on_change(listener)
    queue.submit(["a.mkv"])
    runner.gate("a.mkv").set()
    until(lambda: len(heard) == 6)
    assert [t for t, _ in heard].count("vid2sub-jobs") == 5  # and one from submit, here
    assert [v for t, v in heard if t == "vid2sub-jobs"] == [
        ("running", None, None), ("running", "decode", None),
        ("running", "transcribe", (1, 3)), ("running", "transcribe", (2, 3)),
        ("done", "transcribe", (2, 3))]
    assert "ValueError" in caplog.text and "a listener's bug" not in caplog.text


def test_jobs_are_frozen_snapshots(queue, runner):
    (job,) = queue.submit(["a.mkv"])
    before = view(queue, job)
    with pytest.raises(dataclasses.FrozenInstanceError):
        before.state = "done"  # type: ignore[misc]
    runner.gate("a.mkv").set()
    until(lambda: state(queue, job) == "done")
    assert before.state in ("queued", "running")


def test_close_cancels_the_running_and_waiting_jobs_and_stops_the_worker(runner):
    q = jobs.Queue(runner)
    first, _ = q.submit(["a.mkv", "b.mkv"])
    until(lambda: state(q, first) == "running")
    q.close()
    assert [j.state for j in q.jobs()] == ["cancelled", "cancelled"]
    assert not q._worker.is_alive()
    with pytest.raises(RuntimeError, match="closed"):
        q.submit(["c.mkv"])
