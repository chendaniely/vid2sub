"""The editor view in Chromium, against `vid2sub serve --demo` (spec §20, §6.3, §19.3; S26, S27,
S37; Review Focus 3): the demo episode opens and plays with captions, the cue list follows
playback with the orange bar, `aria-current` and the spoken word marked, hostile subtitles show
as plain text with only `<i>` in the overlay, a two-hour episode opens in under a second with
only the rows on screen in the page, the practice aids work, and every control is reached by
keyboard with its focus visible. Run with `make e2e`."""

import os
import re
import shutil
import time
from pathlib import Path

import pytest
from episodes import make_episode
from playwright.sync_api import expect

from vid2sub.security import safe_component

pytestmark = pytest.mark.e2e

HOSTILE = Path(__file__).parents[1] / "fixtures" / "hostile"
ORANGE = "rgb(242, 101, 34)"  # NYC orange, #F26522: the current cue's bar (spec §19.3)
DEMO_EN = ["I am delighted to be here, and I am\nparticularly delighted to be here on this",
           "occasion.", "We meet at a college noted for knowledge,",
           "in a city noted for progress,\nin a state noted for strength,"]


def demo_copy(server) -> Path:
    return next(server.tmp.glob("vid2sub-demo-*/demo"))


def open_episode(page, video: Path):
    page.get_by_test_id("open-path").fill(str(video))
    page.get_by_test_id("open-button").click()
    rows = page.get_by_test_id("cue-row")
    expect(rows.first).to_be_visible()
    return rows


def seek(page, seconds: float) -> None:
    page.get_by_test_id("media").evaluate(
        "(m, s) => new Promise((done) => { m.addEventListener('seeked', done, { once: true });"
        " m.currentTime = s; })", seconds)


def test_the_demo_episode_plays_with_captions_and_the_cue_list_follows_playback(page, server):
    rows = open_episode(page, demo_copy(server) / "jfk.mp4")
    expect(page.get_by_test_id("episode-name")).to_have_text("jfk.mp4")
    expect(rows).to_have_count(4)
    assert page.get_by_test_id("cue-text").all_inner_texts() == DEMO_EN
    expect(page.get_by_test_id("cue-translation").first).to_have_text(
        "ここに来られて光栄です。")
    media = page.get_by_test_id("media")
    expect(media).to_have_attribute("src", re.compile(r"^/media/[A-Za-z0-9_-]{43}$"))
    # It plays (muted: Chromium lets a muted video play without a gesture).
    media.evaluate("m => { m.muted = true; return m.play(); }")
    page.wait_for_function("() => document.querySelector('[data-testid=media]').currentTime > 0.5")
    current = page.locator("[data-testid=cue-row][aria-current=true]")
    expect(current).to_have_count(1)
    expect(current).to_have_attribute("data-cue", rows.first.get_attribute("data-cue"))
    assert current.evaluate("e => getComputedStyle(e).borderLeftColor") == ORANGE
    assert rows.nth(1).evaluate("e => getComputedStyle(e).borderLeftColor") != ORANGE
    spoken = current.get_by_test_id("spoken-word")
    expect(spoken).to_have_count(1)
    assert spoken.inner_text() in DEMO_EN[0]
    captions = page.get_by_test_id("caption-line")
    expect(captions).to_have_text([DEMO_EN[0], re.compile("^ここに来られて")])
    # A seek moves the bar, the captions and the spoken word to the cue at that time.
    media.evaluate("m => m.pause()")
    seek(page, 6.3)  # "college" is spoken from 6.16 s to 6.62 s
    expect(current).to_have_attribute("data-cue", rows.nth(2).get_attribute("data-cue"))
    expect(current.get_by_test_id("spoken-word")).to_have_text("college")
    expect(captions).to_have_text([
        DEMO_EN[2], "私たちが集うのは、\n知識で知られる大学、"])
    seek(page, 4.8)  # the gap between cues 2 and 3: nothing is current, no caption
    expect(current).to_have_count(0)
    expect(captions).to_have_count(0)
    page.get_by_test_id("showing").select_option("translation")
    seek(page, 10.0)
    expect(captions).to_have_text([
        "進歩で知られる都市、\n力強さで知られる州です。"])


def test_hostile_subtitles_show_as_plain_text_and_the_overlay_renders_only_italics(page, server):
    # S26, spec §6.3: written over the demo's English and Japanese, each comes back as an outside
    # edit, so the source and the translation both reach the page by their own code.
    copy = demo_copy(server)
    shutil.copyfile(HOSTILE / "hostile.srt", copy / "jfk.en.srt")
    shutil.copyfile(HOSTILE / "hostile.srt", copy / "jfk.ja.srt")
    open_episode(page, copy / "jfk.mp4")
    expect(page.get_by_test_id("episode-notes")).to_contain_text("kept your outside edit to en")
    texts = page.get_by_test_id("cue-text")
    expect(texts).to_have_text(["window.__pwned = 1after the script", "red bold <i>italic</i>",
                                "an image", "a link &lt;b&gt; &amp;", "braces *gone?",
                                '<img src=x onerror="window.__pwned = 9"',
                                "window.__pwned = 10after nesting"])
    assert page.locator("[data-testid=cue-row] [data-testid=cue-text] *").count() == 0
    page.get_by_test_id("showing").select_option("source")
    seek(page, 3.0)  # cue 2
    line = page.get_by_test_id("caption-line")
    expect(line).to_have_text("red bold italic")
    assert line.evaluate("e => [...e.querySelectorAll('*')].map((c) => c.tagName)") == ["I"]
    expect(line.locator("i")).to_have_text("italic")
    seek(page, 7.0)  # cue 4: entities stay as typed
    expect(line).to_have_text("a link &lt;b&gt; &amp;")
    assert line.evaluate("e => e.children.length") == 0
    seek(page, 11.0)  # cue 6: an <img> with no closing ">" is not a tag, so it is text (Task 13)
    expect(line).to_have_text('<img src=x onerror="window.__pwned = 9"')
    assert line.evaluate("e => e.children.length") == 0
    translations = page.get_by_test_id("cue-translation")
    assert "red bold <i>italic</i>" in translations.all_inner_texts()
    assert page.locator("[data-testid=cue-translation] *").count() == 0  # text, never markup
    page.get_by_test_id("showing").select_option("translation")
    seek(page, 3.0)  # the translation's cue 2 in the overlay: <i> only
    expect(line).to_have_text("red bold italic")
    assert line.evaluate("e => [...e.querySelectorAll('*')].map((c) => c.tagName)") == ["I"]
    seek(page, 11.0)
    expect(line).to_have_text('<img src=x onerror="window.__pwned = 9"')
    assert line.evaluate("e => e.children.length") == 0
    assert page.evaluate("() => window.__pwned") is None


RAW_NAME = "<img src=x onerror=window.__pwned=1> [abc123xyz00]"


@pytest.mark.parametrize("raw", [
    pytest.param(False, id="through-safe-component"),
    pytest.param(True, id="raw-markup-in-the-name", marks=pytest.mark.skipif(
        os.name == "nt", reason="Windows refuses < and > in file names")),
])
def test_a_hostile_file_name_shaped_like_a_youtube_title_shows_as_plain_text_and_runs_nothing(
        page, server, raw):
    # S26's "hostile file name or YouTube title", spec §6.3. A title reaches the app only as the
    # downloaded file's name (§6.7: safe_component(title) + " [id].mp4"), and Phase 3's
    # jobs_view names a job by its id, so a hostile name of that shape covers the title case.
    # safe_component turns < and > into _, so the raw name is the stricter case: markup in a
    # file name that something else put there.
    copy = demo_copy(server)
    name = RAW_NAME if raw else safe_component(RAW_NAME)
    if not raw:
        assert name == "_img src=x onerror=window.__pwned=1_ [abc123xyz00]"  # what it leaves
    for suffix in (".mp4", ".vid2sub.jsonl", ".en.srt", ".ja.srt"):
        shutil.copyfile(copy / f"jfk{suffix}", copy / f"{name}{suffix}")
    open_episode(page, copy / f"{name}.mp4")
    expect(page.get_by_test_id("episode-name")).to_have_text(f"{name}.mp4")
    assert page.locator("[data-testid=episode-name] *").count() == 0  # text only, no element
    assert page.locator("img[src=x]").count() == 0
    assert page.evaluate("() => window.__pwned") is None


def test_a_two_hour_episode_opens_in_under_a_second_with_only_the_rows_on_screen_in_the_page(
        page, server):
    # Review Focus 3: 2,000 cues, one every 3.6 s. The demo opens anything inside its copy.
    video = make_episode(demo_copy(server) / "long", n=2000)
    page.get_by_test_id("open-path").fill(str(video))
    began = time.monotonic()
    page.get_by_test_id("open-button").click()
    expect(page.get_by_test_id("cue-row").first).to_be_visible()
    elapsed = time.monotonic() - began
    assert elapsed < 1.0, f"{elapsed:.2f} s"  # about 0.25 s where it was built
    rows = page.get_by_test_id("cue-row")
    assert 5 < rows.count() < 60, rows.count()
    expect(rows.first).to_have_attribute("aria-setsize", "2000")
    page.get_by_test_id("cue-list").evaluate("e => { e.scrollTop = e.scrollHeight; }")
    expect(page.locator("[data-testid=cue-row][aria-posinset='2000']")).to_be_visible()
    assert rows.count() < 60


def test_rows_follow_playback_unless_that_is_turned_off(page, server):
    page.set_viewport_size({"width": 1280, "height": 460})  # too short for all four rows
    rows = open_episode(page, demo_copy(server) / "jfk.mp4")
    last = rows.nth(3)
    expect(last).not_to_be_in_viewport()
    seek(page, 10.0)
    expect(last).to_be_in_viewport()
    page.get_by_test_id("follow").uncheck()
    seek(page, 1.0)  # cue 1 is current now, but the list stays where it is
    expect(rows.first).to_have_attribute("aria-current", "true")
    expect(rows.first).not_to_be_in_viewport()
    page.get_by_test_id("follow").check()
    seek(page, 6.0)
    seek(page, 1.0)
    expect(rows.first).to_be_in_viewport()


def test_the_practice_aids_loop_the_current_cue_and_change_the_speed(page, server):
    open_episode(page, demo_copy(server) / "jfk.mp4")
    media = page.get_by_test_id("media")
    page.get_by_test_id("speed").select_option("0.75")
    assert media.evaluate("m => m.playbackRate") == 0.75
    seek(page, 3.9)  # inside cue 2, "occasion." (3.82 s to 4.653 s)
    page.get_by_test_id("loop").click()
    expect(page.get_by_test_id("loop")).to_have_attribute("aria-pressed", "true")
    page.get_by_test_id("speed").select_option("1.25")
    media.evaluate("m => { m.muted = true; return m.play(); }")
    page.wait_for_timeout(2500)  # three times the cue's length at 1.25×
    at = media.evaluate("m => m.currentTime")
    assert 3.8 <= at <= 4.75, at
    page.get_by_test_id("loop").click()
    expect(page.get_by_test_id("loop")).to_have_attribute("aria-pressed", "false")
    page.wait_for_function("() => document.querySelector('[data-testid=media]').currentTime > 5")


def test_every_control_of_the_view_is_reached_by_keyboard_with_its_focus_visible(page, server):
    # S37, spec §19.3: Tab reaches each control in order, and each shows where focus is.
    open_episode(page, demo_copy(server) / "jfk.mp4")
    page.get_by_test_id("open-path").focus()
    wanted = ["open-button", "media", "showing", "speed", "loop", "follow", "cue-list"]
    seen = []
    for _ in range(40):  # the video's own controls take several stops
        page.keyboard.press("Tab")
        found = page.evaluate("() => document.activeElement.dataset.testid || null")
        if found in wanted and found not in seen:
            seen.append(found)
            visible = page.evaluate("""() => {
                const s = getComputedStyle(document.activeElement);
                return document.activeElement.matches(':focus-visible')
                    && (s.outlineStyle !== 'none' && s.outlineWidth !== '0px'
                        || s.boxShadow !== 'none' || document.activeElement.tagName === 'VIDEO');
            }""")
            assert visible, f"{found} has no visible focus"
        if seen == wanted:
            break
    assert seen == wanted


def mpeg4_episode(server) -> Path:
    """MPEG-4 Part 2 video, which Chromium can't decode, with Opus sound, which it plays, in an
    MP4: both from ffmpeg's own encoders, so any ffmpeg makes it (tests/helpers.make_clip)."""
    return make_episode(demo_copy(server) / "mpeg4", name="Clip.mp4", audio_codec="libopus")


def media_urls(watch) -> list[str]:
    return list(dict.fromkeys(u for u in watch.requests if "/media/" in u))


def test_a_video_the_browser_cant_decode_plays_its_sound_through_the_playback_audio(
        page, server, watch):
    # Spec §8.2, §8.8: canPlayType says no before anything loads, so the page asks for the
    # playback audio and plays it with no picture. Make preview copy is Phase 3's (S63).
    assert page.evaluate("""() => document.createElement('video')
        .canPlayType('video/mp4; codecs="mp4v.20.9"')""") == ""
    open_episode(page, mpeg4_episode(server))
    expect(page.get_by_test_id("audio-only")).to_have_text(
        "Playing the sound only: this browser can't play the video itself.")
    media = page.get_by_test_id("media")
    assert media.evaluate("m => m.tagName") == "AUDIO"
    expect(media).to_have_attribute("src", re.compile(r"^/media/[A-Za-z0-9_-]{43}$"))
    media.evaluate("m => { m.muted = true; return m.play(); }")
    page.wait_for_function("() => document.querySelector('[data-testid=media]').currentTime > 0.3")
    assert len(media_urls(watch)) == 1  # the video itself was never loaded


def test_the_videos_own_signals_catch_what_canplaytype_misses(page, server, watch):
    # A browser that says yes to everything still drops the picture it can't decode, with no
    # error but no size: the page then asks for the playback audio, and the video's token goes.
    page.add_init_script(script="HTMLMediaElement.prototype.canPlayType = () => 'probably';")
    page.reload()
    open_episode(page, mpeg4_episode(server))
    expect(page.get_by_test_id("audio-only")).to_have_text(
        "Playing the sound only: this browser can't play the video itself.")
    expect(page.get_by_test_id("media")).to_have_attribute("src", re.compile("^/media/"))
    first, *rest = media_urls(watch)
    assert rest and page.request.get(first).status == 404  # the video's token was revoked


def test_a_video_error_falls_back_to_the_playback_audio_once(page, server, watch):
    # canPlayType says yes and Chromium refuses an AVI: MEDIA_ERR_SRC_NOT_SUPPORTED, the <video>
    # error path (Decision 15), which neither test above takes.
    page.add_init_script(script="HTMLMediaElement.prototype.canPlayType = () => 'probably';")
    page.reload()
    video = make_episode(demo_copy(server) / "avi", name="Clip.avi", audio_codec="libmp3lame")
    open_episode(page, video)
    expect(page.get_by_test_id("audio-only")).to_have_text(
        "Playing the sound only: this browser can't play the video itself.")
    assert page.get_by_test_id("media").evaluate("m => m.tagName") == "AUDIO"
    expect(page.get_by_test_id("media-error")).to_have_count(0)
    urls = media_urls(watch)
    assert len(urls) == 2, urls  # the video, then the playback audio: asked for once
    assert page.request.get(urls[0]).status == 404  # the video's token was revoked
    assert page.request.get(urls[1]).status == 200
