from __future__ import annotations

import json
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from PIL import Image


class Command(BaseCommand):
    help = "Verify that Ultralytics YOLO loads and runs locally or in production."

    def add_arguments(self, parser):
        parser.add_argument("--image", default="", help="Optional image path to analyze")
        parser.add_argument("--download", action="store_true", help="Download the configured model if missing")

    def handle(self, *args, **options):
        model_path = Path(settings.TOUR_AI_YOLO_MODEL_PATH)
        if not model_path.exists() and options["download"]:
            from ultralytics import YOLO
            import shutil
            model_path.parent.mkdir(parents=True, exist_ok=True)
            model = YOLO("yolo11n.pt")
            source = Path(model.ckpt_path)
            if source.resolve() != model_path.resolve():
                shutil.copy2(source, model_path)

        if not model_path.exists():
            raise CommandError(
                f"YOLO model missing at {model_path}. Run: python manage.py download_tour_ai_models"
            )

        from apps.tour_ai_agent.vision.local_detector import LocalObjectDetector
        detector = LocalObjectDetector(str(model_path))
        image_path = options["image"]
        temporary = None
        if not image_path:
            temporary = tempfile.TemporaryDirectory(prefix="twinscopes-yolo-test-")
            image_path = str(Path(temporary.name) / "smoke.jpg")
            Image.new("RGB", (640, 640), "white").save(image_path)
        elif not Path(image_path).exists():
            raise CommandError(f"Image not found: {image_path}")

        detections = detector.detect(image_path, confidence_threshold=0.25)
        output = {
            "ok": True,
            "model": str(model_path),
            "device": settings.TOUR_AI_YOLO_DEVICE,
            "image": image_path,
            "detections": [item.dict() for item in detections],
        }
        self.stdout.write(json.dumps(output, ensure_ascii=False, indent=2))
        self.stdout.write(self.style.SUCCESS("YOLO is working correctly."))
        if temporary:
            temporary.cleanup()
