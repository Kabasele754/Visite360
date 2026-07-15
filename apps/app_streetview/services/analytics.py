from __future__ import annotations

from typing import Any, Dict

from django.utils import timezone

from apps.app_streetview.models import StreetViewAnalyticsEvent, StreetViewHistoryEvent, StreetViewSourcePublication


def record_history(publication: StreetViewSourcePublication, user, action: str, message: str = "", *, source_scene=None, job=None, metadata: Dict[str, Any] | None = None):
    try:
        return StreetViewHistoryEvent.objects.create(
            publication=publication,
            user=user if getattr(user, "is_authenticated", False) else None,
            source_scene=source_scene,
            job=job,
            action=action,
            message=message or action,
            metadata=metadata or {},
        )
    except Exception:
        return None


def record_analytics(publication: StreetViewSourcePublication, user, event_type: str, *, source_scene=None, metadata: Dict[str, Any] | None = None):
    try:
        return StreetViewAnalyticsEvent.objects.create(
            publication=publication,
            user=user if getattr(user, "is_authenticated", False) else None,
            source_scene=source_scene,
            event_type=event_type,
            metadata=metadata or {},
        )
    except Exception:
        return None
