from __future__ import annotations

import uuid
from django.db import models
from apps.common.models import TimeStampedModel


class SystemEvent(TimeStampedModel):
    class Level(models.TextChoices):
        DEBUG = "debug", "Debug"
        INFO = "info", "Info"
        WARNING = "warning", "Warning"
        ERROR = "error", "Error"
        CRITICAL = "critical", "Critical"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", null=True, blank=True, on_delete=models.SET_NULL, related_name="system_events")
    level = models.CharField(max_length=16, choices=Level.choices, default=Level.INFO, db_index=True)
    source = models.CharField(max_length=160, db_index=True)
    event_type = models.CharField(max_length=160, db_index=True)
    message = models.TextField()
    trace_id = models.CharField(max_length=64, blank=True, db_index=True)
    data = models.JSONField(default=dict, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("level", "source", "created_at"))]


class ProviderHealth(TimeStampedModel):
    class Status(models.TextChoices):
        HEALTHY = "healthy", "Healthy"
        DEGRADED = "degraded", "Degraded"
        DOWN = "down", "Down"
        UNKNOWN = "unknown", "Unknown"

    provider = models.CharField(max_length=64)
    service = models.CharField(max_length=120)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.UNKNOWN, db_index=True)
    latency_ms = models.PositiveIntegerField(default=0)
    message = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    checked_at = models.DateTimeField()

    class Meta:
        ordering = ("provider", "service")
        constraints = [models.UniqueConstraint(fields=("provider", "service"), name="unique_provider_health")]


class AuditEvent(TimeStampedModel):
    organization = models.ForeignKey("organizations.Organization", null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_events")
    actor = models.ForeignKey("users.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_events")
    action = models.CharField(max_length=160, db_index=True)
    object_type = models.CharField(max_length=160, blank=True)
    object_id = models.CharField(max_length=160, blank=True)
    request_id = models.CharField(max_length=64, blank=True, db_index=True)
    ip_hash = models.CharField(max_length=64, blank=True)
    data = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("organization", "action", "created_at"))]
