from __future__ import annotations

import io
import importlib.util
import json
import logging
import os
import threading
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from PIL import Image
from django.conf import settings

from apps.ai_core.services.providers import parse_json_object
from apps.ai_core.services.router import AIProviderRouter

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ProviderVisionOutput:
    provider: str
    summary: str = ""
    scene_type: str = ""
    features: list[str] = field(default_factory=list)
    products: list[dict[str, Any]] = field(default_factory=list)
    detections: list[dict[str, Any]] = field(default_factory=list)
    ocr_blocks: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict)


_MODEL_LOCK = threading.Lock()
_YOLO_MODELS: dict[str, Any] = {}
_PADDLE_ENGINES: dict[str, Any] = {}
_PROVIDER_AVAILABILITY_WARNED: set[str] = set()


def _module_available(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, AttributeError, ValueError):
        return False


def _warn_provider_once(provider: str, message: str) -> None:
    if provider in _PROVIDER_AVAILABILITY_WARNED:
        return
    _PROVIDER_AVAILABILITY_WARNED.add(provider)
    logger.warning(message)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_plain(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (list, tuple)):
        return [_to_plain(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _to_plain(item) for key, item in value.items()}
    return value


def _clean_card_text(value: Any, *, max_length: int = 360) -> str:
    """Keep model prose concise and prevent raw JSON from reaching the UI."""
    text = " ".join(str(value or "").replace("```json", " ").replace("```", " ").split())
    if not text:
        return ""
    # A valid card sentence must never contain another JSON payload. Models can
    # occasionally append a second object despite response_mime_type=json.
    for marker in (" {", " [", "\n{", "\n["):
        position = text.find(marker)
        if position > 20:
            text = text[:position].strip()
            break
    if text.startswith(("{", "[")):
        return ""
    if len(text) > max_length:
        text = text[:max_length].rsplit(" ", 1)[0].rstrip(" ,;:-") + "…"
    return text


def _clean_identifier(value: Any, *, max_length: int = 160) -> str:
    return _clean_card_text(value, max_length=max_length).replace(" ", "_").lower().strip("_")


class YOLOVisionProvider:
    name = "yolo"

    def __init__(self):
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError("ultralytics is not installed") from exc
        model_path = str(settings.VISION_YOLO_MODEL)
        with _MODEL_LOCK:
            model = _YOLO_MODELS.get(model_path)
            if model is None:
                model = YOLO(model_path)
                _YOLO_MODELS[model_path] = model
        self.model = model

    def analyze(self, image_bytes: bytes, context: dict[str, Any] | None = None) -> ProviderVisionOutput:
        image = np.asarray(Image.open(io.BytesIO(image_bytes)).convert("RGB"))
        result = self.model.predict(
            image,
            conf=float(getattr(settings, "TOUR_AI_YOLO_CONFIDENCE", 0.30)),
            iou=float(getattr(settings, "TOUR_AI_YOLO_IOU", 0.45)),
            imgsz=int(getattr(settings, "TOUR_AI_YOLO_IMAGE_SIZE", 896)),
            verbose=False,
            device=getattr(settings, "TOUR_AI_YOLO_DEVICE", "cpu"),
        )[0]
        names = result.names
        detections = []
        for local_index, box in enumerate(result.boxes or []):
            cls_id = int(box.cls[0])
            detections.append({
                "local_index": local_index,
                "label": names.get(cls_id, str(cls_id)),
                "confidence": float(box.conf[0]),
                "bbox": [float(value) for value in box.xyxy[0].tolist()],
            })
        return ProviderVisionOutput(
            provider=self.name,
            detections=detections,
            features=sorted({item["label"] for item in detections}),
            confidence=max([item["confidence"] for item in detections], default=0.0),
            raw={"count": len(detections)},
        )


class PaddleOCRProvider:
    """PaddleOCR 3.x-first adapter with compatibility for legacy 2.x APIs."""

    name = "paddleocr"

    def __init__(self):
        # PaddleOCR is only the high-level pipeline. Its actual inference
        # runtime is imported as ``paddle`` from the separate paddlepaddle
        # package. Check it before constructing PaddleOCR so a missing runtime
        # does not trigger model downloads followed by a long traceback.
        if not _module_available("paddle"):
            raise RuntimeError(
                "PaddleOCR runtime unavailable: install the paddlepaddle package "
                "in the active Python environment."
            )
        if not _module_available("paddleocr"):
            raise RuntimeError("PaddleOCR package is not installed.")

        # Avoid the PaddleX model-hoster connectivity probe during application
        # startup. Required model files are still downloaded on first use when
        # they are not already cached.
        os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:
            raise RuntimeError("PaddleOCR package is not installed.") from exc

        language = str(settings.VISION_PADDLEOCR_LANG)
        engine_key = f"{language}:{getattr(settings, 'VISION_PADDLEOCR_DEVICE', 'cpu')}"
        with _MODEL_LOCK:
            engine = _PADDLE_ENGINES.get(engine_key)
            if engine is None:
                try:
                    engine = PaddleOCR(
                        lang=language,
                        use_doc_orientation_classify=False,
                        use_doc_unwarping=False,
                        use_textline_orientation=True,
                        device=getattr(settings, "VISION_PADDLEOCR_DEVICE", None),
                    )
                except (TypeError, ValueError):
                    # PaddleOCR 2.x compatibility.
                    engine = PaddleOCR(use_angle_cls=True, lang=language, show_log=False)
                _PADDLE_ENGINES[engine_key] = engine
        self.engine = engine

    @staticmethod
    def _parse_v3_result(results: Any) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = []
        for result in results or []:
            payload: Any = None
            candidate = getattr(result, "json", None)
            if callable(candidate):
                try:
                    payload = candidate()
                except Exception:
                    payload = None
            elif candidate is not None:
                payload = candidate
            if payload is None:
                payload = getattr(result, "res", None) or getattr(result, "data", None)
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except json.JSONDecodeError:
                    payload = None
            if not isinstance(payload, dict):
                continue
            payload = payload.get("res", payload)
            texts = payload.get("rec_texts") or payload.get("texts") or []
            scores = payload.get("rec_scores") or payload.get("scores") or []
            polygons = (
                payload.get("rec_polys")
                or payload.get("dt_polys")
                or payload.get("polys")
                or []
            )
            for index, text in enumerate(texts):
                if not str(text).strip():
                    continue
                blocks.append({
                    "local_index": len(blocks),
                    "text": str(text).strip(),
                    "confidence": _safe_float(scores[index] if index < len(scores) else 0.0),
                    "polygon": _to_plain(polygons[index] if index < len(polygons) else []),
                })
        return blocks

    @staticmethod
    def _parse_legacy_result(result: Any) -> list[dict[str, Any]]:
        blocks = []
        for line_group in result or []:
            for polygon, content in line_group or []:
                text, confidence = content
                if not str(text).strip():
                    continue
                blocks.append({
                    "local_index": len(blocks),
                    "text": str(text).strip(),
                    "confidence": _safe_float(confidence),
                    "polygon": _to_plain(polygon),
                })
        return blocks

    def analyze(self, image_bytes: bytes, context: dict[str, Any] | None = None) -> ProviderVisionOutput:
        image = np.asarray(Image.open(io.BytesIO(image_bytes)).convert("RGB"))
        blocks: list[dict[str, Any]] = []
        predict = getattr(self.engine, "predict", None)
        if callable(predict):
            try:
                blocks = self._parse_v3_result(predict(image))
            except Exception:
                logger.debug("PaddleOCR 3.x predict failed; trying legacy OCR API", exc_info=True)
        if not blocks:
            legacy = getattr(self.engine, "ocr", None)
            if callable(legacy):
                try:
                    blocks = self._parse_legacy_result(legacy(image, cls=True))
                except TypeError:
                    blocks = self._parse_legacy_result(legacy(image))
        return ProviderVisionOutput(
            provider=self.name,
            ocr_blocks=blocks,
            summary="\n".join(block["text"] for block in blocks),
            confidence=(sum(block["confidence"] for block in blocks) / len(blocks)) if blocks else 0,
            raw={"count": len(blocks)},
        )


class Florence2Provider:
    name = "florence2"

    def __init__(self):
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoProcessor
        except ImportError as exc:
            raise RuntimeError("transformers/torch are not installed for Florence-2") from exc
        self.torch = torch
        self.processor = AutoProcessor.from_pretrained(settings.VISION_FLORENCE_MODEL, trust_remote_code=True)
        self.model = AutoModelForCausalLM.from_pretrained(settings.VISION_FLORENCE_MODEL, trust_remote_code=True)
        self.model.eval()

    def analyze(self, image_bytes: bytes, context: dict[str, Any] | None = None) -> ProviderVisionOutput:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        task = "<MORE_DETAILED_CAPTION>"
        inputs = self.processor(text=task, images=image, return_tensors="pt")
        with self.torch.inference_mode():
            generated = self.model.generate(**inputs, max_new_tokens=512, do_sample=False)
        text = self.processor.batch_decode(generated, skip_special_tokens=False)[0]
        parsed = self.processor.post_process_generation(text, task=task, image_size=image.size)
        summary = str(parsed.get(task, parsed)) if isinstance(parsed, dict) else str(parsed)
        return ProviderVisionOutput(provider=self.name, summary=summary, confidence=0.75, raw={"parsed": _to_plain(parsed)})


class MultimodalLLMProvider:
    def __init__(self, provider: str, organization=None):
        self.name = provider
        self.router = AIProviderRouter(organization=organization)

    def analyze(self, image_bytes: bytes, context: dict[str, Any] | None = None) -> ProviderVisionOutput:
        local_context = context or {}
        prompt = """You are the semantic fusion stage of an advanced 360° computer-vision system.
Inspect this perspective image and use the supplied YOLO/PaddleOCR evidence. Return ONLY strict JSON using this schema:
{
  "scene_type": "short snake_case value",
  "summary": "one precise, customer-friendly sentence",
  "features": ["visibly supported feature"],
  "detections": [
    {
      "local_index": 0,
      "label": "generic object label",
      "title": "short human-readable title",
      "description": "one factual sentence about appearance or likely function",
      "category": "generic category",
      "color": "visible color or empty",
      "material": "visible material or empty",
      "condition": "visible condition or empty",
      "confidence": 0.0
    }
  ],
  "visible_text": [
    {
      "local_index": 0,
      "text": "exact OCR text",
      "kind": "sign|label|price|instruction|brand_text|other",
      "meaning": "brief explanation without invention",
      "language": "language code or empty",
      "confidence": 0.0
    }
  ],
  "products": [],
  "safety_observations": [],
  "accessibility_observations": [],
  "confidence": 0.0
}
Rules:
- Match local_index to the supplied local evidence whenever possible.
- YOLO boxes are evidence of generic object classes, not catalogue products.
- OCR text must stay exact; never correct it silently. Put interpretation in meaning.
- Do not invent brands, models, prices, stock, services, URLs, identities or hidden details.
- Omit uncertain attributes rather than guessing.
- Keep descriptions short enough for an interactive visual card.
- Treat the extracted perspective as upright; do not mention panorama projection, mirroring, upside-down orientation or camera artifacts unless the supplied evidence explicitly proves it.

LOCAL EVIDENCE:
""" + json.dumps(local_context, ensure_ascii=False, default=str)
        result = self.router.analyze_image(image_bytes=image_bytes, prompt=prompt, provider=self.name)
        parsed = parse_json_object(result.text)

        visible_text = parsed.get("visible_text", []) or []
        ocr_blocks: list[dict[str, Any]] = []
        for index, value in enumerate(visible_text):
            if isinstance(value, dict):
                text = str(value.get("text", "")).strip()
                if text:
                    ocr_blocks.append({
                        "local_index": value.get("local_index", index),
                        "text": text,
                        "confidence": _safe_float(value.get("confidence"), 0.7),
                        "metadata": {
                            "kind": value.get("kind", "other"),
                            "meaning": value.get("meaning", ""),
                            "language": value.get("language", ""),
                        },
                    })
            elif str(value).strip():
                ocr_blocks.append({"local_index": index, "text": str(value).strip(), "confidence": 0.7})

        detections = []
        for index, item in enumerate(parsed.get("detections", []) or []):
            if not isinstance(item, dict):
                continue
            cleaned = {
                **item,
                "local_index": item.get("local_index", index),
                "label": _clean_identifier(item.get("label") or "object", max_length=120) or "object",
                "title": _clean_card_text(item.get("title"), max_length=180),
                "description": _clean_card_text(item.get("description"), max_length=320),
                "category": _clean_card_text(item.get("category"), max_length=100),
                "color": _clean_card_text(item.get("color"), max_length=80),
                "material": _clean_card_text(item.get("material"), max_length=80),
                "condition": _clean_card_text(item.get("condition"), max_length=80),
                "confidence": _safe_float(item.get("confidence"), 0.7),
            }
            detections.append(cleaned)

        confidence = max(0.0, min(1.0, _safe_float(parsed.get("confidence"), 0.7)))
        return ProviderVisionOutput(
            provider=self.name,
            summary=_clean_card_text(parsed.get("summary"), max_length=320),
            scene_type=_clean_identifier(parsed.get("scene_type"), max_length=120),
            features=[str(value) for value in parsed.get("features", []) if value],
            products=[item for item in parsed.get("products", []) if isinstance(item, dict)],
            detections=detections,
            ocr_blocks=ocr_blocks,
            confidence=confidence,
            raw=parsed,
        )


    def analyze_target(self, image_bytes: bytes, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Identify only the item intersecting the center reticle of a crop."""
        local_context = context or {}
        prompt = """You are the point-inspection stage of Twinscopes computer vision.
The image is either (a) one EXACT USER SELECTION captured directly from the panorama viewer, or (b) two panels named CONTEXT and DETAIL - TARGET. When it is an EXACT USER SELECTION, every pixel outside the user-drawn rectangle has already been removed: identify only the principal distinct object, product package, sign, or readable text inside that framed image. When two panels are present, identify only the item intersecting the cyan center reticle in DETAIL and use CONTEXT only for orientation.
Return ONLY strict JSON:
{
  "found": true,
  "label": "generic_snake_case_label",
  "title": "short human title",
  "description": "one factual customer-friendly sentence about this exact item",
  "category": "generic category or empty",
  "color": "visible color or empty",
  "material": "visible material or empty",
  "condition": "visible condition or empty",
  "visible_text": "exact text on this item or empty",
  "confidence": 0.0
}
Rules:
- Inspect the entire exact crop carefully before deciding that nothing is present. Small products, packages, labels, controls, furniture details, medical equipment, signs and readable text all count as distinct targets when visibly supported.
- Set found=false only when the exact selection is genuinely empty, too blurred/occluded to verify, or when no distinct item intersects the reticle in two-panel mode.
- The context may say inspection_pass=enhanced_rescan. That image contains the same user-selected pixels with contrast/sharpness enhancement; do not treat enhancement as new visual evidence outside the crop.
- In exact-selection mode, prefer the object occupying the center or largest meaningful part of the crop; never infer anything outside the crop.
- Use OCR evidence only for text visibly present in the selected pixels, and copy visible_text exactly when readable.
- Never return a description of the whole room, aisle, shelf, or panorama unless that structure itself clearly fills the exact selection or reticle.
- Never invent brand, product name, price, stock, URL, service, or hidden detail.
- Do not return markdown or a second JSON object.
- Treat the crop as upright; do not describe panorama projection, mirroring or an upside-down camera view.

LOCAL DETECTION EVIDENCE:
""" + json.dumps(local_context, ensure_ascii=False, default=str)
        result = self.router.analyze_image(image_bytes=image_bytes, prompt=prompt, provider=self.name)
        parsed = parse_json_object(result.text)
        raw_found = parsed.get("found")
        found = raw_found is True or str(raw_found).strip().lower() in {"true", "1", "yes"}
        confidence = max(0.0, min(1.0, _safe_float(parsed.get("confidence"), 0.0)))
        title = _clean_card_text(parsed.get("title"), max_length=180)
        description = _clean_card_text(parsed.get("description"), max_length=320)
        label = _clean_identifier(parsed.get("label"), max_length=120)
        # Reject scene-level leakage even when a provider ignored the prompt.
        scene_terms = ("aisle featuring", "view of a", "scene featuring", "well-stocked", "interior view", "panoramic view")
        structural_labels = {"aisle", "shelf", "display_shelf", "display_rack", "counter", "wall", "floor", "ceiling"}
        if (description or title) and any(
            term in f"{title} {description}".lower() for term in scene_terms
        ) and label not in structural_labels:
            found = False
        return {
            "found": found and bool(label or title),
            "label": label or "object",
            "title": title,
            "description": description,
            "category": _clean_card_text(parsed.get("category"), max_length=100),
            "color": _clean_card_text(parsed.get("color"), max_length=80),
            "material": _clean_card_text(parsed.get("material"), max_length=80),
            "condition": _clean_card_text(parsed.get("condition"), max_length=80),
            "visible_text": _clean_card_text(parsed.get("visible_text"), max_length=180),
            "confidence": confidence,
            "provider": self.name,
        }


def enabled_provider_names(requested: list[str] | None = None) -> list[str]:
    """Return enabled providers that also have the required credentials.

    Local CV engines are allowed when their feature flag is enabled; their
    package/model availability is checked when the provider is built so a
    partial analysis can still succeed. Cloud providers are filtered here to
    avoid filling logs with predictable credential errors for every frame.
    """
    gemini_configured = bool(
        (
            getattr(settings, "GOOGLE_GENAI_USE_VERTEXAI", False)
            and getattr(settings, "GOOGLE_CLOUD_PROJECT", "")
            and getattr(settings, "GOOGLE_CLOUD_LOCATION", "")
        )
        or getattr(settings, "GEMINI_API_KEY", "")
    )
    openai_configured = bool(getattr(settings, "OPENAI_API_KEY", ""))
    paddle_enabled = bool(getattr(settings, "VISION_ENABLE_PADDLEOCR", False))
    paddle_runtime_ready = _module_available("paddle") and _module_available("paddleocr")
    if paddle_enabled and not paddle_runtime_ready:
        _warn_provider_once(
            "paddleocr",
            "PaddleOCR is enabled but its paddlepaddle runtime is unavailable; "
            "continuing with YOLO and semantic vision without local OCR.",
        )

    flags = {
        "yolo": bool(getattr(settings, "VISION_ENABLE_YOLO", False)),
        "florence2": bool(getattr(settings, "VISION_ENABLE_FLORENCE2", False)),
        "paddleocr": paddle_enabled and paddle_runtime_ready,
        "gemini": bool(getattr(settings, "VISION_ENABLE_GEMINI", False)) and gemini_configured,
        "openai": bool(getattr(settings, "VISION_ENABLE_OPENAI", False)) and openai_configured,
    }
    names = requested or list(flags)
    return [name for name in names if flags.get(name, False)]


def semantic_provider_order(enabled_names: list[str]) -> list[str]:
    primary = str(getattr(settings, "VISION_PRIMARY_SEMANTIC_PROVIDER", "gemini")).lower()
    fallback = str(getattr(settings, "VISION_FALLBACK_SEMANTIC_PROVIDER", "openai")).lower()
    ordered: list[str] = []
    for name in (primary, fallback, "gemini", "openai"):
        if name in enabled_names and name not in ordered:
            ordered.append(name)
    return ordered


def build_provider(name: str, *, organization=None):
    if name == "yolo":
        return YOLOVisionProvider()
    if name == "paddleocr":
        return PaddleOCRProvider()
    if name == "florence2":
        return Florence2Provider()
    if name in {"gemini", "openai"}:
        return MultimodalLLMProvider(name, organization=organization)
    raise RuntimeError(f"Unknown vision provider: {name}")
