from django.urls import path

from .dashboard_views import (
    studio_home_view,

    tour_list_view,
    tour_list_partial_view,
    tour_create_view,
    tour_edit_view,
    tour_delete_view,
    tour_bulk_delete_view,
    tour_duplicate_view,
    tour_toggle_status_view,
    tour_toggle_featured_view,
    update_tour_ajax_view,

    tour_builder_view,
    tour_preview_view,
    tour_preview_scene_data_view,
    public_hotspot_pdf_view,

    upload_scenes_ajax_view,
    reorder_scenes_ajax_view,
    update_scene_ajax_view,

    create_hotspot_ajax_view,
    update_hotspot_ajax_view,
    upload_hotspot_image_ajax_view,
    upload_hotspot_media_ajax_view,
    delete_hotspot_ajax_view,

    scene_pipeline_status_ajax_view,
    tour_scenes_pipeline_status_ajax_view,
    queue_scene_pipeline_ajax_view,
    queue_tour_prefetch_ajax_view,
    tour_architect_view,
    queue_tour_architect_ajax_view,
    tour_architect_status_ajax_view,
    review_scene_object_ajax_view,
    rerun_scene_intelligence_ajax_view,
    review_scene_link_ajax_view,
    bulk_apply_scene_links_ajax_view,
)


urlpatterns = [
    # ======================================================================
    # STUDIO HOME
    # ======================================================================
    path(
        "dashboard/studio/",
        studio_home_view,
        name="dashboard-studio-home",
    ),

    # ======================================================================
    # TOURS DASHBOARD
    # ======================================================================
    path(
        "<slug:organization_slug>/tours/",
        tour_list_view,
        name="dashboard-tours-list",
    ),
    path(
        "<slug:organization_slug>/tours/partial/",
        tour_list_partial_view,
        name="dashboard-tours-partial",
    ),
    path(
        "<slug:organization_slug>/tours/create/",
        tour_create_view,
        name="dashboard-tours-create",
    ),
    path(
        "<slug:organization_slug>/tours/bulk-delete/",
        tour_bulk_delete_view,
        name="dashboard-tours-bulk-delete",
    ),
    path(
        "<slug:organization_slug>/tours/<int:tour_id>/edit/",
        tour_edit_view,
        name="dashboard-tours-edit",
    ),
    path(
        "<slug:organization_slug>/tours/<int:tour_id>/delete/",
        tour_delete_view,
        name="dashboard-tours-delete",
    ),
    path(
        "<slug:organization_slug>/tours/<int:tour_id>/duplicate/",
        tour_duplicate_view,
        name="dashboard-tours-duplicate",
    ),
    path(
        "<slug:organization_slug>/tours/<int:tour_id>/toggle-status/",
        tour_toggle_status_view,
        name="dashboard-tours-toggle-status",
    ),
    path(
        "<slug:organization_slug>/tours/<int:tour_id>/toggle-featured/",
        tour_toggle_featured_view,
        name="dashboard-tours-toggle-featured",
    ),

    # ======================================================================
    # BUILDER + PREVIEW
    # Important : ces URLs gardent la structure utilisée dans studio_builder.js
    # ======================================================================
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
        "<slug:organization_slug>/tours/<int:tour_id>/scenes/<int:scene_id>/preview-data/",
        tour_preview_scene_data_view,
        name="tour-preview-scene-data",
    ),

    path(
        "<slug:organization_slug>/tours/<int:tour_id>/hotspots/<int:hotspot_id>/document/",
        public_hotspot_pdf_view,
        name="tour-hotspot-pdf-public",
    ),

    # Preview public propre, sans dupliquer le même name que tour-preview
    path(
        "<slug:organization_slug>/tours/<int:tour_id>/preview/",
        tour_preview_view,
        name="tour-preview-public",
    ),

    # Utilisé par studio_builder.js :
    # fetch(`${config.updateTourBaseUrl}${config.tourId}/update/`)
    path(
        "dashboard/o/<slug:organization_slug>/tours/<int:tour_id>/update/",
        update_tour_ajax_view,
        name="dashboard-update-tour-ajax",
    ),

    # ======================================================================
    # SCENES AJAX
    # ======================================================================
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

    # ======================================================================
    # HOTSPOTS AJAX
    # ======================================================================
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
        "dashboard/o/<slug:organization_slug>/hotspots/<int:hotspot_id>/upload-media/",
        upload_hotspot_media_ajax_view,
        name="dashboard-upload-hotspot-media-ajax",
    ),
    path(
        "dashboard/o/<slug:organization_slug>/hotspots/<int:hotspot_id>/delete/",
        delete_hotspot_ajax_view,
        name="dashboard-delete-hotspot-ajax",
    ),


    # ======================================================================
    # AI TOUR ARCHITECT
    # ======================================================================
    path(
        "dashboard/o/<slug:organization_slug>/tours/<int:tour_id>/architect/",
        tour_architect_view,
        name="dashboard-tour-architect",
    ),
    path(
        "dashboard/o/<slug:organization_slug>/tours/<int:tour_id>/architect/run/",
        queue_tour_architect_ajax_view,
        name="dashboard-tour-architect-run-ajax",
    ),
    path(
        "dashboard/o/<slug:organization_slug>/tours/<int:tour_id>/architect/runs/<uuid:run_id>/status/",
        tour_architect_status_ajax_view,
        name="dashboard-tour-architect-status-ajax",
    ),
    path(
        "dashboard/o/<slug:organization_slug>/architect/objects/<int:candidate_id>/review/",
        review_scene_object_ajax_view,
        name="dashboard-scene-object-review-ajax",
    ),
    path(
        "dashboard/o/<slug:organization_slug>/architect/scenes/<int:scene_id>/rerun/",
        rerun_scene_intelligence_ajax_view,
        name="dashboard-scene-intelligence-rerun-ajax",
    ),
    path(
        "dashboard/o/<slug:organization_slug>/architect/links/<int:proposal_id>/review/",
        review_scene_link_ajax_view,
        name="dashboard-scene-link-review-ajax",
    ),
    path(
        "dashboard/o/<slug:organization_slug>/tours/<int:tour_id>/architect/apply-safe/",
        bulk_apply_scene_links_ajax_view,
        name="dashboard-tour-architect-apply-safe-ajax",
    ),

    # ======================================================================
    # PIPELINE / CELERY / PREFETCH
    # ======================================================================
    path(
        "dashboard/o/<slug:organization_slug>/tours/<int:tour_id>/pipeline-status/",
        tour_scenes_pipeline_status_ajax_view,
        name="dashboard-tour-scenes-pipeline-status-ajax",
    ),
    path(
        "dashboard/o/<slug:organization_slug>/scenes/<int:scene_id>/pipeline-status/",
        scene_pipeline_status_ajax_view,
        name="dashboard-scene-pipeline-status-ajax",
    ),
    path(
        "dashboard/o/<slug:organization_slug>/scenes/<int:scene_id>/queue-pipeline/",
        queue_scene_pipeline_ajax_view,
        name="dashboard-queue-scene-pipeline-ajax",
    ),
    path(
        "dashboard/o/<slug:organization_slug>/tours/<int:tour_id>/queue-prefetch/",
        queue_tour_prefetch_ajax_view,
        name="dashboard-queue-tour-prefetch-ajax",
    ),
]