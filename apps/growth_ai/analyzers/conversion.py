from datetime import timedelta
from django.db.models import Count
from django.utils import timezone
from apps.growth_ai.models import GrowthEvent

def analyze_conversion(organization, days=30):
    since = timezone.now() - timedelta(days=days)
    counts = {row["event_name"]: row["total"] for row in GrowthEvent.objects.filter(organization=organization, occurred_at__gte=since).values("event_name").annotate(total=Count("id"))}
    viewed = counts.get("product_viewed", 0); cart = counts.get("add_to_cart", 0); checkout = counts.get("checkout_started", 0); purchases = counts.get("purchase_completed", 0)
    rate = lambda value, base: round(value / base * 100, 2) if base else 0.0
    return {"period_days": days, "events": counts, "funnel": {"product_views": viewed, "add_to_cart": cart, "checkout_started": checkout, "purchases": purchases}, "rates": {"view_to_cart": rate(cart, viewed), "cart_to_checkout": rate(checkout, cart), "checkout_to_purchase": rate(purchases, checkout), "overall_conversion": rate(purchases, viewed)}}
