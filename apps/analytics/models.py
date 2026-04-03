from django.db import models
from apps.common.models import TimeStampedModel
from apps.organizations.models import Organization
from apps.places.models import Place

class AnalyticsEvent(TimeStampedModel):
    organization = models.ForeignKey(Organization, null=True, blank=True, on_delete=models.SET_NULL, related_name="analytics_events")
    place = models.ForeignKey(Place, null=True, blank=True, on_delete=models.SET_NULL, related_name="analytics_events")
    event_type = models.CharField(max_length=64)
    session_id = models.CharField(max_length=128, blank=True)
    source = models.CharField(max_length=32, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    
    
    