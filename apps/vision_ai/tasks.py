from celery import shared_task

from apps.vision_ai.models import VisionAnalysis
from apps.vision_ai.services.engine import execute_analysis


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=2, soft_time_limit=60 * 20)
def run_vision_analysis(self, analysis_id: str):
    analysis = VisionAnalysis.objects.select_related("organization", "scene").get(pk=analysis_id)
    execute_analysis(analysis)
    return {"analysis_id": str(analysis.pk), "status": analysis.status}
