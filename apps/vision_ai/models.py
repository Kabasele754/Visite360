from __future__ import annotations

import uuid

from django.db import models

from apps.common.models import TimeStampedModel


def vision_upload_to(instance, filename):
    organization_id = instance.organization_id or "platform"
    return f"vision/{organization_id}/{instance.id}/{filename}"


class VisionAnalysis(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        PARTIAL = "partial", "Partial"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="vision_analyses"
    )
    scene = models.ForeignKey(
        "tours.Scene360",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="enterprise_vision_analyses",
    )
    uploaded_image = models.ImageField(upload_to=vision_upload_to, null=True, blank=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PENDING, db_index=True)
    requested_providers = models.JSONField(default=list, blank=True)
    completed_providers = models.JSONField(default=list, blank=True)
    failed_providers = models.JSONField(default=dict, blank=True)
    scene_type = models.CharField(max_length=160, blank=True)
    summary = models.TextField(blank=True)
    features = models.JSONField(default=list, blank=True)
    products = models.JSONField(default=list, blank=True)
    extracted_text = models.TextField(blank=True)
    confidence = models.FloatField(default=0)
    raw_results = models.JSONField(default=dict, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("organization", "status", "created_at")),
            models.Index(fields=("scene", "created_at")),
        ]

    def __str__(self):
        return f"Vision {self.id} — {self.status}"


class VisionFrame(TimeStampedModel):
    analysis = models.ForeignKey(VisionAnalysis, on_delete=models.CASCADE, related_name="frames")
    frame_index = models.PositiveSmallIntegerField()
    yaw = models.FloatField(default=0)
    pitch = models.FloatField(default=0)
    image = models.ImageField(upload_to="vision/frames/%Y/%m/", null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("frame_index",)
        constraints = [
            models.UniqueConstraint(fields=("analysis", "frame_index"), name="unique_vision_frame")
        ]


class VisionDetection(TimeStampedModel):
    analysis = models.ForeignKey(VisionAnalysis, on_delete=models.CASCADE, related_name="detections")
    frame = models.ForeignKey(VisionFrame, null=True, blank=True, on_delete=models.CASCADE, related_name="detections")
    provider = models.CharField(max_length=32, db_index=True)
    label = models.CharField(max_length=160, db_index=True)
    confidence = models.FloatField(default=0)
    bbox = models.JSONField(default=list, blank=True, help_text="[x1, y1, x2, y2] in pixels or normalized coordinates.")
    attributes = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-confidence",)
        indexes = [models.Index(fields=("analysis", "label", "confidence"))]


class OCRTextBlock(TimeStampedModel):
    analysis = models.ForeignKey(VisionAnalysis, on_delete=models.CASCADE, related_name="ocr_blocks")
    frame = models.ForeignKey(VisionFrame, null=True, blank=True, on_delete=models.CASCADE, related_name="ocr_blocks")
    provider = models.CharField(max_length=32, default="paddleocr")
    text = models.TextField()
    confidence = models.FloatField(default=0)
    polygon = models.JSONField(default=list, blank=True)
    language = models.CharField(max_length=16, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("frame_id", "id")


class VisionInsight(TimeStampedModel):
    class Kind(models.TextChoices):
        OBJECT = "object", "Object"
        TEXT = "text", "Text"
        AREA = "area", "Area"

    analysis = models.ForeignKey(
        VisionAnalysis, on_delete=models.CASCADE, related_name="insights"
    )
    frame = models.ForeignKey(
        VisionFrame, null=True, blank=True, on_delete=models.CASCADE, related_name="insights"
    )
    kind = models.CharField(max_length=20, choices=Kind.choices, db_index=True)
    label = models.CharField(max_length=180, blank=True, db_index=True)
    title = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    confidence = models.FloatField(default=0)
    bbox = models.JSONField(default=list, blank=True)
    polygon = models.JSONField(default=list, blank=True)
    yaw = models.FloatField(default=0, help_text="Panorama yaw in radians.")
    pitch = models.FloatField(default=0, help_text="Marzipano pitch in radians.")
    angular_radius = models.FloatField(default=0.12, help_text="Approximate selection radius in radians.")
    source_providers = models.JSONField(default=list, blank=True)
    attributes = models.JSONField(default=dict, blank=True)
    related_product = models.ForeignKey(
        "vendors.Product", null=True, blank=True, on_delete=models.SET_NULL, related_name="vision_insights"
    )
    is_verified = models.BooleanField(default=False)

    class Meta:
        ordering = ("-confidence", "id")
        indexes = [
            models.Index(fields=("analysis", "kind", "confidence"), name="vision_ai_v_analysi_70db40_idx"),
            models.Index(fields=("analysis", "yaw", "pitch"), name="vision_ai_v_analysi_6641c1_idx"),
        ]

    def __str__(self):
        return f"{self.kind}: {self.title}"
