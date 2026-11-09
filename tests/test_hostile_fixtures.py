"""The hostile fixtures (spec §6.3, §22.4; S26) are what the browser tests expect: M1's parser
keeps a subtitle's text and only `<i>` of its markup, so a `<script>`, an `<img onerror>`, `<font>`
or an ASS override reaches the editor as inert text, which it must show as text."""

import json
from pathlib import Path

from vid2sub.subs.formats import parse_subtitles

HOSTILE = Path(__file__).parent / "fixtures" / "hostile"


def test_a_hostile_srt_keeps_its_text_and_only_italics():
    cues = parse_subtitles((HOSTILE / "hostile.srt").read_bytes(), "srt")
    assert [c.text for c in cues] == [
        "window.__pwned = 1after the script",
        "red bold <i>italic</i>",
        "an image",
        "a link &lt;b&gt; &amp;",
        "braces *gone?",
        '<img src=x onerror="window.__pwned = 9"',  # not closed by ">": inert text, shown as text
        "window.__pwned = 10after nesting",  # tags nested in tags: stripped until none is left
    ]


def test_a_hostile_ass_keeps_its_text_and_only_italics():
    cues = parse_subtitles((HOSTILE / "hostile.ass").read_bytes(), "ass")
    assert [c.text for c in cues] == [
        "moved, huge and red",
        "<i>italic</i> and bold\nsecond line",
        "m 0 0 l 100 0 100 100after a drawing",
        "window.__pwned = 5tags in ASS",
        '<img src=x onerror="window.__pwned = 11"',
        "window.__pwned = 12after nesting",
    ]


def test_the_hostile_names_are_markup_bidi_and_paths():
    names = json.loads((HOSTILE / "names.json").read_text(encoding="utf-8"))["names"]
    assert any("<img" in n for n in names) and any("<script>" in n for n in names)
    assert any("\u202e" in n for n in names) and "../../etc/passwd" in names
