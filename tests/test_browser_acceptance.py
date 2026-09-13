import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

import pytest
from alembic import command
from alembic.config import Config
from playwright.sync_api import Error as PlaywrightError, sync_playwright

from local_ai_notes.cli import create_owner
from local_ai_notes.db import database_engine


ROOT = Path(__file__).resolve().parents[1]


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
def live_app(tmp_path, monkeypatch):
    database = tmp_path / "browser.db"
    url = f"sqlite:///{database}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    engine = database_engine(url)
    create_owner(engine, "owner", "synthetic password")
    engine.dispose()

    port = _free_port()
    env = os.environ.copy()
    env["DATABASE_URL"] = url
    env["LOCAL_AI_NOTES_COOKIE_SECURE"] = "false"
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "local_ai_notes.main:create_app", "--factory",
         "--host", "127.0.0.1", "--port", str(port)],
        cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.time() + 15
        while time.time() < deadline:
            if process.poll() is not None:
                raise RuntimeError("test server exited before becoming ready")
            try:
                with urlopen(f"{base}/health/ready", timeout=1) as response:
                    if response.status == 200:
                        break
            except Exception:
                time.sleep(0.1)
        else:
            raise RuntimeError("test server did not become ready")
        yield base
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def _assert_basic_accessible_names(page):
    problems = page.evaluate("""
        () => {
          const unlabeled = [...document.querySelectorAll('input:not([type="hidden"]), textarea, select')]
            .filter(el => !(el.labels && el.labels.length) && !el.getAttribute('aria-label') && !el.getAttribute('aria-labelledby'))
            .map(el => `${el.tagName.toLowerCase()}#${el.id || ''}[name=${el.name || ''}]`);
          const unnamed = [...document.querySelectorAll('button, a[href]')]
            .filter(el => !(el.textContent || '').trim() && !el.getAttribute('aria-label') && !el.getAttribute('aria-labelledby'))
            .map(el => el.outerHTML.slice(0, 120));
          return {unlabeled, unnamed};
        }
    """)
    assert problems == {"unlabeled": [], "unnamed": []}


@pytest.mark.browser
def test_primary_browser_workflow_history_keyboard_and_phone_viewport(live_app):
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch()
        except PlaywrightError as error:
            pytest.skip(f"Chromium is not installed for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        try:
            page.goto(f"{live_app}/login")
            assert page.locator('input[name="username"]').evaluate("el => document.activeElement === el")
            _assert_basic_accessible_names(page)
            page.get_by_label("Username").fill("owner")
            page.get_by_label("Password").fill("synthetic password")
            page.get_by_role("button", name="Sign in").click()
            page.wait_for_url(f"{live_app}/app**")
            _assert_basic_accessible_names(page)

            page.get_by_label("New project").fill("Browser Project")
            page.get_by_role("button", name="Create project").click()
            page.wait_for_url(f"{live_app}/app?project=*")
            page.get_by_role("button", name="New note").click()
            page.wait_for_url(f"{live_app}/app?project=*&note=*")

            page.locator("#title").fill("Browser note")
            page.locator("#body").fill("# First\n\nfirst body")
            page.keyboard.press("Control+s")
            page.locator("#save-status").wait_for(state="visible")
            assert page.locator("#save-status").inner_text() == "Saved"

            page.locator("#body").fill("# Second\n\nsecond body")
            page.get_by_role("button", name="Save", exact=True).click()
            assert page.locator("#save-status").inner_text() == "Saved"

            page.reload()
            page.get_by_role("button", name="View").nth(1).wait_for()
            page.get_by_role("button", name="View").nth(1).click()
            viewer = page.locator("#revision-viewer")
            viewer.wait_for()
            assert "Viewing revision 2" in viewer.inner_text()
            assert "first body" in viewer.inner_text()
            assert viewer.evaluate("el => document.activeElement === el")

            page.get_by_role("button", name="Preview").click()
            page.locator("#preview").wait_for(state="visible")
            assert "Second" in page.locator("#preview").inner_text()

            page.locator("#title").fill("Browser note dirty")
            before = page.url
            page.get_by_role("link", name="Export Markdown").click()
            assert page.url == before
            assert page.locator("#save-status").inner_text() == "Save before exporting"
            page.keyboard.press("Control+s")
            assert page.locator("#save-status").inner_text() == "Saved"

            page.get_by_role("button", name="Move to trash").click()
            page.get_by_role("link", name="Trash").click()
            page.get_by_role("link", name="Browser note dirty").click()
            assert page.get_by_text("Trashed", exact=True).is_visible()
            page.get_by_role("button", name="Restore note").click()
            assert "note=" in page.url

            page.set_viewport_size({"width": 390, "height": 844})
            overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
            assert overflow is False
            _assert_basic_accessible_names(page)

            page.keyboard.press("Tab")
            assert page.evaluate("document.activeElement !== document.body")
        finally:
            browser.close()
