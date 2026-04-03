from django.db import models
from apps.common.models import TimeStampedModel
from apps.organizations.models import Organization
from apps.places.models import Place

class BookingRequest(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        REJECTED = "rejected", "Rejected"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="booking_requests")
    place = models.ForeignKey(Place, on_delete=models.CASCADE, related_name="booking_requests")
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    requested_date = models.DateField(null=True, blank=True)
    guests_count = models.PositiveIntegerField(null=True, blank=True)
    budget = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    
    
    