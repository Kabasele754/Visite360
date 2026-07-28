import json
import mimetypes
import re
from copy import deepcopy
from pathlib import Path
from urllib.parse import quote

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Prefetch
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from apps.organizations.models import Organization, OrganizationMember
from apps.organizations.selectors import get_user_membership
from apps.places.models import Place
from apps.vendors.models import AppointmentType, Product
from apps.tours.forms import TourForm
from django.core.cache import cache

from .models import (
    Tour, Scene360, Hotspot, SceneVisualQuality, SceneObjectCandidate,
    TourArchitectureRun, SceneLinkProposal,
)
from .seo import build_tour_preview_seo
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
    payload = deepcopy(hotspot.payload or {})
    raw_media_url = _safe_file_url(request, getattr(hotspot, "media_file", None))
    document_stream_url = ""
    document_size = None
    if hotspot.type == Hotspot.Type.PDF and getattr(hotspot, "media_file", None):
        document_stream_url = request.build_absolute_uri(
            reverse(
                "tour-hotspot-pdf-public",
                kwargs={
                    "organization_slug": hotspot.organization.slug,
                    "tour_id": hotspot.scene.tour_id,
                    "hotspot_id": hotspot.id,
                },
            )
        )
        try:
            document_size = hotspot.media_file.size
        except (OSError, ValueError, AttributeError):
            document_size = None
        content = payload.setdefault("content", {})
        content["document_url"] = document_stream_url
        content["document_stream_url"] = document_stream_url
        content.setdefault("download_url", raw_media_url)
        content["document_size"] = document_size
        content["mobile_inline_max_bytes"] = int(
            getattr(settings, "PDF_MOBILE_INLINE_MAX_BYTES", 18 * 1024 * 1024)
        )

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
        "media_file_url": raw_media_url,
        "document_stream_url": document_stream_url,
        "document_size": document_size,
        "poster_image_url": _safe_file_url(request, getattr(hotspot, "poster_image", None)),
        "payload": payload,
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


def _preview_public_asset_url(request, value):
    """Return a browser-safe absolute URL for optional AI-generated assets."""
    if not value:
        return ""

    try:
        if hasattr(value, "url"):
            value = value.url
    except Exception:
        return ""

    value = str(value or "").strip()
    if not value:
        return ""

    if value.startswith(("https://", "http://")):
        return value
    if value.startswith("/"):
        return request.build_absolute_uri(value)

    # AI pipelines may store media-relative paths such as depth_maps/scene-1.png.
    if ".." in Path(value).parts:
        return ""
    return request.build_absolute_uri(f"{settings.MEDIA_URL.rstrip('/')}/{value.lstrip('/')}")


def _scene_spatial_payload(request, scene):
    analysis = getattr(scene, "ai_analysis", {}) or {}
    depth = analysis.get("depth") if isinstance(analysis.get("depth"), dict) else {}
    depth_url = (
        analysis.get("depth_map_url")
        or analysis.get("depth_url")
        or depth.get("url")
        or depth.get("depth_map_url")
        or getattr(scene, "depth_map_url", "")
    )
    depth_url = _preview_public_asset_url(request, depth_url)

    raw_confidence = (
        depth.get("confidence")
        or analysis.get("depth_confidence")
        or 0.0
    )
    try:
        depth_confidence = float(raw_confidence)
    except (TypeError, ValueError):
        depth_confidence = 0.0

    return {
        "depth_map_url": depth_url,
        "depth_ready": bool(depth_url),
        "depth_confidence": depth_confidence,
        "depth_source": str(
            depth.get("source")
            or analysis.get("depth_source")
            or ""
        ),
    }


def _serialize_scene_index_payload(request, scene):
    """
    Payload public compact pour la liste des scènes.

    Il contient uniquement ce qui est nécessaire pour afficher la navigation et
    construire la topologie légère. Les panoramas haute qualité, les contenus
    détaillés des hotspots et les analyses IA sont récupérés à la demande.
    """
    assets = _scene_assets_payload(request, scene)
    navigation_hotspots = []

    for hotspot in scene.hotspots.all():
        target_id = hotspot.target_scene_id
        if not target_id or hotspot.type not in {
            Hotspot.Type.NAVIGATE,
            Hotspot.Type.FLOOR,
            Hotspot.Type.DOOR,
        }:
            continue
        navigation_hotspots.append({
            "id": hotspot.id,
            "hotspot_id": hotspot.hotspot_id,
            "type": hotspot.type,
            "label": hotspot.label or "",
            "yaw": hotspot.yaw,
            "pitch": hotspot.pitch,
            "target_scene": target_id,
            "target_scene_id": target_id,
            "is_ai_generated": bool(getattr(hotspot, "is_ai_generated", False)),
        })

    return {
        "id": scene.id,
        "scene_id": scene.scene_id,
        "title": scene.title,
        "order": scene.order,
        "status": getattr(scene, "status", ""),
        "is_public": bool(getattr(scene, "is_public", True)),
        "thumbnail_url": assets["thumbnail"] or assets["light"],
        "image_360_preview_url": assets["light"],
        "assets": {
            "thumbnail": assets["thumbnail"] or assets["light"],
            "light": assets["light"],
        },
        "yaw_default": scene.yaw_default if scene.yaw_default is not None else 0,
        "pitch_default": scene.pitch_default if scene.pitch_default is not None else 0,
        "hfov_default": scene.hfov_default if scene.hfov_default is not None else 100,
        "camera_limits": {
            "enabled": bool(getattr(scene, "camera_limits_enabled", True)),
            "pitch_min": float(getattr(scene, "camera_pitch_min", -82.0)),
            "pitch_max": float(getattr(scene, "camera_pitch_max", 62.0)),
        },
        "spatial": _scene_spatial_payload(request, scene),
        "hotspots": navigation_hotspots,
        "details_loaded": False,
    }


def _serialize_scene_payload(request, scene, include_hotspots=True, prefetch=None, *, include_ai_metadata=True, include_prefetch=True):
    assets = _scene_assets_payload(request, scene)
    tiles = _scene_tiles_payload(request, scene)
    statuses = _scene_statuses_payload(scene)
    spatial = _scene_spatial_payload(request, scene)

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
        "camera_limits": {
            "enabled": bool(getattr(scene, "camera_limits_enabled", True)),
            "pitch_min": float(getattr(scene, "camera_pitch_min", -82.0)),
            "pitch_max": float(getattr(scene, "camera_pitch_max", 62.0)),
        },
        "tripod_logo": {
            "enabled": bool(getattr(scene, "tripod_logo_enabled", False)),
            "size": int(getattr(scene, "tripod_logo_size", 132) or 132),
            "yaw": float(getattr(scene, "tripod_logo_yaw", 0.0) or 0.0),
            "pitch": float(88.5 if getattr(scene, "tripod_logo_pitch", None) is None else scene.tripod_logo_pitch),
            "offset_x": int(getattr(scene, "tripod_logo_offset_x", 0) or 0),
            "offset_y": int(getattr(scene, "tripod_logo_offset_y", 0) or 0),
            "rotation": float(getattr(scene, "tripod_logo_rotation", 0.0) or 0.0),
            "tilt_x": float(getattr(scene, "tripod_logo_tilt_x", 0.0) or 0.0),
            "tilt_y": float(getattr(scene, "tripod_logo_tilt_y", 0.0) or 0.0),
            "radius": int(getattr(scene, "tripod_logo_radius", 900) or 900),
            "background_enabled": bool(getattr(scene, "tripod_logo_background_enabled", False)),
            "background_color": str(getattr(scene, "tripod_logo_background_color", "#FFFFFF") or "#FFFFFF"),
            "background_opacity": float(getattr(scene, "tripod_logo_background_opacity", 0.94)),
            "background_width": int(getattr(scene, "tripod_logo_background_width", 160) or 160),
            "background_height": int(getattr(scene, "tripod_logo_background_height", 160) or 160),
            "background_radius": int(getattr(scene, "tripod_logo_background_radius", 50)),
        },

        **({
            "ai_analysis": getattr(scene, "ai_analysis", {}) or {},
            "ai_hotspot_suggestions": getattr(scene, "ai_hotspot_suggestions", []) or [],
        } if include_ai_metadata else {}),
        "spatial": spatial,

        **({"prefetch": prefetch or getattr(scene, "prefetch_manifest", {}) or {}} if include_prefetch else {}),

        "hotspots": [
            _serialize_hotspot_payload(request, hotspot)
            for hotspot in scene.hotspots.all()
        ] if include_hotspots else [],
        "details_loaded": True,
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
            form.save_domain_profiles(tour)

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
            form.save_domain_profiles(updated_tour)

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
    latest_architect_run = TourArchitectureRun.objects.filter(tour=tour).order_by("-created_at").first()
    architect_stats = {
        "vision_ready": sum(1 for scene in scenes if scene.ai_analysis_status == "ready"),
        "objects": SceneObjectCandidate.objects.filter(scene__tour=tour).exclude(
            review_status=SceneObjectCandidate.ReviewStatus.HIDDEN
        ).count(),
        "anchors": SceneObjectCandidate.objects.filter(
            scene__tour=tour, is_navigation_anchor=True
        ).exclude(review_status=SceneObjectCandidate.ReviewStatus.HIDDEN).count(),
        "proposals": latest_architect_run.proposal_count if latest_architect_run else 0,
        "applied": latest_architect_run.applied_count if latest_architect_run else 0,
    }

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
        "latest_architect_run": latest_architect_run,
        "architect_stats": architect_stats,
        "architect_url": reverse(
            "dashboard-tour-architect",
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
            "camera_limits_enabled": bool(getattr(scene, "camera_limits_enabled", True)),
            "camera_pitch_min": float(getattr(scene, "camera_pitch_min", -82.0)),
            "camera_pitch_max": float(getattr(scene, "camera_pitch_max", 62.0)),
            "tripod_logo_enabled": bool(getattr(scene, "tripod_logo_enabled", False)),
            "tripod_logo_size": int(getattr(scene, "tripod_logo_size", 132) or 132),
            "tripod_logo_yaw": float(getattr(scene, "tripod_logo_yaw", 0.0) or 0.0),
            "tripod_logo_pitch": float(88.5 if getattr(scene, "tripod_logo_pitch", None) is None else scene.tripod_logo_pitch),
            "tripod_logo_offset_x": int(getattr(scene, "tripod_logo_offset_x", 0) or 0),
            "tripod_logo_offset_y": int(getattr(scene, "tripod_logo_offset_y", 0) or 0),
            "tripod_logo_rotation": float(getattr(scene, "tripod_logo_rotation", 0.0) or 0.0),
            "tripod_logo_tilt_x": float(getattr(scene, "tripod_logo_tilt_x", 0.0) or 0.0),
            "tripod_logo_tilt_y": float(getattr(scene, "tripod_logo_tilt_y", 0.0) or 0.0),
            "tripod_logo_radius": int(getattr(scene, "tripod_logo_radius", 900) or 900),
            "tripod_logo_background_enabled": bool(getattr(scene, "tripod_logo_background_enabled", False)),
            "tripod_logo_background_color": str(getattr(scene, "tripod_logo_background_color", "#FFFFFF") or "#FFFFFF"),
            "tripod_logo_background_opacity": float(getattr(scene, "tripod_logo_background_opacity", 0.94)),
            "tripod_logo_background_width": int(getattr(scene, "tripod_logo_background_width", 160) or 160),
            "tripod_logo_background_height": int(getattr(scene, "tripod_logo_background_height", 160) or 160),
            "tripod_logo_background_radius": int(getattr(scene, "tripod_logo_background_radius", 50)),
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


_PDF_RANGE_RE = re.compile(r"^bytes=(\d*)-(\d*)$")


def _pdf_stream(file_field, start: int, length: int, chunk_size: int):
    file_field.open("rb")
    stream = file_field.file
    stream.seek(start)
    remaining = length
    try:
        while remaining > 0:
            chunk = stream.read(min(chunk_size, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk
    finally:
        try:
            file_field.close()
        except Exception:
            pass


@require_http_methods(["GET", "HEAD"])
def public_hotspot_pdf_view(request, organization_slug, tour_id, hotspot_id):
    """Stream a hotspot PDF with HTTP Range support for iOS and Android.

    The endpoint deliberately keeps the document under the same application
    origin, validates public-tour access, returns an inline content disposition,
    and supports partial byte requests used by mobile PDF readers.
    """
    hotspot = get_object_or_404(
        Hotspot.objects.select_related("organization", "scene__tour"),
        pk=hotspot_id,
        organization__slug=organization_slug,
        scene__tour_id=tour_id,
        type=Hotspot.Type.PDF,
    )
    tour = hotspot.scene.tour
    organization = hotspot.organization
    can_manage = bool(
        request.user.is_authenticated
        and (
            request.user.is_superuser
            or get_user_membership(request.user, organization_slug)
        )
    )
    if not can_manage and (
        organization.status != Organization.Status.ACTIVE
        or tour.status != Tour.Status.PUBLISHED
        or not hotspot.scene.is_public
    ):
        return HttpResponse(status=404)
    if not hotspot.media_file:
        return HttpResponse(status=404)

    try:
        size = int(hotspot.media_file.size)
    except (OSError, ValueError, AttributeError):
        return HttpResponse(status=404)
    if size <= 0:
        return HttpResponse(status=404)

    start = 0
    end = size - 1
    status = 200
    range_header = request.headers.get("Range", "").strip()
    if range_header:
        match = _PDF_RANGE_RE.match(range_header)
        if not match:
            response = HttpResponse(status=416)
            response["Content-Range"] = f"bytes */{size}"
            return response
        first, last = match.groups()
        if first:
            start = int(first)
            end = int(last) if last else end
        elif last:
            suffix = int(last)
            if suffix <= 0:
                response = HttpResponse(status=416)
                response["Content-Range"] = f"bytes */{size}"
                return response
            start = max(0, size - suffix)
        if start >= size or start > end:
            response = HttpResponse(status=416)
            response["Content-Range"] = f"bytes */{size}"
            return response
        end = min(end, size - 1)
        status = 206

    length = end - start + 1
    filename = Path(hotspot.media_file.name).name or "document.pdf"
    content_type = mimetypes.guess_type(filename)[0] or "application/pdf"
    if content_type != "application/pdf":
        content_type = "application/pdf"

    if request.method == "HEAD":
        response = HttpResponse(status=status, content_type=content_type)
    else:
        response = StreamingHttpResponse(
            _pdf_stream(
                hotspot.media_file,
                start,
                length,
                int(getattr(settings, "PDF_STREAM_CHUNK_SIZE", 65536)),
            ),
            status=status,
            content_type=content_type,
        )
    response["Accept-Ranges"] = "bytes"
    response["Content-Length"] = str(length)
    if status == 206:
        response["Content-Range"] = f"bytes {start}-{end}/{size}"
    response["Content-Disposition"] = f"inline; filename*=UTF-8''{quote(filename)}"
    response["Cache-Control"] = f"private, max-age={int(getattr(settings, 'PDF_PUBLIC_CACHE_SECONDS', 900))}"
    response["X-Content-Type-Options"] = "nosniff"
    response["X-Frame-Options"] = "SAMEORIGIN"
    response["Cross-Origin-Resource-Policy"] = "same-origin"
    return response


def tour_preview_view(request, organization_slug, tour_id):
    organization = _get_org_or_403(request, organization_slug, allow_public=True)

    if not organization:
        return render(request, "403.html", status=403)

    tour = get_object_or_404(
        _get_tour_with_scenes_queryset(),
        id=tour_id,
        organization=organization,
    )

    all_scenes = list(tour.scenes.all().order_by("order", "id"))
    can_view_private = bool(request.user.is_authenticated)
    visible_scenes = (
        all_scenes
        if can_view_private
        else [scene for scene in all_scenes if bool(getattr(scene, "is_public", True))]
    )

    if not visible_scenes:
        visible_scenes = all_scenes[:1] if can_view_private else []

    requested_scene = str(request.GET.get("s") or "").strip()
    initial_scene = None
    if requested_scene:
        initial_scene = next(
            (
                scene for scene in visible_scenes
                if requested_scene in {str(scene.id), str(scene.scene_id or "")}
            ),
            None,
        )
    if initial_scene is None and visible_scenes:
        initial_scene = visible_scenes[0]

    seo_context = build_tour_preview_seo(
        request,
        tour=tour,
        organization=organization,
        scenes=visible_scenes or all_scenes,
    )

    place = getattr(tour, "place", None)
    preview_latitude = getattr(place, "latitude", None) or getattr(tour, "lat", None)
    preview_longitude = getattr(place, "longitude", None) or getattr(tour, "lng", None)
    configured_assistant_name = str(getattr(organization, "ai_assistant_name", "") or "").strip()
    if not configured_assistant_name or configured_assistant_name.lower() in {
        "twinscopes ai",
        "twinscope ai",
        "artificial intelligence",
        "intelligence artificielle",
    }:
        configured_assistant_name = f"{organization.name} Assistant"

    configured_assistant_tagline = str(getattr(organization, "ai_assistant_tagline", "") or "").strip()
    if not configured_assistant_tagline or configured_assistant_tagline.lower() in {
        "scene-aware assistant",
        "ai assistant",
        "assistant ia",
    }:
        configured_assistant_tagline = "How can we help?"

    preview_runtime_context = {
        "preview_assistant_name": configured_assistant_name,
        "preview_assistant_tagline": configured_assistant_tagline,
        "google_maps_browser_key": (
            getattr(settings, "GOOGLE_MAPS_BROWSER_KEY", "")
            or getattr(settings, "GOOGLE_MAPS_API_KEY", "")
        ),
        "google_maps_3d_map_id": getattr(settings, "GOOGLE_MAPS_3D_MAP_ID", ""),
        "preview_spatial_3d_enabled": bool(
            getattr(settings, "PREVIEW_SPATIAL_3D_ENABLED", True)
        ),
        "preview_three_module_url": getattr(
            settings,
            "PREVIEW_THREE_MODULE_URL",
            "https://cdn.jsdelivr.net/npm/three@0.185.1/build/three.module.js",
        ),
        "preview_google_maps_3d_enabled": bool(
            getattr(settings, "PREVIEW_GOOGLE_MAPS_3D_ENABLED", True)
        ),
        "preview_spatial_depth_strength": float(
            getattr(settings, "PREVIEW_SPATIAL_DEPTH_STRENGTH", 0.55)
        ),
        "preview_spatial_depth_invert": bool(
            getattr(settings, "PREVIEW_SPATIAL_DEPTH_INVERT", True)
        ),
        "preview_spatial_point_budget": int(
            getattr(settings, "PREVIEW_SPATIAL_POINT_BUDGET", 24000)
        ),
        "preview_spatial_mesh_segments": int(
            getattr(settings, "PREVIEW_SPATIAL_MESH_SEGMENTS", 140)
        ),
        "preview_spatial_graph_max_nodes": int(
            getattr(settings, "PREVIEW_SPATIAL_GRAPH_MAX_NODES", 36)
        ),
        "preview_spatial_natural_drag": bool(
            getattr(settings, "PREVIEW_SPATIAL_NATURAL_DRAG", True)
        ),
        "preview_spatial_invert_vertical_drag": bool(
            getattr(settings, "PREVIEW_SPATIAL_INVERT_VERTICAL_DRAG", True)
        ),
        "preview_spatial_open_panorama_on_card_click": bool(
            getattr(settings, "PREVIEW_SPATIAL_OPEN_PANORAMA_ON_CARD_CLICK", True)
        ),
        "tour_ai_external_embed_timeout_ms": int(
            getattr(settings, "TOUR_AI_EXTERNAL_EMBED_TIMEOUT_MS", 7000)
        ),
        "preview_scene_detail_url_template": reverse(
            "tour-preview-scene-data",
            kwargs={
                "organization_slug": organization.slug,
                "tour_id": tour.id,
                "scene_id": 999999999,
            },
        ).replace("999999999", "{sceneId}"),
        "preview_location": {
            "latitude": float(preview_latitude) if preview_latitude is not None else None,
            "longitude": float(preview_longitude) if preview_longitude is not None else None,
            "label": getattr(place, "name", "") or tour.title,
            "address": ", ".join(
                part for part in [
                    getattr(place, "address_line", "") if place else "",
                    getattr(place, "city", "") if place else "",
                    getattr(place, "country", "") if place else "",
                ]
                if part
            ),
        },
    }

    scenes_payload = (
        [
            _serialize_scene_payload(
                request=request,
                scene=initial_scene,
                include_hotspots=True,
                include_ai_metadata=False,
                include_prefetch=False,
            )
        ]
        if initial_scene
        else []
    )
    scene_list_payload = [
        _serialize_scene_index_payload(request, scene)
        for scene in visible_scenes
    ]

    return render(
        request,
        "dashboard/tours/preview.html",
        {
            "tour": tour,
            "current_organization": organization,
            "scenes_json": scenes_payload,
            "scene_list_json": scene_list_payload,
            "appointment_types": AppointmentType.objects.filter(organization=organization, is_active=True),
            "tour_products": Product.objects.filter(organization=organization, status=Product.Status.ACTIVE).order_by("-is_featured", "-created_at")[:8],
            **preview_runtime_context,
            **seo_context,
        },
    )


@require_GET
def tour_preview_scene_data_view(request, organization_slug, tour_id, scene_id):
    """Charge une scène publique complète seulement lorsqu'elle est demandée."""
    organization = _get_org_or_403(request, organization_slug, allow_public=True)
    if not organization:
        return JsonResponse({"detail": "Forbidden"}, status=403)

    tour = get_object_or_404(Tour, id=tour_id, organization=organization)
    scene = get_object_or_404(
        Scene360.objects.select_related("tour", "organization").prefetch_related(
            Prefetch(
                "hotspots",
                queryset=Hotspot.objects.select_related("target_scene").order_by("id"),
            )
        ),
        id=scene_id,
        tour=tour,
        organization=organization,
    )

    if not request.user.is_authenticated and not bool(getattr(scene, "is_public", True)):
        return JsonResponse({"detail": "Not found"}, status=404)

    response = JsonResponse({
        "success": True,
        "scene": _serialize_scene_payload(
            request=request,
            scene=scene,
            include_hotspots=True,
            include_ai_metadata=False,
            include_prefetch=False,
        ),
    })
    response["Cache-Control"] = "private, max-age=180" if request.user.is_authenticated else "public, max-age=180"
    return response

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
@transaction.atomic
def update_scene_ajax_view(request, organization_slug, scene_id):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return JsonResponse({"detail": "Forbidden"}, status=403)

    scene = get_object_or_404(
        Scene360.objects.select_for_update().select_related("tour").prefetch_related(
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
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"detail": "Invalid JSON payload."}, status=400)

    changed_fields = []

    def _assign(field_name, value):
        if getattr(scene, field_name) != value:
            setattr(scene, field_name, value)
            changed_fields.append(field_name)

    if "title" in payload:
        title = (payload.get("title") or "").strip()
        if title:
            _assign("title", title)

    def _safe_float(key, current, minimum, maximum):
        if key not in payload:
            return current
        try:
            value = float(payload.get(key))
        except (TypeError, ValueError):
            return current
        return max(minimum, min(maximum, value))

    if "yaw_default" in payload:
        _assign("yaw_default", _safe_float("yaw_default", scene.yaw_default, -180.0, 180.0))
    if "pitch_default" in payload:
        _assign("pitch_default", _safe_float("pitch_default", scene.pitch_default, -89.5, 89.5))
    if "hfov_default" in payload:
        _assign("hfov_default", _safe_float("hfov_default", scene.hfov_default, 20.0, 160.0))

    if payload.get("order") is not None:
        try:
            _assign("order", max(0, int(payload["order"])))
        except (TypeError, ValueError):
            pass

    if payload.get("status") in {
        Scene360.Status.DRAFT,
        Scene360.Status.PUBLISHED,
        Scene360.Status.INACTIVE,
    }:
        _assign("status", payload["status"])

    if "is_public" in payload:
        _assign(
            "is_public",
            _payload_bool(payload.get("is_public"), default=bool(scene.is_public)),
        )

    # Save general scene values independently from the 360 tripod editor.
    # update_fields prevents a stale in-memory value from overwriting a tripod
    # setting that was just edited in another request.
    if changed_fields:
        scene.save(update_fields=[*dict.fromkeys(changed_fields), "updated_at"])

    camera_keys = {"camera_limits_enabled", "camera_pitch_min", "camera_pitch_max"}
    camera_requested = any(key in payload for key in camera_keys)
    camera_apply_all_scenes = _payload_bool(
        payload.get("camera_limits_apply_all_scenes"),
        default=False,
    )
    camera_applied_scene_ids = [scene.pk]
    camera_updates = {}

    if camera_requested:
        camera_enabled = _payload_bool(
            payload.get("camera_limits_enabled"),
            default=bool(scene.camera_limits_enabled),
        )
        camera_pitch_min = _safe_float(
            "camera_pitch_min", scene.camera_pitch_min, -89.5, 89.5
        )
        camera_pitch_max = _safe_float(
            "camera_pitch_max", scene.camera_pitch_max, -89.5, 89.5
        )
        if camera_pitch_min > camera_pitch_max - 5.0:
            return JsonResponse(
                {"detail": "The upper camera limit must remain at least 5 degrees above the lower limit."},
                status=400,
            )

        camera_updates = {
            "camera_limits_enabled": camera_enabled,
            "camera_pitch_min": camera_pitch_min,
            "camera_pitch_max": camera_pitch_max,
            "updated_at": timezone.now(),
        }
        updated_camera_rows = Scene360.objects.filter(
            pk=scene.pk, organization=organization
        ).update(**camera_updates)
        if updated_camera_rows != 1:
            transaction.set_rollback(True)
            return JsonResponse({"detail": "Camera limits could not be persisted."}, status=409)

        if camera_apply_all_scenes:
            sibling_camera_ids = list(
                Scene360.objects.select_for_update()
                .filter(tour_id=scene.tour_id, organization=organization)
                .exclude(pk=scene.pk)
                .values_list("pk", flat=True)
            )
            if sibling_camera_ids:
                updated_camera_siblings = Scene360.objects.filter(
                    pk__in=sibling_camera_ids
                ).update(**camera_updates)
                if updated_camera_siblings != len(sibling_camera_ids):
                    transaction.set_rollback(True)
                    return JsonResponse(
                        {"detail": "Camera limits could not be applied to every scene."},
                        status=409,
                    )
                camera_applied_scene_ids.extend(sibling_camera_ids)

    tripod_keys = {
        "tripod_logo_enabled",
        "tripod_logo_size",
        "tripod_logo_yaw",
        "tripod_logo_pitch",
        "tripod_logo_offset_x",
        "tripod_logo_offset_y",
        "tripod_logo_rotation",
        "tripod_logo_tilt_x",
        "tripod_logo_tilt_y",
        "tripod_logo_radius",
        "tripod_logo_background_enabled",
        "tripod_logo_background_color",
        "tripod_logo_background_opacity",
        "tripod_logo_background_width",
        "tripod_logo_background_height",
        "tripod_logo_background_radius",
    }
    tripod_requested = any(key in payload for key in tripod_keys)
    tripod_apply_all_scenes = _payload_bool(
        payload.get("tripod_logo_apply_all_scenes"),
        default=False,
    )
    tripod_applied_scene_ids = [scene.pk]

    def _bounded_number(key, current, minimum, maximum, cast=float):
        if key not in payload:
            return current
        try:
            value = cast(payload.get(key))
        except (TypeError, ValueError):
            return current
        return max(minimum, min(maximum, value))

    tripod_updates = {}
    if tripod_requested:
        tripod_updates = {
            "tripod_logo_enabled": _payload_bool(
                payload.get("tripod_logo_enabled"),
                default=bool(scene.tripod_logo_enabled),
            ),
            "tripod_logo_size": _bounded_number(
                "tripod_logo_size", scene.tripod_logo_size, 72, 320, int
            ),
            "tripod_logo_yaw": _bounded_number(
                "tripod_logo_yaw", scene.tripod_logo_yaw, -180.0, 180.0, float
            ),
            "tripod_logo_pitch": _bounded_number(
                "tripod_logo_pitch", scene.tripod_logo_pitch, -89.5, 89.5, float
            ),
            "tripod_logo_offset_x": _bounded_number(
                "tripod_logo_offset_x", scene.tripod_logo_offset_x, -250, 250, int
            ),
            "tripod_logo_offset_y": _bounded_number(
                "tripod_logo_offset_y", scene.tripod_logo_offset_y, -250, 250, int
            ),
            "tripod_logo_rotation": _bounded_number(
                "tripod_logo_rotation", scene.tripod_logo_rotation, -180.0, 180.0, float
            ),
            "tripod_logo_tilt_x": _bounded_number(
                "tripod_logo_tilt_x", scene.tripod_logo_tilt_x, -70.0, 70.0, float
            ),
            "tripod_logo_tilt_y": _bounded_number(
                "tripod_logo_tilt_y", scene.tripod_logo_tilt_y, -70.0, 70.0, float
            ),
            "tripod_logo_radius": _bounded_number(
                "tripod_logo_radius", scene.tripod_logo_radius, 350, 2400, int
            ),
            "tripod_logo_background_enabled": _payload_bool(
                payload.get("tripod_logo_background_enabled"),
                default=bool(scene.tripod_logo_background_enabled),
            ),
            "tripod_logo_background_color": str(
                payload.get("tripod_logo_background_color", scene.tripod_logo_background_color) or "#FFFFFF"
            )[:9],
            "tripod_logo_background_opacity": _bounded_number(
                "tripod_logo_background_opacity", scene.tripod_logo_background_opacity, 0.0, 1.0, float
            ),
            "tripod_logo_background_width": _bounded_number(
                "tripod_logo_background_width", scene.tripod_logo_background_width, 72, 520, int
            ),
            "tripod_logo_background_height": _bounded_number(
                "tripod_logo_background_height", scene.tripod_logo_background_height, 72, 520, int
            ),
            "tripod_logo_background_radius": _bounded_number(
                "tripod_logo_background_radius", scene.tripod_logo_background_radius, 0, 50, int
            ),
            "updated_at": timezone.now(),
        }

        # QuerySet.update performs a direct database write. It deliberately
        # bypasses model-side image processing and guarantees that every
        # tripod field is committed together in this transaction.
        updated_rows = Scene360.objects.filter(
            pk=scene.pk,
            organization=organization,
        ).update(**tripod_updates)
        if updated_rows != 1:
            transaction.set_rollback(True)
            return JsonResponse(
                {"detail": "Tripod logo settings could not be persisted."},
                status=409,
            )

        if tripod_apply_all_scenes:
            sibling_queryset = Scene360.objects.select_for_update().filter(
                tour_id=scene.tour_id,
                organization=organization,
            ).exclude(pk=scene.pk)
            sibling_ids = list(sibling_queryset.values_list("pk", flat=True))
            if sibling_ids:
                updated_siblings = Scene360.objects.filter(pk__in=sibling_ids).update(**tripod_updates)
                if updated_siblings != len(sibling_ids):
                    transaction.set_rollback(True)
                    return JsonResponse(
                        {"detail": "The tripod logo could not be applied to every scene."},
                        status=409,
                    )
                tripod_applied_scene_ids.extend(sibling_ids)

    scene.refresh_from_db()

    persisted_camera_limits = {
        "enabled": bool(scene.camera_limits_enabled),
        "pitch_min": float(scene.camera_pitch_min),
        "pitch_max": float(scene.camera_pitch_max),
    }

    persisted_tripod = {
        "enabled": bool(scene.tripod_logo_enabled),
        "size": int(scene.tripod_logo_size),
        "yaw": float(scene.tripod_logo_yaw),
        "pitch": float(scene.tripod_logo_pitch),
        "offset_x": int(scene.tripod_logo_offset_x),
        "offset_y": int(scene.tripod_logo_offset_y),
        "rotation": float(scene.tripod_logo_rotation),
        "tilt_x": float(scene.tripod_logo_tilt_x),
        "tilt_y": float(scene.tripod_logo_tilt_y),
        "radius": int(scene.tripod_logo_radius),
        "background_enabled": bool(scene.tripod_logo_background_enabled),
        "background_color": str(scene.tripod_logo_background_color or "#FFFFFF"),
        "background_opacity": float(scene.tripod_logo_background_opacity),
        "background_width": int(scene.tripod_logo_background_width),
        "background_height": int(scene.tripod_logo_background_height),
        "background_radius": int(scene.tripod_logo_background_radius),
    }

    if camera_requested:
        expected_camera_limits = {
            "enabled": bool(camera_updates["camera_limits_enabled"]),
            "pitch_min": float(camera_updates["camera_pitch_min"]),
            "pitch_max": float(camera_updates["camera_pitch_max"]),
        }
        camera_verified = (
            persisted_camera_limits["enabled"] == expected_camera_limits["enabled"]
            and abs(persisted_camera_limits["pitch_min"] - expected_camera_limits["pitch_min"]) < 0.0001
            and abs(persisted_camera_limits["pitch_max"] - expected_camera_limits["pitch_max"]) < 0.0001
        )
        if not camera_verified:
            transaction.set_rollback(True)
            return JsonResponse(
                {
                    "detail": "Camera limits were not confirmed by the database.",
                    "expected": expected_camera_limits,
                    "persisted": persisted_camera_limits,
                },
                status=409,
            )

        if camera_apply_all_scenes:
            camera_verification_rows = Scene360.objects.filter(
                pk__in=camera_applied_scene_ids,
                tour_id=scene.tour_id,
                organization=organization,
                camera_limits_enabled=expected_camera_limits["enabled"],
                camera_pitch_min=expected_camera_limits["pitch_min"],
                camera_pitch_max=expected_camera_limits["pitch_max"],
            ).count()
            if camera_verification_rows != len(camera_applied_scene_ids):
                transaction.set_rollback(True)
                return JsonResponse(
                    {
                        "detail": "Camera limits were not confirmed on every scene.",
                        "expected_scene_count": len(camera_applied_scene_ids),
                        "persisted_scene_count": camera_verification_rows,
                    },
                    status=409,
                )

    if tripod_requested:
        expected_tripod = {
            "enabled": bool(tripod_updates["tripod_logo_enabled"]),
            "size": int(tripod_updates["tripod_logo_size"]),
            "yaw": float(tripod_updates["tripod_logo_yaw"]),
            "pitch": float(tripod_updates["tripod_logo_pitch"]),
            "offset_x": int(tripod_updates["tripod_logo_offset_x"]),
            "offset_y": int(tripod_updates["tripod_logo_offset_y"]),
            "rotation": float(tripod_updates["tripod_logo_rotation"]),
            "tilt_x": float(tripod_updates["tripod_logo_tilt_x"]),
            "tilt_y": float(tripod_updates["tripod_logo_tilt_y"]),
            "radius": int(tripod_updates["tripod_logo_radius"]),
            "background_enabled": bool(tripod_updates["tripod_logo_background_enabled"]),
            "background_color": str(tripod_updates["tripod_logo_background_color"]),
            "background_opacity": float(tripod_updates["tripod_logo_background_opacity"]),
            "background_width": int(tripod_updates["tripod_logo_background_width"]),
            "background_height": int(tripod_updates["tripod_logo_background_height"]),
            "background_radius": int(tripod_updates["tripod_logo_background_radius"]),
        }

        numeric_keys = {
            "yaw", "pitch", "rotation", "tilt_x", "tilt_y", "background_opacity"
        }
        verified = all(
            abs(persisted_tripod[key] - expected_tripod[key]) < 0.0001
            if key in numeric_keys
            else persisted_tripod[key] == expected_tripod[key]
            for key in expected_tripod
        )
        if not verified:
            transaction.set_rollback(True)
            return JsonResponse(
                {
                    "detail": "The tripod logo was not confirmed by the database.",
                    "expected": expected_tripod,
                    "persisted": persisted_tripod,
                },
                status=409,
            )

        if tripod_apply_all_scenes:
            verification_rows = Scene360.objects.filter(
                pk__in=tripod_applied_scene_ids,
                tour_id=scene.tour_id,
                organization=organization,
                tripod_logo_enabled=expected_tripod["enabled"],
                tripod_logo_size=expected_tripod["size"],
                tripod_logo_yaw=expected_tripod["yaw"],
                tripod_logo_pitch=expected_tripod["pitch"],
                tripod_logo_offset_x=expected_tripod["offset_x"],
                tripod_logo_offset_y=expected_tripod["offset_y"],
                tripod_logo_rotation=expected_tripod["rotation"],
                tripod_logo_tilt_x=expected_tripod["tilt_x"],
                tripod_logo_tilt_y=expected_tripod["tilt_y"],
                tripod_logo_radius=expected_tripod["radius"],
                tripod_logo_background_enabled=expected_tripod["background_enabled"],
                tripod_logo_background_color=expected_tripod["background_color"],
                tripod_logo_background_opacity=expected_tripod["background_opacity"],
                tripod_logo_background_width=expected_tripod["background_width"],
                tripod_logo_background_height=expected_tripod["background_height"],
                tripod_logo_background_radius=expected_tripod["background_radius"],
            ).count()
            if verification_rows != len(tripod_applied_scene_ids):
                transaction.set_rollback(True)
                return JsonResponse(
                    {
                        "detail": "The tripod logo was not confirmed on every scene.",
                        "expected_scene_count": len(tripod_applied_scene_ids),
                        "persisted_scene_count": verification_rows,
                    },
                    status=409,
                )

    build_tour_manifest(scene.tour)

    response = JsonResponse({
        "success": True,
        "persistence": {
            "database_verified": True,
            "camera_limits_verified": bool(camera_requested),
            "camera_limits": persisted_camera_limits,
            "camera_limits_applied_to_all_scenes": bool(camera_requested and camera_apply_all_scenes),
            "camera_limits_applied_scene_ids": camera_applied_scene_ids if camera_requested else [],
            "camera_limits_applied_scene_count": len(camera_applied_scene_ids) if camera_requested else 0,
            "tripod_logo_verified": bool(tripod_requested),
            "tripod_logo_applied_to_all_scenes": bool(tripod_requested and tripod_apply_all_scenes),
            "tripod_logo_applied_scene_ids": tripod_applied_scene_ids if tripod_requested else [],
            "tripod_logo_applied_scene_count": len(tripod_applied_scene_ids) if tripod_requested else 0,
        },
        "scene": _serialize_scene_payload(
            request=request,
            scene=scene,
            include_hotspots=True,
            prefetch=None,
        ),
    })
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response["Pragma"] = "no-cache"
    return response

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

# =============================================================================
# AI TOUR ARCHITECT DASHBOARD
# =============================================================================

@login_required
def tour_architect_view(request, organization_slug, tour_id):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return render(request, "403.html", status=403)

    active_candidates = Prefetch(
        "object_candidates",
        queryset=SceneObjectCandidate.objects.exclude(
            review_status=SceneObjectCandidate.ReviewStatus.HIDDEN
        ).order_by("-is_navigation_anchor", "-confidence", "id"),
        to_attr="architect_candidates",
    )
    tour = get_object_or_404(
        Tour.objects.select_related("organization", "place").prefetch_related(
            Prefetch(
                "scenes",
                queryset=Scene360.objects.select_related("visual_quality").prefetch_related(active_candidates).order_by("order", "id"),
                to_attr="architect_scenes",
            )
        ),
        pk=tour_id,
        organization=organization,
    )
    latest_run = (
        TourArchitectureRun.objects.filter(tour=tour)
        .prefetch_related(
            Prefetch(
                "proposals",
                queryset=SceneLinkProposal.objects.select_related(
                    "from_scene", "to_scene", "from_anchor", "to_anchor",
                    "applied_from_hotspot", "applied_reverse_hotspot",
                ).order_by("from_scene__order", "-confidence"),
                to_attr="architect_proposals",
            )
        )
        .order_by("-created_at")
        .first()
    )
    scenes = list(getattr(tour, "architect_scenes", []))
    for scene in scenes:
        scene.architect_quality = getattr(scene, "visual_quality", None)
    proposals = list(getattr(latest_run, "architect_proposals", [])) if latest_run else []
    existing_navigation_hotspots = list(
        Hotspot.objects.filter(
            scene__tour=tour,
            target_scene__isnull=False,
            type__in=[Hotspot.Type.NAVIGATE, Hotspot.Type.FLOOR, Hotspot.Type.DOOR],
        ).select_related("scene", "target_scene").order_by("scene__order", "id")
    )
    object_count = sum(len(getattr(scene, "architect_candidates", [])) for scene in scenes)
    client_ready_count = sum(
        1 for scene in scenes for candidate in getattr(scene, "architect_candidates", []) if candidate.client_ready
    )
    portal_count = sum(
        1 for scene in scenes for candidate in getattr(scene, "architect_candidates", []) if candidate.is_navigation_anchor
    )
    quality_ready = sum(
        1 for scene in scenes if getattr(scene.architect_quality, "status", "") == SceneVisualQuality.Status.READY
    )
    vision_ready = sum(1 for scene in scenes if scene.ai_analysis_status == "ready")
    context = {
        "current_organization": organization,
        "tour": tour,
        "scenes": scenes,
        "latest_run": latest_run,
        "proposals": proposals,
        "stats": {
            "scene_count": len(scenes),
            "vision_ready": vision_ready,
            "quality_ready": quality_ready,
            "object_count": object_count,
            "client_ready_count": client_ready_count,
            "portal_count": portal_count,
            "proposal_count": len(proposals),
            "applied_count": sum(1 for item in proposals if item.status == SceneLinkProposal.Status.APPLIED),
            "existing_link_count": len(existing_navigation_hotspots),
        },
        "architect_graph": {
            "nodes": [
                {
                    "id": scene.pk,
                    "title": scene.title,
                    "order": scene.order,
                    "quality": round(float(getattr(scene.architect_quality, "overall_score", 0) or 0), 4),
                    "image": scene.thumbnail_url or scene.image_360_preview_url or "",
                }
                for scene in scenes
            ],
            "edges": [
                {
                    "id": f"hotspot-{hotspot.pk}",
                    "from": hotspot.scene_id,
                    "to": hotspot.target_scene_id,
                    "confidence": float((hotspot.payload or {}).get("confidence") or (0.96 if hotspot.is_ai_generated else 1.0)),
                    "status": "applied",
                    "bidirectional": False,
                    "existing": True,
                    "manual": not hotspot.is_ai_generated,
                }
                for hotspot in existing_navigation_hotspots
            ] + [
                {
                    "id": proposal.pk,
                    "from": proposal.from_scene_id,
                    "to": proposal.to_scene_id,
                    "confidence": proposal.confidence,
                    "status": proposal.status,
                    "bidirectional": proposal.is_bidirectional,
                    "existing": False,
                }
                for proposal in proposals
            ],
        },
    }
    return render(request, "dashboard/tours/architect.html", context)


@login_required
@require_POST
def queue_tour_architect_ajax_view(request, organization_slug, tour_id):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return JsonResponse({"detail": "Forbidden"}, status=403)
    tour = get_object_or_404(Tour, pk=tour_id, organization=organization)
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        payload = {}
    from apps.tours.intelligence.dispatch import dispatch_tour_architecture

    dispatch = dispatch_tour_architecture(
        tour,
        force=_payload_bool(payload.get("force"), default=False),
        mode=str(payload.get("mode") or "auto"),
        user=request.user,
    )
    return JsonResponse({
        "success": True,
        "run_id": str(dispatch.run.pk),
        "created": dispatch.created,
        "mode": dispatch.mode,
        "task_id": dispatch.task_id,
        "status_url": reverse(
            "dashboard-tour-architect-status-ajax",
            kwargs={
                "organization_slug": organization.slug,
                "tour_id": tour.pk,
                "run_id": dispatch.run.pk,
            },
        ),
    })


@login_required
@require_GET
def tour_architect_status_ajax_view(request, organization_slug, tour_id, run_id):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return JsonResponse({"detail": "Forbidden"}, status=403)
    run = get_object_or_404(
        TourArchitectureRun.objects.select_related("tour"),
        pk=run_id,
        tour_id=tour_id,
        organization=organization,
    )
    return JsonResponse({
        "success": True,
        "run": {
            "id": str(run.pk),
            "status": run.status,
            "stage": run.stage,
            "scene_count": run.scene_count,
            "object_count": run.object_count,
            "proposal_count": run.proposal_count,
            "applied_count": run.applied_count,
            "summary": run.summary,
            "error_code": run.error_code,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        },
    })


@login_required
@require_POST
def review_scene_object_ajax_view(request, organization_slug, candidate_id):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return JsonResponse({"detail": "Forbidden"}, status=403)
    candidate = get_object_or_404(
        SceneObjectCandidate.objects.select_related("scene", "scene__tour"),
        pk=candidate_id,
        scene__organization=organization,
    )
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON"}, status=400)
    action = str(payload.get("action") or "").lower()
    mapping = {
        "approve": SceneObjectCandidate.ReviewStatus.APPROVED,
        "reject": SceneObjectCandidate.ReviewStatus.REJECTED,
        "hide": SceneObjectCandidate.ReviewStatus.HIDDEN,
        "restore": SceneObjectCandidate.ReviewStatus.SUGGESTED,
    }
    if action not in mapping:
        return JsonResponse({"detail": "Unsupported action"}, status=400)
    candidate.review_status = mapping[action]
    if action == "approve":
        candidate.client_ready = True
    elif action in {"reject", "hide"}:
        candidate.client_ready = False
    candidate.save(update_fields=("review_status", "client_ready", "updated_at"))
    return JsonResponse({
        "success": True,
        "candidate": {
            "id": candidate.pk,
            "review_status": candidate.review_status,
            "client_ready": candidate.client_ready,
        },
    })


@login_required
@require_POST
def rerun_scene_intelligence_ajax_view(request, organization_slug, scene_id):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return JsonResponse({"detail": "Forbidden"}, status=403)
    scene = get_object_or_404(Scene360.objects.select_related("tour"), pk=scene_id, organization=organization)
    from apps.vision_ai.services.queueing import dispatch_scene_analysis

    dispatch = dispatch_scene_analysis(
        scene,
        force=True,
        requested_providers=["yolo", "paddleocr", "gemini", "openai"],
        mode="auto",
    )
    return JsonResponse({
        "success": True,
        "analysis_id": str(dispatch.analysis.pk),
        "mode": dispatch.mode,
        "task_id": dispatch.task_id,
    })


@login_required
@require_POST
def review_scene_link_ajax_view(request, organization_slug, proposal_id):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return JsonResponse({"detail": "Forbidden"}, status=403)
    proposal = get_object_or_404(
        SceneLinkProposal.objects.select_related("tour", "from_scene", "to_scene", "run"),
        pk=proposal_id,
        tour__organization=organization,
    )
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON"}, status=400)
    action = str(payload.get("action") or "").lower()
    editable_fields = ("from_yaw", "from_pitch", "to_yaw", "to_pitch")
    changed = []
    for field in editable_fields:
        if field in payload:
            try:
                value = float(payload[field])
            except (TypeError, ValueError):
                continue
            if field.endswith("yaw"):
                value = max(-3.14159, min(3.14159, value))
            else:
                value = max(-1.2, min(1.2, value))
            setattr(proposal, field, value)
            changed.append(field)
    if "bidirectional" in payload:
        proposal.is_bidirectional = _payload_bool(payload.get("bidirectional"), default=True)
        changed.append("is_bidirectional")
    if changed:
        proposal.manual_adjusted = True
        changed.append("manual_adjusted")

    if action == "reject":
        proposal.status = SceneLinkProposal.Status.REJECTED
    elif action in {"approve", "update"}:
        proposal.status = SceneLinkProposal.Status.APPROVED
    elif action == "apply":
        if changed:
            proposal.status = SceneLinkProposal.Status.APPROVED
            proposal.save(update_fields=tuple(dict.fromkeys(changed + ["status", "updated_at"])))
        from apps.tours.intelligence.scene_architect import apply_link_proposal

        proposal = apply_link_proposal(proposal, user=request.user)
        return JsonResponse({"success": True, "status": proposal.status, "proposal_id": proposal.pk})
    else:
        return JsonResponse({"detail": "Unsupported action"}, status=400)
    proposal.reviewed_by = request.user
    proposal.reviewed_at = timezone.now()
    proposal.save(update_fields=tuple(dict.fromkeys(changed + ["status", "reviewed_by", "reviewed_at", "updated_at"])))
    return JsonResponse({"success": True, "status": proposal.status, "proposal_id": proposal.pk})


@login_required
@require_POST
def bulk_apply_scene_links_ajax_view(request, organization_slug, tour_id):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return JsonResponse({"detail": "Forbidden"}, status=403)
    tour = get_object_or_404(Tour, pk=tour_id, organization=organization)
    latest_run = TourArchitectureRun.objects.filter(tour=tour).order_by("-created_at").first()
    if not latest_run:
        return JsonResponse({"detail": "No architecture run"}, status=404)
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        payload = {}
    threshold = max(0.0, min(1.0, float(payload.get("min_confidence") or 0.84)))
    from apps.tours.intelligence.scene_architect import apply_link_proposal

    applied = 0
    conflicts = 0
    queryset = latest_run.proposals.filter(
        status__in=[SceneLinkProposal.Status.SUGGESTED, SceneLinkProposal.Status.APPROVED],
        confidence__gte=threshold,
    ).order_by("-confidence")
    for proposal in queryset:
        result = apply_link_proposal(proposal, user=request.user)
        if result.status == SceneLinkProposal.Status.APPLIED:
            applied += 1
        elif result.status == SceneLinkProposal.Status.CONFLICT:
            conflicts += 1
    return JsonResponse({"success": True, "applied": applied, "conflicts": conflicts})
