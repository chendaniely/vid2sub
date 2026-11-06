"""`vid2sub serve` binds 127.0.0.1 only, prints the link that signs a browser in, opens the
browser on the redirect file rather than the token, and removes that file's folder when it stops;
the token reaches no log and no command line (spec §6.1, §6.8, §18.1; S23).

The real CLI runs in a child process, as recordings' SIGTERM test runs its server, with a stand-in
for the Shiny app (the frontend and the Shiny server aren't needed to test the shell). Its
TMPDIR is the test's own, so the redirect file's folder can be watched. Signals and an executable
BROWSER script are POSIX: Windows gets its own run in Phase 3.
"""

import json
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
from vid2sub.web import auth

POSIX = pytest.mark.skipif(os.name == "nt", reason="POSIX signals and an executable script")
LINK = re.compile(r"http://127\.0\.0\.1:(\d+)/auth#t=([A-Za-z0-9_-]{43})")
# The child: the real `vid2sub serve`, with `www/` pointing at a folder holding a ui.js, and a
# stand-in for the Shiny app.
CHILD = r"""
import sys
from pathlib import Path

from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from vid2sub.cli import main
from vid2sub.commands import serve


async def page(request):
    return PlainTextResponse("shiny")


serve.WWW = Path(sys.argv[1])
serve.shiny_app = lambda: Starlette(routes=[Route("/{rest:path}", page)])
raise SystemExit(main(sys.argv[2:]))
"""


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


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


@pytest.fixture
def start(tmp_path):
    started: list[Serving] = []

    def run(*args: str, toml: str = "", env: dict | None = None) -> Serving:
        www = tmp_path / "www"
        www.mkdir(exist_ok=True)
        (www / "ui.js").write_text("// built\n", encoding="utf-8")
        scratch = tmp_path / f"tmp{len(started)}"
        scratch.mkdir()
        config = tmp_path / f"vid2sub{len(started)}.toml"
        config.write_text(toml, encoding="utf-8")
        log = tmp_path / f"serve{len(started)}.log"
        child_env = {k: v for k, v in os.environ.items() if k != "BROWSER"}
        child_env.update({"TMPDIR": str(scratch), **(env or {})})
        with log.open("wb") as out:
            proc = subprocess.Popen(
                [sys.executable, "-c", CHILD, str(www), "serve", "--config", str(config), *args],
                env=child_env, stdout=out, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + 60
        while not (found := LINK.search(log.read_text(encoding="utf-8", errors="replace"))):
            assert proc.poll() is None, log.read_text(encoding="utf-8", errors="replace")
            assert time.monotonic() < deadline, "no link printed in 60 s"
            time.sleep(0.1)
        serving = Serving(proc, log, scratch, int(found.group(1)), found.group(2))
        started.append(serving)
        while True:  # the socket listens before the link is printed; wait for the app too
            try:
                if serving.get("/healthz")[0] == 200:
                    break
            except OSError:
                pass
            assert time.monotonic() < deadline, "healthz never answered"
            time.sleep(0.1)
        return serving

    yield run
    for serving in started:
        if serving.proc.poll() is None:
            serving.proc.kill()
            serving.proc.wait()


def _browser(tmp_path: Path) -> tuple[Path, Path]:
    """An executable BROWSER that records the command line it was run with, as `ps` shows it."""
    script = tmp_path / "browser"
    record = tmp_path / "browser.json"
    script.write_text(f"#!{sys.executable}\nimport json, sys\n"
                      f"open({str(record)!r}, 'w').write(json.dumps(sys.argv))\n",
                      encoding="utf-8")
    script.chmod(0o755)
    return script, record


def _sign_in(serving: Serving, token: str) -> tuple[int, dict, bytes]:
    return serving.get("/auth", json.dumps({"token": token}).encode(),
                       {"Content-Type": "application/json"})


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


def test_bind_listens_on_127_0_0_1_only():
    sock = serve.bind(0)
    try:
        assert sock.family == socket.AF_INET
        assert sock.getsockname()[0] == "127.0.0.1"
        with socket.create_connection(sock.getsockname(), timeout=5):
            pass  # listening already: a browser opened now waits rather than being refused
    finally:
        sock.close()


def test_uvicorn_keeps_no_access_log_and_believes_no_proxy_headers():
    config = serve.uvicorn_config(lambda scope, receive, send: None)
    assert config.access_log is False
    assert config.proxy_headers is False
    assert config.server_header is False


@pytest.mark.parametrize("value", ["-1", "65536", "http", "80.5"])
def test_port_must_be_a_port_number(value, capsys):
    with pytest.raises(SystemExit) as exited:
        main(["serve", "--port", value])
    assert exited.value.code == exitcodes.USAGE
    assert "a port is a number from 0 to 65535" in capsys.readouterr().err


def test_the_printed_link_signs_a_browser_in_on_the_port_given(start):
    configured, given = _free_port(), _free_port()
    serving = start("--port", str(given), "--no-browser", toml=f"[server]\nport = {configured}\n")
    assert serving.port == given  # --port wins over vid2sub.toml
    assert serving.get("/healthz")[2] == b'{"ok":true}'
    assert serving.get("/")[0] == 401
    assert _sign_in(serving, "t" * 43)[0] == 403
    status, headers, _ = _sign_in(serving, serving.token)
    assert status == 204
    cookie = headers["set-cookie"].split(";")[0]
    assert cookie.startswith(f"vid2sub-{given}=")
    status, _, body = serving.get("/", headers={"Cookie": cookie})
    assert (status, body) == (200, b"shiny")
    serving.stop()


@POSIX
def test_the_browser_opens_the_redirect_file_and_ctrl_c_removes_its_folder(start, tmp_path):
    script, record = _browser(tmp_path)
    port = _free_port()
    serving = start(toml=f"[server]\nport = {port}\n", env={"BROWSER": str(script)})
    assert serving.port == port  # [server] port from vid2sub.toml
    deadline = time.monotonic() + 30
    while not record.exists():
        assert time.monotonic() < deadline, "the browser was never opened"
        time.sleep(0.1)
    argv = json.loads(record.read_text(encoding="utf-8"))
    assert serving.token not in " ".join(argv)  # the browser's command line names a file
    page = Path(urllib.request.url2pathname(urlsplit(argv[1]).path))
    assert page.name == "open.html" and page.parent.name.startswith("vid2sub-")
    assert page.parent.parent.resolve() == serving.tmp.resolve()
    assert stat.S_IMODE(page.stat().st_mode) == 0o600
    assert stat.S_IMODE(page.parent.stat().st_mode) == 0o700
    assert auth.auth_url(port, serving.token) in page.read_text(encoding="utf-8")
    assert serving.stop(signal.SIGINT) == exitcodes.OK
    assert serving.folders() == []


@POSIX
def test_the_token_reaches_no_log_or_command_line_and_sigterm_removes_the_folder(start):
    serving = start("--port", "0", "--no-browser")
    ps = subprocess.run(["ps", "-ww", "-o", "command=", "-p", str(serving.proc.pid)],
                        capture_output=True, text=True, check=True).stdout
    assert "serve" in ps and serving.token not in ps
    _sign_in(serving, "t" * 43)
    status, headers, _ = _sign_in(serving, serving.token)
    assert status == 204
    cookie = headers["set-cookie"].split(";")[0]
    serving.get("/", headers={"Cookie": cookie})
    serving.get("/media/unknown", headers={"Cookie": cookie})
    assert len(serving.folders()) == 1
    assert serving.stop(signal.SIGTERM) == 128 + signal.SIGTERM
    assert serving.folders() == []
    lines = serving.log.read_text(encoding="utf-8").splitlines()
    assert [line for line in lines if serving.token in line] == [
        f"  {auth.auth_url(serving.port, serving.token)}"]  # printed once, for the terminal
    assert not [line for line in lines if "GET /" in line or "POST /" in line]  # no access log


@POSIX
@pytest.mark.parametrize(("args", "toml"), [((), "[server]\nopen_browser = false\n"),
                                            (("--no-browser",), "")])
def test_open_browser_false_or_no_browser_opens_nothing(start, tmp_path, args, toml):
    script, record = _browser(tmp_path)
    serving = start("--port", "0", *args, toml=toml, env={"BROWSER": str(script)})
    time.sleep(1)  # the browser is opened just after the link is printed, if at all
    assert not record.exists()
    assert len(serving.folders()) == 1  # the link still works by hand
    serving.stop()
