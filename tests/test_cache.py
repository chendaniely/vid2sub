import json
import os
import stat
import sys
from pathlib import Path

import pytest

from vid2sub import cache as caching
from vid2sub.cache import Cache
from vid2sub.cli import main
from vid2sub.config import Config

OLD, MID, NEW = ("a" * 64, "b" * 64, "c" * 64)


def entry(cache: Cache, key: str, size: int, used: float) -> Path:
    folder = cache.folder(key)
    (folder / "playback-a0.m4a").write_bytes(b"x" * size)
    os.utime(folder, (used, used))
    return folder


@pytest.fixture
def cache(tmp_path) -> Cache:
    c = Cache(tmp_path / "cache", max_bytes=250)
    for key, used in ((OLD, 1_000), (MID, 2_000), (NEW, 3_000)):
        entry(c, key, 100, used)
    return c


def test_the_cache_is_the_platforms_cache_folder(monkeypatch, tmp_path):
    if sys.platform == "darwin":
        monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
        assert caching.default_root() == Path.home() / "Library" / "Caches" / "vid2sub"
    elif sys.platform == "win32":
        assert caching.default_root().parts[-2:] == ("vid2sub", "Cache")
    else:
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
        assert caching.default_root() == tmp_path / "vid2sub"


def test_the_cap_comes_from_cache_max_gb():
    config = Config.model_validate({"defaults": {"cache_max_gb": 1.5}})
    c = caching.from_config(config, Path("/nowhere"))
    assert c.max_bytes == 1_500_000_000 and c.root == Path("/nowhere")


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes")
def test_an_entry_folder_is_private_to_the_user(tmp_path):
    folder = Cache(tmp_path / "cache", max_bytes=1).folder(OLD)
    assert stat.S_IMODE(folder.stat().st_mode) == 0o700
    assert stat.S_IMODE((tmp_path / "cache").stat().st_mode) == 0o700


@pytest.mark.parametrize("key", ["abc", "A" * 64, "../" + "a" * 61, ""])
def test_a_key_that_isnt_a_quick_hash_is_refused(tmp_path, key):
    with pytest.raises(ValueError, match="64-hex"):
        Cache(tmp_path / "cache", max_bytes=1).folder(key)


def test_the_size_counts_every_entry(cache):
    assert cache.size() == 300


def test_past_the_cap_the_least_recently_used_entry_goes_first(cache):
    assert cache.evict() == 100
    assert not (cache.root / OLD).exists()
    assert (cache.root / MID).exists() and (cache.root / NEW).exists()
    assert cache.evict() == 0


def test_using_an_entry_makes_it_the_most_recent(cache):
    cache.folder(OLD)
    cache.evict()
    assert (cache.root / OLD).exists() and not (cache.root / MID).exists()


def test_eviction_never_removes_the_entry_it_is_told_to_keep(cache):
    cache.max_bytes = 0
    assert cache.evict(keep=OLD) == 200
    assert [p.name for p in cache.root.iterdir()] == [OLD]


def test_clear_removes_every_entry_and_nothing_else(cache):
    (cache.root / "notes").mkdir()
    (cache.root / "notes" / "keep.txt").write_text("mine")
    (cache.root / "readme.txt").write_text("mine")
    assert cache.clear() == 300
    assert sorted(p.name for p in cache.root.iterdir()) == ["notes", "readme.txt"]
    assert cache.size() == 0 and cache.clear() == 0


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges on Windows")
def test_clear_never_follows_a_symlink(cache, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "precious.mkv").write_bytes(b"v" * 1000)
    (cache.root / ("d" * 64)).symlink_to(outside, target_is_directory=True)
    (cache.root / NEW / "link").symlink_to(outside, target_is_directory=True)
    (cache.root / NEW / "file-link").symlink_to(outside / "precious.mkv")
    assert cache.size() == 300
    assert cache.clear() == 300
    assert (outside / "precious.mkv").read_bytes() == b"v" * 1000
    assert (cache.root / ("d" * 64)).is_symlink()


def test_a_missing_cache_is_empty(tmp_path):
    c = Cache(tmp_path / "never-made", max_bytes=1)
    assert (c.size(), c.evict(), c.clear()) == (0, 0, 0)
    assert not (tmp_path / "never-made").exists()


@pytest.fixture
def home_cache(tmp_path, monkeypatch) -> Cache:
    monkeypatch.setattr(caching, "default_root", lambda: tmp_path / "cache")
    c = Cache(tmp_path / "cache", max_bytes=1)
    entry(c, OLD, 2_500_000, 1_000)
    return c


def test_cache_clear_reports_the_bytes_freed_as_one_json_line(home_cache, capsys):
    assert main(["cache", "clear", "--json"]) == 0
    out = capsys.readouterr().out
    assert [json.loads(line) for line in out.splitlines()] == [
        {"event": "cache_cleared", "bytes": 2_500_000}]
    assert str(home_cache.root) not in out
    assert not (home_cache.root / OLD).exists()


def test_cache_clear_tells_a_person_how_much_it_freed(home_cache, capsys):
    assert main(["cache", "clear"]) == 0
    assert capsys.readouterr().out == "cleared 2.5 MB from the cache\n"


def test_doctor_reports_the_cache_size_against_its_cap(home_cache, tmp_path, capsys):
    args = ["doctor", "--config", str(tmp_path / "none.toml"), "--offline"]
    main(args + ["--json"])
    out = capsys.readouterr().out
    rows = {e["check"]: e for e in map(json.loads, out.splitlines())}
    assert rows["cache"] == {"event": "check", "check": "cache", "ok": True,
                             "essential": False, "detail": "2.5 MB of 20 GB"}
    assert str(home_cache.root) not in out
    main(args)
    assert "✓ cache: 2.5 MB of 20 GB" in capsys.readouterr().out.splitlines()
