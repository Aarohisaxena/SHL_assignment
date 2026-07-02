"""Replay public conversation traces and compute Recall@10."""
from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TRACE_DIR = ROOT / "data" / "traces"


def parse_trace_markdown(path: Path) -> dict:
    content = path.read_text(encoding="utf-8")
    user_messages: list[str] = []
    for match in re.finditer(r"\*\*User\*\*\s*\n\s*\n\s*>\s*(.+?)(?:\n\n|\Z)", content, re.S):
        msg = re.sub(r"\n>\s*", "\n", match.group(1).strip())
        user_messages.append(msg)

    tables = list(
        re.finditer(r"\|\s*#\s*\|.*?\n\|[-\s|]+\n((?:\|.*\n?)+)", content, re.M)
    )
    expected_urls: list[str] = []
    expected_names: list[str] = []
    if tables:
        last = tables[-1].group(0)
        for row in re.finditer(r"\|\s*\d+\s*\|\s*(.+?)\s*\|.*?\|\s*<?(https://[^>|\s]+)>?\s*\|", last):
            expected_names.append(row.group(1).strip())
            expected_urls.append(row.group(2).strip())

    return {
        "file": path.name,
        "user_messages": user_messages,
        "expected_names": expected_names,
        "expected_urls": expected_urls,
    }


def recall_at_k(recommended: list[str], expected: list[str], k: int = 10) -> float:
    if not expected:
        return 1.0
    rec_set = set(u.rstrip("/") for u in recommended[:k])
    exp_set = set(u.rstrip("/") for u in expected)
    return len(rec_set & exp_set) / len(exp_set)

def precision_at_k(recommended: list[str], expected: list[str], k: int = 10) -> float:
    if not recommended:
        return 0.0

    rec_set = set(u.rstrip("/") for u in recommended[:k])
    exp_set = set(u.rstrip("/") for u in expected)

    return len(rec_set & exp_set) / len(rec_set)

async def replay(trace: dict, base_url: str, max_turns: int = 8) -> dict:
    messages: list[dict] = []
    final_recs: list[dict] = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        for user_msg in trace["user_messages"]:
            if len(messages) >= max_turns:
                break
            messages.append({"role": "user", "content": user_msg})
            resp = await client.post(f"{base_url.rstrip('/')}/chat", json={"messages": messages})
            schema_valid = True
            resp.raise_for_status()
            data = resp.json()
            required = {
                "reply",
                "recommendations",
                "end_of_conversation",
            }
            missing_keys = required - data.keys()
            if missing_keys:
                schema_valid = False
                raise RuntimeError(f"Response missing keys: {missing_keys}")
            messages.append({"role": "assistant", "content": data["reply"]})
            if data["recommendations"]:
                if not (1 <= len(data["recommendations"]) <= 10):
                    raise RuntimeError(f"Invalid recommendation count: {len(data['recommendations'])}")
                final_recs = data["recommendations"]
                break

    urls = [r["url"] for r in final_recs]
    grounded = all(
    url.startswith("https://www.shl.com")
    for url in urls)
    names = [r["name"] for r in final_recs]
    expected = set(trace["expected_urls"])
    recommended = set(urls)
    missing = expected - recommended
    extra = recommended - expected
    recall = recall_at_k(urls, trace["expected_urls"])
    precision = precision_at_k(urls, trace["expected_urls"])
    return {
        "file": trace["file"],
        "recall_at_10": recall,
        "precision_at_10": precision,
        "grounded": grounded,
        "recommended_names": names,
        "missing": list(missing),
        "extra": list(extra),
        "expected_names": trace["expected_names"],
        "turns": len(messages),
        "schema_valid": schema_valid,
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    if not TRACE_DIR.exists():
        print(f"Place assignment trace markdown files in {TRACE_DIR}")
        return

    traces = [parse_trace_markdown(p) for p in sorted(TRACE_DIR.glob("*.md"))]
    if not traces:
        print("No .md trace files found.")
        return

    results = await asyncio.gather(*[replay(t, args.api) for t in traces])
    grounded_count = sum(1 for r in results if r["grounded"])
    recall_scores = [r["recall_at_10"] for r in results]
    precision_scores = [r["precision_at_10"] for r in results]
    print(f"Grounded Responses : "f"{grounded_count}/{len(results)}")
    mean_recall = sum(recall_scores) / len(recall_scores)
    mean_precision = sum(precision_scores) / len(precision_scores)
    print(f"Mean Recall@10    : {mean_recall:.3f}")
    print(f"Mean Precision@10 : {mean_precision:.3f}")
    print(f"Total Traces      : {len(results)}")
    avg_turns = sum(r["turns"] for r in results) / len(results)
    print(f"Average Turns : {avg_turns:.2f}")
    for row in results:
        print("=" * 60)
        print(row["file"])
        print(f"Recall@10 : {row['recall_at_10']:.2f}")
        print(f"Turns      : {row['turns']}")
        if row["missing"]:
            print("Missing:")
            for m in row["missing"]:
                print("   ", m)
        if row["extra"]:
            print("Extra:")
            for e in row["extra"]:
                print("   ", e)
        schema_ok = sum(1 for r in results if r["schema_valid"])
        print(f"Schema Compliance : "f"{schema_ok}/{len(results)}")
if __name__ == "__main__":
    asyncio.run(main())
