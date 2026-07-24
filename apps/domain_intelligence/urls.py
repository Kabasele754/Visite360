from django.urls import path

from .views import public_discovery_search, public_healthcare_appointment

app_name = "domain_intelligence"

urlpatterns = [
    path("search/", public_discovery_search, name="public-discovery-search"),
    path("healthcare/appointments/", public_healthcare_appointment, name="public-healthcare-appointment"),
]
