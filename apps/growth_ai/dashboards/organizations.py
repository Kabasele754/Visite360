from apps.organizations.models import Organization
from apps.growth_ai.models import DataSourceConnection

def organizations_dashboard_context():
    return {"organizations": Organization.objects.all().order_by("name"), "connection_count": DataSourceConnection.objects.filter(is_enabled=True).count()}
