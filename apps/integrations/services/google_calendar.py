from __future__ import annotations

from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from apps.integrations.models import CalendarEventLink, IntegrationConnection
from apps.integrations.services.crypto import decrypt_json


class GoogleCalendarService:
    def __init__(self, connection: IntegrationConnection):
        if connection.provider != IntegrationConnection.Provider.GOOGLE_CALENDAR:
            raise ValueError("Connection is not a Google Calendar connection.")
        credentials_info = decrypt_json(connection.credentials_encrypted)
        self.credentials = Credentials.from_authorized_user_info(credentials_info)
        self.client = build("calendar", "v3", credentials=self.credentials, cache_discovery=False)
        self.connection = connection

    def list_calendars(self) -> list[dict]:
        result = self.client.calendarList().list().execute()
        return result.get("items", [])

    def create_event(self, *, summary: str, starts_at: datetime, ends_at: datetime, description: str = "", attendees: list[str] | None = None, calendar_id: str = "primary", timezone_name: str | None = None) -> dict:
        timezone_name = timezone_name or settings.GOOGLE_CALENDAR_DEFAULT_TIMEZONE
        body = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": starts_at.isoformat(), "timeZone": timezone_name},
            "end": {"dateTime": ends_at.isoformat(), "timeZone": timezone_name},
        }
        if attendees:
            body["attendees"] = [{"email": email} for email in attendees if email]
        return self.client.events().insert(calendarId=calendar_id, body=body, sendUpdates="all").execute()


def create_event_for_appointment(appointment, connection: IntegrationConnection, *, duration_minutes: int | None = None) -> CalendarEventLink:
    if not appointment.preferred_date:
        raise ValueError("Appointment has no preferred date.")
    appointment_time = appointment.preferred_time or datetime.min.time().replace(hour=9)
    starts_at = timezone.make_aware(datetime.combine(appointment.preferred_date, appointment_time))
    duration_minutes = duration_minutes or getattr(appointment.appointment_type, "duration_minutes", None) or 30
    ends_at = starts_at + timedelta(minutes=duration_minutes)
    event = GoogleCalendarService(connection).create_event(
        summary=f"{appointment.organization.name}: {appointment.full_name}",
        starts_at=starts_at,
        ends_at=ends_at,
        description=appointment.notes,
        attendees=[appointment.email] if appointment.email else [],
        calendar_id=connection.settings.get("calendar_id", "primary"),
    )
    return CalendarEventLink.objects.create(
        connection=connection,
        appointment_request=appointment,
        external_event_id=event["id"],
        html_link=event.get("htmlLink", ""),
        starts_at=starts_at,
        ends_at=ends_at,
        timezone=settings.GOOGLE_CALENDAR_DEFAULT_TIMEZONE,
        payload=event,
    )
