# Twinscopes — Local and Production 360° Vision Scan

This version fixes the two runtime errors observed in local development:

1. Vertex AI embedding requests no longer send an unsupported 1536-dimensional output to endpoints limited to 768 dimensions. Google vectors are requested at their native supported size, normalized, then padded to the 1536-dimensional pgvector storage column.
2. `OPENAI_API_KEY` is now read correctly from the local `.env` file. Previously, a later settings assignment only checked the process environment and replaced the value loaded by `python-decouple`.

It also repairs legacy scene statuses (`done` → `ready`, `error` → `failed`) and lets a long press start a missing scene analysis once, then poll until the result is ready.

## 1. Prepare local development without Docker

```bash
cd /path/to/twinscopes
cp .env.local.example .env
```

Edit `.env`. The key settings are:

```env
DJANGO_SETTINGS_MODULE=config.settings.dev

GOOGLE_GENAI_USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT=ziarama-wedding-akk
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_EMBEDDING_MODEL=text-embedding-004
GOOGLE_EMBEDDING_NATIVE_DIMENSIONS=768
AI_EMBEDDING_PROVIDER=gemini
AI_EMBEDDING_DIMENSIONS=1536

OPENAI_API_KEY=sk-proj-...
VISION_ENABLE_OPENAI=true

VISION_ENABLE_YOLO=true
VISION_ENABLE_PADDLEOCR=true
VISION_ENABLE_GEMINI=true
VISION_PRIMARY_SEMANTIC_PROVIDER=gemini
VISION_FALLBACK_SEMANTIC_PROVIDER=openai
VISION_PUBLIC_ON_DEMAND_SCAN=true
VISION_ON_DEMAND_ANALYSIS_MODE=auto
```

For Vertex AI, either set an absolute `GOOGLE_APPLICATION_CREDENTIALS` path or configure Application Default Credentials:

```bash
gcloud auth application-default login
```

Create the environment:

```bash
./scripts/setup_local_vision.sh
source .venv/bin/activate
```

PaddleOCR requires a compatible PaddlePaddle build. If `check_ai_stack` reports `paddle=false`, install the wheel matching the Mac architecture and Python version, then rerun the check. The rest of the vision pipeline can still run in partial mode while PaddleOCR is unavailable.

## 2. Verify credentials and dependencies with real calls

```bash
python manage.py check_ai_stack --live
```

Expected important lines:

```text
OPENAI_KEY_PRESENT=True
YOLO_MODEL_EXISTS=True
LIVE_EMBEDDING_TESTS={... "gemini": {"ok": true ...}}
```

When OpenAI is intentionally not configured, it is skipped instead of failing and entering the cooldown log repeatedly.

## 3. Scan one existing scene synchronously

The screenshot used scene `22`, so the real local test is:

```bash
python manage.py check_ai_stack \
  --scene 22 \
  --force \
  --providers yolo,paddleocr,gemini,openai
```

This executes the complete pipeline in the current terminal:

1. loads the existing panorama from `Scene360`;
2. extracts 12 perspective frames;
3. runs YOLO over every frame;
4. runs PaddleOCR over every frame;
5. selects the most informative frames;
6. uses Gemini Vision to interpret grounded YOLO/OCR evidence;
7. uses OpenAI Vision only as semantic fallback;
8. creates interactive `VisionInsight` regions;
9. marks the scene `ready` or `failed` using valid `PipelineStatus` values.

## 4. Generate an annotated visual report

After scanning scene 22:

```bash
python manage.py export_scene_vision_report 22 --output ./vision_reports
```

The command creates:

```text
vision_reports/
  scene-22-<analysis-uuid>/
    index.html
    report.json
    frames/
      frame-00-annotated.jpg
      frame-01-annotated.jpg
      ...
```

Open `index.html` in the browser. It displays every perspective image with YOLO boxes, OCR polygons, semantic descriptions, provider warnings, object counts and interactive insight data. This is the recommended way to validate whether a shop scene is being understood correctly before enabling it publicly.

## 5. Scan all scenes already stored locally

Show status without running anything:

```bash
python manage.py analyze_existing_scenes --status-only
```

Scan all missing scenes synchronously:

```bash
python manage.py analyze_existing_scenes \
  --mode sync \
  --providers yolo,paddleocr,gemini,openai \
  --json-report ./vision_reports/local-scan.json
```

Scan a specific tour:

```bash
python manage.py analyze_existing_scenes --tour 7 --mode sync
```

Scan selected scenes:

```bash
python manage.py analyze_existing_scenes \
  --scene 22 \
  --scene 23 \
  --scene 24 \
  --mode sync \
  --force
```

Retry only failed scenes:

```bash
python manage.py analyze_existing_scenes --retry-failed --mode sync
```

## 6. What happens during a long press

When a public visitor presses and holds on a scene that has never been analyzed:

- Twinscopes creates only one pending `VisionAnalysis` for that scene;
- local DEBUG mode runs it in a background Python thread when `VISION_ON_DEMAND_ANALYSIS_MODE=auto`;
- production dispatches it to Celery;
- the visual card displays “Scanning this 360° scene”;
- the browser polls the same point every few seconds;
- as soon as the analysis is complete, the object/text card replaces the progress message.

For production traffic, bulk scanning before publication is still recommended. On-demand scanning is a safety net, not the primary production workflow.

## 7. Production scan for scenes already created

Apply migrations first:

```bash
python manage.py migrate
```

The data migration repairs invalid legacy statuses.

With Celery running:

```bash
DJANGO_SETTINGS_MODULE=config.settings.prod \
python manage.py analyze_existing_scenes \
  --mode celery \
  --providers yolo,paddleocr,gemini,openai \
  --json-report /var/log/twinscopes/vision-queue.json
```

For Docker production:

```bash
docker exec -it visite360_app python manage.py migrate

docker exec -it visite360_app \
  python manage.py analyze_existing_scenes \
  --mode celery \
  --providers yolo,paddleocr,gemini,openai

docker compose logs -f celery_ai
```

Check progress:

```bash
python manage.py analyze_existing_scenes --status-only
```

## 8. Rebuild the knowledge vectors after the embedding fix

Use one embedding provider consistently for both indexing and search. After changing the provider/model/dimensionality, rebuild the existing knowledge documents:

```bash
python manage.py reindex_knowledge
```

For one organization:

```bash
python manage.py reindex_knowledge --organization 3
```

This prevents query vectors from being compared with documents generated in a different embedding space.

## 9. Recommended production configuration

```env
AI_EMBEDDING_PROVIDER=gemini
AI_FALLBACK_EMBEDDING_PROVIDER=openai
AI_EMBEDDING_DIMENSIONS=1536
GOOGLE_EMBEDDING_MODEL=text-embedding-004
GOOGLE_EMBEDDING_NATIVE_DIMENSIONS=768

VISION_ENABLE_YOLO=true
VISION_ENABLE_PADDLEOCR=true
VISION_ENABLE_GEMINI=true
VISION_ENABLE_OPENAI=true
VISION_PRIMARY_SEMANTIC_PROVIDER=gemini
VISION_FALLBACK_SEMANTIC_PROVIDER=openai
VISION_PUBLIC_ON_DEMAND_SCAN=true
VISION_ON_DEMAND_ANALYSIS_MODE=celery
VISION_ON_DEMAND_RETRY_AFTER_MS=3000
```

If OpenAI is the selected embedding provider in production, set `AI_EMBEDDING_PROVIDER=openai`, keep it stable, and rerun `reindex_knowledge` once.

## 10. One-command local scan (no Docker, no Redis, no Celery)

After configuring `.env` and running `scripts/setup_local_vision.sh`, scan every missing local scene with:

```bash
./scripts/scan_local_vision.sh
```

Force a real rescan of scene 22 only:

```bash
./scripts/scan_local_vision.sh --scene 22 --force
```

The script applies migrations, prints the loaded settings and scene inventory, runs the complete pipeline synchronously and writes a JSON report under `vision_reports/`.

For browser long presses in local `DEBUG` mode, `auto` now means a background Python thread. The HTTP request returns immediately, the card displays scanning progress and polls until the result is ready. This does not require Docker, Redis or Celery. Command-line tests still use `--mode sync`, which is deterministic and displays provider errors directly in the terminal.

## 11. Production one-command queue

With Redis and the `celery_ai` worker running:

```bash
DJANGO_SETTINGS_MODULE=config.settings.prod ./scripts/queue_production_vision.sh
```

Force all scenes, including already successful analyses:

```bash
DJANGO_SETTINGS_MODULE=config.settings.prod \
./scripts/queue_production_vision.sh --force
```

The production script queues work and returns quickly; processing continues in `celery_ai`.

## 12. Balanced and deep scan profiles

Local CPU/Mac balanced profile:

```env
TOUR_AI_YOLO_MODEL_NAME=yolo11n.pt
TOUR_AI_YOLO_IMAGE_SIZE=896
VISION_MAX_PANORAMA_FRAMES=12
VISION_SEMANTIC_MAX_FRAMES=8
```

Production high-accuracy profile, preferably with adequate CPU/GPU resources:

```env
TOUR_AI_YOLO_MODEL_NAME=yolo11m.pt
TOUR_AI_YOLO_IMAGE_SIZE=1280
VISION_MAX_PANORAMA_FRAMES=24
VISION_SEMANTIC_MAX_FRAMES=12
```

The 24-frame profile creates 12 overlapping horizon views, six upper views and six lower views. YOLO and PaddleOCR process every frame, while Gemini/OpenAI semantic vision is limited to the most informative frames to control latency and cost.

After changing the YOLO model name, download it once:

```bash
python manage.py download_tour_ai_models
```

## 13. Embedding-space safety

Gemini and OpenAI vectors must not be mixed blindly even when both are stored in a 1536-column pgvector field. New knowledge chunks record their actual embedding provider, model and storage dimensions. Search uses vectors from the same provider/model only. If an old index has no matching metadata, Twinscopes falls back to lexical search and asks the administrator to run:

```bash
python manage.py reindex_knowledge
```

Choose one primary embedding provider for a deployment and keep it stable. The other provider remains available for text/vision fallback without corrupting semantic similarity.
