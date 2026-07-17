from django.urls import path

from apps.public.seo import product_sitemap, robots_txt, sitemap_index, static_sitemap, tour_sitemap
from apps.public.views import PublicAboutView, PublicContactView, PublicHomeView, PublicServicesView, PublicTourEngagementView, public_tours_map_view, test_view

urlpatterns = [
    path("sitemap.xml", sitemap_index, name="sitemap-index"),
    path("sitemap-static.xml", static_sitemap, name="sitemap-static"),
    path("sitemap-products.xml", product_sitemap, name="sitemap-products"),
    path("sitemap-tours.xml", tour_sitemap, name="sitemap-tours"),
    path("robots.txt", robots_txt, name="robots-txt"),
    path("", PublicHomeView.as_view(), name="public_home"),
     path(
        "explorer/",
        public_tours_map_view,
        name="public-tours-map",
    ),
     
     path(
        "api/public/tours/<slug:organization_slug>/<int:tour_id>/engagement/",
        PublicTourEngagementView.as_view(),
        name="tour-public-engagement",
    ),
     
     path("about/", PublicAboutView.as_view(), name="public_about"),
    path("services/", PublicServicesView.as_view(), name="public_services"),
    path("contact/", PublicContactView.as_view(), name="public_contact"),
    path("tours-map/", public_tours_map_view, name="public_tours_map"),
    
     path("test/", test_view, name="test"),
    
    
]