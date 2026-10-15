import pytest

from vid2sub.commands._common import duration, expand


def touch(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")
    return path


def test_a_folder_expands_to_its_videos_in_episode_order(tmp_path):
    for name in ("Show S01E10.mkv", "Show S01E02.mkv", "Show S01E01.mkv", "Extras.mkv",
                 ".DS_Store", "Show S01E01.en.srt", "notes.txt"):
        touch(tmp_path / name)
    names = [p.rsplit("/", 1)[-1].rsplit("\\", 1)[-1] for p in expand([str(tmp_path)])]
    assert names == ["Show S01E01.mkv", "Show S01E02.mkv", "Show S01E10.mkv", "Extras.mkv"]


def test_recursive_looks_inside_subfolders(tmp_path):
    touch(tmp_path / "Season 1" / "S01E01.mkv")
    assert expand([str(tmp_path)]) == []
    assert len(expand([str(tmp_path)], recursive=True)) == 1


def test_a_list_file_skips_blank_lines_and_comments_and_links_pass_through(tmp_path):
    video = touch(tmp_path / "a.mkv")
    listing = tmp_path / "list.txt"
    listing.write_text(f"# season one\n\n{video}\nhttps://youtu.be/dQw4w9WgXcQ\n")
    assert expand([], from_file=str(listing)) == [str(video), "https://youtu.be/dQw4w9WgXcQ"]


@pytest.mark.parametrize("value, seconds", [("600", 600), ("90s", 90), ("10m", 600),
                                            ("1.5h", 5400)])
def test_durations_read_seconds_minutes_and_hours(value, seconds):
    assert duration(value) == seconds
