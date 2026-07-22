from django.urls import include, path
from rest_framework.routers import DefaultRouter
from apps.monitoring.views import AuditEventViewSet, ProviderHealthViewSet, SystemEventViewSet, dashboard, run_health_checks

router = DefaultRouter()
router.register("events", SystemEventViewSet, basename="system-event")
router.register("providers", ProviderHealthViewSet, basename="provider-health")
router.register("audit", AuditEventViewSet, basename="audit-event")
urlpatterns = [
    path("dashboard/", dashboard, name="monitoring-dashboard"),
    path("health/run/", run_health_checks, name="monitoring-health-run"),
    path("", include(router.urls)),
]
