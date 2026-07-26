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
    "apps.ai_core.apps.AICoreConfig",
    "apps.knowledge.apps.KnowledgeConfig",
    "apps.vision_ai.apps.VisionAIConfig",
    "apps.ai_agents.apps.AIAgentsConfig",
    "apps.ai_chat.apps.AIChatConfig",
    "apps.integrations.apps.IntegrationsConfig",
    "apps.monitoring.apps.MonitoringConfig",
    "apps.domain_intelligence.apps.DomainIntelligenceConfig",
    "apps.platform_console.apps.PlatformConsoleConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "apps.monitoring.middleware.RequestTraceMiddleware",
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

CELERY_TASK_ROUTES = {
    "apps.vision_ai.tasks.*": {"queue": "ai"},
    "apps.knowledge.tasks.*": {"queue": "ai"},
    "apps.domain_intelligence.tasks.*": {"queue": "ai"},
    "apps.ai_agents.tasks.*": {"queue": "ai"},
}

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


# ---------------------------------------------------------------------
# Twinscopes AI Enterprise
# ---------------------------------------------------------------------
AI_PRIMARY_TEXT_PROVIDER = config("AI_PRIMARY_TEXT_PROVIDER", default="gemini").lower()
AI_FALLBACK_TEXT_PROVIDER = config("AI_FALLBACK_TEXT_PROVIDER", default="openai").lower()
AI_PRIMARY_VISION_PROVIDER = config("AI_PRIMARY_VISION_PROVIDER", default="fusion").lower()
AI_EMBEDDING_PROVIDER = config("AI_EMBEDDING_PROVIDER", default="auto").lower()
AI_FALLBACK_EMBEDDING_PROVIDER = config("AI_FALLBACK_EMBEDDING_PROVIDER", default="openai").lower()
AI_EMBEDDING_DIMENSIONS = config("AI_EMBEDDING_DIMENSIONS", default=1536, cast=int)
AI_PROVIDER_FAILURE_COOLDOWN_SECONDS = config("AI_PROVIDER_FAILURE_COOLDOWN_SECONDS", default=300, cast=int)
AI_VISION_PROVIDER_FAILURE_COOLDOWN_SECONDS = config(
    "AI_VISION_PROVIDER_FAILURE_COOLDOWN_SECONDS", default=180, cast=int
)
AI_PROVIDER_MAX_RETRIES = config("AI_PROVIDER_MAX_RETRIES", default=2, cast=int)
AI_VISION_PROVIDER_MAX_RETRIES = config("AI_VISION_PROVIDER_MAX_RETRIES", default=1, cast=int)
AI_PROVIDER_RETRY_BASE_SECONDS = config("AI_PROVIDER_RETRY_BASE_SECONDS", default=2.0, cast=float)
AI_PROVIDER_RETRY_MAX_SECONDS = config("AI_PROVIDER_RETRY_MAX_SECONDS", default=20.0, cast=float)
AI_ALLOW_DETERMINISTIC_EMBEDDINGS = config(
    "AI_ALLOW_DETERMINISTIC_EMBEDDINGS", default=DEBUG, cast=bool
)
AI_REQUEST_TIMEOUT_SECONDS = config("AI_REQUEST_TIMEOUT_SECONDS", default=90, cast=int)
AI_MAX_CONTEXT_CHARS = config("AI_MAX_CONTEXT_CHARS", default=24000, cast=int)
AI_CHAT_MAX_HISTORY_MESSAGES = config("AI_CHAT_MAX_HISTORY_MESSAGES", default=20, cast=int)
AI_CHAT_REQUIRE_CITATIONS = config("AI_CHAT_REQUIRE_CITATIONS", default=True, cast=bool)

OPENAI_API_KEY = config("OPENAI_API_KEY", default="")
OPENAI_TEXT_MODEL = config("OPENAI_TEXT_MODEL", default="gpt-5.6")
OPENAI_VISION_MODEL = config("OPENAI_VISION_MODEL", default=OPENAI_TEXT_MODEL)
OPENAI_EMBEDDING_MODEL = config("OPENAI_EMBEDDING_MODEL", default="text-embedding-3-small")
GOOGLE_VISION_MODEL = config("GOOGLE_VISION_MODEL", default=GOOGLE_TEXT_MODEL)
GOOGLE_EMBEDDING_MODEL = config("GOOGLE_EMBEDDING_MODEL", default="gemini-embedding-001")
GOOGLE_EMBEDDING_NATIVE_DIMENSIONS = config(
    "GOOGLE_EMBEDDING_NATIVE_DIMENSIONS", default=0, cast=int
)

VISION_ENABLE_YOLO = config("VISION_ENABLE_YOLO", default=True, cast=bool)
VISION_ENABLE_FLORENCE2 = config("VISION_ENABLE_FLORENCE2", default=False, cast=bool)
VISION_ENABLE_PADDLEOCR = config("VISION_ENABLE_PADDLEOCR", default=True, cast=bool)
VISION_ENABLE_GEMINI = config("VISION_ENABLE_GEMINI", default=True, cast=bool)
VISION_ENABLE_OPENAI = config("VISION_ENABLE_OPENAI", default=bool(OPENAI_API_KEY), cast=bool)
VISION_YOLO_MODEL = config("VISION_YOLO_MODEL", default="/app/model_weights/yolo11n.pt")
VISION_FLORENCE_MODEL = config("VISION_FLORENCE_MODEL", default="microsoft/Florence-2-base")
VISION_PADDLEOCR_LANG = config("VISION_PADDLEOCR_LANG", default="en")
VISION_MAX_PANORAMA_FRAMES = config("VISION_MAX_PANORAMA_FRAMES", default=12, cast=int)
VISION_PRIMARY_SEMANTIC_PROVIDER = config("VISION_PRIMARY_SEMANTIC_PROVIDER", default="openai").lower()
VISION_FALLBACK_SEMANTIC_PROVIDER = config("VISION_FALLBACK_SEMANTIC_PROVIDER", default="gemini").lower()
VISION_SEMANTIC_MAX_FRAMES = config("VISION_SEMANTIC_MAX_FRAMES", default=12, cast=int)
VISION_SEMANTIC_MAX_CLOUD_CALLS_PER_SCENE = config(
    "VISION_SEMANTIC_MAX_CLOUD_CALLS_PER_SCENE", default=4, cast=int
)
VISION_SEMANTIC_REQUEST_INTERVAL_SECONDS = config(
    "VISION_SEMANTIC_REQUEST_INTERVAL_SECONDS", default=1.25, cast=float
)
VISION_PERSPECTIVE_FRAME_SIZE = config("VISION_PERSPECTIVE_FRAME_SIZE", default=896, cast=int)
VISION_SEMANTIC_TEMPERATURE = config("VISION_SEMANTIC_TEMPERATURE", default=0.1, cast=float)
VISION_SEMANTIC_MAX_OUTPUT_TOKENS = config("VISION_SEMANTIC_MAX_OUTPUT_TOKENS", default=2200, cast=int)
VISION_LONG_PRESS_DURATION_MS = config("VISION_LONG_PRESS_DURATION_MS", default=650, cast=int)
VISION_POINT_MAX_DISTANCE_DEGREES = config("VISION_POINT_MAX_DISTANCE_DEGREES", default=18.0, cast=float)
VISION_POINT_PIXEL_PADDING_RATIO = config("VISION_POINT_PIXEL_PADDING_RATIO", default=0.012, cast=float)
VISION_POINT_NEAR_PADDING_RATIO = config("VISION_POINT_NEAR_PADDING_RATIO", default=0.035, cast=float)
VISION_POINT_REFINEMENT_AREA_RATIO = config("VISION_POINT_REFINEMENT_AREA_RATIO", default=0.16, cast=float)
VISION_POINT_REFINE_LOCAL_ONLY = config("VISION_POINT_REFINE_LOCAL_ONLY", default=True, cast=bool)
VISION_POINT_REFINE_BELOW_CONFIDENCE = config("VISION_POINT_REFINE_BELOW_CONFIDENCE", default=0.55, cast=float)
VISION_POINT_LEGACY_MAX_DISTANCE_DEGREES = config("VISION_POINT_LEGACY_MAX_DISTANCE_DEGREES", default=5.0, cast=float)
VISION_POINT_ON_DEMAND_INSPECTION = config("VISION_POINT_ON_DEMAND_INSPECTION", default=True, cast=bool)
VISION_POINT_INSPECTION_FOV_DEGREES = config("VISION_POINT_INSPECTION_FOV_DEGREES", default=46.0, cast=float)
VISION_POINT_DETAIL_FOV_DEGREES = config("VISION_POINT_DETAIL_FOV_DEGREES", default=26.0, cast=float)
VISION_POINT_INSPECTION_FRAME_SIZE = config("VISION_POINT_INSPECTION_FRAME_SIZE", default=768, cast=int)
VISION_POINT_YOLO_NEAR_CENTER_RATIO = config("VISION_POINT_YOLO_NEAR_CENTER_RATIO", default=0.16, cast=float)
VISION_POINT_SEMANTIC_MIN_CONFIDENCE = config("VISION_POINT_SEMANTIC_MIN_CONFIDENCE", default=0.55, cast=float)
VISION_POINT_SEMANTIC_ONLY_MIN_CONFIDENCE = config("VISION_POINT_SEMANTIC_ONLY_MIN_CONFIDENCE", default=0.72, cast=float)
VISION_POINT_EXACT_CAPTURE_SEMANTIC_MIN_CONFIDENCE = config(
    "VISION_POINT_EXACT_CAPTURE_SEMANTIC_MIN_CONFIDENCE", default=0.58, cast=float
)
VISION_POINT_EXACT_CAPTURE_ONLY_MIN_CONFIDENCE = config(
    "VISION_POINT_EXACT_CAPTURE_ONLY_MIN_CONFIDENCE", default=0.64, cast=float
)
VISION_POINT_CAPTURE_MAX_BYTES = config("VISION_POINT_CAPTURE_MAX_BYTES", default=2000000, cast=int)
VISION_POINT_CAPTURE_MAX_DIMENSION = config("VISION_POINT_CAPTURE_MAX_DIMENSION", default=1024, cast=int)
VISION_POINT_CAPTURE_MAX_DATA_URL_LENGTH = config(
    "VISION_POINT_CAPTURE_MAX_DATA_URL_LENGTH", default=3000000, cast=int
)
VISION_POINT_AUTO_RESCAN = config("VISION_POINT_AUTO_RESCAN", default=True, cast=bool)
VISION_POINT_AUTO_RESCAN_CONFIDENCE_RELAXATION = config(
    "VISION_POINT_AUTO_RESCAN_CONFIDENCE_RELAXATION", default=0.05, cast=float
)
VISION_POINT_OCR_FALLBACK_MIN_CONFIDENCE = config(
    "VISION_POINT_OCR_FALLBACK_MIN_CONFIDENCE", default=0.82, cast=float
)
VISION_INSIGHT_MIN_CONFIDENCE = config("VISION_INSIGHT_MIN_CONFIDENCE", default=0.25, cast=float)
VISION_PUBLIC_ON_DEMAND_SCAN = config("VISION_PUBLIC_ON_DEMAND_SCAN", default=True, cast=bool)
VISION_ON_DEMAND_ANALYSIS_MODE = config(
    "VISION_ON_DEMAND_ANALYSIS_MODE", default="auto"
).lower()
VISION_ON_DEMAND_RETRY_AFTER_MS = config(
    "VISION_ON_DEMAND_RETRY_AFTER_MS", default=3000, cast=int
)
VISION_LOCAL_THREAD_WORKERS = config("VISION_LOCAL_THREAD_WORKERS", default=1, cast=int)
VISION_ANALYSIS_STALE_MINUTES = config("VISION_ANALYSIS_STALE_MINUTES", default=45, cast=int)
VISION_SELECTION_REQUIRED = config("VISION_SELECTION_REQUIRED", default=True, cast=bool)
VISION_SELECTION_MIN_SIZE_RATIO = config("VISION_SELECTION_MIN_SIZE_RATIO", default=0.08, cast=float)
VISION_SELECTION_MAX_SIZE_RATIO = config("VISION_SELECTION_MAX_SIZE_RATIO", default=0.72, cast=float)
# Marzipano uses positive pitch upwards while the panorama projection uses positive pitch downwards.
VISION_MARZIPANO_PITCH_SIGN = config("VISION_MARZIPANO_PITCH_SIGN", default=-1.0, cast=float)

PDF_MOBILE_INLINE_MAX_BYTES = config("PDF_MOBILE_INLINE_MAX_BYTES", default=18874368, cast=int)
PDF_PUBLIC_CACHE_SECONDS = config("PDF_PUBLIC_CACHE_SECONDS", default=900, cast=int)
PDF_STREAM_CHUNK_SIZE = config("PDF_STREAM_CHUNK_SIZE", default=65536, cast=int)
DISCOVERY_DEFAULT_RADIUS_KM = config("DISCOVERY_DEFAULT_RADIUS_KM", default=40.0, cast=float)
DISCOVERY_ENABLE_AI_QUERY_PARSER = config("DISCOVERY_ENABLE_AI_QUERY_PARSER", default=True, cast=bool)
DISCOVERY_AI_QUERY_MODEL = config("DISCOVERY_AI_QUERY_MODEL", default=OPENAI_TEXT_MODEL)
DISCOVERY_INTENT_CACHE_SECONDS = config("DISCOVERY_INTENT_CACHE_SECONDS", default=600, cast=int)
PUBLIC_DISCOVERY_LIVE_RATE_LIMIT = config("PUBLIC_DISCOVERY_LIVE_RATE_LIMIT", default=120, cast=int)
PUBLIC_DISCOVERY_RATE_LIMIT = config("PUBLIC_DISCOVERY_RATE_LIMIT", default=30, cast=int)
PUBLIC_DISCOVERY_RATE_WINDOW_SECONDS = config("PUBLIC_DISCOVERY_RATE_WINDOW_SECONDS", default=300, cast=int)
DOMAIN_INTELLIGENCE_AUTO_SYNC = config("DOMAIN_INTELLIGENCE_AUTO_SYNC", default=True, cast=bool)
PUBLIC_APPOINTMENT_RATE_LIMIT = config("PUBLIC_APPOINTMENT_RATE_LIMIT", default=5, cast=int)
PUBLIC_APPOINTMENT_RATE_WINDOW_SECONDS = config("PUBLIC_APPOINTMENT_RATE_WINDOW_SECONDS", default=900, cast=int)

KNOWLEDGE_CRAWLER_USER_AGENT = config(
    "KNOWLEDGE_CRAWLER_USER_AGENT", default="TwinscopesKnowledgeBot/1.0"
)
KNOWLEDGE_CRAWLER_MAX_PAGES = config("KNOWLEDGE_CRAWLER_MAX_PAGES", default=50, cast=int)
KNOWLEDGE_CRAWLER_TIMEOUT_SECONDS = config("KNOWLEDGE_CRAWLER_TIMEOUT_SECONDS", default=20, cast=int)
DOMAIN_INTELLIGENCE_ENABLE_AI_EXTRACTION = config(
    "DOMAIN_INTELLIGENCE_ENABLE_AI_EXTRACTION", default=True, cast=bool
)
DOMAIN_INTELLIGENCE_DEFAULT_MAX_PAGES = config(
    "DOMAIN_INTELLIGENCE_DEFAULT_MAX_PAGES", default=25, cast=int
)
DOMAIN_INTELLIGENCE_AUTO_APPLY_MIN_CONFIDENCE = config(
    "DOMAIN_INTELLIGENCE_AUTO_APPLY_MIN_CONFIDENCE", default=0.82, cast=float
)
DOMAIN_INTELLIGENCE_SYNC_INTERVAL_DAYS = config(
    "DOMAIN_INTELLIGENCE_SYNC_INTERVAL_DAYS", default=7, cast=int
)
DOMAIN_INTELLIGENCE_SCHEDULE_BATCH_SIZE = config(
    "DOMAIN_INTELLIGENCE_SCHEDULE_BATCH_SIZE", default=10, cast=int
)
KNOWLEDGE_CHUNK_SIZE = config("KNOWLEDGE_CHUNK_SIZE", default=1200, cast=int)
KNOWLEDGE_CHUNK_OVERLAP = config("KNOWLEDGE_CHUNK_OVERLAP", default=180, cast=int)

GOOGLE_CALENDAR_ENABLED = config("GOOGLE_CALENDAR_ENABLED", default=False, cast=bool)
GOOGLE_CALENDAR_DEFAULT_TIMEZONE = config(
    "GOOGLE_CALENDAR_DEFAULT_TIMEZONE", default=TIME_ZONE
)
INTEGRATION_ENCRYPTION_KEY = config("INTEGRATION_ENCRYPTION_KEY", default="")

MONITORING_STORE_REQUEST_EVENTS = config("MONITORING_STORE_REQUEST_EVENTS", default=False, cast=bool)
MONITORING_SLOW_REQUEST_MS = config("MONITORING_SLOW_REQUEST_MS", default=1500, cast=int)

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
OPENAI_API_KEY = read_secret(
    "OPENAI_API_KEY",
    config("OPENAI_API_KEY", default=""),
)
OPENAI_TOUR_AGENT_MODEL = config("OPENAI_TOUR_AGENT_MODEL", default="gpt-5-mini")
GEMINI_TOUR_VISION_MODEL = config("GEMINI_TOUR_VISION_MODEL", default="gemini-2.5-flash")
TOUR_AI_FRAME_SIZE = config("TOUR_AI_FRAME_SIZE", default=640, cast=int)
TOUR_AI_DETECTION_CONFIDENCE = config("TOUR_AI_DETECTION_CONFIDENCE", default=0.35, cast=float)
TOUR_AI_AUTO_PROMPT_DELAY_SECONDS = config("TOUR_AI_AUTO_PROMPT_DELAY_SECONDS", default=15, cast=int)
TOUR_AI_ANONYMOUS_RETENTION_DAYS = config("TOUR_AI_ANONYMOUS_RETENTION_DAYS", default=30, cast=int)
