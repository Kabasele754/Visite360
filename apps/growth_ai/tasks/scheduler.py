from datetime import timedelta
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from apps.growth_ai.models import GrowthEvent, SyncRun

@shared_task
def cleanup_old_growth_data():
    now = timezone.now()
    deleted_runs, _ = SyncRun.objects.filter(created_at__lt=now - timedelta(days=getattr(settings, "GROWTH_AI_SYNC_RUN_RETENTION_DAYS", 180))).delete()
    deleted_events, _ = GrowthEvent.objects.filter(occurred_at__lt=now - timedelta(days=getattr(settings, "GROWTH_AI_EVENT_RETENTION_DAYS", 730))).delete()
    return {"deleted_sync_runs": deleted_runs, "deleted_events": deleted_events}
