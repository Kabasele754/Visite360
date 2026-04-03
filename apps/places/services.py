from django.utils import timezone
from django.utils.text import slugify

from .models import Place


def generate_unique_place_slug(name: str) -> str:
    base_slug = slugify(name)
    slug = base_slug
    counter = 1

    while Place.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1

    return slug


def prepare_place_before_create(validated_data: dict) -> dict:
    if not validated_data.get("slug") and validated_data.get("name"):
        validated_data["slug"] = generate_unique_place_slug(validated_data["name"])
    return validated_data


def publish_place(place: Place) -> Place:
    place.status = Place.Status.PUBLISHED
    place.published_at = timezone.now()
    place.save(update_fields=["status", "published_at", "updated_at"])
    return place


def archive_place(place: Place) -> Place:
    place.status = Place.Status.ARCHIVED
    place.save(update_fields=["status", "updated_at"])
    return place


def unpublish_place(place: Place) -> Place:
    place.status = Place.Status.DRAFT
    place.save(update_fields=["status", "updated_at"])
    return place

