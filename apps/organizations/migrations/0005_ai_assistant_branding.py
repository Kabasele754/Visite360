import apps.organizations.models
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("organizations", "0004_organization_enterprise_profile")]

    operations = [
        migrations.AddField(
            model_name="organization",
            name="ai_assistant_enabled",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="organization",
            name="ai_assistant_brand_mode",
            field=models.CharField(
                choices=[
                    ("twinscopes", "Twinscopes branding"),
                    ("organization", "Organization branding"),
                    ("custom", "Custom assistant branding"),
                    ("hidden", "No visual branding"),
                ],
                default="twinscopes",
                max_length=24,
            ),
        ),
        migrations.AddField(
            model_name="organization",
            name="ai_assistant_name",
            field=models.CharField(default="Twinscopes AI", max_length=120),
        ),
        migrations.AddField(
            model_name="organization",
            name="ai_assistant_tagline",
            field=models.CharField(default="Scene-aware assistant", max_length=160),
        ),
        migrations.AddField(
            model_name="organization",
            name="ai_assistant_avatar",
            field=models.ImageField(blank=True, null=True, upload_to=apps.organizations.models.organization_ai_avatar_upload_to),
        ),
        migrations.AddField(
            model_name="organization",
            name="ai_allow_embedded_resources",
            field=models.BooleanField(default=True),
        ),
    ]
