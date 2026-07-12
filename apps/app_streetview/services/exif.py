from __future__ import annotations

import datetime as dt
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from PIL import ExifTags, Image
except Exception:  # pragma: no cover
    ExifTags = None
    Image = None


def _ratio_to_float(value):
    try:
        if hasattr(value, "numerator") and hasattr(value, "denominator"):
            return float(value.numerator) / float(value.denominator)
        if isinstance(value, tuple) and len(value) == 2:
            return float(value[0]) / float(value[1])
        return float(value)
    except Exception:
        return None


def _dms_to_decimal(dms, ref) -> Optional[Decimal]:
    if not dms or len(dms) < 3:
        return None
    deg = _ratio_to_float(dms[0])
    minutes = _ratio_to_float(dms[1])
    seconds = _ratio_to_float(dms[2])
    if deg is None or minutes is None or seconds is None:
        return None
    value = deg + (minutes / 60.0) + (seconds / 3600.0)
    if ref in ("S", "W"):
        value *= -1
    return Decimal(str(round(value, 7)))


def _safe_json_value(value):
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8", errors="ignore")
        except Exception:
            return repr(value)
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    if isinstance(value, tuple):
        return [_safe_json_value(v) for v in value]
    if isinstance(value, list):
        return [_safe_json_value(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _safe_json_value(v) for k, v in value.items()}
    try:
        import fractions

        if isinstance(value, fractions.Fraction):
            return float(value)
    except Exception:
        pass
    try:
        from PIL.TiffImagePlugin import IFDRational

        if isinstance(value, IFDRational):
            return float(value)
    except Exception:
        pass
    return value


def _parse_exif_datetime(raw: str):
    if not raw:
        return None
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return dt.datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def detect_xmp(path_or_file) -> bool:
    """Detect Photo Sphere/XMP data without parsing the whole XML."""

    try:
        if hasattr(path_or_file, "read"):
            pos = path_or_file.tell()
            path_or_file.seek(0)
            data = path_or_file.read(1024 * 512)
            path_or_file.seek(pos)
        else:
            with open(path_or_file, "rb") as fh:
                data = fh.read(1024 * 512)
        return any(
            token in data
            for token in (
                b"GPano:",
                b"PhotoSphere",
                b"http://ns.google.com/photos/1.0/panorama/",
                b"http://ns.adobe.com/xap/1.0/",
            )
        )
    except Exception:
        return False


def extract_image_metadata(path_or_file) -> Dict[str, Any]:
    """Extract dimensions, GPS, altitude, capture time and simple XMP detection.

    This function is intentionally forgiving: it never raises if metadata cannot be read.
    """

    result: Dict[str, Any] = {
        "width": 0,
        "height": 0,
        "format": "",
        "gps_latitude": None,
        "gps_longitude": None,
        "gps_altitude": None,
        "capture_time": None,
        "xmp_detected": detect_xmp(path_or_file),
        "raw_exif": {},
    }

    if Image is None or ExifTags is None:
        return result

    try:
        img = Image.open(path_or_file)
        result["width"] = img.width or 0
        result["height"] = img.height or 0
        result["format"] = img.format or ""

        exif = img.getexif()
        if not exif:
            return result

        tag_map = {v: k for k, v in ExifTags.TAGS.items()}
        gps_tag_id = tag_map.get("GPSInfo")
        date_original_id = tag_map.get("DateTimeOriginal")
        date_id = tag_map.get("DateTime")

        raw_exif = {}
        for tag_id, value in exif.items():
            name = ExifTags.TAGS.get(tag_id, str(tag_id))
            if name != "MakerNote":
                raw_exif[name] = _safe_json_value(value)
        result["raw_exif"] = raw_exif

        capture_raw = None
        if date_original_id and exif.get(date_original_id):
            capture_raw = exif.get(date_original_id)
        elif date_id and exif.get(date_id):
            capture_raw = exif.get(date_id)
        parsed = _parse_exif_datetime(capture_raw) if capture_raw else None
        if parsed:
            result["capture_time"] = parsed

        if gps_tag_id is None:
            return result

        gps_ifd = exif.get_ifd(gps_tag_id)
        if not gps_ifd:
            return result

        gps_tags = {ExifTags.GPSTAGS.get(k, str(k)): v for k, v in gps_ifd.items()}
        lat = _dms_to_decimal(gps_tags.get("GPSLatitude"), gps_tags.get("GPSLatitudeRef"))
        lng = _dms_to_decimal(gps_tags.get("GPSLongitude"), gps_tags.get("GPSLongitudeRef"))
        result["gps_latitude"] = lat
        result["gps_longitude"] = lng

        altitude = gps_tags.get("GPSAltitude")
        altitude_ref = gps_tags.get("GPSAltitudeRef", 0)
        altitude_float = _ratio_to_float(altitude) if altitude is not None else None
        if altitude_float is not None:
            if altitude_ref == 1:
                altitude_float *= -1
            result["gps_altitude"] = altitude_float

        return result
    except Exception:
        return result
