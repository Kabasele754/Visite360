from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView



def health_check(request):
    return JsonResponse({
        "status": "ok",
        "service": "twinscopes",
    })

urlpatterns = [
    path("health/", health_check, name="health-check"),
    path("admin/", admin.site.urls),

    path("api/auth/login/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("", include("apps.public.urls")),
    
    path("", include("apps.organizations.dashboard_urls")),
    path("", include("apps.places.dashboard_urls")),
    path("", include("apps.tours.dashboard_urls")),
    path("", include("apps.vendors.urls")),
    path("", include("apps.vendors.dashboard_urls")),
    path("", include("apps.growth_ai.urls")),
    path("", include("apps.monitoring.dashboard_urls")),
    path("api/tour-ai/", include("apps.tour_ai_agent.urls")),
    path("api/enterprise/ai/", include("apps.ai_core.urls")),
    path("api/enterprise/knowledge/", include("apps.knowledge.urls")),
    path("api/enterprise/vision/", include("apps.vision_ai.urls")),
    path("api/enterprise/agents/", include("apps.ai_agents.urls")),
    path("api/enterprise/chat/", include("apps.ai_chat.urls")),
    path("api/enterprise/integrations/", include("apps.integrations.urls")),
    path("api/enterprise/monitoring/", include("apps.monitoring.urls")),

    path("api/", include("apps.users.urls")),
    path("accounts/", include("apps.users.account_urls")),
    path("api/", include("apps.organizations.urls")),
    path("api/", include("apps.places.urls")),
    path("api/", include("apps.tours.urls")),
    path("apis/public/", include("apps.tours.api.urls")),
    path("api/", include("apps.maps_explorer.urls")),
    path("api/", include("apps.leads.urls")),
    path("api/", include("apps.bookings.urls")),
    path("api/", include("apps.analytics.urls")),
    
    path("apis/streetview/", include("apps.app_streetview.urls")),

    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


handler400 = 'apps.public.views.custom_bad_request'
handler403 = 'apps.public.views.custom_permission_denied'
handler404 = 'apps.public.views.custom_page_not_found'
handler500 = 'apps.public.views.custom_server_error'