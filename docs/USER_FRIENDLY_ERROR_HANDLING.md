# Twinscopes — User-friendly errors and PDF.js production fix

## What changed

- PDF.js technical exceptions are never inserted into the public modal.
- Guests receive a short, understandable message and a support reference.
- Technical details remain available only in the browser console.
- When the PDF.js module or worker cannot start on desktop, Twinscopes automatically uses the browser's native PDF viewer inside the modal.
- Mobile users receive clear Retry and Open document actions.
- Both modern and legacy PDF.js module/worker URLs are generated through Django staticfiles.
- Nginx serves `.mjs` files as JavaScript, which is required by module workers while `nosniff` is enabled.
- Duplicate static copies under `apps/tours/static` were removed; `static/` is now the single source of truth.
- AI chat and point-inspection failures now show a friendly message with a support reference instead of a provider/network exception.
- `analyze_existing_scenes` now selects missing Enterprise `VisionAnalysis` rows instead of trusting the legacy `Scene360.ai_analysis_status` value.

## Safe production deployment

These commands do not delete PostgreSQL, media, static or AI model volumes.

```bash
docker compose config -q
docker compose build django nginx
docker compose up -d django nginx
docker compose restart ai_worker celery_worker celery_beat
```

Never run:

```bash
docker compose down -v
docker volume prune
docker system prune --volumes
```

## PDF.js verification

```bash
docker compose exec nginx sh -lc "grep -n 'application/javascript' /etc/nginx/mime.types | head"
```

The line must contain `mjs`.

```bash
curl -I https://twinscopes.com/static/public/vendor/pdfjs/build/pdf.worker.mjs
```

Expected:

- HTTP 200
- `Content-Type: application/javascript`

If the browser still references an old hash, clear only the browser/site cache or perform a hard refresh. Do not delete Docker data volumes.

## Vision production settings

The installed packages can be present while the feature is disabled by `.env`. Use:

```env
VISION_ENABLE_PADDLEOCR=true
VISION_ENABLE_YOLO=true
VISION_ENABLE_GEMINI=true
VISION_ENABLE_OPENAI=true
VISION_ON_DEMAND_ANALYSIS_MODE=celery
```

Then recreate only application workers:

```bash
docker compose up -d --force-recreate django ai_worker celery_worker
```

## Analyze existing scenes safely in batches

After this patch, missing Enterprise analyses are detected from `VisionAnalysis`, even when the old scene pipeline says `ready`.

```bash
docker compose exec django python manage.py analyze_existing_scenes \
  --mode celery \
  --providers yolo,paddleocr,gemini,openai \
  --limit 5
```

Repeat after the current batch finishes. For one tour:

```bash
docker compose exec django python manage.py analyze_existing_scenes \
  --tour 8 \
  --mode celery \
  --providers yolo,paddleocr,gemini,openai
```

Monitor:

```bash
docker compose logs -f ai_worker
```

## Docker Compose `$v` warning

If Compose prints `The "v" variable is not set`, find the literal variable:

```bash
grep -RInE '\$v|\$\{v\}' docker-compose*.yml .env* 2>/dev/null
```

For a secret containing a literal dollar sign, prefer Docker secrets. In `.env`, a single-quoted value keeps it literal:

```env
EXAMPLE_SECRET='abc$v123'
```
