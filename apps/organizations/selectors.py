from .models import Organization, OrganizationMember


def get_user_organizations(user):
    if user.is_superuser:
        return Organization.objects.all()
    return Organization.objects.filter(memberships__user=user, memberships__is_active=True).distinct()


def get_user_membership(user, organization_slug):
    return OrganizationMember.objects.select_related("organization").filter(
        user=user,
        organization__slug=organization_slug,
        is_active=True,
    ).first()