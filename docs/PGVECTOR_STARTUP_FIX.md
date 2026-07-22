# pgvector startup fix

The `knowledge.0001_initial` migration creates a `vector(1536)` column.
PostgreSQL must have the `vector` extension enabled before that table is created.

This package enables it in three idempotent layers:

1. `docker-entrypoint-initdb.d` for a brand-new database volume.
2. `db_vector_init` for existing Docker volumes before Django starts.
3. The first operation of `knowledge.0001_initial` as a migration safety net.

## Recover an already-running deployment

```bash
docker exec -it visite360_postgres_db \
  psql -U elevateaiuser -d elevateaidb \
  -c "CREATE EXTENSION IF NOT EXISTS vector;"

docker exec -it visite360_postgres_db \
  psql -U elevateaiuser -d elevateaidb \
  -c "SELECT extname, extversion FROM pg_extension WHERE extname='vector';"

docker compose up -d --force-recreate db_vector_init
docker compose up -d django
docker compose up -d celery_worker ai_worker
```

Do not delete the PostgreSQL volume. The failed Django migration is transactional and can be safely retried after enabling the extension.
