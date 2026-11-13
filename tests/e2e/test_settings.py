"""The settings drawer in Chromium, against `vid2sub serve` with a vid2sub.toml whose endpoints
are fake servers on this machine (spec §19.2, §5.3, §5.4, §6.4; S35, S37): the native <dialog>
at the right edge, modal; endpoints and models read-only, with Test; a typed key only for the
endpoint that allows one, shown back only as "key entered for this session", sent only to that
endpoint, and kept nowhere in the page; the session's defaults, shared by every tab of the
launch; the cue rules read-only; Copy settings. Run with `make e2e`."""

import pytest
from fakes import FakeServer
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e

KEY = "k" * 40  # a typed key: low entropy, plainly not a real one


def models(req):
    if req.path.endswith("/models"):
        return 200, {"object": "list", "data": [
            {"id": "w", "object": "model", "created": 0, "owned_by": "test"},
            {"id": "g", "object": "model", "created": 0, "owned_by": "test"}]}, {}
    return 404, {}, {}


def toml(spark: str, lan: str) -> str:
    return f"""
[endpoints.spark]
base_url = "{spark}"

[endpoints.lan]
base_url = "{lan}"
allow_typed_key = true

[models.spark-turbo]
endpoint = "spark"
model = "w"
parser = "whisper.cpp"
local = true

[models.lan-gemma]
endpoint = "lan"
model = "g"
task = "translate"
"""


@pytest.fixture
def servers():
    with FakeServer(responder=models) as spark, FakeServer(responder=models) as lan:
        yield spark, lan


def open_settings(page):
    opener = page.get_by_test_id("open-settings")
    opener.click()
    dialog = page.locator("dialog[open]")
    expect(dialog).to_be_visible()
    return opener, dialog


def test_the_drawer_shows_the_toml_read_only_tests_endpoints_and_takes_a_typed_key(
        launch, open_page, servers, tmp_path, context):
    spark, lan = servers
    server = launch(tmp_path / "server", toml=toml(spark.url, lan.url))
    watched = open_page(server)
    page = watched.page
    opener, dialog = open_settings(page)
    # Decision 13: the native <dialog>, modal, at the right edge, focus inside
    assert dialog.evaluate("d => d.matches(':modal') && d.dataset.side === 'right'")
    assert dialog.evaluate("d => d.contains(document.activeElement)")
    expect(page.get_by_test_id("endpoint-spark")).to_contain_text(spark.url)
    expect(page.get_by_test_id("settings-models")).to_contain_text("lan-gemma: translates on lan")
    # nothing of vid2sub.toml can be changed here: lan's key box is the only text field
    assert dialog.locator("input:not([type=checkbox])").count() == 1
    page.get_by_test_id("test-spark").click()
    expect(page.get_by_test_id("test-result-spark")).to_have_text("Answers, serving w, g")
    # §5.3: a typed key, only where vid2sub.toml allows one
    expect(page.get_by_test_id("key-lan")).to_have_text(
        "no key yet: type one below to use it this session")
    box = page.get_by_test_id("typed-key-lan")
    expect(box).to_have_attribute("type", "password")
    expect(box).to_have_attribute("autocomplete", "off")
    box.fill(KEY)
    page.get_by_test_id("use-key-lan").click()
    expect(box).to_have_value("")
    expect(page.get_by_test_id("key-lan")).to_have_text("key entered for this session")
    # kept nowhere in the page: not in Shiny's or shinyreact's copy of the input, the markup or
    # the browser's storage (the page sends null straight after the key)
    page.wait_for_function("""() => {
        const v = window.Shiny.shinyapp.$inputValues["typed_key:shinyreact.default"];
        return v === null;
    }""")
    found = page.evaluate("""key => [JSON.stringify(window.Shiny.shinyapp.$inputValues),
        document.documentElement.outerHTML, JSON.stringify(localStorage),
        JSON.stringify(sessionStorage)].some((s) => s.includes(key))""", KEY)
    assert found is False
    page.get_by_test_id("test-lan").click()
    expect(page.get_by_test_id("test-result-lan")).to_have_text("Answers, serving w, g")
    # §6.4: the key goes only to the origin its endpoint declared
    assert [r.headers.get("authorization") for r in lan.requests] == [f"Bearer {KEY}"]
    assert all(KEY not in str(r.headers) for r in spark.requests)
    page.keyboard.press("Escape")
    expect(dialog).to_have_count(0)
    expect(opener).to_be_focused()
    expect(page.get_by_test_id("status")).to_contain_text("lan: cloud, key set")
    assert watched.errors == [] and watched.violations() == []


def test_the_sessions_defaults_reach_every_tab_and_copy_settings_holds_them(
        launch, open_page, servers, tmp_path, context):
    spark, lan = servers
    server = launch(tmp_path / "server", toml=toml(spark.url, lan.url))
    context.grant_permissions(["clipboard-read", "clipboard-write"], origin=server.url)
    first = open_page(server)
    a = first.page
    open_settings(a)
    expect(a.get_by_test_id("target-en")).to_be_checked()
    expect(a.get_by_test_id("target-en")).to_be_disabled()  # the last target can't go
    # the boxes show the engine's session, so each changes once the engine has the change
    a.get_by_test_id("target-ja").click()
    expect(a.get_by_test_id("target-ja")).to_be_checked()
    a.get_by_test_id("default-ass").click()
    expect(a.get_by_test_id("default-ass")).to_be_checked()
    text = a.get_by_test_id("settings-toml")
    expect(text).to_contain_text('targets = ["en", "ja"]')
    expect(text).to_contain_text('formats = ["srt", "ass"]')
    a.get_by_test_id("copy-settings").click()
    expect(a.get_by_role("status").filter(has_text="Copied")).to_have_count(1)
    assert a.evaluate("() => navigator.clipboard.readText()") == text.inner_text()
    expect(a.get_by_test_id("settings-rules")).to_contain_text("English")
    expect(a.get_by_test_id("settings")).to_contain_text("Cue rules can't be changed yet.")
    assert a.get_by_test_id("settings-rules").locator("input").count() == 0
    second = open_page(server)  # another tab of the same launch
    b = second.page
    open_settings(b)
    expect(b.get_by_test_id("target-ja")).to_be_checked()
    expect(b.get_by_test_id("default-ass")).to_be_checked()
    for watched in (first, second):
        assert watched.errors == [] and watched.violations() == []
