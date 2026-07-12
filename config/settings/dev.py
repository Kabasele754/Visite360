from .base import *

import os
from decouple import config, Csv


# =========================================================
# DEBUG / HOSTS
# =========================================================

DEBUG = True

import os
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS",
    default="127.0.0.1,localhost,twinscopes.com,www.twinscopes.com",
    cast=Csv(),
)


# =========================================================
# CSRF / CORS LOCAL
# =========================================================

CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS_LOCAL",
    default="http://localhost:8000,http://127.0.0.1:8000",
    cast=Csv(),
)

CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS_LOCAL",
    default="http://localhost:8000,http://127.0.0.1:8000",
    cast=Csv(),
)

CORS_ALLOW_CREDENTIALS = True


# =========================================================
# SECURITY LOCAL
# =========================================================

SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

SECURE_SSL_REDIRECT = False

X_FRAME_OPTIONS = "SAMEORIGIN"


# =========================================================
# CSP LOCAL POUR GOOGLE MAPS / MARZIPANO / IMAGES 360
# =========================================================

CSP_HEADER = {
    "default-src": [
        "'self'",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],

    "script-src": [
        "'self'",
        "'unsafe-inline'",
        "'unsafe-eval'",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "https://maps.googleapis.com",
        "https://maps.gstatic.com",
        "https://cdn.jsdelivr.net",
        "https://unpkg.com",
        "https://cdnjs.cloudflare.com",
    ],

    "style-src": [
        "'self'",
        "'unsafe-inline'",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "https://fonts.googleapis.com",
        "https://cdn.jsdelivr.net",
        "https://unpkg.com",
        "https://cdnjs.cloudflare.com",
    ],

    "img-src": [
        "'self'",
        "data:",
        "blob:",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
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
        "http://localhost:8000",
        "http://127.0.0.1:8000",
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
# DATABASE LOCAL SQLITE
# =========================================================

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


# =========================================================
# STATIC / MEDIA LOCAL
# =========================================================

STATIC_URL = config("STATIC_URL", default="/static/")

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "static"),
]

MEDIA_URL = config("MEDIA_URL", default="/media/")
MEDIA_ROOT = os.path.join(BASE_DIR, "media")


# =========================================================
# GOOGLE MAPS FRONTEND
# =========================================================

GOOGLE_MAPS_BROWSER_KEY = config("GOOGLE_MAPS_BROWSER_KEY", default="")


# =========================================================
# GOOGLE STREET VIEW PUBLISH API LOCAL
# =========================================================

GOOGLE_STREETVIEW_CLIENT_ID = config("GOOGLE_STREETVIEW_CLIENT_ID", default="")
GOOGLE_STREETVIEW_CLIENT_SECRET = config("GOOGLE_STREETVIEW_CLIENT_SECRET", default="")

GOOGLE_STREETVIEW_SCOPE = config(
    "GOOGLE_STREETVIEW_SCOPE",
    default="https://www.googleapis.com/auth/streetviewpublish",
)

GOOGLE_STREETVIEW_REDIRECT_URI = config(
    "GOOGLE_STREETVIEW_REDIRECT_URI_LOCAL",
    default="http://localhost:8000/apis/streetview/oauth/callback/",
)


# =========================================================
# SITE URL LOCAL
# =========================================================

SITE_URL = config("SITE_URL_LOCAL", default="http://localhost:8000")

