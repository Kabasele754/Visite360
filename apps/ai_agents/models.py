from __future__ import annotations

import uuid
from django.db import models
from apps.common.models import TimeStampedModel


class AgentDefinition(TimeStampedModel):
    class AgentType(models.TextChoices):
        WEBSITE = "website", "Website Agent"
        PRODUCT = "product", "Product Agent"
        SERVICE = "service", "Service Agent"
        VISION = "vision", "Vision Agent"
        SOCIAL = "social", "Social Agent"
        BOOKING = "booking", "Booking Agent"
        CRM = "crm", "CRM Agent"
        RECOMMENDATION = "recommendation", "Recommendation Agent"
        ANALYTICS = "analytics", "Analytics Agent"

    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="agent_definitions")
    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180)
    agent_type = models.CharField(max_length=32, choices=AgentType.choices)
    description = models.TextField(blank=True)
    system_prompt = models.TextField(blank=True)
    provider = models.CharField(max_length=24, blank=True)
    model_name = models.CharField(max_length=160, blank=True)
    tools = models.JSONField(default=list, blank=True)
    guardrails = models.JSONField(default=dict, blank=True)
    config = models.JSONField(default=dict, blank=True)
    is_enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)
        constraints = [models.UniqueConstraint(fields=("organization", "slug"), name="unique_agent_slug_per_org")]


class AgentRun(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        NEEDS_REVIEW = "needs_review", "Needs review"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent = models.ForeignKey(AgentDefinition, on_delete=models.CASCADE, related_name="runs")
    requested_by = models.ForeignKey("users.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="enterprise_agent_runs")
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PENDING, db_index=True)
    input = models.JSONField(default=dict, blank=True)
    output = models.JSONField(default=dict, blank=True)
    context_snapshot = models.JSONField(default=dict, blank=True)
    provider = models.CharField(max_length=24, blank=True)
    model_name = models.CharField(max_length=160, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at",)


class AgentToolInvocation(TimeStampedModel):
    run = models.ForeignKey(AgentRun, on_delete=models.CASCADE, related_name="tool_invocations")
    tool_name = models.CharField(max_length=120, db_index=True)
    arguments = models.JSONField(default=dict, blank=True)
    result = models.JSONField(default=dict, blank=True)
    succeeded = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)


class AgentMemory(TimeStampedModel):
    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="agent_memories")
    agent = models.ForeignKey(AgentDefinition, null=True, blank=True, on_delete=models.CASCADE, related_name="memories")
    namespace = models.CharField(max_length=120, default="default")
    key = models.CharField(max_length=255)
    value = models.JSONField(default=dict, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("organization", "agent", "namespace", "key"), name="unique_agent_memory_key")]
