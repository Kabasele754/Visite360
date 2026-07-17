from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("vendors", "0001_initial"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.AddField(model_name="order", name="payment_provider", field=models.CharField(default="manual", max_length=24)),
        migrations.AddField(model_name="order", name="payment_reference", field=models.CharField(blank=True, max_length=160)),
        migrations.AddField(model_name="order", name="stripe_checkout_session_id", field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(model_name="order", name="stripe_payment_intent_id", field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(model_name="order", name="paypal_order_id", field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(model_name="order", name="paid_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="order", name="payment_error", field=models.TextField(blank=True)),
        migrations.AddField(model_name="marketinsightreport", name="priority_actions", field=models.JSONField(blank=True, default=list)),
        migrations.AddField(model_name="marketinsightreport", name="funnel_diagnosis", field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name="marketinsightreport", name="product_recommendations", field=models.JSONField(blank=True, default=list)),
        migrations.AddField(model_name="marketinsightreport", name="appointment_strategy", field=models.JSONField(blank=True, default=list)),
        migrations.AddField(model_name="marketinsightreport", name="content_calendar", field=models.JSONField(blank=True, default=list)),
        migrations.CreateModel(name="CustomerBehaviorEvent", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("session_key", models.CharField(blank=True, max_length=80)), ("event_type", models.CharField(max_length=60)),
            ("metadata", models.JSONField(blank=True, default=dict)),
            ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="behavior_events", to="organizations.organization")),
            ("product", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="behavior_events", to="vendors.product")),
            ("tour", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="commerce_behavior_events", to="tours.tour")),
            ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="market_behavior_events", to=settings.AUTH_USER_MODEL)),
        ], options={"ordering": ("-created_at",)}),
        migrations.AddIndex(model_name="customerbehaviorevent", index=models.Index(fields=["organization", "event_type", "created_at"], name="vendors_cus_organiz_6f48a7_idx")),
    ]
