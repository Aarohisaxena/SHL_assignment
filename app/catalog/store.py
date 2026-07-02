from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from app.config import get_settings


@dataclass(frozen=True)
class CatalogItem:
    name: str
    url: str
    test_type: str
    description: str
    keys: tuple[str, ...]
    job_levels: tuple[str, ...]
    search_blob: str

ASSESSMENT_ALIASES = {
    "opq": "opq32r",
    "opq32": "opq32r",
    "gsa": "general ability",
    "verify": "verify",
    "verify g+": "verify g+",
}

class CatalogStore:
    """In-memory catalog with fast lookup by name or URL slug."""

    def __init__(self, items: list[CatalogItem]) -> None:
        self._items = items
        self._by_url = {item.url.rstrip("/"): item for item in items}
        self._by_name = {self._norm_name(item.name): item for item in items}
        self._slug_map: dict[str, CatalogItem] = {}
        for item in items:
            slug = item.url.rstrip("/").split("/")[-1].lower()
            self._slug_map[slug] = item

    @staticmethod
    def _norm_name(name: str) -> str:
        return re.sub(r"\s+", " ", name.strip().lower())

    @classmethod
    def from_json(cls, path: Path) -> "CatalogStore":
        payload = json.loads(path.read_text(encoding="utf-8"))
        items: list[CatalogItem] = []
        for row in payload:
            items.append(
                CatalogItem(
                    name=row["name"],
                    url=row["url"],
                    test_type=row.get("test_type") or "K",
                    description=row.get("description") or "",
                    keys=tuple(row.get("keys") or []),
                    job_levels=tuple(row.get("job_levels") or []),
                    search_blob=row.get("search_blob") or row.get("description", "").lower(),
                )
            )
        return cls(items)

    @property
    def items(self) -> list[CatalogItem]:
        return self._items

    def __len__(self) -> int:
        return len(self._items)

    def get_by_url(self, url: str) -> CatalogItem | None:
        return self._by_url.get(url.rstrip("/"))

    def find_by_name_fragment(self, fragment: str) -> CatalogItem | None:
        needle = self._norm_name(fragment)
        if needle in ASSESSMENT_ALIASES:
            needle = self._norm_name(ASSESSMENT_ALIASES[needle])
        if needle in self._by_name:
            return self._by_name[needle]
        best = None
        best_score = -1
        for norm, item in self._by_name.items():
            if needle in norm or norm in needle:
                score = len(set(needle.split()) & set(norm.split()))
                if score > best_score:
                    best = item
                    best_score = score
        return best
        for slug, item in self._slug_map.items():
            if needle.replace(" ", "-") in slug or slug.replace("-", " ") in needle:
                return item
        return None

    def validate_recommendation(self, name: str, url: str, test_type: str) -> CatalogItem | None:
        item = self.get_by_url(url)
        if item is None:
            return None
        catalog_name = self._norm_name(item.name)
        model_name = self._norm_name(name)
        if catalog_name != model_name:
            if (model_name not in catalog_name and catalog_name not in model_name):
                return None
        if test_type and item.test_type != test_type:
            # Trust catalog type over model output
            pass
        return item


_store: CatalogStore | None = None


def get_catalog() -> CatalogStore:
    global _store
    if _store is None:
        settings = get_settings()
        if not settings.catalog_path.exists():
            raise FileNotFoundError(
                f"Catalog missing at {settings.catalog_path}. "
                "Run: python scripts/build_catalog.py"
            )
        _store = CatalogStore.from_json(settings.catalog_path)
    return _store
