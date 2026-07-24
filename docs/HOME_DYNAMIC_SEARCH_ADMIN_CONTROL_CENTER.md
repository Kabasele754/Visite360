# Dynamic Home Search and Platform Control Center

## Home search

The Home page now displays one compact search bar. Selecting the bar, pressing `Ctrl+K` / `Command+K`, or submitting a query opens a full-screen search workspace.

Key behavior:

- Dynamic search after a short typing pause.
- Direct matching against tour titles, places and organization names.
- Structured matching for homes, hotels, healthcare facilities, specialties and practitioners.
- Results appear immediately below the search field.
- Guest-facing text is English only.
- Live typing requests use a separate rate limit and are not saved as final discovery analytics.
- Explicit searches are saved for dashboard reporting, with healthcare query text redacted.

Relevant files:

- `templates/public/partials/discovery_agent.html`
- `static/public/css/discovery-agent-v2.css`
- `static/public/js/discovery-agent-v2.js`
- `apps/domain_intelligence/services/search.py`
- `apps/domain_intelligence/views.py`

## Platform Control Center

Staff users can open:

```text
/dashboard/control-center/
```

The custom dashboard is separate from Django Admin and provides:

- Platform metrics.
- Traffic and session charts.
- AI provider and run-status charts.
- Computer-vision status charts.
- Appointment status charts.
- Operational activity feeds.
- Searchable management tables.
- Create/edit/delete forms for operational configuration.
- Read-only details for AI runs, vision analyses, discovery logs and traffic events.

Managed areas include organizations, places, tours, AI domain profiles, healthcare facilities, specialties, practitioners, availability, property listings, hospitality profiles, appointments, knowledge sources and service offerings.

Relevant files:

- `apps/platform_console/`
- `templates/dashboard/platform_console/`
- `static/platform_console/`

## Deployment

No database migration is required for this update.

```bash
cd /root/Visite360
cp .env ".env.backup_$(date +%Y%m%d_%H%M%S)"

docker compose config -q
docker compose build django nginx
docker compose up -d django nginx
docker compose exec django python manage.py collectstatic --noinput
docker compose exec django python manage.py check
docker compose exec nginx nginx -t
```

Recommended environment value:

```env
PUBLIC_DISCOVERY_LIVE_RATE_LIMIT=120
```

Do not run commands that remove Docker volumes.
