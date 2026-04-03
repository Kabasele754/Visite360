from rest_framework.permissions import BasePermission
from .selectors import get_user_membership

class IsOrganizationMember(BasePermission):
    def has_permission(self, request, view):
        org_slug = view.kwargs.get("organization_slug") or request.query_params.get("organization_slug")
        if request.user.is_superuser:
            return True
        if not org_slug:
            return False
        return get_user_membership(request.user, org_slug) is not None