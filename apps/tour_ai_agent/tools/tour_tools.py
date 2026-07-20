def get_tour_details(tour):
    return {"id": tour.id, "title": tour.title, "organization": tour.organization.name, "place": tour.place.name if tour.place_id else ""}
