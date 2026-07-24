from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("vendors", "0006_alter_deliveryzone_options_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="appointmentrequest",
            name="appointment_mode",
            field=models.CharField(default="in_person", max_length=24),
        ),
        migrations.AddField(
            model_name="appointmentrequest",
            name="metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="appointmentrequest",
            name="practitioner_name",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="appointmentrequest",
            name="reason_for_visit",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="appointmentrequest",
            name="specialty_name",
            field=models.CharField(blank=True, max_length=180),
        ),
    ]
