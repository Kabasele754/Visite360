from dataclasses import dataclass
@dataclass(frozen=True)
class VisionRoutingDecision: provider:str; reason:str; confidence:float
def choose_vision_provider(scene_confidence,object_confidences,detected_object_count):
    avg=sum(object_confidences)/len(object_confidences) if object_confidences else 0
    combined=round(scene_confidence*.6+avg*.4,4)
    if combined>=.82 and detected_object_count>=2:return VisionRoutingDecision('local','Local vision is sufficiently reliable.',combined)
    if combined>=.58:return VisionRoutingDecision('hybrid','Gemini validation can improve an uncertain local result.',combined)
    return VisionRoutingDecision('gemini','Local confidence is low.',combined)
