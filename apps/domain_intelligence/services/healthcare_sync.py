from __future__ import annotations

import json
import re
from collections.abc import Iterable
from typing import Any

from bs4 import BeautifulSoup
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.knowledge.models import KnowledgeSource
from apps.knowledge.services.crawler import CrawledPage, crawl_website, discover_social_links
from apps.knowledge.services.indexing import index_document, upsert_document
from apps.organizations.models import Organization
from apps.places.models import Place

from apps.domain_intelligence.models import (
    HealthcareFacilityProfile,
    MedicalPractitioner,
    MedicalSpecialty,
    OrganizationIntelligenceProfile,
    VerifiedSourceFact,
)

HEALTHCARE_SCHEMA_TYPES = {
    "Hospital",
    "MedicalClinic",
    "Physician",
    "Dentist",
    "MedicalOrganization",
    "MedicalBusiness",
}


_DOCTOR_NAME_RE = re.compile(
    r"\b(?:Dr\.?|Doctor|Docteur|Prof\.?|Professor)\s+([A-ZÀ-ÖØ-Ý][A-Za-zÀ-ÖØ-öø-ÿ'’.-]+(?:\s+[A-ZÀ-ÖØ-Ý][A-Za-zÀ-ÖØ-öø-ÿ'’.-]+){1,4})",
    re.IGNORECASE,
)
_MEDICAL_PAGE_TOKENS = {
    "doctor", "doctors", "physician", "physicians", "practitioner", "practitioners",
    "docteur", "docteurs", "médecin", "medecin", "specialist", "specialists",
    "specialiste", "spécialiste", "medical team", "our team", "équipe médicale", "equipe medicale",
}
_SPECIALTY_PAGE_TOKENS = {
    "department", "departments", "service", "services", "specialty", "specialties",
    "speciality", "specialities", "département", "departement", "spécialité", "specialite",
    "clinic", "centre", "center",
}


def _page_tokens(page: CrawledPage) -> str:
    return f"{page.url} {page.title}".casefold()


def _public_links(page: CrawledPage) -> tuple[str, str]:
    soup = BeautifulSoup(page.html, "html.parser")
    phone = ""
    email = ""
    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href") or "").strip()
        if not phone and href.lower().startswith("tel:"):
            phone = _text(href[4:], 60)
        if not email and href.lower().startswith("mailto:"):
            email = _text(href[7:].split("?", 1)[0], 254)
        if phone and email:
            break
    return phone, email


def _heuristic_doctor_names(page: CrawledPage) -> list[str]:
    marker = _page_tokens(page)
    if not any(token in marker for token in _MEDICAL_PAGE_TOKENS):
        return []
    soup = BeautifulSoup(page.html, "html.parser")
    candidates: list[str] = []
    for node in soup.select("h1, h2, h3, h4, [class*='doctor'], [class*='physician'], [class*='practitioner'], [class*='provider']"):
        text = _text(node.get_text(" ", strip=True), 240)
        for match in _DOCTOR_NAME_RE.finditer(text):
            prefix = text[match.start():match.start(1)].strip()
            full_name = f"{prefix} {match.group(1)}".strip()
            full_name = re.sub(r"\s+", " ", full_name)[:255]
            key = full_name.casefold()
            if key not in {item.casefold() for item in candidates}:
                candidates.append(full_name)
    return candidates[:50]


def _heuristic_specialty_name(page: CrawledPage) -> str:
    marker = _page_tokens(page)
    if not any(token in marker for token in _SPECIALTY_PAGE_TOKENS):
        return ""
    title = re.sub(r"\s*[|–—-]\s*[^|–—-]{2,80}$", "", _text(page.title, 180)).strip()
    title = re.sub(
        r"^(?:department of|service de|département de|departement de|specialty|speciality)\s+",
        "",
        title,
        flags=re.IGNORECASE,
    ).strip()
    generic = {"home", "services", "our services", "departments", "medical services", "contact", "about us"}
    if not title or title.casefold() in generic or len(title) < 3:
        return ""
    return title[:180]


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _schema_types(value: Any) -> set[str]:
    return {str(item).split("/")[-1] for item in _as_list(value)}


def _iter_json_ld(page: CrawledPage) -> Iterable[dict]:
    soup = BeautifulSoup(page.html, "html.parser")
    for script in soup.find_all("script", attrs={"type": re.compile(r"application/ld\+json", re.I)}):
        raw = script.string or script.get_text("", strip=True)
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        queue = _as_list(payload)
        while queue:
            item = queue.pop(0)
            if not isinstance(item, dict):
                continue
            graph = item.get("@graph")
            if isinstance(graph, list):
                queue.extend(graph)
            yield item


def _text(value: Any, limit: int = 500) -> str:
    if isinstance(value, dict):
        value = value.get("name") or value.get("text") or value.get("url") or ""
    if isinstance(value, list):
        value = ", ".join(_text(item, limit=limit) for item in value if item)
    return " ".join(str(value or "").split())[:limit]


def _url(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("url") or value.get("@id") or ""
    return _text(value, 500)


def _specialty_names(item: dict) -> list[str]:
    values = []
    for key in ("medicalSpecialty", "specialty", "knowsAbout", "department"):
        for value in _as_list(item.get(key)):
            name = _text(value, 180)
            if name and name.casefold() not in {existing.casefold() for existing in values}:
                values.append(name)
    return values[:20]


def _place_for_organization(organization: Organization) -> Place | None:
    healthcare_categories = [
        Place.Category.HOSPITAL,
        Place.Category.CLINIC,
        Place.Category.DENTAL_CLINIC,
        Place.Category.PHARMACY,
    ]
    return (
        organization.places.filter(category__in=healthcare_categories)
        .order_by("-status", "id")
        .first()
    )


def _upsert_fact(*, organization, place, entity_type, entity_key, field_name, value, source_url, confidence="1.000"):
    if value in (None, "", [], {}):
        return None
    fact, _ = VerifiedSourceFact.objects.update_or_create(
        organization=organization,
        entity_type=entity_type,
        entity_key=(entity_key or "")[:255],
        field_name=field_name[:120],
        source_url=source_url,
        defaults={
            "place": place,
            "value": value if isinstance(value, (dict, list)) else {"value": value},
            "confidence": confidence,
            "verified_at": timezone.now(),
            "is_public": True,
        },
    )
    return fact


def sync_healthcare_organization(
    organization: Organization,
    *,
    max_pages: int | None = None,
    pages: list[CrawledPage] | None = None,
    source: KnowledgeSource | None = None,
    index_pages: bool = True,
    manage_profile_status: bool = True,
) -> dict:
    profile, _ = OrganizationIntelligenceProfile.objects.get_or_create(
        organization=organization,
        defaults={"domain_kind": OrganizationIntelligenceProfile.DomainKind.HEALTHCARE},
    )
    if profile.domain_kind == OrganizationIntelligenceProfile.DomainKind.GENERAL:
        profile.domain_kind = OrganizationIntelligenceProfile.DomainKind.HEALTHCARE

    website_url = (organization.website_url or "").strip()
    if not website_url:
        raise ValueError("The organization does not have a website URL.")

    if manage_profile_status:
        profile.last_sync_status = "running"
        profile.last_sync_error = ""
        profile.save(update_fields=("domain_kind", "last_sync_status", "last_sync_error", "updated_at"))

    page_limit = max_pages or profile.website_sync_max_pages or 30
    pages = pages if pages is not None else crawl_website(website_url, max_pages=page_limit, same_domain_only=True)
    place = _place_for_organization(organization)
    source = source or KnowledgeSource.objects.update_or_create(
        organization=organization,
        name="Official organization website",
        defaults={
            "source_type": KnowledgeSource.SourceType.WEBSITE,
            "url": website_url,
            "status": KnowledgeSource.Status.CRAWLING,
            "crawl_same_domain_only": True,
            "max_pages": page_limit,
            "is_active": True,
            "last_error": "",
        },
    )[0]

    discovered = discover_social_links(pages)
    changed = []
    for field, value in discovered.items():
        if not getattr(organization, field, ""):
            setattr(organization, field, value)
            changed.append(field)
    if changed:
        organization.social_links_verified_at = timezone.now()
        changed.append("social_links_verified_at")
        organization.save(update_fields=changed + ["updated_at"])

    indexed_chunks = 0
    practitioner_count = 0
    specialty_count = 0
    facility_updates = 0

    with transaction.atomic():
        facility = None
        if place:
            facility, _ = HealthcareFacilityProfile.objects.get_or_create(place=place)

        for page in pages:
            if index_pages:
                document = upsert_document(
                    source=source,
                    title=page.title,
                    content=page.text,
                    canonical_url=page.url,
                    metadata={"crawler": "beautifulsoup", "domain_intelligence": True},
                )
                indexed_chunks += index_document(document)

            # Many hospital websites do not publish complete JSON-LD. Extract
            # only explicit public contact links and clearly labelled doctor or
            # department headings; every record keeps the official source URL.
            page_phone, page_email = _public_links(page)
            if facility:
                facility_changed = False
                if page_phone and not facility.appointment_phone:
                    facility.appointment_phone = page_phone
                    facility_changed = True
                    facility_updates += 1
                if page_email and not facility.appointment_email:
                    facility.appointment_email = page_email
                    facility_changed = True
                    facility_updates += 1
                if facility_changed:
                    facility.source_url = page.url
                    facility.verified_at = timezone.now()
                    facility.save()

            specialty_name = _heuristic_specialty_name(page)
            heuristic_specialty = None
            if specialty_name:
                heuristic_specialty, specialty_created = MedicalSpecialty.objects.update_or_create(
                    organization=organization,
                    slug=slugify(specialty_name)[:200] or "general-medicine",
                    defaults={
                        "name": specialty_name,
                        "source_url": page.url,
                        "verified_at": timezone.now(),
                        "is_active": True,
                    },
                )
                specialty_count += int(specialty_created)

            for doctor_name in _heuristic_doctor_names(page):
                practitioner, practitioner_created = MedicalPractitioner.objects.update_or_create(
                    organization=organization,
                    full_name=doctor_name,
                    specialty=heuristic_specialty,
                    defaults={
                        "place": place,
                        "source_url": page.url,
                        "verified_at": timezone.now(),
                        "is_active": True,
                        "metadata": {"extraction": "official-page-heading"},
                    },
                )
                practitioner_count += int(practitioner_created)
                _upsert_fact(
                    organization=organization,
                    place=place,
                    entity_type="medical_practitioner",
                    entity_key=str(practitioner.id),
                    field_name="full_name",
                    value=doctor_name,
                    source_url=page.url,
                    confidence="0.900",
                )

            for item in _iter_json_ld(page):
                types = _schema_types(item.get("@type"))
                if not types.intersection(HEALTHCARE_SCHEMA_TYPES):
                    continue

                entity_name = _text(item.get("name"), 255)
                source_url = _url(item.get("url")) or page.url
                phone = _text(item.get("telephone"), 60)
                email = _text(item.get("email"), 254).removeprefix("mailto:")
                booking_url = _url(item.get("appointment") or item.get("potentialAction"))
                specialties = _specialty_names(item)

                if "Physician" in types or "Dentist" in types:
                    if not entity_name:
                        continue
                    specialty = None
                    if specialties:
                        specialty_name = specialties[0]
                        specialty, specialty_created = MedicalSpecialty.objects.update_or_create(
                            organization=organization,
                            slug=slugify(specialty_name)[:200] or "general-medicine",
                            defaults={
                                "name": specialty_name,
                                "source_url": source_url,
                                "verified_at": timezone.now(),
                                "is_active": True,
                            },
                        )
                        specialty_count += int(specialty_created)
                    practitioner, created = MedicalPractitioner.objects.update_or_create(
                        organization=organization,
                        full_name=entity_name,
                        specialty=specialty,
                        defaults={
                            "place": place,
                            "professional_title": _text(item.get("jobTitle"), 180),
                            "bio": _text(item.get("description"), 4000),
                            "languages": [_text(value, 80) for value in _as_list(item.get("knowsLanguage")) if _text(value, 80)],
                            "public_phone": phone,
                            "public_email": email,
                            "booking_url": booking_url,
                            "show_public_phone": bool(phone),
                            "show_public_email": bool(email),
                            "source_url": source_url,
                            "verified_at": timezone.now(),
                            "is_active": True,
                            "metadata": {"schema_types": sorted(types)},
                        },
                    )
                    practitioner_count += int(created)
                    for field_name, value in {
                        "full_name": entity_name,
                        "specialty": specialties,
                        "public_phone": phone,
                        "public_email": email,
                        "booking_url": booking_url,
                    }.items():
                        _upsert_fact(
                            organization=organization,
                            place=place,
                            entity_type="medical_practitioner",
                            entity_key=str(practitioner.id),
                            field_name=field_name,
                            value=value,
                            source_url=source_url,
                        )
                    continue

                if facility:
                    if phone and not facility.appointment_phone:
                        facility.appointment_phone = phone
                        facility_updates += 1
                    if email and not facility.appointment_email:
                        facility.appointment_email = email
                        facility_updates += 1
                    if booking_url and not facility.appointment_url:
                        facility.appointment_url = booking_url
                        facility_updates += 1
                    opening_hours = [_text(value, 180) for value in _as_list(item.get("openingHours") or item.get("openingHoursSpecification")) if _text(value, 180)]
                    if opening_hours:
                        facility.opening_hours = opening_hours
                    if specialties:
                        facility.specialties = sorted(set((facility.specialties or []) + specialties))
                    facility.source_url = source_url
                    facility.verified_at = timezone.now()
                    facility.save()
                    for field_name, value in {
                        "name": entity_name,
                        "appointment_phone": phone,
                        "appointment_email": email,
                        "appointment_url": booking_url,
                        "specialties": specialties,
                        "opening_hours": opening_hours,
                    }.items():
                        _upsert_fact(
                            organization=organization,
                            place=place,
                            entity_type="healthcare_facility",
                            entity_key=str(place.id) if place else organization.slug,
                            field_name=field_name,
                            value=value,
                            source_url=source_url,
                        )

        if index_pages:
            source.status = KnowledgeSource.Status.INDEXED
            source.last_synced_at = timezone.now()
            source.last_error = ""
            source.save(update_fields=("status", "last_synced_at", "last_error", "updated_at"))
        if manage_profile_status:
            profile.last_synced_at = timezone.now()
            profile.last_sync_status = "succeeded"
            profile.last_sync_error = ""
            profile.save(update_fields=("last_synced_at", "last_sync_status", "last_sync_error", "updated_at"))

    return {
        "organization_id": organization.id,
        "pages": len(pages),
        "chunks_indexed": indexed_chunks,
        "practitioners_created": practitioner_count,
        "specialties_created": specialty_count,
        "facility_updates": facility_updates,
    }
