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

from vid2sub.web import runtime

SRC = Path(__file__).resolve().parents[1] / "src" / "vid2sub"

# What spec §21's bundle holds of vid2sub: whole packages, then single modules. `web.ops` parses
# the editor's edits at the door, so the browser editor needs it too; it is pure.
BUNDLED_TREES = ("vid2sub.subs", "vid2sub.parse")
BUNDLED_MODULES = ("vid2sub", "vid2sub.catalog", "vid2sub.web", "vid2sub.web.server",
                   "vid2sub.web.views", "vid2sub.web.episode", "vid2sub.web.runtime",
                   "vid2sub.web.ops")
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


THREADS = {"threading", "concurrent", "multiprocessing", "subprocess", "_thread"}


def test_the_server_never_starts_a_thread_or_a_process_itself():
    tree = ast.parse((SRC / "web" / "server.py").read_text(encoding="utf-8"))
    bad = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            bad += [a.name for a in node.names if a.name.split(".")[0] in THREADS]
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".")[0] in THREADS:
                bad.append(node.module)
            bad += [f"{node.module}.{a.name}" for a in node.names
                    if a.name in ("to_thread", "run_in_executor")]
        elif isinstance(node, ast.Attribute) and node.attr in ("to_thread", "run_in_executor"):
            bad.append(ast.unparse(node))
    assert bad == [], f"server.py must go through runtime.blocking: {bad}"


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
