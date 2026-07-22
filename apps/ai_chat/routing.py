from django.urls import re_path
from apps.ai_chat.consumers import EnterpriseChatConsumer

websocket_urlpatterns = [
    re_path(r"^ws/enterprise/chat/(?P<conversation_id>[0-9a-f-]+)/$", EnterpriseChatConsumer.as_asgi()),
]
