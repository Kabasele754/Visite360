from __future__ import annotations

import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import close_old_connections, transaction
from django.db.models import Max
from django.utils import timezone

from apps.tours.models import Tour, TourArchitectureRun

logger = logging.getLogger(__name__)
_LOCAL_EXECUTOR = ThreadPoolExecutor(
    max_workers=max(1, int(getattr(settings, "TOUR_ARCHITECT_LOCAL_THREAD_WORKERS", 1))),
    thread_name_prefix="twinscopes-architect",
)


@dataclass(slots=True)
class TourArchitectureDispatch:
    run: TourArchitectureRun
    created: bool
    mode: str
    task_id: str = ""


def _run_local(run_id: str, force: bool) -> None:
    close_old_connections()
    try:
        from apps.tours.intelligence.scene_architect import build_tour_architecture

        run = TourArchitectureRun.objects.select_related("tour", "organization").get(pk=run_id)
        build_tour_architecture(run.tour, run=run, force=force)
    except Exception:
        logger.exception("Local Tour Architect failed for run %s", run_id)
    finally:
        close_old_connections()


@transaction.atomic
def prepare_tour_architecture_run(tour: Tour, *, force: bool = False, user=None) -> tuple[TourArchitectureRun, bool]:
    tour = Tour.objects.select_for_update().select_related("organization").get(pk=tour.pk)
    stale_minutes = max(5, int(getattr(settings, "TOUR_ARCHITECT_STALE_MINUTES", 45)))
    active = (
        TourArchitectureRun.objects.filter(
            tour=tour,
            status__in=[TourArchitectureRun.Status.QUEUED, TourArchitectureRun.Status.RUNNING],
        )
        .order_by("-created_at")
        .first()
    )
    if active and not force:
        reference = active.started_at or active.created_at
        if reference and reference >= timezone.now() - timedelta(minutes=stale_minutes):
            return active, False
        active.status = TourArchitectureRun.Status.FAILED
        active.stage = "stale"
        active.error_code = "architect_run_stale"
        active.finished_at = timezone.now()
        active.save()

    run = TourArchitectureRun.objects.create(
        organization=tour.organization,
        tour=tour,
        status=TourArchitectureRun.Status.QUEUED,
        stage="queued",
        provider="gemini",
        model_name=str(getattr(settings, "TOUR_ARCHITECT_GEMINI_MODEL", "")),
        created_by=user if getattr(user, "is_authenticated", False) else None,
    )
    return run, True


def dispatch_tour_architecture(tour: Tour, *, force: bool = False, mode: str = "auto", user=None) -> TourArchitectureDispatch:
    if not bool(getattr(settings, "TOUR_ARCHITECT_ENABLED", True)):
        raise RuntimeError("tour_architect_disabled")
    run, created = prepare_tour_architecture_run(tour, force=force, user=user)
    if not created:
        return TourArchitectureDispatch(run=run, created=False, mode="existing")

    selected_mode = mode
    if selected_mode == "auto":
        selected_mode = "thread" if getattr(settings, "DEBUG", False) else "celery"

    if selected_mode == "sync":
        from apps.tours.intelligence.scene_architect import build_tour_architecture

        build_tour_architecture(tour, run=run, force=force)
        run.refresh_from_db()
        return TourArchitectureDispatch(run=run, created=True, mode="sync")
    if selected_mode == "thread":
        task_id = f"local-thread-{uuid.uuid4()}"
        _LOCAL_EXECUTOR.submit(_run_local, str(run.pk), force)
        return TourArchitectureDispatch(run=run, created=True, mode="thread", task_id=task_id)
    if selected_mode != "celery":
        raise ValueError("mode must be auto, sync, thread or celery")

    from apps.tours.tasks import run_tour_architect_task

    result = run_tour_architect_task.delay(str(run.pk), force=force)
    return TourArchitectureDispatch(run=run, created=True, mode="celery", task_id=str(result.id or ""))


def maybe_dispatch_tour_architecture(tour: Tour) -> TourArchitectureDispatch | None:
    if not bool(getattr(settings, "TOUR_ARCHITECT_ENABLED", True)):
        return None
    if not bool(getattr(settings, "TOUR_ARCHITECT_AUTO_RUN", True)):
        return None
    scenes = tour.scenes.all()
    total = scenes.count()
    if total < 2:
        return None
    completed = scenes.filter(ai_analysis_status__in=["ready", "failed"]).count()
    ready = scenes.filter(ai_analysis_status="ready").count()
    if ready < 2:
        return None
    if bool(getattr(settings, "TOUR_ARCHITECT_REQUIRE_ALL_SCENES_ANALYZED", True)) and completed < total:
        return None

    # Do not produce a duplicate review run when no scene intelligence changed
    # since the latest completed architecture proposal.
    latest_scene_analysis = scenes.aggregate(value=Max("ai_analyzed_at")).get("value")
    latest_run = (
        tour.architecture_runs.filter(
            status__in=[TourArchitectureRun.Status.REVIEW, TourArchitectureRun.Status.APPLIED]
        )
        .order_by("-finished_at", "-created_at")
        .first()
    )
    if latest_run and latest_scene_analysis:
        run_reference = latest_run.finished_at or latest_run.created_at
        if run_reference and run_reference >= latest_scene_analysis:
            return None

    return dispatch_tour_architecture(tour, force=False, mode="auto")
