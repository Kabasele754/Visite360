from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.ai_core.models import AIProviderConfiguration, AIRun, AIUsageDaily
from apps.ai_core.serializers import (
    AIProviderConfigurationSerializer,
    AIRunSerializer,
    AIUsageDailySerializer,
)
from apps.ai_core.services.router import AIProviderRouter
from apps.organizations.selectors import get_user_organizations


class OrganizationScopedMixin:
    def organizations(self):
        return get_user_organizations(self.request.user)


class AIProviderConfigurationViewSet(OrganizationScopedMixin, viewsets.ModelViewSet):
    serializer_class = AIProviderConfigurationSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        return AIProviderConfiguration.objects.filter(organization__in=self.organizations())

    def perform_create(self, serializer):
        organization = serializer.validated_data["organization"]
        if organization not in self.organizations():
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You are not a member of this organization.")
        serializer.save()

    @action(detail=True, methods=["post"])
    def health(self, request, pk=None):
        configuration = self.get_object()
        try:
            result = AIProviderRouter(
                organization=configuration.organization,
                user=request.user,
            ).generate_text(
                prompt="Reply only with OK.",
                provider=configuration.provider,
                model=configuration.model_name,
            )
            configuration.last_health_status = "healthy"
            configuration.last_health_message = result.text[:500]
            response_status = status.HTTP_200_OK
        except Exception as exc:
            configuration.last_health_status = "unhealthy"
            configuration.last_health_message = str(exc)[:2000]
            response_status = status.HTTP_503_SERVICE_UNAVAILABLE
        configuration.last_health_checked_at = timezone.now()
        configuration.save(update_fields=(
            "last_health_status", "last_health_message", "last_health_checked_at", "updated_at"
        ))
        return Response({
            "status": configuration.last_health_status,
            "message": configuration.last_health_message,
        }, status=response_status)


class AIRunViewSet(OrganizationScopedMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = AIRunSerializer
    permission_classes = (permissions.IsAuthenticated,)
    filterset_fields = ("status", "provider", "operation")
    search_fields = ("operation", "trace_id", "error_message")

    def get_queryset(self):
        return AIRun.objects.filter(organization__in=self.organizations())


class AIUsageDailyViewSet(OrganizationScopedMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = AIUsageDailySerializer
    permission_classes = (permissions.IsAuthenticated,)
    filterset_fields = ("provider", "date", "organization")

    def get_queryset(self):
        return AIUsageDaily.objects.filter(organization__in=self.organizations())
