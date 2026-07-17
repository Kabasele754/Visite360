from __future__ import annotations

from collections import Counter
from decimal import Decimal

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Avg, Count, F, Q, Sum
from django.urls import reverse
from django.utils import timezone

from .models import (
    BackInStockSubscription,
    CustomerNotification,
    Order,
    OrderItem,
    OrderStatusHistory,
    Product,
    ProductRecommendation,
)


STATUS_TITLES = {
    Order.Status.PENDING: "Order placed",
    Order.Status.CONFIRMED: "Payment confirmed",
    Order.Status.PREPARING: "Preparing your order",
    Order.Status.READY_FOR_PICKUP: "Ready for pickup",
    Order.Status.OUT_FOR_DELIVERY: "Out for delivery",
    Order.Status.DELIVERED: "Delivered",
    Order.Status.CANCELLED: "Cancelled",
}


def notification_kind_for_status(status):
    if status == Order.Status.CONFIRMED:
        return CustomerNotification.Kind.PAYMENT
    if status in {Order.Status.READY_FOR_PICKUP, Order.Status.OUT_FOR_DELIVERY, Order.Status.DELIVERED}:
        return CustomerNotification.Kind.DELIVERY
    return CustomerNotification.Kind.ORDER


def create_customer_notification(*, user, title, message, kind, order=None, product=None, organization=None, action_url=""):
    if not user:
        return None
    return CustomerNotification.objects.create(
        user=user,
        title=title,
        message=message,
        kind=kind,
        order=order,
        product=product,
        organization=organization,
        action_url=action_url,
    )


def send_notification_email(notification):
    if not notification or notification.email_sent_at or not notification.user.email:
        return False
    send_mail(
        notification.title,
        notification.message,
        getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@twinscopes.com"),
        [notification.user.email],
        fail_silently=True,
    )
    notification.email_sent_at = timezone.now()
    notification.save(update_fields=["email_sent_at", "updated_at"])
    return True


@transaction.atomic
def transition_order(order, status, *, changed_by=None, note="", customer_visible=True, send_email=True):
    order = Order.objects.select_for_update().select_related("customer", "organization").get(pk=order.pk)
    previous = order.status
    if previous == status and order.status_history.filter(status=status).exists():
        return order

    order.status = status
    order.save(update_fields=["status", "updated_at"])

    title = STATUS_TITLES.get(status, order.get_status_display())
    history = OrderStatusHistory.objects.create(
        order=order,
        status=status,
        title=title,
        note=note,
        changed_by=changed_by,
        customer_visible=customer_visible,
    )

    notification = create_customer_notification(
        user=order.customer,
        title=title,
        message=note or f"Order {order.reference} is now {order.get_status_display().lower()}.",
        kind=notification_kind_for_status(status),
        order=order,
        organization=order.organization,
        action_url=reverse("vendors:customer_order_detail", args=[order.reference]),
    )
    if notification and send_email:
        send_notification_email(notification)
        history.notified_at = timezone.now()
        history.save(update_fields=["notified_at", "updated_at"])
    return order


def ensure_initial_order_history(order):
    if not order.status_history.exists():
        OrderStatusHistory.objects.create(
            order=order,
            status=Order.Status.PENDING,
            title=STATUS_TITLES[Order.Status.PENDING],
            note="We received your order.",
        )


def recommend_products(product, limit=8):
    cached = (
        ProductRecommendation.objects.filter(
            source_product=product,
            recommended_product__status=Product.Status.ACTIVE,
            is_active=True,
        )
        .select_related("recommended_product", "recommended_product__organization")
        .order_by("-score")[:limit]
    )
    cached_products = [item.recommended_product for item in cached if item.recommended_product_id]
    if cached_products:
        return cached_products

    purchased_order_ids = OrderItem.objects.filter(product=product).values_list("order_id", flat=True)
    co_purchased = (
        Product.objects.filter(
            order_items__order_id__in=purchased_order_ids,
            status=Product.Status.ACTIVE,
        )
        .exclude(pk=product.pk)
        .annotate(co_count=Count("order_items", distinct=True))
        .order_by("-co_count", "-order_count", "-created_at")
    )
    results = list(co_purchased[:limit])
    if len(results) < limit:
        fallback = Product.objects.filter(status=Product.Status.ACTIVE).exclude(
            pk__in=[product.pk, *[item.pk for item in results]]
        )
        if product.category_id:
            fallback = fallback.filter(category_id=product.category_id)
        results.extend(list(fallback.order_by("-is_featured", "-order_count", "-created_at")[: limit - len(results)]))
    return results


def rebuild_product_recommendations(organization):
    ProductRecommendation.objects.filter(organization=organization, generated_by="rules").delete()
    products = list(organization.products.filter(status=Product.Status.ACTIVE))
    created = 0
    for product in products:
        for position, recommendation in enumerate(recommend_products(product, limit=5), start=1):
            ProductRecommendation.objects.create(
                organization=organization,
                source_product=product,
                recommended_product=recommendation,
                kind=ProductRecommendation.Kind.FREQUENTLY_BOUGHT,
                score=Decimal(str(max(0.1, 1 - position * 0.12))),
                title=f"Recommend {recommendation.name} with {product.name}",
                rationale="Generated from category, popularity and co-purchase signals.",
                generated_by="rules",
            )
            created += 1
    return created


def notify_back_in_stock(product):
    if not product.in_stock:
        return 0
    subscriptions = product.stock_subscriptions.filter(is_active=True, notified_at__isnull=True)
    sent = 0
    for subscription in subscriptions:
        send_mail(
            f"{product.name} is back in stock",
            f"{product.name} is available again on Twinscopes.",
            getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@twinscopes.com"),
            [subscription.email],
            fail_silently=True,
        )
        subscription.notified_at = timezone.now()
        subscription.is_active = False
        subscription.save(update_fields=["notified_at", "is_active", "updated_at"])
        if subscription.user_id:
            create_customer_notification(
                user=subscription.user,
                title="Product back in stock",
                message=f"{product.name} is available again.",
                kind=CustomerNotification.Kind.STOCK,
                product=product,
                organization=product.organization,
                action_url=reverse("vendors:product_detail", args=[product.organization.slug, product.slug]),
            )
        sent += 1
    return sent
