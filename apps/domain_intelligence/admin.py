from django.contrib import admin

from .models import (
    DiscoverySearchLog,
    HealthcareFacilityProfile,
    HospitalityProfile,
    MedicalPractitioner,
    MedicalSpecialty,
    OrganizationIntelligenceProfile,
    PractitionerAvailability,
    PropertyListingProfile,
    VerifiedSourceFact,
)


@admin.register(OrganizationIntelligenceProfile)
class OrganizationIntelligenceProfileAdmin(admin.ModelAdmin):
    list_display = ("organization", "domain_kind", "auto_sync_website", "last_sync_status", "last_synced_at")
    list_filter = ("domain_kind", "auto_sync_website", "last_sync_status")
    search_fields = ("organization__name", "organization__slug")


@admin.register(HealthcareFacilityProfile)
class HealthcareFacilityProfileAdmin(admin.ModelAdmin):
    list_display = ("place", "appointment_phone", "appointment_email", "telemedicine_available", "verified_at")
    search_fields = ("place__name", "place__organization__name")


@admin.register(MedicalSpecialty)
class MedicalSpecialtyAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "is_active", "verified_at")
    list_filter = ("is_active",)
    search_fields = ("name", "organization__name")


class PractitionerAvailabilityInline(admin.TabularInline):
    model = PractitionerAvailability
    extra = 0


@admin.register(MedicalPractitioner)
class MedicalPractitionerAdmin(admin.ModelAdmin):
    list_display = ("full_name", "organization", "specialty", "booking_mode", "is_active", "verified_at")
    list_filter = ("booking_mode", "is_active")
    search_fields = ("full_name", "professional_title", "specialty__name", "organization__name")
    inlines = (PractitionerAvailabilityInline,)


@admin.register(PropertyListingProfile)
class PropertyListingProfileAdmin(admin.ModelAdmin):
    list_display = ("place", "listing_type", "property_type", "bedrooms", "bathrooms", "price", "currency", "availability_status")
    list_filter = ("listing_type", "property_type", "availability_status", "furnished", "pet_friendly")
    search_fields = ("place__name", "place__city", "place__address_line")


@admin.register(HospitalityProfile)
class HospitalityProfileAdmin(admin.ModelAdmin):
    list_display = ("place", "star_rating", "price_from", "currency", "is_available", "verified_at")
    list_filter = ("is_available",)
    search_fields = ("place__name", "place__city")


@admin.register(VerifiedSourceFact)
class VerifiedSourceFactAdmin(admin.ModelAdmin):
    list_display = ("organization", "entity_type", "entity_key", "field_name", "confidence", "verified_at", "is_public")
    list_filter = ("entity_type", "field_name", "is_public")
    search_fields = ("organization__name", "entity_key", "source_url")


@admin.register(DiscoverySearchLog)
class DiscoverySearchLogAdmin(admin.ModelAdmin):
    list_display = ("query", "result_count", "session_key", "created_at")
    readonly_fields = ("query", "normalized_intent", "result_count", "session_key", "selected_tour", "metadata", "created_at", "updated_at")
