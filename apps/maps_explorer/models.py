from django.db import models
from apps.common.models import TimeStampedModel
from apps.places.models import Place
from apps.organizations.models import Organization

class PlaceMapContext(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="map_contexts")
    place = models.OneToOneField(Place, on_delete=models.CASCADE, related_name="map_context")
    street_view_available = models.BooleanField(default=False)
    street_view_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    street_view_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    heading = models.FloatField(null=True, blank=True)
    pitch = models.FloatField(null=True, blank=True)
    zoom = models.FloatField(null=True, blank=True)
    geocode_payload = models.JSONField(default=dict, blank=True)
    

