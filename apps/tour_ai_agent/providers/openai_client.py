from __future__ import annotations

from django.conf import settings
from .base import AITextResponse


class OpenAIClient:
    name = "openai"

    @property
    def enabled(self) -> bool:
        return bool(getattr(settings, "OPENAI_API_KEY", ""))

    def generate(self, *, instructions: str, input_text: str) -> AITextResponse:
        if not self.enabled:
            raise RuntimeError("OpenAI is not configured")
        from openai import OpenAI
        with OpenAI(api_key=settings.OPENAI_API_KEY, timeout=settings.AI_REQUEST_TIMEOUT_SECONDS) as client:
            response = client.responses.create(
                model=settings.OPENAI_TEXT_MODEL,
                instructions=instructions,
                input=input_text,
            )
            text = response.output_text or ""
            response_id = getattr(response, "id", None)
        return AITextResponse(
            text=text,
            provider="openai",
            response_id=response_id,
            raw=None,
        )
