from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Detection:
    label: str
    confidence: float
    bbox: list[float]

    def dict(self) -> dict:
        return asdict(self)


class LocalObjectDetector:
    def __init__(self, model_path: str | None = None) -> None:
        default_path = getattr(
            settings,
            "TOUR_AI_YOLO_MODEL_PATH",
            "/app/model_weights/yolo11n.pt",
        )
        self.model_path = str(model_path or default_path)
        self.device = getattr(settings, "TOUR_AI_YOLO_DEVICE", "cpu")
        self.imgsz = int(getattr(settings, "TOUR_AI_YOLO_IMAGE_SIZE", 640))
        self._model = None

    @property
    def enabled(self) -> bool:
        return bool(getattr(settings, "AI_ENABLE_ULTRALYTICS", True))

    def _load(self):
        if not self.enabled:
            raise RuntimeError("Ultralytics is disabled.")
        if self._model is None:
            from ultralytics import YOLO

            path = Path(self.model_path)
            if not path.exists():
                raise FileNotFoundError(
                    f"YOLO model not found at {path}. Run: "
                    "python manage.py download_tour_ai_models"
                )
            self._model = YOLO(str(path))
        return self._model

    def detect(self, image_path: str, confidence_threshold: float | None = None) -> list[Detection]:
        threshold = float(
            confidence_threshold
            if confidence_threshold is not None
            else getattr(settings, "TOUR_AI_YOLO_CONFIDENCE", 0.35)
        )
        try:
            results = self._load().predict(
                source=str(image_path),
                conf=threshold,
                imgsz=self.imgsz,
                verbose=False,
                device=self.device,
            )
        except Exception:
            logger.exception("Local YOLO detection failed")
            return []

        detections: list[Detection] = []
        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                class_id = int(box.cls.item())
                detections.append(
                    Detection(
                        label=str(result.names[class_id]),
                        confidence=float(box.conf.item()),
                        bbox=[float(value) for value in box.xyxy[0].tolist()],
                    )
                )
        return detections
