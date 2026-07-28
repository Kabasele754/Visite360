from __future__ import annotations

import logging

from celery import shared_task

from apps.app_streetview.models import (
    StreetViewGoogleAccount,
    StreetViewSourcePublication,
    StreetViewTour,
)
from apps.app_streetview.services.publish_runner import run_source_publish_job
from apps.app_streetview.services.status_sync import (
    repair_source_connections,
    sync_direct_project,
    sync_source_publication,
)
from apps.app_streetview.services.streetview_publish import StreetViewPublishClient
from apps.app_streetview.services.tokens import get_valid_access_token

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="app_streetview.publish_source_tour_job")
def publish_source_tour_job(self, job_id: int, options: dict | None = None):
    """Celery entrypoint for Google Street View publishing."""
    options = dict(options or {})
    options.setdefault("runner", "celery")
    return run_source_publish_job(job_id, options)


@shared_task(name="app_streetview.sync_google_publication_statuses")
def sync_google_publication_statuses(*, repair_connections: bool = False, repair_attempts: int = 3):
    """Refresh authoritative Google status for every connected account.

    A failed account or project is isolated so one expired OAuth connection does not
    stop the rest of the scheduled synchronization run.
    """
    summary = {"accounts": 0, "projects": 0, "publications": 0, "errors": []}
    for account in StreetViewGoogleAccount.objects.select_related("user").all():
        if not account.is_connected:
            continue
        summary["accounts"] += 1
        try:
            client = StreetViewPublishClient(access_token=get_valid_access_token(account))
        except Exception as exc:  # account-specific OAuth failure
            summary["errors"].append({"account": account.id, "error": str(exc)})
            continue

        for project in StreetViewTour.objects.filter(owner=account.user, auto_sync_status=True):
            try:
                sync_direct_project(client, project)
                summary["projects"] += 1
            except Exception as exc:
                logger.warning("Street View direct project sync failed project=%s: %s", project.id, exc)
                summary["errors"].append({"project": project.id, "error": str(exc)})

        for publication in StreetViewSourcePublication.objects.filter(owner=account.user):
            try:
                sync_source_publication(client, publication)
                if repair_connections:
                    repair_source_connections(client, publication, attempts=max(1, int(repair_attempts)))
                summary["publications"] += 1
            except Exception as exc:
                logger.warning("Street View source publication sync failed publication=%s: %s", publication.id, exc)
                summary["errors"].append({"publication": publication.id, "error": str(exc)})

    summary["ok"] = not summary["errors"]
    return summary
