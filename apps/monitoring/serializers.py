from rest_framework import serializers
from apps.monitoring.models import AuditEvent, ProviderHealth, SystemEvent


class SystemEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemEvent
        fields = "__all__"


class ProviderHealthSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProviderHealth
        fields = "__all__"


class AuditEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditEvent
        fields = "__all__"
