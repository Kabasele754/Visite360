from django.http import HttpResponse
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from apps.integrations.models import CalendarResource, DynamicForm, DynamicFormField, FormSubmission, IntegrationConnection
from apps.integrations.serializers import CalendarResourceSerializer, DynamicFormFieldSerializer, DynamicFormSerializer, FormSubmissionSerializer, IntegrationConnectionSerializer
from apps.integrations.services.forms import create_submission
from apps.integrations.services.google_calendar import GoogleCalendarService, create_event_for_appointment
from apps.integrations.services.ics import build_ics
from apps.organizations.selectors import get_user_organizations
from apps.vendors.models import AppointmentRequest


class OrganizationScopedMixin:
    organization_lookup = "organization"
    def get_queryset(self):
        return self.queryset.filter(**{f"{self.organization_lookup}__in": get_user_organizations(self.request.user)})


class IntegrationConnectionViewSet(OrganizationScopedMixin, viewsets.ModelViewSet):
    queryset = IntegrationConnection.objects.all()
    serializer_class = IntegrationConnectionSerializer
    permission_classes = (permissions.IsAuthenticated,)
    filterset_fields = ("organization", "provider", "status")

    def perform_create(self, serializer):
        organization = serializer.validated_data["organization"]
        if organization not in get_user_organizations(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Forbidden organization.")
        serializer.save()

    @action(detail=True, methods=["post"])
    def sync_calendars(self, request, pk=None):
        connection = self.get_object()
        if connection.provider != IntegrationConnection.Provider.GOOGLE_CALENDAR:
            return Response({"detail": "Only Google Calendar is implemented by this endpoint."}, status=400)
        try:
            calendars = GoogleCalendarService(connection).list_calendars()
            for item in calendars:
                CalendarResource.objects.update_or_create(
                    connection=connection,
                    external_id=item["id"],
                    defaults={
                        "name": item.get("summary", item["id"]),
                        "timezone": item.get("timeZone", "Africa/Johannesburg"),
                        "is_primary": item.get("primary", False),
                        "is_writable": item.get("accessRole") in {"owner", "writer"},
                        "metadata": item,
                    },
                )
            connection.status = IntegrationConnection.Status.ACTIVE
            connection.last_synced_at = timezone.now()
            connection.last_error = ""
            connection.save(update_fields=("status", "last_synced_at", "last_error", "updated_at"))
            return Response({"calendars": len(calendars)})
        except Exception as exc:
            connection.status = IntegrationConnection.Status.ERROR
            connection.last_error = str(exc)[:8000]
            connection.save(update_fields=("status", "last_error", "updated_at"))
            return Response({"detail": str(exc)}, status=503)

    @action(detail=True, methods=["post"])
    def create_appointment_event(self, request, pk=None):
        connection = self.get_object()
        appointment = AppointmentRequest.objects.filter(pk=request.data.get("appointment_id"), organization=connection.organization).first()
        if not appointment:
            return Response({"detail": "Appointment not found."}, status=404)
        link = create_event_for_appointment(appointment, connection)
        return Response({"event_id": link.external_event_id, "html_link": link.html_link}, status=status.HTTP_201_CREATED)


class CalendarResourceViewSet(OrganizationScopedMixin, viewsets.ReadOnlyModelViewSet):
    queryset = CalendarResource.objects.all()
    serializer_class = CalendarResourceSerializer
    permission_classes = (permissions.IsAuthenticated,)
    organization_lookup = "connection__organization"


class DynamicFormViewSet(OrganizationScopedMixin, viewsets.ModelViewSet):
    queryset = DynamicForm.objects.prefetch_related("fields")
    serializer_class = DynamicFormSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def perform_create(self, serializer):
        organization = serializer.validated_data["organization"]
        if organization not in get_user_organizations(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Forbidden organization.")
        serializer.save()


class DynamicFormFieldViewSet(viewsets.ModelViewSet):
    serializer_class = DynamicFormFieldSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        return DynamicFormField.objects.filter(form__organization__in=get_user_organizations(self.request.user))

    def perform_create(self, serializer):
        form = serializer.validated_data["form"]
        if form.organization not in get_user_organizations(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Forbidden form.")
        serializer.save()

    def perform_update(self, serializer):
        form = serializer.validated_data.get("form", serializer.instance.form)
        if form.organization not in get_user_organizations(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Forbidden form.")
        serializer.save()


class FormSubmissionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = FormSubmissionSerializer
    permission_classes = (permissions.IsAuthenticated,)
    filterset_fields = ("form", "status")
    def get_queryset(self):
        return FormSubmission.objects.filter(form__organization__in=get_user_organizations(self.request.user))


@api_view(["GET", "POST"])
@permission_classes([permissions.AllowAny])
def public_form(request, form_id):
    form = DynamicForm.objects.prefetch_related("fields").filter(pk=form_id, is_public=True, is_active=True).first()
    if not form:
        return Response({"detail": "Form not found."}, status=404)
    if request.method == "GET":
        return Response(DynamicFormSerializer(form).data)
    try:
        submission = create_submission(form=form, data=request.data, request=request, user=request.user)
    except Exception as exc:
        detail = getattr(exc, "message_dict", None) or str(exc)
        return Response({"detail": detail}, status=400)
    return Response({"submission_id": str(submission.pk), "message": form.success_message}, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def appointment_ics(request):
    appointment = AppointmentRequest.objects.filter(pk=request.data.get("appointment_id"), organization__in=get_user_organizations(request.user)).first()
    if not appointment or not appointment.preferred_date:
        return Response({"detail": "Appointment not found or missing date."}, status=404)
    from datetime import datetime, timedelta
    preferred_time = appointment.preferred_time or datetime.min.time().replace(hour=9)
    starts_at = timezone.make_aware(datetime.combine(appointment.preferred_date, preferred_time))
    duration = getattr(appointment.appointment_type, "duration_minutes", None) or 30
    payload = build_ics(
        uid=f"appointment-{appointment.pk}@twinscopes.com",
        summary=f"{appointment.organization.name}: {appointment.full_name}",
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=duration),
        description=appointment.notes,
    )
    response = HttpResponse(payload, content_type="text/calendar; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="twinscopes-appointment-{appointment.pk}.ics"'
    return response
