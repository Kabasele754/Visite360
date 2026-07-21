from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Check Gemini, OpenAI and Ultralytics configuration without exposing secrets."

    def handle(self, *args, **options):
        checks = {
            "AI_PRIMARY_TEXT_PROVIDER": getattr(settings, "AI_PRIMARY_TEXT_PROVIDER", "gemini"),
            "AI_FALLBACK_TEXT_PROVIDER": getattr(settings, "AI_FALLBACK_TEXT_PROVIDER", ""),
            "AI_ENABLE_GEMINI": getattr(settings, "AI_ENABLE_GEMINI", True),
            "GOOGLE_CLOUD_PROJECT": getattr(settings, "GOOGLE_CLOUD_PROJECT", ""),
            "GOOGLE_CLOUD_LOCATION": getattr(settings, "GOOGLE_CLOUD_LOCATION", ""),
            "GOOGLE_TEXT_MODEL": getattr(settings, "GOOGLE_TEXT_MODEL", ""),
            "AI_ENABLE_OPENAI": getattr(settings, "AI_ENABLE_OPENAI", False),
            "OPENAI_KEY_PRESENT": bool(getattr(settings, "OPENAI_API_KEY", "")),
            "AI_ENABLE_ULTRALYTICS": getattr(settings, "AI_ENABLE_ULTRALYTICS", True),
            "TOUR_AI_YOLO_MODEL_PATH": getattr(settings, "TOUR_AI_YOLO_MODEL_PATH", ""),
        }
        for key, value in checks.items():
            self.stdout.write(f"{key}={value}")
