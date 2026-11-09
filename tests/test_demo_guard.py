"""Demo mode touches nothing but its own copy, and the app enforces it (spec §22.4, §22.7):
writes outside the demo's folder, reads in the home folder, lookups and connections beyond this
machine are refused while the demo runs, its backend opens only its own episode, it reads no
vid2sub.toml and no key, and its folder goes when it stops. As recordings' test_demo_guard.py
(packages/ui/tests at 8deb039), whose audit hook only watched; vid2sub's refuses. Each refusal is
a DemoIsolationError, which these tests expect, so they fail if the hook isn't there."""

import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

import pytest
from starlette.testclient import TestClient

import vid2sub
from vid2sub.media.tools import Tools
from vid2sub.web import demo, runtime, server
from vid2sub.web.app import create_app
from vid2sub.web.backend import OpenError
from vid2sub.web.demo import DemoIsolationError
from vid2sub.web.views import episode_view

TOKEN = "t" * 43  # as long as a real token, and plainly not one (the leak scan agrees)
PORT = 8765
BASE = f"http://127.0.0.1:{PORT}"
PAGE = {"Origin": BASE, "Sec-Fetch-Site": "same-origin", "Content-Type": "application/json"}


@pytest.fixture(autouse=True)
def fresh_reactive_lock():
    """As tests/test_web_server.py: each TestClient runs its own event loop."""
    from shiny.reactive import _core

    _core._reactive_environment._lock = None
    yield
    _core._reactive_environment._lock = None


@pytest.fixture
def place(tmp_path):
    """A demo folder, a stand-in for the person's home with their config and a secret in it, and
    a folder elsewhere with a file in it, all made before the demo is isolated."""
    folder, home, outside = tmp_path / "demo", tmp_path / "home", tmp_path / "outside"
    for d in (folder, home, outside / "dir"):
        d.mkdir(parents=True)
    (home / "vid2sub.toml").write_text("[server]\nport = 1\n", encoding="utf-8")
    (outside / "file.txt").write_text("x", encoding="utf-8")
    (folder / "inside.txt").write_text("x", encoding="utf-8")
    yield folder, home, outside
    demo.release()


def test_the_demo_refuses_every_kind_of_write_outside_its_folder(place):
    folder, home, outside = place
    demo.isolate(folder, home=home)
    file, d = outside / "file.txt", outside / "dir"
    writes = [
        lambda: open(outside / "new.txt", "w"),  # noqa: SIM115
        lambda: (file).open("a"),
        lambda: os.open(outside / "fd.txt", os.O_WRONLY | os.O_CREAT),
        lambda: os.replace(folder / "inside.txt", outside / "moved.txt"),
        lambda: os.mkdir(outside / "made"),
        lambda: os.chmod(file, 0o600),
        lambda: os.utime(file),
        lambda: os.symlink(folder / "inside.txt", outside / "link"),
        lambda: os.link(folder / "inside.txt", outside / "hard"),
        lambda: os.truncate(file, 0),
        lambda: os.remove(file),
        lambda: os.rmdir(d),
        lambda: shutil.rmtree(d),
        lambda: shutil.copyfile(folder / "inside.txt", outside / "copy.txt"),
    ]
    if os.name != "nt":  # tempfile reads a PermissionError on nt as "that name exists" and
        writes.append(lambda: tempfile.mkdtemp(dir=outside))  # retries, ending in FileExistsError
    for write in writes:
        with pytest.raises(DemoIsolationError, match="inside its own folder"):
            write()
    assert sorted(p.name for p in outside.iterdir()) == ["dir", "file.txt"]
    assert file.read_text(encoding="utf-8") == "x"
    # Inside, everything works, shutil.rmtree's removals through a folder's descriptor included.
    (folder / "sub").mkdir()
    (folder / "sub" / "a.txt").write_text("y", encoding="utf-8")
    os.replace(folder / "sub" / "a.txt", folder / "sub" / "b.txt")
    shutil.rmtree(folder / "sub")
    assert not (folder / "sub").exists()


def test_the_demo_reads_nothing_in_the_home_folder_but_python_and_vid2sub(place):
    folder, home, outside = place
    demo.isolate(folder, home=home)
    with pytest.raises(DemoIsolationError, match="nothing of yours"):
        (home / "vid2sub.toml").read_text(encoding="utf-8")
    assert (folder / "inside.txt").read_text(encoding="utf-8") == "x"
    assert (outside / "file.txt").read_text(encoding="utf-8") == "x"  # outside home: allowed
    assert Path(vid2sub.__file__).read_text(encoding="utf-8")
    assert Path(os.__file__).read_text(encoding="utf-8")


def test_the_demo_looks_up_and_connects_to_nothing_beyond_this_machine(place):
    folder, home, _ = place
    demo.isolate(folder, home=home)
    with pytest.raises(DemoIsolationError, match="no other machine"):
        socket.getaddrinfo("example.com", 443)
    with socket.socket() as s, pytest.raises(DemoIsolationError, match="beyond this machine"):
        s.settimeout(2)
        s.connect(("192.0.2.1", 9))  # refused before a packet goes
    assert socket.getaddrinfo("127.0.0.1", 9)


def test_the_demos_temporary_files_go_in_its_folder_until_it_is_released(place):
    folder, home, _ = place
    before = tempfile.gettempdir()
    demo.isolate(folder, home=home)
    made = Path(tempfile.mkdtemp(prefix="vid2sub-"))
    assert made.parent == folder / "tmp"
    demo.release()
    assert tempfile.gettempdir() == before
    with open(home / "vid2sub.toml", encoding="utf-8"):  # released: nothing is refused
        pass


@pytest.mark.media
def test_demo_mode_serves_and_opens_its_episode_touching_nothing_else(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    secret = home / "Films" / "secret.mkv"
    secret.parent.mkdir()
    secret.write_bytes(b"\0" * 16)
    tools = Tools.find()
    copy = demo.prepare(tools)
    rt = demo.runtime_for(copy, tools)
    assert rt.config.endpoints == {} and dict(rt.keys.environ) == {}  # no toml, no key
    runtime.configure(rt)
    demo.isolate(copy.parent, home=home)
    try:
        with TestClient(create_app(rt, token=TOKEN, port=PORT, shiny_app=server.app),
                        base_url=BASE) as client:
            assert client.post("/auth", content=json.dumps({"token": TOKEN}),
                               headers=PAGE).status_code == 204
            assert client.get("/").status_code == 200
            seen = _session_values(client, {"capabilities", "status"})
            assert seen["status"] == {"endpoints": [], "ffmpeg": True}
            ep = rt.backend.open(str(copy / demo.VIDEO))  # probes, hashes, reads the sidecar
            view = episode_view(ep, video_url=None, audio_url=None)
            assert view["notes"] == [] and view["tracks"]
            texts = [r["text"] for r in view["rows"]]
            assert texts[2] == "We meet at a college noted for knowledge,"
            token = rt.media.issue(copy / demo.VIDEO, owner=ep.id)
            r = client.get(f"/media/{token}", headers={"Range": "bytes=0-9"})
            assert r.status_code == 206
            with pytest.raises(OpenError, match="only its own episode"):
                rt.backend.open(str(secret))
            with pytest.raises(DemoIsolationError):
                secret.read_bytes()  # and the hook would stop a bug that got past the backend
    finally:
        demo.release()
        runtime.configure(None)
        rt.queue.close()


def _session_values(client, outputs: set[str]) -> dict:
    values: dict = {}
    with client.websocket_connect("ws://127.0.0.1:8765/websocket/",
                                  headers={"Origin": BASE}) as ws:
        init = {f".clientdata_output_{name}_hidden": False for name in outputs}
        ws.send_text(json.dumps({"method": "init", "data": init}))

        def read() -> None:
            while not outputs <= values.keys() or not values.get("status", {}).get("ffmpeg"):
                values.update(json.loads(ws.receive_text()).get("values", {}))

        reader = threading.Thread(target=read, daemon=True)
        reader.start()
        reader.join(20)
    assert outputs <= values.keys(), f"the demo's session sent only {sorted(values)}"
    return values


# The child: the real `vid2sub serve --demo`, with `www/` pointing at a folder holding a ui.js,
# as tests/test_cli_serve.py runs it, so the frontend needn't be built.
CHILD = r"""
import sys
from pathlib import Path

from vid2sub.cli import main
from vid2sub.commands import serve

serve.WWW = Path(sys.argv[1])
raise SystemExit(main(sys.argv[2:]))
"""


@pytest.mark.media
@pytest.mark.skipif(os.name == "nt", reason="POSIX signals")
@pytest.mark.parametrize("sig", [signal.SIGINT, signal.SIGTERM])
def test_demo_mode_reads_no_vid2sub_toml_and_removes_its_copy_when_it_stops(tmp_path, sig):
    www = tmp_path / "www"
    www.mkdir()
    (www / "ui.js").write_text("// built\n", encoding="utf-8")
    scratch = tmp_path / "tmp"
    scratch.mkdir()
    broken = tmp_path / "vid2sub.toml"
    broken.write_text("[server\n", encoding="utf-8")  # would exit 78 if it were read
    env = {**os.environ, "TMPDIR": str(scratch), "VID2SUB_CONFIG": str(broken)}
    log = tmp_path / "serve.log"
    with log.open("wb") as out:
        proc = subprocess.Popen([sys.executable, "-c", CHILD, str(www), "serve", "--demo",
                                 "--no-browser", "--port", "0"],
                                env=env, stdout=out, stderr=subprocess.STDOUT)
    try:
        deadline = time.monotonic() + 60
        while "port " not in log.read_text(encoding="utf-8", errors="replace"):
            assert proc.poll() is None, log.read_text(encoding="utf-8", errors="replace")
            assert time.monotonic() < deadline, "the demo never started"
            time.sleep(0.1)
        port = log.read_text(encoding="utf-8").split("port ")[1].split(".")[0]
        while True:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=1):
                    break
            except OSError:
                assert time.monotonic() < deadline, "healthz never answered"
                time.sleep(0.1)
        (made,) = scratch.glob("vid2sub-demo-*")
        assert (made / "demo" / demo.VIDEO).is_file()
        proc.send_signal(sig)
        code = proc.wait(timeout=30)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
    assert code == (0 if sig == signal.SIGINT else 128 + signal.SIGTERM)
    assert list(scratch.glob("vid2sub-demo-*")) == []


def test_the_demo_lets_the_null_device_through_and_nothing_else_outside(place):
    """subprocess opens os.devnull read-write for stdin=DEVNULL and the like, as the browser
    opener's does: a write that goes nowhere, so it is not a write outside the folder."""
    folder, home, outside = place
    demo.isolate(folder, home=home)
    os.close(os.open(os.devnull, os.O_RDWR))
    with open(os.devnull, "w", encoding="utf-8") as null:
        null.write("x")
    with pytest.raises(DemoIsolationError, match="inside its own folder"):
        os.open(outside / "fd.txt", os.O_RDWR | os.O_CREAT)
    with pytest.raises(DemoIsolationError, match="inside its own folder"):
        open(outside / "null", "w")  # noqa: SIM115


def test_the_null_device_is_let_through_only_to_be_opened(place, monkeypatch):
    """Not renamed over, removed, changed or truncated (the hook is called directly, so nothing
    is done to the device); and where os.devnull is the relative "nul", which the OS names by a
    path of another spelling (Windows), the raw argument of an open is what is compared."""
    folder, home, _ = place
    demo.isolate(folder, home=home)
    for event, args in [("os.remove", (os.devnull,)), ("os.rename", (str(folder / "inside.txt"),
                        os.devnull)), ("os.chmod", (os.devnull, 0o600)),
                        ("os.truncate", (os.devnull, 0)), ("shutil.move", ("a", os.devnull))]:
        with pytest.raises(DemoIsolationError, match="inside its own folder"):
            demo._hook(event, args)
    monkeypatch.setattr(os, "devnull", "nul")
    monkeypatch.setattr(demo, "_target", lambda value, dir_fd: "\\\\.\\nul")
    demo._hook("open", ("nul", "r+b", os.O_RDWR))  # opened: let through
    with pytest.raises(DemoIsolationError):
        demo._hook("os.remove", ("nul",))


@pytest.mark.media
@pytest.mark.skipif(os.name == "nt", reason="POSIX signals and a shell script")
def test_demo_mode_hands_the_browser_its_redirect_file(tmp_path):
    """The opener runs with stdin, stdout and stderr on the null device, which the demo's hook
    mustn't take for a write outside its folder (the browser would never be opened)."""
    www = tmp_path / "www"
    www.mkdir()
    (www / "ui.js").write_text("// built\n", encoding="utf-8")
    scratch = tmp_path / "tmp"
    scratch.mkdir()
    opened = tmp_path / "opened"
    browser = tmp_path / "browser.sh"
    browser.write_text(f'#!/bin/sh\necho "$1" > "{opened}"\n', encoding="utf-8")
    browser.chmod(0o755)
    env = {**os.environ, "TMPDIR": str(scratch), "BROWSER": str(browser)}
    log = tmp_path / "serve.log"
    with log.open("wb") as out:
        proc = subprocess.Popen([sys.executable, "-c", CHILD, str(www), "serve", "--demo",
                                 "--port", "0"], env=env, stdout=out, stderr=subprocess.STDOUT)
    try:
        deadline = time.monotonic() + 60
        while not opened.exists():
            assert proc.poll() is None, log.read_text(encoding="utf-8", errors="replace")
            assert time.monotonic() < deadline, "the browser was never opened"
            time.sleep(0.1)
        time.sleep(0.2)
        got = opened.read_text(encoding="utf-8").strip()
        proc.send_signal(signal.SIGINT)
        proc.wait(timeout=30)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
    assert got.startswith("file://") and got.endswith("open.html")
    assert "couldn't open a browser" not in log.read_text(encoding="utf-8")
