from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("users", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="user",
            name="email_verified_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="is_customer",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="user",
            name="preferred_currency",
            field=models.CharField(default="USD", max_length=8),
        ),
        migrations.AddField(
            model_name="user",
            name="stripe_customer_id",
            field=models.CharField(blank=True, db_index=True, max_length=255),
        ),
    ]
