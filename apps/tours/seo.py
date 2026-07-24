from __future__ import annotations

import json
import re
from html import unescape
from typing import Any, Iterable

from django.templatetags.static import static
from django.urls import reverse
from django.utils.html import strip_tags

from apps.organizations.models import Organization
from apps.places.models import Place
from apps.tours.models import Tour


_SCHEMA_TYPES = {
    Place.Category.HOSPITAL: "Hospital",
    Place.Category.CLINIC: "MedicalClinic",
    Place.Category.DENTAL_CLINIC: "Dentist",
    Place.Category.PHARMACY: "Pharmacy",
    Place.Category.HOTEL: "Hotel",
    Place.Category.RESORT: "Resort",
    Place.Category.GUEST_HOUSE: "LodgingBusiness",
    Place.Category.LODGE: "LodgingBusiness",
    Place.Category.RESTAURANT: "Restaurant",
    Place.Category.CAFE: "CafeOrCoffeeShop",
    Place.Category.BAR: "BarOrPub",
    Place.Category.STORE: "Store",
    Place.Category.BOUTIQUE: "Store",
    Place.Category.SUPERMARKET: "GroceryStore",
    Place.Category.SHOPPING_MALL: "ShoppingCenter",
    Place.Category.BEAUTY_SALON: "BeautySalon",
    Place.Category.BARBERSHOP: "HairSalon",
    Place.Category.GYM: "ExerciseGym",
    Place.Category.FITNESS_CENTER: "ExerciseGym",
    Place.Category.MUSEUM: "Museum",
    Place.Category.PARK: "Park",
    Place.Category.AIRPORT: "Airport",
    Place.Category.BANK: "BankOrCreditUnion",
    Place.Category.CHURCH: "Church",
}


def _clean(value: Any, *, limit: int = 320) -> str:
    text = unescape(strip_tags(str(value or "")))
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    shortened = text[:limit].rsplit(" ", 1)[0].rstrip(" ,;:-")
    return f"{shortened}…" if shortened else text[:limit]


def _absolute(request, value: str | None) -> str:
    value = str(value or "").strip()
    if not value:
        return ""
    return request.build_absolute_uri(value)


def _field_url(value: Any) -> str:
    try:
        return value.url if value else ""
    except (AttributeError, ValueError):
        return ""


def _first_image_url(request, tour: Tour, scenes: Iterable[Any]) -> tuple[str, bool]:
    candidates = [
        _field_url(getattr(tour, "thumbnail_image", None)),
        _field_url(getattr(tour, "thumbnail_image_mobile", None)),
    ]
    for scene in scenes:
        candidates.extend(
            [
                _field_url(getattr(scene, "thumbnail_image", None)),
                _field_url(getattr(scene, "image_360_preview", None)),
            ]
        )
        if any(candidates):
            break
    dynamic = next((item for item in candidates if item), "")
    if dynamic:
        return _absolute(request, dynamic), True
    return _absolute(request, static("public/branding/twinscopes-social-card.jpg")), False


def _json_ld(value: dict[str, Any]) -> str:
    # Keep user-authored text from prematurely closing the JSON-LD script.
    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def build_tour_preview_seo(request, *, tour: Tour, organization, scenes: list[Any]) -> dict[str, Any]:
    place = tour.place
    try:
        canonical_path = reverse(
            "tour-preview-public",
            kwargs={"organization_slug": organization.slug, "tour_id": tour.id},
        )
    except Exception:
        canonical_path = f"/{organization.slug}/tours/{tour.id}/preview/"
    canonical_url = _absolute(request, canonical_path)

    location_parts = [
        _clean(getattr(place, "address_line", ""), limit=140),
        _clean(getattr(place, "city", ""), limit=80),
        _clean(getattr(place, "country", ""), limit=80),
    ]
    location = ", ".join(item for item in location_parts if item)
    category = _clean(place.get_category_display() if place else "Virtual tour", limit=80)

    fallback_description = (
        f"Explore {tour.title} in an immersive 360° virtual tour"
        f" by {organization.name}"
        f"{f' in {location}' if location else ''}."
    )
    long_description = _clean(
        getattr(tour, "description", "")
        or getattr(place, "description", "")
        or getattr(organization, "description", "")
        or fallback_description,
        limit=420,
    )
    meta_description = _clean(long_description or fallback_description, limit=165)
    seo_title = _clean(f"{tour.title} 360° Virtual Tour | {organization.name}", limit=72)
    image_url, image_is_dynamic = _first_image_url(request, tour, scenes)
    image_alt = _clean(f"360° virtual tour of {tour.title} by {organization.name}", limit=140)

    is_indexable = bool(
        tour.status == Tour.Status.PUBLISHED
        and organization.status == Organization.Status.ACTIVE
        and getattr(place, "status", None) == Place.Status.PUBLISHED
    )
    robots = (
        "index,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1"
        if is_indexable
        else "noindex,nofollow,noarchive"
    )

    site_root = _absolute(request, "/")
    website_id = f"{site_root}#website"
    webpage_id = f"{canonical_url}#webpage"
    place_id = f"{canonical_url}#place"
    image_id = f"{canonical_url}#primaryimage"
    breadcrumb_id = f"{canonical_url}#breadcrumb"
    organization_id = f"{canonical_url}#organization"
    virtual_location_id = f"{canonical_url}#virtual-location"

    same_as = [
        getattr(organization, "website_url", ""),
        getattr(organization, "facebook_url", ""),
        getattr(organization, "instagram_url", ""),
        getattr(organization, "tiktok_url", ""),
        getattr(organization, "linkedin_url", ""),
        getattr(organization, "youtube_url", ""),
    ]
    same_as = [url for url in same_as if str(url or "").startswith(("http://", "https://"))]

    publisher = {
        "@type": "Organization",
        "@id": organization_id,
        "name": _clean(organization.name, limit=160),
        "url": getattr(organization, "website_url", "") or site_root,
    }
    logo_url = _field_url(getattr(organization, "logo", None))
    if logo_url:
        publisher["logo"] = {"@type": "ImageObject", "url": _absolute(request, logo_url)}
    if same_as:
        publisher["sameAs"] = same_as
    if getattr(organization, "public_phone", ""):
        publisher["telephone"] = _clean(organization.public_phone, limit=60)
    if getattr(organization, "public_email", ""):
        publisher["email"] = _clean(organization.public_email, limit=160)

    place_node: dict[str, Any] = {
        "@type": _SCHEMA_TYPES.get(getattr(place, "category", ""), "Place"),
        "@id": place_id,
        "name": _clean(getattr(place, "name", "") or tour.title, limit=180),
        "description": long_description,
        "url": canonical_url,
        "image": image_url,
        "mainEntityOfPage": {"@id": webpage_id},
    }
    if location:
        place_node["address"] = {
            "@type": "PostalAddress",
            "streetAddress": _clean(getattr(place, "address_line", ""), limit=180),
            "addressLocality": _clean(getattr(place, "city", ""), limit=100),
            "addressCountry": _clean(getattr(place, "country", ""), limit=100),
        }
        place_node["address"] = {key: value for key, value in place_node["address"].items() if value}
    latitude = getattr(place, "latitude", None) or getattr(tour, "lat", None)
    longitude = getattr(place, "longitude", None) or getattr(tour, "lng", None)
    if latitude is not None and longitude is not None:
        place_node["geo"] = {
            "@type": "GeoCoordinates",
            "latitude": str(latitude),
            "longitude": str(longitude),
        }
    if getattr(organization, "public_phone", ""):
        place_node["telephone"] = _clean(organization.public_phone, limit=60)
    if getattr(organization, "public_email", ""):
        place_node["email"] = _clean(organization.public_email, limit=160)
    if same_as:
        place_node["sameAs"] = same_as

    scene_images = []
    for scene in scenes[:8]:
        scene_image = (
            _field_url(getattr(scene, "thumbnail_image", None))
            or _field_url(getattr(scene, "image_360_preview", None))
        )
        if not scene_image:
            continue
        scene_images.append(
            {
                "@type": "ImageObject",
                "contentUrl": _absolute(request, scene_image),
                "name": _clean(getattr(scene, "title", "") or tour.title, limit=160),
                "caption": _clean(
                    f"360° scene: {getattr(scene, 'title', '') or tour.title}", limit=180
                ),
            }
        )

    graph: list[dict[str, Any]] = [
        {
            "@type": "WebSite",
            "@id": website_id,
            "url": site_root,
            "name": "Twinscopes",
            "inLanguage": "en",
        },
        publisher,
        {
            "@type": "ImageObject",
            "@id": image_id,
            "url": image_url,
            "contentUrl": image_url,
            "caption": image_alt,
        },
        {
            "@type": "BreadcrumbList",
            "@id": breadcrumb_id,
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Twinscopes", "item": site_root},
                {
                    "@type": "ListItem",
                    "position": 2,
                    "name": _clean(organization.name, limit=120),
                    "item": canonical_url,
                },
                {
                    "@type": "ListItem",
                    "position": 3,
                    "name": _clean(tour.title, limit=140),
                    "item": canonical_url,
                },
            ],
        },
        place_node,
        {
            "@type": "VirtualLocation",
            "@id": virtual_location_id,
            "name": _clean(f"{tour.title} 360° virtual tour", limit=180),
            "url": canonical_url,
        },
        {
            "@type": "WebPage",
            "@id": webpage_id,
            "url": canonical_url,
            "name": seo_title,
            "description": meta_description,
            "inLanguage": "en",
            "isPartOf": {"@id": website_id},
            "about": {"@id": place_id},
            "publisher": {"@id": organization_id},
            "primaryImageOfPage": {"@id": image_id},
            "breadcrumb": {"@id": breadcrumb_id},
            "potentialAction": {
                "@type": "ViewAction",
                "target": canonical_url,
                "name": "Open the 360° virtual tour",
            },
            "virtualLocation": {"@id": virtual_location_id},
            "hasPart": scene_images,
            "datePublished": getattr(tour, "published_at", None) or getattr(tour, "created_at", None),
            "dateModified": getattr(tour, "updated_at", None),
        },
    ]

    structured_data = {"@context": "https://schema.org", "@graph": graph}
    return {
        "seo_title": seo_title,
        "seo_description": meta_description,
        "seo_long_description": long_description,
        "seo_canonical_url": canonical_url,
        "seo_robots": robots,
        "seo_indexable": is_indexable,
        "seo_image_url": image_url,
        "seo_image_is_dynamic": image_is_dynamic,
        "seo_image_alt": image_alt,
        "seo_location": location,
        "seo_category": category,
        "seo_structured_data": _json_ld(structured_data),
    }
