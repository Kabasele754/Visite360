from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.forms import ModelForm
from django.shortcuts import get_object_or_404, redirect, render

from .models import Organization, OrganizationMember
from .selectors import get_user_organizations


class OrganizationForm(ModelForm):
    class Meta:
        model = Organization
        fields = ["name", "slug", "status"]


@login_required
def organization_list_view(request):
    organizations = get_user_organizations(request.user)
    return render(
        request,
        "dashboard/organizations/list.html",
        {
            "organizations": organizations,
            "current_organization": None,
        },
    )


@login_required
def organization_create_view(request):
    if request.method == "POST":
        form = OrganizationForm(request.POST)
        if form.is_valid():
            organization = form.save()

            OrganizationMember.objects.get_or_create(
                organization=organization,
                user=request.user,
                defaults={"role": OrganizationMember.Role.OWNER, "is_active": True},
            )

            messages.success(request, "Organization created successfully.")
            return redirect("dashboard-organizations-list")
    else:
        form = OrganizationForm()

    return render(
        request,
        "dashboard/organizations/form.html",
        {
            "form": form,
            "page_mode": "create",
            "current_organization": None,
        },
    )


@login_required
def organization_edit_view(request, organization_slug):
    organization = get_object_or_404(Organization, slug=organization_slug)

    if not request.user.is_superuser:
        membership = organization.memberships.filter(user=request.user, is_active=True).first()
        if not membership:
            return render(request, "403.html", status=403)

    if request.method == "POST":
        form = OrganizationForm(request.POST, instance=organization)
        if form.is_valid():
            form.save()
            messages.success(request, "Organization updated successfully.")
            return redirect("dashboard-organizations-list")
    else:
        form = OrganizationForm(instance=organization)

    return render(
        request,
        "dashboard/organizations/form.html",
        {
            "form": form,
            "page_mode": "edit",
            "organization": organization,
            "current_organization": organization,
        },
    )


@login_required
def organization_delete_view(request, organization_slug):
    organization = get_object_or_404(Organization, slug=organization_slug)

    if not request.user.is_superuser:
        membership = organization.memberships.filter(user=request.user, is_active=True).first()
        if not membership or membership.role != OrganizationMember.Role.OWNER:
            return render(request, "403.html", status=403)

    if request.method == "POST":
        organization.delete()
        messages.success(request, "Organization deleted successfully.")
        return redirect("dashboard-organizations-list")

    return render(
        request,
        "dashboard/organizations/delete.html",
        {
            "organization": organization,
            "current_organization": organization,
        },
    )