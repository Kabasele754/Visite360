from django.urls import path
from .views import PublicTourListAPIView, PublicTourHeroAPIView, PublicTourDetailAPIView, PublicTourEngagementAPIView

urlpatterns = [
    path("tours/", PublicTourListAPIView.as_view(), name="api-public-tour-list"),
    path("tours/hero/", PublicTourHeroAPIView.as_view(), name="api-public-tour-hero"),
    path("tours/<slug:organization_slug>/<int:tour_id>/", PublicTourDetailAPIView.as_view(), name="api-public-tour-detail"),
    path("tours/<slug:organization_slug>/<int:tour_id>/engagement/", PublicTourEngagementAPIView.as_view(), name="api-public-tour-engagement"),
]
