from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.ai_core.views import AIProviderConfigurationViewSet, AIRunViewSet, AIUsageDailyViewSet

router = DefaultRouter()
router.register("providers", AIProviderConfigurationViewSet, basename="ai-provider")
router.register("runs", AIRunViewSet, basename="ai-run")
router.register("usage", AIUsageDailyViewSet, basename="ai-usage")

urlpatterns = [path("", include(router.urls))]
