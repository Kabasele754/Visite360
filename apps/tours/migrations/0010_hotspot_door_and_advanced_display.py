from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("tours", "0009_hotspot_media_pdf_video_floor")]

    operations = [
        migrations.AlterField(
            model_name="hotspot",
            name="type",
            field=models.CharField(
                max_length=20,
                choices=[
                    ("navigate", "Navigate"),
                    ("floor", "Floor navigation"),
                    ("pdf", "PDF document"),
                    ("video", "Video"),
                    ("door", "Interactive door"),
                    ("info", "Info"),
                    ("cta", "CTA"),
                    ("product", "Product"),
                    ("custom", "Custom"),
                ],
            ),
        ),
    ]
