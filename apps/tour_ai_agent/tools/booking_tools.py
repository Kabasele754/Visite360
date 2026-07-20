from apps.vendors.models import AppointmentRequest, AppointmentType

def create_appointment(*, organization, tour, payload):
    obj = AppointmentRequest.objects.create(
        organization=organization,
        tour=tour,
        appointment_type=AppointmentType.objects.filter(pk=payload.get("appointment_type_id"), organization=organization, is_active=True).first(),
        full_name=(payload.get("full_name") or "").strip(),
        email=(payload.get("email") or "").strip(),
        phone=(payload.get("phone") or "").strip(),
        preferred_date=payload.get("preferred_date") or payload.get("date") or None,
        preferred_time=payload.get("preferred_time") or payload.get("time") or None,
        notes=(payload.get("notes") or "").strip(),
        source="tour_ai",
    )
    return {"ok": True, "appointment_id": obj.id, "status": obj.status}
