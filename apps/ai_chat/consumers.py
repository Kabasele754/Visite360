from __future__ import annotations

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.ai_chat.models import EnterpriseConversation
from apps.ai_chat.serializers import EnterpriseMessageSerializer
from apps.ai_chat.services.chat import respond_to_message


class EnterpriseChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        self.conversation = await self._get_conversation()
        if not self.conversation:
            await self.close(code=4403)
            return
        await self.accept()
        await self.send_json({"type": "connected", "conversation_id": str(self.conversation_id)})

    async def receive_json(self, content, **kwargs):
        text = str(content.get("message", "")).strip()
        if not text:
            await self.send_json({"type": "error", "detail": "message is required"})
            return
        await self.send_json({"type": "status", "status": "thinking"})
        data = await self._respond(text)
        await self.send_json({"type": "message", "message": data})

    @database_sync_to_async
    def _get_conversation(self):
        user = self.scope.get("user")
        queryset = EnterpriseConversation.objects.select_related("organization", "agent", "scene")
        if getattr(user, "is_authenticated", False):
            if user.is_superuser:
                return queryset.filter(pk=self.conversation_id).first()
            return queryset.filter(pk=self.conversation_id, organization__memberships__user=user, organization__memberships__is_active=True).first()
        return None

    @database_sync_to_async
    def _respond(self, text):
        message = respond_to_message(self.conversation, text, user=self.scope.get("user"))
        return EnterpriseMessageSerializer(message).data
