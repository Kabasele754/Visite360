from __future__ import annotations

import io
import logging
import math
from typing import Any

from PIL import Image, ImageDraw
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Max

from apps.vision_ai.models import VisionAnalysis, VisionFrame, VisionInsight
from apps.vision_ai.services.geometry import region_to_angular_geometry
from apps.vision_ai.services.panorama import extract_point_frame
from apps.vision_ai.services.providers import (
    ProviderVisionOutput,
    build_provider,
    enabled_provider_names,
    semantic_provider_order,
)

logger = logging.getLogger(__name__)


def _humanize(value: str) -> str:
    return str(value or "object").replace("_", " ").replace("-", " ").strip().title()


def _clean_text(value: Any, *, max_length: int = 320) -> str:
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


def _bbox_metrics(item: dict[str, Any], width: float, height: float) -> tuple[bool, float, float, list[float]]:
    values = list(item.get("bbox") or [])
    if len(values) < 4:
        return False, float("inf"), 1.0, []
    x1, y1, x2, y2 = map(float, values[:4])
    cx, cy = width / 2.0, height / 2.0
    inside = x1 <= cx <= x2 and y1 <= cy <= y2
    distance = math.hypot((x1 + x2) / 2.0 - cx, (y1 + y2) / 2.0 - cy) / max(min(width, height), 1.0)
    area_ratio = max(1.0, (x2 - x1) * (y2 - y1)) / max(width * height, 1.0)
    return inside, distance, area_ratio, [x1, y1, x2, y2]


def _select_center_candidate(output: ProviderVisionOutput, width: int, height: int) -> dict[str, Any] | None:
    exact: list[tuple[tuple[float, ...], dict[str, Any]]] = []
    near: list[tuple[tuple[float, ...], dict[str, Any]]] = []
    for item in output.detections:
        inside, distance, area_ratio, bbox = _bbox_metrics(item, width, height)
        if not bbox:
            continue
        confidence = max(0.0, min(1.0, float(item.get("confidence") or 0)))
        enriched = {**item, "bbox": bbox}
        # A smaller box containing the reticle is usually the concrete product,
        # while a giant box is commonly a shelf, counter or wall.
        score = (area_ratio, distance, 1.0 - confidence)
        if inside:
            exact.append((score, enriched))
        elif distance <= float(getattr(settings, "VISION_POINT_YOLO_NEAR_CENTER_RATIO", 0.16)):
            near.append(((distance, area_ratio, 1.0 - confidence), enriched))
    if exact:
        return min(exact, key=lambda value: value[0])[1]
    if near:
        return min(near, key=lambda value: value[0])[1]
    return None


def _marked_panel(image_bytes: bytes, *, label: str) -> Image.Image:
    with Image.open(io.BytesIO(image_bytes)) as opened:
        image = opened.convert("RGB")
    draw = ImageDraw.Draw(image)
    cx, cy = image.width // 2, image.height // 2
    radius = max(18, min(image.width, image.height) // 28)
    color = (34, 211, 238)
    dark = (2, 6, 23)
    draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=dark, width=7)
    draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=color, width=3)
    draw.line((cx - radius - 12, cy, cx + radius + 12, cy), fill=dark, width=7)
    draw.line((cx, cy - radius - 12, cx, cy + radius + 12), fill=dark, width=7)
    draw.line((cx - radius - 12, cy, cx + radius + 12, cy), fill=color, width=3)
    draw.line((cx, cy - radius - 12, cx, cy + radius + 12), fill=color, width=3)
    label_width = max(120, len(label) * 9 + 24)
    draw.rounded_rectangle((14, 14, 14 + label_width, 50), radius=9, fill=dark, outline=color, width=2)
    draw.text((26, 24), label, fill=(207, 250, 254))
    return image


def _inspection_composite(context_bytes: bytes, detail_bytes: bytes) -> bytes:
    """Create one multimodal image with context and a tighter target panel."""
    context = _marked_panel(context_bytes, label="CONTEXT")
    detail = _marked_panel(detail_bytes, label="DETAIL - TARGET")
    height = max(context.height, detail.height)
    canvas = Image.new("RGB", (context.width + detail.width + 8, height), (2, 6, 23))
    canvas.paste(context, (0, 0))
    canvas.paste(detail, (context.width + 8, 0))
    buffer = io.BytesIO()
    canvas.save(buffer, format="JPEG", quality=91, optimize=True)
    return buffer.getvalue()


def _next_frame_index(analysis: VisionAnalysis) -> int:
    current = analysis.frames.aggregate(value=Max("frame_index"))["value"]
    value = int(current if current is not None else -1) + 1
    if value > 32760:
        raise RuntimeError("The point-inspection frame cache is full for this analysis")
    return value


def _fallback_bbox(width: int, height: int) -> list[float]:
    # Semantic-only targets receive a deliberately tight region so they cannot
    # capture neighbouring products on later clicks.
    span = min(width, height) * 0.22
    cx, cy = width / 2.0, height / 2.0
    return [cx - span / 2.0, cy - span / 2.0, cx + span / 2.0, cy + span / 2.0]


def inspect_scene_point(
    analysis: VisionAnalysis,
    *,
    yaw: float,
    pitch: float,
) -> VisionInsight | None:
    """Perform a targeted, cached inspection of one panorama point.

    This method is only called when no pre-computed YOLO/OCR region contains the
    click. It extracts a narrow perspective crop, runs local detection, then asks
    one semantic provider to identify only the item intersecting the reticle.
    """
    from apps.vision_ai.services.engine import resolve_analysis_image

    image_bytes = resolve_analysis_image(analysis)
    frame_size = int(getattr(settings, "VISION_POINT_INSPECTION_FRAME_SIZE", 768))
    context_frame = extract_point_frame(
        image_bytes,
        yaw=yaw,
        pitch=pitch,
        fov=float(getattr(settings, "VISION_POINT_INSPECTION_FOV_DEGREES", 46.0)),
        size=frame_size,
    )
    frame_data = extract_point_frame(
        image_bytes,
        yaw=yaw,
        pitch=pitch,
        fov=float(getattr(settings, "VISION_POINT_DETAIL_FOV_DEGREES", 26.0)),
        size=frame_size,
    )

    yolo_output = ProviderVisionOutput(provider="yolo")
    yolo_candidate: dict[str, Any] | None = None
    source_providers: list[str] = []
    if "yolo" in enabled_provider_names(["yolo"]):
        try:
            yolo_output = build_provider("yolo", organization=analysis.organization).analyze(frame_data.image_bytes)
            yolo_candidate = _select_center_candidate(yolo_output, frame_data.width, frame_data.height)
            if yolo_candidate:
                source_providers.append("yolo")
        except Exception:
            logger.exception("Targeted YOLO inspection failed for analysis %s", analysis.pk)

    context = {
        "reticle": {"x": frame_data.width / 2.0, "y": frame_data.height / 2.0},
        "image_size": {"width": frame_data.width, "height": frame_data.height},
        "context_fov_degrees": context_frame.fov,
        "detail_fov_degrees": frame_data.fov,
        "center_candidate": yolo_candidate or {},
        "nearby_yolo_detections": yolo_output.detections[:12],
    }
    semantic: dict[str, Any] = {}
    semantic_errors: list[str] = []
    min_semantic = float(getattr(settings, "VISION_POINT_SEMANTIC_MIN_CONFIDENCE", 0.55))
    min_without_local = float(getattr(settings, "VISION_POINT_SEMANTIC_ONLY_MIN_CONFIDENCE", 0.72))
    required_semantic_confidence = min_semantic if yolo_candidate else min_without_local
    provider_names = semantic_provider_order(enabled_provider_names(["gemini", "openai"]))
    marked_image = _inspection_composite(context_frame.image_bytes, frame_data.image_bytes)
    for provider_name in provider_names:
        try:
            provider = build_provider(provider_name, organization=analysis.organization)
            analyze_target = getattr(provider, "analyze_target", None)
            if not callable(analyze_target):
                continue
            semantic = analyze_target(marked_image, context=context)
            if semantic.get("found") and float(semantic.get("confidence") or 0) >= required_semantic_confidence:
                break
        except Exception as exc:
            semantic_errors.append(f"{provider_name}: {exc}")
            logger.warning(
                "Targeted semantic provider %s failed for analysis %s: %s",
                provider_name,
                analysis.pk,
                exc,
            )

    local_confidence = float((yolo_candidate or {}).get("confidence") or 0)
    semantic_confidence = float(semantic.get("confidence") or 0)
    semantic_is_usable = bool(semantic.get("found")) and semantic_confidence >= required_semantic_confidence
    if semantic_is_usable and semantic.get("provider"):
        source_providers.append(str(semantic["provider"]))

    if not yolo_candidate and not semantic_is_usable:
        if semantic_errors:
            logger.info("No target was verified at point (%s, %s): %s", yaw, pitch, semantic_errors)
        return None

    label = str(
        (semantic.get("label") if semantic_is_usable else "")
        or (yolo_candidate or {}).get("label")
        or "object"
    )[:160]
    title = _clean_text(semantic.get("title"), max_length=180) if semantic_is_usable else ""
    title = title or _humanize(label)
    description = _clean_text(semantic.get("description"), max_length=320) if semantic_is_usable else ""
    if not description:
        description = f"A {_humanize(label).lower()} detected at the selected point in this scene."

    bbox = list((yolo_candidate or {}).get("bbox") or _fallback_bbox(frame_data.width, frame_data.height))
    with transaction.atomic():
        locked_analysis = VisionAnalysis.objects.select_for_update().get(pk=analysis.pk)
        frame = VisionFrame(
            analysis=locked_analysis,
            frame_index=_next_frame_index(locked_analysis),
            yaw=frame_data.yaw,
            pitch=frame_data.pitch,
            metadata={
                "width": frame_data.width,
                "height": frame_data.height,
                "fov": frame_data.fov,
                "dynamic_point_inspection": True,
                "source_yaw": yaw,
                "source_pitch": pitch,
            },
        )
        frame.image.save(
            f"point-{frame.frame_index:04d}.jpg",
            ContentFile(frame_data.image_bytes),
            save=False,
        )
        frame.save()

        insight_yaw, insight_pitch, angular_radius = region_to_angular_geometry(
            bbox=bbox,
            polygon=None,
            width=frame_data.width,
            height=frame_data.height,
            frame_yaw_degrees=frame.yaw,
            frame_pitch_degrees=frame.pitch,
            fov_degrees=frame_data.fov,
        )
        visible_text = _clean_text(semantic.get("visible_text"), max_length=180) if semantic_is_usable else ""
        attributes = {
            "origin": "point_inspection",
            "category": _clean_text(semantic.get("category"), max_length=100),
            "color": _clean_text(semantic.get("color"), max_length=80),
            "material": _clean_text(semantic.get("material"), max_length=80),
            "condition": _clean_text(semantic.get("condition"), max_length=80),
            "exact_text": visible_text,
            "local_yolo_label": (yolo_candidate or {}).get("label", ""),
        }
        kind = VisionInsight.Kind.TEXT if visible_text and label in {"sign", "label", "text", "price_tag"} else VisionInsight.Kind.OBJECT
        return VisionInsight.objects.create(
            analysis=locked_analysis,
            frame=frame,
            kind=kind,
            label=label,
            title=title,
            description=description,
            confidence=max(local_confidence, semantic_confidence),
            bbox=bbox,
            yaw=insight_yaw,
            pitch=insight_pitch,
            angular_radius=min(angular_radius, math.radians(9)),
            source_providers=list(dict.fromkeys(source_providers)),
            attributes={key: value for key, value in attributes.items() if value},
            is_verified=False,
        )
