from __future__ import annotations

from apps.ai_agents.models import AgentDefinition


DEFAULT_AGENT_SPECS = {
    AgentDefinition.AgentType.WEBSITE: {
        "name": "Website Agent", "slug": "website-agent", "tools": ["knowledge_search", "list_services", "list_products"],
        "prompt": "Answer from the organization's verified website and knowledge base. Return clean links and never ask permission to inspect already connected organization sources.",
    },
    AgentDefinition.AgentType.PRODUCT: {
        "name": "Product Agent", "slug": "product-agent", "tools": ["list_products", "knowledge_search"],
        "prompt": "Help visitors discover and compare real active products. Never invent prices, stock, specifications or discounts.",
    },
    AgentDefinition.AgentType.SERVICE: {
        "name": "Service Agent", "slug": "service-agent", "tools": ["list_services", "knowledge_search"],
        "prompt": "Explain the organization's verified services and guide the visitor toward the appropriate service or booking flow.",
    },
    AgentDefinition.AgentType.VISION: {
        "name": "Vision Agent", "slug": "vision-agent", "tools": ["knowledge_search", "list_products"],
        "prompt": "Use visible scene evidence and verified knowledge. Separate what is visibly detected from what is documented.",
    },
    AgentDefinition.AgentType.SOCIAL: {
        "name": "Social Agent", "slug": "social-agent", "tools": ["knowledge_search", "analytics_summary"],
        "prompt": "Draft accurate social content based on verified organization information and observed performance. Require human review before publication.",
    },
    AgentDefinition.AgentType.BOOKING: {
        "name": "Booking Agent", "slug": "booking-agent", "tools": ["list_services", "knowledge_search"],
        "prompt": "Collect only the details required for a booking, present available services, and use the connected scheduling workflow.",
    },
    AgentDefinition.AgentType.CRM: {
        "name": "CRM Agent", "slug": "crm-agent", "tools": ["analytics_summary", "knowledge_search"],
        "prompt": "Summarize leads and customer intent, suggest next actions, and avoid exposing private customer data unnecessarily.",
    },
    AgentDefinition.AgentType.RECOMMENDATION: {
        "name": "Recommendation Agent", "slug": "recommendation-agent", "tools": ["list_products", "list_services", "knowledge_search"],
        "prompt": "Recommend only available products and services that match the stated need. Explain why each recommendation fits.",
    },
    AgentDefinition.AgentType.ANALYTICS: {
        "name": "Analytics Agent", "slug": "analytics-agent", "tools": ["analytics_summary"],
        "prompt": "Interpret verified metrics, clearly label assumptions, and distinguish correlation from causation.",
    },
}


def provision_default_agents(organization) -> list[AgentDefinition]:
    agents = []
    for agent_type, spec in DEFAULT_AGENT_SPECS.items():
        agent, _ = AgentDefinition.objects.update_or_create(
            organization=organization,
            slug=spec["slug"],
            defaults={
                "name": spec["name"],
                "agent_type": agent_type,
                "system_prompt": spec["prompt"],
                "tools": spec["tools"],
                "is_enabled": True,
            },
        )
        agents.append(agent)
    return agents
