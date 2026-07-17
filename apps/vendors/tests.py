from decimal import Decimal
from django.test import TestCase
from apps.organizations.models import Organization
from .models import Product, VendorProfile


class VendorModelsTest(TestCase):
    def test_vendor_and_product_creation(self):
        organization = Organization.objects.create(name="Demo Vendor", slug="demo-vendor")
        profile = VendorProfile.objects.create(organization=organization)
        product = Product.objects.create(
            organization=organization, name="Demo product", slug="demo-product",
            price=Decimal("25.00"), status=Product.Status.ACTIVE,
        )
        self.assertEqual(str(profile), "Demo Vendor")
        self.assertTrue(product.in_stock is False)


from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from apps.organizations.models import Organization
from .models import CommerceCurrency, DeliveryZone, IntelligentAgent, ProductCategory


class VendorDefaultsTests(TestCase):
    def test_seed_product_categories_is_idempotent(self):
        call_command("seed_product_categories")
        first_count = ProductCategory.objects.count()
        call_command("seed_product_categories")
        self.assertEqual(ProductCategory.objects.count(), first_count)
        self.assertGreater(first_count, 5)

    def test_currency_contains_south_african_rand(self):
        self.assertIn((CommerceCurrency.ZAR, "South African Rand (R)"), CommerceCurrency.choices)
