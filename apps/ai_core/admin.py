from django.contrib import admin

from apps.ai_core.models import AIProviderConfiguration, AIRun, AIUsageDaily


@admin.register(AIProviderConfiguration)
class AIProviderConfigurationAdmin(admin.ModelAdmin):
    list_display = ("provider", "capability", "model_name", "organization", "priority", "is_enabled", "last_health_status")
    list_filter = ("provider", "capability", "is_enabled", "last_health_status")
    search_fields = ("model_name", "organization__name")


@admin.register(AIRun)
class AIRunAdmin(admin.ModelAdmin):
    list_display = ("id", "operation", "provider", "model_name", "status", "organization", "latency_ms", "created_at")
    list_filter = ("status", "provider", "operation")
    search_fields = ("trace_id", "error_message", "organization__name")
    readonly_fields = tuple(field.name for field in AIRun._meta.fields)


admin.site.register(AIUsageDaily)
