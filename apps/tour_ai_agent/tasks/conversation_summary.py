from celery import shared_task

@shared_task
def summarize_conversation(conversation_id):
    from apps.tour_ai_agent.models import TourAgentConversation
    conversation = TourAgentConversation.objects.get(pk=conversation_id)
    texts = list(conversation.messages.order_by("-id").values_list("content", flat=True)[:12])
    conversation.summary = " | ".join(reversed(texts))[:4000]
    conversation.save(update_fields=["summary", "updated_at"])
    return conversation.summary
