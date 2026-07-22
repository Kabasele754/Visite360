from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.ai_agents.models import AgentDefinition, AgentRun
from apps.ai_agents.serializers import AgentDefinitionSerializer, AgentRunSerializer
from apps.ai_agents.services.registry import provision_default_agents
from apps.ai_agents.tasks import run_agent
from apps.organizations.models import Organization
from apps.organizations.selectors import get_user_organizations


class AgentDefinitionViewSet(viewsets.ModelViewSet):
    serializer_class = AgentDefinitionSerializer
    permission_classes = (permissions.IsAuthenticated,)
    filterset_fields = ("organization", "agent_type", "is_enabled")
    search_fields = ("name", "description", "slug")

    def get_queryset(self):
        return AgentDefinition.objects.filter(organization__in=get_user_organizations(self.request.user))

    def perform_create(self, serializer):
        organization = serializer.validated_data["organization"]
        if organization not in get_user_organizations(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Forbidden organization.")
        serializer.save()

    @action(detail=False, methods=["post"])
    def provision(self, request):
        organization = Organization.objects.filter(pk=request.data.get("organization_id"), memberships__user=request.user, memberships__is_active=True).first()
        if request.user.is_superuser:
            organization = Organization.objects.filter(pk=request.data.get("organization_id")).first()
        if not organization:
            return Response({"detail": "Organization not found or forbidden."}, status=404)
        agents = provision_default_agents(organization)
        return Response(self.get_serializer(agents, many=True).data)


class AgentRunViewSet(viewsets.ModelViewSet):
    serializer_class = AgentRunSerializer
    permission_classes = (permissions.IsAuthenticated,)
    http_method_names = ("get", "post", "delete", "head", "options")
    filterset_fields = ("agent", "status")

    def get_queryset(self):
        return AgentRun.objects.filter(agent__organization__in=get_user_organizations(self.request.user)).select_related("agent", "requested_by").prefetch_related("tool_invocations")

    def perform_create(self, serializer):
        agent = serializer.validated_data["agent"]
        if agent.organization not in get_user_organizations(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Forbidden agent.")
        instance = serializer.save(requested_by=self.request.user)
        run_agent.delay(str(instance.pk))

    @action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        instance = self.get_object()
        instance.status = AgentRun.Status.PENDING
        instance.error_message = ""
        instance.save(update_fields=("status", "error_message", "updated_at"))
        task = run_agent.delay(str(instance.pk))
        return Response({"queued": True, "task_id": task.id}, status=status.HTTP_202_ACCEPTED)
