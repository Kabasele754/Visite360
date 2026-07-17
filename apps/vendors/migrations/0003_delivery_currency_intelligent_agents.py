from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.core.validators
from decimal import Decimal


CURRENCY_CHOICES = [
    ("ZAR", "South African Rand (R)"),
    ("USD", "US Dollar ($)"),
    ("EUR", "Euro (€)"),
    ("GBP", "British Pound (£)"),
    ("BWP", "Botswana Pula (P)"),
    ("NAD", "Namibian Dollar (N$)"),
    ("ZMW", "Zambian Kwacha (K)"),
    ("CDF", "Congolese Franc (FC)"),
    ("KES", "Kenyan Shilling (KSh)"),
]


class Migration(migrations.Migration):
    dependencies = [
        ("vendors", "0002_payments_ai_behavior"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="vendorprofile",
            name="currency",
            field=models.CharField(
                choices=CURRENCY_CHOICES,
                default="USD",
                max_length=8,
            ),
        ),
        migrations.AlterField(
            model_name="product",
            name="currency",
            field=models.CharField(
                choices=CURRENCY_CHOICES,
                default="USD",
                max_length=8,
            ),
        ),
        migrations.AlterField(
            model_name="order",
            name="currency",
            field=models.CharField(
                choices=CURRENCY_CHOICES,
                default="USD",
                max_length=8,
            ),
        ),
        migrations.AddField(
            model_name="deliveryzone",
            name="country_code",
            field=models.CharField(db_index=True, default="ZA", max_length=2),
        ),
        migrations.AddField(
            model_name="deliveryzone",
            name="province",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="deliveryzone",
            name="postal_codes",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="deliveryzone",
            name="currency",
            field=models.CharField(
                choices=CURRENCY_CHOICES,
                default="ZAR",
                max_length=8,
            ),
        ),
        migrations.AddField(
            model_name="deliveryzone",
            name="is_default",
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name="deliveryzone",
            name="fee",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                max_digits=12,
                validators=[django.core.validators.MinValueValidator(Decimal("0.00"))],
            ),
        ),
        migrations.AlterField(
            model_name="deliveryzone",
            name="free_delivery_threshold",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=12,
                null=True,
                validators=[django.core.validators.MinValueValidator(Decimal("0.00"))],
            ),
        ),
        migrations.AddConstraint(
            model_name="deliveryzone",
            constraint=models.UniqueConstraint(
                fields=("organization", "name", "country_code"),
                name="unique_delivery_zone_per_org_country",
            ),
        ),
        migrations.CreateModel(
            name="IntelligentAgent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.SlugField(max_length=80, unique=True)),
                ("name", models.CharField(max_length=160)),
                ("role", models.CharField(max_length=180)),
                ("description", models.TextField(blank=True)),
                ("system_instruction", models.TextField()),
                ("model_name", models.CharField(default="gemini-2.5-flash", max_length=100)),
                ("is_active", models.BooleanField(default=True)),
                ("order", models.PositiveSmallIntegerField(default=0)),
            ],
            options={"ordering": ("order", "name")},
        ),
        migrations.CreateModel(
            name="IntelligentAgentRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("status", models.CharField(
                    choices=[
                        ("pending", "Pending"),
                        ("running", "Running"),
                        ("completed", "Completed"),
                        ("failed", "Failed"),
                    ],
                    default="pending",
                    max_length=20,
                )),
                ("input_snapshot", models.JSONField(blank=True, default=dict)),
                ("output", models.JSONField(blank=True, default=dict)),
                ("error", models.TextField(blank=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("agent", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="runs",
                    to="vendors.intelligentagent",
                )),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="intelligent_agent_runs",
                    to="organizations.organization",
                )),
                ("requested_by", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="requested_intelligent_agent_runs",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="IntelligentRecommendation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("category", models.CharField(default="growth", max_length=80)),
                ("title", models.CharField(max_length=220)),
                ("rationale", models.TextField(blank=True)),
                ("action", models.TextField()),
                ("impact", models.CharField(default="medium", max_length=20)),
                ("effort", models.CharField(default="medium", max_length=20)),
                ("priority", models.PositiveSmallIntegerField(default=3)),
                ("status", models.CharField(
                    choices=[
                        ("new", "New"),
                        ("accepted", "Accepted"),
                        ("in_progress", "In progress"),
                        ("completed", "Completed"),
                        ("dismissed", "Dismissed"),
                    ],
                    default="new",
                    max_length=20,
                )),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="intelligent_recommendations",
                    to="organizations.organization",
                )),
                ("run", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="recommendations",
                    to="vendors.intelligentagentrun",
                )),
            ],
            options={"ordering": ("priority", "-created_at")},
        ),
    ]
