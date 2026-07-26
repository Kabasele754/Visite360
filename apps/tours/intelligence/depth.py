from __future__ import annotations

import io
import logging
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils import timezone
from PIL import Image, ImageFilter, ImageOps

logger = logging.getLogger(__name__)


class DepthGenerationUnavailable(RuntimeError):
    """Raised when the optional local depth runtime is not installed."""


@lru_cache(maxsize=1)
def _depth_pipeline():
    try:
        from transformers import pipeline
    except Exception as exc:  # pragma: no cover - depends on optional AI image
        raise DepthGenerationUnavailable(
            "The optional transformers depth runtime is not installed."
        ) from exc

    model_name = getattr(
        settings,
        "TOUR_DEPTH_MODEL",
        "depth-anything/Depth-Anything-V2-Small-hf",
    )
    device = int(getattr(settings, "TOUR_DEPTH_DEVICE", -1))
    return pipeline("depth-estimation", model=model_name, device=device)


def _source_field(scene):
    for name in ("image_360", "image_360_original", "image_360_mobile"):
        value = getattr(scene, name, None)
        if value:
            return value
    return None


def _load_panorama(scene) -> Image.Image:
    source = _source_field(scene)
    if not source:
        raise ValueError("The scene does not contain a panorama image.")
    source.open("rb")
    try:
        image = Image.open(source)
        image.load()
    finally:
        source.close()
    return ImageOps.exif_transpose(image).convert("RGB")


def _resize_for_depth(image: Image.Image) -> Image.Image:
    max_width = max(512, int(getattr(settings, "TOUR_DEPTH_MAX_WIDTH", 2048)))
    if image.width <= max_width:
        return image
    scale = max_width / float(image.width)
    return image.resize(
        (max_width, max(256, int(round(image.height * scale)))),
        Image.Resampling.LANCZOS,
    )


def _existing_depth(scene) -> dict:
    analysis = getattr(scene, "ai_analysis", {}) or {}
    depth = analysis.get("depth")
    return depth if isinstance(depth, dict) else {}


def generate_scene_depth_map(scene, *, force: bool = False) -> dict:
    """Generate a reviewable equirectangular depth map for Three.js.

    The result is an approximation derived from one panorama, not a metric 3D
    reconstruction. It is stored separately and never alters the source image.
    """
    existing = _existing_depth(scene)
    if existing.get("url") and not force:
        return existing

    panorama = _resize_for_depth(_load_panorama(scene))
    estimator = _depth_pipeline()
    result = estimator(panorama)
    depth_image = result.get("depth") if isinstance(result, dict) else None
    if depth_image is None:
        raise RuntimeError("The depth model did not return a depth image.")
    if not isinstance(depth_image, Image.Image):
        depth_image = Image.fromarray(depth_image)

    # Depth Anything returns relative monocular depth. A light median filter
    # suppresses isolated noise before the browser projects the map into a
    # point cloud or surface mesh. White values are treated as near by default.
    depth_image = ImageOps.autocontrast(depth_image.convert("L"))
    depth_image = depth_image.filter(ImageFilter.MedianFilter(size=3))
    buffer = io.BytesIO()
    depth_image.save(buffer, format="PNG", optimize=True)

    relative_path = f"tours/depth_maps/{scene.scene_id}-depth.png"
    if default_storage.exists(relative_path):
        default_storage.delete(relative_path)
    stored_path = default_storage.save(relative_path, ContentFile(buffer.getvalue()))
    public_url = default_storage.url(stored_path)

    payload = {
        "url": public_url,
        "path": stored_path,
        "source": "depth-anything-v2",
        "model": getattr(
            settings,
            "TOUR_DEPTH_MODEL",
            "depth-anything/Depth-Anything-V2-Small-hf",
        ),
        "width": depth_image.width,
        "height": depth_image.height,
        "confidence": 0.72,
        "generated_at": timezone.now().isoformat(),
        "kind": "monocular_relative_depth",
        "near_is_white": True,
        "render_modes": ["pointcloud", "mesh"],
    }

    analysis = dict(getattr(scene, "ai_analysis", {}) or {})
    analysis["depth"] = payload
    analysis["depth_map_url"] = public_url
    analysis["spatial_reconstruction"] = {
        "ready": True,
        "default_mode": "pointcloud",
        "render_modes": ["pointcloud", "mesh", "panorama"],
        "generated_at": payload["generated_at"],
    }
    scene.ai_analysis = analysis
    scene.save(update_fields=["ai_analysis", "updated_at"])
    return payload
