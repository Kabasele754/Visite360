from collections import Counter
from django.db.models import Count
from django.utils import timezone
from .base import BaseCollector,CollectorResult
from apps.growth_ai.models import GrowthEvent,InternalDailySnapshot
class InternalCollector(BaseCollector):
    provider='internal'
    def collect(self,start_date,end_date):
        qs=GrowthEvent.objects.filter(occurred_at__date__gte=start_date,occurred_at__date__lte=end_date)
        if self.connection.organization_id: qs=qs.filter(organization=self.connection.organization)
        saved=0
        for day in qs.dates('occurred_at','day'):
            dqs=qs.filter(occurred_at__date=day); counts=dict(dqs.values_list('event_name').annotate(c=Count('id')))
            metrics={'events':dqs.count(),'unique_sessions':dqs.exclude(session_key='').values('session_key').distinct().count(),**counts}
            InternalDailySnapshot.objects.update_or_create(organization=self.connection.organization,snapshot_date=day,defaults={'metrics':metrics}); saved+=1
        return CollectorResult(qs.count(),saved,{'days':saved})
