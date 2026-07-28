from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("organizations", "0005_ai_assistant_branding"),
        ("tours", "0017_scene360_tripod_logo_background"),
        ("app_streetview", "0004_google_status_and_direct_projects"),
    ]

    operations = [
        migrations.AddField(
            model_name="streetviewtour",
            name="source_organization",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="streetview_direct_projects", to="organizations.organization"),
        ),
        migrations.AddField(
            model_name="streetviewtour",
            name="source_tour",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="streetview_direct_projects", to="tours.tour"),
        ),
    ]
