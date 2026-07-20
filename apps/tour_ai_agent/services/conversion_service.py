from apps.tour_ai_agent.models import TourAgentAction
def record_action(conversation,action_type,payload,result=None,succeeded=False): return TourAgentAction.objects.create(conversation=conversation,action_type=action_type,payload=payload or {},result=result or {},succeeded=succeeded)
