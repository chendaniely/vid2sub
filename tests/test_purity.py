"""The pure packages run in Pyodide later (spec §3.2, §21), so they may import only the standard
library (minus processes and networking), pydantic and the subtitle libraries."""

import ast
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "vid2sub"
PURE_FILES = [
    *sorted((SRC / "subs").rglob("*.py")),
    *sorted((SRC / "parse").rglob("*.py")),
    *([SRC / "catalog.py"] if (SRC / "catalog.py").exists() else []),
]
THIRD_PARTY = {"pydantic", "pysubs2", "opencc_purepy", "charset_normalizer"}
FORBIDDEN_STDLIB = {"subprocess", "socket", "http", "urllib", "asyncio", "threading",
                    "multiprocessing", "ssl", "ctypes"}
PURE_INTERNAL = ("vid2sub.subs", "vid2sub.parse", "vid2sub.catalog")


def _imports(path: Path):
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.module


def test_pure_modules_import_only_the_standard_library_pydantic_and_subtitle_libraries():
    assert PURE_FILES, "no pure modules found"
    bad = []
    for path in PURE_FILES:
        for name in _imports(path):
            root = name.split(".")[0]
            if name == "__future__":
                continue
            if root == "vid2sub":
                if not name.startswith(PURE_INTERNAL):
                    bad.append(f"{path.name}: {name}")
            elif root in FORBIDDEN_STDLIB or (
                root not in sys.stdlib_module_names and root not in THIRD_PARTY
            ):
                bad.append(f"{path.name}: {name}")
    assert not bad, "impure imports in pure modules:\n" + "\n".join(bad)
