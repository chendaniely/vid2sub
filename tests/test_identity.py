from vid2sub.media.identity import MIB, full_sha256, identify, quick_sha256


def write(path, data):
    path.write_bytes(data)
    return path


def test_the_quick_hash_reads_only_the_ends_and_the_size(tmp_path):
    data = bytearray(b"a" * (5 * MIB))
    a = write(tmp_path / "a.mkv", bytes(data))
    data[2 * MIB] = ord("b")  # the middle: invisible to the quick hash
    b = write(tmp_path / "b.mkv", bytes(data))
    assert quick_sha256(a) == quick_sha256(b)
    assert full_sha256(a) != full_sha256(b)
    data[-1] = ord("c")  # the last MiB: visible
    c = write(tmp_path / "c.mkv", bytes(data))
    assert quick_sha256(c) != quick_sha256(b)


def test_a_small_file_is_hashed_whole_and_its_size_counts(tmp_path):
    x = write(tmp_path / "x", b"hello")
    y = write(tmp_path / "y", b"hello\x00")
    assert quick_sha256(x) != quick_sha256(y)
    assert identify(x).size == 5


def test_files_with_identical_ends_but_different_sizes_differ(tmp_path):
    a = write(tmp_path / "a.mkv", b"a" * (3 * MIB))
    b = write(tmp_path / "b.mkv", b"a" * (4 * MIB))
    assert quick_sha256(a) != quick_sha256(b)
