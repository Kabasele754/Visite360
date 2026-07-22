from django.urls import include, path
from rest_framework.routers import DefaultRouter
from apps.ai_chat.views import ConversationFeedbackViewSet, EnterpriseConversationViewSet

router = DefaultRouter()
router.register("conversations", EnterpriseConversationViewSet, basename="enterprise-conversation")
router.register("feedback", ConversationFeedbackViewSet, basename="conversation-feedback")
urlpatterns = [path("", include(router.urls))]
