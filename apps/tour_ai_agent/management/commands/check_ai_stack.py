from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

from django.conf import settings
from django.db import connection
from django.db.models import Count, Q
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Check Twinscopes text, embedding and advanced 360 vision configuration. "
        "Use --live to execute real provider calls and --scene to run a full panorama analysis."
    )

    def add_arguments(self, parser):
        parser.add_argument("--live", action="store_true", help="Perform real embedding API calls")
        parser.add_argument("--scene", type=int, help="Run a real synchronous scan for this existing scene ID")
        parser.add_argument("--force", action="store_true")
        parser.add_argument(
            "--providers",
            default="yolo,paddleocr,gemini,openai",
            help="Providers used with --scene",
        )
        parser.add_argument("--json", action="store_true", help="Print one JSON object")

    def handle(self, *args, **options):
        yolo_path = Path(str(getattr(settings, "VISION_YOLO_MODEL", "")))
        checks = {
            "DJANGO_SETTINGS_MODULE": os.environ.get("DJANGO_SETTINGS_MODULE", ""),
            "DATABASE_VENDOR": connection.vendor,
            "DEBUG": settings.DEBUG,
            "AI_PRIMARY_TEXT_PROVIDER": getattr(settings, "AI_PRIMARY_TEXT_PROVIDER", "openai"),
            "AI_FALLBACK_TEXT_PROVIDER": getattr(settings, "AI_FALLBACK_TEXT_PROVIDER", "gemini"),
            "AI_EMBEDDING_PROVIDER": getattr(settings, "AI_EMBEDDING_PROVIDER", "auto"),
            "AI_FALLBACK_EMBEDDING_PROVIDER": getattr(settings, "AI_FALLBACK_EMBEDDING_PROVIDER", "openai"),
            "AI_EMBEDDING_DIMENSIONS": getattr(settings, "AI_EMBEDDING_DIMENSIONS", 1536),
            "GOOGLE_EMBEDDING_NATIVE_DIMENSIONS": getattr(settings, "GOOGLE_EMBEDDING_NATIVE_DIMENSIONS", 0),
            "AI_PROVIDER_FAILURE_COOLDOWN_SECONDS": getattr(settings, "AI_PROVIDER_FAILURE_COOLDOWN_SECONDS", 300),
            "AI_VISION_PROVIDER_FAILURE_COOLDOWN_SECONDS": getattr(settings, "AI_VISION_PROVIDER_FAILURE_COOLDOWN_SECONDS", 180),
            "AI_PROVIDER_MAX_RETRIES": getattr(settings, "AI_PROVIDER_MAX_RETRIES", 2),
            "AI_VISION_PROVIDER_MAX_RETRIES": getattr(settings, "AI_VISION_PROVIDER_MAX_RETRIES", 1),
            "AI_PROVIDER_RETRY_BASE_SECONDS": getattr(settings, "AI_PROVIDER_RETRY_BASE_SECONDS", 2.0),
            "OPENAI_KEY_PRESENT": bool(getattr(settings, "OPENAI_API_KEY", "")),
            "OPENAI_TEXT_MODEL": getattr(settings, "OPENAI_TEXT_MODEL", ""),
            "OPENAI_EMBEDDING_MODEL": getattr(settings, "OPENAI_EMBEDDING_MODEL", ""),
            "GOOGLE_VERTEX_ENABLED": getattr(settings, "GOOGLE_GENAI_USE_VERTEXAI", False),
            "GOOGLE_CLOUD_PROJECT": getattr(settings, "GOOGLE_CLOUD_PROJECT", ""),
            "GOOGLE_CLOUD_LOCATION": getattr(settings, "GOOGLE_CLOUD_LOCATION", ""),
            "GOOGLE_TEXT_MODEL": getattr(settings, "GOOGLE_TEXT_MODEL", ""),
            "GOOGLE_EMBEDDING_MODEL": getattr(settings, "GOOGLE_EMBEDDING_MODEL", ""),
            "GOOGLE_APPLICATION_CREDENTIALS": getattr(settings, "GOOGLE_APPLICATION_CREDENTIALS", ""),
            "VISION_ENABLE_YOLO": getattr(settings, "VISION_ENABLE_YOLO", False),
            "VISION_ENABLE_PADDLEOCR": getattr(settings, "VISION_ENABLE_PADDLEOCR", False),
            "VISION_ENABLE_GEMINI": getattr(settings, "VISION_ENABLE_GEMINI", False),
            "VISION_ENABLE_OPENAI": getattr(settings, "VISION_ENABLE_OPENAI", False),
            "VISION_PUBLIC_ON_DEMAND_SCAN": getattr(settings, "VISION_PUBLIC_ON_DEMAND_SCAN", False),
            "VISION_ON_DEMAND_ANALYSIS_MODE": getattr(settings, "VISION_ON_DEMAND_ANALYSIS_MODE", "auto"),
            "VISION_PRIMARY_SEMANTIC_PROVIDER": getattr(settings, "VISION_PRIMARY_SEMANTIC_PROVIDER", "gemini"),
            "VISION_FALLBACK_SEMANTIC_PROVIDER": getattr(settings, "VISION_FALLBACK_SEMANTIC_PROVIDER", "openai"),
            "VISION_MAX_PANORAMA_FRAMES": getattr(settings, "VISION_MAX_PANORAMA_FRAMES", 12),
            "VISION_SEMANTIC_MAX_FRAMES": getattr(settings, "VISION_SEMANTIC_MAX_FRAMES", 12),
            "VISION_SEMANTIC_MAX_CLOUD_CALLS_PER_SCENE": getattr(settings, "VISION_SEMANTIC_MAX_CLOUD_CALLS_PER_SCENE", 4),
            "VISION_SEMANTIC_REQUEST_INTERVAL_SECONDS": getattr(settings, "VISION_SEMANTIC_REQUEST_INTERVAL_SECONDS", 1.25),
            "VISION_PERSPECTIVE_FRAME_SIZE": getattr(settings, "VISION_PERSPECTIVE_FRAME_SIZE", 896),
            "VISION_LONG_PRESS_DURATION_MS": getattr(settings, "VISION_LONG_PRESS_DURATION_MS", 650),
            "VISION_POINT_ON_DEMAND_INSPECTION": getattr(settings, "VISION_POINT_ON_DEMAND_INSPECTION", True),
            "VISION_POINT_INSPECTION_FOV_DEGREES": getattr(settings, "VISION_POINT_INSPECTION_FOV_DEGREES", 46.0),
            "VISION_POINT_DETAIL_FOV_DEGREES": getattr(settings, "VISION_POINT_DETAIL_FOV_DEGREES", 26.0),
            "VISION_POINT_INSPECTION_FRAME_SIZE": getattr(settings, "VISION_POINT_INSPECTION_FRAME_SIZE", 768),
            "VISION_POINT_PIXEL_PADDING_RATIO": getattr(settings, "VISION_POINT_PIXEL_PADDING_RATIO", 0.012),
            "VISION_POINT_NEAR_PADDING_RATIO": getattr(settings, "VISION_POINT_NEAR_PADDING_RATIO", 0.035),
            "VISION_POINT_REFINEMENT_AREA_RATIO": getattr(settings, "VISION_POINT_REFINEMENT_AREA_RATIO", 0.16),
            "VISION_POINT_REFINE_LOCAL_ONLY": getattr(settings, "VISION_POINT_REFINE_LOCAL_ONLY", True),
            "VISION_POINT_REFINE_BELOW_CONFIDENCE": getattr(settings, "VISION_POINT_REFINE_BELOW_CONFIDENCE", 0.55),
            "VISION_POINT_SEMANTIC_MIN_CONFIDENCE": getattr(settings, "VISION_POINT_SEMANTIC_MIN_CONFIDENCE", 0.55),
            "VISION_POINT_SEMANTIC_ONLY_MIN_CONFIDENCE": getattr(settings, "VISION_POINT_SEMANTIC_ONLY_MIN_CONFIDENCE", 0.72),
            "VISION_YOLO_MODEL": str(yolo_path),
            "YOLO_MODEL_EXISTS": yolo_path.exists(),
            "YOLO_MODEL_SIZE_MB": round(yolo_path.stat().st_size / 1024 / 1024, 2) if yolo_path.exists() else 0,
            "PYTHON_PACKAGES": {
                name: bool(importlib.util.find_spec(module))
                for name, module in {
                    "openai": "openai",
                    "google-genai": "google.genai",
                    "ultralytics": "ultralytics",
                    "paddleocr": "paddleocr",
                    "paddle": "paddle",
                    "opencv": "cv2",
                    "pgvector": "pgvector",
                    "pillow-heif": "pillow_heif",
                    "pillow-avif": "pillow_avif",
                }.items()
            },
        }

        try:
            from apps.tours.models import Scene360
            from apps.vision_ai.models import VisionAnalysis

            scene_queryset = Scene360.objects.all()
            checks["SCENE_INVENTORY"] = {
                "total_scenes": scene_queryset.count(),
                "scenes_with_panorama": scene_queryset.filter(
                    (~Q(image_360_original="") & Q(image_360_original__isnull=False))
                    | (~Q(image_360="") & Q(image_360__isnull=False))
                    | (~Q(image_360_mobile="") & Q(image_360_mobile__isnull=False))
                    | (~Q(image_360_preview="") & Q(image_360_preview__isnull=False))
                ).distinct().count(),
                "scene_statuses": {
                    str(row["ai_analysis_status"]): row["count"]
                    for row in scene_queryset.values("ai_analysis_status")
                    .annotate(count=Count("id"))
                    .order_by("ai_analysis_status")
                },
                "vision_analyses": VisionAnalysis.objects.count(),
            }
        except Exception as exc:
            checks["SCENE_INVENTORY"] = {"available": False, "error": str(exc)}

        live_results: dict[str, dict] = {}
        if options["live"]:
            from apps.ai_core.services.providers import GeminiProvider, OpenAIProvider

            providers = [
                ("gemini", GeminiProvider(), bool(
                    getattr(settings, "GOOGLE_GENAI_USE_VERTEXAI", False)
                    or getattr(settings, "GEMINI_API_KEY", "")
                )),
                ("openai", OpenAIProvider(), bool(getattr(settings, "OPENAI_API_KEY", ""))),
            ]
            for name, provider, configured in providers:
                if not configured:
                    live_results[name] = {"ok": False, "skipped": True, "error": "credentials not configured"}
                    continue
                try:
                    vector = provider.embed(
                        ["Twinscopes 360 computer vision runtime check"],
                        dimensions=int(getattr(settings, "AI_EMBEDDING_DIMENSIONS", 1536)),
                    )[0]
                    live_results[name] = {
                        "ok": True,
                        "dimensions": len(vector),
                        "non_zero_values": sum(1 for value in vector if value),
                    }
                except Exception as exc:
                    live_results[name] = {"ok": False, "error": str(exc)}
            checks["LIVE_EMBEDDING_TESTS"] = live_results

        if options["scene"]:
            from apps.tours.models import Scene360
            from apps.vision_ai.services.queueing import analysis_status_payload, dispatch_scene_analysis

            scene = Scene360.objects.filter(pk=options["scene"]).first()
            if scene is None:
                raise CommandError(f"Scene {options['scene']} not found")
            providers = [value.strip() for value in options["providers"].split(",") if value.strip()]
            dispatch_scene_analysis(
                scene,
                force=options["force"],
                requested_providers=providers,
                mode="sync",
            )
            scene.refresh_from_db()
            checks["SCENE_ANALYSIS"] = analysis_status_payload(scene)

        if options["json"]:
            self.stdout.write(json.dumps(checks, ensure_ascii=False, indent=2, default=str))
            return

        for key, value in checks.items():
            if isinstance(value, (dict, list)):
                self.stdout.write(f"{key}={json.dumps(value, ensure_ascii=False, default=str)}")
            else:
                self.stdout.write(f"{key}={value}")

        if options["live"]:
            passed = [name for name, result in live_results.items() if result.get("ok")]
            if passed:
                self.stdout.write(self.style.SUCCESS(f"Live embedding provider(s) working: {', '.join(passed)}"))
            else:
                self.stdout.write(self.style.WARNING("No live embedding provider succeeded."))
        if options["scene"]:
            status = checks["SCENE_ANALYSIS"].get("status")
            if status in {"succeeded", "partial"}:
                self.stdout.write(self.style.SUCCESS(f"Scene {options['scene']} vision scan completed: {status}"))
            else:
                self.stdout.write(self.style.ERROR(f"Scene {options['scene']} vision scan finished with status: {status}"))
