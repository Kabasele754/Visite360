from django.urls import path
from .dashboard_views import tour_builder_view, tour_list_view

urlpatterns = [
    
     path(
        "dashboard/o/<slug:organization_slug>/tours/",
        tour_list_view,
        name="dashboard-tours-list",
    ),

    path(
        "o/<slug:organization_slug>/tours/<int:tour_id>/builder/",
        tour_builder_view,
        name="tour-builder",
    ),
]