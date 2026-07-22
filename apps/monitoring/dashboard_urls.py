from django.urls import path
from apps.monitoring.dashboard_views import enterprise_dashboard

urlpatterns = [path("dashboard/enterprise-ai/", enterprise_dashboard, name="enterprise-ai-dashboard")]
