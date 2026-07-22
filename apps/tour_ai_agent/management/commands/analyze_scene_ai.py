from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Analyze one 360 scene with local YOLO and optional Gemini Vision."

    def add_arguments(self, parser):
        parser.add_argument("scene_id", type=int)
        parser.add_argument("--force", action="store_true", default=False)

    def handle(self, *args, **options):
        from apps.tours.models import Scene360
        from apps.tour_ai_agent.vision.scene_analyzer import analyze_scene

        try:
            scene = Scene360.objects.get(pk=options["scene_id"])
        except Scene360.DoesNotExist as exc:
            raise CommandError(f"Scene {options['scene_id']} not found") from exc

        profile = analyze_scene(scene, force=options["force"])
        payload = {
            "scene_id": scene.id,
            "source": profile.analysis_source,
            "scene_type": profile.final_scene_type,
            "confidence": profile.analysis_confidence,
            "detections": len(profile.local_detections or []),
            "features": profile.final_features,
            "summary": profile.final_summary,
            "last_error": profile.last_error,
        }
        self.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
        self.stdout.write(self.style.SUCCESS("Twinscopes Vision analysis completed."))
