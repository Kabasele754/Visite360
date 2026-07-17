from datetime import timedelta
from celery import shared_task
from django.db.models import Count
from django.utils import timezone
from apps.growth_ai.analyzers.marketing import analyze_marketing
from apps.growth_ai.models import GrowthEvent, InternalDailySnapshot
from apps.organizations.models import Organization

@shared_task
def aggregate_internal_daily_snapshots(snapshot_date=None):
    target = timezone.datetime.fromisoformat(snapshot_date).date() if snapshot_date else timezone.localdate() - timedelta(days=1)
    start = timezone.make_aware(timezone.datetime.combine(target, timezone.datetime.min.time()))
    end = start + timedelta(days=1); base = GrowthEvent.objects.filter(occurred_at__gte=start, occurred_at__lt=end)
    saved = 0
    for organization_id in base.values_list("organization_id", flat=True).distinct():
        events = base.filter(organization_id=organization_id)
        counts = {row["event_name"]: row["total"] for row in events.values("event_name").annotate(total=Count("id"))}
        metrics = {"total_events": events.count(), "unique_sessions": events.exclude(session_key="").values("session_key").distinct().count(), "events": counts}
        InternalDailySnapshot.objects.update_or_create(organization_id=organization_id, snapshot_date=target, defaults={"metrics": metrics}); saved += 1
    return {"snapshot_date": target.isoformat(), "organizations": saved}

@shared_task
def analyze_organization_growth(organization_id, days=30):
    organization = Organization.objects.get(pk=organization_id)
    return analyze_marketing(organization, days)
