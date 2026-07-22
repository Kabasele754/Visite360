from django.contrib import admin
from apps.integrations.models import CalendarEventLink, CalendarResource, DynamicForm, DynamicFormField, FormSubmission, IntegrationConnection
admin.site.register(IntegrationConnection)
admin.site.register(CalendarResource)
admin.site.register(DynamicForm)
admin.site.register(DynamicFormField)
admin.site.register(FormSubmission)
admin.site.register(CalendarEventLink)
