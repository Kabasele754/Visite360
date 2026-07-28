from __future__ import annotations

import json
import os
import threading
import time
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import close_old_connections, transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from apps.organizations.models import Organization, OrganizationMember
from apps.places.models import Place
from apps.tours.models import Hotspot, Scene360, Tour

from .canonical_serializers import (
    organization_to_dict,
    place_to_dict,
    source_publication_to_dict,
    source_publish_job_to_dict,
    source_scene_state_to_dict,
    source_tour_to_dict,
)
from .models import (
    StreetViewGoogleAccount,
    StreetViewAnalyticsEvent,
    StreetViewHistoryEvent,
    StreetViewQualityReport,
    StreetViewSourcePublication,
    StreetViewSourcePublishJob,
    StreetViewSourceSceneState,
)
from .services.streetview_publish import StreetViewPublishClient, StreetViewPublishError, extract_google_photo_fields
from .services.tokens import GoogleStreetViewAuthError, get_valid_access_token
from .services.orientation import normalize_heading, normalize_pitch, normalize_roll, normalize_fov
from .services.xmp import prepare_streetview_jpeg_with_xmp
from .services.quality import run_quality_check, build_smart_link_suggestions
from .services.analytics import record_history, record_analytics
from .services.publish_runner import run_source_publish_job
from .services.status_sync import sync_source_publication, repair_source_connections


def _json(data=None, *, status=200):
    return JsonResponse(data or {}, status=status, json_dumps_params={"ensure_ascii": False})


def _body(request):
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return None


def _absolute(request, url):
    if not url:
        return ""
    return request.build_absolute_uri(url)


def _as_decimal(value):
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return None


def _as_float(value, default=None):
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _user_orgs_queryset(user):
    qs = Organization.objects.all().order_by("name")
    if user.is_staff or user.is_superuser:
        return qs
    return qs.filter(memberships__user=user, memberships__is_active=True).distinct()


def _owned_org(request, org_id):
    return get_object_or_404(_user_orgs_queryset(request.user), pk=org_id)


def _owned_place(request, place_id):
    orgs = _user_orgs_queryset(request.user).values_list("id", flat=True)
    return get_object_or_404(Place.objects.filter(organization_id__in=orgs), pk=place_id)


def _owned_source_tour(request, tour_id):
    orgs = _user_orgs_queryset(request.user).values_list("id", flat=True)
    return get_object_or_404(
        Tour.objects.select_related("organization", "place").prefetch_related("scenes"),
        pk=tour_id,
        organization_id__in=orgs,
    )


def _ensure_source_publication(request, tour: Tour) -> StreetViewSourcePublication:
    publication, _ = StreetViewSourcePublication.objects.get_or_create(
        source_tour=tour,
        defaults={"owner": request.user, "status": StreetViewSourcePublication.Status.DRAFT},
    )

    # Keep the owner stable but allow project owner/staff to take ownership if created by another admin.
    if publication.owner_id != request.user.id and (request.user.is_staff or request.user.is_superuser):
        publication.owner = request.user
        publication.save(update_fields=["owner", "updated_at"])

    existing = set(publication.scene_states.values_list("source_scene_id", flat=True))
    new_states = []
    scenes = Scene360.objects.filter(tour=tour).order_by("order", "id")
    for scene in scenes:
        if scene.id in existing:
            continue
        new_states.append(
            StreetViewSourceSceneState(
                publication=publication,
                source_scene=scene,
                heading=normalize_heading(scene.yaw_default or 0),
                pitch=normalize_pitch(scene.pitch_default or 0),
                roll=0,
                initial_fov=normalize_fov(scene.hfov_default or 90),
                publish_status=StreetViewSourceSceneState.PublishStatus.READY,
            )
        )
    if new_states:
        StreetViewSourceSceneState.objects.bulk_create(new_states)

    return publication


def _publication_for_source_tour(request, tour_id):
    tour = _owned_source_tour(request, tour_id)
    return _ensure_source_publication(request, tour)


def _google_share_link(photo_id):
    if not photo_id:
        return ""
    compact = photo_id.replace("CAoS", "CIAB", 1).rstrip(".")
    return f"https://www.google.com/maps/@0,0,0a,90y,90t/data=!3m4!1e1!3m2!1s{compact}!2e10"


def _client_for_user(request):
    account = StreetViewGoogleAccount.objects.filter(user=request.user).first()
    if not account or not account.is_connected:
        raise GoogleStreetViewAuthError("Google Street View account is not connected.")
    return StreetViewPublishClient(access_token=get_valid_access_token(account))


def _source_state_proxy(state: StreetViewSourceSceneState):
    """Compatibility object for existing XMP and Street View client services."""
    lat = state.effective_latitude
    lng = state.effective_longitude
    return SimpleNamespace(
        id=state.id,
        title=state.source_scene.title,
        image=state.image_file,
        latitude=lat,
        longitude=lng,
        altitude=state.altitude,
        heading=normalize_heading(state.heading),
        pitch=normalize_pitch(state.pitch),
        roll=normalize_roll(state.roll),
        initial_fov=normalize_fov(state.initial_fov),
        capture_time=None,
    )


def _source_connection_map(publication: StreetViewSourcePublication):
    tour = publication.source_tour
    scene_ids = set(tour.scenes.values_list("id", flat=True))
    connection_map = {scene_id: set() for scene_id in scene_ids}

    navs = Hotspot.objects.filter(
        scene__tour=tour,
        type=Hotspot.Type.NAVIGATE,
        target_scene__isnull=False,
    ).values_list("scene_id", "target_scene_id")

    for source_id, target_id in navs:
        if source_id in scene_ids and target_id in scene_ids and source_id != target_id:
            connection_map[source_id].add(target_id)

    return {scene_id: list(targets) for scene_id, targets in connection_map.items()}


def _is_photo_not_ready_error(exc: StreetViewPublishError) -> bool:
    """Google can return "Photo with id ... does not exist" just after photo.create.

    The photo has been accepted, but the connection update endpoint may need
    a short processing delay before it can see the new photo IDs.
    """
    message = str(exc).lower()
    return (
        "does not exist" in message
        or "not found" in message
        or "photo with id" in message
    )


def _send_source_connections(
    client: StreetViewPublishClient,
    publication: StreetViewSourcePublication,
    *,
    max_attempts: int = 5,
    delay_seconds: float = 4.0,
):
    states = {
        state.source_scene_id: state
        for state in publication.scene_states.select_related("source_scene").all()
    }
    connection_map = _source_connection_map(publication)
    results = []
    warnings = 0
    updated = 0

    for source_scene_id, state in states.items():
        if not state.google_photo_id:
            continue

        target_photo_ids = []
        for target_source_scene_id in connection_map.get(source_scene_id, []):
            target_state = states.get(target_source_scene_id)
            if target_state and target_state.google_photo_id:
                target_photo_ids.append(target_state.google_photo_id)

        # Stable order + dedupe, so retrying does not create noisy payloads.
        target_photo_ids = list(dict.fromkeys(target_photo_ids))

        if not target_photo_ids:
            state.connection_sync_status = "not_required"
            state.connection_audit = {
                "expected": [],
                "actual": [],
                "missing": [],
                "unexpected": [],
                "checked_at": timezone.now().isoformat(),
                "message": "This panorama has no outgoing Google navigation connection.",
            }
            state.save(update_fields=["connection_sync_status", "connection_audit", "updated_at"])
            results.append({
                "scene_id": source_scene_id,
                "state_id": state.id,
                "ok": True,
                "message": "No outgoing connection to send.",
                "targets": [],
            })
            continue

        last_error = None
        for attempt in range(1, max_attempts + 1):
            try:
                client.update_photo_connections(state.google_photo_id, target_photo_ids)
                # Google accepted the update request. A later photo.get verification is
                # still required before the dashboard calls the connection synchronized.
                state.publish_status = StreetViewSourceSceneState.PublishStatus.CONNECTED
                state.connection_sync_status = "verification_pending"
                state.connection_audit = {
                    "expected": target_photo_ids,
                    "actual": [],
                    "missing": target_photo_ids,
                    "unexpected": [],
                    "checked_at": timezone.now().isoformat(),
                    "message": "Connection update accepted; waiting for Google indexing verification.",
                }
                state.last_error = ""
                state.save(update_fields=[
                    "publish_status", "connection_sync_status", "connection_audit",
                    "last_error", "updated_at",
                ])
                updated += 1
                suffix = "" if attempt == 1 else f" after {attempt} attempts"
                results.append({
                    "scene_id": source_scene_id,
                    "state_id": state.id,
                    "ok": True,
                    "message": f"Google connections updated{suffix}.",
                    "targets": target_photo_ids,
                })
                last_error = None
                break
            except StreetViewPublishError as exc:
                last_error = exc
                if attempt < max_attempts and _is_photo_not_ready_error(exc):
                    time.sleep(delay_seconds * attempt)
                    continue
                break

        if last_error is not None:
            warnings += 1
            state.connection_sync_status = "retry_required"
            state.connection_audit = {
                "expected": target_photo_ids,
                "actual": [],
                "missing": target_photo_ids,
                "unexpected": [],
                "checked_at": timezone.now().isoformat(),
                "message": "Google has not exposed the requested navigation links yet.",
            }
            state.last_error = str(last_error)
            state.save(update_fields=["connection_sync_status", "connection_audit", "last_error", "updated_at"])
            results.append({
                "scene_id": source_scene_id,
                "state_id": state.id,
                "ok": False,
                "message": str(last_error),
                "targets": target_photo_ids,
                "retry_advice": "Photos are published, but Google may not see them for connections yet. Retry connections in a few minutes.",
            })

    return {"updated": updated, "warnings": warnings, "results": results}



def _photo_id_from_payload(photo: dict) -> str:
    photo_id = photo.get("photoId") or photo.get("photo_id") or {}
    if isinstance(photo_id, dict):
        return str(photo_id.get("id") or photo_id.get("photo_id") or "").strip()
    return str(photo_id or "").strip()


def _photo_status(photo: dict) -> str:
    return str(
        photo.get("mapsPublishStatus")
        or photo.get("maps_publish_status")
        or photo.get("status")
        or "UNKNOWN"
    ).strip()


def _photo_pose(photo: dict) -> dict:
    pose = photo.get("pose") or {}
    latlng = pose.get("latLngPair") or pose.get("lat_lng_pair") or {}
    return {
        "latitude": _as_float(latlng.get("latitude"), None),
        "longitude": _as_float(latlng.get("longitude"), None),
        "altitude": _as_float(pose.get("altitude"), None),
        "heading": normalize_heading(pose.get("heading", 0)),
        "pitch": normalize_pitch(pose.get("pitch", 0)),
        "roll": normalize_roll(pose.get("roll", 0)),
    }


def _scene_file_url(request, scene) -> str:
    """Best public preview for a local Scene360, used when Google does not return a thumbnail."""
    if not scene:
        return ""
    candidates = [
        getattr(scene, "thumbnail_url", "") or "",
        getattr(scene, "image_360_preview_url", "") or "",
        getattr(scene, "image_360_mobile_url", "") or "",
        getattr(scene, "image_360_url", "") or "",
    ]
    for value in candidates:
        if value:
            value = str(value)
            if value.startswith("http://") or value.startswith("https://"):
                return value
            return request.build_absolute_uri(value)
    for field_name in ("thumbnail_image", "image_360_preview", "image_360_mobile", "image_360"):
        f = getattr(scene, field_name, None)
        if f:
            try:
                return request.build_absolute_uri(f.url)
            except Exception:
                pass
    return ""


def _google_photo_library_item(request, photo: dict, local_state=None, *, source="google") -> dict:
    photo_id = _photo_id_from_payload(photo)
    pose = _photo_pose(photo)
    connections = []
    for item in (photo.get("connections") or []):
        target = item.get("target") or {}
        target_id = target.get("id") or item.get("targetPhotoId") or ""
        if target_id:
            connections.append(str(target_id))

    local = {"matched": False}
    if local_state is not None:
        scene = local_state.source_scene
        tour = scene.tour
        place = getattr(tour, "place", None)
        org = getattr(tour, "organization", None)
        local = {
            "matched": True,
            "state_id": local_state.id,
            "source_scene_id": scene.id,
            "scene_title": scene.title,
            "tour_id": tour.id,
            "tour_title": tour.title,
            "organization_id": org.id if org else None,
            "organization_name": org.name if org else "",
            "place_id": place.id if place else None,
            "place_name": place.name if place else "",
            "publish_status": local_state.publish_status,
            "preview_url": _scene_file_url(request, scene),
        }

    share_link = photo.get("shareLink") or photo.get("share_link") or ""
    if not share_link and photo_id:
        share_link = _google_share_link(photo_id)

    return {
        "photo_id": photo_id,
        "source": source,
        "maps_publish_status": _photo_status(photo),
        "share_link": share_link,
        "thumbnail_url": photo.get("thumbnailUrl") or photo.get("thumbnail_url") or (local.get("preview_url") if local.get("matched") else ""),
        "download_url": photo.get("downloadUrl") or photo.get("download_url") or (local.get("preview_url") if local.get("matched") else ""),
        "capture_time": photo.get("captureTime") or photo.get("capture_time") or "",
        "upload_time": photo.get("uploadTime") or photo.get("upload_time") or "",
        "pose": pose,
        "connections": connections,
        "connections_count": len(connections),
        "local": local,
    }




def _google_photo_sequence_id(seq: dict) -> str:
    response = seq.get("response") or seq.get("photoSequence") or seq.get("photo_sequence") or {}
    if isinstance(response, dict):
        value = response.get("id") or response.get("sequenceId") or response.get("photoSequenceId") or ""
        if value:
            return str(value).strip()
    name = str(seq.get("name") or "").strip()
    return name.rsplit("/", 1)[-1] if name else ""


def _google_photo_sequence_item(seq: dict) -> dict:
    response = seq.get("response") or seq.get("photoSequence") or seq.get("photo_sequence") or {}
    error = seq.get("error") or {}
    done = bool(seq.get("done", False))
    sequence_id = _google_photo_sequence_id(seq)
    filename = ""
    status = "PROCESSING"
    upload_time = ""
    capture_time = ""
    distance_meters = None
    photos_count = None

    if isinstance(response, dict):
        filename = str(response.get("filename") or response.get("filenameQuery") or response.get("fileName") or "").strip()
        status = str(response.get("processingState") or response.get("processing_state") or response.get("mapsPublishStatus") or "DONE").strip()
        upload_time = response.get("uploadTime") or response.get("upload_time") or ""
        capture_time = response.get("captureTimeOverride") or response.get("capture_time_override") or ""
        distance_meters = response.get("distanceMeters") or response.get("distance_meters")
        photos_count = response.get("photosCount") or response.get("photos_count") or response.get("photoCount")

    if error:
        status = f"ERROR: {error.get('message') or error.get('code') or 'processing failed'}"
    elif not done:
        status = "PROCESSING"

    return {
        "sequence_id": sequence_id,
        "name": seq.get("name") or "",
        "done": done,
        "status": status,
        "filename": filename,
        "upload_time": upload_time,
        "capture_time": capture_time,
        "distance_meters": distance_meters,
        "photos_count": photos_count,
        "error": error,
        "raw": seq,
    }


def _local_google_states_for_user(request, photo_ids=None):
    qs = StreetViewSourceSceneState.objects.select_related(
        "source_scene",
        "source_scene__tour",
        "source_scene__tour__organization",
        "source_scene__tour__place",
        "publication",
    ).filter(
        publication__owner=request.user,
        google_photo_id__gt="",
    )
    if photo_ids is not None:
        qs = qs.filter(google_photo_id__in=photo_ids)
    return qs


@login_required
@require_GET
def publisher_page(request):
    return render(
        request,
        "app_streetview/canonical_publisher.html",
        {
            "google_maps_api_key": (
                getattr(settings, "GOOGLE_MAPS_API_KEY", "")
                or getattr(settings, "GOOGLE_MAPS_BROWSER_KEY", "")
            ),
            "google_maps_map_id": getattr(settings, "GOOGLE_MAPS_MAP_ID", "DEMO_MAP_ID"),
        },
    )


@login_required
@require_GET
def organizations(request):
    qs = _user_orgs_queryset(request.user)
    return _json({"results": [organization_to_dict(org) for org in qs]})


@login_required
@require_GET
def organization_places(request, org_id):
    org = _owned_org(request, org_id)
    qs = Place.objects.filter(organization=org).order_by("name")
    return _json({"organization": organization_to_dict(org), "results": [place_to_dict(place) for place in qs]})


@login_required
@require_GET
def place_tours(request, place_id):
    place = _owned_place(request, place_id)
    tours = Tour.objects.filter(place=place).select_related("organization", "place").annotate(scenes_count=Count("scenes")).order_by("-created_at")
    publications = {p.source_tour_id: p for p in StreetViewSourcePublication.objects.filter(source_tour__in=tours)}
    return _json({
        "place": place_to_dict(place),
        "results": [source_tour_to_dict(tour, publication=publications.get(tour.id)) for tour in tours],
    })


@login_required
@require_GET
def source_tour_detail(request, tour_id):
    publication = _publication_for_source_tour(request, tour_id)
    record_analytics(publication, request.user, "tour_opened")
    return _json(source_publication_to_dict(publication, absolute_url_builder=lambda url: _absolute(request, url)))


@login_required
@require_POST
def source_apply_place_gps(request, tour_id):
    publication = _publication_for_source_tour(request, tour_id)
    tour = publication.source_tour
    data = _body(request)
    if data is None:
        return _json({"ok": False, "error": "JSON invalide."}, status=400)

    lat = _as_decimal(data.get("latitude"))
    lng = _as_decimal(data.get("longitude"))
    if lat is None or lng is None:
        if tour.lat is not None and tour.lng is not None:
            lat, lng = Decimal(str(tour.lat)), Decimal(str(tour.lng))
        elif tour.place.latitude is not None and tour.place.longitude is not None:
            lat, lng = tour.place.latitude, tour.place.longitude

    if lat is None or lng is None:
        return _json({"ok": False, "error": "No GPS found on the tour or place."}, status=400)

    apply_to = data.get("apply_to") or "missing"  # missing | all
    qs = publication.scene_states.all()
    if apply_to == "missing":
        qs = [s for s in qs if not s.has_gps]
    count = 0
    for state in qs:
        state.latitude = lat
        state.longitude = lng
        state.publish_status = StreetViewSourceSceneState.PublishStatus.READY
        state.save(update_fields=["latitude", "longitude", "publish_status", "updated_at"])
        count += 1
    return _json({"ok": True, "updated": count, **source_publication_to_dict(publication, absolute_url_builder=lambda url: _absolute(request, url))})


@login_required
@require_http_methods(["PATCH", "POST"])
def source_scene_state_update(request, source_scene_id):
    scene = get_object_or_404(Scene360.objects.select_related("tour"), pk=source_scene_id)
    _owned_source_tour(request, scene.tour_id)
    publication = _ensure_source_publication(request, scene.tour)
    state = get_object_or_404(StreetViewSourceSceneState, publication=publication, source_scene=scene)
    data = _body(request)
    if data is None:
        return _json({"ok": False, "error": "JSON invalide."}, status=400)

    gps = data.get("gps") or data
    if "latitude" in gps:
        state.latitude = _as_decimal(gps.get("latitude"))
    if "longitude" in gps:
        state.longitude = _as_decimal(gps.get("longitude"))
    if "altitude" in gps:
        state.altitude = _as_float(gps.get("altitude"), None)

    camera = data.get("camera") or data
    if "heading" in camera:
        state.heading = normalize_heading(camera.get("heading"), state.heading)
    if "pitch" in camera:
        state.pitch = normalize_pitch(camera.get("pitch"), state.pitch)
    if "roll" in camera:
        state.roll = normalize_roll(camera.get("roll"), state.roll)
    if "initial_fov" in camera:
        state.initial_fov = normalize_fov(camera.get("initial_fov"), state.initial_fov)

    state.publish_status = StreetViewSourceSceneState.PublishStatus.READY if state.has_gps else StreetViewSourceSceneState.PublishStatus.LOCAL
    state.save()
    return _json({"ok": True, "scene": source_scene_state_to_dict(state, absolute_url_builder=lambda url: _absolute(request, url))})


def _ensure_navigation_hotspot(request=None, *, organization, scene, target_scene, label, yaw, pitch):
    """Create one navigation hotspot per (organization, scene, target_scene).

    We do not use get_or_create here because old data can contain duplicate
    hotspots for the same source/target pair. In that case Django raises
    MultipleObjectsReturned. This helper keeps the oldest one, updates it,
    and removes exact duplicates created by previous auto-link attempts.
    """
    qs = Hotspot.objects.filter(
        organization=organization,
        scene=scene,
        type=Hotspot.Type.NAVIGATE,
        target_scene=target_scene,
    ).order_by("id")

    hotspot = qs.first()
    duplicate_count = max(qs.count() - 1, 0)

    if hotspot:
        changed = False
        updates = {
            "label": label,
            "yaw": yaw,
            "pitch": pitch,
            "tooltip_text": label,
            "title": label,
        }
        for field, value in updates.items():
            if hasattr(hotspot, field) and getattr(hotspot, field) != value:
                setattr(hotspot, field, value)
                changed = True
        if changed:
            hotspot.save()

        if duplicate_count:
            qs.exclude(pk=hotspot.pk).delete()

        return hotspot, False, duplicate_count

    hotspot = Hotspot.objects.create(
        organization=organization,
        scene=scene,
        type=Hotspot.Type.NAVIGATE,
        target_scene=target_scene,
        label=label,
        yaw=yaw,
        pitch=pitch,
        tooltip_text=label,
        title=label,
    )
    return hotspot, True, 0


def _auto_link_source_tour(tour, *, bidirectional: bool = True, request=None):
    scenes = list(Scene360.objects.filter(tour=tour, is_public=True).order_by("order", "id"))
    created = 0
    duplicates_removed = 0

    with transaction.atomic():
        for src, dst in zip(scenes, scenes[1:]):
            _, was_created, removed = _ensure_navigation_hotspot(
                request=request,
                organization=tour.organization,
                scene=src,
                target_scene=dst,
                label=f"Vers {dst.title}",
                yaw=src.yaw_default or 0,
                pitch=src.pitch_default or 0,
            )
            created += 1 if was_created else 0
            duplicates_removed += removed

            if bidirectional:
                _, was_created, removed = _ensure_navigation_hotspot(
                    request=request,
                    organization=tour.organization,
                    scene=dst,
                    target_scene=src,
                    label=f"Retour {src.title}",
                    yaw=dst.yaw_default or 0,
                    pitch=dst.pitch_default or 0,
                )
                created += 1 if was_created else 0
                duplicates_removed += removed

    return {
        "created": created,
        "duplicates_removed": duplicates_removed,
        "scenes": len(scenes),
    }


@login_required
@require_POST
def source_auto_link(request, tour_id):
    publication = _publication_for_source_tour(request, tour_id)
    data = _body(request) or {}
    bidirectional = bool(data.get("bidirectional", True))
    result = _auto_link_source_tour(publication.source_tour, bidirectional=bidirectional, request=request)
    record_history(publication, request.user, StreetViewHistoryEvent.Action.AUTO_LINK, f"Auto-link created/updated {result.get('created', 0)} connection(s).", metadata=result)
    return _json({"ok": True, **result, **source_publication_to_dict(publication, absolute_url_builder=lambda url: _absolute(request, url))})


@login_required
@require_GET
def source_connections(request, tour_id):
    publication = _publication_for_source_tour(request, tour_id)
    return _json({
        "ok": True,
        **source_publication_to_dict(publication, absolute_url_builder=lambda url: _absolute(request, url)),
    })


@login_required
@require_POST
def source_add_connection(request, tour_id):
    publication = _publication_for_source_tour(request, tour_id)
    tour = publication.source_tour
    data = _body(request)
    if data is None:
        return _json({"ok": False, "error": "JSON invalide."}, status=400)

    from_scene_id = data.get("from_scene_id") or data.get("source_scene_id") or data.get("scene")
    to_scene_id = data.get("to_scene_id") or data.get("target_scene_id") or data.get("target_scene")

    if not from_scene_id or not to_scene_id:
        return _json({"ok": False, "error": "Source scene and target scene are required."}, status=400)

    if str(from_scene_id) == str(to_scene_id):
        return _json({"ok": False, "error": "Source scene and target scene must be different."}, status=400)

    source_scene = get_object_or_404(Scene360, pk=from_scene_id, tour=tour)
    target_scene = get_object_or_404(Scene360, pk=to_scene_id, tour=tour)

    label = (data.get("label") or f"Vers {target_scene.title}").strip()
    yaw = _as_float(data.get("yaw"), source_scene.yaw_default or 0) or 0
    pitch = _as_float(data.get("pitch"), source_scene.pitch_default or 0) or 0

    hotspot, was_created, removed = _ensure_navigation_hotspot(
        request=request,
        organization=tour.organization,
        scene=source_scene,
        target_scene=target_scene,
        label=label,
        yaw=yaw,
        pitch=pitch,
    )

    record_history(publication, request.user, StreetViewHistoryEvent.Action.MANUAL_LINK, f"Manual link: {source_scene.title} → {target_scene.title}", metadata={"hotspot_id": hotspot.id, "created": was_created})
    return _json({
        "ok": True,
        "created": was_created,
        "duplicates_removed": removed,
        "hotspot_id": hotspot.id,
        **source_publication_to_dict(publication, absolute_url_builder=lambda url: _absolute(request, url)),
    })


@login_required
@require_POST
def source_delete_connection(request, tour_id, hotspot_id):
    publication = _publication_for_source_tour(request, tour_id)
    hotspot = get_object_or_404(
        Hotspot,
        pk=hotspot_id,
        scene__tour=publication.source_tour,
        type=Hotspot.Type.NAVIGATE,
    )
    hotspot.delete()
    return _json({
        "ok": True,
        "deleted": hotspot_id,
        **source_publication_to_dict(publication, absolute_url_builder=lambda url: _absolute(request, url)),
    })



@login_required
@require_GET
def google_published_photos(request):
    """Return Google Street View photos for the connected account.

    Main mode is account-first: list photos directly from Google using the
    connected OAuth account, including photos that were not created by
    TwinScopes. Local StreetViewSourceSceneState rows are used only as optional
    metadata when a returned Google Photo ID matches a local scene.
    """
    try:
        client = _client_for_user(request)
    except GoogleStreetViewAuthError as exc:
        return _json({
            "ok": False,
            "error": str(exc),
            "oauth_url": request.build_absolute_uri(reverse("apps.app_streetview:oauth_start")),
        }, status=401)

    page_size = min(max(int(request.GET.get("page_size") or 100), 1), 100)
    page_token = (request.GET.get("page_token") or "").strip()
    view = (request.GET.get("view") or "INCLUDE_DOWNLOAD_URL").strip()
    # mode=account means: Google account is the source of truth.
    # It returns all photos visible to photos.list for the connected Gmail,
    # even when they are not linked to any TwinScopes tour.
    mode = (request.GET.get("mode") or "account").strip().lower()
    account_only = mode in {"account", "google", "all_google"}

    # include_local only adds TwinScopes-local photos that Google has not
    # returned yet, useful immediately after publishing because Google can
    # take time to index new photos. For the Google Library tab, keep it off
    # so the list truly means "what this Google account already owns".
    include_local = (request.GET.get("include_local") or ("0" if account_only else "1")) != "0"
    load_all = (request.GET.get("all") or "1") != "0" and not page_token
    max_pages = min(max(int(request.GET.get("max_pages") or 200), 1), 300)

    include_sequences = (request.GET.get("include_sequences") or "1") != "0"
    sequences_data = {"photoSequences": [], "nextPageToken": "", "pages": 0}
    photos_error = ""
    sequences_error = ""

    try:
        if load_all:
            data = client.list_all_photos(page_size=page_size, max_pages=max_pages, view=view)
        else:
            data = client.list_photos(page_size=page_size, page_token=page_token, view=view)
    except StreetViewPublishError as exc:
        # Keep the response usable and show the local index/diagnostics when possible.
        data = {"photos": [], "nextPageToken": "", "pages": 0}
        photos_error = str(exc)
        if not include_local:
            return _json({
                "ok": False,
                "error": str(exc),
                "payload": getattr(exc, "payload", {}),
            }, status=getattr(exc, "status_code", None) or 400)

    if include_sequences and not page_token:
        try:
            sequences_data = client.list_all_photo_sequences(page_size=100, max_pages=max_pages)
        except StreetViewPublishError as exc:
            sequences_error = str(exc)

    google_photos = data.get("photos") or []
    google_ids = [_photo_id_from_payload(photo) for photo in google_photos]
    google_ids = [photo_id for photo_id in google_ids if photo_id]
    states_by_photo_id = {
        state.google_photo_id: state
        for state in _local_google_states_for_user(request, google_ids)
    }

    items = []
    seen = set()
    for photo in google_photos:
        photo_id = _photo_id_from_payload(photo)
        if not photo_id:
            continue
        seen.add(photo_id)
        items.append(_google_photo_library_item(
            request,
            photo,
            states_by_photo_id.get(photo_id),
            source="google",
        ))

    local_index_total = _local_google_states_for_user(request).count()

    if include_local:
        for state in _local_google_states_for_user(request).exclude(google_photo_id__in=seen):
            photo = {
                "photoId": {"id": state.google_photo_id},
                "shareLink": state.google_share_link or _google_share_link(state.google_photo_id),
                "thumbnailUrl": state.google_thumbnail_url or _scene_file_url(request, state.source_scene),
                "downloadUrl": _scene_file_url(request, state.source_scene),
                "mapsPublishStatus": "LOCAL_INDEXED",
                "pose": {
                    "latLngPair": {
                        "latitude": float(state.effective_latitude) if state.effective_latitude is not None else None,
                        "longitude": float(state.effective_longitude) if state.effective_longitude is not None else None,
                    },
                    "altitude": state.altitude,
                    "heading": state.heading,
                    "pitch": state.pitch,
                    "roll": state.roll,
                },
            }
            items.append(_google_photo_library_item(request, photo, state, source="local"))

    sequence_items = [
        _google_photo_sequence_item(seq)
        for seq in (sequences_data.get("photoSequences") or sequences_data.get("photo_sequences") or [])
    ]

    stats = {
        "total": len(items),
        "matched": sum(1 for item in items if item["local"].get("matched")),
        "unmatched": sum(1 for item in items if not item["local"].get("matched")),
        "published": sum(1 for item in items if str(item.get("maps_publish_status", "")).upper() in {"PUBLISHED", "LOCAL_INDEXED"}),
        "rejected": sum(1 for item in items if "REJECTED" in str(item.get("maps_publish_status", "")).upper()),
        "from_google_account": sum(1 for item in items if item.get("source") == "google"),
        "from_local_index": sum(1 for item in items if item.get("source") == "local"),
        "sequences": len(sequence_items),
        "google_raw_photos": len(google_photos),
        "local_index_total": local_index_total,
    }

    message = ""
    if not google_photos and not sequence_items:
        message = (
            "Google returned 0 photos and 0 photo sequences for this OAuth account. "
            "If you see photos in Google Maps, reconnect with the exact Gmail that owns them, "
            "or note that some Google Maps/Street View Studio contributions may not be exposed as Photo resources immediately."
        )

    return _json({
        "ok": True,
        "results": items,
        "stats": stats,
        "sequences": sequence_items,
        "sequences_nextPageToken": sequences_data.get("nextPageToken") or sequences_data.get("next_page_token") or "",
        "nextPageToken": data.get("nextPageToken") or "",
        "raw_count": len(google_photos),
        "source_mode": mode,
        "account_only": account_only,
        "include_local": include_local,
        "include_sequences": include_sequences,
        "pages_loaded": data.get("pages", 1),
        "sequence_pages_loaded": sequences_data.get("pages", 0),
        "message": message,
        "diagnostics": {
            "photos_error": photos_error,
            "sequences_error": sequences_error,
            "local_index_total": local_index_total,
            "google_raw_photos": len(google_photos),
            "google_sequences": len(sequence_items),
        },
    })


@login_required
@require_POST
def google_delete_published_photo(request):
    data = _body(request)
    if data is None:
        return _json({"ok": False, "error": "JSON invalide."}, status=400)
    photo_id = (data.get("photo_id") or data.get("google_photo_id") or "").strip()
    if not photo_id:
        return _json({"ok": False, "error": "Google Photo ID requis."}, status=400)

    try:
        client = _client_for_user(request)
        client.delete_photo(photo_id)
    except GoogleStreetViewAuthError as exc:
        return _json({"ok": False, "error": str(exc)}, status=401)
    except StreetViewPublishError as exc:
        return _json({"ok": False, "error": str(exc), "payload": getattr(exc, "payload", {})}, status=getattr(exc, "status_code", None) or 400)

    updated = 0
    for state in _local_google_states_for_user(request).filter(google_photo_id=photo_id):
        state.google_photo_id = ""
        state.google_share_link = ""
        state.google_thumbnail_url = ""
        state.upload_reference_url = ""
        state.publish_status = StreetViewSourceSceneState.PublishStatus.READY if state.has_gps else StreetViewSourceSceneState.PublishStatus.LOCAL
        state.last_error = "Photo deleted from the Google library."
        state.save(update_fields=[
            "google_photo_id",
            "google_share_link",
            "google_thumbnail_url",
            "upload_reference_url",
            "publish_status",
            "last_error",
            "updated_at",
        ])
        updated += 1

    return _json({"ok": True, "deleted_photo_id": photo_id, "local_states_cleared": updated})


@login_required
@require_POST
def google_link_photo_to_scene(request):
    data = _body(request)
    if data is None:
        return _json({"ok": False, "error": "JSON invalide."}, status=400)
    photo_id = (data.get("photo_id") or data.get("google_photo_id") or "").strip()
    source_scene_id = data.get("source_scene_id") or data.get("scene_id")
    if not photo_id or not source_scene_id:
        return _json({"ok": False, "error": "Photo ID and source scene are required."}, status=400)

    scene = get_object_or_404(Scene360.objects.select_related("tour"), pk=source_scene_id)
    publication = _publication_for_source_tour(request, scene.tour_id)
    state = get_object_or_404(StreetViewSourceSceneState, publication=publication, source_scene=scene)

    # Try to enrich from Google, but do not block manual linking if Google is still indexing.
    share_link = (data.get("share_link") or _google_share_link(photo_id)).strip()
    thumb = data.get("thumbnail_url") or ""
    try:
        client = _client_for_user(request)
        google_photo = client.get_photo(photo_id, view="INCLUDE_DOWNLOAD_URL")
        share_link = google_photo.get("shareLink") or share_link
        thumb = google_photo.get("thumbnailUrl") or thumb
    except Exception:
        pass

    state.google_photo_id = photo_id
    state.google_share_link = share_link
    state.google_thumbnail_url = thumb
    state.publish_status = StreetViewSourceSceneState.PublishStatus.CREATED
    state.last_error = ""
    state.save(update_fields=["google_photo_id", "google_share_link", "google_thumbnail_url", "publish_status", "last_error", "updated_at"])

    return _json({
        "ok": True,
        "scene": source_scene_state_to_dict(state, absolute_url_builder=lambda url: _absolute(request, url)),
        **source_publication_to_dict(publication, absolute_url_builder=lambda url: _absolute(request, url)),
    })


@login_required
@require_POST
def google_update_published_photo_pose(request):
    data = _body(request)
    if data is None:
        return _json({"ok": False, "error": "JSON invalide."}, status=400)
    photo_id = (data.get("photo_id") or data.get("google_photo_id") or "").strip()
    if not photo_id:
        return _json({"ok": False, "error": "Google Photo ID requis."}, status=400)

    proxy = SimpleNamespace(
        latitude=_as_decimal(data.get("latitude")),
        longitude=_as_decimal(data.get("longitude")),
        altitude=_as_float(data.get("altitude"), None),
        heading=normalize_heading(data.get("heading", 0)),
        pitch=normalize_pitch(data.get("pitch", 0)),
        roll=normalize_roll(data.get("roll", 0)),
    )
    if proxy.latitude is None or proxy.longitude is None:
        return _json({"ok": False, "error": "Latitude et longitude sont requis."}, status=400)

    try:
        client = _client_for_user(request)
        result = client.update_photo_pose(photo_id, proxy)
    except GoogleStreetViewAuthError as exc:
        return _json({"ok": False, "error": str(exc)}, status=401)
    except StreetViewPublishError as exc:
        return _json({"ok": False, "error": str(exc), "payload": getattr(exc, "payload", {})}, status=getattr(exc, "status_code", None) or 400)

    updated = 0
    for state in _local_google_states_for_user(request).filter(google_photo_id=photo_id):
        state.latitude = proxy.latitude
        state.longitude = proxy.longitude
        state.altitude = proxy.altitude
        state.heading = proxy.heading
        state.pitch = proxy.pitch
        state.roll = proxy.roll
        state.last_error = ""
        state.save(update_fields=["latitude", "longitude", "altitude", "heading", "pitch", "roll", "last_error", "updated_at"])
        updated += 1

    return _json({"ok": True, "google": result, "local_states_updated": updated})


@login_required
@require_POST
def source_mark_scene_published(request, source_scene_id):
    scene = get_object_or_404(Scene360.objects.select_related("tour"), pk=source_scene_id)
    publication = _publication_for_source_tour(request, scene.tour_id)
    state = get_object_or_404(StreetViewSourceSceneState, publication=publication, source_scene=scene)
    data = _body(request)
    if data is None:
        return _json({"ok": False, "error": "JSON invalide."}, status=400)
    photo_id = (data.get("google_photo_id") or data.get("photo_id") or "").strip()
    if not photo_id:
        return _json({"ok": False, "error": "Google Photo ID requis."}, status=400)
    state.google_photo_id = photo_id
    state.google_share_link = (data.get("google_share_link") or data.get("share_link") or _google_share_link(photo_id)).strip()
    state.publish_status = StreetViewSourceSceneState.PublishStatus.CREATED
    state.last_error = ""
    state.save(update_fields=["google_photo_id", "google_share_link", "publish_status", "last_error", "updated_at"])
    return _json({"ok": True, "scene": source_scene_state_to_dict(state, absolute_url_builder=lambda url: _absolute(request, url))})


@login_required
@require_POST
def source_delete_google_photo(request, source_scene_id):
    """Delete a published Street View photo from Google and clear local publication state.

    This does not delete the original Scene360 or its image in the user's app.
    It only removes the Google Street View photo (when possible) and resets the
    StreetViewSourceSceneState so the scene can be published again later.
    """
    scene = get_object_or_404(Scene360.objects.select_related("tour"), pk=source_scene_id)
    publication = _publication_for_source_tour(request, scene.tour_id)
    state = get_object_or_404(StreetViewSourceSceneState, publication=publication, source_scene=scene)
    data = _body(request) or {}
    if data is None:
        return _json({"ok": False, "error": "JSON invalide."}, status=400)

    photo_id = state.google_photo_id
    if not photo_id:
        return _json({"ok": False, "error": "This scene does not have a Google Photo ID."}, status=400)

    delete_from_google = data.get("delete_from_google", True) is not False
    clear_local_if_missing = data.get("clear_local_if_missing", True) is not False

    try:
        client = _client_for_user(request)
    except GoogleStreetViewAuthError as exc:
        return _json({
            "ok": False,
            "error": str(exc),
            "oauth_url": request.build_absolute_uri(reverse("apps.app_streetview:oauth_start")),
        }, status=401)

    deleted_on_google = False
    delete_warning = ""

    if delete_from_google:
        try:
            client.delete_photo(photo_id)
            deleted_on_google = True
        except StreetViewPublishError as exc:
            msg = str(exc)
            # If it is already gone on Google, allow local cleanup.
            if clear_local_if_missing and ("not found" in msg.lower() or "does not exist" in msg.lower()):
                delete_warning = msg
            else:
                return _json({
                    "ok": False,
                    "error": msg,
                    "payload": getattr(exc, "payload", {}),
                }, status=getattr(exc, "status_code", None) or 400)

    state.google_photo_id = ""
    state.google_share_link = ""
    state.google_thumbnail_url = ""
    state.upload_reference_url = ""
    state.publish_status = StreetViewSourceSceneState.PublishStatus.READY if state.has_gps else StreetViewSourceSceneState.PublishStatus.LOCAL
    state.last_error = delete_warning
    state.save(update_fields=[
        "google_photo_id",
        "google_share_link",
        "google_thumbnail_url",
        "upload_reference_url",
        "publish_status",
        "last_error",
        "updated_at",
    ])

    # Clean remaining Google connections so no photo keeps a link toward the deleted image.
    cleanup_results = []
    cleanup_warnings = 0
    remaining_states = {
        item.source_scene_id: item
        for item in publication.scene_states.select_related("source_scene").all()
    }
    connection_map = _source_connection_map(publication)

    for source_id, source_state in remaining_states.items():
        if not source_state.google_photo_id:
            continue
        targets = []
        for target_source_id in connection_map.get(source_id, []):
            target_state = remaining_states.get(target_source_id)
            if target_state and target_state.google_photo_id:
                targets.append(target_state.google_photo_id)
        targets = list(dict.fromkeys(targets))
        try:
            # Even an empty list is useful here: it removes old/stale connections.
            client.update_photo_connections(source_state.google_photo_id, targets)
            source_state.publish_status = (
                StreetViewSourceSceneState.PublishStatus.CONNECTED
                if targets
                else StreetViewSourceSceneState.PublishStatus.CREATED
            )
            source_state.last_error = ""
            source_state.save(update_fields=["publish_status", "last_error", "updated_at"])
            cleanup_results.append({
                "scene_id": source_id,
                "ok": True,
                "targets": targets,
                "message": "Connections cleaned.",
            })
        except StreetViewPublishError as exc:
            cleanup_warnings += 1
            cleanup_results.append({
                "scene_id": source_id,
                "ok": False,
                "targets": targets,
                "message": str(exc),
            })

    published_count = publication.scene_states.filter(google_photo_id__gt="").count()
    connected_count = publication.scene_states.filter(publish_status=StreetViewSourceSceneState.PublishStatus.CONNECTED).count()
    if published_count == 0:
        publication.status = StreetViewSourcePublication.Status.DRAFT
        publication.published_at = None
    elif connected_count == published_count:
        publication.status = StreetViewSourcePublication.Status.PUBLISHED
    else:
        publication.status = StreetViewSourcePublication.Status.READY
    publication.last_error = "" if cleanup_warnings == 0 else "Photo deleted, but some Google connections could not be cleaned."
    publication.save(update_fields=["status", "published_at", "last_error", "updated_at"])

    return _json({
        "ok": cleanup_warnings == 0,
        "deleted_on_google": deleted_on_google,
        "cleared_local_state": True,
        "deleted_photo_id": photo_id,
        "cleanup_warnings": cleanup_warnings,
        "cleanup_results": cleanup_results,
        **source_publication_to_dict(publication, absolute_url_builder=lambda url: _absolute(request, url)),
    }, status=200 if cleanup_warnings == 0 else 207)



@login_required
@require_GET
def source_quality_check(request, tour_id):
    publication = _publication_for_source_tour(request, tour_id)
    report = run_quality_check(publication)
    status_map = {
        "ready": StreetViewQualityReport.Status.READY,
        "needs_attention": StreetViewQualityReport.Status.NEEDS_ATTENTION,
        "blocked": StreetViewQualityReport.Status.BLOCKED,
    }
    saved = StreetViewQualityReport.objects.create(
        publication=publication,
        user=request.user,
        status=status_map.get(report.get("status"), StreetViewQualityReport.Status.NEEDS_ATTENTION),
        score=int(report.get("score") or 0),
        blockers=int(report.get("counts", {}).get("blockers") or 0),
        warnings=int(report.get("counts", {}).get("warnings") or 0),
        report=report,
    )
    record_history(publication, request.user, StreetViewHistoryEvent.Action.QUALITY_CHECK, f"Quality check: {report.get('status')} ({report.get('score')}/100).", metadata={"report_id": saved.id, "score": report.get("score")})
    record_analytics(publication, request.user, "quality_check", metadata={"score": report.get("score"), "status": report.get("status")})
    return _json({"ok": True, "report_id": saved.id, "quality": report})


@login_required
@require_GET
def source_smart_link(request, tour_id):
    publication = _publication_for_source_tour(request, tour_id)
    max_distance = _as_float(request.GET.get("max_distance_m"), 250.0) or 250.0
    bidirectional = request.GET.get("bidirectional", "1") not in {"0", "false", "False"}
    suggestions = build_smart_link_suggestions(publication, bidirectional=bidirectional, max_distance_m=max_distance)
    return _json(suggestions)


@login_required
@require_POST
def source_apply_smart_link(request, tour_id):
    publication = _publication_for_source_tour(request, tour_id)
    data = _body(request) or {}
    if data is None:
        return _json({"ok": False, "error": "Invalid JSON."}, status=400)

    selected_ids = set(str(x) for x in (data.get("suggestion_ids") or []))
    max_distance = _as_float(data.get("max_distance_m"), 250.0) or 250.0
    bidirectional = bool(data.get("bidirectional", True))
    suggestions = build_smart_link_suggestions(publication, bidirectional=bidirectional, max_distance_m=max_distance)["suggestions"]
    if selected_ids:
        suggestions = [s for s in suggestions if str(s.get("id")) in selected_ids]
    else:
        suggestions = [s for s in suggestions if s.get("recommended")]

    created = 0
    updated = 0
    duplicates_removed = 0
    applied = []
    with transaction.atomic():
        for suggestion in suggestions:
            source_scene = get_object_or_404(Scene360, pk=suggestion["from_scene_id"], tour=publication.source_tour)
            target_scene = get_object_or_404(Scene360, pk=suggestion["to_scene_id"], tour=publication.source_tour)
            hotspot, was_created, removed = _ensure_navigation_hotspot(
                request=request,
                organization=publication.source_tour.organization,
                scene=source_scene,
                target_scene=target_scene,
                label=suggestion.get("label") or f"Go to {target_scene.title}",
                yaw=suggestion.get("heading") or 0,
                pitch=suggestion.get("pitch") or 0,
            )
            created += 1 if was_created else 0
            updated += 0 if was_created else 1
            duplicates_removed += removed
            applied.append({**suggestion, "hotspot_id": hotspot.id, "created": was_created})

    record_history(publication, request.user, StreetViewHistoryEvent.Action.SMART_LINK, f"Smart link applied: {len(applied)} connection(s).", metadata={"created": created, "updated": updated, "duplicates_removed": duplicates_removed})
    record_analytics(publication, request.user, "smart_link_applied", metadata={"applied": len(applied), "created": created})
    return _json({
        "ok": True,
        "created": created,
        "updated": updated,
        "duplicates_removed": duplicates_removed,
        "applied": applied,
        **source_publication_to_dict(publication, absolute_url_builder=lambda url: _absolute(request, url)),
    })


def _start_local_publish_thread(job_id: int, options: dict):
    def target():
        close_old_connections()
        try:
            run_source_publish_job(job_id, {**options, "runner": "local_thread"})
        except Exception:
            # run_source_publish_job already stores the failure in the job log.
            pass
        finally:
            close_old_connections()

    thread = threading.Thread(target=target, name=f"streetview-publish-{job_id}", daemon=True)
    thread.start()
    return thread


@login_required
@require_POST
def source_publish_tour_background(request, tour_id):
    publication = _publication_for_source_tour(request, tour_id)
    data = _body(request) or {}
    if data is None:
        return _json({"ok": False, "error": "Invalid JSON."}, status=400)

    quality = run_quality_check(publication)
    if not quality.get("ok"):
        return _json({"ok": False, "error": "Quality check blocked publishing. Fix blockers first.", "quality": quality}, status=400)

    options = {
        "skip_published": bool(data.get("skip_published", True)),
        "force_reupload": bool(data.get("force_reupload", False)),
        "indexing_wait_seconds": float(data.get("indexing_wait_seconds", 2) or 0),
    }

    # auto = Celery only when explicitly enabled in settings, otherwise local-thread.
    # This makes the publisher work on a simple Django runserver without Celery.
    run_mode = str(data.get("run_mode") or "auto").lower().strip()
    if run_mode == "auto":
        run_mode = "celery" if getattr(settings, "STREETVIEW_PUBLISH_USE_CELERY", False) else "local"

    job = StreetViewSourcePublishJob.objects.create(
        publication=publication,
        user=request.user,
        status=StreetViewSourcePublishJob.Status.QUEUED,
        total_scenes=publication.scene_states.count(),
    )
    publication.status = StreetViewSourcePublication.Status.PUBLISHING
    publication.last_error = ""
    publication.save(update_fields=["status", "last_error", "updated_at"])
    record_history(publication, request.user, StreetViewHistoryEvent.Action.PUBLISH_STARTED, f"Publish job queued ({run_mode}).", job=job)
    record_analytics(publication, request.user, "publish_started", metadata={"job_id": job.id, "mode": run_mode})

    if run_mode == "sync":
        try:
            run_source_publish_job(job.id, {**options, "runner": "sync"})
            job.refresh_from_db()
            publication.refresh_from_db()
            return _json({
                "ok": job.status != StreetViewSourcePublishJob.Status.FAILED,
                "queued": False,
                "execution_mode": "sync",
                "job": source_publish_job_to_dict(job),
                **source_publication_to_dict(publication, absolute_url_builder=lambda url: _absolute(request, url)),
            }, status=200)
        except Exception as exc:
            job.refresh_from_db()
            return _json({"ok": False, "error": str(exc), "execution_mode": "sync", "job": source_publish_job_to_dict(job)}, status=500)

    if run_mode == "celery":
        try:
            from .tasks import publish_source_tour_job
            async_result = publish_source_tour_job.delay(job.id, {**options, "runner": "celery"})
            task_id = getattr(async_result, "id", "")
            job.append_log("info", "Background job queued with Celery.", celery_task_id=task_id, step="queued")
            return _json({
                "ok": True,
                "queued": True,
                "execution_mode": "celery",
                "task_id": task_id,
                "job": source_publish_job_to_dict(job),
                **source_publication_to_dict(publication, absolute_url_builder=lambda url: _absolute(request, url)),
            }, status=202)
        except Exception as exc:
            # Broker or Celery unavailable: fallback to local thread unless explicitly disabled.
            if data.get("local_fallback", True) is False:
                job.status = StreetViewSourcePublishJob.Status.FAILED
                job.error = str(exc)
                job.finished_at = timezone.now()
                job.save(update_fields=["status", "error", "finished_at", "updated_at"])
                publication.status = StreetViewSourcePublication.Status.FAILED
                publication.last_error = str(exc)
                publication.save(update_fields=["status", "last_error", "updated_at"])
                return _json({"ok": False, "error": str(exc), "execution_mode": "celery", "job": source_publish_job_to_dict(job)}, status=500)
            job.append_log("warning", f"Celery unavailable, using local fallback: {exc}", step="queued")
            run_mode = "local"

    _start_local_publish_thread(job.id, options)
    job.append_log("info", "Background job started with local Django fallback.", step="queued")
    return _json({
        "ok": True,
        "queued": True,
        "execution_mode": "local_thread",
        "job": source_publish_job_to_dict(job),
        **source_publication_to_dict(publication, absolute_url_builder=lambda url: _absolute(request, url)),
    }, status=202)

@login_required
@require_GET
def source_publish_job_status(request, job_public_id):
    job = get_object_or_404(StreetViewSourcePublishJob.objects.select_related("publication", "publication__source_tour"), public_id=job_public_id, user=request.user)
    publication = job.publication
    return _json({
        "ok": True,
        "job": source_publish_job_to_dict(job),
        **source_publication_to_dict(publication, absolute_url_builder=lambda url: _absolute(request, url)),
    })


@login_required
@require_GET
def source_history(request, tour_id):
    publication = _publication_for_source_tour(request, tour_id)
    limit = min(int(request.GET.get("limit", 80) or 80), 200)
    events = []
    for event in publication.history_events.select_related("user", "source_scene", "job")[:limit]:
        events.append({
            "id": event.id,
            "action": event.action,
            "message": event.message,
            "scene_id": event.source_scene_id,
            "scene_title": event.source_scene.title if event.source_scene else "",
            "job_id": event.job.public_id if event.job else "",
            "metadata": event.metadata,
            "created_at": event.created_at.isoformat(),
            "user": getattr(event.user, "email", "") or getattr(event.user, "username", "") if event.user else "",
        })
    return _json({"ok": True, "events": events})


@login_required
@require_GET
def source_analytics(request, tour_id):
    publication = _publication_for_source_tour(request, tour_id)
    job_counts = {}
    for row in publication.publish_jobs.values("status").annotate(count=Count("id")):
        job_counts[row["status"]] = row["count"]
    event_counts = {}
    for row in publication.analytics_events.values("event_type").annotate(count=Count("id")):
        event_counts[row["event_type"]] = row["count"]
    quality = publication.quality_reports.first()
    return _json({
        "ok": True,
        "summary": {
            "jobs": job_counts,
            "events": event_counts,
            "latest_quality": {
                "status": quality.status,
                "score": quality.score,
                "blockers": quality.blockers,
                "warnings": quality.warnings,
                "created_at": quality.created_at.isoformat(),
            } if quality else None,
            "scenes": publication.scene_states.count(),
            "published": publication.scene_states.filter(google_photo_id__gt="").count(),
            "connected": publication.scene_states.filter(publish_status=StreetViewSourceSceneState.PublishStatus.CONNECTED).count(),
        }
    })


@login_required
@require_POST
def source_publish_tour(request, tour_id):
    publication = _publication_for_source_tour(request, tour_id)
    data = _body(request) or {}
    if data is None:
        return _json({"ok": False, "error": "JSON invalide."}, status=400)

    skip_published = bool(data.get("skip_published", True))
    force_reupload = bool(data.get("force_reupload", False))
    auto_link = bool(data.get("auto_link", False))

    if auto_link:
        # Create existing app hotspots only. No source tour or source scene duplication.
        _auto_link_source_tour(publication.source_tour, bidirectional=True)

    try:
        client = _client_for_user(request)
    except GoogleStreetViewAuthError as exc:
        return _json({"ok": False, "error": str(exc), "oauth_url": request.build_absolute_uri(reverse("apps.app_streetview:oauth_start"))}, status=401)

    states = list(publication.scene_states.select_related("source_scene", "source_scene__tour", "source_scene__tour__place").order_by("source_scene__order", "source_scene_id"))
    if not states:
        return _json({"ok": False, "error": "This tour has no 360 scene."}, status=400)

    missing = [s.source_scene.title for s in states if not s.has_gps]
    if missing:
        return _json({"ok": False, "error": "Some scenes do not have GPS.", "scenes": missing}, status=400)

    missing_images = [s.source_scene.title for s in states if not s.has_image]
    if missing_images:
        return _json({"ok": False, "error": "Some scenes do not have a 360 image.", "scenes": missing_images}, status=400)

    job = StreetViewSourcePublishJob.objects.create(
        publication=publication,
        user=request.user,
        status=StreetViewSourcePublishJob.Status.RUNNING,
        total_scenes=len(states),
    )
    publication.status = StreetViewSourcePublication.Status.PUBLISHING
    publication.last_error = ""
    publication.save(update_fields=["status", "last_error", "updated_at"])

    try:
        for state in states:
            if state.google_photo_id and skip_published and not force_reupload:
                if not state.google_share_link:
                    state.google_share_link = _google_share_link(state.google_photo_id)
                    state.save(update_fields=["google_share_link", "updated_at"])
                job.published_scenes += 1
                job.save(update_fields=["published_scenes", "updated_at"])
                job.append_log("info", f"Already published, upload skipped: {state.source_scene.title}", source_scene_id=state.source_scene_id, google_photo_id=state.google_photo_id)
                continue

            proxy = _source_state_proxy(state)
            job.append_log("info", f"Upload: {proxy.title}", source_scene_id=state.source_scene_id)
            state.publish_status = StreetViewSourceSceneState.PublishStatus.UPLOADING
            state.last_error = ""
            state.save(update_fields=["publish_status", "last_error", "updated_at"])

            upload_url = client.start_upload()
            state.upload_reference_url = upload_url
            state.save(update_fields=["upload_reference_url", "updated_at"])

            prepared_path = None
            try:
                prepared_path = prepare_streetview_jpeg_with_xmp(proxy)
                client.upload_photo_bytes(upload_url, prepared_path)
            finally:
                if prepared_path and prepared_path != proxy.image.path:
                    try:
                        os.remove(prepared_path)
                    except OSError:
                        pass

            created_payload = client.create_photo(upload_url, proxy)
            fields = extract_google_photo_fields(created_payload)
            state.google_photo_id = fields["photo_id"]
            state.google_share_link = fields["share_link"] or _google_share_link(fields["photo_id"])
            state.google_thumbnail_url = fields["thumbnail_url"]
            state.publish_status = StreetViewSourceSceneState.PublishStatus.CREATED
            state.last_error = ""
            state.save(update_fields=["google_photo_id", "google_share_link", "google_thumbnail_url", "publish_status", "last_error", "updated_at"])
            job.published_scenes += 1
            job.save(update_fields=["published_scenes", "updated_at"])
            job.append_log("success", f"Google photo created: {state.google_photo_id}", source_scene_id=state.source_scene_id, share_link=state.google_share_link)

        result = _send_source_connections(client, publication)
        for item in result["results"]:
            level = "success" if item.get("ok") else "warning"
            job.append_log(level, item.get("message") or "Connection processed", source_scene_id=item.get("scene_id"), targets=item.get("targets", []))

        publication.status = StreetViewSourcePublication.Status.PUBLISHED
        publication.published_at = timezone.now()
        publication.last_error = ""
        publication.save(update_fields=["status", "published_at", "last_error", "updated_at"])
        job.status = StreetViewSourcePublishJob.Status.SUCCEEDED_WITH_WARNINGS if result["warnings"] else StreetViewSourcePublishJob.Status.SUCCEEDED
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "finished_at", "updated_at"])

        return _json({
            "ok": result["warnings"] == 0,
            "job": source_publish_job_to_dict(job),
            "connections": result,
            **source_publication_to_dict(publication, absolute_url_builder=lambda url: _absolute(request, url)),
        }, status=200 if result["warnings"] == 0 else 207)

    except StreetViewPublishError as exc:
        publication.status = StreetViewSourcePublication.Status.FAILED
        publication.last_error = str(exc)
        publication.save(update_fields=["status", "last_error", "updated_at"])
        job.status = StreetViewSourcePublishJob.Status.FAILED
        job.error = str(exc)
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "error", "finished_at", "updated_at"])
        job.append_log("error", str(exc), status_code=getattr(exc, "status_code", None), payload=getattr(exc, "payload", {}))
        return _json({"ok": False, "error": str(exc), "job": source_publish_job_to_dict(job)}, status=500)


@login_required
@require_POST
def source_retry_connections(request, tour_id):
    publication = _publication_for_source_tour(request, tour_id)
    try:
        client = _client_for_user(request)
    except GoogleStreetViewAuthError as exc:
        return _json({"ok": False, "error": str(exc), "oauth_url": request.build_absolute_uri(reverse("apps.app_streetview:oauth_start"))}, status=401)
    result = _send_source_connections(client, publication)
    record_history(publication, request.user, StreetViewHistoryEvent.Action.CONNECTIONS_RETRIED, "Google connections retried.", metadata={"warnings": result.get("warnings", 0), "updated": result.get("updated", 0)})
    return _json({"ok": result["warnings"] == 0, **result, **source_publication_to_dict(publication, absolute_url_builder=lambda url: _absolute(request, url))}, status=200 if result["warnings"] == 0 else 207)


@login_required
@require_GET
def source_share_links(request, tour_id):
    publication = _publication_for_source_tour(request, tour_id)
    links = []
    for state in publication.scene_states.select_related("source_scene").order_by("source_scene__order", "source_scene_id"):
        if not state.google_photo_id:
            continue
        share_link = state.google_share_link or _google_share_link(state.google_photo_id)
        links.append({
            "source_scene_id": state.source_scene_id,
            "title": state.source_scene.title,
            "photo_id": state.google_photo_id,
            "share_link": share_link,
            "thumbnail_url": state.google_thumbnail_url,
            "publish_status": state.publish_status,
        })
    text = "\n".join([f"{item['title']}: {item['share_link']}" for item in links])
    return _json({"ok": True, "source_tour_id": publication.source_tour_id, "title": publication.source_tour.title, "count": len(links), "links": links, "share_text": text})


@login_required
@require_POST
def source_sync_google_status(request, tour_id):
    publication = _publication_for_source_tour(request, tour_id)
    try:
        client = _client_for_user(request)
        result = sync_source_publication(client, publication)
        record_history(publication, request.user, StreetViewHistoryEvent.Action.OTHER, "Google publication statuses synchronized.", metadata={"summary": result})
        return _json(result)
    except (StreetViewPublishError, GoogleStreetViewAuthError, Exception) as exc:
        return _json({"ok": False, "error": "Google publication status synchronization failed.", "details": str(exc)}, status=400)


@login_required
@require_POST
def source_audit_and_repair_connections(request, tour_id):
    publication = _publication_for_source_tour(request, tour_id)
    data = _body(request) or {}
    attempts = max(1, min(int(data.get("attempts") or getattr(settings, "STREETVIEW_CONNECTION_REPAIR_ATTEMPTS", 5)), 10))
    try:
        client = _client_for_user(request)
        before = sync_source_publication(client, publication)
        repaired = repair_source_connections(client, publication, attempts=attempts)
        after = sync_source_publication(client, publication)
        record_history(
            publication, request.user, StreetViewHistoryEvent.Action.CONNECTIONS_RETRIED,
            "Google connections audited and repaired.",
            metadata={"before": before, "repair": repaired, "after": after},
        )
        return _json({"ok": repaired.get("ok", False), "before": before, "repair": repaired, "after": after})
    except (StreetViewPublishError, GoogleStreetViewAuthError, Exception) as exc:
        return _json({"ok": False, "error": "Google connection audit failed.", "details": str(exc)}, status=400)
