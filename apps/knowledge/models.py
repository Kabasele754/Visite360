from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from pgvector.django import VectorField

from apps.common.models import TimeStampedModel


class KnowledgeSource(TimeStampedModel):
    class SourceType(models.TextChoices):
        WEBSITE = "website", "Website"
        DOCUMENT = "document", "Document"
        FAQ = "faq", "FAQ"
        PRODUCT = "product", "Product catalogue"
        SERVICE = "service", "Service catalogue"
        MANUAL = "manual", "Manual content"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        READY = "ready", "Ready"
        CRAWLING = "crawling", "Crawling"
        INDEXED = "indexed", "Indexed"
        FAILED = "failed", "Failed"
        DISABLED = "disabled", "Disabled"

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="knowledge_sources"
    )
    name = models.CharField(max_length=255)
    source_type = models.CharField(max_length=24, choices=SourceType.choices)
    url = models.URLField(blank=True)
    file = models.FileField(upload_to="knowledge/sources/%Y/%m/", null=True, blank=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT, db_index=True)
    crawl_same_domain_only = models.BooleanField(default=True)
    max_pages = models.PositiveSmallIntegerField(default=25)
    schedule = models.CharField(max_length=80, blank=True, help_text="Optional cron or human-readable schedule.")
    metadata = models.JSONField(default=dict, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(fields=("organization", "name"), name="unique_knowledge_source_name")
        ]

    def __str__(self) -> str:
        return f"{self.organization.name} — {self.name}"


class KnowledgeDocument(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.ForeignKey(KnowledgeSource, on_delete=models.CASCADE, related_name="documents")
    title = models.CharField(max_length=500)
    canonical_url = models.URLField(blank=True)
    external_id = models.CharField(max_length=255, blank=True)
    language = models.CharField(max_length=16, default="en")
    raw_content = models.TextField(blank=True)
    clean_content = models.TextField()
    checksum = models.CharField(max_length=64, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    indexed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("title",)
        constraints = [
            models.UniqueConstraint(
                fields=("source", "checksum"), name="unique_knowledge_document_checksum"
            )
        ]
        indexes = [models.Index(fields=("source", "external_id"))]


class KnowledgeChunk(TimeStampedModel):
    document = models.ForeignKey(KnowledgeDocument, on_delete=models.CASCADE, related_name="chunks")
    position = models.PositiveIntegerField(default=0)
    content = models.TextField()
    token_count = models.PositiveIntegerField(default=0)
    embedding = VectorField(dimensions=settings.AI_EMBEDDING_DIMENSIONS, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("document", "position")
        constraints = [
            models.UniqueConstraint(fields=("document", "position"), name="unique_knowledge_chunk_position")
        ]
        indexes = [models.Index(fields=("document", "position"))]


class FAQItem(TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="faq_items"
    )
    question = models.CharField(max_length=500)
    answer = models.TextField()
    category = models.CharField(max_length=120, blank=True)
    locale = models.CharField(max_length=16, default="en")
    order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("order", "question")


class ServiceOffering(TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="service_offerings"
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280)
    short_description = models.CharField(max_length=320, blank=True)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=120, blank=True)
    price_from = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=8, default="USD")
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    booking_url = models.URLField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(fields=("organization", "slug"), name="unique_service_slug_per_org")
        ]
