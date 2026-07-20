from __future__ import annotations
import json
from pathlib import Path
from django.conf import settings
class GeminiVisionClient:
    def __init__(self): self.model=getattr(settings,'GEMINI_TOUR_VISION_MODEL','gemini-2.5-flash')
    @property
    def enabled(self): return bool(getattr(settings,'GEMINI_API_KEY','') or getattr(settings,'GOOGLE_CLOUD_PROJECT',''))
    def analyze(self,frame_paths,local_context):
        if not self.enabled:return {}
        from google import genai
        from google.genai import types
        client=genai.Client(vertexai=bool(getattr(settings,'GOOGLE_GENAI_USE_VERTEXAI',False)),project=getattr(settings,'GOOGLE_CLOUD_PROJECT',None),location=getattr(settings,'GOOGLE_CLOUD_LOCATION',None),api_key=getattr(settings,'GEMINI_API_KEY',None))
        parts=[types.Part.from_text(text='Analyze these views of one 360 scene. Return strict JSON with scene_type, summary, features, commercial_intents, suggested_questions, opening_message. Local context: '+json.dumps(local_context))]
        for p in frame_paths: parts.append(types.Part.from_bytes(data=Path(p).read_bytes(),mime_type='image/jpeg'))
        r=client.models.generate_content(model=self.model,contents=[types.Content(role='user',parts=parts)],config=types.GenerateContentConfig(response_mime_type='application/json'))
        try:return json.loads(r.text)
        except Exception:return {'summary':r.text or ''}
