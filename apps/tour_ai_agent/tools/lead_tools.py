from apps.leads.models import Lead

def create_sales_lead(*, organization, tour, payload):
    if not tour.place_id:
        return {"ok": False, "error": "Tour has no place"}
    lead = Lead.objects.create(
        organization=organization,
        place=tour.place,
        full_name=(payload.get("full_name") or "Tour visitor").strip(),
        phone=(payload.get("phone") or "").strip(),
        email=(payload.get("email") or "").strip(),
        message=(payload.get("message") or payload.get("interest") or "").strip(),
        source="tour_ai",
    )
    return {"ok": True, "lead_id": lead.id}
