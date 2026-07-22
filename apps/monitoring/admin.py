from django.contrib import admin
from apps.monitoring.models import AuditEvent, ProviderHealth, SystemEvent
admin.site.register(SystemEvent)
admin.site.register(ProviderHealth)
admin.site.register(AuditEvent)
