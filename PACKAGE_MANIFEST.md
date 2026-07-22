# Package manifest

Package: Twinscopes AI Enterprise — Local & Production Vision Scan Final  
Build date: 2026-07-22

## Included advanced vision capabilities

- 12-view balanced and 24/32-view deep panorama projection.
- YOLO object detection over every projected view.
- PaddleOCR text extraction over every projected view.
- Gemini semantic fusion grounded in YOLO/OCR evidence.
- OpenAI Vision credential-aware fallback.
- Interactive long-press object/text cards using precomputed `VisionInsight` regions.
- Non-blocking local background-thread scan without Docker, Redis or Celery.
- Production Celery queue for existing and on-demand scenes.
- Annotated HTML/JPEG scene reports.
- Bulk scan, retry, status, live credential and scene inventory commands.

## Embedding corrections

- Vertex/Gemini native output is capped/configured at 768 and normalized before storage-width padding.
- Local `.env`, process environment and Docker secret loading for OpenAI are preserved.
- Unconfigured providers are skipped rather than repeatedly entering cooldown.
- Knowledge chunks record embedding provider/model/dimensions; vector search does not mix incompatible embedding spaces.

## Verification performed for this build

- Python compilation of all `apps/` and `config/` files: passed.
- JavaScript syntax check for the tour AI agent: passed.
- Shell syntax checks for all scripts: passed.
- Docker Compose YAML parsing: passed.
- 12, 24 and 32-frame panorama extraction tests: passed.
- Panorama center-coordinate geometry test: passed.
- Static checks found no remaining `done`/`error` scene-status writes and no hard-coded Gemini 1536 output request.
- ZIP integrity and SHA-256 verification: performed during packaging.

Full Django/database/provider integration tests were not executed inside the packaging sandbox because it does not contain Django, Google Gen AI, Ultralytics, PaddleOCR, pgvector, the user's database, media files or cloud credentials. The package includes `check_ai_stack --live`, synchronous scene scans and annotated reports so those tests run against the user's real local or production environment.

## Exact object point-inspection update

- `apps/vision_ai/services/point_inspection.py`
- `apps/vision_ai/services/geometry.py`
- `apps/vision_ai/services/insights.py`
- `apps/tour_ai_agent/management/commands/rebuild_vision_insights.py`
- `docs/EXACT_OBJECT_POINT_INSPECTION.md`
- `OBJECT_POINT_FIX_REPORT.md`
