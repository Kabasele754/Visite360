from django.db import migrations, models
from django.core.validators import FileExtensionValidator
import apps.app_streetview.models


class Migration(migrations.Migration):
    dependencies = [("app_streetview", "0003_advanced_streetview_studio")]

    operations = [
        migrations.AddField(model_name="streetviewtour", name="project_mode", field=models.CharField(choices=[("direct", "Direct Google project"), ("managed", "Managed Street View project")], default="direct", max_length=20)),
        migrations.AddField(model_name="streetviewtour", name="storage_policy", field=models.CharField(choices=[("keep_local", "Keep local originals"), ("delete_after_verified", "Delete local bytes after Google verification")], default="keep_local", max_length=32)),
        migrations.AddField(model_name="streetviewtour", name="google_place_id", field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(model_name="streetviewtour", name="auto_connect", field=models.BooleanField(default=True)),
        migrations.AddField(model_name="streetviewtour", name="auto_sync_status", field=models.BooleanField(default=True)),
        migrations.AlterField(model_name="streetviewscene", name="image", field=models.ImageField(blank=True, upload_to=apps.app_streetview.models.streetview_scene_upload_path, validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp", "tif", "tiff"])])),
        migrations.AddField(model_name="streetviewscene", name="google_maps_publish_status", field=models.CharField(blank=True, db_index=True, max_length=64)),
        migrations.AddField(model_name="streetviewscene", name="google_transfer_status", field=models.CharField(blank=True, max_length=64)),
        migrations.AddField(model_name="streetviewscene", name="google_view_count", field=models.PositiveBigIntegerField(default=0)),
        migrations.AddField(model_name="streetviewscene", name="google_last_synced_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="streetviewscene", name="google_status_payload", field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name="streetviewscene", name="connection_sync_status", field=models.CharField(blank=True, db_index=True, default="pending", max_length=32)),
        migrations.AddField(model_name="streetviewscene", name="connection_audit", field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name="streetviewscene", name="remote_only", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="streetviewscene", name="local_bytes_deleted_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="streetviewsourcescenestate", name="google_maps_publish_status", field=models.CharField(blank=True, db_index=True, max_length=64)),
        migrations.AddField(model_name="streetviewsourcescenestate", name="google_transfer_status", field=models.CharField(blank=True, max_length=64)),
        migrations.AddField(model_name="streetviewsourcescenestate", name="google_view_count", field=models.PositiveBigIntegerField(default=0)),
        migrations.AddField(model_name="streetviewsourcescenestate", name="google_last_synced_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="streetviewsourcescenestate", name="google_status_payload", field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name="streetviewsourcescenestate", name="connection_sync_status", field=models.CharField(blank=True, db_index=True, default="pending", max_length=32)),
        migrations.AddField(model_name="streetviewsourcescenestate", name="connection_audit", field=models.JSONField(blank=True, default=dict)),
    ]
