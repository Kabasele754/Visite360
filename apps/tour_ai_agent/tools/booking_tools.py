from __future__ import annotations

import logging
from django.urls import reverse
from django.utils.text import slugify

from apps.integrations.models import DynamicForm, DynamicFormField, IntegrationConnection
from apps.integrations.services.google_calendar import create_event_for_appointment
from apps.vendors.models import AppointmentRequest, AppointmentType

logger = logging.getLogger(__name__)


def get_or_create_booking_form(organization) -> DynamicForm:
    form, _ = DynamicForm.objects.get_or_create(
        organization=organization,
        slug="ai-appointment-request",
        defaults={
            "name": "AI appointment request",
            "purpose": DynamicForm.Purpose.BOOKING,
            "title": f"Book an appointment with {organization.name}",
            "description": "Choose your preferred date and provide your contact details.",
            "success_message": "Your appointment request has been received.",
            "is_public": True,
            "is_active": True,
        },
    )
    defaults = [
        ("full_name", "Full name", "text", True, 10),
        ("email", "Email", "email", False, 20),
        ("phone", "Phone", "phone", True, 30),
        ("preferred_date", "Preferred date", "date", True, 40),
        ("preferred_time", "Preferred time", "time", False, 50),
        ("notes", "Additional details", "textarea", False, 60),
    ]
    for key, label, field_type, required, order in defaults:
        DynamicFormField.objects.update_or_create(
            form=form,
            key=key,
            defaults={"label": label, "field_type": field_type, "is_required": required, "order": order},
        )
    return form


def booking_form_payload(organization) -> dict:
    form = get_or_create_booking_form(organization)
    return {
        "id": str(form.id),
        "title": form.title,
        "description": form.description,
        "submit_url": reverse("integrations:public-dynamic-form", kwargs={"form_id": form.id}),
        "fields": [
            {
                "key": field.key,
                "label": field.label,
                "type": field.field_type,
                "required": field.is_required,
                "options": field.options,
            }
            for field in form.fields.all()
        ],
    }


def create_appointment(*, organization, tour, payload):
    obj = AppointmentRequest.objects.create(
        organization=organization,
        tour=tour,
        appointment_type=AppointmentType.objects.filter(
            pk=payload.get("appointment_type_id"), organization=organization, is_active=True
        ).first(),
        full_name=(payload.get("full_name") or "").strip(),
        email=(payload.get("email") or "").strip(),
        phone=(payload.get("phone") or "").strip(),
        preferred_date=payload.get("preferred_date") or payload.get("date") or None,
        preferred_time=payload.get("preferred_time") or payload.get("time") or None,
        notes=(payload.get("notes") or "").strip(),
        source="tour_ai",
    )
    result = {"ok": True, "appointment_id": obj.id, "status": obj.status, "calendar_synced": False}
    connection = IntegrationConnection.objects.filter(
        organization=organization,
        provider=IntegrationConnection.Provider.GOOGLE_CALENDAR,
        status=IntegrationConnection.Status.ACTIVE,
    ).order_by("-is_default", "id").first()
    if connection and obj.preferred_date:
        try:
            link = create_event_for_appointment(obj, connection)
            result.update({"calendar_synced": True, "calendar_event_url": link.html_link})
        except Exception as exc:
            logger.exception("Unable to sync appointment %s to Google Calendar", obj.pk)
            result["calendar_error"] = str(exc)[:500]
    return result
