from django.urls import path
from .views import (
    PublicPlaceListView,
    PublicPlaceDetailView,
    OrgPlaceListCreateView,
    OrgPlaceDetailView,
    PublishPlaceView,
)

urlpatterns = [
    path("public/places/", PublicPlaceListView.as_view(), name="public-place-list"),
    path("public/places/<slug:slug>/", PublicPlaceDetailView.as_view(), name="public-place-detail"),

    path("admin/orgs/<slug:organization_slug>/places/", OrgPlaceListCreateView.as_view(), name="org-place-list-create"),
    path("admin/orgs/<slug:organization_slug>/places/<int:id>/", OrgPlaceDetailView.as_view(), name="org-place-detail"),
    path("admin/orgs/<slug:organization_slug>/places/<int:id>/publish/", PublishPlaceView.as_view(), name="org-place-publish"),
]