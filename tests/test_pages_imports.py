"""The Shiny server and its views import only what the Pages bundle has, and never start a thread
or a process themselves (spec §3.3, §21; the Phase 2 plan's Global Constraints).

Spec §21 bundles `vid2sub.subs`, `vid2sub.catalog`, `vid2sub.parse` and `web/server.py` with
`BrowserBackend`, with shinyreact and the wheels of pysubs2, opencc-purepy and
charset-normalizer; Pyodide brings shiny, htmltools and pydantic, and has no FastAPI, uvicorn,
network client, ffmpeg or threads. So a fresh interpreter first loads what the bundle brings
(the host's shiny imports uvicorn, httpx and openai on its own; that is shiny's business), then
forgets and refuses at import every vid2sub module outside the server's own and the pure
packages, and every package of vid2sub's dependencies the bundle lacks, and the server and its
views must still import. Local-only code is reached through the configured `Runtime`, and every
blocking call goes through `runtime.blocking`, which runs inline in Pyodide.
"""

import ast
import asyncio
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from vid2sub.web import runtime

SRC = Path(__file__).resolve().parents[1] / "src" / "vid2sub"

# What spec §21's bundle holds of vid2sub: whole packages, then single modules. `web.ops` parses
# the editor's edits at the door, so the browser editor needs it too; it is pure. `web.settings`
# holds the session's defaults, which the runtime makes (Task 18).
BUNDLED_TREES = ("vid2sub.subs", "vid2sub.parse")
BUNDLED_MODULES = ("vid2sub", "vid2sub.catalog", "vid2sub.web", "vid2sub.web.server",
                   "vid2sub.web.views", "vid2sub.web.episode", "vid2sub.web.runtime",
                   "vid2sub.web.ops", "vid2sub.web.settings")
# vid2sub's own dependencies (pyproject.toml, the mac extra, and Phase 3's faster-whisper) that
# the bundle doesn't have.
NOT_BUNDLED = ("platformdirs", "numpy", "onnxruntime", "chatlas", "openai", "httpx", "yt_dlp",
               "fastapi", "uvicorn", "mlx_qwen3_asr", "faster_whisper")

SCRIPT = r"""
import importlib, sys

import htmltools, pydantic, pysubs2, shiny, shinyreact  # what the bundle brings, loaded first

TREES, MODULES, PACKAGES = {trees!r}, {modules!r}, {packages!r}


def refused(name):
    if name.split(".")[0] == "vid2sub":
        return name not in MODULES and not any(name == t or name.startswith(t + ".")
                                               for t in TREES)
    return name.split(".")[0] in PACKAGES


class Refuse:
    def find_spec(self, name, path=None, target=None):
        if refused(name):
            raise ImportError(f"the Pages bundle has no {{name}}")
        return None


for name in [n for n in sys.modules if refused(n)]:
    del sys.modules[name]  # so an import of it asks the finder again
sys.meta_path.insert(0, Refuse())
for module in sys.argv[1:]:
    importlib.import_module(module)
print("imported", *sys.argv[1:])
"""


def _import_as_pages(*modules: str) -> subprocess.CompletedProcess:
    script = SCRIPT.format(trees=BUNDLED_TREES, modules=BUNDLED_MODULES, packages=NOT_BUNDLED)
    return subprocess.run([sys.executable, "-c", script, *modules], check=False,
                          capture_output=True, text=True, timeout=120)


def test_the_server_and_its_views_import_with_only_what_the_pages_bundle_has():
    done = _import_as_pages("vid2sub.web.views", "vid2sub.web.server")
    assert done.returncode == 0, done.stderr[-3000:]
    assert done.stdout.strip() == "imported vid2sub.web.views vid2sub.web.server"


def test_the_refusal_itself_works():
    # why: a finder that refused nothing would pass the test above whatever the server imports.
    done = _import_as_pages("vid2sub.web.backend")
    assert done.returncode != 0
    assert "ImportError: the Pages bundle has no vid2sub.web.backend" in done.stderr


THREADS = {"threading", "concurrent", "multiprocessing", "subprocess", "_thread", "anyio"}
# Names that start a thread or a process wherever they are imported from or reached through.
STARTERS = {"to_thread", "run_in_executor", "run_in_threadpool", "create_subprocess_exec",
            "create_subprocess_shell"}
OS_STARTERS = {"system", "fork", "popen", "execv", "execl", "execvp", "execlp"}


def _starts_a_thread_or_process(source: str) -> list[str]:
    """Every import or attribute in `source` that could start a thread or a process."""
    tree = ast.parse(source)
    bad = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            bad += [a.name for a in node.names if a.name.split(".")[0] in THREADS]
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".")[0] in THREADS:
                bad.append(node.module)
            for a in node.names:
                if a.name in STARTERS or (node.module == "os" and _os_starter(a.name)):
                    bad.append(f"{node.module}.{a.name}")
        elif isinstance(node, ast.Attribute):
            on_os = isinstance(node.value, ast.Name) and node.value.id == "os"
            if node.attr in STARTERS or (on_os and _os_starter(node.attr)):
                bad.append(ast.unparse(node))
    return bad


def _os_starter(name: str) -> bool:
    return name in OS_STARTERS or name.startswith("spawn")


@pytest.mark.parametrize("module", ["server.py", "views.py"])
def test_the_server_and_its_views_never_start_a_thread_or_a_process_themselves(module):
    bad = _starts_a_thread_or_process((SRC / "web" / module).read_text(encoding="utf-8"))
    assert bad == [], f"{module} must go through runtime.blocking: {bad}"


@pytest.mark.parametrize("line", [
    "import threading",
    "from concurrent.futures import ThreadPoolExecutor",
    "import multiprocessing",
    "import subprocess",
    "import _thread",
    "import anyio",
    "from anyio.to_thread import run_sync",
    "from anyio import to_thread",
    "from starlette.concurrency import run_in_threadpool",
    "from asyncio import to_thread as x",
    "from asyncio import create_subprocess_exec",
    "import asyncio\nx = asyncio.to_thread",
    "import asyncio\nasyncio.create_subprocess_exec('ls')",
    "import asyncio\nasyncio.create_subprocess_shell('ls')",
    "import asyncio\nasyncio.get_running_loop().run_in_executor(None, print)",
    "import os\nos.system('ls')",
    "import os\nos.fork()",
    "import os\nos.spawnl(0, 'ls')",
    "from os import system",
])
def test_the_thread_and_process_check_catches_each_way_of_starting_one(line):
    # why: a check that flagged nothing would pass the test above whatever the server does.
    assert _starts_a_thread_or_process(line), line


def test_blocking_runs_a_call_off_the_event_loop_and_returns_its_result():
    async def main():
        loop_thread = threading.get_ident()
        return loop_thread, await runtime.blocking(lambda a, *, b: (threading.get_ident(), a + b),
                                                   1, b=2)

    loop_thread, (worker, total) = asyncio.run(main())
    assert total == 3 and worker != loop_thread


def test_blocking_runs_inline_in_pyodide_which_has_no_threads(monkeypatch):
    monkeypatch.setattr(runtime, "INLINE", True)  # as sys.platform == "emscripten" makes it

    async def main():
        return threading.get_ident(), await runtime.blocking(threading.get_ident)

    loop_thread, worker = asyncio.run(main())
    assert worker == loop_thread
