from __future__ import annotations

from icalendar import Calendar, Event


def build_ics(*, uid: str, summary: str, starts_at, ends_at, description: str = "", location: str = "") -> bytes:
    calendar = Calendar()
    calendar.add("prodid", "-//Twinscopes//Enterprise Booking//EN")
    calendar.add("version", "2.0")
    event = Event()
    event.add("uid", uid)
    event.add("summary", summary)
    event.add("dtstart", starts_at)
    event.add("dtend", ends_at)
    if description:
        event.add("description", description)
    if location:
        event.add("location", location)
    calendar.add_component(event)
    return calendar.to_ical()
