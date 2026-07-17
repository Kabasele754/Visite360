from celery import shared_task
from apps.growth_ai.ai.report_writer import write_growth_report
from apps.growth_ai.analyzers.marketing import analyze_marketing
from apps.organizations.models import Organization

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=2)
def generate_organization_growth_report(self, organization_id, days=30):
    organization = Organization.objects.get(pk=organization_id)
    analysis = analyze_marketing(organization, days)
    return {"organization_id": organization_id, "days": days, "report": write_growth_report(organization, analysis), "analysis": analysis}
