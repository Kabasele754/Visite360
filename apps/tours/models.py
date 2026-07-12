import uuid
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.common.models import TimeStampedModel
from apps.organizations.models import Organization
from apps.places.models import Place


# -----------------------------------------------------------------------------
# Shared choices
# -----------------------------------------------------------------------------
class PipelineStatus(models.TextChoices):
    NONE = "none", "None"
    PENDING = "pending", "Pending"
    PROCESSING = "processing", "Processing"
    READY = "ready", "Ready"
    FAILED = "failed", "Failed"


class DeliveryStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    SENT = "sent", "Sent"
    FAILED = "failed", "Failed"


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _safe_webp_name(filename, fallback="file"):
    stem = slugify(Path(filename).stem) or fallback
    token = uuid.uuid4().hex[:10]
    return f"{stem}-{token}.webp"


def _safe_original_file_name(filename, fallback="file"):
    path = Path(filename)
    stem = slugify(path.stem) or fallback
    suffix = path.suffix.lower() or ".bin"
    token = uuid.uuid4().hex[:10]
    return f"{stem}-{token}{suffix}"


def _unique_short_id(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


# -----------------------------------------------------------------------------
# Upload paths
# -----------------------------------------------------------------------------
def tour_thumbnail_source_upload_to(instance, filename):
    return f"tours/source/thumbnails/{_safe_original_file_name(filename, 'tour-thumb-source')}"


def tour_thumbnail_upload_to(instance, filename):
    return f"tours/thumbnails/{_safe_webp_name(filename, 'tour-thumb')}"


def tour_thumbnail_mobile_upload_to(instance, filename):
    return f"tours/thumbnails/mobile/{_safe_webp_name(filename, 'tour-thumb-mobile')}"


def tour_video_upload_to(instance, filename):
    return f"tours/videos/{_safe_original_file_name(filename, 'tour-video')}"


def scene_panorama_original_upload_to(instance, filename):
    return f"tours/panoramas/source/{_safe_original_file_name(filename, 'scene-original')}"


def scene_panorama_upload_to(instance, filename):
    return f"tours/panoramas/{_safe_webp_name(filename, 'scene-panorama')}"


def scene_panorama_mobile_upload_to(instance, filename):
    return f"tours/panoramas/mobile/{_safe_webp_name(filename, 'scene-mobile')}"


def scene_panorama_preview_upload_to(instance, filename):
    return f"tours/panoramas/previews/{_safe_webp_name(filename, 'scene-preview')}"


def scene_thumbnail_upload_to(instance, filename):
    return f"tours/panoramas/thumbs/{_safe_webp_name(filename, 'scene-thumb')}"


def scene_tile_upload_to(instance, filename):
    scene_key = getattr(instance.scene, "scene_id", None) or f"scene-{instance.scene_id}"
    return (
        f"tours/panoramas/tiles/"
        f"{scene_key}/"
        f"l{instance.level}/"
        f"{instance.face}/"
        f"{instance.x}_{instance.y}.webp"
    )


def hotspot_ad_upload_to(instance, filename):
    return f"tours/hotspots/ads/{_safe_webp_name(filename, 'hotspot-ad')}"


def hotspot_media_upload_to(instance, filename):
    return f"tours/hotspots/media/{_safe_original_file_name(filename, 'hotspot-media')}"


def hotspot_poster_upload_to(instance, filename):
    return f"tours/hotspots/posters/{_safe_webp_name(filename, 'hotspot-poster')}"


def tour_photo_upload_to(instance, filename):
    return f"tours/photos/{_safe_webp_name(filename, 'tour-photo')}"


# -----------------------------------------------------------------------------
# Tour
# -----------------------------------------------------------------------------
class Tour(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        INACTIVE = "inactive", "Inactive"

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="tours",
    )
    place = models.ForeignKey(
        Place,
        on_delete=models.CASCADE,
        related_name="tours",
    )

    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)

    thumbnail_source = models.ImageField(
        upload_to=tour_thumbnail_source_upload_to,
        null=True,
        blank=True,
    )
    thumbnail_image = models.ImageField(
        upload_to=tour_thumbnail_upload_to,
        null=True,
        blank=True,
    )
    thumbnail_image_mobile = models.ImageField(
        upload_to=tour_thumbnail_mobile_upload_to,
        null=True,
        blank=True,
    )

    video_tour = models.FileField(
        upload_to=tour_video_upload_to,
        null=True,
        blank=True,
    )
    virtual_tour_url = models.URLField(null=True, blank=True)

    version = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    manifest = models.JSONField(default=dict, blank=True)

    tour_date = models.DateField(null=True, blank=True)
    duration = models.DurationField(null=True, blank=True)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        default=Decimal("0.00"),
    )
    is_featured = models.BooleanField(default=False)
    max_participants = models.PositiveIntegerField(null=True, blank=True)

    rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
    )
    view_count = models.PositiveIntegerField(default=0)

    guide_name = models.CharField(max_length=255, null=True, blank=True)
    contact_email = models.EmailField(null=True, blank=True)

    location = models.CharField(max_length=255, blank=True, null=True)
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)
    radius = models.FloatField(default=100)

    chambres = models.IntegerField(null=True, blank=True)
    balcon = models.BooleanField(default=False)
    floor_number = models.IntegerField(null=True, blank=True)
    parking = models.BooleanField(default=False)
    ascenseur = models.BooleanField(default=False)

    thumbnail_status = models.CharField(
        max_length=20,
        choices=PipelineStatus.choices,
        default=PipelineStatus.NONE,
    )
    thumbnail_error = models.TextField(blank=True, default="")
    thumbnail_generated_at = models.DateTimeField(null=True, blank=True)

    publish_email_status = models.CharField(
        max_length=20,
        choices=DeliveryStatus.choices,
        null=True,
        blank=True,
    )
    publish_email_error = models.TextField(blank=True, default="")
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["organization", "created_at"]),
            models.Index(fields=["organization", "is_featured"]),
            models.Index(fields=["place", "status"]),
            models.Index(fields=["slug"]),
            models.Index(fields=["is_featured"]),
        ]

    def __str__(self):
        return self.title

    @property
    def thumbnail_image_url(self):
        return self.thumbnail_image.url if self.thumbnail_image else None

    @property
    def thumbnail_image_mobile_url(self):
        return self.thumbnail_image_mobile.url if self.thumbnail_image_mobile else None

    @property
    def display_price(self):
        return self.price if self.price is not None else Decimal("0.00")

    @property
    def status_badge_class(self):
        return {
            self.Status.DRAFT: "status-draft",
            self.Status.PUBLISHED: "status-published",
            self.Status.INACTIVE: "status-inactive",
        }.get(self.status, "status-draft")

    def increment_views(self):
        self.view_count += 1
        self.save(update_fields=["view_count", "updated_at"])

    def queue_thumbnail_generation(self):
        def _enqueue():
            from apps.tours.tasks import generate_tour_thumbnail_assets_task
            generate_tour_thumbnail_assets_task.delay(self.pk)

        transaction.on_commit(_enqueue)

    def queue_publish_email(self):
        def _enqueue():
            from apps.tours.tasks import send_tour_published_email_task
            send_tour_published_email_task.delay(self.pk)

        transaction.on_commit(_enqueue)

    def save(self, *args, **kwargs):
        if not self.slug and self.title:
            self.slug = slugify(self.title)

        old = None
        if self.pk:
            old = type(self).objects.filter(pk=self.pk).only(
                "thumbnail_source",
                "status",
                "published_at",
            ).first()

        source_changed = False
        if self.thumbnail_source:
            old_name = old.thumbnail_source.name if old and old.thumbnail_source else None
            source_changed = self.thumbnail_source.name != old_name

        just_published = (
            old
            and old.status != self.Status.PUBLISHED
            and self.status == self.Status.PUBLISHED
        )

        creating = self.pk is None

        if self.thumbnail_source and (creating or source_changed):
            self.thumbnail_status = PipelineStatus.PENDING
            self.thumbnail_error = ""

        if self.status == self.Status.PUBLISHED and not self.published_at:
            self.published_at = timezone.now()

        super().save(*args, **kwargs)

        if self.thumbnail_source and (creating or source_changed):
            if getattr(settings, "TOURS_AUTO_QUEUE_TOUR_ASSETS", True):
                self.queue_thumbnail_generation()

        if just_published or (
            creating and self.status == self.Status.PUBLISHED
        ):
            if getattr(settings, "TOURS_AUTO_QUEUE_PUBLISH_EMAIL", True):
                self.publish_email_status = DeliveryStatus.PENDING
                super().save(update_fields=["publish_email_status", "updated_at"])
                self.queue_publish_email()
                


class TourUniqueView(TimeStampedModel):
    """
    Une vue unique par tour et par visiteur.
    - Si l'utilisateur est connecté : visitor_key = user:<id>
    - Sinon : visitor_key = cookie anonyme vtour_visitor_id
    """
    tour = models.ForeignKey(
        Tour,
        on_delete=models.CASCADE,
        related_name="unique_views",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tour_unique_views",
    )
    visitor_key = models.CharField(max_length=120, db_index=True)
    ip_hash = models.CharField(max_length=64, blank=True, default="")
    user_agent_hash = models.CharField(max_length=64, blank=True, default="")

    class Meta:
        indexes = [
            models.Index(fields=["tour", "visitor_key"]),
            models.Index(fields=["tour", "created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tour", "visitor_key"],
                name="unique_tour_view_per_visitor",
            )
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"Unique view {self.tour_id} - {self.visitor_key}"


class TourShare(TimeStampedModel):
    class Channel(models.TextChoices):
        WEB_SHARE = "web_share", "Web Share"
        COPY_LINK = "copy_link", "Copy Link"
        WHATSAPP = "whatsapp", "WhatsApp"
        FACEBOOK = "facebook", "Facebook"
        OTHER = "other", "Other"

    tour = models.ForeignKey(
        Tour,
        on_delete=models.CASCADE,
        related_name="shares",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tour_shares",
    )
    visitor_key = models.CharField(max_length=120, db_index=True)
    channel = models.CharField(
        max_length=30,
        choices=Channel.choices,
        default=Channel.OTHER,
    )
    ip_hash = models.CharField(max_length=64, blank=True, default="")
    user_agent_hash = models.CharField(max_length=64, blank=True, default="")

    class Meta:
        indexes = [
            models.Index(fields=["tour", "created_at"]),
            models.Index(fields=["tour", "channel"]),
            models.Index(fields=["visitor_key"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"Share {self.tour_id} - {self.channel}"



# -----------------------------------------------------------------------------
# Scene360
# -----------------------------------------------------------------------------
class Scene360(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        INACTIVE = "inactive", "Inactive"

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="scenes",
    )
    tour = models.ForeignKey(
        Tour,
        on_delete=models.CASCADE,
        related_name="scenes",
    )

    scene_id = models.CharField(max_length=100, unique=True, blank=True, null=True)
    title = models.CharField(max_length=255)

    image_360_original = models.ImageField(
        upload_to=scene_panorama_original_upload_to,
        null=True, blank=True
    )

    image_360 = models.ImageField(
        upload_to=scene_panorama_upload_to,
        null=True,
        blank=True,
    )
    image_360_mobile = models.ImageField(
        upload_to=scene_panorama_mobile_upload_to,
        null=True,
        blank=True,
    )
    image_360_preview = models.ImageField(
        upload_to=scene_panorama_preview_upload_to,
        null=True,
        blank=True,
    )
    thumbnail_image = models.ImageField(
        upload_to=scene_thumbnail_upload_to,
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    
    # Permet de cacher/afficher une scène dans le preview public
    is_public = models.BooleanField(default=True)

    order = models.PositiveIntegerField(default=0)

    yaw_default = models.FloatField(default=0)
    pitch_default = models.FloatField(default=0)
    hfov_default = models.FloatField(default=100)

    # Assets pipeline
    assets_status = models.CharField(
        max_length=20,
        choices=PipelineStatus.choices,
        default=PipelineStatus.NONE,
    )
    assets_error = models.TextField(blank=True, default="")
    assets_generated_at = models.DateTimeField(null=True, blank=True)

    # Tiles
    tiles_enabled = models.BooleanField(default=True)
    tiles_status = models.CharField(
        max_length=20,
        choices=PipelineStatus.choices,
        default=PipelineStatus.NONE,
    )
    tiles_manifest = models.JSONField(default=dict, blank=True)
    tiles_generated_at = models.DateTimeField(null=True, blank=True)
    tiles_error = models.TextField(blank=True, default="")
    tile_size = models.PositiveIntegerField(default=512)
    max_tile_cube_size = models.PositiveIntegerField(default=2048)

    # AI analysis
    ai_analysis_status = models.CharField(
        max_length=20,
        choices=PipelineStatus.choices,
        default=PipelineStatus.NONE,
    )
    ai_analysis = models.JSONField(default=dict, blank=True)
    ai_analysis_error = models.TextField(blank=True, default="")
    ai_analyzed_at = models.DateTimeField(null=True, blank=True)

    # AI hotspots
    ai_hotspots_status = models.CharField(
        max_length=20,
        choices=PipelineStatus.choices,
        default=PipelineStatus.NONE,
    )
    ai_hotspot_suggestions = models.JSONField(default=list, blank=True)
    ai_hotspot_error = models.TextField(blank=True, default="")
    ai_hotspots_generated_at = models.DateTimeField(null=True, blank=True)

    # Intelligent prefetch
    prefetch_manifest = models.JSONField(default=dict, blank=True)
    prefetch_generated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["order", "id"]
        indexes = [
            models.Index(fields=["organization", "tour"]),
            models.Index(fields=["tour", "order"]),
            models.Index(fields=["tour", "status"]),
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["tour", "is_public"]),
            models.Index(fields=["organization", "is_public"]),
            models.Index(fields=["tour", "is_public", "order"]),
            models.Index(fields=["assets_status"]),
            models.Index(fields=["tiles_status"]),
            models.Index(fields=["ai_analysis_status"]),
            models.Index(fields=["ai_hotspots_status"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.tour.title})"

    @property
    def image_360_url(self):
        return self.image_360.url if self.image_360 else None

    @property
    def image_360_mobile_url(self):
        return self.image_360_mobile.url if self.image_360_mobile else None

    @property
    def image_360_preview_url(self):
        return self.image_360_preview.url if self.image_360_preview else None

    @property
    def thumbnail_url(self):
        return self.thumbnail_image.url if self.thumbnail_image else None

    @property
    def is_published(self):
        return self.status == self.Status.PUBLISHED

    def queue_full_pipeline(self):
        def _enqueue():
            from apps.tours.tasks import run_scene_pipeline_task
            run_scene_pipeline_task.delay(self.pk)

        transaction.on_commit(_enqueue)

    def save(self, *args, **kwargs):
        if self.tour_id and self.organization_id != self.tour.organization_id:
            self.organization = self.tour.organization

        if not self.scene_id:
            self.scene_id = _unique_short_id("scene")

        old = None
        if self.pk:
            old = type(self).objects.filter(pk=self.pk).only("image_360_original").first()

        image_changed = False
        if self.image_360_original:
            old_name = old.image_360_original.name if old and old.image_360_original else None
            image_changed = self.image_360_original.name != old_name

        creating = self.pk is None

        if self.image_360_original and (creating or image_changed):
            self.assets_status = PipelineStatus.PENDING
            self.assets_error = ""

            self.tiles_status = PipelineStatus.PENDING if self.tiles_enabled else PipelineStatus.NONE
            self.tiles_error = ""

            self.ai_analysis_status = PipelineStatus.PENDING
            self.ai_analysis_error = ""

            self.ai_hotspots_status = PipelineStatus.PENDING
            self.ai_hotspot_error = ""

        super().save(*args, **kwargs)

        if self.image_360_original and (creating or image_changed):
            if getattr(settings, "TOURS_AUTO_QUEUE_SCENE_PIPELINE", True):
                self.queue_full_pipeline()


# -----------------------------------------------------------------------------
# Scene360Tile
# -----------------------------------------------------------------------------
class Scene360Tile(TimeStampedModel):
    class Face(models.TextChoices):
        FRONT = "f", "Front"
        BACK = "b", "Back"
        LEFT = "l", "Left"
        RIGHT = "r", "Right"
        UP = "u", "Up"
        DOWN = "d", "Down"

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="scene_360_tiles",
    )
    scene = models.ForeignKey(
        Scene360,
        on_delete=models.CASCADE,
        related_name="tiles",
    )

    level = models.PositiveIntegerField()
    cube_size = models.PositiveIntegerField(default=512)

    face = models.CharField(max_length=1, choices=Face.choices)

    x = models.PositiveIntegerField()
    y = models.PositiveIntegerField()

    width = models.PositiveIntegerField(default=512)
    height = models.PositiveIntegerField(default=512)

    image = models.ImageField(upload_to=scene_tile_upload_to)

    size_kb = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    quality = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["scene", "level", "face", "y", "x"]
        constraints = [
            models.UniqueConstraint(
                fields=["scene", "level", "face", "x", "y"],
                name="unique_scene360_tile",
            )
        ]
        indexes = [
            models.Index(fields=["organization", "scene"]),
            models.Index(fields=["scene", "level"]),
            models.Index(fields=["scene", "level", "face"]),
            models.Index(fields=["scene", "face", "x", "y"]),
        ]

    def __str__(self):
        return f"{self.scene.title} | L{self.level} {self.face} ({self.x},{self.y})"

    @property
    def image_url(self):
        return self.image.url if self.image else None


# -----------------------------------------------------------------------------
# Hotspot
# -----------------------------------------------------------------------------
class Hotspot(TimeStampedModel):
    class Type(models.TextChoices):
        NAVIGATE = "navigate", "Navigate"
        FLOOR = "floor", "Floor navigation"
        PDF = "pdf", "PDF document"
        VIDEO = "video", "Video"
        DOOR = "door", "Interactive door"
        INFO = "info", "Info"
        CTA = "cta", "CTA"
        PRODUCT = "product", "Product"
        CUSTOM = "custom", "Custom"

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="hotspots",
    )
    scene = models.ForeignKey(
        Scene360,
        on_delete=models.CASCADE,
        related_name="hotspots",
    )

    hotspot_id = models.CharField(max_length=100, blank=True, null=True)
    type = models.CharField(max_length=20, choices=Type.choices)
    label = models.CharField(max_length=255)

    yaw = models.FloatField()
    pitch = models.FloatField()

    target_scene = models.ForeignKey(
        Scene360,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="incoming_hotspots",
    )

    tooltip_text = models.CharField(max_length=255, null=True, blank=True)
    title = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    selected_icon = models.CharField(max_length=255, blank=True, null=True)

    ad_image = models.ImageField(
        upload_to=hotspot_ad_upload_to,
        blank=True,
        null=True,
    )

    media_file = models.FileField(
        upload_to=hotspot_media_upload_to,
        blank=True,
        null=True,
    )
    poster_image = models.ImageField(
        upload_to=hotspot_poster_upload_to,
        blank=True,
        null=True,
    )

    payload = models.JSONField(default=dict, blank=True)
    is_ai_generated = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["organization", "scene"]),
            models.Index(fields=["scene", "type"]),
            models.Index(fields=["scene", "is_ai_generated"]),
        ]

    def __str__(self):
        return f"Hotspot {self.label} dans {self.scene.title}"

    @property
    def ad_image_url(self):
        return self.ad_image.url if self.ad_image else None

    @property
    def media_file_url(self):
        return self.media_file.url if self.media_file else None

    @property
    def poster_image_url(self):
        return self.poster_image.url if self.poster_image else None

    def save(self, *args, **kwargs):
        if self.scene_id and self.organization_id != self.scene.organization_id:
            self.organization = self.scene.organization

        if not self.hotspot_id:
            self.hotspot_id = _unique_short_id("hotspot")

        if self.type not in {self.Type.NAVIGATE, self.Type.FLOOR, self.Type.DOOR}:
            self.target_scene = None

        super().save(*args, **kwargs)


# -----------------------------------------------------------------------------
# TourPhoto
# -----------------------------------------------------------------------------
class TourPhoto(TimeStampedModel):
    tour = models.ForeignKey(
        Tour,
        on_delete=models.CASCADE,
        related_name="photos",
    )
    image = models.ImageField(upload_to=tour_photo_upload_to)
    caption = models.CharField(max_length=255, blank=True, null=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        indexes = [
            models.Index(fields=["tour", "order"]),
        ]

    def __str__(self):
        return f"Photo {self.order} - {self.tour.title}"

    @property
    def image_url(self):
        return self.image.url if self.image else None


# -----------------------------------------------------------------------------
# Tour email log
# -----------------------------------------------------------------------------
class TourEmailLog(TimeStampedModel):
    tour = models.ForeignKey(
        Tour,
        on_delete=models.CASCADE,
        related_name="email_logs",
    )
    recipient = models.EmailField()
    subject = models.CharField(max_length=255)
    body = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=20,
        choices=DeliveryStatus.choices,
        default=DeliveryStatus.PENDING,
    )
    error = models.TextField(blank=True, default="")
    provider_response = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tour", "status"]),
            models.Index(fields=["recipient"]),
        ]

    def __str__(self):
        return f"{self.recipient} - {self.tour.title} ({self.status})"