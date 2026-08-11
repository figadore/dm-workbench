"""add library embedding profiles and exact chunk embeddings"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_library_embeddings"
down_revision: str | None = "0003_library_sources"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


class Vector(sa.types.UserDefinedType[object]):
    """Database-native pgvector type without a Python provider dependency."""

    cache_ok = True

    def get_col_spec(self, **kwargs: object) -> str:
        return "vector"


def _create_embedding_guards() -> None:
    op.execute("""
        CREATE FUNCTION validate_document_chunk_embedding()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            source_chunk document_chunk%ROWTYPE;
            profile embedding_profile%ROWTYPE;
        BEGIN
            SELECT * INTO source_chunk
            FROM document_chunk WHERE id = NEW.document_chunk_id;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'chunk embedding references unknown chunk'
                    USING ERRCODE = '23503';
            END IF;
            IF NEW.chunk_content_hash <> source_chunk.content_hash THEN
                RAISE EXCEPTION 'chunk embedding hash does not match source chunk'
                    USING ERRCODE = '23514';
            END IF;
            SELECT * INTO profile
            FROM embedding_profile WHERE id = NEW.embedding_profile_id;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'chunk embedding references unknown profile'
                    USING ERRCODE = '23503';
            END IF;
            IF vector_dims(NEW.embedding) <> profile.dimensions THEN
                RAISE EXCEPTION 'chunk embedding dimensions do not match profile'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_document_chunk_embedding_validate
        BEFORE INSERT ON document_chunk_embedding
        FOR EACH ROW EXECUTE FUNCTION validate_document_chunk_embedding()
    """)
    op.execute("""
        CREATE FUNCTION enforce_embedding_profile_lifecycle()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'embedding profiles cannot be deleted'
                    USING ERRCODE = '55000';
            END IF;
            IF ROW(
                NEW.id, NEW.runtime_kind, NEW.provider, NEW.model,
                NEW.model_revision, NEW.license, NEW.dimensions,
                NEW.distance_metric, NEW.normalization_version,
                NEW.preprocessing_version, NEW.config_hash, NEW.created_at
            ) IS DISTINCT FROM ROW(
                OLD.id, OLD.runtime_kind, OLD.provider, OLD.model,
                OLD.model_revision, OLD.license, OLD.dimensions,
                OLD.distance_metric, OLD.normalization_version,
                OLD.preprocessing_version, OLD.config_hash, OLD.created_at
            ) THEN
                RAISE EXCEPTION 'embedding profile metadata is immutable'
                    USING ERRCODE = '55000';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_embedding_profile_lifecycle
        BEFORE UPDATE OR DELETE ON embedding_profile
        FOR EACH ROW EXECUTE FUNCTION enforce_embedding_profile_lifecycle()
    """)
    op.execute("""
        CREATE FUNCTION reject_document_chunk_embedding_change()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'chunk embeddings are immutable'
                USING ERRCODE = '55000';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_document_chunk_embedding_immutable
        BEFORE UPDATE OR DELETE ON document_chunk_embedding
        FOR EACH ROW EXECUTE FUNCTION reject_document_chunk_embedding_change()
    """)


def _drop_embedding_guards() -> None:
    op.execute(
        "DROP TRIGGER trg_document_chunk_embedding_immutable "
        "ON document_chunk_embedding"
    )
    op.execute("DROP FUNCTION reject_document_chunk_embedding_change()")
    op.execute("DROP TRIGGER trg_embedding_profile_lifecycle ON embedding_profile")
    op.execute("DROP FUNCTION enforce_embedding_profile_lifecycle()")
    op.execute(
        "DROP TRIGGER trg_document_chunk_embedding_validate "
        "ON document_chunk_embedding"
    )
    op.execute("DROP FUNCTION validate_document_chunk_embedding()")


def upgrade() -> None:
    op.create_table(
        "embedding_profile",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("runtime_kind", sa.String(length=20), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=200), nullable=False),
        sa.Column("model_revision", sa.String(length=200), nullable=False),
        sa.Column("license", sa.String(length=200), nullable=False),
        sa.Column("dimensions", sa.SmallInteger(), nullable=False),
        sa.Column("distance_metric", sa.String(length=20), nullable=False),
        sa.Column("normalization_version", sa.String(length=100), nullable=False),
        sa.Column("preprocessing_version", sa.String(length=100), nullable=False),
        sa.Column("config_hash", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "runtime_kind IN ('local','hosted')",
            name=op.f("ck_embedding_profile_runtime_kind_allowed"),
        ),
        sa.CheckConstraint(
            "dimensions > 0", name=op.f("ck_embedding_profile_dimensions_positive")
        ),
        sa.CheckConstraint(
            "distance_metric IN ('cosine','euclidean','inner_product')",
            name=op.f("ck_embedding_profile_distance_metric_allowed"),
        ),
        sa.CheckConstraint(
            "config_hash ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_embedding_profile_config_hash_valid"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_embedding_profile")),
        sa.UniqueConstraint(
            "provider",
            "model",
            "model_revision",
            "config_hash",
            name=op.f("uq_embedding_profile_identity"),
        ),
    )
    op.create_table(
        "document_chunk_embedding",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("document_chunk_id", sa.UUID(), nullable=False),
        sa.Column("embedding_profile_id", sa.UUID(), nullable=False),
        sa.Column("chunk_content_hash", sa.String(length=64), nullable=False),
        sa.Column("embedding", Vector(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "chunk_content_hash ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_document_chunk_embedding_chunk_content_hash_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["document_chunk_id"],
            ["document_chunk.id"],
            name=op.f("fk_document_chunk_embedding_document_chunk_id_document_chunk"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["embedding_profile_id"],
            ["embedding_profile.id"],
            name=op.f("fk_document_chunk_embedding_embedding_profile_id_embedding_profile"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_chunk_embedding")),
        sa.UniqueConstraint(
            "document_chunk_id",
            "embedding_profile_id",
            "chunk_content_hash",
            name=op.f("uq_document_chunk_embedding_derivation"),
        ),
    )
    op.create_index(
        op.f("ix_document_chunk_embedding_profile_chunk"),
        "document_chunk_embedding",
        ["embedding_profile_id", "document_chunk_id"],
        unique=False,
    )
    _create_embedding_guards()


def downgrade() -> None:
    _drop_embedding_guards()
    op.drop_index(
        op.f("ix_document_chunk_embedding_profile_chunk"),
        table_name="document_chunk_embedding",
    )
    op.drop_table("document_chunk_embedding")
    op.drop_table("embedding_profile")