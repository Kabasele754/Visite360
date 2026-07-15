from django.urls import path

from . import canonical_views, views

app_name = "apps.app_streetview"

urlpatterns = [
    # Optional page shell
    path("", canonical_views.publisher_page, name="publisher"),


    # Canonical publisher: uses existing Organization / Place / Tour / Scene360
    # It does not duplicate tours, scenes or images. It only stores Google publication state.
    path("source/organizations/", canonical_views.organizations, name="source_organizations"),
    path("source/organizations/<int:org_id>/places/", canonical_views.organization_places, name="source_organization_places"),
    path("source/places/<int:place_id>/tours/", canonical_views.place_tours, name="source_place_tours"),
    path("source/tours/<int:tour_id>/", canonical_views.source_tour_detail, name="source_tour_detail"),
    path("source/tours/<int:tour_id>/apply-place-gps/", canonical_views.source_apply_place_gps, name="source_apply_place_gps"),
    path("source/tours/<int:tour_id>/auto-link/", canonical_views.source_auto_link, name="source_auto_link"),
    path("source/tours/<int:tour_id>/quality-check/", canonical_views.source_quality_check, name="source_quality_check"),
    path("source/tours/<int:tour_id>/smart-link/", canonical_views.source_smart_link, name="source_smart_link"),
    path("source/tours/<int:tour_id>/smart-link/apply/", canonical_views.source_apply_smart_link, name="source_apply_smart_link"),
    path("source/tours/<int:tour_id>/history/", canonical_views.source_history, name="source_history"),
    path("source/tours/<int:tour_id>/analytics/", canonical_views.source_analytics, name="source_analytics"),
    path("source/tours/<int:tour_id>/connections/", canonical_views.source_connections, name="source_connections"),
    path("source/tours/<int:tour_id>/connections/add/", canonical_views.source_add_connection, name="source_add_connection"),
    path("source/tours/<int:tour_id>/connections/<int:hotspot_id>/delete/", canonical_views.source_delete_connection, name="source_delete_connection"),
    path("source/tours/<int:tour_id>/publish/", canonical_views.source_publish_tour, name="source_publish_tour"),
    path("source/tours/<int:tour_id>/publish/background/", canonical_views.source_publish_tour_background, name="source_publish_tour_background"),
    path("source/publish-jobs/<uuid:job_public_id>/", canonical_views.source_publish_job_status, name="source_publish_job_status"),
    path("source/tours/<int:tour_id>/retry-connections/", canonical_views.source_retry_connections, name="source_retry_connections"),
    path("source/tours/<int:tour_id>/share-links/", canonical_views.source_share_links, name="source_share_links"),
    path("source/scenes/<int:source_scene_id>/state/", canonical_views.source_scene_state_update, name="source_scene_state_update"),
    path("source/scenes/<int:source_scene_id>/mark-published/", canonical_views.source_mark_scene_published, name="source_mark_scene_published"),
    path("source/scenes/<int:source_scene_id>/delete-google-photo/", canonical_views.source_delete_google_photo, name="source_delete_google_photo"),

    # Google published photo library for connected account
    path("published/google-photos/", canonical_views.google_published_photos, name="google_published_photos"),
    path("published/google-photos/delete/", canonical_views.google_delete_published_photo, name="google_delete_published_photo"),
    path("published/google-photos/link-scene/", canonical_views.google_link_photo_to_scene, name="google_link_photo_to_scene"),
    path("published/google-photos/update-pose/", canonical_views.google_update_published_photo_pose, name="google_update_published_photo_pose"),

    # Config / Google OAuth
    path("config/", views.streetview_config, name="config"),
    path("google/status/", views.google_account_status, name="google_status"),
    path("google/disconnect/", views.google_disconnect, name="google_disconnect"),
    path("oauth/start/", views.google_oauth_start, name="oauth_start"),
    path("oauth/callback/", views.google_oauth_callback, name="oauth_callback"),

    # Tours
    path("tours/", views.list_tours, name="list_tours"),
    path("tours/create/", views.create_tour, name="create_tour"),
    path("tours/<int:tour_id>/", views.tour_detail, name="tour_detail"),
    path("tours/<int:tour_id>/update/", views.update_tour, name="update_tour"),
    path("tours/<int:tour_id>/delete/", views.delete_tour, name="delete_tour"),

    # Scenes / editor payload
    path("tours/<int:tour_id>/upload-scenes/", views.upload_scenes, name="upload_scenes"),
    path("scenes/<int:scene_id>/update/", views.update_scene, name="update_scene"),
    path("scenes/<int:scene_id>/delete/", views.delete_scene, name="delete_scene"),
    path("tours/<int:tour_id>/save-connections/", views.save_connections, name="save_connections"),
    path("tours/<int:tour_id>/save-hotspots/", views.save_hotspots, name="save_hotspots"),
    path("tours/<int:tour_id>/save-project/", views.save_project_payload, name="save_project_payload"),
    path("tours/<int:tour_id>/export-json/", views.export_project_json, name="export_project_json"),

    # Google Street View publication / sharing / connection helpers
    path("tours/<int:tour_id>/publish/", views.publish_tour, name="publish_tour"),
    path("tours/<int:tour_id>/auto-connect/", views.auto_connect_scenes, name="auto_connect_scenes"),
    path("tours/<int:tour_id>/retry-connections/", views.retry_google_connections, name="retry_google_connections"),
    path("tours/<int:tour_id>/share-links/", views.tour_share_links, name="tour_share_links"),
    path("scenes/<int:scene_id>/mark-published/", views.mark_scene_published, name="mark_scene_published"),
    path("scenes/<int:scene_id>/clear-google/", views.clear_scene_google_publication, name="clear_scene_google_publication"),
    path("scenes/<int:scene_id>/google-status/", views.scene_google_status, name="scene_google_status"),
    path("scenes/<int:scene_id>/update-google-camera/", views.update_google_camera, name="update_google_camera"),
    path("publish-jobs/<uuid:job_public_id>/", views.publish_job_status, name="publish_job_status"),
]
