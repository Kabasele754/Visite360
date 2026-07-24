# Twinscopes Advanced Platform — Final Integration

Cette livraison transforme le projet en plateforme métier plus complète tout en conservant les tours, scènes, médias et volumes existants.

## Blocs livrés

- **PDF mobile Android/iOS** : diffusion same-origin avec HTTP Range, PDF.js progressif, pages paresseuses et lecteur natif de secours.
- **Healthcare Intelligence** : profils hôpitaux/cliniques, spécialités, docteurs, disponibilités, sources officielles vérifiées et prise de rendez-vous.
- **Smart Discovery Home** : recherche naturelle de maisons, appartements, hôtels, établissements de santé et spécialistes avec ouverture directe du tour 360.
- **Profils métiers dans le formulaire Tour** : détails immobiliers, hôteliers et hospitaliers enregistrables depuis le Studio.
- **Computer Vision précise** : sélection déplaçable/redimensionnable obligatoire avant scan, vérification locale + sémantique et correction du pitch vertical.
- **Sécurité production** : réponses publiques sans erreurs techniques, rate limiting, cache d’intention, contacts publics uniquement, `.gitignore` et `.dockerignore` sécurisés.

Guide complet : [`docs/ADVANCED_PDF_HEALTHCARE_DISCOVERY_VISION.md`](docs/ADVANCED_PDF_HEALTHCARE_DISCOVERY_VISION.md)

## Déploiement sûr

```bash
cd /root/Visite360
cp .env ".env.backup_$(date +%Y%m%d_%H%M%S)"

docker compose config -q
docker compose build django celery_worker ai_worker nginx
docker compose up -d django celery_worker ai_worker celery_beat nginx

docker compose exec django python manage.py migrate --noinput
docker compose exec django python manage.py collectstatic --noinput
docker compose exec django python manage.py check
docker compose exec nginx nginx -t
```

Initialiser les profils métier des lieux et tours déjà présents :

```bash
docker compose exec django \
python manage.py bootstrap_domain_profiles
```

Ne pas utiliser `docker compose down -v`, `docker volume prune` ou `docker system prune --volumes` pour cette mise à jour.
