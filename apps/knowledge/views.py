from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from apps.knowledge.models import FAQItem, KnowledgeDocument, KnowledgeSource, ServiceOffering
from apps.knowledge.serializers import (
    FAQItemSerializer,
    KnowledgeDocumentSerializer,
    KnowledgeSourceSerializer,
    ServiceOfferingSerializer,
)
from apps.knowledge.services.search import semantic_search
from apps.knowledge.tasks import sync_knowledge_source
from apps.organizations.models import Organization
from apps.organizations.selectors import get_user_organizations


class OrganizationScopedViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    organization_field = "organization"

    def organizations(self):
        return get_user_organizations(self.request.user)

    def get_queryset(self):
        return self.queryset.filter(**{f"{self.organization_field}__in": self.organizations()})

    def perform_create(self, serializer):
        organization = serializer.validated_data.get("organization")
        if organization not in self.organizations():
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You are not a member of this organization.")
        serializer.save()


class KnowledgeSourceViewSet(OrganizationScopedViewSet):
    queryset = KnowledgeSource.objects.all()
    serializer_class = KnowledgeSourceSerializer
    filterset_fields = ("organization", "source_type", "status", "is_active")
    search_fields = ("name", "url")

    @action(detail=True, methods=["post"])
    def sync(self, request, pk=None):
        source = self.get_object()
        async_result = sync_knowledge_source.delay(source.pk)
        return Response({"queued": True, "task_id": async_result.id}, status=status.HTTP_202_ACCEPTED)


class KnowledgeDocumentViewSet(OrganizationScopedViewSet):
    queryset = KnowledgeDocument.objects.select_related("source", "source__organization")
    serializer_class = KnowledgeDocumentSerializer
    organization_field = "source__organization"
    http_method_names = ("get", "patch", "head", "options")
    filterset_fields = ("source", "is_active", "language")
    search_fields = ("title", "canonical_url", "clean_content")


class FAQItemViewSet(OrganizationScopedViewSet):
    queryset = FAQItem.objects.all()
    serializer_class = FAQItemSerializer
    filterset_fields = ("organization", "category", "locale", "is_active")
    search_fields = ("question", "answer")


class ServiceOfferingViewSet(OrganizationScopedViewSet):
    queryset = ServiceOffering.objects.all()
    serializer_class = ServiceOfferingSerializer
    filterset_fields = ("organization", "category", "is_active")
    search_fields = ("name", "short_description", "description")


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def search(request):
    organization = Organization.objects.filter(
        pk=request.data.get("organization_id"),
        memberships__user=request.user,
        memberships__is_active=True,
    ).first()
    if request.user.is_superuser:
        organization = Organization.objects.filter(pk=request.data.get("organization_id")).first()
    if not organization:
        return Response({"detail": "Organization not found or forbidden."}, status=404)
    query = str(request.data.get("query", "")).strip()
    if not query:
        return Response({"detail": "query is required"}, status=400)
    hits = semantic_search(
        organization=organization,
        query=query,
        limit=min(int(request.data.get("limit", 8)), 20),
    )
    return Response({
        "query": query,
        "results": [
            {
                "chunk_id": hit.chunk_id,
                "document_id": hit.document_id,
                "title": hit.title,
                "source": hit.source_name,
                "content": hit.content,
                "url": hit.url,
                "score": round(hit.score, 4),
                "metadata": hit.metadata,
            }
            for hit in hits
        ],
    })
