from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),

    path("api/auth/login/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    
    path("", include("apps.organizations.dashboard_urls")),
path("", include("apps.places.dashboard_urls")),
path("", include("apps.tours.dashboard_urls")),

    path("api/", include("apps.users.urls")),
    path("api/", include("apps.organizations.urls")),
    path("api/", include("apps.places.urls")),
    path("api/", include("apps.tours.urls")),
    path("api/", include("apps.maps_explorer.urls")),
    path("api/", include("apps.leads.urls")),
    path("api/", include("apps.bookings.urls")),
    path("api/", include("apps.analytics.urls")),

    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

