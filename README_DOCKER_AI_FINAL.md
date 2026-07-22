# Twinscopes — Docker AI Production Final

This package keeps the existing named volumes unchanged:

- `dev-db-data` — PostgreSQL
- `media-data` — uploaded panoramas and media
- `static-data`
- `redis-data`
- `pgadmin-data`
- `ai-models`

## Never run

```bash
docker compose down -v
docker volume prune
docker system prune --volumes
```

## Safe deployment

Keep the current `.env`, `secrets/`, `certbot/`, and Docker volumes. Then run:

```bash
docker compose config -q
docker compose build django celery_worker ai_worker celery_beat
docker compose --profile tools run --rm ai_model_init
docker compose up -d
```

No `down -v` is required.

## Verify startup

```bash
docker compose ps
docker compose logs --tail=200 django
docker compose logs --tail=200 ai_worker
docker compose exec django python manage.py check
docker compose exec nginx nginx -t
```

## Verify the AI worker

```bash
docker compose exec ai_worker python -c "
import torch, cv2, ultralytics, paddle
from paddleocr import PaddleOCR
print('torch=', torch.__version__)
print('opencv=', cv2.__version__)
print('ultralytics=', ultralytics.__version__)
print('paddle=', paddle.__version__)
print('PaddleOCR import OK')
"

docker compose exec ai_worker python manage.py check_ai_stack
```

## Initial TLS certificate

Nginx starts in HTTP bootstrap mode when no certificate exists.

```bash
docker compose --profile tools run --rm certbot
docker compose restart nginx
```

After the certificate exists, Nginx automatically enables HTTPS on restart.

## Analyze existing scenes

```bash
docker compose exec django python manage.py analyze_existing_scenes --status-only

docker compose exec django python manage.py analyze_existing_scenes \
  --mode celery \
  --providers yolo,paddleocr,gemini,openai
```

Use `--force` only when you intentionally want to regenerate all analyses.

## Back up the database before a major deployment

```bash
mkdir -p backups

docker exec visite360_postgres_db sh -lc '
export PGPASSWORD="$(cat /run/secrets/db_password)"
pg_dump -h 127.0.0.1 -U elevateaiuser -d elevateaidb \
  --format=custom --no-owner --no-privileges
' > "backups/elevateaidb_$(date +%Y-%m-%d_%H-%M-%S).dump"
```

Confirm the resulting file is not empty before continuing.
