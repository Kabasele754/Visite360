from django.contrib import admin

from .models import (
    AppointmentRequest,
    AppointmentType,
    BackInStockSubscription,
    CustomerBehaviorEvent,
    CustomerNotification,
    DeliveryZone,
    IntelligentAgent,
    IntelligentAgentRun,
    IntelligentRecommendation,
    MarketDataSource,
    MarketInsightReport,
    Order,
    OrderItem,
    OrderStatusHistory,
    Product,
    ProductCategory,
    ProductImage,
    ProductRecommendation,
    ProductReview,
    ProductReviewImage,
    StockReservation,
    VendorProfile,
    WebVitalMeasurement,
)


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name", "organization", "category", "price", "currency",
        "stock_quantity", "status", "is_featured", "created_at",
    )
    list_filter = ("status", "is_featured", "currency", "category", "organization")
    search_fields = ("name", "sku", "organization__name", "description")
    autocomplete_fields = ("organization", "category")
    list_select_related = ("organization", "category")
    actions = ("activate_products", "archive_products", "feature_products", "unfeature_products")
    inlines = (ProductImageInline,)

    @admin.action(description="Activate selected products")
    def activate_products(self, request, queryset):
        queryset.update(status=Product.Status.ACTIVE)

    @admin.action(description="Archive selected products")
    def archive_products(self, request, queryset):
        queryset.update(status=Product.Status.ARCHIVED)

    @admin.action(description="Feature selected products")
    def feature_products(self, request, queryset):
        queryset.update(is_featured=True)

    @admin.action(description="Remove Featured from selected products")
    def unfeature_products(self, request, queryset):
        queryset.update(is_featured=False)


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "slug", "description")
    prepopulated_fields = {"slug": ("name",)}


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product", "product_name", "quantity", "unit_price", "line_total")


class OrderStatusHistoryInline(admin.TabularInline):
    model = OrderStatusHistory
    extra = 0
    readonly_fields = ("created_at", "notified_at")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "reference", "organization", "customer_name", "total", "currency",
        "status", "payment_status", "fulfillment", "created_at",
    )
    list_filter = ("status", "payment_status", "fulfillment", "currency", "organization")
    search_fields = ("reference", "customer_name", "customer_email", "organization__name")
    list_select_related = ("organization", "customer", "delivery_zone")
    inlines = (OrderItemInline, OrderStatusHistoryInline)


@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = ("product", "customer", "rating", "status", "created_at")
    list_filter = ("status", "rating", "product__organization")
    search_fields = ("product__name", "customer__email", "comment")
    list_select_related = ("product", "customer", "order_item")


@admin.register(DeliveryZone)
class DeliveryZoneAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "country_code", "province", "currency", "fee", "is_active")
    list_filter = ("country_code", "province", "currency", "is_active")
    search_fields = ("name", "organization__name", "cities", "postal_codes")


@admin.register(StockReservation)
class StockReservationAdmin(admin.ModelAdmin):
    list_display = ("product", "quantity", "status", "expires_at", "order")
    list_filter = ("status",)
    search_fields = ("product__name", "session_key", "order__reference")


@admin.register(CustomerNotification)
class CustomerNotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "kind", "read_at", "email_sent_at", "created_at")
    list_filter = ("kind", "read_at", "email_sent_at")
    search_fields = ("title", "message", "user__email")


@admin.register(ProductRecommendation)
class ProductRecommendationAdmin(admin.ModelAdmin):
    list_display = ("title", "organization", "kind", "score", "generated_by", "is_active")
    list_filter = ("kind", "generated_by", "is_active", "organization")
    search_fields = ("title", "rationale", "source_product__name", "recommended_product__name")


@admin.register(WebVitalMeasurement)
class WebVitalMeasurementAdmin(admin.ModelAdmin):
    list_display = ("name", "value", "rating", "page_path", "device", "created_at")
    list_filter = ("name", "rating", "device")
    search_fields = ("page_path", "session_key")


admin.site.register([
    VendorProfile,
    AppointmentType,
    AppointmentRequest,
    MarketDataSource,
    MarketInsightReport,
    CustomerBehaviorEvent,
    IntelligentAgent,
    IntelligentAgentRun,
    IntelligentRecommendation,
    ProductReviewImage,
    BackInStockSubscription,
])
