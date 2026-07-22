from django.urls import include, path
from rest_framework.routers import DefaultRouter
app_name = "integrations"

from apps.integrations.views import CalendarResourceViewSet, DynamicFormFieldViewSet, DynamicFormViewSet, FormSubmissionViewSet, IntegrationConnectionViewSet, appointment_ics, public_form

router = DefaultRouter()
router.register("connections", IntegrationConnectionViewSet, basename="integration-connection")
router.register("calendars", CalendarResourceViewSet, basename="calendar-resource")
router.register("forms", DynamicFormViewSet, basename="dynamic-form")
router.register("form-fields", DynamicFormFieldViewSet, basename="dynamic-form-field")
router.register("submissions", FormSubmissionViewSet, basename="form-submission")
urlpatterns = [
    path("public/forms/<uuid:form_id>/", public_form, name="public-dynamic-form"),
    path("appointments/ics/", appointment_ics, name="appointment-ics"),
    path("", include(router.urls)),
]
