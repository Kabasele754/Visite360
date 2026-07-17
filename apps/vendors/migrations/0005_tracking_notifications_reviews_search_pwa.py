from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.core.validators
from decimal import Decimal


class Migration(migrations.Migration):
    dependencies = [
        ("vendors", "0004_marketplace_pro_stock_address"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="order",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("confirmed", "Confirmed"),
                    ("preparing", "Preparing"),
                    ("ready_for_pickup", "Ready for pickup"),
                    ("out_for_delivery", "Out for delivery"),
                    ("delivered", "Delivered"),
                    ("cancelled", "Cancelled"),
                ],
                default="pending",
                max_length=24,
            ),
        ),
        migrations.CreateModel(
            name="OrderStatusHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("status", models.CharField(
                    choices=[
                        ("pending", "Pending"),
                        ("confirmed", "Confirmed"),
                        ("preparing", "Preparing"),
                        ("ready_for_pickup", "Ready for pickup"),
                        ("out_for_delivery", "Out for delivery"),
                        ("delivered", "Delivered"),
                        ("cancelled", "Cancelled"),
                    ],
                    max_length=24,
                )),
                ("title", models.CharField(max_length=180)),
                ("note", models.TextField(blank=True)),
                ("customer_visible", models.BooleanField(default=True)),
                ("notified_at", models.DateTimeField(blank=True, null=True)),
                ("changed_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="vendor_order_status_changes",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("order", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="status_history",
                    to="vendors.order",
                )),
            ],
            options={"ordering": ("created_at",)},
        ),
        migrations.CreateModel(
            name="CustomerNotification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("kind", models.CharField(
                    choices=[
                        ("order", "Order"), ("payment", "Payment"), ("delivery", "Delivery"),
                        ("cart", "Cart"), ("stock", "Stock"), ("review", "Review"), ("general", "General"),
                    ],
                    default="general", max_length=20,
                )),
                ("title", models.CharField(max_length=180)),
                ("message", models.TextField()),
                ("action_url", models.CharField(blank=True, max_length=500)),
                ("email_sent_at", models.DateTimeField(blank=True, null=True)),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                ("order", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="notifications", to="vendors.order")),
                ("organization", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="customer_notifications", to="organizations.organization")),
                ("product", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="notifications", to="vendors.product")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="market_notifications", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.AddIndex(
            model_name="customernotification",
            index=models.Index(fields=["user", "read_at", "created_at"], name="vendors_cus_user_id_a87ef0_idx"),
        ),
        migrations.CreateModel(
            name="ProductReview",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("rating", models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ("comment", models.TextField()),
                ("status", models.CharField(choices=[("pending", "Pending"), ("published", "Published"), ("rejected", "Rejected")], default="published", max_length=20)),
                ("vendor_response", models.TextField(blank=True)),
                ("vendor_responded_at", models.DateTimeField(blank=True, null=True)),
                ("customer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="product_reviews", to=settings.AUTH_USER_MODEL)),
                ("order_item", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="verified_review", to="vendors.orderitem")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reviews", to="vendors.product")),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.AddIndex(
            model_name="productreview",
            index=models.Index(fields=["product", "status", "created_at"], name="vendors_pro_product_97b7d0_idx"),
        ),
        migrations.CreateModel(
            name="ProductReviewImage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("image", models.ImageField(upload_to="vendors/reviews/")),
                ("alt_text", models.CharField(blank=True, max_length=180)),
                ("review", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="images", to="vendors.productreview")),
            ],
        ),
        migrations.CreateModel(
            name="BackInStockSubscription",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("email", models.EmailField(max_length=254)),
                ("notified_at", models.DateTimeField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="stock_subscriptions", to="vendors.product")),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="stock_subscriptions", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name="backinstocksubscription",
            constraint=models.UniqueConstraint(fields=("product", "email"), name="unique_stock_subscription_product_email"),
        ),
        migrations.CreateModel(
            name="ProductRecommendation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("kind", models.CharField(choices=[
                    ("similar", "Similar"), ("frequently_bought", "Frequently bought together"),
                    ("bundle", "Bundle"), ("campaign", "Campaign"), ("featured", "Featured"),
                    ("delivery", "Delivery"),
                ], max_length=32)),
                ("score", models.DecimalField(decimal_places=4, default=Decimal("0.0000"), max_digits=6)),
                ("title", models.CharField(max_length=220)),
                ("rationale", models.TextField(blank=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("generated_by", models.CharField(default="rules", max_length=40)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="product_recommendations", to="organizations.organization")),
                ("recommended_product", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="recommendation_targets", to="vendors.product")),
                ("source_product", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="recommendation_sources", to="vendors.product")),
            ],
            options={"ordering": ("-score", "-created_at")},
        ),
        migrations.CreateModel(
            name="WebVitalMeasurement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=20)),
                ("value", models.FloatField()),
                ("rating", models.CharField(blank=True, max_length=20)),
                ("page_path", models.CharField(max_length=500)),
                ("navigation_type", models.CharField(blank=True, max_length=40)),
                ("device", models.CharField(blank=True, max_length=40)),
                ("session_key", models.CharField(blank=True, max_length=80)),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="web_vital_measurements", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.AddIndex(
            model_name="webvitalmeasurement",
            index=models.Index(fields=["name", "created_at"], name="vendors_web_name_4fe49f_idx"),
        ),
    ]
