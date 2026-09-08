# Database Migrations

Alembic reads PostgreSQL only from validated `DM_DATABASE_URL` settings or the ignored local `.env`;
`alembic.ini` contains no credential or fallback URL. Alembic's `alembic_version` table is the sole
schema-version authority.

```bash
uv run --frozen alembic upgrade head
uv run --frozen alembic downgrade base
uv run --frozen alembic upgrade head
```

| Revision | Capability |
| --- | --- |
| `0001_foundation` | pgvector extension and campaign aggregate |
| `0002_preparation` | preparation artifacts/versions, generation runs, generated assets, role links, lifecycle audit, and immutability guards |
| `0003_library_sources` | logical documents/path history, immutable revisions/chunks, lexical vectors, ingestion runs, and corpus snapshots |
| `0004_library_embeddings` | versioned embedding profiles and derivations |
| `0005_library_embedding_runs` | resumable snapshot-pinned embedding runs |
| `0006_library_retrieval_runs` | immutable source-body-free retrieval audit runs |
| `0007_campaign_knowledge_entities` | campaign entities, aliases, mentions, and merge history foundation |
| `0008_workbench_defaults` | inspectable active campaign and task-specific Workbench defaults |

Migration tests may be destructive only against an explicitly configured database whose name ends in
`_test`. Never edit an applied/shared migration or put model calls in a migration.
