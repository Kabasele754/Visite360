from django.contrib import admin
from apps.ai_chat.models import ConversationFeedback, EnterpriseConversation, EnterpriseMessage

admin.site.register(EnterpriseConversation)
admin.site.register(EnterpriseMessage)
admin.site.register(ConversationFeedback)
