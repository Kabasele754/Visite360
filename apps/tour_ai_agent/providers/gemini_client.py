from __future__ import annotations

import logging
import os
import threading
from typing import Any

from django.conf import settings
from google import genai
from google.genai import types

from .base import AITextResponse


logger = logging.getLogger(__name__)


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default

    if isinstance(value, bool):
        return value

    return str(value).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


class GeminiClient:
    """
    Client Gemini texte via Vertex AI.

    Le client google.genai est conservé dans l'instance afin d'éviter :
        RuntimeError: Cannot send a request, as the client has been closed.
    """

    name = "gemini"

    def __init__(self) -> None:
        self._client_instance: genai.Client | None = None
        self._client_lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        configured = getattr(
            settings,
            "AI_ENABLE_GEMINI",
            os.getenv("AI_ENABLE_GEMINI", "true"),
        )

        return bool(
            _as_bool(configured, default=True)
            and self.project
            and self.location
            and self.model
        )

    @property
    def project(self) -> str:
        return str(
            getattr(
                settings,
                "GOOGLE_CLOUD_PROJECT",
                os.getenv("GOOGLE_CLOUD_PROJECT", ""),
            )
        ).strip()

    @property
    def location(self) -> str:
        return str(
            getattr(
                settings,
                "GOOGLE_CLOUD_LOCATION",
                os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
            )
        ).strip()

    @property
    def model(self) -> str:
        return str(
            getattr(
                settings,
                "GOOGLE_TEXT_MODEL",
                os.getenv("GOOGLE_TEXT_MODEL", "gemini-2.5-flash"),
            )
        ).strip()

    @property
    def temperature(self) -> float:
        value = getattr(
            settings,
            "AI_TEXT_TEMPERATURE",
            os.getenv("AI_TEXT_TEMPERATURE", "0.3"),
        )

        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.3

    @property
    def max_output_tokens(self) -> int:
        value = getattr(
            settings,
            "AI_TEXT_MAX_TOKENS",
            os.getenv("AI_TEXT_MAX_TOKENS", "1400"),
        )

        try:
            return int(value)
        except (TypeError, ValueError):
            return 1400

    def _create_client(self) -> genai.Client:
        if not self.project:
            raise RuntimeError(
                "GOOGLE_CLOUD_PROJECT is missing."
            )

        if not self.location:
            raise RuntimeError(
                "GOOGLE_CLOUD_LOCATION is missing."
            )

        return genai.Client(
            vertexai=True,
            project=self.project,
            location=self.location,
            http_options=types.HttpOptions(
                api_version="v1",
                timeout=120_000,
            ),
        )

    def _get_client(self) -> genai.Client:
        if self._client_instance is None:
            with self._client_lock:
                if self._client_instance is None:
                    self._client_instance = self._create_client()

        return self._client_instance

    def _reset_client(self) -> None:
        client = self._client_instance
        self._client_instance = None

        if client is None:
            return

        try:
            client.close()
        except Exception:
            logger.debug(
                "Unable to close Gemini client cleanly.",
                exc_info=True,
            )

    def generate(
        self,
        *,
        instructions: str,
        input_text: str,
    ) -> AITextResponse:
        if not self.enabled:
            raise RuntimeError(
                "Gemini provider is disabled or incomplete."
            )

        prompt = self._build_prompt(
            instructions=instructions,
            input_text=input_text,
        )

        config = types.GenerateContentConfig(
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens,
        )

        try:
            client = self._get_client()

            response = client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            )

        except RuntimeError as exc:
            error_message = str(exc).lower()

            if "client has been closed" not in error_message:
                raise

            logger.warning(
                "Gemini client was closed. Recreating the client."
            )

            self._reset_client()

            client = self._get_client()

            response = client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            )

        text = self._extract_text(response)

        if not text:
            raise RuntimeError(
                "Gemini returned an empty response."
            )

        return AITextResponse(
            text=text,
            provider=self.name,
            response_id=self._extract_response_id(response),
            raw=response,
        )

    @staticmethod
    def _build_prompt(
        *,
        instructions: str,
        input_text: str,
    ) -> str:
        clean_instructions = (instructions or "").strip()
        clean_input = (input_text or "").strip()

        if not clean_instructions:
            return clean_input

        return (
            "SYSTEM INSTRUCTIONS:\n"
            f"{clean_instructions}\n\n"
            "USER INPUT:\n"
            f"{clean_input}"
        )

    @staticmethod
    def _extract_text(response: Any) -> str:
        direct_text = getattr(response, "text", None)

        if direct_text:
            return str(direct_text).strip()

        candidates = getattr(response, "candidates", None) or []
        collected_parts: list[str] = []

        for candidate in candidates:
            content = getattr(candidate, "content", None)

            if content is None:
                continue

            parts = getattr(content, "parts", None) or []

            for part in parts:
                part_text = getattr(part, "text", None)

                if part_text:
                    collected_parts.append(str(part_text))

        return "\n".join(collected_parts).strip()

    @staticmethod
    def _extract_response_id(response: Any) -> str | None:
        for attribute_name in (
            "response_id",
            "id",
            "request_id",
        ):
            value = getattr(response, attribute_name, None)

            if value:
                return str(value)

        return None

    def close(self) -> None:
        self._reset_client()


class GeminiVisionClient(GeminiClient):
    """
    Client Gemini Vision.

    Il réutilise la gestion stable du client Gemini.
    """

    name = "gemini_vision"

    @property
    def enabled(self) -> bool:
        configured = getattr(
            settings,
            "AI_ENABLE_GEMINI_VISION",
            os.getenv("AI_ENABLE_GEMINI_VISION", "true"),
        )

        return bool(
            _as_bool(configured, default=True)
            and self.project
            and self.location
            and self.model
        )

    @property
    def model(self) -> str:
        return str(
            getattr(
                settings,
                "GEMINI_TOUR_VISION_MODEL",
                os.getenv(
                    "GEMINI_TOUR_VISION_MODEL",
                    "gemini-2.5-flash",
                ),
            )
        ).strip()

    def analyze_image(
        self,
        *,
        image_bytes: bytes,
        mime_type: str,
        instructions: str,
        input_text: str = "",
    ) -> AITextResponse:
        if not self.enabled:
            raise RuntimeError(
                "Gemini Vision provider is disabled or incomplete."
            )

        if not image_bytes:
            raise ValueError("image_bytes cannot be empty.")

        prompt = self._build_prompt(
            instructions=instructions,
            input_text=input_text,
        )

        image_part = types.Part.from_bytes(
            data=image_bytes,
            mime_type=mime_type,
        )

        config = types.GenerateContentConfig(
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens,
        )

        try:
            client = self._get_client()

            response = client.models.generate_content(
                model=self.model,
                contents=[
                    prompt,
                    image_part,
                ],
                config=config,
            )

        except RuntimeError as exc:
            if "client has been closed" not in str(exc).lower():
                raise

            logger.warning(
                "Gemini Vision client was closed. Recreating it."
            )

            self._reset_client()
            client = self._get_client()

            response = client.models.generate_content(
                model=self.model,
                contents=[
                    prompt,
                    image_part,
                ],
                config=config,
            )

        text = self._extract_text(response)

        if not text:
            raise RuntimeError(
                "Gemini Vision returned an empty response."
            )

        return AITextResponse(
            text=text,
            provider=self.name,
            response_id=self._extract_response_id(response),
            raw=response,
        )
# Backward-compatible structured multi-frame analysis used by scene_analyzer.py.
def _vision_analyze(self, image_paths: list[str], local_context: dict) -> dict:
    import json
    import mimetypes
    import re

    if not self.enabled or not image_paths:
        return {}

    contents: list[Any] = [
        """Analyze these perspective frames extracted from one 360 panorama.
Return ONLY valid JSON with this exact structure:
{
  "scene_type": "short snake_case type",
  "summary": "truthful customer-friendly scene summary",
  "features": ["visible feature"],
  "objects": [{"label":"object type","count":1,"confidence":0.0,"visual_description":"short description"}],
  "product_hypotheses": [{"generic_name":"generic product/object type","category":"category","style":"style","color":"color","material":"material","confidence":0.0,"evidence":"visible evidence only"}],
  "commercial_intents": ["view_products","request_quote","book_appointment"],
  "suggested_questions": ["question"],
  "opening_message": "short helpful opening"
}
Do not identify a visually observed object as a catalogue product. Do not invent brands, prices, stock or exact models.
Local detector context follows:
""" + json.dumps(local_context, ensure_ascii=False)
    ]
    for path in image_paths[:8]:
        mime_type = mimetypes.guess_type(path)[0] or "image/jpeg"
        with open(path, "rb") as handle:
            contents.append(types.Part.from_bytes(data=handle.read(), mime_type=mime_type))

    client = self._get_client()
    response = client.models.generate_content(
        model=self.model,
        contents=contents,
        config=types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=max(self.max_output_tokens, 2200),
            response_mime_type="application/json",
        ),
    )
    text = self._extract_text(response).strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I | re.S)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Gemini Vision returned non-JSON output")
        return {}
    return parsed if isinstance(parsed, dict) else {}


GeminiVisionClient.analyze = _vision_analyze
