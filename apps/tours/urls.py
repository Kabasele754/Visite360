from django.urls import path

from .views import (
    PublicPlaceTourView,
    OrgTourListCreateView,
    OrgTourDetailView,
    PublishTourView,
    UnpublishTourView,
    RebuildTourManifestView,
    OrgSceneListCreateView,
    OrgSceneDetailView,
    OrgHotspotListCreateView,
    OrgHotspotDetailView,
    OrgTourPhotoListCreateView,
    OrgTourPhotoDetailView,
)

urlpatterns = [
    # public
    path(
        "public/places/<slug:slug>/tour/",
        PublicPlaceTourView.as_view(),
        name="public-place-tour",
    ),

    # tours
    path(
        "admin/orgs/<slug:organization_slug>/tours/",
        OrgTourListCreateView.as_view(),
        name="org-tour-list-create",
    ),
    path(
        "admin/orgs/<slug:organization_slug>/tours/<int:id>/",
        OrgTourDetailView.as_view(),
        name="org-tour-detail",
    ),
    path(
        "admin/orgs/<slug:organization_slug>/tours/<int:id>/publish/",
        PublishTourView.as_view(),
        name="org-tour-publish",
    ),
    path(
        "admin/orgs/<slug:organization_slug>/tours/<int:id>/unpublish/",
        UnpublishTourView.as_view(),
        name="org-tour-unpublish",
    ),
    path(
        "admin/orgs/<slug:organization_slug>/tours/<int:id>/rebuild-manifest/",
        RebuildTourManifestView.as_view(),
        name="org-tour-rebuild-manifest",
    ),

    # scenes
    path(
        "admin/orgs/<slug:organization_slug>/tours/<int:tour_id>/scenes/",
        OrgSceneListCreateView.as_view(),
        name="org-scene-list-create",
    ),
    path(
        "admin/orgs/<slug:organization_slug>/scenes/<int:id>/",
        OrgSceneDetailView.as_view(),
        name="org-scene-detail",
    ),

    # hotspots
    path(
        "admin/orgs/<slug:organization_slug>/scenes/<int:scene_id>/hotspots/",
        OrgHotspotListCreateView.as_view(),
        name="org-hotspot-list-create",
    ),
    path(
        "admin/orgs/<slug:organization_slug>/hotspots/<int:id>/",
        OrgHotspotDetailView.as_view(),
        name="org-hotspot-detail",
    ),

    # photos
    path(
        "admin/orgs/<slug:organization_slug>/tours/<int:tour_id>/photos/",
        OrgTourPhotoListCreateView.as_view(),
        name="org-tour-photo-list-create",
    ),
    path(
        "admin/orgs/<slug:organization_slug>/photos/<int:id>/",
        OrgTourPhotoDetailView.as_view(),
        name="org-tour-photo-detail",
    ),
]