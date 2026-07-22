from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("organizations", "0003_organization_logo")]

    operations = [
        migrations.AddField(model_name="organization", name="description", field=models.TextField(blank=True)),
        migrations.AddField(model_name="organization", name="website_url", field=models.URLField(blank=True)),
        migrations.AddField(model_name="organization", name="booking_url", field=models.URLField(blank=True)),
        migrations.AddField(model_name="organization", name="public_email", field=models.EmailField(blank=True, max_length=254)),
        migrations.AddField(model_name="organization", name="public_phone", field=models.CharField(blank=True, max_length=40)),
        migrations.AddField(model_name="organization", name="facebook_url", field=models.URLField(blank=True)),
        migrations.AddField(model_name="organization", name="instagram_url", field=models.URLField(blank=True)),
        migrations.AddField(model_name="organization", name="tiktok_url", field=models.URLField(blank=True)),
        migrations.AddField(model_name="organization", name="linkedin_url", field=models.URLField(blank=True)),
        migrations.AddField(model_name="organization", name="youtube_url", field=models.URLField(blank=True)),
        migrations.AddField(model_name="organization", name="social_links_verified_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="organization", name="ai_use_website", field=models.BooleanField(default=True)),
        migrations.AddField(model_name="organization", name="ai_auto_discover_social_links", field=models.BooleanField(default=True)),
    ]
