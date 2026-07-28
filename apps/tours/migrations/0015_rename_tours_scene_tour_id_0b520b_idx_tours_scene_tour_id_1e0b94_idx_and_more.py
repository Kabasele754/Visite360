from django.db import migrations


class Migration(migrations.Migration):
    """Keep the explicit index names declared by migration 0012."""

    dependencies = [
        ("tours", "0014_scene360_tripod_logo_perspective"),
    ]

    operations = []
