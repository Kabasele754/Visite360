"""
Production settings for Twinscopes.

Expected environment:
- Django behind Nginx
- HTTPS terminated by Nginx
- PostgreSQL
- Redis
- Daphne / ASGI
- Celery Worker
- Celery Beat
"""

from .base import *

from django.core.exceptions import ImproperlyConfigured
from decouple import Csv, config


# =============================================================================
# CORE
# =============================================================================

DEBUG = False

ENVIRONMENT = "production"

if not SECRET_KEY or SECRET_KEY == "unsafe-dev-key":
    raise ImproperlyConfigured(
        "SECRET_KEY must be configured with a strong production value."
    )


# =============================================================================
# HOSTS AND ORIGINS
# =============================================================================

ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS",
    default=(
        "twinscopes.com,"
        "www.twinscopes.com,"
        "api.twinscopes.com"
    ),
    cast=Csv(),
)

CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS",
    default=(
        "https://twinscopes.com,"
        "https://www.twinscopes.com,"
        "https://api.twinscopes.com"
    ),
    cast=Csv(),
)

CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default=(
        "https://twinscopes.com,"
        "https://www.twinscopes.com,"
        "https://api.twinscopes.com"
    ),
    cast=Csv(),
)

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_ALL_ORIGINS = False


# Organization intelligence is executed by the dedicated AI Celery worker in production.
DOMAIN_INTELLIGENCE_EXECUTION_MODE = config(
    "DOMAIN_INTELLIGENCE_EXECUTION_MODE",
    default="celery",
)
DOMAIN_INTELLIGENCE_CELERY_QUEUE = config(
    "DOMAIN_INTELLIGENCE_CELERY_QUEUE",
    default="ai",
)
DOMAIN_INTELLIGENCE_STALE_QUEUE_SECONDS = config(
    "DOMAIN_INTELLIGENCE_STALE_QUEUE_SECONDS",
    default=120,
    cast=int,
)

# =============================================================================
# SITE
# =============================================================================

SITE_URL = config(
    "SITE_URL",
    default="https://twinscopes.com",
).rstrip("/")

SITE_DOMAIN = config(
    "SITE_DOMAIN",
    default="twinscopes.com",
)


# =============================================================================
# HTTPS AND PROXY SECURITY
# =============================================================================

# Nginx must send:
# proxy_set_header X-Forwarded-Proto $scheme;
SECURE_PROXY_SSL_HEADER = (
    "HTTP_X_FORWARDED_PROTO",
    "https",
)

USE_X_FORWARDED_HOST = True

SECURE_SSL_REDIRECT = config(
    "SECURE_SSL_REDIRECT",
    default=True,
    cast=bool,
)

SECURE_HSTS_SECONDS = config(
    "SECURE_HSTS_SECONDS",
    default=31536000,
    cast=int,
)

SECURE_HSTS_INCLUDE_SUBDOMAINS = config(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS",
    default=True,
    cast=bool,
)

SECURE_HSTS_PRELOAD = config(
    "SECURE_HSTS_PRELOAD",
    default=True,
    cast=bool,
)

SECURE_CONTENT_TYPE_NOSNIFF = True

SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

X_FRAME_OPTIONS = "SAMEORIGIN"


# =============================================================================
# COOKIES
# =============================================================================

SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

CSRF_COOKIE_SECURE = True

# Django doit laisser le token CSRF accessible au JavaScript
# lorsque l'application l'envoie avec fetch/AJAX.
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"

SESSION_COOKIE_AGE = config(
    "SESSION_COOKIE_AGE",
    default=1209600,
    cast=int,
)

SESSION_SAVE_EVERY_REQUEST = False


# =============================================================================
# DATABASE
# =============================================================================

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config(
            "DB_NAME",
            default="elevateaidb",
        ),
        "USER": config(
            "DB_USER",
            default="elevateaiuser",
        ),
        "PASSWORD": read_secret(
            "DB_PASS",
            config(
                "DB_PASS",
                default="",
            ),
        ),
        "HOST": config(
            "DB_HOST",
            default="db",
        ),
        "PORT": config(
            "DB_PORT",
            default="5432",
        ),
        "CONN_MAX_AGE": config(
            "DB_CONN_MAX_AGE",
            default=60,
            cast=int,
        ),
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {
            "connect_timeout": config(
                "DB_CONNECT_TIMEOUT",
                default=10,
                cast=int,
            ),
        },
    }
}

if not DATABASES["default"]["PASSWORD"]:
    raise ImproperlyConfigured(
        "DB_PASS must be configured in production."
    )


# =============================================================================
# REDIS CACHE
# =============================================================================

CACHES = {
    "default": {
        "BACKEND": (
            "django.core.cache.backends.redis.RedisCache"
        ),
        "LOCATION": config(
            "CACHE_URL",
            default=f"{REDIS_BASE_URL}/{REDIS_DB_CACHE}",
        ),
        "TIMEOUT": config(
            "CACHE_DEFAULT_TIMEOUT",
            default=300,
            cast=int,
        ),
        "KEY_PREFIX": config(
            "CACHE_KEY_PREFIX",
            default="twinscopes",
        ),
        "OPTIONS": {
            "socket_connect_timeout": 5,
            "socket_timeout": 5,
            "retry_on_timeout": True,
        },
    }
}

SESSION_ENGINE = (
    "django.contrib.sessions.backends.cached_db"
)

SESSION_CACHE_ALIAS = "default"


# =============================================================================
# STATIC AND MEDIA FILES
# =============================================================================

STATIC_ROOT = config(
    "STATIC_ROOT",
    default="/app/staticfiles",
)

MEDIA_ROOT = config(
    "MEDIA_ROOT",
    default="/app/media",
)

COMPRESS_ROOT = STATIC_ROOT

STORAGES = {
    "default": {
        "BACKEND": (
            "django.core.files.storage.FileSystemStorage"
        ),
    },
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage."
            "ManifestStaticFilesStorage"
        ),
    },
}

FILE_UPLOAD_PERMISSIONS = 0o644

FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o755

DATA_UPLOAD_MAX_MEMORY_SIZE = config(
    "DATA_UPLOAD_MAX_MEMORY_SIZE",
    default=104857600,
    cast=int,
)

FILE_UPLOAD_MAX_MEMORY_SIZE = config(
    "FILE_UPLOAD_MAX_MEMORY_SIZE",
    default=10485760,
    cast=int,
)


# =============================================================================
# EMAIL
# =============================================================================

EMAIL_BACKEND = config(
    "EMAIL_BACKEND",
    default=(
        "django.core.mail.backends.smtp."
        "EmailBackend"
    ),
)

EMAIL_HOST = config(
    "EMAIL_HOST",
    default="",
)

EMAIL_PORT = config(
    "EMAIL_PORT",
    default=587,
    cast=int,
)

EMAIL_HOST_USER = config(
    "EMAIL_HOST_USER",
    default="",
)

EMAIL_HOST_PASSWORD = read_secret(
    "EMAIL_HOST_PASSWORD",
    config(
        "EMAIL_HOST_PASSWORD",
        default="",
    ),
)

EMAIL_USE_TLS = config(
    "EMAIL_USE_TLS",
    default=True,
    cast=bool,
)

EMAIL_USE_SSL = config(
    "EMAIL_USE_SSL",
    default=False,
    cast=bool,
)

EMAIL_TIMEOUT = config(
    "EMAIL_TIMEOUT",
    default=20,
    cast=int,
)

DEFAULT_FROM_EMAIL = config(
    "DEFAULT_FROM_EMAIL",
    default=(
        "Twinscopes "
        "<noreply@twinscopes.com>"
    ),
)

SERVER_EMAIL = config(
    "SERVER_EMAIL",
    default=(
        "Twinscopes Server "
        "<server@twinscopes.com>"
    ),
)

ADMINS = [
    (
        config(
            "ADMIN_NAME",
            default="Twinscopes Admin",
        ),
        config(
            "ADMIN_EMAIL",
            default="admin@twinscopes.com",
        ),
    ),
]

MANAGERS = ADMINS


# =============================================================================
# GOOGLE CLOUD
# =============================================================================

GOOGLE_APPLICATION_CREDENTIALS = config(
    "GOOGLE_APPLICATION_CREDENTIALS",
    default="/run/secrets/google_adc.json",
)

GOOGLE_CLOUD_PROJECT = config(
    "GOOGLE_CLOUD_PROJECT",
    default="",
)

GOOGLE_CLOUD_LOCATION = config(
    "GOOGLE_CLOUD_LOCATION",
    default="us-central1",
)

GOOGLE_GENAI_USE_VERTEXAI = config(
    "GOOGLE_GENAI_USE_VERTEXAI",
    default=True,
    cast=bool,
)


# =============================================================================
# GOOGLE STREET VIEW
# =============================================================================

GOOGLE_STREETVIEW_REDIRECT_URI = config(
    "GOOGLE_STREETVIEW_REDIRECT_URI",
    default=(
        f"{SITE_URL}/apis/streetview/"
        "oauth/callback/"
    ),
)


# =============================================================================
# GROWTH AI
# =============================================================================

GROWTH_AI_ENABLED = config(
    "GROWTH_AI_ENABLED",
    default=True,
    cast=bool,
)

GOOGLE_GROWTH_REDIRECT_URI = config(
    "GOOGLE_GROWTH_REDIRECT_URI",
    default=(
        f"{SITE_URL}/growth/oauth/"
        "google/callback/"
    ),
)

GROWTH_AI_DEFAULT_LOOKBACK_DAYS = config(
    "GROWTH_AI_DEFAULT_LOOKBACK_DAYS",
    default=30,
    cast=int,
)

GROWTH_AI_EVENT_RETENTION_DAYS = config(
    "GROWTH_AI_EVENT_RETENTION_DAYS",
    default=730,
    cast=int,
)

GROWTH_AI_SYNC_RUN_RETENTION_DAYS = config(
    "GROWTH_AI_SYNC_RUN_RETENTION_DAYS",
    default=180,
    cast=int,
)


# =============================================================================
# CELERY
# =============================================================================

CELERY_TASK_ALWAYS_EAGER = False

CELERY_TASK_EAGER_PROPAGATES = False

CELERY_TASK_TRACK_STARTED = True

CELERY_TASK_ACKS_LATE = True

CELERY_TASK_REJECT_ON_WORKER_LOST = True

CELERY_WORKER_PREFETCH_MULTIPLIER = config(
    "CELERY_WORKER_PREFETCH_MULTIPLIER",
    default=1,
    cast=int,
)

CELERY_TASK_SOFT_TIME_LIMIT = config(
    "CELERY_TASK_SOFT_TIME_LIMIT",
    default=1500,
    cast=int,
)

CELERY_TASK_TIME_LIMIT = config(
    "CELERY_TASK_TIME_LIMIT",
    default=1800,
    cast=int,
)

CELERY_RESULT_EXPIRES = config(
    "CELERY_RESULT_EXPIRES",
    default=86400,
    cast=int,
)

CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

CELERY_WORKER_SEND_TASK_EVENTS = True

CELERY_TASK_SEND_SENT_EVENT = True

CELERY_TIMEZONE = TIME_ZONE

CELERY_ENABLE_UTC = True


# =============================================================================
# STRIPE
# =============================================================================

STRIPE_MODE = config(
    "STRIPE_MODE",
    default="live",
).strip().lower()

if STRIPE_MODE not in {
    "test",
    "live",
}:
    raise ImproperlyConfigured(
        "STRIPE_MODE must be 'test' or 'live'."
    )

if STRIPE_MODE == "live":
    STRIPE_PUBLISHABLE_KEY = config(
        "STRIPE_PUBLISHABLE_KEY_LIVE",
        default="",
    )

    STRIPE_SECRET_KEY = read_secret(
        "STRIPE_SECRET_KEY_LIVE",
        config(
            "STRIPE_SECRET_KEY_LIVE",
            default="",
        ),
    )

    STRIPE_WEBHOOK_SECRET = read_secret(
        "STRIPE_WEBHOOK_SECRET_LIVE",
        config(
            "STRIPE_WEBHOOK_SECRET_LIVE",
            default="",
        ),
    )

else:
    STRIPE_PUBLISHABLE_KEY = config(
        "STRIPE_PUBLISHABLE_KEY_TEST",
        default="",
    )

    STRIPE_SECRET_KEY = read_secret(
        "STRIPE_SECRET_KEY_TEST",
        config(
            "STRIPE_SECRET_KEY_TEST",
            default="",
        ),
    )

    STRIPE_WEBHOOK_SECRET = read_secret(
        "STRIPE_WEBHOOK_SECRET_TEST",
        config(
            "STRIPE_WEBHOOK_SECRET_TEST",
            default="",
        ),
    )

STRIPE_ENABLED = bool(
    STRIPE_PUBLISHABLE_KEY
    and STRIPE_SECRET_KEY
)


# =============================================================================
# PAYPAL
# =============================================================================

PAYPAL_MODE = config(
    "PAYPAL_MODE",
    default="live",
).strip().lower()

if PAYPAL_MODE not in {
    "sandbox",
    "live",
}:
    raise ImproperlyConfigured(
        "PAYPAL_MODE must be "
        "'sandbox' or 'live'."
    )

if PAYPAL_MODE == "live":
    PAYPAL_CLIENT_ID = config(
        "PAYPAL_CLIENT_ID_LIVE",
        default="",
    )

    PAYPAL_SECRET = read_secret(
        "PAYPAL_SECRET_LIVE",
        config(
            "PAYPAL_SECRET_LIVE",
            default="",
        ),
    )

    PAYPAL_WEBHOOK_ID = config(
        "PAYPAL_WEBHOOK_ID_LIVE",
        default="",
    )

    PAYPAL_API_BASE_URL = (
        "https://api-m.paypal.com"
    )

else:
    PAYPAL_CLIENT_ID = config(
        "PAYPAL_CLIENT_ID_TEST",
        default="",
    )

    PAYPAL_SECRET = read_secret(
        "PAYPAL_SECRET_TEST",
        config(
            "PAYPAL_SECRET_TEST",
            default="",
        ),
    )

    PAYPAL_WEBHOOK_ID = config(
        "PAYPAL_WEBHOOK_ID_TEST",
        default="",
    )

    PAYPAL_API_BASE_URL = (
        "https://api-m.sandbox.paypal.com"
    )

PAYPAL_ENABLED = bool(
    PAYPAL_CLIENT_ID
    and PAYPAL_SECRET
)

PAYPAL_RETURN_URL = config(
    "PAYPAL_RETURN_URL",
    default=(
        f"{SITE_URL}/payments/"
        "paypal/return/"
    ),
)

PAYPAL_CANCEL_URL = config(
    "PAYPAL_CANCEL_URL",
    default=(
        f"{SITE_URL}/payments/"
        "paypal/cancel/"
    ),
)


# =============================================================================
# PAYMENT VALIDATION
# =============================================================================

if (
    PAYMENTS_REQUIRE_PROVIDER
    and not (
        STRIPE_ENABLED
        or PAYPAL_ENABLED
        or PAYMENTS_ALLOW_MANUAL
    )
):
    raise ImproperlyConfigured(
        "No payment provider is configured. "
        "Configure Stripe, PayPal, or enable "
        "PAYMENTS_ALLOW_MANUAL."
    )


# =============================================================================
# CONTENT SECURITY POLICY
# =============================================================================

CSP_HEADER = {
    "default-src": [
        "'self'",
        SITE_URL,
    ],

    "script-src": [
        "'self'",
        "'unsafe-inline'",
        "'unsafe-eval'",
        "https://js.stripe.com",
        "https://www.paypal.com",
        "https://www.paypalobjects.com",
        "https://maps.googleapis.com",
        "https://maps.gstatic.com",
        "https://tile.googleapis.com",
        "https://*.googleapis.com",
        "https://cdn.jsdelivr.net",
        "https://unpkg.com",
        "https://cdnjs.cloudflare.com",
    ],

    "style-src": [
        "'self'",
        "'unsafe-inline'",
        "https://fonts.googleapis.com",
        "https://cdn.jsdelivr.net",
        "https://unpkg.com",
        "https://cdnjs.cloudflare.com",
    ],

    "img-src": [
        "'self'",
        "data:",
        "blob:",
        "https://maps.googleapis.com",
        "https://maps.gstatic.com",
        "https://streetviewpixels-pa.googleapis.com",
        "https://*.googleusercontent.com",
        "https://lh3.googleusercontent.com",
        "https://*.stripe.com",
        "https://*.paypal.com",
        "https://*.paypalobjects.com",
    ],

    "font-src": [
        "'self'",
        "data:",
        "https://fonts.gstatic.com",
        "https://cdnjs.cloudflare.com",
    ],

    "connect-src": [
        "'self'",
        SITE_URL,
        "https://api.stripe.com",
        "https://api-m.paypal.com",
        "https://api-m.sandbox.paypal.com",
        "https://maps.googleapis.com",
        "https://maps.gstatic.com",
        "https://tile.googleapis.com",
        "https://*.googleapis.com",
        "https://streetviewpublish.googleapis.com",
        "https://searchconsole.googleapis.com",
        "https://analyticsdata.googleapis.com",
        "https://businessprofileperformance.googleapis.com",
        "https://mybusinessaccountmanagement.googleapis.com",
        "https://mybusinessbusinessinformation.googleapis.com",
        "https://oauth2.googleapis.com",
        "https://accounts.google.com",
        "https://generativelanguage.googleapis.com",
    ],

    "worker-src": [
        "'self'",
        "blob:",
    ],

    "frame-src": [
        "'self'",
        "https://js.stripe.com",
        "https://hooks.stripe.com",
        "https://www.paypal.com",
        "https://www.sandbox.paypal.com",
        "https://accounts.google.com",
        "https://www.google.com",
        "https://maps.google.com",
        "https://www.youtube.com",
        "https://www.youtube-nocookie.com",
    ],

    "media-src": [
        "'self'",
        "blob:",
        "data:",
    ],

    "object-src": [
        "'none'",
    ],

    "base-uri": [
        "'self'",
    ],

    "form-action": [
        "'self'",
        "https://www.paypal.com",
        "https://www.sandbox.paypal.com",
    ],

    "frame-ancestors": [
        "'self'",
    ],
}


# =============================================================================
# LOGGING
# =============================================================================

DJANGO_LOG_LEVEL = config(
    "DJANGO_LOG_LEVEL",
    default="INFO",
).upper()

CELERY_LOG_LEVEL = config(
    "CELERY_LOG_LEVEL",
    default="INFO",
).upper()

GROWTH_AI_LOG_LEVEL = config(
    "GROWTH_AI_LOG_LEVEL",
    default="INFO",
).upper()

LOGGING = {
    "version": 1,

    "disable_existing_loggers": False,

    "formatters": {
        "standard": {
            "format": (
                "{levelname} "
                "{asctime} "
                "{name} "
                "pid={process:d} "
                "thread={thread:d} "
                "{message}"
            ),
            "style": "{",
        },

        "simple": {
            "format": (
                "{levelname} "
                "{name}: "
                "{message}"
            ),
            "style": "{",
        },
    },

    "handlers": {
        "console": {
            "class": (
                "logging.StreamHandler"
            ),
            "formatter": "standard",
            "level": DJANGO_LOG_LEVEL,
        },
    },

    "root": {
        "handlers": [
            "console",
        ],
        "level": DJANGO_LOG_LEVEL,
    },

    "loggers": {
        "django": {
            "handlers": [
                "console",
            ],
            "level": DJANGO_LOG_LEVEL,
            "propagate": False,
        },

        "django.request": {
            "handlers": [
                "console",
            ],
            "level": "WARNING",
            "propagate": False,
        },

        "django.security": {
            "handlers": [
                "console",
            ],
            "level": "WARNING",
            "propagate": False,
        },

        "django.db.backends": {
            "handlers": [
                "console",
            ],
            "level": "WARNING",
            "propagate": False,
        },

        "daphne": {
            "handlers": [
                "console",
            ],
            "level": DJANGO_LOG_LEVEL,
            "propagate": False,
        },

        "channels": {
            "handlers": [
                "console",
            ],
            "level": DJANGO_LOG_LEVEL,
            "propagate": False,
        },

        "celery": {
            "handlers": [
                "console",
            ],
            "level": CELERY_LOG_LEVEL,
            "propagate": False,
        },

        "apps.growth_ai": {
            "handlers": [
                "console",
            ],
            "level": GROWTH_AI_LOG_LEVEL,
            "propagate": False,
        },
    },
}