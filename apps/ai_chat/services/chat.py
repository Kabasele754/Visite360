from __future__ import annotations

import json
from django.conf import settings
from django.db import transaction

from apps.ai_chat.models import EnterpriseMessage
from apps.ai_chat.services.context import build_chat_context
from apps.ai_chat.services.validator import validate_response
from apps.ai_core.services.providers import parse_json_object
from apps.ai_core.services.router import AIProviderRouter


DEFAULT_SYSTEM = """You are the official Twinscopes assistant for this organization.
Use the verified context supplied by Twinscopes. Do not ask the visitor for permission to inspect organization sources that are already connected.
Never invent services, products, prices, availability, contact details, policies or URLs.
Cite organization-specific claims with [K1], [K2], etc.
When information is unavailable, say so and suggest a safe next action.
Return JSON with answer, intent, confidence, recommended_actions and needs_human_review."""


@transaction.atomic
def respond_to_message(conversation, text: str, *, user=None) -> EnterpriseMessage:
    EnterpriseMessage.objects.create(
        conversation=conversation,
        role=EnterpriseMessage.Role.USER,
        content=text,
        metadata={"user_id": getattr(user, "pk", None)},
    )
    context, citations = build_chat_context(conversation, text)
    history = list(conversation.messages.order_by("-created_at")[: settings.AI_CHAT_MAX_HISTORY_MESSAGES])
    history.reverse()
    history_text = "\n".join(f"{message.role}: {message.content}" for message in history)
    system = conversation.agent.system_prompt if conversation.agent_id and conversation.agent.system_prompt else DEFAULT_SYSTEM
    prompt = f"Conversation history:\n{history_text}\n\nVerified context:\n{context}\n\nCurrent user message:\n{text}"
    result = AIProviderRouter(organization=conversation.organization, user=user).generate_text(
        prompt=prompt,
        system=system,
        provider=conversation.agent.provider if conversation.agent_id and conversation.agent.provider else None,
        model=conversation.agent.model_name if conversation.agent_id and conversation.agent.model_name else None,
    )
    parsed = parse_json_object(result.text)
    answer = str(parsed.get("answer") or parsed.get("text") or result.text)
    validation = validate_response(
        answer=answer,
        citations=citations,
        require_citations=settings.AI_CHAT_REQUIRE_CITATIONS,
    )
    if not validation["passed"] and validation["unverified_links"]:
        for link in validation["unverified_links"]:
            answer = answer.replace(link, "[unverified link removed]")
    message = EnterpriseMessage.objects.create(
        conversation=conversation,
        role=EnterpriseMessage.Role.ASSISTANT,
        content=answer,
        citations=citations,
        confidence=float(parsed.get("confidence", 0.6) or 0.6),
        intent=str(parsed.get("intent", ""))[:120],
        validation=validation,
        metadata={
            "provider": result.provider,
            "model": result.model,
            "recommended_actions": parsed.get("recommended_actions", []),
            "needs_human_review": bool(parsed.get("needs_human_review")) or not validation["passed"],
        },
    )
    if not conversation.title:
        conversation.title = text[:120]
        conversation.save(update_fields=("title", "updated_at", "last_activity_at"))
    return message
