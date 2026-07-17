from dataclasses import dataclass
from django.conf import settings
from django.utils import timezone
from apps.growth_ai.models import TrafficMetric
@dataclass
class CollectorResult: received:int=0; saved:int=0; metadata:dict=None
class BaseCollector:
    provider=''
    def __init__(self,connection): self.connection=connection; self.config=connection.config or {}; self.credentials=(getattr(settings,'GROWTH_AI_CREDENTIALS',{}) or {}).get(connection.credential_ref,{})
    def collect(self,start_date,end_date): raise NotImplementedError
    def save_rows(self,rows):
        saved=0
        for row in rows:
            dims=row.get('dimensions') or {}
            _,created=TrafficMetric.objects.update_or_create(connection=self.connection,organization=self.connection.organization,metric_date=row['date'],granularity=row.get('granularity','day'),dimension_hash=TrafficMetric.hash_dimensions(dims),defaults={'dimensions':dims,'metrics':row.get('metrics') or {}})
            saved+=1
        return saved
