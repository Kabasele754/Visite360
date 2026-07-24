from celery import shared_task

from apps.organizations.models import Organization

from .models import OrganizationIntelligenceProfile
from .services.healthcare_sync import sync_healthcare_organization


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, max_retries=3)
def sync_domain_intelligence(self, organization_id: int, max_pages: int | None = None):
    organization = Organization.objects.get(pk=organization_id)
    profile, _ = OrganizationIntelligenceProfile.objects.get_or_create(organization=organization)
    try:
        if profile.domain_kind in {
            OrganizationIntelligenceProfile.DomainKind.HEALTHCARE,
            OrganizationIntelligenceProfile.DomainKind.MIXED,
        }:
            return sync_healthcare_organization(organization, max_pages=max_pages)
        return {"organization_id": organization_id, "status": "skipped", "reason": "No domain synchronizer is enabled."}
    except Exception as exc:
        profile.last_sync_status = "failed"
        profile.last_sync_error = str(exc)[:8000]
        profile.save(update_fields=("last_sync_status", "last_sync_error", "updated_at"))
        raise
