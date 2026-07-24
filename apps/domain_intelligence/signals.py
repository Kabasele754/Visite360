from __future__ import annotations

from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.organizations.models import Organization
from apps.places.models import Place
from apps.tours.models import Tour

from .models import (
    HealthcareFacilityProfile,
    HospitalityProfile,
    OrganizationIntelligenceProfile,
    PropertyListingProfile,
)

REAL_ESTATE_CATEGORIES = {
    Place.Category.HOUSE,
    Place.Category.APARTMENT,
    Place.Category.VILLA,
    Place.Category.STUDIO,
    Place.Category.OFFICE,
    Place.Category.BUILDING,
    Place.Category.LAND,
    Place.Category.REAL_ESTATE,
}
HEALTHCARE_CATEGORIES = {
    Place.Category.HOSPITAL,
    Place.Category.CLINIC,
    Place.Category.DENTAL_CLINIC,
    Place.Category.PHARMACY,
}
HOSPITALITY_CATEGORIES = {
    Place.Category.HOTEL,
    Place.Category.RESORT,
    Place.Category.GUEST_HOUSE,
    Place.Category.LODGE,
}

def _refresh_organization_domain_kind(organization, profile):
    categories = set(organization.places.values_list("category", flat=True))
    kinds = set()
    if categories & REAL_ESTATE_CATEGORIES:
        kinds.add(OrganizationIntelligenceProfile.DomainKind.REAL_ESTATE)
    if categories & HEALTHCARE_CATEGORIES:
        kinds.add(OrganizationIntelligenceProfile.DomainKind.HEALTHCARE)
    if categories & HOSPITALITY_CATEGORIES:
        kinds.add(OrganizationIntelligenceProfile.DomainKind.HOSPITALITY)
    if len(kinds) > 1:
        value = OrganizationIntelligenceProfile.DomainKind.MIXED
    elif kinds:
        value = next(iter(kinds))
    else:
        value = OrganizationIntelligenceProfile.DomainKind.GENERAL
    if profile.domain_kind != value:
        profile.domain_kind = value
        profile.save(update_fields=("domain_kind", "updated_at"))
    return value


@receiver(pre_save, sender=Organization)
def remember_organization_website(sender, instance: Organization, **kwargs):
    if not instance.pk:
        instance._previous_website_url = ""
        return
    instance._previous_website_url = (
        Organization.objects.filter(pk=instance.pk).values_list("website_url", flat=True).first() or ""
    )


@receiver(post_save, sender=Organization)
def queue_domain_sync_when_website_changes(sender, instance: Organization, created: bool, **kwargs):
    previous = getattr(instance, "_previous_website_url", "")
    current = (instance.website_url or "").strip()
    if not current or (not created and current == previous):
        return
    if not getattr(settings, "DOMAIN_INTELLIGENCE_AUTO_SYNC", True):
        return
    profile, _ = OrganizationIntelligenceProfile.objects.get_or_create(organization=instance)
    if not profile.auto_sync_website or profile.domain_kind not in {
        OrganizationIntelligenceProfile.DomainKind.HEALTHCARE,
        OrganizationIntelligenceProfile.DomainKind.MIXED,
    }:
        return
    from .tasks import sync_domain_intelligence
    transaction.on_commit(lambda: sync_domain_intelligence.delay(instance.id))


@receiver(post_save, sender=Place)
def ensure_place_domain_profile(sender, instance: Place, created: bool, **kwargs):
    organization_profile, _ = OrganizationIntelligenceProfile.objects.get_or_create(
        organization=instance.organization,
    )
    if instance.category in HEALTHCARE_CATEGORIES:
        HealthcareFacilityProfile.objects.get_or_create(place=instance)
        _refresh_organization_domain_kind(instance.organization, organization_profile)
        if (
            created
            and instance.organization.website_url
            and organization_profile.auto_sync_website
            and getattr(settings, "DOMAIN_INTELLIGENCE_AUTO_SYNC", True)
        ):
            from .tasks import sync_domain_intelligence
            transaction.on_commit(lambda: sync_domain_intelligence.delay(instance.organization_id))
    elif instance.category in REAL_ESTATE_CATEGORIES:
        type_map = {
            Place.Category.HOUSE: PropertyListingProfile.PropertyType.HOUSE,
            Place.Category.APARTMENT: PropertyListingProfile.PropertyType.APARTMENT,
            Place.Category.VILLA: PropertyListingProfile.PropertyType.VILLA,
            Place.Category.STUDIO: PropertyListingProfile.PropertyType.STUDIO,
            Place.Category.OFFICE: PropertyListingProfile.PropertyType.OFFICE,
            Place.Category.BUILDING: PropertyListingProfile.PropertyType.BUILDING,
            Place.Category.LAND: PropertyListingProfile.PropertyType.LAND,
        }
        PropertyListingProfile.objects.get_or_create(
            place=instance,
            defaults={"property_type": type_map.get(instance.category, PropertyListingProfile.PropertyType.OTHER)},
        )
        _refresh_organization_domain_kind(instance.organization, organization_profile)
    elif instance.category in HOSPITALITY_CATEGORIES:
        HospitalityProfile.objects.get_or_create(place=instance)
        _refresh_organization_domain_kind(instance.organization, organization_profile)
    else:
        _refresh_organization_domain_kind(instance.organization, organization_profile)


@receiver(post_save, sender=Tour)
def sync_legacy_tour_property_fields(sender, instance: Tour, **kwargs):
    if instance.place.category not in REAL_ESTATE_CATEGORIES:
        return
    profile, _ = PropertyListingProfile.objects.get_or_create(place=instance.place)
    changed = []
    if instance.chambres is not None and profile.bedrooms != max(0, instance.chambres):
        profile.bedrooms = max(0, instance.chambres)
        changed.append("bedrooms")
    if instance.price is not None and profile.price != instance.price:
        profile.price = instance.price
        changed.append("price")
    amenities = set(profile.amenities or [])
    for enabled, value in (
        (instance.parking, "parking"),
        (instance.balcon, "balcony"),
        (instance.ascenseur, "elevator"),
    ):
        if enabled:
            amenities.add(value)
    normalized = sorted(amenities)
    if normalized != (profile.amenities or []):
        profile.amenities = normalized
        changed.append("amenities")
    if changed:
        profile.save(update_fields=tuple(changed) + ("updated_at",))
