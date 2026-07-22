-- Runs only when PostgreSQL initializes a new data directory.
-- db_vector_init also runs for already-existing production volumes.
CREATE EXTENSION IF NOT EXISTS vector;
