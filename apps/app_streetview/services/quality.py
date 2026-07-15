from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from django.utils import timezone

from apps.tours.models import Hotspot, Scene360
from apps.app_streetview.models import StreetViewSourcePublication, StreetViewSourceSceneState
from apps.app_streetview.services.orientation import normalize_heading, normalize_pitch, normalize_roll, normalize_fov

try:
    from PIL import Image
except Exception:  # pragma: no cover - optional at runtime
    Image = None


EARTH_RADIUS_M = 6371000.0


def _float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def haversine_meters(a_lat, a_lng, b_lat, b_lng) -> Optional[float]:
    a_lat = _float(a_lat)
    a_lng = _float(a_lng)
    b_lat = _float(b_lat)
    b_lng = _float(b_lng)
    if None in (a_lat, a_lng, b_lat, b_lng):
        return None
    phi1 = math.radians(a_lat)
    phi2 = math.radians(b_lat)
    d_phi = math.radians(b_lat - a_lat)
    d_lam = math.radians(b_lng - a_lng)
    s = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.atan2(math.sqrt(s), math.sqrt(1 - s))


def bearing_degrees(a_lat, a_lng, b_lat, b_lng) -> float:
    a_lat = _float(a_lat, 0.0)
    a_lng = _float(a_lng, 0.0)
    b_lat = _float(b_lat, 0.0)
    b_lng = _float(b_lng, 0.0)
    phi1 = math.radians(a_lat)
    phi2 = math.radians(b_lat)
    lam1 = math.radians(a_lng)
    lam2 = math.radians(b_lng)
    y = math.sin(lam2 - lam1) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(lam2 - lam1)
    return normalize_heading(math.degrees(math.atan2(y, x)))


def _issue(level: str, code: str, message: str, scene_id=None, scene_title="", extra=None):
    return {
        "level": level,
        "code": code,
        "message": message,
        "scene_id": scene_id,
        "scene_title": scene_title,
        "extra": extra or {},
    }


def _image_ratio_info(state: StreetViewSourceSceneState) -> Dict[str, Any]:
    f = state.image_file
    if not f:
        return {"ok": False, "width": 0, "height": 0, "ratio": 0, "message": "No image"}
    if Image is None:
        return {"ok": True, "width": 0, "height": 0, "ratio": 0, "message": "Pillow unavailable; ratio skipped"}
    try:
        with Image.open(f.path) as img:
            width, height = img.size
        ratio = width / max(height, 1)
        return {
            "ok": 1.85 <= ratio <= 2.15,
            "width": width,
            "height": height,
            "ratio": ratio,
            "message": "OK" if 1.85 <= ratio <= 2.15 else "Panorama ratio is not close to 2:1",
        }
    except Exception as exc:
        return {"ok": False, "width": 0, "height": 0, "ratio": 0, "message": str(exc)}


def run_quality_check(publication: StreetViewSourcePublication) -> Dict[str, Any]:
    states = list(
        publication.scene_states.select_related("source_scene", "source_scene__tour", "source_scene__tour__place")
        .order_by("source_scene__order", "source_scene_id")
    )
    tour = publication.source_tour
    issues: List[Dict[str, Any]] = []

    if not states:
        issues.append(_issue("blocker", "NO_SCENES", "This tour has no 360 scene."))

    navs = list(
        Hotspot.objects.filter(
            scene__tour=tour,
            type=Hotspot.Type.NAVIGATE,
            target_scene__isnull=False,
        ).values_list("scene_id", "target_scene_id")
    )
    outgoing = {}
    incoming = {}
    for src, dst in navs:
        if src == dst:
            issues.append(_issue("warning", "SELF_LINK", "A navigation link points to itself.", src))
        outgoing.setdefault(src, set()).add(dst)
        incoming.setdefault(dst, set()).add(src)

    gps_index = {}
    coords_by_scene = {}

    for state in states:
        title = state.source_scene.title or f"Scene {state.source_scene_id}"
        lat = state.effective_latitude
        lng = state.effective_longitude
        coords_by_scene[state.source_scene_id] = (lat, lng)

        if not state.has_image:
            issues.append(_issue("blocker", "MISSING_IMAGE", "Scene has no 360 image.", state.source_scene_id, title))
        else:
            ratio = _image_ratio_info(state)
            if not ratio["ok"]:
                issues.append(_issue("warning", "IMAGE_RATIO", ratio["message"], state.source_scene_id, title, ratio))

        if lat is None or lng is None:
            issues.append(_issue("blocker", "MISSING_GPS", "Scene has no GPS position.", state.source_scene_id, title))
        else:
            key = (round(float(lat), 7), round(float(lng), 7))
            gps_index.setdefault(key, []).append(title)

        if normalize_heading(state.heading) != state.heading:
            issues.append(_issue("warning", "HEADING_NORMALIZED", "Heading will be normalized before sending to Google.", state.source_scene_id, title, {"value": state.heading}))
        if state.initial_fov < 10 or state.initial_fov > 120:
            issues.append(_issue("warning", "FOV_RANGE", "FOV should stay between 10 and 120.", state.source_scene_id, title, {"value": state.initial_fov}))

        if len(states) > 1:
            if not outgoing.get(state.source_scene_id):
                issues.append(_issue("warning", "NO_OUTGOING_LINK", "Scene has no outgoing navigation link.", state.source_scene_id, title))
            if not incoming.get(state.source_scene_id):
                issues.append(_issue("warning", "NO_INCOMING_LINK", "Scene has no incoming navigation link.", state.source_scene_id, title))

    for key, titles in gps_index.items():
        if len(titles) > 1:
            issues.append(_issue("warning", "DUPLICATE_GPS", "Several scenes share exactly the same GPS position.", extra={"gps": key, "scenes": titles}))

    # Distance warnings for existing links.
    for src, dst in navs:
        a = coords_by_scene.get(src)
        b = coords_by_scene.get(dst)
        if not a or not b:
            continue
        dist = haversine_meters(a[0], a[1], b[0], b[1])
        if dist is not None and dist > 1000:
            issues.append(_issue("warning", "LONG_CONNECTION", "A connection is more than 1 km. Google may not show it naturally.", src, extra={"target_scene_id": dst, "distance_m": round(dist, 2)}))

    blockers = [x for x in issues if x["level"] == "blocker"]
    warnings = [x for x in issues if x["level"] == "warning"]
    score = max(0, 100 - len(blockers) * 30 - len(warnings) * 7)
    status = "blocked" if blockers else ("needs_attention" if warnings else "ready")

    return {
        "ok": not blockers,
        "status": status,
        "score": score,
        "checked_at": timezone.now().isoformat(),
        "counts": {
            "scenes": len(states),
            "published": sum(1 for s in states if s.google_photo_id),
            "connected": sum(1 for s in states if s.publish_status == StreetViewSourceSceneState.PublishStatus.CONNECTED),
            "navigation_links": len(navs),
            "blockers": len(blockers),
            "warnings": len(warnings),
        },
        "issues": issues,
    }


def build_smart_link_suggestions(publication: StreetViewSourcePublication, *, bidirectional=True, max_distance_m=250.0) -> Dict[str, Any]:
    states = list(
        publication.scene_states.select_related("source_scene")
        .order_by("source_scene__order", "source_scene_id")
    )
    existing = set(
        Hotspot.objects.filter(
            scene__tour=publication.source_tour,
            type=Hotspot.Type.NAVIGATE,
            target_scene__isnull=False,
        ).values_list("scene_id", "target_scene_id")
    )
    suggestions = []

    def add(src_state, dst_state, direction="forward"):
        src = src_state.source_scene
        dst = dst_state.source_scene
        if src.id == dst.id:
            return
        lat1 = src_state.effective_latitude
        lng1 = src_state.effective_longitude
        lat2 = dst_state.effective_latitude
        lng2 = dst_state.effective_longitude
        distance = haversine_meters(lat1, lng1, lat2, lng2)
        heading = bearing_degrees(lat1, lng1, lat2, lng2) if distance is not None else normalize_heading(src.yaw_default or src_state.heading or 0)
        already = (src.id, dst.id) in existing
        suggestions.append({
            "id": f"{src.id}-{dst.id}",
            "from_scene_id": src.id,
            "from_title": src.title,
            "to_scene_id": dst.id,
            "to_title": dst.title,
            "label": ("Back to " if direction == "back" else "Go to ") + (dst.title or f"Scene {dst.id}"),
            "heading": heading,
            "pitch": normalize_pitch(src.pitch_default or src_state.pitch or 0),
            "distance_m": None if distance is None else round(distance, 2),
            "already_exists": already,
            "recommended": (not already) and (distance is None or distance <= max_distance_m),
            "reason": "Already linked" if already else ("Nearby ordered scene" if distance is None or distance <= max_distance_m else "Far scene; review before applying"),
        })

    for current, nxt in zip(states, states[1:]):
        add(current, nxt, "forward")
        if bidirectional:
            add(nxt, current, "back")

    return {
        "ok": True,
        "mode": "ordered_nearby",
        "max_distance_m": max_distance_m,
        "count": len(suggestions),
        "recommended_count": sum(1 for s in suggestions if s["recommended"]),
        "suggestions": suggestions,
    }
