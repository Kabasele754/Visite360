from __future__ import annotations

import base64
import binascii
import io
import logging
import math
from typing import Any

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps, UnidentifiedImageError
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Max

from apps.ai_core.services.error_safety import classify_provider_error, provider_should_stop_for_analysis
from apps.vision_ai.models import VisionAnalysis, VisionFrame, VisionInsight
from apps.vision_ai.services.geometry import angular_distance
from apps.vision_ai.services.panorama import PanoramaFrameData, extract_point_frame
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


def _inspection_exact_capture(image_bytes: bytes) -> bytes:
    """Mark the exact browser-framed pixels without adding outside context."""
    image = _marked_panel(image_bytes, label="EXACT USER SELECTION")
    draw = ImageDraw.Draw(image)
    border = max(3, min(image.width, image.height) // 160)
    draw.rectangle((1, 1, image.width - 2, image.height - 2), outline=(34, 211, 238), width=border)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=91, optimize=True)
    return buffer.getvalue()


def _decode_selection_capture(selection: dict[str, Any] | None) -> tuple[bytes, int, int] | None:
    """Decode and canonicalize a client-side screenshot crop.

    The browser sends only the pixels inside the user's selection. Strict size,
    MIME and image validation prevents this convenience payload from becoming a
    generic upload endpoint.
    """
    if not isinstance(selection, dict):
        return None
    capture = selection.get("capture")
    if not isinstance(capture, dict):
        return None
    data_url = str(capture.get("data_url") or "")
    prefixes = {
        "data:image/jpeg;base64,": "JPEG",
        "data:image/png;base64,": "PNG",
        "data:image/webp;base64,": "WEBP",
    }
    prefix = next((value for value in prefixes if data_url.startswith(value)), None)
    if prefix is None:
        return None
    encoded = data_url[len(prefix):]
    max_bytes = int(getattr(settings, "VISION_POINT_CAPTURE_MAX_BYTES", 2_000_000))
    if not encoded or len(encoded) > max_bytes * 2:
        return None
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        return None
    if not raw or len(raw) > max_bytes:
        return None

    max_dimension = int(getattr(settings, "VISION_POINT_CAPTURE_MAX_DIMENSION", 1024))
    try:
        with Image.open(io.BytesIO(raw)) as opened:
            opened.load()
            image = ImageOps.exif_transpose(opened).convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError):
        return None
    if image.width < 96 or image.height < 96 or image.width > 4096 or image.height > 4096:
        return None
    image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=90, optimize=True)
    return buffer.getvalue(), image.width, image.height


def _enhance_exact_capture(image_bytes: bytes) -> bytes:
    """Improve a selected crop without introducing pixels outside its frame."""
    with Image.open(io.BytesIO(image_bytes)) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
    image = ImageOps.autocontrast(image, cutoff=0.5)
    image = ImageEnhance.Contrast(image).enhance(1.12)
    image = ImageEnhance.Sharpness(image).enhance(1.35)
    image = image.filter(ImageFilter.UnsharpMask(radius=1.2, percent=130, threshold=3))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=92, optimize=True)
    return buffer.getvalue()


def _best_ocr_block(output: ProviderVisionOutput) -> dict[str, Any] | None:
    candidates = [
        block for block in output.ocr_blocks
        if str(block.get("text") or "").strip()
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda block: float(block.get("confidence") or 0.0))


def _select_exact_capture_candidate(
    output: ProviderVisionOutput,
    width: int,
    height: int,
) -> dict[str, Any] | None:
    """Choose the detection that best represents an explicitly framed crop."""
    candidates: list[tuple[tuple[float, ...], dict[str, Any]]] = []
    central = (width * 0.18, height * 0.18, width * 0.82, height * 0.82)
    for item in output.detections:
        inside, distance, area_ratio, bbox = _bbox_metrics(item, width, height)
        if not bbox:
            continue
        x1, y1, x2, y2 = bbox
        ix1, iy1 = max(x1, central[0]), max(y1, central[1])
        ix2, iy2 = min(x2, central[2]), min(y2, central[3])
        intersection = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
        box_area = max(1.0, (x2 - x1) * (y2 - y1))
        central_overlap = intersection / box_area
        confidence = max(0.0, min(1.0, float(item.get("confidence") or 0)))
        if not inside and distance > 0.52 and central_overlap <= 0.02:
            continue
        score = (-central_overlap, distance, -confidence, abs(0.38 - min(area_ratio, 1.0)))
        candidates.append((score, {**item, "bbox": bbox}))
    return min(candidates, key=lambda value: value[0])[1] if candidates else None


def _selection_metadata(selection: dict[str, Any] | None) -> dict[str, Any]:
    """Return persistence-safe selection metadata without the base64 image."""
    if not isinstance(selection, dict):
        return {}
    value = {
        "version": selection.get("version"),
        "bbox": selection.get("bbox") or {},
        "corners": selection.get("corners") or [],
        "view_fov": selection.get("view_fov"),
    }
    capture = selection.get("capture")
    if isinstance(capture, dict):
        value["capture"] = {
            "present": True,
            "width": capture.get("width"),
            "height": capture.get("height"),
            "source": capture.get("source") or "viewer_canvas",
        }
    return value


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


def _selection_fovs(selection: dict[str, Any] | None, *, yaw: float, pitch: float) -> tuple[float, float, float]:
    default_context = float(getattr(settings, "VISION_POINT_INSPECTION_FOV_DEGREES", 46.0))
    default_detail = float(getattr(settings, "VISION_POINT_DETAIL_FOV_DEGREES", 26.0))
    if not isinstance(selection, dict):
        return default_context, default_detail, math.radians(default_detail * 0.18)
    distances = []
    for corner in selection.get("corners") or []:
        try:
            distances.append(angular_distance(yaw, pitch, float(corner["yaw"]), float(corner["pitch"])))
        except (KeyError, TypeError, ValueError):
            continue
    if not distances:
        return default_context, default_detail, math.radians(default_detail * 0.18)
    angular_radius = max(distances)
    selected_diameter = math.degrees(angular_radius * 2.0)
    detail_fov = max(10.0, min(42.0, selected_diameter * 1.18))
    context_fov = max(detail_fov + 8.0, min(58.0, detail_fov * 1.65))
    return context_fov, detail_fov, angular_radius


def inspect_scene_point(
    analysis: VisionAnalysis,
    *,
    yaw: float,
    pitch: float,
    selection: dict[str, Any] | None = None,
) -> VisionInsight | None:
    """Perform a targeted, cached inspection of one panorama point.

    This method is only called when no pre-computed YOLO/OCR region contains the
    click. It extracts a narrow perspective crop, runs local detection, then asks
    one semantic provider to identify only the item intersecting the reticle.
    """
    from apps.vision_ai.services.engine import resolve_analysis_image

    image_bytes = resolve_analysis_image(analysis)
    frame_size = int(getattr(settings, "VISION_POINT_INSPECTION_FRAME_SIZE", 768))
    context_fov, detail_fov, selected_angular_radius = _selection_fovs(
        selection, yaw=yaw, pitch=pitch
    )
    decoded_capture = _decode_selection_capture(selection)
    exact_capture = decoded_capture is not None

    if decoded_capture is not None:
        capture_bytes, capture_width, capture_height = decoded_capture
        frame_data = PanoramaFrameData(
            index=0,
            yaw=float(yaw),
            pitch=float(pitch),
            image_bytes=capture_bytes,
            width=capture_width,
            height=capture_height,
            fov=detail_fov,
        )
        # No pixels outside the user-framed rectangle are supplied to either
        # local or cloud vision engines.
        context_frame = frame_data
    else:
        context_frame = extract_point_frame(
            image_bytes,
            yaw=yaw,
            pitch=pitch,
            fov=context_fov,
            size=frame_size,
        )
        frame_data = extract_point_frame(
            image_bytes,
            yaw=yaw,
            pitch=pitch,
            fov=detail_fov,
            size=frame_size,
        )

    # The first pass uses the exact browser crop. When it cannot verify an
    # item, a second pass enhances those same pixels (contrast/sharpness only)
    # and retries local + semantic recognition. No neighbouring panorama pixels
    # are ever introduced into the automatic rescan.
    inspection_variants: list[tuple[str, bytes]] = [("original", frame_data.image_bytes)]
    if exact_capture and bool(getattr(settings, "VISION_POINT_AUTO_RESCAN", True)):
        try:
            enhanced_bytes = _enhance_exact_capture(frame_data.image_bytes)
            if enhanced_bytes:
                inspection_variants.append(("enhanced_rescan", enhanced_bytes))
        except Exception:
            logger.info("Exact-capture enhancement was unavailable for analysis %s", analysis.pk, exc_info=True)

    yolo_output = ProviderVisionOutput(provider="yolo")
    ocr_output = ProviderVisionOutput(provider="paddleocr")
    yolo_candidate: dict[str, Any] | None = None
    semantic: dict[str, Any] = {}
    semantic_errors: list[str] = []
    semantic_is_usable = False
    required_semantic_confidence = 1.0
    source_providers: list[str] = []
    inspection_pass = "original"
    auto_rescan_performed = False
    disabled_semantic_providers: set[str] = set()

    base_min_semantic = float(getattr(settings, "VISION_POINT_SEMANTIC_MIN_CONFIDENCE", 0.55))
    base_min_without_local = float(getattr(settings, "VISION_POINT_SEMANTIC_ONLY_MIN_CONFIDENCE", 0.72))
    if exact_capture:
        base_min_semantic = float(getattr(settings, "VISION_POINT_EXACT_CAPTURE_SEMANTIC_MIN_CONFIDENCE", 0.58))
        base_min_without_local = float(getattr(settings, "VISION_POINT_EXACT_CAPTURE_ONLY_MIN_CONFIDENCE", 0.64))
    relaxation = max(
        0.0,
        min(0.15, float(getattr(settings, "VISION_POINT_AUTO_RESCAN_CONFIDENCE_RELAXATION", 0.05))),
    )
    semantic_names = semantic_provider_order(enabled_provider_names(["gemini", "openai"]))

    for pass_index, (pass_name, pass_bytes) in enumerate(inspection_variants):
        inspection_pass = pass_name
        auto_rescan_performed = pass_index > 0
        pass_sources: list[str] = []
        pass_yolo = ProviderVisionOutput(provider="yolo")
        pass_ocr = ProviderVisionOutput(provider="paddleocr")
        pass_candidate: dict[str, Any] | None = None

        if "yolo" in enabled_provider_names(["yolo"]):
            try:
                pass_yolo = build_provider("yolo", organization=analysis.organization).analyze(pass_bytes)
                pass_candidate = (
                    _select_exact_capture_candidate(pass_yolo, frame_data.width, frame_data.height)
                    if exact_capture else
                    _select_center_candidate(pass_yolo, frame_data.width, frame_data.height)
                )
                if pass_candidate:
                    pass_sources.append("yolo")
            except Exception:
                logger.warning(
                    "Targeted local object detection was unavailable for analysis %s",
                    analysis.pk,
                    exc_info=True,
                )

        if "paddleocr" in enabled_provider_names(["paddleocr"]):
            try:
                pass_ocr = build_provider("paddleocr", organization=analysis.organization).analyze(pass_bytes)
                if pass_ocr.ocr_blocks:
                    pass_sources.append("paddleocr")
            except Exception as exc:
                logger.warning(
                    "Targeted text recognition is unavailable for analysis %s; "
                    "continuing without local OCR (%s).",
                    analysis.pk,
                    str(exc).splitlines()[0][:180],
                )

        min_semantic = max(0.50, base_min_semantic - (relaxation if pass_index else 0.0))
        min_without_local = max(0.56, base_min_without_local - (relaxation if pass_index else 0.0))
        pass_required_confidence = min_semantic if pass_candidate else min_without_local
        pass_context = {
            "inspection_mode": "exact_user_screenshot" if exact_capture else "panorama_point_crop",
            "inspection_pass": pass_name,
            "automatic_rescan": bool(pass_index),
            "selection_is_source_of_truth": bool(exact_capture),
            "reticle": {"x": frame_data.width / 2.0, "y": frame_data.height / 2.0},
            "image_size": {"width": frame_data.width, "height": frame_data.height},
            "context_fov_degrees": context_frame.fov,
            "detail_fov_degrees": frame_data.fov,
            "center_candidate": pass_candidate or {},
            "nearby_yolo_detections": pass_yolo.detections[:12],
            "ocr_blocks": pass_ocr.ocr_blocks[:12],
        }
        marked_image = (
            pass_bytes
            if exact_capture else
            _inspection_composite(context_frame.image_bytes, pass_bytes)
        )
        pass_semantic: dict[str, Any] = {}
        for provider_name in semantic_names:
            if provider_name in disabled_semantic_providers:
                continue
            try:
                provider = build_provider(provider_name, organization=analysis.organization)
                analyze_target = getattr(provider, "analyze_target", None)
                if not callable(analyze_target):
                    continue
                candidate_semantic = analyze_target(marked_image, context=pass_context) or {}
                if float(candidate_semantic.get("confidence") or 0) >= float(pass_semantic.get("confidence") or 0):
                    pass_semantic = candidate_semantic
                if candidate_semantic.get("found") and float(candidate_semantic.get("confidence") or 0) >= pass_required_confidence:
                    pass_semantic = candidate_semantic
                    break
            except Exception as exc:
                error_code = classify_provider_error(exc)
                semantic_errors.append(f"{provider_name}: {error_code}")
                if provider_should_stop_for_analysis(exc):
                    disabled_semantic_providers.add(provider_name)
                logger.warning(
                    "Targeted semantic provider %s was unavailable for analysis %s; continuing with fallback.",
                    provider_name,
                    analysis.pk,
                )

        pass_semantic_confidence = float(pass_semantic.get("confidence") or 0)
        pass_semantic_usable = bool(pass_semantic.get("found")) and pass_semantic_confidence >= pass_required_confidence

        # High-confidence visible text is still a valid selected target even
        # when a generic object detector does not know the package or sign.
        best_ocr = _best_ocr_block(pass_ocr)
        ocr_threshold = float(getattr(settings, "VISION_POINT_OCR_FALLBACK_MIN_CONFIDENCE", 0.82))
        if not pass_candidate and not pass_semantic_usable and best_ocr is not None:
            ocr_confidence = float(best_ocr.get("confidence") or 0)
            visible_text = _clean_text(best_ocr.get("text"), max_length=180)
            if visible_text and ocr_confidence >= ocr_threshold:
                pass_semantic = {
                    "found": True,
                    "label": "text",
                    "title": visible_text[:80],
                    "description": f'Visible text in the selected area reads “{visible_text}”.',
                    "visible_text": visible_text,
                    "category": "visible_text",
                    "confidence": ocr_confidence,
                    "provider": "paddleocr",
                }
                pass_semantic_confidence = ocr_confidence
                pass_semantic_usable = True

        if pass_candidate or pass_semantic_usable:
            yolo_output = pass_yolo
            ocr_output = pass_ocr
            yolo_candidate = pass_candidate
            semantic = pass_semantic
            semantic_is_usable = pass_semantic_usable
            required_semantic_confidence = pass_required_confidence
            source_providers = pass_sources
            semantic_provider = str(pass_semantic.get("provider") or "")
            if pass_semantic_usable and semantic_provider:
                source_providers.append(semantic_provider)
            break

        # Keep the last pass outputs for diagnostics without presenting them as
        # a verified object.
        yolo_output = pass_yolo
        ocr_output = pass_ocr
        semantic = pass_semantic
        required_semantic_confidence = pass_required_confidence

    local_confidence = float((yolo_candidate or {}).get("confidence") or 0)
    semantic_confidence = float(semantic.get("confidence") or 0)
    if not yolo_candidate and not semantic_is_usable:
        if semantic_errors:
            logger.info(
                "No exact target was verified after %s pass(es) at point (%s, %s): %s",
                len(inspection_variants), yaw, pitch, semantic_errors,
            )
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

    bbox = list(
        (yolo_candidate or {}).get("bbox")
        or ([0.0, 0.0, float(frame_data.width), float(frame_data.height)] if exact_capture else _fallback_bbox(frame_data.width, frame_data.height))
    )
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
                "exact_browser_capture": exact_capture,
                "capture_source": ((selection or {}).get("capture") or {}).get("source", "active_viewer_canvas") if exact_capture else "server_panorama_projection",
                "inspection_pass": inspection_pass,
                "auto_rescan_performed": auto_rescan_performed,
                "source_yaw": yaw,
                "source_pitch": pitch,
                "selection": _selection_metadata(selection),
                "selection_angular_radius": selected_angular_radius,
                "projection_pitch_sign": float(getattr(settings, "VISION_MARZIPANO_PITCH_SIGN", -1.0)),
            },
        )
        frame.image.save(
            f"point-{frame.frame_index:04d}.jpg",
            ContentFile(frame_data.image_bytes),
            save=False,
        )
        frame.save()

        bbox_width = max(1.0, float(bbox[2]) - float(bbox[0])) if len(bbox) >= 4 else frame_data.width * 0.2
        bbox_height = max(1.0, float(bbox[3]) - float(bbox[1])) if len(bbox) >= 4 else frame_data.height * 0.2
        bbox_ratio = max(bbox_width / max(frame_data.width, 1), bbox_height / max(frame_data.height, 1))
        angular_radius = max(
            math.radians(1.2),
            min(selected_angular_radius, math.radians(frame_data.fov * bbox_ratio * 0.62)),
        )
        # Keep the insight anchored to the exact panorama point confirmed by the
        # user. The saved perspective frame uses a projection-specific pitch sign
        # and must not be converted back as though it were the source point.
        insight_yaw, insight_pitch = float(yaw), float(pitch)
        visible_text = _clean_text(semantic.get("visible_text"), max_length=180) if semantic_is_usable else ""
        attributes = {
            "origin": "point_inspection",
            "exact_user_selection": exact_capture,
            "category": _clean_text(semantic.get("category"), max_length=100),
            "color": _clean_text(semantic.get("color"), max_length=80),
            "material": _clean_text(semantic.get("material"), max_length=80),
            "condition": _clean_text(semantic.get("condition"), max_length=80),
            "exact_text": visible_text,
            "local_yolo_label": (yolo_candidate or {}).get("label", ""),
            "inspection_pass": inspection_pass,
            "auto_rescan_performed": auto_rescan_performed,
            "ocr_text": " | ".join(_clean_text(block.get("text"), max_length=80) for block in ocr_output.ocr_blocks[:3] if _clean_text(block.get("text"), max_length=80)),
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
