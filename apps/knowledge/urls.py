from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.knowledge.views import (
    FAQItemViewSet,
    KnowledgeDocumentViewSet,
    KnowledgeSourceViewSet,
    ServiceOfferingViewSet,
    search,
)

router = DefaultRouter()
router.register("sources", KnowledgeSourceViewSet, basename="knowledge-source")
router.register("documents", KnowledgeDocumentViewSet, basename="knowledge-document")
router.register("faqs", FAQItemViewSet, basename="knowledge-faq")
router.register("services", ServiceOfferingViewSet, basename="knowledge-service")

urlpatterns = [path("search/", search, name="knowledge-search"), path("", include(router.urls))]
