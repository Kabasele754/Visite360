from __future__ import annotations

import hashlib
import io
import json
import logging
import math
from typing import Any

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction

from apps.tours.models import SceneObjectCandidate
from apps.vision_ai.models import VisionAnalysis, VisionInsight

logger = logging.getLogger(__name__)

PORTAL_TERMS = {
    "door", "doorway", "entrance", "entry", "exit", "gate", "passage",
    "corridor", "hallway", "stairs", "staircase", "elevator", "lift",
    "archway", "opening", "lobby", "room entrance", "sliding door",
}


def _normalized_label(value: str) -> str:
    return " ".join(str(value or "").lower().replace("_", " ").replace("-", " ").split())


def _is_portal(insight: VisionInsight) -> bool:
    haystack = " ".join(
        _normalized_label(value)
        for value in (
            insight.label,
            insight.title,
            insight.description,
            (insight.attributes or {}).get("category"),
        )
    )
    return any(term in haystack for term in PORTAL_TERMS)


def _bbox_from_region(insight: VisionInsight, width: int, height: int) -> list[float]:
    bbox = list(insight.bbox or [])
    if len(bbox) >= 4:
        values = [float(v) for v in bbox[:4]]
        if max(abs(v) for v in values) <= 1.5:
            # Existing vision geometry uses [x1,y1,x2,y2] for YOLO outputs.
            values = [values[0] * width, values[1] * height, values[2] * width, values[3] * height]
        return values

    polygon = list(insight.polygon or [])
    points: list[tuple[float, float]] = []
    for point in polygon:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            continue
        x, y = float(point[0]), float(point[1])
        if max(abs(x), abs(y)) <= 1.5:
            x, y = x * width, y * height
        points.append((x, y))
    if points:
        xs = [item[0] for item in points]
        ys = [item[1] for item in points]
        return [min(xs), min(ys), max(xs), max(ys)]
    return []


def _safe_crop(image: Image.Image, bbox: list[float], *, padding_ratio: float = 0.10) -> Image.Image | None:
    if len(bbox) < 4:
        return None
    x1, y1, x2, y2 = bbox[:4]
    if x2 < x1:
        x1, x2 = x2, x1
    if y2 < y1:
        y1, y2 = y2, y1
    box_width = max(1.0, x2 - x1)
    box_height = max(1.0, y2 - y1)
    pad_x = box_width * padding_ratio
    pad_y = box_height * padding_ratio
    left = max(0, int(math.floor(x1 - pad_x)))
    top = max(0, int(math.floor(y1 - pad_y)))
    right = min(image.width, int(math.ceil(x2 + pad_x)))
    bottom = min(image.height, int(math.ceil(y2 + pad_y)))
    if right - left < 8 or bottom - top < 8:
        return None
    return image.crop((left, top, right, bottom)).convert("RGB")


def _clarity_metrics(image: Image.Image) -> dict[str, float]:
    working = image.copy()
    working.thumbnail((900, 900), Image.Resampling.LANCZOS)
    gray = np.asarray(working.convert("L"), dtype=np.uint8)
    brightness = float(gray.mean())
    contrast = float(gray.std())
    try:
        import cv2

        sharpness_raw = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    except Exception:
        sharpness_raw = float(np.asarray(working.convert("L").filter(ImageFilter.FIND_EDGES)).var())
    sharpness = max(0.0, min(1.0, math.log1p(max(0.0, sharpness_raw)) / math.log1p(900.0)))
    exposure = max(0.0, min(1.0, 1.0 - abs(brightness - 128.0) / 110.0))
    contrast_score = max(0.0, min(1.0, contrast / 58.0))
    dimension_score = max(0.0, min(1.0, min(image.width, image.height) / 420.0))
    clarity = max(0.0, min(1.0, sharpness * 0.45 + exposure * 0.20 + contrast_score * 0.20 + dimension_score * 0.15))
    return {
        "clarity": clarity,
        "sharpness": sharpness,
        "sharpness_raw": sharpness_raw,
        "exposure": exposure,
        "brightness": brightness,
        "contrast": contrast_score,
        "contrast_raw": contrast,
        "dimension": dimension_score,
    }


def _encode(image: Image.Image, *, enhanced: bool = False) -> bytes:
    output = image.copy()
    output.thumbnail((1100, 1100), Image.Resampling.LANCZOS)
    if enhanced:
        output = ImageOps.autocontrast(output, cutoff=0.8)
        output = ImageEnhance.Contrast(output).enhance(1.12)
        output = ImageEnhance.Sharpness(output).enhance(1.38)
    buffer = io.BytesIO()
    output.save(buffer, "WEBP", quality=84 if enhanced else 82, method=6)
    return buffer.getvalue()


def _fingerprint(insight: VisionInsight, bbox: list[float]) -> str:
    payload = {
        "frame": insight.frame_id,
        "kind": insight.kind,
        "label": _normalized_label(insight.label),
        "bbox": [round(float(value), 2) for value in bbox[:4]],
        "yaw": round(float(insight.yaw or 0), 5),
        "pitch": round(float(insight.pitch or 0), 5),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _build_recommendations(metrics: dict[str, float], confidence: float, crop: Image.Image | None) -> tuple[list[str], list[str]]:
    issues: list[str] = []
    recommendations: list[str] = []
    if crop is None:
        issues.append("crop_unavailable")
        recommendations.append("Re-run scene analysis so Twinscopes can generate an exact visual crop.")
        return issues, recommendations
    if min(crop.size) < 120:
        issues.append("small_object_crop")
        recommendations.append("Capture the panorama at a higher resolution or move closer to this object.")
    if metrics["sharpness"] < 0.38:
        issues.append("soft_object")
        recommendations.append("Use a sharper source panorama; labels and small details are currently difficult to verify.")
    if metrics["exposure"] < 0.48:
        issues.append("object_exposure")
        recommendations.append("Improve local lighting or HDR exposure around this object.")
    if metrics["contrast"] < 0.38:
        issues.append("low_object_contrast")
        recommendations.append("Increase local contrast carefully so the object separates from its background.")
    if confidence < 0.48:
        issues.append("low_detection_confidence")
        recommendations.append("Review this object manually before exposing it to visitors.")
    return issues, recommendations


@transaction.atomic
def synchronize_scene_object_catalog(analysis: VisionAnalysis) -> int:
    if not analysis.scene_id:
        return 0
    scene = analysis.scene
    min_confidence = float(getattr(settings, "TOUR_OBJECT_CATALOG_MIN_CONFIDENCE", 0.25))
    max_candidates = max(1, int(getattr(settings, "TOUR_OBJECT_CATALOG_MAX_CANDIDATES", 90)))

    # Older analyses stay available for audits but are not shown in the active catalogue.
    SceneObjectCandidate.objects.filter(scene=scene).exclude(analysis=analysis).exclude(
        review_status=SceneObjectCandidate.ReviewStatus.APPROVED
    ).update(review_status=SceneObjectCandidate.ReviewStatus.HIDDEN, client_ready=False)

    insights = list(
        analysis.insights.select_related("frame")
        .filter(confidence__gte=min_confidence)
        .order_by("-confidence", "id")[:max_candidates]
    )
    active_fingerprints: set[str] = set()
    created_or_updated = 0

    for insight in insights:
        frame = insight.frame
        crop = None
        bbox: list[float] = []
        if frame and frame.image:
            try:
                frame.image.open("rb")
                try:
                    frame_bytes = frame.image.read()
                finally:
                    frame.image.close()
                with Image.open(io.BytesIO(frame_bytes)) as opened:
                    frame_image = ImageOps.exif_transpose(opened).convert("RGB")
                    frame_image.load()
                bbox = _bbox_from_region(insight, frame_image.width, frame_image.height)
                crop = _safe_crop(frame_image, bbox)
            except Exception:
                logger.warning("Could not build object crop for insight %s", insight.pk, exc_info=True)

        fingerprint = _fingerprint(insight, bbox)
        active_fingerprints.add(fingerprint)
        portal = _is_portal(insight)
        kind = (
            SceneObjectCandidate.Kind.PORTAL
            if portal
            else SceneObjectCandidate.Kind.TEXT
            if insight.kind == VisionInsight.Kind.TEXT
            else SceneObjectCandidate.Kind.OBJECT
        )
        metrics = _clarity_metrics(crop) if crop is not None else {
            "clarity": 0.0,
            "sharpness": 0.0,
            "exposure": 0.0,
            "contrast": 0.0,
            "dimension": 0.0,
            "brightness": 0.0,
            "sharpness_raw": 0.0,
            "contrast_raw": 0.0,
        }
        issues, recommendations = _build_recommendations(metrics, float(insight.confidence or 0), crop)
        quality_score = max(0.0, min(1.0, metrics["clarity"] * 0.62 + float(insight.confidence or 0) * 0.38))
        client_ready = (
            float(insight.confidence or 0) >= float(getattr(settings, "TOUR_OBJECT_CLIENT_READY_MIN_CONFIDENCE", 0.58))
            and metrics["clarity"] >= float(getattr(settings, "TOUR_OBJECT_CLIENT_READY_MIN_CLARITY", 0.46))
            and "crop_unavailable" not in issues
        )
        defaults: dict[str, Any] = {
            "scene": scene,
            "kind": kind,
            "label": (insight.label or kind)[:180],
            "title": (insight.title or insight.label or "Detected object")[:240],
            "description": insight.description or "",
            "category": str((insight.attributes or {}).get("category") or "")[:120],
            "confidence": float(insight.confidence or 0),
            "bbox": bbox,
            "yaw": float(insight.yaw or 0),
            "pitch": float(insight.pitch or 0),
            "clarity_score": metrics["clarity"],
            "quality_score": quality_score,
            "is_navigation_anchor": portal,
            "client_ready": client_ready,
            "issues": issues,
            "recommendations": recommendations,
            "source_providers": insight.source_providers or [],
            "frame": frame,
            "payload": {
                "vision_insight_id": insight.pk,
                "metrics": {key: round(float(value), 5) for key, value in metrics.items()},
                "attributes": insight.attributes or {},
            },
        }
        candidate, created = SceneObjectCandidate.objects.update_or_create(
            analysis=analysis,
            fingerprint=fingerprint,
            defaults=defaults,
        )
        # Preserve explicit human decisions when refreshing the same candidate.
        if not created and candidate.review_status == SceneObjectCandidate.ReviewStatus.HIDDEN:
            candidate.review_status = SceneObjectCandidate.ReviewStatus.SUGGESTED

        if crop is not None:
            if candidate.crop_image:
                try:
                    candidate.crop_image.delete(save=False)
                except Exception:
                    pass
            if candidate.enhanced_crop_image:
                try:
                    candidate.enhanced_crop_image.delete(save=False)
                except Exception:
                    pass
            candidate.crop_image.save(
                f"scene-{scene.pk}-object-{insight.pk}.webp",
                ContentFile(_encode(crop, enhanced=False)),
                save=False,
            )
            candidate.enhanced_crop_image.save(
                f"scene-{scene.pk}-object-{insight.pk}-enhanced.webp",
                ContentFile(_encode(crop, enhanced=True)),
                save=False,
            )
        candidate.save()
        created_or_updated += 1

    SceneObjectCandidate.objects.filter(analysis=analysis).exclude(
        fingerprint__in=active_fingerprints
    ).exclude(review_status=SceneObjectCandidate.ReviewStatus.APPROVED).update(
        review_status=SceneObjectCandidate.ReviewStatus.HIDDEN,
        client_ready=False,
    )
    return created_or_updated
