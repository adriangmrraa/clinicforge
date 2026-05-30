#!/usr/bin/env python3
"""Render HTML presentation to PDF using Playwright."""
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = Path(__file__).parent
INPUT_HTML = BASE / "guia-pruebas-paula.html"
OUTPUT_PDF = BASE / "Guia de Pruebas - Agente Paula - Mayo 2026.pdf"


def generate_pdf():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            device_scale_factor=2,
        )
        page = context.new_page()
        page.goto(f"file://{INPUT_HTML.resolve()}", wait_until="networkidle")
        page.wait_for_timeout(2000)

        page.pdf(
            path=str(OUTPUT_PDF),
            width="1920px",
            height="1080px",
            landscape=False,
            print_background=True,
            margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
            prefer_css_page_size=True,
        )
        browser.close()
        print(f"Done: {OUTPUT_PDF}")


if __name__ == "__main__":
    generate_pdf()
