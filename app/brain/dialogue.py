from __future__ import annotations

import json
from dataclasses import asdict

from app.brain.guards import off_topic_reason
from app.brain.llm import LLMClient
from app.brain.signals import extract_context, should_clarify
from app.catalog.search import CatalogSearcher, HiringContext, SearchHit
from app.catalog.store import CatalogItem, CatalogStore, get_catalog
from app.config import Settings
from app.models import ChatMessage, ChatResponse, Recommendation


class DialogueManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.catalog: CatalogStore = get_catalog()
        self.searcher = CatalogSearcher(self.catalog)
        self.llm = LLMClient(settings)

    def respond(self, messages: list[ChatMessage]) -> ChatResponse:
        last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")

        refusal = off_topic_reason(last_user)
        if refusal:
            return ChatResponse(reply=refusal, recommendations=[], end_of_conversation=False)

        ctx = extract_context(messages)

        if ctx.compare_targets:
            return self._handle_compare(messages, ctx)

        if should_clarify(messages, ctx):
            return self._handle_clarify(messages, ctx)

        hits = self.searcher.search(
            query=ctx.raw_text,
            limit=self.settings.retrieval_pool,
            context=ctx,
        )
        return self._handle_recommend(messages, ctx, hits)

    def _handle_clarify(self, messages: list[ChatMessage], ctx: HiringContext) -> ChatResponse:
        if self.llm.enabled:
            system = (
    "You are an SHL Individual Test Solutions recommendation assistant.\n"
    "Recommend ONLY from the supplied candidates.\n"
    "Never invent assessment names.\n"
    "Never modify assessment URLs.\n"
    "Never recommend assessments outside the candidate list.\n"
    "If the user's request changes, update the recommendations instead of restarting.\n"
    "Prefer the smallest high-confidence shortlist (1–10 items).\n"
    "Return valid JSON:\n"
    "{\"reply\":\"...\",\"recommendations\":[{\"name\":\"...\",\"url\":\"...\",\"test_type\":\"...\"}]}"
)
            
            payload = self.llm.complete_json(
                system=system,
                user=json.dumps({"conversation": [m.model_dump() for m in messages], "signals": asdict(ctx)}),
            )
            reply = payload.get("reply") or self._fallback_clarify(ctx)
        else:
            reply = self._fallback_clarify(ctx)

        return ChatResponse(reply=reply, recommendations=[], end_of_conversation=False)

    @staticmethod
    def _fallback_clarify(ctx: HiringContext) -> str:
        if not ctx.role:
            return "Happy to help. What role are you hiring for, and is there a seniority level?"
        if not ctx.seniority:
            return f"Got it — a {ctx.role} role. What seniority level should the assessment target?"
        return "What should we prioritize measuring: technical skills, personality fit, or cognitive ability?"

    def _handle_compare(self, messages: list[ChatMessage], ctx: HiringContext) -> ChatResponse:
        left = self.catalog.find_by_name_fragment(ctx.compare_targets[0])
        right = self.catalog.find_by_name_fragment(ctx.compare_targets[1])

        if not left or not right:
            missing = []
            if not left:
                missing.append(ctx.compare_targets[0])
            if not right:
                missing.append(ctx.compare_targets[1])
            return ChatResponse(
                reply=(
                    "I could not find those exact catalog items: "
                    + ", ".join(missing)
                    + ". Please use assessment names from the SHL catalog."
                ),
                recommendations=[],
                end_of_conversation=False,
            )

        if self.llm.enabled:
            system = (
    "Compare ONLY the information provided for these two SHL assessments.\n"
    "Do not use outside knowledge.\n"
    "If a feature is not present in the provided data, explicitly say it is not specified.\n"
    "Mention:\n"
    "- assessment purpose\n"
    "- test type\n"
    "- job level (if available)\n"
    "- key differences\n"
    "Return JSON: {\"reply\":\"...\"}"
)
            facts = {
                "left": self._item_facts(left),
                "right": self._item_facts(right),
            }
            payload = self.llm.complete_json(system=system, user=json.dumps(facts))
            reply = payload.get("reply") or self._fallback_compare(left, right)
        else:
            reply = self._fallback_compare(left, right)

        return ChatResponse(reply=reply, recommendations=[], end_of_conversation=False)

    @staticmethod
    def _item_facts(item: CatalogItem) -> dict:
        return {
            "name": item.name,
            "url": item.url,
            "test_type": item.test_type,
            "description": item.description[:900],
            "categories": list(item.keys),
            "job_levels": list(item.job_levels),
        }

    @staticmethod
    def _fallback_compare(a: CatalogItem, b: CatalogItem) -> str:
        return (
            f"{a.name} ({a.test_type}) focuses on: {a.description[:220]}… "
            f"Whereas {b.name} ({b.test_type}) focuses on: {b.description[:220]}…"
        )

    def _handle_recommend(
        self,
        messages: list[ChatMessage],
        ctx: HiringContext,
        hits: list[SearchHit],
    ) -> ChatResponse:
        candidates = [self._item_facts(h.item) for h in hits[: self.settings.retrieval_pool]]
        max_items = min(self.settings.shortlist_max, 10)

        if self.llm.enabled:
            system = (
                "You recommend SHL Individual Test Solutions. Pick 1-10 items ONLY from candidates. "
                "Every name and url must match a candidate exactly. "
                "Return JSON: {\"reply\": \"...\", \"recommendations\": [{\"name\",\"url\",\"test_type\"}]}"
            )
            user_payload = {
                "conversation": [m.model_dump() for m in messages],
                "signals": asdict(ctx),
                "candidates": candidates,
                "max_items": max_items,
            }
            payload = self.llm.complete_json(system=system, user=json.dumps(user_payload))
            reply = payload.get("reply") or "Here are SHL assessments that match your needs."
            raw_recs = payload.get("recommendations") or []
        else:
            reply = "Here are SHL assessments that match your needs."
            raw_recs = [
                {"name": h.item.name, "url": h.item.url, "test_type": h.item.test_type}
                for h in hits[:max_items]
            ]

        validated = self._validate_recommendations(raw_recs)
        if not validated:
            validated = self._validate_recommendations(
                [{"name": h.item.name, "url": h.item.url, "test_type": h.item.test_type} for h in hits[:max_items]]
            )

        conversation_done = len(validated) > 0

        return ChatResponse(
    reply=reply,
    recommendations=validated,
    end_of_conversation=conversation_done,
)

    def _validate_recommendations(self, raw: list[dict]) -> list[Recommendation]:
        out: list[Recommendation] = []
        seen: set[str] = set()
        for row in raw:
            name = str(row.get("name", "")).strip()
            url = str(row.get("url", "")).strip()
            test_type = str(row.get("test_type", "")).strip() or "K"
            if not name or not url:
                continue
            item = self.catalog.validate_recommendation(name, url, test_type)
            if item is None:
                continue
            key = item.url.rstrip("/")
            if key in seen:
                continue
            seen.add(key)
            out.append(
                Recommendation(name=item.name, url=item.url, test_type=item.test_type)
            )
            if len(out) >= 10:
                break
        return out