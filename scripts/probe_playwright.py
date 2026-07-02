"""Quick playwright probe of catalog listing."""
import asyncio
from playwright.async_api import async_playwright

URL = "https://www.shl.com/products/product-catalog/"


async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(URL, wait_until="networkidle", timeout=120_000)
        await page.wait_for_timeout(4000)
        print("title:", await page.title())
        links = await page.eval_on_selector_all(
            "a[href*='/products/product-catalog/view/']",
            "els => els.slice(0,15).map(e => ({href: e.href, text: e.innerText.trim()}))",
        )
        print("links:", len(links))
        for l in links[:10]:
            print(l)
        # dump visible text snippets
        text = await page.inner_text("body")
        for kw in ["Individual Test", "Job Solution", "OPQ", "Verify", "Filter"]:
            print(kw, text.lower().count(kw.lower()))
        await browser.close()


asyncio.run(main())
