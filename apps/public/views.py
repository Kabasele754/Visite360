from urllib.parse import parse_qs, unquote, urlparse

from django.conf import settings
from django.core.cache import cache
from django.utils.text import Truncator

import hashlib
import json
import uuid
import re

from django.db.models import F
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from django.contrib import messages
from django.db.models import Count, Q, Prefetch
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse, reverse_lazy
from django.views.generic import TemplateView, FormView

from apps.tours.models import Hotspot, Tour, Scene360, TourUniqueView, TourShare
from apps.places.models import Place
from apps.organizations.models import Organization
from apps.vendors.models import Product, ProductCategory
from .forms import ContactLeadForm








def test_view(request):
    return render(request, "public/3dcards/index.html")



class PublicHomeView(TemplateView):
    template_name = "public/home.html"

    HOME_CATALOG_PAGE_SIZE = 15
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

    def _get_organization_logo_url(self, organization):
        if not organization or not getattr(organization, "logo", None):
            return ""

        return self._normalize_media_url(self._get_file_url(organization.logo))

    def _parse_positive_int(self, value, default, maximum=None):
        try:
            number = int(value)
        except (TypeError, ValueError):
            number = default

        if number < 1:
            number = default

        if maximum is not None:
            number = min(number, maximum)

        return number

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
        Le select_related charge aussi organization.logo via l'objet organization.
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
                unique_view_count=Count("unique_views", distinct=True),
                share_count=Count("shares", distinct=True),
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
        tour_source = ""
        if getattr(tour, "thumbnail_source", None):
            tour_source = self._get_file_url(tour.thumbnail_source)

        # Image originale du Tour : meilleure qualité pour les cards de la home.
        tour.safe_thumbnail_source_url = self._normalize_media_url(tour_source)

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
        tour.safe_organization_logo_url = self._get_organization_logo_url(
            getattr(tour, "organization", None)
        )

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
        """
        Gestion progressive des images :
        - CARD LIGHT : image légère optimisée pour l'affichage immédiat.
        - CARD HIGH : image source plus grande, chargée après coup seulement si nécessaire.
        - HERO / VIEWER : garde les images 360 pour Marzipano.

        Important : Explore all ne doit pas utiliser les panoramas 360 comme images de card.
        """
        empty = {
            "hero": "",
            "hero_mobile": "",
            "card": "",
            "card_mobile": "",
            "card_high": "",
            "viewer_desktop": "",
            "viewer_mobile": "",
            "thumbnail": "",
            "placeholder": "",
            "card_source": "none",
            "card_high_source": "none",
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

        # Images marketing du Tour / Place.
        # thumbnail_source = originale/grande, donc on l'utilise comme image HIGH, pas comme premier chargement.
        tour_source = getattr(tour, "safe_thumbnail_source_url", "") or ""
        tour_thumb = getattr(tour, "safe_thumbnail_image_url", "") or ""
        tour_thumb_mobile = getattr(tour, "safe_thumbnail_image_mobile_url", "") or ""
        place_cover = getattr(tour, "safe_place_cover_image_url", "") or ""

        # LIGHT : charger vite, surtout sur mobile.
        card_mobile = (
            tour_thumb_mobile
            or tour_thumb
            or place_cover
            or tour_source
            or ""
        )

        card_desktop = (
            tour_thumb
            or tour_thumb_mobile
            or place_cover
            or tour_source
            or ""
        )

        # HIGH : qualité max, chargée progressivement après affichage.
        card_high = (
            tour_source
            or tour_thumb
            or tour_thumb_mobile
            or place_cover
            or ""
        )

        if tour_thumb_mobile:
            card_source = "tour.thumbnail_image_mobile"
        elif tour_thumb:
            card_source = "tour.thumbnail_image"
        elif place_cover:
            card_source = "place.cover_image"
        elif tour_source:
            card_source = "tour.thumbnail_source_only"
        else:
            card_source = "none"

        if tour_source:
            card_high_source = "tour.thumbnail_source"
        elif tour_thumb:
            card_high_source = "tour.thumbnail_image"
        elif tour_thumb_mobile:
            card_high_source = "tour.thumbnail_image_mobile"
        elif place_cover:
            card_high_source = "place.cover_image"
        else:
            card_high_source = "none"

        # Hero garde la logique panorama/360.
        hero_desktop = (
            scene_preview
            or scene_thumb
            or scene_mobile
            or scene_full
            or card_desktop
        )

        hero_mobile = (
            scene_preview
            or scene_thumb
            or scene_mobile
            or scene_full
            or card_mobile
        )

        viewer_desktop = (
            scene_full
            or scene_mobile
            or scene_preview
            or scene_thumb
            or ""
        )

        viewer_mobile = (
            scene_mobile
            or scene_full
            or scene_preview
            or scene_thumb
            or ""
        )

        thumbnail = card_mobile or card_desktop or card_high

        return {
            "hero": self._normalize_media_url(hero_desktop),
            "hero_mobile": self._normalize_media_url(hero_mobile),
            "card": self._normalize_media_url(card_desktop),
            "card_mobile": self._normalize_media_url(card_mobile),
            "card_high": self._normalize_media_url(card_high),
            "viewer_desktop": self._normalize_media_url(viewer_desktop),
            "viewer_mobile": self._normalize_media_url(viewer_mobile),
            "thumbnail": self._normalize_media_url(thumbnail),
            "placeholder": self._normalize_media_url(thumbnail),
            "card_source": card_source,
            "card_high_source": card_high_source,
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
        short_description = Truncator(tour.description or "").chars(840)

        return {
            "id": tour.id,
            "title": tour.title or "",
            "description": short_description,
            "organization": tour.organization.name if tour.organization else "",
            "organization_slug": tour.organization.slug if tour.organization else "",
            "organization_logo_url": getattr(tour, "safe_organization_logo_url", "")
            or self._get_organization_logo_url(getattr(tour, "organization", None)),
            "place_name": tour.place.name if tour.place else "",
            "category": tour.place.category if tour.place else "",
            "category_label": tour.place.get_category_display() if tour.place else "",
            "city": tour.place.city if tour.place else "",
            "country": tour.place.country if tour.place else "",
            "scene_count": tour.scene_count or 0,
            "photo_count": tour.photo_count or 0,
            "view_count": tour.view_count or 0,
            "unique_view_count": getattr(tour, "unique_view_count", None) or tour.view_count or 0,
            "share_count": getattr(tour, "share_count", None) or 0,
            "rating": float(tour.rating) if getattr(tour, "rating", None) is not None else None,
            "price": str(tour.display_price) if getattr(tour, "display_price", None) is not None else "",
            "is_featured": bool(tour.is_featured),

            # Images Explore all : STRICTEMENT image du Tour / Place.
            # Pas de fallback Scene360 ici, pour éviter les panoramas flous dans les cards.
            "tour_image_url": preview_images["card"],
            "tour_image_mobile_url": preview_images["card_mobile"],
            "tour_card_image_url": preview_images["card"],
            "tour_card_image_mobile_url": preview_images["card_mobile"],
            "tour_card_image_high_url": preview_images["card_high"],
            "tour_card_image_high_source": preview_images.get("card_high_source", "none"),
            "image_url": preview_images["card"],
            "image_mobile_url": preview_images["card_mobile"],
            "thumbnail_url": preview_images["thumbnail"],
            "placeholder_url": preview_images["placeholder"],
            "card_image_source": preview_images.get("card_source", "none"),
            "has_tour_card_image": bool(preview_images["card"] or preview_images["card_mobile"]),

            # Images 360 complètes : à utiliser seulement au clic.
            "viewer_desktop_url": preview_images["viewer_desktop"],
            "viewer_mobile_url": preview_images["viewer_mobile"],

            "preview_url": preview_url,
            "engagement_url": f"/api/public/tours/{tour.organization.slug}/{tour.id}/engagement/",
            "created_at": tour.created_at.isoformat() if tour.created_at else "",
            "updated_at": tour.updated_at.isoformat() if getattr(tour, "updated_at", None) else "",
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

    def _get_catalog_page_data(self, q="", category="", city="", page=1, page_size=None):
        page_size = self._parse_positive_int(
            page_size,
            self.HOME_CATALOG_PAGE_SIZE,
            maximum=48,
        )
        page = self._parse_positive_int(page, 1)

        filtered_qs = self._apply_filters(
            self._get_base_tours_queryset(),
            q=q,
            category=category,
            city=city,
        )

        # Explore all : par défaut on évite de répéter les Featured.
        # Si l'utilisateur recherche/filtre, on garde tout pour ne pas cacher des résultats utiles.
        if not q and not category and not city:
            filtered_qs = filtered_qs.exclude(is_featured=True)

        total_filtered_tours = filtered_qs.count()
        total_pages = max(1, (total_filtered_tours + page_size - 1) // page_size)
        page = min(page, total_pages)

        start = (page - 1) * page_size
        end = start + page_size

        display_qs = (
            filtered_qs
            .prefetch_related(
                Prefetch(
                    "scenes",
                    queryset=self._get_scene_queryset(),
                    to_attr="ordered_scenes",
                )
            )
            .order_by("-created_at", "-id")[start:end]
        )

        published_tours = list(display_qs)

        for tour in published_tours:
            self._decorate_tour_media(tour)

        return {
            "results": [self._build_catalog_item(tour) for tour in published_tours],
            "total_count": total_filtered_tours,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "loaded_count": min(end, total_filtered_tours),
            "has_more": page < total_pages,
        }

    def _get_decorated_tours(self, queryset, limit):
        display_qs = (
            queryset
            .prefetch_related(
                Prefetch(
                    "scenes",
                    queryset=self._get_scene_queryset(),
                    to_attr="ordered_scenes",
                )
            )[:limit]
        )

        tours = list(display_qs)

        for tour in tours:
            self._decorate_tour_media(tour)

        return tours

    def get(self, request, *args, **kwargs):
        wants_json = (
            request.GET.get("format") == "json"
            or request.headers.get("x-requested-with") == "XMLHttpRequest"
        )

        if wants_json:
            q = request.GET.get("q", "").strip()
            category = request.GET.get("category", "").strip()
            city = request.GET.get("city", "").strip()
            page = request.GET.get("page", "1")
            page_size = request.GET.get("page_size", self.HOME_CATALOG_PAGE_SIZE)

            return JsonResponse(
                self._get_catalog_page_data(
                    q=q,
                    category=category,
                    city=city,
                    page=page,
                    page_size=page_size,
                )
            )

        return super().get(request, *args, **kwargs)

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

        catalog_page_data = self._get_catalog_page_data(
            q=q,
            category=category,
            city=city,
            page=1,
            page_size=self.HOME_CATALOG_PAGE_SIZE,
        )

        filtered_base_qs = self._apply_filters(
            self._get_base_tours_queryset(),
            q=q,
            category=category,
            city=city,
        )

        featured_tours = self._get_decorated_tours(
            filtered_base_qs.filter(is_featured=True).order_by("-created_at"),
            self.FEATURED_LIMIT,
        )

        latest_tours = self._get_decorated_tours(
            filtered_base_qs.order_by("-created_at"),
            self.LATEST_LIMIT,
        )

        hero_tour = featured_tours[0] if featured_tours else (latest_tours[0] if latest_tours else None)
        hero_preview_images = self._get_tour_preview_images(hero_tour)
        global_stats = self._get_global_stats()

        featured_products = list(
            Product.objects.select_related("organization", "category")
            .prefetch_related("gallery")
            .filter(status=Product.Status.ACTIVE, is_featured=True)
            .order_by("-created_at")[:10]
        )

        # Products shown inside the Explore all / Products tab.
        # We keep the queryset deliberately small for a fast home page while
        # still offering a useful catalogue preview.
        home_products = list(
            Product.objects.select_related("organization", "category")
            .prefetch_related("gallery")
            .filter(status=Product.Status.ACTIVE, is_featured=False)
            .order_by("-order_count", "-created_at")[:24]
        )

        product_categories = list(
            ProductCategory.objects.filter(
                is_active=True,
                products__status=Product.Status.ACTIVE,
            )
            .annotate(active_product_count=Count("products", filter=Q(products__status=Product.Status.ACTIVE)))
            .filter(active_product_count__gt=0)
            .order_by("name")
            .distinct()
        )

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
                "featured_products": featured_products,
                "home_products": home_products,
                "home_products_count": len(home_products),
                "product_categories": product_categories,
                "latest_tours": latest_tours,

                "top_places": self._get_top_places(),
                "top_organizations": self._get_top_organizations(),
                "available_cities": self._get_available_cities(),

                "category_choices": Place.Category.choices,
                "selected_q": q,
                "selected_category": category,
                "selected_city": city,

                # Première page seulement. Les suivantes arrivent par infinite scroll JSON.
                "catalog_tours": catalog_page_data["results"],
                "catalog_total_count": catalog_page_data["total_count"],
                "catalog_loaded_count": len(catalog_page_data["results"]),
                "catalog_has_more": catalog_page_data["has_more"],

                "stats": {
                    "tour_count": catalog_page_data["total_count"],
                    "place_count": global_stats["place_count"],
                    "organization_count": global_stats["organization_count"],
                },
            }
        )

        return context




@method_decorator(csrf_exempt, name="dispatch")
class PublicTourEngagementView(View):
    """
    Endpoint public pour compter :
    - les vues uniques du tour ;
    - les partages du tour.

    POST JSON:
    {"action": "view"}
    {"action": "share", "channel": "web_share"}
    """

    COOKIE_NAME = "vtour_visitor_id"
    COOKIE_MAX_AGE = 60 * 60 * 24 * 365  # 1 an

    def _hash(self, value):
        value = str(value or "").strip()
        if not value:
            return ""
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _client_ip(self, request):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "")

    def _visitor_key(self, request):
        if request.user.is_authenticated:
            return f"user:{request.user.pk}", None

        visitor_id = request.COOKIES.get(self.COOKIE_NAME)
        created_cookie = None

        if not visitor_id:
            visitor_id = uuid.uuid4().hex
            created_cookie = visitor_id

        return f"anon:{visitor_id}", created_cookie

    def _payload(self, request):
        try:
            raw = request.body.decode("utf-8") if request.body else "{}"
            return json.loads(raw or "{}")
        except Exception:
            return {}

    def post(self, request, organization_slug, tour_id):
        tour = (
            Tour.objects
            .select_related("organization")
            .filter(
                id=tour_id,
                organization__slug=organization_slug,
                organization__status=Organization.Status.ACTIVE,
                status=Tour.Status.PUBLISHED,
            )
            .first()
        )

        if not tour:
            return JsonResponse({"ok": False, "error": "Tour not found"}, status=404)

        payload = self._payload(request)
        action = str(payload.get("action") or "view").strip().lower()
        visitor_key, new_cookie = self._visitor_key(request)

        user = request.user if request.user.is_authenticated else None
        ip_hash = self._hash(self._client_ip(request))
        user_agent_hash = self._hash(request.META.get("HTTP_USER_AGENT", ""))

        created_view = False
        created_share = False

        if action == "view":
            _, created_view = TourUniqueView.objects.get_or_create(
                tour=tour,
                visitor_key=visitor_key,
                defaults={
                    "user": user,
                    "ip_hash": ip_hash,
                    "user_agent_hash": user_agent_hash,
                },
            )

            # Ancien compteur view_count : on l'incrémente seulement si la vue est unique.
            if created_view:
                Tour.objects.filter(pk=tour.pk).update(view_count=F("view_count") + 1)

        elif action == "share":
            channel = str(payload.get("channel") or "web_share").strip().lower()
            valid_channels = {choice[0] for choice in TourShare.Channel.choices}
            if channel not in valid_channels:
                channel = TourShare.Channel.OTHER

            TourShare.objects.create(
                tour=tour,
                user=user,
                visitor_key=visitor_key,
                channel=channel,
                ip_hash=ip_hash,
                user_agent_hash=user_agent_hash,
            )
            created_share = True

        else:
            return JsonResponse({"ok": False, "error": "Invalid action"}, status=400)

        tour.refresh_from_db(fields=["view_count"])

        response = JsonResponse({
            "ok": True,
            "action": action,
            "created_view": created_view,
            "created_share": created_share,
            "view_count": tour.view_count,
            "unique_view_count": tour.unique_views.count(),
            "share_count": tour.shares.count(),
        })

        if new_cookie:
            response.set_cookie(
                self.COOKIE_NAME,
                new_cookie,
                max_age=self.COOKIE_MAX_AGE,
                httponly=True,
                secure=request.is_secure(),
                samesite="Lax",
            )

        return response




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




def _extract_google_streetview_pano_id(value):
    """
    Extract the public Google Maps pano id from a Google Maps Street View URL.
    Fallback is handled by the frontend with the Street View Publish photo id.
    """
    if not value:
        return ""

    raw = str(value).strip()

    try:
        parsed = urlparse(raw)
        query = parse_qs(parsed.query or "")
        panoid = (query.get("panoid") or [""])[0]
        if panoid:
            return unquote(panoid)
    except Exception:
        pass

    # Common Google Maps share pattern:
    # ...data=!3m4!1e1!3m2!1s<public-pano-id>!2e10
    match = re.search(r"(?:!|&)1s([^!&]+)", raw)
    if match:
        return unquote(match.group(1))

    return ""


def _get_google_streetview_state_map_for_tours(tour_ids):
    """
    Returns the first Google-published scene state for each source tour.
    The page can then open the real uploaded Street View panorama instead of
    searching a random nearby road Street View.
    """
    tour_ids = [int(tour_id) for tour_id in tour_ids if tour_id]
    if not tour_ids:
        return {}

    try:
        from apps.app_streetview.models import StreetViewSourceSceneState
    except Exception:
        return {}

    states = (
        StreetViewSourceSceneState.objects
        .filter(
            publication__source_tour_id__in=tour_ids,
            google_photo_id__gt="",
        )
        .select_related("publication", "source_scene", "source_scene__tour", "source_scene__tour__place")
        .order_by("publication__source_tour_id", "source_scene__order", "source_scene_id")
    )

    state_map = {}

    for state in states:
        tour_id = state.publication.source_tour_id
        current = state_map.get(tour_id)

        if current is None:
            state_map[tour_id] = state
            continue

        # Prefer a scene whose connections were already applied successfully.
        if current.publish_status != "connected" and state.publish_status == "connected":
            state_map[tour_id] = state

    return state_map


def _build_google_streetview_payload(state):
    if not state or not getattr(state, "google_photo_id", ""):
        return {
            "available": False,
            "photo_id": "",
            "pano_id": "",
            "share_link": "",
            "thumbnail_url": "",
            "scene_id": None,
            "scene_title": "",
            "publish_status": "",
            "heading": 0,
            "pitch": 0,
            "latitude": None,
            "longitude": None,
        }

    lat = state.effective_latitude
    lng = state.effective_longitude
    share_link = state.google_share_link or ""
    pano_id = _extract_google_streetview_pano_id(share_link) or state.google_photo_id

    return {
        "available": True,
        "photo_id": state.google_photo_id,
        "pano_id": pano_id,
        "share_link": share_link,
        "thumbnail_url": state.google_thumbnail_url or "",
        "scene_id": state.source_scene_id,
        "scene_title": state.source_scene.title if state.source_scene else "",
        "publish_status": state.publish_status,
        "heading": float(state.heading or 0),
        "pitch": float(state.pitch or 0),
        "latitude": float(lat) if lat is not None else None,
        "longitude": float(lng) if lng is not None else None,
    }

def _build_public_map_tour_item(tour, streetview_state=None):
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

    google_streetview = _build_google_streetview_payload(streetview_state)

    result = {
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
        "street_view_lat": google_streetview.get("latitude") or lat,
        "street_view_lng": google_streetview.get("longitude") or lng,
        "google_streetview": google_streetview,
        "has_google_streetview": bool(google_streetview.get("available")),
        "google_streetview_photo_id": google_streetview.get("photo_id", ""),
        "google_streetview_pano_id": google_streetview.get("pano_id", ""),
        "google_streetview_share_link": google_streetview.get("share_link", ""),
        "google_streetview_scene_title": google_streetview.get("scene_title", ""),
        "search_blob": search_blob,
    }

    return result


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

    tours_qs = list(
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

    streetview_state_map = _get_google_streetview_state_map_for_tours([tour.id for tour in tours_qs])
    tours_map_data = []

    for tour in tours_qs:
        item = _build_public_map_tour_item(
            tour,
            streetview_state=streetview_state_map.get(tour.id),
        )

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
from apps.vendors.models import Product, ProductCategory
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "marketplace_contact_email": getattr(
                settings,
                "TWINSCOPE_CONTACT_EMAIL",
                "contact@twinscopes.com",
            ),
            "marketplace_contact_phone": getattr(
                settings,
                "TWINSCOPE_CONTACT_PHONE",
                "",
            ),
            "marketplace_whatsapp": str(
                getattr(settings, "TWINSCOPE_WHATSAPP", "")
            ).replace("+", "").replace(" ", "").replace("-", ""),
            "marketplace_maps_url": getattr(
                settings,
                "TWINSCOPE_MAPS_URL",
                "https://www.google.com/maps/search/?api=1&query=Twinscopes",
            ),
        })
        return context

    def _is_ajax(self):
        return self.request.headers.get("x-requested-with") == "XMLHttpRequest"

    def form_valid(self, form):
        lead = form.save()

        if self._is_ajax():
            return JsonResponse(
                {
                    "ok": True,
                    "message": "Thank you. Your message has been sent successfully.",
                    "lead_id": lead.pk,
                },
                status=201,
            )

        messages.success(
            self.request,
            "Thank you. Your message has been sent successfully.",
        )
        return super().form_valid(form)

    def form_invalid(self, form):
        if self._is_ajax():
            return JsonResponse(
                {
                    "ok": False,
                    "message": "Please correct the highlighted fields.",
                    "errors": {
                        field: [str(error) for error in errors]
                        for field, errors in form.errors.items()
                    },
                },
                status=422,
            )

        messages.error(
            self.request,
            "Please correct the form errors and try again.",
        )
        return self.render_to_response(self.get_context_data(form=form))


def custom_bad_request(request, exception):
    return render(request, "errors/400.html", status=400)


def custom_permission_denied(request, exception):
    return render(request, "errors/403.html", status=403)


def custom_page_not_found(request, exception):
    return render(request, "errors/404.html", status=404)


def custom_server_error(request):
    return render(request, "errors/500.html", status=500)
