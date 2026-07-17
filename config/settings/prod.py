from .base import *

from django.core.exceptions import ImproperlyConfigured
from decouple import Csv, config


DEBUG = False

if SECRET_KEY == "unsafe-dev-key":
    raise ImproperlyConfigured("SECRET_KEY must be configured in production.")

ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS",
    default="twinscopes.com,www.twinscopes.com,api.twinscopes.com",
    cast=Csv(),
)

CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS",
    default="https://twinscopes.com,https://www.twinscopes.com,https://api.twinscopes.com",
    cast=Csv(),
)
CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="https://twinscopes.com,https://www.twinscopes.com,https://api.twinscopes.com",
    cast=Csv(),
)
CORS_ALLOW_CREDENTIALS = True

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=False, cast=bool)
SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=31536000, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "SAMEORIGIN"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("DB_NAME", default="elevateaidb"),
        "USER": config("DB_USER", default="elevateaiuser"),
        "PASSWORD": read_secret("DB_PASS", config("DB_PASS", default="")),
        "HOST": config("DB_HOST", default="db"),
        "PORT": config("DB_PORT", default="5432"),
        "CONN_MAX_AGE": config("DB_CONN_MAX_AGE", default=60, cast=int),
        "OPTIONS": {
            "connect_timeout": config("DB_CONNECT_TIMEOUT", default=10, cast=int),
        },
    }
}

STATIC_ROOT = config("STATIC_ROOT", default="/app/staticfiles")
MEDIA_ROOT = config("MEDIA_ROOT", default="/app/media")
COMPRESS_ROOT = STATIC_ROOT

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage",
    },
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": config(
            "CACHE_URL",
            default=f"{REDIS_BASE_URL}/{REDIS_DB_CACHE}",
        ),
        "TIMEOUT": config("CACHE_DEFAULT_TIMEOUT", default=300, cast=int),
        "KEY_PREFIX": "twinscopes",
    }
}

SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"

EMAIL_BACKEND = config(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = config("EMAIL_HOST", default="")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = read_secret("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)

SITE_URL = config("SITE_URL", default="https://twinscopes.com").rstrip("/")
GOOGLE_STREETVIEW_REDIRECT_URI = config(
    "GOOGLE_STREETVIEW_REDIRECT_URI",
    default=f"{SITE_URL}/apis/streetview/oauth/callback/",
)

# Stripe production mode.
STRIPE_MODE = config("STRIPE_MODE", default="live").strip().lower()
if STRIPE_MODE not in {"test", "live"}:
    raise ImproperlyConfigured("STRIPE_MODE must be 'test' or 'live'.")

if STRIPE_MODE == "live":
    STRIPE_PUBLISHABLE_KEY = config("STRIPE_PUBLISHABLE_KEY_LIVE", default="")
    STRIPE_SECRET_KEY = read_secret("STRIPE_SECRET_KEY_LIVE", "")
    STRIPE_WEBHOOK_SECRET = read_secret("STRIPE_WEBHOOK_SECRET_LIVE", "")
else:
    STRIPE_PUBLISHABLE_KEY = config("STRIPE_PUBLISHABLE_KEY_TEST", default="")
    STRIPE_SECRET_KEY = read_secret("STRIPE_SECRET_KEY_TEST", "")
    STRIPE_WEBHOOK_SECRET = read_secret("STRIPE_WEBHOOK_SECRET_TEST", "")

STRIPE_ENABLED = bool(STRIPE_PUBLISHABLE_KEY and STRIPE_SECRET_KEY)

# PayPal production mode.
PAYPAL_MODE = config("PAYPAL_MODE", default="live").strip().lower()
if PAYPAL_MODE not in {"sandbox", "live"}:
    raise ImproperlyConfigured("PAYPAL_MODE must be 'sandbox' or 'live'.")

if PAYPAL_MODE == "live":
    PAYPAL_CLIENT_ID = config("PAYPAL_CLIENT_ID_LIVE", default="")
    PAYPAL_SECRET = read_secret("PAYPAL_SECRET_LIVE", "")
    PAYPAL_WEBHOOK_ID = config("PAYPAL_WEBHOOK_ID_LIVE", default="")
    PAYPAL_API_BASE_URL = "https://api-m.paypal.com"
else:
    PAYPAL_CLIENT_ID = config("PAYPAL_CLIENT_ID_TEST", default="")
    PAYPAL_SECRET = read_secret("PAYPAL_SECRET_TEST", "")
    PAYPAL_WEBHOOK_ID = config("PAYPAL_WEBHOOK_ID_TEST", default="")
    PAYPAL_API_BASE_URL = "https://api-m.sandbox.paypal.com"

PAYPAL_ENABLED = bool(PAYPAL_CLIENT_ID and PAYPAL_SECRET)
PAYPAL_RETURN_URL = config(
    "PAYPAL_RETURN_URL",
    default=f"{SITE_URL}/payments/paypal/return/",
)
PAYPAL_CANCEL_URL = config(
    "PAYPAL_CANCEL_URL",
    default=f"{SITE_URL}/payments/paypal/cancel/",
)

if PAYMENTS_REQUIRE_PROVIDER and not (STRIPE_ENABLED or PAYPAL_ENABLED or PAYMENTS_ALLOW_MANUAL):
    raise ImproperlyConfigured(
        "No payment provider is configured. Configure Stripe, PayPal, "
        "or enable PAYMENTS_ALLOW_MANUAL."
    )

# Production CSP definition used by your existing middleware, if enabled.
CSP_HEADER = {
    "default-src": ["'self'", SITE_URL],
    "script-src": [
        "'self'", "'unsafe-inline'", "'unsafe-eval'",
        "https://js.stripe.com",
        "https://www.paypal.com",
        "https://www.paypalobjects.com",
        "https://maps.googleapis.com",
        "https://maps.gstatic.com",
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
        "https://*.paypalobjects.com",
    ],
    "font-src": ["'self'", "data:", "https://fonts.gstatic.com", "https://cdnjs.cloudflare.com"],
    "connect-src": [
        "'self'",
        SITE_URL,
        "https://api.stripe.com",
        "https://api-m.paypal.com",
        "https://api-m.sandbox.paypal.com",
        "https://maps.googleapis.com",
        "https://maps.gstatic.com",
        "https://streetviewpublish.googleapis.com",
        "https://oauth2.googleapis.com",
        "https://accounts.google.com",
    ],
    "worker-src": ["'self'", "blob:"],
    "frame-src": [
        "'self'",
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

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "{levelname} {asctime} {name} {message}}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": config("DJANGO_LOG_LEVEL", default="INFO"),
    },
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "apps.vendors": {
            "handlers": ["console"],
            "level": config("PAYMENTS_LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
    },
}
