from django.urls import path
from .dashboard_views import (
    organization_list_view,
    organization_create_view,
    organization_edit_view,
    organization_delete_view,
)

urlpatterns = [
    path("dashboard/organizations/", organization_list_view, name="dashboard-organizations-list"),
    path("dashboard/organizations/create/", organization_create_view, name="dashboard-organizations-create"),
    path("dashboard/organizations/<slug:organization_slug>/edit/", organization_edit_view, name="dashboard-organizations-edit"),
    path("dashboard/organizations/<slug:organization_slug>/delete/", organization_delete_view, name="dashboard-organizations-delete"),
]