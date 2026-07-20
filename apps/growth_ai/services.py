"""Growth AI service layer.

This module exposes the two stable public APIs used by the application:

- ``record_request_event`` for server-side visitor and conversion tracking.
- ``sync_connection`` for Celery data-source synchronization.

Keeping both functions here preserves compatibility with existing imports in
``apps.users.views`` and ``apps.growth_ai.tasks.collectors``.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import date, timedelta
from typing import Any
from urllib.parse import urlparse

from django.db import transaction
from django.utils import timezone

from .collectors import get_collector
from .models import DataSourceConnection, GrowthEvent, SyncRun

logger = logging.getLogger(__name__)


def request_session_hash(request) -> str:
    """Return a stable, non-reversible identifier for the current session."""
    if not request.session.session_key:
        request.session.create()

    seed = (
        request.session.session_key
        or request.COOKIES.get("growth_sid")
        or request.META.get("REMOTE_ADDR", "")
    )
    seed += "|" + request.META.get("HTTP_USER_AGENT", "")
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def detect_device(request) -> str:
    """Return a compact device category from the request user agent."""
    user_agent = request.META.get("HTTP_USER_AGENT", "").lower()

    if "tablet" in user_agent or "ipad" in user_agent:
        return "tablet"

    if any(token in user_agent for token in ("mobile", "iphone", "android")):
        return "mobile"

    return "desktop"


def infer_source(request) -> str:
    """Infer a basic acquisition source from the HTTP referrer."""
    referrer = request.META.get("HTTP_REFERER", "")
    if not referrer:
        return "direct"

    host = urlparse(referrer).netloc.lower()

    source_map = {
        "google.": "google",
        "facebook.": "facebook",
        "fb.com": "facebook",
        "instagram.": "instagram",
        "tiktok.": "tiktok",
        "linkedin.": "linkedin",
        "whatsapp.": "whatsapp",
        "wa.me": "whatsapp",
    }

    for token, source in source_map.items():
        if token in host:
            return source

    return host[:120] or "referral"


def record_request_event(
    request,
    event_name: str,
    *,
    organization=None,
    tour_id: int | None = None,
    product_id: int | None = None,
    metadata: dict[str, Any] | None = None,
    user=None,
):
    """Persist a server-side Growth AI event without breaking the main flow.

    Tracking must never prevent login, registration, checkout, or page loading.
    For that reason this function logs failures and returns ``None`` instead of
    raising an exception to the caller.
    """
    if not event_name:
        logger.warning("Growth AI event ignored because event_name is empty.")
        return None

    try:
        resolved_user = user
        if resolved_user is None:
            request_user = getattr(request, "user", None)
            if request_user is not None and getattr(request_user, "is_authenticated", False):
                resolved_user = request_user

        return GrowthEvent.objects.create(
            organization=organization,
            event_name=str(event_name)[:80],
            session_key=request_session_hash(request),
            user=resolved_user,
            tour_id=tour_id,
            product_id=product_id,
            page_path=getattr(request, "path", "")[:500],
            referrer=request.META.get("HTTP_REFERER", "")[:500],
            device=detect_device(request),
            source=infer_source(request),
            metadata=metadata or {},
            occurred_at=timezone.now(),
        )
    except Exception:
        logger.exception("Unable to record Growth AI event '%s'.", event_name)
        return None


def _resolve_sync_period(
    connection: DataSourceConnection,
    start_date: date | None = None,
    end_date: date | None = None,
) -> tuple[date, date]:
    """Return a validated inclusive synchronization period."""
    resolved_end = end_date or (timezone.localdate() - timedelta(days=1))

    try:
        lookback_days = int((connection.config or {}).get("lookback_days", 7))
    except (TypeError, ValueError):
        lookback_days = 7

    lookback_days = max(1, min(lookback_days, 365))
    resolved_start = start_date or (
        resolved_end - timedelta(days=lookback_days - 1)
    )

    if resolved_start > resolved_end:
        raise ValueError("Growth AI start_date cannot be after end_date.")

    return resolved_start, resolved_end


def sync_connection(
    connection: DataSourceConnection,
    start_date: date | None = None,
    end_date: date | None = None,
) -> SyncRun:
    """Synchronize one configured Growth AI data source.

    A ``SyncRun`` is persisted for both success and failure. Exceptions are
    re-raised so Celery can apply its configured retry policy.
    """
    if not isinstance(connection, DataSourceConnection):
        raise TypeError("connection must be a DataSourceConnection instance.")

    if not connection.is_enabled:
        raise ValueError(f"Growth AI connection {connection.pk} is disabled.")

    resolved_start, resolved_end = _resolve_sync_period(
        connection=connection,
        start_date=start_date,
        end_date=end_date,
    )

    run = SyncRun.objects.create(
        connection=connection,
        status=SyncRun.Status.RUNNING,
        started_at=timezone.now(),
        metadata={
            "start_date": resolved_start.isoformat(),
            "end_date": resolved_end.isoformat(),
            "provider": connection.provider,
        },
    )

    try:
        collector = get_collector(connection)
        result = collector.collect(resolved_start, resolved_end)

        received = int(getattr(result, "received", 0) or 0)
        saved = int(getattr(result, "saved", 0) or 0)
        result_metadata: dict[str, Any] = getattr(result, "metadata", {}) or {}

        run.status = SyncRun.Status.SUCCESS
        run.rows_received = max(0, received)
        run.rows_saved = max(0, saved)
        run.metadata = {**run.metadata, **result_metadata}
        run.error = ""

        DataSourceConnection.objects.filter(pk=connection.pk).update(
            last_synced_at=timezone.now(),
            last_error="",
            updated_at=timezone.now(),
        )

    except Exception as exc:
        error_message = str(exc)[:10000]
        run.status = SyncRun.Status.FAILED
        run.error = error_message

        DataSourceConnection.objects.filter(pk=connection.pk).update(
            last_error=error_message,
            updated_at=timezone.now(),
        )
        raise

    finally:
        run.finished_at = timezone.now()
        run.save(
            update_fields=[
                "status",
                "finished_at",
                "rows_received",
                "rows_saved",
                "error",
                "metadata",
                "updated_at",
            ]
        )

    return run
