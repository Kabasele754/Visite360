from django.urls import path
from . import dashboard_views

app_name = "vendor_dashboard"

urlpatterns = [
    path("dashboard/o/<slug:organization_slug>/vendor/", dashboard_views.vendor_dashboard, name="home"),
    path("dashboard/o/<slug:organization_slug>/vendor/products/", dashboard_views.product_list, name="products"),
    path("dashboard/o/<slug:organization_slug>/vendor/products/create/", dashboard_views.product_form, name="product_create"),
    path("dashboard/o/<slug:organization_slug>/vendor/products/<int:product_id>/edit/", dashboard_views.product_form, name="product_edit"),
    path("dashboard/o/<slug:organization_slug>/vendor/orders/", dashboard_views.order_list, name="orders"),
    path("dashboard/o/<slug:organization_slug>/vendor/orders/<str:reference>/", dashboard_views.order_detail, name="order_detail"),
    path("dashboard/o/<slug:organization_slug>/vendor/orders/<str:reference>/status/", dashboard_views.order_status_update, name="order_status_update"),
    path("dashboard/o/<slug:organization_slug>/vendor/delivery-zones/", dashboard_views.delivery_zone_list, name="delivery_zones"),
    path("dashboard/o/<slug:organization_slug>/vendor/delivery-zones/create/", dashboard_views.delivery_zone_form, name="delivery_zone_create"),
    path("dashboard/o/<slug:organization_slug>/vendor/delivery-zones/<int:zone_id>/edit/", dashboard_views.delivery_zone_form, name="delivery_zone_edit"),
    path("dashboard/o/<slug:organization_slug>/vendor/delivery-zones/<int:zone_id>/delete/", dashboard_views.delivery_zone_delete, name="delivery_zone_delete"),
    path("dashboard/o/<slug:organization_slug>/vendor/delivery-zones/seed-south-africa/", dashboard_views.seed_south_africa_zones, name="delivery_zone_seed_za"),
    path("dashboard/o/<slug:organization_slug>/vendor/appointments/", dashboard_views.appointment_list, name="appointments"),
    path("dashboard/o/<slug:organization_slug>/vendor/insights/", dashboard_views.insights, name="insights"),
    path("dashboard/o/<slug:organization_slug>/vendor/intelligent-agents/", dashboard_views.intelligent_agents, name="intelligent_agents"),
    path("dashboard/o/<slug:organization_slug>/vendor/intelligent-agents/rebuild-products/", dashboard_views.rebuild_recommendations, name="rebuild_recommendations"),
    path("dashboard/o/<slug:organization_slug>/vendor/reviews/<int:review_id>/response/", dashboard_views.review_response, name="review_response"),
    path("dashboard/o/<slug:organization_slug>/vendor/intelligent-agents/<slug:agent_code>/run/", dashboard_views.intelligent_agent_run, name="intelligent_agent_run"),
    path("dashboard/o/<slug:organization_slug>/vendor/intelligent-agents/recommendations/<int:recommendation_id>/status/", dashboard_views.intelligent_recommendation_status, name="intelligent_recommendation_status"),
    path("dashboard/o/<slug:organization_slug>/vendor/insights/source/", dashboard_views.source_create, name="source_create"),
    path("dashboard/o/<slug:organization_slug>/vendor/insights/generate/", dashboard_views.generate_insights, name="generate_insights"),
]
