from .base import *

import os
from decouple import Csv, config


DEBUG = True
os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS_DEV",
    default="127.0.0.1,localhost",
    cast=Csv(),
)

CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS_DEV",
    default="http://localhost:8000,http://127.0.0.1:8000",
    cast=Csv(),
)
CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS_DEV",
    default="http://localhost:8000,http://127.0.0.1:8000",
    cast=Csv(),
)
CORS_ALLOW_CREDENTIALS = True

SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_SSL_REDIRECT = False
X_FRAME_OPTIONS = "SAMEORIGIN"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "twinscopes-dev",
    }
}

STATIC_ROOT = BASE_DIR / "staticfiles-dev"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

SITE_URL = config("SITE_URL_DEV", default="http://localhost:8000")
GOOGLE_STREETVIEW_REDIRECT_URI = config(
    "GOOGLE_STREETVIEW_REDIRECT_URI_DEV",
    default=f"{SITE_URL}/apis/streetview/oauth/callback/",
)

# Stripe development/test mode.
STRIPE_MODE = "test"
STRIPE_PUBLISHABLE_KEY = config(
    "STRIPE_PUBLISHABLE_KEY_TEST",
    default=config("STRIPE_PUBLISHABLE_KEY", default=""),
)
STRIPE_SECRET_KEY = config(
    "STRIPE_SECRET_KEY_TEST",
    default=config("STRIPE_SECRET_KEY", default=""),
)
STRIPE_WEBHOOK_SECRET = config(
    "STRIPE_WEBHOOK_SECRET_TEST",
    default=config("STRIPE_WEBHOOK_SECRET", default=""),
)
STRIPE_ENABLED = bool(STRIPE_PUBLISHABLE_KEY and STRIPE_SECRET_KEY)

# PayPal development/sandbox mode.
PAYPAL_MODE = "sandbox"
PAYPAL_CLIENT_ID = config(
    "PAYPAL_CLIENT_ID_TEST",
    default=config("PAYPAL_CLIENT_ID", default=""),
)
PAYPAL_SECRET = config(
    "PAYPAL_SECRET_TEST",
    default=config("PAYPAL_SECRET", default=""),
)
PAYPAL_WEBHOOK_ID = config(
    "PAYPAL_WEBHOOK_ID_TEST",
    default=config("PAYPAL_WEBHOOK_ID", default=""),
)
PAYPAL_API_BASE_URL = "https://api-m.sandbox.paypal.com"
PAYPAL_ENABLED = bool(PAYPAL_CLIENT_ID and PAYPAL_SECRET)

PAYPAL_RETURN_URL = config(
    "PAYPAL_RETURN_URL_DEV",
    default=f"{SITE_URL}/payments/paypal/return/",
)
PAYPAL_CANCEL_URL = config(
    "PAYPAL_CANCEL_URL_DEV",
    default=f"{SITE_URL}/payments/paypal/cancel/",
)

# Local CSP definition used by your existing middleware, if enabled.
CSP_HEADER = {
    "default-src": ["'self'", "http://localhost:8000", "http://127.0.0.1:8000"],
    "script-src": [
        "'self'", "'unsafe-inline'", "'unsafe-eval'",
        "https://js.stripe.com",
        "https://www.paypal.com",
        "https://www.sandbox.paypal.com",
        "https://maps.googleapis.com",
        "https://maps.gstatic.com",
        "https://tile.googleapis.com",
        "https://*.googleapis.com",
        "https://cdn.jsdelivr.net",
        "https://unpkg.com",
        "https://cdnjs.cloudflare.com",
    ],
    "style-src": [
        "'self'", "'unsafe-inline'",
        "https://fonts.googleapis.com",
        "https://cdn.jsdelivr.net",
        "https://unpkg.com",
        "https://cdnjs.cloudflare.com",
    ],
    "img-src": [
        "'self'", "data:", "blob:",
        "https://maps.googleapis.com",
        "https://maps.gstatic.com",
        "https://streetviewpixels-pa.googleapis.com",
        "https://*.googleusercontent.com",
        "https://lh3.googleusercontent.com",
        "https://*.stripe.com",
        "https://*.paypal.com",
    ],
    "font-src": ["'self'", "data:", "https://fonts.gstatic.com", "https://cdnjs.cloudflare.com"],
    "connect-src": [
        "'self'",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "https://api.stripe.com",
        "https://api-m.sandbox.paypal.com",
        "https://maps.googleapis.com",
        "https://maps.gstatic.com",
        "https://tile.googleapis.com",
        "https://*.googleapis.com",
        "https://streetviewpublish.googleapis.com",
        "https://oauth2.googleapis.com",
        "https://accounts.google.com",
    ],
    "worker-src": ["'self'", "blob:"],
    "frame-src": [
        "'self'",
        "https:",  # verified external CRM/booking resources opened in a sandboxed modal
        "https://js.stripe.com",
        "https://hooks.stripe.com",
        "https://www.paypal.com",
        "https://www.sandbox.paypal.com",
        "https://accounts.google.com",
        "https://www.google.com",
        "https://maps.google.com",
    ],
    "media-src": ["'self'", "blob:", "data:"],
}

# Development-only fallback for semantic indexing without cloud credentials.
AI_ALLOW_DETERMINISTIC_EMBEDDINGS = True

# Organization Intelligence runs in a background thread during local development.
# This keeps runserver responsive and avoids a permanently queued dashboard run
# when Redis/Celery is not running on the developer machine.
DOMAIN_INTELLIGENCE_EXECUTION_MODE = config(
    "DOMAIN_INTELLIGENCE_EXECUTION_MODE",
    default="thread",
)
DOMAIN_INTELLIGENCE_LOCAL_THREAD_WORKERS = config(
    "DOMAIN_INTELLIGENCE_LOCAL_THREAD_WORKERS",
    default=1,
    cast=int,
)
DOMAIN_INTELLIGENCE_STALE_QUEUE_SECONDS = config(
    "DOMAIN_INTELLIGENCE_STALE_QUEUE_SECONDS",
    default=20,
    cast=int,
)

# Keep Celery asynchronous unless explicitly enabled for a focused test.
CELERY_TASK_ALWAYS_EAGER = config("CELERY_TASK_ALWAYS_EAGER", default=False, cast=bool)
CELERY_TASK_EAGER_PROPAGATES = True

# Reduce transient SQLite lock errors while the local collector updates progress
# and the browser polls the run status at the same time.
DATABASES["default"].setdefault("OPTIONS", {})["timeout"] = 30
