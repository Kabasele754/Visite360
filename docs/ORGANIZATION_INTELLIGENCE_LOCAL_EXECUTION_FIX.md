# Organization Intelligence — local execution fix

## Why the run stayed queued

The dashboard successfully created an `OrganizationIntelligenceRun` and polled its status endpoint, but the task was routed to the Celery `ai` queue. When only Django `runserver` was running locally, no worker consumed that queue, so the run remained `queued` indefinitely.

## New behavior

- Development defaults to `DOMAIN_INTELLIGENCE_EXECUTION_MODE=thread`.
- Production defaults to `DOMAIN_INTELLIGENCE_EXECUTION_MODE=celery`.
- The local thread closes and reopens Django database connections safely.
- The run page reports a stalled queue and provides a **Retry collection** button.
- The management command accepts `--mode auto|thread|sync|celery`.

## Local configuration

```env
DJANGO_SETTINGS_MODULE=config.settings.dev
DOMAIN_INTELLIGENCE_EXECUTION_MODE=thread
DOMAIN_INTELLIGENCE_LOCAL_THREAD_WORKERS=1
DOMAIN_INTELLIGENCE_STALE_QUEUE_SECONDS=20
```

Start Django normally:

```bash
python manage.py runserver
```

No Redis or Celery worker is required for Organization Intelligence in this local mode.

## Optional local Celery mode

```env
DOMAIN_INTELLIGENCE_EXECUTION_MODE=celery
CELERY_BROKER_URL=redis://127.0.0.1:6379/0
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/0
```

Then run:

```bash
redis-server
celery -A config worker -l info -Q ai,celery --pool=solo
python manage.py runserver
```

## Direct command tests

Local background thread:

```bash
python manage.py sync_domain_intelligence \
  --organization ORGANIZATION_SLUG \
  --mode thread \
  --max-pages 5
```

Synchronous diagnostic:

```bash
python manage.py sync_domain_intelligence \
  --organization ORGANIZATION_SLUG \
  --mode sync \
  --max-pages 3
```

Production Celery:

```bash
python manage.py sync_domain_intelligence \
  --organization ORGANIZATION_SLUG \
  --mode celery \
  --max-pages 25
```
