from django.urls import path
from . import views
app_name="tour_ai_agent"
urlpatterns=[
 path("bootstrap/",views.bootstrap,name="bootstrap"),
 path("message/",views.message,name="message"),
 path("signal/",views.signal,name="signal"),
 path("action/",views.action,name="action"),
 path("scene/<int:scene_id>/analyze/",views.analyze_scene_now,name="analyze-scene"),
]
