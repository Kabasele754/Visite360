from django.db import models


class ContactLead(models.Model):
    SERVICE_CHOICES = [
        ("virtual_tour", "360° Virtual Tour"),
        ("hotspots", "Interactive Hotspots"),
        ("showcase", "Property / Venue Showcase"),
        ("lead_capture", "Lead Capture & Booking"),
        ("branding", "Branded Presentation"),
        ("other", "Other"),
    ]

    full_name = models.CharField(max_length=150)
    email = models.EmailField()
    phone = models.CharField(max_length=50, blank=True)
    company_name = models.CharField(max_length=150, blank=True)
    service_interest = models.CharField(max_length=50, choices=SERVICE_CHOICES, default="virtual_tour")
    subject = models.CharField(max_length=200)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_processed = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Contact Lead"
        verbose_name_plural = "Contact Leads"

    def __str__(self):
        return f"{self.full_name} - {self.subject}"
    
    
    
    