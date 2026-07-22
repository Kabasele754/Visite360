from django.urls import include, path
from rest_framework.routers import DefaultRouter
from apps.ai_agents.views import AgentDefinitionViewSet, AgentRunViewSet

router = DefaultRouter()
router.register("definitions", AgentDefinitionViewSet, basename="agent-definition")
router.register("runs", AgentRunViewSet, basename="agent-run")
urlpatterns = [path("", include(router.urls))]
