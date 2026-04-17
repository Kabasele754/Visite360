import uuid
from decimal import Decimal
from pathlib import Path

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.text import slugify

from apps.common.models import TimeStampedModel
from apps.organizations.models import Organization
from apps.places.models import Place
from apps.tours.utils_compress_image import compress_image, generate_thumbnail


def _safe_filename(filename, fallback="file"):
    ext = Path(filename).suffix.lower() or ".jpg"
    stem = slugify(Path(filename).stem) or fallback
    token = uuid.uuid4().hex[:12]
    return f"{stem}-{token}{ext}"


def tour_thumbnail_upload_to(instance, filename):
    return f"tours/thumbnails/{_safe_filename(filename, 'tour-thumbnail')}"


def tour_video_upload_to(instance, filename):
    return f"tours/videos/{_safe_filename(filename, 'tour-video')}"


def scene_panorama_upload_to(instance, filename):
    return f"tours/panoramas/{_safe_filename(filename, 'scene-panorama')}"


def scene_panorama_mobile_upload_to(instance, filename):
    return f"tours/panoramas/mobile/{_safe_filename(filename, 'scene-mobile')}"


def scene_thumbnail_upload_to(instance, filename):
    return f"tours/panoramas/thumbs/{_safe_filename(filename, 'scene-thumb')}"


def hotspot_ad_upload_to(instance, filename):
    return f"tours/hotspots/ads/{_safe_filename(filename, 'hotspot-ad')}"


def tour_photo_upload_to(instance, filename):
    return f"tours/photos/{_safe_filename(filename, 'tour-photo')}"


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

    thumbnail_image = models.ImageField(
        upload_to=tour_thumbnail_upload_to,
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
    def display_price(self):
        return self.price if self.price is not None else Decimal("0.00")

    @property
    def status_badge_class(self):
        return {
            self.Status.DRAFT: "status-draft",
            self.Status.PUBLISHED: "status-published",
            self.Status.INACTIVE: "status-inactive",
        }.get(self.status, "status-draft")

    def save(self, *args, **kwargs):
        if not self.slug and self.title:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def increment_views(self):
        self.view_count += 1
        self.save(update_fields=["view_count", "updated_at"])


class Scene360(TimeStampedModel):
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

    image_360 = models.ImageField(upload_to=scene_panorama_upload_to)
    image_360_mobile = models.ImageField(
        upload_to=scene_panorama_mobile_upload_to,
        null=True,
        blank=True,
    )
    thumbnail_image = models.ImageField(
        upload_to=scene_thumbnail_upload_to,
        null=True,
        blank=True,
    )

    order = models.PositiveIntegerField(default=0)

    yaw_default = models.FloatField(default=0)
    pitch_default = models.FloatField(default=0)
    hfov_default = models.FloatField(default=100)

    class Meta:
        ordering = ["order", "id"]
        indexes = [
            models.Index(fields=["organization", "tour"]),
            models.Index(fields=["tour", "order"]),
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
    def thumbnail_url(self):
        return self.thumbnail_image.url if self.thumbnail_image else None

    def generate_mobile_image(self, save=True):
        if not self.image_360:
            return

        clean_base_name = slugify(self.title) or f"scene-{self.pk or 'new'}"

        mobile_content, mobile_size_kb = compress_image(
            self.image_360,
            quality=90,
            add_watermark=False,
            max_width=2600,
            max_height=1300,
        )

        self.image_360_mobile.save(
            f"{clean_base_name}-mobile.webp",
            mobile_content,
            save=False,
        )

        thumb_content, thumb_size_kb = generate_thumbnail(
            self.image_360,
            size=(1200, 600),
            format="WEBP",
            quality=88,
        )

        self.thumbnail_image.save(
            f"{clean_base_name}-thumb.webp",
            thumb_content,
            save=False,
        )

        print(f"Image mobile générée : {mobile_size_kb} Ko")
        print(f"Thumbnail généré : {thumb_size_kb} Ko")

        if save:
            self._skip_mobile_generation = True
            try:
                super().save(update_fields=["image_360_mobile", "thumbnail_image", "updated_at"])
            finally:
                self._skip_mobile_generation = False

    def save(self, *args, **kwargs):
        if getattr(self, "_skip_mobile_generation", False):
            return super().save(*args, **kwargs)

        previous_image_name = None
        if self.pk:
            old = type(self).objects.filter(pk=self.pk).only("image_360").first()
            if old and old.image_360:
                previous_image_name = old.image_360.name

        current_image_name = self.image_360.name if self.image_360 else None
        image_changed = bool(current_image_name and current_image_name != previous_image_name)
        creating = self.pk is None

        super().save(*args, **kwargs)

        if self.image_360 and (creating or image_changed or not self.image_360_mobile or not self.thumbnail_image):
            self.generate_mobile_image(save=True)


class Hotspot(TimeStampedModel):
    class Type(models.TextChoices):
        NAVIGATE = "navigate", "Navigate"
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

    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["organization", "scene"]),
            models.Index(fields=["scene", "type"]),
        ]

    def __str__(self):
        return f"Hotspot {self.label} dans {self.scene.title}"

    @property
    def ad_image_url(self):
        return self.ad_image.url if self.ad_image else None


class TourPhoto(TimeStampedModel):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="tour_photos",
    )
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

    def __str__(self):
        return f"Photo for {self.tour.title}"