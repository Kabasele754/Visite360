# Déploiement Enterprise

## 1. Variables et secrets

Copier `.env.example` vers `.env`, puis créer les secrets Docker :

```bash
./scripts/bootstrap_secrets.sh
```

Fichiers attendus :

```text
secrets/db_password.txt
secrets/pgadmin_password.txt
secrets/google_adc.json
```

Ne jamais versionner de véritables identifiants.

## 2. Base PostgreSQL/pgvector

Le service `db` utilise `pgvector/pgvector:pg16`. La migration `knowledge.0002_enable_pgvector` crée l’extension `vector` quand le moteur est PostgreSQL.

La dimension livrée est `1536`. Une modification de `AI_EMBEDDING_DIMENSIONS` nécessite une migration de schéma et une réindexation complète des chunks.

## 3. Construire et lancer

```bash
docker compose build
docker compose run --rm django python manage.py migrate
docker compose run --rm django python manage.py collectstatic --noinput
docker compose up -d
```

## 4. Modèles Vision

YOLO :

```bash
docker compose run --rm ai_model_init
```

Florence-2 et PaddleOCR :

```bash
INSTALL_FULL_AI=true docker compose build ai_worker
```

Installer en plus une distribution PaddlePaddle correspondant au matériel cible, puis activer les flags dans `.env`.

## 5. Nginx et TLS

`nginx/conf.d/default.conf` démarre en HTTP et permet le challenge ACME. Après émission des certificats :

1. vérifier les domaines et l’adresse email dans `docker-compose.yml` ;
2. exécuter `docker compose run --rm certbot` ;
3. activer le contenu de `nginx/conf.d/https.conf.example` comme configuration HTTPS ;
4. reconstruire/redémarrer Nginx.

## 6. Vérifications de production

```bash
python manage.py check --deploy --settings=config.settings.prod
python manage.py check_enterprise_ai
python manage.py provision_enterprise_agents <organization-slug>
```

Endpoints :

```text
GET  /health/
GET  /api/schema/
GET  /api/docs/
GET  /dashboard/enterprise-ai/
POST /api/enterprise/monitoring/health/run/
```

## 7. Sauvegardes

Sauvegarder au minimum :

- volume PostgreSQL `dev-db-data` ;
- volume média `media-data` ;
- secrets externes ;
- configuration `.env` ;
- éventuels poids de modèles personnalisés.

Les caches Hugging Face et PaddleOCR peuvent être reconstruits.

## 8. Montée en charge

- Augmenter les workers Web/Daphne horizontalement derrière Nginx.
- Séparer le worker IA sur une machine GPU.
- Conserver Redis et PostgreSQL comme services partagés.
- Ajuster `AI_WORKER_CONCURRENCY` avec prudence pour les modèles lourds.
- Placer les médias sur un stockage objet/CDN en production à grande échelle.
