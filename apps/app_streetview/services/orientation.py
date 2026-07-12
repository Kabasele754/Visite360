from __future__ import annotations

import math


def _as_float(value, default: float = 0.0) -> float:
    if value in (None, ''):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(number):
        return default
    return number


def normalize_heading(value, default: float = 0.0) -> float:
    """Return a Google Street View heading in the valid range [0, 360).

    Google refuses 360, negative headings, NaN, and infinity. This function
    also converts 720 -> 0, -10 -> 350, and 360 -> 0.
    """
    number = _as_float(value, default) % 360.0
    if number >= 360.0:
        number = 0.0
    if abs(number - 360.0) < 1e-9:
        number = 0.0
    if abs(number) < 1e-9:
        number = 0.0
    return round(number, 6)


def clamp_float(value, minimum: float, maximum: float, default: float = 0.0) -> float:
    number = _as_float(value, default)
    if number < minimum:
        return minimum
    if number > maximum:
        return maximum
    return round(number, 6)


def normalize_pitch(value, default: float = 0.0) -> float:
    return clamp_float(value, -90.0, 90.0, default)


def normalize_roll(value, default: float = 0.0) -> float:
    # Keep roll inside Google's safe range.
    number = _as_float(value, default)
    while number < -180.0:
        number += 360.0
    while number > 180.0:
        number -= 360.0
    return clamp_float(number, -180.0, 180.0, default)


def normalize_fov(value, default: float = 90.0) -> float:
    # Marzipano can show wide FOV, but keep the stored initial FOV reasonable.
    return clamp_float(value, 10.0, 120.0, default)
