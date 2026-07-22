import os
from pathlib import Path

from decouple import config

BASE_DIR = Path(__file__).resolve().parents[2]


def read_secret(name: str, default: str = "") -> str:
    file_path = os.getenv(f"{name}_FILE", "").strip()
    if file_path:
        try:
            return Path(file_path).read_text(encoding="utf-8").strip()
        except OSError:
            pass
    return os.getenv(name, default).strip()


AI_PRIMARY_TEXT_PROVIDER = config("AI_PRIMARY_TEXT_PROVIDER", default="gemini")
AI_FALLBACK_TEXT_PROVIDER = config("AI_FALLBACK_TEXT_PROVIDER", default="openai")
AI_ENABLE_GEMINI = config("AI_ENABLE_GEMINI", default=True, cast=bool)
AI_ENABLE_GEMINI_VISION = config("AI_ENABLE_GEMINI_VISION", default=True, cast=bool)
AI_ENABLE_OPENAI = config(
    "AI_ENABLE_OPENAI",
    default=bool(read_secret("OPENAI_API_KEY", config("OPENAI_API_KEY", default=""))),
    cast=bool,
)
AI_ENABLE_ULTRALYTICS = config("AI_ENABLE_ULTRALYTICS", default=True, cast=bool)
AI_TEXT_TEMPERATURE = config("AI_TEXT_TEMPERATURE", default=0.3, cast=float)
AI_TEXT_MAX_TOKENS = config("AI_TEXT_MAX_TOKENS", default=1400, cast=int)

GOOGLE_GENAI_USE_VERTEXAI = config("GOOGLE_GENAI_USE_VERTEXAI", default=True, cast=bool)
GOOGLE_CLOUD_PROJECT = config("GOOGLE_CLOUD_PROJECT", default="")
GOOGLE_CLOUD_LOCATION = config("GOOGLE_CLOUD_LOCATION", default="us-central1")
GOOGLE_TEXT_MODEL = config("GOOGLE_TEXT_MODEL", default="gemini-2.5-flash")
GEMINI_TOUR_VISION_MODEL = config("GEMINI_TOUR_VISION_MODEL", default="gemini-2.5-flash")
GOOGLE_IMAGE_MODEL = config("GOOGLE_IMAGE_MODEL", default="imagen-4.0-generate-001")

OPENAI_API_KEY = read_secret("OPENAI_API_KEY", config("OPENAI_API_KEY", default=""))
OPENAI_TEXT_MODEL = config("OPENAI_TEXT_MODEL", default="gpt-4.1-mini")

# YOLO path resolution:
# - Local development: <project>/apps/tour_ai_agent/model_weights/<model>
# - Docker production: /app/model_weights/<model>
# A production path accidentally left in the local .env is ignored automatically.
TOUR_AI_YOLO_MODEL_NAME = config("TOUR_AI_YOLO_MODEL_NAME", default="yolo11n.pt").strip() or "yolo11n.pt"
LOCAL_YOLO_MODEL_PATH = BASE_DIR / "apps" / "tour_ai_agent" / "model_weights" / TOUR_AI_YOLO_MODEL_NAME
DOCKER_YOLO_MODEL_PATH = Path("/app/model_weights") / TOUR_AI_YOLO_MODEL_NAME
RUNNING_IN_DOCKER = Path("/.dockerenv").exists() or config(
    "RUNNING_IN_DOCKER", default=False, cast=bool
)

_configured_yolo_path = config("TOUR_AI_YOLO_MODEL_PATH", default="").strip()
if _configured_yolo_path:
    candidate = Path(os.path.expandvars(os.path.expanduser(_configured_yolo_path)))
    if not candidate.is_absolute():
        candidate = BASE_DIR / candidate

    # Protect local macOS/Linux development from a Docker-only /app path.
    if not RUNNING_IN_DOCKER and str(candidate).startswith("/app/"):
        candidate = LOCAL_YOLO_MODEL_PATH
else:
    candidate = DOCKER_YOLO_MODEL_PATH if RUNNING_IN_DOCKER else LOCAL_YOLO_MODEL_PATH

TOUR_AI_YOLO_MODEL_PATH = str(candidate)
# Enterprise vision uses the same resolved model path, so local development
# never accidentally points to Docker-only /app/model_weights.
VISION_YOLO_MODEL = str(candidate)
TOUR_AI_YOLO_DEVICE = config("TOUR_AI_YOLO_DEVICE", default="cpu")
TOUR_AI_YOLO_CONFIDENCE = config("TOUR_AI_YOLO_CONFIDENCE", default=0.35, cast=float)
TOUR_AI_YOLO_IMAGE_SIZE = config("TOUR_AI_YOLO_IMAGE_SIZE", default=896, cast=int)

TOUR_AI_AUTO_ANALYZE = config("TOUR_AI_AUTO_ANALYZE", default=True, cast=bool)
TOUR_AI_FRAME_YAWS = config("TOUR_AI_FRAME_YAWS", default="0,45,90,135,180,225,270,315")
TOUR_AI_FRAME_PITCHES = config("TOUR_AI_FRAME_PITCHES", default="0")
TOUR_AI_FRAME_FOV = config("TOUR_AI_FRAME_FOV", default=90.0, cast=float)
