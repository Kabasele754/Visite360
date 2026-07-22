from __future__ import annotations

import hashlib
import time
import uuid
from django.conf import settings


class RequestTraceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        started = time.monotonic()
        response = self.get_response(request)
        latency_ms = int((time.monotonic() - started) * 1000)
        response["X-Request-ID"] = request.request_id
        response["Server-Timing"] = f"app;dur={latency_ms}"
        if settings.MONITORING_STORE_REQUEST_EVENTS and latency_ms >= settings.MONITORING_SLOW_REQUEST_MS:
            self._store_slow_request(request, response.status_code, latency_ms)
        return response

    @staticmethod
    def _store_slow_request(request, status_code: int, latency_ms: int):
        try:
            from apps.monitoring.models import SystemEvent
            ip = request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", "")).split(",")[0].strip()
            SystemEvent.objects.create(
                level=SystemEvent.Level.WARNING,
                source="http",
                event_type="slow_request",
                message=f"{request.method} {request.path} took {latency_ms} ms",
                trace_id=request.request_id,
                data={
                    "method": request.method,
                    "path": request.path,
                    "status_code": status_code,
                    "latency_ms": latency_ms,
                    "ip_hash": hashlib.sha256(ip.encode()).hexdigest() if ip else "",
                },
            )
        except Exception:
            pass
