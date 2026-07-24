from __future__ import annotations

import logging
from django.urls import reverse
from django.utils.dateparse import parse_date, parse_time

from apps.domain_intelligence.models import MedicalPractitioner, MedicalSpecialty
from apps.integrations.models import DynamicForm, DynamicFormField, IntegrationConnection
from apps.integrations.services.google_calendar import create_event_for_appointment
from apps.vendors.models import AppointmentRequest, AppointmentType

logger = logging.getLogger(__name__)


def _healthcare_options(organization) -> tuple[list[dict], list[dict]]:
    specialties = [
        {"value": str(item.id), "label": item.name}
        for item in MedicalSpecialty.objects.filter(organization=organization, is_active=True).order_by("name")[:100]
    ]
    practitioners = [
        {
            "value": str(item.id),
            "label": " — ".join(filter(None, [item.full_name, item.specialty.name if item.specialty else ""])),
        }
        for item in MedicalPractitioner.objects.select_related("specialty")
        .filter(organization=organization, is_active=True)
        .order_by("full_name")[:200]
    ]
    return specialties, practitioners


def get_or_create_booking_form(organization) -> DynamicForm:
    healthcare = hasattr(organization, "intelligence_profile") and organization.intelligence_profile.domain_kind in {
        "healthcare",
        "mixed",
    }
    form, _ = DynamicForm.objects.get_or_create(
        organization=organization,
        slug="ai-appointment-request",
        defaults={
            "name": "AI appointment request",
            "purpose": DynamicForm.Purpose.BOOKING,
            "title": (
                f"Request a medical appointment with {organization.name}"
                if healthcare
                else f"Book an appointment with {organization.name}"
            ),
            "description": (
                "Choose a specialty or practitioner, then provide your preferred date and contact details."
                if healthcare
                else "Choose your preferred date and provide your contact details."
            ),
            "success_message": "Your appointment request has been received.",
            "is_public": True,
            "is_active": True,
        },
    )
    base_fields = [
        ("full_name", "Full name", "text", True, 10, []),
        ("email", "Email", "email", False, 20, []),
        ("phone", "Phone", "phone", True, 30, []),
    ]
    if healthcare:
        specialty_options, practitioner_options = _healthcare_options(organization)
        base_fields.extend([
            ("specialty_id", "Medical specialty", "select", False, 35, specialty_options),
            ("practitioner_id", "Preferred doctor", "select", False, 36, practitioner_options),
            ("reason_for_visit", "Reason for visit", "textarea", False, 38, []),
            (
                "appointment_mode",
                "Appointment mode",
                "select",
                False,
                39,
                [
                    {"value": "in_person", "label": "In person"},
                    {"value": "telemedicine", "label": "Telemedicine"},
                ],
            ),
        ])
    base_fields.extend([
        ("preferred_date", "Preferred date", "date", True, 40, []),
        ("preferred_time", "Preferred time", "time", False, 50, []),
        ("notes", "Additional details", "textarea", False, 60, []),
    ])
    for key, label, field_type, required, order, options in base_fields:
        DynamicFormField.objects.update_or_create(
            form=form,
            key=key,
            defaults={
                "label": label,
                "field_type": field_type,
                "is_required": required,
                "order": order,
                "options": options,
            },
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
    practitioner = MedicalPractitioner.objects.select_related("specialty", "place").filter(
        pk=payload.get("practitioner_id"),
        organization=organization,
        is_active=True,
    ).first() if payload.get("practitioner_id") else None
    specialty = MedicalSpecialty.objects.filter(
        pk=payload.get("specialty_id"),
        organization=organization,
        is_active=True,
    ).first() if payload.get("specialty_id") else None
    if practitioner and not specialty:
        specialty = practitioner.specialty

    appointment_type = AppointmentType.objects.filter(
        pk=payload.get("appointment_type_id"),
        organization=organization,
        is_active=True,
    ).first()
    if not appointment_type and specialty:
        appointment_type = AppointmentType.objects.filter(
            organization=organization,
            is_active=True,
            name__icontains=specialty.name,
        ).first()

    preferred_date_value = payload.get("preferred_date") or payload.get("date") or ""
    preferred_time_value = payload.get("preferred_time") or payload.get("time") or ""
    preferred_date = parse_date(str(preferred_date_value)) if preferred_date_value else None
    preferred_time = parse_time(str(preferred_time_value)) if preferred_time_value else None

    obj = AppointmentRequest.objects.create(
        organization=organization,
        tour=tour,
        place=(practitioner.place if practitioner else getattr(tour, "place", None)),
        appointment_type=appointment_type,
        full_name=(payload.get("full_name") or "").strip(),
        email=(payload.get("email") or "").strip(),
        phone=(payload.get("phone") or "").strip(),
        preferred_date=preferred_date,
        preferred_time=preferred_time,
        notes=(payload.get("notes") or "").strip(),
        source="tour_ai",
        practitioner_name=practitioner.full_name if practitioner else "",
        specialty_name=specialty.name if specialty else "",
        reason_for_visit=(payload.get("reason_for_visit") or "").strip(),
        appointment_mode=(payload.get("appointment_mode") or "in_person")[:24],
        metadata={
            "practitioner_id": practitioner.id if practitioner else None,
            "specialty_id": specialty.id if specialty else None,
            "verified_source_url": practitioner.source_url if practitioner else "",
        },
    )
    result = {
        "ok": True,
        "appointment_id": obj.id,
        "status": obj.status,
        "calendar_synced": False,
        "practitioner": obj.practitioner_name,
        "specialty": obj.specialty_name,
    }
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
            result["calendar_error"] = "The appointment was saved, but calendar synchronization is temporarily unavailable."
    return result
