from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.domain_intelligence.models import (
    HealthcareFacilityProfile,
    HospitalityProfile,
    OrganizationIntelligenceProfile,
    PropertyListingProfile,
)
from apps.domain_intelligence.signals import (
    HEALTHCARE_CATEGORIES,
    HOSPITALITY_CATEGORIES,
    REAL_ESTATE_CATEGORIES,
)
from apps.domain_intelligence.tasks import sync_domain_intelligence
from apps.organizations.models import Organization
from apps.places.models import Place
from apps.tours.models import Tour


class Command(BaseCommand):
    help = "Create domain profiles for existing places and tours without deleting or duplicating tour data."

    def add_arguments(self, parser):
        parser.add_argument("--organization", help="Optional organization slug or numeric ID")
        parser.add_argument("--queue-healthcare-sync", action="store_true")
        parser.add_argument("--max-pages", type=int, default=20)

    def handle(self, *args, **options):
        organizations = Organization.objects.all().order_by("id")
        lookup = str(options.get("organization") or "").strip()
        if lookup:
            organizations = (
                organizations.filter(pk=int(lookup))
                if lookup.isdigit()
                else organizations.filter(slug=lookup)
            )
            if not organizations.exists():
                raise CommandError("Organization not found")

        counters = {
            "organizations": 0,
            "property_profiles": 0,
            "hospitality_profiles": 0,
            "healthcare_profiles": 0,
            "healthcare_sync_tasks": 0,
        }
        for organization in organizations.iterator():
            with transaction.atomic():
                places = list(Place.objects.filter(organization=organization).order_by("id"))
                kinds = set()
                for place in places:
                    latest_tour = (
                        Tour.objects.filter(place=place)
                        .order_by("-published_at", "-updated_at", "-id")
                        .first()
                    )
                    if place.category in REAL_ESTATE_CATEGORIES:
                        kinds.add(OrganizationIntelligenceProfile.DomainKind.REAL_ESTATE)
                        type_map = {
                            Place.Category.HOUSE: PropertyListingProfile.PropertyType.HOUSE,
                            Place.Category.APARTMENT: PropertyListingProfile.PropertyType.APARTMENT,
                            Place.Category.VILLA: PropertyListingProfile.PropertyType.VILLA,
                            Place.Category.STUDIO: PropertyListingProfile.PropertyType.STUDIO,
                            Place.Category.OFFICE: PropertyListingProfile.PropertyType.OFFICE,
                            Place.Category.BUILDING: PropertyListingProfile.PropertyType.BUILDING,
                            Place.Category.LAND: PropertyListingProfile.PropertyType.LAND,
                        }
                        amenities = []
                        if latest_tour:
                            amenities = [
                                name for enabled, name in (
                                    (latest_tour.parking, "parking"),
                                    (latest_tour.balcon, "balcony"),
                                    (latest_tour.ascenseur, "elevator"),
                                ) if enabled
                            ]
                        _, created = PropertyListingProfile.objects.get_or_create(
                            place=place,
                            defaults={
                                "property_type": type_map.get(place.category, PropertyListingProfile.PropertyType.OTHER),
                                "bedrooms": max(0, (latest_tour.chambres if latest_tour else 0) or 0),
                                "price": latest_tour.price if latest_tour else None,
                                "parking_spaces": int(bool(latest_tour and latest_tour.parking)),
                                "amenities": amenities,
                            },
                        )
                        counters["property_profiles"] += int(created)
                    elif place.category in HOSPITALITY_CATEGORIES:
                        kinds.add(OrganizationIntelligenceProfile.DomainKind.HOSPITALITY)
                        _, created = HospitalityProfile.objects.get_or_create(
                            place=place,
                            defaults={
                                "price_from": latest_tour.price if latest_tour else None,
                                "booking_url": organization.booking_url,
                                "is_available": True,
                            },
                        )
                        counters["hospitality_profiles"] += int(created)
                    elif place.category in HEALTHCARE_CATEGORIES:
                        kinds.add(OrganizationIntelligenceProfile.DomainKind.HEALTHCARE)
                        _, created = HealthcareFacilityProfile.objects.get_or_create(
                            place=place,
                            defaults={
                                "appointment_phone": organization.public_phone,
                                "appointment_email": organization.public_email,
                                "appointment_url": organization.booking_url,
                                "source_url": organization.website_url,
                                "is_active": True,
                            },
                        )
                        counters["healthcare_profiles"] += int(created)

                if len(kinds) > 1:
                    domain_kind = OrganizationIntelligenceProfile.DomainKind.MIXED
                elif kinds:
                    domain_kind = next(iter(kinds))
                else:
                    domain_kind = OrganizationIntelligenceProfile.DomainKind.GENERAL
                OrganizationIntelligenceProfile.objects.update_or_create(
                    organization=organization,
                    defaults={"domain_kind": domain_kind},
                )
                counters["organizations"] += 1

            if (
                options.get("queue_healthcare_sync")
                and organization.website_url
                and OrganizationIntelligenceProfile.objects.filter(
                    organization=organization,
                    domain_kind__in=(
                        OrganizationIntelligenceProfile.DomainKind.HEALTHCARE,
                        OrganizationIntelligenceProfile.DomainKind.MIXED,
                    ),
                ).exists()
            ):
                sync_domain_intelligence.delay(organization.id, max_pages=options["max_pages"])
                counters["healthcare_sync_tasks"] += 1

        self.stdout.write(self.style.SUCCESS("Existing domain profiles are ready."))
        for key, value in counters.items():
            self.stdout.write(f"{key}: {value}")
