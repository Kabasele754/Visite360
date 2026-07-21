import os
from pathlib import Path
from datetime import timedelta

from decouple import Csv, config


BASE_DIR = Path(__file__).resolve().parents[2]


def read_secret(name: str, default: str = "") -> str:
    """
    Read a secret from NAME_FILE first, then NAME.
    Compatible with Docker secrets and regular environment variables.
    """
    file_path = os.getenv(f"{name}_FILE", "").strip()
    if file_path:
        try:
            return Path(file_path).read_text(encoding="utf-8").strip()
        except OSError:
            pass
    return os.getenv(name, default).strip()


SECRET_KEY = read_secret("SECRET_KEY", config("SECRET_KEY", default="unsafe-dev-key"))
DEBUG = False  # Each environment overrides this explicitly.

INSTALLED_APPS = [
    "channels",
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt",
    "django_filters",
    "drf_spectacular",
    "apps.common",
    "apps.users",
    "apps.organizations",
    "apps.places",
    "apps.tours",
    "apps.maps_explorer",
    "apps.leads",
    "apps.bookings",
    "apps.analytics",
    "apps.public",
    "apps.app_streetview",
    "apps.vendors",
    "apps.growth_ai.apps.GrowthAIConfig",
    "apps.tour_ai_agent.apps.TourAIAgentConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

AUTH_USER_MODEL = "users.User"
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Johannesburg"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

X_FRAME_OPTIONS = "SAMEORIGIN"
SECURE_CONTENT_TYPE_NOSNIFF = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.DefaultPageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_RENDERER_CLASSES": (
        "rest_framework.renderers.JSONRenderer",
    ),
    "DEFAULT_PARSER_CLASSES": (
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
    ),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Immersive 360 API",
    "VERSION": "1.0.0",
}

GOOGLE_MAPS_API_KEY = config("GOOGLE_MAPS_API_KEY", default="")
GOOGLE_MAPS_BROWSER_KEY = config("GOOGLE_MAPS_BROWSER_KEY", default="")

REDIS_HOST = config("REDIS_HOST", default="redis")
REDIS_PORT = config("REDIS_PORT", default=6379, cast=int)
REDIS_PASSWORD = config("REDIS_PASSWORD", default="")
REDIS_DB_CACHE = config("REDIS_DB_CACHE", default=1, cast=int)
REDIS_DB_CELERY = config("REDIS_DB_CELERY", default=0, cast=int)

_redis_auth = f":{REDIS_PASSWORD}@" if REDIS_PASSWORD else ""
REDIS_BASE_URL = f"redis://{_redis_auth}{REDIS_HOST}:{REDIS_PORT}"

CELERY_ENABLE_UTC = True
CELERY_TIMEZONE = TIME_ZONE
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_BROKER_URL = config(
    "CELERY_BROKER_URL",
    default=f"{REDIS_BASE_URL}/{REDIS_DB_CELERY}",
)
CELERY_RESULT_BACKEND = config(
    "CELERY_RESULT_BACKEND",
    default=f"{REDIS_BASE_URL}/{REDIS_DB_CELERY}",
)
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 60 * 20
CELERY_TASK_SOFT_TIME_LIMIT = 60 * 18
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [f"{REDIS_BASE_URL}/{REDIS_DB_CELERY}"],
        },
    },
}

STREETVIEW_PUBLISH_USE_CELERY = True
TOURS_AUTO_QUEUE_SCENE_PIPELINE = True
TOURS_AUTO_QUEUE_TOUR_ASSETS = True
TOURS_AUTO_QUEUE_PUBLISH_EMAIL = True
TOURS_GENERATE_TILES_ON_SAVE = False

DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="no-reply@twinscopes.com")
SERVER_EMAIL = config("SERVER_EMAIL", default=DEFAULT_FROM_EMAIL)

# ---------------------------------------------------------------------
# Payments: environment-specific files choose test/live credentials.
# ---------------------------------------------------------------------
STRIPE_MODE = "test"
STRIPE_PUBLISHABLE_KEY = ""
STRIPE_SECRET_KEY = ""
STRIPE_WEBHOOK_SECRET = ""
STRIPE_ENABLED = False

PAYPAL_MODE = "sandbox"
PAYPAL_CLIENT_ID = ""
PAYPAL_SECRET = ""
PAYPAL_WEBHOOK_ID = ""
PAYPAL_API_BASE_URL = "https://api-m.sandbox.paypal.com"
PAYPAL_ENABLED = False

PAYMENTS_ALLOW_MANUAL = config("PAYMENTS_ALLOW_MANUAL", default=True, cast=bool)
PAYMENTS_CURRENCY = config("PAYMENTS_CURRENCY", default="USD").upper()
PAYMENTS_REQUIRE_PROVIDER = config("PAYMENTS_REQUIRE_PROVIDER", default=False, cast=bool)

# ---------------------------------------------------------------------
# Gemini / Vertex AI
# ---------------------------------------------------------------------
GEMINI_API_KEY = config("GEMINI_API_KEY", default="")
DEFAULT_AI_IMAGE_PROVIDER = config(
    "DEFAULT_AI_IMAGE_PROVIDER",
    default="GOOGLE_VERTEX",
)
GOOGLE_GENAI_USE_VERTEXAI = config(
    "GOOGLE_GENAI_USE_VERTEXAI",
    default=True,
    cast=bool,
)
GOOGLE_CLOUD_PROJECT = config(
    "GOOGLE_CLOUD_PROJECT",
    default="ziarama-wedding-akk",
)
GOOGLE_CLOUD_LOCATION = config(
    "GOOGLE_CLOUD_LOCATION",
    default="us-central1",
)
GOOGLE_TEXT_MODEL = config(
    "GOOGLE_TEXT_MODEL",
    default="gemini-2.5-flash",
)
GEMINI_MARKET_MODEL = config(
    "GEMINI_MARKET_MODEL",
    default=GOOGLE_TEXT_MODEL,
)


GOOGLE_IMAGE_MODEL = config(
    "GOOGLE_IMAGE_MODEL",
    default="imagen-4.0-generate-001",
)
GEMINI_IMAGE_MODEL = config(
    "GEMINI_IMAGE_MODEL",
    default="gemini-2.5-flash-image",
)
AI_ENABLED = bool(
    (GOOGLE_GENAI_USE_VERTEXAI and GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_LOCATION)
    or GEMINI_API_KEY
)

GOOGLE_STREETVIEW_CLIENT_ID = config("GOOGLE_STREETVIEW_CLIENT_ID", default="")
GOOGLE_STREETVIEW_CLIENT_SECRET = config("GOOGLE_STREETVIEW_CLIENT_SECRET", default="")
GOOGLE_STREETVIEW_SCOPE = config(
    "GOOGLE_STREETVIEW_SCOPE",
    default="https://www.googleapis.com/auth/streetviewpublish",
)

SITE_URL = "http://localhost:8000"



# ---------------------------------------------------------------------
# Growth AI — external data-source credentials
# ---------------------------------------------------------------------

GOOGLE_GROWTH_CLIENT_ID = config(
    "GOOGLE_GROWTH_CLIENT_ID",
    default="",
)

GOOGLE_GROWTH_CLIENT_SECRET = read_secret(
    "GOOGLE_GROWTH_CLIENT_SECRET",
    config("GOOGLE_GROWTH_CLIENT_SECRET", default=""),
)

GOOGLE_GROWTH_REFRESH_TOKEN = read_secret(
    "GOOGLE_GROWTH_REFRESH_TOKEN",
    config("GOOGLE_GROWTH_REFRESH_TOKEN", default=""),
)

GOOGLE_GROWTH_ACCESS_TOKEN = read_secret(
    "GOOGLE_GROWTH_ACCESS_TOKEN",
    config("GOOGLE_GROWTH_ACCESS_TOKEN", default=""),
)

BING_WEBMASTER_API_KEY = read_secret(
    "BING_WEBMASTER_API_KEY",
    config("BING_WEBMASTER_API_KEY", default=""),
)

GROWTH_AI_CREDENTIALS = {
    "google_main": {
        "client_id": GOOGLE_GROWTH_CLIENT_ID,
        "client_secret": GOOGLE_GROWTH_CLIENT_SECRET,
        "refresh_token": GOOGLE_GROWTH_REFRESH_TOKEN,
        "access_token": GOOGLE_GROWTH_ACCESS_TOKEN,
    },
    "bing_main": {
        "api_key": BING_WEBMASTER_API_KEY,
    },
}

# Feature-specific settings
from .growth_ai import *  # noqa: F401,F403,E402
from .ai import *  # noqa: F401,F403,E402
from .celery_schedule import *  # noqa: F401,F403,E402

# Public account authentication (email/password + Google OpenID Connect)
LOGIN_URL = "/?auth=signin"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

GOOGLE_AUTH_CLIENT_ID = config("GOOGLE_AUTH_CLIENT_ID", default=config("GOOGLE_GROWTH_CLIENT_ID", default=""))
GOOGLE_AUTH_CLIENT_SECRET = read_secret(
    "GOOGLE_AUTH_CLIENT_SECRET",
    config("GOOGLE_GROWTH_CLIENT_SECRET", default=""),
)
GOOGLE_AUTH_REDIRECT_URI = config(
    "GOOGLE_AUTH_REDIRECT_URI",
    default=f"{config('SITE_URL', default='http://localhost:8000').rstrip('/')}/accounts/google/callback/",
)


# Tour AI Agent
TOUR_AI_ENABLED = config("TOUR_AI_ENABLED", default=True, cast=bool)
OPENAI_API_KEY = read_secret("OPENAI_API_KEY", "")
OPENAI_TOUR_AGENT_MODEL = config("OPENAI_TOUR_AGENT_MODEL", default="gpt-5-mini")
GEMINI_TOUR_VISION_MODEL = config("GEMINI_TOUR_VISION_MODEL", default="gemini-2.5-flash")
TOUR_AI_YOLO_MODEL_PATH = str(BASE_DIR / "apps" / "tour_ai_agent" / "model_weights" / "yolo11n.pt")
TOUR_AI_FRAME_SIZE = config("TOUR_AI_FRAME_SIZE", default=640, cast=int)
TOUR_AI_DETECTION_CONFIDENCE = config("TOUR_AI_DETECTION_CONFIDENCE", default=0.35, cast=float)
TOUR_AI_AUTO_PROMPT_DELAY_SECONDS = config("TOUR_AI_AUTO_PROMPT_DELAY_SECONDS", default=15, cast=int)
TOUR_AI_ANONYMOUS_RETENTION_DAYS = config("TOUR_AI_ANONYMOUS_RETENTION_DAYS", default=30, cast=int)
