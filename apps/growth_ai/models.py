import hashlib
from django.conf import settings
from django.db import models
from apps.common.models import TimeStampedModel
from apps.organizations.models import Organization

class Provider(models.TextChoices):
    SEARCH_CONSOLE='search_console','Google Search Console'
    ANALYTICS='analytics','Google Analytics 4'
    BUSINESS_PROFILE='business_profile','Google Business Profile'
    GOOGLE_TRENDS='google_trends','Google Trends'
    BING='bing','Bing Webmaster'
    INTERNAL='internal','Twinscopes Internal'

class DataSourceConnection(TimeStampedModel):
    organization=models.ForeignKey(Organization,null=True,blank=True,on_delete=models.CASCADE,related_name='growth_connections')
    provider=models.CharField(max_length=40,choices=Provider.choices)
    name=models.CharField(max_length=120,blank=True)
    credential_ref=models.CharField(max_length=120,blank=True,help_text='Key in settings.GROWTH_AI_CREDENTIALS; secrets are not stored here.')
    config=models.JSONField(default=dict,blank=True)
    is_enabled=models.BooleanField(default=True)
    last_synced_at=models.DateTimeField(null=True,blank=True)
    last_error=models.TextField(blank=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['organization','provider','name'],name='growth_unique_source')]
        indexes=[models.Index(fields=['provider','is_enabled']),models.Index(fields=['organization','provider'])]
    def __str__(self): return self.name or self.get_provider_display()

class SyncRun(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING='pending','Pending'; RUNNING='running','Running'; SUCCESS='success','Success'; FAILED='failed','Failed'; PARTIAL='partial','Partial'
    connection=models.ForeignKey(DataSourceConnection,on_delete=models.CASCADE,related_name='sync_runs')
    status=models.CharField(max_length=20,choices=Status.choices,default=Status.PENDING)
    started_at=models.DateTimeField(null=True,blank=True); finished_at=models.DateTimeField(null=True,blank=True)
    rows_received=models.PositiveIntegerField(default=0); rows_saved=models.PositiveIntegerField(default=0)
    cursor=models.CharField(max_length=255,blank=True); error=models.TextField(blank=True); metadata=models.JSONField(default=dict,blank=True)
    class Meta: ordering=['-created_at']

class TrafficMetric(TimeStampedModel):
    connection=models.ForeignKey(DataSourceConnection,on_delete=models.CASCADE,related_name='metrics')
    organization=models.ForeignKey(Organization,null=True,blank=True,on_delete=models.CASCADE,related_name='growth_metrics')
    metric_date=models.DateField(db_index=True)
    granularity=models.CharField(max_length=20,default='day')
    dimensions=models.JSONField(default=dict,blank=True)
    dimension_hash=models.CharField(max_length=64,db_index=True)
    metrics=models.JSONField(default=dict,blank=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['connection','metric_date','granularity','dimension_hash'],name='growth_unique_metric_row')]
        indexes=[models.Index(fields=['organization','metric_date']),models.Index(fields=['connection','metric_date'])]
    @staticmethod
    def hash_dimensions(data):
        import json
        return hashlib.sha256(json.dumps(data or {},sort_keys=True,separators=(',',':')).encode()).hexdigest()
    def save(self,*args,**kwargs):
        self.dimension_hash=self.hash_dimensions(self.dimensions); super().save(*args,**kwargs)

class TrackedKeyword(TimeStampedModel):
    organization=models.ForeignKey(Organization,null=True,blank=True,on_delete=models.CASCADE,related_name='tracked_keywords')
    keyword=models.CharField(max_length=255); country=models.CharField(max_length=8,default='ZA'); language=models.CharField(max_length=12,default='en')
    is_active=models.BooleanField(default=True)
    class Meta: constraints=[models.UniqueConstraint(fields=['organization','keyword','country','language'],name='growth_unique_keyword')]

class GrowthEvent(TimeStampedModel):
    organization=models.ForeignKey(Organization,null=True,blank=True,on_delete=models.SET_NULL,related_name='growth_events')
    event_name=models.CharField(max_length=80,db_index=True)
    session_key=models.CharField(max_length=64,blank=True,db_index=True)
    user=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name='growth_events')
    tour_id=models.PositiveBigIntegerField(null=True,blank=True,db_index=True)
    product_id=models.PositiveBigIntegerField(null=True,blank=True,db_index=True)
    page_path=models.CharField(max_length=500,blank=True)
    referrer=models.CharField(max_length=500,blank=True)
    device=models.CharField(max_length=30,blank=True)
    source=models.CharField(max_length=120,blank=True)
    metadata=models.JSONField(default=dict,blank=True)
    occurred_at=models.DateTimeField(db_index=True)
    class Meta: indexes=[models.Index(fields=['organization','occurred_at']),models.Index(fields=['event_name','occurred_at'])]

class InternalDailySnapshot(TimeStampedModel):
    organization=models.ForeignKey(Organization,null=True,blank=True,on_delete=models.CASCADE,related_name='growth_daily_snapshots')
    snapshot_date=models.DateField(db_index=True)
    metrics=models.JSONField(default=dict,blank=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['organization','snapshot_date'],name='growth_unique_internal_snapshot')]
        ordering=['-snapshot_date']
