"""Servers and pages for the browser tests (spec §22.7): the real `vid2sub serve`, on a free port,
in a child process with its own TMPDIR and an empty vid2sub.toml, and a page signed in through
the launch link as a person's browser is (Task 9's token flow, scripted).

As recordings' e2e conftest (packages/ui/tests/e2e/conftest.py at 8deb039): a server per test,
polled on /healthz, stopped at the end. vid2sub prints the link only to a terminal, so the
harness reads it from the redirect file whose path the server prints (0600, its own user's).
`page` replaces pytest-playwright's: it is already signed in, and the test fails on any console
error or CSP violation the page saw, unless the test took them itself (`watch`). Run with
`make e2e`, which builds the frontend first.
"""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from playwright.sync_api import BrowserContext, Page, expect

from vid2sub.web import WWW

LINK = re.compile(r"http://127\.0\.0\.1:(\d+)/auth#t=([A-Za-z0-9_-]{43})")
PAGE_LINE = re.compile(r"^  (.+open\.html)$", re.MULTILINE)
# Runs before any page script, outside the CSP (Playwright injects it): a page's CSP violations,
# with what was blocked, for the document that is open now.
WATCH_CSP = """
window.__csp = [];
document.addEventListener("securitypolicyviolation", (e) => {
  window.__csp.push(`${e.violatedDirective} ${e.blockedURI} ${e.sample || ""}`.trim());
});
"""


@dataclass
class Server:
    url: str  # http://127.0.0.1:<port>
    link: str  # the launch link, /auth#t=<token>
    port: int
    proc: subprocess.Popen
    log: Path
    tmp: Path  # the server's TMPDIR

    def stop(self) -> int:
        if self.proc.poll() is None:
            if os.name == "nt":
                self.proc.terminate()
            else:
                self.proc.send_signal(signal.SIGINT)
            try:
                self.proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
        return self.proc.returncode


def start_server(tmp: Path, *args: str, port: int = 0) -> Server:
    """`vid2sub serve --no-browser` on `port` (0: any free one), up and answering."""
    if not (WWW / "ui.js").is_file():
        pytest.fail("the frontend isn't built: run make build (make e2e does)")
    tmp.mkdir(parents=True, exist_ok=True)
    config = tmp / "vid2sub.toml"
    config.write_text("", encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if not k.startswith("VID2SUB_")}
    env["TMPDIR"] = str(tmp)
    log = tmp / "server.log"
    with log.open("wb") as out:
        proc = subprocess.Popen(
            [sys.executable, "-m", "vid2sub", "serve", "--no-browser", "--port", str(port),
             "--config", str(config), *args],
            env=env, stdout=out, stderr=subprocess.STDOUT)

    def tail() -> str:
        return log.read_text(encoding="utf-8", errors="replace")[-2000:]

    deadline = time.monotonic() + 60
    while not (found := PAGE_LINE.search(log.read_text(encoding="utf-8", errors="replace"))):
        if proc.poll() is not None:
            pytest.fail(f"vid2sub serve exited with {proc.returncode}:\n{tail()}")
        if time.monotonic() > deadline:
            proc.kill()
            pytest.fail(f"vid2sub serve printed no redirect file in 60 s:\n{tail()}")
        time.sleep(0.1)
    link = LINK.search(Path(found.group(1)).read_text(encoding="utf-8"))
    url = f"http://127.0.0.1:{link.group(1)}"
    while True:
        try:
            with urllib.request.urlopen(f"{url}/healthz", timeout=1) as r:
                if json.load(r) == {"ok": True}:
                    break
        except OSError:
            pass
        if time.monotonic() > deadline:
            proc.kill()
            pytest.fail(f"vid2sub serve never answered /healthz:\n{tail()}")
        time.sleep(0.1)
    return Server(url, link.group(0), int(link.group(1)), proc, log, tmp)


@pytest.fixture
def server(tmp_path):
    started = start_server(tmp_path / "server")
    yield started
    started.stop()


@pytest.fixture
def launch():
    """Starts another server, `launch(tmp, *args, port=0)`, stopped at the end of the test."""
    started: list[Server] = []

    def run(tmp: Path, *args: str, port: int = 0) -> Server:
        started.append(start_server(tmp, *args, port=port))
        return started[-1]

    yield run
    for s in started:
        s.stop()


@dataclass
class Watch:
    """What a page did: console errors (CSP violations among them, as Chromium logs each one)
    and every request it made, across navigations."""

    page: Page
    errors: list[str] = field(default_factory=list)
    requests: list[str] = field(default_factory=list)

    def violations(self) -> list[str]:
        """The CSP violations in the document open now."""
        return self.page.evaluate("() => window.__csp")

    def clear(self) -> None:
        """Takes what was seen so far, for a test whose point it was."""
        self.errors.clear()
        self.page.evaluate("() => { window.__csp = []; }")


def watched_page(context: BrowserContext) -> Watch:
    context.add_init_script(script=WATCH_CSP)
    page = context.new_page()
    watch = Watch(page)
    page.on("console", lambda m: watch.errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: watch.errors.append(f"uncaught: {e}"))
    page.on("request", lambda r: watch.requests.append(r.url))
    return watch


def sign_in(page: Page, server: Server) -> None:
    """Through the launch link, as the browser vid2sub opens does: /auth posts the token from the
    fragment, gets the cookie and replaces the address with "/"."""
    page.goto(server.link)
    page.wait_for_url(f"{server.url}/")
    expect(page.get_by_test_id("app")).to_be_visible()


@pytest.fixture
def open_page(context):
    """Opens a new page signed in to `server`, watched; the test checks what it saw itself."""

    def run(server: Server) -> Watch:
        watched = watched_page(context)
        sign_in(watched.page, server)
        return watched

    return run


@pytest.fixture
def watch(open_page, server):
    watched = open_page(server)
    yield watched
    assert watched.errors == [], f"console errors: {watched.errors}"
    assert watched.violations() == []


@pytest.fixture
def page(watch) -> Page:
    """A page already through /auth on the `server` fixture's engine; the test fails on any
    console error or CSP violation it saw."""
    return watch.page
