from django.urls import path

from . import views

urlpatterns = [
    path("dashboard/control-center/", views.overview, name="platform-console-overview"),
    path("dashboard/control-center/<slug:resource_key>/", views.resource_list, name="platform-console-resource-list"),
    path("dashboard/control-center/<slug:resource_key>/create/", views.resource_create, name="platform-console-resource-create"),
    path("dashboard/control-center/<slug:resource_key>/<str:pk>/edit/", views.resource_edit, name="platform-console-resource-edit"),
    path("dashboard/control-center/<slug:resource_key>/<str:pk>/delete/", views.resource_delete, name="platform-console-resource-delete"),
    path("dashboard/control-center/<slug:resource_key>/<str:pk>/", views.resource_detail, name="platform-console-resource-detail"),
]
