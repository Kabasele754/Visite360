from datetime import timedelta

from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework import permissions, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.ai_core.models import AIRun
from apps.monitoring.models import AuditEvent, ProviderHealth, SystemEvent
from apps.monitoring.serializers import AuditEventSerializer, ProviderHealthSerializer, SystemEventSerializer
from apps.monitoring.services.health import run_platform_health_checks
from apps.organizations.selectors import get_user_organizations


class SystemEventViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SystemEventSerializer
    permission_classes = (permissions.IsAdminUser,)
    queryset = SystemEvent.objects.all()
    filterset_fields = ("level", "source", "event_type", "organization")
    search_fields = ("message", "trace_id")


class ProviderHealthViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ProviderHealthSerializer
    permission_classes = (permissions.IsAdminUser,)
    queryset = ProviderHealth.objects.all()


class AuditEventViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AuditEventSerializer
    permission_classes = (permissions.IsAuthenticated,)
    filterset_fields = ("organization", "action", "actor")
    search_fields = ("object_type", "object_id", "request_id")

    def get_queryset(self):
        if self.request.user.is_superuser:
            return AuditEvent.objects.all()
        return AuditEvent.objects.filter(organization__in=get_user_organizations(self.request.user))


@api_view(["GET"])
@permission_classes([permissions.IsAdminUser])
def dashboard(request):
    since = timezone.now() - timedelta(hours=24)
    ai_runs = AIRun.objects.filter(created_at__gte=since)
    return Response({
        "providers": ProviderHealthSerializer(ProviderHealth.objects.all(), many=True).data,
        "events_24h": SystemEvent.objects.filter(created_at__gte=since).values("level").annotate(total=Count("id")),
        "ai_24h": ai_runs.aggregate(
            requests=Count("id"),
            prompt_tokens=Sum("prompt_tokens"),
            completion_tokens=Sum("completion_tokens"),
            cost_usd=Sum("cost_usd"),
        ),
        "ai_statuses_24h": list(ai_runs.values("status").annotate(total=Count("id"))),
    })


@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])
def run_health_checks(request):
    rows = run_platform_health_checks()
    return Response(ProviderHealthSerializer(rows, many=True).data)
