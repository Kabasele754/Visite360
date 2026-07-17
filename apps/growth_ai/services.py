import hashlib
from datetime import timedelta
from django.utils import timezone
from .models import DataSourceConnection,SyncRun
from .collectors import get_collector

def sync_connection(connection,start_date=None,end_date=None):
    end_date=end_date or timezone.localdate()-timedelta(days=1); start_date=start_date or end_date-timedelta(days=int(connection.config.get('lookback_days',7))-1)
    run=SyncRun.objects.create(connection=connection,status=SyncRun.Status.RUNNING,started_at=timezone.now(),metadata={'start_date':str(start_date),'end_date':str(end_date)})
    try:
        result=get_collector(connection).collect(start_date,end_date)
        run.status=SyncRun.Status.SUCCESS; run.rows_received=result.received; run.rows_saved=result.saved; run.metadata={**run.metadata,**(result.metadata or {})}
        connection.last_synced_at=timezone.now(); connection.last_error=''; connection.save(update_fields=['last_synced_at','last_error','updated_at'])
    except Exception as exc:
        run.status=SyncRun.Status.FAILED; run.error=str(exc); connection.last_error=str(exc); connection.save(update_fields=['last_error','updated_at']); raise
    finally:
        run.finished_at=timezone.now(); run.save()
    return run
