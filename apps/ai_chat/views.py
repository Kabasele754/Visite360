from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.ai_chat.models import ConversationFeedback, EnterpriseConversation
from apps.ai_chat.serializers import ConversationFeedbackSerializer, EnterpriseConversationSerializer, EnterpriseMessageSerializer
from apps.ai_chat.services.chat import respond_to_message
from apps.organizations.selectors import get_user_organizations


class EnterpriseConversationViewSet(viewsets.ModelViewSet):
    serializer_class = EnterpriseConversationSerializer
    permission_classes = (permissions.IsAuthenticated,)
    filterset_fields = ("organization", "status", "tour", "scene", "agent")
    search_fields = ("title", "summary", "visitor_id")

    def get_queryset(self):
        return EnterpriseConversation.objects.filter(
            organization__in=get_user_organizations(self.request.user)
        ).select_related("organization", "agent", "tour", "scene").prefetch_related("messages")

    def perform_create(self, serializer):
        organization = serializer.validated_data["organization"]
        if organization not in get_user_organizations(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Forbidden organization.")
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["post"])
    def message(self, request, pk=None):
        conversation = self.get_object()
        text = str(request.data.get("message", "")).strip()
        if not text:
            return Response({"detail": "message is required"}, status=400)
        message = respond_to_message(conversation, text, user=request.user)
        return Response(EnterpriseMessageSerializer(message).data, status=status.HTTP_201_CREATED)


class ConversationFeedbackViewSet(viewsets.ModelViewSet):
    serializer_class = ConversationFeedbackSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        return ConversationFeedback.objects.filter(
            conversation__organization__in=get_user_organizations(self.request.user)
        )

    def perform_create(self, serializer):
        conversation = serializer.validated_data["conversation"]
        if conversation.organization not in get_user_organizations(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Forbidden conversation.")
        serializer.save()
