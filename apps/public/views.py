from django.views.generic import TemplateView
from django.db.models import Count, Q, Prefetch
from django.urls import reverse
from django.contrib import messages
from django.shortcuts import redirect

from apps.tours.models import Hotspot, Tour, Scene360
from apps.places.models import Place
from apps.organizations.models import Organization
from django.conf import settings
from django.db.models import Prefetch
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.generic import TemplateView, FormView
from .forms import ContactLeadForm




class PublicHomeView(TemplateView):
    template_name = "public/home.html"

    def _get_tour_preview_image(self, tour):
        first_scene = tour.ordered_scenes[0] if getattr(tour, "ordered_scenes", []) else None
        if first_scene and first_scene.image_360_url:
            return first_scene.image_360_url
        if tour.thumbnail_image_url:
            return tour.thumbnail_image_url
        if tour.place and tour.place.cover_image:
            return tour.place.cover_image
        return ""

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
                    queryset=Scene360.objects.order_by("order", "id"),
                    to_attr="ordered_scenes",
                )
            )
            .filter(
                status=Tour.Status.PUBLISHED,
                organization__status=Organization.Status.ACTIVE,
                place__status=Place.Status.PUBLISHED,
            )
            .annotate(
                scene_count=Count("scenes", distinct=True),
                photo_count=Count("photos", distinct=True),
            )
            .order_by("-is_featured", "-created_at")
        )

        published_tours = list(published_tours_qs)

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
        hero_scene_url = self._get_tour_preview_image(hero_tour) if hero_tour else None

        catalog_tours = []
        for tour in published_tours:
            preview_url = reverse(
                "tour-preview-public",
                kwargs={
                    "organization_slug": tour.organization.slug,
                    "tour_id": tour.id,
                },
            )

            catalog_tours.append(
                {
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
                    "image_url": self._get_tour_preview_image(tour),
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
            )

        context.update(
            {
                "hero_tour": hero_tour,
                "hero_scene_url": hero_scene_url,
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

    scene_qs = Scene360.objects.order_by("order").prefetch_related(
        Prefetch(
            "hotspots",
            queryset=Hotspot.objects.select_related("target_scene").order_by("id"),
        )
    )

    tours_qs = (
        Tour.objects.select_related("organization", "place")
        .prefetch_related(Prefetch("scenes", queryset=scene_qs))
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

        scenes = list(tour.scenes.all())
        first_scene = scenes[0] if scenes else None

        cover_image = (
            tour.thumbnail_image_url
            or (place.cover_image if place.cover_image else "")
            or (first_scene.thumbnail_url if first_scene and first_scene.thumbnail_url else "")
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



from django.views.generic import TemplateView


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
    return render(request, 'errors/400.html', status=400)


def custom_permission_denied(request, exception):
    return render(request, 'errors/403.html', status=403)


def custom_page_not_found(request, exception):
    return render(request, 'errors/404.html', status=404)


def custom_server_error(request):
    return render(request, 'errors/500.html', status=500)



    


