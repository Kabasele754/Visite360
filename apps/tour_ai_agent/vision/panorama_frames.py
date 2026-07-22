from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image


def _bilinear(img, x, y):
    h, w, _ = img.shape
    x = np.mod(x, w)
    y = np.clip(y, 0, h - 1)
    x0 = np.floor(x).astype(int)
    x1 = (x0 + 1) % w
    y0 = np.floor(y).astype(int)
    y1 = np.minimum(y0 + 1, h - 1)
    wx = x - x0
    wy = y - y0
    return (
        (1 - wx)[..., None] * (1 - wy)[..., None] * img[y0, x0]
        + wx[..., None] * (1 - wy)[..., None] * img[y0, x1]
        + (1 - wx)[..., None] * wy[..., None] * img[y1, x0]
        + wx[..., None] * wy[..., None] * img[y1, x1]
    ).astype(np.uint8)


def equirectangular_to_perspective(
    image_path: str | Path,
    out_path: str | Path,
    yaw: float,
    pitch: float = 0,
    fov: float = 90,
    size: int = 640,
) -> Path:
    pano = np.asarray(Image.open(image_path).convert("RGB"))
    h, w, _ = pano.shape
    xx, yy = np.meshgrid(np.linspace(-1, 1, size), np.linspace(-1, 1, size))
    z = 1 / np.tan(np.deg2rad(fov) / 2)
    directions = np.stack([xx, -yy, np.full_like(xx, z)], axis=-1)
    directions /= np.linalg.norm(directions, axis=-1, keepdims=True)

    yaw_radians = np.deg2rad(yaw)
    pitch_radians = np.deg2rad(pitch)
    rotate_y = np.array([
        [math.cos(yaw_radians), 0, math.sin(yaw_radians)],
        [0, 1, 0],
        [-math.sin(yaw_radians), 0, math.cos(yaw_radians)],
    ])
    rotate_x = np.array([
        [1, 0, 0],
        [0, math.cos(pitch_radians), -math.sin(pitch_radians)],
        [0, math.sin(pitch_radians), math.cos(pitch_radians)],
    ])
    transformed = directions @ ((rotate_y @ rotate_x).T)
    longitude = np.arctan2(transformed[..., 0], transformed[..., 2])
    latitude = np.arcsin(np.clip(transformed[..., 1], -1, 1))
    x = (longitude / (2 * np.pi) + 0.5) * w
    y = (0.5 - latitude / np.pi) * h

    output = Image.fromarray(_bilinear(pano, x, y))
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    output.save(out_path, "JPEG", quality=88, optimize=True)
    return out_path


def _parse_numbers(value, fallback, cast=float):
    if isinstance(value, (list, tuple)):
        return [cast(item) for item in value]
    try:
        return [cast(item.strip()) for item in str(value).split(",") if item.strip()]
    except (TypeError, ValueError):
        return list(fallback)


def generate_panorama_frames(
    image_path: str | Path,
    output_dir: str | Path,
    size: int = 640,
    yaws=None,
    pitches=None,
    fov: float = 90,
) -> list[dict]:
    yaws = _parse_numbers(yaws, [0, 45, 90, 135, 180, 225, 270, 315])
    pitches = _parse_numbers(pitches, [0])
    result = []
    for pitch in pitches:
        for yaw in yaws:
            name = f"yaw_{int(yaw) % 360:03d}_pitch_{int(pitch):+03d}"
            path = Path(output_dir) / f"{name}.jpg"
            equirectangular_to_perspective(
                image_path,
                path,
                yaw=yaw,
                pitch=pitch,
                fov=fov,
                size=size,
            )
            result.append({
                "name": name,
                "yaw": float(yaw),
                "pitch": float(pitch),
                "fov": float(fov),
                "path": str(path),
            })
    return result
