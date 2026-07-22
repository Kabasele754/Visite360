from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.organizations.selectors import get_user_organizations
from apps.vision_ai.models import VisionAnalysis
from apps.vision_ai.serializers import VisionAnalysisSerializer
from apps.vision_ai.tasks import run_vision_analysis


class VisionAnalysisViewSet(viewsets.ModelViewSet):
    serializer_class = VisionAnalysisSerializer
    permission_classes = (permissions.IsAuthenticated,)
    filterset_fields = ("organization", "scene", "status")
    search_fields = ("scene_type", "summary", "extracted_text")
    http_method_names = ("get", "post", "delete", "head", "options")

    def get_queryset(self):
        return VisionAnalysis.objects.filter(
            organization__in=get_user_organizations(self.request.user)
        ).select_related("organization", "scene").prefetch_related("frames__detections", "frames__ocr_blocks")

    def perform_create(self, serializer):
        organization = serializer.validated_data["organization"]
        if organization not in get_user_organizations(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You are not a member of this organization.")
        analysis = serializer.save()
        run_vision_analysis.delay(str(analysis.pk))

    @action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        analysis = self.get_object()
        analysis.status = VisionAnalysis.Status.PENDING
        analysis.error_message = ""
        analysis.save(update_fields=("status", "error_message", "updated_at"))
        task = run_vision_analysis.delay(str(analysis.pk))
        return Response({"queued": True, "task_id": task.id}, status=status.HTTP_202_ACCEPTED)
