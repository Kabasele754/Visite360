from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import render

from apps.ai_agents.models import AgentDefinition, AgentRun
from apps.ai_chat.models import EnterpriseConversation
from apps.ai_core.models import AIRun
from apps.knowledge.models import KnowledgeChunk, KnowledgeDocument, KnowledgeSource
from apps.organizations.selectors import get_user_organizations
from apps.vision_ai.models import VisionAnalysis


@login_required
def enterprise_dashboard(request):
    organizations = get_user_organizations(request.user)
    selected = organizations.filter(slug=request.GET.get("organization")).first() or organizations.first()
    context = {"organizations": organizations, "organization": selected}
    if selected:
        context.update({
            "stats": {
                "sources": KnowledgeSource.objects.filter(organization=selected).count(),
                "documents": KnowledgeDocument.objects.filter(source__organization=selected).count(),
                "chunks": KnowledgeChunk.objects.filter(document__source__organization=selected).count(),
                "agents": AgentDefinition.objects.filter(organization=selected, is_enabled=True).count(),
                "conversations": EnterpriseConversation.objects.filter(organization=selected).count(),
                "vision": VisionAnalysis.objects.filter(organization=selected).count(),
            },
            "agent_runs": AgentRun.objects.filter(agent__organization=selected).select_related("agent")[:8],
            "ai_runs": AIRun.objects.filter(organization=selected)[:8],
            "vision_runs": VisionAnalysis.objects.filter(organization=selected).select_related("scene")[:6],
            "source_statuses": KnowledgeSource.objects.filter(organization=selected).values("status").annotate(total=Count("id")),
        })
    return render(request, "enterprise_ai/dashboard.html", context)
