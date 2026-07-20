from __future__ import annotations
from dataclasses import dataclass,asdict
from pathlib import Path
from django.conf import settings
@dataclass(frozen=True)
class Detection:
    label:str; confidence:float; bbox:list[float]
    def dict(self): return asdict(self)
class LocalObjectDetector:
    def __init__(self,model_path=None):
        self.model_path=str(model_path or getattr(settings,'TOUR_AI_YOLO_MODEL_PATH','yolo11n.pt')); self._model=None
    def _load(self):
        if self._model is None:
            from ultralytics import YOLO
            self._model=YOLO(self.model_path)
        return self._model
    def detect(self,image_path,confidence_threshold=.35):
        try: results=self._load().predict(source=str(image_path),conf=confidence_threshold,imgsz=640,verbose=False,device='cpu')
        except Exception: return []
        out=[]
        for result in results:
            if result.boxes is None: continue
            for box in result.boxes:
                cid=int(box.cls.item()); out.append(Detection(str(result.names[cid]),float(box.conf.item()),[float(v) for v in box.xyxy[0].tolist()]))
        return out
