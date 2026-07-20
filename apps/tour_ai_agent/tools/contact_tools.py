def contact_options(organization, tour=None):
    return {"email": getattr(tour, "contact_email", "") or getattr(organization, "email", ""), "phone": getattr(organization, "phone", ""), "website": getattr(organization, "website", "")}
