from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

# This command must be placed inside the same Django application
# that contains Product and ProductCategory.
from ...models import Product, ProductCategory


CATEGORIES = [
    {
        "name": "360 Cameras",
        "slug": "360-cameras",
        "description": "Professional cameras for immersive photography and virtual tours.",
    },
    {
        "name": "Supports and Tripods",
        "slug": "supports-tripods",
        "description": "Tripods, invisible selfie sticks and camera mounting accessories.",
    },
    {
        "name": "Professional Kits",
        "slug": "professional-kits",
        "description": "Complete equipment bundles for virtual-tour professionals.",
    },
    {
        "name": "Protection and Care",
        "slug": "protection-care",
        "description": "Protective cases, lens guards and maintenance accessories.",
    },
    {
        "name": "Storage",
        "slug": "storage",
        "description": "Memory cards and storage accessories for high-resolution content.",
    },
    {
        "name": "Power and Batteries",
        "slug": "power-batteries",
        "description": "Batteries, chargers and portable power solutions.",
    },
    {
        "name": "Lighting",
        "slug": "lighting",
        "description": "Portable lighting equipment for indoor photography and video.",
    },
    {
        "name": "Audio",
        "slug": "audio",
        "description": "Microphones and audio equipment for content creators.",
    },
]


PRODUCTS = [
    {
        "category_slug": "360-cameras",
        "name": "Insta360 X4 8K 360 Camera",
        "slug": "insta360-x4-8k-360-camera",
        "sku": "CAM-X4-360-001",
        "short_description": (
            "High-resolution 360 camera designed for virtual tours, events "
            "and immersive content creation."
        ),
        "description": (
            "The Insta360 X4 is a versatile 360 camera suitable for content "
            "creators, virtual-tour photographers, event agencies and property "
            "professionals. Its compact body makes it easy to capture immersive "
            "content indoors and outdoors. It can be combined with an invisible "
            "selfie stick to create dynamic floating-camera effects."
        ),
        "specifications": {
            "product_type": "360 camera",
            "video_resolution": "Up to 8K",
            "photo_mode": "360-degree panoramic photography",
            "stabilization": "Electronic image stabilization",
            "display": "Touchscreen display",
            "connectivity": [
                "Wi-Fi",
                "Bluetooth",
                "USB-C",
            ],
            "recommended_uses": [
                "Virtual tours",
                "Events",
                "Real estate",
                "Tourism",
                "Social media content",
            ],
            "color": "Black",
        },
        "price": Decimal("599.00"),
        "compare_at_price": Decimal("649.00"),
        "currency": "USD",
        "stock_quantity": 8,
        "track_inventory": True,
        "delivery_available": True,
        "pickup_available": True,
        "estimated_delivery_days": 2,
        "status": "active",
        "is_featured": True,
    },
    {
        "category_slug": "360-cameras",
        "name": "Ricoh Theta Z1 Professional 360 Camera",
        "slug": "ricoh-theta-z1-professional-360-camera",
        "sku": "CAM-THETA-Z1-002",
        "short_description": (
            "Professional panoramic camera for real-estate virtual tours "
            "and commercial projects."
        ),
        "description": (
            "The Ricoh Theta Z1 is designed for professionals who need detailed "
            "panoramic images for real estate, hotels, restaurants, event halls, "
            "retail stores and architectural projects. Its compact format makes "
            "it convenient for photographers working across multiple locations."
        ),
        "specifications": {
            "product_type": "Professional panoramic camera",
            "capture_modes": [
                "360-degree photography",
                "360-degree video",
            ],
            "output_format": "Equirectangular panorama",
            "display": "Built-in information display",
            "connectivity": [
                "Wi-Fi",
                "Bluetooth",
                "USB",
            ],
            "recommended_uses": [
                "Google Street View",
                "Real estate",
                "Hospitality",
                "Architecture",
                "Commercial virtual tours",
            ],
            "color": "Black",
        },
        "price": Decimal("949.00"),
        "compare_at_price": Decimal("1049.00"),
        "currency": "USD",
        "stock_quantity": 4,
        "track_inventory": True,
        "delivery_available": True,
        "pickup_available": True,
        "estimated_delivery_days": 3,
        "status": "active",
        "is_featured": True,
    },
    {
        "category_slug": "supports-tripods",
        "name": "Insta360 Invisible Selfie Stick",
        "slug": "insta360-invisible-selfie-stick",
        "sku": "SUP-INVISIBLE-003",
        "short_description": (
            "Telescopic selfie stick designed to disappear automatically "
            "from compatible 360 photos and videos."
        ),
        "description": (
            "The invisible selfie stick creates the impression that the camera "
            "is floating in the air. It is ideal for immersive videos, virtual "
            "tours, travel content, events and social-media productions."
        ),
        "specifications": {
            "product_type": "Telescopic selfie stick",
            "main_feature": "Invisible-stick effect in 360 footage",
            "material": "Lightweight alloy",
            "handle": "Anti-slip grip",
            "mount": "Standard camera screw",
            "color": "Black",
        },
        "price": Decimal("39.00"),
        "compare_at_price": Decimal("49.00"),
        "currency": "USD",
        "stock_quantity": 25,
        "track_inventory": True,
        "delivery_available": True,
        "pickup_available": True,
        "estimated_delivery_days": 1,
        "status": "active",
        "is_featured": False,
    },
    {
        "category_slug": "supports-tripods",
        "name": "Flexible Mini Tripod for 360 Cameras",
        "slug": "flexible-mini-tripod-for-360-cameras",
        "sku": "SUP-TRIPOD-004",
        "short_description": (
            "Compact flexible tripod for stabilizing a 360 camera "
            "on tables, floors and uneven surfaces."
        ),
        "description": (
            "This flexible mini tripod is a portable support solution for "
            "photographers and video creators. Its adjustable legs allow it "
            "to stand on different surfaces or wrap around compatible objects."
        ),
        "specifications": {
            "product_type": "Flexible mini tripod",
            "legs": "Flexible and anti-slip",
            "mount": "Standard camera screw",
            "head": "Adjustable ball head",
            "recommended_uses": [
                "Tabletop photography",
                "Virtual tours",
                "Outdoor photography",
                "Content creation",
            ],
            "color": "Black",
        },
        "price": Decimal("28.00"),
        "compare_at_price": None,
        "currency": "USD",
        "stock_quantity": 18,
        "track_inventory": True,
        "delivery_available": True,
        "pickup_available": True,
        "estimated_delivery_days": 1,
        "status": "active",
        "is_featured": False,
    },
    {
        "category_slug": "professional-kits",
        "name": "Ricoh Theta Z1 Virtual Tour Creator Kit",
        "slug": "ricoh-theta-z1-virtual-tour-creator-kit",
        "sku": "KIT-THETA-CREATOR-005",
        "short_description": (
            "Professional bundle including a Ricoh Theta Z1, mini tripod "
            "and protective carrying case."
        ),
        "description": (
            "The Ricoh Theta Z1 Virtual Tour Creator Kit contains the essential "
            "equipment needed to start producing professional virtual tours. "
            "It is suitable for photographers, property agencies, hotels, "
            "restaurants, event venues and retail businesses."
        ),
        "specifications": {
            "package_contents": [
                "Ricoh Theta Z1 camera",
                "Flexible mini tripod",
                "Protective carrying case",
                "Charging cable",
            ],
            "skill_level": "Professional",
            "recommended_uses": [
                "Virtual tours",
                "Google Street View",
                "Real estate",
                "Hospitality",
                "Retail businesses",
            ],
            "sample_warranty": "12 months",
        },
        "price": Decimal("999.00"),
        "compare_at_price": Decimal("1099.00"),
        "currency": "USD",
        "stock_quantity": 3,
        "track_inventory": True,
        "delivery_available": True,
        "pickup_available": True,
        "estimated_delivery_days": 3,
        "status": "active",
        "is_featured": True,
    },
    {
        "category_slug": "professional-kits",
        "name": "Insta360 X4 Adventure Creator Kit",
        "slug": "insta360-x4-adventure-creator-kit",
        "sku": "KIT-X4-ADV-006",
        "short_description": (
            "Complete bundle with an Insta360 X4 camera, invisible selfie stick, "
            "extra battery and protective case."
        ),
        "description": (
            "The Insta360 X4 Adventure Creator Kit brings together the equipment "
            "required to produce immersive travel videos, event content, virtual "
            "tours and professional social-media productions."
        ),
        "specifications": {
            "package_contents": [
                "Insta360 X4 camera",
                "Invisible selfie stick",
                "Extra battery",
                "Protective hard case",
                "USB-C charging cable",
            ],
            "skill_level": "Creator and professional",
            "recommended_uses": [
                "Travel",
                "Events",
                "Tourism",
                "Outdoor activities",
                "Social media",
            ],
        },
        "price": Decimal("699.00"),
        "compare_at_price": Decimal("759.00"),
        "currency": "USD",
        "stock_quantity": 6,
        "track_inventory": True,
        "delivery_available": True,
        "pickup_available": True,
        "estimated_delivery_days": 2,
        "status": "active",
        "is_featured": True,
    },
    {
        "category_slug": "protection-care",
        "name": "360 Camera Lens Guards",
        "slug": "360-camera-lens-guards",
        "sku": "PRO-LENS-007",
        "short_description": (
            "Transparent lens guards that help protect exposed 360 camera "
            "lenses against scratches, dust and minor impacts."
        ),
        "description": (
            "These removable lens guards help reduce the risk of damaging "
            "the exposed lenses of a 360 camera. They are especially useful "
            "during travel, outdoor filming and daily equipment transportation."
        ),
        "specifications": {
            "product_type": "Lens protection",
            "material": "Transparent protective polymer",
            "protection_against": [
                "Scratches",
                "Dust",
                "Minor impacts",
            ],
            "installation": "Removable",
            "package_quantity": "One pair",
        },
        "price": Decimal("24.00"),
        "compare_at_price": Decimal("29.00"),
        "currency": "USD",
        "stock_quantity": 30,
        "track_inventory": True,
        "delivery_available": True,
        "pickup_available": True,
        "estimated_delivery_days": 1,
        "status": "active",
        "is_featured": False,
    },
    {
        "category_slug": "storage",
        "name": "256 GB High-Speed MicroSD Card",
        "slug": "256-gb-high-speed-microsd-card",
        "sku": "STO-SD256-008",
        "short_description": (
            "High-capacity memory card suitable for high-resolution "
            "360-degree video recording."
        ),
        "description": (
            "This high-speed microSD card provides useful storage capacity "
            "for panoramic photography, 360 videos and long recording sessions. "
            "It is suitable for creators who need reliable portable storage."
        ),
        "specifications": {
            "product_type": "MicroSD memory card",
            "capacity": "256 GB",
            "recommended_use": "High-resolution photo and video",
            "adapter": "Included",
            "compatibility": "Must be verified against the selected camera",
        },
        "price": Decimal("44.00"),
        "compare_at_price": Decimal("52.00"),
        "currency": "USD",
        "stock_quantity": 20,
        "track_inventory": True,
        "delivery_available": True,
        "pickup_available": True,
        "estimated_delivery_days": 1,
        "status": "active",
        "is_featured": False,
    },
    {
        "category_slug": "power-batteries",
        "name": "Rechargeable Battery for 360 Camera",
        "slug": "rechargeable-battery-for-360-camera",
        "sku": "PWR-BAT360-009",
        "short_description": (
            "Replacement rechargeable battery for longer photography "
            "and video recording sessions."
        ),
        "description": (
            "An additional battery is recommended for long virtual-tour "
            "sessions, events and outdoor assignments where immediate access "
            "to electrical power may not be available."
        ),
        "specifications": {
            "product_type": "Rechargeable battery",
            "recommended_use": "360 camera",
            "charging": "Compatible charger required",
            "protection": "Overcharge protection",
            "compatibility": "Depends on the selected camera model",
        },
        "price": Decimal("49.00"),
        "compare_at_price": None,
        "currency": "USD",
        "stock_quantity": 15,
        "track_inventory": True,
        "delivery_available": True,
        "pickup_available": True,
        "estimated_delivery_days": 2,
        "status": "active",
        "is_featured": False,
    },
    {
        "category_slug": "lighting",
        "name": "Portable LED Light for Virtual Tours",
        "slug": "portable-led-light-for-virtual-tours",
        "sku": "LGT-LED-010",
        "short_description": (
            "Compact adjustable LED light for improving indoor photography "
            "and virtual-tour image quality."
        ),
        "description": (
            "This portable LED light helps improve image quality in dark rooms, "
            "shops, restaurants and event venues. It can also be used for "
            "interviews, product presentations and mobile content creation."
        ),
        "specifications": {
            "product_type": "Portable LED light",
            "brightness": "Adjustable",
            "color_temperature": "Adjustable",
            "power_source": "Rechargeable battery",
            "mount": "Standard accessory mount",
            "recommended_uses": [
                "Virtual tours",
                "Indoor photography",
                "Interviews",
                "Product photography",
            ],
        },
        "price": Decimal("69.00"),
        "compare_at_price": Decimal("79.00"),
        "currency": "USD",
        "stock_quantity": 10,
        "track_inventory": True,
        "delivery_available": True,
        "pickup_available": True,
        "estimated_delivery_days": 2,
        "status": "active",
        "is_featured": False,
    },
    {
        "category_slug": "audio",
        "name": "Wireless Microphone for Content Creators",
        "slug": "wireless-microphone-for-content-creators",
        "sku": "AUD-WMIC-011",
        "short_description": (
            "Compact wireless microphone for interviews, presentations "
            "and social-media videos."
        ),
        "description": (
            "This wireless microphone helps creators record clearer speech "
            "during interviews, guided tours, events and property presentations. "
            "It can be used with compatible smartphones, cameras and computers."
        ),
        "specifications": {
            "product_type": "Wireless lavalier microphone",
            "connections": [
                "USB-C",
                "Device-dependent adapter",
            ],
            "range": "Short to medium distance",
            "recommended_uses": [
                "Interviews",
                "Presentations",
                "Social media",
                "Guided tours",
            ],
            "rechargeable": True,
        },
        "price": Decimal("89.00"),
        "compare_at_price": Decimal("109.00"),
        "currency": "USD",
        "stock_quantity": 11,
        "track_inventory": True,
        "delivery_available": True,
        "pickup_available": True,
        "estimated_delivery_days": 2,
        "status": "active",
        "is_featured": False,
    },
    {
        "category_slug": "protection-care",
        "name": "Hard Carrying Case for 360 Camera Equipment",
        "slug": "hard-carrying-case-for-360-camera-equipment",
        "sku": "PRO-CASE-012",
        "short_description": (
            "Protective carrying case with compartments for a camera, batteries, "
            "memory cards, cables and accessories."
        ),
        "description": (
            "This hard carrying case protects professional camera equipment "
            "during transport. Its adjustable compartments can hold a 360 camera, "
            "batteries, cables, memory cards and other small accessories."
        ),
        "specifications": {
            "product_type": "Protective carrying case",
            "protection_against": [
                "Impacts",
                "Dust",
                "Scratches",
            ],
            "interior": "Adjustable compartments",
            "closure": "Secure locking system",
            "color": "Black",
        },
        "price": Decimal("59.00"),
        "compare_at_price": Decimal("69.00"),
        "currency": "USD",
        "stock_quantity": 9,
        "track_inventory": True,
        "delivery_available": True,
        "pickup_available": True,
        "estimated_delivery_days": 2,
        "status": "active",
        "is_featured": False,
    },
]


class Command(BaseCommand):
    help = (
        "Seeds sample 360-camera products, accessories, categories "
        "and professional equipment kits."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--organization-id",
            type=int,
            help=(
                "ID of the organization that will own the products. "
                "When omitted, the first organization is used."
            ),
        )

    @transaction.atomic
    def handle(self, *args, **options):
        organization_model = Product._meta.get_field(
            "organization"
        ).remote_field.model

        organization_id = options.get("organization_id")

        if organization_id:
            organization = organization_model.objects.filter(
                pk=organization_id
            ).first()

            if organization is None:
                raise CommandError(
                    f"Organization with ID {organization_id} was not found."
                )
        else:
            organization = organization_model.objects.order_by("pk").first()

            if organization is None:
                raise CommandError(
                    "No organization was found. Create an organization first "
                    "or provide a valid --organization-id."
                )

        self.stdout.write(
            self.style.NOTICE(
                f"Seeding products for organization: {organization}"
            )
        )

        categories = self._seed_categories(organization)

        created_count = 0
        updated_count = 0

        for product_data in PRODUCTS:
            data = product_data.copy()

            category_slug = data.pop("category_slug")
            sku = data.pop("sku")

            data["category"] = categories.get(category_slug)

            product, created = Product.objects.update_or_create(
                organization=organization,
                sku=sku,
                defaults=data,
            )

            if created:
                created_count += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created product: {product.name}"
                    )
                )
            else:
                updated_count += 1

                self.stdout.write(
                    self.style.WARNING(
                        f"Updated product: {product.name}"
                    )
                )

        self.stdout.write("")

        self.stdout.write(
            self.style.SUCCESS(
                "Product seeding completed successfully."
            )
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Created: {created_count} | Updated: {updated_count}"
            )
        )

    def _seed_categories(self, organization):
        category_fields = {
            field.name
            for field in ProductCategory._meta.concrete_fields
        }

        categories = {}

        for category_data in CATEGORIES:
            lookup = {}
            defaults = {}

            if "organization" in category_fields:
                lookup["organization"] = organization

            if "slug" in category_fields:
                lookup["slug"] = category_data["slug"]
            elif "name" in category_fields:
                lookup["name"] = category_data["name"]
            else:
                raise CommandError(
                    "ProductCategory must contain either a slug or name field."
                )

            if "name" in category_fields and "name" not in lookup:
                defaults["name"] = category_data["name"]

            if "slug" in category_fields and "slug" not in lookup:
                defaults["slug"] = category_data["slug"]

            if "description" in category_fields:
                defaults["description"] = category_data["description"]

            if "is_active" in category_fields:
                defaults["is_active"] = True

            category, created = ProductCategory.objects.update_or_create(
                **lookup,
                defaults=defaults,
            )

            categories[category_data["slug"]] = category

            action = "Created" if created else "Updated"

            self.stdout.write(
                f"{action} category: {category_data['name']}"
            )

        return categories