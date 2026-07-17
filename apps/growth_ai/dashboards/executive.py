from apps.growth_ai.analyzers.marketing import analyze_marketing
from apps.growth_ai.models import DataSourceConnection, SyncRun

def executive_dashboard_context(organization, days=30):
    return {"organization": organization, "analysis": analyze_marketing(organization, days), "connections": DataSourceConnection.objects.filter(organization=organization), "recent_syncs": SyncRun.objects.filter(connection__organization=organization).select_related("connection")[:10]}
