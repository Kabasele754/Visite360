from __future__ import annotations

import json
import os
import tempfile
from types import SimpleNamespace
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max, Prefetch
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .models import (
    StreetViewConnection,
    StreetViewGoogleAccount,
    StreetViewHotspot,
    StreetViewPublishJob,
    StreetViewScene,
    StreetViewTour,
)
from .serializers import publish_job_to_dict, scene_to_dict, tour_to_dict
from .services.exif import extract_image_metadata
from .services.google_oauth import credentials_to_account_defaults, fetch_credentials_from_callback, generate_code_verifier, get_authorization_url
from .services.project_export import build_project_export
from .services.streetview_publish import StreetViewPublishClient, StreetViewPublishError, extract_google_photo_fields
from .services.tokens import GoogleStreetViewAuthError, get_valid_access_token
from .services.xmp import prepare_streetview_jpeg_with_xmp
from .services.status_sync import sync_direct_project, repair_direct_connections


def _json_response(data=None, *, status=200):
    return JsonResponse(data or {}, status=status, json_dumps_params={"ensure_ascii": False})


def _parse_json_body(request):
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return None


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


def _owned_tour(request, tour_id):
    return get_object_or_404(
        StreetViewTour.objects.filter(owner=request.user).prefetch_related(
            Prefetch("scenes", queryset=StreetViewScene.objects.prefetch_related("hotspots")),
            "connections",
        ),
        pk=tour_id,
    )


def _scene_in_owned_tour(request, scene_id):
    return get_object_or_404(StreetViewScene.objects.select_related("tour"), pk=scene_id, tour__owner=request.user)


def _absolute(request, url):
    if not url:
        return ""
    return request.build_absolute_uri(url)


@login_required
@require_GET
def publisher_page(request):
    """Optional Django page shell. You can replace it with your Tailwind/Marzipano frontend."""

    return render(request, "app_streetview/publisher.html")


@login_required
@require_GET
def streetview_config(request):
    account = StreetViewGoogleAccount.objects.filter(user=request.user).first()
    return _json_response(
        {
            "googleMapsKey": getattr(settings, "GOOGLE_MAPS_BROWSER_KEY", ""),
            "oauthStartUrl": request.build_absolute_uri(reverse("apps.app_streetview:oauth_start")),
            "googleConnected": bool(account and account.is_connected),
            "googleEmail": account.google_email if account else "",
            "streetViewScope": getattr(settings, "GOOGLE_STREETVIEW_SCOPE", "https://www.googleapis.com/auth/streetviewpublish"),
            "redirectUri": getattr(settings, "GOOGLE_STREETVIEW_REDIRECT_URI", ""),
        }
    )


@login_required
@require_GET
def google_account_status(request):
    account = StreetViewGoogleAccount.objects.filter(user=request.user).first()
    return _json_response(
        {
            "connected": bool(account and account.is_connected),
            "googleEmail": account.google_email if account else "",
            "tokenExpiry": account.token_expiry.isoformat() if account and account.token_expiry else None,
            "isExpired": bool(account and account.is_expired),
            "oauthStartUrl": request.build_absolute_uri(reverse("apps.app_streetview:oauth_start")),
        }
    )


@login_required
@require_GET
def google_oauth_start(request):
    code_verifier = generate_code_verifier()

    authorization_url, state = get_authorization_url(
        code_verifier=code_verifier,
    )

    request.session["google_streetview_oauth_state"] = state
    request.session["google_streetview_oauth_code_verifier"] = code_verifier

    next_url = (
        request.GET.get("next")
        or request.META.get("HTTP_REFERER")
        or reverse("apps.app_streetview:publisher")
    )
    request.session["google_streetview_oauth_next"] = next_url
    request.session.modified = True

    return redirect(authorization_url)


@login_required
@require_GET
def google_oauth_callback(request):
    expected_state = request.session.get("google_streetview_oauth_state")
    received_state = request.GET.get("state")
    code_verifier = request.session.get("google_streetview_oauth_code_verifier")

    if not expected_state:
        return _json_response(
            {
                "ok": False,
                "error": "OAuth state absent dans la session Django.",
                "solution": "Relance /apis/streetview/oauth/start/ depuis le même navigateur.",
            },
            status=400,
        )

    if not code_verifier:
        return _json_response(
            {
                "ok": False,
                "error": "PKCE code_verifier absent dans la session Django.",
                "solution": "Relance /apis/streetview/oauth/start/. Ne recharge pas directement l'URL callback.",
            },
            status=400,
        )

    if expected_state != received_state:
        return _json_response(
            {
                "ok": False,
                "error": "OAuth state invalide.",
                "expected_state": expected_state,
                "received_state": received_state,
                "solution": "Utilise toujours le même domaine pendant tout le test : localhost OU 127.0.0.1, pas les deux.",
            },
            status=400,
        )

    if request.GET.get("error"):
        return _json_response(
            {
                "ok": False,
                "error": request.GET.get("error"),
                "error_description": request.GET.get("error_description", ""),
            },
            status=400,
        )

    try:
        credentials = fetch_credentials_from_callback(
            request.build_absolute_uri(),
            state=expected_state,
            code_verifier=code_verifier,
        )
    except Exception as exc:
        return _json_response(
            {
                "ok": False,
                "error": "Connexion Google impossible.",
                "details": str(exc),
                "callbackUrl": request.build_absolute_uri(),
                "redirectUriConfigured": getattr(settings, "GOOGLE_STREETVIEW_REDIRECT_URI", ""),
            },
            status=400,
        )

    defaults = credentials_to_account_defaults(credentials)

    old = StreetViewGoogleAccount.objects.filter(user=request.user).first()
    if old and not defaults.get("refresh_token") and old.refresh_token:
        defaults["refresh_token"] = old.refresh_token

    StreetViewGoogleAccount.objects.update_or_create(
        user=request.user,
        defaults=defaults,
    )

    request.session.pop("google_streetview_oauth_state", None)
    request.session.pop("google_streetview_oauth_code_verifier", None)

    next_url = request.session.pop(
        "google_streetview_oauth_next",
        reverse("apps.app_streetview:publisher"),
    )

    return redirect(f"{next_url}{'&' if '?' in next_url else '?'}google_connected=1")
@login_required
@require_POST
def google_disconnect(request):
    StreetViewGoogleAccount.objects.filter(user=request.user).delete()
    return _json_response({"ok": True, "message": "Compte Google Street View déconnecté."})


@login_required
@require_GET
def list_tours(request):
    tours = StreetViewTour.objects.filter(owner=request.user).prefetch_related("scenes", "connections")
    return _json_response({"results": [tour_to_dict(tour, include_children=False) for tour in tours]})


@login_required
@require_POST
def create_tour(request):
    data = _parse_json_body(request)
    if data is None:
        return _json_response({"ok": False, "error": "JSON invalide."}, status=400)

    title = (data.get("title") or request.POST.get("title") or "Nouvelle visite Street View").strip()
    description = (data.get("description") or request.POST.get("description") or "").strip()

    storage_policy = data.get("storage_policy") or request.POST.get("storage_policy") or StreetViewTour.StoragePolicy.KEEP_LOCAL
    if storage_policy not in StreetViewTour.StoragePolicy.values:
        storage_policy = StreetViewTour.StoragePolicy.KEEP_LOCAL
    tour = StreetViewTour.objects.create(
        owner=request.user,
        title=title,
        description=description,
        project_mode=StreetViewTour.ProjectMode.DIRECT,
        storage_policy=storage_policy,
        google_place_id=(data.get("google_place_id") or request.POST.get("google_place_id") or "").strip(),
        auto_connect=bool(data.get("auto_connect", True)),
        auto_sync_status=bool(data.get("auto_sync_status", True)),
    )
    return _json_response({"ok": True, "tour": tour_to_dict(tour, include_children=False)}, status=201)


@login_required
@require_GET
def tour_detail(request, tour_id):
    tour = _owned_tour(request, tour_id)
    return _json_response({"tour": tour_to_dict(tour, absolute_url_builder=lambda url: _absolute(request, url))})


@login_required
@require_http_methods(["PATCH", "POST"])
def update_tour(request, tour_id):
    tour = _owned_tour(request, tour_id)
    data = _parse_json_body(request)
    if data is None:
        return _json_response({"ok": False, "error": "JSON invalide."}, status=400)

    if "title" in data:
        tour.title = (data.get("title") or tour.title).strip()
    if "description" in data:
        tour.description = data.get("description") or ""
    if "storage_policy" in data and data.get("storage_policy") in StreetViewTour.StoragePolicy.values:
        tour.storage_policy = data["storage_policy"]
    if "google_place_id" in data:
        tour.google_place_id = str(data.get("google_place_id") or "").strip()[:255]
    if "auto_connect" in data:
        tour.auto_connect = bool(data.get("auto_connect"))
    if "auto_sync_status" in data:
        tour.auto_sync_status = bool(data.get("auto_sync_status"))
    tour.save(update_fields=["title", "description", "storage_policy", "google_place_id", "auto_connect", "auto_sync_status", "updated_at"])
    return _json_response({"ok": True, "tour": tour_to_dict(tour, include_children=False)})


@login_required
@require_POST
def delete_tour(request, tour_id):
    tour = _owned_tour(request, tour_id)
    tour.delete()
    return _json_response({"ok": True})


@login_required
@require_POST
def upload_scenes(request, tour_id):
    tour = _owned_tour(request, tour_id)
    files = request.FILES.getlist("images") or request.FILES.getlist("files")
    if not files:
        return _json_response({"ok": False, "error": "Aucune image reçue. Utilise le champ multipart images[]."}, status=400)

    max_order = tour.scenes.aggregate(value=Max("order"))["value"] or 0
    created_scenes = []

    for index, image_file in enumerate(files, start=1):
        title = Path(image_file.name).stem.replace("_", " ").replace("-", " ").strip() or f"Scène {index}"
        scene = StreetViewScene.objects.create(
            tour=tour,
            title=title,
            image=image_file,
            file_size=getattr(image_file, "size", 0) or 0,
            order=max_order + index,
        )

        metadata = extract_image_metadata(scene.image.path)
        scene.image_width = metadata.get("width") or 0
        scene.image_height = metadata.get("height") or 0
        scene.latitude = metadata.get("gps_latitude")
        scene.longitude = metadata.get("gps_longitude")
        scene.altitude = metadata.get("gps_altitude")
        scene.capture_time = metadata.get("capture_time")
        scene.xmp_detected = bool(metadata.get("xmp_detected"))
        scene.exif_data = metadata.get("raw_exif") or {}
        scene.publish_status = StreetViewScene.PublishStatus.READY if scene.has_gps else StreetViewScene.PublishStatus.LOCAL
        scene.save(
            update_fields=[
                "image_width",
                "image_height",
                "latitude",
                "longitude",
                "altitude",
                "capture_time",
                "xmp_detected",
                "exif_data",
                "publish_status",
                "updated_at",
            ]
        )
        created_scenes.append(scene_to_dict(scene, absolute_url_builder=lambda url: _absolute(request, url)))

    tour.mark_ready_if_valid()
    return _json_response({"ok": True, "scenes": created_scenes}, status=201)


@login_required
@require_http_methods(["PATCH", "POST"])
def update_scene(request, scene_id):
    scene = _scene_in_owned_tour(request, scene_id)
    data = _parse_json_body(request)
    if data is None:
        return _json_response({"ok": False, "error": "JSON invalide."}, status=400)

    simple_fields = ["title", "description"]
    for field in simple_fields:
        if field in data:
            setattr(scene, field, data.get(field) or "")

    gps = data.get("gps") or data
    if "latitude" in gps:
        scene.latitude = _as_decimal(gps.get("latitude"))
    if "longitude" in gps:
        scene.longitude = _as_decimal(gps.get("longitude"))
    if "altitude" in gps:
        scene.altitude = _as_float(gps.get("altitude"), None)

    orientation = data.get("orientation") or data
    for field in ["heading", "pitch", "roll", "initial_yaw", "initial_pitch", "initial_fov"]:
        if field in orientation:
            setattr(scene, field, _as_float(orientation.get(field), getattr(scene, field)))

    if "order" in data:
        try:
            scene.order = int(data.get("order"))
        except Exception:
            pass

    if scene.google_photo_id:
        # Do not lose Google publication state when editing GPS/orientation after publish.
        if scene.publish_status in (StreetViewScene.PublishStatus.LOCAL, StreetViewScene.PublishStatus.READY):
            scene.publish_status = StreetViewScene.PublishStatus.CREATED
    else:
        scene.publish_status = StreetViewScene.PublishStatus.READY if scene.has_gps else StreetViewScene.PublishStatus.LOCAL
    try:
        scene.full_clean()
    except ValidationError as exc:
        return _json_response({"ok": False, "error": exc.message_dict if hasattr(exc, "message_dict") else exc.messages}, status=400)

    scene.save()
    scene.tour.mark_ready_if_valid()
    return _json_response({"ok": True, "scene": scene_to_dict(scene, absolute_url_builder=lambda url: _absolute(request, url))})


@login_required
@require_POST
def delete_scene(request, scene_id):
    scene = _scene_in_owned_tour(request, scene_id)
    scene.delete()
    return _json_response({"ok": True})


@login_required
@require_POST
def save_connections(request, tour_id):
    tour = _owned_tour(request, tour_id)
    data = _parse_json_body(request)
    if data is None:
        return _json_response({"ok": False, "error": "JSON invalide."}, status=400)

    connections = data.get("connections", [])
    scene_ids = set(tour.scenes.values_list("id", flat=True))

    with transaction.atomic():
        tour.connections.all().delete()
        created = []
        for index, item in enumerate(connections):
            from_id = int(item.get("from_scene") or item.get("from") or 0)
            to_id = int(item.get("to_scene") or item.get("to") or 0)
            if from_id not in scene_ids or to_id not in scene_ids or from_id == to_id:
                continue
            conn, _ = StreetViewConnection.objects.get_or_create(
                tour=tour,
                from_scene_id=from_id,
                to_scene_id=to_id,
                defaults={
                    "yaw": _as_float(item.get("yaw"), 0) or 0,
                    "pitch": _as_float(item.get("pitch"), 0) or 0,
                    "label": item.get("label") or "",
                    "order": int(item.get("order") or index),
                },
            )
            created.append(conn.id)

    return _json_response({"ok": True, "created": len(created)})


@login_required
@require_POST
def save_hotspots(request, tour_id):
    tour = _owned_tour(request, tour_id)
    data = _parse_json_body(request)
    if data is None:
        return _json_response({"ok": False, "error": "JSON invalide."}, status=400)

    hotspots = data.get("hotspots", [])
    scene_ids = set(tour.scenes.values_list("id", flat=True))

    with transaction.atomic():
        StreetViewHotspot.objects.filter(scene__tour=tour).delete()
        created = []
        for index, item in enumerate(hotspots):
            scene_id = int(item.get("scene") or item.get("scene_id") or 0)
            if scene_id not in scene_ids:
                continue
            target_scene_id = item.get("target_scene") or item.get("target")
            if target_scene_id:
                target_scene_id = int(target_scene_id)
                if target_scene_id not in scene_ids:
                    target_scene_id = None
            hotspot = StreetViewHotspot.objects.create(
                scene_id=scene_id,
                type=item.get("type") or StreetViewHotspot.Type.INFO,
                title=item.get("title") or "Hotspot",
                description=item.get("description") or item.get("desc") or "",
                target_scene_id=target_scene_id,
                url=item.get("url") or "",
                yaw=_as_float(item.get("yaw"), 0) or 0,
                pitch=_as_float(item.get("pitch"), 0) or 0,
                icon=item.get("icon") or "",
                css_class=item.get("css_class") or "",
                order=int(item.get("order") or index),
            )
            created.append(hotspot.id)

    return _json_response({"ok": True, "created": len(created)})


@login_required
@require_POST
def save_project_payload(request, tour_id):
    """Convenience endpoint: save scenes metadata, connections and hotspots in one call."""

    tour = _owned_tour(request, tour_id)
    data = _parse_json_body(request)
    if data is None:
        return _json_response({"ok": False, "error": "JSON invalide."}, status=400)

    with transaction.atomic():
        for item in data.get("scenes", []):
            scene_id = item.get("id")
            if not scene_id:
                continue
            try:
                scene = tour.scenes.get(id=scene_id)
            except StreetViewScene.DoesNotExist:
                continue
            if "title" in item:
                scene.title = item.get("title") or scene.title
            if "description" in item:
                scene.description = item.get("description") or ""
            gps = item.get("gps") or item
            if "latitude" in gps:
                scene.latitude = _as_decimal(gps.get("latitude"))
            if "longitude" in gps:
                scene.longitude = _as_decimal(gps.get("longitude"))
            if "altitude" in gps:
                scene.altitude = _as_float(gps.get("altitude"), None)
            orientation = item.get("orientation") or item
            for field in ["heading", "pitch", "roll", "initial_yaw", "initial_pitch", "initial_fov"]:
                if field in orientation:
                    setattr(scene, field, _as_float(orientation.get(field), getattr(scene, field)))
            if scene.google_photo_id:
                if scene.publish_status in (StreetViewScene.PublishStatus.LOCAL, StreetViewScene.PublishStatus.READY):
                    scene.publish_status = StreetViewScene.PublishStatus.CREATED
            else:
                scene.publish_status = StreetViewScene.PublishStatus.READY if scene.has_gps else StreetViewScene.PublishStatus.LOCAL
            scene.save()

        # Reuse logic with local code to avoid internal request mutation.
        scene_ids = set(tour.scenes.values_list("id", flat=True))
        tour.connections.all().delete()
        for index, item in enumerate(data.get("connections", [])):
            from_id = int(item.get("from_scene") or item.get("from") or 0)
            to_id = int(item.get("to_scene") or item.get("to") or 0)
            if from_id in scene_ids and to_id in scene_ids and from_id != to_id:
                StreetViewConnection.objects.get_or_create(
                    tour=tour,
                    from_scene_id=from_id,
                    to_scene_id=to_id,
                    defaults={
                        "yaw": _as_float(item.get("yaw"), 0) or 0,
                        "pitch": _as_float(item.get("pitch"), 0) or 0,
                        "label": item.get("label") or "",
                        "order": int(item.get("order") or index),
                    },
                )

        StreetViewHotspot.objects.filter(scene__tour=tour).delete()
        for index, item in enumerate(data.get("hotspots", [])):
            scene_id = int(item.get("scene") or item.get("scene_id") or 0)
            if scene_id not in scene_ids:
                continue
            target_scene_id = item.get("target_scene") or item.get("target")
            if target_scene_id:
                target_scene_id = int(target_scene_id)
                if target_scene_id not in scene_ids:
                    target_scene_id = None
            StreetViewHotspot.objects.create(
                scene_id=scene_id,
                type=item.get("type") or StreetViewHotspot.Type.INFO,
                title=item.get("title") or "Hotspot",
                description=item.get("description") or item.get("desc") or "",
                target_scene_id=target_scene_id,
                url=item.get("url") or "",
                yaw=_as_float(item.get("yaw"), 0) or 0,
                pitch=_as_float(item.get("pitch"), 0) or 0,
                icon=item.get("icon") or "",
                css_class=item.get("css_class") or "",
                order=int(item.get("order") or index),
            )

    tour.mark_ready_if_valid()
    return _json_response({"ok": True, "tour": tour_to_dict(_owned_tour(request, tour_id), absolute_url_builder=lambda url: _absolute(request, url))})


@login_required
@require_GET
def export_project_json(request, tour_id):
    tour = _owned_tour(request, tour_id)
    payload = build_project_export(tour, absolute_url_builder=lambda url: _absolute(request, url))
    if request.GET.get("download") == "1":
        response = HttpResponse(json.dumps(payload, ensure_ascii=False, indent=2), content_type="application/json")
        response["Content-Disposition"] = f'attachment; filename="streetview_tour_{tour.id}.json"'
        return response
    return _json_response(payload)




def _google_share_link_from_photo_id(photo_id: str) -> str:
    """Best-effort fallback link when Google does not return shareLink yet."""
    if not photo_id:
        return ""
    return f"https://www.google.com/maps?layer=c&panoid={photo_id}"


def _scene_is_already_published(scene) -> bool:
    return bool(scene.google_photo_id)


def _get_streetview_client_for_user(request):
    account = StreetViewGoogleAccount.objects.filter(user=request.user).first()
    if not account or not account.is_connected:
        raise GoogleStreetViewAuthError("Compte Google Street View non connecté.")
    access_token = get_valid_access_token(account)
    return StreetViewPublishClient(access_token=access_token)


def _publishable_scenes_for_tour(tour):
    # Avoid stale prefetch cache after google_photo_id updates.
    return list(StreetViewScene.objects.filter(tour=tour).order_by("order", "id"))


def _build_google_connection_map(tour):
    """Merge explicit StreetViewConnection rows and Marzipano link hotspots.

    This makes the editor simpler: if the user creates a hotspot of type "link",
    it automatically becomes a Google Street View connection too.
    """
    scene_ids = set(StreetViewScene.objects.filter(tour=tour).values_list("id", flat=True))
    connection_map = {scene_id: set() for scene_id in scene_ids}

    for conn in StreetViewConnection.objects.filter(tour=tour):
        if conn.from_scene_id in scene_ids and conn.to_scene_id in scene_ids and conn.from_scene_id != conn.to_scene_id:
            connection_map[conn.from_scene_id].add(conn.to_scene_id)

    link_hotspots = StreetViewHotspot.objects.filter(
        scene__tour=tour,
        type=StreetViewHotspot.Type.LINK,
        target_scene__isnull=False,
    ).select_related("scene", "target_scene")
    for hotspot in link_hotspots:
        if hotspot.scene_id in scene_ids and hotspot.target_scene_id in scene_ids and hotspot.scene_id != hotspot.target_scene_id:
            connection_map[hotspot.scene_id].add(hotspot.target_scene_id)

    return {scene_id: list(targets) for scene_id, targets in connection_map.items()}


def _send_google_connections(client, tour, *, only_scene_ids=None):
    """Send Street View connections without re-uploading images."""
    scenes = {
        scene.id: scene
        for scene in StreetViewScene.objects.filter(tour=tour)
    }
    allowed = set(only_scene_ids or []) if only_scene_ids else None
    results = []
    warnings = 0
    updated = 0

    for scene in scenes.values():
        if allowed is not None and scene.id not in allowed:
            continue
        if not scene.google_photo_id:
            results.append({
                "scene_id": scene.id,
                "title": scene.title,
                "ok": False,
                "message": "Scène non publiée: aucun Google Photo ID.",
                "targets": [],
            })
            warnings += 1
            continue

        target_ids = []
        connection_map = _build_google_connection_map(tour)
        for target_scene_id in connection_map.get(scene.id, []):
            target = scenes.get(target_scene_id)
            if target and target.google_photo_id:
                target_ids.append(target.google_photo_id)

        if not target_ids:
            scene.connection_sync_status = "not_required"
            scene.connection_audit = {
                "expected": [], "actual": [], "missing": [], "unexpected": [],
                "checked_at": timezone.now().isoformat(),
                "message": "This panorama has no outgoing Google navigation connection.",
            }
            scene.save(update_fields=["connection_sync_status", "connection_audit", "updated_at"])
            results.append({
                "scene_id": scene.id,
                "title": scene.title,
                "ok": True,
                "message": "Aucune connexion sortante.",
                "targets": [],
            })
            continue

        try:
            client.update_photo_connections(scene.google_photo_id, target_ids)
            scene.publish_status = StreetViewScene.PublishStatus.CONNECTED
            scene.connection_sync_status = "verification_pending"
            scene.connection_audit = {
                "expected": target_ids, "actual": [], "missing": target_ids, "unexpected": [],
                "checked_at": timezone.now().isoformat(),
                "message": "Connection update accepted; waiting for Google verification.",
            }
            scene.last_error = ""
            if not scene.google_share_link:
                scene.google_share_link = _google_share_link_from_photo_id(scene.google_photo_id)
            scene.save(update_fields=[
                "publish_status", "connection_sync_status", "connection_audit",
                "last_error", "google_share_link", "updated_at",
            ])
            updated += 1
            results.append({
                "scene_id": scene.id,
                "title": scene.title,
                "ok": True,
                "message": "Connexions Google mises à jour.",
                "targets": target_ids,
            })
        except StreetViewPublishError as exc:
            warnings += 1
            scene.connection_sync_status = "retry_required"
            scene.connection_audit = {
                "expected": target_ids, "actual": [], "missing": target_ids, "unexpected": [],
                "checked_at": timezone.now().isoformat(),
                "message": "Google has not exposed the requested navigation links yet.",
            }
            scene.last_error = str(exc)
            scene.save(update_fields=["connection_sync_status", "connection_audit", "last_error", "updated_at"])
            results.append({
                "scene_id": scene.id,
                "title": scene.title,
                "ok": False,
                "message": str(exc),
                "targets": target_ids,
            })
    return {"updated": updated, "warnings": warnings, "results": results}


@login_required
@require_POST
def auto_connect_scenes(request, tour_id):
    """Create a simple Street View navigation: scene 1 <-> scene 2 <-> scene 3..."""
    tour = _owned_tour(request, tour_id)
    data = _parse_json_body(request) or {}
    bidirectional = bool(data.get("bidirectional", True))
    replace = bool(data.get("replace", False))

    scenes = list(StreetViewScene.objects.filter(tour=tour).order_by("order", "id"))
    if len(scenes) < 2:
        return _json_response({"ok": False, "error": "Il faut au moins 2 scènes pour créer une navigation."}, status=400)

    created = 0
    with transaction.atomic():
        if replace:
            tour.connections.all().delete()
        for index, (src, dst) in enumerate(zip(scenes, scenes[1:])):
            _, was_created = StreetViewConnection.objects.get_or_create(
                tour=tour,
                from_scene=src,
                to_scene=dst,
                defaults={"label": f"Vers {dst.title}", "order": index * 2},
            )
            created += 1 if was_created else 0
            if bidirectional:
                _, was_created = StreetViewConnection.objects.get_or_create(
                    tour=tour,
                    from_scene=dst,
                    to_scene=src,
                    defaults={"label": f"Retour {src.title}", "order": index * 2 + 1},
                )
                created += 1 if was_created else 0

    return _json_response({
        "ok": True,
        "created": created,
        "tour": tour_to_dict(_owned_tour(request, tour_id), absolute_url_builder=lambda url: _absolute(request, url)),
        "message": "Navigation automatique créée.",
    })


@login_required
@require_POST
def mark_scene_published(request, scene_id):
    """Mark a scene as already published on Street View without re-uploading it."""
    scene = _scene_in_owned_tour(request, scene_id)
    data = _parse_json_body(request)
    if data is None:
        return _json_response({"ok": False, "error": "JSON invalide."}, status=400)

    photo_id = (data.get("photo_id") or data.get("google_photo_id") or "").strip()
    share_link = (data.get("share_link") or data.get("google_share_link") or "").strip()
    thumbnail_url = (data.get("thumbnail_url") or "").strip()
    status = data.get("publish_status") or StreetViewScene.PublishStatus.CREATED

    if not photo_id:
        return _json_response({"ok": False, "error": "Google Photo ID obligatoire."}, status=400)

    scene.google_photo_id = photo_id
    scene.google_share_link = share_link or _google_share_link_from_photo_id(photo_id)
    scene.google_thumbnail_url = thumbnail_url
    scene.publish_status = status if status in StreetViewScene.PublishStatus.values else StreetViewScene.PublishStatus.CREATED
    scene.last_error = ""
    scene.save(update_fields=["google_photo_id", "google_share_link", "google_thumbnail_url", "publish_status", "last_error", "updated_at"])
    scene.tour.status = StreetViewTour.Status.PUBLISHED
    scene.tour.published_at = scene.tour.published_at or timezone.now()
    scene.tour.save(update_fields=["status", "published_at", "updated_at"])

    return _json_response({"ok": True, "scene": scene_to_dict(scene, absolute_url_builder=lambda url: _absolute(request, url))})


@login_required
@require_POST
def clear_scene_google_publication(request, scene_id):
    scene = _scene_in_owned_tour(request, scene_id)
    scene.google_photo_id = ""
    scene.google_share_link = ""
    scene.google_thumbnail_url = ""
    scene.upload_reference_url = ""
    scene.publish_status = StreetViewScene.PublishStatus.READY if scene.has_gps else StreetViewScene.PublishStatus.LOCAL
    scene.last_error = ""
    scene.save(update_fields=["google_photo_id", "google_share_link", "google_thumbnail_url", "upload_reference_url", "publish_status", "last_error", "updated_at"])
    return _json_response({"ok": True, "scene": scene_to_dict(scene, absolute_url_builder=lambda url: _absolute(request, url))})


@login_required
@require_GET
def scene_google_status(request, scene_id):
    scene = _scene_in_owned_tour(request, scene_id)
    if not scene.google_photo_id:
        return _json_response({"ok": False, "error": "Cette scène n'a pas de Google Photo ID."}, status=400)
    try:
        client = _get_streetview_client_for_user(request)
        payload = client.get_photo(scene.google_photo_id, view=request.GET.get("view") or "INCLUDE_DOWNLOAD_URL")
        fields = extract_google_photo_fields(payload)
        if fields.get("share_link"):
            scene.google_share_link = fields["share_link"]
        elif not scene.google_share_link:
            scene.google_share_link = _google_share_link_from_photo_id(scene.google_photo_id)
        if fields.get("thumbnail_url"):
            scene.google_thumbnail_url = fields["thumbnail_url"]
        scene.last_error = ""
        scene.save(update_fields=["google_share_link", "google_thumbnail_url", "last_error", "updated_at"])
        return _json_response({"ok": True, "google": payload, "scene": scene_to_dict(scene, absolute_url_builder=lambda url: _absolute(request, url))})
    except Exception as exc:
        scene.last_error = str(exc)
        scene.save(update_fields=["last_error", "updated_at"])
        return _json_response({"ok": False, "error": str(exc), "scene": scene_to_dict(scene, absolute_url_builder=lambda url: _absolute(request, url))}, status=200)


@login_required
@require_GET
def tour_share_links(request, tour_id):
    tour = _owned_tour(request, tour_id)
    scenes = StreetViewScene.objects.filter(tour=tour).order_by("order", "id")
    links = []
    for scene in scenes:
        if not scene.google_photo_id:
            continue
        share_link = scene.google_share_link or _google_share_link_from_photo_id(scene.google_photo_id)
        links.append({
            "scene_id": scene.id,
            "title": scene.title,
            "photo_id": scene.google_photo_id,
            "share_link": share_link,
            "thumbnail_url": scene.google_thumbnail_url,
            "publish_status": scene.publish_status,
        })
    text = "\n".join([f"{item['title']}: {item['share_link']}" for item in links])
    return _json_response({"ok": True, "tour_id": tour.id, "title": tour.title, "count": len(links), "links": links, "share_text": text})


@login_required
@require_POST
def retry_google_connections(request, tour_id):
    tour = _owned_tour(request, tour_id)
    try:
        client = _get_streetview_client_for_user(request)
    except GoogleStreetViewAuthError as exc:
        return _json_response({
            "ok": False,
            "error": str(exc),
            "oauth_url": request.build_absolute_uri(reverse("apps.app_streetview:oauth_start")),
        }, status=401)

    initial = _send_google_connections(client, tour)
    before = sync_direct_project(client, tour)
    repair = repair_direct_connections(
        client,
        tour,
        attempts=max(1, min(int(getattr(settings, "STREETVIEW_CONNECTION_REPAIR_ATTEMPTS", 5)), 10)),
        base_delay=float(getattr(settings, "STREETVIEW_CONNECTION_REPAIR_BASE_DELAY", 2.0)),
    )
    after = sync_direct_project(client, tour)
    ok = bool(repair.get("ok")) and not after.get("rejected")
    return _json_response({
        "ok": ok,
        "initial": initial,
        "before": before,
        "repair": repair,
        "after": after,
        "tour": tour_to_dict(_owned_tour(request, tour_id), absolute_url_builder=lambda url: _absolute(request, url)),
    }, status=200 if ok else 207)


@login_required
@require_POST
def publish_tour(request, tour_id):
    tour = _owned_tour(request, tour_id)
    data = _parse_json_body(request) if request.body else {}
    if data is None:
        return _json_response({"ok": False, "error": "JSON invalide."}, status=400)

    skip_published = bool(data.get("skip_published", True))
    force_reupload = bool(data.get("force_reupload", False))
    auto_connect = bool(data.get("auto_connect", False))
    bidirectional = bool(data.get("bidirectional", True))

    if auto_connect:
        scenes_for_connect = list(StreetViewScene.objects.filter(tour=tour).order_by("order", "id"))
        for index, (src, dst) in enumerate(zip(scenes_for_connect, scenes_for_connect[1:])):
            StreetViewConnection.objects.get_or_create(
                tour=tour, from_scene=src, to_scene=dst,
                defaults={"label": f"Vers {dst.title}", "order": index * 2},
            )
            if bidirectional:
                StreetViewConnection.objects.get_or_create(
                    tour=tour, from_scene=dst, to_scene=src,
                    defaults={"label": f"Retour {src.title}", "order": index * 2 + 1},
                )

    try:
        client = _get_streetview_client_for_user(request)
    except GoogleStreetViewAuthError as exc:
        return _json_response({
            "ok": False,
            "error": str(exc),
            "oauth_url": request.build_absolute_uri(reverse("apps.app_streetview:oauth_start")),
        }, status=401)

    scenes = _publishable_scenes_for_tour(tour)
    if not scenes:
        return _json_response({"ok": False, "error": "Aucune scène dans cette visite."}, status=400)

    missing_gps = [scene.title for scene in scenes if not scene.has_gps]
    if missing_gps:
        return _json_response({"ok": False, "error": "Certaines scènes n'ont pas de GPS.", "scenes": missing_gps}, status=400)

    job = StreetViewPublishJob.objects.create(
        tour=tour,
        user=request.user,
        status=StreetViewPublishJob.Status.RUNNING,
        total_scenes=len(scenes),
    )
    tour.status = StreetViewTour.Status.PUBLISHING
    tour.last_error = ""
    tour.save(update_fields=["status", "last_error", "updated_at"])

    try:
        for scene in scenes:
            already = _scene_is_already_published(scene) and skip_published and not force_reupload
            if already:
                if not scene.google_share_link:
                    scene.google_share_link = _google_share_link_from_photo_id(scene.google_photo_id)
                    scene.save(update_fields=["google_share_link", "updated_at"])
                job.published_scenes += 1
                job.save(update_fields=["published_scenes", "updated_at"])
                job.append_log("info", f"Scène déjà publiée, upload ignoré: {scene.title}", scene_id=scene.id, google_photo_id=scene.google_photo_id)
                continue

            job.append_log("info", f"Upload de la scène {scene.title}", scene_id=scene.id)
            scene.publish_status = StreetViewScene.PublishStatus.UPLOADING
            scene.last_error = ""
            scene.save(update_fields=["publish_status", "last_error", "updated_at"])

            upload_url = client.start_upload()
            scene.upload_reference_url = upload_url
            scene.save(update_fields=["upload_reference_url", "updated_at"])

            prepared_path = None
            try:
                prepared_path = prepare_streetview_jpeg_with_xmp(scene)
                client.upload_photo_bytes(upload_url, prepared_path)
            finally:
                if prepared_path and prepared_path != scene.image.path:
                    try:
                        os.remove(prepared_path)
                    except OSError:
                        pass

            created_payload = client.create_photo(upload_url, scene)
            fields = extract_google_photo_fields(created_payload)

            scene.google_photo_id = fields["photo_id"]
            scene.google_share_link = fields["share_link"] or _google_share_link_from_photo_id(fields["photo_id"])
            scene.google_thumbnail_url = fields["thumbnail_url"]
            scene.publish_status = StreetViewScene.PublishStatus.CREATED
            scene.google_maps_publish_status = created_payload.get("mapsPublishStatus") or "UNSPECIFIED_MAPS_PUBLISH_STATUS"
            scene.google_transfer_status = created_payload.get("transferStatus") or "TRANSFER_STATUS_UNKNOWN"
            scene.google_status_payload = created_payload
            scene.google_last_synced_at = timezone.now()
            scene.connection_sync_status = "pending"
            scene.last_error = ""
            scene.save(update_fields=[
                "google_photo_id", "google_share_link", "google_thumbnail_url", "publish_status",
                "google_maps_publish_status", "google_transfer_status", "google_status_payload",
                "google_last_synced_at", "connection_sync_status", "last_error", "updated_at",
            ])
            job.published_scenes += 1
            job.save(update_fields=["published_scenes", "updated_at"])
            job.append_log("success", f"Photo créée sur Google Street View: {scene.google_photo_id}", scene_id=scene.id, share_link=scene.google_share_link)

        initial_connections = _send_google_connections(client, tour)
        for item in initial_connections["results"]:
            level = "success" if item.get("ok") else "warning"
            job.append_log(level, item.get("message") or "Connexion traitée", scene_id=item.get("scene_id"), targets=item.get("targets", []))

        status_before = sync_direct_project(client, tour)
        repaired = repair_direct_connections(
            client,
            tour,
            attempts=max(1, min(int(getattr(settings, "STREETVIEW_CONNECTION_REPAIR_ATTEMPTS", 5)), 10)),
            base_delay=float(getattr(settings, "STREETVIEW_CONNECTION_REPAIR_BASE_DELAY", 2.0)),
        )
        status_after = sync_direct_project(client, tour)
        warnings = int(initial_connections.get("warnings") or 0)
        warnings += sum(1 for item in repaired.get("results", []) if not item.get("ok"))
        warnings += int(status_after.get("rejected") or 0)
        result = {
            "initial": initial_connections, "status_before": status_before,
            "repair": repaired, "status_after": status_after, "warnings": warnings,
        }
        tour.status = StreetViewTour.Status.PUBLISHED
        tour.published_at = timezone.now()
        tour.last_error = ""
        tour.save(update_fields=["status", "published_at", "last_error", "updated_at"])

        job.status = StreetViewPublishJob.Status.SUCCEEDED_WITH_WARNINGS if warnings else StreetViewPublishJob.Status.SUCCEEDED
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "finished_at", "updated_at"])

        return _json_response({
            "ok": True,
            "job": publish_job_to_dict(job),
            "connections": result,
            "tour": tour_to_dict(_owned_tour(request, tour_id), absolute_url_builder=lambda url: _absolute(request, url)),
        }, status=200 if not warnings else 207)

    except StreetViewPublishError as exc:
        tour.status = StreetViewTour.Status.FAILED
        tour.last_error = str(exc)
        tour.save(update_fields=["status", "last_error", "updated_at"])

        job.status = StreetViewPublishJob.Status.FAILED
        job.error = str(exc)
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "error", "finished_at", "updated_at"])
        job.append_log("error", str(exc), status_code=getattr(exc, "status_code", None), payload=getattr(exc, "payload", {}))

        return _json_response({"ok": False, "error": str(exc), "job": publish_job_to_dict(job)}, status=500)


@login_required
@require_POST
def update_google_camera(request, scene_id):
    """Update Google pose metadata for an already published scene.

    This is useful after the user opens the panorama in Marzipano, clicks
    "Définir comme vue principale", and wants to push the new heading/pitch/roll
    to Google without re-uploading the image.
    """
    scene = _scene_in_owned_tour(request, scene_id)
    if not scene.google_photo_id:
        return _json_response({"ok": False, "error": "Cette scène n'a pas encore de Google Photo ID."}, status=400)

    try:
        client = _get_streetview_client_for_user(request)
        payload = client.update_photo_pose(scene.google_photo_id, scene)
        scene.last_error = ""
        if scene.publish_status == StreetViewScene.PublishStatus.LOCAL:
            scene.publish_status = StreetViewScene.PublishStatus.CREATED
        scene.save(update_fields=["publish_status", "last_error", "updated_at"])
        return _json_response({
            "ok": True,
            "message": "Caméra Google Street View mise à jour.",
            "google": payload,
            "scene": scene_to_dict(scene, absolute_url_builder=lambda url: _absolute(request, url)),
        })
    except Exception as exc:
        scene.last_error = str(exc)
        scene.save(update_fields=["last_error", "updated_at"])
        return _json_response({
            "ok": False,
            "error": str(exc),
            "scene": scene_to_dict(scene, absolute_url_builder=lambda url: _absolute(request, url)),
        }, status=400)


@login_required
@require_GET
def publish_job_status(request, job_public_id):
    job = get_object_or_404(StreetViewPublishJob, public_id=job_public_id, user=request.user)
    return _json_response({"job": publish_job_to_dict(job)})


@login_required
@require_POST
def direct_publish_scene(request, tour_id):
    """Publish one 360 image without storing its original bytes in MEDIA_ROOT.

    The uploaded file is written to a temporary file only long enough to validate,
    inject Photo Sphere XMP and stream it to Google's upload session. The database
    keeps metadata, Google status and navigation state, not the local image.
    """
    tour = _owned_tour(request, tour_id)
    image_file = request.FILES.get("image") or request.FILES.get("file")
    if not image_file:
        return _json_response({"ok": False, "error": "A 360 image is required."}, status=400)
    max_bytes = int(getattr(settings, "STREETVIEW_DIRECT_UPLOAD_MAX_BYTES", 120 * 1024 * 1024))
    if int(getattr(image_file, "size", 0) or 0) > max_bytes:
        return _json_response({"ok": False, "error": "The image is larger than the direct upload limit."}, status=413)

    latitude = _as_decimal(request.POST.get("latitude"))
    longitude = _as_decimal(request.POST.get("longitude"))
    if latitude is None or longitude is None:
        return _json_response({"ok": False, "error": "Latitude and longitude are required."}, status=400)

    title = (request.POST.get("title") or Path(image_file.name).stem or "Street View panorama").strip()[:180]
    heading = _as_float(request.POST.get("heading"), 0.0) or 0.0
    pitch = _as_float(request.POST.get("pitch"), 0.0) or 0.0
    roll = _as_float(request.POST.get("roll"), 0.0) or 0.0
    initial_fov = _as_float(request.POST.get("initial_fov"), 90.0) or 90.0
    capture_time = parse_datetime(request.POST.get("capture_time") or "")

    suffix = Path(image_file.name).suffix.lower() or ".jpg"
    fd, temp_path = tempfile.mkstemp(prefix="twinscopes-streetview-", suffix=suffix)
    os.close(fd)
    prepared_path = None
    scene = None
    try:
        with open(temp_path, "wb") as target:
            for chunk in image_file.chunks():
                target.write(chunk)

        metadata = extract_image_metadata(temp_path)
        width = int(metadata.get("width") or 0)
        height = int(metadata.get("height") or 0)
        ratio = width / max(height, 1)
        if width < 1024 or height < 512 or not 1.85 <= ratio <= 2.15:
            return _json_response({
                "ok": False,
                "error": "The uploaded image is not a valid full 360 equirectangular panorama.",
                "details": {"width": width, "height": height, "ratio": round(ratio, 4)},
            }, status=400)

        scene = StreetViewScene.objects.create(
            tour=tour,
            title=title,
            image="",
            image_width=width,
            image_height=height,
            file_size=int(getattr(image_file, "size", 0) or 0),
            latitude=latitude,
            longitude=longitude,
            altitude=_as_float(request.POST.get("altitude")),
            heading=heading,
            pitch=pitch,
            roll=roll,
            initial_yaw=heading,
            initial_pitch=pitch,
            initial_fov=initial_fov,
            capture_time=capture_time,
            xmp_detected=bool(metadata.get("xmp_detected")),
            exif_data=metadata,
            publish_status=StreetViewScene.PublishStatus.UPLOADING,
            remote_only=True,
            order=(tour.scenes.aggregate(value=Max("order"))["value"] or 0) + 1,
        )

        client = _get_streetview_client_for_user(request)
        upload_url = client.start_upload()
        scene.upload_reference_url = upload_url
        scene.save(update_fields=["upload_reference_url", "updated_at"])
        proxy = SimpleNamespace(
            id=scene.id,
            title=scene.title,
            image=SimpleNamespace(path=temp_path),
            latitude=latitude,
            longitude=longitude,
            altitude=scene.altitude,
            heading=heading,
            pitch=pitch,
            roll=roll,
            initial_fov=initial_fov,
            capture_time=capture_time,
            google_place_id=tour.google_place_id,
        )
        prepared_path = prepare_streetview_jpeg_with_xmp(proxy)
        client.upload_photo_bytes(upload_url, prepared_path)
        created = client.create_photo(upload_url, proxy)
        fields = extract_google_photo_fields(created)
        scene.google_photo_id = fields["photo_id"]
        scene.google_share_link = fields["share_link"] or _google_share_link_from_photo_id(fields["photo_id"])
        scene.google_thumbnail_url = fields["thumbnail_url"]
        scene.publish_status = StreetViewScene.PublishStatus.CREATED
        scene.google_maps_publish_status = created.get("mapsPublishStatus") or "UNSPECIFIED_MAPS_PUBLISH_STATUS"
        scene.google_transfer_status = created.get("transferStatus") or "TRANSFER_STATUS_UNKNOWN"
        scene.google_status_payload = created
        scene.google_last_synced_at = timezone.now()
        scene.last_error = ""
        scene.save(update_fields=[
            "google_photo_id", "google_share_link", "google_thumbnail_url", "publish_status",
            "google_maps_publish_status", "google_transfer_status", "google_status_payload",
            "google_last_synced_at", "last_error", "updated_at",
        ])
        tour.status = StreetViewTour.Status.PUBLISHED
        tour.published_at = timezone.now()
        tour.last_error = ""
        tour.save(update_fields=["status", "published_at", "last_error", "updated_at"])
        return _json_response({"ok": True, "scene": scene_to_dict(scene, absolute_url_builder=lambda value: _absolute(request, value)), "storage": "google_only"}, status=201)
    except (StreetViewPublishError, GoogleStreetViewAuthError, Exception) as exc:
        if scene:
            scene.publish_status = StreetViewScene.PublishStatus.FAILED
            scene.last_error = str(exc)
            scene.save(update_fields=["publish_status", "last_error", "updated_at"])
        return _json_response({"ok": False, "error": "Google Street View could not publish this panorama.", "details": str(exc)}, status=400)
    finally:
        for path in {temp_path, prepared_path}:
            if path:
                try:
                    os.remove(path)
                except OSError:
                    pass


@login_required
@require_POST
def sync_direct_project_status(request, tour_id):
    tour = _owned_tour(request, tour_id)
    try:
        client = _get_streetview_client_for_user(request)
        result = sync_direct_project(client, tour)
    except (StreetViewPublishError, GoogleStreetViewAuthError, Exception) as exc:
        return _json_response({"ok": False, "error": "Google status synchronization failed.", "details": str(exc)}, status=400)
    return _json_response(result)
