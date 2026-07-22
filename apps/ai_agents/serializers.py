from rest_framework import serializers
from apps.ai_agents.models import AgentDefinition, AgentRun, AgentToolInvocation


class AgentDefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentDefinition
        fields = "__all__"


class AgentToolInvocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentToolInvocation
        fields = "__all__"


class AgentRunSerializer(serializers.ModelSerializer):
    tool_invocations = AgentToolInvocationSerializer(many=True, read_only=True)

    class Meta:
        model = AgentRun
        fields = "__all__"
        read_only_fields = ("requested_by", "status", "output", "context_snapshot", "provider", "model_name", "started_at", "finished_at", "error_message")
