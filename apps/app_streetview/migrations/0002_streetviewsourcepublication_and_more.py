# Clean migration for canonical Street View publishing layer.
# This migration intentionally DOES NOT rename/remove old legacy indexes.
# It only adds the canonical publication tables that reference existing tours.Tour/Scene360.

import uuid

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app_streetview", "0001_initial"),
        ("tours", "0008_tourshare_touruniqueview"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="StreetViewSourcePublication",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("status", models.CharField(choices=[("draft", "Draft"), ("ready", "Ready"), ("publishing", "Publishing"), ("published", "Published"), ("failed", "Failed")], default="draft", max_length=30)),
                ("last_error", models.TextField(blank=True)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="streetview_source_publications", to=settings.AUTH_USER_MODEL)),
                ("source_tour", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="streetview_publication", to="tours.tour")),
            ],
            options={
                "verbose_name": "Street View Source Publication",
                "verbose_name_plural": "Street View Source Publications",
                "ordering": ["-updated_at"],
            },
        ),
        migrations.CreateModel(
            name="StreetViewSourceSceneState",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("latitude", models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True)),
                ("longitude", models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True)),
                ("altitude", models.FloatField(blank=True, null=True)),
                ("heading", models.FloatField(default=0, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(360)])),
                ("pitch", models.FloatField(default=0, validators=[django.core.validators.MinValueValidator(-90), django.core.validators.MaxValueValidator(90)])),
                ("roll", models.FloatField(default=0, validators=[django.core.validators.MinValueValidator(-180), django.core.validators.MaxValueValidator(180)])),
                ("initial_fov", models.FloatField(default=90)),
                ("google_photo_id", models.CharField(blank=True, max_length=255)),
                ("google_share_link", models.URLField(blank=True)),
                ("google_thumbnail_url", models.URLField(blank=True)),
                ("upload_reference_url", models.TextField(blank=True)),
                ("publish_status", models.CharField(choices=[("local", "Local"), ("ready", "Ready"), ("uploading", "Uploading"), ("created", "Created"), ("connected", "Connected"), ("failed", "Failed")], default="local", max_length=30)),
                ("last_error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("publication", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="scene_states", to="app_streetview.streetviewsourcepublication")),
                ("source_scene", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="streetview_state", to="tours.scene360")),
            ],
            options={
                "verbose_name": "Street View Source Scene State",
                "verbose_name_plural": "Street View Source Scene States",
                "ordering": ["source_scene__order", "source_scene_id"],
            },
        ),
        migrations.CreateModel(
            name="StreetViewSourcePublishJob",
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
                ("publication", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="publish_jobs", to="app_streetview.streetviewsourcepublication")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="streetview_source_publish_jobs", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Street View Source Publish Job",
                "verbose_name_plural": "Street View Source Publish Jobs",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="streetviewsourcepublication",
            index=models.Index(fields=["owner", "status"], name="sv_src_pub_owner_status_idx"),
        ),
        migrations.AddIndex(
            model_name="streetviewsourcepublication",
            index=models.Index(fields=["source_tour"], name="sv_src_pub_tour_idx"),
        ),
        migrations.AddIndex(
            model_name="streetviewsourcepublication",
            index=models.Index(fields=["public_id"], name="sv_src_pub_public_id_idx"),
        ),
        migrations.AddIndex(
            model_name="streetviewsourcescenestate",
            index=models.Index(fields=["publication", "publish_status"], name="sv_src_state_pub_status_idx"),
        ),
        migrations.AddIndex(
            model_name="streetviewsourcescenestate",
            index=models.Index(fields=["source_scene"], name="sv_src_state_scene_idx"),
        ),
        migrations.AddIndex(
            model_name="streetviewsourcescenestate",
            index=models.Index(fields=["google_photo_id"], name="sv_src_state_google_idx"),
        ),
    ]
