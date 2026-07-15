from __future__ import annotations

import os
import time
from types import SimpleNamespace

from django.utils import timezone

from apps.app_streetview.models import (
    StreetViewGoogleAccount,
    StreetViewHistoryEvent,
    StreetViewSourcePublication,
    StreetViewSourcePublishJob,
    StreetViewSourceSceneState,
)
from apps.app_streetview.services.analytics import record_analytics, record_history
from apps.app_streetview.services.orientation import normalize_heading, normalize_pitch, normalize_roll, normalize_fov
from apps.app_streetview.services.quality import run_quality_check
from apps.app_streetview.services.streetview_publish import (
    StreetViewPublishClient,
    StreetViewPublishError,
    extract_google_photo_fields,
)
from apps.app_streetview.services.tokens import get_valid_access_token
from apps.app_streetview.services.xmp import prepare_streetview_jpeg_with_xmp


def google_share_link(photo_id: str) -> str:
    if not photo_id:
        return ""
    compact = str(photo_id).replace("CAoS", "CIAB", 1).rstrip(".")
    return f"https://www.google.com/maps/@0,0,0a,90y,90t/data=!3m4!1e1!3m2!1s{compact}!2e10"


def client_for_job(job: StreetViewSourcePublishJob) -> StreetViewPublishClient:
    account = StreetViewGoogleAccount.objects.filter(user=job.user).first()
    if not account or not account.is_connected:
        raise RuntimeError("Google Street View account is not connected.")
    return StreetViewPublishClient(access_token=get_valid_access_token(account))


def source_state_proxy(state: StreetViewSourceSceneState):
    return SimpleNamespace(
        id=state.id,
        title=state.source_scene.title,
        image=state.image_file,
        latitude=state.effective_latitude,
        longitude=state.effective_longitude,
        altitude=state.altitude,
        heading=normalize_heading(state.heading),
        pitch=normalize_pitch(state.pitch),
        roll=normalize_roll(state.roll),
        initial_fov=normalize_fov(state.initial_fov),
        capture_time=None,
    )


def set_job_stage(
    job: StreetViewSourcePublishJob,
    step: str,
    message: str,
    *,
    current: int | None = None,
    total: int | None = None,
    level: str = "stage",
    **extra,
):
    payload = {"step": step, **extra}
    if current is not None:
        payload["current"] = current
    if total is not None:
        payload["total"] = total
    job.append_log(level, message, **payload)


def _refresh_publication_status(publication: StreetViewSourcePublication, *, warnings: int = 0):
    published_count = publication.scene_states.filter(google_photo_id__gt="").count()
    connected_count = publication.scene_states.filter(
        publish_status=StreetViewSourceSceneState.PublishStatus.CONNECTED
    ).count()
    if published_count == 0:
        publication.status = StreetViewSourcePublication.Status.READY
        publication.published_at = None
    elif connected_count == published_count and warnings == 0:
        publication.status = StreetViewSourcePublication.Status.PUBLISHED
        publication.published_at = timezone.now()
    else:
        publication.status = StreetViewSourcePublication.Status.PUBLISHED
        publication.published_at = timezone.now()
    publication.last_error = ""
    publication.save(update_fields=["status", "published_at", "last_error", "updated_at"])


def run_source_publish_job(job_id: int, options: dict | None = None) -> dict:
    """Run one Street View publish job.

    This is intentionally independent from Celery. It can be called by:
    - a Celery worker;
    - the local-thread fallback;
    - a direct synchronous fallback.

    It updates StreetViewSourcePublishJob.log frequently, so the UI can poll and
    show progress such as: Uploading 4/20, Creating Google photos 7/20,
    Waiting for indexing, Updating connections, Done.
    """
    options = options or {}
    skip_published = bool(options.get("skip_published", True))
    force_reupload = bool(options.get("force_reupload", False))

    job = StreetViewSourcePublishJob.objects.select_related(
        "publication",
        "user",
        "publication__source_tour",
    ).get(pk=job_id)
    publication = job.publication

    job.status = StreetViewSourcePublishJob.Status.RUNNING
    job.error = ""
    job.save(update_fields=["status", "error", "updated_at"])
    publication.status = StreetViewSourcePublication.Status.PUBLISHING
    publication.last_error = ""
    publication.save(update_fields=["status", "last_error", "updated_at"])

    record_history(publication, job.user, StreetViewHistoryEvent.Action.PUBLISH_STARTED, "Publish job started.", job=job)
    record_analytics(publication, job.user, "publish_started", metadata={"job_id": job.id, "runner": options.get("runner", "auto")})

    try:
        set_job_stage(job, "preparing", "Preparing publish job.")
        quality = run_quality_check(publication)
        if not quality.get("ok"):
            raise RuntimeError("Quality check blocked publishing. Fix blockers first.")

        client = client_for_job(job)
        states = list(
            publication.scene_states.select_related("source_scene", "source_scene__tour", "source_scene__tour__place")
            .order_by("source_scene__order", "source_scene_id")
        )
        if not states:
            raise RuntimeError("This tour has no 360 scene.")

        missing_gps = [state.source_scene.title for state in states if not state.has_gps]
        if missing_gps:
            raise RuntimeError("Some scenes do not have GPS: " + ", ".join(missing_gps))

        missing_images = [state.source_scene.title for state in states if not state.has_image]
        if missing_images:
            raise RuntimeError("Some scenes do not have a 360 image: " + ", ".join(missing_images))

        job.total_scenes = len(states)
        job.published_scenes = 0
        job.failed_scenes = 0
        job.save(update_fields=["total_scenes", "published_scenes", "failed_scenes", "updated_at"])

        total = len(states)
        for index, state in enumerate(states, start=1):
            if state.google_photo_id and skip_published and not force_reupload:
                if not state.google_share_link:
                    state.google_share_link = google_share_link(state.google_photo_id)
                    state.save(update_fields=["google_share_link", "updated_at"])
                job.published_scenes += 1
                job.save(update_fields=["published_scenes", "updated_at"])
                set_job_stage(
                    job,
                    "uploading",
                    f"Uploading {index} / {total}: already published, skipped.",
                    current=index,
                    total=total,
                    level="info",
                    source_scene_id=state.source_scene_id,
                    google_photo_id=state.google_photo_id,
                )
                continue

            proxy = source_state_proxy(state)
            set_job_stage(
                job,
                "uploading",
                f"Uploading {index} / {total}: {proxy.title}",
                current=index,
                total=total,
                source_scene_id=state.source_scene_id,
            )
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

            set_job_stage(
                job,
                "creating",
                f"Creating Google photos {index} / {total}: {proxy.title}",
                current=index,
                total=total,
                source_scene_id=state.source_scene_id,
            )
            created_payload = client.create_photo(upload_url, proxy)
            fields = extract_google_photo_fields(created_payload)
            state.google_photo_id = fields["photo_id"]
            state.google_share_link = fields["share_link"] or google_share_link(fields["photo_id"])
            state.google_thumbnail_url = fields["thumbnail_url"]
            state.publish_status = StreetViewSourceSceneState.PublishStatus.CREATED
            state.last_error = ""
            state.save(update_fields=["google_photo_id", "google_share_link", "google_thumbnail_url", "publish_status", "last_error", "updated_at"])
            job.published_scenes += 1
            job.save(update_fields=["published_scenes", "updated_at"])
            job.append_log("success", f"Google photo created: {state.google_photo_id}", source_scene_id=state.source_scene_id, share_link=state.google_share_link, step="creating", current=index, total=total)

        set_job_stage(job, "indexing", "Waiting for indexing before updating connections.", current=total, total=total)
        wait_seconds = float(options.get("indexing_wait_seconds", 2) or 0)
        if wait_seconds > 0:
            time.sleep(min(wait_seconds, 15))

        set_job_stage(job, "connections", "Updating connections.", current=total, total=total)
        from apps.app_streetview.canonical_views import _send_source_connections

        result = _send_source_connections(client, publication)
        for item in result.get("results", []):
            level = "success" if item.get("ok") else "warning"
            job.append_log(level, item.get("message") or "Connection processed", source_scene_id=item.get("scene_id"), targets=item.get("targets", []), step="connections")

        _refresh_publication_status(publication, warnings=int(result.get("warnings") or 0))
        job.status = StreetViewSourcePublishJob.Status.SUCCEEDED_WITH_WARNINGS if result.get("warnings") else StreetViewSourcePublishJob.Status.SUCCEEDED
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "finished_at", "updated_at"])
        set_job_stage(job, "done", "Done.", current=total, total=total, level="success")

        record_history(publication, job.user, StreetViewHistoryEvent.Action.PUBLISH_FINISHED, "Publish finished.", job=job, metadata={"warnings": result.get("warnings", 0), "runner": options.get("runner", "auto")})
        record_analytics(publication, job.user, "publish_succeeded", metadata={"job_id": job.id, "warnings": result.get("warnings", 0), "runner": options.get("runner", "auto")})
        return {"ok": True, "job_id": job.id, "status": job.status, "connections": result}

    except (StreetViewPublishError, Exception) as exc:
        message = str(exc)
        publication.status = StreetViewSourcePublication.Status.FAILED
        publication.last_error = message
        publication.save(update_fields=["status", "last_error", "updated_at"])

        job.status = StreetViewSourcePublishJob.Status.FAILED
        job.error = message
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "error", "finished_at", "updated_at"])
        job.append_log("error", message, status_code=getattr(exc, "status_code", None), payload=getattr(exc, "payload", {}), step="failed")

        record_history(publication, job.user, StreetViewHistoryEvent.Action.PUBLISH_FAILED, message, job=job)
        record_analytics(publication, job.user, "publish_failed", metadata={"job_id": job.id, "error": message, "runner": options.get("runner", "auto")})
        raise
