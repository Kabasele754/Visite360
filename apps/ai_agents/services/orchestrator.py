from __future__ import annotations

import json
from django.utils import timezone

from apps.ai_agents.models import AgentRun, AgentToolInvocation
from apps.ai_agents.services.tools import TOOL_REGISTRY
from apps.ai_core.services.providers import parse_json_object
from apps.ai_core.services.router import AIProviderRouter


def _requested_tools(run: AgentRun) -> list[str]:
    requested = run.input.get("tools") or run.agent.tools
    return [name for name in requested if name in TOOL_REGISTRY]


def execute_agent_run(run: AgentRun) -> AgentRun:
    run.status = AgentRun.Status.RUNNING
    run.started_at = timezone.now()
    run.error_message = ""
    run.save(update_fields=("status", "started_at", "error_message", "updated_at"))
    organization = run.agent.organization
    context = {}
    try:
        query = str(run.input.get("query") or run.input.get("message") or "").strip()
        for tool_name in _requested_tools(run):
            invocation = AgentToolInvocation.objects.create(run=run, tool_name=tool_name, arguments={})
            try:
                kwargs = {"organization": organization}
                if tool_name == "knowledge_search":
                    kwargs["query"] = query
                result = TOOL_REGISTRY[tool_name](**kwargs)
                if hasattr(result, "__iter__") and not isinstance(result, (dict, str, list, tuple)):
                    result = list(result)
                invocation.result = json.loads(json.dumps(result, default=str))
                invocation.succeeded = True
                invocation.save()
                context[tool_name] = invocation.result
            except Exception as exc:
                invocation.error_message = str(exc)[:4000]
                invocation.save()
                context[tool_name] = {"error": str(exc)}

        system = "\n".join(filter(None, [
            run.agent.system_prompt,
            "Use only the supplied verified context for organization-specific facts.",
            "Return JSON with keys answer, citations, recommended_actions, confidence, needs_human_review.",
        ]))
        prompt = f"User request:\n{query}\n\nVerified context:\n{json.dumps(context, ensure_ascii=False, default=str)[:50000]}"
        result = AIProviderRouter(organization=organization, user=run.requested_by).generate_text(
            prompt=prompt,
            system=system,
            provider=run.agent.provider or None,
            model=run.agent.model_name or None,
        )
        output = parse_json_object(result.text)
        run.output = output
        run.context_snapshot = context
        run.provider = result.provider
        run.model_name = result.model
        run.status = AgentRun.Status.NEEDS_REVIEW if output.get("needs_human_review") else AgentRun.Status.SUCCEEDED
    except Exception as exc:
        run.status = AgentRun.Status.FAILED
        run.error_message = str(exc)[:8000]
    run.finished_at = timezone.now()
    run.save()
    return run
