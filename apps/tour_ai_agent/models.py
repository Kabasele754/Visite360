from django.conf import settings
from django.db import models
from apps.common.models import TimeStampedModel

class TourSceneAIProfile(TimeStampedModel):
    SOURCE_LOCAL="local"; SOURCE_HYBRID="hybrid"; SOURCE_GEMINI="gemini"
    scene=models.OneToOneField("tours.Scene360",on_delete=models.CASCADE,related_name="tour_ai_profile")
    image_hash=models.CharField(max_length=64,db_index=True,blank=True)
    local_scene_type=models.CharField(max_length=120,blank=True)
    local_scene_confidence=models.FloatField(default=0)
    local_detections=models.JSONField(default=list,blank=True)
    local_features=models.JSONField(default=list,blank=True)
    gemini_summary=models.TextField(blank=True)
    gemini_payload=models.JSONField(default=dict,blank=True)
    final_scene_type=models.CharField(max_length=120,blank=True)
    final_summary=models.TextField(blank=True)
    final_features=models.JSONField(default=list,blank=True)
    commercial_intents=models.JSONField(default=list,blank=True)
    suggested_questions=models.JSONField(default=list,blank=True)
    suggested_opening_message=models.CharField(max_length=500,blank=True)
    analysis_source=models.CharField(max_length=20,default=SOURCE_LOCAL,choices=[(SOURCE_LOCAL,"Local"),(SOURCE_HYBRID,"Hybrid"),(SOURCE_GEMINI,"Gemini")])
    analysis_confidence=models.FloatField(default=0)
    analysis_version=models.PositiveIntegerField(default=1)
    analyzed_at=models.DateTimeField(null=True,blank=True)
    last_error=models.TextField(blank=True)

class ProductVisualProfile(TimeStampedModel):
    product=models.OneToOneField("vendors.Product",on_delete=models.CASCADE,related_name="tour_ai_visual_profile")
    image_hash=models.CharField(max_length=64,db_index=True,blank=True)
    detected_labels=models.JSONField(default=list,blank=True)
    visual_embedding=models.JSONField(default=list,blank=True)
    primary_category=models.CharField(max_length=120,blank=True)
    dominant_features=models.JSONField(default=list,blank=True)
    indexed_at=models.DateTimeField(null=True,blank=True)

class SceneProductMatch(TimeStampedModel):
    scene=models.ForeignKey("tours.Scene360",on_delete=models.CASCADE,related_name="tour_ai_product_matches")
    product=models.ForeignKey("vendors.Product",on_delete=models.CASCADE,related_name="tour_ai_scene_matches")
    confidence=models.FloatField(default=0)
    match_reason=models.TextField(blank=True)
    is_verified=models.BooleanField(default=False)
    class Meta:
        constraints=[models.UniqueConstraint(fields=("scene","product"),name="tour_ai_unique_scene_product")]

class SceneAIRegion(TimeStampedModel):
    scene=models.ForeignKey("tours.Scene360",on_delete=models.CASCADE,related_name="tour_ai_regions")
    label=models.CharField(max_length=120)
    yaw_min=models.FloatField(); yaw_max=models.FloatField(); pitch_min=models.FloatField(); pitch_max=models.FloatField()
    product=models.ForeignKey("vendors.Product",null=True,blank=True,on_delete=models.SET_NULL,related_name="tour_ai_regions")
    confidence=models.FloatField(default=0)

class TourAgentConversation(TimeStampedModel):
    STATUS=[("active","Active"),("converted","Converted"),("closed","Closed")]
    organization=models.ForeignKey("organizations.Organization",on_delete=models.CASCADE,related_name="tour_ai_conversations")
    tour=models.ForeignKey("tours.Tour",on_delete=models.CASCADE,related_name="ai_conversations")
    scene=models.ForeignKey("tours.Scene360",on_delete=models.SET_NULL,null=True,blank=True,related_name="ai_conversations")
    visitor_id=models.CharField(max_length=120,db_index=True)
    session_id=models.CharField(max_length=120,db_index=True)
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name="tour_ai_conversations")
    status=models.CharField(max_length=20,choices=STATUS,default="active")
    locale=models.CharField(max_length=16,default="en")
    detected_intent=models.CharField(max_length=100,blank=True)
    lead_score=models.PositiveSmallIntegerField(default=0)
    summary=models.TextField(blank=True)
    consent_marketing=models.BooleanField(default=False)
    last_activity_at=models.DateTimeField(auto_now=True)

class TourAgentMessage(TimeStampedModel):
    ROLE=[("user","User"),("assistant","Assistant"),("tool","Tool"),("system","System")]
    conversation=models.ForeignKey(TourAgentConversation,on_delete=models.CASCADE,related_name="messages")
    role=models.CharField(max_length=20,choices=ROLE)
    content=models.TextField(blank=True)
    metadata=models.JSONField(default=dict,blank=True)

class TourAgentAction(TimeStampedModel):
    conversation=models.ForeignKey(TourAgentConversation,on_delete=models.CASCADE,related_name="actions")
    action_type=models.CharField(max_length=80,db_index=True)
    payload=models.JSONField(default=dict,blank=True)
    result=models.JSONField(default=dict,blank=True)
    succeeded=models.BooleanField(default=False)

class VisitorSignal(TimeStampedModel):
    conversation=models.ForeignKey(TourAgentConversation,on_delete=models.CASCADE,related_name="signals")
    signal_type=models.CharField(max_length=80,db_index=True)
    scene=models.ForeignKey("tours.Scene360",on_delete=models.SET_NULL,null=True,blank=True)
    payload=models.JSONField(default=dict,blank=True)
