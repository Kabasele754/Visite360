from django.urls import path
from .dashboard_views import (
    studio_home_view,
    tour_bulk_delete_view,
    tour_duplicate_view,
    tour_list_partial_view,
    tour_list_view,
    tour_create_view,
    tour_edit_view,
    tour_delete_view,
    tour_builder_view,
    tour_preview_view,
    tour_toggle_featured_view,
    tour_toggle_status_view,
    update_tour_ajax_view,
    upload_hotspot_image_ajax_view,
    upload_scenes_ajax_view,
    update_scene_ajax_view,
    create_hotspot_ajax_view,
    update_hotspot_ajax_view,
    delete_hotspot_ajax_view,
    reorder_scenes_ajax_view,
)

urlpatterns = [
    path("dashboard/studio/", studio_home_view, name="dashboard-studio-home"),

     path("<slug:organization_slug>/tours/", tour_list_view, name="dashboard-tours-list"),
    path("<slug:organization_slug>/tours/partial/", tour_list_partial_view, name="dashboard-tours-partial"),
    path("<slug:organization_slug>/tours/create/", tour_create_view, name="dashboard-tours-create"),
    path("<slug:organization_slug>/tours/bulk-delete/", tour_bulk_delete_view, name="dashboard-tours-bulk-delete"),
    path("<slug:organization_slug>/tours/<int:tour_id>/edit/", tour_edit_view, name="dashboard-tours-edit"),
    path("<slug:organization_slug>/tours/<int:tour_id>/delete/", tour_delete_view, name="dashboard-tours-delete"),
    path("<slug:organization_slug>/tours/<int:tour_id>/duplicate/", tour_duplicate_view, name="dashboard-tours-duplicate"),
    path("<slug:organization_slug>/tours/<int:tour_id>/toggle-status/", tour_toggle_status_view, name="dashboard-tours-toggle-status"),
    path("<slug:organization_slug>/tours/<int:tour_id>/toggle-featured/", tour_toggle_featured_view, name="dashboard-tours-toggle-featured"),

    
    path(
        "dashboard/o/<slug:organization_slug>/tours/<int:tour_id>/builder/",
        tour_builder_view,
        name="tour-builder",
    ),
    path(
        "dashboard/o/<slug:organization_slug>/tours/<int:tour_id>/preview/",
        tour_preview_view,
        name="tour-preview",
    ),
    
      path(
        "<slug:organization_slug>/tours/<int:tour_id>/preview/",
        tour_preview_view,
        name="tour-preview",
    ),  path(
        "<slug:organization_slug>/tours/<int:tour_id>/preview/",
        tour_preview_view,
        name="tour-preview-public",
    ),

    path(
        "dashboard/o/<slug:organization_slug>/tours/<int:tour_id>/upload-scenes/",
        upload_scenes_ajax_view,
        name="dashboard-upload-scenes-ajax",
    ),
    path(
        "dashboard/o/<slug:organization_slug>/tours/<int:tour_id>/reorder-scenes/",
        reorder_scenes_ajax_view,
        name="dashboard-reorder-scenes-ajax",
    ),
    path(
        "dashboard/o/<slug:organization_slug>/scenes/<int:scene_id>/update/",
        update_scene_ajax_view,
        name="dashboard-update-scene-ajax",
    ),
    path(
        "dashboard/o/<slug:organization_slug>/scenes/<int:scene_id>/create-hotspot/",
        create_hotspot_ajax_view,
        name="dashboard-create-hotspot-ajax",
    ),
    path(
        "dashboard/o/<slug:organization_slug>/hotspots/<int:hotspot_id>/update/",
        update_hotspot_ajax_view,
        name="dashboard-update-hotspot-ajax",
    ),
    path(
    "dashboard/o/<slug:organization_slug>/hotspots/<int:hotspot_id>/upload-image/",
    upload_hotspot_image_ajax_view,
    name="dashboard-upload-hotspot-image-ajax",
),
    path(
        "dashboard/o/<slug:organization_slug>/hotspots/<int:hotspot_id>/delete/",
        delete_hotspot_ajax_view,
        name="dashboard-delete-hotspot-ajax",
    ),
]