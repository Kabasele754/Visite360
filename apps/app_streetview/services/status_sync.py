from __future__ import annotations

import time
from typing import Iterable

from django.db import transaction
from django.utils import timezone

from apps.tours.models import Hotspot
from apps.app_streetview.models import (
    StreetViewConnection,
    StreetViewScene,
    StreetViewSourcePublication,
    StreetViewSourceSceneState,
    StreetViewTour,
)
from apps.app_streetview.services.streetview_publish import StreetViewPublishClient, StreetViewPublishError


PUBLISHED = "PUBLISHED"
REJECTED = {"REJECTED_UNKNOWN"}


def _is_rejected_status(value: str) -> bool:
    return str(value or "").upper().startswith("REJECTED")


def _photo_id(payload: dict) -> str:
    value = payload.get("photoId") or {}
    return str(value.get("id") or value.get("photo_id") or "")


def _connection_ids(payload: dict) -> set[str]:
    output = set()
    for item in payload.get("connections") or []:
        target = item.get("target") or {}
        target_id = target.get("id") or target.get("photo_id")
        if target_id:
            output.add(str(target_id))
    return output


def _expected_source_targets(state: StreetViewSourceSceneState) -> list[str]:
    target_scene_ids = list(
        Hotspot.objects.filter(
            scene_id=state.source_scene_id,
            type=Hotspot.Type.NAVIGATE,
            target_scene__isnull=False,
        ).values_list("target_scene_id", flat=True)
    )
    return list(
        StreetViewSourceSceneState.objects.filter(
            publication=state.publication,
            source_scene_id__in=target_scene_ids,
        ).exclude(google_photo_id="").values_list("google_photo_id", flat=True)
    )


def _expected_direct_targets(scene: StreetViewScene) -> list[str]:
    target_scene_ids = StreetViewConnection.objects.filter(
        tour=scene.tour,
        from_scene=scene,
    ).values_list("to_scene_id", flat=True)
    return list(
        StreetViewScene.objects.filter(id__in=target_scene_ids)
        .exclude(google_photo_id="")
        .values_list("google_photo_id", flat=True)
    )


def _audit(expected: Iterable[str], actual: Iterable[str], maps_status: str) -> tuple[str, dict]:
    expected_set = {str(value) for value in expected if value}
    actual_set = {str(value) for value in actual if value}
    missing = sorted(expected_set - actual_set)
    unexpected = sorted(actual_set - expected_set)
    if _is_rejected_status(maps_status):
        status = "rejected"
    elif not expected_set:
        status = "not_required"
    elif not missing:
        status = "synced"
    elif actual_set:
        status = "partial"
    else:
        status = "missing"
    return status, {
        "expected": sorted(expected_set),
        "actual": sorted(actual_set),
        "missing": missing,
        "unexpected": unexpected,
        "checked_at": timezone.now().isoformat(),
    }


def _status_message(maps_status: str, audit_status: str) -> str:
    if maps_status == PUBLISHED and audit_status in {"synced", "not_required"}:
        return "Published and connected on Google Maps."
    if _is_rejected_status(maps_status):
        return "Google Maps rejected this panorama. Review image quality, privacy, GPS and panorama metadata."
    if maps_status == PUBLISHED:
        return "Published on Google Maps; navigation connections still need attention."
    return "Google is still processing or indexing this panorama."


def _apply_payload(instance, payload: dict, expected_targets: list[str]):
    maps_status = str(payload.get("mapsPublishStatus") or "UNSPECIFIED_MAPS_PUBLISH_STATUS")
    transfer_status = str(payload.get("transferStatus") or "TRANSFER_STATUS_UNKNOWN")
    try:
        view_count = int(payload.get("viewCount") or 0)
    except (TypeError, ValueError):
        view_count = 0
    audit_status, audit = _audit(expected_targets, _connection_ids(payload), maps_status)
    audit["message"] = _status_message(maps_status, audit_status)

    instance.google_maps_publish_status = maps_status
    instance.google_transfer_status = transfer_status
    instance.google_view_count = view_count
    instance.google_last_synced_at = timezone.now()
    instance.google_status_payload = {
        "photo_id": _photo_id(payload),
        "maps_publish_status": maps_status,
        "transfer_status": transfer_status,
        "view_count": view_count,
        "share_link": payload.get("shareLink") or "",
        "thumbnail_url": payload.get("thumbnailUrl") or "",
        "upload_time": payload.get("uploadTime") or "",
    }
    instance.connection_sync_status = audit_status
    instance.connection_audit = audit
    if _is_rejected_status(maps_status):
        instance.publish_status = "failed"
    elif maps_status == PUBLISHED and audit_status in {"synced", "not_required"}:
        instance.publish_status = "connected"
    elif getattr(instance, "google_photo_id", ""):
        instance.publish_status = "created"
    if payload.get("shareLink"):
        instance.google_share_link = payload["shareLink"]
    if payload.get("thumbnailUrl"):
        instance.google_thumbnail_url = payload["thumbnailUrl"]


def _cleanup_direct_local_bytes(scene: StreetViewScene):
    if scene.tour.storage_policy != StreetViewTour.StoragePolicy.DELETE_AFTER_VERIFIED:
        return False
    if scene.google_maps_publish_status != PUBLISHED or scene.remote_only or not scene.image:
        return False
    try:
        scene.image.delete(save=False)
    except Exception:
        return False
    scene.image = ""
    scene.remote_only = True
    scene.local_bytes_deleted_at = timezone.now()
    return True


def sync_source_state(client: StreetViewPublishClient, state: StreetViewSourceSceneState) -> dict:
    if not state.google_photo_id:
        return {"ok": False, "status": "not_published", "scene_id": state.source_scene_id}
    payload = client.get_photo(state.google_photo_id, view="BASIC")
    _apply_payload(state, payload, _expected_source_targets(state))
    state.last_error = "" if not _is_rejected_status(state.google_maps_publish_status) else state.connection_audit.get("message", "Rejected by Google Maps")
    state.save(update_fields=[
        "publish_status", "google_maps_publish_status", "google_transfer_status", "google_view_count",
        "google_last_synced_at", "google_status_payload", "connection_sync_status",
        "connection_audit", "google_share_link", "google_thumbnail_url", "last_error", "updated_at",
    ])
    return {"ok": True, "scene_id": state.source_scene_id, "photo_id": state.google_photo_id, "maps_status": state.google_maps_publish_status, "connection_status": state.connection_sync_status, "audit": state.connection_audit}


def sync_direct_scene(client: StreetViewPublishClient, scene: StreetViewScene) -> dict:
    if not scene.google_photo_id:
        return {"ok": False, "status": "not_published", "scene_id": scene.id}
    payload = client.get_photo(scene.google_photo_id, view="BASIC")
    _apply_payload(scene, payload, _expected_direct_targets(scene))
    scene.last_error = "" if not _is_rejected_status(scene.google_maps_publish_status) else scene.connection_audit.get("message", "Rejected by Google Maps")
    deleted = _cleanup_direct_local_bytes(scene)
    update_fields = [
        "publish_status", "google_maps_publish_status", "google_transfer_status", "google_view_count",
        "google_last_synced_at", "google_status_payload", "connection_sync_status",
        "connection_audit", "google_share_link", "google_thumbnail_url", "last_error", "updated_at",
    ]
    if deleted:
        update_fields += ["image", "remote_only", "local_bytes_deleted_at"]
    scene.save(update_fields=update_fields)
    return {"ok": True, "scene_id": scene.id, "photo_id": scene.google_photo_id, "maps_status": scene.google_maps_publish_status, "connection_status": scene.connection_sync_status, "local_deleted": deleted, "audit": scene.connection_audit}


def sync_source_publication(client: StreetViewPublishClient, publication: StreetViewSourcePublication) -> dict:
    results = []
    for state in publication.scene_states.exclude(google_photo_id="").select_related("source_scene"):
        try:
            results.append(sync_source_state(client, state))
        except StreetViewPublishError as exc:
            state.last_error = str(exc)
            state.google_last_synced_at = timezone.now()
            state.save(update_fields=["last_error", "google_last_synced_at", "updated_at"])
            results.append({"ok": False, "scene_id": state.source_scene_id, "error": str(exc), "status_code": exc.status_code})
    return _summary(results)


def sync_direct_project(client: StreetViewPublishClient, tour: StreetViewTour) -> dict:
    results = []
    for scene in tour.scenes.exclude(google_photo_id=""):
        try:
            results.append(sync_direct_scene(client, scene))
        except StreetViewPublishError as exc:
            scene.last_error = str(exc)
            scene.google_last_synced_at = timezone.now()
            scene.save(update_fields=["last_error", "google_last_synced_at", "updated_at"])
            results.append({"ok": False, "scene_id": scene.id, "error": str(exc), "status_code": exc.status_code})
    return _summary(results)


def _summary(results: list[dict]) -> dict:
    return {
        "ok": all(item.get("ok") for item in results) if results else True,
        "total": len(results),
        "published": sum(item.get("maps_status") == PUBLISHED for item in results),
        "rejected": sum(_is_rejected_status(item.get("maps_status")) for item in results),
        "connections_synced": sum(item.get("connection_status") in {"synced", "not_required"} for item in results),
        "results": results,
    }


def repair_source_connections(client: StreetViewPublishClient, publication: StreetViewSourcePublication, *, attempts: int = 5, base_delay: float = 2.0) -> dict:
    results = []
    states = list(publication.scene_states.exclude(google_photo_id="").select_related("source_scene"))
    for state in states:
        targets = _expected_source_targets(state)
        if not targets:
            state.connection_sync_status = "not_required"
            state.connection_audit = {"expected": [], "actual": [], "missing": [], "checked_at": timezone.now().isoformat()}
            state.save(update_fields=["connection_sync_status", "connection_audit", "updated_at"])
            results.append({"ok": True, "scene_id": state.source_scene_id, "status": "not_required"})
            continue
        last_error = ""
        for attempt in range(1, max(1, attempts) + 1):
            try:
                client.update_photo_connections(state.google_photo_id, targets)
                verification = sync_source_state(client, state)
                if verification.get("connection_status") == "synced":
                    results.append({"ok": True, "scene_id": state.source_scene_id, "status": "synced", "attempt": attempt})
                    break
                last_error = "Google accepted the update but the connection is not visible yet."
            except StreetViewPublishError as exc:
                last_error = str(exc)
                if exc.status_code not in {409, 429, 503} and "indexed" not in last_error.lower() and "unavailable" not in last_error.lower():
                    break
            if attempt < attempts:
                time.sleep(min(base_delay * (2 ** (attempt - 1)), 20))
        else:
            pass
        if not any(item.get("scene_id") == state.source_scene_id and item.get("ok") for item in results):
            state.connection_sync_status = "failed"
            state.last_error = last_error
            state.save(update_fields=["connection_sync_status", "last_error", "updated_at"])
            results.append({"ok": False, "scene_id": state.source_scene_id, "status": "failed", "error": last_error})
    return _summary(results)


def repair_direct_connections(client: StreetViewPublishClient, tour: StreetViewTour, *, attempts: int = 5, base_delay: float = 2.0) -> dict:
    """Repair and verify navigation for a standalone Google project."""
    results = []
    scenes = list(tour.scenes.exclude(google_photo_id=""))
    for scene in scenes:
        targets = _expected_direct_targets(scene)
        if not targets:
            scene.connection_sync_status = "not_required"
            scene.connection_audit = {
                "expected": [], "actual": [], "missing": [], "unexpected": [],
                "checked_at": timezone.now().isoformat(),
                "message": "This panorama has no outgoing Google navigation connection.",
            }
            scene.save(update_fields=["connection_sync_status", "connection_audit", "updated_at"])
            results.append({"ok": True, "scene_id": scene.id, "status": "not_required"})
            continue
        last_error = ""
        completed = False
        for attempt in range(1, max(1, attempts) + 1):
            try:
                client.update_photo_connections(scene.google_photo_id, targets)
                verification = sync_direct_scene(client, scene)
                if verification.get("connection_status") == "synced":
                    results.append({"ok": True, "scene_id": scene.id, "status": "synced", "attempt": attempt})
                    completed = True
                    break
                last_error = "Google accepted the update but the navigation is not visible yet."
            except StreetViewPublishError as exc:
                last_error = str(exc)
                if exc.status_code not in {409, 429, 503} and "indexed" not in last_error.lower() and "unavailable" not in last_error.lower():
                    break
            if attempt < attempts:
                time.sleep(min(base_delay * (2 ** (attempt - 1)), 20))
        if not completed:
            scene.connection_sync_status = "failed"
            scene.last_error = last_error
            scene.connection_audit = {
                "expected": targets,
                "actual": (scene.connection_audit or {}).get("actual", []),
                "missing": targets,
                "unexpected": [],
                "checked_at": timezone.now().isoformat(),
                "message": "Google navigation could not be verified yet.",
            }
            scene.save(update_fields=["connection_sync_status", "connection_audit", "last_error", "updated_at"])
            results.append({"ok": False, "scene_id": scene.id, "status": "failed", "error": last_error})
    return _summary(results)
