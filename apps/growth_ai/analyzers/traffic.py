from datetime import timedelta
from django.db.models import Sum
from django.utils import timezone
from apps.growth_ai.models import TrafficMetric

def _number(value):
    try: return float(value or 0)
    except (TypeError, ValueError): return 0.0

def analyze_traffic(organization, days=30):
    since = timezone.localdate() - timedelta(days=days - 1)
    rows = TrafficMetric.objects.filter(organization=organization, metric_date__gte=since)
    totals = {"clicks": 0.0, "impressions": 0.0, "sessions": 0.0, "users": 0.0, "pageviews": 0.0}
    sources = {}
    for row in rows.iterator():
        metrics = row.metrics or {}
        for key in totals: totals[key] += _number(metrics.get(key) or metrics.get("active_users" if key == "users" else key))
        source = (row.dimensions or {}).get("source") or row.connection.get_provider_display()
        sources[source] = sources.get(source, 0.0) + _number(metrics.get("sessions") or metrics.get("clicks"))
    return {"period_days": days, "totals": totals, "top_sources": sorted(sources.items(), key=lambda x: x[1], reverse=True)[:10]}
