from rest_framework import serializers
from apps.integrations.models import CalendarEventLink, CalendarResource, DynamicForm, DynamicFormField, FormSubmission, IntegrationConnection


class IntegrationConnectionSerializer(serializers.ModelSerializer):
    credentials = serializers.JSONField(write_only=True, required=False)

    class Meta:
        model = IntegrationConnection
        exclude = ("credentials_encrypted",)
        read_only_fields = ("status", "last_synced_at", "last_error")

    def create(self, validated_data):
        from apps.integrations.services.crypto import encrypt_json
        credentials = validated_data.pop("credentials", None)
        instance = super().create(validated_data)
        if credentials:
            instance.credentials_encrypted = encrypt_json(credentials)
            instance.status = IntegrationConnection.Status.ACTIVE
            instance.save(update_fields=("credentials_encrypted", "status", "updated_at"))
        return instance

    def update(self, instance, validated_data):
        from apps.integrations.services.crypto import encrypt_json
        credentials = validated_data.pop("credentials", None)
        instance = super().update(instance, validated_data)
        if credentials:
            instance.credentials_encrypted = encrypt_json(credentials)
            instance.status = IntegrationConnection.Status.ACTIVE
            instance.save(update_fields=("credentials_encrypted", "status", "updated_at"))
        return instance


class CalendarResourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = CalendarResource
        fields = "__all__"


class DynamicFormFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = DynamicFormField
        fields = "__all__"


class DynamicFormSerializer(serializers.ModelSerializer):
    fields = DynamicFormFieldSerializer(many=True, read_only=True)

    class Meta:
        model = DynamicForm
        fields = "__all__"


class FormSubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FormSubmission
        fields = "__all__"
        read_only_fields = ("user", "status", "ip_hash", "user_agent", "processing_log")


class CalendarEventLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = CalendarEventLink
        fields = "__all__"
