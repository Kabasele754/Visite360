# app_site/consumers.py
from channels.generic.websocket import AsyncWebsocketConsumer
import json


class TestConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        await self.send(text_data=json.dumps({"message": "WS connecté ✅"}))

    async def receive(self, text_data=None, bytes_data=None):
        # Echo simple
        await self.send(text_data=json.dumps({"echo": text_data}))

    async def disconnect(self, close_code):
        pass