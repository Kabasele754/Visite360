import json

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from apps.organizations.selectors import get_user_membership
from .models import Tour


from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from apps.organizations.models import Organization
from apps.organizations.selectors import get_user_membership

from .models import Tour


def _get_org_or_403(request, organization_slug):
    organization = get_object_or_404(Organization, slug=organization_slug)

    if request.user.is_superuser:
        return organization

    membership = get_user_membership(request.user, organization_slug)
    if not membership:
        return None

    return organization


@login_required
def tour_list_view(request, organization_slug):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return render(request, "403.html", status=403)

    tours = Tour.objects.filter(organization=organization).select_related("place").order_by("-created_at")

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
def tour_builder_view(request, organization_slug, tour_id):
    membership = get_user_membership(request.user, organization_slug)

    if not membership and not request.user.is_superuser:
        return render(request, "403.html", status=403)

    tour = get_object_or_404(
        Tour.objects.select_related("place", "organization").prefetch_related("scenes"),
        id=tour_id,
        organization__slug=organization_slug,
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
        }
        for scene in scenes
    ]

    context = {
        "tour": tour,
        "scenes": scenes,
        "scenes_json": scenes_payload,
        "organization_slug": organization_slug,
    }
    return render(request, "dashboard/tours/builder.html", context)