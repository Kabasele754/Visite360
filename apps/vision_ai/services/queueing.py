from __future__ import annotations

import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import timedelta
from typing import Iterable

from django.conf import settings
from django.db import close_old_connections, transaction
from django.utils import timezone

from apps.tours.models import PipelineStatus, Scene360
from apps.vision_ai.models import VisionAnalysis
from apps.vision_ai.services.engine import execute_analysis
from apps.vision_ai.services.providers import enabled_provider_names
from apps.vision_ai.tasks import run_vision_analysis

logger = logging.getLogger(__name__)
_LOCAL_EXECUTOR = ThreadPoolExecutor(
    max_workers=max(1, int(getattr(settings, "VISION_LOCAL_THREAD_WORKERS", 1))),
    thread_name_prefix="twinscopes-vision",
)


def _execute_analysis_in_thread(analysis_id: str) -> None:
    """Run local on-demand vision without Celery or blocking the HTTP request."""
    close_old_connections()
    try:
        analysis = VisionAnalysis.objects.select_related(
            "organization", "scene", "scene__tour"
        ).get(pk=analysis_id)
        execute_analysis(analysis)
    except Exception:
        logger.exception("Local vision thread failed for analysis %s", analysis_id)
    finally:
        close_old_connections()


@dataclass(slots=True)
class SceneAnalysisDispatch:
    analysis: VisionAnalysis
    created: bool
    mode: str
    task_id: str = ""


def scene_has_readable_panorama(scene: Scene360) -> bool:
    return bool(
        scene.image_360_original
        or scene.image_360
        or scene.image_360_mobile
        or scene.image_360_preview
    )


def resolve_requested_providers(requested: Iterable[str] | None = None) -> list[str]:
    cleaned = [str(name).strip().lower() for name in (requested or []) if str(name).strip()]
    if not cleaned:
        cleaned = ["yolo", "paddleocr", "gemini", "openai", "florence2"]
    return enabled_provider_names(cleaned)


def latest_active_analysis(scene: Scene360) -> VisionAnalysis | None:
    return (
        VisionAnalysis.objects.filter(
            scene=scene,
            status__in=[VisionAnalysis.Status.PENDING, VisionAnalysis.Status.RUNNING],
        )
        .order_by("-created_at")
        .first()
    )


def latest_completed_analysis(scene: Scene360) -> VisionAnalysis | None:
    return (
        VisionAnalysis.objects.filter(
            scene=scene,
            status__in=[
                VisionAnalysis.Status.SUCCEEDED,
                VisionAnalysis.Status.PARTIAL,
                VisionAnalysis.Status.FAILED,
            ],
        )
        .order_by("-finished_at", "-created_at")
        .first()
    )


@transaction.atomic
def prepare_scene_analysis(
    scene: Scene360,
    *,
    force: bool = False,
    requested_providers: Iterable[str] | None = None,
) -> tuple[VisionAnalysis, bool]:
    scene = Scene360.objects.select_for_update().select_related("organization", "tour").get(pk=scene.pk)
    if not scene_has_readable_panorama(scene):
        raise RuntimeError(f"Scene {scene.pk} has no readable panorama image.")

    active = latest_active_analysis(scene)
    if active and not force:
        stale_minutes = max(
            5, int(getattr(settings, "VISION_ANALYSIS_STALE_MINUTES", 45))
        )
        reference_time = active.started_at or active.created_at
        if reference_time and reference_time < timezone.now() - timedelta(minutes=stale_minutes):
            active.status = VisionAnalysis.Status.FAILED
            active.error_message = (
                f"Analysis was considered stale after {stale_minutes} minutes and may be retried."
            )
            active.finished_at = timezone.now()
            active.save(update_fields=(
                "status", "error_message", "finished_at", "updated_at",
            ))
        else:
            return active, False

    completed = latest_completed_analysis(scene)
    if (
        completed
        and not force
        and completed.status in {VisionAnalysis.Status.SUCCEEDED, VisionAnalysis.Status.PARTIAL}
    ):
        return completed, False

    providers = resolve_requested_providers(requested_providers)
    if not providers:
        raise RuntimeError("No enabled computer-vision provider is configured.")

    analysis = VisionAnalysis.objects.create(
        organization=scene.organization,
        scene=scene,
        requested_providers=providers,
    )
    scene.ai_analysis_status = PipelineStatus.PENDING
    scene.ai_analysis_error = ""
    scene.save(update_fields=("ai_analysis_status", "ai_analysis_error", "updated_at"))
    return analysis, True


def dispatch_scene_analysis(
    scene: Scene360,
    *,
    force: bool = False,
    requested_providers: Iterable[str] | None = None,
    mode: str = "auto",
) -> SceneAnalysisDispatch:
    analysis, created = prepare_scene_analysis(
        scene,
        force=force,
        requested_providers=requested_providers,
    )
    if not created:
        return SceneAnalysisDispatch(analysis=analysis, created=False, mode="existing")

    selected_mode = mode
    if selected_mode == "auto":
        # Local browser requests must return immediately even when Docker,
        # Redis and Celery are not running. Explicit management commands still
        # use sync for deterministic testing.
        selected_mode = "thread" if getattr(settings, "DEBUG", False) else "celery"

    if selected_mode == "sync":
        execute_analysis(analysis)
        analysis.refresh_from_db()
        return SceneAnalysisDispatch(analysis=analysis, created=True, mode="sync")
    if selected_mode == "thread":
        local_task_id = f"local-thread-{uuid.uuid4()}"
        _LOCAL_EXECUTOR.submit(_execute_analysis_in_thread, str(analysis.pk))
        return SceneAnalysisDispatch(
            analysis=analysis,
            created=True,
            mode="thread",
            task_id=local_task_id,
        )
    if selected_mode != "celery":
        raise ValueError("mode must be one of: auto, sync, thread, celery")

    result = run_vision_analysis.delay(str(analysis.pk))
    return SceneAnalysisDispatch(
        analysis=analysis,
        created=True,
        mode="celery",
        task_id=str(result.id or ""),
    )


def analysis_status_payload(scene: Scene360) -> dict:
    analysis = (
        VisionAnalysis.objects.filter(scene=scene)
        .order_by("-created_at")
        .first()
    )
    if analysis is None:
        return {
            "scene_id": scene.pk,
            "status": "not_analyzed",
            "scene_status": scene.ai_analysis_status,
        }
    return {
        "scene_id": scene.pk,
        "analysis_id": str(analysis.pk),
        "status": analysis.status,
        "scene_status": scene.ai_analysis_status,
        "requested_providers": analysis.requested_providers,
        "completed_providers": analysis.completed_providers,
        "failed_providers": analysis.failed_providers,
        "scene_type": analysis.scene_type,
        "summary": analysis.summary,
        "confidence": analysis.confidence,
        "frame_count": analysis.frames.count(),
        "detection_count": analysis.detections.count(),
        "ocr_count": analysis.ocr_blocks.count(),
        "insight_count": analysis.insights.count(),
        "error": analysis.error_message,
        "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
        "started_at": analysis.started_at.isoformat() if analysis.started_at else None,
        "finished_at": analysis.finished_at.isoformat() if analysis.finished_at else None,
    }
