"""Deep search of static HTML for product data."""
import json
import re
import urllib.request
from pathlib import Path

URL = "https://www.shl.com/products/product-catalog/"
req = urllib.request.Request(
    URL,
    headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    },
)
html = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", errors="replace")
out = Path(__file__).resolve().parents[1] / "data" / "raw_catalog.html"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(html, encoding="utf-8")
print("saved", out, len(html))

# JSON-like arrays with name/url patterns
for pat in [
    r'"name"\s*:\s*"[^"]{3,80}"',
    r'"slug"\s*:\s*"[^"]+"',
    r'"testType"\s*:\s*"[^"]+"',
    r'"url"\s*:\s*"[^"]*product-catalog[^"]*"',
]:
    hits = re.findall(pat, html)
    print(pat, len(hits))
    for h in hits[:8]:
        print(" ", h)

# large json blocks
for m in re.finditer(r"\{[^{}]{200,5000}\}", html):
    chunk = m.group(0)
    if "product" in chunk.lower() or "catalog" in chunk.lower():
        print("chunk:", chunk[:400])
        break

# search for contentful entries
idx = html.lower().find("contentful")
print("contentful idx", idx)
if idx >= 0:
    print(html[idx - 200 : idx + 400])
