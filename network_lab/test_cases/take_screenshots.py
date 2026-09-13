# -*- coding: utf-8 -*-
"""Logs into the REAL running app (http://localhost:8000) with the default
seed credentials and captures real screenshots of the pages the thesis
references. Read-only: never edits the live topology/devices."""
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent
BASE = "http://localhost:8000"


def shot(page, path, name, wait_ms=1200, full_page=True):
    page.goto(f"{BASE}{path}", wait_until="networkidle")
    page.wait_for_timeout(wait_ms)
    page.screenshot(path=str(OUT / name), full_page=full_page)
    print("saved", name)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        # ---- Login page (logged out) ----
        page.goto(f"{BASE}/login", wait_until="networkidle")
        page.wait_for_timeout(600)
        page.screenshot(path=str(OUT / "shot_login.png"))
        print("saved shot_login.png")

        # ---- log in with the default seed admin account ----
        page.fill('input[type="text"], input:not([type])', "")  # no-op safeguard
        page.fill("input >> nth=0", "admin")
        page.fill('input[type="password"]', "admin123")
        page.click('button[type="submit"], button.primary')
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)

        shot(page, "/", "shot_dashboard.png")
        shot(page, "/devices", "shot_devices.png")
        shot(page, "/topology", "shot_topology.png", wait_ms=2200)
        shot(page, "/smart-config", "shot_smart_config.png")
        shot(page, "/manual-config", "shot_manual_config.png")

        browser.close()


if __name__ == "__main__":
    main()
