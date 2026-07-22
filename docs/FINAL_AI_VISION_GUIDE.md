# Twinscopes AI — Vision, website grounding and booking

## 1. Activate OpenAI and the vision providers

```env
OPENAI_API_KEY=sk-proj-...
AI_PRIMARY_TEXT_PROVIDER=openai
AI_FALLBACK_TEXT_PROVIDER=gemini
OPENAI_TEXT_MODEL=gpt-5.6
OPENAI_VISION_MODEL=gpt-5.6
VISION_ENABLE_YOLO=true
VISION_ENABLE_PADDLEOCR=true
VISION_ENABLE_GEMINI=true
VISION_ENABLE_OPENAI=true
```

Install the optional local vision stack when required:

```bash
pip install -r requirements-ai-full.txt
```

## 2. Analyze all existing 360 scenes

Queue only scenes not successfully analyzed:

```bash
docker exec -it visite360_app python manage.py analyze_existing_scenes
```

Reanalyze every scene with the improved pipeline:

```bash
docker exec -it visite360_app python manage.py analyze_existing_scenes --force
```

Run a small synchronous verification:

```bash
docker exec -it visite360_app python manage.py analyze_existing_scenes --force --sync --limit 1
```

The panorama is converted into overlapping perspective frames covering the horizon, upper walls and lower furniture zones. Results from object detection, OCR and multimodal LLMs are stored in `VisionAnalysis`, `VisionDetection`, `OCRTextBlock`, and copied to `Scene360.ai_analysis`.

## 3. Organization website and social profiles

Fill `website_url` in the organization, then create or update a Website `KnowledgeSource`. Running `sync_knowledge_source` indexes its pages in pgvector and automatically discovers Facebook, Instagram, TikTok, LinkedIn and YouTube links found on the official site. The agent consumes those indexed pages internally; it never asks the guest to visit or authorize the website.

The organization now supports:

- website and booking URLs;
- public email and phone;
- Facebook, Instagram, TikTok, LinkedIn and YouTube URLs;
- automatic social-link discovery;
- an option to enable website grounding.

## 4. Grounded answers

The public 360 assistant receives, for every question:

- the current scene and verified vision results;
- verified catalogue matches;
- active services and their booking links;
- the organization profile and official social links;
- the most relevant indexed website/document chunks.

It may only return URLs present in this trusted context. Missing information produces an honest “not confirmed” response rather than an invented answer.

## 5. Appointment workflow

Twinscopes automatically creates a public dynamic booking form for each organization. The guest provides name, phone, email, preferred date/time and notes. When an active default Google Calendar connection exists, the appointment is inserted automatically into the organization calendar and an invitation is sent to the guest email when provided.

## 6. Database migration and restart

```bash
docker exec -it visite360_app python manage.py migrate
docker compose restart django celery_worker celery_ai
```
