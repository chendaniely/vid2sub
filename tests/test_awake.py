import sys

import pytest

from vid2sub.awake import keep_awake


def test_keeping_awake_starts_and_stops_cleanly():
    with keep_awake():
        pass


@pytest.mark.skipif(sys.platform not in ("darwin", "linux"), reason="needs a helper process")
def test_the_helper_process_has_exited_when_the_block_ends():
    with keep_awake() as helper:
        pass
    if sys.platform == "darwin":
        assert helper is not None
    if helper is not None:  # None on a Linux machine without systemd-inhibit
        assert helper.poll() is not None
