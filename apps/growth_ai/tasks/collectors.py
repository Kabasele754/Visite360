from celery import shared_task
from django.conf import settings
from apps.growth_ai.models import DataSourceConnection
from apps.growth_ai.services import sync_connection

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_backoff_max=900, retry_jitter=True, max_retries=3)
def sync_growth_connection(self, connection_id: int):
    return sync_connection(DataSourceConnection.objects.get(pk=connection_id)).pk

@shared_task
def sync_all_growth_sources():
    if not getattr(settings, "GROWTH_AI_ENABLED", True): return {"queued": [], "disabled": True}
    ids = list(DataSourceConnection.objects.filter(is_enabled=True).order_by("pk").values_list("pk", flat=True))
    for connection_id in ids: sync_growth_connection.delay(connection_id)
    return {"queued": ids, "count": len(ids)}
