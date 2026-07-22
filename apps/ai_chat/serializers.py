from rest_framework import serializers
from apps.ai_chat.models import ConversationFeedback, EnterpriseConversation, EnterpriseMessage


class EnterpriseMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = EnterpriseMessage
        fields = "__all__"
        read_only_fields = tuple(field.name for field in EnterpriseMessage._meta.fields)


class EnterpriseConversationSerializer(serializers.ModelSerializer):
    messages = EnterpriseMessageSerializer(many=True, read_only=True)

    class Meta:
        model = EnterpriseConversation
        fields = "__all__"
        read_only_fields = ("user", "summary", "lead_score", "last_activity_at")

    def validate(self, attrs):
        organization = attrs.get("organization") or getattr(self.instance, "organization", None)
        if not organization:
            return attrs
        for field_name in ("tour", "scene", "agent"):
            value = attrs.get(field_name)
            if value is not None and getattr(value, "organization_id", None) != organization.pk:
                raise serializers.ValidationError({field_name: "This object does not belong to the selected organization."})
        scene = attrs.get("scene")
        tour = attrs.get("tour")
        if scene is not None and tour is not None and getattr(scene, "tour_id", None) != tour.pk:
            raise serializers.ValidationError({"scene": "The selected scene does not belong to the selected tour."})
        return attrs


class ConversationFeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConversationFeedback
        fields = "__all__"

    def validate(self, attrs):
        conversation = attrs.get("conversation") or getattr(self.instance, "conversation", None)
        message = attrs.get("message")
        if message is not None and conversation is not None and message.conversation_id != conversation.pk:
            raise serializers.ValidationError({"message": "The message does not belong to this conversation."})
        return attrs
