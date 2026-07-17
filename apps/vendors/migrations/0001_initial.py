# Generated for Twinscopes vendor commerce module.
from decimal import Decimal
import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("organizations", "0003_organization_logo"),
        ("places", "0002_alter_place_category"),
        ("tours", "0010_hotspot_door_and_advanced_display"),
    ]
    operations = [
        migrations.CreateModel(name="ProductCategory", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("name", models.CharField(max_length=120)), ("slug", models.SlugField(unique=True)),
            ("description", models.TextField(blank=True)), ("icon", models.CharField(blank=True, max_length=32)),
            ("is_active", models.BooleanField(default=True)),
        ], options={"ordering": ("name",), "verbose_name_plural": "Product categories"}),
        migrations.CreateModel(name="VendorProfile", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("display_name", models.CharField(blank=True, max_length=255)), ("description", models.TextField(blank=True)),
            ("phone", models.CharField(blank=True, max_length=40)), ("email", models.EmailField(blank=True, max_length=254)),
            ("whatsapp", models.CharField(blank=True, max_length=40)), ("website_url", models.URLField(blank=True)),
            ("currency", models.CharField(default="USD", max_length=8)), ("accepts_orders", models.BooleanField(default=True)),
            ("offers_delivery", models.BooleanField(default=True)), ("offers_pickup", models.BooleanField(default=True)),
            ("minimum_order", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
            ("is_verified", models.BooleanField(default=False)),
            ("organization", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="vendor_profile", to="organizations.organization")),
        ]),
        migrations.CreateModel(name="Product", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("name", models.CharField(max_length=255)), ("slug", models.SlugField(max_length=280)), ("sku", models.CharField(blank=True, max_length=80)),
            ("short_description", models.CharField(blank=True, max_length=320)), ("description", models.TextField(blank=True)),
            ("specifications", models.JSONField(blank=True, default=dict)), ("cover_image", models.ImageField(blank=True, null=True, upload_to="vendors/products")),
            ("price", models.DecimalField(decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal("0.00"))])),
            ("compare_at_price", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)), ("currency", models.CharField(default="USD", max_length=8)),
            ("stock_quantity", models.PositiveIntegerField(default=0)), ("track_inventory", models.BooleanField(default=True)),
            ("delivery_available", models.BooleanField(default=True)), ("pickup_available", models.BooleanField(default=True)),
            ("estimated_delivery_days", models.PositiveSmallIntegerField(default=2)),
            ("status", models.CharField(choices=[("draft", "Draft"), ("active", "Active"), ("out_of_stock", "Out of stock"), ("archived", "Archived")], default="draft", max_length=24)),
            ("is_featured", models.BooleanField(default=False)), ("view_count", models.PositiveIntegerField(default=0)), ("order_count", models.PositiveIntegerField(default=0)),
            ("category", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="products", to="vendors.productcategory")),
            ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="products", to="organizations.organization")),
        ], options={"ordering": ("-is_featured", "-created_at")}),
        migrations.AddConstraint(model_name="product", constraint=models.UniqueConstraint(fields=("organization", "slug"), name="unique_product_slug_per_org")),
        migrations.CreateModel(name="ProductImage", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("image", models.ImageField(upload_to="vendors/product-gallery")), ("alt_text", models.CharField(blank=True, max_length=180)), ("order", models.PositiveSmallIntegerField(default=0)),
            ("product", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="gallery", to="vendors.product")),
        ], options={"ordering": ("order", "id")}),
        migrations.CreateModel(name="DeliveryZone", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("name", models.CharField(max_length=180)), ("cities", models.JSONField(blank=True, default=list)), ("fee", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
            ("free_delivery_threshold", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)), ("estimated_days_min", models.PositiveSmallIntegerField(default=1)),
            ("estimated_days_max", models.PositiveSmallIntegerField(default=3)), ("is_active", models.BooleanField(default=True)),
            ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="delivery_zones", to="organizations.organization")),
        ]),
        migrations.CreateModel(name="Order", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("reference", models.CharField(editable=False, max_length=24, unique=True)), ("customer_name", models.CharField(max_length=255)), ("customer_email", models.EmailField(blank=True, max_length=254)),
            ("customer_phone", models.CharField(max_length=40)), ("fulfillment", models.CharField(choices=[("delivery", "Delivery"), ("pickup", "Pickup")], default="delivery", max_length=20)),
            ("delivery_address", models.TextField(blank=True)), ("delivery_city", models.CharField(blank=True, max_length=120)), ("customer_notes", models.TextField(blank=True)),
            ("subtotal", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)), ("delivery_fee", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
            ("total", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)), ("currency", models.CharField(default="USD", max_length=8)),
            ("status", models.CharField(choices=[("pending", "Pending"), ("confirmed", "Confirmed"), ("preparing", "Preparing"), ("out_for_delivery", "Out for delivery"), ("delivered", "Delivered"), ("cancelled", "Cancelled")], default="pending", max_length=24)),
            ("payment_status", models.CharField(default="unpaid", max_length=24)),
            ("customer", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="vendor_orders", to=settings.AUTH_USER_MODEL)),
            ("delivery_zone", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="orders", to="vendors.deliveryzone")),
            ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="orders", to="organizations.organization")),
        ]),
        migrations.CreateModel(name="OrderItem", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("product_name", models.CharField(max_length=255)), ("quantity", models.PositiveIntegerField(default=1)), ("unit_price", models.DecimalField(decimal_places=2, max_digits=12)),
            ("line_total", models.DecimalField(decimal_places=2, max_digits=12)),
            ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="vendors.order")),
            ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="order_items", to="vendors.product")),
        ]),
        migrations.CreateModel(name="AppointmentType", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("name", models.CharField(max_length=180)), ("description", models.TextField(blank=True)), ("duration_minutes", models.PositiveSmallIntegerField(default=30)),
            ("price", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)), ("is_active", models.BooleanField(default=True)),
            ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="appointment_types", to="organizations.organization")),
        ]),
        migrations.CreateModel(name="AppointmentRequest", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("full_name", models.CharField(max_length=255)), ("email", models.EmailField(blank=True, max_length=254)), ("phone", models.CharField(max_length=40)),
            ("preferred_date", models.DateField(blank=True, null=True)), ("preferred_time", models.TimeField(blank=True, null=True)), ("notes", models.TextField(blank=True)),
            ("source", models.CharField(default="tour", max_length=40)), ("status", models.CharField(choices=[("pending", "Pending"), ("confirmed", "Confirmed"), ("completed", "Completed"), ("cancelled", "Cancelled")], default="pending", max_length=20)),
            ("appointment_type", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="requests", to="vendors.appointmenttype")),
            ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="appointment_requests", to="organizations.organization")),
            ("place", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="vendor_appointment_requests", to="places.place")),
            ("tour", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="appointment_requests", to="tours.tour")),
        ]),
        migrations.CreateModel(name="MarketDataSource", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("source_type", models.CharField(choices=[("website", "Website"), ("google", "Google Business"), ("facebook", "Facebook"), ("instagram", "Instagram"), ("tiktok", "TikTok"), ("linkedin", "LinkedIn"), ("manual", "Manual metrics")], max_length=24)),
            ("url", models.URLField(blank=True)), ("label", models.CharField(blank=True, max_length=180)), ("metrics", models.JSONField(blank=True, default=dict)),
            ("latest_summary", models.TextField(blank=True)), ("is_active", models.BooleanField(default=True)),
            ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="market_sources", to="organizations.organization")),
        ]),
        migrations.CreateModel(name="MarketInsightReport", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("period_start", models.DateField(blank=True, null=True)), ("period_end", models.DateField(blank=True, null=True)), ("input_snapshot", models.JSONField(blank=True, default=dict)),
            ("executive_summary", models.TextField(blank=True)), ("strengths", models.JSONField(blank=True, default=list)), ("weaknesses", models.JSONField(blank=True, default=list)),
            ("opportunities", models.JSONField(blank=True, default=list)), ("recommendations", models.JSONField(blank=True, default=list)), ("suggested_campaigns", models.JSONField(blank=True, default=list)),
            ("status", models.CharField(default="ready", max_length=24)), ("model_name", models.CharField(blank=True, max_length=80)),
            ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="market_reports", to="organizations.organization")),
        ]),
    ]
