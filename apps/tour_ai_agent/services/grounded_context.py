from __future__ import annotations

import hashlib
import re

from django.core.cache import cache

from apps.knowledge.models import ServiceOffering
from apps.knowledge.services.search import semantic_search
from apps.domain_intelligence.services.grounding import build_domain_grounding


_SIMPLE_GREETING_RE = re.compile(
    r"^(?:hi|hello|hey|good\s+(?:morning|afternoon|evening)|bonjour|bonsoir|salut|coucou|merci|thank\s+you)[!.?\s]*$",
    re.IGNORECASE,
)


def _cache_get(key: str):
    try:
        return cache.get(key)
    except Exception:
        return None


def _cache_set(key: str, value, timeout: int) -> None:
    try:
        cache.set(key, value, timeout)
    except Exception:
        pass


def _social_links(organization) -> dict:
    fields = ("facebook_url", "instagram_url", "tiktok_url", "linkedin_url", "youtube_url")
    return {field.removesuffix("_url"): getattr(organization, field, "") for field in fields if getattr(organization, field, "")}


def should_use_semantic_grounding(query: str, intent: str = "question") -> bool:
    """Avoid an embedding/search call when structured data can answer safely."""
    text = " ".join(str(query or "").lower().split())
    if not text or _SIMPLE_GREETING_RE.fullmatch(text):
        return False
    words = text.split()
    if len(words) > 18:
        return True
    knowledge_markers = {
        "doctor", "doctors", "médecin", "médecins", "specialist", "spécialiste",
        "service", "services", "available", "availability", "disponible", "disponibilité",
        "hours", "horaire", "horaires", "price", "prix", "product", "produit",
        "property", "maison", "apartment", "appartement", "room", "chambre",
        "policy", "politique", "explain", "details", "détails", "about", "concernant",
    }
    if any(marker in text for marker in knowledge_markers):
        return True
    return intent not in {"contact", "booking", "quote"}


def _organization_profile(organization) -> dict:
    services = list(
        ServiceOffering.objects.filter(organization=organization, is_active=True)
        .values(
            "id", "name", "slug", "short_description", "description", "category",
            "price_from", "currency", "duration_minutes", "booking_url",
        )[:12]
    )
    for service in services:
        if service["price_from"] is not None:
            service["price_from"] = str(service["price_from"])
        service["short_description"] = str(service.get("short_description") or "")[:260]
        service["description"] = str(service.get("description") or "")[:700]
    try:
        embedded_resources = list(
            organization.embedded_resources.filter(
                is_active=True, is_verified=True, allow_in_tour_agent=True
            ).values("id", "label", "kind", "url", "embed_mode", "button_label", "description")[:8]
        )
    except Exception:
        embedded_resources = []
    return {
        "business": {
            "name": organization.name,
            "description": str(getattr(organization, "description", "") or "")[:1200],
            "website_url": getattr(organization, "website_url", ""),
            "booking_url": getattr(organization, "booking_url", ""),
            "public_email": getattr(organization, "public_email", ""),
            "public_phone": getattr(organization, "public_phone", ""),
            "social_links": _social_links(organization),
            "embedded_resources": embedded_resources,
        },
        "services": services,
    }


def build_organization_profile(organization) -> dict:
    key = f"tour-ai-profile:v3:{organization.pk}"
    cached = _cache_get(key)
    if isinstance(cached, dict):
        return cached
    result = _organization_profile(organization)
    _cache_set(key, result, 300)
    return result


def build_organization_grounding(organization, query: str, *, limit: int = 4) -> dict:
    limit = max(1, min(int(limit or 4), 6))
    normalized_query = " ".join(str(query or "").lower().split())[:500]
    digest = hashlib.sha256(normalized_query.encode("utf-8")).hexdigest()[:20]
    key = f"tour-ai-grounding:v4:{organization.pk}:{limit}:{digest}"
    cached = _cache_get(key)
    if isinstance(cached, dict):
        return cached

    hits = semantic_search(organization=organization, query=query, limit=limit)
    sources = []
    for index, hit in enumerate(hits, 1):
        sources.append({
            "citation": f"K{index}",
            "title": str(hit.title or "")[:220],
            "content": str(hit.content or "")[:1000],
            "url": hit.url,
            "score": round(hit.score, 4),
            "source": str(hit.source_name or "")[:160],
        })

    result = build_organization_profile(organization)
    result = {
        **result,
        "knowledge_sources": sources,
        "domain_intelligence": build_domain_grounding(organization, query, limit=limit),
    }
    _cache_set(key, result, 600)
    return result
