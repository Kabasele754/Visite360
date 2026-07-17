from django.contrib import admin
from .models import DataSourceConnection,SyncRun,TrafficMetric,TrackedKeyword,GrowthEvent,InternalDailySnapshot
@admin.register(DataSourceConnection)
class DataSourceConnectionAdmin(admin.ModelAdmin):
    list_display=('name','provider','organization','is_enabled','last_synced_at'); list_filter=('provider','is_enabled'); search_fields=('name','organization__name')
@admin.register(SyncRun)
class SyncRunAdmin(admin.ModelAdmin): list_display=('connection','status','started_at','finished_at','rows_saved'); list_filter=('status','connection__provider')
@admin.register(TrafficMetric)
class TrafficMetricAdmin(admin.ModelAdmin): list_display=('connection','organization','metric_date','granularity'); list_filter=('connection__provider','granularity')
admin.site.register(TrackedKeyword); admin.site.register(GrowthEvent); admin.site.register(InternalDailySnapshot)
