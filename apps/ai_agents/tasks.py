from celery import shared_task
from apps.ai_agents.models import AgentRun
from apps.ai_agents.services.orchestrator import execute_agent_run


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=2)
def run_agent(self, run_id: str):
    run = AgentRun.objects.select_related("agent__organization", "requested_by").get(pk=run_id)
    execute_agent_run(run)
    return {"run_id": str(run.pk), "status": run.status}
