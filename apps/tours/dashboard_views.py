import json
from copy import deepcopy

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_GET, require_POST

from apps.organizations.models import Organization, OrganizationMember
from apps.organizations.selectors import get_user_membership
from apps.places.models import Place
from apps.tours.forms import TourForm
from django.core.cache import cache

from .models import Tour, Scene360, Hotspot
from .services import (
    generate_unique_tour_slug,
    handle_uploaded_scenes,
    create_hotspot,
    build_tour_manifest,
    reorder_scenes_for_tour,
    update_hotspot,
)


# =============================================================================
# BASIC HELPERS
# =============================================================================

def is_ajax(request):
    return request.headers.get("x-requested-with") == "XMLHttpRequest"


def _unique_org_slug(base: str) -> str:
    base_slug = slugify(base) or "my-workspace"
    slug = base_slug
    counter = 1

    while Organization.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1

    return slug


def _unique_place_slug(base: str) -> str:
    base_slug = slugify(base) or "untitled-place"
    slug = base_slug
    counter = 1

    while Place.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1

    return slug

def _payload_bool(value, default=True):
    """
    Convertit proprement une valeur JSON/POST en booléen.
    Utile pour is_public, car parfois le front peut envoyer:
    true, false, "true", "false", "1", "0", "on", "off".
    """
    if value is None:
        return default

    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        value = value.strip().lower()

        if value in {"true", "1", "yes", "on", "public"}:
            return True

        if value in {"false", "0", "no", "off", "hidden", "private"}:
            return False

    return bool(value)


def _get_org_or_403(request, organization_slug, allow_public=False):
    organization = get_object_or_404(Organization, slug=organization_slug)

    if allow_public and not request.user.is_authenticated:
        return organization

    if request.user.is_authenticated and request.user.is_superuser:
        return organization

    if not request.user.is_authenticated:
        return None

    membership = get_user_membership(request.user, organization_slug)
    if not membership:
        return None

    return organization


def _get_or_create_default_workspace(user):
    membership = (
        OrganizationMember.objects.select_related("organization")
        .filter(user=user, is_active=True)
        .order_by("created_at")
        .first()
    )

    if membership:
        organization = membership.organization
    else:
        org_name = "My Workspace"
        org_slug = _unique_org_slug(org_name)

        organization = Organization.objects.create(
            name=org_name,
            slug=org_slug,
            status=Organization.Status.ACTIVE,
        )

        OrganizationMember.objects.create(
            organization=organization,
            user=user,
            role=OrganizationMember.Role.OWNER,
            is_active=True,
        )

    place = Place.objects.filter(organization=organization).order_by("created_at").first()

    if not place:
        place_name = "Untitled Place"
        place = Place.objects.create(
            organization=organization,
            name=place_name,
            slug=_unique_place_slug(place_name),
            category=Place.Category.STORE,
            description="",
            status=Place.Status.DRAFT,
        )

    tour = (
        Tour.objects.filter(organization=organization, place=place)
        .order_by("created_at")
        .first()
    )

    if not tour:
        tour = Tour.objects.create(
            organization=organization,
            place=place,
            title="Untitled Tour",
            slug=generate_unique_tour_slug("Untitled Tour"),
            description="",
            status=Tour.Status.DRAFT,
        )

    return organization, place, tour


# =============================================================================
# SCENE / HOTSPOT PAYLOAD HELPERS
# =============================================================================



def _safe_file_url(request, file_field):
    """
    Retourne une URL absolue propre pour ImageField/FileField.
    Compatible avec stockage local, S3, Cloudflare R2, etc.
    """
    if not file_field:
        return ""

    try:
        url = file_field.url
    except Exception:
        return ""

    if not url:
        return ""

    if url.startswith("http://") or url.startswith("https://"):
        return url

    return request.build_absolute_uri(url)


def _status_value(obj, field_name, default="none"):
    value = getattr(obj, field_name, None)
    return value or default


def _is_status_ready(value):
    return value == "ready"


def _normalize_tiles_manifest(request, scene):
    """
    Convertit le manifest tiles en format directement utilisable par le JS.

    Exemple final :
    {
        "type": "cube",
        "tileSize": 512,
        "levels": [...],
        "urlTemplate": "https://site.com/media/tours/panoramas/tiles/scene/l{z}/{f}/{x}_{y}.webp"
    }
    """
    manifest = deepcopy(getattr(scene, "tiles_manifest", {}) or {})

    url_template = manifest.get("urlTemplate") or ""

    if url_template:
        if not url_template.startswith("http://") and not url_template.startswith("https://"):
            if not url_template.startswith("/"):
                media_url = getattr(settings, "MEDIA_URL", "/media/")
                url_template = f"{media_url.rstrip('/')}/{url_template.lstrip('/')}"

            url_template = request.build_absolute_uri(url_template)

        manifest["urlTemplate"] = url_template

    return manifest


def _scene_assets_payload(request, scene):
    """
    Payload progressif propre :
    - light/preview/thumbnail = image légère pour affichage immédiat.
    - mobile = panorama léger pour téléphone.
    - desktop = panorama haute qualité pour ordinateur.

    Important : on ne transforme pas automatiquement `mobile` en `desktop` dans
    les champs principaux, sinon le front croit avoir une vraie version mobile
    alors qu'il télécharge une grosse image.
    """
    preview = _safe_file_url(request, getattr(scene, "image_360_preview", None))
    thumbnail = _safe_file_url(request, getattr(scene, "thumbnail_image", None))
    mobile = _safe_file_url(request, getattr(scene, "image_360_mobile", None))
    desktop = _safe_file_url(request, getattr(scene, "image_360", None))
    original = _safe_file_url(request, getattr(scene, "image_360_original", None))

    light = preview or thumbnail or mobile
    viewer_mobile = mobile or desktop or original or preview or thumbnail
    viewer_desktop = desktop or original or mobile or preview or thumbnail
    fallback = light or viewer_mobile or viewer_desktop

    return {
        "preview": preview,
        "thumbnail": thumbnail,
        "light": light or fallback,
        "mobile": mobile,
        "desktop": desktop,
        "viewer_mobile": viewer_mobile,
        "viewer_desktop": viewer_desktop,
        "fallback": fallback,
        "original": original,
    }


def _scene_tiles_payload(request, scene):
    tiles_status = _status_value(scene, "tiles_status")
    manifest = _normalize_tiles_manifest(request, scene)

    return {
        "enabled": bool(getattr(scene, "tiles_enabled", False)),
        "status": tiles_status,
        "ready": _is_status_ready(tiles_status) and bool(manifest),
        "manifest": manifest,
        "generated_at": (
            scene.tiles_generated_at.isoformat()
            if getattr(scene, "tiles_generated_at", None)
            else None
        ),
        "error": getattr(scene, "tiles_error", "") or "",
    }


def _scene_statuses_payload(scene):
    return {
        "assets": _status_value(scene, "assets_status"),
        "tiles": _status_value(scene, "tiles_status"),
        "ai_analysis": _status_value(scene, "ai_analysis_status"),
        "ai_hotspots": _status_value(scene, "ai_hotspots_status"),
    }


def _serialize_hotspot_payload(request, hotspot):
    return {
        "id": hotspot.id,
        "hotspot_id": hotspot.hotspot_id,
        "type": hotspot.type,
        "label": hotspot.label,
        "tooltip_text": hotspot.tooltip_text or "",
        "yaw": hotspot.yaw,
        "pitch": hotspot.pitch,

        # Compatibilité ancien JS
        "target_scene": hotspot.target_scene_id,

        # Nouveau format plus clair
        "target_scene_id": hotspot.target_scene_id,
        "target_scene_scene_id": (
            hotspot.target_scene.scene_id
            if getattr(hotspot, "target_scene", None)
            else None
        ),

        "title": hotspot.title or "",
        "description": hotspot.description or "",
        "selected_icon": hotspot.selected_icon or "default",
        "ad_image_url": _safe_file_url(request, getattr(hotspot, "ad_image", None)),
        "media_file_url": _safe_file_url(request, getattr(hotspot, "media_file", None)),
        "poster_image_url": _safe_file_url(request, getattr(hotspot, "poster_image", None)),
        "payload": hotspot.payload or {},
        "is_ai_generated": bool(getattr(hotspot, "is_ai_generated", False)),
    }


def _build_prefetch_map(request, scenes):
    """
    Prépare les scènes voisines pour le préchargement intelligent.
    Le JS pourra précharger la scène suivante/précédente sans recalculer.
    """
    prefetch_map = {}

    for index, scene in enumerate(scenes):
        previous_scene = scenes[index - 1] if index - 1 >= 0 else None
        next_scene = scenes[index + 1] if index + 1 < len(scenes) else None

        neighbors = []

        for neighbor in [next_scene, previous_scene]:
            if not neighbor:
                continue

            neighbors.append({
                "id": neighbor.id,
                "scene_id": neighbor.scene_id,
                "title": neighbor.title,
                "order": neighbor.order,
                "is_public": bool(getattr(neighbor, "is_public", True)),
                "assets_status": _status_value(neighbor, "assets_status"),
                "tiles_status": _status_value(neighbor, "tiles_status"),
                "assets": _scene_assets_payload(request, neighbor),
                "tiles": _scene_tiles_payload(request, neighbor),
            })

        prefetch_map[scene.id] = {
            "current_scene_id": scene.scene_id,
            "current_scene_is_public": bool(getattr(scene, "is_public", True)),
            "next_scene_id": next_scene.scene_id if next_scene else None,
            "previous_scene_id": previous_scene.scene_id if previous_scene else None,
            "neighbors": neighbors,
        }

    return prefetch_map


def _serialize_scene_payload(request, scene, include_hotspots=True, prefetch=None):
    assets = _scene_assets_payload(request, scene)
    tiles = _scene_tiles_payload(request, scene)
    statuses = _scene_statuses_payload(scene)

    return {
        "id": scene.id,
        "scene_id": scene.scene_id,
        "title": scene.title,
        "order": scene.order,
        "status": getattr(scene, "status", ""),
        "is_public": bool(getattr(scene, "is_public", True)),

        # Ancien format gardé pour ne pas casser le JS existant,
        # mais avec une vraie sélection progressive.
        "image_360_url": assets["viewer_desktop"],
        "image_360_mobile_url": assets["viewer_mobile"],
        "image_360_preview_url": assets["light"],
        "thumbnail_url": assets["thumbnail"] or assets["light"],

        # Nouveau format recommandé
        "assets": assets,
        "tiles": tiles,
        "statuses": statuses,

        "assets_status": statuses["assets"],
        "tiles_status": statuses["tiles"],
        "ai_analysis_status": statuses["ai_analysis"],
        "ai_hotspots_status": statuses["ai_hotspots"],

        "assets_ready": _is_status_ready(statuses["assets"]),
        "tiles_ready": tiles["ready"],

        "yaw_default": scene.yaw_default if scene.yaw_default is not None else 0,
        "pitch_default": scene.pitch_default if scene.pitch_default is not None else 0,
        "hfov_default": scene.hfov_default if scene.hfov_default is not None else 100,

        "ai_analysis": getattr(scene, "ai_analysis", {}) or {},
        "ai_hotspot_suggestions": getattr(scene, "ai_hotspot_suggestions", []) or [],

        "prefetch": prefetch or getattr(scene, "prefetch_manifest", {}) or {},

        "hotspots": [
            _serialize_hotspot_payload(request, hotspot)
            for hotspot in scene.hotspots.all()
        ] if include_hotspots else [],
    }

def _get_tour_with_scenes_queryset():
    return Tour.objects.select_related("place", "organization").prefetch_related(
        Prefetch(
            "scenes",
            queryset=Scene360.objects.order_by("order", "id").prefetch_related(
                Prefetch(
                    "hotspots",
                    queryset=Hotspot.objects.select_related("target_scene").order_by("id"),
                )
            ),
        )
    )


# =============================================================================
# STUDIO HOME
# =============================================================================

@login_required
def studio_home_view(request):
    organization, place, tour = _get_or_create_default_workspace(request.user)
    return redirect("tour-builder", organization_slug=organization.slug, tour_id=tour.id)


# =============================================================================
# TOUR LIST
# =============================================================================

def build_tours_queryset(request, organization):
    tours = (
        Tour.objects.filter(organization=organization)
        .select_related("place")
        .order_by("-created_at")
    )

    q = request.GET.get("q", "").strip()
    place_id = request.GET.get("place", "").strip()
    status_filter = request.GET.get("status", "").strip()
    featured = request.GET.get("featured", "").strip()
    has_video = request.GET.get("has_video", "").strip()
    min_price = request.GET.get("min_price", "").strip()
    max_price = request.GET.get("max_price", "").strip()

    if q:
        tours = tours.filter(
            Q(title__icontains=q)
            | Q(slug__icontains=q)
            | Q(place__name__icontains=q)
            | Q(place__city__icontains=q)
            | Q(place__country__icontains=q)
            | Q(location__icontains=q)
            | Q(guide_name__icontains=q)
        )

    if place_id:
        tours = tours.filter(place_id=place_id)

    if status_filter:
        tours = tours.filter(status=status_filter)

    if featured == "1":
        tours = tours.filter(is_featured=True)
    elif featured == "0":
        tours = tours.filter(is_featured=False)

    if has_video == "1":
        tours = tours.exclude(video_tour="").exclude(video_tour__isnull=True)
    elif has_video == "0":
        tours = tours.filter(Q(video_tour="") | Q(video_tour__isnull=True))

    if min_price:
        tours = tours.filter(price__gte=min_price)

    if max_price:
        tours = tours.filter(price__lte=max_price)

    return tours


@login_required
def tour_list_view(request, organization_slug):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return render(request, "403.html", status=403)

    tours_qs = build_tours_queryset(request, organization)
    paginator = Paginator(tours_qs, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    places = Place.objects.filter(organization=organization).order_by("name")

    context = {
        "page_obj": page_obj,
        "tours": page_obj.object_list,
        "places": places,
        "q": request.GET.get("q", "").strip(),
        "selected_place_id": request.GET.get("place", "").strip(),
        "selected_status": request.GET.get("status", "").strip(),
        "selected_featured": request.GET.get("featured", "").strip(),
        "selected_has_video": request.GET.get("has_video", "").strip(),
        "selected_min_price": request.GET.get("min_price", "").strip(),
        "selected_max_price": request.GET.get("max_price", "").strip(),
        "total_count": Tour.objects.filter(organization=organization).count(),
        "published_count": Tour.objects.filter(
            organization=organization,
            status=Tour.Status.PUBLISHED,
        ).count(),
        "draft_count": Tour.objects.filter(
            organization=organization,
            status=Tour.Status.DRAFT,
        ).count(),
        "inactive_count": Tour.objects.filter(
            organization=organization,
            status=Tour.Status.INACTIVE,
        ).count(),
        "current_organization": organization,
        "google_maps_api_key": getattr(settings, "GOOGLE_MAPS_API_KEY", ""),
    }

    return render(request, "dashboard/tours/list.html", context)


@login_required
@require_GET
def tour_list_partial_view(request, organization_slug):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return JsonResponse({"success": False, "message": "Unauthorized."}, status=403)

    tours_qs = build_tours_queryset(request, organization)
    paginator = Paginator(tours_qs, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    html = render_to_string(
        "dashboard/tours/partials/tour_list_content.html",
        {
            "page_obj": page_obj,
            "tours": page_obj.object_list,
            "current_organization": organization,
            "q": request.GET.get("q", "").strip(),
            "selected_place_id": request.GET.get("place", "").strip(),
            "selected_status": request.GET.get("status", "").strip(),
            "selected_featured": request.GET.get("featured", "").strip(),
            "selected_has_video": request.GET.get("has_video", "").strip(),
            "selected_min_price": request.GET.get("min_price", "").strip(),
            "selected_max_price": request.GET.get("max_price", "").strip(),
        },
        request=request,
    )

    return JsonResponse({"success": True, "html": html})


# =============================================================================
# TOUR CRUD
# =============================================================================

@login_required
def tour_create_view(request, organization_slug):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return render(request, "403.html", status=403)

    if request.method == "POST":
        form = TourForm(request.POST, request.FILES, organization=organization)

        if form.is_valid():
            tour = form.save(commit=False)
            tour.organization = organization

            if not tour.slug:
                tour.slug = generate_unique_tour_slug(tour.title)

            tour.save()

            if is_ajax(request):
                row_html = render_to_string(
                    "dashboard/tours/partials/tour_table_row.html",
                    {"tour": tour, "current_organization": organization},
                    request=request,
                )
                card_html = render_to_string(
                    "dashboard/tours/partials/tour_card_single.html",
                    {"tour": tour, "current_organization": organization},
                    request=request,
                )

                return JsonResponse({
                    "success": True,
                    "message": "Tour created successfully.",
                    "row_html": row_html,
                    "card_html": card_html,
                    "tour_id": tour.id,
                })

            messages.success(request, "Tour created successfully.")
            return redirect("dashboard-tours-list", organization_slug=organization.slug)
    else:
        form = TourForm(organization=organization)

    context = {
        "form": form,
        "page_mode": "create",
        "current_organization": organization,
    }

    if is_ajax(request):
        html = render_to_string(
            "dashboard/tours/partials/tour_form_modal.html",
            context,
            request=request,
        )
        return JsonResponse({"html": html})

    return render(request, "dashboard/tours/form.html", context)


@login_required
def tour_edit_view(request, organization_slug, tour_id):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return render(request, "403.html", status=403)

    tour = get_object_or_404(Tour, id=tour_id, organization=organization)

    if request.method == "POST":
        form = TourForm(
            request.POST,
            request.FILES,
            instance=tour,
            organization=organization,
        )

        if form.is_valid():
            updated_tour = form.save(commit=False)

            if not updated_tour.slug:
                updated_tour.slug = generate_unique_tour_slug(updated_tour.title)

            updated_tour.save()

            if is_ajax(request):
                row_html = render_to_string(
                    "dashboard/tours/partials/tour_table_row.html",
                    {"tour": updated_tour, "current_organization": organization},
                    request=request,
                )
                card_html = render_to_string(
                    "dashboard/tours/partials/tour_card_single.html",
                    {"tour": updated_tour, "current_organization": organization},
                    request=request,
                )

                return JsonResponse({
                    "success": True,
                    "message": "Tour updated successfully.",
                    "tour_id": updated_tour.id,
                    "row_html": row_html,
                    "card_html": card_html,
                })

            messages.success(request, "Tour updated successfully.")
            return redirect("dashboard-tours-list", organization_slug=organization.slug)
    else:
        form = TourForm(instance=tour, organization=organization)

    context = {
        "form": form,
        "tour": tour,
        "page_mode": "edit",
        "current_organization": organization,
    }

    if is_ajax(request):
        html = render_to_string(
            "dashboard/tours/partials/tour_form_modal.html",
            context,
            request=request,
        )
        return JsonResponse({"html": html})

    return render(request, "dashboard/tours/form.html", context)


@login_required
def tour_delete_view(request, organization_slug, tour_id):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        if is_ajax(request):
            return JsonResponse({"success": False, "message": "Unauthorized."}, status=403)
        return render(request, "403.html", status=403)

    tour = get_object_or_404(Tour, id=tour_id, organization=organization)

    if request.method == "POST":
        deleted_id = tour.id
        tour.delete()

        if is_ajax(request):
            return JsonResponse({
                "success": True,
                "message": "Tour deleted successfully.",
                "tour_id": deleted_id,
            })

        messages.success(request, "Tour deleted successfully.")
        return redirect("dashboard-tours-list", organization_slug=organization.slug)

    return render(
        request,
        "dashboard/tours/delete.html",
        {
            "tour": tour,
            "current_organization": organization,
        },
    )


@login_required
@require_POST
def tour_bulk_delete_view(request, organization_slug):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return JsonResponse({"success": False, "message": "Unauthorized."}, status=403)

    ids = request.POST.getlist("tour_ids[]")
    if not ids:
        return JsonResponse({"success": False, "message": "No tours selected."}, status=400)

    tours = Tour.objects.filter(organization=organization, id__in=ids)
    deleted_ids = list(tours.values_list("id", flat=True))
    deleted_count = tours.count()
    tours.delete()

    return JsonResponse({
        "success": True,
        "message": f"{deleted_count} tour(s) deleted successfully.",
        "deleted_ids": deleted_ids,
    })


@login_required
@require_POST
def tour_duplicate_view(request, organization_slug, tour_id):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return JsonResponse({"success": False, "message": "Unauthorized."}, status=403)

    source_tour = get_object_or_404(Tour, id=tour_id, organization=organization)

    duplicated = Tour.objects.get(pk=source_tour.pk)
    duplicated.pk = None
    duplicated.id = None
    duplicated.title = f"{source_tour.title} Copy"
    duplicated.slug = generate_unique_tour_slug(f"{source_tour.title}-copy")
    duplicated.status = Tour.Status.DRAFT
    duplicated.view_count = 0
    duplicated.rating = None
    duplicated.manifest = deepcopy(source_tour.manifest)
    duplicated.published_at = None
    duplicated.publish_email_status = None
    duplicated.publish_email_error = ""
    duplicated.save()

    row_html = render_to_string(
        "dashboard/tours/partials/tour_table_row.html",
        {"tour": duplicated, "current_organization": organization},
        request=request,
    )
    card_html = render_to_string(
        "dashboard/tours/partials/tour_card_single.html",
        {"tour": duplicated, "current_organization": organization},
        request=request,
    )

    return JsonResponse({
        "success": True,
        "message": "Tour duplicated successfully.",
        "row_html": row_html,
        "card_html": card_html,
        "tour_id": duplicated.id,
    })


@login_required
@require_POST
def tour_toggle_status_view(request, organization_slug, tour_id):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return JsonResponse({"success": False, "message": "Unauthorized."}, status=403)

    tour = get_object_or_404(Tour, id=tour_id, organization=organization)
    next_status = request.POST.get("status", "").strip()

    allowed_statuses = {
        Tour.Status.DRAFT,
        Tour.Status.PUBLISHED,
        Tour.Status.INACTIVE,
    }

    if next_status not in allowed_statuses:
        return JsonResponse({"success": False, "message": "Invalid status."}, status=400)

    tour.status = next_status
    tour.save(update_fields=["status", "updated_at"])

    row_html = render_to_string(
        "dashboard/tours/partials/tour_table_row.html",
        {"tour": tour, "current_organization": organization},
        request=request,
    )
    card_html = render_to_string(
        "dashboard/tours/partials/tour_card_single.html",
        {"tour": tour, "current_organization": organization},
        request=request,
    )

    return JsonResponse({
        "success": True,
        "message": f"Tour marked as {tour.get_status_display()}.",
        "tour_id": tour.id,
        "row_html": row_html,
        "card_html": card_html,
        "is_published": tour.status == Tour.Status.PUBLISHED,
    })


@login_required
@require_POST
def tour_toggle_featured_view(request, organization_slug, tour_id):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return JsonResponse({"success": False, "message": "Unauthorized."}, status=403)

    tour = get_object_or_404(Tour, id=tour_id, organization=organization)
    tour.is_featured = not tour.is_featured
    tour.save(update_fields=["is_featured", "updated_at"])

    row_html = render_to_string(
        "dashboard/tours/partials/tour_table_row.html",
        {"tour": tour, "current_organization": organization},
        request=request,
    )
    card_html = render_to_string(
        "dashboard/tours/partials/tour_card_single.html",
        {"tour": tour, "current_organization": organization},
        request=request,
    )

    return JsonResponse({
        "success": True,
        "message": "Featured status updated.",
        "tour_id": tour.id,
        "row_html": row_html,
        "card_html": card_html,
        "is_featured": tour.is_featured,
    })


@login_required
@require_POST
def update_tour_ajax_view(request, organization_slug, tour_id):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return JsonResponse({"detail": "Forbidden"}, status=403)

    tour = get_object_or_404(Tour, id=tour_id, organization=organization)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON payload."}, status=400)

    title = (payload.get("title") or "").strip()
    if not title:
        return JsonResponse({"detail": "Title is required."}, status=400)

    tour.title = title
    tour.save(update_fields=["title", "updated_at"])

    return JsonResponse({
        "success": True,
        "tour": {
            "id": tour.id,
            "title": tour.title,
        },
    })


# =============================================================================
# BUILDER + PREVIEW
# =============================================================================

@login_required
def tour_builder_view(request, organization_slug, tour_id):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return render(request, "403.html", status=403)

    tour = get_object_or_404(
        _get_tour_with_scenes_queryset(),
        id=tour_id,
        organization=organization,
    )

    scenes = list(tour.scenes.all().order_by("order", "id"))
    prefetch_map = _build_prefetch_map(request, scenes)

    scenes_payload = [
        _serialize_scene_payload(
            request=request,
            scene=scene,
            include_hotspots=True,
            prefetch=prefetch_map.get(scene.id),
        )
        for scene in scenes
    ]

    context = {
    "tour": tour,
    "scenes": scenes,
    "scenes_json": scenes_payload,
    "current_organization": organization,
    "current_place": tour.place,
    "google_maps_api_key": getattr(settings, "GOOGLE_MAPS_API_KEY", ""),

    # Utilisé dans builder.html :
    # pipelineStatusUrl: "{{ pipeline_status_url|default:'' }}"
    "pipeline_status_url": reverse(
        "dashboard-tour-scenes-pipeline-status-ajax",
        kwargs={
            "organization_slug": organization.slug,
            "tour_id": tour.id,
        },
    ),

    # Utilisé dans builder.html :
    # queueTourPrefetchUrl: "{{ queue_tour_prefetch_url|default:'' }}"
    "queue_tour_prefetch_url": reverse(
        "dashboard-queue-tour-prefetch-ajax",
        kwargs={
            "organization_slug": organization.slug,
            "tour_id": tour.id,
        },
    ),
}

    return render(request, "dashboard/tours/builder.html", context)




import hashlib
import json

from django.core.cache import cache
from django.shortcuts import get_object_or_404, render


def _safe_dt_version(value):
    try:
        return int(value.timestamp()) if value else 0
    except Exception:
        return 0


def _safe_file_name(file_field):
    try:
        return file_field.name or ""
    except Exception:
        return ""


def _build_preview_payload_version(tour, scenes):
    parts = []

    tour_updated_value = getattr(tour, "updated_at", None) or getattr(tour, "created_at", None)
    parts.append(f"tour:{tour.id}:{_safe_dt_version(tour_updated_value)}")

    for scene in scenes:
        scene_updated_value = getattr(scene, "updated_at", None) or getattr(scene, "created_at", None)

        scene_part = {
            "id": scene.id,
            "scene_id": str(getattr(scene, "scene_id", "")),
            "updated": _safe_dt_version(scene_updated_value),
            "order": getattr(scene, "order", 0),
            "is_public": bool(getattr(scene, "is_public", True)),
            "status": getattr(scene, "status", ""),
            "assets_status": getattr(scene, "assets_status", ""),
            "tiles_status": getattr(scene, "tiles_status", ""),
            "image_360": _safe_file_name(getattr(scene, "image_360", None)),
            "image_360_mobile": _safe_file_name(getattr(scene, "image_360_mobile", None)),
            "image_360_preview": _safe_file_name(getattr(scene, "image_360_preview", None)),
            "image_360_original": _safe_file_name(getattr(scene, "image_360_original", None)),
            "thumbnail_image": _safe_file_name(getattr(scene, "thumbnail_image", None)),
            "tiles_manifest": getattr(scene, "tiles_manifest", {}) or {},
        }

        parts.append(json.dumps(scene_part, sort_keys=True, default=str))

        for hotspot in scene.hotspots.all():
            hotspot_updated_value = getattr(hotspot, "updated_at", None) or getattr(hotspot, "created_at", None)

            hotspot_part = {
                "id": hotspot.id,
                "hotspot_id": str(getattr(hotspot, "hotspot_id", "")),
                "updated": _safe_dt_version(hotspot_updated_value),
                "type": getattr(hotspot, "type", ""),
                "yaw": getattr(hotspot, "yaw", None),
                "pitch": getattr(hotspot, "pitch", None),
                "target_scene_id": getattr(hotspot, "target_scene_id", None),
                "selected_icon": getattr(hotspot, "selected_icon", ""),
                "payload": getattr(hotspot, "payload", {}) or {},
                "ad_image": _safe_file_name(getattr(hotspot, "ad_image", None)),
            }

            parts.append(json.dumps(hotspot_part, sort_keys=True, default=str))

    raw = "|".join(parts)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def tour_preview_view(request, organization_slug, tour_id):
    organization = _get_org_or_403(request, organization_slug, allow_public=True)

    if not organization:
        return render(request, "403.html", status=403)

    tour = get_object_or_404(
        _get_tour_with_scenes_queryset(),
        id=tour_id,
        organization=organization,
    )

    all_scenes = list(
        tour.scenes
        .all()
        .order_by("order", "id")
    )

    payload_version = _build_preview_payload_version(tour, all_scenes)

    cache_key = (
        f"tour_preview_payload:v6:"
        f"{request.get_host()}:"
        f"{organization.slug}:"
        f"{tour.id}:"
        f"{payload_version}"
    )

    cached_payload = cache.get(cache_key)

    if cached_payload is not None:
        return render(
            request,
            "dashboard/tours/preview.html",
            {
                "tour": tour,
                "current_organization": organization,
                "scenes_json": cached_payload["scenes_json"],
                "scene_list_json": cached_payload["scene_list_json"],
            },
        )

    public_list_scenes = [
        scene for scene in all_scenes
        if bool(getattr(scene, "is_public", True))
    ]

    prefetch_map = _build_prefetch_map(request, all_scenes)

    scenes_payload = [
        _serialize_scene_payload(
            request=request,
            scene=scene,
            include_hotspots=True,
            prefetch=prefetch_map.get(scene.id),
        )
        for scene in all_scenes
    ]

    scene_list_payload = [
        _serialize_scene_payload(
            request=request,
            scene=scene,
            include_hotspots=False,
            prefetch=prefetch_map.get(scene.id),
        )
        for scene in public_list_scenes
    ]

    payload = {
        "scenes_json": scenes_payload,
        "scene_list_json": scene_list_payload,
    }

    cache.set(cache_key, payload, 60 * 3)

    return render(
        request,
        "dashboard/tours/preview.html",
        {
            "tour": tour,
            "current_organization": organization,
            "scenes_json": scenes_payload,
            "scene_list_json": scene_list_payload,
        },
    )

# =============================================================================
# SCENES AJAX
# =============================================================================

@login_required
@require_POST
def upload_scenes_ajax_view(request, organization_slug, tour_id):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return JsonResponse({"detail": "Forbidden"}, status=403)

    tour = get_object_or_404(Tour, id=tour_id, organization=organization)
    files = request.FILES.getlist("panos")

    if not files:
        return JsonResponse({"detail": "No files uploaded."}, status=400)

    created_scenes = handle_uploaded_scenes(
        tour=tour,
        files=files,
        is_public=True,
    )

    build_tour_manifest(tour)

    created_ids = [scene.id for scene in created_scenes]

    scenes = list(
        Scene360.objects.filter(id__in=created_ids, organization=organization)
        .prefetch_related(
            Prefetch(
                "hotspots",
                queryset=Hotspot.objects.select_related("target_scene").order_by("id"),
            )
        )
        .order_by("order", "id")
    )

    data = [
        _serialize_scene_payload(
            request=request,
            scene=scene,
            include_hotspots=False,
            prefetch=None,
        )
        for scene in scenes
    ]

    return JsonResponse({
        "success": True,
        "message": "Scenes uploaded. Processing started.",
        "scenes": data,
    }, status=201)



@login_required
@require_POST
def update_scene_ajax_view(request, organization_slug, scene_id):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return JsonResponse({"detail": "Forbidden"}, status=403)

    scene = get_object_or_404(
        Scene360.objects.select_related("tour").prefetch_related(
            Prefetch(
                "hotspots",
                queryset=Hotspot.objects.select_related("target_scene").order_by("id"),
            )
        ),
        id=scene_id,
        organization=organization,
    )

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON payload."}, status=400)

    if "title" in payload:
        title = (payload.get("title") or "").strip()
        if title:
            scene.title = title

    if "yaw_default" in payload:
        scene.yaw_default = payload.get("yaw_default", scene.yaw_default)

    if "pitch_default" in payload:
        scene.pitch_default = payload.get("pitch_default", scene.pitch_default)

    if "hfov_default" in payload:
        scene.hfov_default = payload.get("hfov_default", scene.hfov_default)

    if payload.get("order") is not None:
        scene.order = payload["order"]

    if payload.get("status") in {
        Scene360.Status.DRAFT,
        Scene360.Status.PUBLISHED,
        Scene360.Status.INACTIVE,
    }:
        scene.status = payload["status"]

    # Nouveau : sauvegarder l'affichage dans le preview
    if "is_public" in payload:
        scene.is_public = _payload_bool(
            payload.get("is_public"),
            default=bool(getattr(scene, "is_public", True)),
        )

    scene.save()
    build_tour_manifest(scene.tour)

    scene.refresh_from_db()

    return JsonResponse({
        "success": True,
        "scene": _serialize_scene_payload(
            request=request,
            scene=scene,
            include_hotspots=True,
            prefetch=None,
        ),
    })

@login_required
@require_POST
def reorder_scenes_ajax_view(request, organization_slug, tour_id):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return JsonResponse({"detail": "Forbidden"}, status=403)

    tour = get_object_or_404(Tour, id=tour_id, organization=organization)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON payload."}, status=400)

    ordered_scene_ids = payload.get("scene_ids", [])

    if not isinstance(ordered_scene_ids, list):
        return JsonResponse({"detail": "scene_ids must be a list."}, status=400)

    reorder_scenes_for_tour(tour, ordered_scene_ids)
    build_tour_manifest(tour)

    scenes = list(
        Scene360.objects.filter(tour=tour, organization=organization)
        .prefetch_related(
            Prefetch(
                "hotspots",
                queryset=Hotspot.objects.select_related("target_scene").order_by("id"),
            )
        )
        .order_by("order", "id")
    )

    prefetch_map = _build_prefetch_map(request, scenes)

    return JsonResponse({
        "success": True,
        "scenes": [
            _serialize_scene_payload(
                request=request,
                scene=scene,
                include_hotspots=True,
                prefetch=prefetch_map.get(scene.id),
            )
            for scene in scenes
        ],
    })


# =============================================================================
# PIPELINE STATUS AJAX
# =============================================================================

@login_required
@require_GET
def scene_pipeline_status_ajax_view(request, organization_slug, scene_id):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return JsonResponse({"detail": "Forbidden"}, status=403)

    scene = get_object_or_404(
        Scene360.objects.select_related("tour").prefetch_related(
            Prefetch(
                "hotspots",
                queryset=Hotspot.objects.select_related("target_scene").order_by("id"),
            )
        ),
        id=scene_id,
        organization=organization,
    )

    return JsonResponse({
        "success": True,
        "scene": _serialize_scene_payload(
            request=request,
            scene=scene,
            include_hotspots=True,
            prefetch=None,
        ),
    })


@login_required
@require_GET
def tour_scenes_pipeline_status_ajax_view(request, organization_slug, tour_id):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return JsonResponse({"detail": "Forbidden"}, status=403)

    tour = get_object_or_404(Tour, id=tour_id, organization=organization)

    scenes = list(
        Scene360.objects.filter(tour=tour, organization=organization)
        .prefetch_related(
            Prefetch(
                "hotspots",
                queryset=Hotspot.objects.select_related("target_scene").order_by("id"),
            )
        )
        .order_by("order", "id")
    )

    prefetch_map = _build_prefetch_map(request, scenes)

    scenes_payload = [
        _serialize_scene_payload(
            request=request,
            scene=scene,
            include_hotspots=True,
            prefetch=prefetch_map.get(scene.id),
        )
        for scene in scenes
    ]

    all_assets_ready = all(scene.get("assets_ready") for scene in scenes_payload)

    all_tiles_ready = all(
        scene.get("tiles_ready") or not scene.get("tiles", {}).get("enabled")
        for scene in scenes_payload
    )

    return JsonResponse({
        "success": True,
        "all_assets_ready": all_assets_ready,
        "all_tiles_ready": all_tiles_ready,
        "scenes": scenes_payload,
    })


@login_required
@require_POST
def queue_scene_pipeline_ajax_view(request, organization_slug, scene_id):
    """
    Relance manuellement le pipeline Celery d'une scène :
    assets + tiles + IA + hotspots + prefetch.
    """
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return JsonResponse({"detail": "Forbidden"}, status=403)

    scene = get_object_or_404(
        Scene360.objects.select_related("tour"),
        id=scene_id,
        organization=organization,
    )

    from apps.tours.tasks import run_scene_pipeline_task

    run_scene_pipeline_task.delay(scene.id)

    return JsonResponse({
        "success": True,
        "message": "Scene pipeline queued.",
        "scene_id": scene.id,
    })


@login_required
@require_POST
def queue_tour_prefetch_ajax_view(request, organization_slug, tour_id):
    """
    Relance manuellement le prefetch manifest du tour.
    """
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return JsonResponse({"detail": "Forbidden"}, status=403)

    tour = get_object_or_404(Tour, id=tour_id, organization=organization)

    from apps.tours.tasks import build_tour_prefetch_manifest_task

    build_tour_prefetch_manifest_task.delay(tour.id)

    return JsonResponse({
        "success": True,
        "message": "Tour prefetch manifest queued.",
        "tour_id": tour.id,
    })


# =============================================================================
# HOTSPOTS AJAX
# =============================================================================

@login_required
@require_POST
def create_hotspot_ajax_view(request, organization_slug, scene_id):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return JsonResponse({"detail": "Forbidden"}, status=403)

    scene = get_object_or_404(
        Scene360.objects.select_related("tour"),
        id=scene_id,
        organization=organization,
    )

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON payload."}, status=400)

    hotspot_type = payload.get("type", Hotspot.Type.INFO)
    label = payload.get("label", "Hotspot")
    yaw = float(payload.get("yaw", 0))
    pitch = float(payload.get("pitch", 0))
    tooltip_text = payload.get("tooltip_text", "")
    title = payload.get("title", "")
    description = payload.get("description", "")
    selected_icon = payload.get("selected_icon", "")
    target_scene_id = payload.get("target_scene")
    extra_payload = payload.get("payload", {})

    target_scene = None

    if target_scene_id:
        target_scene = Scene360.objects.filter(
            id=target_scene_id,
            organization=organization,
            tour=scene.tour,
        ).first()

    hotspot = create_hotspot(
        scene,
        hotspot_type=hotspot_type,
        label=label,
        yaw=yaw,
        pitch=pitch,
        target_scene=target_scene,
        tooltip_text=tooltip_text,
        title=title,
        description=description,
        selected_icon=selected_icon,
        payload=extra_payload,
    )

    build_tour_manifest(scene.tour)

    return JsonResponse({
        "success": True,
        "hotspot": _serialize_hotspot_payload(request, hotspot),
    }, status=201)


@login_required
@require_POST
def update_hotspot_ajax_view(request, organization_slug, hotspot_id):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return JsonResponse({"detail": "Forbidden"}, status=403)

    hotspot = get_object_or_404(
        Hotspot.objects.select_related("scene", "scene__tour", "target_scene"),
        id=hotspot_id,
        organization=organization,
    )

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON payload."}, status=400)

    hotspot_type = payload.get("type", hotspot.type)
    label = payload.get("label", hotspot.label)
    yaw = float(payload.get("yaw", hotspot.yaw))
    pitch = float(payload.get("pitch", hotspot.pitch))
    tooltip_text = payload.get("tooltip_text", hotspot.tooltip_text or "")
    title = payload.get("title", hotspot.title or "")
    description = payload.get("description", hotspot.description or "")
    selected_icon = payload.get("selected_icon", hotspot.selected_icon or "")
    extra_payload = payload.get("payload", hotspot.payload or {})
    target_scene_id = payload.get("target_scene")

    target_scene = None

    if target_scene_id:
        target_scene = Scene360.objects.filter(
            id=target_scene_id,
            organization=organization,
            tour=hotspot.scene.tour,
        ).first()

    hotspot = update_hotspot(
        hotspot,
        hotspot_type=hotspot_type,
        label=label,
        yaw=yaw,
        pitch=pitch,
        target_scene=target_scene,
        tooltip_text=tooltip_text,
        title=title,
        description=description,
        selected_icon=selected_icon,
        payload=extra_payload,
    )

    build_tour_manifest(hotspot.scene.tour)

    return JsonResponse({
        "success": True,
        "hotspot": _serialize_hotspot_payload(request, hotspot),
    })


@login_required
@require_POST
def upload_hotspot_image_ajax_view(request, organization_slug, hotspot_id):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return JsonResponse({"detail": "Forbidden"}, status=403)

    hotspot = get_object_or_404(
        Hotspot.objects.select_related("scene", "scene__tour"),
        id=hotspot_id,
        organization=organization,
    )

    image_file = request.FILES.get("image")

    if not image_file:
        return JsonResponse({"detail": "No image uploaded."}, status=400)

    hotspot.ad_image = image_file
    hotspot.save(update_fields=["ad_image", "updated_at"])

    build_tour_manifest(hotspot.scene.tour)

    return JsonResponse({
        "success": True,
        "hotspot": _serialize_hotspot_payload(request, hotspot),
    })


@login_required
@require_POST
def upload_hotspot_media_ajax_view(request, organization_slug, hotspot_id):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return JsonResponse({"detail": "Forbidden"}, status=403)

    hotspot = get_object_or_404(
        Hotspot.objects.select_related("scene", "scene__tour"),
        id=hotspot_id,
        organization=organization,
    )

    media_file = request.FILES.get("media")
    poster_file = request.FILES.get("poster")
    if not media_file and not poster_file:
        return JsonResponse({"detail": "No media uploaded."}, status=400)

    allowed_pdf = {"application/pdf"}
    allowed_video = {"video/mp4", "video/webm", "video/quicktime", "application/octet-stream"}

    if media_file:
        content_type = (getattr(media_file, "content_type", "") or "").lower()
        max_size = 25 * 1024 * 1024 if hotspot.type == Hotspot.Type.PDF else 250 * 1024 * 1024
        if media_file.size > max_size:
            return JsonResponse({"detail": "File too large."}, status=400)
        if hotspot.type == Hotspot.Type.PDF and content_type not in allowed_pdf and not media_file.name.lower().endswith(".pdf"):
            return JsonResponse({"detail": "Only PDF files are allowed."}, status=400)
        if hotspot.type == Hotspot.Type.VIDEO and content_type not in allowed_video and not media_file.name.lower().endswith((".mp4", ".webm", ".mov")):
            return JsonResponse({"detail": "Unsupported video format."}, status=400)
        hotspot.media_file = media_file

    if poster_file:
        if poster_file.size > 8 * 1024 * 1024:
            return JsonResponse({"detail": "Poster image too large."}, status=400)
        hotspot.poster_image = poster_file

    hotspot.save(update_fields=[field for field in ["media_file" if media_file else None, "poster_image" if poster_file else None, "updated_at"] if field])
    content = dict((hotspot.payload or {}).get("content") or {})
    if hotspot.media_file:
        content["document_url" if hotspot.type == Hotspot.Type.PDF else "video_url"] = request.build_absolute_uri(hotspot.media_file.url)
    if hotspot.poster_image:
        content["poster_url"] = request.build_absolute_uri(hotspot.poster_image.url)
    hotspot.payload = {**(hotspot.payload or {}), "content": content}
    hotspot.save(update_fields=["payload", "updated_at"])
    build_tour_manifest(hotspot.scene.tour)
    return JsonResponse({"success": True, "hotspot": _serialize_hotspot_payload(request, hotspot)})


@login_required
@require_POST
def delete_hotspot_ajax_view(request, organization_slug, hotspot_id):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return JsonResponse({"detail": "Forbidden"}, status=403)

    hotspot = get_object_or_404(
        Hotspot.objects.select_related("scene", "scene__tour"),
        id=hotspot_id,
        organization=organization,
    )

    tour = hotspot.scene.tour
    hotspot.delete()

    build_tour_manifest(tour)

    return JsonResponse({
        "success": True,
        "deleted_hotspot_id": hotspot_id,
    })