from celery import shared_task

@shared_task
def score_conversation(conversation_id):
    from apps.tour_ai_agent.models import TourAgentConversation
    conversation = TourAgentConversation.objects.get(pk=conversation_id)
    kinds = set(conversation.actions.values_list("action_type", flat=True))
    score = min(100, conversation.messages.filter(role="user").count() * 5 + len(kinds) * 12 + (25 if "book_appointment" in kinds else 0))
    conversation.lead_score = score
    conversation.save(update_fields=["lead_score", "updated_at"])
    return score
