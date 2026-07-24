# Advanced Platform Change Manifest

## Nouveau module

`apps/domain_intelligence/` fournit les modèles, l’admin, les migrations, la recherche, le parsing d’intention, la synchronisation hospitalière officielle, les tâches Celery et les commandes de gestion.

## Modifications principales

- `apps/tours/dashboard_views.py` : endpoint PDF HTTP Range et payload PDF same-origin.
- `apps/tours/dashboard_urls.py` : route publique sécurisée pour les documents PDF.
- `static/dashboard/js/preview-tailwind.js` : PDF mobile progressif et sélecteur visuel exact.
- `static/dashboard/css/preview-tailwind.css` : interface de sélection et lecteur mobile.
- `apps/vision_ai/services/panorama.py` : correction du signe de pitch Marzipano.
- `apps/vision_ai/services/point_inspection.py` : scan ciblé et refus des zones non vérifiées.
- `apps/tour_ai_agent/views.py` : validation obligatoire de la sélection et réponses publiques sûres.
- `apps/tours/forms.py` et formulaire Studio : profils immobilier, hôtel et santé.
- `apps/vendors/models.py` : contexte docteur/spécialité/mode pour les rendez-vous.
- `apps/integrations/services/google_calendar.py` : contexte médical administratif dans l’événement.
- `templates/public/home.html` : Smart Discovery sur la Home.
- `docker-compose.yml`, Nginx et settings : variables, MIME `.mjs`, Range et headers mobiles.

## Migrations

- `domain_intelligence.0001_initial`
- `vendors.0007_appointmentrequest_healthcare_context`

## Commandes nouvelles

```bash
python manage.py bootstrap_domain_profiles
python manage.py sync_domain_intelligence --organization SLUG --mode celery --max-pages 30
```
