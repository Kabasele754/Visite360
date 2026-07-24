from __future__ import annotations

import math
from decimal import Decimal
from typing import Iterable

from django.db.models import Prefetch, Q
from django.urls import reverse

from apps.organizations.models import Organization
from apps.places.models import Place
from apps.tours.models import Scene360, Tour

from apps.domain_intelligence.models import MedicalPractitioner, MedicalSpecialty, PractitionerAvailability
from apps.domain_intelligence.services.query_parser import DiscoveryIntent


REAL_ESTATE_CATEGORIES = {
    Place.Category.HOUSE,
    Place.Category.APARTMENT,
    Place.Category.VILLA,
    Place.Category.STUDIO,
    Place.Category.OFFICE,
    Place.Category.BUILDING,
    Place.Category.LAND,
    Place.Category.REAL_ESTATE,
}
HOSPITALITY_CATEGORIES = {
    Place.Category.HOTEL,
    Place.Category.RESORT,
    Place.Category.GUEST_HOUSE,
    Place.Category.LODGE,
}
HEALTHCARE_CATEGORIES = {
    Place.Category.HOSPITAL,
    Place.Category.CLINIC,
    Place.Category.DENTAL_CLINIC,
    Place.Category.PHARMACY,
}


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    value = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(value), math.sqrt(max(0.0, 1 - value)))


def _safe_url(field) -> str:
    if not field:
        return ""
    try:
        return field.url
    except Exception:
        return str(field or "")


def _cover_url(tour: Tour) -> str:
    for field_name in ("thumbnail_image_mobile", "thumbnail_image", "thumbnail_source"):
        value = _safe_url(getattr(tour, field_name, None))
        if value:
            return value
    scene = next(iter(getattr(tour, "discovery_scenes", []) or []), None)
    if scene:
        for field_name in ("thumbnail_image", "image_360_preview", "image_360_mobile", "image_360"):
            value = _safe_url(getattr(scene, field_name, None))
            if value:
                return value
    return getattr(tour.place, "cover_image", "") or ""


def _profile_amenities(tour: Tour) -> set[str]:
    values: set[str] = set()
    profile = getattr(tour.place, "property_profile", None)
    for value in getattr(profile, "amenities", []) or []:
        values.add(str(value).casefold())
    if tour.parking:
        values.add("parking")
    if tour.balcon:
        values.add("balcony")
    if tour.ascenseur:
        values.add("elevator")
    return values


def _matches_amenities(tour: Tour, requested: Iterable[str]) -> bool:
    required = {str(value).casefold() for value in requested if value}
    return not required or required.issubset(_profile_amenities(tour))


def _reason_labels(tour: Tour, intent: DiscoveryIntent, *, distance: float | None) -> list[str]:
    reasons: list[str] = []
    profile = getattr(tour.place, "property_profile", None)
    bedrooms = getattr(profile, "bedrooms", None) or tour.chambres
    if intent.bedrooms is not None and bedrooms == intent.bedrooms:
        reasons.append(f"{bedrooms} bedrooms")
    if intent.city and tour.place.city and tour.place.city.casefold() == intent.city.casefold():
        reasons.append(tour.place.city)
    if intent.max_price is not None:
        value = getattr(profile, "price", None) or tour.price
        if value is not None and Decimal(value) <= intent.max_price:
            reasons.append("Within budget")
    if distance is not None:
        reasons.append(f"{distance:.1f} km away")
    if intent.category == "healthcare":
        reasons.append("Verified healthcare profile")
    if not reasons:
        reasons.append("360° virtual visit available")
    return reasons[:4]


def search_tours(
    intent: DiscoveryIntent,
    *,
    latitude: float | None = None,
    longitude: float | None = None,
    radius_km: float | None = None,
    limit: int = 12,
) -> list[dict]:
    scene_qs = Scene360.objects.filter(is_public=True).order_by("order", "id")
    base_queryset = (
        Tour.objects.select_related(
            "organization",
            "place",
            "place__property_profile",
            "place__hospitality_profile",
            "place__healthcare_profile",
        )
        .prefetch_related(Prefetch("scenes", queryset=scene_qs, to_attr="discovery_scenes"))
        .filter(
            status=Tour.Status.PUBLISHED,
            organization__status=Organization.Status.ACTIVE,
            place__status=Place.Status.PUBLISHED,
        )
    )
    queryset = base_queryset
    normalized_query = " ".join(str(intent.raw_query or "").casefold().split())
    generic_queries = {
        "tour", "tours", "virtual tour", "virtual tours", "360 tour", "360 tours",
        "visit", "visits", "virtual visit", "virtual visits", "all tours",
    }
    direct_match_ids = []
    if normalized_query and normalized_query not in generic_queries:
        direct_match_ids = list(
            base_queryset.filter(
                Q(title__icontains=normalized_query)
                | Q(place__name__icontains=normalized_query)
                | Q(organization__name__icontains=normalized_query)
            ).values_list("pk", flat=True)[:50]
        )

    if intent.category == "healthcare":
        queryset = queryset.filter(place__category__in=HEALTHCARE_CATEGORIES)
    elif intent.category == "hotel":
        queryset = queryset.filter(place__category__in=HOSPITALITY_CATEGORIES)
    elif intent.category in {"house", "apartment", "studio", "office"}:
        category_map = {
            "house": [Place.Category.HOUSE, Place.Category.VILLA, Place.Category.REAL_ESTATE],
            "apartment": [Place.Category.APARTMENT, Place.Category.REAL_ESTATE],
            "studio": [Place.Category.STUDIO, Place.Category.APARTMENT, Place.Category.REAL_ESTATE],
            "office": [Place.Category.OFFICE, Place.Category.BUILDING, Place.Category.REAL_ESTATE],
        }
        queryset = queryset.filter(place__category__in=category_map[intent.category])
    elif intent.listing_type or intent.bedrooms is not None:
        queryset = queryset.filter(place__category__in=REAL_ESTATE_CATEGORIES)

    location_query = (intent.city or intent.location_text or "").strip()
    if location_query:
        queryset = queryset.filter(
            Q(place__city__icontains=location_query)
            | Q(place__address_line__icontains=location_query)
            | Q(place__country__icontains=location_query)
            | Q(location__icontains=location_query)
        )

    if intent.listing_type:
        queryset = queryset.filter(place__property_profile__listing_type=intent.listing_type)
        queryset = queryset.filter(
            Q(place__property_profile__availability_status="available")
            | Q(place__property_profile__isnull=True)
        )
    if intent.bedrooms is not None:
        queryset = queryset.filter(
            Q(place__property_profile__bedrooms=intent.bedrooms)
            | Q(place__property_profile__isnull=True, chambres=intent.bedrooms)
        )
    if intent.bathrooms is not None:
        queryset = queryset.filter(place__property_profile__bathrooms__gte=intent.bathrooms)
    if intent.furnished is not None:
        queryset = queryset.filter(place__property_profile__furnished=intent.furnished)
    if intent.pet_friendly is not None:
        queryset = queryset.filter(place__property_profile__pet_friendly=intent.pet_friendly)
    if intent.max_price is not None:
        queryset = queryset.filter(
            Q(place__property_profile__price__lte=intent.max_price)
            | Q(place__property_profile__price__isnull=True, price__lte=intent.max_price)
        )

    text_terms = [term.strip(".,:;!?()[]{}") for term in normalized_query.split() if len(term.strip(".,:;!?()[]{}")) >= 2][:8]
    if intent.specialty:
        healthcare_org_ids = MedicalPractitioner.objects.filter(
            is_active=True,
        ).filter(
            Q(specialty__name__icontains=intent.specialty)
            | Q(professional_title__icontains=intent.specialty)
        ).values_list("organization_id", flat=True)
        queryset = queryset.filter(organization_id__in=healthcare_org_ids)
    elif intent.practitioner:
        healthcare_org_ids = MedicalPractitioner.objects.filter(
            is_active=True,
            full_name__icontains=intent.practitioner,
        ).values_list("organization_id", flat=True)
        queryset = queryset.filter(organization_id__in=healthcare_org_ids)
    elif normalized_query not in generic_queries and not any((intent.category, intent.city, intent.listing_type, intent.bedrooms, intent.max_price)) and text_terms:
        textual = Q()
        for term in text_terms:
            textual |= (
                Q(title__icontains=term)
                | Q(description__icontains=term)
                | Q(place__name__icontains=term)
                | Q(place__description__icontains=term)
                | Q(organization__name__icontains=term)
            )
        queryset = queryset.filter(textual)

    if direct_match_ids:
        queryset = (queryset | base_queryset.filter(pk__in=direct_match_ids)).distinct()

    queryset = queryset.order_by("-is_featured", "-rating", "-published_at", "-created_at")[: max(limit * 4, 30)]

    results: list[tuple[float, dict]] = []
    for tour in queryset:
        if not _matches_amenities(tour, intent.amenities):
            continue
        distance = None
        if latitude is not None and longitude is not None:
            place_lat = tour.place.latitude if tour.place.latitude is not None else tour.lat
            place_lng = tour.place.longitude if tour.place.longitude is not None else tour.lng
            if place_lat is not None and place_lng is not None:
                distance = _distance_km(float(latitude), float(longitude), float(place_lat), float(place_lng))
                if radius_km is not None and distance > radius_km:
                    continue

        property_profile = getattr(tour.place, "property_profile", None)
        hospitality = getattr(tour.place, "hospitality_profile", None)
        healthcare = getattr(tour.place, "healthcare_profile", None)
        price = getattr(property_profile, "price", None)
        currency = getattr(property_profile, "currency", "")
        if price is None:
            price = getattr(hospitality, "price_from", None) or tour.price
            currency = getattr(hospitality, "currency", "") or currency or "USD"

        bedrooms = getattr(property_profile, "bedrooms", None)
        if bedrooms in (None, 0):
            bedrooms = tour.chambres

        score = 0.0
        searchable_values = [
            str(tour.title or "").casefold(),
            str(tour.place.name or "").casefold(),
            str(tour.organization.name or "").casefold(),
            str(tour.description or "").casefold(),
            str(tour.place.description or "").casefold(),
        ]
        if normalized_query and normalized_query not in generic_queries:
            if any(normalized_query == value for value in searchable_values[:3]):
                score += 120
            elif any(normalized_query in value for value in searchable_values[:3]):
                score += 80
            for term in text_terms:
                if term in searchable_values[0]:
                    score += 18
                elif any(term in value for value in searchable_values[1:3]):
                    score += 12
                elif any(term in value for value in searchable_values[3:]):
                    score += 5
        score += 30 if tour.is_featured else 0
        score += float(tour.rating or 0) * 4
        score += 30 if intent.city and tour.place.city.casefold() == intent.city.casefold() else 0
        score += 24 if intent.bedrooms is not None and bedrooms == intent.bedrooms else 0
        score += 18 if intent.category == "healthcare" and healthcare else 0
        score += max(0, 20 - (distance or 0)) if distance is not None else 0

        practitioners = []
        specialties = []
        if intent.category == "healthcare" or intent.specialty or intent.practitioner:
            specialty_qs = MedicalSpecialty.objects.filter(
                organization=tour.organization,
                is_active=True,
            ).order_by("name")
            if intent.specialty:
                specialty_qs = specialty_qs.filter(name__icontains=intent.specialty)
            specialties = [
                {"id": item.id, "name": item.name, "source_url": item.source_url}
                for item in specialty_qs[:12]
            ]
            availability_qs = PractitionerAvailability.objects.filter(is_active=True).order_by("weekday", "starts_at")
            practitioner_qs = MedicalPractitioner.objects.select_related("specialty").prefetch_related(
                Prefetch("availability_slots", queryset=availability_qs, to_attr="public_availability_slots")
            ).filter(
                organization=tour.organization,
                is_active=True,
            )
            if intent.specialty:
                practitioner_qs = practitioner_qs.filter(
                    Q(specialty__name__icontains=intent.specialty)
                    | Q(professional_title__icontains=intent.specialty)
                )
            if intent.practitioner:
                practitioner_qs = practitioner_qs.filter(full_name__icontains=intent.practitioner)
            practitioners = [
                {
                    "id": item.id,
                    "name": item.full_name,
                    "title": item.professional_title,
                    "specialty": item.specialty.name if item.specialty else "",
                    "contact": item.public_contact_payload(),
                    "availability": [
                        {
                            "weekday": slot.weekday,
                            "weekday_label": slot.get_weekday_display(),
                            "starts_at": slot.starts_at.strftime("%H:%M"),
                            "ends_at": slot.ends_at.strftime("%H:%M"),
                            "mode": slot.appointment_mode,
                            "location": slot.location_label,
                        }
                        for slot in getattr(item, "public_availability_slots", [])[:8]
                    ],
                    "source_url": item.source_url,
                }
                for item in practitioner_qs[:5]
            ]

        payload = {
            "tour_id": tour.id,
            "title": tour.title,
            "description": tour.description or tour.place.description,
            "organization": {
                "name": tour.organization.name,
                "slug": tour.organization.slug,
                "public_phone": tour.organization.public_phone,
                "public_email": tour.organization.public_email,
                "booking_url": tour.organization.booking_url,
            },
            "place": {
                "name": tour.place.name,
                "category": tour.place.category,
                "category_label": tour.place.get_category_display(),
                "address": tour.place.address_line,
                "city": tour.place.city,
                "country": tour.place.country,
                "latitude": float(tour.place.latitude) if tour.place.latitude is not None else tour.lat,
                "longitude": float(tour.place.longitude) if tour.place.longitude is not None else tour.lng,
            },
            "preview_url": reverse(
                "tour-preview-public",
                kwargs={"organization_slug": tour.organization.slug, "tour_id": tour.id},
            ),
            "cover_url": _cover_url(tour),
            "price": str(price) if price is not None else "",
            "currency": currency,
            "bedrooms": bedrooms,
            "bathrooms": str(getattr(property_profile, "bathrooms", "") or ""),
            "listing_type": getattr(property_profile, "listing_type", ""),
            "amenities": sorted(_profile_amenities(tour)),
            "distance_km": round(distance, 2) if distance is not None else None,
            "reasons": _reason_labels(tour, intent, distance=distance),
            "appointment": {
                "available": bool(healthcare or tour.organization.booking_url),
                "phone": getattr(healthcare, "appointment_phone", "") or tour.organization.public_phone,
                "email": getattr(healthcare, "appointment_email", "") or tour.organization.public_email,
                "url": getattr(healthcare, "appointment_url", "") or tour.organization.booking_url,
            },
            "specialties": specialties,
            "practitioners": practitioners,
        }
        results.append((score, payload))

    results.sort(key=lambda item: item[0], reverse=True)
    return [payload for _, payload in results[:limit]]
