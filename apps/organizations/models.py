from django.conf import settings
from django.db import models
from apps.common.models import TimeStampedModel


def organization_logo_upload_to(instance, filename):
    return f"organizations/{instance.slug}/logo/{filename}"


class Organization(TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    logo = models.ImageField(
        upload_to=organization_logo_upload_to,
        null=True,
        blank=True
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    description = models.TextField(blank=True)
    website_url = models.URLField(blank=True)
    booking_url = models.URLField(blank=True)
    public_email = models.EmailField(blank=True)
    public_phone = models.CharField(max_length=40, blank=True)
    facebook_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    tiktok_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    youtube_url = models.URLField(blank=True)
    social_links_verified_at = models.DateTimeField(null=True, blank=True)
    ai_use_website = models.BooleanField(default=True)
    ai_auto_discover_social_links = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class OrganizationMember(TimeStampedModel):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        MANAGER = "manager", "Manager"
        EDITOR = "editor", "Editor"
        VIEWER = "viewer", "Viewer"

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="memberships"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organization_memberships"
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("organization", "user")

    def __str__(self):
        return f"{self.user.email} @ {self.organization.slug}"