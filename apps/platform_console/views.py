from __future__ import annotations

from datetime import timedelta
import json
from decimal import Decimal

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.forms import modelform_factory
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.urls import reverse
from django.utils import timezone

from apps.ai_core.models import AIRun
from apps.analytics.models import AnalyticsEvent
from apps.domain_intelligence.models import (
    DiscoverySearchLog,
    IntelligenceReviewItem,
    MedicalPractitioner,
    OrganizationIntelligenceProfile,
    OrganizationIntelligenceRun,
    VerifiedSourceFact,
)
from apps.domain_intelligence.services.organization_sync import apply_review_item, reject_review_item
from apps.domain_intelligence.services.execution import dispatch_organization_intelligence_run
from apps.domain_intelligence.services.readiness import calculate_organization_readiness, readiness_distribution
from apps.knowledge.models import KnowledgeChunk, KnowledgeDocument, KnowledgeSource, ServiceOffering
from apps.knowledge.tasks import sync_knowledge_source
from apps.organizations.models import Organization
from apps.places.models import Place
from apps.tours.models import Tour
from apps.users.models import User
from apps.vendors.models import AppointmentRequest
from apps.vision_ai.models import VisionAnalysis

from .resources import RESOURCE_DEFINITIONS, ResourceDefinition, get_resource


staff_required = user_passes_test(lambda user: user.is_authenticated and user.is_staff, login_url="/accounts/login/")


def _intelligence_execution_mode(request) -> str:
    """Use the in-process runner for an actual localhost dashboard.

    This also protects developers who accidentally launch localhost with the
    production settings module still present in their shell environment.
    """
    host = request.get_host().split(":", 1)[0].strip("[]").casefold()
    if host in {"localhost", "127.0.0.1", "::1"}:
        return "thread"
    return "auto"


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

    for organization in Organization.objects.all()[:200]:
        try:
            profile = organization.intelligence_profile
        except OrganizationIntelligenceProfile.DoesNotExist:
            profile = None
        if profile is None or profile.readiness_checked_at is None:
            calculate_organization_readiness(organization)
    ready_organizations = OrganizationIntelligenceProfile.objects.filter(
        readiness_status=OrganizationIntelligenceProfile.ReadinessStatus.READY
    ).count()
    review_organizations = OrganizationIntelligenceProfile.objects.filter(
        readiness_status=OrganizationIntelligenceProfile.ReadinessStatus.REVIEW
    ).count()
    active_intelligence_runs = OrganizationIntelligenceRun.objects.filter(
        status__in=[OrganizationIntelligenceRun.Status.QUEUED, OrganizationIntelligenceRun.Status.RUNNING]
    ).count()
    pending_intelligence_reviews = IntelligenceReviewItem.objects.filter(
        status=IntelligenceReviewItem.Status.PENDING
    ).count()

    metrics = [
        {"label": "Organizations", "value": Organization.objects.count(), "detail": f"{Organization.objects.filter(status='active').count()} active", "icon": "🏢"},
        {"label": "Published tours", "value": Tour.objects.filter(status=Tour.Status.PUBLISHED).count(), "detail": f"{Tour.objects.count()} total", "icon": "🌐"},
        {"label": "Places", "value": Place.objects.count(), "detail": f"{Place.objects.filter(status=Place.Status.PUBLISHED).count()} published", "icon": "📍"},
        {"label": "Medical practitioners", "value": MedicalPractitioner.objects.filter(is_active=True).count(), "detail": "Active searchable profiles", "icon": "🩺"},
        {"label": "Pending appointments", "value": AppointmentRequest.objects.filter(status=AppointmentRequest.Status.PENDING).count(), "detail": "Awaiting confirmation", "icon": "📅"},
        {"label": "Vision ready", "value": VisionAnalysis.objects.filter(status__in=[VisionAnalysis.Status.SUCCEEDED, VisionAnalysis.Status.PARTIAL]).count(), "detail": f"{VisionAnalysis.objects.filter(status=VisionAnalysis.Status.FAILED).count()} failed", "icon": "👁️"},
        {"label": "AI runs (30 days)", "value": AIRun.objects.filter(created_at__gte=start_30).count(), "detail": f"${ai_cost:,.4f} tracked cost", "icon": "✨"},
        {"label": "Client-ready organizations", "value": ready_organizations, "detail": f"{review_organizations} need review", "icon": "◉"},
        {"label": "Users", "value": User.objects.count(), "detail": f"{User.objects.filter(is_active=True).count()} active", "icon": "👥"},
    ]

    resource_groups = [
        ("Core platform", ["users", "organizations", "places", "tours"]),
        ("Healthcare", ["healthcare-facilities", "medical-specialties", "practitioners", "practitioner-availability", "appointments", "verified-facts"]),
        ("Property & hospitality", ["property-listings", "hospitality"]),
        ("Marketplace", ["product-categories", "products", "orders"]),
        ("AI & knowledge", ["ai-providers", "intelligence-profiles", "intelligence-runs", "intelligence-reviews", "knowledge-sources", "services", "vision-analyses", "ai-runs"]),
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
        "intelligence_summary": {
            "ready": ready_organizations,
            "review": review_organizations,
            "active_runs": active_intelligence_runs,
            "pending_reviews": pending_intelligence_reviews,
        },
        "recent_intelligence_runs": OrganizationIntelligenceRun.objects.select_related("organization", "requested_by").order_by("-created_at")[:8],
        "readiness_chart": {
            "labels": [label for _, label in OrganizationIntelligenceProfile.ReadinessStatus.choices],
            "data": [readiness_distribution().get(value, 0) for value, _ in OrganizationIntelligenceProfile.ReadinessStatus.choices],
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

@staff_required
def intelligence_hub(request):
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    domain = request.GET.get("domain", "").strip()
    organizations = Organization.objects.all().order_by("name")
    if query:
        organizations = organizations.filter(
            Q(name__icontains=query) | Q(slug__icontains=query) | Q(website_url__icontains=query)
        )
    if status:
        organizations = organizations.filter(intelligence_profile__readiness_status=status)
    if domain:
        organizations = organizations.filter(intelligence_profile__domain_kind=domain)
    paginator = Paginator(organizations, 24)
    page = paginator.get_page(request.GET.get("page"))
    rows = []
    for organization in page.object_list:
        result = calculate_organization_readiness(organization)
        profile = OrganizationIntelligenceProfile.objects.get(organization=organization)
        latest_run = organization.intelligence_runs.order_by("-created_at").first()
        counts = result.breakdown.get("counts", {})
        rows.append({
            "organization": organization,
            "profile": profile,
            "latest_run": latest_run,
            "counts": counts,
        })
    distribution = readiness_distribution()
    domain_rows = list(
        OrganizationIntelligenceProfile.objects.values("domain_kind")
        .annotate(total=Count("id")).order_by("domain_kind")
    )
    return render(request, "dashboard/platform_console/intelligence_hub.html", {
        "current_organization": None,
        "rows": rows,
        "page_obj": page,
        "query": query,
        "selected_status": status,
        "selected_domain": domain,
        "status_choices": OrganizationIntelligenceProfile.ReadinessStatus.choices,
        "domain_choices": OrganizationIntelligenceProfile.DomainKind.choices,
        "readiness_chart": {
            "labels": [label for _, label in OrganizationIntelligenceProfile.ReadinessStatus.choices],
            "data": [distribution.get(value, 0) for value, _ in OrganizationIntelligenceProfile.ReadinessStatus.choices],
        },
        "domain_chart": {
            "labels": [dict(OrganizationIntelligenceProfile.DomainKind.choices).get(row["domain_kind"], row["domain_kind"]).title() for row in domain_rows],
            "data": [row["total"] for row in domain_rows],
        },
        "summary": {
            "organizations": Organization.objects.count(),
            "ready": distribution.get(OrganizationIntelligenceProfile.ReadinessStatus.READY, 0),
            "review": distribution.get(OrganizationIntelligenceProfile.ReadinessStatus.REVIEW, 0),
            "active": OrganizationIntelligenceRun.objects.filter(status__in=[OrganizationIntelligenceRun.Status.QUEUED, OrganizationIntelligenceRun.Status.RUNNING]).count(),
            "pending_reviews": IntelligenceReviewItem.objects.filter(status=IntelligenceReviewItem.Status.PENDING).count(),
        },
    })


@staff_required
def intelligence_organization(request, organization_id):
    organization = get_object_or_404(Organization, pk=organization_id)
    readiness = calculate_organization_readiness(organization)
    profile = OrganizationIntelligenceProfile.objects.get(organization=organization)
    sources = KnowledgeSource.objects.filter(organization=organization).order_by("-updated_at")
    source_ids = list(sources.values_list("id", flat=True))
    return render(request, "dashboard/platform_console/intelligence_organization.html", {
        "current_organization": None,
        "organization": organization,
        "profile": profile,
        "readiness": readiness,
        "sources": sources,
        "documents_count": KnowledgeDocument.objects.filter(source_id__in=source_ids, is_active=True).count(),
        "chunks_count": KnowledgeChunk.objects.filter(document__source_id__in=source_ids).count(),
        "services": ServiceOffering.objects.filter(organization=organization, is_active=True).order_by("name")[:20],
        "facts": VerifiedSourceFact.objects.filter(organization=organization, is_public=True).order_by("-verified_at")[:30],
        "review_items": IntelligenceReviewItem.objects.filter(organization=organization).select_related("run", "place", "reviewed_by").order_by("status", "-created_at")[:50],
        "runs": OrganizationIntelligenceRun.objects.filter(organization=organization).select_related("requested_by").order_by("-created_at")[:30],
        "active_run": OrganizationIntelligenceRun.objects.filter(organization=organization, status__in=[OrganizationIntelligenceRun.Status.QUEUED, OrganizationIntelligenceRun.Status.RUNNING]).first(),
        "practitioners_count": MedicalPractitioner.objects.filter(organization=organization, is_active=True).count(),
    })


@staff_required
@require_POST
def intelligence_collect(request, organization_id):
    organization = get_object_or_404(Organization, pk=organization_id)
    if not organization.website_url:
        messages.error(request, "Add the official website URL before starting collection.")
        return redirect("platform-console-intelligence-organization", organization_id=organization.pk)
    active = OrganizationIntelligenceRun.objects.filter(
        organization=organization,
        status__in=[OrganizationIntelligenceRun.Status.QUEUED, OrganizationIntelligenceRun.Status.RUNNING],
    ).first()
    if active:
        messages.info(request, "An intelligence collection is already queued or running for this organization.")
        return redirect("platform-console-intelligence-run", run_id=active.pk)
    profile, _ = OrganizationIntelligenceProfile.objects.get_or_create(organization=organization)
    try:
        max_pages = int(request.POST.get("max_pages") or profile.website_sync_max_pages or 25)
    except (TypeError, ValueError):
        max_pages = 25
    run = OrganizationIntelligenceRun.objects.create(
        organization=organization,
        requested_by=request.user,
        trigger=OrganizationIntelligenceRun.Trigger.MANUAL,
        website_url=organization.website_url,
        max_pages=max(1, min(max_pages, 100)),
    )
    try:
        dispatch = dispatch_organization_intelligence_run(run, mode=_intelligence_execution_mode(request))
        messages.success(
            request,
            "Website collection started. The dashboard will update as the agent progresses."
            if dispatch["mode"] in {"thread", "sync"}
            else "Website collection was queued. The dashboard will update as the agent progresses.",
        )
    except Exception as exc:
        run.status = OrganizationIntelligenceRun.Status.FAILED
        run.error_code = "queue_unavailable"
        run.error_message = str(exc)[:1000]
        run.finished_at = timezone.now()
        run.save(update_fields=("status", "error_code", "error_message", "finished_at", "updated_at"))
        messages.error(request, "The collection could not be queued. Check the AI worker and Redis services.")
    return redirect("platform-console-intelligence-run", run_id=run.pk)


@staff_required
@require_POST
def intelligence_bulk_collect(request):
    candidates = Organization.objects.filter(status=Organization.Status.ACTIVE).exclude(website_url="").order_by("id")
    queued = 0
    skipped = 0
    try:
        limit = max(1, min(int(request.POST.get("limit") or 10), 25))
    except (TypeError, ValueError):
        limit = 10
    for organization in candidates:
        if queued >= limit:
            break
        if OrganizationIntelligenceRun.objects.filter(organization=organization, status__in=[OrganizationIntelligenceRun.Status.QUEUED, OrganizationIntelligenceRun.Status.RUNNING]).exists():
            skipped += 1
            continue
        profile, _ = OrganizationIntelligenceProfile.objects.get_or_create(organization=organization)
        if profile.readiness_status == OrganizationIntelligenceProfile.ReadinessStatus.READY and profile.last_synced_at and profile.last_synced_at >= timezone.now() - timedelta(days=7):
            skipped += 1
            continue
        run = OrganizationIntelligenceRun.objects.create(
            organization=organization,
            requested_by=request.user,
            trigger=OrganizationIntelligenceRun.Trigger.MANUAL,
            website_url=organization.website_url,
            max_pages=profile.website_sync_max_pages or 25,
        )
        try:
            dispatch_organization_intelligence_run(run, mode=_intelligence_execution_mode(request))
            queued += 1
        except Exception as exc:
            run.status = OrganizationIntelligenceRun.Status.FAILED
            run.error_code = "queue_unavailable"
            run.error_message = str(exc)[:1000]
            run.finished_at = timezone.now()
            run.save(update_fields=("status", "error_code", "error_message", "finished_at", "updated_at"))
            break
    if queued:
        messages.success(request, f"Queued {queued} organization intelligence collection(s).")
    else:
        messages.info(request, "No organization currently requires a new collection run.")
    if skipped:
        messages.info(request, f"Skipped {skipped} organization(s) already running or recently ready.")
    return redirect("platform-console-intelligence-hub")


@staff_required
def intelligence_run(request, run_id):
    run = get_object_or_404(OrganizationIntelligenceRun.objects.select_related("organization", "requested_by"), pk=run_id)
    return render(request, "dashboard/platform_console/intelligence_run.html", {
        "current_organization": None,
        "run": run,
        "review_items": run.review_items.select_related("place", "reviewed_by").order_by("status", "-created_at"),
    })


@staff_required
def intelligence_run_status(request, run_id):
    run = get_object_or_404(OrganizationIntelligenceRun, pk=run_id)
    terminal = run.status in {
        OrganizationIntelligenceRun.Status.SUCCEEDED,
        OrganizationIntelligenceRun.Status.PARTIAL,
        OrganizationIntelligenceRun.Status.FAILED,
        OrganizationIntelligenceRun.Status.CANCELLED,
    }
    queued_seconds = max(0, int((timezone.now() - run.created_at).total_seconds())) if run.status == OrganizationIntelligenceRun.Status.QUEUED else 0
    stalled = run.status == OrganizationIntelligenceRun.Status.QUEUED and queued_seconds >= int(getattr(settings, "DOMAIN_INTELLIGENCE_STALE_QUEUE_SECONDS", 20))
    task_mode = "thread" if run.task_id.startswith("thread:") else "sync" if run.task_id.startswith("sync:") else "celery" if run.task_id else "unknown"
    if run.status == OrganizationIntelligenceRun.Status.QUEUED:
        message = "Waiting for the local background runner to start." if task_mode == "thread" else "Waiting for the AI worker to accept this collection."
    elif run.status == OrganizationIntelligenceRun.Status.RUNNING:
        message = str((run.summary or {}).get("stage_label") or "Collecting official pages and preparing client-ready information.")
    elif run.status == OrganizationIntelligenceRun.Status.SUCCEEDED:
        message = "The organization information is ready for review and client use."
    elif run.status == OrganizationIntelligenceRun.Status.PARTIAL:
        message = "Collection completed with some items requiring attention."
    elif run.status == OrganizationIntelligenceRun.Status.FAILED:
        message = "The collection stopped before completion. You can retry this run."
    else:
        message = run.get_status_display()
    return JsonResponse({
        "id": str(run.id),
        "status": run.status,
        "status_label": run.get_status_display(),
        "message": message,
        "stage": str((run.summary or {}).get("stage") or ""),
        "stage_label": str((run.summary or {}).get("stage_label") or ""),
        "task_mode": task_mode,
        "task_id": run.task_id,
        "pages_crawled": run.pages_crawled,
        "documents_indexed": run.documents_indexed,
        "chunks_indexed": run.chunks_indexed,
        "services_collected": run.services_collected,
        "facts_collected": run.facts_collected,
        "review_items_created": run.review_items_created,
        "readiness_before": run.readiness_before,
        "readiness_after": run.readiness_after,
        "finished": terminal,
        "stalled": stalled,
        "can_retry": stalled or run.status == OrganizationIntelligenceRun.Status.FAILED,
        "queued_seconds": queued_seconds,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "updated_at": run.updated_at.isoformat(),
    })


@staff_required
@require_POST
def intelligence_run_retry(request, run_id):
    previous_run = get_object_or_404(OrganizationIntelligenceRun, pk=run_id)
    if previous_run.status == OrganizationIntelligenceRun.Status.RUNNING and previous_run.started_at:
        messages.info(request, "This collection is already running.")
        return redirect("platform-console-intelligence-run", run_id=previous_run.pk)

    if previous_run.status == OrganizationIntelligenceRun.Status.QUEUED:
        previous_run.status = OrganizationIntelligenceRun.Status.CANCELLED
        previous_run.finished_at = timezone.now()
        previous_run.save(update_fields=("status", "finished_at", "updated_at"))

    run = OrganizationIntelligenceRun.objects.create(
        organization=previous_run.organization,
        requested_by=request.user,
        trigger=OrganizationIntelligenceRun.Trigger.MANUAL,
        website_url=previous_run.organization.website_url or previous_run.website_url,
        max_pages=previous_run.max_pages,
    )
    try:
        dispatch = dispatch_organization_intelligence_run(run, mode=_intelligence_execution_mode(request))
        messages.success(request, f"Collection restarted using the {dispatch['mode']} runner.")
    except Exception as exc:
        run.status = OrganizationIntelligenceRun.Status.FAILED
        run.error_code = "dispatch_failed"
        run.error_message = str(exc)[:1000]
        run.finished_at = timezone.now()
        run.save(update_fields=("status", "error_code", "error_message", "finished_at", "updated_at"))
        messages.error(request, "The collection could not be restarted. Check the local runner or Celery worker.")
    return redirect("platform-console-intelligence-run", run_id=run.pk)


@staff_required
@require_POST
def intelligence_review_apply(request, item_id):
    item = get_object_or_404(IntelligenceReviewItem, pk=item_id)
    organization_id = item.organization_id
    try:
        apply_review_item(item, request.user)
        messages.success(request, "The collected information was approved and applied.")
    except Exception as exc:
        messages.error(request, f"This item could not be applied automatically: {str(exc)[:240]}")
    return redirect("platform-console-intelligence-organization", organization_id=organization_id)


@staff_required
@require_POST
def intelligence_review_reject(request, item_id):
    item = get_object_or_404(IntelligenceReviewItem, pk=item_id)
    organization_id = item.organization_id
    reject_review_item(item, request.user)
    messages.success(request, "The collected suggestion was rejected.")
    return redirect("platform-console-intelligence-organization", organization_id=organization_id)


@staff_required
@require_POST
def intelligence_source_reindex(request, source_id):
    source = get_object_or_404(KnowledgeSource, pk=source_id)
    try:
        task = sync_knowledge_source.delay(source.pk)
        messages.success(request, f"Knowledge reindex queued: {task.id}")
    except Exception:
        messages.error(request, "Knowledge reindex could not be queued. Check the AI worker and Redis.")
    return redirect("platform-console-intelligence-organization", organization_id=source.organization_id)

