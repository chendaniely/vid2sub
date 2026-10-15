"""Keep the machine awake while vid2sub works (spec §8.10; plan decision 5).

A season run from the CLI must survive the laptop's idle sleep. macOS: caffeinate, tied to this
process. Windows: SetThreadExecutionState. Linux: systemd-inhibit, when it exists. These are
long-running helpers rather than run_tool calls, so they're started here directly, by absolute
path, with the key-free environment.
"""

from __future__ import annotations

import contextlib
import os
import subprocess
import sys
from collections.abc import Iterator

from vid2sub.media.tools import which
from vid2sub.security import child_env

_ES_CONTINUOUS = 0x80000000
_ES_SYSTEM_REQUIRED = 0x00000001


@contextlib.contextmanager
def keep_awake() -> Iterator[subprocess.Popen | None]:
    """Yield the helper process (None where there is none), and stop it on the way out."""
    proc: subprocess.Popen | None = None
    windows = False
    quiet = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL,
             "stderr": subprocess.DEVNULL}
    try:
        if sys.platform == "darwin" and os.path.exists("/usr/bin/caffeinate"):
            proc = subprocess.Popen(["/usr/bin/caffeinate", "-i", "-w", str(os.getpid())],
                                    env=child_env(), **quiet)
        elif os.name == "nt":
            import ctypes

            ctypes.windll.kernel32.SetThreadExecutionState(_ES_CONTINUOUS | _ES_SYSTEM_REQUIRED)
            windows = True
        else:
            exe, tail = which("systemd-inhibit"), which("tail")
            if exe and tail:
                # tail follows this process and exits with it, so the lock can't outlive us
                proc = subprocess.Popen([exe, "--what=idle:sleep", "--who=vid2sub",
                                         "--why=making subtitles", "--mode=block", tail,
                                         f"--pid={os.getpid()}", "-f", "/dev/null"],
                                        env=child_env(), **quiet)
        yield proc
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        if windows:
            import ctypes

            ctypes.windll.kernel32.SetThreadExecutionState(_ES_CONTINUOUS)
