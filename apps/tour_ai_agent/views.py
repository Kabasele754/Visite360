import json
import logging
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_protect
from apps.tours.models import Tour, Scene360
from apps.tour_ai_agent.models import VisitorSignal
from apps.tour_ai_agent.services.visitor_service import get_visitor_id, get_session_id
from apps.tour_ai_agent.services.conversation_service import get_or_create_conversation, add_message
from apps.tour_ai_agent.services.scene_context_service import get_scene_context
from apps.tour_ai_agent.services.conversion_service import record_action
from apps.tour_ai_agent.agents.orchestrator import run_agent
from apps.tour_ai_agent.tools.cart_tools import add_product_to_cart
from apps.tour_ai_agent.tools.booking_tools import create_appointment, booking_form_payload
from apps.tour_ai_agent.tools.lead_tools import create_sales_lead
from apps.tour_ai_agent.tools.contact_tools import contact_options
from apps.tour_ai_agent.services.grounded_context import build_organization_grounding
from django.core import signing
from apps.vision_ai.models import VisionAnalysis, VisionInsight
from apps.vision_ai.services.point_inspection import inspect_scene_point
from apps.vision_ai.services.queueing import (
    dispatch_scene_analysis,
    latest_active_analysis,
    latest_completed_analysis,
)
from apps.vision_ai.services.insights import (
    CROP_SIGNING_SALT, crop_insight_image, find_point_insight,
    insight_requires_point_refinement, latest_scene_analysis, serialize_insight,
)


logger = logging.getLogger(__name__)


def _json(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        return {}


def _conversation(request, payload):
    tour = get_object_or_404(Tour.objects.select_related("organization", "place"), pk=payload.get("tour_id"))
    scene = None
    if payload.get("scene_id"):
        scene = Scene360.objects.filter(pk=payload.get("scene_id"), tour=tour).first()
    visitor_id = payload.get("visitor_id") or get_visitor_id(request)
    conversation = get_or_create_conversation(
        organization=tour.organization,
        tour=tour,
        scene=scene,
        visitor_id=visitor_id,
        session_id=get_session_id(request),
        user=request.user,
        locale=payload.get("locale") or request.LANGUAGE_CODE,
    )
    return conversation, tour, scene, visitor_id


@require_POST
@csrf_protect
def bootstrap(request):
    payload = _json(request)
    conversation, tour, scene, visitor_id = _conversation(request, payload)
    context = get_scene_context(scene, tour=tour) if scene else {"organization": {"id": tour.organization_id, "name": tour.organization.name}, "place": {}, "scene": {}, "products": [], "catalogue_status": {}}
    opening = "Need help exploring this space?"
    if scene and hasattr(scene, "tour_ai_profile"):
        opening = scene.tour_ai_profile.suggested_opening_message or opening
    response = JsonResponse({
        "ok": True,
        "conversation_id": conversation.id,
        "visitor_id": visitor_id,
        "opening_message": opening,
        "scene": context["scene"],
        "products": context["products"],
        "quick_actions": ["book_appointment", "view_products", "contact_business"],
        "booking_form": booking_form_payload(tour.organization),
        "auto_prompt_delay": int(getattr(settings, "TOUR_AI_AUTO_PROMPT_DELAY_SECONDS", 15)),
        "vision_long_press_duration_ms": int(getattr(settings, "VISION_LONG_PRESS_DURATION_MS", 650)),
        "vision_available": bool(
            (context.get("scene") or {}).get("vision_pipeline")
            or getattr(settings, "VISION_PUBLIC_ON_DEMAND_SCAN", False)
        ),
    })
    response.set_cookie("tw_visitor_id", visitor_id, max_age=60 * 60 * 24 * 365, samesite="Lax", secure=request.is_secure(), httponly=False)
    return response


@require_POST
@csrf_protect
def message(request):
    payload = _json(request)
    text = (payload.get("message") or "").strip()
    if not text:
        return JsonResponse({"ok": False, "error": "Message is required"}, status=400)
    conversation, tour, scene, visitor_id = _conversation(request, payload)
    request_id = str(payload.get("request_id") or "")[:80]
    if request_id:
        previous = conversation.messages.filter(role="assistant", metadata__request_id=request_id).order_by("-created_at").first()
        if previous:
            cached = previous.metadata.get("response_payload") or {}
            return JsonResponse({"ok": True, "conversation_id": conversation.id, **cached, "duplicate": True})
    add_message(conversation, "user", text, {"scene_id": scene.id if scene else None, "request_id": request_id})
    context = get_scene_context(scene, tour=tour) if scene else {"organization": {"id": tour.organization_id, "name": tour.organization.name}, "place": {}, "scene": {}, "products": [], "catalogue_status": {}}
    context.update(build_organization_grounding(tour.organization, text))
    context.update({
        "tour": {"id": tour.id, "title": tour.title, "organization": tour.organization.name},
        "locale": conversation.locale,
        "contact": contact_options(tour.organization, tour),
        "conversation_summary": conversation.summary,
    })
    selected_insight_id = payload.get("vision_insight_id")
    if selected_insight_id and scene is not None:
        selected_insight = VisionInsight.objects.filter(
            pk=selected_insight_id, analysis__scene=scene
        ).first()
        if selected_insight is not None:
            context["selected_visual_insight"] = {
                "id": selected_insight.id,
                "kind": selected_insight.kind,
                "label": selected_insight.label,
                "title": selected_insight.title,
                "description": selected_insight.description,
                "confidence": selected_insight.confidence,
                "attributes": selected_insight.attributes,
                "source_providers": selected_insight.source_providers,
                "instruction": (
                    "Answer about this exact selected item only. Do not substitute the general scene, "
                    "another object or an unverified catalogue product."
                ),
            }
    result = run_agent(text=text, context=context)
    conversation.detected_intent = result.get("intent", "question")
    conversation.save(update_fields=["detected_intent", "last_activity_at"])
    response_payload = {**result, "products": context["products"], "booking_form": booking_form_payload(tour.organization)}
    add_message(conversation, "assistant", result["text"], {
        "provider": result.get("provider"), "intent": result.get("intent"),
        "request_id": request_id, "response_payload": response_payload,
    })
    return JsonResponse({"ok": True, "conversation_id": conversation.id, **response_payload})


@require_POST
@csrf_protect
def signal(request):
    payload = _json(request)
    conversation, tour, scene, visitor_id = _conversation(request, payload)
    signal_type = (payload.get("signal_type") or "unknown")[:80]
    VisitorSignal.objects.create(conversation=conversation, signal_type=signal_type, scene=scene, payload=payload.get("payload") or {})
    return JsonResponse({"ok": True})


@require_POST
@csrf_protect
def action(request):
    payload = _json(request)
    conversation, tour, scene, visitor_id = _conversation(request, payload)
    action_type = payload.get("action_type")
    data = payload.get("payload") or {}
    if action_type == "add_to_cart":
        result = add_product_to_cart(request, data.get("product_id"), data.get("quantity", 1))
    elif action_type == "book_appointment":
        if not data.get("full_name") or not data.get("phone"):
            return JsonResponse({"ok": False, "error": "Full name and phone are required"}, status=400)
        result = create_appointment(organization=tour.organization, tour=tour, payload=data)
    elif action_type in {"create_lead", "request_quote"}:
        result = create_sales_lead(organization=tour.organization, tour=tour, payload=data)
    elif action_type == "contact_business":
        result = {"ok": True, "contact": contact_options(tour.organization, tour)}
    else:
        return JsonResponse({"ok": False, "error": "Unsupported action"}, status=400)
    record_action(conversation, action_type, data, result, bool(result.get("ok")))
    return JsonResponse(result)


@require_POST
@csrf_protect
def analyze_scene_now(request, scene_id):
    if not request.user.is_staff:
        return JsonResponse({"ok": False, "error": "Forbidden"}, status=403)
    from apps.tour_ai_agent.tasks.scene_analysis import analyze_tour_scene
    task = analyze_tour_scene.delay(scene_id, force=True)
    return JsonResponse({"ok": True, "task_id": task.id})


@require_POST
@csrf_protect
def inspect_point(request):
    """Return the closest pre-computed visual insight for a panorama point."""
    payload = _json(request)
    conversation, tour, scene, visitor_id = _conversation(request, payload)
    if scene is None:
        return JsonResponse({"ok": False, "error": "A valid scene is required"}, status=400)
    try:
        yaw = float(payload.get("yaw"))
        pitch = float(payload.get("pitch"))
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "Valid yaw and pitch are required"}, status=400)
    if not (-1.5709 <= pitch <= 1.5709):
        return JsonResponse({"ok": False, "error": "Pitch is outside the panorama range"}, status=400)

    analysis = latest_scene_analysis(scene)
    if analysis is None:
        active = latest_active_analysis(scene)
        if active is None and getattr(settings, "VISION_PUBLIC_ON_DEMAND_SCAN", False):
            latest = latest_completed_analysis(scene)
            retry_failed = bool(latest and latest.status == VisionAnalysis.Status.FAILED)
            try:
                dispatch = dispatch_scene_analysis(
                    scene,
                    force=retry_failed,
                    mode=getattr(settings, "VISION_ON_DEMAND_ANALYSIS_MODE", "auto"),
                )
                if dispatch.mode == "sync":
                    analysis = latest_scene_analysis(scene)
                else:
                    active = dispatch.analysis
            except Exception as exc:
                VisitorSignal.objects.create(
                    conversation=conversation, signal_type="vision_scan_failed", scene=scene,
                    payload={"yaw": yaw, "pitch": pitch, "error": str(exc)[:500]},
                )
                return JsonResponse({
                    "ok": True,
                    "status": "scan_failed",
                    "title": "Scene scan could not start",
                    "description": "The computer-vision service is not ready yet. An administrator can run the local scene scan command and try again.",
                    "scene_id": scene.id,
                })

        if analysis is None and active is not None:
            VisitorSignal.objects.create(
                conversation=conversation, signal_type="vision_scan_waiting", scene=scene,
                payload={"yaw": yaw, "pitch": pitch, "analysis_id": str(active.pk)},
            )
            return JsonResponse({
                "ok": True,
                "status": "analyzing",
                "title": "Scanning this 360° scene",
                "description": "YOLO is detecting objects, PaddleOCR is reading visible text, and semantic vision is verifying the scene. This card will update automatically.",
                "scene_id": scene.id,
                "analysis_id": str(active.pk),
                "analysis_status": active.status,
                "retry_after_ms": int(getattr(settings, "VISION_ON_DEMAND_RETRY_AFTER_MS", 3000)),
            })

        if analysis is None:
            VisitorSignal.objects.create(
                conversation=conversation, signal_type="vision_long_press_unavailable", scene=scene,
                payload={"yaw": yaw, "pitch": pitch},
            )
            return JsonResponse({
                "ok": True,
                "status": "not_analyzed",
                "title": "Visual analysis not ready",
                "description": "This scene must be analyzed before object and text details can be displayed.",
                "scene_id": scene.id,
            })

    insight, distance = find_point_insight(analysis, yaw=yaw, pitch=pitch)
    VisitorSignal.objects.create(
        conversation=conversation, signal_type="vision_long_press", scene=scene,
        payload={
            "yaw": yaw, "pitch": pitch,
            "analysis_id": str(analysis.id),
            "insight_id": insight.id if insight else None,
        },
    )
    original_insight = insight
    needs_targeted_inspection = insight is None or (
        insight is not None and insight_requires_point_refinement(insight)
    )
    if needs_targeted_inspection and bool(getattr(settings, "VISION_POINT_ON_DEMAND_INSPECTION", True)):
        targeted_insight = None
        try:
            targeted_insight = inspect_scene_point(analysis, yaw=yaw, pitch=pitch)
            if targeted_insight is not None:
                insight = targeted_insight
                distance = 0.0
                VisitorSignal.objects.create(
                    conversation=conversation, signal_type="vision_point_targeted", scene=scene,
                    payload={
                        "yaw": yaw, "pitch": pitch,
                        "analysis_id": str(analysis.id),
                        "insight_id": insight.id,
                    },
                )
        except Exception as exc:
            logger.exception(
                "Targeted point inspection failed for scene %s at yaw=%s pitch=%s",
                scene.id, yaw, pitch,
            )
            VisitorSignal.objects.create(
                conversation=conversation, signal_type="vision_point_targeted_failed", scene=scene,
                payload={"yaw": yaw, "pitch": pitch, "error": str(exc)[:500]},
            )
        # Never present a broad shelf/room region as though it were the exact
        # clicked product. A failed refinement is reported honestly instead.
        if targeted_insight is None and original_insight is not None:
            insight = None
            distance = None

    if insight is None:
        return JsonResponse({
            "ok": True,
            "status": "no_object",
            "scene_id": scene.id,
            "analysis_id": str(analysis.id),
            "title": "No verified object at this exact point",
            "description": "Twinscopes did not find a distinct object or readable text under the selected point. Press directly on the visible item and hold without moving.",
            "confidence_percent": 0,
            "pipeline": (scene.ai_analysis or {}).get("pipeline", {}),
        })

    return JsonResponse({
        "ok": True,
        "status": "insight",
        "scene_id": scene.id,
        "analysis_id": str(analysis.id),
        "insight": serialize_insight(request, insight, tour_id=tour.id, distance=distance),
        "pipeline": (scene.ai_analysis or {}).get("pipeline", {}),
    })


@require_GET
def vision_crop(request, token):
    try:
        payload = signing.loads(token, salt=CROP_SIGNING_SALT, max_age=60 * 60)
        insight = VisionInsight.objects.select_related(
            "frame", "analysis__scene__tour", "related_product"
        ).get(pk=payload.get("insight_id"))
        scene = insight.analysis.scene
        if scene is None or int(payload.get("tour_id")) != int(scene.tour_id):
            raise signing.BadSignature("Tour mismatch")
        image_bytes, content_type = crop_insight_image(insight)
    except (signing.BadSignature, signing.SignatureExpired, VisionInsight.DoesNotExist, FileNotFoundError, ValueError, TypeError):
        return HttpResponse(status=404)
    response = HttpResponse(image_bytes, content_type=content_type)
    response["Cache-Control"] = "private, max-age=3600"
    response["X-Content-Type-Options"] = "nosniff"
    return response
