# Twinscopes — Advanced 360 Computer Vision

## 1. Final vision pipeline

Each panorama is converted into overlapping perspective frames. The advanced profile uses up to 12 frames so the horizon, upper walls, labels, shelves and lower furniture zones are covered.

1. **YOLO** runs on every frame and stores generic object boxes, class labels and confidence.
2. **PaddleOCR** runs on every frame and stores exact text, polygons and confidence.
3. **Florence-2** is optional and can add a detailed local caption.
4. **Gemini Vision** is the primary semantic-fusion stage. It receives the perspective image plus the YOLO and OCR evidence and creates short, cautious titles, descriptions, material/color observations, text meanings, scene type, safety/accessibility observations and confidence.
5. **OpenAI Vision** is the semantic fallback. It is called for a frame only when Gemini fails; it is not used as a duplicate paid call when Gemini succeeds.
6. The fusion engine maps each box or OCR polygon back to panorama yaw/pitch coordinates and creates `VisionInsight` records used by the public viewer.

The model is explicitly forbidden from treating a visible object as a catalogue product unless a verified product record confirms it.

## 2. Long press in the public 360 viewer

A press held for about 650 ms on the panorama:

- converts the screen point to Marzipano yaw/pitch coordinates;
- finds the closest precomputed object or text region;
- displays a signed crop of the exact area;
- shows a concise title, description, confidence, OCR quotation, visible attributes and pipeline badges;
- allows the guest to ask Twinscopes AI a grounded follow-up question.

No image is sent to an LLM during the press. The response uses the analysis already stored in the database, so interaction is fast and predictable.

Public endpoints:

```text
POST /api/tour-ai/inspect-point/
GET  /api/tour-ai/vision-crop/<signed-token>/
```

## 3. Gemini embedding lifecycle fix

The Google Gen AI `Client` is now held open for the complete SDK operation using a request-scoped context manager. The result is fully extracted before the client closes. A fresh client is retried once when a stale transport is detected.

The embedding router also supports provider fallback and a failure cooldown. After a provider error, it is temporarily bypassed instead of logging the same failure for every guest message.

Recommended configuration when OpenAI is already configured:

```env
AI_PRIMARY_TEXT_PROVIDER=openai
AI_FALLBACK_TEXT_PROVIDER=gemini
AI_EMBEDDING_PROVIDER=auto
AI_FALLBACK_EMBEDDING_PROVIDER=openai
AI_PROVIDER_FAILURE_COOLDOWN_SECONDS=300

OPENAI_EMBEDDING_MODEL=text-embedding-3-small
GOOGLE_EMBEDDING_MODEL=gemini-embedding-001

VISION_ENABLE_YOLO=true
VISION_ENABLE_PADDLEOCR=true
VISION_ENABLE_FLORENCE2=false
VISION_ENABLE_GEMINI=true
VISION_ENABLE_OPENAI=true
VISION_PRIMARY_SEMANTIC_PROVIDER=gemini
VISION_FALLBACK_SEMANTIC_PROVIDER=openai
VISION_MAX_PANORAMA_FRAMES=12
VISION_SEMANTIC_MAX_FRAMES=12
VISION_LONG_PRESS_DURATION_MS=650
```

With `AI_EMBEDDING_PROVIDER=auto`, OpenAI embeddings are selected when an OpenAI key is present. Gemini remains active in its strongest role: visual semantic fusion.

## 4. Deployment

```bash
docker compose build django celery_worker celery_ai
docker compose up -d

docker exec -it visite360_app python manage.py migrate
docker exec -it visite360_app python manage.py collectstatic --noinput
```

Install the heavy local vision stack in the dedicated AI image/worker. PaddlePaddle itself must match the CPU/GPU platform.

```bash
pip install -r requirements-ai-full.txt
```

Analyze scenes that do not yet have Enterprise vision results:

```bash
docker exec -it visite360_app python manage.py analyze_existing_scenes
```

Rebuild all old scene analyses and interactive insight coordinates:

```bash
docker exec -it visite360_app python manage.py analyze_existing_scenes --force
```

Test one scene synchronously before processing the whole catalogue:

```bash
docker exec -it visite360_app python manage.py analyze_existing_scenes --force --sync --limit 1
```

## 5. Important database changes

Migration `vision_ai/0003_ocr_metadata_vision_insight.py` adds:

- metadata for OCR blocks;
- `VisionInsight` object/text records;
- panorama yaw/pitch coordinates;
- source provider list;
- signed crop support;
- optional verified product relation.

Always run migrations before testing the long-press interface.

## 6. Accuracy policy

The public card is evidence-first:

- YOLO label = generic visible object;
- PaddleOCR text = exact recognized text;
- Gemini/OpenAI description = short semantic interpretation;
- catalogue status = separate verified commercial fact;
- no invented brand, model, price, stock, service, link or identity.
