from __future__ import annotations
import json
from django.conf import settings
class OpenAIClient:
    def __init__(self):
        self.api_key=getattr(settings,'OPENAI_API_KEY',''); self.model=getattr(settings,'OPENAI_TOUR_AGENT_MODEL','gpt-5-mini')
    @property
    def enabled(self): return bool(self.api_key)
    def respond(self,*,instructions,input_text,tools=None):
        if not self.enabled:return None
        from openai import OpenAI
        client=OpenAI(api_key=self.api_key)
        kwargs={'model':self.model,'instructions':instructions,'input':input_text}
        if tools: kwargs['tools']=tools
        response=client.responses.create(**kwargs)
        return {'text':getattr(response,'output_text',''),'response_id':response.id,'raw':response}
