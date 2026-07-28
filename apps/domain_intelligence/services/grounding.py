from __future__ import annotations

from django.db.models import Q

from apps.domain_intelligence.models import (
    HealthcareFacilityProfile,
    HospitalityProfile,
    MedicalPractitioner,
    PropertyListingProfile,
    VerifiedSourceFact,
)


def build_domain_grounding(organization, query: str = "", *, limit: int = 6) -> dict:
    limit = max(1, min(int(limit or 6), 10))
    normalized = str(query or "").strip()
    practitioners_qs = MedicalPractitioner.objects.select_related("specialty", "place").filter(
        organization=organization,
        is_active=True,
    )
    if normalized:
        words = [word for word in normalized.split() if len(word) >= 3][:8]
        if words:
            criteria = Q()
            for word in words:
                criteria |= (
                    Q(full_name__icontains=word)
                    | Q(professional_title__icontains=word)
                    | Q(specialty__name__icontains=word)
                    | Q(bio__icontains=word)
                )
            practitioners_qs = practitioners_qs.filter(criteria)
    practitioners = []
    for item in practitioners_qs.distinct()[:limit]:
        practitioners.append({
            "id": item.id,
            "name": item.full_name,
            "title": item.professional_title,
            "specialty": item.specialty.name if item.specialty else "",
            "bio": item.bio[:600],
            "languages": item.languages,
            "public_contact": item.public_contact_payload(),
            "booking_mode": item.booking_mode,
            "source_url": item.source_url,
            "verified_at": item.verified_at.isoformat() if item.verified_at else None,
        })

    facilities = [
        {
            "place_id": item.place_id,
            "place": item.place.name,
            "appointment_phone": item.appointment_phone,
            "appointment_email": item.appointment_email,
            "appointment_url": item.appointment_url,
            "emergency_phone": item.emergency_phone,
            "opening_hours": item.opening_hours,
            "specialties": item.specialties,
            "telemedicine_available": item.telemedicine_available,
            "source_url": item.source_url,
            "verified_at": item.verified_at.isoformat() if item.verified_at else None,
        }
        for item in HealthcareFacilityProfile.objects.select_related("place").filter(
            place__organization=organization,
            is_active=True,
        )[:limit]
    ]
    properties = [
        {
            "place_id": item.place_id,
            "place": item.place.name,
            "city": item.place.city,
            "listing_type": item.listing_type,
            "property_type": item.property_type,
            "bedrooms": item.bedrooms,
            "bathrooms": str(item.bathrooms),
            "parking_spaces": item.parking_spaces,
            "furnished": item.furnished,
            "price": str(item.price) if item.price is not None else "",
            "currency": item.currency,
            "amenities": item.amenities,
            "availability_status": item.availability_status,
            "source_url": item.source_url,
        }
        for item in PropertyListingProfile.objects.select_related("place").filter(
            place__organization=organization,
        )[:limit]
    ]
    hospitality = [
        {
            "place_id": item.place_id,
            "place": item.place.name,
            "city": item.place.city,
            "star_rating": str(item.star_rating) if item.star_rating is not None else "",
            "price_from": str(item.price_from) if item.price_from is not None else "",
            "currency": item.currency,
            "amenities": item.amenities,
            "booking_url": item.booking_url,
            "source_url": item.source_url,
        }
        for item in HospitalityProfile.objects.select_related("place").filter(
            place__organization=organization,
            is_available=True,
        )[:limit]
    ]
    facts = [
        {
            "entity_type": item.entity_type,
            "entity_key": item.entity_key,
            "field": item.field_name,
            "value": item.value,
            "source_url": item.source_url,
            "confidence": str(item.confidence),
            "verified_at": item.verified_at.isoformat(),
        }
        for item in VerifiedSourceFact.objects.filter(
            organization=organization,
            is_public=True,
        )[:limit]
    ]
    return {
        "healthcare": {
            "facilities": facilities,
            "practitioners": practitioners,
        },
        "real_estate": properties,
        "hospitality": hospitality,
        "verified_facts": facts,
        "grounding_policy": (
            "Only present public contact details and factual claims contained in these verified records or cited knowledge sources. "
            "Never invent doctor availability, prices, medical advice, property availability or contact information."
        ),
    }
