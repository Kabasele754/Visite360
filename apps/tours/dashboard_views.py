from django.contrib import messages
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.forms import ModelForm
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_POST
import json
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

from apps.organizations.models import Organization, OrganizationMember
from apps.organizations.selectors import get_user_membership
from apps.places.models import Place
from apps.tours.forms import TourForm

from .models import Tour, Scene360, Hotspot
from .services import (
    generate_unique_tour_slug,
    handle_uploaded_scenes,
    create_hotspot,
    build_tour_manifest,
    reorder_scenes_for_tour,
    update_hotspot,
)
from django.db.models import Q
from django.core.paginator import Paginator
from django.views.decorators.http import require_GET, require_POST
from django.utils.text import slugify
from copy import deepcopy
from .utils import generate_unique_tour_slug


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


@login_required
def studio_home_view(request):
    organization, place, tour = _get_or_create_default_workspace(request.user)
    return redirect("tour-builder", organization_slug=organization.slug, tour_id=tour.id)




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
            organization=organization, status=Tour.Status.PUBLISHED
        ).count(),
        "draft_count": Tour.objects.filter(
            organization=organization, status=Tour.Status.DRAFT
        ).count(),
        "inactive_count": Tour.objects.filter(
            organization=organization, status=Tour.Status.INACTIVE
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
        form = TourForm(request.POST, request.FILES, instance=tour, organization=organization)

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
@require_POST
def tour_delete_view(request, organization_slug, tour_id):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return JsonResponse({"success": False, "message": "Unauthorized."}, status=403)

    tour = get_object_or_404(Tour, id=tour_id, organization=organization)
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


# @login_required
# def tour_list_view(request, organization_slug):
#     organization = _get_org_or_403(request, organization_slug)
#     if not organization:
#         return render(request, "403.html", status=403)

#     tours = (
#         Tour.objects.filter(organization=organization)
#         .select_related("place")
#         .order_by("-created_at")
#     )

#     place_id = request.GET.get("place")
#     if place_id:
#         tours = tours.filter(place_id=place_id)

#     return render(
#         request,
#         "dashboard/tours/list.html",
#         {
#             "tours": tours,
#             "current_organization": organization,
#         },
#     )


# @login_required
# def tour_create_view(request, organization_slug):
#     organization = _get_org_or_403(request, organization_slug)
#     if not organization:
#         return render(request, "403.html", status=403)

#     if request.method == "POST":
#         form = TourForm(request.POST, request.FILES)
#         form.fields["place"].queryset = Place.objects.filter(organization=organization)

#         if form.is_valid():
#             tour = form.save(commit=False)
#             tour.organization = organization

#             if not tour.slug:
#                 tour.slug = generate_unique_tour_slug(tour.title)

#             tour.save()
#             messages.success(request, "Tour created successfully.")
#             return redirect("dashboard-tours-list", organization_slug=organization.slug)
#     else:
#         form = TourForm()
#         form.fields["place"].queryset = Place.objects.filter(organization=organization)

#     return render(
#         request,
#         "dashboard/tours/form.html",
#         {
#             "form": form,
#             "page_mode": "create",
#             "current_organization": organization,
#         },
#     )


# @login_required
# def tour_edit_view(request, organization_slug, tour_id):
#     organization = _get_org_or_403(request, organization_slug)
#     if not organization:
#         return render(request, "403.html", status=403)

#     tour = get_object_or_404(Tour, id=tour_id, organization=organization)

#     if request.method == "POST":
#         form = TourForm(request.POST, request.FILES, instance=tour)
#         form.fields["place"].queryset = Place.objects.filter(organization=organization)

#         if form.is_valid():
#             tour = form.save(commit=False)

#             if not tour.slug:
#                 tour.slug = generate_unique_tour_slug(tour.title)

#             tour.save()
#             messages.success(request, "Tour updated successfully.")
#             return redirect("dashboard-tours-list", organization_slug=organization.slug)
#     else:
#         form = TourForm(instance=tour)
#         form.fields["place"].queryset = Place.objects.filter(organization=organization)

#     return render(
#         request,
#         "dashboard/tours/form.html",
#         {
#             "form": form,
#             "tour": tour,
#             "page_mode": "edit",
#             "current_organization": organization,
#         },
#     )
    

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
        "tour": {
            "id": tour.id,
            "title": tour.title,
        }
    })


@login_required
def tour_delete_view(request, organization_slug, tour_id):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return render(request, "403.html", status=403)

    tour = get_object_or_404(Tour, id=tour_id, organization=organization)

    if request.method == "POST":
        tour.delete()
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
def tour_builder_view(request, organization_slug, tour_id):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return render(request, "403.html", status=403)

    tour = get_object_or_404(
        Tour.objects.select_related("place", "organization").prefetch_related("scenes__hotspots"),
        id=tour_id,
        organization=organization,
    )

    scenes = tour.scenes.all().order_by("order", "id")

    scenes_payload = [
        {
            "id": scene.id,
            "scene_id": scene.scene_id,
            "title": scene.title,
            "image_360_url": scene.image_360.url if scene.image_360 else "",
            "thumbnail_url": scene.thumbnail_image.url if scene.thumbnail_image else "",
            "order": scene.order,
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
        }
        for scene in scenes
    ]

    context = {
        "tour": tour,
        "scenes": scenes,
        "scenes_json": scenes_payload,
        "current_organization": organization,
        "current_place": tour.place,
    }
    return render(request, "dashboard/tours/builder.html", context)


# @login_required
def tour_preview_view(request, organization_slug, tour_id):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return render(request, "403.html", status=403)

    tour = get_object_or_404(
        Tour.objects.select_related("place", "organization").prefetch_related(
            "scenes__hotspots",
            "scenes__hotspots__target_scene",
        ),
        id=tour_id,
        organization=organization,
    )

    scenes = tour.scenes.all().order_by("order", "id")

    scenes_payload = []
    for scene in scenes:
        scene_hotspots = []

        for hotspot in scene.hotspots.all():
            scene_hotspots.append({
                "id": hotspot.id,
                "type": hotspot.type,
                "label": hotspot.label,
                "yaw": hotspot.yaw,
                "pitch": hotspot.pitch,
                "target_scene": hotspot.target_scene_id,
                "selected_icon": hotspot.selected_icon or "default",
                "title": hotspot.title or "",
                "description": hotspot.description or "",
                "tooltip_text": hotspot.tooltip_text or "",
                "ad_image_url": hotspot.ad_image.url if getattr(hotspot, "ad_image", None) else "",
                "payload": hotspot.payload or {},
            })

        scenes_payload.append({
            "id": scene.id,
            "scene_id": scene.scene_id,
            "title": scene.title,
            "order": scene.order,
            "image_360_url": scene.image_360.url if scene.image_360 else "",
            "image_360_mobile_url": scene.image_360_mobile.url if getattr(scene, "image_360_mobile", None) else "",
            "thumbnail_url": scene.thumbnail_image.url if getattr(scene, "thumbnail_image", None) else "",
            "yaw_default": scene.yaw_default if scene.yaw_default is not None else 0,
            "pitch_default": scene.pitch_default if scene.pitch_default is not None else 0,
            "hfov_default": scene.hfov_default if scene.hfov_default is not None else 100,
            "hotspots": scene_hotspots,
        })

    return render(
        request,
        "dashboard/tours/preview.html",
        {
            "tour": tour,
            "current_organization": organization,
            "scenes_json": scenes_payload,
        },
    ) 
    
    
    
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

    created_scenes = handle_uploaded_scenes(tour, files)

    data = []
    for scene in created_scenes:
        data.append({
            "id": scene.id,
            "scene_id": scene.scene_id,
            "title": scene.title,
            "image_360_url": scene.image_360.url if scene.image_360 else "",
            "thumbnail_url": scene.thumbnail_image.url if scene.thumbnail_image else "",
            "order": scene.order,
            "yaw_default": scene.yaw_default,
            "pitch_default": scene.pitch_default,
            "hfov_default": scene.hfov_default,
            "hotspots": [],
        })

    return JsonResponse({"scenes": data}, status=201)


@login_required
@require_POST
def update_scene_ajax_view(request, organization_slug, scene_id):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return JsonResponse({"detail": "Forbidden"}, status=403)

    scene = get_object_or_404(Scene360, id=scene_id, organization=organization)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON payload."}, status=400)

    scene.title = payload.get("title", scene.title)
    scene.yaw_default = payload.get("yaw_default", scene.yaw_default)
    scene.pitch_default = payload.get("pitch_default", scene.pitch_default)
    scene.hfov_default = payload.get("hfov_default", scene.hfov_default)

    if payload.get("order") is not None:
        scene.order = payload["order"]

    scene.save()
    build_tour_manifest(scene.tour)

    return JsonResponse({
        "scene": {
            "id": scene.id,
            "scene_id": scene.scene_id,
            "title": scene.title,
            "image_360_url": scene.image_360.url if scene.image_360 else "",
            "thumbnail_url": scene.thumbnail_image.url if scene.thumbnail_image else "",
            "order": scene.order,
            "yaw_default": scene.yaw_default,
            "pitch_default": scene.pitch_default,
            "hfov_default": scene.hfov_default,
        }
    })


@login_required
@require_POST
def create_hotspot_ajax_view(request, organization_slug, scene_id):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return JsonResponse({"detail": "Forbidden"}, status=403)

    scene = get_object_or_404(Scene360, id=scene_id, organization=organization)

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

    return JsonResponse({
        "hotspot": {
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
    }, status=201)
    
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

    scenes = reorder_scenes_for_tour(tour, ordered_scene_ids)

    return JsonResponse({
        "scenes": [
            {
                "id": scene.id,
                "scene_id": scene.scene_id,
                "title": scene.title,
                "image_360_url": scene.image_360.url if scene.image_360 else "",
                "thumbnail_url": scene.thumbnail_image.url if scene.thumbnail_image else "",
                "order": scene.order,
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
            }
            for scene in scenes
        ]
    })
    
@login_required
@require_POST
def update_hotspot_ajax_view(request, organization_slug, hotspot_id):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return JsonResponse({"detail": "Forbidden"}, status=403)

    hotspot = get_object_or_404(Hotspot, id=hotspot_id, organization=organization)

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

    return JsonResponse({
        "hotspot": {
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
    })
    

@login_required
@require_POST
def upload_hotspot_image_ajax_view(request, organization_slug, hotspot_id):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return JsonResponse({"detail": "Forbidden"}, status=403)

    hotspot = get_object_or_404(Hotspot, id=hotspot_id, organization=organization)

    image_file = request.FILES.get("image")
    if not image_file:
        return JsonResponse({"detail": "No image uploaded."}, status=400)

    hotspot.ad_image = image_file
    hotspot.save(update_fields=["ad_image", "updated_at"])

    return JsonResponse({
        "hotspot": {
            "id": hotspot.id,
            "ad_image_url": hotspot.ad_image.url if hotspot.ad_image else "",
        }
    })


@login_required
@require_POST
def delete_hotspot_ajax_view(request, organization_slug, hotspot_id):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return JsonResponse({"detail": "Forbidden"}, status=403)

    hotspot = get_object_or_404(Hotspot, id=hotspot_id, organization=organization)
    tour = hotspot.scene.tour
    hotspot.delete()

    build_tour_manifest(tour)
    return JsonResponse({"success": True})
