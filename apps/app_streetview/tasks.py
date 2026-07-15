from __future__ import annotations

from celery import shared_task

from apps.app_streetview.services.publish_runner import run_source_publish_job


@shared_task(bind=True, name="app_streetview.publish_source_tour_job")
def publish_source_tour_job(self, job_id: int, options: dict | None = None):
    """Celery entrypoint for Google Street View publishing.

    The real runner lives in services.publish_runner so the same job can also
    run through the local-thread fallback when Celery is not available.
    """
    options = dict(options or {})
    options.setdefault("runner", "celery")
    return run_source_publish_job(job_id, options)
