import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("organizations", "0005_ai_assistant_branding"),
        ("domain_intelligence", "0002_intelligence_operations"),
    ]

    operations = [
        migrations.CreateModel(
            name="OrganizationEmbeddedResource",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("label", models.CharField(max_length=180)),
                ("kind", models.CharField(choices=[("website", "Website"), ("booking", "Booking"), ("contact", "Contact form"), ("crm", "CRM portal"), ("form", "External form"), ("social", "Social profile"), ("other", "Other")], db_index=True, default="other", max_length=24)),
                ("url", models.URLField(max_length=1000)),
                ("embed_mode", models.CharField(choices=[("auto", "Try embedded preview"), ("iframe", "Embedded iframe"), ("native_booking", "Twinscopes booking form"), ("native_contact", "Twinscopes contact form"), ("summary", "Information only")], default="auto", max_length=24)),
                ("button_label", models.CharField(blank=True, max_length=80)),
                ("description", models.TextField(blank=True)),
                ("allow_in_tour_agent", models.BooleanField(default=True)),
                ("is_verified", models.BooleanField(db_index=True, default=False)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("sandbox_permissions", models.JSONField(blank=True, default=list)),
                ("source_url", models.URLField(blank=True, max_length=1000)),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="embedded_resources", to="organizations.organization")),
            ],
            options={"ordering": ("kind", "label")},
        ),
        migrations.AddIndex(model_name="organizationembeddedresource", index=models.Index(fields=["organization", "is_active", "is_verified"], name="di_embed_org_active_idx")),
        migrations.AddIndex(model_name="organizationembeddedresource", index=models.Index(fields=["organization", "kind"], name="di_embed_org_kind_idx")),
        migrations.AddConstraint(model_name="organizationembeddedresource", constraint=models.UniqueConstraint(fields=("organization", "url"), name="unique_embedded_resource_url_per_org")),
    ]
