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


class PublicHomeView(TemplateView):
    template_name = "public/home.html"

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
        Home publique : on ne charge que les scènes utiles et publiques.
        On garde les images lourdes disponibles dans le contexte, mais l'affichage
        de la home utilise d'abord les images légères.
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
        )

        # Si tu veux montrer seulement les scènes visibles dans la partie publique.
        queryset = queryset.filter(is_public=True)

        # Évite les scènes explicitement inactives sur la home publique.
        if hasattr(Scene360, "Status") and hasattr(Scene360.Status, "INACTIVE"):
            queryset = queryset.exclude(status=Scene360.Status.INACTIVE)

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
        """
        Règle finale :
        - home hero/card = image légère d'abord : preview/thumbnail/cover.
        - viewer = image 360 complète selon l'appareil.
        - mobile = priorité à image légère, puis image_360_mobile seulement si besoin.
        """
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

        first_scene = tour.ordered_scenes[0] if getattr(tour, "ordered_scenes", []) else None

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

        # Très léger : affichage immédiat après le chargement de la page.
        placeholder = scene_thumb or tour_thumb_mobile or tour_thumb or place_cover or scene_preview or scene_mobile or scene_full

        # Home desktop : ne jamais commencer par l'image panoramique complète.
        lightweight_desktop = scene_preview or scene_thumb or tour_thumb or place_cover or scene_mobile or scene_full

        # Home mobile : thumbnail/preview d'abord, image_360_mobile seulement en fallback.
        lightweight_mobile = scene_thumb or scene_preview or tour_thumb_mobile or tour_thumb or place_cover or scene_mobile or scene_full

        # Viewer : vraie image 360, choisie selon l'appareil.
        viewer_desktop = scene_full or scene_mobile or scene_preview or scene_thumb or tour_thumb or place_cover
        viewer_mobile = scene_mobile or scene_full or scene_preview or scene_thumb or tour_thumb_mobile or tour_thumb or place_cover

        thumbnail = scene_thumb or scene_preview or tour_thumb_mobile or tour_thumb or place_cover or lightweight_mobile or viewer_desktop

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

        return {
            "id": tour.id,
            "title": tour.title or "",
            "description": tour.description or "",
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
            "rating": float(tour.rating) if tour.rating is not None else None,
            "price": str(tour.display_price) if tour.display_price is not None else "",
            "is_featured": bool(tour.is_featured),

            # Affichage immédiat : images légères seulement.
            "image_url": preview_images["card"],
            "image_mobile_url": preview_images["card_mobile"],
            "thumbnail_url": preview_images["thumbnail"],
            "placeholder_url": preview_images["placeholder"],

            # Viewer : utilisé seulement au clic/ouverture du panorama.
            "viewer_desktop_url": preview_images["viewer_desktop"],
            "viewer_mobile_url": preview_images["viewer_mobile"],

            "preview_url": preview_url,
            "created_at": tour.created_at.isoformat() if tour.created_at else "",
            "search_blob": " ".join(
                filter(
                    None,
                    [
                        tour.title,
                        tour.description,
                        tour.organization.name if tour.organization else "",
                        tour.place.name if tour.place else "",
                        tour.place.city if tour.place else "",
                        tour.place.country if tour.place else "",
                        tour.guide_name or "",
                    ],
                )
            ).lower(),
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        q = self.request.GET.get("q", "").strip()
        category = self.request.GET.get("category", "").strip()
        city = self.request.GET.get("city", "").strip()

        published_tours_qs = (
            Tour.objects.select_related("organization", "place")
            .prefetch_related(
                Prefetch(
                    "scenes",
                    queryset=self._get_scene_queryset(),
                    to_attr="ordered_scenes",
                )
            )
            .filter(
                status=Tour.Status.PUBLISHED,
                organization__status=Organization.Status.ACTIVE,
                place__status=Place.Status.PUBLISHED,
            )
            .annotate(
                scene_count=Count("scenes", filter=Q(scenes__is_public=True), distinct=True),
                photo_count=Count("photos", distinct=True),
            )
            .order_by("-is_featured", "-created_at")
        )

        if q:
            published_tours_qs = published_tours_qs.filter(
                Q(title__icontains=q)
                | Q(description__icontains=q)
                | Q(guide_name__icontains=q)
                | Q(place__name__icontains=q)
                | Q(place__city__icontains=q)
                | Q(place__country__icontains=q)
                | Q(organization__name__icontains=q)
            )

        if category:
            published_tours_qs = published_tours_qs.filter(place__category=category)

        if city:
            published_tours_qs = published_tours_qs.filter(place__city__iexact=city)

        published_tours = list(published_tours_qs)
        for tour in published_tours:
            self._decorate_tour_media(tour)

        featured_tours = [tour for tour in published_tours if tour.is_featured][:6]
        latest_tours = published_tours[:12]

        top_places = (
            Place.objects.select_related("organization")
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

        top_organizations = (
            Organization.objects.filter(status=Organization.Status.ACTIVE)
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

        available_cities = (
            Place.objects.filter(
                status=Place.Status.PUBLISHED,
                organization__status=Organization.Status.ACTIVE,
            )
            .exclude(city__isnull=True)
            .exclude(city__exact="")
            .values_list("city", flat=True)
            .distinct()
            .order_by("city")[:50]
        )

        hero_tour = featured_tours[0] if featured_tours else (latest_tours[0] if latest_tours else None)
        hero_preview_images = self._get_tour_preview_images(hero_tour)

        catalog_tours = [self._build_catalog_item(tour) for tour in published_tours]

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
                "top_places": top_places,
                "top_organizations": top_organizations,
                "available_cities": available_cities,
                "category_choices": Place.Category.choices,
                "selected_q": q,
                "selected_category": category,
                "selected_city": city,
                "catalog_tours": catalog_tours,
                "stats": {
                    "tour_count": published_tours_qs.count(),
                    "place_count": Place.objects.filter(
                        status=Place.Status.PUBLISHED,
                        organization__status=Organization.Status.ACTIVE,
                    ).count(),
                    "organization_count": Organization.objects.filter(
                        status=Organization.Status.ACTIVE,
                        tours__status=Tour.Status.PUBLISHED,
                    ).distinct().count(),
                },
            }
        )
        return context


def public_tours_map_view(request):
    selected_q = (request.GET.get("q") or "").strip()
    selected_category = (request.GET.get("category") or "").strip()
    selected_city = (request.GET.get("city") or "").strip()

    scene_qs = (
        Scene360.objects.filter(is_public=True)
        .exclude(status=getattr(Scene360.Status, "INACTIVE", "inactive"))
        .order_by("order")
        .only(
            "id",
            "tour_id",
            "title",
            "order",
            "status",
            "is_public",
            "image_360_mobile",
            "thumbnail_image",
        )
        .prefetch_related(
            Prefetch(
                "hotspots",
                queryset=Hotspot.objects.select_related("target_scene").order_by("id"),
            )
        )
    )

    tours_qs = (
        Tour.objects.select_related("organization", "place")
        .prefetch_related(Prefetch("scenes", queryset=scene_qs, to_attr="ordered_scenes"))
        .filter(
            status=Tour.Status.PUBLISHED,
            organization__status=Organization.Status.ACTIVE,
            place__status=Place.Status.PUBLISHED,
        )
        .order_by("-is_featured", "-created_at")
    )

    tours_map_data = []
    city_values = set()

    for tour in tours_qs:
        place = tour.place
        lat = tour.lat if tour.lat is not None else place.latitude
        lng = tour.lng if tour.lng is not None else place.longitude

        if lat is None or lng is None:
            continue

        lat = float(lat)
        lng = float(lng)

        scenes = list(getattr(tour, "ordered_scenes", []))
        first_scene = scenes[0] if scenes else None

        first_scene_thumb = ""
        if first_scene:
            first_scene_thumb = self_url = ""
            try:
                first_scene_thumb = first_scene.thumbnail_url or ""
            except Exception:
                first_scene_thumb = ""

        cover_image = (
            tour.thumbnail_image_url
            or (place.cover_image.url if getattr(place, "cover_image", None) else "")
            or first_scene_thumb
            or ""
        )

        address_parts = [place.address_line, place.city, place.country]
        address = ", ".join([p for p in address_parts if p])

        hotspot_keywords = []
        hotspot_count = 0

        for scene in scenes:
            for hotspot in scene.hotspots.all():
                hotspot_count += 1
                payload = hotspot.payload or {}
                content = payload.get("content", {}) if isinstance(payload, dict) else {}
                hotspot_keywords.extend(
                    [
                        hotspot.label or "",
                        hotspot.title or "",
                        hotspot.description or "",
                        hotspot.tooltip_text or "",
                        str(content.get("badge", "")),
                        str(content.get("price", "")),
                        str(content.get("site_name", "")),
                        str(content.get("button_text", "")),
                    ]
                )

        search_blob = " ".join(
            [
                tour.title or "",
                tour.description or "",
                place.name or "",
                place.get_category_display() or "",
                place.category or "",
                place.city or "",
                place.country or "",
                address or "",
                tour.location or "",
                tour.guide_name or "",
                " ".join(hotspot_keywords),
            ]
        ).lower()

        city_name = (place.city or "").strip()
        if city_name:
            city_values.add(city_name)

        tours_map_data.append(
            {
                "id": tour.id,
                "title": tour.title,
                "slug": tour.slug,
                "description": tour.description or "",
                "organization_name": tour.organization.name,
                "organization_slug": tour.organization.slug,
                "place_name": place.name,
                "category": place.category or "",
                "category_label": place.get_category_display(),
                "city": place.city or "",
                "country": place.country or "",
                "address": address,
                "lat": lat,
                "lng": lng,
                "price": str(tour.display_price),
                "rating": float(tour.rating) if tour.rating is not None else None,
                "view_count": tour.view_count,
                "is_featured": tour.is_featured,
                "guide_name": tour.guide_name or "",
                "contact_email": tour.contact_email or "",
                "thumbnail": cover_image,
                "scene_count": len(scenes),
                "hotspot_count": hotspot_count,
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
        )

    context = {
        "page_title": "Explore Virtual Tours",
        "google_maps_api_key": getattr(settings, "GOOGLE_MAPS_API_KEY", ""),
        "google_maps_map_id": getattr(settings, "GOOGLE_MAPS_MAP_ID", "DEMO_MAP_ID"),
        "tours_map_data": tours_map_data,
        "category_choices": Place.Category.choices,
        "available_cities": sorted(city_values),
        "selected_q": selected_q,
        "selected_category": selected_category,
        "selected_city": selected_city,
    }
    return render(request, "public/public_tours_map.html", context)


class PublicAboutView(TemplateView):
    template_name = "public/about.html"


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
