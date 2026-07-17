from datetime import timedelta
from django.utils import timezone
from apps.growth_ai.models import Provider, TrafficMetric

def analyze_seo(organization, days=30):
    since = timezone.localdate() - timedelta(days=days - 1)
    rows = TrafficMetric.objects.filter(organization=organization, metric_date__gte=since, connection__provider__in=[Provider.SEARCH_CONSOLE, Provider.BING])
    queries = {}
    for row in rows.iterator():
        query = (row.dimensions or {}).get("query")
        if not query: continue
        item = queries.setdefault(query, {"clicks": 0.0, "impressions": 0.0, "position_sum": 0.0, "rows": 0})
        metrics = row.metrics or {}
        item["clicks"] += float(metrics.get("clicks") or 0); item["impressions"] += float(metrics.get("impressions") or 0)
        item["position_sum"] += float(metrics.get("position") or 0); item["rows"] += 1
    opportunities = []
    for query, item in queries.items():
        position = item["position_sum"] / max(item["rows"], 1)
        ctr = item["clicks"] / item["impressions"] if item["impressions"] else 0
        if item["impressions"] >= 20 and (position <= 20 or ctr < .03): opportunities.append({"query": query, "clicks": item["clicks"], "impressions": item["impressions"], "ctr": ctr, "position": position})
    opportunities.sort(key=lambda x: (x["impressions"], -x["position"]), reverse=True)
    return {"period_days": days, "keyword_count": len(queries), "opportunities": opportunities[:25]}
