"""Inspect a single product page for structured fields."""
import re
import urllib.request

SLUG = "opq32r"
URL = f"https://www.shl.com/products/product-catalog/view/{SLUG}/"
req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=60) as resp:
    html = resp.read().decode("utf-8", errors="replace")

for kw in ["test_type", "Test Type", "Individual Test", "Job Solution", "description", "product-catalog"]:
    print(kw, ":", html.lower().count(kw.lower()))

# title
m = re.search(r"<title>([^<]+)</title>", html, re.I)
print("title:", m.group(1) if m else None)

# meta description
m = re.search(r'name="description"\s+content="([^"]+)"', html, re.I)
print("meta:", (m.group(1)[:200] if m else None))

# h1
m = re.search(r"<h1[^>]*>([^<]+)", html, re.I)
print("h1:", m.group(1).strip() if m else None)

# json-ld
for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL):
    print("json-ld:", m.group(1)[:600])

# look for data attributes
for pat in [r'data-[^=]+="[^"]{5,80}"', r'"testType"\s*:\s*"[^"]+"', r'"productType"\s*:\s*"[^"]+"']:
    hits = re.findall(pat, html)
    if hits:
        print(pat, "->", hits[:5])
