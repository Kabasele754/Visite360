# Deployment — Preview Intelligence & SEO V14

## Environment

Add or confirm:

```env
VISION_POINT_AUTO_RESCAN=true
VISION_POINT_AUTO_RESCAN_CONFIDENCE_RELAXATION=0.05
VISION_POINT_OCR_FALLBACK_MIN_CONFIDENCE=0.82
```

For the current provider availability, OpenAI can remain the primary semantic provider and Gemini the fallback:

```env
VISION_PRIMARY_SEMANTIC_PROVIDER=openai
VISION_FALLBACK_SEMANTIC_PROVIDER=gemini
```

## Safe deployment

```bash
cd /root/Visite360
cp .env ".env.backup_$(date +%Y%m%d_%H%M%S)"
docker compose config -q
docker compose build django ai_worker nginx
docker compose up -d django ai_worker nginx
docker compose exec django python manage.py collectstatic --noinput
docker compose exec django python manage.py check
docker compose exec nginx nginx -t
docker compose ps
```

Do not remove Docker volumes. The patch requires no database migration.

## Preview verification

1. Hard-refresh the preview page.
2. Long-press an object near the lower part of the viewport.
3. Confirm the normal dock disappears while framing.
4. Move and resize the frame; ensure it never passes behind the action bar.
5. Select a package or sign that YOLO does not commonly recognize.
6. Confirm the server automatically performs the enhanced second pass.
7. If recognition remains uncertain, confirm `Scan again` reopens the exact selector at the previous position.

## SEO verification

```bash
curl -s https://twinscopes.com/ORGANIZATION/tours/TOUR_ID/preview/ \
  | grep -E 'canonical|og:title|twitter:card|application/ld\\+json|<h1'

curl -s https://twinscopes.com/sitemap-tours.xml | head -80
```

Validate a public URL with Google Rich Results Test and Search Console URL Inspection after deployment.
