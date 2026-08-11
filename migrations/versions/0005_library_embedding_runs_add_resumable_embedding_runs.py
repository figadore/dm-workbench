"""add resumable library embedding runs"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_library_embedding_runs"
down_revision: str | None = "0004_library_embeddings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_embedding_run_guards() -> None:
    op.execute("""
        CREATE FUNCTION validate_embedding_run()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            profile embedding_profile%ROWTYPE;
        BEGIN
            SELECT * INTO profile
            FROM embedding_profile WHERE id = NEW.embedding_profile_id;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'embedding run references unknown profile'
                    USING ERRCODE = '23503';
            END IF;
            IF ROW(NEW.runtime_kind, NEW.provider, NEW.model_revision, NEW.dimensions)
               IS DISTINCT FROM ROW(
                    profile.runtime_kind, profile.provider,
                    profile.model_revision, profile.dimensions
               ) THEN
                RAISE EXCEPTION 'embedding run metadata does not match profile'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_embedding_run_validate
        BEFORE INSERT ON embedding_run
        FOR EACH ROW EXECUTE FUNCTION validate_embedding_run()
    """)
    op.execute("""
        CREATE FUNCTION validate_embedding_run_item()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            target_run embedding_run%ROWTYPE;
            source_embedding document_chunk_embedding%ROWTYPE;
        BEGIN
            SELECT * INTO target_run
            FROM embedding_run WHERE id = NEW.embedding_run_id;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'embedding run item references unknown run'
                    USING ERRCODE = '23503';
            END IF;
            IF NOT EXISTS (
                SELECT 1
                FROM corpus_snapshot_document membership
                JOIN document_chunk chunk
                  ON chunk.document_revision_id = membership.document_revision_id
                WHERE membership.corpus_snapshot_id = target_run.corpus_snapshot_id
                  AND chunk.id = NEW.document_chunk_id
                  AND chunk.content_hash = NEW.chunk_content_hash
            ) THEN
                RAISE EXCEPTION 'embedding run item is not an exact snapshot chunk'
                    USING ERRCODE = '23514';
            END IF;
            IF NEW.document_chunk_embedding_id IS NOT NULL THEN
                SELECT * INTO source_embedding
                FROM document_chunk_embedding
                WHERE id = NEW.document_chunk_embedding_id;
                IF NOT FOUND
                   OR source_embedding.document_chunk_id <> NEW.document_chunk_id
                   OR source_embedding.embedding_profile_id
                      <> target_run.embedding_profile_id
                   OR source_embedding.chunk_content_hash <> NEW.chunk_content_hash THEN
                    RAISE EXCEPTION 'embedding run item derivation does not match run'
                        USING ERRCODE = '23514';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_embedding_run_item_validate
        BEFORE INSERT OR UPDATE ON embedding_run_item
        FOR EACH ROW EXECUTE FUNCTION validate_embedding_run_item()
    """)
    op.execute("""
        CREATE FUNCTION enforce_embedding_run_lifecycle()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'embedding runs cannot be deleted'
                    USING ERRCODE = '55000';
            END IF;
            IF TG_OP = 'INSERT' THEN
                IF NEW.status <> 'running' THEN
                    RAISE EXCEPTION 'new embedding runs must start running'
                        USING ERRCODE = '23514';
                END IF;
                RETURN NEW;
            END IF;
            IF ROW(
                NEW.id, NEW.corpus_snapshot_id, NEW.embedding_profile_id,
                NEW.runtime_kind, NEW.provider, NEW.model_revision,
                NEW.dimensions, NEW.batch_size, NEW.max_attempts, NEW.started_at
            ) IS DISTINCT FROM ROW(
                OLD.id, OLD.corpus_snapshot_id, OLD.embedding_profile_id,
                OLD.runtime_kind, OLD.provider, OLD.model_revision,
                OLD.dimensions, OLD.batch_size, OLD.max_attempts, OLD.started_at
            ) THEN
                RAISE EXCEPTION 'embedding run pins are immutable'
                    USING ERRCODE = '55000';
            END IF;
            IF OLD.status = 'running'
               AND NEW.status IN ('succeeded', 'failed', 'cancelled') THEN
                IF NEW.status = 'succeeded' AND EXISTS (
                    SELECT 1 FROM embedding_run_item
                    WHERE embedding_run_id = NEW.id
                      AND status NOT IN ('succeeded', 'skipped')
                ) THEN
                    RAISE EXCEPTION 'embedding run has unfinished items'
                        USING ERRCODE = '23514';
                END IF;
                IF NEW.status = 'succeeded' AND EXISTS (
                    SELECT 1
                    FROM corpus_snapshot_document membership
                    JOIN document_chunk chunk
                      ON chunk.document_revision_id = membership.document_revision_id
                    WHERE membership.corpus_snapshot_id = NEW.corpus_snapshot_id
                      AND NOT EXISTS (
                          SELECT 1 FROM embedding_run_item item
                          WHERE item.embedding_run_id = NEW.id
                            AND item.document_chunk_id = chunk.id
                            AND item.chunk_content_hash = chunk.content_hash
                            AND item.status IN ('succeeded', 'skipped')
                      )
                ) THEN
                    RAISE EXCEPTION 'embedding run has incomplete snapshot coverage'
                        USING ERRCODE = '23514';
                END IF;
                RETURN NEW;
            END IF;
            IF OLD.status = 'running' AND NEW.status = 'running' THEN
                RETURN NEW;
            END IF;
            IF OLD.status IN ('failed', 'cancelled')
               AND NEW.status = 'running' AND NEW.finished_at IS NULL THEN
                RETURN NEW;
            END IF;
            RAISE EXCEPTION 'invalid embedding run lifecycle transition'
                USING ERRCODE = '55000';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_embedding_run_lifecycle
        BEFORE INSERT OR UPDATE OR DELETE ON embedding_run
        FOR EACH ROW EXECUTE FUNCTION enforce_embedding_run_lifecycle()
    """)


def _drop_embedding_run_guards() -> None:
    op.execute("DROP TRIGGER trg_embedding_run_lifecycle ON embedding_run")
    op.execute("DROP FUNCTION enforce_embedding_run_lifecycle()")
    op.execute("DROP TRIGGER trg_embedding_run_item_validate ON embedding_run_item")
    op.execute("DROP FUNCTION validate_embedding_run_item()")
    op.execute("DROP TRIGGER trg_embedding_run_validate ON embedding_run")
    op.execute("DROP FUNCTION validate_embedding_run()")


def upgrade() -> None:
    op.create_table(
        "embedding_run",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("corpus_snapshot_id", sa.UUID(), nullable=False),
        sa.Column("embedding_profile_id", sa.UUID(), nullable=False),
        sa.Column("runtime_kind", sa.String(length=20), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("model_revision", sa.String(length=200), nullable=False),
        sa.Column("dimensions", sa.SmallInteger(), nullable=False),
        sa.Column("batch_size", sa.SmallInteger(), nullable=False),
        sa.Column("max_attempts", sa.SmallInteger(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column(
            "resource_observations",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "usage_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "batch_size > 0", name=op.f("ck_embedding_run_batch_size_positive")
        ),
        sa.CheckConstraint(
            "dimensions > 0", name=op.f("ck_embedding_run_dimensions_positive")
        ),
        sa.CheckConstraint(
            "finished_at IS NULL OR finished_at >= started_at",
            name=op.f("ck_embedding_run_finished_after_started"),
        ),
        sa.CheckConstraint(
            "max_attempts > 0", name=op.f("ck_embedding_run_max_attempts_positive")
        ),
        sa.CheckConstraint(
            "jsonb_typeof(resource_observations) = 'object' AND "
            "jsonb_typeof(usage_metadata) = 'object'",
            name=op.f("ck_embedding_run_observations_and_usage_objects"),
        ),
        sa.CheckConstraint(
            "status IN ('running','succeeded','failed','cancelled')",
            name=op.f("ck_embedding_run_status_allowed"),
        ),
        sa.CheckConstraint(
            "(status = 'running' AND finished_at IS NULL) OR "
            "(status IN ('succeeded','failed','cancelled') AND "
            "finished_at IS NOT NULL)",
            name=op.f("ck_embedding_run_status_finished_consistent"),
        ),
        sa.ForeignKeyConstraint(
            ["corpus_snapshot_id"],
            ["corpus_snapshot.id"],
            name=op.f("fk_embedding_run_corpus_snapshot_id_corpus_snapshot"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["embedding_profile_id"],
            ["embedding_profile.id"],
            name=op.f("fk_embedding_run_embedding_profile_id_embedding_profile"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_embedding_run")),
    )
    op.create_index(
        op.f("ix_embedding_run_snapshot_profile_status"),
        "embedding_run",
        ["corpus_snapshot_id", "embedding_profile_id", "status"],
        unique=False,
    )
    op.create_table(
        "embedding_run_item",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("embedding_run_id", sa.UUID(), nullable=False),
        sa.Column("document_chunk_id", sa.UUID(), nullable=False),
        sa.Column("chunk_content_hash", sa.String(length=64), nullable=False),
        sa.Column("document_chunk_embedding_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("attempt_count", sa.SmallInteger(), nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "attempt_count >= 0",
            name=op.f("ck_embedding_run_item_attempt_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "chunk_content_hash ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_embedding_run_item_chunk_content_hash_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('pending','processing','succeeded','skipped',"
            "'retryable_failed','failed','cancelled')",
            name=op.f("ck_embedding_run_item_status_allowed"),
        ),
        sa.CheckConstraint(
            "(status IN ('succeeded','skipped') AND "
            "document_chunk_embedding_id IS NOT NULL) OR "
            "(status NOT IN ('succeeded','skipped') AND "
            "document_chunk_embedding_id IS NULL)",
            name=op.f("ck_embedding_run_item_terminal_derivation_consistent"),
        ),
        sa.ForeignKeyConstraint(
            ["document_chunk_embedding_id"],
            ["document_chunk_embedding.id"],
            name=op.f("fk_embedding_run_item_document_chunk_embedding_id_document_chunk_embedding"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_chunk_id"],
            ["document_chunk.id"],
            name=op.f("fk_embedding_run_item_document_chunk_id_document_chunk"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["embedding_run_id"],
            ["embedding_run.id"],
            name=op.f("fk_embedding_run_item_embedding_run_id_embedding_run"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_embedding_run_item")),
        sa.UniqueConstraint(
            "embedding_run_id",
            "document_chunk_id",
            "chunk_content_hash",
            name=op.f("uq_embedding_run_item_derivation"),
        ),
    )
    op.create_index(
        op.f("ix_embedding_run_item_run_status"),
        "embedding_run_item",
        ["embedding_run_id", "status"],
        unique=False,
    )
    _create_embedding_run_guards()


def downgrade() -> None:
    _drop_embedding_run_guards()
    op.drop_index(
        op.f("ix_embedding_run_item_run_status"), table_name="embedding_run_item"
    )
    op.drop_table("embedding_run_item")
    op.drop_index(
        op.f("ix_embedding_run_snapshot_profile_status"), table_name="embedding_run"
    )
    op.drop_table("embedding_run")