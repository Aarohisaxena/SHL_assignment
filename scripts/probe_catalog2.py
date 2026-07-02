"""Search HTML for embedded data sources."""
import re
import urllib.request

URL = "https://www.shl.com/products/product-catalog/"
req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=60) as resp:
    html = resp.read().decode("utf-8", errors="replace")

keywords = [
    "Individual Test",
    "Job Solution",
    "productCatalog",
    "product_catalog",
    "algolia",
    "contentful",
    "drupal",
    "view/",
    "testType",
    "OPQ",
    "Verify",
    "graphql",
    "wp-json",
    "umbraco",
]
for kw in keywords:
    count = html.lower().count(kw.lower())
    if count:
        print(f"{kw}: {count}")

# script src
scripts = re.findall(r'<script[^>]+src="([^"]+)"', html)
print("\nscript count:", len(scripts))
for s in scripts[:15]:
    print(s)

# inline script snippets mentioning product
for m in re.finditer(r"<script[^>]*>(.*?)</script>", html, re.DOTALL | re.I):
    body = m.group(1)
    if "product" in body.lower() and len(body) > 100:
        print("\n--- script snippet ---")
        print(body[:800])
