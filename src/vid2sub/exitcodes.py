"""Exit codes, after sysexits, as in audio-router (spec §18.2)."""

OK = 0
FAILED = 1  # at least one input failed
USAGE = 64
UNAVAILABLE = 69  # a tool, model or endpoint isn't there
TEMPFAIL = 75  # interrupted, or a connection dropped: re-run to carry on
CONFIG = 78
