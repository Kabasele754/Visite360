import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


def streetview_scene_upload_path(instance, filename):
    tour_id = instance.tour_id or "draft"
    return f"streetview/tours/{tour_id}/scenes/{uuid.uuid4()}_{filename}"


class StreetViewGoogleAccount(models.Model):
    """OAuth tokens for the Google account that will publish Street View photos."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="streetview_google_account")
    google_email = models.EmailField(blank=True)

    access_token = models.TextField(blank=True)
    refresh_token = models.TextField(blank=True)
    token_uri = models.URLField(default="https://oauth2.googleapis.com/token")
    scopes = models.TextField(blank=True)
    token_expiry = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Street View Google Account"
        verbose_name_plural = "Street View Google Accounts"

    def __str__(self):
        return f"Street View Google Account - {self.user}"

    @property
    def is_connected(self):
        return bool(self.refresh_token or self.access_token)

    @property
    def is_expired(self):
        if not self.token_expiry:
            return True
        return self.token_expiry <= timezone.now()


class StreetViewTour(models.Model):
    class ProjectMode(models.TextChoices):
        DIRECT = "direct", "Direct Google project"
        MANAGED = "managed", "Managed Street View project"

    class StoragePolicy(models.TextChoices):
        KEEP_LOCAL = "keep_local", "Keep local originals"
        DELETE_AFTER_VERIFIED = "delete_after_verified", "Delete local bytes after Google verification"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        READY = "ready", "Ready"
        PUBLISHING = "publishing", "Publishing"
        PUBLISHED = "published", "Published"
        FAILED = "failed", "Failed"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="streetview_tours")
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    project_mode = models.CharField(max_length=20, choices=ProjectMode.choices, default=ProjectMode.DIRECT)
    storage_policy = models.CharField(max_length=32, choices=StoragePolicy.choices, default=StoragePolicy.KEEP_LOCAL)
    google_place_id = models.CharField(max_length=255, blank=True)
    auto_connect = models.BooleanField(default=True)
    auto_sync_status = models.BooleanField(default=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.DRAFT)
    last_error = models.TextField(blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["owner", "status"], name="app_street_owner_i_77a8f0_idx"),
            models.Index(fields=["public_id"], name="app_street_public__149887_idx"),
        ]

    def __str__(self):
        return self.title

    def mark_ready_if_valid(self):
        if self.scenes.exists() and self.scenes.filter(latitude__isnull=False, longitude__isnull=False).exists():
            if self.status == self.Status.DRAFT:
                self.status = self.Status.READY
                self.save(update_fields=["status", "updated_at"])


class StreetViewScene(models.Model):
    class PublishStatus(models.TextChoices):
        LOCAL = "local", "Local"
        READY = "ready", "Ready"
        UPLOADING = "uploading", "Uploading"
        CREATED = "created", "Created"
        CONNECTED = "connected", "Connected"
        FAILED = "failed", "Failed"

    tour = models.ForeignKey(StreetViewTour, on_delete=models.CASCADE, related_name="scenes")
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    image = models.ImageField(
        upload_to=streetview_scene_upload_path,
        validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp", "tif", "tiff"])],
        blank=True,
    )
    image_width = models.PositiveIntegerField(default=0)
    image_height = models.PositiveIntegerField(default=0)
    file_size = models.PositiveBigIntegerField(default=0)

    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    altitude = models.FloatField(null=True, blank=True)

    # Marzipano / editor orientation. For Google create, heading/pitch/roll should also exist in Photo Sphere XMP.
    heading = models.FloatField(default=0, validators=[MinValueValidator(0), MaxValueValidator(360)])
    pitch = models.FloatField(default=0, validators=[MinValueValidator(-90), MaxValueValidator(90)])
    roll = models.FloatField(default=0, validators=[MinValueValidator(-180), MaxValueValidator(180)])
    initial_yaw = models.FloatField(default=0)
    initial_pitch = models.FloatField(default=0)
    initial_fov = models.FloatField(default=90)

    capture_time = models.DateTimeField(null=True, blank=True)
    xmp_detected = models.BooleanField(default=False)
    exif_data = models.JSONField(default=dict, blank=True)

    google_photo_id = models.CharField(max_length=255, blank=True)
    google_share_link = models.URLField(blank=True)
    google_thumbnail_url = models.URLField(blank=True)
    upload_reference_url = models.TextField(blank=True)
    publish_status = models.CharField(max_length=30, choices=PublishStatus.choices, default=PublishStatus.LOCAL)
    google_maps_publish_status = models.CharField(max_length=64, blank=True, db_index=True)
    google_transfer_status = models.CharField(max_length=64, blank=True)
    google_view_count = models.PositiveBigIntegerField(default=0)
    google_last_synced_at = models.DateTimeField(null=True, blank=True)
    google_status_payload = models.JSONField(default=dict, blank=True)
    connection_sync_status = models.CharField(max_length=32, blank=True, default="pending", db_index=True)
    connection_audit = models.JSONField(default=dict, blank=True)
    remote_only = models.BooleanField(default=False)
    local_bytes_deleted_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)

    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "id"]
        indexes = [
            models.Index(fields=["tour", "order"], name="app_street_tour_id_7bf1c3_idx"),
            models.Index(fields=["google_photo_id"], name="app_street_google__a08763_idx"),
        ]

    def __str__(self):
        return f"{self.tour.title} / {self.title}"

    @property
    def has_gps(self):
        return self.latitude is not None and self.longitude is not None

    @property
    def is_full_360_ratio(self):
        if not self.image_width or not self.image_height:
            return False
        ratio = self.image_width / max(self.image_height, 1)
        return 1.85 <= ratio <= 2.15

    def clean(self):
        if self.latitude is not None and not Decimal("-90") <= self.latitude <= Decimal("90"):
            raise ValidationError({"latitude": "Latitude must be between -90 and 90."})
        if self.longitude is not None and not Decimal("-180") <= self.longitude <= Decimal("180"):
            raise ValidationError({"longitude": "Longitude must be between -180 and 180."})


class StreetViewConnection(models.Model):
    tour = models.ForeignKey(StreetViewTour, on_delete=models.CASCADE, related_name="connections")
    from_scene = models.ForeignKey(StreetViewScene, on_delete=models.CASCADE, related_name="outgoing_connections")
    to_scene = models.ForeignKey(StreetViewScene, on_delete=models.CASCADE, related_name="incoming_connections")

    # Direction of the visual arrow in Marzipano from from_scene to to_scene.
    yaw = models.FloatField(default=0)
    pitch = models.FloatField(default=0)
    label = models.CharField(max_length=120, blank=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["tour", "from_scene", "to_scene"], name="unique_streetview_connection"),
        ]

    def __str__(self):
        return f"{self.from_scene_id} → {self.to_scene_id}"

    def clean(self):
        if self.from_scene_id == self.to_scene_id:
            raise ValidationError("A scene cannot be connected to itself.")
        if self.from_scene and self.to_scene and self.from_scene.tour_id != self.to_scene.tour_id:
            raise ValidationError("Connected scenes must be in the same tour.")


class StreetViewHotspot(models.Model):
    class Type(models.TextChoices):
        INFO = "info", "Info"
        LINK = "link", "Link"
        URL = "url", "URL"

    scene = models.ForeignKey(StreetViewScene, on_delete=models.CASCADE, related_name="hotspots")
    type = models.CharField(max_length=20, choices=Type.choices, default=Type.INFO)
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    target_scene = models.ForeignKey(
        StreetViewScene,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="targeted_hotspots",
    )
    url = models.URLField(blank=True)
    yaw = models.FloatField(default=0)
    pitch = models.FloatField(default=0)
    icon = models.CharField(max_length=80, blank=True)
    css_class = models.CharField(max_length=80, blank=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.title

    def clean(self):
        if self.type == self.Type.LINK and not self.target_scene_id:
            raise ValidationError({"target_scene": "A link hotspot requires a target scene."})
        if self.type == self.Type.URL and not self.url:
            raise ValidationError({"url": "A URL hotspot requires a URL."})
        if self.target_scene_id and self.target_scene.tour_id != self.scene.tour_id:
            raise ValidationError("Target scene must be in the same tour.")


class StreetViewPublishJob(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        SUCCEEDED_WITH_WARNINGS = "succeeded_with_warnings", "Succeeded with warnings"
        FAILED = "failed", "Failed"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    tour = models.ForeignKey(StreetViewTour, on_delete=models.CASCADE, related_name="publish_jobs")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="streetview_publish_jobs")
    status = models.CharField(max_length=40, choices=Status.choices, default=Status.QUEUED)
    total_scenes = models.PositiveIntegerField(default=0)
    published_scenes = models.PositiveIntegerField(default=0)
    failed_scenes = models.PositiveIntegerField(default=0)
    log = models.JSONField(default=list, blank=True)
    error = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Publish job {self.public_id} - {self.status}"

    def append_log(self, level, message, **extra):
        entry = {
            "time": timezone.now().isoformat(),
            "level": level,
            "message": message,
            **extra,
        }
        current = list(self.log or [])
        current.append(entry)
        self.log = current
        self.save(update_fields=["log", "updated_at"])


# -----------------------------------------------------------------------------
# Canonical publishing layer
# -----------------------------------------------------------------------------
# These models DO NOT duplicate the existing Organization / Place / Tour / Scene360
# content. They only store the Google Street View publication state for your
# existing apps.tours.Tour and apps.tours.Scene360 objects.

class StreetViewSourcePublication(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        READY = "ready", "Ready"
        PUBLISHING = "publishing", "Publishing"
        PUBLISHED = "published", "Published"
        FAILED = "failed", "Failed"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="streetview_source_publications")
    source_tour = models.OneToOneField("tours.Tour", on_delete=models.CASCADE, related_name="streetview_publication")

    status = models.CharField(max_length=30, choices=Status.choices, default=Status.DRAFT)
    last_error = models.TextField(blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["owner", "status"], name="sv_src_pub_owner_status_idx"),
            models.Index(fields=["source_tour"], name="sv_src_pub_tour_idx"),
            models.Index(fields=["public_id"], name="sv_src_pub_public_id_idx"),
        ]
        verbose_name = "Street View Source Publication"
        verbose_name_plural = "Street View Source Publications"

    def __str__(self):
        return f"Street View publication for {self.source_tour}"


class StreetViewSourceSceneState(models.Model):
    class PublishStatus(models.TextChoices):
        LOCAL = "local", "Local"
        READY = "ready", "Ready"
        UPLOADING = "uploading", "Uploading"
        CREATED = "created", "Created"
        CONNECTED = "connected", "Connected"
        FAILED = "failed", "Failed"

    publication = models.ForeignKey(StreetViewSourcePublication, on_delete=models.CASCADE, related_name="scene_states")
    source_scene = models.OneToOneField("tours.Scene360", on_delete=models.CASCADE, related_name="streetview_state")

    # Optional overrides used only for Google Street View publication.
    # Empty values fall back to source tour/place information.
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    altitude = models.FloatField(null=True, blank=True)

    heading = models.FloatField(default=0, validators=[MinValueValidator(0), MaxValueValidator(360)])
    pitch = models.FloatField(default=0, validators=[MinValueValidator(-90), MaxValueValidator(90)])
    roll = models.FloatField(default=0, validators=[MinValueValidator(-180), MaxValueValidator(180)])
    initial_fov = models.FloatField(default=90)

    google_photo_id = models.CharField(max_length=255, blank=True)
    google_share_link = models.URLField(blank=True)
    google_thumbnail_url = models.URLField(blank=True)
    upload_reference_url = models.TextField(blank=True)
    publish_status = models.CharField(max_length=30, choices=PublishStatus.choices, default=PublishStatus.LOCAL)
    google_maps_publish_status = models.CharField(max_length=64, blank=True, db_index=True)
    google_transfer_status = models.CharField(max_length=64, blank=True)
    google_view_count = models.PositiveBigIntegerField(default=0)
    google_last_synced_at = models.DateTimeField(null=True, blank=True)
    google_status_payload = models.JSONField(default=dict, blank=True)
    connection_sync_status = models.CharField(max_length=32, blank=True, default="pending", db_index=True)
    connection_audit = models.JSONField(default=dict, blank=True)
    last_error = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["source_scene__order", "source_scene_id"]
        indexes = [
            models.Index(fields=["publication", "publish_status"], name="sv_src_state_pub_status_idx"),
            models.Index(fields=["source_scene"], name="sv_src_state_scene_idx"),
            models.Index(fields=["google_photo_id"], name="sv_src_state_google_idx"),
        ]
        verbose_name = "Street View Source Scene State"
        verbose_name_plural = "Street View Source Scene States"

    def __str__(self):
        return f"Street View state for {self.source_scene}"

    @property
    def title(self):
        return self.source_scene.title

    @property
    def image_file(self):
        # Prefer original image for Google upload; fallback to processed panorama.
        scene = self.source_scene
        return scene.image_360_original or scene.image_360 or scene.image_360_mobile

    @property
    def image(self):
        # Compatibility with prepare_streetview_jpeg_with_xmp and StreetViewPublishClient.
        return self.image_file

    @property
    def has_image(self):
        return bool(self.image_file)

    @property
    def effective_latitude(self):
        if self.latitude is not None:
            return self.latitude
        tour = self.source_scene.tour
        if tour.lat is not None:
            return Decimal(str(tour.lat))
        place = getattr(tour, "place", None)
        if place and place.latitude is not None:
            return place.latitude
        return None

    @property
    def effective_longitude(self):
        if self.longitude is not None:
            return self.longitude
        tour = self.source_scene.tour
        if tour.lng is not None:
            return Decimal(str(tour.lng))
        place = getattr(tour, "place", None)
        if place and place.longitude is not None:
            return place.longitude
        return None

    @property
    def latitude_for_google(self):
        return self.effective_latitude

    @property
    def longitude_for_google(self):
        return self.effective_longitude

    @property
    def has_gps(self):
        return self.effective_latitude is not None and self.effective_longitude is not None

    @property
    def latitude_value(self):
        return self.effective_latitude

    @property
    def longitude_value(self):
        return self.effective_longitude

    @property
    def is_published_to_google(self):
        return bool(self.google_photo_id)

    @property
    def is_connected(self):
        return self.publish_status == self.PublishStatus.CONNECTED


class StreetViewSourcePublishJob(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        SUCCEEDED_WITH_WARNINGS = "succeeded_with_warnings", "Succeeded with warnings"
        FAILED = "failed", "Failed"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    publication = models.ForeignKey(StreetViewSourcePublication, on_delete=models.CASCADE, related_name="publish_jobs")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="streetview_source_publish_jobs")
    status = models.CharField(max_length=40, choices=Status.choices, default=Status.QUEUED)
    total_scenes = models.PositiveIntegerField(default=0)
    published_scenes = models.PositiveIntegerField(default=0)
    failed_scenes = models.PositiveIntegerField(default=0)
    log = models.JSONField(default=list, blank=True)
    error = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Street View Source Publish Job"
        verbose_name_plural = "Street View Source Publish Jobs"

    def __str__(self):
        return f"Source publish job {self.public_id} - {self.status}"

    def append_log(self, level, message, **extra):
        entry = {"time": timezone.now().isoformat(), "level": level, "message": message, **extra}
        current = list(self.log or [])
        current.append(entry)
        self.log = current
        self.save(update_fields=["log", "updated_at"])


class StreetViewQualityReport(models.Model):
    class Status(models.TextChoices):
        READY = "ready", "Ready"
        NEEDS_ATTENTION = "needs_attention", "Needs attention"
        BLOCKED = "blocked", "Blocked"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    publication = models.ForeignKey(StreetViewSourcePublication, on_delete=models.CASCADE, related_name="quality_reports")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="streetview_quality_reports")
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.NEEDS_ATTENTION)
    score = models.PositiveSmallIntegerField(default=0)
    blockers = models.PositiveIntegerField(default=0)
    warnings = models.PositiveIntegerField(default=0)
    report = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["publication", "created_at"], name="sv_quality_pub_created_idx"),
            models.Index(fields=["status"], name="sv_quality_status_idx"),
        ]

    def __str__(self):
        return f"Quality report {self.public_id} - {self.status}"


class StreetViewHistoryEvent(models.Model):
    class Action(models.TextChoices):
        QUALITY_CHECK = "quality_check", "Quality check"
        SMART_LINK = "smart_link", "Smart link"
        AUTO_LINK = "auto_link", "Auto link"
        MANUAL_LINK = "manual_link", "Manual link"
        SCENE_UPDATE = "scene_update", "Scene update"
        PUBLISH_STARTED = "publish_started", "Publish started"
        PUBLISH_FINISHED = "publish_finished", "Publish finished"
        PUBLISH_FAILED = "publish_failed", "Publish failed"
        CONNECTIONS_RETRIED = "connections_retried", "Connections retried"
        GOOGLE_PHOTO_DELETED = "google_photo_deleted", "Google photo deleted"
        GOOGLE_PHOTO_LINKED = "google_photo_linked", "Google photo linked"
        OTHER = "other", "Other"

    publication = models.ForeignKey(StreetViewSourcePublication, on_delete=models.CASCADE, related_name="history_events")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="streetview_history_events")
    source_scene = models.ForeignKey("tours.Scene360", null=True, blank=True, on_delete=models.SET_NULL, related_name="streetview_history_events")
    job = models.ForeignKey(StreetViewSourcePublishJob, null=True, blank=True, on_delete=models.SET_NULL, related_name="history_events")
    action = models.CharField(max_length=48, choices=Action.choices, default=Action.OTHER)
    message = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["publication", "created_at"], name="sv_hist_pub_created_idx"),
            models.Index(fields=["action"], name="sv_hist_action_idx"),
        ]

    def __str__(self):
        return f"{self.action} - {self.publication_id}"


class StreetViewAnalyticsEvent(models.Model):
    class Type(models.TextChoices):
        TOUR_OPENED = "tour_opened", "Tour opened"
        SCENE_SELECTED = "scene_selected", "Scene selected"
        CAMERA_SAVED = "camera_saved", "Camera saved"
        QUALITY_CHECK = "quality_check", "Quality check"
        SMART_LINK_APPLIED = "smart_link_applied", "Smart link applied"
        PUBLISH_STARTED = "publish_started", "Publish started"
        PUBLISH_SUCCEEDED = "publish_succeeded", "Publish succeeded"
        PUBLISH_FAILED = "publish_failed", "Publish failed"
        GOOGLE_LIBRARY_OPENED = "google_library_opened", "Google library opened"
        GOOGLE_PHOTO_OPENED = "google_photo_opened", "Google photo opened"
        OTHER = "other", "Other"

    publication = models.ForeignKey(StreetViewSourcePublication, on_delete=models.CASCADE, related_name="analytics_events")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="streetview_analytics_events")
    source_scene = models.ForeignKey("tours.Scene360", null=True, blank=True, on_delete=models.SET_NULL, related_name="streetview_analytics_events")
    event_type = models.CharField(max_length=48, choices=Type.choices, default=Type.OTHER)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["publication", "created_at"], name="sv_analytics_pub_created_idx"),
            models.Index(fields=["event_type"], name="sv_analytics_type_idx"),
        ]

    def __str__(self):
        return f"{self.event_type} - {self.publication_id}"
