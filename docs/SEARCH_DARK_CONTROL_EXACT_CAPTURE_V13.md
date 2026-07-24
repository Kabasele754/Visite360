# Twinscopes Search, Dark UI, Control Center and Exact Capture — v13

## Scope

This patch refines four customer-facing areas without changing existing database models:

1. The Home page now exposes one compact search launcher.
2. Search opens a dedicated responsive page with a back button, live results and full light/dark support.
3. The dashboard and Control Center use unified dark surfaces, structured operations, resource filtering and theme-aware Chart.js charts.
4. Panorama object inspection captures and analyzes the exact pixels inside the user-selected rectangle whenever the viewer canvas can be read.

## Home and dedicated search

- Route: `/search/`
- View: `apps.public.views.PublicSearchView`
- Template: `templates/public/search.html`
- Home launcher: `templates/public/partials/discovery_agent.html`
- Assets:
  - `static/public/css/discovery-launcher-v3.css`
  - `static/public/js/discovery-launcher-v3.js`
  - `static/public/css/discovery-search-page-v3.css`
  - `static/public/js/discovery-search-page-v3.js`

The launcher no longer displays a large explanation panel. Clicking or focusing the input opens the dedicated search workspace. `Command/Ctrl + K` is supported.

## Dashboard and Control Center

- Unified dashboard dark-mode overrides are in `templates/dashboard/base.html`.
- Control Center assets:
  - `static/platform_console/css/control-center.css`
  - `static/platform_console/js/control-center.js`
- Resource controls are grouped by business purpose and can be filtered from the command bar.
- Chart.js text, grids, borders, tooltips and doughnut borders are rebuilt when the dashboard theme changes.

## Exact object capture

The selection workflow now behaves like a screenshot crop:

1. The visitor long-presses the panorama.
2. A movable and resizable frame appears.
3. The browser crops the visible panorama canvas to the exact rectangle.
4. The crop is compressed as a bounded JPEG data URL.
5. Django validates MIME type, dimensions and payload size.
6. YOLO and the semantic provider receive only that crop.
7. The persisted frame contains the exact crop, so the returned result image has the same orientation the visitor saw.

If the browser cannot read the WebGL canvas, the existing yaw/pitch projection pipeline remains available as a safe fallback.

### Security and persistence

- Maximum encoded URL length is bounded.
- Maximum decoded bytes and dimensions are bounded.
- Only JPEG, PNG and WebP data URLs are accepted.
- The base64 image is never stored in JSON metadata or visitor signals.
- Public result payloads do not expose internal provider names.
- Technical metadata is filtered from public visual cards.

## Optional environment values

```env
VISION_POINT_EXACT_CAPTURE_SEMANTIC_MIN_CONFIDENCE=0.58
VISION_POINT_EXACT_CAPTURE_ONLY_MIN_CONFIDENCE=0.64
VISION_POINT_CAPTURE_MAX_BYTES=2000000
VISION_POINT_CAPTURE_MAX_DIMENSION=1024
VISION_POINT_CAPTURE_MAX_DATA_URL_LENGTH=3000000
```

Defaults are already defined, so deployment does not require adding these values immediately.

## Safe deployment

```bash
cd /root/Visite360
cp .env ".env.backup_$(date +%Y%m%d_%H%M%S)"

docker compose config -q
docker compose build django ai_worker
docker compose up -d django ai_worker

docker compose exec django python manage.py collectstatic --noinput
docker compose exec django python manage.py check
docker compose ps
```

No migration is required.

Do not run commands that remove volumes, such as `docker compose down -v`, `docker volume prune`, or `docker system prune --volumes`.

## Verification

### Search

- Open the Home page in light and dark mode.
- Click the search bar and confirm navigation to `/search/`.
- Confirm the Back button returns to the previous page.
- Search a Tour by title and confirm dynamic results.

### Control Center

- Open `/dashboard/control-center/`.
- Toggle light/dark mode.
- Confirm chart labels and cards remain readable.
- Press `Command/Ctrl + K` and filter a resource.

### Exact capture

- Open a published Tour.
- Long-press an object.
- Resize the frame tightly around the object.
- Confirm both action buttons remain visible.
- Select **Analyze selection**.
- Confirm the returned image matches the framed orientation and area.
- Select an empty region and confirm the interface reports that no precise object was identified rather than describing the whole room.
