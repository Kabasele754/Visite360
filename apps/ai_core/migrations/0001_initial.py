# Generated manually for Twinscopes AI Enterprise.
import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("organizations", "0003_organization_logo"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="AIProviderConfiguration",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("provider", models.CharField(choices=[("gemini", "Google Gemini / Vertex AI"), ("openai", "OpenAI"), ("local", "Local model")], max_length=24)),
                ("capability", models.CharField(choices=[("text", "Text"), ("vision", "Vision"), ("embedding", "Embedding"), ("image", "Image generation")], max_length=24)),
                ("model_name", models.CharField(max_length=160)),
                ("credential_reference", models.CharField(blank=True, help_text="Environment variable or secret reference; never store the raw key here.", max_length=160)),
                ("settings", models.JSONField(blank=True, default=dict)),
                ("priority", models.PositiveSmallIntegerField(default=100)),
                ("is_enabled", models.BooleanField(default=True)),
                ("last_health_status", models.CharField(blank=True, max_length=32)),
                ("last_health_message", models.TextField(blank=True)),
                ("last_health_checked_at", models.DateTimeField(blank=True, null=True)),
                ("organization", models.ForeignKey(blank=True, help_text="Leave empty for a platform-wide default.", null=True, on_delete=django.db.models.deletion.CASCADE, related_name="ai_provider_configurations", to="organizations.organization")),
            ],
            options={"ordering": ("priority", "provider", "capability")},
        ),
        migrations.CreateModel(
            name="AIRun",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("operation", models.CharField(db_index=True, max_length=120)),
                ("provider", models.CharField(blank=True, db_index=True, max_length=24)),
                ("model_name", models.CharField(blank=True, max_length=160)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("running", "Running"), ("succeeded", "Succeeded"), ("failed", "Failed"), ("cancelled", "Cancelled")], db_index=True, default="pending", max_length=24)),
                ("trace_id", models.CharField(blank=True, db_index=True, max_length=64)),
                ("input_summary", models.TextField(blank=True)),
                ("output_summary", models.TextField(blank=True)),
                ("input_metadata", models.JSONField(blank=True, default=dict)),
                ("output_metadata", models.JSONField(blank=True, default=dict)),
                ("prompt_tokens", models.PositiveIntegerField(default=0)),
                ("completion_tokens", models.PositiveIntegerField(default=0)),
                ("cost_usd", models.DecimalField(decimal_places=6, default=0, max_digits=12)),
                ("latency_ms", models.PositiveIntegerField(default=0)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("error_type", models.CharField(blank=True, max_length=160)),
                ("error_message", models.TextField(blank=True)),
                ("organization", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="ai_runs", to="organizations.organization")),
                ("requested_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="ai_runs", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="AIUsageDaily",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("date", models.DateField()),
                ("provider", models.CharField(max_length=24)),
                ("model_name", models.CharField(blank=True, max_length=160)),
                ("requests", models.PositiveIntegerField(default=0)),
                ("failures", models.PositiveIntegerField(default=0)),
                ("prompt_tokens", models.PositiveBigIntegerField(default=0)),
                ("completion_tokens", models.PositiveBigIntegerField(default=0)),
                ("cost_usd", models.DecimalField(decimal_places=6, default=0, max_digits=14)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="ai_usage_daily", to="organizations.organization")),
            ],
            options={"ordering": ("-date",)},
        ),
        migrations.AddConstraint(model_name="aiproviderconfiguration", constraint=models.UniqueConstraint(fields=("organization", "provider", "capability", "model_name"), name="unique_ai_provider_configuration")),
        migrations.AddConstraint(model_name="aiusagedaily", constraint=models.UniqueConstraint(fields=("organization", "date", "provider", "model_name"), name="unique_ai_usage_daily")),
        migrations.AddIndex(model_name="airun", index=models.Index(fields=["organization", "operation", "created_at"], name="ai_core_air_organiz_915dc7_idx")),
        migrations.AddIndex(model_name="airun", index=models.Index(fields=["provider", "status", "created_at"], name="ai_core_air_provide_94336a_idx")),
    ]
