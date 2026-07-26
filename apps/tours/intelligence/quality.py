from __future__ import annotations

import io
import logging
import math
from statistics import median
from typing import Any

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from django.core.files.base import ContentFile
from django.utils import timezone

from apps.tours.models import Scene360, SceneVisualQuality
from apps.vision_ai.services.panorama import prepare_image_bytes

logger = logging.getLogger(__name__)


def _read_scene_image(scene: Scene360) -> tuple[bytes, str]:
    for field_name in (
        "image_360_original",
        "image_360",
        "image_360_mobile",
        "image_360_preview",
    ):
        field = getattr(scene, field_name, None)
        if not field:
            continue
        try:
            field.open("rb")
            try:
                payload = field.read()
            finally:
                field.close()
            if payload:
                return payload, str(getattr(field, "name", "") or field_name)
        except Exception:
            logger.warning("Could not read %s for scene %s", field_name, scene.pk, exc_info=True)
    raise RuntimeError("scene_image_unavailable")


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _sharpness(gray: np.ndarray) -> tuple[float, float]:
    try:
        import cv2

        raw = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    except Exception:
        pil = Image.fromarray(gray).filter(ImageFilter.FIND_EDGES)
        raw = float(np.asarray(pil, dtype=np.float32).var())
    score = _clamp(math.log1p(max(raw, 0.0)) / math.log1p(1200.0))
    return score, raw


def _horizon_score(gray: np.ndarray) -> tuple[float, float]:
    try:
        import cv2

        resized = cv2.resize(gray, (min(1200, gray.shape[1]), min(600, gray.shape[0])))
        edges = cv2.Canny(resized, 65, 150)
        lines = cv2.HoughLinesP(
            edges,
            1,
            np.pi / 180,
            threshold=70,
            minLineLength=max(80, resized.shape[1] // 8),
            maxLineGap=20,
        )
        angles: list[float] = []
        if lines is not None:
            for line in lines[:250]:
                x1, y1, x2, y2 = [float(v) for v in line[0]]
                angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
                while angle > 90:
                    angle -= 180
                while angle < -90:
                    angle += 180
                if abs(angle) <= 18:
                    angles.append(angle)
        tilt = float(median(angles)) if angles else 0.0
        return _clamp(1.0 - abs(tilt) / 8.0), tilt
    except Exception:
        return 0.75, 0.0


def _make_enhanced_preview(image: Image.Image) -> bytes:
    preview = image.copy()
    preview.thumbnail((1800, 900), Image.Resampling.LANCZOS)
    preview = ImageOps.autocontrast(preview, cutoff=0.6)
    preview = ImageEnhance.Contrast(preview).enhance(1.08)
    preview = ImageEnhance.Sharpness(preview).enhance(1.22)
    buffer = io.BytesIO()
    preview.save(buffer, "WEBP", quality=80, method=6)
    return buffer.getvalue()


def assess_scene_quality(scene: Scene360, *, analysis=None) -> SceneVisualQuality:
    quality, _ = SceneVisualQuality.objects.get_or_create(scene=scene)
    quality.status = SceneVisualQuality.Status.PROCESSING
    quality.error_code = ""
    quality.analysis = analysis
    quality.save(update_fields=("status", "error_code", "analysis", "updated_at"))

    try:
        raw, source_name = _read_scene_image(scene)
        prepared = prepare_image_bytes(raw, source_name=source_name)
        with Image.open(io.BytesIO(prepared.image_bytes)) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGB")
            image.load()

        width, height = image.size
        working = image.copy()
        working.thumbnail((2048, 1024), Image.Resampling.LANCZOS)
        rgb = np.asarray(working, dtype=np.uint8)
        gray = np.asarray(working.convert("L"), dtype=np.uint8)

        brightness_raw = float(gray.mean())
        contrast_raw = float(gray.std())
        exposure_score = _clamp(1.0 - abs(brightness_raw - 128.0) / 105.0)
        contrast_score = _clamp(contrast_raw / 62.0)
        sharpness_score, sharpness_raw = _sharpness(gray)

        ratio = width / max(height, 1)
        size_component = min(1.0, width / 6000.0) * 0.72 + min(1.0, height / 3000.0) * 0.28
        ratio_component = _clamp(1.0 - abs(ratio - 2.0) / 0.35)
        resolution_score = _clamp(size_component * 0.75 + ratio_component * 0.25)

        seam_width = max(2, int(rgb.shape[1] * 0.015))
        left = rgb[:, :seam_width].astype(np.float32)
        right = rgb[:, -seam_width:].astype(np.float32)
        seam_difference = float(np.abs(left - right).mean())
        seam_score = _clamp(1.0 - seam_difference / 58.0)
        horizon_score, horizon_tilt = _horizon_score(gray)

        dark_ratio = float((gray < 22).mean())
        bright_ratio = float((gray > 242).mean())
        clipped_ratio = dark_ratio + bright_ratio

        issues: list[dict[str, Any]] = []
        recommendations: list[dict[str, Any]] = []

        def add_issue(code: str, title: str, detail: str, severity: str, action: str) -> None:
            issues.append({"code": code, "title": title, "detail": detail, "severity": severity})
            recommendations.append({"code": code, "action": action, "priority": severity})

        if resolution_score < 0.58:
            add_issue(
                "low_resolution",
                "Panorama resolution is limited",
                f"The source is {width}×{height}px. Small objects may lose detail when visitors zoom in.",
                "high",
                "Upload an equirectangular panorama close to 6000×3000px or higher.",
            )
        if sharpness_score < 0.42:
            add_issue(
                "soft_image",
                "The scene is not sufficiently sharp",
                "Fine labels and small objects may be difficult for visitors and computer vision to read.",
                "high",
                "Capture again with a stable tripod, clean lens and lower motion blur.",
            )
        if exposure_score < 0.50 or clipped_ratio > 0.25:
            add_issue(
                "exposure",
                "Exposure needs improvement",
                "Important areas are too dark or too bright, which reduces visual recognition quality.",
                "medium",
                "Use HDR/bracketing or rebalance the lighting before uploading the final panorama.",
            )
        if contrast_score < 0.38:
            add_issue(
                "low_contrast",
                "Low local contrast",
                "Objects blend into the background and labels are less readable.",
                "medium",
                "Increase local contrast carefully or upload the original HDR panorama.",
            )
        if seam_score < 0.48:
            add_issue(
                "visible_seam",
                "Possible panorama seam",
                "The left and right edges differ strongly and may produce a visible stitch line.",
                "medium",
                "Re-export the panorama with seam correction and consistent exposure.",
            )
        if horizon_score < 0.50:
            add_issue(
                "tilted_horizon",
                "The horizon may be tilted",
                f"Estimated horizontal tilt is {horizon_tilt:.1f}°.",
                "medium",
                "Level the camera or correct the panorama horizon before publishing.",
            )

        overall = _clamp(
            sharpness_score * 0.25
            + exposure_score * 0.18
            + contrast_score * 0.14
            + resolution_score * 0.20
            + seam_score * 0.11
            + horizon_score * 0.12
        )
        requires_reupload = any(item["severity"] == "high" for item in issues) or overall < 0.48

        if quality.enhanced_preview:
            try:
                quality.enhanced_preview.delete(save=False)
            except Exception:
                pass
        enhanced = _make_enhanced_preview(image)
        quality.enhanced_preview.save(
            f"scene-{scene.pk}-enhanced.webp",
            ContentFile(enhanced),
            save=False,
        )
        quality.status = SceneVisualQuality.Status.READY
        quality.overall_score = overall
        quality.sharpness_score = sharpness_score
        quality.exposure_score = exposure_score
        quality.contrast_score = contrast_score
        quality.resolution_score = resolution_score
        quality.seam_score = seam_score
        quality.horizon_score = horizon_score
        quality.source_width = width
        quality.source_height = height
        quality.requires_reupload = requires_reupload
        quality.issues = issues
        quality.recommendations = recommendations
        quality.metrics = {
            "source_name": source_name,
            "decoder": prepared.decoder,
            "repaired": prepared.repaired,
            "brightness_mean": round(brightness_raw, 3),
            "contrast_std": round(contrast_raw, 3),
            "sharpness_variance": round(sharpness_raw, 3),
            "seam_difference": round(seam_difference, 3),
            "horizon_tilt_degrees": round(horizon_tilt, 3),
            "dark_pixel_ratio": round(dark_ratio, 5),
            "bright_pixel_ratio": round(bright_ratio, 5),
            "aspect_ratio": round(ratio, 5),
        }
        quality.error_code = ""
        quality.analyzed_at = timezone.now()
        quality.save()
        return quality
    except Exception as exc:
        logger.exception("Scene quality assessment failed for scene %s", scene.pk)
        quality.status = SceneVisualQuality.Status.FAILED
        quality.error_code = "quality_assessment_failed"
        quality.metrics = {"technical_detail": str(exc)[:500]}
        quality.analyzed_at = timezone.now()
        quality.save(update_fields=("status", "error_code", "metrics", "analyzed_at", "updated_at"))
        return quality
