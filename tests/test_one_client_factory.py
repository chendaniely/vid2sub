"""Spec §6.4: one client factory. Only engines/clients.py may import openai, httpx or chatlas,
so every client gets an explicit address and key, no redirects, and the cloud check."""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "vid2sub"
NETWORK = {"openai", "httpx", "chatlas"}


def test_only_the_client_factory_imports_network_libraries():
    offenders = []
    for path in SRC.rglob("*.py"):
        if path == SRC / "engines" / "clients.py":
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                if name.split(".")[0] in NETWORK:
                    offenders.append(f"{path.relative_to(SRC)}: {name}")
    assert not offenders, "network libraries imported outside engines/clients.py:\n" + \
        "\n".join(offenders)
