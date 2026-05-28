import math

import numpy as np
from PIL import Image

from apps.tours.utils_compress_image import (
    _open_image,
    compress_pil_image_to_webp,
)


CUBE_FACES = ("f", "b", "l", "r", "u", "d")


def _largest_power_of_two_lte(value, min_size=512, max_size=2048):
    value = max(int(value), min_size)
    value = min(value, max_size)

    power = 1
    while power * 2 <= value:
        power *= 2

    return max(power, min_size)


def _build_level_sizes(max_cube_size, min_cube_size=512):
    sizes = []
    size = min_cube_size

    while size <= max_cube_size:
        sizes.append(size)
        size *= 2

    return sizes


def _face_direction(face, xx, yy):
    if face == "f":
        x = xx
        y = -yy
        z = np.ones_like(xx)
    elif face == "b":
        x = -xx
        y = -yy
        z = -np.ones_like(xx)
    elif face == "r":
        x = np.ones_like(xx)
        y = -yy
        z = -xx
    elif face == "l":
        x = -np.ones_like(xx)
        y = -yy
        z = xx
    elif face == "u":
        x = xx
        y = np.ones_like(xx)
        z = yy
    elif face == "d":
        x = xx
        y = -np.ones_like(xx)
        z = -yy
    else:
        raise ValueError(f"Face cube invalide : {face}")

    norm = np.sqrt(x * x + y * y + z * z)
    return x / norm, y / norm, z / norm


def _sample_equirectangular(src_array, lon, lat):
    src_h, src_w, channels = src_array.shape

    uf = (lon / (2.0 * np.pi) + 0.5) * src_w
    vf = (0.5 - lat / np.pi) * src_h

    uf = np.mod(uf, src_w)
    vf = np.clip(vf, 0, src_h - 1)

    x0 = np.floor(uf).astype(np.int32)
    y0 = np.floor(vf).astype(np.int32)

    x1 = (x0 + 1) % src_w
    y1 = np.clip(y0 + 1, 0, src_h - 1)

    dx = (uf - x0)[..., None]
    dy = (vf - y0)[..., None]

    top_left = src_array[y0, x0].astype(np.float32)
    top_right = src_array[y0, x1].astype(np.float32)
    bottom_left = src_array[y1, x0].astype(np.float32)
    bottom_right = src_array[y1, x1].astype(np.float32)

    top = top_left * (1 - dx) + top_right * dx
    bottom = bottom_left * (1 - dx) + bottom_right * dx

    sampled = top * (1 - dy) + bottom * dy
    return np.clip(sampled, 0, 255).astype(np.uint8)


def _equirectangular_to_cube_face(src_array, face, face_size):
    lin = (np.arange(face_size, dtype=np.float32) + 0.5) / face_size
    lin = lin * 2.0 - 1.0

    xx, yy = np.meshgrid(lin, lin)

    dx, dy, dz = _face_direction(face, xx, yy)

    lon = np.arctan2(dx, dz)
    lat = np.arcsin(dy)

    face_array = _sample_equirectangular(src_array, lon, lat)
    return Image.fromarray(face_array, mode="RGB")


def generate_multires_cube_tiles_from_equirectangular(
    image_file,
    tile_size=512,
    max_cube_size=2048,
    min_cube_size=512,
    initial_quality=76,
    min_quality=54,
    target_tile_max_kb=180,
):
    src_image = _open_image(image_file)
    src_w, src_h = src_image.size

    if src_w < src_h:
        raise ValueError("Image 360 invalide : largeur inférieure à la hauteur.")

    estimated_cube_size = int(src_w / 4)

    max_level_cube_size = _largest_power_of_two_lte(
        estimated_cube_size,
        min_size=min_cube_size,
        max_size=max_cube_size,
    )

    level_sizes = _build_level_sizes(
        max_cube_size=max_level_cube_size,
        min_cube_size=min_cube_size,
    )

    src_array = np.asarray(src_image, dtype=np.uint8)

    tiles = []

    for level_index, cube_size in enumerate(level_sizes):
        for face in CUBE_FACES:
            cube_face_image = _equirectangular_to_cube_face(
                src_array=src_array,
                face=face,
                face_size=cube_size,
            )

            cols = math.ceil(cube_size / tile_size)
            rows = math.ceil(cube_size / tile_size)

            for y in range(rows):
                for x in range(cols):
                    left = x * tile_size
                    top = y * tile_size
                    right = min(left + tile_size, cube_size)
                    bottom = min(top + tile_size, cube_size)

                    tile_img = cube_face_image.crop((left, top, right, bottom))

                    content, size_kb, quality_used = compress_pil_image_to_webp(
                        tile_img,
                        initial_quality=initial_quality,
                        min_quality=min_quality,
                        target_max_kb=target_tile_max_kb,
                    )

                    tiles.append(
                        {
                            "level": level_index,
                            "cube_size": cube_size,
                            "face": face,
                            "x": x,
                            "y": y,
                            "width": right - left,
                            "height": bottom - top,
                            "content": content,
                            "size_kb": size_kb,
                            "quality": quality_used,
                        }
                    )

    manifest = {
        "type": "cube",
        "tileSize": tile_size,
        "faces": list(CUBE_FACES),
        "levels": [
            {
                "level": index,
                "cubeSize": cube_size,
                "tileSize": tile_size,
            }
            for index, cube_size in enumerate(level_sizes)
        ],
        "totalTiles": len(tiles),
    }

    return manifest, tiles