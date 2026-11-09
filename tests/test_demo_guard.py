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
from vid2sub import exitcodes
from vid2sub.cli import main
from vid2sub.commands import serve
from vid2sub.media.identity import full_sha256
from vid2sub.media.tools import ToolFailed, Tools
from vid2sub.store import sidecar_path
from vid2sub.subs.sidecar import parse_sidecar
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
    assert rt.backend.cache.root == copy.parent / "cache"  # the demo's own folder
    side, _ = parse_sidecar(sidecar_path(copy / demo.VIDEO).read_text(encoding="utf-8"))
    assert side.identity() == full_sha256(copy / demo.VIDEO)  # the identity names this MP4
    runtime.configure(rt)
    monkeypatch.setattr(sys, "dont_write_bytecode", False)  # restored when the test ends
    demo.isolate(copy.parent, home=home)
    assert sys.dont_write_bytecode
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


@pytest.mark.parametrize("event, args", [
    ("os.chflags", ("{outside}/file.txt", 0)),
    ("os.setxattr", ("{outside}/file.txt", "user.x", b"1", 0)),
    ("os.removexattr", ("{outside}/file.txt", "user.x")),
    ("sqlite3.connect", ("{outside}/x.db",)),
])
def test_the_demo_refuses_the_other_writes_python_audits(place, event, args):
    """Each event's argument shape is as CPython's audit table gives it and as a recording hook
    saw it (os.lchflags raises os.chflags); called directly, as the OS may lack the call."""
    folder, home, outside = place
    demo.isolate(folder, home=home)
    shaped = tuple(a.format(outside=outside) if isinstance(a, str) else a for a in args)
    with pytest.raises(DemoIsolationError, match="inside its own folder"):
        demo._hook(event, shaped)
    inside = tuple(a.replace(str(outside), str(folder)) if isinstance(a, str) else a
                   for a in shaped)
    demo._hook(event, inside)  # inside the folder: let through


def test_the_demo_refuses_sends_and_reverse_lookups_beyond_this_machine_and_unix_sockets(place):
    folder, home, _ = place
    demo.isolate(folder, home=home)
    sock = object()  # the hook never looks at the socket
    for event in ("socket.sendto", "socket.sendmsg", "socket.connect"):
        with pytest.raises(DemoIsolationError, match="beyond this machine"):
            demo._hook(event, (sock, ("192.0.2.1", 9)))
        with pytest.raises(DemoIsolationError, match="beyond this machine"):
            demo._hook(event, (sock, "/tmp/some.sock"))  # AF_UNIX: a path, not a (host, port)
        demo._hook(event, (sock, ("127.0.0.1", 9)))
    demo._hook("socket.sendmsg", (sock, None))  # already connected: no address of its own
    with pytest.raises(DemoIsolationError, match="no other machine"):
        demo._hook("socket.getnameinfo", (("192.0.2.1", 9), 0))
    demo._hook("socket.getnameinfo", (("127.0.0.1", 9), 0))


@pytest.mark.skipif(os.name == "nt", reason="symlinks need a privilege on Windows")
def test_a_link_in_the_demos_folder_to_a_file_in_the_home_folder_is_not_read(place):
    folder, home, _ = place
    (folder / "link").symlink_to(home / "vid2sub.toml")
    demo.isolate(folder, home=home)
    with pytest.raises(DemoIsolationError, match="nothing of yours"):
        (folder / "link").read_text(encoding="utf-8")


def test_the_demo_refuses_what_it_cannot_name_and_the_other_lookups_and_addresses(place,
                                                                                     monkeypatch):
    folder, home, outside = place
    monkeypatch.chdir(folder)  # a "" path would then resolve inside the folder, and be let through
    demo.isolate(folder, home=home)
    closed = 999_999  # a directory descriptor the OS won't name
    with pytest.raises(DemoIsolationError, match="inside its own folder"):
        demo._hook("os.remove", ("inside.txt", closed))
    with pytest.raises(DemoIsolationError, match="inside its own folder"):
        demo._hook("os.chown", (str(outside / "file.txt"), -1, -1, None))
    demo._hook("os.chown", (str(folder / "inside.txt"), -1, -1, None))
    for event in ("socket.gethostbyname", "socket.gethostbyaddr"):
        with pytest.raises(DemoIsolationError, match="no other machine"):
            demo._hook(event, ("192.0.2.1",))
    for spelling in ("0.0.0.0", "127.1", "::ffff:127.0.0.1", "LOCALHOST"):
        with pytest.raises(DemoIsolationError, match="beyond this machine"):
            demo._hook("socket.connect", (object(), (spelling, 9)))


@pytest.fixture
def checkout(tmp_path, monkeypatch):
    """serve's start-up with the frontend "built" and the temporary folder the test's own."""
    www = tmp_path / "www"
    www.mkdir()
    (www / "ui.js").write_text("// built\n", encoding="utf-8")
    monkeypatch.setattr(serve, "WWW", www)
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(scratch))
    return scratch


def test_demo_is_exclusive_with_config(checkout, capsys):
    with pytest.raises(SystemExit) as stop:
        main(["serve", "--demo", "--config", "x.toml"])
    assert stop.value.code == exitcodes.USAGE
    assert "not allowed with" in capsys.readouterr().err


def test_demo_without_ffmpeg_exits_69_and_leaves_nothing(checkout, monkeypatch, capsys):
    monkeypatch.setattr(Tools, "find", classmethod(lambda cls: cls(None, None, None)))
    assert main(["serve", "--demo", "--no-browser", "--port", "0"]) == exitcodes.UNAVAILABLE
    assert "the demo needs ffmpeg" in capsys.readouterr().err  # its folder goes at exit


def test_demo_with_an_ffmpeg_lacking_libvpx_or_libopus_exits_69(checkout, monkeypatch, capsys):
    monkeypatch.setattr(Tools, "find", classmethod(lambda cls: cls("/ffmpeg", None, None)))

    def failing(tools, out):
        raise ToolFailed("ffmpeg", 1, "Unknown encoder 'libvpx-vp9'")

    monkeypatch.setattr(demo, "mux", failing)
    assert main(["serve", "--demo", "--no-browser", "--port", "0"]) == exitcodes.UNAVAILABLE
    assert "libvpx and libopus" in capsys.readouterr().err


def test_demo_outside_a_checkout_exits_69(checkout, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(Tools, "find", classmethod(lambda cls: cls("/ffmpeg", None, None)))
    monkeypatch.setattr(demo, "DEMO", tmp_path / "no-such-demo")
    assert main(["serve", "--demo", "--no-browser", "--port", "0"]) == exitcodes.UNAVAILABLE
    assert "run it from a checkout" in capsys.readouterr().err
    assert list(checkout.iterdir()) == []


# The child again, with serve.serve wrapped to try a write outside the demo's folder first, as
# the engine is about to serve: the app, not a test, must have isolated by then.
ISOLATED_CHILD = CHILD.replace(
    "raise SystemExit(", r"""_serve = serve.serve


def _wrapped(*args, **kwargs):
    try:
        open(sys.argv[2], "w").close()
    except PermissionError as err:
        print("write outside:", type(err).__name__, flush=True)
    else:
        print("write outside: allowed", flush=True)
    return _serve(*args, **kwargs)


serve.serve = _wrapped
raise SystemExit(""").replace("sys.argv[2:]", "sys.argv[3:]")


@pytest.mark.media
@pytest.mark.skipif(os.name == "nt", reason="POSIX signals")
def test_serve_isolates_the_demo_before_it_serves(tmp_path):
    www = tmp_path / "www"
    www.mkdir()
    (www / "ui.js").write_text("// built\n", encoding="utf-8")
    outside = tmp_path / "outside.txt"
    log = tmp_path / "serve.log"
    with log.open("wb") as out:
        proc = subprocess.Popen([sys.executable, "-c", ISOLATED_CHILD, str(www), str(outside),
                                 "serve", "--demo", "--no-browser", "--port", "0"],
                                env={**os.environ, "TMPDIR": str(tmp_path)}, stdout=out,
                                stderr=subprocess.STDOUT)
    try:
        deadline = time.monotonic() + 60
        while "port " not in log.read_text(encoding="utf-8", errors="replace"):
            assert proc.poll() is None, log.read_text(encoding="utf-8", errors="replace")
            assert time.monotonic() < deadline, "the demo never started"
            time.sleep(0.1)
        proc.send_signal(signal.SIGINT)
        proc.wait(timeout=30)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
    said = log.read_text(encoding="utf-8")
    assert "write outside: DemoIsolationError" in said
    assert not outside.exists()


def test_the_demos_clip_is_read_through_the_input_whitelist(tmp_path, monkeypatch):
    """Spec §6.7: ffmpeg reads a file only with the protocol and format whitelists."""
    seen: list[list[str]] = []
    monkeypatch.setattr(demo, "run_tool", lambda args, **kwargs: seen.append(list(args)))
    demo.mux(Tools("/ffmpeg", None, None), tmp_path / "out.mp4")
    (args,) = seen
    at = args.index("-protocol_whitelist")
    assert args[at + 1] == "file" and "-format_whitelist" in args
    assert args[args.index("-i", at) + 1] == f"file:{demo.CLIP}"


@pytest.mark.media
def test_the_demos_sidecar_is_written_with_lf_bytes_on_every_os(monkeypatch):
    """Spec §22.2: LF bytes on every OS. Path.write_text translates newlines on Windows, so it
    is made to here (as it would there); safe_write writes the bytes it is given."""
    real = Path.write_text
    monkeypatch.setattr(Path, "write_text", lambda self, data, encoding=None, errors=None,
                        newline=None: real(self, data, encoding=encoding, errors=errors,
                                           newline="\r\n"))
    copy = demo.prepare(Tools.find())
    raw = sidecar_path(copy / demo.VIDEO).read_bytes()
    assert raw.endswith(b"\n") and b"\r" not in raw
