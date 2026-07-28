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
from apps.tour_ai_agent.agents.intent_router import detect_intent
from apps.tour_ai_agent.tools.cart_tools import add_product_to_cart
from apps.tour_ai_agent.tools.booking_tools import create_appointment, booking_form_payload
from apps.tour_ai_agent.tools.lead_tools import create_sales_lead
from apps.tour_ai_agent.tools.contact_tools import contact_options
from apps.tour_ai_agent.services.grounded_context import (
    build_organization_grounding,
    build_organization_profile,
    should_use_semantic_grounding,
)
from apps.tour_ai_agent.services.public_response import serialize_public_contact, serialize_public_sources
from django.core import signing
from apps.vision_ai.models import VisionAnalysis, VisionInsight
from apps.ai_core.services.error_safety import public_error_copy
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


def _normalize_point_selection(value):
    if not isinstance(value, dict):
        return None
    bbox = value.get("bbox") if isinstance(value.get("bbox"), dict) else {}
    normalized = bbox.get("normalized") if isinstance(bbox.get("normalized"), dict) else {}
    try:
        nx = float(normalized.get("x"))
        ny = float(normalized.get("y"))
        nw = float(normalized.get("width"))
        nh = float(normalized.get("height"))
    except (TypeError, ValueError):
        return None
    minimum = float(getattr(settings, "VISION_SELECTION_MIN_SIZE_RATIO", 0.08))
    maximum = float(getattr(settings, "VISION_SELECTION_MAX_SIZE_RATIO", 0.72))
    if not (0 <= nx <= 1 and 0 <= ny <= 1 and minimum <= nw <= maximum and minimum <= nh <= maximum):
        return None
    if nx + nw > 1.01 or ny + nh > 1.01:
        return None
    corners = []
    for item in value.get("corners") or []:
        if not isinstance(item, dict):
            continue
        try:
            corner_yaw = float(item.get("yaw"))
            corner_pitch = float(item.get("pitch"))
        except (TypeError, ValueError):
            continue
        if -1.5709 <= corner_pitch <= 1.5709:
            corners.append({"yaw": corner_yaw, "pitch": corner_pitch})
    if len(corners) != 4:
        return None

    capture = None
    raw_capture = value.get("capture")
    if isinstance(raw_capture, dict):
        data_url = str(raw_capture.get("data_url") or "")
        max_data_url_length = int(getattr(settings, "VISION_POINT_CAPTURE_MAX_DATA_URL_LENGTH", 3_000_000))
        allowed_prefixes = (
            "data:image/jpeg;base64,",
            "data:image/png;base64,",
            "data:image/webp;base64,",
        )
        if data_url.startswith(allowed_prefixes) and len(data_url) <= max_data_url_length:
            try:
                capture_width = int(raw_capture.get("width") or 0)
                capture_height = int(raw_capture.get("height") or 0)
            except (TypeError, ValueError):
                capture_width = capture_height = 0
            if 96 <= capture_width <= 2048 and 96 <= capture_height <= 2048:
                requested_source = str(raw_capture.get("source") or "active_viewer_canvas")
                capture = {
                    "data_url": data_url,
                    "width": capture_width,
                    "height": capture_height,
                    "source": requested_source if requested_source in {"active_viewer_canvas", "viewer_canvas"} else "active_viewer_canvas",
                }

    normalized_selection = {
        "version": 3 if capture else 1,
        "bbox": {"normalized": {"x": nx, "y": ny, "width": nw, "height": nh}},
        "corners": corners,
        "view_fov": value.get("view_fov"),
    }
    if capture:
        normalized_selection["capture"] = capture
    return normalized_selection


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
        "contact": serialize_public_contact(contact_options(tour.organization, tour)),
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
    max_message_chars = int(getattr(settings, "TOUR_AI_MAX_MESSAGE_CHARS", 2000))
    if len(text) > max_message_chars:
        return JsonResponse({"ok": False, "error": f"Message is too long (maximum {max_message_chars} characters)"}, status=400)
    conversation, tour, scene, visitor_id = _conversation(request, payload)
    request_id = str(payload.get("request_id") or "")[:80]
    if request_id:
        previous = conversation.messages.filter(role="assistant", metadata__request_id=request_id).order_by("-created_at").first()
        if previous:
            cached = previous.metadata.get("response_payload") or {}
            return JsonResponse({"ok": True, "conversation_id": conversation.id, **cached, "duplicate": True})
    add_message(conversation, "user", text, {"scene_id": scene.id if scene else None, "request_id": request_id})
    context = get_scene_context(scene, tour=tour) if scene else {"organization": {"id": tour.organization_id, "name": tour.organization.name}, "place": {}, "scene": {}, "products": [], "catalogue_status": {}}
    detected_intent = detect_intent(text)
    if should_use_semantic_grounding(text, detected_intent):
        context.update(build_organization_grounding(tour.organization, text, limit=4))
    else:
        context.update(build_organization_profile(tour.organization))
        context.setdefault("knowledge_sources", [])
        context.setdefault("domain_intelligence", {})
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
    response_payload = {
        **result,
        "products": context["products"],
        "contact": serialize_public_contact(context.get("contact")),
        "sources": serialize_public_sources(context),
        "booking_form": booking_form_payload(tour.organization),
    }
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
        result = {"ok": True, "contact": serialize_public_contact(contact_options(tour.organization, tour))}
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
    selection = _normalize_point_selection(payload.get("selection"))

    locale = getattr(conversation, "locale", None) or getattr(request, "LANGUAGE_CODE", "en")
    if bool(getattr(settings, "VISION_SELECTION_REQUIRED", True)) and selection is None:
        is_french = str(locale or "").lower().startswith("fr")
        return JsonResponse({
            "ok": True,
            "status": "selection_required",
            "title": "Cadrez précisément l’objet" if is_french else "Frame the exact object",
            "description": (
                "Déplacez ou redimensionnez la zone, puis confirmez l’analyse."
                if is_french
                else "Move or resize the selection, then confirm the analysis."
            ),
            "scene_id": scene.id,
        })
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
                title, description = public_error_copy(locale, kind="temporary")
                return JsonResponse({
                    "ok": True,
                    "status": "scan_failed",
                    "title": title,
                    "description": description,
                    "scene_id": scene.id,
                })

        if analysis is None and active is not None:
            VisitorSignal.objects.create(
                conversation=conversation, signal_type="vision_scan_waiting", scene=scene,
                payload={"yaw": yaw, "pitch": pitch, "analysis_id": str(active.pk)},
            )
            title, description = public_error_copy(locale, kind="analyzing")
            return JsonResponse({
                "ok": True,
                "status": "analyzing",
                "title": title,
                "description": description,
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
            title, description = public_error_copy(locale, kind="not_ready")
            return JsonResponse({
                "ok": True,
                "status": "not_analyzed",
                "title": title,
                "description": description,
                "scene_id": scene.id,
            })

    insight, distance = find_point_insight(analysis, yaw=yaw, pitch=pitch)
    VisitorSignal.objects.create(
        conversation=conversation, signal_type="vision_long_press", scene=scene,
        payload={
            "yaw": yaw, "pitch": pitch,
            "analysis_id": str(analysis.id),
            "insight_id": insight.id if insight else None,
            "selection": selection.get("bbox", {}) if selection else {},
        },
    )
    original_insight = insight
    # A confirmed crop always deserves an exact re-inspection. Reusing a broad
    # panorama insight here would defeat the user's explicit selection and can
    # return a nearby shelf, wall or room instead of the framed object.
    needs_targeted_inspection = selection is not None or insight is None or (
        insight is not None and insight_requires_point_refinement(insight)
    )
    if needs_targeted_inspection and bool(getattr(settings, "VISION_POINT_ON_DEMAND_INSPECTION", True)):
        targeted_insight = None
        try:
            targeted_insight = inspect_scene_point(analysis, yaw=yaw, pitch=pitch, selection=selection)
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
        exact_capture_requested = bool(selection and isinstance(selection.get("capture"), dict))
        response_status = "refine_selection" if exact_capture_requested else "no_object"
        title, description = public_error_copy(locale, kind=response_status)
        VisitorSignal.objects.create(
            conversation=conversation,
            signal_type="vision_point_refine_required",
            scene=scene,
            payload={
                "yaw": yaw,
                "pitch": pitch,
                "analysis_id": str(analysis.id),
                "exact_capture": exact_capture_requested,
                "automatic_rescan_performed": exact_capture_requested,
            },
        )
        return JsonResponse({
            "ok": True,
            "status": response_status,
            "scene_id": scene.id,
            "analysis_id": str(analysis.id),
            "title": title,
            "description": description,
            "confidence_percent": 0,
            "rescan_performed": exact_capture_requested,
            "can_refine_selection": True,
        })

    return JsonResponse({
        "ok": True,
        "status": "insight",
        "scene_id": scene.id,
        "analysis_id": str(analysis.id),
        "insight": serialize_insight(request, insight, tour_id=tour.id, distance=distance),
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
