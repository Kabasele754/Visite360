from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError

from apps.organizations.models import Organization
from apps.vendors.models import CommerceCurrency, DeliveryZone, VendorProfile


SOUTH_AFRICA_ZONES = [
    {
        "name": "Johannesburg Metro",
        "province": "Gauteng",
        "cities": ["Johannesburg", "Sandton", "Randburg", "Roodepoort", "Soweto", "Midrand"],
        "fee": Decimal("95.00"),
        "free_delivery_threshold": Decimal("1500.00"),
        "estimated_days_min": 1,
        "estimated_days_max": 2,
        "is_default": True,
    },
    {
        "name": "Pretoria / Tshwane",
        "province": "Gauteng",
        "cities": ["Pretoria", "Centurion", "Akasia", "Mamelodi"],
        "fee": Decimal("110.00"),
        "free_delivery_threshold": Decimal("1800.00"),
        "estimated_days_min": 1,
        "estimated_days_max": 3,
    },
    {
        "name": "Cape Town Metro",
        "province": "Western Cape",
        "cities": ["Cape Town", "Bellville", "Stellenbosch", "Somerset West"],
        "fee": Decimal("145.00"),
        "free_delivery_threshold": Decimal("2200.00"),
        "estimated_days_min": 2,
        "estimated_days_max": 4,
    },
    {
        "name": "Durban / eThekwini",
        "province": "KwaZulu-Natal",
        "cities": ["Durban", "Umhlanga", "Pinetown", "Amanzimtoti"],
        "fee": Decimal("135.00"),
        "free_delivery_threshold": Decimal("2200.00"),
        "estimated_days_min": 2,
        "estimated_days_max": 4,
    },
    {
        "name": "South Africa National",
        "province": "Nationwide",
        "cities": [],
        "fee": Decimal("195.00"),
        "free_delivery_threshold": Decimal("3000.00"),
        "estimated_days_min": 3,
        "estimated_days_max": 7,
    },
]


class Command(BaseCommand):
    help = "Seed South African delivery zones for one organization or all vendor organizations."

    def add_arguments(self, parser):
        parser.add_argument("--organization", dest="organization_slug")
        parser.add_argument("--all", action="store_true", dest="all_organizations")

    def handle(self, *args, **options):
        slug = options.get("organization_slug")
        if slug:
            organizations = Organization.objects.filter(slug=slug)
            if not organizations.exists():
                raise CommandError(f"Organization '{slug}' was not found.")
        elif options.get("all_organizations"):
            organizations = Organization.objects.filter(vendor_profile__isnull=False)
        else:
            raise CommandError("Use --organization=<slug> or --all.")

        for organization in organizations:
            profile, _ = VendorProfile.objects.get_or_create(organization=organization)
            if not profile.currency:
                profile.currency = CommerceCurrency.ZAR
                profile.save(update_fields=["currency", "updated_at"])

            created_count = 0
            for zone in SOUTH_AFRICA_ZONES:
                _, created = DeliveryZone.objects.update_or_create(
                    organization=organization,
                    name=zone["name"],
                    country_code="ZA",
                    defaults={
                        **zone,
                        "country_code": "ZA",
                        "currency": CommerceCurrency.ZAR,
                        "postal_codes": [],
                        "is_active": True,
                    },
                )
                created_count += int(created)

            self.stdout.write(self.style.SUCCESS(
                f"{organization.name}: South Africa zones ready ({created_count} created)."
            ))
