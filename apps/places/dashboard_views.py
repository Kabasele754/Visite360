from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.forms import ModelForm
from django.shortcuts import get_object_or_404, redirect, render

from apps.organizations.models import Organization
from apps.organizations.selectors import get_user_membership

from .models import Place
from .services import generate_unique_place_slug, publish_place, unpublish_place, archive_place


class PlaceForm(ModelForm):
    class Meta:
        model = Place
        fields = [
            "name",
            "slug",
            "category",
            "description",
            "address_line",
            "city",
            "country",
            "latitude",
            "longitude",
            "cover_image",
            "status",
        ]


def _get_org_or_403(request, organization_slug):
    organization = get_object_or_404(Organization, slug=organization_slug)

    if request.user.is_superuser:
        return organization

    membership = get_user_membership(request.user, organization_slug)
    if not membership:
        return None

    return organization


@login_required
def place_list_view(request, organization_slug):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return render(request, "403.html", status=403)

    places = Place.objects.filter(organization=organization).order_by("-created_at")

    return render(
        request,
        "dashboard/places/list.html",
        {
            "places": places,
            "current_organization": organization,
        },
    )


@login_required
def place_create_view(request, organization_slug):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return render(request, "403.html", status=403)

    if request.method == "POST":
        form = PlaceForm(request.POST)
        if form.is_valid():
            place = form.save(commit=False)
            place.organization = organization

            if not place.slug:
                place.slug = generate_unique_place_slug(place.name)

            place.save()

            if place.status == Place.Status.PUBLISHED:
                publish_place(place)

            messages.success(request, "Place created successfully.")
            return redirect("dashboard-places-list", organization_slug=organization.slug)
    else:
        form = PlaceForm()

    return render(
        request,
        "dashboard/places/form.html",
        {
            "form": form,
            "page_mode": "create",
            "current_organization": organization,
        },
    )


@login_required
def place_edit_view(request, organization_slug, place_id):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return render(request, "403.html", status=403)

    place = get_object_or_404(Place, id=place_id, organization=organization)

    if request.method == "POST":
        old_status = place.status
        form = PlaceForm(request.POST, instance=place)
        if form.is_valid():
            place = form.save(commit=False)

            if not place.slug:
                place.slug = generate_unique_place_slug(place.name)

            place.save()

            if old_status != place.status:
                if place.status == Place.Status.PUBLISHED:
                    publish_place(place)
                elif place.status == Place.Status.DRAFT:
                    unpublish_place(place)
                elif place.status == Place.Status.ARCHIVED:
                    archive_place(place)

            messages.success(request, "Place updated successfully.")
            return redirect("dashboard-places-list", organization_slug=organization.slug)
    else:
        form = PlaceForm(instance=place)

    return render(
        request,
        "dashboard/places/form.html",
        {
            "form": form,
            "place": place,
            "page_mode": "edit",
            "current_organization": organization,
        },
    )


@login_required
def place_delete_view(request, organization_slug, place_id):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return render(request, "403.html", status=403)

    place = get_object_or_404(Place, id=place_id, organization=organization)

    if request.method == "POST":
        place.delete()
        messages.success(request, "Place deleted successfully.")
        return redirect("dashboard-places-list", organization_slug=organization.slug)

    return render(
        request,
        "dashboard/places/delete.html",
        {
            "place": place,
            "current_organization": organization,
        },
    )


@login_required
def place_publish_view(request, organization_slug, place_id):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return render(request, "403.html", status=403)

    place = get_object_or_404(Place, id=place_id, organization=organization)
    publish_place(place)
    messages.success(request, "Place published successfully.")
    return redirect("dashboard-places-list", organization_slug=organization.slug)


@login_required
def place_unpublish_view(request, organization_slug, place_id):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return render(request, "403.html", status=403)

    place = get_object_or_404(Place, id=place_id, organization=organization)
    unpublish_place(place)
    messages.success(request, "Place moved to draft.")
    return redirect("dashboard-places-list", organization_slug=organization.slug)


@login_required
def place_archive_view(request, organization_slug, place_id):
    organization = _get_org_or_403(request, organization_slug)
    if not organization:
        return render(request, "403.html", status=403)

    place = get_object_or_404(Place, id=place_id, organization=organization)
    archive_place(place)
    messages.success(request, "Place archived successfully.")
    return redirect("dashboard-places-list", organization_slug=organization.slug)