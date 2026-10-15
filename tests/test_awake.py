from vid2sub.awake import keep_awake


def test_keeping_awake_starts_and_stops_cleanly():
    with keep_awake():
        pass
