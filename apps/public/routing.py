from django.urls import re_path

from apps.public.consumers import TestConsumer


websocket_urlpatterns = [
    re_path(r"^ws/test/$", TestConsumer.as_asgi()),
]