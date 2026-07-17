from django.core.management.base import BaseCommand

from apps.vendors.models import ProductCategory


DEFAULT_CATEGORIES = [
    ("Medical equipment", "medical-equipment", "Healthcare equipment, devices and supplies.", "medical"),
    ("Furniture", "furniture", "Home, office and hospitality furniture.", "chair"),
    ("Fashion", "fashion", "Clothing, footwear and fashion accessories.", "fashion"),
    ("Electronics", "electronics", "Electronics, devices and accessories.", "devices"),
    ("Home & decor", "home-decor", "Interior decoration and home products.", "home"),
    ("Beauty & wellness", "beauty-wellness", "Beauty, personal care and wellness products.", "wellness"),
    ("Food & beverage", "food-beverage", "Prepared food, ingredients and beverages.", "food"),
    ("Automotive accessories", "automotive-accessories", "Vehicle accessories and approved parts.", "car"),
    ("Professional services", "professional-services", "Bookable professional and business services.", "briefcase"),
    ("Events & wedding", "events-wedding", "Event, wedding and celebration products.", "events"),
    ("Construction & hardware", "construction-hardware", "Building supplies, tools and hardware.", "tools"),
    ("Other", "other", "Products that do not fit another category.", "grid"),
]


class Command(BaseCommand):
    help = "Create or update the default Twinscopes product categories."

    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0
        for name, slug, description, icon in DEFAULT_CATEGORIES:
            category, created = ProductCategory.objects.update_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "description": description,
                    "icon": icon,
                    "is_active": True,
                },
            )
            created_count += int(created)
            updated_count += int(not created)
        self.stdout.write(self.style.SUCCESS(
            f"Product categories ready: {created_count} created, {updated_count} updated."
        ))
