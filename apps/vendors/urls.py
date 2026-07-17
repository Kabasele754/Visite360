from django.urls import path
from . import views, admin_dashboard_views

app_name = "vendors"

urlpatterns = [
    path("dashboard/", views.account_entry, name="dashboard_compat"),
    path("account/entry/", views.account_entry, name="account_entry"),
    path("dashboard/marketplace/", admin_dashboard_views.marketplace_admin_home, name="marketplace_admin_home"),
    path("dashboard/marketplace/products/", admin_dashboard_views.marketplace_admin_products, name="marketplace_admin_products"),
    path("dashboard/marketplace/products/<int:product_id>/action/", admin_dashboard_views.marketplace_admin_product_action, name="marketplace_admin_product_action"),
    path("dashboard/marketplace/categories/", admin_dashboard_views.marketplace_admin_categories, name="marketplace_admin_categories"),
    path("dashboard/marketplace/categories/create/", admin_dashboard_views.marketplace_admin_category_form, name="marketplace_admin_category_create"),
    path("dashboard/marketplace/categories/<int:category_id>/edit/", admin_dashboard_views.marketplace_admin_category_form, name="marketplace_admin_category_edit"),
    path("dashboard/marketplace/orders/", admin_dashboard_views.marketplace_admin_orders, name="marketplace_admin_orders"),
    path("dashboard/marketplace/reviews/", admin_dashboard_views.marketplace_admin_reviews, name="marketplace_admin_reviews"),
    path("dashboard/marketplace/reviews/<int:review_id>/action/", admin_dashboard_views.marketplace_admin_review_action, name="marketplace_admin_review_action"),
    path("dashboard/marketplace/system/", admin_dashboard_views.marketplace_admin_system, name="marketplace_admin_system"),
    path("api/vendors/<slug:organization_slug>/products/", views.organization_products_api, name="organization_products_api"),
    path("products/", views.product_list, name="product_list"),
    path("api/products/suggest/", views.product_search_suggestions, name="product_search_suggestions"),
    path("products/<slug:organization_slug>/<slug:product_slug>/", views.product_detail, name="product_detail"),
    path("cart/", views.cart_detail, name="cart_detail"),
    path("cart/summary/", views.cart_summary, name="cart_summary"),
    path("cart/add/<int:product_id>/", views.cart_add, name="cart_add"),
    path("cart/update/<int:product_id>/", views.cart_update, name="cart_update"),
    path("cart/remove/<int:product_id>/", views.cart_remove, name="cart_remove"),
    path("checkout/", views.checkout, name="checkout"),
    path("checkout/vendor/<slug:organization_slug>/", views.checkout, name="checkout_vendor"),
    path("orders/<str:reference>/payment/", views.payment_page, name="payment_page"),
    path("orders/<str:reference>/stripe/embedded-session/", views.stripe_embedded_session, name="stripe_embedded_session"),
    path("orders/<str:reference>/paypal/create/", views.paypal_create_order_api, name="paypal_create_order_api"),
    path("orders/<str:reference>/paypal/capture/", views.paypal_capture_order_api, name="paypal_capture_order_api"),
    path("orders/<str:reference>/stripe/success/", views.stripe_success, name="stripe_success"),
    path("orders/<str:reference>/paypal/return/", views.paypal_return, name="paypal_return"),
    path("webhooks/stripe/", views.stripe_webhook, name="stripe_webhook"),
    path("api/behavior/", views.behavior_event, name="behavior_event"),
    path("orders/<str:reference>/success/", views.order_success, name="order_success"),
    path("account/orders/", views.customer_orders, name="customer_orders"),
    path("account/notifications/", views.customer_notifications, name="customer_notifications"),
    path("account/notifications/<int:notification_id>/read/", views.customer_notification_read, name="customer_notification_read"),
    path("reviews/order-item/<int:order_item_id>/", views.product_review_create, name="product_review_create"),
    path("products/<int:product_id>/back-in-stock/", views.back_in_stock_subscribe, name="back_in_stock_subscribe"),
    path("account/orders/<str:reference>/", views.customer_order_detail, name="customer_order_detail"),
    path("account/activate/<uidb64>/<token>/", views.customer_activate, name="customer_activate"),
    path("api/appointments/tour/<int:tour_id>/", views.tour_appointment_create, name="tour_appointment_create"),
]

urlpatterns += [
    path("manifest.webmanifest", views.pwa_manifest, name="pwa_manifest"),
    path("service-worker.js", views.pwa_service_worker, name="pwa_service_worker"),
    path("offline/", views.pwa_offline, name="pwa_offline"),
    path("api/performance/web-vitals/", views.web_vital_collect, name="web_vital_collect"),
]
