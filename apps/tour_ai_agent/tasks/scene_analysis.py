from celery import shared_task

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def analyze_tour_scene(self, scene_id, force=False):
    from apps.tours.models import Scene360
    from apps.tour_ai_agent.vision.scene_analyzer import analyze_scene
    profile = analyze_scene(Scene360.objects.get(pk=scene_id), force=force)
    return {"scene_id": scene_id, "source": profile.analysis_source, "confidence": profile.analysis_confidence}
