"""`vid2sub serve` binds 127.0.0.1 only, prints the sign-in link to a terminal and only there,
opens the browser on the redirect file rather than the token, and removes that file's folder
whenever it stops; the token reaches no log and no command line (spec §6.1, §6.8, §18.1; S23).

The real CLI runs in a child process, as recordings' SIGTERM test runs its server, with a stand-in
for the Shiny app (the frontend and the Shiny server aren't needed to test the shell). Its
TMPDIR is the test's own, so the redirect file's folder can be watched. Signals, a terminal and
an executable BROWSER script are POSIX: Windows gets its own run in Phase 3.
"""

import json
import logging
import os
import re
import signal
import socket
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from vid2sub import exitcodes
from vid2sub.cli import main
from vid2sub.commands import serve
from vid2sub.web import auth, runtime

POSIX = pytest.mark.skipif(os.name == "nt", reason="POSIX signals, terminals and scripts")
LINK = re.compile(r"http://127\.0\.0\.1:(\d+)/auth#t=([A-Za-z0-9_-]{43})")
PAGE_LINE = re.compile(r"^  (.+open\.html)$", re.MULTILINE)  # the redirect file, when not a tty
# The child: the real `vid2sub serve`, with `www/` pointing at a folder holding a ui.js, and a
# stand-in for the Shiny app whose /stream never ends, as a paused video's stream doesn't.
CHILD = r"""
import asyncio
import sys
from pathlib import Path

from starlette.applications import Starlette
from starlette.responses import PlainTextResponse, StreamingResponse
from starlette.routing import Route

from vid2sub.cli import main
from vid2sub.commands import serve


async def page(request):
    return PlainTextResponse("shiny")


async def forever():
    while True:
        yield b"x" * 65536
        await asyncio.sleep(0.01)


async def stream(request):
    return StreamingResponse(forever(), media_type="application/octet-stream")


serve.WWW = Path(sys.argv[1])
serve.shiny_app = lambda: Starlette(routes=[Route("/stream", stream), Route("/{rest:path}", page)])
raise SystemExit(main(sys.argv[2:]))
"""


def _free_ports(n: int) -> list[int]:
    """`n` different free ports: held at once while they are picked, so none comes twice."""
    socks = [socket.socket() for _ in range(n)]
    try:
        for s in socks:
            s.bind(("127.0.0.1", 0))
        return [s.getsockname()[1] for s in socks]
    finally:
        for s in socks:
            s.close()


@dataclass
class Serving:
    proc: subprocess.Popen
    log: Path
    tmp: Path  # the child's TMPDIR
    port: int
    token: str

    def get(self, path: str, data: bytes | None = None, headers: dict | None = None):
        request = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data,
                                         headers=headers or {})
        try:
            with urllib.request.urlopen(request, timeout=10) as r:
                return r.status, dict(r.headers), r.read()
        except urllib.error.HTTPError as err:
            return err.code, dict(err.headers), err.read()

    def stop(self, sig: int = signal.SIGINT) -> int:
        if os.name == "nt":
            self.proc.terminate()
        else:
            self.proc.send_signal(sig)
        try:
            return self.proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            raise

    def folders(self) -> list[Path]:
        return sorted(self.tmp.glob("vid2sub-*"))

    def text(self) -> str:
        return self.log.read_text(encoding="utf-8", errors="replace")


def _child(tmp_path: Path, n: int, args: tuple[str, ...], toml: str, env: dict | None):
    www = tmp_path / "www"
    www.mkdir(exist_ok=True)
    (www / "ui.js").write_text("// built\n", encoding="utf-8")
    scratch = tmp_path / f"tmp{n}"
    scratch.mkdir()
    config = tmp_path / f"vid2sub{n}.toml"
    config.write_text(toml, encoding="utf-8")
    child_env = {k: v for k, v in os.environ.items() if k != "BROWSER"}
    child_env.update({"TMPDIR": str(scratch), **(env or {})})
    command = [sys.executable, "-c", CHILD, str(www), "serve", "--config", str(config), *args]
    return command, child_env, scratch


def _wait_for_health(serving: Serving, deadline: float) -> None:
    while True:  # the socket listens before anything is printed; wait for the app too
        try:
            if serving.get("/healthz")[0] == 200:
                return
        except OSError:
            pass
        assert time.monotonic() < deadline, "healthz never answered"
        time.sleep(0.1)


@pytest.fixture
def start(tmp_path):
    """Starts `vid2sub serve` with its output in a file, as a log would be. The link is then not
    printed, so it is read from the redirect file whose path is."""
    started: list[Serving] = []

    def run(*args: str, toml: str = "", env: dict | None = None) -> Serving:
        command, child_env, scratch = _child(tmp_path, len(started), args, toml, env)
        log = tmp_path / f"serve{len(started)}.log"
        with log.open("wb") as out:
            proc = subprocess.Popen(command, env=child_env, stdout=out, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + 60
        while not (found := PAGE_LINE.search(log.read_text(encoding="utf-8", errors="replace"))):
            assert proc.poll() is None, log.read_text(encoding="utf-8", errors="replace")
            assert time.monotonic() < deadline, "no redirect file named in 60 s"
            time.sleep(0.1)
        link = LINK.search(Path(found.group(1)).read_text(encoding="utf-8"))
        serving = Serving(proc, log, scratch, int(link.group(1)), link.group(2))
        started.append(serving)
        _wait_for_health(serving, deadline)
        return serving

    yield run
    for serving in started:
        if serving.proc.poll() is None:
            serving.proc.kill()
            serving.proc.wait()


def _browser(tmp_path: Path) -> tuple[Path, Path]:
    """An executable BROWSER that records the command line it was run with, as `ps` shows it.
    It writes the record whole (a rename), so it is never seen half-written."""
    script = tmp_path / "browser"
    record = tmp_path / "browser.json"
    script.write_text(f"#!{sys.executable}\nimport json, os, sys\n"
                      f"open({str(record)!r} + '.part', 'w').write(json.dumps(sys.argv))\n"
                      f"os.replace({str(record)!r} + '.part', {str(record)!r})\n",
                      encoding="utf-8")
    script.chmod(0o755)
    return script, record


def _sign_in(serving: Serving, token: str) -> tuple[int, dict, bytes]:
    return serving.get("/auth", json.dumps({"token": token}).encode(),
                       {"Content-Type": "application/json"})


def _cookie(serving: Serving) -> str:
    status, headers, _ = _sign_in(serving, serving.token)
    assert status == 204
    return headers["set-cookie"].split(";")[0]


def test_serve_refuses_without_the_built_frontend(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(serve, "WWW", tmp_path / "www")  # no ui.js
    broken = tmp_path / "vid2sub.toml"
    broken.write_text("[server\n", encoding="utf-8")  # checked after the frontend
    assert main(["serve", "--config", str(broken)]) == exitcodes.UNAVAILABLE
    assert "build the frontend first" in capsys.readouterr().err


def test_a_port_in_use_exits_69_and_says_how_to_pick_another(tmp_path, monkeypatch, capsys):
    (tmp_path / "www").mkdir()
    (tmp_path / "www" / "ui.js").write_text("// built\n", encoding="utf-8")
    monkeypatch.setattr(serve, "WWW", tmp_path / "www")
    config = tmp_path / "vid2sub.toml"
    config.write_text("", encoding="utf-8")
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen()
        port = taken.getsockname()[1]
        code = main(["serve", "--port", str(port), "--no-browser", "--config", str(config)])
    assert code == exitcodes.UNAVAILABLE
    err = capsys.readouterr().err
    assert f"port {port}" in err and "--port" in err


def test_serve_keeps_the_model_libraries_loggers_at_warning(tmp_path, monkeypatch):
    # Spec §6.8: OPENAI_LOG and CHATLAS_LOG are ignored, as every other command ignores them.
    monkeypatch.setattr(serve, "WWW", tmp_path / "www")  # it stops at the frontend check
    for name in ("openai", "httpx", "chatlas"):
        logging.getLogger(name).setLevel(logging.DEBUG)
    main(["serve"])
    assert [logging.getLogger(n).level for n in ("openai", "httpx", "chatlas")] == [
        logging.WARNING] * 3


def test_a_failure_after_binding_leaves_nothing_running(tmp_path, monkeypatch):
    (tmp_path / "www").mkdir()
    (tmp_path / "www" / "ui.js").write_text("// built\n", encoding="utf-8")
    monkeypatch.setattr(serve, "WWW", tmp_path / "www")

    def broken():
        raise RuntimeError("the Shiny app failed to load")

    monkeypatch.setattr(serve, "shiny_app", broken)
    (port,) = _free_ports(1)
    with pytest.raises(RuntimeError, match="failed to load"):
        main(["serve", "--port", str(port), "--no-browser", "--config", str(tmp_path / "x.toml")])
    try:
        with socket.socket() as again:
            again.bind(("127.0.0.1", port))  # the engine's socket was closed
        with pytest.raises(RuntimeError, match="closed"):
            runtime.current().queue.submit(["/videos/a.mkv"])  # and its job queue stopped
    finally:
        runtime.configure(None)


def test_bind_listens_on_127_0_0_1_only():
    sock = serve.bind(0)
    try:
        assert sock.family == socket.AF_INET
        assert sock.getsockname()[0] == "127.0.0.1"
        with socket.create_connection(sock.getsockname(), timeout=5):
            pass  # listening already: a browser opened now waits rather than being refused
    finally:
        sock.close()


def test_uvicorn_keeps_no_access_log_believes_no_proxy_and_waits_at_most_3_s_to_stop():
    config = serve.uvicorn_config(lambda scope, receive, send: None)
    assert config.access_log is False
    assert config.proxy_headers is False
    assert config.server_header is False
    assert config.timeout_graceful_shutdown == 3


@pytest.mark.parametrize("value", ["-1", "65536", "http", "80.5", "٣"])
def test_port_must_be_a_port_number(value, capsys):
    with pytest.raises(SystemExit) as exited:
        main(["serve", "--port", value])
    assert exited.value.code == exitcodes.USAGE
    assert "a port is a number from 0 to 65535" in capsys.readouterr().err


def test_the_link_signs_a_browser_in_on_the_port_given(start):
    configured, given = _free_ports(2)
    serving = start("--port", str(given), "--no-browser", toml=f"[server]\nport = {configured}\n")
    assert serving.port == given  # --port wins over vid2sub.toml
    assert serving.get("/healthz")[2] == b'{"ok":true}'
    assert serving.get("/")[0] == 401
    assert _sign_in(serving, "t" * 43)[0] == 403
    cookie = _cookie(serving)
    assert cookie.startswith(f"vid2sub-{given}=")
    status, _, body = serving.get("/", headers={"Cookie": cookie})
    assert (status, body) == (200, b"shiny")
    serving.stop()


@POSIX
def test_a_terminal_gets_the_link_itself(tmp_path):
    import pty

    command, env, scratch = _child(tmp_path, 0, ("--port", "0", "--no-browser"), "", None)
    leader, follower = pty.openpty()
    proc = subprocess.Popen(command, env=env, stdin=subprocess.DEVNULL, stdout=follower,
                            stderr=follower)
    os.close(follower)
    seen, deadline = b"", time.monotonic() + 60
    try:
        while not LINK.search(seen.decode(errors="replace")):
            assert time.monotonic() < deadline, seen.decode(errors="replace")
            seen += os.read(leader, 4096)
        port, token = LINK.search(seen.decode()).groups()
        assert len(list(scratch.glob("vid2sub-*"))) == 1
        serving = Serving(proc, tmp_path / "unused.log", scratch, int(port), token)
        _wait_for_health(serving, deadline)
        assert _sign_in(serving, token)[0] == 204  # the link printed is the live one
        assert serving.stop(signal.SIGINT) == exitcodes.OK
        assert serving.folders() == []
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        os.close(leader)


@POSIX
def test_the_browser_opens_the_redirect_file_and_ctrl_c_removes_its_folder(start, tmp_path):
    script, record = _browser(tmp_path)
    (port,) = _free_ports(1)
    serving = start(toml=f"[server]\nport = {port}\n", env={"BROWSER": str(script)})
    assert serving.port == port  # [server] port from vid2sub.toml
    deadline = time.monotonic() + 30
    while not record.exists():
        assert time.monotonic() < deadline, "the browser was never opened"
        time.sleep(0.1)
    argv = json.loads(record.read_text(encoding="utf-8"))
    leaked = serving.token in " ".join(argv)
    assert not leaked, "the token reached the browser's command line"  # it names a file
    page = Path(urllib.request.url2pathname(urlsplit(argv[1]).path))
    assert page.name == "open.html" and page.parent.name.startswith("vid2sub-")
    assert page.parent.parent.resolve() == serving.tmp.resolve()
    assert stat.S_IMODE(page.stat().st_mode) == 0o600
    assert stat.S_IMODE(page.parent.stat().st_mode) == 0o700
    named = auth.auth_url(port, serving.token) in page.read_text(encoding="utf-8")
    assert named, "the redirect file doesn't hold the sign-in link"
    assert serving.stop(signal.SIGINT) == exitcodes.OK
    assert serving.folders() == []


@POSIX
def test_the_token_reaches_no_log_or_command_line_and_sigterm_removes_the_folder(start):
    serving = start("--port", "0", "--no-browser")
    ps = subprocess.run(["ps", "-ww", "-o", "command=", "-p", str(serving.proc.pid)],
                        capture_output=True, text=True, check=True).stdout
    leaked = serving.token in ps
    assert "serve" in ps and not leaked, "the token reached the command line"
    _sign_in(serving, "t" * 43)
    cookie = _cookie(serving)
    serving.get("/", headers={"Cookie": cookie})
    serving.get("/media/unknown", headers={"Cookie": cookie})
    assert len(serving.folders()) == 1
    assert serving.stop(signal.SIGTERM) == 128 + signal.SIGTERM
    assert serving.folders() == []
    leaked = serving.token in serving.text()  # output to a file names the redirect file
    assert not leaked, "the token reached the log"


@POSIX
@pytest.mark.parametrize("sig", [signal.SIGINT, signal.SIGTERM])
def test_a_stalled_response_doesnt_keep_the_engine_from_stopping(start, sig):
    serving = start("--port", "0", "--no-browser")
    cookie = _cookie(serving)
    with socket.create_connection(("127.0.0.1", serving.port), timeout=10) as stalled:
        stalled.sendall(f"GET /stream HTTP/1.1\r\nHost: 127.0.0.1:{serving.port}\r\n"
                        f"Cookie: {cookie}\r\n\r\n".encode())
        stalled.recv(1024)  # streaming; then never read again, as a paused video
        began = time.monotonic()
        code = serving.stop(sig)
    assert time.monotonic() - began < 15
    assert code == (exitcodes.OK if sig == signal.SIGINT else 128 + signal.SIGTERM)
    assert serving.folders() == []


@POSIX
@pytest.mark.parametrize(("args", "toml"), [((), "[server]\nopen_browser = false\n"),
                                            (("--no-browser",), "")])
def test_open_browser_false_or_no_browser_opens_nothing(start, tmp_path, args, toml):
    script, record = _browser(tmp_path)
    serving = start("--port", "0", *args, toml=toml, env={"BROWSER": str(script)})
    deadline = time.monotonic() + 3  # the browser opens just after the output, if at all
    while time.monotonic() < deadline:
        assert not record.exists()
        time.sleep(0.1)
    assert len(serving.folders()) == 1  # the redirect file still works by hand
    serving.stop()
