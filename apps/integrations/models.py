from __future__ import annotations

import uuid
from django.db import models
from apps.common.models import TimeStampedModel


class IntegrationConnection(TimeStampedModel):
    class Provider(models.TextChoices):
        GOOGLE_CALENDAR = "google_calendar", "Google Calendar"
        OUTLOOK = "outlook", "Microsoft Outlook"
        CALENDLY = "calendly", "Calendly"
        STRIPE = "stripe", "Stripe"
        PAYPAL = "paypal", "PayPal"
        SMTP = "smtp", "Email / SMTP"
        WEBHOOK = "webhook", "Webhook"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACTIVE = "active", "Active"
        EXPIRED = "expired", "Expired"
        ERROR = "error", "Error"
        DISABLED = "disabled", "Disabled"

    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="integration_connections")
    provider = models.CharField(max_length=32, choices=Provider.choices)
    name = models.CharField(max_length=160)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PENDING, db_index=True)
    credentials_encrypted = models.TextField(blank=True)
    settings = models.JSONField(default=dict, blank=True)
    scopes = models.JSONField(default=list, blank=True)
    external_account_id = models.CharField(max_length=255, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    is_default = models.BooleanField(default=False)

    class Meta:
        ordering = ("provider", "name")
        constraints = [models.UniqueConstraint(fields=("organization", "provider", "name"), name="unique_integration_connection")]


class CalendarResource(TimeStampedModel):
    connection = models.ForeignKey(IntegrationConnection, on_delete=models.CASCADE, related_name="calendars")
    external_id = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    timezone = models.CharField(max_length=80, default="Africa/Johannesburg")
    is_primary = models.BooleanField(default=False)
    is_writable = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("connection", "external_id"), name="unique_calendar_resource")]


class DynamicForm(TimeStampedModel):
    class Purpose(models.TextChoices):
        BOOKING = "booking", "Booking"
        LEAD = "lead", "Lead"
        CONTACT = "contact", "Contact"
        QUOTE = "quote", "Quote request"
        RSVP = "rsvp", "RSVP"
        CUSTOM = "custom", "Custom"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="dynamic_forms")
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280)
    purpose = models.CharField(max_length=24, choices=Purpose.choices, default=Purpose.CONTACT)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    success_message = models.TextField(default="Thank you. Your request has been received.")
    config = models.JSONField(default=dict, blank=True)
    is_public = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)
        constraints = [models.UniqueConstraint(fields=("organization", "slug"), name="unique_dynamic_form_slug")]


class DynamicFormField(TimeStampedModel):
    class FieldType(models.TextChoices):
        TEXT = "text", "Text"
        TEXTAREA = "textarea", "Textarea"
        EMAIL = "email", "Email"
        PHONE = "phone", "Phone"
        NUMBER = "number", "Number"
        DATE = "date", "Date"
        TIME = "time", "Time"
        DATETIME = "datetime", "Date and time"
        SELECT = "select", "Select"
        MULTISELECT = "multiselect", "Multiple select"
        CHECKBOX = "checkbox", "Checkbox"
        FILE = "file", "File"

    form = models.ForeignKey(DynamicForm, on_delete=models.CASCADE, related_name="fields")
    key = models.SlugField(max_length=120)
    label = models.CharField(max_length=255)
    field_type = models.CharField(max_length=24, choices=FieldType.choices, default=FieldType.TEXT)
    placeholder = models.CharField(max_length=255, blank=True)
    help_text = models.CharField(max_length=500, blank=True)
    options = models.JSONField(default=list, blank=True)
    validation = models.JSONField(default=dict, blank=True)
    is_required = models.BooleanField(default=False)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("order", "id")
        constraints = [models.UniqueConstraint(fields=("form", "key"), name="unique_dynamic_form_field_key")]


class FormSubmission(TimeStampedModel):
    class Status(models.TextChoices):
        RECEIVED = "received", "Received"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        SPAM = "spam", "Spam"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    form = models.ForeignKey(DynamicForm, on_delete=models.CASCADE, related_name="submissions")
    user = models.ForeignKey("users.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="dynamic_form_submissions")
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.RECEIVED, db_index=True)
    data = models.JSONField(default=dict)
    source_url = models.URLField(blank=True)
    visitor_id = models.CharField(max_length=120, blank=True, db_index=True)
    ip_hash = models.CharField(max_length=64, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    related_object_type = models.CharField(max_length=120, blank=True)
    related_object_id = models.CharField(max_length=120, blank=True)
    processing_log = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ("-created_at",)


class CalendarEventLink(TimeStampedModel):
    connection = models.ForeignKey(IntegrationConnection, on_delete=models.CASCADE, related_name="event_links")
    calendar = models.ForeignKey(CalendarResource, null=True, blank=True, on_delete=models.SET_NULL, related_name="event_links")
    booking_request = models.ForeignKey("bookings.BookingRequest", null=True, blank=True, on_delete=models.CASCADE, related_name="calendar_event_links")
    appointment_request = models.ForeignKey("vendors.AppointmentRequest", null=True, blank=True, on_delete=models.CASCADE, related_name="calendar_event_links")
    external_event_id = models.CharField(max_length=255, db_index=True)
    html_link = models.URLField(blank=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    timezone = models.CharField(max_length=80, default="Africa/Johannesburg")
    payload = models.JSONField(default=dict, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
