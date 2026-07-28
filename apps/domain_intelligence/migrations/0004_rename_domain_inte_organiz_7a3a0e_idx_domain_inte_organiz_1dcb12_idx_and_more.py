from django.db import migrations


class Migration(migrations.Migration):
    """Keep legacy explicit index names without touching drifted SQLite indexes."""

    dependencies = [
        ("domain_intelligence", "0003_organization_embedded_resource"),
    ]

    operations = []
