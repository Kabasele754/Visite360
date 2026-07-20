from django.urls import path
from . import views

app_name = "users_accounts"

urlpatterns = [
    path("google/start/", views.google_start, name="google_start"),
    path("google/callback/", views.google_callback, name="google_callback"),
]
