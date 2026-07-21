import json
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from apps.tours.models import Tour, Scene360
from apps.tour_ai_agent.models import VisitorSignal
from apps.tour_ai_agent.services.visitor_service import get_visitor_id, get_session_id
from apps.tour_ai_agent.services.conversation_service import get_or_create_conversation, add_message
from apps.tour_ai_agent.services.scene_context_service import get_scene_context
from apps.tour_ai_agent.services.conversion_service import record_action
from apps.tour_ai_agent.agents.orchestrator import run_agent
from apps.tour_ai_agent.tools.cart_tools import add_product_to_cart
from apps.tour_ai_agent.tools.booking_tools import create_appointment
from apps.tour_ai_agent.tools.lead_tools import create_sales_lead
from apps.tour_ai_agent.tools.contact_tools import contact_options


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
        "auto_prompt_delay": int(getattr(settings, "TOUR_AI_AUTO_PROMPT_DELAY_SECONDS", 15)),
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
    add_message(conversation, "user", text, {"scene_id": scene.id if scene else None})
    context = get_scene_context(scene, tour=tour) if scene else {"organization": {"id": tour.organization_id, "name": tour.organization.name}, "place": {}, "scene": {}, "products": [], "catalogue_status": {}}
    context.update({
        "tour": {"id": tour.id, "title": tour.title, "organization": tour.organization.name},
        "locale": conversation.locale,
        "contact": contact_options(tour.organization, tour),
        "conversation_summary": conversation.summary,
    })
    result = run_agent(text=text, context=context)
    conversation.detected_intent = result.get("intent", "question")
    conversation.save(update_fields=["detected_intent", "last_activity_at"])
    add_message(conversation, "assistant", result["text"], {"provider": result.get("provider"), "intent": result.get("intent")})
    return JsonResponse({"ok": True, "conversation_id": conversation.id, **result, "products": context["products"]})


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
