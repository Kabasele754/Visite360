from django.db import models
from apps.common.models import TimeStampedModel
from apps.places.models import Place
from apps.organizations.models import Organization


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

    # identité de la visite
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)

    # contenu de visite
    thumbnail_image = models.ImageField(upload_to="tours/thumbnails/", null=True, blank=True)
    video_tour = models.FileField(upload_to="tours/videos/", null=True, blank=True)
    virtual_tour_url = models.URLField(null=True, blank=True)

    # logique métier / commerciale
    version = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    manifest = models.JSONField(default=dict, blank=True)

    tour_date = models.DateField(null=True, blank=True)
    duration = models.DurationField(null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    is_featured = models.BooleanField(default=False)
    max_participants = models.PositiveIntegerField(null=True, blank=True)

    rating = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    view_count = models.PositiveIntegerField(default=0)

    guide_name = models.CharField(max_length=255, null=True, blank=True)
    contact_email = models.EmailField(null=True, blank=True)

    # contexte géo complémentaire si nécessaire pour la visite
    location = models.CharField(max_length=255, blank=True, null=True)
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)
    radius = models.FloatField(default=100)

    # détails utiles selon le type de lieu / immobilier / événementiel
    chambres = models.IntegerField(null=True, blank=True)
    balcon = models.BooleanField(default=False)
    floor_number = models.IntegerField(null=True, blank=True)
    parking = models.BooleanField(default=False)
    ascenseur = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["place", "status"]),
            models.Index(fields=["slug"]),
            models.Index(fields=["is_featured"]),
        ]

    def __str__(self):
        return self.title

    @property
    def thumbnail_image_url(self):
        if self.thumbnail_image:
            return self.thumbnail_image.url
        return None

    # def increment_views(self):
    #     self.view_count += 1
    #     self.save(update_fields=["view_count", "updated_at"])


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

    image_360 = models.ImageField(upload_to="tours/panoramas/")
    thumbnail_image = models.ImageField(upload_to="tours/panoramas/thumbs/", null=True, blank=True)

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
        if self.image_360:
            return self.image_360.url
        return None

    @property
    def thumbnail_url(self):
        if self.thumbnail_image:
            return self.thumbnail_image.url
        return None


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
    ad_image = models.ImageField(upload_to="tours/hotspots/ads/", blank=True, null=True)

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
        if self.ad_image:
            return self.ad_image.url
        return None


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
    image = models.ImageField(upload_to="tours/photos/")
    caption = models.CharField(max_length=255, blank=True, null=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"Photo for {self.tour.title}"
    
    