from django.urls import path
from .views import PublicPlaceMapContextView, OrgPlaceMapContextUpsertView

urlpatterns = [
    path("public/places/<slug:slug>/map-context/", PublicPlaceMapContextView.as_view(), name="public-place-map-context"),
    path("admin/orgs/<slug:organization_slug>/map-context/", OrgPlaceMapContextUpsertView.as_view(), name="org-map-context-upsert"),
]