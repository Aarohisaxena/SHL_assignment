"""Scrape SHL Individual Test Solutions from the product catalog."""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from urllib.parse import urljoin

from playwright.async_api import async_playwright

CATALOG_URL = "https://www.shl.com/products/product-catalog/"
BASE = "https://www.shl.com"
OUTPUT = Path(__file__).resolve().parents[1] / "data" / "catalog.json"

# SHL test type codes used in evaluator responses
TYPE_LABELS = {
    "A": "Ability & Aptitude",
    "K": "Knowledge & Skills",
    "P": "Personality & Behavior",
    "S": "Situational Judgment",
    "B": "Behavioral Simulation",
    "D": "Development",
}


def normalize_type(raw: str) -> str | None:
    if not raw:
        return None
    raw = raw.strip().upper()
    if raw in TYPE_LABELS:
        return raw
    for code, label in TYPE_LABELS.items():
        if label.lower() in raw.lower():
            return code
    mapping = {
        "ability": "A",
        "aptitude": "A",
        "knowledge": "K",
        "skill": "K",
        "personality": "P",
        "behavior": "P",
        "behaviour": "P",
        "situational": "S",
        "simulation": "B",
        "development": "D",
    }
    lower = raw.lower()
    for key, code in mapping.items():
        if key in lower:
            return code
    return None


async def scrape_catalog() -> list[dict]:
    items: list[dict] = []
    seen_urls: set[str] = set()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(CATALOG_URL, wait_until="networkidle", timeout=120_000)
        await page.wait_for_timeout(3000)

        # Collect product links from listing
        links = await page.eval_on_selector_all(
            "a[href*='/products/product-catalog/view/']",
            "els => els.map(e => ({href: e.href, text: (e.innerText||'').trim()}))",
        )
        product_urls: list[tuple[str, str]] = []
        for link in links:
            href = link.get("href", "")
            if not href or href in seen_urls:
                continue
            seen_urls.add(href)
            product_urls.append((href, link.get("text", "")))

        print(f"Found {len(product_urls)} product links on listing page")

        # If listing is empty, try filter for Individual Test Solutions
        if not product_urls:
            filters = await page.query_selector_all("button, label, input, [role='tab']")
            for el in filters:
                txt = (await el.inner_text()) if hasattr(el, "inner_text") else ""
                if "individual" in txt.lower():
                    await el.click()
                    await page.wait_for_timeout(2000)
                    break
            links = await page.eval_on_selector_all(
                "a[href*='/products/product-catalog/view/']",
                "els => els.map(e => ({href: e.href, text: (e.innerText||'').trim()}))",
            )
            for link in links:
                href = link.get("href", "")
                if href and href not in seen_urls:
                    seen_urls.add(href)
                    product_urls.append((href, link.get("text", "")))
            print(f"After filter: {len(product_urls)} links")

        for idx, (url, list_name) in enumerate(product_urls):
            try:
                detail = await browser.new_page()
                await detail.goto(url, wait_until="networkidle", timeout=90_000)
                await detail.wait_for_timeout(1500)

                body_text = await detail.inner_text("body")
                title = await detail.title()
                h1_el = await detail.query_selector("h1")
                h1 = (await h1_el.inner_text()).strip() if h1_el else list_name

                # Skip pre-packaged job solutions when labeled on page
                if re.search(r"job solution", body_text, re.I):
                    await detail.close()
                    continue

                name = h1 or list_name or title.split("|")[0].strip()
                if name.lower() in {"shl products", "our products", "products"}:
                    await detail.close()
                    continue

                # Extract test type from page
                test_type = None
                type_match = re.search(
                    r"(Ability\s*&\s*Aptitude|Knowledge\s*&\s*Skills|Personality\s*&\s*Behavior|"
                    r"Situational\s*Judgment|Behavioral\s*Simulation|Development)",
                    body_text,
                    re.I,
                )
                if type_match:
                    test_type = normalize_type(type_match.group(1))

                # Description: first substantial paragraph near product header
                desc = ""
                paras = await detail.eval_on_selector_all(
                    "main p, article p, .product-description p, p",
                    "els => els.map(e => e.innerText.trim()).filter(t => t.length > 40)",
                )
                if paras:
                    desc = paras[0][:1200]

                slug = url.rstrip("/").split("/")[-1]
                record = {
                    "name": name,
                    "url": url if url.startswith("http") else urljoin(BASE, url),
                    "slug": slug,
                    "test_type": test_type or "K",
                    "description": desc,
                    "search_text": f"{name} {desc} {test_type or ''}".lower(),
                }
                items.append(record)
                await detail.close()
                if (idx + 1) % 10 == 0:
                    print(f"  scraped {idx + 1}/{len(product_urls)}")
            except Exception as exc:
                print(f"  skip {url}: {exc}")

        await browser.close()

    return items


def main() -> None:
    items = asyncio.run(scrape_catalog())
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(items)} items to {OUTPUT}")


if __name__ == "__main__":
    main()
