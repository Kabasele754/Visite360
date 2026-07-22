from __future__ import annotations

import uuid
from django.conf import settings
from django.db import models
from apps.common.models import TimeStampedModel


class EnterpriseConversation(TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        CONVERTED = "converted", "Converted"
        CLOSED = "closed", "Closed"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="enterprise_conversations")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="enterprise_conversations")
    visitor_id = models.CharField(max_length=120, blank=True, db_index=True)
    session_id = models.CharField(max_length=120, blank=True, db_index=True)
    tour = models.ForeignKey("tours.Tour", null=True, blank=True, on_delete=models.SET_NULL, related_name="enterprise_conversations")
    scene = models.ForeignKey("tours.Scene360", null=True, blank=True, on_delete=models.SET_NULL, related_name="enterprise_conversations")
    agent = models.ForeignKey("ai_agents.AgentDefinition", null=True, blank=True, on_delete=models.SET_NULL, related_name="conversations")
    locale = models.CharField(max_length=16, default="en")
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    title = models.CharField(max_length=255, blank=True)
    summary = models.TextField(blank=True)
    lead_score = models.PositiveSmallIntegerField(default=0)
    consent_marketing = models.BooleanField(default=False)
    last_activity_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-last_activity_at",)
        indexes = [models.Index(fields=("organization", "status", "last_activity_at"))]


class EnterpriseMessage(TimeStampedModel):
    class Role(models.TextChoices):
        SYSTEM = "system", "System"
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"
        TOOL = "tool", "Tool"

    conversation = models.ForeignKey(EnterpriseConversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=16, choices=Role.choices)
    content = models.TextField(blank=True)
    citations = models.JSONField(default=list, blank=True)
    confidence = models.FloatField(default=0)
    intent = models.CharField(max_length=120, blank=True)
    validation = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("created_at", "id")
        indexes = [models.Index(fields=("conversation", "created_at"))]


class ConversationFeedback(TimeStampedModel):
    conversation = models.ForeignKey(EnterpriseConversation, on_delete=models.CASCADE, related_name="feedback")
    message = models.ForeignKey(EnterpriseMessage, null=True, blank=True, on_delete=models.SET_NULL, related_name="feedback")
    rating = models.SmallIntegerField(null=True, blank=True)
    helpful = models.BooleanField(null=True, blank=True)
    comment = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
