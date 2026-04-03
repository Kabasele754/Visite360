from django.db import models
from apps.common.models import TimeStampedModel
from apps.organizations.models import Organization

class Place(TimeStampedModel):
    class Category(models.TextChoices):
        STORE = "store", "Store"
        BOUTIQUE = "boutique", "Boutique"
        WEDDING_HALL = "wedding_hall", "Wedding Hall"
        HOUSE = "house", "House"
        APARTMENT = "apartment", "Apartment"
        RESTAURANT = "restaurant", "Restaurant"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="places")
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    category = models.CharField(max_length=40, choices=Category.choices)
    description = models.TextField(blank=True)
    address_line = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120, blank=True)
    country = models.CharField(max_length=120, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    cover_image = models.URLField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["city", "category"]),
        ]

    def __str__(self):
        return self.name