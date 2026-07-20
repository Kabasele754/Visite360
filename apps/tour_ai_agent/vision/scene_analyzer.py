from __future__ import annotations
import tempfile
from django.conf import settings
from django.utils import timezone
from apps.tour_ai_agent.models import TourSceneAIProfile
from apps.tour_ai_agent.providers.gemini_client import GeminiVisionClient
from .panorama_frames import generate_panorama_frames
from .preprocessing import sha256_file
from .local_detector import LocalObjectDetector
from .local_classifier import classify_scene
from .confidence_router import choose_vision_provider
from .product_matcher import match_scene_products


def scene_image_path(scene):
    for field in ("image_360_original", "image_360", "image_360_mobile", "image_360_preview"):
        value = getattr(scene, field, None)
        if value:
            try:
                return value.path
            except Exception:
                continue
    raise ValueError("Scene has no local panorama image")


def analyze_scene(scene, force=False):
    path = scene_image_path(scene)
    digest = sha256_file(path)
    profile, _ = TourSceneAIProfile.objects.get_or_create(scene=scene)
    if not force and profile.image_hash == digest and profile.analyzed_at:
        return profile
    try:
        with tempfile.TemporaryDirectory(prefix=f"tour-ai-{scene.id}-") as tmp:
            frames = generate_panorama_frames(path, tmp, size=int(getattr(settings, "TOUR_AI_FRAME_SIZE", 640)))
            detector = LocalObjectDetector()
            detections = []
            for frame in frames:
                for detection in detector.detect(frame["path"], float(getattr(settings, "TOUR_AI_DETECTION_CONFIDENCE", 0.35))):
                    item = detection.dict()
                    item.update({"frame": frame["name"], "yaw": frame["yaw"]})
                    detections.append(item)
            simple = [type("D", (), item) for item in detections]
            classification = classify_scene(simple)
            decision = choose_vision_provider(
                classification["confidence"],
                [item["confidence"] for item in detections],
                len(detections),
            )
            gemini = {}
            provider = decision.provider
            if provider in {"hybrid", "gemini"}:
                gemini = GeminiVisionClient().analyze(
                    [item["path"] for item in frames],
                    {
                        "scene_type": classification["scene_type"],
                        "confidence": classification["confidence"],
                        "objects": [item["label"] for item in detections],
                    },
                ) or {}
                if not gemini:
                    provider = "local"
            final_type = gemini.get("scene_type") or classification["scene_type"]
            features = gemini.get("features") or sorted({item["label"] for item in detections})
            feature_text = ", ".join(features[:6]) if features else "visible interior features"
            summary = gemini.get("summary") or f"{scene.title}: {final_type.replace('_', ' ')} with {feature_text}."
            profile.image_hash = digest
            profile.local_scene_type = classification["scene_type"]
            profile.local_scene_confidence = classification["confidence"]
            profile.local_detections = detections
            profile.local_features = sorted({item["label"] for item in detections})
            profile.gemini_payload = gemini
            profile.gemini_summary = gemini.get("summary", "")
            profile.final_scene_type = final_type
            profile.final_summary = summary
            profile.final_features = features
            profile.commercial_intents = gemini.get("commercial_intents") or ["ask_question", "book_appointment", "view_products"]
            profile.suggested_questions = gemini.get("suggested_questions") or ["Would you like to book an appointment?", "Would you like to see related products?"]
            profile.suggested_opening_message = gemini.get("opening_message") or "Need help exploring this space?"
            profile.analysis_source = provider
            profile.analysis_confidence = decision.confidence
            profile.analyzed_at = timezone.now()
            profile.last_error = ""
            profile.save()
            match_scene_products(scene, profile.local_features)
            return profile
    except Exception as exc:
        profile.last_error = str(exc)
        profile.save(update_fields=["last_error", "updated_at"])
        raise
