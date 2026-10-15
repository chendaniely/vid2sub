import os
import sys

import pytest

from vid2sub import security as s


@pytest.mark.parametrize("name, expected", [
    ("a/b: c?", "a_b_ c_"),
    ("CON", "_CON"),
    ("nul.txt", "_nul.txt"),
    ("ends with dots...", "ends with dots"),
    ("tab\there\u202eevil", "tabhereevil"),
    ("", "untitled"),
])
def test_safe_component_makes_names_every_os_accepts(name, expected):
    assert s.safe_component(name) == expected


def test_safe_component_caps_the_length_in_bytes():
    name = s.safe_component("字" * 300)
    assert len(name.encode()) <= 200 and name.startswith("字")


def test_safe_write_creates_a_file_and_leaves_no_temporary_files(tmp_path):
    target = tmp_path / "a.srt"
    s.safe_write(target, b"hello", overwrite=False)
    assert target.read_bytes() == b"hello"
    assert [p.name for p in tmp_path.iterdir()] == ["a.srt"]


def test_safe_write_refuses_to_overwrite_unless_told(tmp_path):
    target = tmp_path / "a.srt"
    target.write_bytes(b"old")
    with pytest.raises(s.WriteRefused, match="already exists"):
        s.safe_write(target, b"new", overwrite=False)
    s.safe_write(target, b"new", overwrite=True)
    assert target.read_bytes() == b"new"


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges on Windows")
def test_safe_write_never_follows_a_planted_symlink(tmp_path):
    secret = tmp_path / "zshrc"
    secret.write_bytes(b"precious")
    link = tmp_path / "Show.en.srt"
    link.symlink_to(secret)
    with pytest.raises(s.WriteRefused, match="isn't a regular file"):
        s.safe_write(link, b"evil", overwrite=True)
    assert secret.read_bytes() == b"precious"


def test_safe_write_cleans_up_when_the_replace_fails(tmp_path, monkeypatch):
    def boom(src, dst):
        raise OSError("disk on fire")
    monkeypatch.setattr(s.os, "replace", boom)
    with pytest.raises(OSError):
        s.safe_write(tmp_path / "a.srt", b"x", overwrite=False)
    assert list(tmp_path.iterdir()) == []


def test_redact_removes_every_secret_value():
    assert s.redact("auth sk-abcdef123 failed for sk-abcdef123", ["sk-abcdef123", ""]) == \
        "auth [redacted] failed for [redacted]"


def test_child_processes_never_inherit_keys():
    env = s.child_env({"PATH": "/bin", "HOME": "/h", "OPENAI_API_KEY": "x", "SPARK_API_KEY": "y"})
    assert env == {"PATH": "/bin", "HOME": "/h"}


@pytest.mark.parametrize("url, ok", [
    ("https://api.openai.com/v1", True),
    ("http://127.0.0.1:9100/v1", True),
    ("http://localhost:9100/v1", True),
    ("http://brightroar.tail1234.ts.net:9100/v1", True),
    ("http://100.101.102.103:9100/v1", True),
    ("http://192.168.1.50:9100/v1", False),
    ("http://evil.example/v1", False),
])
def test_keys_travel_over_plain_http_only_to_this_machine_or_the_tailnet(url, ok):
    assert s.key_transport_ok(url) is ok


def test_relative_inputs_resolve_against_the_working_directory(tmp_path):
    assert s.resolve_input("ep1.mkv", cwd=tmp_path) == tmp_path / "ep1.mkv"
    assert s.resolve_input(str(tmp_path / "x.mkv")) == tmp_path / "x.mkv"


@pytest.mark.skipif(os.name != "nt", reason="drive-relative paths exist only on Windows")
def test_a_drive_relative_windows_path_is_refused():
    with pytest.raises(s.InputRefused):
        s.resolve_input("C:episode.mkv")
