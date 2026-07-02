"""Normalize raw SHL catalog exports into the in-app schema."""
from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "data" / "catalog.json"

# Fallback source when assignment zip is not available yet.
PUBLIC_MIRROR = (
    "https://raw.githubusercontent.com/Arshad-Shaik/"
    "shl-assessment-recommender-agent/main/data/shl_catalog.json"
)

TYPE_FROM_KEYS = [
    ("Knowledge & Skills", "K"),
    ("Personality & Behavior", "P"),
    ("Ability & Aptitude", "A"),
    ("Biodata & Situational Judgment", "S"),
    ("Simulations", "B"),
    ("Assessment Exercises", "B"),
    ("Development & 360", "D"),
    ("Competencies", "P"),
]

JOB_SOLUTION_RE = re.compile(r"\bsolution\b", re.I)


def infer_test_type(keys: list[str]) -> str:
    keyset = set(keys or [])
    for label, code in TYPE_FROM_KEYS:
        if label in keyset:
            return code
    return "K"


def is_individual_test(record: dict) -> bool:
    name = record.get("name", "")
    if JOB_SOLUTION_RE.search(name):
        return False
    link = record.get("link") or record.get("url") or ""
    if not link:
        return False
    return "/products/product-catalog/view/" in link


def normalize_record(raw: dict) -> dict | None:
    if not is_individual_test(raw):
        return None

    name = (raw.get("name") or "").strip()
    url = (raw.get("link") or raw.get("url") or "").strip()
    if not name or not url:
        return None

    description = (raw.get("description") or "").strip()
    keys = raw.get("keys") or []
    test_type = raw.get("test_type") or infer_test_type(keys)
    job_levels = raw.get("job_levels") or []
    languages = raw.get("languages") or []

    tokens = " ".join(
        [
            name,
            description,
            " ".join(keys),
            " ".join(job_levels),
            " ".join(languages),
        ]
    ).lower()

    return {
        "name": name,
        "url": url,
        "test_type": test_type,
        "description": description,
        "keys": keys,
        "job_levels": job_levels,
        "languages": languages,
        "search_blob": tokens,
    }


def load_source(path: Path | None) -> list[dict]:
    if path and path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    with urllib.request.urlopen(PUBLIC_MIRROR, timeout=90) as resp:
        return json.loads(resp.read().decode("utf-8"))


def build_catalog(source: Path | None = None, out: Path = DEFAULT_OUT) -> int:
    raw_items = load_source(source)
    cleaned: list[dict] = []
    seen_urls: set[str] = set()

    for item in raw_items:
        norm = normalize_record(item)
        if not norm or norm["url"] in seen_urls:
            continue
        seen_urls.add(norm["url"])
        cleaned.append(norm)

    cleaned.sort(key=lambda x: x["name"].lower())
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(cleaned, indent=2, ensure_ascii=False), encoding="utf-8")
    return len(cleaned)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build normalized SHL catalog JSON")
    parser.add_argument(
        "--source",
        type=Path,
        help="Path to raw catalog JSON (assignment export or scraper output)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help="Output path for normalized catalog",
    )
    args = parser.parse_args()
    count = build_catalog(args.source, args.out)
    print(f"Wrote {count} individual test records to {args.out}")
