from django.utils import timezone
from django.utils.text import slugify

from .models import Tour


def generate_unique_tour_slug(title: str, model=Tour) -> str:
    base_slug = slugify(title)
    slug = base_slug
    counter = 1

    while model.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1

    return slug


def build_tour_manifest(tour: Tour) -> dict:
    scenes_data = []
    ordered_scenes = tour.scenes.prefetch_related("hotspots").all().order_by("order", "id")
    initial_scene_id = None

    for index, scene in enumerate(ordered_scenes):
        if index == 0:
            initial_scene_id = scene.id

        scenes_data.append({
            "id": scene.id,
            "scene_id": scene.scene_id,
            "title": scene.title,
            "image_url": scene.image_360.url if scene.image_360 else None,
            "thumbnail_url": scene.thumbnail_image.url if scene.thumbnail_image else None,
            "yaw_default": scene.yaw_default,
            "pitch_default": scene.pitch_default,
            "hfov_default": scene.hfov_default,
            "hotspots": [
                {
                    "id": hotspot.id,
                    "hotspot_id": hotspot.hotspot_id,
                    "type": hotspot.type,
                    "label": hotspot.label,
                    "tooltip_text": hotspot.tooltip_text,
                    "yaw": hotspot.yaw,
                    "pitch": hotspot.pitch,
                    "target_scene": hotspot.target_scene_id,
                    "title": hotspot.title,
                    "description": hotspot.description,
                    "selected_icon": hotspot.selected_icon,
                    "ad_image_url": hotspot.ad_image.url if hotspot.ad_image else None,
                    "payload": hotspot.payload,
                }
                for hotspot in scene.hotspots.all()
            ],
        })

    manifest = {
        "tour_id": tour.id,
        "slug": tour.slug,
        "title": tour.title,
        "initial_scene": initial_scene_id,
        "scenes": scenes_data,
    }

    tour.manifest = manifest
    tour.save(update_fields=["manifest", "updated_at"])
    return manifest


def publish_tour(tour: Tour) -> Tour:
    tour.status = Tour.Status.PUBLISHED
    tour.version = (tour.version or 0) + 1
    build_tour_manifest(tour)
    tour.save(update_fields=["status", "version", "manifest", "updated_at"])
    return tour


def increment_tour_views(tour: Tour) -> Tour:
    tour.view_count += 1
    tour.save(update_fields=["view_count", "updated_at"])
    return tour


def prepare_tour_before_create(validated_data: dict) -> dict:
    if not validated_data.get("slug") and validated_data.get("title"):
        validated_data["slug"] = generate_unique_tour_slug(validated_data["title"])
    return validated_data


def unpublish_tour(tour: Tour) -> Tour:
    tour.status = Tour.Status.INACTIVE
    tour.save(update_fields=["status", "updated_at"])
    return tour
