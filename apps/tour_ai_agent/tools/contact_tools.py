from __future__ import annotations


def contact_options(organization, tour=None):
    """Return only contact data belonging to the active tour organization."""
    # Organization-level public contacts are authoritative. A legacy tour
    # contact is used only when the organization has no configured public email.
    email = getattr(organization, "public_email", "") or getattr(organization, "email", "")
    if not email and tour:
        email = getattr(tour, "contact_email", "")
    phone = getattr(organization, "public_phone", "") or getattr(organization, "phone", "")
    website = getattr(organization, "website_url", "") or getattr(organization, "website", "")
    booking_url = getattr(organization, "booking_url", "")
    social = {
        key: value for key, value in {
            "facebook": getattr(organization, "facebook_url", ""),
            "instagram": getattr(organization, "instagram_url", ""),
            "tiktok": getattr(organization, "tiktok_url", ""),
            "linkedin": getattr(organization, "linkedin_url", ""),
            "youtube": getattr(organization, "youtube_url", ""),
        }.items() if value
    }
    try:
        resources = list(
            organization.embedded_resources.filter(
                is_active=True,
                is_verified=True,
                allow_in_tour_agent=True,
            ).values(
                "id", "label", "kind", "url", "embed_mode",
                "button_label", "description", "sandbox_permissions",
            )[:20]
        )
    except Exception:
        resources = []

    return {
        "organization_id": organization.id,
        "organization_name": organization.name,
        "email": email or "",
        "phone": phone or "",
        "website": website or "",
        "booking_url": booking_url or "",
        "social_links": social,
        "resources": resources,
        "allow_embedded_resources": bool(getattr(organization, "ai_allow_embedded_resources", True)),
    }
