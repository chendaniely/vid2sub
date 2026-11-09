"""The shell in Chromium, against `vid2sub serve --demo` and a hostile vid2sub.toml: the top bar
says this is the local engine, every hostile name shows as plain text, and nothing it carries
runs (spec §6.3, §19.2; S26). Run with `make e2e`."""

import json
from pathlib import Path

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e

HOSTILE = Path(__file__).parents[1] / "fixtures" / "hostile"
NAMES = json.loads((HOSTILE / "names.json").read_text(encoding="utf-8"))["names"]


def test_the_demo_is_the_local_engine_with_nothing_configured(page):
    expect(page.get_by_test_id("engine")).to_have_text("Local engine")
    expect(page.get_by_test_id("endpoint")).to_have_count(0)  # the demo reads no vid2sub.toml
    expect(page.get_by_text("ffmpeg missing")).to_have_count(0)


def test_hostile_names_show_as_plain_text_and_run_nothing(open_page, launch, tmp_path):
    toml = "".join(f"[endpoints.{json.dumps(name, ensure_ascii=False)}]\n"
                   'base_url = "http://127.0.0.1:9/v1"\n' for name in NAMES)
    watch = open_page(launch(tmp_path / "hostile", toml=toml))
    page = watch.page
    shown = page.get_by_test_id("endpoint")
    expect(shown).to_have_count(len(NAMES))
    assert shown.all_inner_texts() == [f"{name}: cloud" for name in NAMES]
    assert page.locator("[data-testid=endpoint] *").count() == 0  # text only, no element
    assert page.evaluate("() => window.__pwned") is None
    assert watch.errors == [] and watch.violations() == []
