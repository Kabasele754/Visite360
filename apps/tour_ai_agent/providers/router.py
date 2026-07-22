from __future__ import annotations

import logging
from collections.abc import Iterable

from django.conf import settings

from .base import AITextResponse, TextProvider
from .gemini_client import GeminiClient
from .openai_client import OpenAIClient


logger = logging.getLogger(__name__)


class AIProviderRouter:
    """
    Routeur des fournisseurs IA.

    Gemini est utilisé comme fournisseur principal.
    OpenAI pourra être ajouté en fallback plus tard.
    """

    _provider_instances: dict[str, TextProvider] = {}

    def __init__(self) -> None:
        self.primary_provider = str(
            getattr(
                settings,
                "AI_PRIMARY_TEXT_PROVIDER",
                "gemini",
            )
        ).strip().lower()

        self.fallback_provider = str(
            getattr(
                settings,
                "AI_FALLBACK_TEXT_PROVIDER",
                "",
            )
        ).strip().lower()

    @classmethod
    def _get_provider(
        cls,
        provider_name: str,
    ) -> TextProvider | None:
        normalized_name = (
            provider_name or ""
        ).strip().lower()

        if not normalized_name:
            return None

        aliases = {
            "google": "gemini",
            "vertex": "gemini",
            "google_vertex": "gemini",
            "google-vertex": "gemini",
        }

        normalized_name = aliases.get(
            normalized_name,
            normalized_name,
        )

        existing = cls._provider_instances.get(
            normalized_name
        )

        if existing is not None:
            return existing

        if normalized_name == "gemini":
            provider: TextProvider = GeminiClient()
        elif normalized_name == "openai":
            provider = OpenAIClient()
        else:
            logger.warning(
                "Unknown AI provider: %s",
                normalized_name,
            )
            return None

        cls._provider_instances[normalized_name] = provider

        return provider

    def _provider_order(self) -> Iterable[str]:
        seen: set[str] = set()

        for provider_name in (
            self.primary_provider,
            self.fallback_provider,
        ):
            normalized_name = (
                provider_name or ""
            ).strip().lower()

            if not normalized_name:
                continue

            if normalized_name in seen:
                continue

            seen.add(normalized_name)
            yield normalized_name

    def generate(
        self,
        *,
        instructions: str,
        input_text: str,
    ) -> AITextResponse:
        errors: list[str] = []

        for provider_name in self._provider_order():
            provider = self._get_provider(provider_name)

            if provider is None:
                errors.append(
                    f"{provider_name}: provider unavailable"
                )
                continue

            if not provider.enabled:
                errors.append(
                    f"{provider_name}: provider disabled"
                )
                continue

            try:
                response = provider.generate(
                    instructions=instructions,
                    input_text=input_text,
                )

                logger.info(
                    "AI provider succeeded: provider=%s",
                    response.provider,
                )

                return response

            except Exception as exc:
                logger.exception(
                    "AI provider %s failed",
                    provider_name,
                )

                errors.append(
                    f"{provider_name}: {exc}"
                )

        if not errors:
            errors.append("no provider configured")

        raise RuntimeError(
            "No AI text provider succeeded: "
            + " | ".join(errors)
        )