from __future__ import annotations

import json
import logging
import re
from datetime import timedelta
from decimal import Decimal
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.ai_core.services.router import AIProviderRouter
from apps.domain_intelligence.models import (
    HealthcareFacilityProfile,
    HospitalityProfile,
    IntelligenceReviewItem,
    OrganizationIntelligenceProfile,
    OrganizationIntelligenceRun,
    PropertyListingProfile,
    VerifiedSourceFact,
)
from apps.knowledge.models import KnowledgeSource, ServiceOffering
from apps.knowledge.services.crawler import CrawledPage, crawl_website, discover_social_links
from apps.knowledge.services.indexing import index_document, upsert_document
from apps.organizations.models import Organization
from apps.places.models import Place

from .healthcare_sync import sync_healthcare_organization
from .readiness import calculate_organization_readiness

logger = logging.getLogger(__name__)

_ORGANIZATION_SCHEMA_TYPES = {
    "Organization", "Corporation", "LocalBusiness", "ProfessionalService", "Store",
    "Hospital", "MedicalClinic", "Dentist", "Pharmacy", "Hotel", "LodgingBusiness",
    "Resort", "Restaurant", "RealEstateAgent", "EducationalOrganization",
}
_SERVICE_SCHEMA_TYPES = {"Service", "Offer", "MedicalProcedure"}
_BOOKING_WORDS = {
    "book", "booking", "appointment", "reserve", "reservation", "schedule",
    "rendez-vous", "rendezvous", "contact us", "get started", "request a quote",
}
_SERVICE_PATH_WORDS = {
    "service", "services", "treatment", "treatments", "department", "departments",
    "specialty", "specialties", "speciality", "specialities", "solutions", "what-we-do",
    "rooms", "accommodation", "facilities", "amenities", "properties", "listings",
}
_AMENITY_WORDS = {
    "wifi": "Wi-Fi", "wi-fi": "Wi-Fi", "parking": "Parking", "pool": "Swimming pool",
    "swimming pool": "Swimming pool", "restaurant": "Restaurant", "breakfast": "Breakfast",
    "gym": "Gym", "fitness": "Fitness centre", "spa": "Spa", "airport shuttle": "Airport shuttle",
    "wheelchair": "Wheelchair access", "accessible": "Accessibility", "air conditioning": "Air conditioning",
    "security": "Security", "generator": "Backup power", "garden": "Garden", "balcony": "Balcony",
}


def _clean_text(value: Any, limit: int = 4000) -> str:
    if isinstance(value, dict):
        value = value.get("name") or value.get("text") or value.get("description") or value.get("url") or ""
    if isinstance(value, list):
        value = ", ".join(_clean_text(item, limit=limit) for item in value if item)
    return " ".join(str(value or "").split())[:limit]


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _schema_types(value: Any) -> set[str]:
    return {str(item).split("/")[-1] for item in _as_list(value)}


def _iter_json_ld(page: CrawledPage) -> Iterable[dict[str, Any]]:
    soup = BeautifulSoup(page.html, "html.parser")
    for script in soup.find_all("script", attrs={"type": re.compile(r"application/ld\+json", re.I)}):
        raw = script.string or script.get_text("", strip=True)
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            continue
        queue = _as_list(payload)
        while queue:
            item = queue.pop(0)
            if not isinstance(item, dict):
                continue
            if isinstance(item.get("@graph"), list):
                queue.extend(item["@graph"])
            yield item


def _safe_source_url(candidate: str, allowed_urls: set[str], fallback: str) -> str:
    candidate = str(candidate or "").strip()
    if candidate in allowed_urls:
        return candidate
    return fallback


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool, list, dict)):
        return value
    return str(value)


def _same_value(left: Any, right: Any) -> bool:
    if isinstance(left, str) or isinstance(right, str):
        return _clean_text(left).casefold() == _clean_text(right).casefold()
    return left == right


def _record_fact(*, organization, place, entity_type: str, entity_key: str, field_name: str, value: Any, source_url: str, confidence: float = 0.95) -> VerifiedSourceFact | None:
    if value in (None, "", [], {}):
        return None
    fact, _ = VerifiedSourceFact.objects.update_or_create(
        organization=organization,
        entity_type=entity_type,
        entity_key=entity_key,
        field_name=field_name,
        source_url=source_url,
        defaults={
            "place": place,
            "value": _json_value(value),
            "confidence": Decimal(str(max(0.0, min(1.0, confidence)))),
            "verified_at": timezone.now(),
            "is_public": True,
        },
    )
    return fact


def _create_review_item(*, run, organization, place, item_type: str, target_model: str, target_field: str, label: str, current_value: Any, proposed_value: Any, source_url: str, confidence: float, reason: str = "", entity_key: str = "") -> IntelligenceReviewItem:
    candidates = IntelligenceReviewItem.objects.filter(
        organization=organization,
        status=IntelligenceReviewItem.Status.PENDING,
        target_model=target_model,
        target_field=target_field,
        source_url=source_url,
    ).order_by("-created_at")[:20]
    for existing in candidates:
        if existing.proposed_value == _json_value(proposed_value):
            return existing
    return IntelligenceReviewItem.objects.create(
        organization=organization,
        run=run,
        place=place,
        item_type=item_type,
        target_model=target_model,
        target_field=target_field,
        entity_key=entity_key,
        label=label[:255],
        current_value=_json_value(current_value),
        proposed_value=_json_value(proposed_value),
        source_url=source_url,
        confidence=Decimal(str(max(0.0, min(1.0, confidence)))),
        reason=reason[:4000],
        is_public_safe=True,
    )


def _apply_or_review_field(*, run, instance, model_name: str, field_name: str, value: Any, source_url: str, confidence: float, item_type: str, label: str, place=None, entity_type: str = "organization") -> str:
    if value in (None, "", [], {}):
        return "ignored"
    if field_name in {"public_email", "appointment_email"}:
        try:
            validate_email(str(value))
        except ValidationError:
            return "ignored"
    if field_name.endswith("_url") or field_name in {"booking_url", "cover_image"}:
        parsed = urlparse(str(value))
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return "ignored"
    if field_name in {"public_phone", "appointment_phone", "emergency_phone"}:
        value = _clean_text(value, 60)
        if len(re.sub(r"\D", "", value)) < 6:
            return "ignored"
    organization = run.organization
    current = getattr(instance, field_name, None)
    if current in (None, "", [], {}):
        setattr(instance, field_name, value)
        update_fields = [field_name]
        if hasattr(instance, "verified_at"):
            instance.verified_at = timezone.now()
            update_fields.append("verified_at")
        if hasattr(instance, "source_url") and field_name != "source_url":
            instance.source_url = source_url
            update_fields.append("source_url")
        instance.save(update_fields=tuple(dict.fromkeys(update_fields + ["updated_at"])))
        _record_fact(
            organization=organization,
            place=place,
            entity_type=entity_type,
            entity_key=str(getattr(instance, "pk", organization.slug)),
            field_name=field_name,
            value=value,
            source_url=source_url,
            confidence=confidence,
        )
        return "applied"
    if _same_value(current, value):
        _record_fact(
            organization=organization,
            place=place,
            entity_type=entity_type,
            entity_key=str(getattr(instance, "pk", organization.slug)),
            field_name=field_name,
            value=value,
            source_url=source_url,
            confidence=confidence,
        )
        return "verified"
    _create_review_item(
        run=run,
        organization=organization,
        place=place,
        item_type=item_type,
        target_model=model_name,
        target_field=field_name,
        label=label,
        current_value=current,
        proposed_value=value,
        source_url=source_url,
        confidence=confidence,
        reason="The official website contains a different value. Review it before replacing curated dashboard data.",
        entity_key=str(getattr(instance, "pk", "")),
    )
    return "review"


def _extract_contacts(pages: list[CrawledPage]) -> dict[str, tuple[str, str, float]]:
    result: dict[str, tuple[str, str, float]] = {}
    for page in pages:
        soup = BeautifulSoup(page.html, "html.parser")
        priority = 0.98 if any(token in page.url.casefold() for token in ("contact", "booking", "appointment", "reservation")) else 0.90
        for anchor in soup.find_all("a", href=True):
            href = str(anchor.get("href") or "").strip()
            if href.lower().startswith("tel:") and "public_phone" not in result:
                value = _clean_text(href[4:].split("?", 1)[0], 40)
                if value:
                    result["public_phone"] = (value, page.url, priority)
            elif href.lower().startswith("mailto:") and "public_email" not in result:
                value = _clean_text(href[7:].split("?", 1)[0], 254)
                if value:
                    result["public_email"] = (value, page.url, priority)
            text = _clean_text(anchor.get_text(" ", strip=True), 100).casefold()
            if text and any(word in text for word in _BOOKING_WORDS):
                candidate = urljoin(page.url, href)
                parsed = urlparse(candidate)
                if parsed.scheme in {"http", "https"} and "booking_url" not in result:
                    result["booking_url"] = (candidate[:500], page.url, 0.92)
    return result


def _extract_descriptions(pages: list[CrawledPage]) -> list[tuple[str, str, float]]:
    candidates: list[tuple[str, str, float]] = []
    for page in pages:
        soup = BeautifulSoup(page.html, "html.parser")
        marker = f"{page.url} {page.title}".casefold()
        meta = soup.find("meta", attrs={"name": re.compile("description", re.I)})
        value = _clean_text(meta.get("content") if meta else "", 4000)
        confidence = 0.96 if any(token in marker for token in ("about", "who-we-are", "our-story")) else 0.88
        if len(value) >= 50:
            candidates.append((value, page.url, confidence))
        for item in _iter_json_ld(page):
            if _schema_types(item.get("@type")).intersection(_ORGANIZATION_SCHEMA_TYPES):
                description = _clean_text(item.get("description"), 4000)
                if len(description) >= 50:
                    candidates.append((description, page.url, 0.98))
    candidates.sort(key=lambda item: (item[2], len(item[0])), reverse=True)
    return candidates


def _extract_structured_location(pages: list[CrawledPage]) -> dict[str, tuple[Any, str, float]]:
    values: dict[str, tuple[Any, str, float]] = {}
    for page in pages:
        for item in _iter_json_ld(page):
            if not _schema_types(item.get("@type")).intersection(_ORGANIZATION_SCHEMA_TYPES):
                continue
            address = item.get("address")
            if isinstance(address, dict):
                street = _clean_text(address.get("streetAddress"), 255)
                city = _clean_text(address.get("addressLocality"), 120)
                country = _clean_text(address.get("addressCountry"), 120)
                if street and "address_line" not in values:
                    values["address_line"] = (street, page.url, 0.98)
                if city and "city" not in values:
                    values["city"] = (city, page.url, 0.98)
                if country and "country" not in values:
                    values["country"] = (country, page.url, 0.98)
            hours = item.get("openingHours") or item.get("openingHoursSpecification")
            if hours and "opening_hours" not in values:
                normalized = [_clean_text(v, 220) for v in _as_list(hours) if _clean_text(v, 220)]
                if normalized:
                    values["opening_hours"] = (normalized, page.url, 0.97)
    return values


def _service_candidates(pages: list[CrawledPage]) -> list[dict[str, Any]]:
    candidates: dict[str, dict[str, Any]] = {}
    for page in pages:
        for item in _iter_json_ld(page):
            types = _schema_types(item.get("@type"))
            if not types.intersection(_SERVICE_SCHEMA_TYPES):
                continue
            name = _clean_text(item.get("name") or item.get("itemOffered"), 255)
            if not name or len(name) < 3:
                continue
            key = slugify(name)[:280]
            candidates[key] = {
                "name": name,
                "short_description": _clean_text(item.get("description"), 320),
                "description": _clean_text(item.get("description"), 4000),
                "category": _clean_text(item.get("category") or next(iter(types), "Service"), 120),
                "booking_url": _clean_text(item.get("url"), 500) or page.url,
                "source_url": page.url,
                "confidence": 0.98,
            }
        path_tokens = {part.casefold() for part in urlparse(page.url).path.split("/") if part}
        if not path_tokens.intersection(_SERVICE_PATH_WORDS):
            continue
        soup = BeautifulSoup(page.html, "html.parser")
        heading = soup.find("h1") or soup.find("h2")
        name = _clean_text(heading.get_text(" ", strip=True) if heading else page.title, 255)
        generic = {"services", "our services", "departments", "rooms", "accommodation", "facilities", "amenities", "properties"}
        if not name or name.casefold() in generic or len(name) < 3:
            continue
        key = slugify(name)[:280]
        candidates.setdefault(key, {
            "name": name,
            "short_description": _clean_text(page.text, 320),
            "description": _clean_text(page.text, 4000),
            "category": "Website service",
            "booking_url": page.url,
            "source_url": page.url,
            "confidence": 0.87,
        })
    return list(candidates.values())[:100]


def _extract_amenities(pages: list[CrawledPage]) -> list[str]:
    content = " ".join(page.text.casefold() for page in pages[:30])
    found = {label for token, label in _AMENITY_WORDS.items() if token in content}
    return sorted(found)


def _infer_domain(profile: OrganizationIntelligenceProfile, organization: Organization, pages: list[CrawledPage]) -> str:
    if profile.domain_kind != OrganizationIntelligenceProfile.DomainKind.GENERAL:
        return profile.domain_kind
    categories = set(organization.places.values_list("category", flat=True))
    if categories.intersection({Place.Category.HOSPITAL, Place.Category.CLINIC, Place.Category.DENTAL_CLINIC, Place.Category.PHARMACY}):
        return OrganizationIntelligenceProfile.DomainKind.HEALTHCARE
    if categories.intersection({Place.Category.HOTEL, Place.Category.RESORT, Place.Category.GUEST_HOUSE, Place.Category.LODGE}):
        return OrganizationIntelligenceProfile.DomainKind.HOSPITALITY
    if categories.intersection({Place.Category.HOUSE, Place.Category.APARTMENT, Place.Category.VILLA, Place.Category.STUDIO, Place.Category.OFFICE, Place.Category.BUILDING, Place.Category.LAND, Place.Category.REAL_ESTATE}):
        return OrganizationIntelligenceProfile.DomainKind.REAL_ESTATE
    sample = " ".join((page.title + " " + page.text[:1000]).casefold() for page in pages[:8])
    healthcare = any(token in sample for token in ("hospital", "clinic", "doctor", "medical", "surgical", "patient"))
    hospitality = any(token in sample for token in ("hotel", "rooms", "check-in", "accommodation", "resort"))
    real_estate = any(token in sample for token in ("property", "apartment", "bedroom", "for rent", "real estate"))
    if sum((healthcare, hospitality, real_estate)) > 1:
        return OrganizationIntelligenceProfile.DomainKind.MIXED
    if healthcare:
        return OrganizationIntelligenceProfile.DomainKind.HEALTHCARE
    if hospitality:
        return OrganizationIntelligenceProfile.DomainKind.HOSPITALITY
    if real_estate:
        return OrganizationIntelligenceProfile.DomainKind.REAL_ESTATE
    return profile.domain_kind


def _strip_json_fence(text: str) -> str:
    value = (text or "").strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*", "", value, flags=re.I)
        value = re.sub(r"\s*```$", "", value)
    first, last = value.find("{"), value.rfind("}")
    return value[first:last + 1] if first >= 0 and last > first else value


def _ai_extract(organization: Organization, pages: list[CrawledPage], run: OrganizationIntelligenceRun) -> dict[str, Any]:
    if not getattr(settings, "DOMAIN_INTELLIGENCE_ENABLE_AI_EXTRACTION", True):
        return {}
    selected = sorted(
        pages,
        key=lambda page: (any(token in f"{page.url} {page.title}".casefold() for token in ("about", "service", "contact", "booking", "department")), len(page.text)),
        reverse=True,
    )[:6]
    if not selected:
        return {}
    sources = []
    for page in selected:
        sources.append(f"SOURCE URL: {page.url}\nTITLE: {page.title}\nCONTENT:\n{page.text[:6000]}")
    prompt = f"""
Extract client-ready public business information for {organization.name} from the official website excerpts below.
Return strict JSON only. Never infer facts that are not explicitly written. Never invent doctors, prices, contacts, availability or services.
Every service must include a source_url copied exactly from one of the supplied SOURCE URL values.
Schema:
{{
  "description": "",
  "public_phone": "",
  "public_email": "",
  "booking_url": "",
  "domain_kind": "general|healthcare|real_estate|hospitality|mixed",
  "opening_hours": [],
  "services": [{{"name":"", "description":"", "category":"", "booking_url":"", "source_url":"", "confidence":0.0}}]
}}

{"\n\n---\n\n".join(sources)}
""".strip()
    router = AIProviderRouter(organization=organization, user=run.requested_by, trace_id=f"domain-sync:{run.id}")
    result = router.generate_text(
        prompt=prompt,
        system="You are a conservative business-data extraction engine. Output valid JSON only and ground every value in the supplied official website text.",
    )
    payload = json.loads(_strip_json_fence(getattr(result, "text", "")))
    return payload if isinstance(payload, dict) else {}


def _upsert_service(*, run, candidate: dict[str, Any], place=None) -> str:
    organization = run.organization
    name = _clean_text(candidate.get("name"), 255)
    if not name:
        return "ignored"
    confidence = float(candidate.get("confidence") or 0.8)
    source_url = _clean_text(candidate.get("source_url"), 500) or organization.website_url
    payload = {
        "name": name,
        "slug": slugify(name)[:280] or f"service-{abs(hash(name))}",
        "short_description": _clean_text(candidate.get("short_description") or candidate.get("description"), 320),
        "description": _clean_text(candidate.get("description"), 4000),
        "category": _clean_text(candidate.get("category"), 120),
        "booking_url": _clean_text(candidate.get("booking_url"), 500),
        "metadata": {"source_url": source_url, "collection_run": str(run.id), "confidence": confidence},
        "is_active": True,
    }
    if confidence < float(getattr(settings, "DOMAIN_INTELLIGENCE_AUTO_APPLY_MIN_CONFIDENCE", 0.82)):
        _create_review_item(
            run=run, organization=organization, place=place,
            item_type=IntelligenceReviewItem.ItemType.SERVICE,
            target_model="service_offering", target_field="", entity_key=payload["slug"],
            label=f"Add service: {name}", current_value={}, proposed_value=payload,
            source_url=source_url, confidence=confidence,
            reason="The service was extracted from unstructured website content and needs approval.",
        )
        return "review"
    service, created = ServiceOffering.objects.get_or_create(
        organization=organization,
        slug=payload["slug"],
        defaults={key: value for key, value in payload.items() if key != "slug"},
    )
    if not created:
        changed = []
        for field in ("short_description", "description", "category", "booking_url"):
            incoming = payload[field]
            if incoming and not getattr(service, field):
                setattr(service, field, incoming)
                changed.append(field)
        service.metadata = {**(service.metadata or {}), **payload["metadata"]}
        changed.append("metadata")
        if changed:
            service.save(update_fields=tuple(dict.fromkeys(changed + ["updated_at"])))
    _record_fact(
        organization=organization, place=place, entity_type="service_offering",
        entity_key=str(service.pk), field_name="name", value=name,
        source_url=source_url, confidence=confidence,
    )
    return "created" if created else "updated"


def _ensure_domain_profiles(organization: Organization, profile: OrganizationIntelligenceProfile, pages: list[CrawledPage]) -> dict[str, int]:
    counts = {"healthcare": 0, "property": 0, "hospitality": 0}
    amenities = _extract_amenities(pages)
    for place in organization.places.all():
        if place.category in {Place.Category.HOSPITAL, Place.Category.CLINIC, Place.Category.DENTAL_CLINIC, Place.Category.PHARMACY}:
            _, created = HealthcareFacilityProfile.objects.get_or_create(place=place)
            counts["healthcare"] += int(created)
        if place.category in {Place.Category.HOUSE, Place.Category.APARTMENT, Place.Category.VILLA, Place.Category.STUDIO, Place.Category.OFFICE, Place.Category.BUILDING, Place.Category.LAND, Place.Category.REAL_ESTATE}:
            defaults = {"property_type": place.category if place.category in dict(PropertyListingProfile.PropertyType.choices) else PropertyListingProfile.PropertyType.OTHER}
            _, created = PropertyListingProfile.objects.get_or_create(place=place, defaults=defaults)
            counts["property"] += int(created)
        if place.category in {Place.Category.HOTEL, Place.Category.RESORT, Place.Category.GUEST_HOUSE, Place.Category.LODGE}:
            hospitality, created = HospitalityProfile.objects.get_or_create(place=place)
            if amenities and not hospitality.amenities:
                hospitality.amenities = amenities
                hospitality.source_url = organization.website_url
                hospitality.verified_at = timezone.now()
                hospitality.save(update_fields=("amenities", "source_url", "verified_at", "updated_at"))
            counts["hospitality"] += int(created)
    return counts


def _save_run_progress(run: OrganizationIntelligenceRun, stage: str, **counters: int) -> None:
    labels = {
        "starting": "Preparing the organization collection",
        "crawling": "Collecting official website pages",
        "indexing": "Creating searchable knowledge",
        "structuring": "Structuring contacts, services and domain data",
        "ai_enrichment": "Enriching information with the configured AI provider",
        "domain_enrichment": "Preparing specialist domain information",
        "finalizing": "Calculating client readiness",
        "completed": "Organization intelligence is ready",
        "failed": "Collection stopped before completion",
    }
    changed = []
    for field_name, value in counters.items():
        if hasattr(run, field_name):
            setattr(run, field_name, max(0, int(value or 0)))
            changed.append(field_name)
    summary = dict(run.summary or {})
    summary.update({"stage": stage, "stage_label": labels.get(stage, stage.replace("_", " ").title())})
    run.summary = summary
    changed.extend(["summary", "updated_at"])
    run.save(update_fields=tuple(dict.fromkeys(changed)))


def collect_organization_intelligence(run: OrganizationIntelligenceRun) -> dict[str, Any]:
    organization = Organization.objects.get(pk=run.organization_id)
    profile, _ = OrganizationIntelligenceProfile.objects.get_or_create(organization=organization)
    readiness_before = calculate_organization_readiness(organization).score
    website_url = (organization.website_url or run.website_url or "").strip()

    run.status = OrganizationIntelligenceRun.Status.RUNNING
    run.website_url = website_url
    run.readiness_before = readiness_before
    run.started_at = timezone.now()
    run.error_code = ""
    run.error_message = ""
    run.summary = {"stage": "starting", "stage_label": "Preparing the organization collection"}
    run.save(update_fields=("status", "website_url", "readiness_before", "started_at", "error_code", "error_message", "summary", "updated_at"))
    profile.last_sync_status = "running"
    profile.last_sync_error = ""
    profile.save(update_fields=("last_sync_status", "last_sync_error", "updated_at"))

    warnings: list[dict[str, str]] = []
    applied_fields: list[str] = []
    pages: list[CrawledPage] = []
    source = None
    documents_indexed = 0
    chunks_indexed = 0
    services_collected = 0
    healthcare_result: dict[str, Any] = {}

    try:
        if not website_url:
            raise ValueError("The organization does not have an official website URL.")
        if not organization.ai_use_website:
            raise ValueError("Website intelligence is disabled for this organization.")
        page_limit = max(1, min(int(run.max_pages or profile.website_sync_max_pages or 25), int(getattr(settings, "KNOWLEDGE_CRAWLER_MAX_PAGES", 100))))
        _save_run_progress(run, "crawling")
        crawl_diagnostics: dict[str, Any] = {}
        pages = crawl_website(
            website_url,
            max_pages=page_limit,
            same_domain_only=True,
            diagnostics=crawl_diagnostics,
        )
        if not pages:
            attempted = int(crawl_diagnostics.get("attempted_count", 0))
            raise ValueError(
                "No readable public page was found on the official website. "
                "Twinscopes tried the configured URL, the site home page, About, "
                f"Services, Contact and sitemap pages ({attempted} URL(s) checked)."
            )

        effective_website_url = str(crawl_diagnostics.get("effective_start_url") or pages[0].url or website_url)
        if crawl_diagnostics.get("fallback_used"):
            warnings.append({
                "code": "website_url_recovered",
                "message": (
                    "The configured website page was unavailable. Twinscopes continued "
                    f"from another official page: {effective_website_url}"
                ),
            })
        failed_page_count = int(crawl_diagnostics.get("failed_count", 0))
        if failed_page_count:
            warnings.append({
                "code": "unavailable_pages_skipped",
                "message": (
                    f"{failed_page_count} unavailable or unsupported page(s) were skipped. "
                    "The collection continued with the remaining official pages."
                ),
            })

        _save_run_progress(run, "indexing", pages_crawled=len(pages))
        source, _ = KnowledgeSource.objects.update_or_create(
            organization=organization,
            name="Official organization website",
            defaults={
                "source_type": KnowledgeSource.SourceType.WEBSITE,
                "url": effective_website_url,
                "status": KnowledgeSource.Status.CRAWLING,
                "crawl_same_domain_only": True,
                "max_pages": page_limit,
                "is_active": True,
                "last_error": "",
                "metadata": {
                    "managed_by": "organization_intelligence",
                    "last_run_id": str(run.id),
                    "requested_url": website_url,
                    "effective_start_url": effective_website_url,
                    "fallback_used": bool(crawl_diagnostics.get("fallback_used")),
                    "attempted_count": int(crawl_diagnostics.get("attempted_count", 0)),
                    "failed_count": failed_page_count,
                    "sitemap_urls_found": int(crawl_diagnostics.get("sitemap_urls_found", 0)),
                },
            },
        )

        seen_document_ids = []
        for page in pages:
            document = upsert_document(
                source=source,
                title=page.title,
                content=page.text,
                canonical_url=page.url,
                metadata={"crawler": "beautifulsoup", "domain_intelligence": True, "run_id": str(run.id)},
            )
            seen_document_ids.append(document.pk)
            try:
                chunks_indexed += index_document(document)
                documents_indexed += 1
            except Exception as exc:
                warnings.append({"code": "document_index_failed", "message": f"{page.url}: {str(exc)[:400]}"})
                logger.warning("Knowledge indexing failed for %s during run %s: %s", page.url, run.id, exc)
            _save_run_progress(
                run,
                "indexing",
                pages_crawled=len(pages),
                documents_indexed=documents_indexed,
                chunks_indexed=chunks_indexed,
            )
        if seen_document_ids:
            source.documents.exclude(pk__in=seen_document_ids).update(is_active=False)

        _save_run_progress(
            run,
            "structuring",
            pages_crawled=len(pages),
            documents_indexed=documents_indexed,
            chunks_indexed=chunks_indexed,
        )
        place = organization.places.order_by("id").first()
        if crawl_diagnostics.get("fallback_used") and effective_website_url.rstrip("/") != website_url.rstrip("/"):
            _create_review_item(
                run=run,
                organization=organization,
                place=place,
                item_type=IntelligenceReviewItem.ItemType.PROFILE,
                target_model="organization",
                target_field="website_url",
                entity_key=str(organization.pk),
                label="Update official website URL",
                current_value=website_url,
                proposed_value=effective_website_url,
                source_url=effective_website_url,
                confidence=0.99,
                reason=(
                    "The configured URL was unavailable, but another page on the same official "
                    "website responded successfully. Approve this suggestion to prevent future "
                    "collection runs from starting from a broken page."
                ),
            )

        descriptions = _extract_descriptions(pages)
        if descriptions:
            value, source_url, confidence = descriptions[0]
            outcome = _apply_or_review_field(
                run=run, instance=organization, model_name="organization", field_name="description",
                value=value, source_url=source_url, confidence=confidence,
                item_type=IntelligenceReviewItem.ItemType.PROFILE,
                label="Organization description", place=place,
            )
            if outcome == "applied":
                applied_fields.append("description")

        for field, (value, source_url, confidence) in _extract_contacts(pages).items():
            outcome = _apply_or_review_field(
                run=run, instance=organization, model_name="organization", field_name=field,
                value=value, source_url=source_url, confidence=confidence,
                item_type=IntelligenceReviewItem.ItemType.CONTACT,
                label=field.replace("_", " ").title(), place=place,
            )
            if outcome == "applied":
                applied_fields.append(field)

        discovered_socials = discover_social_links(pages)
        social_count = 0
        for field, value in discovered_socials.items():
            outcome = _apply_or_review_field(
                run=run, instance=organization, model_name="organization", field_name=field,
                value=value, source_url=website_url, confidence=0.98,
                item_type=IntelligenceReviewItem.ItemType.SOCIAL,
                label=field.replace("_url", "").replace("_", " ").title(), place=place,
            )
            if outcome == "applied":
                social_count += 1
                applied_fields.append(field)
        if social_count:
            organization.social_links_verified_at = timezone.now()
            organization.save(update_fields=("social_links_verified_at", "updated_at"))

        structured = _extract_structured_location(pages)
        if place:
            for field in ("address_line", "city", "country"):
                if field in structured:
                    value, source_url, confidence = structured[field]
                    outcome = _apply_or_review_field(
                        run=run, instance=place, model_name="place", field_name=field,
                        value=value, source_url=source_url, confidence=confidence,
                        item_type=IntelligenceReviewItem.ItemType.LOCATION,
                        label=f"{place.name}: {field.replace('_', ' ').title()}", place=place,
                        entity_type="place",
                    )
                    if outcome == "applied":
                        applied_fields.append(f"place.{field}")

        profile.domain_kind = _infer_domain(profile, organization, pages)
        profile.save(update_fields=("domain_kind", "updated_at"))
        profile_counts = _ensure_domain_profiles(organization, profile, pages)

        service_candidates = _service_candidates(pages)
        allowed_urls = {page.url for page in pages}
        _save_run_progress(
            run,
            "ai_enrichment",
            pages_crawled=len(pages),
            documents_indexed=documents_indexed,
            chunks_indexed=chunks_indexed,
        )
        try:
            ai_payload = _ai_extract(organization, pages, run)
        except Exception as exc:
            ai_payload = {}
            warnings.append({"code": "ai_extraction_unavailable", "message": str(exc)[:400]})
            logger.info("AI enrichment was unavailable for organization %s: %s", organization.pk, exc)

        if ai_payload:
            ai_source = pages[0].url
            for field in ("description", "public_phone", "public_email", "booking_url"):
                value = ai_payload.get(field)
                if value:
                    outcome = _apply_or_review_field(
                        run=run, instance=organization, model_name="organization", field_name=field,
                        value=_clean_text(value, 4000 if field == "description" else 500),
                        source_url=ai_source, confidence=0.82,
                        item_type=IntelligenceReviewItem.ItemType.PROFILE if field == "description" else IntelligenceReviewItem.ItemType.CONTACT,
                        label=field.replace("_", " ").title(), place=place,
                    )
                    if outcome == "applied":
                        applied_fields.append(field)
            ai_domain = _clean_text(ai_payload.get("domain_kind"), 24)
            if ai_domain in dict(OrganizationIntelligenceProfile.DomainKind.choices) and profile.domain_kind == OrganizationIntelligenceProfile.DomainKind.GENERAL:
                profile.domain_kind = ai_domain
                profile.save(update_fields=("domain_kind", "updated_at"))
            for raw_service in _as_list(ai_payload.get("services")):
                if not isinstance(raw_service, dict):
                    continue
                raw_service["source_url"] = _safe_source_url(raw_service.get("source_url", ""), allowed_urls, ai_source)
                raw_service.setdefault("confidence", 0.82)
                service_candidates.append(raw_service)

        seen_service_slugs: set[str] = set()
        for candidate in service_candidates:
            key = slugify(_clean_text(candidate.get("name"), 255))[:280]
            if not key or key in seen_service_slugs:
                continue
            seen_service_slugs.add(key)
            outcome = _upsert_service(run=run, candidate=candidate, place=place)
            if outcome in {"created", "updated"}:
                services_collected += 1

        _save_run_progress(
            run,
            "domain_enrichment",
            pages_crawled=len(pages),
            documents_indexed=documents_indexed,
            chunks_indexed=chunks_indexed,
            services_collected=services_collected,
        )
        if profile.domain_kind in {OrganizationIntelligenceProfile.DomainKind.HEALTHCARE, OrganizationIntelligenceProfile.DomainKind.MIXED}:
            try:
                healthcare_result = sync_healthcare_organization(
                    organization,
                    max_pages=page_limit,
                    pages=pages,
                    source=source,
                    index_pages=False,
                    manage_profile_status=False,
                )
            except Exception as exc:
                warnings.append({"code": "healthcare_enrichment_failed", "message": str(exc)[:400]})
                logger.warning("Healthcare enrichment failed for run %s: %s", run.id, exc)

        source.status = KnowledgeSource.Status.INDEXED if documents_indexed else KnowledgeSource.Status.FAILED
        source.last_synced_at = timezone.now()
        source.last_error = "" if documents_indexed else "Website pages were collected but could not be embedded."
        source.save(update_fields=("status", "last_synced_at", "last_error", "updated_at"))

        profile.last_synced_at = timezone.now()
        profile.last_sync_status = "succeeded" if documents_indexed else "partial"
        profile.last_sync_error = ""
        profile.next_sync_at = timezone.now() + timedelta(days=max(1, int(getattr(settings, "DOMAIN_INTELLIGENCE_SYNC_INTERVAL_DAYS", 7))))
        profile.save(update_fields=("last_synced_at", "last_sync_status", "last_sync_error", "next_sync_at", "updated_at"))

        _save_run_progress(
            run,
            "finalizing",
            pages_crawled=len(pages),
            documents_indexed=documents_indexed,
            chunks_indexed=chunks_indexed,
            services_collected=services_collected,
        )
        readiness_after_result = calculate_organization_readiness(organization)
        run.pages_crawled = len(pages)
        run.documents_indexed = documents_indexed
        run.chunks_indexed = chunks_indexed
        run.services_collected = services_collected
        run.facts_collected = VerifiedSourceFact.objects.filter(organization=organization, created_at__gte=run.started_at).count()
        run.review_items_created = run.review_items.count()
        run.practitioners_collected = int(healthcare_result.get("practitioners_created", 0))
        run.specialties_collected = int(healthcare_result.get("specialties_created", 0))
        run.social_links_collected = social_count
        run.readiness_after = readiness_after_result.score
        run.status = OrganizationIntelligenceRun.Status.SUCCEEDED if documents_indexed else OrganizationIntelligenceRun.Status.PARTIAL
        run.summary = {
            "stage": "completed",
            "stage_label": "Organization intelligence is ready",
            "domain_kind": profile.domain_kind,
            "knowledge_source_id": source.pk,
            "applied_fields": sorted(set(applied_fields)),
            "domain_profiles_created": profile_counts,
            "healthcare": healthcare_result,
            "readiness_status": readiness_after_result.status,
            "crawl": {
                "requested_url": website_url,
                "effective_start_url": effective_website_url,
                "fallback_used": bool(crawl_diagnostics.get("fallback_used")),
                "attempted_count": int(crawl_diagnostics.get("attempted_count", 0)),
                "failed_count": failed_page_count,
                "sitemap_urls_found": int(crawl_diagnostics.get("sitemap_urls_found", 0)),
            },
        }
        run.warnings = warnings
        run.finished_at = timezone.now()
        run.save(update_fields=(
            "pages_crawled", "documents_indexed", "chunks_indexed", "services_collected",
            "facts_collected", "review_items_created", "practitioners_collected",
            "specialties_collected", "social_links_collected", "readiness_after", "status",
            "summary", "warnings", "finished_at", "updated_at",
        ))
        return {
            "run_id": str(run.id),
            "organization_id": organization.pk,
            "status": run.status,
            "pages": len(pages),
            "documents_indexed": documents_indexed,
            "chunks_indexed": chunks_indexed,
            "services_collected": services_collected,
            "review_items": run.review_items_created,
            "readiness_before": readiness_before,
            "readiness_after": readiness_after_result.score,
        }
    except Exception as exc:
        profile.last_sync_status = "failed"
        profile.last_sync_error = str(exc)[:8000]
        profile.next_sync_at = timezone.now() + timedelta(days=1)
        profile.save(update_fields=("last_sync_status", "last_sync_error", "next_sync_at", "updated_at"))
        run.status = OrganizationIntelligenceRun.Status.FAILED
        run.error_code = exc.__class__.__name__.lower()
        run.error_message = str(exc)[:8000]
        run.warnings = warnings
        run.summary = {
            **dict(run.summary or {}),
            "stage": "failed",
            "stage_label": "Collection stopped before completion",
        }
        run.finished_at = timezone.now()
        run.save(update_fields=("status", "error_code", "error_message", "warnings", "summary", "finished_at", "updated_at"))
        calculate_organization_readiness(organization)
        raise


_ORGANIZATION_FIELDS = {
    "website_url", "description", "public_phone", "public_email", "booking_url",
    "facebook_url", "instagram_url", "tiktok_url", "linkedin_url", "youtube_url",
}
_PLACE_FIELDS = {"description", "address_line", "city", "country", "cover_image"}
_HEALTHCARE_FIELDS = {
    "appointment_phone", "appointment_email", "appointment_url", "emergency_phone",
    "opening_hours", "specialties", "insurance_providers", "accessibility",
}


@transaction.atomic
def apply_review_item(item: IntelligenceReviewItem, user) -> IntelligenceReviewItem:
    item = IntelligenceReviewItem.objects.select_for_update().select_related("organization", "place").get(pk=item.pk)
    if item.status != IntelligenceReviewItem.Status.PENDING:
        return item
    value = item.proposed_value
    if item.target_model == "organization" and item.target_field in _ORGANIZATION_FIELDS:
        setattr(item.organization, item.target_field, value)
        item.organization.save(update_fields=(item.target_field, "updated_at"))
    elif item.target_model == "place" and item.place and item.target_field in _PLACE_FIELDS:
        setattr(item.place, item.target_field, value)
        item.place.save(update_fields=(item.target_field, "updated_at"))
    elif item.target_model == "healthcare_facility" and item.place and item.target_field in _HEALTHCARE_FIELDS:
        facility, _ = HealthcareFacilityProfile.objects.get_or_create(place=item.place)
        setattr(facility, item.target_field, value)
        facility.source_url = item.source_url
        facility.verified_at = timezone.now()
        facility.save(update_fields=(item.target_field, "source_url", "verified_at", "updated_at"))
    elif item.target_model == "service_offering" and isinstance(value, dict):
        name = _clean_text(value.get("name"), 255)
        slug = _clean_text(value.get("slug"), 280) or slugify(name)[:280]
        if not name or not slug:
            raise ValueError("The proposed service is incomplete.")
        ServiceOffering.objects.update_or_create(
            organization=item.organization,
            slug=slug,
            defaults={
                "name": name,
                "short_description": _clean_text(value.get("short_description"), 320),
                "description": _clean_text(value.get("description"), 4000),
                "category": _clean_text(value.get("category"), 120),
                "booking_url": _clean_text(value.get("booking_url"), 500),
                "metadata": value.get("metadata") if isinstance(value.get("metadata"), dict) else {},
                "is_active": True,
            },
        )
    else:
        raise ValueError("This review item cannot be applied automatically. Edit the target resource manually.")

    _record_fact(
        organization=item.organization,
        place=item.place,
        entity_type=item.target_model,
        entity_key=item.entity_key or str(getattr(item.place, "pk", item.organization.pk)),
        field_name=item.target_field or "record",
        value=value,
        source_url=item.source_url,
        confidence=float(item.confidence),
    )
    item.status = IntelligenceReviewItem.Status.APPLIED
    item.reviewed_by = user
    item.reviewed_at = timezone.now()
    item.save(update_fields=("status", "reviewed_by", "reviewed_at", "updated_at"))
    calculate_organization_readiness(item.organization)
    return item


@transaction.atomic
def reject_review_item(item: IntelligenceReviewItem, user) -> IntelligenceReviewItem:
    item = IntelligenceReviewItem.objects.select_for_update().get(pk=item.pk)
    if item.status == IntelligenceReviewItem.Status.PENDING:
        item.status = IntelligenceReviewItem.Status.REJECTED
        item.reviewed_by = user
        item.reviewed_at = timezone.now()
        item.save(update_fields=("status", "reviewed_by", "reviewed_at", "updated_at"))
        calculate_organization_readiness(item.organization)
    return item
