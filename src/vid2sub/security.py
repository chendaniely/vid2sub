"""Security helpers every other module uses (spec §6.5–§6.8).

`safe_component` builds every name vid2sub writes, so a YouTube title or a hostile file name can't
smuggle in a path separator, a Windows reserved name or a bidi trick. `safe_write` is the only way
vid2sub writes a file: a temporary file created exclusively without following links, fsynced,
then atomically replaced; a target that isn't a regular file (a planted symlink) is refused, and
Windows' sharing violations (Plex or antivirus holding the file) are retried. Child processes get
an allowlisted environment, so they never inherit keys. Keys travel over plain http only to this
machine or a Tailscale address (spec §5.2).
"""

from __future__ import annotations

import ipaddress
import os
import re
import secrets
import stat
import time
import unicodedata
from collections.abc import Iterable, Mapping
from pathlib import Path
from urllib.parse import urlsplit

_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
             *(f"LPT{i}" for i in range(1, 10))}
_BAD = set('<>:"/\\|?*')
_ENV_KEEP = ("PATH", "HOME", "USERPROFILE", "TMP", "TEMP", "TMPDIR", "LANG", "LC_ALL",
             "LC_CTYPE", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "XDG_CACHE_HOME",
             "DENO_DIR", "SSL_CERT_FILE", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY",
             "http_proxy", "https_proxy", "no_proxy")
_TAILNET = ipaddress.ip_network("100.64.0.0/10")


class WriteRefused(Exception):
    pass


class InputRefused(ValueError):
    pass


def safe_component(name: str, *, max_bytes: int = 200) -> str:
    name = unicodedata.normalize("NFC", name)
    kept = []
    for ch in name:
        if unicodedata.category(ch) in ("Cc", "Cf", "Cs", "Co", "Cn"):
            continue  # control characters, bidi and other format marks, surrogates
        kept.append("_" if ch in _BAD else ch)
    out = re.sub(r"\s+", " ", "".join(kept)).strip().rstrip(". ")
    if not out:
        return "untitled"
    if out.split(".")[0].upper() in _RESERVED:
        out = "_" + out
    while len(out.encode("utf-8")) > max_bytes:
        out = out[:-1]
    return out.rstrip(". ") or "untitled"


def _replace(src: Path, dst: Path, attempts: int = 6) -> None:
    for i in range(attempts):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if os.name != "nt" or i == attempts - 1:
                raise WriteRefused(f"{dst.name} is open in another program (Plex or antivirus?);"
                                   " try again") from None
            time.sleep(0.2 * 2 ** i)


def safe_write(path: Path, data: bytes, *, overwrite: bool) -> None:
    path = Path(path)
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        st = None
    if st is not None:
        if not stat.S_ISREG(st.st_mode):
            raise WriteRefused(f"{path.name} exists and isn't a regular file")
        if not overwrite:
            raise WriteRefused(f"{path.name} already exists")
    tmp = path.parent / f".{path.name}.{secrets.token_hex(6)}.tmp"
    flags = (os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
             | getattr(os, "O_BINARY", 0))
    fd = os.open(tmp, flags, 0o644)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        _replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def redact(text: str, secret_values: Iterable[str]) -> str:
    for value in sorted({v for v in secret_values if v and len(v) >= 6}, key=len, reverse=True):
        text = text.replace(value, "[redacted]")
    return text


def child_env(environ: Mapping[str, str] = os.environ) -> dict[str, str]:
    return {k: environ[k] for k in _ENV_KEEP if k in environ}


def host_of(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def is_tailnet(host: str) -> bool:
    if host.endswith(".ts.net"):
        return True
    try:
        return ipaddress.ip_address(host) in _TAILNET
    except ValueError:
        return False


def key_transport_ok(url: str) -> bool:
    scheme, host = urlsplit(url).scheme, host_of(url)
    return scheme == "https" or (scheme == "http" and (is_loopback(host) or is_tailnet(host)))


def resolve_input(value: str, *, cwd: Path | None = None) -> Path:
    """CLI inputs may be relative (plan decision 9); drive-relative Windows paths are refused."""
    p = Path(value).expanduser()
    if os.name == "nt" and p.drive and not p.root:
        raise InputRefused("a drive-relative path like C:file is ambiguous; give the full path")
    return p if p.is_absolute() else (cwd or Path.cwd()) / p
