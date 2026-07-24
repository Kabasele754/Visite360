from __future__ import annotations

import hashlib
import json

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods, require_POST
from django.utils.dateparse import parse_date, parse_time

from apps.integrations.models import IntegrationConnection
from apps.integrations.services.google_calendar import create_event_for_appointment
from apps.organizations.models import Organization
from apps.tours.models import Tour
from apps.vendors.models import AppointmentRequest, AppointmentType

from .models import (
    DiscoverySearchLog,
    HealthcareFacilityProfile,
    MedicalPractitioner,
    MedicalSpecialty,
    OrganizationIntelligenceProfile,
)
from .services.intent_router import parse_discovery_query_enhanced
from .services.search import search_tours


def _json_payload(request) -> dict:
    if request.method == "GET":
        return request.GET.dict()
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}


def _float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _client_fingerprint(request, scope: str) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    address = (forwarded.split(",", 1)[0].strip() if forwarded else request.META.get("REMOTE_ADDR", ""))
    session = request.session.session_key or ""
    raw = f"{scope}|{address}|{session}|{request.headers.get('user-agent', '')[:120]}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _rate_limit(request, scope: str, *, limit: int, window_seconds: int) -> bool:
    key = f"public-rate:{_client_fingerprint(request, scope)}"
    try:
        count = cache.get(key)
        if count is None:
            cache.set(key, 1, timeout=window_seconds)
            return True
        if int(count) >= limit:
            return False
        cache.incr(key)
        return True
    except Exception:
        # A cache outage must not prevent a legitimate appointment request.
        return True


@require_http_methods(["GET", "POST"])
def public_discovery_search(request):
    payload = _json_payload(request)
    query = str(payload.get("q") or payload.get("query") or "").strip()
    is_live = str(payload.get("live") or "0").strip().lower() in {"1", "true", "yes"}
    if not query:
        return JsonResponse({
            "ok": False,
            "message": "Tell us what kind of place, service or virtual visit you are looking for.",
            "results": [],
        }, status=400)
    if not _rate_limit(
        request,
        "discovery-live-search" if is_live else "discovery-search",
        limit=(
            int(getattr(settings, "PUBLIC_DISCOVERY_LIVE_RATE_LIMIT", 120))
            if is_live
            else int(getattr(settings, "PUBLIC_DISCOVERY_RATE_LIMIT", 30))
        ),
        window_seconds=int(getattr(settings, "PUBLIC_DISCOVERY_RATE_WINDOW_SECONDS", 300)),
    ):
        return JsonResponse({
            "ok": False,
            "message": "Too many searches were sent from this device. Please wait a moment and try again.",
            "results": [],
        }, status=429)

    intent = parse_discovery_query_enhanced(
        query,
        city=payload.get("city") or "",
        location_text=payload.get("location") or payload.get("address") or "",
    )
    latitude = _float(payload.get("latitude"))
    longitude = _float(payload.get("longitude"))
    radius = _float(payload.get("radius_km"), getattr(settings, "DISCOVERY_DEFAULT_RADIUS_KM", 40))
    try:
        limit = max(1, min(int(payload.get("limit") or 12), 30))
    except (TypeError, ValueError):
        limit = 12
    results = search_tours(
        intent,
        latitude=latitude,
        longitude=longitude,
        radius_km=radius if latitude is not None and longitude is not None else None,
        limit=limit,
    )

    session_key = request.session.session_key or ""
    if not is_live:
        try:
            is_healthcare_query = intent.category == "healthcare" or bool(intent.specialty or intent.practitioner)
            normalized_log_intent = intent.as_dict()
            if is_healthcare_query:
                normalized_log_intent["raw_query"] = "[redacted]"
            DiscoverySearchLog.objects.create(
                query=("[healthcare search]" if is_healthcare_query else query[:500]),
                normalized_intent=normalized_log_intent,
                result_count=len(results),
                session_key=session_key[:80],
                metadata={
                    "has_coordinates": latitude is not None and longitude is not None,
                    "query_hash": hashlib.sha256(query.casefold().encode("utf-8")).hexdigest(),
                    "healthcare_query_redacted": is_healthcare_query,
                    "user_agent": request.headers.get("user-agent", "")[:300],
                },
            )
        except Exception:
            pass

    return JsonResponse({
        "ok": True,
        "query": query,
        "intent": intent.as_dict(),
        "count": len(results),
        "results": results,
        "message": (
            "We found virtual visits matching your request."
            if results
            else "No exact match was found. Try broadening the location, budget or number of rooms."
        ),
    })


@require_POST
@csrf_protect
def public_healthcare_appointment(request):
    payload = _json_payload(request)
    if payload.get("website"):
        # Honeypot: behave like a successful submission without storing spam.
        return JsonResponse({"ok": True, "message": "Your request has been received."}, status=201)
    if not _rate_limit(
        request,
        "healthcare-appointment",
        limit=int(getattr(settings, "PUBLIC_APPOINTMENT_RATE_LIMIT", 5)),
        window_seconds=int(getattr(settings, "PUBLIC_APPOINTMENT_RATE_WINDOW_SECONDS", 900)),
    ):
        return JsonResponse({
            "ok": False,
            "message": "Too many requests were sent from this device. Please wait a few minutes and try again.",
        }, status=429)

    organization = get_object_or_404(
        Organization,
        slug=payload.get("organization_slug"),
        status=Organization.Status.ACTIVE,
    )
    has_healthcare_domain = (
        OrganizationIntelligenceProfile.objects.filter(
            organization=organization,
            domain_kind__in=(
                OrganizationIntelligenceProfile.DomainKind.HEALTHCARE,
                OrganizationIntelligenceProfile.DomainKind.MIXED,
            ),
        ).exists()
        or HealthcareFacilityProfile.objects.filter(place__organization=organization, is_active=True).exists()
    )
    if not has_healthcare_domain:
        return JsonResponse({
            "ok": False,
            "message": "Medical appointment requests are not enabled for this organization.",
        }, status=400)

    practitioner = None
    if payload.get("practitioner_id"):
        practitioner = MedicalPractitioner.objects.select_related("specialty", "place").filter(
            pk=payload.get("practitioner_id"),
            organization=organization,
            is_active=True,
        ).first()
        if practitioner is None:
            return JsonResponse({
                "ok": False,
                "message": "The selected practitioner is no longer available. Please choose another option.",
            }, status=400)
    specialty = None
    if payload.get("specialty_id"):
        specialty = MedicalSpecialty.objects.filter(
            pk=payload.get("specialty_id"),
            organization=organization,
            is_active=True,
        ).first()
        if specialty is None:
            return JsonResponse({
                "ok": False,
                "message": "The selected specialty is no longer available. Please choose another option.",
            }, status=400)
    if practitioner and not specialty:
        specialty = practitioner.specialty

    full_name = str(payload.get("full_name") or "").strip()
    phone = str(payload.get("phone") or "").strip()
    email = str(payload.get("email") or "").strip()
    preferred_date = parse_date(str(payload.get("preferred_date") or ""))
    preferred_time = parse_time(str(payload.get("preferred_time") or ""))
    if not full_name or not phone:
        return JsonResponse({
            "ok": False,
            "message": "Your name and phone number are required.",
        }, status=400)
    if preferred_date is None:
        return JsonResponse({
            "ok": False,
            "message": "Please choose a valid preferred date.",
        }, status=400)
    appointment_mode = str(payload.get("appointment_mode") or "in_person").strip().lower()
    if appointment_mode not in {"in_person", "telemedicine"}:
        return JsonResponse({
            "ok": False,
            "message": "Please choose a valid appointment mode.",
        }, status=400)
    if len(phone) < 6:
        return JsonResponse({
            "ok": False,
            "message": "Please enter a valid phone number.",
        }, status=400)
    if email:
        try:
            validate_email(email)
        except ValidationError:
            return JsonResponse({
                "ok": False,
                "message": "Please enter a valid email address.",
            }, status=400)
    if preferred_date and preferred_date < timezone.localdate():
        return JsonResponse({
            "ok": False,
            "message": "The preferred date cannot be in the past.",
        }, status=400)

    tour = Tour.objects.filter(
        pk=payload.get("tour_id"),
        organization=organization,
        status=Tour.Status.PUBLISHED,
    ).first()
    if payload.get("tour_id") and tour is None:
        return JsonResponse({
            "ok": False,
            "message": "The selected virtual visit is no longer available.",
        }, status=400)
    appointment_type = AppointmentType.objects.filter(
        organization=organization,
        is_active=True,
        name__icontains=specialty.name if specialty else "",
    ).first() if specialty else None

    with transaction.atomic():
        appointment = AppointmentRequest.objects.create(
            organization=organization,
            tour=tour,
            place=(practitioner.place if practitioner else getattr(tour, "place", None)),
            appointment_type=appointment_type,
            full_name=full_name[:255],
            email=email,
            phone=phone[:40],
            preferred_date=preferred_date,
            preferred_time=preferred_time,
            notes=str(payload.get("notes") or payload.get("reason_for_visit") or "").strip(),
            source="healthcare_ai",
            practitioner_name=practitioner.full_name if practitioner else "",
            specialty_name=specialty.name if specialty else "",
            reason_for_visit=str(payload.get("reason_for_visit") or "").strip(),
            appointment_mode=appointment_mode,
            metadata={
                "practitioner_id": practitioner.id if practitioner else None,
                "specialty_id": specialty.id if specialty else None,
                "source_url": practitioner.source_url if practitioner else "",
            },
        )

    calendar_synced = False
    connection = IntegrationConnection.objects.filter(
        organization=organization,
        provider=IntegrationConnection.Provider.GOOGLE_CALENDAR,
        status=IntegrationConnection.Status.ACTIVE,
    ).order_by("-is_default", "id").first()
    if connection and appointment.preferred_date:
        try:
            create_event_for_appointment(appointment, connection)
            calendar_synced = True
        except Exception:
            # The request remains safely stored even when the calendar provider
            # is temporarily unavailable. Public responses never expose provider details.
            calendar_synced = False

    return JsonResponse({
        "ok": True,
        "appointment_id": appointment.id,
        "status": appointment.status,
        "calendar_synced": calendar_synced,
        "message": "Your appointment request has been received. The facility will confirm the available time.",
    }, status=201)
