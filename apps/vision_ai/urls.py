from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.vision_ai.views import VisionAnalysisViewSet

router = DefaultRouter()
router.register("analyses", VisionAnalysisViewSet, basename="vision-analysis")
urlpatterns = [path("", include(router.urls))]
