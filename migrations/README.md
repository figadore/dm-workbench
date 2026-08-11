# Database migrations

Alembic reads the PostgreSQL URL only from validated `DM_DATABASE_URL` settings (or an ignored `.env`); `alembic.ini` contains no credential or fallback URL.

```bash
uv run --frozen alembic upgrade head
uv run --frozen alembic downgrade base
uv run --frozen alembic upgrade head
```

The foundation migration installs pgvector and creates only `campaign`. P7-01 adds preparation artifacts/versions, generation runs, generic generated assets, role links, lifecycle audit, and immutability triggers. P1-01 adds logical Library documents/path history, exact immutable revisions/chunks, lexical vectors, ingestion runs, and scope-safe corpus snapshots in `0003_library_sources`. Alembic's own `alembic_version` table is the schema-version record; a second application schema-version table would duplicate that authority.
