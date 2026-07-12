from .base import *

import os
from decouple import config, Csv


# =========================================================
# DEBUG / HOSTS
# =========================================================

DEBUG = False

ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS",
    default="158.220.108.251,www.twinscopes.com,twinscopes.com,api.twinscopes.com,localhost,127.0.0.1",
    cast=Csv(),
)


# =========================================================
# CSRF / CORS
# =========================================================

CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS",
    default="https://twinscopes.com,https://www.twinscopes.com,https://api.twinscopes.com",
    cast=Csv(),
)

CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="https://twinscopes.com,https://www.twinscopes.com,https://admin.twinscopes.com,https://api.twinscopes.com",
    cast=Csv(),
)

CORS_ALLOW_CREDENTIALS = True


# =========================================================
# SECURITY PRODUCTION
# =========================================================

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SESSION_COOKIE_SECURE = config("SESSION_COOKIE_SECURE", default=True, cast=bool)
CSRF_COOKIE_SECURE = config("CSRF_COOKIE_SECURE", default=True, cast=bool)

SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=False, cast=bool)

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

X_FRAME_OPTIONS = "SAMEORIGIN"


# =========================================================
# CSP POUR GOOGLE MAPS / MARZIPANO / IMAGES 360
# =========================================================
# Si ton projet utilise ton propre middleware CSP_HEADER,
# cette variable reste compatible avec ta structure actuelle.

CSP_HEADER = {
    "default-src": [
        "'self'",
        "https://twinscopes.com",
        "https://www.twinscopes.com",
        "https://api.twinscopes.com",
    ],

    "script-src": [
        "'self'",
        "'unsafe-inline'",
        "'unsafe-eval'",
        "https://twinscopes.com",
        "https://www.twinscopes.com",
        "https://api.twinscopes.com",
        "https://maps.googleapis.com",
        "https://maps.gstatic.com",
        "https://cdn.jsdelivr.net",
        "https://unpkg.com",
        "https://cdnjs.cloudflare.com",
    ],

    "style-src": [
        "'self'",
        "'unsafe-inline'",
        "https://twinscopes.com",
        "https://www.twinscopes.com",
        "https://api.twinscopes.com",
        "https://fonts.googleapis.com",
        "https://cdn.jsdelivr.net",
        "https://unpkg.com",
        "https://cdnjs.cloudflare.com",
    ],

    "img-src": [
        "'self'",
        "data:",
        "blob:",
        "https://twinscopes.com",
        "https://www.twinscopes.com",
        "https://api.twinscopes.com",
        "https://maps.googleapis.com",
        "https://maps.gstatic.com",
        "https://streetviewpixels-pa.googleapis.com",
        "https://*.googleusercontent.com",
        "https://lh3.googleusercontent.com",
    ],

    "font-src": [
        "'self'",
        "data:",
        "https://fonts.gstatic.com",
        "https://cdnjs.cloudflare.com",
    ],

    "connect-src": [
        "'self'",
        "https://twinscopes.com",
        "https://www.twinscopes.com",
        "https://api.twinscopes.com",
        "https://maps.googleapis.com",
        "https://maps.gstatic.com",
        "https://streetviewpublish.googleapis.com",
        "https://oauth2.googleapis.com",
        "https://accounts.google.com",
    ],

    "worker-src": [
        "'self'",
        "blob:",
    ],

    "frame-src": [
        "'self'",
        "https://accounts.google.com",
        "https://www.google.com",
        "https://maps.google.com",
    ],

    "media-src": [
        "'self'",
        "blob:",
        "data:",
    ],
}


# =========================================================
# DATABASE PRODUCTION POSTGRESQL
# =========================================================

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("DB_NAME", default="elevateaidb"),
        "USER": config("DB_USER", default="elevateaiuser"),
        "PASSWORD": config("DB_PASS", default="elevateaipass"),
        "HOST": config("DB_HOST", default="db"),
        "PORT": config("DB_PORT", default="5432"),
    }
}


# =========================================================
# STATIC / MEDIA
# =========================================================

STATIC_URL = config("STATIC_URL", default="/static/")
STATIC_ROOT = config("STATIC_ROOT", default="/app/staticfiles")

MEDIA_URL = config("MEDIA_URL", default="/media/")
MEDIA_ROOT = config("MEDIA_ROOT", default="/app/media")

COMPRESS_ROOT = STATIC_ROOT


# =========================================================
# GOOGLE MAPS FRONTEND
# =========================================================

GOOGLE_MAPS_BROWSER_KEY = config("GOOGLE_MAPS_BROWSER_KEY", default="")


# =========================================================
# GOOGLE STREET VIEW PUBLISH API
# =========================================================

GOOGLE_STREETVIEW_CLIENT_ID = config("GOOGLE_STREETVIEW_CLIENT_ID", default="")
GOOGLE_STREETVIEW_CLIENT_SECRET = config("GOOGLE_STREETVIEW_CLIENT_SECRET", default="")

GOOGLE_STREETVIEW_SCOPE = config(
    "GOOGLE_STREETVIEW_SCOPE",
    default="https://www.googleapis.com/auth/streetviewpublish",
)

GOOGLE_STREETVIEW_REDIRECT_URI = config(
    "GOOGLE_STREETVIEW_REDIRECT_URI",
    default="https://twinscopes.com/apis/streetview/oauth/callback/",
)


# =========================================================
# SITE URL
# =========================================================

SITE_URL = config("SITE_URL", default="https://twinscopes.com")

