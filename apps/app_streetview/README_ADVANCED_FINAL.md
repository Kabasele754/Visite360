# Street View Publisher — Advanced Final Version

This version keeps the canonical TwinScopes architecture:

Organization → Place → existing Tour → existing Scene360 → Google Street View publication state.

It does not duplicate tours, scenes, or 360 images.

## Added modules

1. Studio camera + map
   - 360 viewer + Google map side by side.
   - Draggable map markers.
   - Live heading arrow.
   - Save GPS + camera overrides.

2. Quality check
   - Validates GPS, image presence, 2:1 panorama ratio, heading/FOV values, navigation links, duplicate GPS, and long connections.
   - Blocks publishing only on critical blockers.

3. Smart link
   - Suggests ordered two-way navigation links.
   - Computes distance and heading between adjacent scenes.
   - Lets the user apply recommended links.

4. Google account library
   - Loads photos from the connected Google Street View account.
   - Also loads Street View sequences where available.
   - Shows linked vs Google-only photos.
   - Can link, open, copy, or delete Google photos.

5. Background publishing
   - Adds Celery task `app_streetview.publish_source_tour_job`.
   - Endpoint: `POST /apis/streetview/source/tours/<tour_id>/publish/background/`.
   - Poll endpoint: `GET /apis/streetview/source/publish-jobs/<job_public_id>/`.

6. Analytics + history
   - Stores quality checks, smart links, scene edits, publish lifecycle, and other key events.

## Install

```bash
unzip apps_app_streetview_advanced_final.zip -d .
python manage.py migrate app_streetview
python manage.py check
python manage.py runserver 8000
```

In production:

```bash
python manage.py collectstatic --noinput
```

Run workers if not already running:

```bash
celery -A config worker -l info
```

## New migrations

- `0003_advanced_streetview_studio.py`

This migration only creates new advanced studio tables. It does not rename indexes.

## Celery optional publish runner

The advanced publisher now works in three modes:

- `local_thread` (default): starts a small local Django background thread and keeps the UI polling `/source/publish-jobs/<public_id>/`. This works without Celery.
- `celery`: set `STREETVIEW_PUBLISH_USE_CELERY = True` in Django settings to send jobs to Celery workers.
- `sync`: available for debugging; the request waits until publishing finishes.

Frontend progress labels now show:

```text
Uploading 4 / 20
Creating Google photos 7 / 20
Waiting for indexing
Updating connections
Done
```

For production with many images, Celery is still recommended. For local tests or small deployments, the local-thread fallback keeps the publisher usable even when Celery or the broker is not running.
