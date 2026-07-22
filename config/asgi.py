import os

from django.core.asgi import get_asgi_application

# La configuration doit être définie avant l'initialisation de Django.
os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "config.settings.prod",
)

# Django charge ici les applications, les modèles et le registre.
django_asgi_application = get_asgi_application()

# Ces imports doivent obligatoirement arriver après get_asgi_application().
from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402

from apps.public.routing import (  # noqa: E402
    websocket_urlpatterns as public_websocket_urlpatterns,
)
from apps.ai_chat.routing import (  # noqa: E402
    websocket_urlpatterns as ai_chat_websocket_urlpatterns,
)


websocket_urlpatterns = [
    *public_websocket_urlpatterns,
    *ai_chat_websocket_urlpatterns,
]


application = ProtocolTypeRouter(
    {
        "http": django_asgi_application,
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(
                URLRouter(websocket_urlpatterns)
            )
        ),
    }
)