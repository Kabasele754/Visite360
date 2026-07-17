from __future__ import annotations

import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.common.models import TimeStampedModel
from apps.organizations.models import Organization
from apps.places.models import Place
from apps.tours.models import Tour


def vendor_product_upload_to(instance, filename):
    return f"vendors/{instance.organization.slug}/products/{instance.slug}/{filename}"


def vendor_product_gallery_upload_to(instance, filename):
    return f"vendors/{instance.product.organization.slug}/products/{instance.product.slug}/gallery/{filename}"



class CommerceCurrency(models.TextChoices):
    ZAR = "ZAR", "South African Rand (R)"
    USD = "USD", "US Dollar ($)"
    EUR = "EUR", "Euro (€)"
    GBP = "GBP", "British Pound (£)"
    BWP = "BWP", "Botswana Pula (P)"
    NAD = "NAD", "Namibian Dollar (N$)"
    ZMW = "ZMW", "Zambian Kwacha (K)"
    CDF = "CDF", "Congolese Franc (FC)"
    KES = "KES", "Kenyan Shilling (KSh)"


class AgentRunStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    RUNNING = "running", "Running"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"


class VendorProfile(TimeStampedModel):
    organization = models.OneToOneField(Organization, on_delete=models.CASCADE, related_name="vendor_profile")
    display_name = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    whatsapp = models.CharField(max_length=40, blank=True)
    website_url = models.URLField(blank=True)
    currency = models.CharField(max_length=8, choices=CommerceCurrency.choices, default=CommerceCurrency.USD)
    accepts_orders = models.BooleanField(default=True)
    offers_delivery = models.BooleanField(default=True)
    offers_pickup = models.BooleanField(default=True)
    minimum_order = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    is_verified = models.BooleanField(default=False)

    def __str__(self):
        return self.display_name or self.organization.name


class ProductCategory(TimeStampedModel):
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=32, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)
        verbose_name_plural = "Product categories"

    def __str__(self):
        return self.name


class Product(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        OUT_OF_STOCK = "out_of_stock", "Out of stock"
        ARCHIVED = "archived", "Archived"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="products")
    category = models.ForeignKey(ProductCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name="products")
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280)
    sku = models.CharField(max_length=80, blank=True)
    short_description = models.CharField(max_length=320, blank=True)
    description = models.TextField(blank=True)
    specifications = models.JSONField(default=dict, blank=True)
    cover_image = models.ImageField(upload_to=vendor_product_upload_to, null=True, blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))])
    compare_at_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=8, choices=CommerceCurrency.choices, default=CommerceCurrency.USD)
    stock_quantity = models.PositiveIntegerField(default=0)
    track_inventory = models.BooleanField(default=True)
    delivery_available = models.BooleanField(default=True)
    pickup_available = models.BooleanField(default=True)
    estimated_delivery_days = models.PositiveSmallIntegerField(default=2)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT)
    is_featured = models.BooleanField(default=False)
    view_count = models.PositiveIntegerField(default=0)
    order_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("-is_featured", "-created_at")
        constraints = [models.UniqueConstraint(fields=("organization", "slug"), name="unique_product_slug_per_org")]

    def __str__(self):
        return self.name

    @property
    def in_stock(self):
        return not self.track_inventory or self.stock_quantity > 0


class ProductImage(TimeStampedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="gallery")
    image = models.ImageField(upload_to=vendor_product_gallery_upload_to)
    alt_text = models.CharField(max_length=180, blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("order", "id")


class DeliveryZone(TimeStampedModel):
    SOUTH_AFRICA = "ZA"

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="delivery_zones",
    )
    name = models.CharField(max_length=180)
    country_code = models.CharField(max_length=2, default=SOUTH_AFRICA, db_index=True)
    province = models.CharField(max_length=120, blank=True)
    cities = models.JSONField(default=list, blank=True)
    postal_codes = models.JSONField(default=list, blank=True)
    currency = models.CharField(
        max_length=8,
        choices=CommerceCurrency.choices,
        default=CommerceCurrency.ZAR,
    )
    fee = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    free_delivery_threshold = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    estimated_days_min = models.PositiveSmallIntegerField(default=1)
    estimated_days_max = models.PositiveSmallIntegerField(default=3)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("country_code", "province", "name")
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "name", "country_code"),
                name="unique_delivery_zone_per_org_country",
            )
        ]

    def clean(self):
        self.country_code = (self.country_code or self.SOUTH_AFRICA).strip().upper()
        if self.estimated_days_min > self.estimated_days_max:
            raise ValidationError({
                "estimated_days_max": "Maximum delivery days must be greater than or equal to the minimum."
            })
        self.cities = sorted({
            str(city).strip()
            for city in (self.cities or [])
            if str(city).strip()
        })
        self.postal_codes = sorted({
            str(code).strip()
            for code in (self.postal_codes or [])
            if str(code).strip()
        })

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.is_default:
            DeliveryZone.objects.filter(
                organization=self.organization,
                country_code=self.country_code,
                is_default=True,
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)

    def __str__(self):
        location = self.province or self.country_code
        return f"{self.organization.name} — {self.name} ({location})"

class Order(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        PREPARING = "preparing", "Preparing"
        READY_FOR_PICKUP = "ready_for_pickup", "Ready for pickup"
        OUT_FOR_DELIVERY = "out_for_delivery", "Out for delivery"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    class Fulfillment(models.TextChoices):
        DELIVERY = "delivery", "Delivery"
        PICKUP = "pickup", "Pickup"

    reference = models.CharField(max_length=24, unique=True, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="orders")
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="vendor_orders")
    customer_name = models.CharField(max_length=255)
    customer_email = models.EmailField(blank=True)
    customer_phone = models.CharField(max_length=40)
    fulfillment = models.CharField(max_length=20, choices=Fulfillment.choices, default=Fulfillment.DELIVERY)
    delivery_zone = models.ForeignKey(DeliveryZone, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders")
    delivery_address = models.TextField(blank=True)
    delivery_city = models.CharField(max_length=120, blank=True)
    delivery_suburb = models.CharField(max_length=120, blank=True)
    delivery_province = models.CharField(max_length=120, blank=True)
    delivery_postal_code = models.CharField(max_length=20, blank=True)
    delivery_country_code = models.CharField(max_length=2, default="ZA")
    customer_notes = models.TextField(blank=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    delivery_fee = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=8, choices=CommerceCurrency.choices, default=CommerceCurrency.USD)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PENDING)
    payment_status = models.CharField(max_length=24, default="unpaid")
    payment_provider = models.CharField(max_length=24, default="manual")
    payment_reference = models.CharField(max_length=160, blank=True)
    stripe_checkout_session_id = models.CharField(max_length=255, blank=True)
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True)
    paypal_order_id = models.CharField(max_length=255, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    payment_error = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"TS-{timezone.now():%y%m%d}-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.reference


class OrderItem(TimeStampedModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="order_items")
    product_name = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)



class StockReservation(TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        CONVERTED = "converted", "Converted"
        RELEASED = "released", "Released"
        EXPIRED = "expired", "Expired"

    session_key = models.CharField(max_length=80, db_index=True)
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="stock_reservations",
    )
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="stock_reservations",
    )
    quantity = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ("expires_at",)
        indexes = [
            models.Index(fields=("product", "status", "expires_at")),
            models.Index(fields=("session_key", "status")),
        ]

    def __str__(self):
        return f"{self.product.name} × {self.quantity} ({self.status})"


class AppointmentType(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="appointment_types")
    name = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    duration_minutes = models.PositiveSmallIntegerField(default=30)
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.organization.name} — {self.name}"


class AppointmentRequest(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="appointment_requests")
    tour = models.ForeignKey(Tour, on_delete=models.SET_NULL, null=True, blank=True, related_name="appointment_requests")
    place = models.ForeignKey(Place, on_delete=models.SET_NULL, null=True, blank=True, related_name="vendor_appointment_requests")
    appointment_type = models.ForeignKey(AppointmentType, on_delete=models.SET_NULL, null=True, blank=True, related_name="requests")
    full_name = models.CharField(max_length=255)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40)
    preferred_date = models.DateField(null=True, blank=True)
    preferred_time = models.TimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    source = models.CharField(max_length=40, default="tour")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)


class MarketDataSource(TimeStampedModel):
    class SourceType(models.TextChoices):
        WEBSITE = "website", "Website"
        GOOGLE = "google", "Google Business"
        FACEBOOK = "facebook", "Facebook"
        INSTAGRAM = "instagram", "Instagram"
        TIKTOK = "tiktok", "TikTok"
        LINKEDIN = "linkedin", "LinkedIn"
        MANUAL = "manual", "Manual metrics"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="market_sources")
    source_type = models.CharField(max_length=24, choices=SourceType.choices)
    url = models.URLField(blank=True)
    label = models.CharField(max_length=180, blank=True)
    metrics = models.JSONField(default=dict, blank=True)
    latest_summary = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)


class MarketInsightReport(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="market_reports")
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    input_snapshot = models.JSONField(default=dict, blank=True)
    executive_summary = models.TextField(blank=True)
    strengths = models.JSONField(default=list, blank=True)
    weaknesses = models.JSONField(default=list, blank=True)
    opportunities = models.JSONField(default=list, blank=True)
    recommendations = models.JSONField(default=list, blank=True)
    suggested_campaigns = models.JSONField(default=list, blank=True)
    priority_actions = models.JSONField(default=list, blank=True)
    funnel_diagnosis = models.JSONField(default=dict, blank=True)
    product_recommendations = models.JSONField(default=list, blank=True)
    appointment_strategy = models.JSONField(default=list, blank=True)
    content_calendar = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=24, default="ready")
    model_name = models.CharField(max_length=80, blank=True)


class CustomerBehaviorEvent(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="behavior_events")
    session_key = models.CharField(max_length=80, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="market_behavior_events")
    event_type = models.CharField(max_length=60)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, related_name="behavior_events")
    tour = models.ForeignKey(Tour, on_delete=models.SET_NULL, null=True, blank=True, related_name="commerce_behavior_events")
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("organization", "event_type", "created_at"))]


class IntelligentAgent(TimeStampedModel):
    code = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=160)
    role = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    system_instruction = models.TextField()
    model_name = models.CharField(max_length=100, default="gemini-2.5-flash")
    is_active = models.BooleanField(default=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("order", "name")

    def __str__(self):
        return self.name


class IntelligentAgentRun(TimeStampedModel):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="intelligent_agent_runs",
    )
    agent = models.ForeignKey(
        IntelligentAgent,
        on_delete=models.PROTECT,
        related_name="runs",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requested_intelligent_agent_runs",
    )
    status = models.CharField(
        max_length=20,
        choices=AgentRunStatus.choices,
        default=AgentRunStatus.PENDING,
    )
    input_snapshot = models.JSONField(default=dict, blank=True)
    output = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.organization.name} — {self.agent.name} — {self.status}"


class IntelligentRecommendation(TimeStampedModel):
    class Status(models.TextChoices):
        NEW = "new", "New"
        ACCEPTED = "accepted", "Accepted"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        DISMISSED = "dismissed", "Dismissed"

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="intelligent_recommendations",
    )
    run = models.ForeignKey(
        IntelligentAgentRun,
        on_delete=models.CASCADE,
        related_name="recommendations",
    )
    category = models.CharField(max_length=80, default="growth")
    title = models.CharField(max_length=220)
    rationale = models.TextField(blank=True)
    action = models.TextField()
    impact = models.CharField(max_length=20, default="medium")
    effort = models.CharField(max_length=20, default="medium")
    priority = models.PositiveSmallIntegerField(default=3)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NEW,
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("priority", "-created_at")

    def __str__(self):
        return self.title



class OrderStatusHistory(TimeStampedModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="status_history")
    status = models.CharField(max_length=24, choices=Order.Status.choices)
    title = models.CharField(max_length=180)
    note = models.TextField(blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vendor_order_status_changes",
    )
    customer_visible = models.BooleanField(default=True)
    notified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("created_at",)

    def __str__(self):
        return f"{self.order.reference} — {self.title}"


class CustomerNotification(TimeStampedModel):
    class Kind(models.TextChoices):
        ORDER = "order", "Order"
        PAYMENT = "payment", "Payment"
        DELIVERY = "delivery", "Delivery"
        CART = "cart", "Cart"
        STOCK = "stock", "Stock"
        REVIEW = "review", "Review"
        GENERAL = "general", "General"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="market_notifications",
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_notifications",
    )
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.GENERAL)
    title = models.CharField(max_length=180)
    message = models.TextField()
    action_url = models.CharField(max_length=500, blank=True)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("user", "read_at", "created_at"))]

    @property
    def is_read(self):
        return bool(self.read_at)


class ProductReview(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PUBLISHED = "published", "Published"
        REJECTED = "rejected", "Rejected"

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
    order_item = models.OneToOneField(
        OrderItem,
        on_delete=models.CASCADE,
        related_name="verified_review",
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="product_reviews",
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)],
    )
    comment = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PUBLISHED)
    vendor_response = models.TextField(blank=True)
    vendor_responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("product", "status", "created_at"))]

    def clean(self):
        if self.rating > 5:
            raise ValidationError({"rating": "Rating must be between 1 and 5."})
        if self.order_item.order.status != Order.Status.DELIVERED:
            raise ValidationError("Only delivered orders can be reviewed.")
        if self.order_item.product_id != self.product_id:
            raise ValidationError("The reviewed product does not match the order item.")
        if self.order_item.order.customer_id != self.customer_id:
            raise ValidationError("The review customer does not own this order.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


def product_review_upload_to(instance, filename):
    return f"vendors/reviews/{instance.review.product_id}/{filename}"


class ProductReviewImage(TimeStampedModel):
    review = models.ForeignKey(ProductReview, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to=product_review_upload_to)
    alt_text = models.CharField(max_length=180, blank=True)


class BackInStockSubscription(TimeStampedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="stock_subscriptions")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="stock_subscriptions",
    )
    email = models.EmailField()
    notified_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("product", "email"),
                name="unique_stock_subscription_product_email",
            )
        ]


class ProductRecommendation(TimeStampedModel):
    class Kind(models.TextChoices):
        SIMILAR = "similar", "Similar"
        FREQUENTLY_BOUGHT = "frequently_bought", "Frequently bought together"
        BUNDLE = "bundle", "Bundle"
        CAMPAIGN = "campaign", "Campaign"
        FEATURED = "featured", "Featured"
        DELIVERY = "delivery", "Delivery"

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="product_recommendations",
    )
    source_product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="recommendation_sources",
    )
    recommended_product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="recommendation_targets",
    )
    kind = models.CharField(max_length=32, choices=Kind.choices)
    score = models.DecimalField(max_digits=6, decimal_places=4, default=Decimal("0.0000"))
    title = models.CharField(max_length=220)
    rationale = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    generated_by = models.CharField(max_length=40, default="rules")
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("-score", "-created_at")


class WebVitalMeasurement(TimeStampedModel):
    name = models.CharField(max_length=20)
    value = models.FloatField()
    rating = models.CharField(max_length=20, blank=True)
    page_path = models.CharField(max_length=500)
    navigation_type = models.CharField(max_length=40, blank=True)
    device = models.CharField(max_length=40, blank=True)
    session_key = models.CharField(max_length=80, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="web_vital_measurements",
    )

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("name", "created_at"))]
