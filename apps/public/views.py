from urllib.parse import unquote

from django.conf import settings
from django.contrib import messages
from django.db.models import Count, Q, Prefetch
from django.shortcuts import render
from django.urls import reverse, reverse_lazy
from django.views.generic import TemplateView, FormView

from apps.tours.models import Hotspot, Tour, Scene360
from apps.places.models import Place
from apps.organizations.models import Organization
from .forms import ContactLeadForm



from django.core.cache import cache
from django.utils.text import Truncator



class PublicHomeView(TemplateView):
    template_name = "public/home.html"

    HOME_CATALOG_LIMIT = 30
    FEATURED_LIMIT = 6
    LATEST_LIMIT = 12
    CACHE_TIMEOUT = 60 * 5  # 5 minutes

    def _normalize_media_url(self, value):
        if not value:
            return ""

        if hasattr(value, "url"):
            try:
                value = value.url
            except Exception:
                value = str(value)

        url = unquote(str(value)).strip()
        url = (
            url.replace("\\u002D", "-")
               .replace("u002D", "-")
               .replace("\\u002F", "/")
               .replace("u002F", "/")
        )

        while "/media//" in url:
            url = url.replace("/media//", "/media/")

        return url

    def _get_file_url(self, file_field):
        if not file_field:
            return ""

        try:
            return file_field.url
        except Exception:
            return str(file_field)

    def _get_scene_queryset(self):
        """
        Important pour la rapidité :
        on charge uniquement les scènes publiques utiles pour l'image de preview.
        """
        queryset = Scene360.objects.order_by("order", "id").only(
            "id",
            "tour_id",
            "title",
            "order",
            "status",
            "is_public",
            "image_360",
            "image_360_mobile",
            "thumbnail_image",
        ).filter(is_public=True)

        if hasattr(Scene360, "Status") and hasattr(Scene360.Status, "INACTIVE"):
            queryset = queryset.exclude(status=Scene360.Status.INACTIVE)

        return queryset

    def _get_base_tours_queryset(self):
        """
        Base propre et optimisée.
        On ne met pas encore Prefetch ici pour éviter de charger les scènes
        de toutes les visites avant la limitation.
        """
        return (
            Tour.objects
            .select_related("organization", "place")
            .filter(
                status=Tour.Status.PUBLISHED,
                organization__status=Organization.Status.ACTIVE,
                place__status=Place.Status.PUBLISHED,
            )
            .annotate(
                scene_count=Count(
                    "scenes",
                    filter=Q(scenes__is_public=True),
                    distinct=True,
                ),
                photo_count=Count("photos", distinct=True),
            )
        )

    def _apply_filters(self, queryset, q="", category="", city=""):
        if q:
            queryset = queryset.filter(
                Q(title__icontains=q)
                | Q(description__icontains=q)
                | Q(guide_name__icontains=q)
                | Q(place__name__icontains=q)
                | Q(place__city__icontains=q)
                | Q(place__country__icontains=q)
                | Q(organization__name__icontains=q)
            )

        if category:
            queryset = queryset.filter(place__category=category)

        if city:
            queryset = queryset.filter(place__city__iexact=city)

        return queryset

    def _decorate_tour_media(self, tour):
        tour.safe_thumbnail_image_url = self._normalize_media_url(
            getattr(tour, "thumbnail_image_url", "") or ""
        )
        tour.safe_thumbnail_image_mobile_url = self._normalize_media_url(
            getattr(tour, "thumbnail_image_mobile_url", "") or ""
        )

        place_cover = ""
        if getattr(tour, "place", None) and getattr(tour.place, "cover_image", None):
            place_cover = self._get_file_url(tour.place.cover_image)

        tour.safe_place_cover_image_url = self._normalize_media_url(place_cover)

        for scene in getattr(tour, "ordered_scenes", []):
            scene.safe_image_360_url = self._normalize_media_url(
                getattr(scene, "image_360_url", "") or ""
            )
            scene.safe_image_360_mobile_url = self._normalize_media_url(
                getattr(scene, "image_360_mobile_url", "") or ""
            )
            scene.safe_image_360_preview_url = self._normalize_media_url(
                getattr(scene, "image_360_preview_url", "") or ""
            )
            scene.safe_thumbnail_url = self._normalize_media_url(
                getattr(scene, "thumbnail_url", "") or ""
            )

        return tour

    def _get_tour_preview_images(self, tour):
        empty = {
            "hero": "",
            "hero_mobile": "",
            "card": "",
            "card_mobile": "",
            "viewer_desktop": "",
            "viewer_mobile": "",
            "thumbnail": "",
            "placeholder": "",
        }

        if not tour:
            return empty

        ordered_scenes = getattr(tour, "ordered_scenes", []) or []
        first_scene = ordered_scenes[0] if ordered_scenes else None

        scene_full = ""
        scene_mobile = ""
        scene_preview = ""
        scene_thumb = ""

        if first_scene:
            scene_full = getattr(first_scene, "safe_image_360_url", "") or ""
            scene_mobile = getattr(first_scene, "safe_image_360_mobile_url", "") or ""
            scene_preview = getattr(first_scene, "safe_image_360_preview_url", "") or ""
            scene_thumb = getattr(first_scene, "safe_thumbnail_url", "") or ""

        tour_thumb = getattr(tour, "safe_thumbnail_image_url", "") or ""
        tour_thumb_mobile = getattr(tour, "safe_thumbnail_image_mobile_url", "") or ""
        place_cover = getattr(tour, "safe_place_cover_image_url", "") or ""

        placeholder = (
            scene_thumb
            or tour_thumb_mobile
            or tour_thumb
            or place_cover
            or scene_preview
            or scene_mobile
            or scene_full
        )

        lightweight_desktop = (
            scene_preview
            or scene_thumb
            or tour_thumb
            or place_cover
            or scene_mobile
            or scene_full
        )

        lightweight_mobile = (
            scene_thumb
            or scene_preview
            or tour_thumb_mobile
            or tour_thumb
            or place_cover
            or scene_mobile
            or scene_full
        )

        viewer_desktop = (
            scene_full
            or scene_mobile
            or scene_preview
            or scene_thumb
            or tour_thumb
            or place_cover
        )

        viewer_mobile = (
            scene_mobile
            or scene_full
            or scene_preview
            or scene_thumb
            or tour_thumb_mobile
            or tour_thumb
            or place_cover
        )

        thumbnail = (
            scene_thumb
            or scene_preview
            or tour_thumb_mobile
            or tour_thumb
            or place_cover
            or lightweight_mobile
            or viewer_desktop
        )

        return {
            "hero": self._normalize_media_url(lightweight_desktop),
            "hero_mobile": self._normalize_media_url(lightweight_mobile),
            "card": self._normalize_media_url(lightweight_desktop),
            "card_mobile": self._normalize_media_url(lightweight_mobile),
            "viewer_desktop": self._normalize_media_url(viewer_desktop),
            "viewer_mobile": self._normalize_media_url(viewer_mobile),
            "thumbnail": self._normalize_media_url(thumbnail),
            "placeholder": self._normalize_media_url(placeholder),
        }

    def _build_catalog_item(self, tour):
        preview_url = reverse(
            "tour-preview-public",
            kwargs={
                "organization_slug": tour.organization.slug,
                "tour_id": tour.id,
            },
        )

        preview_images = self._get_tour_preview_images(tour)

        short_description = Truncator(tour.description or "").chars(140)

        return {
            "id": tour.id,
            "title": tour.title or "",
            "description": short_description,
            "organization": tour.organization.name if tour.organization else "",
            "organization_slug": tour.organization.slug if tour.organization else "",
            "place_name": tour.place.name if tour.place else "",
            "category": tour.place.category if tour.place else "",
            "category_label": tour.place.get_category_display() if tour.place else "",
            "city": tour.place.city if tour.place else "",
            "country": tour.place.country if tour.place else "",
            "scene_count": tour.scene_count or 0,
            "photo_count": tour.photo_count or 0,
            "view_count": tour.view_count or 0,
            "rating": float(tour.rating) if getattr(tour, "rating", None) is not None else None,
            "price": str(tour.display_price) if getattr(tour, "display_price", None) is not None else "",
            "is_featured": bool(tour.is_featured),

            # Images légères pour la home.
            "image_url": preview_images["card"],
            "image_mobile_url": preview_images["card_mobile"],
            "thumbnail_url": preview_images["thumbnail"],
            "placeholder_url": preview_images["placeholder"],

            # Images 360 complètes : à utiliser seulement au clic.
            "viewer_desktop_url": preview_images["viewer_desktop"],
            "viewer_mobile_url": preview_images["viewer_mobile"],

            "preview_url": preview_url,
            "created_at": tour.created_at.isoformat() if tour.created_at else "",
            "search_blob": " ".join(
                filter(
                    None,
                    [
                        tour.title or "",
                        short_description,
                        tour.organization.name if tour.organization else "",
                        tour.place.name if tour.place else "",
                        tour.place.city if tour.place else "",
                        tour.place.country if tour.place else "",
                        tour.guide_name or "",
                    ],
                )
            ).lower(),
        }

    def _get_top_places(self):
        cache_key = "public_home_top_places_v1"
        cached = cache.get(cache_key)

        if cached is not None:
            return cached

        data = list(
            Place.objects
            .select_related("organization")
            .filter(
                status=Place.Status.PUBLISHED,
                organization__status=Organization.Status.ACTIVE,
            )
            .annotate(
                published_tour_count=Count(
                    "tours",
                    filter=Q(tours__status=Tour.Status.PUBLISHED),
                    distinct=True,
                )
            )
            .filter(published_tour_count__gt=0)
            .order_by("-published_tour_count", "name")[:8]
        )

        cache.set(cache_key, data, self.CACHE_TIMEOUT)
        return data

    def _get_top_organizations(self):
        cache_key = "public_home_top_organizations_v1"
        cached = cache.get(cache_key)

        if cached is not None:
            return cached

        data = list(
            Organization.objects
            .filter(status=Organization.Status.ACTIVE)
            .annotate(
                published_tour_count=Count(
                    "tours",
                    filter=Q(tours__status=Tour.Status.PUBLISHED),
                    distinct=True,
                ),
                published_place_count=Count(
                    "places",
                    filter=Q(places__status=Place.Status.PUBLISHED),
                    distinct=True,
                ),
            )
            .filter(published_tour_count__gt=0)
            .order_by("-published_tour_count", "name")[:8]
        )

        cache.set(cache_key, data, self.CACHE_TIMEOUT)
        return data

    def _get_available_cities(self):
        cache_key = "public_home_available_cities_v1"
        cached = cache.get(cache_key)

        if cached is not None:
            return cached

        data = list(
            Place.objects
            .filter(
                status=Place.Status.PUBLISHED,
                organization__status=Organization.Status.ACTIVE,
            )
            .exclude(city__isnull=True)
            .exclude(city__exact="")
            .values_list("city", flat=True)
            .distinct()
            .order_by("city")[:50]
        )

        cache.set(cache_key, data, self.CACHE_TIMEOUT)
        return data

    def _get_global_stats(self):
        cache_key = "public_home_global_stats_v1"
        cached = cache.get(cache_key)

        if cached is not None:
            return cached

        data = {
            "place_count": Place.objects.filter(
                status=Place.Status.PUBLISHED,
                organization__status=Organization.Status.ACTIVE,
            ).count(),
            "organization_count": Organization.objects.filter(
                status=Organization.Status.ACTIVE,
                tours__status=Tour.Status.PUBLISHED,
            ).distinct().count(),
        }

        cache.set(cache_key, data, self.CACHE_TIMEOUT)
        return data

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        q = self.request.GET.get("q", "").strip()
        category = self.request.GET.get("category", "").strip()
        city = self.request.GET.get("city", "").strip()

        base_qs = self._get_base_tours_queryset()
        filtered_qs = self._apply_filters(base_qs, q=q, category=category, city=city)

        total_filtered_tours = filtered_qs.count()

        display_qs = (
            filtered_qs
            .prefetch_related(
                Prefetch(
                    "scenes",
                    queryset=self._get_scene_queryset(),
                    to_attr="ordered_scenes",
                )
            )
            .order_by("-is_featured", "-created_at")[:self.HOME_CATALOG_LIMIT]
        )

        published_tours = list(display_qs)

        for tour in published_tours:
            self._decorate_tour_media(tour)

        featured_tours = [tour for tour in published_tours if tour.is_featured][:self.FEATURED_LIMIT]
        latest_tours = published_tours[:self.LATEST_LIMIT]

        hero_tour = featured_tours[0] if featured_tours else (latest_tours[0] if latest_tours else None)
        hero_preview_images = self._get_tour_preview_images(hero_tour)

        catalog_tours = [self._build_catalog_item(tour) for tour in published_tours]

        global_stats = self._get_global_stats()

        context.update(
            {
                "hero_tour": hero_tour,
                "hero_scene_url": hero_preview_images["hero"],
                "hero_scene_mobile_url": hero_preview_images["hero_mobile"],
                "hero_scene_thumbnail_url": hero_preview_images["thumbnail"],
                "hero_scene_placeholder_url": hero_preview_images["placeholder"],
                "hero_scene_viewer_url": hero_preview_images["viewer_desktop"],
                "hero_scene_viewer_mobile_url": hero_preview_images["viewer_mobile"],

                "featured_tours": featured_tours,
                "latest_tours": latest_tours,

                "top_places": self._get_top_places(),
                "top_organizations": self._get_top_organizations(),
                "available_cities": self._get_available_cities(),

                "category_choices": Place.Category.choices,
                "selected_q": q,
                "selected_category": category,
                "selected_city": city,

                # Important : seulement 30 visites maximum dans le HTML.
                "catalog_tours": catalog_tours,
                "catalog_total_count": total_filtered_tours,
                "catalog_loaded_count": len(catalog_tours),
                "catalog_has_more": total_filtered_tours > len(catalog_tours),

                "stats": {
                    "tour_count": total_filtered_tours,
                    "place_count": global_stats["place_count"],
                    "organization_count": global_stats["organization_count"],
                },
            }
        )

        return context





PUBLIC_MAP_TOUR_LIMIT = 120
PUBLIC_MAP_CACHE_TIMEOUT = 60 * 3  # 3 minutes


def _normalize_media_url(value):
    if not value:
        return ""

    if hasattr(value, "url"):
        try:
            value = value.url
        except Exception:
            value = str(value)

    url = unquote(str(value)).strip()
    url = (
        url.replace("\\u002D", "-")
           .replace("u002D", "-")
           .replace("\\u002F", "/")
           .replace("u002F", "/")
    )

    while "/media//" in url:
        url = url.replace("/media//", "/media/")

    return url


def _safe_file_or_url(value):
    if not value:
        return ""

    if hasattr(value, "url"):
        try:
            return value.url
        except Exception:
            return str(value)

    return str(value)


def _get_public_map_scene_queryset():
    """
    Pour la carte, on ne charge pas les images 360 complètes.
    On charge seulement les scènes publiques utiles pour trouver une miniature.
    """
    queryset = (
        Scene360.objects
        .filter(is_public=True)
        .order_by("order", "id")
        .only(
            "id",
            "tour_id",
            "title",
            "order",
            "status",
            "is_public",
            "thumbnail_image",
            "image_360_mobile",
        )
    )

    if hasattr(Scene360, "Status") and hasattr(Scene360.Status, "INACTIVE"):
        queryset = queryset.exclude(status=Scene360.Status.INACTIVE)

    return queryset


def _get_public_map_base_queryset():
    """
    Base optimisée :
    - select_related pour éviter les requêtes répétées organization/place.
    - Count pour éviter de parcourir toutes les scènes/hotspots en Python.
    """
    return (
        Tour.objects
        .select_related("organization", "place")
        .filter(
            status=Tour.Status.PUBLISHED,
            organization__status=Organization.Status.ACTIVE,
            place__status=Place.Status.PUBLISHED,
        )
        .annotate(
            public_scene_count=Count(
                "scenes",
                filter=Q(scenes__is_public=True),
                distinct=True,
            ),
            public_hotspot_count=Count(
                "scenes__hotspots",
                filter=Q(scenes__is_public=True),
                distinct=True,
            ),
        )
    )


def _apply_public_map_filters(queryset, selected_q="", selected_category="", selected_city=""):
    if selected_q:
        queryset = queryset.filter(
            Q(title__icontains=selected_q)
            | Q(description__icontains=selected_q)
            | Q(location__icontains=selected_q)
            | Q(guide_name__icontains=selected_q)
            | Q(place__name__icontains=selected_q)
            | Q(place__description__icontains=selected_q)
            | Q(place__address_line__icontains=selected_q)
            | Q(place__city__icontains=selected_q)
            | Q(place__country__icontains=selected_q)
            | Q(place__category__icontains=selected_q)
            | Q(organization__name__icontains=selected_q)
            | Q(scenes__hotspots__label__icontains=selected_q)
            | Q(scenes__hotspots__title__icontains=selected_q)
            | Q(scenes__hotspots__description__icontains=selected_q)
            | Q(scenes__hotspots__tooltip_text__icontains=selected_q)
        ).distinct()

    if selected_category:
        queryset = queryset.filter(place__category=selected_category)

    if selected_city:
        queryset = queryset.filter(place__city__iexact=selected_city)

    return queryset


def _get_public_map_available_cities():
    cache_key = "public_map_available_cities_v1"
    cached = cache.get(cache_key)

    if cached is not None:
        return cached

    cities = list(
        Place.objects
        .filter(
            status=Place.Status.PUBLISHED,
            organization__status=Organization.Status.ACTIVE,
            tours__status=Tour.Status.PUBLISHED,
        )
        .exclude(city__isnull=True)
        .exclude(city__exact="")
        .values_list("city", flat=True)
        .distinct()
        .order_by("city")[:80]
    )

    cache.set(cache_key, cities, PUBLIC_MAP_CACHE_TIMEOUT)
    return cities


def _build_public_map_tour_item(tour):
    place = tour.place

    lat = tour.lat if tour.lat is not None else place.latitude
    lng = tour.lng if tour.lng is not None else place.longitude

    if lat is None or lng is None:
        return None

    lat = float(lat)
    lng = float(lng)

    scenes = list(getattr(tour, "ordered_scenes", []))
    first_scene = scenes[0] if scenes else None

    first_scene_thumb = ""
    first_scene_mobile = ""

    if first_scene:
        try:
            first_scene_thumb = getattr(first_scene, "thumbnail_url", "") or ""
        except Exception:
            first_scene_thumb = ""

        try:
            first_scene_mobile = getattr(first_scene, "image_360_mobile_url", "") or ""
        except Exception:
            first_scene_mobile = ""

    place_cover = ""
    if getattr(place, "cover_image", None):
        place_cover = _safe_file_or_url(place.cover_image)

    tour_thumb = ""
    try:
        tour_thumb = getattr(tour, "thumbnail_image_url", "") or ""
    except Exception:
        tour_thumb = ""

    cover_image = (
        tour_thumb
        or first_scene_thumb
        or place_cover
        or first_scene_mobile
        or ""
    )

    address_parts = [
        place.address_line or "",
        place.city or "",
        place.country or "",
    ]
    address = ", ".join([part for part in address_parts if part])

    short_description = Truncator(tour.description or "").chars(120)

    search_blob = " ".join(
        filter(
            None,
            [
                tour.title or "",
                short_description,
                place.name or "",
                place.get_category_display() or "",
                place.category or "",
                place.city or "",
                place.country or "",
                address or "",
                tour.location or "",
                tour.guide_name or "",
                tour.organization.name if tour.organization else "",
            ],
        )
    ).lower()

    return {
        "id": tour.id,
        "title": tour.title or "",
        "slug": tour.slug or "",
        "description": short_description,
        "organization_name": tour.organization.name if tour.organization else "",
        "organization_slug": tour.organization.slug if tour.organization else "",
        "place_name": place.name if place else "",
        "category": place.category or "",
        "category_label": place.get_category_display() if place else "",
        "city": place.city or "",
        "country": place.country or "",
        "address": address,
        "lat": lat,
        "lng": lng,
        "price": str(tour.display_price) if getattr(tour, "display_price", None) is not None else "",
        "rating": float(tour.rating) if getattr(tour, "rating", None) is not None else None,
        "view_count": tour.view_count or 0,
        "is_featured": bool(tour.is_featured),
        "guide_name": tour.guide_name or "",
        "thumbnail": _normalize_media_url(cover_image),
        "scene_count": tour.public_scene_count or 0,
        "hotspot_count": tour.public_hotspot_count or 0,
        "preview_url": reverse(
            "tour-preview-public",
            kwargs={
                "organization_slug": tour.organization.slug,
                "tour_id": tour.id,
            },
        ),
        "street_view_lat": lat,
        "street_view_lng": lng,
        "search_blob": search_blob,
    }


def public_tours_map_view(request):
    selected_q = (request.GET.get("q") or "").strip()
    selected_category = (request.GET.get("category") or "").strip()
    selected_city = (request.GET.get("city") or "").strip()

    base_qs = _get_public_map_base_queryset()
    filtered_qs = _apply_public_map_filters(
        base_qs,
        selected_q=selected_q,
        selected_category=selected_category,
        selected_city=selected_city,
    )

    total_count = filtered_qs.count()

    tours_qs = (
        filtered_qs
        .prefetch_related(
            Prefetch(
                "scenes",
                queryset=_get_public_map_scene_queryset(),
                to_attr="ordered_scenes",
            )
        )
        .order_by("-is_featured", "-created_at")[:PUBLIC_MAP_TOUR_LIMIT]
    )

    tours_map_data = []

    for tour in tours_qs:
        item = _build_public_map_tour_item(tour)

        if item is not None:
            tours_map_data.append(item)

    context = {
        "page_title": "Explore Virtual Tours",
        "google_maps_api_key": getattr(settings, "GOOGLE_MAPS_API_KEY", ""),
        "google_maps_map_id": getattr(settings, "GOOGLE_MAPS_MAP_ID", "DEMO_MAP_ID"),

        # Important : données limitées pour éviter une page trop lourde.
        "tours_map_data": tours_map_data,
        "map_total_count": total_count,
        "map_loaded_count": len(tours_map_data),
        "map_has_more": total_count > len(tours_map_data),

        "category_choices": Place.Category.choices,
        "available_cities": _get_public_map_available_cities(),
        "selected_q": selected_q,
        "selected_category": selected_category,
        "selected_city": selected_city,
    }

    return render(request, "public/public_tours_map.html", context)


from django.db.models import Count, Q, Prefetch
from django.views.generic import TemplateView

from apps.organizations.models import Organization
from apps.places.models import Place


class PublicAboutView(TemplateView):
    template_name = "public/about.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        published_places_qs = (
            Place.objects
            .filter(status=Place.Status.PUBLISHED)
            .order_by("-published_at", "-created_at")
        )

        clients = list(
            Organization.objects
            .filter(status=Organization.Status.ACTIVE)
            .annotate(
                published_places_count=Count(
                    "places",
                    filter=Q(places__status=Place.Status.PUBLISHED),
                    distinct=True,
                )
            )
            .filter(published_places_count__gt=0)
            .prefetch_related(
                Prefetch(
                    "places",
                    queryset=published_places_qs,
                    to_attr="published_places",
                )
            )
            .order_by("name")
        )

        for client in clients:
            category_labels = []
            seen_categories = set()

            for place in getattr(client, "published_places", []):
                if place.category not in seen_categories:
                    seen_categories.add(place.category)
                    category_labels.append(place.get_category_display())

            client.category_labels = category_labels[:4]
            client.featured_places = getattr(client, "published_places", [])[:3]

        context["clients"] = clients
        context["clients_count"] = len(clients)
        context["clients_places_count"] = sum(
            getattr(client, "published_places_count", 0)
            for client in clients
        )

        return context
    
class PublicServicesView(TemplateView):
    template_name = "public/services.html"


class PublicContactView(FormView):
    template_name = "public/contact.html"
    form_class = ContactLeadForm
    success_url = reverse_lazy("public_contact")

    def form_valid(self, form):
        form.save()
        messages.success(self.request, "Thank you. Your message has been sent successfully.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Please correct the form errors and try again.")
        return self.render_to_response(self.get_context_data(form=form))


def custom_bad_request(request, exception):
    return render(request, "errors/400.html", status=400)


def custom_permission_denied(request, exception):
    return render(request, "errors/403.html", status=403)


def custom_page_not_found(request, exception):
    return render(request, "errors/404.html", status=404)


def custom_server_error(request):
    return render(request, "errors/500.html", status=500)
