from rest_framework.permissions import BasePermission
from apps.organizations.selectors import get_user_membership


class CanManageOrganizationPlace(BasePermission):
    allowed_roles = {"owner", "manager", "editor"}

    def has_permission(self, request, view):
        org_slug = view.kwargs.get("organization_slug")

        if request.user.is_superuser:
            return True

        if not org_slug:
            return False

        membership = get_user_membership(request.user, org_slug)
        return bool(membership and membership.role in self.allowed_roles)
    
    