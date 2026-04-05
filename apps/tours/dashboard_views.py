from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.forms import ModelForm
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.http import JsonResponse
from django.views.decorators.http import require_POST
import json

from apps.organizations.models import Organization, OrganizationMember
from apps.organizations.selectors import get_user_membership
from apps.places.models import Place

from .models import Tour, Scene360, Hotspot
from .services import (
    generate_unique_tour_slug,
    handle_uploaded_scenes,
    create_hotspot,
    build_tour_manifest,
)


class TourForm(ModelForm):
    class Meta:
        model = Tour
        fields = [
            "place",
            "title",
            "slug",
            "description",
            "thumbnail_image",
            "video_tour",
            "virtual_tour_url",
            "tour_date",
            "duration",
            "price",
            "is_featured",
            "max_participants",
            "rating",
            "guide_name",
            "contact_email",
            "location",
            "lat",
            "lng",
            "radius",
            "chambres",
            "balcon",
            "floor_number",
            "parking",
            "ascenseur",
            "status",
        ]


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


def _get_org_or_403(request, organization_slug):
    organization = get_object_or_404(Organization, slug=organization_slug)

    if request.user.is_superuser:
        return organization

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


@login_required
def tour_list_view(request, organization_slug):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return render(request, "403.html", status=403)

    tours = (
        Tour.objects.filter(organization=organization)
        .select_related("place")
        .order_by("-created_at")
    )

    place_id = request.GET.get("place")
    if place_id:
        tours = tours.filter(place_id=place_id)

    return render(
        request,
        "dashboard/tours/list.html",
        {
            "tours": tours,
            "current_organization": organization,
        },
    )


@login_required
def tour_create_view(request, organization_slug):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return render(request, "403.html", status=403)

    if request.method == "POST":
        form = TourForm(request.POST, request.FILES)
        form.fields["place"].queryset = Place.objects.filter(organization=organization)

        if form.is_valid():
            tour = form.save(commit=False)
            tour.organization = organization

            if not tour.slug:
                tour.slug = generate_unique_tour_slug(tour.title)

            tour.save()
            messages.success(request, "Tour created successfully.")
            return redirect("dashboard-tours-list", organization_slug=organization.slug)
    else:
        form = TourForm()
        form.fields["place"].queryset = Place.objects.filter(organization=organization)

    return render(
        request,
        "dashboard/tours/form.html",
        {
            "form": form,
            "page_mode": "create",
            "current_organization": organization,
        },
    )


@login_required
def tour_edit_view(request, organization_slug, tour_id):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return render(request, "403.html", status=403)

    tour = get_object_or_404(Tour, id=tour_id, organization=organization)

    if request.method == "POST":
        form = TourForm(request.POST, request.FILES, instance=tour)
        form.fields["place"].queryset = Place.objects.filter(organization=organization)

        if form.is_valid():
            tour = form.save(commit=False)

            if not tour.slug:
                tour.slug = generate_unique_tour_slug(tour.title)

            tour.save()
            messages.success(request, "Tour updated successfully.")
            return redirect("dashboard-tours-list", organization_slug=organization.slug)
    else:
        form = TourForm(instance=tour)
        form.fields["place"].queryset = Place.objects.filter(organization=organization)

    return render(
        request,
        "dashboard/tours/form.html",
        {
            "form": form,
            "tour": tour,
            "page_mode": "edit",
            "current_organization": organization,
        },
    )


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


@login_required
def tour_preview_view(request, organization_slug, tour_id):
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
            "hotspots": [
                {
                    "id": hotspot.id,
                    "type": hotspot.type,
                    "label": hotspot.label,
                    "yaw": hotspot.yaw,
                    "pitch": hotspot.pitch,
                    "target_scene": hotspot.target_scene_id,
                    "title": hotspot.title,
                    "description": hotspot.description,
                }
                for hotspot in scene.hotspots.all()
            ],
        }
        for scene in scenes
    ]

    return render(
        request,
        "dashboard/tours/preview.html",
        {
            "tour": tour,
            "scenes_json": scenes_payload,
            "current_organization": organization,
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
def delete_hotspot_ajax_view(request, organization_slug, hotspot_id):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return JsonResponse({"detail": "Forbidden"}, status=403)

    hotspot = get_object_or_404(Hotspot, id=hotspot_id, organization=organization)
    tour = hotspot.scene.tour
    hotspot.delete()

    build_tour_manifest(tour)
    return JsonResponse({"success": True})
