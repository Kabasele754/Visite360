import uuid
from django.db import migrations, models
import django.db.models.deletion
import apps.vision_ai.models


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("organizations", "0003_organization_logo"),
        ("tours", "0010_hotspot_door_and_advanced_display"),
    ]
    operations = [
        migrations.CreateModel(
            name="VisionAnalysis",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("uploaded_image", models.ImageField(blank=True, null=True, upload_to=apps.vision_ai.models.vision_upload_to)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("running", "Running"), ("succeeded", "Succeeded"), ("partial", "Partial"), ("failed", "Failed")], db_index=True, default="pending", max_length=24)),
                ("requested_providers", models.JSONField(blank=True, default=list)),
                ("completed_providers", models.JSONField(blank=True, default=list)),
                ("failed_providers", models.JSONField(blank=True, default=dict)),
                ("scene_type", models.CharField(blank=True, max_length=160)),
                ("summary", models.TextField(blank=True)),
                ("features", models.JSONField(blank=True, default=list)),
                ("products", models.JSONField(blank=True, default=list)),
                ("extracted_text", models.TextField(blank=True)),
                ("confidence", models.FloatField(default=0)),
                ("raw_results", models.JSONField(blank=True, default=dict)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("error_message", models.TextField(blank=True)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="vision_analyses", to="organizations.organization")),
                ("scene", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="enterprise_vision_analyses", to="tours.scene360")),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="VisionFrame",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("frame_index", models.PositiveSmallIntegerField()),
                ("yaw", models.FloatField(default=0)),
                ("pitch", models.FloatField(default=0)),
                ("image", models.ImageField(blank=True, null=True, upload_to="vision/frames/%Y/%m/")),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("analysis", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="frames", to="vision_ai.visionanalysis")),
            ],
            options={"ordering": ("frame_index",)},
        ),
        migrations.CreateModel(
            name="VisionDetection",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("provider", models.CharField(db_index=True, max_length=32)),
                ("label", models.CharField(db_index=True, max_length=160)),
                ("confidence", models.FloatField(default=0)),
                ("bbox", models.JSONField(blank=True, default=list, help_text="[x1, y1, x2, y2] in pixels or normalized coordinates.")),
                ("attributes", models.JSONField(blank=True, default=dict)),
                ("analysis", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="detections", to="vision_ai.visionanalysis")),
                ("frame", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="detections", to="vision_ai.visionframe")),
            ],
            options={"ordering": ("-confidence",)},
        ),
        migrations.CreateModel(
            name="OCRTextBlock",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("provider", models.CharField(default="paddleocr", max_length=32)),
                ("text", models.TextField()),
                ("confidence", models.FloatField(default=0)),
                ("polygon", models.JSONField(blank=True, default=list)),
                ("language", models.CharField(blank=True, max_length=16)),
                ("analysis", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="ocr_blocks", to="vision_ai.visionanalysis")),
                ("frame", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="ocr_blocks", to="vision_ai.visionframe")),
            ],
            options={"ordering": ("frame_id", "id")},
        ),
        migrations.AddConstraint(model_name="visionframe", constraint=models.UniqueConstraint(fields=("analysis", "frame_index"), name="unique_vision_frame")),
        migrations.AddIndex(model_name="visionanalysis", index=models.Index(fields=["organization", "status", "created_at"], name="vision_ai_v_organiz_3cc2af_idx")),
        migrations.AddIndex(model_name="visionanalysis", index=models.Index(fields=["scene", "created_at"], name="vision_ai_v_scene_i_1d6014_idx")),
        migrations.AddIndex(model_name="visiondetection", index=models.Index(fields=["analysis", "label", "confidence"], name="vision_ai_v_analysi_5b6194_idx")),
    ]
