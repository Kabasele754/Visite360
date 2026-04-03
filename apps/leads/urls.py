from django.urls import path
from .views import PublicLeadCreateView, OrgLeadListView

urlpatterns = [
    path("public/leads/", PublicLeadCreateView.as_view(), name="public-lead-create"),
    path("admin/orgs/<slug:organization_slug>/leads/", OrgLeadListView.as_view(), name="org-leads"),
]