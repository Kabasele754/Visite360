from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("vendors", "0003_delivery_currency_intelligent_agents"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="delivery_suburb",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="order",
            name="delivery_province",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="order",
            name="delivery_postal_code",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="order",
            name="delivery_country_code",
            field=models.CharField(default="ZA", max_length=2),
        ),
        migrations.CreateModel(
            name="StockReservation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("session_key", models.CharField(db_index=True, max_length=80)),
                ("quantity", models.PositiveIntegerField(default=1)),
                ("status", models.CharField(
                    choices=[
                        ("active", "Active"),
                        ("converted", "Converted"),
                        ("released", "Released"),
                        ("expired", "Expired"),
                    ],
                    db_index=True,
                    default="active",
                    max_length=20,
                )),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("order", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="stock_reservations",
                    to="vendors.order",
                )),
                ("product", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="stock_reservations",
                    to="vendors.product",
                )),
            ],
            options={"ordering": ("expires_at",)},
        ),
        migrations.AddIndex(
            model_name="stockreservation",
            index=models.Index(fields=["product", "status", "expires_at"], name="vendors_sto_product_7a9ab4_idx"),
        ),
        migrations.AddIndex(
            model_name="stockreservation",
            index=models.Index(fields=["session_key", "status"], name="vendors_sto_session_f1ef7c_idx"),
        ),
    ]
