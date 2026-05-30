#!/usr/bin/env python3
"""Render informe HTML to PDF using Playwright."""
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = Path(__file__).parent
INPUT_HTML = BASE / "informe-pruebas-bot-paula.html"
OUTPUT_PDF = BASE / "informe-pruebas-bot-paula.pdf"

def generate_pdf():
    print(f"Generando PDF desde: {INPUT_HTML}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            device_scale_factor=2,
        )
        page = context.new_page()
        page.goto(f"file://{INPUT_HTML.resolve()}", wait_until='networkidle')
        page.wait_for_timeout(2000)

        page.pdf(
            path=str(OUTPUT_PDF),
            width='1920px',
            height='1080px',
            print_background=True,
            margin={'top': '0', 'bottom': '0', 'left': '0', 'right': '0'},
        )
        browser.close()
        
        size_kb = OUTPUT_PDF.stat().st_size / 1024
        print(f"PDF generado: {OUTPUT_PDF}")
        print(f"Tamano: {size_kb:.0f} KB")
        print(f"Paginas: 6 (horizontal landscape)")

if __name__ == "__main__":
    generate_pdf()
