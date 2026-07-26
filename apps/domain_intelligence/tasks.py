from __future__ import annotations

from celery import shared_task
from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from apps.organizations.models import Organization

from .models import OrganizationIntelligenceProfile, OrganizationIntelligenceRun
from .services.organization_sync import collect_organization_intelligence
from .services.readiness import calculate_organization_readiness


@shared_task(bind=True)
def collect_organization_intelligence_task(self, run_id: str):
    run = OrganizationIntelligenceRun.objects.select_related("organization", "requested_by").get(pk=run_id)
    if run.status == OrganizationIntelligenceRun.Status.CANCELLED:
        return {"run_id": str(run.id), "status": "cancelled"}
    run.task_id = self.request.id or run.task_id
    run.save(update_fields=("task_id", "updated_at"))
    return collect_organization_intelligence(run)


@shared_task(bind=True)
def sync_domain_intelligence(self, organization_id: int, max_pages: int | None = None):
    """Backward-compatible task that now runs the complete organization pipeline."""
    organization = Organization.objects.get(pk=organization_id)
    profile, _ = OrganizationIntelligenceProfile.objects.get_or_create(organization=organization)
    active = OrganizationIntelligenceRun.objects.filter(
        organization=organization,
        status__in=[OrganizationIntelligenceRun.Status.QUEUED, OrganizationIntelligenceRun.Status.RUNNING],
    ).order_by("-created_at").first()
    if active:
        return {"organization_id": organization_id, "status": "already_running", "run_id": str(active.id)}
    run = OrganizationIntelligenceRun.objects.create(
        organization=organization,
        trigger=OrganizationIntelligenceRun.Trigger.API,
        status=OrganizationIntelligenceRun.Status.QUEUED,
        website_url=organization.website_url,
        max_pages=max_pages or profile.website_sync_max_pages or 25,
        task_id=self.request.id or "",
    )
    return collect_organization_intelligence(run)


@shared_task
def refresh_all_intelligence_readiness():
    updated = 0
    for organization in Organization.objects.iterator():
        calculate_organization_readiness(organization)
        updated += 1
    return {"organizations_updated": updated}

@shared_task
def queue_due_organization_intelligence():
    limit = max(1, int(getattr(settings, "DOMAIN_INTELLIGENCE_SCHEDULE_BATCH_SIZE", 10)))
    profiles = (
        OrganizationIntelligenceProfile.objects.select_related("organization")
        .filter(auto_sync_website=True, organization__status=Organization.Status.ACTIVE, organization__ai_use_website=True)
        .exclude(organization__website_url="")
        .filter(Q(next_sync_at__isnull=True) | Q(next_sync_at__lte=timezone.now()))
        .order_by("next_sync_at", "id")
    )
    queued = 0
    skipped = 0
    for profile in profiles:
        if queued >= limit:
            break
        active = OrganizationIntelligenceRun.objects.filter(
            organization=profile.organization,
            status__in=[OrganizationIntelligenceRun.Status.QUEUED, OrganizationIntelligenceRun.Status.RUNNING],
        ).exists()
        if active:
            skipped += 1
            continue
        run = OrganizationIntelligenceRun.objects.create(
            organization=profile.organization,
            trigger=OrganizationIntelligenceRun.Trigger.SCHEDULED,
            website_url=profile.organization.website_url,
            max_pages=profile.website_sync_max_pages or 25,
        )
        result = collect_organization_intelligence_task.delay(str(run.id))
        run.task_id = result.id
        run.save(update_fields=("task_id", "updated_at"))
        queued += 1
    return {"queued": queued, "skipped": skipped}

