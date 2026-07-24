from __future__ import annotations

import io
import logging
import math
from dataclasses import dataclass
from typing import Any

import numpy as np
from django.conf import settings
from PIL import Image, ImageFile, ImageOps, UnidentifiedImageError

logger = logging.getLogger(__name__)

# Large panoramas and camera exports can contain a slightly truncated final
# JPEG block while remaining fully decodable. Pillow is conservative by
# default, so explicitly allow these files and canonicalize them before CV.
ImageFile.LOAD_TRUNCATED_IMAGES = True


class InvalidPanoramaImageError(ValueError):
    """Raised when a panorama candidate cannot be decoded as an image."""


@dataclass(slots=True)
class PreparedImageData:
    image_bytes: bytes
    format: str
    width: int
    height: int
    repaired: bool = False
    decoder: str = "pillow"


@dataclass(slots=True)
class PanoramaFrameData:
    index: int
    yaw: float
    pitch: float
    image_bytes: bytes
    width: int
    height: int
    fov: float = 82.0


_OPTIONAL_IMAGE_PLUGINS_REGISTERED = False


def _register_optional_image_plugins() -> None:
    """Register HEIF/AVIF Pillow plugins when they are available.

    iPhone, Android and some 360 cameras can upload HEIC/HEIF or AVIF files
    while keeping a generic or misleading extension. The plugins are optional:
    a missing package must never prevent JPEG/PNG processing.
    """
    global _OPTIONAL_IMAGE_PLUGINS_REGISTERED
    if _OPTIONAL_IMAGE_PLUGINS_REGISTERED:
        return
    _OPTIONAL_IMAGE_PLUGINS_REGISTERED = True
    try:
        from pillow_heif import register_heif_opener

        register_heif_opener()
    except Exception:
        logger.debug("pillow-heif is not available; HEIF decoding is disabled", exc_info=True)
    try:
        # Importing this package registers its Pillow decoder.
        import pillow_avif  # type: ignore  # noqa: F401
    except Exception:
        logger.debug("pillow-avif-plugin is not available; AVIF decoding is disabled", exc_info=True)


def _first_image_signature_offset(payload: bytes) -> int | None:
    """Find a known image signature near the start of a malformed upload."""
    signatures = (
        b"\xff\xd8\xff",                  # JPEG
        b"\x89PNG\r\n\x1a\n",          # PNG
        b"GIF87a",
        b"GIF89a",
        b"BM",                              # BMP
        b"II*\x00",                        # TIFF little endian
        b"MM\x00*",                        # TIFF big endian
    )
    search_window = payload[: min(len(payload), 1024 * 1024)]
    offsets = [search_window.find(signature) for signature in signatures]
    # WEBP is RIFF....WEBP, so validate both markers.
    riff = search_window.find(b"RIFF")
    if riff >= 0 and search_window[riff + 8 : riff + 12] == b"WEBP":
        offsets.append(riff)
    valid = [offset for offset in offsets if offset >= 0]
    return min(valid) if valid else None


def _looks_like_non_image_response(payload: bytes) -> bool:
    prefix = payload[:512].lstrip().lower()
    return prefix.startswith((
        b"<!doctype html",
        b"<html",
        b"<?xml",
        b"{\"error\"",
        b"{\"detail\"",
        b"access denied",
    ))


def _encode_canonical_jpeg(image: Image.Image, *, quality: int = 95) -> bytes:
    image = ImageOps.exif_transpose(image).convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality, optimize=True)
    return buffer.getvalue()


def prepare_image_bytes(image_bytes: bytes, *, source_name: str = "") -> PreparedImageData:
    """Validate and normalize an uploaded panorama before computer vision.

    Recovery order:
    1. Pillow with truncated-JPEG support and optional HEIF/AVIF plugins.
    2. Remove accidental bytes placed before a valid image signature.
    3. OpenCV ``imdecode`` as a tolerant fallback and re-encode as JPEG.

    The returned bytes are guaranteed to be decodable by Pillow in the current
    process. This also protects Gemini/OpenAI from receiving HTML error pages or
    zero-byte storage objects masquerading as scene images.
    """
    _register_optional_image_plugins()

    if not image_bytes:
        raise InvalidPanoramaImageError(f"Empty panorama file{f' ({source_name})' if source_name else ''}.")
    if len(image_bytes) < 16:
        raise InvalidPanoramaImageError(
            f"Panorama file is too small ({len(image_bytes)} bytes){f' ({source_name})' if source_name else ''}."
        )
    if _looks_like_non_image_response(image_bytes):
        raise InvalidPanoramaImageError(
            f"The panorama contains an HTML/XML/API response instead of image data"
            f"{f' ({source_name})' if source_name else ''}."
        )

    candidates: list[tuple[bytes, bool]] = [(image_bytes, False)]
    signature_offset = _first_image_signature_offset(image_bytes)
    if signature_offset and signature_offset > 0:
        candidates.append((image_bytes[signature_offset:], True))

    pillow_errors: list[str] = []
    for candidate, repaired in candidates:
        try:
            with Image.open(io.BytesIO(candidate)) as opened:
                opened.load()
                image = ImageOps.exif_transpose(opened).convert("RGB")
                image_format = str(opened.format or "UNKNOWN").upper()
                width, height = image.size
                if width < 2 or height < 2:
                    raise InvalidPanoramaImageError(f"Invalid image dimensions: {width}x{height}")

                # Keep ordinary files unchanged to avoid unnecessary quality
                # loss. Re-encode repaired, HEIF/AVIF or unusual camera formats.
                canonical_formats = {"JPEG", "JPG", "PNG", "WEBP", "TIFF", "BMP"}
                needs_reencode = repaired or image_format not in canonical_formats
                normalized = _encode_canonical_jpeg(image) if needs_reencode else candidate
                return PreparedImageData(
                    image_bytes=normalized,
                    format="JPEG" if needs_reencode else image_format,
                    width=width,
                    height=height,
                    repaired=needs_reencode,
                    decoder="pillow",
                )
        except Exception as exc:
            pillow_errors.append(str(exc))

    # OpenCV is often able to decode camera JPEGs with malformed metadata that
    # Pillow rejects. It is already present in the CV stack for panorama remap.
    try:
        import cv2

        array = np.frombuffer(image_bytes, dtype=np.uint8)
        decoded = cv2.imdecode(array, cv2.IMREAD_COLOR)
        if decoded is not None and decoded.size:
            rgb = cv2.cvtColor(decoded, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(rgb)
            width, height = image.size
            return PreparedImageData(
                image_bytes=_encode_canonical_jpeg(image),
                format="JPEG",
                width=width,
                height=height,
                repaired=True,
                decoder="opencv",
            )
    except Exception as exc:
        pillow_errors.append(f"OpenCV: {exc}")

    head_hex = image_bytes[:24].hex(" ")
    details = "; ".join(error for error in pillow_errors if error)[:1200]
    raise InvalidPanoramaImageError(
        "Cannot decode panorama image"
        f"{f' ({source_name})' if source_name else ''}; size={len(image_bytes)} bytes; "
        f"header={head_hex}. Decoder details: {details or 'unknown format'}"
    )


def _equirectangular_to_perspective(
    image: np.ndarray,
    *,
    yaw: float,
    pitch: float,
    fov: float = 90,
    size: int = 768,
) -> np.ndarray:
    height, width = image.shape[:2]
    x, y = np.meshgrid(np.arange(size), np.arange(size))
    focal = 0.5 * size / math.tan(math.radians(fov) / 2)
    vx = (x - size / 2) / focal
    vy = (y - size / 2) / focal
    vz = np.ones_like(vx)
    norm = np.sqrt(vx * vx + vy * vy + vz * vz)
    vx, vy, vz = vx / norm, vy / norm, vz / norm

    yaw_r = math.radians(yaw)
    pitch_r = math.radians(pitch)
    x1 = math.cos(yaw_r) * vx + math.sin(yaw_r) * vz
    z1 = -math.sin(yaw_r) * vx + math.cos(yaw_r) * vz
    y1 = vy
    y2 = math.cos(pitch_r) * y1 - math.sin(pitch_r) * z1
    z2 = math.sin(pitch_r) * y1 + math.cos(pitch_r) * z1

    lon = np.arctan2(x1, z2)
    lat = np.arcsin(np.clip(y2, -1, 1))
    map_x = ((lon / (2 * math.pi)) + 0.5) * width
    map_y = (0.5 - lat / math.pi) * height

    try:
        import cv2

        return cv2.remap(
            image,
            map_x.astype(np.float32),
            map_y.astype(np.float32),
            interpolation=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_WRAP,
        )
    except ImportError:
        map_x = np.mod(map_x.astype(int), width)
        map_y = np.clip(map_y.astype(int), 0, height - 1)
        return image[map_y, map_x]


def extract_panorama_frames(image_bytes: bytes, *, max_frames: int = 12) -> list[PanoramaFrameData]:
    """Create overlapping perspective views covering horizon, walls and floor."""
    prepared = prepare_image_bytes(image_bytes)
    with Image.open(io.BytesIO(prepared.image_bytes)) as opened:
        source = ImageOps.exif_transpose(opened).convert("RGB")
        source.load()
    array = np.asarray(source)
    ratio = source.width / max(source.height, 1)
    if ratio < 1.8:
        buffer = io.BytesIO()
        source.save(buffer, format="JPEG", quality=92)
        return [PanoramaFrameData(0, 0, 0, buffer.getvalue(), source.width, source.height, 82.0)]

    max_frames = max(1, int(max_frames))
    if max_frames <= 8:
        step = 360.0 / max_frames
        viewpoints = [(round(index * step, 4), 0.0) for index in range(max_frames)]
    elif max_frames <= 12:
        viewpoints = [(float(yaw), 0.0) for yaw in range(0, 360, 45)]
        viewpoints += [
            (0.0, -28.0),
            (90.0, 28.0),
            (180.0, -28.0),
            (270.0, 28.0),
        ]
        viewpoints = viewpoints[:max_frames]
    else:
        viewpoints = [(float(yaw), 0.0) for yaw in range(0, 360, 30)]
        viewpoints += [(float(yaw), -30.0) for yaw in range(0, 360, 60)]
        viewpoints += [(float(yaw + 30), 30.0) for yaw in range(0, 360, 60)]
        if max_frames > 24:
            viewpoints += [(float(yaw), -55.0) for yaw in range(0, 360, 90)]
            viewpoints += [(float(yaw + 45), 55.0) for yaw in range(0, 360, 90)]
        viewpoints = viewpoints[:max_frames]

    frame_size = max(512, int(getattr(settings, "VISION_PERSPECTIVE_FRAME_SIZE", 896)))
    frames: list[PanoramaFrameData] = []
    for index, (yaw, pitch) in enumerate(viewpoints):
        frame = _equirectangular_to_perspective(
            array,
            yaw=float(yaw),
            pitch=float(pitch),
            fov=82,
            size=frame_size,
        )
        pil_frame = Image.fromarray(frame.astype(np.uint8))
        buffer = io.BytesIO()
        pil_frame.save(buffer, format="JPEG", quality=90, optimize=True)
        frames.append(
            PanoramaFrameData(
                index,
                float(yaw),
                float(pitch),
                buffer.getvalue(),
                pil_frame.width,
                pil_frame.height,
                82.0,
            )
        )
    return frames


def extract_point_frame(
    image_bytes: bytes,
    *,
    yaw: float,
    pitch: float,
    fov: float = 46.0,
    size: int = 768,
) -> PanoramaFrameData:
    """Extract a perspective crop centered on one Marzipano yaw/pitch point."""
    prepared = prepare_image_bytes(image_bytes)
    with Image.open(io.BytesIO(prepared.image_bytes)) as opened:
        source = ImageOps.exif_transpose(opened).convert("RGB")
        source.load()
    array = np.asarray(source)
    ratio = source.width / max(source.height, 1)
    if ratio < 1.8:
        # A non-equirectangular scene has no spherical reprojection; return the
        # image itself so point inspection can still identify its central item.
        output = io.BytesIO()
        source.save(output, format="JPEG", quality=92, optimize=True)
        source_yaw_degrees = math.degrees(float(yaw))
        projection_pitch_degrees = math.degrees(float(pitch)) * float(
            getattr(settings, "VISION_MARZIPANO_PITCH_SIGN", -1.0)
        )
        return PanoramaFrameData(0, source_yaw_degrees, projection_pitch_degrees, output.getvalue(), source.width, source.height, fov)

    source_yaw_degrees = math.degrees(float(yaw))
    source_pitch_degrees = math.degrees(float(pitch))
    projection_pitch_degrees = source_pitch_degrees * float(
        getattr(settings, "VISION_MARZIPANO_PITCH_SIGN", -1.0)
    )
    frame = _equirectangular_to_perspective(
        array,
        yaw=source_yaw_degrees,
        pitch=projection_pitch_degrees,
        fov=float(fov),
        size=max(384, int(size)),
    )
    pil_frame = Image.fromarray(frame.astype(np.uint8))
    buffer = io.BytesIO()
    pil_frame.save(buffer, format="JPEG", quality=92, optimize=True)
    return PanoramaFrameData(
        0,
        source_yaw_degrees,
        projection_pitch_degrees,
        buffer.getvalue(),
        pil_frame.width,
        pil_frame.height,
        float(fov),
    )
