from __future__ import annotations

import hashlib
import json
import logging
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.cache import cache

from apps.ai_core.services.router import AIProviderRouter

from .query_parser import DiscoveryIntent, parse_discovery_query

logger = logging.getLogger(__name__)

_ALLOWED_CATEGORIES = {"", "healthcare", "hotel", "house", "apartment", "studio", "office"}
_ALLOWED_LISTING_TYPES = {"", "rent", "sale", "short_stay"}
_ALLOWED_AMENITIES = {"parking", "pool", "elevator", "balcony", "wifi", "air_conditioning"}


def _decimal(value):
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value).replace(",", "."))
    except (InvalidOperation, ValueError):
        return None


def _json_object(text: str) -> dict:
    value = str(text or "").strip()
    if value.startswith("```"):
        value = value.strip("`")
        if value.lower().startswith("json"):
            value = value[4:].lstrip()
    start, end = value.find("{"), value.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        payload = json.loads(value[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _merge(base: DiscoveryIntent, payload: dict) -> DiscoveryIntent:
    category = str(payload.get("category") or "").strip().lower()
    if category in _ALLOWED_CATEGORIES and category:
        base.category = category
    listing_type = str(payload.get("listing_type") or "").strip().lower()
    if listing_type in _ALLOWED_LISTING_TYPES and listing_type:
        base.listing_type = listing_type

    for key in ("bedrooms",):
        try:
            value = int(payload.get(key))
        except (TypeError, ValueError):
            value = None
        if value is not None and 0 <= value <= 99:
            setattr(base, key, value)

    for key in ("bathrooms", "max_price", "min_price"):
        value = _decimal(payload.get(key))
        if value is not None and value >= 0:
            setattr(base, key, value)

    for key, limit in (("currency", 8), ("city", 120), ("location_text", 255), ("specialty", 120), ("practitioner", 160)):
        value = str(payload.get(key) or "").strip()
        if value:
            setattr(base, key, value[:limit])

    for key in ("furnished", "pet_friendly"):
        value = payload.get(key)
        if isinstance(value, bool):
            setattr(base, key, value)

    amenities = payload.get("amenities")
    if isinstance(amenities, list):
        normalized = []
        for value in amenities:
            name = str(value or "").strip().lower()
            if name in _ALLOWED_AMENITIES and name not in normalized:
                normalized.append(name)
        if normalized:
            base.amenities = normalized
    return base


def parse_discovery_query_enhanced(query: str, *, city: str = "", location_text: str = "") -> DiscoveryIntent:
    """Parse a public discovery request with deterministic fallback.

    The rule-based parser always runs first. The AI layer only enriches the
    structured intent and can fail without breaking public search.
    """
    intent = parse_discovery_query(query, city=city, location_text=location_text)
    if not getattr(settings, "DISCOVERY_ENABLE_AI_QUERY_PARSER", True):
        return intent

    cache_raw = "|".join((str(query or "")[:500], str(city or "")[:120], str(location_text or "")[:255]))
    cache_key = "discovery-intent:" + hashlib.sha256(cache_raw.casefold().encode("utf-8")).hexdigest()
    try:
        cached_payload = cache.get(cache_key)
    except Exception:
        cached_payload = None
    if isinstance(cached_payload, dict):
        return _merge(intent, cached_payload)

    system = (
        "Extract a safe virtual-tour search intent. Return one JSON object only. "
        "Never invent a city, price, doctor, specialty or amenity not present in the request."
    )
    prompt = json.dumps({
        "request": str(query or "")[:500],
        "explicit_city": str(city or "")[:120],
        "explicit_location": str(location_text or "")[:255],
        "schema": {
            "category": "healthcare|hotel|house|apartment|studio|office|empty",
            "listing_type": "rent|sale|short_stay|empty",
            "bedrooms": "integer|null",
            "bathrooms": "number|null",
            "max_price": "number|null",
            "min_price": "number|null",
            "currency": "USD|ZAR|EUR|CDF|empty",
            "city": "string",
            "location_text": "string",
            "furnished": "boolean|null",
            "pet_friendly": "boolean|null",
            "amenities": ["parking", "pool", "elevator", "balcony", "wifi", "air_conditioning"],
            "specialty": "string",
            "practitioner": "string",
        },
    }, ensure_ascii=False)
    try:
        result = AIProviderRouter().generate_text(
            prompt=prompt,
            system=system,
            model=getattr(settings, "DISCOVERY_AI_QUERY_MODEL", None) or None,
        )
        structured = _json_object(result.text)
        if structured:
            try:
                cache.set(
                    cache_key,
                    structured,
                    timeout=max(30, int(getattr(settings, "DISCOVERY_INTENT_CACHE_SECONDS", 600))),
                )
            except Exception:
                pass
        return _merge(intent, structured)
    except Exception as exc:
        logger.info("Discovery AI parser unavailable; using deterministic intent parser")
        logger.debug("Discovery parser provider detail: %s", exc, exc_info=True)
        return intent
