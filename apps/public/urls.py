from django.urls import path

from apps.public.views import PublicAboutView, PublicContactView, PublicHomeView, PublicServicesView, public_tours_map_view

urlpatterns = [
    path("", PublicHomeView.as_view(), name="public_home"),
     path(
        "explorer/",
        public_tours_map_view,
        name="public-tours-map",
    ),
     
     path("about/", PublicAboutView.as_view(), name="public_about"),
    path("services/", PublicServicesView.as_view(), name="public_services"),
    path("contact/", PublicContactView.as_view(), name="public_contact"),
    path("tours-map/", public_tours_map_view, name="public_tours_map"),
]