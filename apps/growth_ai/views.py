import hashlib,json
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404,render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from apps.organizations.models import Organization,OrganizationMember
from .models import DataSourceConnection,SyncRun,TrafficMetric,GrowthEvent,InternalDailySnapshot
from .tasks import sync_growth_connection

def _can_manage(user,org): return user.is_superuser or OrganizationMember.objects.filter(user=user,organization=org,is_active=True,role__in=['owner','manager']).exists()
@login_required
def dashboard(request,organization_slug):
    org=get_object_or_404(Organization,slug=organization_slug)
    if not _can_manage(request.user,org): return JsonResponse({'detail':'Forbidden'},status=403)
    sources=DataSourceConnection.objects.filter(organization=org).order_by('provider')
    latest=InternalDailySnapshot.objects.filter(organization=org).first()
    recent_runs=SyncRun.objects.filter(connection__organization=org).select_related('connection')[:12]
    totals={'events_30d':GrowthEvent.objects.filter(organization=org,occurred_at__gte=timezone.now()-timezone.timedelta(days=30)).count(),'metric_rows':TrafficMetric.objects.filter(organization=org).count(),'connected_sources':sources.filter(is_enabled=True).count()}
    return render(request,'dashboard/growth_ai/index.html',{'organization':org,'sources':sources,'latest_snapshot':latest,'recent_runs':recent_runs,'totals':totals})
@login_required
@require_POST
def sync_now(request,organization_slug,connection_id):
    org=get_object_or_404(Organization,slug=organization_slug)
    if not _can_manage(request.user,org): return JsonResponse({'detail':'Forbidden'},status=403)
    c=get_object_or_404(DataSourceConnection,pk=connection_id,organization=org); task=sync_growth_connection.delay(c.pk)
    return JsonResponse({'queued':True,'task_id':task.id})
@csrf_exempt
@require_POST
def collect_event(request):
    """Collect a browser Growth AI event without disturbing the public UI.

    The endpoint accepts the stable event vocabulary used by the global tracker,
    normalizes a few legacy names, safely parses optional identifiers and returns
    a non-error response for unknown client events so outdated cached JavaScript
    cannot flood Django logs with HTTP 400 responses.
    """
    try:
        payload = json.loads(request.body or b"{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({"ok": False, "detail": "Invalid JSON"}, status=400)

    if not isinstance(payload, dict):
        return JsonResponse({"ok": False, "detail": "JSON object required"}, status=400)

    raw_name = str(payload.get("event_name") or "").strip().lower()[:80]
    if not raw_name:
        return JsonResponse({"ok": False, "detail": "event_name required"}, status=400)

    aliases = {
        "tour_open": "tour_opened",
        "tour_started": "tour_opened",
        "product_view": "product_viewed",
        "cart_opened": "cart_viewed",
        "cart_updated": "add_to_cart",
        "checkout": "checkout_started",
        "payment_started": "stripe_checkout_opened",
        "google_account_created": "google_account_created",
        "search": "search_performed",
        "share": "share_clicked",
    }
    name = aliases.get(raw_name, raw_name)

    allowed = {
        "page_view", "business_view", "tour_opened", "tour_completed",
        "scene_changed", "hotspot_clicked", "product_viewed", "add_to_cart",
        "remove_from_cart", "cart_viewed", "checkout_started",
        "stripe_checkout_opened", "paypal_checkout_opened", "payment_success",
        "payment_failed", "purchase_completed", "whatsapp_clicked",
        "phone_clicked", "email_clicked", "gps_clicked", "search_performed",
        "share_clicked", "favorite", "like", "comment", "login", "register",
        "google_login", "google_account_created", "logout",
    }

    # Old cached front-end files may still emit a retired event name. Ignore it
    # gracefully instead of returning 400 repeatedly in development/production.
    if name not in allowed:
        return JsonResponse({"ok": True, "ignored": True, "event_name": raw_name}, status=202)

    def positive_int(value):
        if value in (None, "", 0, "0"):
            return None
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    organization_id = positive_int(payload.get("organization_id"))
    organization = Organization.objects.filter(pk=organization_id).first() if organization_id else None

    if not request.session.session_key:
        request.session.create()

    seed = (
        request.session.session_key
        or request.COOKIES.get("growth_sid")
        or request.META.get("REMOTE_ADDR", "")
        or "anonymous"
    )
    seed += "|" + request.META.get("HTTP_USER_AGENT", "")
    session_key = hashlib.sha256(seed.encode("utf-8")).hexdigest()

    user_agent = request.META.get("HTTP_USER_AGENT", "").lower()
    if "tablet" in user_agent or "ipad" in user_agent:
        device = "tablet"
    elif any(token in user_agent for token in ("mobile", "iphone", "android")):
        device = "mobile"
    else:
        device = "desktop"

    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    metadata = {**metadata, "client_event_name": raw_name}

    event = GrowthEvent.objects.create(
        organization=organization,
        event_name=name,
        session_key=session_key,
        user=request.user if request.user.is_authenticated else None,
        tour_id=positive_int(payload.get("tour_id")),
        product_id=positive_int(payload.get("product_id")),
        page_path=str(payload.get("page_path") or request.META.get("HTTP_REFERER", ""))[:500],
        referrer=str(payload.get("referrer") or "")[:500],
        device=device,
        source=str(payload.get("source") or "direct")[:120],
        metadata=metadata,
        occurred_at=timezone.now(),
    )
    return JsonResponse({"ok": True, "event_id": event.pk}, status=201)

