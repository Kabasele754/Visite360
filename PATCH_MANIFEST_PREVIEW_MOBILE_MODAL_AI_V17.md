# Preview Mobile Modal + AI Nudge V17

## Fixed

- The Tour Information modal now resets the inherited desktop `left: 50%` rule on mobile.
- The mobile sheet is pinned to `left: 0; right: 0; bottom: 0` and uses the dynamic viewport height.
- Header, description, facts, and footer cannot overflow horizontally.
- Safe-area spacing is respected on iOS and Android.
- Short landscape screens use a compact layout.
- The `Need help exploring this space?` prompt now has a real responsive width.
- The AI prompt text wraps naturally inside the bubble instead of one word per line.
- The close action has its own fixed-width column.
- The AI nudge automatically retracts while the Tour Information modal is open.
- Static asset cache versions were bumped to `preview-mobile-modal-ai-17`.

## Deployment

```bash
docker compose build django
docker compose up -d django
docker compose exec django python manage.py collectstatic --noinput
docker compose restart nginx
```

No database migration is required.
