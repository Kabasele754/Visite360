from decouple import config

AI_PRIMARY_TEXT_PROVIDER = config("AI_PRIMARY_TEXT_PROVIDER", default="gemini")
AI_FALLBACK_TEXT_PROVIDER = config("AI_FALLBACK_TEXT_PROVIDER", default="")
AI_ENABLE_GEMINI = config("AI_ENABLE_GEMINI", default=True, cast=bool)
AI_ENABLE_GEMINI_VISION = config("AI_ENABLE_GEMINI_VISION", default=True, cast=bool)
AI_ENABLE_OPENAI = config("AI_ENABLE_OPENAI", default=False, cast=bool)
AI_ENABLE_ULTRALYTICS = config("AI_ENABLE_ULTRALYTICS", default=True, cast=bool)
AI_TEXT_TEMPERATURE = config("AI_TEXT_TEMPERATURE", default=0.3, cast=float)
AI_TEXT_MAX_TOKENS = config("AI_TEXT_MAX_TOKENS", default=1400, cast=int)

GOOGLE_GENAI_USE_VERTEXAI = config("GOOGLE_GENAI_USE_VERTEXAI", default=True, cast=bool)
GOOGLE_CLOUD_PROJECT = config("GOOGLE_CLOUD_PROJECT", default="")
GOOGLE_CLOUD_LOCATION = config("GOOGLE_CLOUD_LOCATION", default="us-central1")
GOOGLE_TEXT_MODEL = config("GOOGLE_TEXT_MODEL", default="gemini-2.5-flash")
GEMINI_TOUR_VISION_MODEL = config("GEMINI_TOUR_VISION_MODEL", default="gemini-2.5-flash")
GOOGLE_IMAGE_MODEL = config("GOOGLE_IMAGE_MODEL", default="imagen-4.0-generate-001")

OPENAI_API_KEY = config("OPENAI_API_KEY", default="")
OPENAI_TEXT_MODEL = config("OPENAI_TEXT_MODEL", default="gpt-4.1-mini")

TOUR_AI_YOLO_MODEL_PATH = config(
    "TOUR_AI_YOLO_MODEL_PATH", default="/app/model_weights/yolo11n.pt"
)
TOUR_AI_YOLO_DEVICE = config("TOUR_AI_YOLO_DEVICE", default="cpu")
TOUR_AI_YOLO_CONFIDENCE = config("TOUR_AI_YOLO_CONFIDENCE", default=0.35, cast=float)
TOUR_AI_YOLO_IMAGE_SIZE = config("TOUR_AI_YOLO_IMAGE_SIZE", default=640, cast=int)
