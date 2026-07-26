# Twinscopes AI Tour Architect — Automatic 360° Scene Intelligence

This release replaces the legacy generic hotspot generator with a review-first AI construction workflow for professional virtual tours.

## What happens after a 360° scene upload

1. The normal scene asset pipeline creates preview, mobile, desktop and tiled assets.
2. Enterprise Vision analyzes perspective frames with YOLO, PaddleOCR and the configured semantic providers.
3. Tour Architect post-processing creates:
   - a visual-quality assessment for the panorama;
   - exact reviewable object crops;
   - enhanced object previews;
   - client-readiness and clarity scores;
   - navigation-anchor candidates such as doors, corridors, stairs, lifts and entrances.
4. When the tour has enough analyzed scenes, Gemini receives scene previews, structured scene metadata and selected navigation-anchor crops.
5. Gemini returns a structured navigation proposal while treating existing manual and AI navigation links as fixed graph edges.
6. The administrator reviews, adjusts, approves or rejects every proposal.
7. Only approved links are converted to navigation hotspots.

The workflow never deletes or overwrites a manual hotspot. The old default `Info` and `Discover` hotspot generator is disabled.

## Dashboard workspace

Open the Tour Builder and choose **AI Architect**, or visit:

```text
/dashboard/o/<organization-slug>/tours/<tour-id>/architect/
```

The workspace includes four areas:

- **Overview:** readiness, scene graph and active AI run.
- **Scene quality:** sharpness, exposure, contrast, resolution, seam and horizon review.
- **Object catalogue:** exact crops, enhanced crops, confidence, clarity and approval controls.
- **Navigation proposals:** a visual equirectangular yaw/pitch editor, numeric fine-tuning, bidirectional control, evidence and application status.

## Safety rules

- Generic public information hotspots are no longer created automatically.
- Manual hotspots and existing navigation links are preserved and displayed in the architecture graph.
- Gemini results are staged as proposals, not published directly.
- A manual navigation link causes a conflict status instead of being overwritten.
- Deterministic fallback links are low-confidence and require review.
- Automatic application is disabled by default.
- Enhanced images are stored as previews only; original panoramas are never replaced.

## Configuration

```env
TOUR_ARCHITECT_ENABLED=true
TOUR_ARCHITECT_AUTO_RUN=true
TOUR_ARCHITECT_REQUIRE_ALL_SCENES_ANALYZED=true
TOUR_ARCHITECT_GEMINI_MODEL=gemini-2.5-flash
TOUR_ARCHITECT_LOCAL_THREAD_WORKERS=1
TOUR_ARCHITECT_STALE_MINUTES=45
TOUR_ARCHITECT_TIMEOUT_SECONDS=150
TOUR_ARCHITECT_MAX_OUTPUT_TOKENS=5000
TOUR_ARCHITECT_MAX_ANCHORS_PER_SCENE=6
TOUR_ARCHITECT_MAX_OUTGOING_LINKS=4
TOUR_ARCHITECT_INCLUDE_ANCHOR_CROPS=true

# Keep review-first behavior in production.
TOUR_ARCHITECT_AUTO_APPLY_SAFE_LINKS=false
TOUR_ARCHITECT_AUTO_APPLY_MIN_CONFIDENCE=0.94

TOUR_OBJECT_CATALOG_MIN_CONFIDENCE=0.25
TOUR_OBJECT_CATALOG_MAX_CANDIDATES=90
TOUR_OBJECT_CLIENT_READY_MIN_CONFIDENCE=0.58
TOUR_OBJECT_CLIENT_READY_MIN_CLARITY=0.46
```

## Local execution

With `DEBUG=True`, automatic architecture runs use a local background thread. For a direct test:

```bash
python manage.py build_tour_architecture --tour 7 --mode sync --force
```

Show the latest status:

```bash
python manage.py build_tour_architecture --tour 7 --status-only
```

## Production execution

The Tour Architect Celery task is routed to the `ai` queue.

```bash
docker compose exec django \
python manage.py build_tour_architecture \
  --tour 7 \
  --mode celery \
  --force
```

Follow the worker:

```bash
docker compose logs --tail=150 -f ai_worker
```

## Review and application

The safest path is to apply links in the dashboard after examining the graph and every crop.

For a controlled synchronous test that applies only Gemini proposals above the configured high-confidence threshold:

```bash
python manage.py build_tour_architecture \
  --tour 7 \
  --mode sync \
  --force \
  --apply-safe
```

Manual hotspots are still preserved during this action.

## Legacy hotspot cleanup

Preview the legacy generic AI hotspots that can be removed:

```bash
python manage.py cleanup_legacy_ai_hotspots --tour 7
```

Delete only the matched AI-generated `info`, `product` and `cta` records:

```bash
python manage.py cleanup_legacy_ai_hotspots --tour 7 --apply
```

This command does not target manual hotspots or navigation hotspots.

## Deployment

```bash
docker compose config -q

docker compose build django ai_worker celery_worker

docker compose up -d django ai_worker celery_worker

docker compose exec django python manage.py migrate --noinput

docker compose exec django python manage.py collectstatic --noinput

docker compose exec django python manage.py check
```

Do not remove Docker volumes. PostgreSQL, media, scenes, panoramas, PDFs, users and previous analyses remain persistent.
