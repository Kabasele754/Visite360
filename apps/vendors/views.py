from __future__ import annotations

import json
from django.conf import settings
from django.http import HttpResponse, JsonResponse, HttpResponseBadRequest
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.db import transaction
from django.db.models import F, Q, Avg, Count
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.core.paginator import Paginator
from django.urls import reverse
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.http import require_POST

from apps.tours.models import Tour
from apps.organizations.models import Organization
from .forms import AppointmentRequestForm, CheckoutForm, CustomerActivateForm, ProductReviewForm
from .models import (
    AppointmentRequest,
    BackInStockSubscription,
    CustomerBehaviorEvent,
    CustomerNotification,
    Order,
    OrderItem,
    OrderStatusHistory,
    Product,
    ProductCategory,
    ProductReview,
    ProductReviewImage,
    StockReservation,
    WebVitalMeasurement,
)
from .customer_accounts import (
    apply_stripe_customer_id, attach_existing_customer, provision_customer_after_payment,
    send_customer_activation,
)
from .payment_services import stripe_enabled
from .cart_services import group_cart_rows, reserve_rows
from .commerce_services import ensure_initial_order_history, recommend_products

CART_KEY = "vendor_cart_v1"


def _cart(request):
    return request.session.setdefault(CART_KEY, {})


def _cart_rows(request, organization_id=None):
    raw = _cart(request)
    ids = [int(value) for value in raw.keys() if str(value).isdigit()]
    products = Product.objects.select_related("organization", "category").filter(
        id__in=ids, status=Product.Status.ACTIVE
    )
    if organization_id is not None:
        products = products.filter(organization_id=organization_id)
    rows, subtotal = [], Decimal("0.00")
    changed = False
    for product in products:
        requested = max(1, int(raw.get(str(product.id), 1)))
        max_qty = product.stock_quantity if product.track_inventory else 99
        qty = min(requested, max_qty) if max_qty > 0 else 0
        if qty <= 0:
            raw.pop(str(product.id), None)
            changed = True
            continue
        if qty != requested:
            raw[str(product.id)] = qty
            changed = True
        line_total = product.price * qty
        subtotal += line_total
        rows.append({"product": product, "quantity": qty, "line_total": line_total, "max_quantity": max_qty})
    if changed:
        request.session.modified = True
    return rows, subtotal


def product_list(request):
    base_qs = Product.objects.select_related("organization", "category").filter(
        status=Product.Status.ACTIVE
    )
    q = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()
    organization = request.GET.get("organization", "").strip()
    city = request.GET.get("city", "").strip()
    availability = request.GET.get("availability", "").strip()
    delivery = request.GET.get("delivery", "").strip()
    featured = request.GET.get("featured", "").strip()
    ordering = request.GET.get("ordering", "popular").strip()
    min_price = request.GET.get("min_price", "").strip()
    max_price = request.GET.get("max_price", "").strip()

    filtered = base_qs
    if q:
        filtered = filtered.filter(
            Q(name__icontains=q)
            | Q(description__icontains=q)
            | Q(short_description__icontains=q)
            | Q(sku__icontains=q)
            | Q(organization__name__icontains=q)
            | Q(category__name__icontains=q)
        )
    if category:
        filtered = filtered.filter(category__slug=category)
    if organization:
        filtered = filtered.filter(organization__slug=organization)
    if city:
        filtered = filtered.filter(organization__delivery_zones__cities__icontains=city).distinct()
    if availability == "in_stock":
        filtered = filtered.filter(Q(track_inventory=False) | Q(stock_quantity__gt=0))
    if delivery == "delivery":
        filtered = filtered.filter(delivery_available=True)
    elif delivery == "pickup":
        filtered = filtered.filter(pickup_available=True)
    if featured in {"1", "true", "yes"}:
        filtered = filtered.filter(is_featured=True)
    try:
        if min_price:
            filtered = filtered.filter(price__gte=min_price)
        if max_price:
            filtered = filtered.filter(price__lte=max_price)
    except Exception:
        pass

    ordering_map = {
        "popular": ("-order_count", "-view_count", "-created_at"),
        "newest": ("-created_at",),
        "price_low": ("price", "-created_at"),
        "price_high": ("-price", "-created_at"),
        "featured": ("-is_featured", "-order_count", "-created_at"),
    }
    filtered = filtered.order_by(*ordering_map.get(ordering, ordering_map["popular"]))

    featured_products = list(filtered.filter(is_featured=True).prefetch_related("gallery")[:10])
    regular_qs = filtered.exclude(pk__in=[item.pk for item in featured_products])

    paginator = Paginator(regular_qs, 16)
    page_obj = paginator.get_page(request.GET.get("page") or 1)
    context = {
        "products": page_obj.object_list,
        "featured_products": featured_products,
        "page_obj": page_obj,
        "has_next": page_obj.has_next(),
        "next_page_number": page_obj.next_page_number() if page_obj.has_next() else None,
        "total_products": filtered.count(),
        "regular_products_count": paginator.count,
        "categories": ProductCategory.objects.filter(is_active=True),
        "organizations": Organization.objects.filter(products__status=Product.Status.ACTIVE).distinct().order_by("name"),
        "selected_q": q,
        "selected_category": category,
        "selected_organization": organization,
        "selected_city": city,
        "selected_availability": availability,
        "selected_delivery": delivery,
        "selected_featured": featured,
        "selected_ordering": ordering,
        "selected_min_price": min_price,
        "selected_max_price": max_price,
        "active_market_nav": "products",
        "active_public_nav": "products",
        "show_search": True,
    }
    if request.headers.get("x-requested-with") == "XMLHttpRequest" or request.GET.get("format") == "json":
        html = render_to_string("public/products/_grid_items.html", context, request=request)
        return JsonResponse({
            "html": html,
            "has_next": context["has_next"],
            "next_page": context["next_page_number"],
            "count": paginator.count,
        })
    return render(request, "public/products/list.html", context)


def product_search_suggestions(request):
    q = request.GET.get("q", "").strip()
    if len(q) < 2:
        return JsonResponse({"results": []})
    products = (
        Product.objects.filter(status=Product.Status.ACTIVE)
        .filter(
            Q(name__icontains=q)
            | Q(sku__icontains=q)
            | Q(category__name__icontains=q)
            | Q(organization__name__icontains=q)
        )
        .select_related("organization", "category")
        .order_by("-is_featured", "-order_count", "-view_count")[:8]
    )
    return JsonResponse({
        "results": [
            {
                "type": "product",
                "label": item.name,
                "meta": f"{item.organization.name} · {item.currency} {item.price}",
                "image": item.cover_image.url if item.cover_image else "",
                "url": reverse("vendors:product_detail", args=[item.organization.slug, item.slug]),
            }
            for item in products
        ]
    })
def product_detail(request, organization_slug, product_slug):
    product = get_object_or_404(
        Product.objects.select_related("organization", "category").prefetch_related("gallery"),
        organization__slug=organization_slug,
        slug=product_slug,
        status=Product.Status.ACTIVE,
    )
    Product.objects.filter(pk=product.pk).update(view_count=F("view_count") + 1)
    if not request.session.session_key:
        request.session.save()
    CustomerBehaviorEvent.objects.create(
        organization=product.organization,
        product=product,
        user=request.user if request.user.is_authenticated else None,
        session_key=request.session.session_key or "",
        event_type="view_product",
    )

    related_products = list(
        Product.objects.select_related("organization", "category")
        .filter(
            organization=product.organization,
            status=Product.Status.ACTIVE,
        )
        .exclude(pk=product.pk)
        .order_by("-is_featured", "-order_count", "-created_at")[:6]
    )

    similar_qs = Product.objects.select_related("organization", "category").filter(
        status=Product.Status.ACTIVE,
    ).exclude(pk=product.pk)
    if product.category_id:
        similar_qs = similar_qs.filter(category_id=product.category_id)
    else:
        similar_qs = similar_qs.exclude(organization=product.organization)
    similar_products = recommend_products(product, limit=8)
    # Intelligent virtual-tour recommendations:
    # 1) tours from the same company;
    # 2) featured/high-performing tours as similarity fallback.
    company_tours = list(
        Tour.objects.select_related("organization", "place")
        .prefetch_related("scenes")
        .filter(
            organization=product.organization,
            status=Tour.Status.PUBLISHED,
        )
        .order_by("-is_featured", "-view_count", "-created_at")[:4]
    )

    excluded_tour_ids = [tour.id for tour in company_tours]
    similar_tours_qs = (
        Tour.objects.select_related("organization", "place")
        .prefetch_related("scenes")
        .filter(status=Tour.Status.PUBLISHED)
        .exclude(pk__in=excluded_tour_ids)
    )

    product_terms = " ".join(
        value for value in [
            product.name,
            product.short_description,
            product.category.name if product.category_id else "",
            product.organization.name,
        ] if value
    ).split()

    similarity_filter = Q()
    for term in product_terms[:8]:
        if len(term) >= 4:
            similarity_filter |= (
                Q(title__icontains=term)
                | Q(description__icontains=term)
                | Q(place__name__icontains=term)
                | Q(location__icontains=term)
            )

    if similarity_filter:
        similar_tours_qs = similar_tours_qs.filter(similarity_filter)

    similar_tours = list(
        similar_tours_qs
        .order_by("-is_featured", "-rating", "-view_count", "-created_at")[:4]
    )

    # If keyword similarity gives too few results, complete with the best
    # published tours from other companies.
    if len(similar_tours) < 4:
        fallback_ids = excluded_tour_ids + [tour.id for tour in similar_tours]
        fallback_tours = list(
            Tour.objects.select_related("organization", "place")
            .prefetch_related("scenes")
            .filter(status=Tour.Status.PUBLISHED)
            .exclude(pk__in=fallback_ids)
            .order_by("-is_featured", "-rating", "-view_count", "-created_at")[
                : 4 - len(similar_tours)
            ]
        )
        similar_tours.extend(fallback_tours)

    reviews = product.reviews.filter(status=ProductReview.Status.PUBLISHED).select_related("customer").prefetch_related("images")
    review_summary = reviews.aggregate(average=Avg("rating"), total=Count("id"))
    reviewable_item = None
    if request.user.is_authenticated:
        reviewable_item = (
            OrderItem.objects.filter(
                product=product,
                order__customer=request.user,
                order__status=Order.Status.DELIVERED,
            )
            .exclude(verified_review__isnull=False)
            .select_related("order")
            .first()
        )

    return render(request, "public/products/detail.html", {
        "product": product,
        "related_products": related_products,
        "similar_products": similar_products,
        "company_tours": company_tours,
        "similar_tours": similar_tours,
        "marketplace_contact_email": getattr(settings, "TWINSCOPE_CONTACT_EMAIL", "contact@twinscopes.com"),
        "marketplace_contact_phone": getattr(settings, "TWINSCOPE_CONTACT_PHONE", ""),
        "marketplace_whatsapp": str(getattr(settings, "TWINSCOPE_WHATSAPP", "")).replace("+", "").replace(" ", "").replace("-", ""),
        "marketplace_maps_url": getattr(settings, "TWINSCOPE_MAPS_URL", ""),
        "reviews": reviews,
        "review_summary": review_summary,
        "reviewable_item": reviewable_item,
        "active_market_nav": "products",
    })

@require_POST
@transaction.atomic
def cart_add(request, product_id):
    product = get_object_or_404(
        Product.objects.select_for_update(),
        pk=product_id,
        status=Product.Status.ACTIVE,
    )
    requested = max(1, min(99, int(request.POST.get("quantity", 1))))
    max_qty = product.stock_quantity if product.track_inventory else 99
    cart = _cart(request)
    current = int(cart.get(str(product.id), 0))
    qty = min(current + requested, max_qty)
    if qty <= 0:
        messages.error(request, "This product is out of stock.")
        return redirect(request.POST.get("next") or "vendors:cart_detail")
    cart[str(product.id)] = qty
    request.session.modified = True
    if not request.session.session_key: request.session.save()
    CustomerBehaviorEvent.objects.create(organization=product.organization, product=product, user=request.user if request.user.is_authenticated else None, session_key=request.session.session_key or "", event_type="add_to_cart", metadata={"quantity": requested})
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "ok": True,
            "count": len([key for key, value in cart.items() if int(value or 0) > 0]),
            "quantity": qty,
            "max_quantity": max_qty,
            "stock_remaining": max(0, max_qty - qty) if product.track_inventory else None,
            "item_count": sum(int(value or 0) for value in cart.values()),
            "message": f"{product.name} added to your cart.",
            "cart_url": reverse("vendors:cart_detail"),
        })
    return redirect(request.POST.get("next") or "vendors:cart_detail")


@require_POST
def cart_update(request, product_id):
    product = get_object_or_404(Product, pk=product_id, status=Product.Status.ACTIVE)
    cart = _cart(request)
    try:
        qty = int(request.POST.get("quantity", 1))
    except (TypeError, ValueError):
        qty = 1
    max_qty = product.stock_quantity if product.track_inventory else 99
    qty = max(0, min(max_qty or 0, qty))
    if qty <= 0:
        cart.pop(str(product.id), None)
    else:
        cart[str(product.id)] = qty
    request.session.modified = True
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        rows, subtotal = _cart_rows(request)
        row = next((item for item in rows if item["product"].id == product.id), None)
        return JsonResponse({
            "ok": True,
            "count": len([key for key, value in cart.items() if int(value or 0) > 0]),
            "subtotal": str(subtotal),
            "quantity": row["quantity"] if row else 0,
            "line_total": str(row["line_total"]) if row else "0.00",
            "max_quantity": product.stock_quantity if product.track_inventory else 99,
            "removed": row is None,
            "currency": product.currency,
            "item_count": sum(int(value or 0) for value in cart.values()),
            "stock_remaining": max(0, max_qty - qty) if product.track_inventory else None,
        })
    return redirect("vendors:cart_detail")


@require_POST
def cart_remove(request, product_id):
    cart = _cart(request)
    cart.pop(str(product_id), None)
    request.session.modified = True
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        rows, subtotal = _cart_rows(request)
        return JsonResponse({
            "ok": True,
            "count": len([key for key, value in cart.items() if int(value or 0) > 0]),
            "item_count": sum(int(value or 0) for value in cart.values()),
            "subtotal": str(subtotal),
            "removed_product_id": product_id,
        })
    return redirect("vendors:cart_detail")


def cart_detail(request):
    rows, subtotal = _cart_rows(request)
    groups = group_cart_rows(rows)
    return render(request, "public/products/cart.html", {
        "cart_rows": rows,
        "cart_groups": groups,
        "subtotal": subtotal,
        "cart_item_count": sum(row["quantity"] for row in rows),
        "active_market_nav": "cart",
        "mobile_back": True,
    })


def cart_summary(request):
    rows, subtotal = _cart_rows(request)
    return JsonResponse({
        "ok": True,
        "product_count": len(rows),
        "item_count": sum(row["quantity"] for row in rows),
        "subtotal": str(subtotal),
        "items": [
            {
                "id": row["product"].id,
                "name": row["product"].name,
                "organization": row["product"].organization.name,
                "organization_slug": row["product"].organization.slug,
                "slug": row["product"].slug,
                "currency": row["product"].currency,
                "unit_price": str(row["product"].price),
                "quantity": row["quantity"],
                "line_total": str(row["line_total"]),
                "max_quantity": row["max_quantity"],
                "image": row["product"].cover_image.url if row["product"].cover_image else "",
                "update_url": reverse("vendors:cart_update", args=[row["product"].id]),
                "remove_url": reverse("vendors:cart_remove", args=[row["product"].id]),
            }
            for row in rows
        ],
        "cart_url": reverse("vendors:cart_detail"),
    })


@transaction.atomic
def checkout(request, organization_slug=None):
    organization_filter = None
    if organization_slug:
        organization_filter = get_object_or_404(Organization, slug=organization_slug).pk
    rows, subtotal = _cart_rows(request, organization_id=organization_filter)
    if not rows:
        return redirect("vendors:cart_detail")
    organizations = {row["product"].organization_id for row in rows}
    if len(organizations) != 1:
        messages.error(request, "Choose one vendor group to continue to checkout.")
        return redirect("vendors:cart_detail")

    organization = rows[0]["product"].organization
    initial = {}
    if request.user.is_authenticated:
        user = request.user
        full_name = user.get_full_name().strip() if hasattr(user, "get_full_name") else ""
        initial.update({
            "customer_name": full_name or getattr(user, "username", ""),
            "customer_email": getattr(user, "email", "") or "",
            "customer_phone": getattr(user, "phone", "") or "",
        })

    form = CheckoutForm(request.POST or None, initial=initial)
    available_methods = []
    if stripe_enabled():
        available_methods.append(("stripe", "Credit or debit card"))
    if settings.PAYPAL_CLIENT_ID and settings.PAYPAL_SECRET:
        available_methods.append(("paypal", "PayPal"))
    available_methods.append(("manual", "Pay on delivery / pickup"))
    form.fields["payment_method"].choices = available_methods
    active_delivery_zones = organization.delivery_zones.filter(is_active=True)
    form.fields["delivery_zone"].queryset = active_delivery_zones
    if not active_delivery_zones.exists():
        form.fields["delivery_zone"].help_text = (
            "This vendor has not configured delivery zones yet. Choose pickup or contact the vendor."
        )

    if request.method == "GET":
        if not request.session.session_key:
            request.session.save()
        CustomerBehaviorEvent.objects.create(
            organization=organization,
            user=request.user if request.user.is_authenticated else None,
            session_key=request.session.session_key or "",
            event_type="begin_checkout",
            metadata={"items": sum(row["quantity"] for row in rows), "subtotal": str(subtotal)},
        )

    if request.method == "POST" and form.is_valid():
        if not request.session.session_key:
            request.session.save()
        try:
            reservations = reserve_rows(request.session.session_key, rows)
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("vendors:cart_detail")

        stock_errors = []
        for row in rows:
            product = Product.objects.select_for_update().get(pk=row["product"].pk)
            if product.track_inventory and product.stock_quantity < row["quantity"]:
                stock_errors.append(
                    f"Only {product.stock_quantity} unit(s) of {product.name} remain in stock."
                )
        if stock_errors:
            for error in stock_errors:
                messages.error(request, error)
            return redirect("vendors:cart_detail")

        order = form.save(commit=False)
        order.organization = organization
        order.customer = request.user if request.user.is_authenticated else None
        order.subtotal = subtotal
        order.currency = rows[0]["product"].currency
        zone = order.delivery_zone
        order.delivery_fee = (
            zone.fee
            if zone and order.fulfillment == Order.Fulfillment.DELIVERY
            else Decimal("0.00")
        )
        if zone and zone.free_delivery_threshold and subtotal >= zone.free_delivery_threshold:
            order.delivery_fee = Decimal("0.00")
        order.total = order.subtotal + order.delivery_fee
        order.payment_provider = form.cleaned_data.get("payment_method", "stripe")
        order.save()
        ensure_initial_order_history(order)
        StockReservation.objects.filter(
            pk__in=[reservation.pk for reservation in reservations]
        ).update(order=order)

        # Existing emails are linked to the existing account instead of creating duplicates.
        if not order.customer_id:
            attach_existing_customer(order)

        for row in rows:
            product = Product.objects.select_for_update().get(pk=row["product"].pk)
            OrderItem.objects.create(
                order=order,
                product=product,
                product_name=product.name,
                quantity=row["quantity"],
                unit_price=product.price,
                line_total=row["line_total"],
            )
            updates = {"order_count": F("order_count") + row["quantity"]}
            if product.track_inventory:
                updates["stock_quantity"] = F("stock_quantity") - row["quantity"]
            Product.objects.filter(pk=product.pk).update(**updates)

        StockReservation.objects.filter(
            pk__in=[reservation.pk for reservation in reservations]
        ).update(status=StockReservation.Status.CONVERTED)

        cart = _cart(request)
        for row in rows:
            cart.pop(str(row["product"].id), None)
        request.session.modified = True
        request.session["latest_order_reference"] = order.reference
        if order.payment_provider == "manual":
            order.payment_status = "pending_manual"
            order.save(update_fields=["payment_status", "updated_at"])
            if not order.customer_id:
                provision_customer_after_payment(order, request)
            return redirect("vendors:order_success", reference=order.reference)
        return redirect("vendors:payment_page", reference=order.reference)

    return render(request, "public/products/checkout.html", {
        "form": form,
        "cart_rows": rows,
        "subtotal": subtotal,
        "organization": organization,
        "active_market_nav": "cart",
        "mobile_back": True,
        "stripe_enabled": stripe_enabled(),
        "paypal_enabled": bool(settings.PAYPAL_CLIENT_ID and settings.PAYPAL_SECRET),
        "has_delivery_zones": active_delivery_zones.exists(),
    })


def payment_page(request, reference):
    order = get_object_or_404(
        Order.objects.prefetch_related("items__product"),
        reference=reference,
    )
    if order.payment_status == "paid":
        return redirect("vendors:order_success", reference=order.reference)

    selected_provider = (
        request.GET.get("provider")
        or order.payment_provider
        or "stripe"
    )
    return render(request, "public/products/payment.html", {
        "order": order,
        "active_market_nav": "cart",
        "mobile_back": True,
        "stripe_enabled": stripe_enabled(),
        "stripe_publishable_key": getattr(settings, "STRIPE_PUBLISHABLE_KEY", ""),
        "paypal_enabled": bool(settings.PAYPAL_CLIENT_ID and settings.PAYPAL_SECRET),
        "paypal_client_id": getattr(settings, "PAYPAL_CLIENT_ID", ""),
        "selected_provider": selected_provider,
    })


@require_POST
def stripe_embedded_session(request, reference):
    order = get_object_or_404(Order.objects.prefetch_related("items"), reference=reference)
    if order.payment_status == "paid":
        return JsonResponse({
            "ok": True,
            "paid": True,
            "redirect_url": reverse("vendors:order_success", kwargs={"reference": order.reference}),
        })
    try:
        from .payment_services import create_stripe_embedded_checkout
        client_secret = create_stripe_embedded_checkout(request, order)
        return JsonResponse({"ok": True, "client_secret": client_secret})
    except Exception as exc:
        order.payment_error = str(exc)[:1000]
        order.save(update_fields=["payment_error", "updated_at"])
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)


@require_POST
def paypal_create_order_api(request, reference):
    order = get_object_or_404(Order.objects.prefetch_related("items"), reference=reference)
    if order.payment_status == "paid":
        return JsonResponse({
            "ok": True,
            "paid": True,
            "redirect_url": reverse("vendors:order_success", kwargs={"reference": order.reference}),
        })
    try:
        from .payment_services import create_paypal_order_for_sdk
        paypal_order_id = create_paypal_order_for_sdk(order)
        return JsonResponse({"ok": True, "id": paypal_order_id})
    except Exception as exc:
        order.payment_error = str(exc)[:1000]
        order.save(update_fields=["payment_error", "updated_at"])
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)


@require_POST
def paypal_capture_order_api(request, reference):
    order = get_object_or_404(Order, reference=reference)
    try:
        payload = json.loads(request.body or b"{}")
    except Exception:
        payload = {}
    paypal_order_id = payload.get("order_id") or order.paypal_order_id
    try:
        from .payment_services import capture_paypal_order
        data = capture_paypal_order(order, paypal_order_id)
        if data.get("status") != "COMPLETED":
            return JsonResponse({
                "ok": False,
                "error": "PayPal has not completed the payment yet.",
            }, status=409)
        _mark_order_paid(
            order,
            "paypal",
            payment_reference=data.get("id", ""),
            request=request,
        )
        return JsonResponse({
            "ok": True,
            "redirect_url": reverse(
                "vendors:order_success",
                kwargs={"reference": order.reference},
            ),
        })
    except Exception as exc:
        order.payment_error = str(exc)[:1000]
        order.save(update_fields=["payment_error", "updated_at"])
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

def _mark_order_paid(order, provider, payment_reference="", payment_intent="", stripe_customer="", request=None):
    if order.payment_status == "paid":
        return order
    order.payment_status = "paid"
    order.status = Order.Status.CONFIRMED
    order.payment_provider = provider
    order.payment_reference = payment_reference
    if payment_intent:
        order.stripe_payment_intent_id = payment_intent
    order.paid_at = timezone.now()
    order.payment_error = ""
    order.save()
    result = provision_customer_after_payment(order, request)
    if stripe_customer:
        apply_stripe_customer_id(result.user, stripe_customer)
    CustomerBehaviorEvent.objects.create(
        organization=order.organization,
        user=order.customer,
        session_key=request.session.session_key if request and request.session.session_key else "",
        event_type="purchase",
        metadata={"order": order.reference, "total": str(order.total), "provider": provider},
    )
    return order


def stripe_success(request, reference):
    order = get_object_or_404(Order, reference=reference)
    session_id = request.GET.get("session_id", "")
    if session_id and settings.STRIPE_SECRET_KEY:
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            if (
                session.payment_status == "paid"
                and (session.metadata or {}).get("order_reference") == order.reference
            ):
                _mark_order_paid(
                    order,
                    "stripe",
                    payment_reference=session.id,
                    payment_intent=str(session.payment_intent or ""),
                    stripe_customer=str(session.customer or ""),
                    request=request,
                )
        except stripe.error.StripeError as exc:
            order.payment_error = exc.user_message or str(exc)
            order.save(update_fields=["payment_error", "updated_at"])
            messages.error(request, "Stripe payment confirmation is still pending.")
    order.refresh_from_db(fields=["customer", "payment_status"])
    if order.payment_status == "paid" and order.customer_id:
        customer = order.customer
        if not customer.has_usable_password() and not getattr(customer, "email_verified_at", None):
            send_customer_activation(customer, request)
    return redirect("vendors:order_success", reference=order.reference)


def paypal_return(request, reference):
    order = get_object_or_404(Order, reference=reference)
    try:
        from .payment_services import capture_paypal_order
        data = capture_paypal_order(order)
        if data.get("status") == "COMPLETED":
            _mark_order_paid(
                order,
                "paypal",
                payment_reference=data.get("id", ""),
                request=request,
            )
    except Exception as exc:
        order.payment_error = str(exc)[:1000]
        order.save(update_fields=["payment_error", "updated_at"])
        messages.error(request, "PayPal payment could not be confirmed.")
        return redirect("vendors:payment_page", reference=order.reference)
    return redirect("vendors:order_success", reference=order.reference)


@csrf_exempt
def stripe_webhook(request):
    import stripe
    webhook_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "") or ""
    if not webhook_secret.startswith("whsec_"):
        return HttpResponse("Stripe signing secret is not configured.", status=503)
    try:
        event = stripe.Webhook.construct_event(
            request.body,
            request.META.get("HTTP_STRIPE_SIGNATURE", ""),
            webhook_secret,
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        return HttpResponse(status=400)

    if event.get("type") in {"checkout.session.completed", "checkout.session.async_payment_succeeded"}:
        obj = event["data"]["object"]
        ref = (obj.get("metadata") or {}).get("order_reference")
        if ref:
            order = Order.objects.filter(reference=ref).first()
            if order:
                _mark_order_paid(
                    order,
                    "stripe",
                    payment_reference=obj.get("id", ""),
                    payment_intent=obj.get("payment_intent", "") or "",
                    stripe_customer=obj.get("customer", "") or "",
                    request=None,
                )
    return HttpResponse(status=200)


@require_POST
def behavior_event(request):
    try: payload=json.loads(request.body or b"{}")
    except Exception: payload=request.POST.dict()
    org_id=payload.get("organization_id"); product_id=payload.get("product_id"); tour_id=payload.get("tour_id")
    if not org_id: return JsonResponse({"ok":False},status=400)
    if not request.session.session_key: request.session.save()
    CustomerBehaviorEvent.objects.create(organization_id=org_id,session_key=request.session.session_key or "",user=request.user if request.user.is_authenticated else None,event_type=str(payload.get("event_type","unknown"))[:60],product_id=product_id or None,tour_id=tour_id or None,metadata=payload.get("metadata") or {})
    return JsonResponse({"ok":True})


def order_success(request, reference):
    order = get_object_or_404(Order.objects.prefetch_related("items"), reference=reference)
    return render(request, "public/products/order_success.html", {
        "order": order,
        "customer_account_created": bool(order.customer_id and not request.user.is_authenticated),
    })


@login_required
def customer_orders(request):
    orders = Order.objects.filter(customer=request.user).select_related("organization").prefetch_related("items").order_by("-created_at")
    return render(request, "public/account/orders.html", {"orders": orders, "active_market_nav": "account"})


@login_required
def customer_order_detail(request, reference):
    order = get_object_or_404(
        Order.objects.select_related("organization").prefetch_related("items", "status_history"),
        reference=reference,
        customer=request.user,
    )
    return render(request, "public/account/order_detail.html", {"order": order, "active_market_nav": "account"})


def customer_activate(request, uidb64, token):
    User = get_user_model()
    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(uidb64)))
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    if user is None or not default_token_generator.check_token(user, token):
        return render(request, "public/account/activate.html", {"invalid": True})
    form = CustomerActivateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user.set_password(form.cleaned_data["new_password1"])
        user.email_verified_at = timezone.now()
        user.is_customer = True
        user.save(update_fields=["password", "email_verified_at", "is_customer"])
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(request, "Your customer account is ready.")
        return redirect("vendors:customer_orders")
    return render(request, "public/account/activate.html", {"form": form, "invalid": False})


@require_POST
def tour_appointment_create(request, tour_id):
    tour = get_object_or_404(Tour.objects.select_related("organization", "place"), pk=tour_id)
    form = AppointmentRequestForm(request.POST)
    form.fields["appointment_type"].queryset = tour.organization.appointment_types.filter(is_active=True)
    if form.is_valid():
        appointment = form.save(commit=False)
        appointment.organization = tour.organization
        appointment.tour = tour
        appointment.place = tour.place
        appointment.source = "tour_preview"
        appointment.save()
        return JsonResponse({"ok": True, "message": "Your appointment request has been sent."})
    return JsonResponse({"ok": False, "errors": form.errors.get_json_data()}, status=400)


def organization_products_api(request, organization_slug):
    products = Product.objects.filter(organization__slug=organization_slug, status=Product.Status.ACTIVE).select_related("organization")[:100]
    return JsonResponse({"results": [{
        "id": item.id, "name": item.name, "price": str(item.price), "currency": item.currency,
        "image_url": item.cover_image.url if item.cover_image else "",
        "detail_url": reverse("vendors:product_detail", kwargs={"organization_slug": item.organization.slug, "product_slug": item.slug}),
        "delivery_available": item.delivery_available, "pickup_available": item.pickup_available,
    } for item in products]})


@login_required
@require_POST
def product_review_create(request, order_item_id):
    order_item = get_object_or_404(
        OrderItem.objects.select_related("order", "product", "product__organization"),
        pk=order_item_id,
        order__customer=request.user,
        order__status=Order.Status.DELIVERED,
    )
    if hasattr(order_item, "verified_review"):
        messages.info(request, "You have already reviewed this product.")
        return redirect("vendors:customer_order_detail", reference=order_item.order.reference)

    form = ProductReviewForm(request.POST, request.FILES)
    if form.is_valid():
        review = form.save(commit=False)
        review.order_item = order_item
        review.product = order_item.product
        review.customer = request.user
        review.save()
        for image in request.FILES.getlist("images")[:4]:
            ProductReviewImage.objects.create(review=review, image=image)
        messages.success(request, "Your verified review has been published.")
    else:
        messages.error(request, "Please correct the review form.")
    return redirect("vendors:customer_order_detail", reference=order_item.order.reference)


@require_POST
def back_in_stock_subscribe(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    email = (request.POST.get("email") or getattr(request.user, "email", "") or "").strip()
    if not email:
        return JsonResponse({"ok": False, "message": "Email is required."}, status=400)
    subscription, _ = BackInStockSubscription.objects.update_or_create(
        product=product,
        email=email,
        defaults={
            "user": request.user if request.user.is_authenticated else None,
            "is_active": True,
            "notified_at": None,
        },
    )
    return JsonResponse({"ok": True, "message": "We will notify you when this product is available."})


@login_required
def customer_notifications(request):
    notifications = request.user.market_notifications.select_related("order", "product", "organization")
    return render(request, "public/account/notifications.html", {
        "notifications": notifications,
        "unread_count": notifications.filter(read_at__isnull=True).count(),
        "active_market_nav": "account",
    })


@login_required
@require_POST
def customer_notification_read(request, notification_id):
    notification = get_object_or_404(CustomerNotification, pk=notification_id, user=request.user)
    notification.read_at = timezone.now()
    notification.save(update_fields=["read_at", "updated_at"])
    return JsonResponse({"ok": True})


@csrf_exempt
@require_POST
def web_vital_collect(request):
    try:
        payload = json.loads(request.body or b"{}")
        name = str(payload.get("name", ""))[:20]
        value = float(payload.get("value", 0))
    except (ValueError, TypeError, json.JSONDecodeError):
        return HttpResponseBadRequest("Invalid metric")
    if name not in {"CLS", "INP", "LCP", "FCP", "TTFB"}:
        return HttpResponseBadRequest("Unsupported metric")
    if not request.session.session_key:
        request.session.save()
    WebVitalMeasurement.objects.create(
        name=name,
        value=value,
        rating=str(payload.get("rating", ""))[:20],
        page_path=str(payload.get("path", request.path))[:500],
        navigation_type=str(payload.get("navigationType", ""))[:40],
        device=str(payload.get("device", ""))[:40],
        session_key=request.session.session_key or "",
        user=request.user if request.user.is_authenticated else None,
    )
    return JsonResponse({"ok": True})


def pwa_manifest(request):
    return JsonResponse({
        "name": "Twinscopes",
        "short_name": "Twinscopes",
        "description": "Virtual tours, products, appointments and intelligent marketplace.",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#06111f",
        "theme_color": "#0891b2",
        "icons": [
            {"src": "/static/public/icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/static/public/icons/icon-512.png", "sizes": "512x512", "type": "image/png"},
        ],
    })


def pwa_service_worker(request):
    source = """
const CACHE = 'twinscopes-v18';
const OFFLINE = '/offline/';
const CORE = ['/', '/products/', OFFLINE,
  '/static/public/css/twinscopes-public-shell-v12.css',
  '/static/public/css/vendor-commerce-v9.css',
  '/static/public/js/twinscopes-public-shell-v12.js',
  '/static/public/js/product-commerce-v9.js'
];
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(CORE)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE).map(key => caches.delete(key)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  const url = new URL(event.request.url);
  if (url.origin !== location.origin) return;
  if (event.request.mode === 'navigate') {
    event.respondWith(fetch(event.request).then(response => {
      const copy = response.clone();
      caches.open(CACHE).then(cache => cache.put(event.request, copy));
      return response;
    }).catch(() => caches.match(event.request).then(response => response || caches.match(OFFLINE))));
    return;
  }
  if (url.pathname.startsWith('/static/') || url.pathname.startsWith('/media/')) {
    event.respondWith(caches.match(event.request).then(cached => cached || fetch(event.request).then(response => {
      const copy = response.clone();
      caches.open(CACHE).then(cache => cache.put(event.request, copy));
      return response;
    })));
  }
});
"""
    return HttpResponse(source, content_type="application/javascript")


def pwa_offline(request):
    return render(request, "public/offline.html")


@login_required
def account_entry(request):
    """
    Route authenticated users to the dashboard that matches their role.
    Staff/superusers -> global marketplace administration.
    Active organization members -> their organization Vendor Studio.
    Customers -> customer order center.
    """
    if request.user.is_staff or request.user.is_superuser:
        return redirect("vendors:marketplace_admin_home")

    membership = (
        request.user.organization_memberships
        .filter(is_active=True, organization__status=Organization.Status.ACTIVE)
        .select_related("organization")
        .order_by("created_at")
        .first()
    )
    if membership:
        return redirect(
            "vendor_dashboard:home",
            organization_slug=membership.organization.slug,
        )

    return redirect("vendors:customer_orders")
