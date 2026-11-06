"""The browser plays a video or its playback audio by an unguessable token bound to the launch,
never by its path, and a file swapped since the token was issued is never served (spec §6.3,
§6.5; plan Decision 1; S27, S43; Review Focus 1).

The Range, 416 and 404 tests follow recordings' media route tests (packages/ui/tests/test_app.py
at 8deb039).
"""

import logging
import mimetypes
import os
import re
import secrets
import sys
import traceback
from pathlib import Path

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from vid2sub import pipeline
from vid2sub.web import media
from vid2sub.web.guards import LOCAL_HOSTS, HostGuard, WriteGuard

BODY = bytes(range(256)) * 4  # 1024 bytes, each position recognisable
MEDIA = {
    "content-security-policy": "sandbox",
    "x-content-type-options": "nosniff",
    "cache-control": "no-store",
    "cross-origin-resource-policy": "same-origin",
    "x-frame-options": "DENY",
}


@pytest.fixture
def tokens():
    return media.MediaTokens()


@pytest.fixture
def client(tokens):
    # As Task 11 wraps it, less TokenGuard (Task 9's tests cover the cookie).
    app = HostGuard(WriteGuard(Starlette(routes=[media.route(tokens)]), LOCAL_HOSTS), LOCAL_HOSTS)
    with TestClient(app, base_url="http://127.0.0.1:8765") as c:
        yield c


def _file(folder: Path, name: str, body: bytes = BODY) -> Path:
    path = folder / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return path


# ---- tokens ----------------------------------------------------------------------------------


def test_a_token_is_256_random_bits_and_never_names_the_file(tokens, tmp_path):
    video = _file(tmp_path, "Show S01E01.mp4")
    issued = [tokens.issue(video, owner="ep1") for _ in range(20)]
    assert len(set(issued)) == 20  # a fresh token each time, not one derived from the path
    assert all(re.fullmatch(r"[A-Za-z0-9_-]{43}", t) for t in issued)
    assert not any("Show" in t for t in issued)


def test_a_live_token_resolves_to_its_file(tokens, tmp_path):
    video = _file(tmp_path, "clip.mp4")
    assert tokens.resolve(tokens.issue(video, owner="ep1")) == video


@pytest.mark.parametrize(
    "name", ["page.html", "image.svg", "notes.txt", "noextension", "clip.mp4.gz", "clip.mkv.zip"]
)
def test_only_an_audio_or_video_file_gets_a_token(tokens, tmp_path, name):
    # Never a page or an SVG served from the engine's own origin (as in recordings' route).
    path = _file(tmp_path, name, b"<script>alert(1)</script>")
    with pytest.raises(ValueError, match="not an audio or video file"):
        tokens.issue(path, owner="ep1")


def test_only_a_regular_file_gets_a_token(tokens, tmp_path):
    folder = tmp_path / "folder.mp4"
    folder.mkdir()
    with pytest.raises(ValueError, match="not a regular file"):
        tokens.issue(folder, owner="ep1")


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX FIFOs")
def test_a_fifo_gets_no_token(tokens, tmp_path):
    # Serving a FIFO would block a worker forever.
    fifo = tmp_path / "pipe.mp4"
    os.mkfifo(fifo)
    with pytest.raises(ValueError, match="not a regular file"):
        tokens.issue(fifo, owner="ep1")


def test_a_missing_or_relative_path_gets_no_token_and_the_error_names_no_path(tokens, tmp_path):
    # Spec §6.5: accepted paths are fully qualified. Spec §6.8: an error may be logged.
    for path in (
        tmp_path / "secret-title.mp4",
        Path("secret-title.mp4"),
        tmp_path / "secret\x00title.mp4",
    ):
        with pytest.raises(ValueError) as exc:
            tokens.issue(path, owner="ep1")
        assert "secret" not in str(exc.value) and str(tmp_path) not in str(exc.value)


def test_a_relative_path_gets_no_token_even_when_the_file_exists(tokens, tmp_path, monkeypatch):
    # Spec §6.5: accepted paths are fully qualified, so the working directory never decides.
    _file(tmp_path, "clip.mp4")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="must be absolute"):
        tokens.issue(Path("clip.mp4"), owner="ep1")


@pytest.mark.parametrize(
    "name, expected",
    [
        ("a.mkv", "video/x-matroska"),
        ("A.MKV", "video/x-matroska"),
        ("a.m4a", "audio/mp4"),
        ("a.mp4", "video/mp4"),
        ("a.mp3", "audio/mpeg"),
        ("a.webm", "video/webm"),
        ("a.wav", "audio/wav"),
        ("a.opus", "audio/ogg"),
        ("a.html", None),
        ("a.svg", None),
        ("a", None),
        ("a.mp4.gz", None),
    ],
)
def test_the_media_type_is_audio_or_video_and_fixed_for_the_editors_formats(name, expected):
    # Every type comes from one fixed table, never the OS's (which differs by host). .wav and
    # .opus are the types browsers recognise: Chrome's canPlayType says "" for audio/vnd.wave.
    assert media.media_type(Path(name)) == expected


# ---- revocation and swapped files ------------------------------------------------------------


def test_revoking_an_owner_revokes_only_its_tokens(tokens, client, tmp_path):
    # Plan Decision 1: closing an episode revokes its tokens; another episode's still play.
    video, audio, other = (_file(tmp_path, n) for n in ("v.mp4", "a.m4a", "o.mp4"))
    t1, t2 = tokens.issue(video, owner="ep1"), tokens.issue(audio, owner="ep1")
    t3 = tokens.issue(other, owner="ep2")
    tokens.revoke_owner("ep1")
    assert [client.get(f"/media/{t}").status_code for t in (t1, t2, t3)] == [404, 404, 200]
    assert tokens.resolve(t1) is None and tokens.resolve(t3) == other
    tokens.revoke_owner("no-such-episode")  # nothing to revoke is fine
    assert tokens.resolve(t3) == other


def test_a_file_replaced_since_the_token_was_issued_is_never_served(tokens, client, tmp_path):
    # Spec §6.5: the token records (dev, inode, size), so another file put in its place, even of
    # the same size, isn't served.
    video = _file(tmp_path, "clip.mp4")
    token = tokens.issue(video, owner="ep1")
    os.replace(_file(tmp_path, "planted.mp4", b"\xff" * len(BODY)), video)
    assert client.get(f"/media/{token}").status_code == 404
    assert tokens.resolve(token) is None


def test_a_file_rewritten_in_place_to_another_size_is_never_served(tokens, client, tmp_path):
    video = _file(tmp_path, "clip.mp4")
    token = tokens.issue(video, owner="ep1")
    with video.open("ab") as f:
        f.write(b"more")
    assert client.get(f"/media/{token}").status_code == 404


def test_a_file_deleted_since_is_404_not_500(tokens, client, tmp_path):
    video = _file(tmp_path, "clip.mp4")
    token = tokens.issue(video, owner="ep1")
    video.unlink()
    assert client.get(f"/media/{token}").status_code == 404


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges on Windows")
def test_a_symlink_pointed_elsewhere_since_is_never_served(tokens, client, tmp_path):
    real = _file(tmp_path, "real.mp4")
    other = _file(tmp_path, "other.mp4")
    link = tmp_path / "link.mp4"
    link.symlink_to(real)
    token = tokens.issue(link, owner="ep1")
    assert client.get(f"/media/{token}").content == BODY  # the file it points at
    link.unlink()
    link.symlink_to(other)
    assert client.get(f"/media/{token}").status_code == 404


# ---- the route -------------------------------------------------------------------------------


def test_media_is_served_whole_and_by_range(tokens, client, tmp_path):
    token = tokens.issue(_file(tmp_path, "clip.mp4"), owner="ep1")
    full = client.get(f"/media/{token}")
    assert full.status_code == 200 and full.content == BODY
    assert full.headers["content-type"] == "video/mp4"
    assert full.headers["accept-ranges"] == "bytes"
    part = client.get(f"/media/{token}", headers={"Range": "bytes=0-99"})
    assert part.status_code == 206
    assert part.headers["content-range"] == f"bytes 0-99/{len(BODY)}"
    assert part.content == BODY[:100]
    tail = client.get(f"/media/{token}", headers={"Range": "bytes=1000-"})
    assert tail.status_code == 206 and tail.content == BODY[1000:]


def test_a_range_past_the_end_is_416_not_500(tokens, client, tmp_path):
    token = tokens.issue(_file(tmp_path, "clip.mp4"), owner="ep1")
    r = client.get(f"/media/{token}", headers={"Range": "bytes=999999999-"})
    assert r.status_code == 416


def test_head_answers_the_headers_without_the_body(tokens, client, tmp_path):
    token = tokens.issue(_file(tmp_path, "clip.mkv"), owner="ep1")
    r = client.head(f"/media/{token}")
    assert r.status_code == 200 and r.content == b""
    assert r.headers["content-type"] == "video/x-matroska"
    assert r.headers["content-length"] == str(len(BODY))


@pytest.mark.parametrize(
    "token",
    ["", "x", "..", "%2e%2e", secrets.token_urlsafe(32)],
    ids=["empty", "short", "dots", "encoded-dots", "unknown"],
)
def test_an_unknown_token_is_404_and_echoes_nothing(tokens, client, tmp_path, token):
    live = tokens.issue(_file(tmp_path, "clip.mp4"), owner="ep1")
    r = client.get(f"/media/{token}")
    assert r.status_code == 404
    assert live.encode() not in r.content


def test_a_near_miss_of_a_live_token_is_404(tokens, client, tmp_path):
    live = tokens.issue(_file(tmp_path, "clip.mp4"), owner="ep1")
    for near in (live + "x", live[:-1], live.upper() if live.upper() != live else live + "A"):
        assert client.get(f"/media/{near}").status_code == 404


def test_the_file_name_is_in_no_header_and_the_file_plays_inline(tokens, client, tmp_path):
    token = tokens.issue(_file(tmp_path, "Secret Title S01E01.mp4"), owner="ep1")
    r = client.get(f"/media/{token}")
    assert r.headers["content-disposition"] == "inline"
    assert not any(b"Secret" in k + v for k, v in r.headers.raw)


@pytest.mark.parametrize(
    "folder, name",
    [
        ("日本語のドラマ", "第01話 字幕.mkv"),
        # A right-to-left override in the folder name: written as escapes, which ruff requires.
        ("Épisodes \u202efdp.exe\u202c", "Épisode 01 – l’été.mp4"),
        ("🎬 Films", "Clip 🎞️ 01.m4a"),
    ],
    ids=["cjk", "accents-and-bidi", "emoji"],
)
def test_a_path_with_non_ascii_bidi_or_emoji_characters_plays(
    tokens, client, tmp_path, caplog, folder, name
):
    # Review Focus 1: it opens and plays through /media/, and the path goes nowhere else.
    caplog.set_level(logging.DEBUG)
    path = _file(tmp_path / folder, name)
    token = tokens.issue(path, owner="ep1")
    full = client.get(f"/media/{token}")
    part = client.get(f"/media/{token}", headers={"Range": "bytes=10-19"})
    assert (full.status_code, full.content) == (200, BODY)
    assert (part.status_code, part.content) == (206, BODY[10:20])
    for r in (full, part):
        raw = b"".join(k + v for k, v in r.headers.raw).decode("latin-1")
        assert folder not in raw and name not in raw
    assert not any(folder in rec.getMessage() or name in rec.getMessage() for rec in caplog.records)


def test_every_media_answer_carries_the_media_headers_through_the_guard(tokens, client, tmp_path):
    # Spec §6.3. The headers are WriteGuard's (Task 8); 404 and 416 are under /media/ too.
    token = tokens.issue(_file(tmp_path, "clip.mp4"), owner="ep1")
    answers = [
        client.get(f"/media/{token}"),
        client.get(f"/media/{token}", headers={"Range": "bytes=0-9"}),
        client.get(f"/media/{token}", headers={"Range": "bytes=999999999-"}),
        client.get("/media/unknown"),
    ]
    assert [r.status_code for r in answers] == [200, 206, 416, 404]
    for r in answers:
        assert {k: r.headers.get(k) for k in MEDIA} == MEDIA
        assert r.headers.get_list("content-security-policy") == ["sandbox"]


# ---- no path leaves /media/ in an exception --------------------------------------------------


def _vanish_after_the_check(monkeypatch, tokens, change):
    """Make the gap between the route's check and FileResponse's open: `change()` runs once the
    check has passed."""
    live = tokens._live

    def checked_then_changed(token):
        answer = live(token)
        change()
        return answer

    monkeypatch.setattr(tokens, "_live", checked_then_changed)


def _names_nothing(exc: BaseException, caplog, *hidden: str) -> bool:
    shown = "".join(traceback.format_exception(exc)) + "".join(
        rec.getMessage() + (rec.exc_text or "") for rec in caplog.records
    )
    return not any(h in shown for h in hidden)


def test_a_file_removed_after_the_check_raises_an_error_that_names_no_path(
    tokens, client, tmp_path, monkeypatch, caplog
):
    # Spec §6.8: Starlette opens the file by path after the check, and its OSError names the path.
    video = _file(tmp_path / "Secret Show", "Secret Title S01E01.mp4")
    token = tokens.issue(video, owner="ep1")
    _vanish_after_the_check(monkeypatch, tokens, video.unlink)
    with pytest.raises(Exception) as exc:
        client.get(f"/media/{token}")
    assert _names_nothing(exc.value, caplog, "Secret", str(tmp_path))
    assert isinstance(exc.value, media.MediaUnreadable)
    assert exc.value.__cause__ is None and exc.value.__context__ is None


def test_a_file_truncated_after_the_check_raises_an_error_that_names_no_path(
    tokens, client, tmp_path, monkeypatch, caplog
):
    # Several ranges make Starlette raise "File at path <path> is shorter than expected".
    video = _file(tmp_path / "Secret Show", "Another Title.mp4")
    token = tokens.issue(video, owner="ep1")
    _vanish_after_the_check(monkeypatch, tokens, lambda: video.write_bytes(BODY[:50]))
    with pytest.raises(Exception) as exc:
        client.get(f"/media/{token}", headers={"Range": "bytes=0-9,100-199"})
    assert _names_nothing(exc.value, caplog, "Secret", "Another", str(tmp_path))
    assert isinstance(exc.value, media.MediaUnreadable)


# ---- one fixed table of media types, never the OS's ------------------------------------------


@pytest.fixture
def knows_no_types(monkeypatch):
    """Python's mimetypes knowing nothing, as on a host with no mime.types and a bare registry."""
    monkeypatch.setattr(mimetypes, "guess_type", lambda *a, **k: (None, None))


@pytest.mark.parametrize("suffix", sorted(pipeline.MEDIA_SUFFIXES))
def test_every_suffix_the_pipeline_accepts_gets_an_audio_or_video_type_whatever_the_os_holds(
    suffix, knows_no_types
):
    assert (media.media_type(Path(f"a{suffix}")) or "").startswith(("audio/", "video/"))


@pytest.mark.parametrize("suffix", [".ts", ".m2ts"])
def test_mpeg_transport_streams_are_video_mp2t_as_the_iana_registry_has_it(suffix, knows_no_types):
    assert media.media_type(Path(f"a{suffix}")) == "video/MP2T"


def test_the_table_covers_exactly_the_suffixes_the_pipeline_accepts():
    assert set(media._TYPES) == set(pipeline.MEDIA_SUFFIXES)


@pytest.mark.parametrize("name", ["list.m3u", "list.asx", "list.wax", "list.ram", "a.mkv.gz"])
def test_a_playlist_or_a_compressed_name_gets_no_type_whatever_the_os_holds(name):
    # This Mac's /etc/apache2/mime.types types .m3u and .asx as audio and video.
    assert media.media_type(Path(name)) is None


def test_a_name_with_url_characters_is_judged_by_its_plain_suffix():
    # mimetypes.guess_type parses a name as a URL, which would call this video/mp4. The plain
    # suffix is .html, so it is None.
    assert media.media_type(Path("ab:x.mp4#.html")) is None
    assert media.media_type(Path("ab:x.mp4?.svg")) is None


# ---- a file rewritten in place, even at the same size ----------------------------------------


def test_a_file_rewritten_in_place_at_the_same_size_is_never_served(tokens, client, tmp_path):
    # Same device, inode and size: only the modification time shows the bytes changed.
    video = _file(tmp_path, "clip.mp4")
    token = tokens.issue(video, owner="ep1")
    before = video.stat()
    video.write_bytes(b"\xff" * len(BODY))
    os.utime(video, ns=(before.st_atime_ns, before.st_mtime_ns + 5_000_000_000))
    after = video.stat()
    assert (after.st_ino, after.st_size) == (before.st_ino, before.st_size)
    assert tokens.resolve(token) is None
    assert client.get(f"/media/{token}").status_code == 404
