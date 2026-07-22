from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, TypeVar

from django.conf import settings

from apps.ai_core.services.error_safety import provider_failure_token

logger = logging.getLogger(__name__)


class AIProviderError(RuntimeError):
    pass


@dataclass(slots=True)
class AITextResult:
    text: str
    provider: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AIVisionResult:
    text: str
    provider: str
    model: str
    structured: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


T = TypeVar("T")


class GeminiProvider:
    """Google Gen AI provider with an explicit, request-scoped client lifecycle.

    Keeping the ``Client`` in a local variable (or a context manager) is
    important. Expressions such as ``self._client().models.embed_content(...)``
    can release the temporary Client before the nested Models call completes,
    which may close the underlying HTTP transport and raise:
    ``Cannot send a request, as the client has been closed``.
    """

    name = "gemini"

    def _client(self):
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise AIProviderError("google-genai is not installed") from exc

        http_options = types.HttpOptions(
            api_version="v1",
            timeout=int(getattr(settings, "AI_REQUEST_TIMEOUT_SECONDS", 90) * 1000),
        )
        if settings.GOOGLE_GENAI_USE_VERTEXAI:
            if not settings.GOOGLE_CLOUD_PROJECT:
                raise AIProviderError("GOOGLE_CLOUD_PROJECT is not configured")
            return genai.Client(
                vertexai=True,
                project=settings.GOOGLE_CLOUD_PROJECT,
                location=settings.GOOGLE_CLOUD_LOCATION,
                http_options=http_options,
            )
        if not settings.GEMINI_API_KEY:
            raise AIProviderError("GEMINI_API_KEY is not configured")
        return genai.Client(api_key=settings.GEMINI_API_KEY, http_options=http_options)

    def _with_client(self, callback: Callable[[Any], T]) -> T:
        """Run one complete SDK operation while the sync client stays open."""
        def run_once() -> T:
            client = self._client()
            try:
                return callback(client)
            finally:
                try:
                    client.close()
                except Exception:
                    logger.debug("Gemini client did not close cleanly", exc_info=True)

        try:
            return run_once()
        except RuntimeError as exc:
            # A stale transport can survive a development autoreload or a worker
            # fork. A fresh request-scoped client is safe to retry once.
            if "client has been closed" not in str(exc).lower():
                raise
            logger.warning("Gemini transport was closed; retrying with a fresh client")
            return run_once()

    def generate_text(
        self,
        *,
        prompt: str,
        system: str = "",
        model: str | None = None,
        **kwargs,
    ) -> AITextResult:
        model = model or settings.GOOGLE_TEXT_MODEL
        contents = prompt if not system else f"System instructions:\n{system}\n\nUser request:\n{prompt}"
        try:
            def operation(client):
                response = client.models.generate_content(model=model, contents=contents)
                text = getattr(response, "text", "") or ""
                usage = getattr(response, "usage_metadata", None)
                return AITextResult(
                    text=text,
                    provider=self.name,
                    model=model,
                    prompt_tokens=int(getattr(usage, "prompt_token_count", 0) or 0),
                    completion_tokens=int(getattr(usage, "candidates_token_count", 0) or 0),
                )

            return self._with_client(operation)
        except Exception as exc:
            token = provider_failure_token("gemini", "text", exc)
            logger.warning("Gemini text generation failed [%s]: %s", token, exc, exc_info=True)
            raise AIProviderError(token) from exc

    def analyze_image(
        self,
        *,
        image_bytes: bytes,
        prompt: str,
        mime_type: str = "image/jpeg",
        model: str | None = None,
        **kwargs,
    ) -> AIVisionResult:
        model = model or settings.GOOGLE_VISION_MODEL
        try:
            from google.genai import types

            def operation(client):
                response = client.models.generate_content(
                    model=model,
                    contents=[
                        prompt,
                        types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    ],
                    config=types.GenerateContentConfig(
                        temperature=float(getattr(settings, "VISION_SEMANTIC_TEMPERATURE", 0.1)),
                        max_output_tokens=int(getattr(settings, "VISION_SEMANTIC_MAX_OUTPUT_TOKENS", 2200)),
                        response_mime_type="application/json",
                    ),
                )
                return AIVisionResult(
                    text=getattr(response, "text", "") or "",
                    provider=self.name,
                    model=model,
                )

            return self._with_client(operation)
        except Exception as exc:
            token = provider_failure_token("gemini", "vision", exc)
            logger.warning("Gemini vision analysis failed [%s]: %s", token, exc, exc_info=True)
            raise AIProviderError(token) from exc

    def embed(
        self,
        texts: Iterable[str],
        *,
        model: str | None = None,
        dimensions: int | None = None,
    ) -> list[list[float]]:
        model = model or settings.GOOGLE_EMBEDDING_MODEL
        values = [str(value) for value in texts]
        if not values:
            return []

        storage_dimensions = dimensions or int(getattr(settings, "AI_EMBEDDING_DIMENSIONS", 1536))
        native_dimensions = _google_native_embedding_dimensions(
            model=model,
            requested_dimensions=storage_dimensions,
        )

        try:
            from google.genai import types

            def operation(client):
                config = types.EmbedContentConfig(output_dimensionality=native_dimensions)

                # Vertex endpoints differ by model. Some accept a batch, while
                # gemini-embedding-001 can require one text per request. Try the
                # efficient batch first, then safely fall back to one-by-one.
                try:
                    response = client.models.embed_content(
                        model=model,
                        contents=values,
                        config=config,
                    )
                    embeddings = getattr(response, "embeddings", []) or []
                    vectors = [list(getattr(item, "values", []) or []) for item in embeddings]
                    if len(vectors) != len(values):
                        raise RuntimeError(
                            f"Google returned {len(vectors)} embeddings for {len(values)} texts"
                        )
                except Exception as batch_exc:
                    if len(values) == 1:
                        raise
                    logger.info(
                        "Google embedding batch failed for %s; retrying one text at a time: %s",
                        model,
                        batch_exc,
                    )
                    vectors = []
                    for value in values:
                        response = client.models.embed_content(
                            model=model,
                            contents=value,
                            config=config,
                        )
                        embeddings = getattr(response, "embeddings", []) or []
                        if not embeddings:
                            raise RuntimeError("Google returned an empty embedding response")
                        vectors.append(list(getattr(embeddings[0], "values", []) or []))

                return [
                    _normalize_vector(_fit_dimensions(vector, storage_dimensions))
                    for vector in vectors
                ]

            return self._with_client(operation)
        except Exception as exc:
            token = provider_failure_token("gemini", "embedding", exc)
            logger.warning("Gemini embedding failed [%s]: %s", token, exc, exc_info=True)
            raise AIProviderError(token) from exc


class OpenAIProvider:
    name = "openai"

    def _client(self):
        if not settings.OPENAI_API_KEY:
            raise AIProviderError("OPENAI_API_KEY is not configured")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise AIProviderError("openai is not installed") from exc
        return OpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=float(getattr(settings, "AI_REQUEST_TIMEOUT_SECONDS", 90)),
        )

    def generate_text(self, *, prompt: str, system: str = "", model: str | None = None, **kwargs) -> AITextResult:
        model = model or settings.OPENAI_TEXT_MODEL
        try:
            with self._client() as client:
                response = client.responses.create(
                    model=model,
                    instructions=system or None,
                    input=prompt,
                )
                usage = getattr(response, "usage", None)
                return AITextResult(
                    text=getattr(response, "output_text", "") or "",
                    provider=self.name,
                    model=model,
                    prompt_tokens=int(getattr(usage, "input_tokens", 0) or 0),
                    completion_tokens=int(getattr(usage, "output_tokens", 0) or 0),
                )
        except Exception as exc:
            token = provider_failure_token("openai", "text", exc)
            logger.warning("OpenAI text generation failed [%s]: %s", token, exc, exc_info=True)
            raise AIProviderError(token) from exc

    def analyze_image(self, *, image_bytes: bytes, prompt: str, mime_type: str = "image/jpeg", model: str | None = None, **kwargs) -> AIVisionResult:
        import base64

        model = model or settings.OPENAI_VISION_MODEL
        encoded = base64.b64encode(image_bytes).decode("ascii")
        try:
            with self._client() as client:
                response = client.responses.create(
                    model=model,
                    input=[{
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": prompt},
                            {"type": "input_image", "image_url": f"data:{mime_type};base64,{encoded}"},
                        ],
                    }],
                )
                return AIVisionResult(
                    text=getattr(response, "output_text", "") or "",
                    provider=self.name,
                    model=model,
                )
        except Exception as exc:
            token = provider_failure_token("openai", "vision", exc)
            logger.warning("OpenAI vision analysis failed [%s]: %s", token, exc, exc_info=True)
            raise AIProviderError(token) from exc

    def embed(self, texts: Iterable[str], *, model: str | None = None, dimensions: int | None = None) -> list[list[float]]:
        model = model or settings.OPENAI_EMBEDDING_MODEL
        values = list(texts)
        if not values:
            return []
        try:
            kwargs: dict[str, Any] = {"model": model, "input": values}
            if dimensions:
                kwargs["dimensions"] = dimensions
            with self._client() as client:
                response = client.embeddings.create(**kwargs)
                return [_normalize_vector(_fit_dimensions(list(item.embedding), dimensions)) for item in response.data]
        except Exception as exc:
            token = provider_failure_token("openai", "embedding", exc)
            logger.warning("OpenAI embedding failed [%s]: %s", token, exc, exc_info=True)
            raise AIProviderError(token) from exc


class DeterministicLocalProvider:
    """Safe development fallback. It is deterministic, not semantically intelligent."""

    name = "local"

    def embed(self, texts: Iterable[str], *, dimensions: int | None = None, **kwargs) -> list[list[float]]:
        dimensions = dimensions or settings.AI_EMBEDDING_DIMENSIONS
        vectors: list[list[float]] = []
        for text in texts:
            seed = hashlib.sha512(text.encode("utf-8")).digest()
            raw = bytearray()
            counter = 0
            while len(raw) < dimensions:
                raw.extend(hashlib.sha512(seed + counter.to_bytes(4, "big")).digest())
                counter += 1
            vector = [((byte / 255.0) * 2.0) - 1.0 for byte in raw[:dimensions]]
            norm = sum(value * value for value in vector) ** 0.5 or 1.0
            vectors.append([value / norm for value in vector])
        return vectors


def _google_native_embedding_dimensions(*, model: str, requested_dimensions: int) -> int:
    configured = int(getattr(settings, "GOOGLE_EMBEDDING_NATIVE_DIMENSIONS", 0) or 0)
    if configured > 0:
        return max(1, min(configured, requested_dimensions))

    model_name = (model or "").lower()
    # Vertex endpoints in some regions/models reject values above 768 even when
    # the public Gemini API supports larger vectors. Use 768 by default on
    # Vertex and pad to the pgvector storage width afterward. An explicit
    # GOOGLE_EMBEDDING_NATIVE_DIMENSIONS value can override this behavior.
    if getattr(settings, "GOOGLE_GENAI_USE_VERTEXAI", False):
        return max(1, min(requested_dimensions, 768))
    if "text-embedding" in model_name:
        return max(1, min(requested_dimensions, 768))
    if "gemini-embedding" in model_name:
        return max(1, min(requested_dimensions, 3072))
    return max(1, min(requested_dimensions, 768))


def _fit_dimensions(vector: list[float], dimensions: int | None) -> list[float]:
    if not dimensions:
        return vector
    if len(vector) > dimensions:
        return vector[:dimensions]
    if len(vector) < dimensions:
        return vector + [0.0] * (dimensions - len(vector))
    return vector


def _normalize_vector(vector: list[float]) -> list[float]:
    norm = sum(value * value for value in vector) ** 0.5
    if not norm:
        return vector
    return [value / norm for value in vector]


def _balanced_json_objects(text: str):
    """Yield balanced JSON-object substrings, respecting quoted braces."""
    start = None
    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            continue
        if char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                yield text[start : index + 1]
                start = None


def parse_json_object(text: str) -> dict[str, Any]:
    """Parse the first valid JSON object without merging adjacent responses.

    Vision models occasionally append prose or a second JSON object. The old
    implementation sliced from the first ``{`` to the final ``}``, producing an
    invalid mega-payload whose raw text could leak into scene cards.
    """
    cleaned = str(text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        cleaned = cleaned.rsplit("```", 1)[0]
    candidates = [cleaned, *_balanced_json_objects(cleaned)]
    seen: set[str] = set()
    for candidate in candidates:
        candidate = candidate.strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
        return {"value": value}
    return {"text": str(text or "")}
