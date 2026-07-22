from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

from django.conf import settings
from django.utils import timezone

from apps.ai_core.models import AIRun
from apps.ai_core.services.providers import (
    AIProviderError,
    DeterministicLocalProvider,
    GeminiProvider,
    OpenAIProvider,
)

logger = logging.getLogger(__name__)


class AIProviderRouter:
    _embedding_failure_until: dict[str, float] = {}
    _provider_failure_until: dict[tuple[str, str], float] = {}
    _provider_failure_reason: dict[tuple[str, str], str] = {}
    provider_classes = {
        "gemini": GeminiProvider,
        "openai": OpenAIProvider,
        "local": DeterministicLocalProvider,
    }

    def __init__(self, *, organization=None, user=None, trace_id: str = ""):
        self.organization = organization
        self.user = user
        self.trace_id = trace_id
        self.last_embedding_provider = ""
        self.last_embedding_model = ""
        self.last_embedding_dimensions = 0

    def _provider(self, name: str):
        provider_class = self.provider_classes.get(name)
        if not provider_class:
            raise AIProviderError(f"Unsupported AI provider: {name}")
        return provider_class()

    @staticmethod
    def _is_retryable_error(exc: Exception) -> bool:
        message = str(exc).lower()
        return any(token in message for token in (
            "429",
            "resource_exhausted",
            "resource exhausted",
            "rate limit",
            "too many requests",
            "503",
            "service unavailable",
            "unavailable",
            "deadline exceeded",
            "timed out",
            "timeout",
            "connection reset",
            "temporarily unavailable",
        ))

    @staticmethod
    def _retry_count_for(operation: str) -> int:
        if operation.startswith("vision."):
            return max(0, int(getattr(settings, "AI_VISION_PROVIDER_MAX_RETRIES", 1)))
        return max(0, int(getattr(settings, "AI_PROVIDER_MAX_RETRIES", 2)))

    @staticmethod
    def _failure_cooldown_for(operation: str) -> int:
        if operation.startswith("vision."):
            return max(
                15,
                int(getattr(settings, "AI_VISION_PROVIDER_FAILURE_COOLDOWN_SECONDS", 180)),
            )
        return max(
            15,
            int(getattr(settings, "AI_PROVIDER_FAILURE_COOLDOWN_SECONDS", 300)),
        )

    def _execute(
        self,
        *,
        operation: str,
        providers: list[str],
        callback: Callable[[Any], Any],
        input_summary: str = "",
    ):
        last_error: Exception | None = None
        bypassed: list[str] = []
        for provider_name in [name for name in providers if name]:
            breaker_key = (operation, provider_name)
            failure_until = self._provider_failure_until.get(breaker_key, 0.0)
            if failure_until > time.monotonic():
                remaining = max(1, int(failure_until - time.monotonic()))
                reason = self._provider_failure_reason.get(breaker_key, "recent transient failure")
                bypassed.append(f"{provider_name} ({remaining}s: {reason})")
                logger.debug(
                    "AI provider %s is temporarily bypassed for %s (%ss remaining)",
                    provider_name,
                    operation,
                    remaining,
                )
                continue

            run = AIRun.objects.create(
                organization=self.organization,
                requested_by=self.user if getattr(self.user, "is_authenticated", False) else None,
                operation=operation,
                provider=provider_name,
                status=AIRun.Status.RUNNING,
                trace_id=self.trace_id,
                input_summary=input_summary[:2000],
                started_at=timezone.now(),
            )
            started = time.monotonic()
            max_retries = self._retry_count_for(operation)
            base_delay = max(
                0.1,
                float(getattr(settings, "AI_PROVIDER_RETRY_BASE_SECONDS", 2.0)),
            )
            max_delay = max(
                base_delay,
                float(getattr(settings, "AI_PROVIDER_RETRY_MAX_SECONDS", 20.0)),
            )

            result = None
            final_error: Exception | None = None
            for attempt in range(max_retries + 1):
                try:
                    result = callback(self._provider(provider_name))
                    final_error = None
                    break
                except Exception as exc:
                    final_error = exc
                    last_error = exc
                    retryable = self._is_retryable_error(exc)
                    if retryable and attempt < max_retries:
                        delay = min(max_delay, base_delay * (2 ** attempt))
                        logger.warning(
                            "AI provider %s was throttled/unavailable for %s; "
                            "retrying in %.1fs (%s/%s): %s",
                            provider_name,
                            operation,
                            delay,
                            attempt + 1,
                            max_retries,
                            exc,
                        )
                        time.sleep(delay)
                        continue
                    break

            if result is not None:
                self._provider_failure_until.pop(breaker_key, None)
                self._provider_failure_reason.pop(breaker_key, None)
                run.status = AIRun.Status.SUCCEEDED
                run.model_name = getattr(result, "model", "")
                run.output_summary = getattr(result, "text", "")[:2000]
                run.prompt_tokens = getattr(result, "prompt_tokens", 0)
                run.completion_tokens = getattr(result, "completion_tokens", 0)
                run.finished_at = timezone.now()
                run.latency_ms = int((time.monotonic() - started) * 1000)
                run.save()
                return result

            assert final_error is not None
            if self._is_retryable_error(final_error):
                cooldown = self._failure_cooldown_for(operation)
                self._provider_failure_until[breaker_key] = time.monotonic() + cooldown
                self._provider_failure_reason[breaker_key] = str(final_error)[:240]
                logger.warning(
                    "AI provider %s will be bypassed for %ss for %s after a transient failure: %s",
                    provider_name,
                    cooldown,
                    operation,
                    final_error,
                )
            else:
                logger.warning("AI provider %s failed for %s: %s", provider_name, operation, final_error)

            run.status = AIRun.Status.FAILED
            run.error_type = final_error.__class__.__name__
            run.error_message = str(final_error)[:8000]
            run.finished_at = timezone.now()
            run.latency_ms = int((time.monotonic() - started) * 1000)
            run.save()

        if last_error is not None:
            raise AIProviderError(str(last_error))
        if bypassed:
            raise AIProviderError("Providers temporarily bypassed: " + ", ".join(bypassed))
        raise AIProviderError("No AI provider is configured")

    def generate_text(self, *, prompt: str, system: str = "", provider: str | None = None, model: str | None = None):
        providers = [provider] if provider else [settings.AI_PRIMARY_TEXT_PROVIDER, settings.AI_FALLBACK_TEXT_PROVIDER]
        return self._execute(
            operation="text.generate",
            providers=providers,
            input_summary=prompt,
            callback=lambda client: client.generate_text(prompt=prompt, system=system, model=model),
        )

    def analyze_image(self, *, image_bytes: bytes, prompt: str, mime_type: str = "image/jpeg", provider: str | None = None, model: str | None = None):
        providers = [provider] if provider else ["gemini", "openai"]
        return self._execute(
            operation="vision.analyze",
            providers=providers,
            input_summary=prompt,
            callback=lambda client: client.analyze_image(
                image_bytes=image_bytes, prompt=prompt, mime_type=mime_type, model=model
            ),
        )

    def _embedding_provider_order(self, explicit_provider: str | None = None) -> list[str]:
        configured = (explicit_provider or getattr(settings, "AI_EMBEDDING_PROVIDER", "auto") or "auto").lower()
        fallback = (getattr(settings, "AI_FALLBACK_EMBEDDING_PROVIDER", "") or "").lower()

        if configured == "auto":
            configured = "openai" if getattr(settings, "OPENAI_API_KEY", "") else "gemini"

        def is_configured(name: str) -> bool:
            if name == "openai":
                return bool(getattr(settings, "OPENAI_API_KEY", ""))
            if name == "gemini":
                return bool(
                    (
                        getattr(settings, "GOOGLE_GENAI_USE_VERTEXAI", False)
                        and getattr(settings, "GOOGLE_CLOUD_PROJECT", "")
                        and getattr(settings, "GOOGLE_CLOUD_LOCATION", "")
                    )
                    or getattr(settings, "GEMINI_API_KEY", "")
                )
            if name == "local":
                return bool(getattr(settings, "AI_ALLOW_DETERMINISTIC_EMBEDDINGS", False))
            return bool(name)

        ordered: list[str] = []
        for name in (
            configured,
            fallback,
            "openai" if configured != "openai" else "",
            "gemini" if configured != "gemini" else "",
        ):
            if name and name not in ordered and is_configured(name):
                ordered.append(name)

        if is_configured("local") and "local" not in ordered:
            ordered.append("local")
        return ordered

    def embed(self, texts: list[str], *, provider: str | None = None, dimensions: int | None = None) -> list[list[float]]:
        dimensions = dimensions or settings.AI_EMBEDDING_DIMENSIONS
        providers = self._embedding_provider_order(provider)
        last_error: Exception | None = None
        for provider_name in providers:
            failure_until = self._embedding_failure_until.get(provider_name, 0.0)
            if failure_until > time.monotonic():
                logger.debug("Embedding provider %s is temporarily bypassed after a recent failure", provider_name)
                continue
            try:
                vectors = self._provider(provider_name).embed(texts, dimensions=dimensions)
                if len(vectors) != len(texts):
                    raise AIProviderError(
                        f"Embedding provider {provider_name} returned {len(vectors)} vectors for {len(texts)} texts"
                    )
                self._embedding_failure_until.pop(provider_name, None)
                self.last_embedding_provider = provider_name
                if provider_name == "openai":
                    self.last_embedding_model = str(getattr(settings, "OPENAI_EMBEDDING_MODEL", ""))
                elif provider_name == "gemini":
                    self.last_embedding_model = str(getattr(settings, "GOOGLE_EMBEDDING_MODEL", ""))
                else:
                    self.last_embedding_model = "deterministic-local"
                self.last_embedding_dimensions = int(dimensions)
                return vectors
            except Exception as exc:
                last_error = exc
                cooldown = int(getattr(settings, "AI_PROVIDER_FAILURE_COOLDOWN_SECONDS", 300))
                self._embedding_failure_until[provider_name] = time.monotonic() + max(15, cooldown)
                logger.warning(
                    "Embedding provider %s failed and will be bypassed for %ss: %s",
                    provider_name, max(15, cooldown), exc,
                )
        raise AIProviderError(str(last_error or "No embedding provider is configured"))
