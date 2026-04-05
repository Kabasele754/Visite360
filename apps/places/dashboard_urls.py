from django.urls import path
from .dashboard_views import (
    place_list_view,
    place_create_view,
    place_edit_view,
    place_delete_view,
    place_publish_view,
    place_unpublish_view,
    place_archive_view,
)

urlpatterns = [
    path("dashboard/o/<slug:organization_slug>/places/", place_list_view, name="dashboard-places-list"),
    path("dashboard/o/<slug:organization_slug>/places/create/", place_create_view, name="dashboard-places-create"),
    path("dashboard/o/<slug:organization_slug>/places/<int:place_id>/edit/", place_edit_view, name="dashboard-places-edit"),
    path("dashboard/o/<slug:organization_slug>/places/<int:place_id>/delete/", place_delete_view, name="dashboard-places-delete"),
    path("dashboard/o/<slug:organization_slug>/places/<int:place_id>/publish/", place_publish_view, name="dashboard-places-publish"),
    path("dashboard/o/<slug:organization_slug>/places/<int:place_id>/unpublish/", place_unpublish_view, name="dashboard-places-unpublish"),
    path("dashboard/o/<slug:organization_slug>/places/<int:place_id>/archive/", place_archive_view, name="dashboard-places-archive"),
]

