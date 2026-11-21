"""Browser checks: the site loads with the committed data, without errors, in light and dark."""

from __future__ import annotations

import functools
import http.server
import os
import pathlib
import shutil
import threading

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = pathlib.Path(os.environ.get("ATLAS_TEST_DATA", ROOT / "data" / "wi-07"))
SAMPLE = bool(os.environ.get("ATLAS_TEST_SAMPLE"))

pytestmark = pytest.mark.skipif(not (DATA / "summary.json").exists(), reason="no data build yet")


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    web = tmp_path_factory.mktemp("web")
    shutil.copytree(ROOT / "site", web, dirs_exist_ok=True)
    shutil.copytree(DATA, web / "data", dirs_exist_ok=True)

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(web)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/"
    httpd.shutdown()


@pytest.fixture(scope="module")
def browser():
    pw = pytest.importorskip("playwright.sync_api")
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception:
            b = p.chromium.launch(executable_path="/usr/bin/google-chrome")
        yield b
        b.close()


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_page_renders_without_errors(base, browser, scheme):
    page = browser.new_page(viewport={"width": 1366, "height": 900}, color_scheme=scheme)
    errors, missing = [], []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" and "Failed to load resource" not in m.text else None)
    # The tour video is optional; every other request must succeed.
    page.on("response", lambda r: missing.append(r.url) if r.status >= 400 and "/media/" not in r.url else None)
    page.goto(base)
    page.wait_for_timeout(2500)
    assert not errors, errors
    assert not missing, missing
    assert page.locator("#glance-grid .stat").count() >= 6
    assert page.locator("#map svg path.part").count() >= 20
    assert page.locator("#county-grid .county-card").count() >= 20
    assert page.locator("#checks li").count() >= 8
    assert page.locator("#sources li").count() >= 5
    if not SAMPLE:
        assert page.locator("#sample-banner").is_hidden()
    page.close()


def test_county_drawer_opens_and_closes(base, browser):
    page = browser.new_page(viewport={"width": 1366, "height": 900})
    page.goto(base)
    page.wait_for_timeout(1500)
    page.locator("#county-grid .county-card").first.click()
    page.wait_for_timeout(700)
    assert "open" in (page.locator("#drawer").get_attribute("class") or "")
    assert "County" in page.locator("#drawer-title").inner_text()
    page.keyboard.press("Escape")
    page.wait_for_timeout(600)
    assert "open" not in (page.locator("#drawer").get_attribute("class") or "")
    page.close()


def test_mobile_layout_has_no_horizontal_scroll(base, browser):
    page = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    page.goto(base)
    page.wait_for_timeout(1500)
    overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    assert overflow <= 1, f"page is {overflow}px wider than the screen"
    page.close()
