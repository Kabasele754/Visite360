# Validation Report — Home Search V2 and Platform Control Center

Validated in the artifact environment:

- Python syntax compilation for all new and modified Python modules.
- JavaScript syntax for dynamic discovery and dashboard charts.
- Django template block/tag balance for all new templates.
- Resource form-field names against the project model definitions.
- Home template references the V2 discovery CSS and JavaScript.
- Platform Console app is registered in `INSTALLED_APPS` and root URLs.
- No embedded OpenAI or Google API keys detected by pattern scan.
- New public UI strings are English.

Not executed in the artifact environment:

- Django system checks.
- Database-backed view tests.
- Docker image build.
- Browser rendering against production data.

Run after deployment:

```bash
docker compose exec django python manage.py check
docker compose exec django python manage.py collectstatic --noinput
docker compose exec nginx nginx -t
```
