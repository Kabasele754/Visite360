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
    try: payload=json.loads(request.body or '{}')
    except Exception: return JsonResponse({'detail':'Invalid JSON'},status=400)
    name=str(payload.get('event_name',''))[:80]
    if not name: return JsonResponse({'detail':'event_name required'},status=400)
    allowed={'page_view','tour_opened','tour_completed','hotspot_clicked','product_viewed','add_to_cart','cart_viewed','checkout_started','purchase_completed','whatsapp_clicked','phone_clicked','email_clicked','gps_clicked','search_performed','share_clicked'}
    if name not in allowed: return JsonResponse({'detail':'Unsupported event'},status=400)
    org=None
    if payload.get('organization_id'): org=Organization.objects.filter(pk=payload['organization_id']).first()
    seed=(request.session.session_key or request.COOKIES.get('growth_sid') or request.META.get('REMOTE_ADDR',''))+'|'+request.META.get('HTTP_USER_AGENT','')
    session_key=hashlib.sha256(seed.encode()).hexdigest()
    ua=request.META.get('HTTP_USER_AGENT','').lower(); device='mobile' if 'mobile' in ua else 'tablet' if 'tablet' in ua else 'desktop'
    ev=GrowthEvent.objects.create(organization=org,event_name=name,session_key=session_key,user=request.user if request.user.is_authenticated else None,tour_id=payload.get('tour_id') or None,product_id=payload.get('product_id') or None,page_path=str(payload.get('page_path') or request.META.get('HTTP_REFERER',''))[:500],referrer=str(payload.get('referrer',''))[:500],device=device,source=str(payload.get('source',''))[:120],metadata=payload.get('metadata') if isinstance(payload.get('metadata'),dict) else {},occurred_at=timezone.now())
    return JsonResponse({'ok':True,'event_id':ev.pk},status=201)
