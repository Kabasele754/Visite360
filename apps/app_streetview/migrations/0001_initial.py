# Generated manually for app_streetview
import uuid

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import apps.app_streetview.models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="StreetViewTour",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("title", models.CharField(max_length=180)),
                ("description", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("draft", "Draft"), ("ready", "Ready"), ("publishing", "Publishing"), ("published", "Published"), ("failed", "Failed")], default="draft", max_length=30)),
                ("last_error", models.TextField(blank=True)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="streetview_tours", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="StreetViewGoogleAccount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("google_email", models.EmailField(blank=True, max_length=254)),
                ("access_token", models.TextField(blank=True)),
                ("refresh_token", models.TextField(blank=True)),
                ("token_uri", models.URLField(default="https://oauth2.googleapis.com/token")),
                ("scopes", models.TextField(blank=True)),
                ("token_expiry", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="streetview_google_account", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "Street View Google Account", "verbose_name_plural": "Street View Google Accounts"},
        ),
        migrations.CreateModel(
            name="StreetViewScene",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=180)),
                ("description", models.TextField(blank=True)),
                ("image", models.ImageField(upload_to=apps.app_streetview.models.streetview_scene_upload_path, validators=[django.core.validators.FileExtensionValidator(["jpg", "jpeg", "png", "webp", "tif", "tiff"])])),
                ("image_width", models.PositiveIntegerField(default=0)),
                ("image_height", models.PositiveIntegerField(default=0)),
                ("file_size", models.PositiveBigIntegerField(default=0)),
                ("latitude", models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True)),
                ("longitude", models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True)),
                ("altitude", models.FloatField(blank=True, null=True)),
                ("heading", models.FloatField(default=0, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(360)])),
                ("pitch", models.FloatField(default=0, validators=[django.core.validators.MinValueValidator(-90), django.core.validators.MaxValueValidator(90)])),
                ("roll", models.FloatField(default=0, validators=[django.core.validators.MinValueValidator(-180), django.core.validators.MaxValueValidator(180)])),
                ("initial_yaw", models.FloatField(default=0)),
                ("initial_pitch", models.FloatField(default=0)),
                ("initial_fov", models.FloatField(default=90)),
                ("capture_time", models.DateTimeField(blank=True, null=True)),
                ("xmp_detected", models.BooleanField(default=False)),
                ("exif_data", models.JSONField(blank=True, default=dict)),
                ("google_photo_id", models.CharField(blank=True, max_length=255)),
                ("google_share_link", models.URLField(blank=True)),
                ("google_thumbnail_url", models.URLField(blank=True)),
                ("upload_reference_url", models.TextField(blank=True)),
                ("publish_status", models.CharField(choices=[("local", "Local"), ("ready", "Ready"), ("uploading", "Uploading"), ("created", "Created"), ("connected", "Connected"), ("failed", "Failed")], default="local", max_length=30)),
                ("last_error", models.TextField(blank=True)),
                ("order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("tour", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="scenes", to="app_streetview.streetviewtour")),
            ],
            options={"ordering": ["order", "id"]},
        ),
        migrations.CreateModel(
            name="StreetViewPublishJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("status", models.CharField(choices=[("queued", "Queued"), ("running", "Running"), ("succeeded", "Succeeded"), ("succeeded_with_warnings", "Succeeded with warnings"), ("failed", "Failed")], default="queued", max_length=40)),
                ("total_scenes", models.PositiveIntegerField(default=0)),
                ("published_scenes", models.PositiveIntegerField(default=0)),
                ("failed_scenes", models.PositiveIntegerField(default=0)),
                ("log", models.JSONField(blank=True, default=list)),
                ("error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("tour", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="publish_jobs", to="app_streetview.streetviewtour")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="streetview_publish_jobs", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="StreetViewHotspot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("type", models.CharField(choices=[("info", "Info"), ("link", "Link"), ("url", "URL")], default="info", max_length=20)),
                ("title", models.CharField(max_length=180)),
                ("description", models.TextField(blank=True)),
                ("url", models.URLField(blank=True)),
                ("yaw", models.FloatField(default=0)),
                ("pitch", models.FloatField(default=0)),
                ("icon", models.CharField(blank=True, max_length=80)),
                ("css_class", models.CharField(blank=True, max_length=80)),
                ("order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("scene", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="hotspots", to="app_streetview.streetviewscene")),
                ("target_scene", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="targeted_hotspots", to="app_streetview.streetviewscene")),
            ],
            options={"ordering": ["order", "id"]},
        ),
        migrations.CreateModel(
            name="StreetViewConnection",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("yaw", models.FloatField(default=0)),
                ("pitch", models.FloatField(default=0)),
                ("label", models.CharField(blank=True, max_length=120)),
                ("order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("from_scene", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="outgoing_connections", to="app_streetview.streetviewscene")),
                ("to_scene", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="incoming_connections", to="app_streetview.streetviewscene")),
                ("tour", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="connections", to="app_streetview.streetviewtour")),
            ],
            options={"ordering": ["order", "id"]},
        ),
        migrations.AddIndex(model_name="streetviewtour", index=models.Index(fields=["owner", "status"], name="app_street_owner_i_77a8f0_idx")),
        migrations.AddIndex(model_name="streetviewtour", index=models.Index(fields=["public_id"], name="app_street_public__149887_idx")),
        migrations.AddIndex(model_name="streetviewscene", index=models.Index(fields=["tour", "order"], name="app_street_tour_id_7bf1c3_idx")),
        migrations.AddIndex(model_name="streetviewscene", index=models.Index(fields=["google_photo_id"], name="app_street_google__a08763_idx")),
        migrations.AddConstraint(model_name="streetviewconnection", constraint=models.UniqueConstraint(fields=("tour", "from_scene", "to_scene"), name="unique_streetview_connection")),
    ]
