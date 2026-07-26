from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db.models import Count
from django.utils import timezone

from apps.domain_intelligence.models import (
    HealthcareFacilityProfile,
    HospitalityProfile,
    IntelligenceReviewItem,
    MedicalPractitioner,
    MedicalSpecialty,
    OrganizationIntelligenceProfile,
    OrganizationIntelligenceRun,
    PropertyListingProfile,
    VerifiedSourceFact,
)
from apps.knowledge.models import KnowledgeChunk, KnowledgeDocument, KnowledgeSource, ServiceOffering
from apps.places.models import Place
from apps.tours.models import Tour


@dataclass(slots=True)
class ReadinessResult:
    score: int
    status: str
    breakdown: dict[str, Any]


def _ratio_score(completed: int, total: int, weight: int) -> int:
    if total <= 0:
        return 0
    return round(weight * min(1.0, completed / total))


def _domain_kind_from_places(organization) -> str:
    categories = set(organization.places.values_list("category", flat=True))
    healthcare = bool(categories.intersection({Place.Category.HOSPITAL, Place.Category.CLINIC, Place.Category.DENTAL_CLINIC, Place.Category.PHARMACY}))
    property_domain = bool(categories.intersection({Place.Category.HOUSE, Place.Category.APARTMENT, Place.Category.VILLA, Place.Category.STUDIO, Place.Category.OFFICE, Place.Category.BUILDING, Place.Category.LAND, Place.Category.REAL_ESTATE}))
    hospitality = bool(categories.intersection({Place.Category.HOTEL, Place.Category.RESORT, Place.Category.GUEST_HOUSE, Place.Category.LODGE}))
    enabled = sum((healthcare, property_domain, hospitality))
    if enabled > 1:
        return OrganizationIntelligenceProfile.DomainKind.MIXED
    if healthcare:
        return OrganizationIntelligenceProfile.DomainKind.HEALTHCARE
    if property_domain:
        return OrganizationIntelligenceProfile.DomainKind.REAL_ESTATE
    if hospitality:
        return OrganizationIntelligenceProfile.DomainKind.HOSPITALITY
    return OrganizationIntelligenceProfile.DomainKind.GENERAL


def calculate_organization_readiness(organization, *, persist: bool = True) -> ReadinessResult:
    profile, _ = OrganizationIntelligenceProfile.objects.get_or_create(organization=organization)
    if profile.domain_kind == OrganizationIntelligenceProfile.DomainKind.GENERAL:
        inferred = _domain_kind_from_places(organization)
        if inferred != profile.domain_kind:
            profile.domain_kind = inferred

    places = organization.places.all()
    place_count = places.count()
    published_places = places.filter(status=Place.Status.PUBLISHED).count()
    tours = Tour.objects.filter(organization=organization)
    tour_count = tours.count()
    published_tours = tours.filter(status=Tour.Status.PUBLISHED).count()

    source_qs = KnowledgeSource.objects.filter(organization=organization, is_active=True)
    indexed_sources = source_qs.filter(status=KnowledgeSource.Status.INDEXED).count()
    document_qs = KnowledgeDocument.objects.filter(source__organization=organization, is_active=True)
    document_count = document_qs.count()
    chunk_count = KnowledgeChunk.objects.filter(document__source__organization=organization).count()
    service_count = ServiceOffering.objects.filter(organization=organization, is_active=True).count()
    fact_count = VerifiedSourceFact.objects.filter(organization=organization, is_public=True).count()
    pending_reviews = IntelligenceReviewItem.objects.filter(organization=organization, status=IntelligenceReviewItem.Status.PENDING).count()
    active_runs = OrganizationIntelligenceRun.objects.filter(
        organization=organization,
        status__in=[OrganizationIntelligenceRun.Status.QUEUED, OrganizationIntelligenceRun.Status.RUNNING],
    ).count()

    identity_checks = [
        bool(organization.name),
        bool(organization.description and len(organization.description.strip()) >= 40),
        bool(organization.logo),
        bool(place_count),
    ]
    contact_checks = [
        bool(organization.website_url),
        bool(organization.public_phone or organization.public_email),
        bool(organization.booking_url or service_count),
        bool(any((organization.facebook_url, organization.instagram_url, organization.linkedin_url, organization.youtube_url, organization.tiktok_url))),
    ]
    knowledge_checks = [
        bool(source_qs.count()),
        bool(indexed_sources),
        bool(document_count),
        bool(chunk_count),
        bool(fact_count),
    ]
    discovery_checks = [
        bool(published_places),
        bool(published_tours),
        bool(tour_count and tours.exclude(description="").exists()),
    ]

    domain_checks: list[bool] = [bool(profile.domain_kind)]
    domain_detail = "General business data"
    if profile.domain_kind in {OrganizationIntelligenceProfile.DomainKind.HEALTHCARE, OrganizationIntelligenceProfile.DomainKind.MIXED}:
        facilities = HealthcareFacilityProfile.objects.filter(place__organization=organization, is_active=True).count()
        doctors = MedicalPractitioner.objects.filter(organization=organization, is_active=True).count()
        specialties = MedicalSpecialty.objects.filter(organization=organization, is_active=True).count()
        domain_checks.extend([bool(facilities), bool(doctors or specialties), bool(service_count or fact_count)])
        domain_detail = f"{facilities} facilities · {doctors} practitioners · {specialties} specialties"
    elif profile.domain_kind == OrganizationIntelligenceProfile.DomainKind.REAL_ESTATE:
        listings = PropertyListingProfile.objects.filter(place__organization=organization).count()
        domain_checks.extend([bool(listings), bool(service_count or published_tours), bool(fact_count)])
        domain_detail = f"{listings} property profiles"
    elif profile.domain_kind == OrganizationIntelligenceProfile.DomainKind.HOSPITALITY:
        hospitality = HospitalityProfile.objects.filter(place__organization=organization).count()
        domain_checks.extend([bool(hospitality), bool(service_count or published_tours), bool(fact_count)])
        domain_detail = f"{hospitality} hospitality profiles"
    else:
        domain_checks.extend([bool(service_count), bool(fact_count)])
        domain_detail = f"{service_count} services · {fact_count} verified facts"

    sections = {
        "identity": {
            "label": "Identity & presentation",
            "score": _ratio_score(sum(identity_checks), len(identity_checks), 20),
            "max": 20,
            "completed": sum(identity_checks),
            "total": len(identity_checks),
            "detail": f"Organization profile, logo and {place_count} places",
        },
        "contact": {
            "label": "Public contact & conversion",
            "score": _ratio_score(sum(contact_checks), len(contact_checks), 20),
            "max": 20,
            "completed": sum(contact_checks),
            "total": len(contact_checks),
            "detail": "Website, contact, booking and social links",
        },
        "knowledge": {
            "label": "AI knowledge readiness",
            "score": _ratio_score(sum(knowledge_checks), len(knowledge_checks), 25),
            "max": 25,
            "completed": sum(knowledge_checks),
            "total": len(knowledge_checks),
            "detail": f"{indexed_sources}/{source_qs.count()} sources indexed · {document_count} documents · {chunk_count} chunks",
        },
        "discovery": {
            "label": "Search & virtual tour discovery",
            "score": _ratio_score(sum(discovery_checks), len(discovery_checks), 15),
            "max": 15,
            "completed": sum(discovery_checks),
            "total": len(discovery_checks),
            "detail": f"{published_places} published places · {published_tours} published tours",
        },
        "domain": {
            "label": "Domain intelligence",
            "score": _ratio_score(sum(domain_checks), len(domain_checks), 20),
            "max": 20,
            "completed": sum(domain_checks),
            "total": len(domain_checks),
            "detail": domain_detail,
        },
    }
    score = min(100, sum(section["score"] for section in sections.values()))

    if active_runs:
        status = OrganizationIntelligenceProfile.ReadinessStatus.IN_PROGRESS
    elif score >= 80 and pending_reviews == 0:
        status = OrganizationIntelligenceProfile.ReadinessStatus.READY
    elif score >= 55 or pending_reviews:
        status = OrganizationIntelligenceProfile.ReadinessStatus.REVIEW
    else:
        status = OrganizationIntelligenceProfile.ReadinessStatus.NOT_READY

    next_actions: list[dict[str, str]] = []
    if not organization.website_url:
        next_actions.append({"priority": "high", "label": "Add the official website URL", "detail": "Website collection cannot start without an approved public domain."})
    if not organization.description or len(organization.description.strip()) < 40:
        next_actions.append({"priority": "medium", "label": "Complete the organization description", "detail": "A clear public description improves search and grounded AI answers."})
    if not (organization.public_phone or organization.public_email):
        next_actions.append({"priority": "high", "label": "Confirm a public contact channel", "detail": "Guests need a verified phone number or email address."})
    if not indexed_sources or not chunk_count:
        next_actions.append({"priority": "high", "label": "Index the official knowledge source", "detail": "The client-facing agent needs searchable website documents and embeddings."})
    if not published_tours:
        next_actions.append({"priority": "medium", "label": "Publish at least one virtual tour", "detail": "Discovery results require a public tour that guests can open."})
    if pending_reviews:
        next_actions.append({"priority": "high", "label": f"Review {pending_reviews} collected suggestion(s)", "detail": "Approve or reject conflicts before the information becomes client-facing."})
    if not service_count:
        next_actions.append({"priority": "medium", "label": "Structure service offerings", "detail": "Services make the organization searchable and actionable for guests."})

    breakdown = {
        "sections": sections,
        "next_actions": next_actions[:8],
        "counts": {
            "places": place_count,
            "published_places": published_places,
            "tours": tour_count,
            "published_tours": published_tours,
            "knowledge_sources": source_qs.count(),
            "indexed_sources": indexed_sources,
            "documents": document_count,
            "chunks": chunk_count,
            "services": service_count,
            "verified_facts": fact_count,
            "pending_reviews": pending_reviews,
            "active_runs": active_runs,
        },
        "generated_at": timezone.now().isoformat(),
    }

    if persist:
        profile.readiness_score = score
        profile.readiness_status = status
        profile.readiness_breakdown = breakdown
        profile.readiness_checked_at = timezone.now()
        profile.save(update_fields=(
            "domain_kind", "readiness_score", "readiness_status", "readiness_breakdown",
            "readiness_checked_at", "updated_at",
        ))
    return ReadinessResult(score=score, status=status, breakdown=breakdown)


def readiness_distribution() -> dict[str, int]:
    values = {choice: 0 for choice, _ in OrganizationIntelligenceProfile.ReadinessStatus.choices}
    rows = OrganizationIntelligenceProfile.objects.values("readiness_status").annotate(total=Count("id"))
    for row in rows:
        values[row["readiness_status"]] = row["total"]
    return values
