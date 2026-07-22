from rest_framework import serializers

from apps.ai_core.models import AIProviderConfiguration, AIRun, AIUsageDaily


class AIProviderConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIProviderConfiguration
        fields = "__all__"
        read_only_fields = ("last_health_status", "last_health_message", "last_health_checked_at")


class AIRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIRun
        fields = "__all__"
        read_only_fields = tuple(field.name for field in AIRun._meta.fields)


class AIUsageDailySerializer(serializers.ModelSerializer):
    class Meta:
        model = AIUsageDaily
        fields = "__all__"
        read_only_fields = tuple(field.name for field in AIUsageDaily._meta.fields)
