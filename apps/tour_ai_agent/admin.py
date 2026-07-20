from django.contrib import admin
from .models import *
@admin.register(TourSceneAIProfile)
class SceneProfileAdmin(admin.ModelAdmin):
    list_display=("scene","final_scene_type","analysis_source","analysis_confidence","analyzed_at")
    search_fields=("scene__title","final_scene_type")
@admin.register(SceneProductMatch)
class SceneProductMatchAdmin(admin.ModelAdmin):
    list_display=("scene","product","confidence","is_verified")
    list_editable=("is_verified",)
admin.site.register([ProductVisualProfile,SceneAIRegion,TourAgentConversation,TourAgentMessage,TourAgentAction,VisitorSignal])
