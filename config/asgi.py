import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

from apps.public.routing import websocket_urlpatterns as public_websocket_urlpatterns
from apps.ai_chat.routing import websocket_urlpatterns as ai_chat_websocket_urlpatterns

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.prod')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(public_websocket_urlpatterns + ai_chat_websocket_urlpatterns)  # 👈 plus vide !
    ),
})
