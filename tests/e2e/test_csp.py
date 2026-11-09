"""In Chromium, the engine's page runs under the spec's CSP with no violation and no console
error, the CSP blocks inline scripts, eval and inline styles, nothing leaves the engine's own
origin, and a tab whose engine restarted says to open the new link instead of reconnecting
(spec §6.3, §29; S26; Review Focus 5). Run with `make e2e`."""

import time

import pytest
from playwright.sync_api import expect

from vid2sub.web.auth import SIGN_IN_AGAIN
from vid2sub.web.guards import CSP

pytestmark = pytest.mark.e2e


def test_the_page_loads_with_no_csp_violation_or_console_error(page, server, watch):
    expect(page.get_by_test_id("engine")).to_have_text("Local engine")
    for theme in ("dark", "light", "system"):  # Radix's toggle group, and the theme classes
        page.get_by_test_id(f"theme-{theme}").click()
    assert page.evaluate("() => document.documentElement.classList.contains('light')")
    assert page.request.get(f"{server.url}/").headers["content-security-policy"] == CSP
    # Shiny's busy indicators still switch on, from the file that replaced the inline script.
    assert page.evaluate("() => document.documentElement.dataset.shinyBusyPulse") == "true"
    # The fonts are the engine's own (spec §19.3).
    loaded = page.evaluate("""async () => {
        await document.fonts.ready;
        return document.fonts.check('16px "Atkinson Hyperlegible"');
    }""")
    assert loaded
    assert watch.errors == [] and watch.violations() == []


def test_the_csp_blocks_an_inline_script_eval_and_inline_styles(page, watch):
    ran = page.evaluate("""() => {
        const s = document.createElement("script");
        s.textContent = "window.__ran = true";
        document.body.append(s);
        return window.__ran === true;
    }""")
    assert ran is False
    # eval here only proves the CSP refuses it ('unsafe-eval' is never allowed, spec §6.3). It
    # runs from a real click: code Playwright evaluates itself is exempt from the CSP's eval rule.
    page.evaluate("""() => {
        window.__eval = "not run";
        document.querySelector("main").addEventListener("click", () => {
            try { window.__eval = String(eval("1 + 1")); } catch (e) { window.__eval = e.name; }
        }, { once: true });
    }""")
    page.get_by_test_id("main").click()
    assert page.evaluate("() => window.__eval") == "EvalError"
    styled = page.evaluate("""() => {
        const style = document.createElement("style");
        style.textContent = "main { color: rgb(1, 2, 3) }";
        document.head.append(style);
        const main = document.querySelector("main");
        main.setAttribute("style", "background-color: rgb(4, 5, 6)");
        const seen = getComputedStyle(main);
        return [seen.color, seen.backgroundColor];
    }""")
    assert "rgb(1, 2, 3)" not in styled and "rgb(4, 5, 6)" not in styled
    # The browser reports each violation as a task of its own, and logs the three inline ones.
    deadline = time.monotonic() + 5
    while (len(watch.violations()) < 4 or len(watch.errors) < 3) and time.monotonic() < deadline:
        page.wait_for_timeout(50)
    assert sorted(v.split()[0] for v in watch.violations()) == [
        "script-src", "script-src-elem", "style-src-attr", "style-src-elem"]
    watch.clear()  # the violations were the point


def test_nothing_leaves_the_engines_own_origin(page, server, watch):
    page.get_by_test_id("theme-dark").click()
    assert watch.requests, "no request was seen"
    assert [u for u in watch.requests if not u.startswith(f"{server.url}/")] == []


def test_a_restarted_engine_tells_the_page_to_open_the_new_link_and_it_never_reconnects(
        open_page, server, launch, tmp_path):
    # Review Focus 5. A refused websocket reaches the browser as an HTTP 403 (close code 1006),
    # so the page asks the engine for "/" once when Shiny says the socket closed.
    watch = open_page(server)
    page = watch.page
    expect(page.get_by_test_id("engine")).to_have_text("Local engine")
    opened = []  # websockets opened after the first
    page.on("websocket", lambda ws: opened.append(ws.url))
    server.stop()
    lost = page.get_by_test_id("lost")
    expect(lost).to_contain_text("vid2sub isn't running")
    launch(tmp_path / "again", port=server.port)  # a new launch, so a new token
    page.wait_for_timeout(2000)  # long enough for any reconnect Shiny might try
    page.get_by_test_id("check-again").click()
    expect(lost).to_contain_text(f"vid2sub was restarted, so this page is signed out: "
                                 f"{SIGN_IN_AGAIN}.")
    assert opened == []  # it never reconnected
    page.reload()  # the old cookie is refused by the new launch
    expect(page.locator("body")).to_have_text(SIGN_IN_AGAIN)
    # A closed socket, a refused fetch and a 401 are logged; a CSP violation never is.
    assert [e for e in watch.errors if "Content Security Policy" in e] == []
