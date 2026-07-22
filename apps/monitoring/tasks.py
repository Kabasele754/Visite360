from celery import shared_task
from apps.monitoring.services.health import run_platform_health_checks


@shared_task
def check_platform_health():
    rows = run_platform_health_checks()
    return [{"provider": row.provider, "service": row.service, "status": row.status, "latency_ms": row.latency_ms} for row in rows]
