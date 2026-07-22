from __future__ import annotations

import socket
import time
from django.conf import settings
from django.db import connection
from django.utils import timezone

from apps.monitoring.models import ProviderHealth


def _record(provider: str, service: str, status: str, latency_ms: int, message: str = "", metadata: dict | None = None):
    return ProviderHealth.objects.update_or_create(
        provider=provider,
        service=service,
        defaults={
            "status": status,
            "latency_ms": latency_ms,
            "message": message[:4000],
            "metadata": metadata or {},
            "checked_at": timezone.now(),
        },
    )[0]


def check_database():
    started = time.monotonic()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return _record("postgresql" if connection.vendor == "postgresql" else connection.vendor, "database", "healthy", int((time.monotonic() - started) * 1000))
    except Exception as exc:
        return _record(connection.vendor, "database", "down", int((time.monotonic() - started) * 1000), str(exc))


def check_redis():
    started = time.monotonic()
    try:
        from redis import Redis
        client = Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, password=settings.REDIS_PASSWORD or None, socket_timeout=3)
        client.ping()
        return _record("redis", "cache-broker", "healthy", int((time.monotonic() - started) * 1000))
    except Exception as exc:
        return _record("redis", "cache-broker", "down", int((time.monotonic() - started) * 1000), str(exc))


def run_platform_health_checks():
    return [check_database(), check_redis()]
