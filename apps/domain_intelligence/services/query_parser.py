from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from decimal import Decimal, InvalidOperation


_CATEGORY_SYNONYMS = {
    "healthcare": ("hospital", "hôpital", "hopital", "clinic", "clinique", "doctor", "docteur", "médecin", "medecin"),
    "hotel": ("hotel", "hôtel", "resort", "lodge", "guest house", "maison d'hôtes", "maison d’hôtes"),
    "house": ("house", "maison", "villa"),
    "apartment": ("apartment", "appartement", "flat"),
    "studio": ("studio",),
    "office": ("office", "bureau"),
}

_LISTING_SYNONYMS = {
    "rent": ("rent", "rental", "louer", "location", "à louer", "a louer"),
    "sale": ("buy", "purchase", "sale", "acheter", "achat", "à vendre", "a vendre"),
    "short_stay": ("night", "nights", "nuit", "nuits", "short stay", "séjour", "sejour"),
}


@dataclass(slots=True)
class DiscoveryIntent:
    raw_query: str
    category: str = ""
    listing_type: str = ""
    bedrooms: int | None = None
    bathrooms: Decimal | None = None
    max_price: Decimal | None = None
    min_price: Decimal | None = None
    currency: str = ""
    city: str = ""
    location_text: str = ""
    furnished: bool | None = None
    pet_friendly: bool | None = None
    amenities: list[str] = field(default_factory=list)
    specialty: str = ""
    practitioner: str = ""

    def as_dict(self) -> dict:
        payload = asdict(self)
        for key in ("bathrooms", "max_price", "min_price"):
            if payload[key] is not None:
                payload[key] = str(payload[key])
        return payload


def _decimal(value: str | None) -> Decimal | None:
    if not value:
        return None
    cleaned = value.replace(" ", "").replace(",", ".")
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def parse_discovery_query(query: str, *, city: str = "", location_text: str = "") -> DiscoveryIntent:
    raw = " ".join(str(query or "").split())[:500]
    normalized = raw.casefold()
    intent = DiscoveryIntent(raw_query=raw, city=str(city or "").strip()[:120], location_text=str(location_text or "").strip()[:255])

    for category, terms in _CATEGORY_SYNONYMS.items():
        if any(term in normalized for term in terms):
            intent.category = category
            break

    for listing_type, terms in _LISTING_SYNONYMS.items():
        if any(term in normalized for term in terms):
            intent.listing_type = listing_type
            break

    bedroom_match = re.search(r"\b(\d{1,2})\s*(?:bed(?:room)?s?|chambres?|pi[eè]ces?)\b", normalized)
    if bedroom_match:
        intent.bedrooms = min(int(bedroom_match.group(1)), 99)

    bathroom_match = re.search(r"\b(\d{1,2}(?:[.,]5)?)\s*(?:bath(?:room)?s?|salles?\s+de\s+bain)\b", normalized)
    if bathroom_match:
        intent.bathrooms = _decimal(bathroom_match.group(1))

    price_match = re.search(
        r"(?:moins\s+de|maximum|max|budget(?:\s+(?:maximum|max))?|under|up\s+to|jusqu['’]?à)\s*[:=]?\s*([\d\s.,]+)\s*(usd|zar|eur|€|\$|r|cdf)?",
        normalized,
    )
    if price_match:
        intent.max_price = _decimal(price_match.group(1))
        token = (price_match.group(2) or "").upper()
        intent.currency = {"€": "EUR", "$": "USD", "R": "ZAR"}.get(token, token)

    if any(term in normalized for term in ("furnished", "meublé", "meuble")):
        intent.furnished = True
    if any(term in normalized for term in ("unfurnished", "non meublé", "non meuble")):
        intent.furnished = False
    if any(term in normalized for term in ("pet friendly", "animaux acceptés", "animaux acceptes")):
        intent.pet_friendly = True

    amenity_map = {
        "parking": ("parking", "garage"),
        "pool": ("pool", "piscine"),
        "elevator": ("elevator", "lift", "ascenseur"),
        "balcony": ("balcony", "balcon"),
        "wifi": ("wifi", "wi-fi"),
        "air_conditioning": ("air conditioning", "climatisation", "climatisé", "climatise"),
    }
    for amenity, terms in amenity_map.items():
        if any(term in normalized for term in terms):
            intent.amenities.append(amenity)

    specialty_match = re.search(
        r"(?:sp[eé]cialiste|specialist|service|department|d[eé]partement)\s+(?:en\s+|de\s+)?([\wÀ-ÿ\- ]{3,80})",
        normalized,
    )
    if specialty_match:
        intent.specialty = specialty_match.group(1).strip(" .,;:")[:120]

    doctor_match = re.search(r"(?:dr\.?|docteur|doctor)\s+([\wÀ-ÿ'’\- ]{2,100})", raw, flags=re.IGNORECASE)
    if doctor_match:
        intent.practitioner = doctor_match.group(1).strip(" .,;:")[:160]

    if not intent.city:
        city_match = re.search(
            r"(?:\bà\b|\ba\b|\bin\b|\bnear\b|\bproche\s+de\b)\s+([\wÀ-ÿ'’\- ]{2,80})(?:[,.;]|$)",
            raw,
            flags=re.IGNORECASE,
        )
        if city_match:
            candidate = city_match.group(1).strip()
            candidate = re.sub(r"\b(?:avec|under|moins|maximum|max|budget)\b.*$", "", candidate, flags=re.IGNORECASE).strip()
            intent.city = candidate[:120]

    return intent
