from __future__ import annotations

from collections import OrderedDict
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .models import Product, StockReservation


RESERVATION_MINUTES = 15


def group_cart_rows(rows):
    groups = OrderedDict()
    for row in rows:
        organization = row["product"].organization
        group = groups.setdefault(
            organization.pk,
            {
                "organization": organization,
                "rows": [],
                "subtotal": Decimal("0.00"),
                "currency": row["product"].currency,
                "item_count": 0,
                "product_count": 0,
            },
        )
        group["rows"].append(row)
        group["subtotal"] += row["line_total"]
        group["item_count"] += row["quantity"]
        group["product_count"] += 1
    return list(groups.values())


def available_stock(product):
    if not product.track_inventory:
        return 99
    reserved = (
        product.stock_reservations.filter(
            status=StockReservation.Status.ACTIVE,
            expires_at__gt=timezone.now(),
        )
        .aggregate(total=Sum("quantity"))["total"]
        or 0
    )
    return max(0, product.stock_quantity - reserved)


@transaction.atomic
def reserve_rows(session_key, rows):
    now = timezone.now()
    expires_at = now + timedelta(minutes=RESERVATION_MINUTES)

    StockReservation.objects.filter(
        session_key=session_key,
        status=StockReservation.Status.ACTIVE,
    ).update(status=StockReservation.Status.RELEASED)

    reservations = []
    for row in rows:
        product = Product.objects.select_for_update().get(pk=row["product"].pk)
        if product.track_inventory:
            already_reserved = (
                StockReservation.objects.filter(
                    product=product,
                    status=StockReservation.Status.ACTIVE,
                    expires_at__gt=now,
                ).aggregate(total=Sum("quantity"))["total"]
                or 0
            )
            available = max(0, product.stock_quantity - already_reserved)
            if row["quantity"] > available:
                raise ValueError(
                    f"Only {available} unit(s) of {product.name} are currently available."
                )

        reservations.append(
            StockReservation.objects.create(
                session_key=session_key,
                product=product,
                quantity=row["quantity"],
                expires_at=expires_at,
            )
        )
    return reservations


def release_expired_reservations():
    return StockReservation.objects.filter(
        status=StockReservation.Status.ACTIVE,
        expires_at__lte=timezone.now(),
    ).update(status=StockReservation.Status.EXPIRED)
