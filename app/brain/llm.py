from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from app.config import Settings


class LLMClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client = OpenAI(
            api_key=settings.openai_api_key or "not-set",
            base_url=settings.openai_base_url,
        )

    @property
    def enabled(self) -> bool:
        return bool(self.settings.openai_api_key)

    def complete_json(
        self,
        system: str,
        user: str,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        if not self.enabled:
            return {}

        response = self._client.chat.completions.create(
            model=self.settings.openai_model,
            temperature=temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)

    def complete_text(
        self,
        system: str,
        user: str,
        temperature: float = 0.3,
    ) -> str:
        if not self.enabled:
            return ""

        response = self._client.chat.completions.create(
            model=self.settings.openai_model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return (response.choices[0].message.content or "").strip()
