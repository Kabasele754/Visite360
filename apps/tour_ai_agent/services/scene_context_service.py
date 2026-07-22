from __future__ import annotations

from apps.tour_ai_agent.models import SceneProductMatch, TourSceneAIProfile


def _safe(value, default=""):
    return value if value not in (None, "") else default


def _clean_visual_text(value, max_length=360):
    text = " ".join(str(value or "").replace("```json", " ").replace("```", " ").split())
    if not text or text.startswith(("{", "[")):
        return ""
    for marker in (" {", " ["):
        position = text.find(marker)
        if position > 20:
            text = text[:position].strip()
            break
    if len(text) > max_length:
        text = text[:max_length].rsplit(" ", 1)[0].rstrip(" ,;:-") + "…"
    return text


def _organization_context(organization) -> dict:
    if not organization:
        return {}
    return {
        "id": organization.id,
        "name": organization.name,
        "slug": organization.slug,
        "status": organization.status,
        "description": _safe(getattr(organization, "description", "")),
        "website_url": _safe(getattr(organization, "website_url", "")),
        "booking_url": _safe(getattr(organization, "booking_url", "")),
        "public_email": _safe(getattr(organization, "public_email", "")),
        "public_phone": _safe(getattr(organization, "public_phone", "")),
        "social_links": {
            key: value for key, value in {
                "facebook": getattr(organization, "facebook_url", ""),
                "instagram": getattr(organization, "instagram_url", ""),
                "tiktok": getattr(organization, "tiktok_url", ""),
                "linkedin": getattr(organization, "linkedin_url", ""),
                "youtube": getattr(organization, "youtube_url", ""),
            }.items() if value
        },
    }


def _place_context(place) -> dict:
    if not place:
        return {}
    return {
        "id": place.id,
        "name": place.name,
        "category": place.category,
        "description": place.description,
        "address": place.address_line,
        "city": place.city,
        "country": place.country,
    }


def get_scene_context(scene, *, tour=None) -> dict:
    profile = TourSceneAIProfile.objects.filter(scene=scene).first() if scene else None
    matches = []
    if scene:
        matches = list(
            SceneProductMatch.objects.filter(scene=scene, product__status="active")
            .select_related("product", "product__category")
            .order_by("-is_verified", "-confidence")[:12]
        )

    detected_objects = []
    if profile:
        for detection in profile.local_detections or []:
            label = str(detection.get("label", "")).strip()
            if not label:
                continue
            detected_objects.append({
                "label": label,
                "confidence": round(float(detection.get("confidence", 0)), 3),
                "yaw": detection.get("yaw"),
                "source": "local_vision",
            })

    # Deduplicate labels while preserving the strongest confidence.
    deduped = {}
    for item in detected_objects:
        current = deduped.get(item["label"].lower())
        if current is None or item["confidence"] > current["confidence"]:
            deduped[item["label"].lower()] = item

    products = []
    for match in matches:
        product = match.product
        products.append({
            "id": product.id,
            "name": product.name,
            "category": product.category.name if product.category else "",
            "short_description": product.short_description,
            "price": str(product.price),
            "currency": product.currency,
            "in_stock": product.in_stock,
            "verified": match.is_verified,
            "confidence": round(match.confidence, 3),
            "match_reason": match.match_reason,
            "cover_image": product.cover_image.url if product.cover_image else "",
        })

    enterprise = None
    enterprise_insights = []
    if scene:
        try:
            from apps.vision_ai.services.insights import latest_scene_analysis
            enterprise = latest_scene_analysis(scene)
            if enterprise:
                enterprise_insights = list(
                    enterprise.insights.order_by("-confidence").values(
                        "kind", "label", "title", "description", "confidence", "source_providers"
                    )[:40]
                )
        except Exception:
            enterprise = None

    enterprise_objects = [
        {
            "label": item["label"] or item["title"],
            "title": _clean_visual_text(item["title"], 180),
            "description": _clean_visual_text(item["description"], 320),
            "confidence": round(float(item["confidence"] or 0), 3),
            "kind": item["kind"],
            "source": item["source_providers"],
        }
        for item in enterprise_insights
    ]

    scene_payload = {
        "id": scene.id if scene else None,
        "title": scene.title if scene else "",
        "type": enterprise.scene_type if enterprise else (profile.final_scene_type if profile else ""),
        "summary": _clean_visual_text(enterprise.summary if enterprise else (profile.final_summary if profile else ""), 360),
        "features": enterprise.features if enterprise else (profile.final_features if profile else []),
        "analysis_source": "enterprise_vision" if enterprise else (profile.analysis_source if profile else ""),
        "analysis_confidence": round(float(enterprise.confidence), 3) if enterprise else (round(profile.analysis_confidence, 3) if profile else 0),
        "detected_objects": enterprise_objects or list(deduped.values())[:30],
        "recognized_text": enterprise.extracted_text[:5000] if enterprise else "",
        "vision_pipeline": {
            "providers": enterprise.completed_providers,
            "analysis_id": str(enterprise.id),
            "insight_count": len(enterprise_insights),
        } if enterprise else {},
        "visual_hypotheses": enterprise.products if enterprise else ((profile.gemini_payload or {}).get("product_hypotheses", []) if profile else []),
        "suggested_questions": profile.suggested_questions if profile else [],
    }

    resolved_tour = tour or getattr(scene, "tour", None)
    organization = getattr(resolved_tour, "organization", None) if resolved_tour else getattr(scene, "organization", None)
    place = getattr(resolved_tour, "place", None) if resolved_tour else None

    return {
        "organization": _organization_context(organization),
        "place": _place_context(place),
        "scene": scene_payload,
        "products": products,
        "catalogue_status": {
            "verified_product_count": sum(1 for product in products if product["verified"]),
            "candidate_product_count": sum(1 for product in products if not product["verified"]),
            "has_verified_products": any(product["verified"] for product in products),
        },
    }
