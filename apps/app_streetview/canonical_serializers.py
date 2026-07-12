from __future__ import annotations

from apps.tours.models import Hotspot


def _url(field, absolute_url_builder=None):
    try:
        value = field.url if field else ""
    except Exception:
        value = ""
    if value and absolute_url_builder:
        return absolute_url_builder(value)
    return value


def organization_to_dict(org):
    return {
        "id": org.id,
        "name": org.name,
        "slug": org.slug,
        "logo_url": _url(getattr(org, "logo", None)),
        "status": getattr(org, "status", ""),
    }


def place_to_dict(place):
    return {
        "id": place.id,
        "organization_id": place.organization_id,
        "name": place.name,
        "slug": place.slug,
        "category": place.category,
        "description": place.description,
        "address_line": place.address_line,
        "city": place.city,
        "country": place.country,
        "latitude": float(place.latitude) if place.latitude is not None else None,
        "longitude": float(place.longitude) if place.longitude is not None else None,
        "cover_image": place.cover_image,
        "status": place.status,
    }


def source_tour_to_dict(tour, publication=None, include_counts=True):
    place = getattr(tour, "place", None)
    org = getattr(tour, "organization", None)
    data = {
        "id": tour.id,
        "organization_id": tour.organization_id,
        "organization_name": org.name if org else "",
        "place_id": tour.place_id,
        "place_name": place.name if place else "",
        "title": tour.title,
        "slug": tour.slug,
        "description": tour.description,
        "status": tour.status,
        "thumbnail_url": tour.thumbnail_image_url,
        "location": tour.location or (place.address_line if place else ""),
        "city": place.city if place else "",
        "country": place.country if place else "",
        "latitude": float(tour.lat) if tour.lat is not None else (float(place.latitude) if place and place.latitude is not None else None),
        "longitude": float(tour.lng) if tour.lng is not None else (float(place.longitude) if place and place.longitude is not None else None),
    }
    if publication:
        data["streetview"] = source_publication_summary_to_dict(publication)
    if include_counts:
        data["scenes_count"] = getattr(tour, "scenes_count", None) or tour.scenes.count()
        data["published_scenes_count"] = publication.scene_states.filter(google_photo_id__gt="").count() if publication else 0
    return data


def source_scene_state_to_dict(state, absolute_url_builder=None):
    scene = state.source_scene
    tour = scene.tour
    place = getattr(tour, "place", None)
    image = state.image_file
    preview = scene.thumbnail_image or scene.image_360_preview or scene.image_360_mobile or scene.image_360 or scene.image_360_original
    lat = state.effective_latitude
    lng = state.effective_longitude
    return {
        "id": scene.id,
        "state_id": state.id,
        "publication_id": state.publication_id,
        "tour_id": tour.id,
        "title": scene.title,
        "order": scene.order,
        "status": scene.status,
        "is_public": scene.is_public,
        "image_url": _url(image, absolute_url_builder),
        "preview_url": _url(preview, absolute_url_builder),
        "thumbnail_url": _url(scene.thumbnail_image, absolute_url_builder),
        "has_image": state.has_image,
        "source_images": {
            "original": _url(scene.image_360_original, absolute_url_builder),
            "desktop": _url(scene.image_360, absolute_url_builder),
            "mobile": _url(scene.image_360_mobile, absolute_url_builder),
            "preview": _url(scene.image_360_preview, absolute_url_builder),
            "thumbnail": _url(scene.thumbnail_image, absolute_url_builder),
        },
        "gps": {
            "latitude": float(lat) if lat is not None else None,
            "longitude": float(lng) if lng is not None else None,
            "altitude": state.altitude,
            "source": "scene_override" if state.latitude is not None and state.longitude is not None else ("tour" if tour.lat is not None and tour.lng is not None else ("place" if place and place.latitude is not None and place.longitude is not None else "missing")),
        },
        "camera": {
            "heading": state.heading,
            "pitch": state.pitch,
            "roll": state.roll,
            "initial_fov": state.initial_fov,
            "source_yaw_default": scene.yaw_default,
            "source_pitch_default": scene.pitch_default,
            "source_hfov_default": scene.hfov_default,
        },
        "google": {
            "photo_id": state.google_photo_id,
            "share_link": state.google_share_link,
            "thumbnail_url": state.google_thumbnail_url,
            "publish_status": state.publish_status,
            "last_error": state.last_error,
            "is_published": bool(state.google_photo_id),
            "is_connected": state.publish_status == "connected",
        },
    }


def hotspot_to_source_link_dict(hotspot):
    return {
        "id": hotspot.id,
        "scene": hotspot.scene_id,
        "target_scene": hotspot.target_scene_id,
        "label": hotspot.label,
        "yaw": hotspot.yaw,
        "pitch": hotspot.pitch,
        "type": hotspot.type,
    }


def source_publication_summary_to_dict(publication):
    return {
        "id": publication.id,
        "public_id": str(publication.public_id),
        "source_tour_id": publication.source_tour_id,
        "status": publication.status,
        "last_error": publication.last_error,
        "published_at": publication.published_at.isoformat() if publication.published_at else None,
        "scenes_count": publication.scene_states.count(),
        "published_scenes_count": publication.scene_states.filter(google_photo_id__gt="").count(),
        "connected_scenes_count": publication.scene_states.filter(publish_status="connected").count(),
    }


def source_publication_to_dict(publication, absolute_url_builder=None):
    tour = publication.source_tour
    nav_hotspots = Hotspot.objects.filter(
        scene__tour=tour,
        type=Hotspot.Type.NAVIGATE,
        target_scene__isnull=False,
    ).order_by("scene__order", "id")
    return {
        "publication": source_publication_summary_to_dict(publication),
        "tour": source_tour_to_dict(tour, publication=publication, include_counts=True),
        "organization": organization_to_dict(tour.organization),
        "place": place_to_dict(tour.place),
        "scenes": [source_scene_state_to_dict(s, absolute_url_builder) for s in publication.scene_states.select_related("source_scene", "source_scene__tour", "source_scene__tour__place").order_by("source_scene__order", "source_scene_id")],
        "navigation_links": [hotspot_to_source_link_dict(h) for h in nav_hotspots],
    }


def source_publish_job_to_dict(job):
    return {
        "id": job.id,
        "public_id": str(job.public_id),
        "publication_id": job.publication_id,
        "source_tour_id": job.publication.source_tour_id,
        "status": job.status,
        "total_scenes": job.total_scenes,
        "published_scenes": job.published_scenes,
        "failed_scenes": job.failed_scenes,
        "log": job.log,
        "error": job.error,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }
