from __future__ import annotations

import io
import math
from typing import Any

from PIL import Image
from django.conf import settings
from django.core import signing
from django.db import transaction
from django.urls import reverse

from apps.vision_ai.models import OCRTextBlock, VisionAnalysis, VisionDetection, VisionInsight
from apps.vision_ai.services.geometry import (
    angular_distance,
    panorama_to_frame_pixel,
    point_in_bbox,
    point_in_polygon,
    region_center_and_area,
    region_to_angular_geometry,
)

CROP_SIGNING_SALT = "twinscopes.vision.crop.v1"


def _humanize(label: str) -> str:
    return str(label or "Object").replace("_", " ").replace("-", " ").strip().title()


def _card_text(value: Any, *, max_length: int = 360) -> str:
    """Normalize UI prose and remove accidental JSON/model payloads."""
    text = " ".join(str(value or "").replace("```json", " ").replace("```", " ").split())
    if not text or text.startswith(("{", "[")):
        return ""
    for marker in (" {", " ["):
        position = text.find(marker)
        if position > 20:
            text = text[:position].strip()
            break
    if len(text) > max_length:
        text = text[:max_length].rsplit(" ", 1)[0].rstrip(" ,;:-") + "…"
    return text


def clean_scene_summary(value: Any) -> str:
    return _card_text(value, max_length=360)


def _safe_description(label: str, attributes: dict[str, Any]) -> str:
    description = _card_text(attributes.get("description"), max_length=320)
    if description:
        return description
    visible_bits = [
        str(attributes.get(key) or "").strip()
        for key in ("color", "material", "condition")
        if str(attributes.get(key) or "").strip()
    ]
    if visible_bits:
        return f"Visible {_humanize(label).lower()} with " + ", ".join(visible_bits) + "."
    return f"A {_humanize(label).lower()} detected in this part of the 360° scene."


def _semantic_detection_lookup(analysis: VisionAnalysis) -> dict[tuple[int, int], dict[str, Any]]:
    lookup: dict[tuple[int, int], dict[str, Any]] = {}
    providers = analysis.raw_results or {}
    for provider_name in ("gemini", "openai"):
        provider = providers.get(provider_name) or {}
        frames = (provider.get("raw") or {}).get("frames") if isinstance(provider, dict) else None
        if not isinstance(frames, list):
            continue
        for item in frames:
            if not isinstance(item, dict):
                continue
            frame_index = int(item.get("frame_index", -1))
            raw = item.get("raw") or {}
            for semantic in raw.get("detections", []) or []:
                if not isinstance(semantic, dict):
                    continue
                try:
                    local_index = int(semantic.get("local_index"))
                except (TypeError, ValueError):
                    continue
                lookup[(frame_index, local_index)] = {**semantic, "semantic_provider": provider_name}
    return lookup


def _semantic_text_lookup(analysis: VisionAnalysis) -> dict[tuple[int, int], dict[str, Any]]:
    lookup: dict[tuple[int, int], dict[str, Any]] = {}
    providers = analysis.raw_results or {}
    for provider_name in ("gemini", "openai"):
        provider = providers.get(provider_name) or {}
        frames = (provider.get("raw") or {}).get("frames") if isinstance(provider, dict) else None
        if not isinstance(frames, list):
            continue
        for item in frames:
            if not isinstance(item, dict):
                continue
            frame_index = int(item.get("frame_index", -1))
            raw = item.get("raw") or {}
            for semantic in raw.get("visible_text", []) or []:
                if not isinstance(semantic, dict):
                    continue
                try:
                    local_index = int(semantic.get("local_index"))
                except (TypeError, ValueError):
                    continue
                lookup[(frame_index, local_index)] = {**semantic, "semantic_provider": provider_name}
    return lookup


@transaction.atomic
def rebuild_insights(analysis: VisionAnalysis) -> int:
    analysis.insights.all().delete()
    min_confidence = float(getattr(settings, "VISION_INSIGHT_MIN_CONFIDENCE", 0.25))
    detection_semantics = _semantic_detection_lookup(analysis)
    text_semantics = _semantic_text_lookup(analysis)
    insights: list[VisionInsight] = []

    detections = (
        VisionDetection.objects.filter(analysis=analysis, provider="yolo")
        .select_related("frame")
        .order_by("frame__frame_index", "id")
    )
    per_frame_detection_index: dict[int, int] = {}
    for detection in detections:
        if detection.confidence < min_confidence or not detection.frame_id:
            continue
        frame_index = detection.frame.frame_index
        fallback_index = per_frame_detection_index.get(frame_index, 0)
        try:
            local_index = int((detection.attributes or {}).get("local_index", fallback_index))
        except (TypeError, ValueError):
            local_index = fallback_index
        per_frame_detection_index[frame_index] = fallback_index + 1
        semantic = detection_semantics.get((frame_index, local_index), {})
        frame_meta = detection.frame.metadata or {}
        yaw, pitch, angular_radius = region_to_angular_geometry(
            bbox=detection.bbox,
            polygon=None,
            width=float(frame_meta.get("width") or 896),
            height=float(frame_meta.get("height") or 896),
            frame_yaw_degrees=detection.frame.yaw,
            frame_pitch_degrees=detection.frame.pitch,
            fov_degrees=float(frame_meta.get("fov") or 82),
        )
        attributes = {
            **(detection.attributes or {}),
            **{key: value for key, value in semantic.items() if key not in {"local_index", "label", "confidence"}},
        }
        providers = ["yolo"]
        if semantic.get("semantic_provider"):
            providers.append(semantic["semantic_provider"])
        title = _card_text(semantic.get("title"), max_length=180) or _humanize(detection.label)
        insights.append(VisionInsight(
            analysis=analysis,
            frame=detection.frame,
            kind=VisionInsight.Kind.OBJECT,
            label=detection.label,
            title=title[:240],
            description=_safe_description(detection.label, attributes),
            confidence=max(float(detection.confidence), float(semantic.get("confidence") or 0)),
            bbox=detection.bbox,
            yaw=yaw,
            pitch=pitch,
            angular_radius=angular_radius,
            source_providers=providers,
            attributes=attributes,
        ))

    ocr_blocks = (
        OCRTextBlock.objects.filter(analysis=analysis)
        .select_related("frame")
        .order_by("frame__frame_index", "id")
    )
    per_frame_text_index: dict[int, int] = {}
    for block in ocr_blocks:
        if block.confidence < min_confidence or not block.frame_id or not block.text.strip():
            continue
        frame_index = block.frame.frame_index
        fallback_index = per_frame_text_index.get(frame_index, 0)
        try:
            local_index = int((block.metadata or {}).get("local_index", fallback_index))
        except (TypeError, ValueError):
            local_index = fallback_index
        per_frame_text_index[frame_index] = fallback_index + 1
        semantic = text_semantics.get((frame_index, local_index), {})
        frame_meta = block.frame.metadata or {}
        yaw, pitch, angular_radius = region_to_angular_geometry(
            bbox=None,
            polygon=block.polygon,
            width=float(frame_meta.get("width") or 896),
            height=float(frame_meta.get("height") or 896),
            frame_yaw_degrees=block.frame.yaw,
            frame_pitch_degrees=block.frame.pitch,
            fov_degrees=float(frame_meta.get("fov") or 82),
        )
        metadata = {**(block.metadata or {}), **semantic}
        meaning = _card_text(metadata.get("meaning"), max_length=260)
        kind = str(metadata.get("kind") or "text").replace("_", " ").title()
        providers = ["paddleocr"]
        if semantic.get("semantic_provider"):
            providers.append(semantic["semantic_provider"])
        description = meaning or f"Text detected in the scene ({kind.lower()})."
        insights.append(VisionInsight(
            analysis=analysis,
            frame=block.frame,
            kind=VisionInsight.Kind.TEXT,
            label=str(metadata.get("kind") or "text"),
            title=block.text.strip()[:240],
            description=description,
            confidence=max(float(block.confidence), float(semantic.get("confidence") or 0)),
            polygon=block.polygon,
            yaw=yaw,
            pitch=pitch,
            angular_radius=max(angular_radius, math.radians(4.5)),
            source_providers=providers,
            attributes={
                **metadata,
                "exact_text": block.text.strip(),
                "language": metadata.get("language") or block.language,
            },
        ))

    if insights:
        VisionInsight.objects.bulk_create(insights, batch_size=500)
    return len(insights)


def latest_scene_analysis(scene) -> VisionAnalysis | None:
    return (
        VisionAnalysis.objects.filter(
            scene=scene,
            status__in=[VisionAnalysis.Status.SUCCEEDED, VisionAnalysis.Status.PARTIAL],
        )
        .prefetch_related("insights__frame")
        .order_by("-finished_at", "-created_at")
        .first()
    )


def find_point_insight(
    analysis: VisionAnalysis,
    *,
    yaw: float,
    pitch: float,
) -> tuple[VisionInsight | None, float | None]:
    """Select the visual region actually intersecting the clicked point.

    The previous implementation compared only angular centers and generous
    radii. Overlapping 360 frames could therefore make one large shelf/scene
    insight capture almost every click. We now project the panorama click back
    into each source perspective frame and test its real bbox/polygon.
    """
    exact_hits: list[tuple[tuple[float, ...], VisionInsight, float]] = []
    near_hits: list[tuple[tuple[float, ...], VisionInsight, float]] = []
    legacy_hits: list[tuple[tuple[float, ...], VisionInsight, float]] = []
    pixel_padding_ratio = float(getattr(settings, "VISION_POINT_PIXEL_PADDING_RATIO", 0.012))
    near_padding_ratio = float(getattr(settings, "VISION_POINT_NEAR_PADDING_RATIO", 0.035))
    legacy_max = math.radians(float(getattr(settings, "VISION_POINT_LEGACY_MAX_DISTANCE_DEGREES", 5.0)))

    for insight in analysis.insights.all():
        distance = angular_distance(yaw, pitch, insight.yaw, insight.pitch)
        frame = insight.frame
        frame_meta = (frame.metadata or {}) if frame else {}
        width = float(frame_meta.get("width") or 0)
        height = float(frame_meta.get("height") or 0)
        fov = float(frame_meta.get("fov") or 82)
        has_region = bool(insight.bbox or insight.polygon)

        if frame and width > 0 and height > 0 and has_region:
            projected = panorama_to_frame_pixel(
                yaw=yaw,
                pitch=pitch,
                width=width,
                height=height,
                frame_yaw_degrees=frame.yaw,
                frame_pitch_degrees=frame.pitch,
                fov_degrees=fov,
            )
            if projected is None:
                continue
            x, y = projected
            base = min(width, height)
            exact_padding = max(2.0, base * pixel_padding_ratio)
            near_padding = max(8.0, base * near_padding_ratio)
            bbox = list(insight.bbox or [])
            if len(bbox) >= 4 and max(abs(float(value)) for value in bbox[:4]) <= 1.5:
                bbox = [
                    float(bbox[0]) * width, float(bbox[1]) * height,
                    float(bbox[2]) * width, float(bbox[3]) * height,
                ]
            polygon = list(insight.polygon or [])
            polygon_flat = [
                abs(float(coordinate))
                for point in polygon
                if isinstance(point, (list, tuple)) and len(point) >= 2
                for coordinate in point[:2]
            ]
            if polygon_flat and max(polygon_flat) <= 1.5:
                polygon = [
                    [float(point[0]) * width, float(point[1]) * height]
                    for point in polygon
                    if isinstance(point, (list, tuple)) and len(point) >= 2
                ]
            exact = (
                point_in_bbox(x, y, bbox, padding=exact_padding)
                if bbox
                else point_in_polygon(x, y, polygon, padding=exact_padding)
            )
            near = (
                point_in_bbox(x, y, bbox, padding=near_padding)
                if bbox
                else point_in_polygon(x, y, polygon, padding=near_padding)
            )
            cx, cy, area = region_center_and_area(
                bbox=bbox, polygon=polygon, width=width, height=height
            )
            center_distance = math.hypot(x - cx, y - cy) / max(base, 1.0)
            area_ratio = min(1.0, area / max(width * height, 1.0))
            kind_priority = 0.0 if insight.kind == VisionInsight.Kind.TEXT else 0.15
            confidence_penalty = 1.0 - min(max(float(insight.confidence or 0), 0.0), 1.0)
            # Prefer the tightest exact region under the point. This is crucial
            # when a product sits inside a larger shelf/display bounding box.
            score = (kind_priority, area_ratio, center_distance, confidence_penalty, float(insight.id))
            if exact:
                exact_hits.append((score, insight, distance))
            elif near and distance <= math.radians(5.5):
                near_hits.append((score, insight, distance))
            continue

        # Compatibility for old manually-created insights without frame geometry.
        if distance <= min(legacy_max, max(float(insight.angular_radius or 0), math.radians(2.5))):
            score = (distance, 1.0 - min(float(insight.confidence or 0), 1.0), float(insight.id))
            legacy_hits.append((score, insight, distance))

    if exact_hits:
        _, insight, distance = min(exact_hits, key=lambda item: item[0])
        return insight, distance
    if near_hits:
        _, insight, distance = min(near_hits, key=lambda item: item[0])
        return insight, distance
    if legacy_hits:
        _, insight, distance = min(legacy_hits, key=lambda item: item[0])
        return insight, distance
    return None, None


def insight_requires_point_refinement(insight: VisionInsight) -> bool:
    """Return True when a broad region should be inspected more precisely."""
    if (insight.attributes or {}).get("origin") == "point_inspection":
        return False
    if insight.kind == VisionInsight.Kind.TEXT:
        return False
    if insight.kind == VisionInsight.Kind.AREA:
        return True
    providers = {str(value).lower() for value in (insight.source_providers or [])}
    has_semantic_provider = bool(providers & {"gemini", "openai", "florence2"})
    if bool(getattr(settings, "VISION_POINT_REFINE_LOCAL_ONLY", True)) and not has_semantic_provider:
        return True
    if float(insight.confidence or 0) < float(
        getattr(settings, "VISION_POINT_REFINE_BELOW_CONFIDENCE", 0.55)
    ):
        return True
    label = str(insight.label or "").lower().replace("-", "_").replace(" ", "_")
    broad_labels = {
        "aisle", "room", "store", "shop", "shelf", "shelving", "display",
        "display_shelf", "display_rack", "rack", "counter", "wall", "floor",
        "ceiling", "cabinet", "bookcase", "refrigerator", "table",
    }
    frame = insight.frame
    if frame and (insight.bbox or insight.polygon):
        meta = frame.metadata or {}
        width = float(meta.get("width") or 0)
        height = float(meta.get("height") or 0)
        if width > 0 and height > 0:
            _, _, area = region_center_and_area(
                bbox=insight.bbox, polygon=insight.polygon, width=width, height=height
            )
            area_ratio = area / max(width * height, 1.0)
            if area_ratio >= float(getattr(settings, "VISION_POINT_REFINEMENT_AREA_RATIO", 0.16)):
                return True
    return label in broad_labels


def build_crop_token(insight: VisionInsight, *, tour_id: int) -> str:
    return signing.dumps(
        {"insight_id": insight.id, "tour_id": int(tour_id)},
        salt=CROP_SIGNING_SALT,
        compress=True,
    )


def build_crop_url(request, insight: VisionInsight, *, tour_id: int) -> str:
    token = build_crop_token(insight, tour_id=tour_id)
    path = reverse("tour_ai_agent:vision-crop", kwargs={"token": token})
    return request.build_absolute_uri(path)


def crop_insight_image(insight: VisionInsight) -> tuple[bytes, str]:
    if not insight.frame_id or not insight.frame.image:
        raise FileNotFoundError("The insight frame image is unavailable")
    insight.frame.image.open("rb")
    try:
        image = Image.open(insight.frame.image).convert("RGB")
        width, height = image.size
        coordinates: list[float] = []
        if insight.bbox and len(insight.bbox) >= 4:
            coordinates = [float(value) for value in insight.bbox[:4]]
        elif insight.polygon:
            xs = [float(point[0]) for point in insight.polygon if isinstance(point, (list, tuple)) and len(point) >= 2]
            ys = [float(point[1]) for point in insight.polygon if isinstance(point, (list, tuple)) and len(point) >= 2]
            if xs and ys:
                coordinates = [min(xs), min(ys), max(xs), max(ys)]
        if not coordinates:
            coordinates = [0, 0, width, height]
        x1, y1, x2, y2 = coordinates
        # Accept both pixel and normalized [0, 1] coordinates.
        if max(abs(x1), abs(x2)) <= 1.5 and max(abs(y1), abs(y2)) <= 1.5:
            x1, x2 = x1 * width, x2 * width
            y1, y2 = y1 * height, y2 * height
        box_width = max(1.0, x2 - x1)
        box_height = max(1.0, y2 - y1)
        padding = max(18.0, min(max(box_width, box_height) * 0.28, 120.0))
        crop_box = (
            max(0, int(x1 - padding)),
            max(0, int(y1 - padding)),
            min(width, int(x2 + padding)),
            min(height, int(y2 + padding)),
        )
        crop = image.crop(crop_box)
        crop.thumbnail((960, 720), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        crop.save(buffer, format="JPEG", quality=88, optimize=True)
        return buffer.getvalue(), "image/jpeg"
    finally:
        insight.frame.image.close()


def serialize_insight(request, insight: VisionInsight, *, tour_id: int, distance: float | None = None) -> dict[str, Any]:
    product = insight.related_product
    attributes = insight.attributes or {}
    exact_text = attributes.get("exact_text") or ""
    return {
        "id": insight.id,
        "kind": insight.kind,
        "label": insight.label,
        "title": _card_text(insight.title, max_length=180) or _humanize(insight.label),
        "description": _card_text(insight.description, max_length=320) or _safe_description(insight.label, attributes),
        "confidence": round(float(insight.confidence or 0), 4),
        "confidence_percent": int(round(float(insight.confidence or 0) * 100)),
        "attributes": {
            key: value for key, value in attributes.items()
            if key in {"category", "color", "material", "condition", "kind", "meaning", "language"} and value
        },
        "exact_text": exact_text,
        "crop_url": build_crop_url(request, insight, tour_id=tour_id),
        "distance_degrees": round(math.degrees(distance), 2) if distance is not None else None,
        "related_product": {
            "id": product.id,
            "name": product.name,
            "price": str(product.price),
            "currency": product.currency,
            "url": getattr(product, "get_absolute_url", lambda: "")(),
        } if product else None,
    }
