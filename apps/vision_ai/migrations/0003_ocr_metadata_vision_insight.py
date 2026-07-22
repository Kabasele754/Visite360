from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("vendors", "0006_alter_deliveryzone_options_and_more"),
        ("vision_ai", "0002_rename_vision_ai_v_organiz_3cc2af_idx_vision_ai_v_organiz_a9c687_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="ocrtextblock",
            name="metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.CreateModel(
            name="VisionInsight",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("kind", models.CharField(choices=[("object", "Object"), ("text", "Text"), ("area", "Area")], db_index=True, max_length=20)),
                ("label", models.CharField(blank=True, db_index=True, max_length=180)),
                ("title", models.CharField(max_length=240)),
                ("description", models.TextField(blank=True)),
                ("confidence", models.FloatField(default=0)),
                ("bbox", models.JSONField(blank=True, default=list)),
                ("polygon", models.JSONField(blank=True, default=list)),
                ("yaw", models.FloatField(default=0, help_text="Panorama yaw in radians.")),
                ("pitch", models.FloatField(default=0, help_text="Marzipano pitch in radians.")),
                ("angular_radius", models.FloatField(default=0.12, help_text="Approximate selection radius in radians.")),
                ("source_providers", models.JSONField(blank=True, default=list)),
                ("attributes", models.JSONField(blank=True, default=dict)),
                ("is_verified", models.BooleanField(default=False)),
                ("analysis", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="insights", to="vision_ai.visionanalysis")),
                ("frame", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="insights", to="vision_ai.visionframe")),
                ("related_product", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="vision_insights", to="vendors.product")),
            ],
            options={"ordering": ("-confidence", "id")},
        ),
        migrations.AddIndex(
            model_name="visioninsight",
            index=models.Index(fields=["analysis", "kind", "confidence"], name="vision_ai_v_analysi_70db40_idx"),
        ),
        migrations.AddIndex(
            model_name="visioninsight",
            index=models.Index(fields=["analysis", "yaw", "pitch"], name="vision_ai_v_analysi_6641c1_idx"),
        ),
    ]
