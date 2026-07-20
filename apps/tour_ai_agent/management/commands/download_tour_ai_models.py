from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Download and validate the local YOLO model used by the Tour AI Agent."

    def add_arguments(self, parser):
        parser.add_argument("--model", default="yolo11n.pt")

    def handle(self, *args, **options):
        from ultralytics import YOLO
        target = Path(getattr(settings, "TOUR_AI_YOLO_MODEL_PATH"))
        target.parent.mkdir(parents=True, exist_ok=True)
        model_name = options["model"]
        self.stdout.write(f"Downloading/loading {model_name}...")
        model = YOLO(model_name)
        source = Path(getattr(model, "ckpt_path", model_name))
        if source.exists() and source.resolve() != target.resolve():
            target.write_bytes(source.read_bytes())
        if not target.exists():
            raise RuntimeError(f"Model was not created at {target}")
        self.stdout.write(self.style.SUCCESS(f"YOLO model ready: {target} ({target.stat().st_size} bytes)"))
