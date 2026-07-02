"""One-off probe script to discover SHL catalog structure."""
import re
import urllib.request

URL = "https://www.shl.com/products/product-catalog/"
req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=60) as resp:
    html = resp.read().decode("utf-8", errors="replace")

print("html length:", len(html))
paths = sorted(set(re.findall(r"/products/product-catalog/[^\s\"'<>]+", html)))
print("catalog paths:", len(paths))
for p in paths[:40]:
    print(p)

apis = sorted(set(re.findall(r"https?://[^\\s\"'<>]+api[^\\s\"'<>]*", html, re.I)))
print("api urls:", len(apis))
for u in apis[:20]:
    print(u)
