from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum, Count
from django.forms import ModelForm
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.utils import timezone

from apps.organizations.models import Organization
from .forms import DeliveryZoneForm
from .models import (
    AppointmentRequest, DeliveryZone, IntelligentAgent, IntelligentAgentRun,
    IntelligentRecommendation, MarketDataSource, MarketInsightReport,
    Order, OrderStatusHistory, Product, ProductReview, VendorProfile,
)
from .services import generate_market_insight
from .commerce_services import rebuild_product_recommendations, transition_order


class ProductForm(ModelForm):
    class Meta:
        model = Product
        fields = [
            "category", "name", "slug", "sku", "short_description", "description",
            "specifications", "cover_image", "price", "compare_at_price", "currency",
            "stock_quantity", "track_inventory", "delivery_available", "pickup_available",
            "estimated_delivery_days", "status", "is_featured",
        ]


def _organization(request, slug):
    return get_object_or_404(Organization, slug=slug, memberships__user=request.user, memberships__is_active=True)


@login_required
def vendor_dashboard(request, organization_slug):
    organization = _organization(request, organization_slug)
    VendorProfile.objects.get_or_create(organization=organization)
    stats = {
        "products": organization.products.count(),
        "active_products": organization.products.filter(status=Product.Status.ACTIVE).count(),
        "orders": organization.orders.count(),
        "revenue": organization.orders.exclude(status=Order.Status.CANCELLED).aggregate(total=Sum("total"))["total"] or 0,
        "appointments": organization.appointment_requests.count(),
        "delivery_zones": organization.delivery_zones.filter(is_active=True).count(),
    }
    return render(request, "dashboard/vendors/home.html", {
        "organization": organization, "stats": stats,
        "latest_orders": organization.orders.order_by("-created_at")[:8],
        "latest_appointments": organization.appointment_requests.order_by("-created_at")[:8],
    })


@login_required
def product_list(request, organization_slug):
    organization = _organization(request, organization_slug)
    return render(request, "dashboard/vendors/products.html", {
        "organization": organization, "products": organization.products.select_related("category").all(),
    })


@login_required
def product_form(request, organization_slug, product_id=None):
    organization = _organization(request, organization_slug)
    product = get_object_or_404(Product, organization=organization, pk=product_id) if product_id else None
    vendor_profile, _ = VendorProfile.objects.get_or_create(organization=organization)
    initial = {"currency": vendor_profile.currency} if not product else None
    form = ProductForm(
        request.POST or None,
        request.FILES or None,
        instance=product,
        initial=initial,
    )
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.organization = organization
        item.save()
        return redirect("vendor_dashboard:products", organization_slug=organization.slug)
    return render(request, "dashboard/vendors/product_form.html", {"organization": organization, "form": form, "product": product})


@login_required
def order_list(request, organization_slug):
    organization = _organization(request, organization_slug)
    return render(request, "dashboard/vendors/orders.html", {"organization": organization, "orders": organization.orders.prefetch_related("items")})


@login_required
def appointment_list(request, organization_slug):
    organization = _organization(request, organization_slug)
    return render(request, "dashboard/vendors/appointments.html", {"organization": organization, "appointments": organization.appointment_requests.select_related("tour", "appointment_type")})


@login_required
def insights(request, organization_slug):
    organization = _organization(request, organization_slug)
    return render(request, "dashboard/vendors/insights.html", {
        "organization": organization,
        "reports": organization.market_reports.order_by("-created_at")[:12],
        "latest_report": organization.market_reports.order_by("-created_at").first(),
        "sources": organization.market_sources.all(),
    })


@login_required
@require_POST
def generate_insights(request, organization_slug):
    organization = _organization(request, organization_slug)
    generate_market_insight(organization)
    return redirect("vendor_dashboard:insights", organization_slug=organization.slug)


@login_required
@require_POST
def source_create(request, organization_slug):
    organization = _organization(request, organization_slug)
    metrics = {}
    for key in ("followers", "reach", "engagement", "visits", "clicks", "leads", "conversions"):
        value = request.POST.get(key, "").strip()
        if value:
            metrics[key] = value
    MarketDataSource.objects.create(
        organization=organization,
        source_type=request.POST.get("source_type", "manual"),
        label=request.POST.get("label", "").strip(),
        url=request.POST.get("url", "").strip(),
        metrics=metrics,
        latest_summary=request.POST.get("latest_summary", "").strip(),
    )
    return redirect("vendor_dashboard:insights", organization_slug=organization.slug)


@login_required
def delivery_zone_list(request, organization_slug):
    organization = _organization(request, organization_slug)
    zones = organization.delivery_zones.all()
    return render(request, "dashboard/vendors/delivery_zones.html", {
        "organization": organization,
        "zones": zones,
    })


@login_required
def delivery_zone_form(request, organization_slug, zone_id=None):
    organization = _organization(request, organization_slug)
    zone = (
        get_object_or_404(DeliveryZone, organization=organization, pk=zone_id)
        if zone_id else None
    )
    form = DeliveryZoneForm(request.POST or None, instance=zone)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.organization = organization
        item.save()
        messages.success(request, "Delivery zone saved.")
        return redirect("vendor_dashboard:delivery_zones", organization_slug=organization.slug)
    return render(request, "dashboard/vendors/delivery_zone_form.html", {
        "organization": organization,
        "form": form,
        "zone": zone,
    })


@login_required
@require_POST
def delivery_zone_delete(request, organization_slug, zone_id):
    organization = _organization(request, organization_slug)
    zone = get_object_or_404(DeliveryZone, organization=organization, pk=zone_id)
    zone.delete()
    messages.success(request, "Delivery zone deleted.")
    return redirect("vendor_dashboard:delivery_zones", organization_slug=organization.slug)


@login_required
@require_POST
def seed_south_africa_zones(request, organization_slug):
    organization = _organization(request, organization_slug)
    from django.core.management import call_command
    call_command("seed_south_africa_delivery_zones", organization=organization.slug)
    messages.success(request, "South African delivery zones are ready.")
    return redirect("vendor_dashboard:delivery_zones", organization_slug=organization.slug)


@login_required
def intelligent_agents(request, organization_slug):
    organization = _organization(request, organization_slug)
    return render(request, "dashboard/vendors/intelligent_agents.html", {
        "organization": organization,
        "agents": IntelligentAgent.objects.filter(is_active=True),
        "runs": organization.intelligent_agent_runs.select_related("agent", "requested_by")[:15],
        "recommendations": organization.intelligent_recommendations.select_related("run", "run__agent")[:30],
    })


@login_required
@require_POST
def intelligent_agent_run(request, organization_slug, agent_code):
    organization = _organization(request, organization_slug)
    agent = get_object_or_404(IntelligentAgent, code=agent_code, is_active=True)
    run = IntelligentAgentRun.objects.create(
        organization=organization,
        agent=agent,
        requested_by=request.user,
    )
    try:
        from .tasks import execute_intelligent_agent_run
        transaction.on_commit(lambda: execute_intelligent_agent_run.delay(run.pk))
        messages.success(request, f"{agent.name} is analysing your organization.")
    except Exception:
        from .agents import execute_agent_run
        execute_agent_run(run.pk)
        messages.success(request, f"{agent.name} completed the analysis.")
    return redirect("vendor_dashboard:intelligent_agents", organization_slug=organization.slug)


@login_required
@require_POST
def intelligent_recommendation_status(request, organization_slug, recommendation_id):
    organization = _organization(request, organization_slug)
    recommendation = get_object_or_404(
        IntelligentRecommendation,
        organization=organization,
        pk=recommendation_id,
    )
    allowed = dict(IntelligentRecommendation.Status.choices)
    status = request.POST.get("status", "")
    if status in allowed:
        recommendation.status = status
        recommendation.save(update_fields=["status", "updated_at"])
    return redirect("vendor_dashboard:intelligent_agents", organization_slug=organization.slug)


@login_required
def order_detail(request, organization_slug, reference):
    organization = _organization(request, organization_slug)
    order = get_object_or_404(
        organization.orders.prefetch_related("items", "status_history"),
        reference=reference,
    )
    return render(request, "dashboard/vendors/order_detail.html", {
        "organization": organization,
        "order": order,
        "status_choices": Order.Status.choices,
    })


@login_required
@require_POST
def order_status_update(request, organization_slug, reference):
    organization = _organization(request, organization_slug)
    order = get_object_or_404(organization.orders, reference=reference)
    status = request.POST.get("status", "")
    valid = dict(Order.Status.choices)
    if status not in valid:
        messages.error(request, "Invalid order status.")
    else:
        transition_order(
            order,
            status,
            changed_by=request.user,
            note=(request.POST.get("note") or "").strip(),
            customer_visible=request.POST.get("customer_visible") == "on",
        )
        messages.success(request, f"Order updated to {valid[status]}.")
    return redirect("vendor_dashboard:order_detail", organization_slug=organization.slug, reference=order.reference)


@login_required
@require_POST
def review_response(request, organization_slug, review_id):
    organization = _organization(request, organization_slug)
    review = get_object_or_404(ProductReview, pk=review_id, product__organization=organization)
    review.vendor_response = (request.POST.get("vendor_response") or "").strip()
    review.vendor_responded_at = timezone.now() if review.vendor_response else None
    review.save(update_fields=["vendor_response", "vendor_responded_at", "updated_at"])
    messages.success(request, "Review response saved.")
    return redirect("vendor_dashboard:product_edit", organization_slug=organization.slug, product_id=review.product_id)


@login_required
@require_POST
def rebuild_recommendations(request, organization_slug):
    organization = _organization(request, organization_slug)
    created = rebuild_product_recommendations(organization)
    messages.success(request, f"{created} product recommendations generated.")
    return redirect("vendor_dashboard:intelligent_agents", organization_slug=organization.slug)
