from apps.tour_ai_agent.services.scene_context_service import get_scene_context
def recommendations_for_scene(scene): return get_scene_context(scene).get('products',[])
