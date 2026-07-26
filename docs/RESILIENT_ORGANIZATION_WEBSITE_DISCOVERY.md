# Resilient Organization Website Discovery

This patch prevents Organization Intelligence from stopping when the configured website URL points to an unavailable page.

## Recovery sequence

When the saved URL returns a 404, 410, timeout, unsupported content type or another page-level error, Twinscopes continues with:

1. the official site root;
2. the www/apex-domain alternative;
3. the configured URL;
4. common organization pages such as About, Services, Departments, Doctors, Booking and Contact;
5. same-domain URLs discovered in the sitemap;
6. useful links discovered from successfully loaded pages.

A single broken page is skipped and recorded in crawl diagnostics. It does not fail the entire collection.

## Security retained

The crawler still:

- allows only absolute HTTP(S) URLs;
- rejects localhost, private, loopback, link-local and reserved addresses;
- validates every redirect target;
- stays on the same official site, while accepting www/apex variants;
- respects robots.txt when available;
- ignores binary downloads and non-HTML resources;
- strips tracking parameters and URL fragments;
- limits the number of page requests.

## New configuration

```env
KNOWLEDGE_CRAWLER_MAX_ATTEMPTS=75
```

This limits total URL attempts independently of the number of successfully collected pages.

## Dashboard behavior

A recovered run shows a readable notice such as:

- `Website URL recovered`
- `Unavailable pages skipped`

The dashboard no longer exposes a raw Python `HTTPError` to administrators. If the configured URL is broken but another official page works, a review suggestion is created so the saved `website_url` can be corrected safely.

## Deployment

No database migration is required.

```bash
python manage.py check
python manage.py test tests.test_resilient_organization_crawler
```

For Docker production:

```bash
docker compose build django celery_worker ai_worker
docker compose up -d django celery_worker ai_worker
docker compose exec django python manage.py collectstatic --noinput
```
