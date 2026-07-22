from __future__ import annotations

import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Download and persist the configured Ultralytics YOLO model."

    def add_arguments(self, parser):
        parser.add_argument("--model", default=getattr(settings, "TOUR_AI_YOLO_MODEL_NAME", "yolo11n.pt"))

    def handle(self, *args, **options):
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise CommandError(
                "Ultralytics is not installed. Run: pip install ultralytics"
            ) from exc

        target = Path(settings.TOUR_AI_YOLO_MODEL_PATH).expanduser().resolve()
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise CommandError(
                f"Cannot create the YOLO model directory: {target.parent}. "
                "In local development, remove TOUR_AI_YOLO_MODEL_PATH=/app/... "
                "from .env or use a path inside the project."
            ) from exc

        model_name = options["model"]
        self.stdout.write(f"Runtime: {'Docker' if getattr(settings, 'RUNNING_IN_DOCKER', False) else 'local'}")
        self.stdout.write(f"Target: {target}")
        self.stdout.write(f"Loading {model_name}...")

        model = YOLO(model_name)
        source = Path(model.ckpt_path).expanduser().resolve()
        if source != target:
            shutil.copy2(source, target)

        self.stdout.write(self.style.SUCCESS(f"Model ready: {target}"))
