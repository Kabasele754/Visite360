from django.urls import path
from .views import PublicBookingRequestCreateView, OrgBookingRequestListView

urlpatterns = [
    path("public/booking-requests/", PublicBookingRequestCreateView.as_view(), name="public-booking-request-create"),
    path("admin/orgs/<slug:organization_slug>/booking-requests/", OrgBookingRequestListView.as_view(), name="org-booking-requests"),
]

