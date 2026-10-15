"""Shared test setup.

Tests marked `media` need ffmpeg and ffprobe. They skip without them, unless
VID2SUB_REQUIRE_FFMPEG=1 (CI sets it), when they fail instead: a skipped guard is no guard.
"""

from __future__ import annotations

import os
import shutil

import pytest


def pytest_collection_modifyitems(config, items):
    have = shutil.which("ffmpeg") and shutil.which("ffprobe")
    if have or os.environ.get("VID2SUB_REQUIRE_FFMPEG") == "1":
        return
    skip = pytest.mark.skip(reason="ffmpeg/ffprobe not installed")
    for item in items:
        if "media" in item.keywords:
            item.add_marker(skip)
