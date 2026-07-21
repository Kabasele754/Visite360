from __future__ import annotations

import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Download and persist the configured Ultralytics YOLO model."

    def add_arguments(self, parser):
        parser.add_argument("--model", default="yolo11n.pt")

    def handle(self, *args, **options):
        from ultralytics import YOLO

        target = Path(
            getattr(settings, "TOUR_AI_YOLO_MODEL_PATH", "/app/model_weights/yolo11n.pt")
        )
        target.parent.mkdir(parents=True, exist_ok=True)

        model_name = options["model"]
        self.stdout.write(f"Loading {model_name}...")
        model = YOLO(model_name)
        source = Path(model.ckpt_path)
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
        self.stdout.write(self.style.SUCCESS(f"Model ready: {target}"))
