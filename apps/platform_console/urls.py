from django.urls import path

from . import views

urlpatterns = [
    path("dashboard/control-center/", views.overview, name="platform-console-overview"),
    path("dashboard/control-center/intelligence/", views.intelligence_hub, name="platform-console-intelligence-hub"),
    path("dashboard/control-center/intelligence/collect/", views.intelligence_bulk_collect, name="platform-console-intelligence-bulk-collect"),
    path("dashboard/control-center/intelligence/organizations/<int:organization_id>/", views.intelligence_organization, name="platform-console-intelligence-organization"),
    path("dashboard/control-center/intelligence/organizations/<int:organization_id>/collect/", views.intelligence_collect, name="platform-console-intelligence-collect"),
    path("dashboard/control-center/intelligence/runs/<uuid:run_id>/", views.intelligence_run, name="platform-console-intelligence-run"),
    path("dashboard/control-center/intelligence/runs/<uuid:run_id>/status/", views.intelligence_run_status, name="platform-console-intelligence-run-status"),
    path("dashboard/control-center/intelligence/runs/<uuid:run_id>/retry/", views.intelligence_run_retry, name="platform-console-intelligence-run-retry"),
    path("dashboard/control-center/intelligence/reviews/<uuid:item_id>/apply/", views.intelligence_review_apply, name="platform-console-intelligence-review-apply"),
    path("dashboard/control-center/intelligence/reviews/<uuid:item_id>/reject/", views.intelligence_review_reject, name="platform-console-intelligence-review-reject"),
    path("dashboard/control-center/intelligence/sources/<int:source_id>/reindex/", views.intelligence_source_reindex, name="platform-console-intelligence-source-reindex"),
    path("dashboard/control-center/<slug:resource_key>/", views.resource_list, name="platform-console-resource-list"),
    path("dashboard/control-center/<slug:resource_key>/create/", views.resource_create, name="platform-console-resource-create"),
    path("dashboard/control-center/<slug:resource_key>/<str:pk>/edit/", views.resource_edit, name="platform-console-resource-edit"),
    path("dashboard/control-center/<slug:resource_key>/<str:pk>/delete/", views.resource_delete, name="platform-console-resource-delete"),
    path("dashboard/control-center/<slug:resource_key>/<str:pk>/", views.resource_detail, name="platform-console-resource-detail"),
]
