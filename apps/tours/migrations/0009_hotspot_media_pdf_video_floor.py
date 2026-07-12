from django.db import migrations, models
import apps.tours.models


class Migration(migrations.Migration):
    dependencies = [("tours", "0008_tourshare_touruniqueview")]

    operations = [
        migrations.AddField(
            model_name="hotspot",
            name="media_file",
            field=models.FileField(blank=True, null=True, upload_to=apps.tours.models.hotspot_media_upload_to),
        ),
        migrations.AddField(
            model_name="hotspot",
            name="poster_image",
            field=models.ImageField(blank=True, null=True, upload_to=apps.tours.models.hotspot_poster_upload_to),
        ),
        migrations.AlterField(
            model_name="hotspot",
            name="type",
            field=models.CharField(choices=[("navigate", "Navigate"), ("floor", "Floor navigation"), ("pdf", "PDF document"), ("video", "Video"), ("info", "Info"), ("cta", "CTA"), ("product", "Product"), ("custom", "Custom")], max_length=20),
        ),
    ]
