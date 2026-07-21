from __future__ import annotations

from django.conf import settings

from .base import AITextResponse


class OpenAIClient:
    name = "openai"

    def __init__(self) -> None:
        self.api_key = getattr(settings, "OPENAI_API_KEY", "").strip()
        self.model = getattr(settings, "OPENAI_TEXT_MODEL", "gpt-4.1-mini")

    @property
    def enabled(self) -> bool:
        return bool(getattr(settings, "AI_ENABLE_OPENAI", False) and self.api_key)

    def generate(self, *, instructions: str, input_text: str) -> AITextResponse:
        if not self.enabled:
            raise RuntimeError("OpenAI provider is disabled or not configured.")

        from openai import OpenAI

        response = OpenAI(api_key=self.api_key).responses.create(
            model=self.model,
            instructions=instructions,
            input=input_text,
        )
        text = (response.output_text or "").strip()
        if not text:
            raise RuntimeError("OpenAI returned an empty response.")
        return AITextResponse(
            text=text,
            provider=self.name,
            response_id=getattr(response, "id", None),
            raw=response,
        )
