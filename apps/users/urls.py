from django.urls import path
from . import views

app_name = "users"

urlpatterns = [
    path("me/", views.MeView.as_view(), name="me"),
    path("auth/email/login/", views.email_login, name="email_login"),
    path("auth/email/register/", views.email_register, name="email_register"),
    path("auth/logout/", views.session_logout, name="logout"),
]

account_urlpatterns = [
    path("google/start/", views.google_start, name="google_start"),
    path("google/callback/", views.google_callback, name="google_callback"),
]
