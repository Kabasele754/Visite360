from django.db import migrations


def enable_vector(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("CREATE EXTENSION IF NOT EXISTS vector")


class Migration(migrations.Migration):
    dependencies = [("knowledge", "0001_initial")]
    operations = [migrations.RunPython(enable_vector, migrations.RunPython.noop)]
