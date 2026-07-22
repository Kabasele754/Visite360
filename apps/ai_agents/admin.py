from django.contrib import admin
from apps.ai_agents.models import AgentDefinition, AgentMemory, AgentRun, AgentToolInvocation
admin.site.register(AgentDefinition)
admin.site.register(AgentRun)
admin.site.register(AgentToolInvocation)
admin.site.register(AgentMemory)
