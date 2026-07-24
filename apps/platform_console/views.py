from __future__ import annotations

from datetime import timedelta
import json
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.forms import modelform_factory
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.ai_core.models import AIRun
from apps.analytics.models import AnalyticsEvent
from apps.domain_intelligence.models import DiscoverySearchLog, MedicalPractitioner
from apps.knowledge.models import KnowledgeSource
from apps.organizations.models import Organization
from apps.places.models import Place
from apps.tours.models import Tour
from apps.users.models import User
from apps.vendors.models import AppointmentRequest
from apps.vision_ai.models import VisionAnalysis

from .resources import RESOURCE_DEFINITIONS, ResourceDefinition, get_resource


staff_required = user_passes_test(lambda user: user.is_authenticated and user.is_staff, login_url="/accounts/login/")


def _resource_or_404(resource_key: str) -> ResourceDefinition:
    resource = get_resource(resource_key)
    if resource is None:
        raise Http404("Unknown control-center resource")
    return resource


def _format_value(value) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, Decimal):
        return f"{value:,.2f}"
    if hasattr(value, "strftime"):
        try:
            return value.strftime("%d %b %Y, %H:%M")
        except Exception:
            return str(value)
    text = str(value)
    return text if len(text) <= 88 else f"{text[:85]}…"


def _resolve_attr(instance, path: str):
    value = instance
    for part in path.split("."):
        value = getattr(value, part, None)
        if callable(value):
            value = value()
        if value is None:
            break
    model_field = path.split(".")[0]
    display_method = getattr(instance, f"get_{model_field}_display", None)
    if callable(display_method):
        try:
            value = display_method()
        except Exception:
            pass
    return _format_value(value)


def _apply_form_classes(form):
    for field in form.fields.values():
        widget = field.widget
        current = widget.attrs.get("class", "")
        widget.attrs["class"] = f"{current} ts-control-field".strip()
        if isinstance(widget, forms.CheckboxInput):
            widget.attrs["class"] += " ts-control-checkbox"
        if isinstance(widget, forms.Textarea):
            widget.attrs.setdefault("rows", 4)


def _date_series(queryset, start_date, days: int, *, date_field="created_at", distinct_session=False):
    aggregate = Count("session_id", distinct=True) if distinct_session else Count("id")
    rows = (
        queryset.filter(**{f"{date_field}__date__gte": start_date})
        .annotate(day=TruncDate(date_field))
        .values("day")
        .annotate(total=aggregate)
        .order_by("day")
    )
    values = {row["day"]: row["total"] for row in rows}
    labels, data = [], []
    for offset in range(days):
        day = start_date + timedelta(days=offset)
        labels.append(day.strftime("%d %b"))
        data.append(values.get(day, 0))
    return labels, data


@staff_required
def overview(request):
    today = timezone.localdate()
    start_14 = today - timedelta(days=13)
    start_30 = timezone.now() - timedelta(days=30)

    traffic_labels, traffic_events = _date_series(AnalyticsEvent.objects.all(), start_14, 14)
    _, traffic_sessions = _date_series(AnalyticsEvent.objects.exclude(session_id=""), start_14, 14, distinct_session=True)

    ai_rows = list(
        AIRun.objects.filter(created_at__gte=start_30)
        .values("provider", "status")
        .annotate(total=Count("id"))
        .order_by("provider", "status")
    )
    providers = sorted({row["provider"] or "unknown" for row in ai_rows})
    ai_statuses = ["succeeded", "failed", "running", "pending"]
    ai_datasets = [
        {
            "label": status.title(),
            "data": [next((row["total"] for row in ai_rows if (row["provider"] or "unknown") == provider and row["status"] == status), 0) for provider in providers],
        }
        for status in ai_statuses
    ]

    vision_rows = list(VisionAnalysis.objects.values("status").annotate(total=Count("id")).order_by("status"))
    appointment_rows = list(AppointmentRequest.objects.values("status").annotate(total=Count("id")).order_by("status"))
    ai_cost = AIRun.objects.filter(created_at__gte=start_30).aggregate(total=Sum("cost_usd"))["total"] or Decimal("0")

    metrics = [
        {"label": "Organizations", "value": Organization.objects.count(), "detail": f"{Organization.objects.filter(status='active').count()} active", "icon": "🏢"},
        {"label": "Published tours", "value": Tour.objects.filter(status=Tour.Status.PUBLISHED).count(), "detail": f"{Tour.objects.count()} total", "icon": "🌐"},
        {"label": "Places", "value": Place.objects.count(), "detail": f"{Place.objects.filter(status=Place.Status.PUBLISHED).count()} published", "icon": "📍"},
        {"label": "Medical practitioners", "value": MedicalPractitioner.objects.filter(is_active=True).count(), "detail": "Active searchable profiles", "icon": "🩺"},
        {"label": "Pending appointments", "value": AppointmentRequest.objects.filter(status=AppointmentRequest.Status.PENDING).count(), "detail": "Awaiting confirmation", "icon": "📅"},
        {"label": "Vision ready", "value": VisionAnalysis.objects.filter(status__in=[VisionAnalysis.Status.SUCCEEDED, VisionAnalysis.Status.PARTIAL]).count(), "detail": f"{VisionAnalysis.objects.filter(status=VisionAnalysis.Status.FAILED).count()} failed", "icon": "👁️"},
        {"label": "AI runs (30 days)", "value": AIRun.objects.filter(created_at__gte=start_30).count(), "detail": f"${ai_cost:,.4f} tracked cost", "icon": "✨"},
        {"label": "Users", "value": User.objects.count(), "detail": f"{User.objects.filter(is_active=True).count()} active", "icon": "👥"},
    ]

    resource_groups = [
        ("Core platform", ["users", "organizations", "places", "tours"]),
        ("Healthcare", ["healthcare-facilities", "medical-specialties", "practitioners", "practitioner-availability", "appointments", "verified-facts"]),
        ("Property & hospitality", ["property-listings", "hospitality"]),
        ("Marketplace", ["product-categories", "products", "orders"]),
        ("AI & knowledge", ["ai-providers", "intelligence-profiles", "knowledge-sources", "services", "vision-analyses", "ai-runs"]),
        ("Insights", ["discovery-searches", "analytics-events"]),
    ]

    return render(request, "dashboard/platform_console/overview.html", {
        "current_organization": None,
        "metrics": metrics,
        "resource_groups": [(label, [RESOURCE_DEFINITIONS[key] for key in keys]) for label, keys in resource_groups],
        "traffic_chart": {"labels": traffic_labels, "events": traffic_events, "sessions": traffic_sessions},
        "ai_chart": {"labels": [provider.title() for provider in providers], "datasets": ai_datasets},
        "vision_chart": {"labels": [row["status"].title() for row in vision_rows], "data": [row["total"] for row in vision_rows]},
        "appointment_chart": {"labels": [row["status"].title() for row in appointment_rows], "data": [row["total"] for row in appointment_rows]},
        "recent_ai_runs": AIRun.objects.select_related("organization").order_by("-created_at")[:8],
        "recent_vision": VisionAnalysis.objects.select_related("organization", "scene").order_by("-created_at")[:8],
        "recent_appointments": AppointmentRequest.objects.select_related("organization").order_by("-created_at")[:8],
        "recent_searches": DiscoverySearchLog.objects.select_related("selected_tour").order_by("-created_at")[:8],
        "knowledge_summary": {
            "total": KnowledgeSource.objects.count(),
            "indexed": KnowledgeSource.objects.filter(status=KnowledgeSource.Status.INDEXED).count(),
            "failed": KnowledgeSource.objects.filter(status=KnowledgeSource.Status.FAILED).count(),
        },
    })


@staff_required
def resource_list(request, resource_key):
    resource = _resource_or_404(resource_key)
    queryset = resource.model.objects.all()
    if resource.select_related:
        queryset = queryset.select_related(*resource.select_related)
    query = request.GET.get("q", "").strip()
    if query and resource.search_fields:
        condition = Q()
        for field in resource.search_fields:
            condition |= Q(**{f"{field}__icontains": query})
        queryset = queryset.filter(condition)
    status = request.GET.get("status", "").strip()
    if status and any(field.name == "status" for field in resource.model._meta.fields):
        queryset = queryset.filter(status=status)
    queryset = queryset.order_by(*resource.order_by)
    paginator = Paginator(queryset, 25)
    page = paginator.get_page(request.GET.get("page"))
    rows = [
        {
            "object": obj,
            "values": [_resolve_attr(obj, path) for path, _ in resource.columns],
            "action_url": reverse(
                "platform-console-resource-detail" if resource.readonly else "platform-console-resource-edit",
                kwargs={"resource_key": resource.key, "pk": obj.pk},
            ),
            "action_label": "View" if resource.readonly else "Edit",
        }
        for obj in page.object_list
    ]
    status_choices = []
    try:
        status_field = resource.model._meta.get_field("status")
        status_choices = list(status_field.choices or [])
    except Exception:
        pass
    return render(request, "dashboard/platform_console/resource_list.html", {
        "current_organization": None,
        "resource": resource,
        "rows": rows,
        "page_obj": page,
        "query": query,
        "selected_status": status,
        "status_choices": status_choices,
    })


@staff_required
def resource_detail(request, resource_key, pk):
    resource = _resource_or_404(resource_key)
    instance = get_object_or_404(resource.model, pk=pk)
    fields = []
    for field in resource.model._meta.fields:
        try:
            value = getattr(instance, field.name)
        except Exception:
            value = None
        is_structured = isinstance(value, (dict, list, tuple))
        if is_structured:
            try:
                display_value = json.dumps(value, indent=2, ensure_ascii=False, default=str)
            except Exception:
                display_value = str(value)
        else:
            display_value = _format_value(value)
        fields.append({"label": field.verbose_name.title(), "value": display_value, "structured": is_structured or len(str(display_value)) > 180})
    return render(request, "dashboard/platform_console/resource_detail.html", {
        "current_organization": None,
        "resource": resource,
        "object": instance,
        "detail_fields": fields,
    })


@staff_required
def resource_create(request, resource_key):
    resource = _resource_or_404(resource_key)
    if resource.readonly or not resource.form_fields:
        raise Http404("This resource is read-only")
    FormClass = modelform_factory(resource.model, fields=resource.form_fields)
    form = FormClass(request.POST or None, request.FILES or None)
    _apply_form_classes(form)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"{resource.singular} created successfully.")
        return redirect("platform-console-resource-list", resource_key=resource.key)
    return render(request, "dashboard/platform_console/resource_form.html", {
        "current_organization": None, "resource": resource, "form": form, "mode": "create", "object": None,
    })


@staff_required
def resource_edit(request, resource_key, pk):
    resource = _resource_or_404(resource_key)
    if resource.readonly or not resource.form_fields:
        raise Http404("This resource is read-only")
    instance = get_object_or_404(resource.model, pk=pk)
    FormClass = modelform_factory(resource.model, fields=resource.form_fields)
    form = FormClass(request.POST or None, request.FILES or None, instance=instance)
    _apply_form_classes(form)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"{resource.singular} updated successfully.")
        return redirect("platform-console-resource-list", resource_key=resource.key)
    return render(request, "dashboard/platform_console/resource_form.html", {
        "current_organization": None, "resource": resource, "form": form, "mode": "edit", "object": instance,
    })


@staff_required
def resource_delete(request, resource_key, pk):
    resource = _resource_or_404(resource_key)
    if resource.readonly or not resource.allow_delete:
        raise Http404("This resource cannot be deleted here")
    instance = get_object_or_404(resource.model, pk=pk)
    if request.method == "POST":
        instance.delete()
        messages.success(request, f"{resource.singular} deleted.")
        return redirect("platform-console-resource-list", resource_key=resource.key)
    return render(request, "dashboard/platform_console/resource_delete.html", {
        "current_organization": None, "resource": resource, "object": instance,
    })
