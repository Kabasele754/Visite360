from django.db import models
from apps.common.models import TimeStampedModel
from apps.organizations.models import Organization
from apps.places.models import Place

class Lead(TimeStampedModel):
    class Status(models.TextChoices):
        NEW = "new", "New"
        CONTACTED = "contacted", "Contacted"
        QUALIFIED = "qualified", "Qualified"
        CLOSED = "closed", "Closed"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="leads")
    place = models.ForeignKey(Place, on_delete=models.CASCADE, related_name="leads")
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    message = models.TextField(blank=True)
    source = models.CharField(max_length=32, default="web")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)