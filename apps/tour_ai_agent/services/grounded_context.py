from __future__ import annotations

from apps.knowledge.models import ServiceOffering
from apps.knowledge.services.search import semantic_search


def _social_links(organization) -> dict:
    fields = ("facebook_url", "instagram_url", "tiktok_url", "linkedin_url", "youtube_url")
    return {field.removesuffix("_url"): getattr(organization, field, "") for field in fields if getattr(organization, field, "")}


def build_organization_grounding(organization, query: str, *, limit: int = 8) -> dict:
    hits = semantic_search(organization=organization, query=query, limit=limit)
    sources = []
    for index, hit in enumerate(hits, 1):
        sources.append({
            "citation": f"K{index}",
            "title": hit.title,
            "content": hit.content[:2400],
            "url": hit.url,
            "score": round(hit.score, 4),
            "source": hit.source_name,
        })
    services = list(
        ServiceOffering.objects.filter(organization=organization, is_active=True)
        .values("id", "name", "slug", "short_description", "description", "category", "price_from", "currency", "duration_minutes", "booking_url")[:30]
    )
    for service in services:
        if service["price_from"] is not None:
            service["price_from"] = str(service["price_from"])
    return {
        "business": {
            "name": organization.name,
            "description": getattr(organization, "description", ""),
            "website_url": getattr(organization, "website_url", ""),
            "booking_url": getattr(organization, "booking_url", ""),
            "public_email": getattr(organization, "public_email", ""),
            "public_phone": getattr(organization, "public_phone", ""),
            "social_links": _social_links(organization),
        },
        "services": services,
        "knowledge_sources": sources,
    }
