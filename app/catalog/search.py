from __future__ import annotations

import re
from dataclasses import dataclass, field

from rank_bm25 import BM25Okapi

from app.catalog.store import CatalogItem, CatalogStore


TOKEN_RE = re.compile(r"[a-z0-9+#]+")


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


@dataclass
class SearchHit:
    item: CatalogItem
    score: float


@dataclass
class HiringContext:
    role: str = ""
    seniority: str = ""
    skills: list[str] = field(default_factory=list)
    wants_personality: bool = False
    wants_cognitive: bool = False
    wants_technical: bool = False
    wants_sjt: bool = False
    wants_simulation: bool = False
    exclude_terms: list[str] = field(default_factory=list)
    pasted_jd: bool = False
    compare_targets: list[str] = field(default_factory=list)
    raw_text: str = ""


class CatalogSearcher:
    def __init__(self, store: CatalogStore) -> None:
        self.store = store
        self._corpus = [tokenize(item.search_blob + " " + item.name) for item in store.items]
        self._bm25 = BM25Okapi(self._corpus)

    def search(self, query: str, limit: int = 30, context: HiringContext | None = None) -> list[SearchHit]:
        ctx = context or HiringContext()
        tokens = tokenize(query)
        if not tokens:
            return []

        scores = self._bm25.get_scores(tokens)
        hits: list[SearchHit] = []
        for idx, base in enumerate(scores):
            item = self.store.items[idx]
            score = float(base)
            score += self._context_boost(item, ctx)
            if self._is_excluded(item, ctx):
                score -= 50.0
            hits.append(SearchHit(item=item, score=score))

        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:limit]

    def _context_boost(self, item: CatalogItem, ctx: HiringContext) -> float:
        boost = 0.0
        blob = item.search_blob

        for skill in ctx.skills:
            skill_lower = skill.lower()
            if skill_lower in blob or skill_lower in item.name.lower():
                boost += 4.0

        if ctx.role:
            role = ctx.role.lower()
            if role in blob or role in item.name.lower():
                boost += 3.0
        if ctx.wants_personality and item.test_type == "P":
            boost += 3.0
        if ctx.wants_cognitive and item.test_type == "A":
            boost += 3.0
        if ctx.wants_technical and item.test_type == "K":
            boost += 3.0
        if ctx.wants_sjt and item.test_type == "S":
            boost += 3.0
        if ctx.wants_simulation and item.test_type == "B":
            boost += 2.5

        if ctx.seniority:
            sen = ctx.seniority.lower()
            if any(
                sen == lvl.lower() or sen in lvl.lower() or lvl.lower() in sen
                for lvl in item.job_levels):
                    boost += 2.0

        return boost

    @staticmethod
    def _is_excluded(item: CatalogItem, ctx: HiringContext) -> bool:
        hay = (item.name + " " + item.search_blob).lower()
        for term in ctx.exclude_terms:
            t = term.lower()
            if t and t in hay:
                return True
        return False
