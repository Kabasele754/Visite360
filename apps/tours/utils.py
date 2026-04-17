from django.utils.text import slugify
from .models import Tour


def generate_unique_tour_slug(title: str) -> str:
    base_slug = slugify(title)[:50] or "tour"
    slug = base_slug
    counter = 1

    while Tour.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1

    return slug



