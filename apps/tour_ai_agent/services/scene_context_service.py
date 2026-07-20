from apps.tour_ai_agent.models import TourSceneAIProfile,SceneProductMatch
def get_scene_context(scene):
    profile=TourSceneAIProfile.objects.filter(scene=scene).first()
    matches=SceneProductMatch.objects.filter(scene=scene,product__status='active').select_related('product','product__category').order_by('-is_verified','-confidence')[:8]
    return {'scene':{'id':scene.id,'title':scene.title,'type':profile.final_scene_type if profile else '', 'summary':profile.final_summary if profile else '', 'features':profile.final_features if profile else []},'products':[{'id':m.product_id,'name':m.product.name,'price':str(m.product.price),'currency':m.product.currency,'verified':m.is_verified,'confidence':round(m.confidence,3)} for m in matches]}
