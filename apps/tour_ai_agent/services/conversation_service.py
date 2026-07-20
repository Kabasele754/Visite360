from django.utils import timezone
from apps.tour_ai_agent.models import TourAgentConversation,TourAgentMessage
def get_or_create_conversation(*,organization,tour,scene,visitor_id,session_id,user,locale='en'):
    conv=TourAgentConversation.objects.filter(tour=tour,visitor_id=visitor_id,status='active').order_by('-updated_at').first()
    if not conv: conv=TourAgentConversation.objects.create(organization=organization,tour=tour,scene=scene,visitor_id=visitor_id,session_id=session_id,user=user if getattr(user,'is_authenticated',False) else None,locale=locale[:16])
    elif scene and conv.scene_id!=scene.id: conv.scene=scene; conv.save(update_fields=['scene','last_activity_at'])
    return conv
def add_message(conv,role,content,metadata=None): return TourAgentMessage.objects.create(conversation=conv,role=role,content=content,metadata=metadata or {})
