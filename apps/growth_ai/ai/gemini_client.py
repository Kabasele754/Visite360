from django.conf import settings

def generate_text(prompt: str) -> str:
    if not getattr(settings, "AI_ENABLED", False):
        raise RuntimeError("AI is disabled. Configure Vertex AI or GEMINI_API_KEY.")
    from google import genai
    if getattr(settings, "GOOGLE_GENAI_USE_VERTEXAI", False):
        client = genai.Client(vertexai=True, project=settings.GOOGLE_CLOUD_PROJECT, location=settings.GOOGLE_CLOUD_LOCATION)
    else:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
    response = client.models.generate_content(model=getattr(settings, "GEMINI_MARKET_MODEL", "gemini-2.5-flash"), contents=prompt)
    return (response.text or "").strip()
