import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

# Django must initialize its app registry before importing websocket consumers,
# because the routing modules import models.
django_asgi_application = get_asgi_application()

from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402

from apps.ai_chat.routing import (  # noqa: E402
    websocket_urlpatterns as ai_chat_websocket_urlpatterns,
)
from apps.public.routing import (  # noqa: E402
    websocket_urlpatterns as public_websocket_urlpatterns,
)

websocket_urlpatterns = [
    *public_websocket_urlpatterns,
    *ai_chat_websocket_urlpatterns,
]

application = ProtocolTypeRouter(
    {
        "http": django_asgi_application,
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        ),
    }
)
