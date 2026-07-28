from django.db import migrations


class Migration(migrations.Migration):
    """Keep legacy explicit index names without renaming missing SQLite indexes."""

    dependencies = [
        ("vision_ai", "0003_ocr_metadata_vision_insight"),
    ]

    operations = []
