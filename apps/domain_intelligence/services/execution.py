from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
import logging
import uuid

from django.conf import settings
from django.db import close_old_connections

from apps.domain_intelligence.models import OrganizationIntelligenceRun

from .organization_sync import collect_organization_intelligence

logger = logging.getLogger(__name__)

_LOCAL_EXECUTOR = ThreadPoolExecutor(
    max_workers=max(1, int(getattr(settings, "DOMAIN_INTELLIGENCE_LOCAL_THREAD_WORKERS", 1))),
    thread_name_prefix="twinscopes-intelligence",
)


def _run_in_local_thread(run_id: str) -> None:
    close_old_connections()
    try:
        run = OrganizationIntelligenceRun.objects.get(pk=run_id)
        if run.status == OrganizationIntelligenceRun.Status.CANCELLED:
            return
        collect_organization_intelligence(run)
    except Exception:
        logger.exception("Local organization intelligence run %s failed.", run_id)
    finally:
        close_old_connections()


def _log_future_failure(run_id: str, future: Future) -> None:
    try:
        future.result()
    except Exception:
        # The worker wrapper already logs the full exception. This callback keeps
        # unobserved future exceptions from being silently discarded.
        logger.error("Background organization intelligence future %s ended with an error.", run_id)


def resolve_execution_mode(mode: str | None = None) -> str:
    requested = (mode or "auto").strip().lower()
    if requested != "auto":
        if requested not in {"sync", "thread", "celery"}:
            raise ValueError(f"Unsupported organization intelligence execution mode: {requested}")
        return requested

    configured = str(
        getattr(
            settings,
            "DOMAIN_INTELLIGENCE_EXECUTION_MODE",
            "thread" if settings.DEBUG else "celery",
        )
    ).strip().lower()
    return configured if configured in {"sync", "thread", "celery"} else ("thread" if settings.DEBUG else "celery")


def dispatch_organization_intelligence_run(
    run: OrganizationIntelligenceRun,
    *,
    mode: str | None = "auto",
) -> dict[str, str]:
    """Dispatch an organization intelligence run without leaving local runs stuck.

    Production uses Celery. Development defaults to an in-process background
    thread so ``runserver`` remains responsive and the status page can continue
    polling while the website is collected.
    """

    execution_mode = resolve_execution_mode(mode)

    if execution_mode == "sync":
        token = f"sync:{uuid.uuid4()}"
        run.task_id = token
        run.save(update_fields=("task_id", "updated_at"))
        collect_organization_intelligence(run)
        return {"mode": execution_mode, "task_id": token}

    if execution_mode == "thread":
        token = f"thread:{uuid.uuid4()}"
        run.task_id = token
        run.save(update_fields=("task_id", "updated_at"))
        future = _LOCAL_EXECUTOR.submit(_run_in_local_thread, str(run.pk))
        future.add_done_callback(lambda completed: _log_future_failure(str(run.pk), completed))
        return {"mode": execution_mode, "task_id": token}

    # Import lazily to avoid a circular import at Django startup.
    from apps.domain_intelligence.tasks import collect_organization_intelligence_task

    result = collect_organization_intelligence_task.apply_async(
        args=[str(run.pk)],
        queue=str(getattr(settings, "DOMAIN_INTELLIGENCE_CELERY_QUEUE", "ai")),
    )
    run.task_id = result.id
    run.save(update_fields=("task_id", "updated_at"))
    return {"mode": execution_mode, "task_id": result.id}
