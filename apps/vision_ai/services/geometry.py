from __future__ import annotations

import math
from typing import Iterable


def normalize_yaw(value: float) -> float:
    return ((float(value) + math.pi) % (2 * math.pi)) - math.pi


def angular_distance(yaw_a: float, pitch_a: float, yaw_b: float, pitch_b: float) -> float:
    """Great-circle distance for Marzipano yaw/pitch coordinates."""
    # Marzipano pitch is positive downward, so latitude is -pitch.
    lat_a = -float(pitch_a)
    lat_b = -float(pitch_b)
    delta_yaw = normalize_yaw(float(yaw_a) - float(yaw_b))
    cosine = (
        math.sin(lat_a) * math.sin(lat_b)
        + math.cos(lat_a) * math.cos(lat_b) * math.cos(delta_yaw)
    )
    return math.acos(max(-1.0, min(1.0, cosine)))


def frame_pixel_to_panorama(
    *,
    x: float,
    y: float,
    width: float,
    height: float,
    frame_yaw_degrees: float,
    frame_pitch_degrees: float,
    fov_degrees: float,
) -> tuple[float, float]:
    """Map a perspective-frame pixel back to Marzipano yaw/pitch."""
    width = max(float(width), 1.0)
    height = max(float(height), 1.0)
    size_ref = min(width, height)
    focal = 0.5 * size_ref / math.tan(math.radians(float(fov_degrees)) / 2.0)

    vx = (float(x) - width / 2.0) / focal
    vy = (float(y) - height / 2.0) / focal
    vz = 1.0
    norm = math.sqrt(vx * vx + vy * vy + vz * vz) or 1.0
    vx, vy, vz = vx / norm, vy / norm, vz / norm

    yaw_r = math.radians(float(frame_yaw_degrees))
    pitch_r = math.radians(float(frame_pitch_degrees))

    x1 = math.cos(yaw_r) * vx + math.sin(yaw_r) * vz
    z1 = -math.sin(yaw_r) * vx + math.cos(yaw_r) * vz
    y1 = vy

    y2 = math.cos(pitch_r) * y1 - math.sin(pitch_r) * z1
    z2 = math.sin(pitch_r) * y1 + math.cos(pitch_r) * z1

    panorama_yaw = normalize_yaw(math.atan2(x1, z2))
    latitude = math.asin(max(-1.0, min(1.0, y2)))
    marzipano_pitch = -latitude
    return panorama_yaw, marzipano_pitch


def panorama_to_frame_pixel(
    *,
    yaw: float,
    pitch: float,
    width: float,
    height: float,
    frame_yaw_degrees: float,
    frame_pitch_degrees: float,
    fov_degrees: float,
) -> tuple[float, float] | None:
    """Project a Marzipano panorama point into a perspective frame.

    ``None`` means that the panorama point is behind the perspective camera or
    outside the frame's field of view. This exact projection is used for object
    hit-testing, replacing the old broad angular-circle approximation that
    could return the same object for unrelated clicks.
    """
    width = max(float(width), 1.0)
    height = max(float(height), 1.0)
    latitude = -float(pitch)
    cos_lat = math.cos(latitude)

    # Panorama/world direction.
    x2 = math.sin(float(yaw)) * cos_lat
    y2 = math.sin(latitude)
    z2 = math.cos(float(yaw)) * cos_lat

    yaw_r = math.radians(float(frame_yaw_degrees))
    pitch_r = math.radians(float(frame_pitch_degrees))

    # Inverse pitch rotation.
    y1 = math.cos(pitch_r) * y2 + math.sin(pitch_r) * z2
    z1 = -math.sin(pitch_r) * y2 + math.cos(pitch_r) * z2
    x1 = x2

    # Inverse yaw rotation.
    vx = math.cos(yaw_r) * x1 - math.sin(yaw_r) * z1
    vz = math.sin(yaw_r) * x1 + math.cos(yaw_r) * z1
    vy = y1
    if vz <= 1e-8:
        return None

    size_ref = min(width, height)
    focal = 0.5 * size_ref / math.tan(math.radians(float(fov_degrees)) / 2.0)
    x = width / 2.0 + focal * (vx / vz)
    y = height / 2.0 + focal * (vy / vz)
    if x < 0 or y < 0 or x > width or y > height:
        return None
    return x, y


def point_in_bbox(x: float, y: float, bbox: Iterable[float], *, padding: float = 0.0) -> bool:
    values = list(bbox or [])
    if len(values) < 4:
        return False
    x1, y1, x2, y2 = (float(values[0]), float(values[1]), float(values[2]), float(values[3]))
    return x1 - padding <= x <= x2 + padding and y1 - padding <= y <= y2 + padding


def _point_segment_distance(
    x: float, y: float, x1: float, y1: float, x2: float, y2: float
) -> float:
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(x - x1, y - y1)
    t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
    px, py = x1 + t * dx, y1 + t * dy
    return math.hypot(x - px, y - py)


def point_in_polygon(x: float, y: float, polygon: Iterable, *, padding: float = 0.0) -> bool:
    points: list[tuple[float, float]] = []
    for value in polygon or []:
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            try:
                points.append((float(value[0]), float(value[1])))
            except (TypeError, ValueError):
                continue
    if len(points) < 3:
        return False

    inside = False
    previous = points[-1]
    for current in points:
        x1, y1 = previous
        x2, y2 = current
        intersects = ((y1 > y) != (y2 > y)) and (
            x < (x2 - x1) * (y - y1) / ((y2 - y1) or 1e-12) + x1
        )
        if intersects:
            inside = not inside
        previous = current
    if inside:
        return True
    if padding <= 0:
        return False
    previous = points[-1]
    for current in points:
        if _point_segment_distance(x, y, previous[0], previous[1], current[0], current[1]) <= padding:
            return True
        previous = current
    return False


def region_center_and_area(
    *,
    bbox: Iterable[float] | None,
    polygon: Iterable | None,
    width: float,
    height: float,
) -> tuple[float, float, float]:
    values = list(bbox or [])
    if len(values) >= 4:
        x1, y1, x2, y2 = map(float, values[:4])
        area = max(1.0, abs((x2 - x1) * (y2 - y1)))
        return (x1 + x2) / 2.0, (y1 + y2) / 2.0, area
    points = [
        (float(item[0]), float(item[1]))
        for item in (polygon or [])
        if isinstance(item, (list, tuple)) and len(item) >= 2
    ]
    if points:
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        area = max(1.0, (max(xs) - min(xs)) * (max(ys) - min(ys)))
        return sum(xs) / len(xs), sum(ys) / len(ys), area
    return float(width) / 2.0, float(height) / 2.0, max(1.0, float(width) * float(height))


def _bbox_points(bbox: Iterable[float]) -> list[tuple[float, float]]:
    values = list(bbox or [])
    if len(values) < 4:
        return []
    x1, y1, x2, y2 = (float(values[0]), float(values[1]), float(values[2]), float(values[3]))
    cx = (x1 + x2) / 2.0
    cy = (y1 + y2) / 2.0
    return [(cx, cy), (x1, y1), (x2, y1), (x2, y2), (x1, y2)]


def _polygon_points(polygon: Iterable) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for item in polygon or []:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            try:
                points.append((float(item[0]), float(item[1])))
            except (TypeError, ValueError):
                continue
    if not points:
        return []
    cx = sum(point[0] for point in points) / len(points)
    cy = sum(point[1] for point in points) / len(points)
    return [(cx, cy), *points]


def region_to_angular_geometry(
    *,
    bbox: Iterable[float] | None,
    polygon: Iterable | None,
    width: float,
    height: float,
    frame_yaw_degrees: float,
    frame_pitch_degrees: float,
    fov_degrees: float,
) -> tuple[float, float, float]:
    bbox_values = list(bbox or [])
    if len(bbox_values) >= 4 and max(abs(float(value)) for value in bbox_values[:4]) <= 1.5:
        bbox_values = [
            float(bbox_values[0]) * width,
            float(bbox_values[1]) * height,
            float(bbox_values[2]) * width,
            float(bbox_values[3]) * height,
        ]
    polygon_values = list(polygon or [])
    if polygon_values:
        flat = [
            abs(float(coordinate))
            for point in polygon_values
            if isinstance(point, (list, tuple)) and len(point) >= 2
            for coordinate in point[:2]
        ]
        if flat and max(flat) <= 1.5:
            polygon_values = [
                [float(point[0]) * width, float(point[1]) * height]
                for point in polygon_values
                if isinstance(point, (list, tuple)) and len(point) >= 2
            ]
    points = _bbox_points(bbox_values) or _polygon_points(polygon_values)
    if not points:
        return (
            math.radians(float(frame_yaw_degrees)),
            math.radians(float(frame_pitch_degrees)),
            math.radians(5),
        )

    projected = [
        frame_pixel_to_panorama(
            x=x,
            y=y,
            width=width,
            height=height,
            frame_yaw_degrees=frame_yaw_degrees,
            frame_pitch_degrees=frame_pitch_degrees,
            fov_degrees=fov_degrees,
        )
        for x, y in points
    ]
    center_yaw, center_pitch = projected[0]
    radius = max(
        (angular_distance(center_yaw, center_pitch, yaw, pitch) for yaw, pitch in projected[1:]),
        default=math.radians(3),
    )
    # Angular radius is now only a legacy/near-hit fallback. Exact selection is
    # performed against the original pixel bbox/polygon, so keep it conservative.
    radius = max(math.radians(2.0), min(radius * 1.08, math.radians(12)))
    return center_yaw, center_pitch, radius
