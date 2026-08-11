"""add immutable library retrieval audit runs"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_library_retrieval_runs"
down_revision: str | None = "0005_library_embedding_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_retrieval_run_guards() -> None:
    op.execute("""
        CREATE FUNCTION validate_retrieval_run()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            source_run embedding_run%ROWTYPE;
            candidate jsonb;
            selected_citation text;
        BEGIN
            IF NEW.embedding_run_id IS NOT NULL THEN
                SELECT * INTO source_run
                FROM embedding_run WHERE id = NEW.embedding_run_id;
                IF NOT FOUND
                   OR source_run.status <> 'succeeded'
                   OR source_run.corpus_snapshot_id <> NEW.corpus_snapshot_id THEN
                    RAISE EXCEPTION 'retrieval run embedding lineage is invalid'
                        USING ERRCODE = '23514';
                END IF;
            END IF;
            IF NEW.mode = 'hybrid' AND NEW.embedding_run_id IS NULL THEN
                RAISE EXCEPTION 'hybrid retrieval run requires embedding lineage'
                    USING ERRCODE = '23514';
            END IF;
            IF EXISTS (
                SELECT 1 FROM jsonb_object_keys(NEW.resolved_scope) AS item(key)
                WHERE item.key NOT IN (
                    'campaign_id', 'corpus', 'corpus_snapshot_id',
                    'authority_classes', 'visible_policies', 'rulesets',
                    'include_preparation', 'limit', 'snippet_chars'
                )
            ) THEN
                RAISE EXCEPTION 'retrieval scope contains forbidden audit data'
                    USING ERRCODE = '23514';
            END IF;
            IF EXISTS (
                SELECT 1 FROM jsonb_object_keys(NEW.retrieval_versions) AS item(key)
                WHERE item.key NOT IN ('lexical', 'vector', 'fusion')
            ) OR NEW.retrieval_versions = '{}'::jsonb THEN
                RAISE EXCEPTION 'retrieval versions are invalid'
                    USING ERRCODE = '23514';
            END IF;
            FOR candidate IN SELECT value FROM jsonb_array_elements(NEW.candidates)
            LOOP
                IF jsonb_typeof(candidate) <> 'object'
                   OR candidate ?| ARRAY['snippet', 'content', 'query', 'embedding', 'vector']
                   OR EXISTS (
                       SELECT 1 FROM jsonb_object_keys(candidate) AS item(key)
                       WHERE item.key NOT IN ('citation_id', 'score', 'lexical_rank', 'vector_rank')
                   )
                   OR NOT (candidate ? 'citation_id' AND candidate ? 'score')
                   OR candidate->>'citation_id' !~ '^chunk:[0-9a-f-]{36}$'
                   OR jsonb_typeof(candidate->'score') <> 'number'
                   OR (candidate ? 'lexical_rank'
                       AND jsonb_typeof(candidate->'lexical_rank') NOT IN ('number', 'null'))
                   OR (candidate ? 'vector_rank'
                       AND jsonb_typeof(candidate->'vector_rank') NOT IN ('number', 'null')) THEN
                    RAISE EXCEPTION 'retrieval candidate record is invalid'
                        USING ERRCODE = '23514';
                END IF;
            END LOOP;
            FOR selected_citation IN
                SELECT value #>> '{}' FROM jsonb_array_elements(NEW.selected_citation_ids)
            LOOP
                IF selected_citation !~ '^chunk:[0-9a-f-]{36}$'
                   OR NOT EXISTS (
                       SELECT 1 FROM jsonb_array_elements(NEW.candidates) AS candidate(value)
                       WHERE candidate.value->>'citation_id' = selected_citation
                   ) THEN
                    RAISE EXCEPTION 'retrieval selection is not a candidate citation'
                        USING ERRCODE = '23514';
                END IF;
            END LOOP;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_retrieval_run_validate
        BEFORE INSERT ON retrieval_run
        FOR EACH ROW EXECUTE FUNCTION validate_retrieval_run()
    """)
    op.execute("""
        CREATE FUNCTION reject_retrieval_run_change()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'retrieval runs are immutable'
                USING ERRCODE = '55000';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_retrieval_run_immutable
        BEFORE UPDATE OR DELETE ON retrieval_run
        FOR EACH ROW EXECUTE FUNCTION reject_retrieval_run_change()
    """)


def _drop_retrieval_run_guards() -> None:
    op.execute("DROP TRIGGER trg_retrieval_run_immutable ON retrieval_run")
    op.execute("DROP FUNCTION reject_retrieval_run_change()")
    op.execute("DROP TRIGGER trg_retrieval_run_validate ON retrieval_run")
    op.execute("DROP FUNCTION validate_retrieval_run()")


def upgrade() -> None:
    op.create_table(
        "retrieval_run",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("corpus_snapshot_id", sa.UUID(), nullable=False),
        sa.Column("embedding_run_id", sa.UUID(), nullable=True),
        sa.Column("mode", sa.String(length=24), nullable=False),
        sa.Column("query_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "retrieval_versions", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "resolved_scope", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("candidates", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "selected_citation_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("duration_milliseconds", sa.Float(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "duration_milliseconds >= 0",
            name=op.f("ck_retrieval_run_duration_milliseconds_nonnegative"),
        ),
        sa.CheckConstraint(
            "mode IN ('hybrid','lexical_fallback')",
            name=op.f("ck_retrieval_run_mode_allowed"),
        ),
        sa.CheckConstraint(
            "query_sha256 ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_retrieval_run_query_hash_valid"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(resolved_scope) = 'object' AND "
            "jsonb_typeof(retrieval_versions) = 'object' AND "
            "jsonb_typeof(candidates) = 'array' AND "
            "jsonb_typeof(selected_citation_ids) = 'array'",
            name=op.f("ck_retrieval_run_audit_json_shapes"),
        ),
        sa.ForeignKeyConstraint(
            ["corpus_snapshot_id"],
            ["corpus_snapshot.id"],
            name=op.f("fk_retrieval_run_corpus_snapshot_id_corpus_snapshot"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["embedding_run_id"],
            ["embedding_run.id"],
            name=op.f("fk_retrieval_run_embedding_run_id_embedding_run"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_retrieval_run")),
    )
    op.create_index(
        op.f("ix_retrieval_run_snapshot_created"),
        "retrieval_run",
        ["corpus_snapshot_id", "created_at"],
        unique=False,
    )
    _create_retrieval_run_guards()


def downgrade() -> None:
    _drop_retrieval_run_guards()
    op.drop_index(
        op.f("ix_retrieval_run_snapshot_created"), table_name="retrieval_run"
    )
    op.drop_table("retrieval_run")