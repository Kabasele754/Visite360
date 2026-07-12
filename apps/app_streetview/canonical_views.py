from __future__ import annotations

import json
import os
import time
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace

from django.contrib.auth.decorators import login_required
from django.db import transaction
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
    StreetViewSourcePublication,
    StreetViewSourcePublishJob,
    StreetViewSourceSceneState,
)
from .services.streetview_publish import StreetViewPublishClient, StreetViewPublishError, extract_google_photo_fields
from .services.tokens import GoogleStreetViewAuthError, get_valid_access_token
from .services.orientation import normalize_heading, normalize_pitch, normalize_roll, normalize_fov
from .services.xmp import prepare_streetview_jpeg_with_xmp


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
        raise GoogleStreetViewAuthError("Compte Google Street View non connecté.")
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
            results.append({
                "scene_id": source_scene_id,
                "state_id": state.id,
                "ok": True,
                "message": "Aucune connexion sortante à envoyer.",
                "targets": [],
            })
            continue

        last_error = None
        for attempt in range(1, max_attempts + 1):
            try:
                client.update_photo_connections(state.google_photo_id, target_photo_ids)
                state.publish_status = StreetViewSourceSceneState.PublishStatus.CONNECTED
                state.last_error = ""
                state.save(update_fields=["publish_status", "last_error", "updated_at"])
                updated += 1
                suffix = "" if attempt == 1 else f" après {attempt} tentatives"
                results.append({
                    "scene_id": source_scene_id,
                    "state_id": state.id,
                    "ok": True,
                    "message": f"Connexions Google mises à jour{suffix}.",
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
            state.last_error = str(last_error)
            state.save(update_fields=["last_error", "updated_at"])
            results.append({
                "scene_id": source_scene_id,
                "state_id": state.id,
                "ok": False,
                "message": str(last_error),
                "targets": target_photo_ids,
                "retry_advice": "Les photos sont publiées, mais Google ne les voit pas encore pour les connexions. Réessaie les connexions dans quelques minutes.",
            })

    return {"updated": updated, "warnings": warnings, "results": results}



@login_required
@require_GET
def publisher_page(request):
    return render(request, "app_streetview/canonical_publisher.html")


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
        return _json({"ok": False, "error": "Aucun GPS trouvé sur le tour ou le place."}, status=400)

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
        return _json({"ok": False, "error": "Scène source et scène cible requises."}, status=400)

    if str(from_scene_id) == str(to_scene_id):
        return _json({"ok": False, "error": "La scène source et la scène cible doivent être différentes."}, status=400)

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
        return _json({"ok": False, "error": "Cette scène n'a pas de Google Photo ID."}, status=400)

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
                "message": "Connexions nettoyées.",
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
    publication.last_error = "" if cleanup_warnings == 0 else "Photo supprimée, mais certaines connexions Google n'ont pas pu être nettoyées."
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
        return _json({"ok": False, "error": "Ce tour n'a aucune scène 360."}, status=400)

    missing = [s.source_scene.title for s in states if not s.has_gps]
    if missing:
        return _json({"ok": False, "error": "Certaines scènes n'ont pas de GPS.", "scenes": missing}, status=400)

    missing_images = [s.source_scene.title for s in states if not s.has_image]
    if missing_images:
        return _json({"ok": False, "error": "Certaines scènes n'ont pas d'image 360.", "scenes": missing_images}, status=400)

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
                job.append_log("info", f"Déjà publié, upload ignoré: {state.source_scene.title}", source_scene_id=state.source_scene_id, google_photo_id=state.google_photo_id)
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
            job.append_log("success", f"Photo Google créée: {state.google_photo_id}", source_scene_id=state.source_scene_id, share_link=state.google_share_link)

        result = _send_source_connections(client, publication)
        for item in result["results"]:
            level = "success" if item.get("ok") else "warning"
            job.append_log(level, item.get("message") or "Connexion traitée", source_scene_id=item.get("scene_id"), targets=item.get("targets", []))

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
