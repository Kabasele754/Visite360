# Rapport d’implémentation — Twinscopes AI Enterprise

## Objectif

Transformer l’archive Twinscopes existante en une base Enterprise extensible, sans casser les applications déjà présentes et sans dupliquer les fonctionnalités métier existantes.

## Applications ajoutées

```text
apps/ai_core
apps/knowledge
apps/vision_ai
apps/ai_agents
apps/ai_chat
apps/integrations
apps/monitoring
```

## Infrastructure ajoutée ou complétée

```text
manage.py
.env.example
nginx/
scripts/bootstrap_secrets.sh
secrets/README.md
requirements-ai-full.txt
```

`docker-compose.yml` utilise désormais PostgreSQL avec pgvector et contient un worker Celery réservé à l’IA.

## Robustesse

- Providers IA isolés derrière une interface commune.
- Échec d’un moteur Vision non bloquant pour les autres moteurs.
- Embeddings déterministes uniquement autorisés en développement ou par configuration explicite.
- Crawler protégé contre les hôtes internes et redirections dangereuses.
- Credentials d’intégration chiffrés au repos.
- Isolation multi-organisation dans les querysets et relations API.
- Citations et liens externes contrôlés dans le chat.
- Request ID et temps serveur ajoutés aux réponses.

## Validation exécutée

- `python manage.py check`
- migrations complètes sur une base SQLite propre
- compilation Python de `apps`, `config` et `manage.py`
- tests unitaires des nouveaux modules
- validation syntaxique Docker Compose

## Étapes de mise en production

1. Renseigner `.env` et les secrets.
2. Utiliser PostgreSQL/pgvector, jamais SQLite en production.
3. Configurer les credentials Gemini/Vertex AI ou OpenAI.
4. Installer/activer les moteurs Vision réellement utilisés.
5. Exécuter les migrations.
6. Provisionner les agents par organisation.
7. Indexer les sources de connaissances.
8. Configurer Google Calendar pour les organisations concernées.
9. Activer HTTPS après émission Certbot.
10. Exécuter les checks de déploiement et les sauvegardes.

## Final grounded AI enhancement

- OpenAI added to the legacy public 360 agent router as primary/fallback provider.
- “Powered by Gemini” removed from the visitor interface.
- Twelve-view panorama extraction for improved coverage.
- Richer object, OCR, accessibility, safety, material and layout evidence schema.
- Backfill command for all existing scenes.
- Automatic organization website RAG and social-link discovery.
- Organization website, booking, contact and social fields.
- Strict trusted-link and non-invention instructions.
- Duplicate question prevention using request idempotency.
- Dynamic guest appointment form and automatic Google Calendar synchronization.

## Advanced 360 Vision — long-press release

- Fixed Google Gen AI client lifecycle for text, vision and embeddings.
- Added automatic embedding fallback and provider failure cooldown.
- Assigned Gemini the primary semantic-fusion role after YOLO and PaddleOCR.
- Added OpenAI Vision frame-level fallback.
- Increased advanced panorama coverage to 12 perspective frames.
- Added OCR metadata and the `VisionInsight` interactive-region model.
- Added projection from frame pixels to Marzipano panorama yaw/pitch.
- Added signed object/text crops and public point-inspection endpoints.
- Added desktop/mobile long-press interaction and a polished visual insight sheet.
- Connected Enterprise vision results to scene-aware chat context.
- Corrected organization contact precedence and invalid citation placeholders.

## 2026-07-22 — Local/production scene scan hardening

- Fixed local `.env` OpenAI key loading being overwritten by an environment-only assignment.
- Added Vertex-safe Google embedding dimensionality handling and vector normalization.
- Skip unconfigured embedding providers instead of producing repeated cooldown failures.
- Repaired legacy `Scene360.ai_analysis_status` values with a data migration.
- Added idempotent scene analysis dispatch for local synchronous and production Celery modes.
- Added public on-demand scene analysis with automatic long-press polling.
- Expanded `analyze_existing_scenes` filters, status reporting and JSON reports.
- Expanded `check_ai_stack` with real embedding tests and full scene scans.
- Added annotated HTML/JSON vision reports.
- Added knowledge reindexing after embedding-provider changes.
- Added local non-Docker setup assets and documentation.

## Local + production scene scanning hardening

- Corrected Vertex/Gemini native embedding output dimensions and retained the existing pgvector storage width through normalized zero-padding.
- Corrected local and Docker-secret loading for `OPENAI_API_KEY`, including the later AI settings module that previously could overwrite it.
- Cloud vision providers are skipped when their credentials are absent, preventing repeated cooldown warnings.
- Added embedding provider/model provenance and same-space semantic search protection.
- Added non-blocking local background-thread scans for long-press requests without Docker/Celery.
- Added stale analysis recovery, local and production scan scripts, database scene inventory and live provider diagnostics.
- Added 24/32-view deep panorama coverage profiles and configurable YOLO model/image size.
- Added tests for Vertex dimensionality, vector normalization, provider credential filtering and 24-view panorama coverage.
