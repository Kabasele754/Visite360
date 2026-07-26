from __future__ import annotations

from decimal import Decimal
import uuid

from django.conf import settings

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.common.models import TimeStampedModel


class OrganizationIntelligenceProfile(TimeStampedModel):
    class DomainKind(models.TextChoices):
        GENERAL = "general", "General"
        HEALTHCARE = "healthcare", "Healthcare"
        REAL_ESTATE = "real_estate", "Real estate"
        HOSPITALITY = "hospitality", "Hospitality"
        MIXED = "mixed", "Mixed"

    organization = models.OneToOneField(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="intelligence_profile",
    )
    domain_kind = models.CharField(
        max_length=24,
        choices=DomainKind.choices,
        default=DomainKind.GENERAL,
        db_index=True,
    )
    default_locale = models.CharField(max_length=16, default="en")
    timezone = models.CharField(max_length=80, default="Africa/Johannesburg")
    country_code = models.CharField(max_length=3, blank=True)
    auto_sync_website = models.BooleanField(default=True)
    website_sync_max_pages = models.PositiveSmallIntegerField(default=30)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_sync_status = models.CharField(max_length=24, blank=True)
    last_sync_error = models.TextField(blank=True)

    class ReadinessStatus(models.TextChoices):
        NOT_READY = "not_ready", "Not ready"
        IN_PROGRESS = "in_progress", "In progress"
        REVIEW = "review", "Needs review"
        READY = "ready", "Client ready"

    readiness_score = models.PositiveSmallIntegerField(default=0)
    readiness_status = models.CharField(
        max_length=24,
        choices=ReadinessStatus.choices,
        default=ReadinessStatus.NOT_READY,
        db_index=True,
    )
    readiness_breakdown = models.JSONField(default=dict, blank=True)
    readiness_checked_at = models.DateTimeField(null=True, blank=True)
    next_sync_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.organization.name} — {self.get_domain_kind_display()}"


class HealthcareFacilityProfile(TimeStampedModel):
    place = models.OneToOneField(
        "places.Place",
        on_delete=models.CASCADE,
        related_name="healthcare_profile",
    )
    appointment_phone = models.CharField(max_length=60, blank=True)
    appointment_email = models.EmailField(blank=True)
    appointment_url = models.URLField(blank=True)
    emergency_phone = models.CharField(max_length=60, blank=True)
    accepts_walk_ins = models.BooleanField(default=False)
    telemedicine_available = models.BooleanField(default=False)
    opening_hours = models.JSONField(default=list, blank=True)
    specialties = models.JSONField(default=list, blank=True)
    insurance_providers = models.JSONField(default=list, blank=True)
    accessibility = models.JSONField(default=list, blank=True)
    source_url = models.URLField(blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Healthcare — {self.place.name}"


class MedicalSpecialty(TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="medical_specialties",
    )
    name = models.CharField(max_length=180)
    slug = models.SlugField(max_length=200)
    description = models.TextField(blank=True)
    aliases = models.JSONField(default=list, blank=True)
    default_duration_minutes = models.PositiveSmallIntegerField(default=30)
    source_url = models.URLField(blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "slug"),
                name="unique_medical_specialty_slug_per_org",
            )
        ]

    def __str__(self):
        return f"{self.organization.name} — {self.name}"


class MedicalPractitioner(TimeStampedModel):
    class BookingMode(models.TextChoices):
        REQUEST = "request", "Request confirmation"
        DIRECT = "direct", "Direct booking"
        CONTACT = "contact", "Contact facility"

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="medical_practitioners",
    )
    place = models.ForeignKey(
        "places.Place",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="medical_practitioners",
    )
    specialty = models.ForeignKey(
        MedicalSpecialty,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="practitioners",
    )
    full_name = models.CharField(max_length=255)
    professional_title = models.CharField(max_length=180, blank=True)
    bio = models.TextField(blank=True)
    languages = models.JSONField(default=list, blank=True)
    public_phone = models.CharField(max_length=60, blank=True)
    public_email = models.EmailField(blank=True)
    booking_url = models.URLField(blank=True)
    booking_mode = models.CharField(
        max_length=16,
        choices=BookingMode.choices,
        default=BookingMode.REQUEST,
    )
    show_public_phone = models.BooleanField(default=False)
    show_public_email = models.BooleanField(default=False)
    source_url = models.URLField(blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("full_name",)
        indexes = [
            models.Index(fields=("organization", "is_active")),
            models.Index(fields=("organization", "specialty")),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "full_name", "specialty"),
                name="unique_practitioner_name_specialty_per_org",
            )
        ]

    def __str__(self):
        return self.full_name

    def public_contact_payload(self) -> dict:
        return {
            "phone": self.public_phone if self.show_public_phone else "",
            "email": self.public_email if self.show_public_email else "",
            "booking_url": self.booking_url,
        }


class PractitionerAvailability(TimeStampedModel):
    class Weekday(models.IntegerChoices):
        MONDAY = 0, "Monday"
        TUESDAY = 1, "Tuesday"
        WEDNESDAY = 2, "Wednesday"
        THURSDAY = 3, "Thursday"
        FRIDAY = 4, "Friday"
        SATURDAY = 5, "Saturday"
        SUNDAY = 6, "Sunday"

    practitioner = models.ForeignKey(
        MedicalPractitioner,
        on_delete=models.CASCADE,
        related_name="availability_slots",
    )
    weekday = models.PositiveSmallIntegerField(choices=Weekday.choices)
    starts_at = models.TimeField()
    ends_at = models.TimeField()
    location_label = models.CharField(max_length=180, blank=True)
    appointment_mode = models.CharField(max_length=24, default="in_person")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("weekday", "starts_at")


class PropertyListingProfile(TimeStampedModel):
    class ListingType(models.TextChoices):
        RENT = "rent", "For rent"
        SALE = "sale", "For sale"
        SHORT_STAY = "short_stay", "Short stay"

    class PropertyType(models.TextChoices):
        HOUSE = "house", "House"
        APARTMENT = "apartment", "Apartment"
        VILLA = "villa", "Villa"
        STUDIO = "studio", "Studio"
        OFFICE = "office", "Office"
        BUILDING = "building", "Building"
        LAND = "land", "Land"
        OTHER = "other", "Other"

    class AvailabilityStatus(models.TextChoices):
        AVAILABLE = "available", "Available"
        RESERVED = "reserved", "Reserved"
        RENTED = "rented", "Rented"
        SOLD = "sold", "Sold"
        UNAVAILABLE = "unavailable", "Unavailable"

    place = models.OneToOneField(
        "places.Place",
        on_delete=models.CASCADE,
        related_name="property_profile",
    )
    listing_type = models.CharField(
        max_length=20,
        choices=ListingType.choices,
        default=ListingType.RENT,
        db_index=True,
    )
    property_type = models.CharField(
        max_length=20,
        choices=PropertyType.choices,
        default=PropertyType.HOUSE,
        db_index=True,
    )
    bedrooms = models.PositiveSmallIntegerField(default=0, db_index=True)
    bathrooms = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        default=Decimal("0.0"),
        validators=[MinValueValidator(0), MaxValueValidator(99)],
    )
    parking_spaces = models.PositiveSmallIntegerField(default=0)
    furnished = models.BooleanField(default=False)
    area_sqm = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    price = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, db_index=True)
    currency = models.CharField(max_length=8, default="USD")
    available_from = models.DateField(null=True, blank=True)
    amenities = models.JSONField(default=list, blank=True)
    pet_friendly = models.BooleanField(default=False)
    availability_status = models.CharField(
        max_length=20,
        choices=AvailabilityStatus.choices,
        default=AvailabilityStatus.AVAILABLE,
        db_index=True,
    )
    source_url = models.URLField(blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=("listing_type", "property_type", "bedrooms")),
            models.Index(fields=("availability_status", "price")),
        ]

    def __str__(self):
        return f"{self.place.name} — {self.get_listing_type_display()}"


class HospitalityProfile(TimeStampedModel):
    place = models.OneToOneField(
        "places.Place",
        on_delete=models.CASCADE,
        related_name="hospitality_profile",
    )
    star_rating = models.DecimalField(
        max_digits=2,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
    )
    room_count = models.PositiveIntegerField(null=True, blank=True)
    price_from = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=8, default="USD")
    check_in_time = models.TimeField(null=True, blank=True)
    check_out_time = models.TimeField(null=True, blank=True)
    amenities = models.JSONField(default=list, blank=True)
    booking_url = models.URLField(blank=True)
    is_available = models.BooleanField(default=True)
    source_url = models.URLField(blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Hospitality — {self.place.name}"


class VerifiedSourceFact(TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="verified_domain_facts",
    )
    place = models.ForeignKey(
        "places.Place",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="verified_domain_facts",
    )
    entity_type = models.CharField(max_length=80, db_index=True)
    entity_key = models.CharField(max_length=255, blank=True, db_index=True)
    field_name = models.CharField(max_length=120, db_index=True)
    value = models.JSONField(default=dict, blank=True)
    source_url = models.URLField()
    confidence = models.DecimalField(
        max_digits=4,
        decimal_places=3,
        default=Decimal("1.000"),
        validators=[MinValueValidator(0), MaxValueValidator(1)],
    )
    verified_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_public = models.BooleanField(default=True)

    class Meta:
        ordering = ("-verified_at",)
        indexes = [
            models.Index(fields=("organization", "entity_type", "field_name")),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "entity_type", "entity_key", "field_name", "source_url"),
                name="unique_verified_domain_fact_source",
            )
        ]


class DiscoverySearchLog(TimeStampedModel):
    query = models.CharField(max_length=500)
    normalized_intent = models.JSONField(default=dict, blank=True)
    result_count = models.PositiveIntegerField(default=0)
    session_key = models.CharField(max_length=80, blank=True, db_index=True)
    selected_tour = models.ForeignKey(
        "tours.Tour",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="discovery_search_selections",
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-created_at",)

class OrganizationIntelligenceRun(TimeStampedModel):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        PARTIAL = "partial", "Partial"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    class Trigger(models.TextChoices):
        MANUAL = "manual", "Manual"
        SCHEDULED = "scheduled", "Scheduled"
        ONBOARDING = "onboarding", "Onboarding"
        API = "api", "API"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="intelligence_runs",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requested_intelligence_runs",
    )
    trigger = models.CharField(max_length=24, choices=Trigger.choices, default=Trigger.MANUAL)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.QUEUED, db_index=True)
    task_id = models.CharField(max_length=255, blank=True, db_index=True)
    website_url = models.URLField(blank=True)
    max_pages = models.PositiveSmallIntegerField(default=25)
    pages_crawled = models.PositiveIntegerField(default=0)
    documents_indexed = models.PositiveIntegerField(default=0)
    chunks_indexed = models.PositiveIntegerField(default=0)
    services_collected = models.PositiveIntegerField(default=0)
    facts_collected = models.PositiveIntegerField(default=0)
    review_items_created = models.PositiveIntegerField(default=0)
    practitioners_collected = models.PositiveIntegerField(default=0)
    specialties_collected = models.PositiveIntegerField(default=0)
    social_links_collected = models.PositiveIntegerField(default=0)
    readiness_before = models.PositiveSmallIntegerField(default=0)
    readiness_after = models.PositiveSmallIntegerField(default=0)
    summary = models.JSONField(default=dict, blank=True)
    warnings = models.JSONField(default=list, blank=True)
    error_code = models.CharField(max_length=80, blank=True)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("organization", "status")),
            models.Index(fields=("status", "created_at")),
        ]

    def __str__(self):
        return f"{self.organization.name} — {self.get_status_display()}"


class IntelligenceReviewItem(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending review"
        APPLIED = "applied", "Applied"
        REJECTED = "rejected", "Rejected"

    class ItemType(models.TextChoices):
        PROFILE = "profile", "Organization profile"
        CONTACT = "contact", "Public contact"
        SOCIAL = "social", "Social media"
        LOCATION = "location", "Location"
        SERVICE = "service", "Service offering"
        HEALTHCARE = "healthcare", "Healthcare information"
        PROPERTY = "property", "Property information"
        HOSPITALITY = "hospitality", "Hospitality information"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="intelligence_review_items",
    )
    run = models.ForeignKey(
        OrganizationIntelligenceRun,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="review_items",
    )
    place = models.ForeignKey(
        "places.Place",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="intelligence_review_items",
    )
    item_type = models.CharField(max_length=24, choices=ItemType.choices, default=ItemType.OTHER, db_index=True)
    target_model = models.CharField(max_length=80)
    target_field = models.CharField(max_length=120, blank=True)
    entity_key = models.CharField(max_length=255, blank=True)
    label = models.CharField(max_length=255)
    current_value = models.JSONField(default=dict, blank=True)
    proposed_value = models.JSONField(default=dict, blank=True)
    source_url = models.URLField()
    confidence = models.DecimalField(
        max_digits=4,
        decimal_places=3,
        default=Decimal("0.750"),
        validators=[MinValueValidator(0), MaxValueValidator(1)],
    )
    reason = models.TextField(blank=True)
    is_public_safe = models.BooleanField(default=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PENDING, db_index=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_intelligence_items",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("organization", "status")),
            models.Index(fields=("target_model", "target_field")),
        ]

    def __str__(self):
        return f"{self.organization.name} — {self.label}"

