from __future__ import annotations

import uuid

from django.db import models

from apps.common.models import TimeStampedModel


class AIProviderConfiguration(TimeStampedModel):
    class Provider(models.TextChoices):
        GEMINI = "gemini", "Google Gemini / Vertex AI"
        OPENAI = "openai", "OpenAI"
        LOCAL = "local", "Local model"

    class Capability(models.TextChoices):
        TEXT = "text", "Text"
        VISION = "vision", "Vision"
        EMBEDDING = "embedding", "Embedding"
        IMAGE = "image", "Image generation"

    organization = models.ForeignKey(
        "organizations.Organization",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="ai_provider_configurations",
        help_text="Leave empty for a platform-wide default.",
    )
    provider = models.CharField(max_length=24, choices=Provider.choices)
    capability = models.CharField(max_length=24, choices=Capability.choices)
    model_name = models.CharField(max_length=160)
    credential_reference = models.CharField(
        max_length=160,
        blank=True,
        help_text="Environment variable or secret reference; never store the raw key here.",
    )
    settings = models.JSONField(default=dict, blank=True)
    priority = models.PositiveSmallIntegerField(default=100)
    is_enabled = models.BooleanField(default=True)
    last_health_status = models.CharField(max_length=32, blank=True)
    last_health_message = models.TextField(blank=True)
    last_health_checked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("priority", "provider", "capability")
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "provider", "capability", "model_name"),
                name="unique_ai_provider_configuration",
            )
        ]

    def __str__(self) -> str:
        owner = self.organization.slug if self.organization_id else "platform"
        return f"{owner}: {self.provider}/{self.capability}/{self.model_name}"


class AIRun(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ai_runs",
    )
    requested_by = models.ForeignKey(
        "users.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ai_runs",
    )
    operation = models.CharField(max_length=120, db_index=True)
    provider = models.CharField(max_length=24, blank=True, db_index=True)
    model_name = models.CharField(max_length=160, blank=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PENDING, db_index=True)
    trace_id = models.CharField(max_length=64, blank=True, db_index=True)
    input_summary = models.TextField(blank=True)
    output_summary = models.TextField(blank=True)
    input_metadata = models.JSONField(default=dict, blank=True)
    output_metadata = models.JSONField(default=dict, blank=True)
    prompt_tokens = models.PositiveIntegerField(default=0)
    completion_tokens = models.PositiveIntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    latency_ms = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    error_type = models.CharField(max_length=160, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("organization", "operation", "created_at")),
            models.Index(fields=("provider", "status", "created_at")),
        ]


class AIUsageDaily(TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="ai_usage_daily"
    )
    date = models.DateField()
    provider = models.CharField(max_length=24)
    model_name = models.CharField(max_length=160, blank=True)
    requests = models.PositiveIntegerField(default=0)
    failures = models.PositiveIntegerField(default=0)
    prompt_tokens = models.PositiveBigIntegerField(default=0)
    completion_tokens = models.PositiveBigIntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=14, decimal_places=6, default=0)

    class Meta:
        ordering = ("-date",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "date", "provider", "model_name"),
                name="unique_ai_usage_daily",
            )
        ]
