"""add immutable library sources"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_library_sources"
down_revision: str | None = "0002_preparation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_library_guards() -> None:
    op.execute("""
        CREATE FUNCTION reject_immutable_library_row()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'immutable library record cannot be changed'
                USING ERRCODE = '55000';
        END;
        $$
    """)
    for table_name in (
        "document_revision",
        "document_chunk",
        "corpus_snapshot_document",
    ):
        op.execute(f"""
            CREATE TRIGGER trg_{table_name}_immutable
            BEFORE UPDATE OR DELETE ON {table_name}
            FOR EACH ROW EXECUTE FUNCTION reject_immutable_library_row()
        """)

    op.execute("""
        CREATE FUNCTION validate_document_revision()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            source_document document%ROWTYPE;
            source_run ingestion_run%ROWTYPE;
        BEGIN
            SELECT * INTO source_document FROM document WHERE id = NEW.document_id;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'document revision references unknown document'
                    USING ERRCODE = '23503';
            END IF;
            IF NEW.campaign_id IS DISTINCT FROM source_document.campaign_id
               OR NEW.corpus <> source_document.corpus THEN
                RAISE EXCEPTION 'document revision scope does not match document'
                    USING ERRCODE = '23514';
            END IF;
            SELECT * INTO source_run FROM ingestion_run WHERE id = NEW.ingestion_run_id;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'document revision references unknown ingestion run'
                    USING ERRCODE = '23503';
            END IF;
            IF NEW.campaign_id IS DISTINCT FROM source_run.campaign_id
               OR NEW.corpus <> source_run.corpus THEN
                RAISE EXCEPTION 'document revision scope does not match ingestion run'
                    USING ERRCODE = '23514';
            END IF;
            IF encode(sha256(convert_to(NEW.content_snapshot, 'UTF8')), 'hex')
               <> NEW.content_hash THEN
                RAISE EXCEPTION 'document revision content hash does not match source'
                    USING ERRCODE = '23514';
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM document_path_history
                WHERE document_id = NEW.document_id
                  AND source_path = NEW.source_path
                  AND content_hash_at_event = NEW.content_hash
            ) THEN
                RAISE EXCEPTION 'revision source path/hash is absent from document history'
                    USING ERRCODE = '23514';
            END IF;
            IF EXISTS (
                SELECT 1 FROM jsonb_array_elements(NEW.visibility_audience) AS audience(value)
                WHERE jsonb_typeof(audience.value) <> 'string'
            ) OR (
                SELECT count(*) FROM jsonb_array_elements(NEW.visibility_audience)
            ) <> (
                SELECT count(DISTINCT value)
                FROM jsonb_array_elements_text(NEW.visibility_audience) AS item(value)
            ) THEN
                RAISE EXCEPTION 'visibility audience must contain unique strings'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_document_revision_validate
        BEFORE INSERT ON document_revision
        FOR EACH ROW EXECUTE FUNCTION validate_document_revision()
    """)

    op.execute("""
        CREATE FUNCTION validate_document_chunk()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            source_revision document_revision%ROWTYPE;
            source_visibility_rank integer;
            chunk_visibility_rank integer;
        BEGIN
            SELECT * INTO source_revision
            FROM document_revision WHERE id = NEW.document_revision_id;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'document chunk references unknown revision'
                    USING ERRCODE = '23503';
            END IF;
            IF NEW.campaign_id IS DISTINCT FROM source_revision.campaign_id
               OR NEW.corpus <> source_revision.corpus THEN
                RAISE EXCEPTION 'document chunk scope does not match revision'
                    USING ERRCODE = '23514';
            END IF;
            IF NEW.end_offset > char_length(source_revision.content_snapshot)
               OR substring(
                    source_revision.content_snapshot
                    FROM NEW.start_offset + 1
                    FOR NEW.end_offset - NEW.start_offset
               ) <> NEW.content THEN
                RAISE EXCEPTION 'document chunk content does not match exact source span'
                    USING ERRCODE = '23514';
            END IF;
            IF encode(sha256(convert_to(NEW.content, 'UTF8')), 'hex')
               <> NEW.content_hash THEN
                RAISE EXCEPTION 'document chunk content hash does not match content'
                    USING ERRCODE = '23514';
            END IF;
            IF NEW.authority_class <> source_revision.authority_class
               OR NEW.ruleset IS DISTINCT FROM source_revision.ruleset THEN
                RAISE EXCEPTION 'chunk authority and ruleset must inherit revision'
                    USING ERRCODE = '23514';
            END IF;

            source_visibility_rank := CASE source_revision.visibility_policy
                WHEN 'dm_only' THEN 0
                WHEN 'explicit_audience' THEN 1
                WHEN 'all_campaign_players' THEN 2
                WHEN 'public' THEN 3
            END;
            chunk_visibility_rank := CASE NEW.visibility_policy
                WHEN 'dm_only' THEN 0
                WHEN 'explicit_audience' THEN 1
                WHEN 'all_campaign_players' THEN 2
                WHEN 'public' THEN 3
            END;
            IF chunk_visibility_rank > source_visibility_rank THEN
                RAISE EXCEPTION 'chunk visibility cannot be broader than revision'
                    USING ERRCODE = '23514';
            END IF;
            IF source_revision.visibility_policy = 'explicit_audience'
               AND NEW.visibility_policy = 'explicit_audience'
               AND EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements_text(NEW.visibility_audience) AS item(value)
                    WHERE NOT source_revision.visibility_audience ? item.value
               ) THEN
                RAISE EXCEPTION 'chunk explicit audience must be a revision audience subset'
                    USING ERRCODE = '23514';
            END IF;
            IF EXISTS (
                SELECT 1 FROM jsonb_array_elements(NEW.heading_path) AS heading(value)
                WHERE jsonb_typeof(heading.value) <> 'string'
            ) OR EXISTS (
                SELECT 1 FROM jsonb_array_elements(NEW.visibility_audience) AS audience(value)
                WHERE jsonb_typeof(audience.value) <> 'string'
            ) OR (
                SELECT count(*) FROM jsonb_array_elements(NEW.visibility_audience)
            ) <> (
                SELECT count(DISTINCT value)
                FROM jsonb_array_elements_text(NEW.visibility_audience) AS item(value)
            ) THEN
                RAISE EXCEPTION 'chunk headings/audience must contain valid strings'
                    USING ERRCODE = '23514';
            END IF;
            NEW.search_vector := to_tsvector(NEW.fts_config::regconfig, NEW.content);
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_document_chunk_validate
        BEFORE INSERT ON document_chunk
        FOR EACH ROW EXECUTE FUNCTION validate_document_chunk()
    """)

    op.execute("""
        CREATE FUNCTION validate_snapshot_document()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            target_snapshot corpus_snapshot%ROWTYPE;
            target_revision document_revision%ROWTYPE;
        BEGIN
            SELECT * INTO target_snapshot
            FROM corpus_snapshot WHERE id = NEW.corpus_snapshot_id;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'snapshot membership references unknown snapshot'
                    USING ERRCODE = '23503';
            END IF;
            IF target_snapshot.state <> 'candidate' THEN
                RAISE EXCEPTION 'membership can only be added to candidate snapshot'
                    USING ERRCODE = '55000';
            END IF;
            SELECT * INTO target_revision
            FROM document_revision WHERE id = NEW.document_revision_id;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'snapshot membership references unknown revision'
                    USING ERRCODE = '23503';
            END IF;
            IF NEW.campaign_id IS DISTINCT FROM target_snapshot.campaign_id
               OR NEW.campaign_id IS DISTINCT FROM target_revision.campaign_id
               OR NEW.corpus <> target_snapshot.corpus
               OR NEW.corpus <> target_revision.corpus
               OR NEW.document_id <> target_revision.document_id THEN
                RAISE EXCEPTION 'snapshot membership scope/document mismatch'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_corpus_snapshot_document_validate
        BEFORE INSERT ON corpus_snapshot_document
        FOR EACH ROW EXECUTE FUNCTION validate_snapshot_document()
    """)

    op.execute("""
        CREATE FUNCTION enforce_corpus_snapshot_lifecycle()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            source_run ingestion_run%ROWTYPE;
            parent_snapshot corpus_snapshot%ROWTYPE;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'corpus snapshots cannot be deleted'
                    USING ERRCODE = '55000';
            END IF;
            IF TG_OP = 'INSERT' THEN
                IF NEW.state <> 'candidate' OR NEW.activated_at IS NOT NULL THEN
                    RAISE EXCEPTION 'new corpus snapshots must be candidates'
                        USING ERRCODE = '23514';
                END IF;
                SELECT * INTO source_run
                FROM ingestion_run WHERE id = NEW.ingestion_run_id;
                IF NOT FOUND
                   OR NEW.campaign_id IS DISTINCT FROM source_run.campaign_id
                   OR NEW.corpus <> source_run.corpus
                   OR source_run.status <> 'succeeded' THEN
                    RAISE EXCEPTION 'snapshot requires succeeded same-scope ingestion run'
                        USING ERRCODE = '23514';
                END IF;
                IF NEW.parent_snapshot_id IS NOT NULL THEN
                    SELECT * INTO parent_snapshot
                    FROM corpus_snapshot WHERE id = NEW.parent_snapshot_id;
                    IF NOT FOUND
                       OR NEW.campaign_id IS DISTINCT FROM parent_snapshot.campaign_id
                       OR NEW.corpus <> parent_snapshot.corpus THEN
                        RAISE EXCEPTION 'snapshot parent must have same scope'
                            USING ERRCODE = '23514';
                    END IF;
                END IF;
                RETURN NEW;
            END IF;

            IF ROW(
                NEW.id, NEW.campaign_id, NEW.corpus, NEW.parent_snapshot_id,
                NEW.ingestion_run_id, NEW.created_at
            ) IS DISTINCT FROM ROW(
                OLD.id, OLD.campaign_id, OLD.corpus, OLD.parent_snapshot_id,
                OLD.ingestion_run_id, OLD.created_at
            ) THEN
                RAISE EXCEPTION 'corpus snapshot pins are immutable'
                    USING ERRCODE = '55000';
            END IF;
            IF OLD.state = 'candidate'
               AND NEW.state = 'active'
               AND NEW.activated_at IS NOT NULL THEN
                RETURN NEW;
            END IF;
            IF OLD.state = 'active'
               AND NEW.state = 'superseded'
               AND NEW.activated_at = OLD.activated_at THEN
                RETURN NEW;
            END IF;
            RAISE EXCEPTION 'invalid corpus snapshot lifecycle transition'
                USING ERRCODE = '55000';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_corpus_snapshot_lifecycle
        BEFORE INSERT OR UPDATE OR DELETE ON corpus_snapshot
        FOR EACH ROW EXECUTE FUNCTION enforce_corpus_snapshot_lifecycle()
    """)

    op.execute("""
        CREATE FUNCTION enforce_ingestion_run_lifecycle()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' OR OLD.status <> 'running' THEN
                RAISE EXCEPTION 'ingestion run cannot be changed'
                    USING ERRCODE = '55000';
            END IF;
            IF NEW.status NOT IN ('succeeded', 'failed', 'review_required')
               OR NEW.finished_at IS NULL THEN
                RAISE EXCEPTION 'ingestion run may only transition to terminal state'
                    USING ERRCODE = '55000';
            END IF;
            IF ROW(
                NEW.id, NEW.campaign_id, NEW.corpus, NEW.source_root_label,
                NEW.configuration, NEW.parser_version, NEW.chunker_version,
                NEW.started_at
            ) IS DISTINCT FROM ROW(
                OLD.id, OLD.campaign_id, OLD.corpus, OLD.source_root_label,
                OLD.configuration, OLD.parser_version, OLD.chunker_version,
                OLD.started_at
            ) THEN
                RAISE EXCEPTION 'ingestion run pins are immutable'
                    USING ERRCODE = '55000';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_ingestion_run_lifecycle
        BEFORE UPDATE OR DELETE ON ingestion_run
        FOR EACH ROW EXECUTE FUNCTION enforce_ingestion_run_lifecycle()
    """)

    op.execute("""
        CREATE FUNCTION enforce_document_identity()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'logical documents cannot be deleted'
                    USING ERRCODE = '55000';
            END IF;
            IF ROW(
                NEW.id, NEW.campaign_id, NEW.corpus, NEW.logical_key, NEW.created_at
            ) IS DISTINCT FROM ROW(
                OLD.id, OLD.campaign_id, OLD.corpus, OLD.logical_key, OLD.created_at
            ) THEN
                RAISE EXCEPTION 'logical document identity is immutable'
                    USING ERRCODE = '55000';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_document_identity
        BEFORE UPDATE OR DELETE ON document
        FOR EACH ROW EXECUTE FUNCTION enforce_document_identity()
    """)

    op.execute("""
        CREATE FUNCTION enforce_document_path_history()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            source_document document%ROWTYPE;
        BEGIN
            IF TG_OP = 'INSERT' THEN
                SELECT * INTO source_document FROM document WHERE id = NEW.document_id;
                IF NOT FOUND
                   OR NEW.campaign_id IS DISTINCT FROM source_document.campaign_id
                   OR NEW.corpus <> source_document.corpus THEN
                    RAISE EXCEPTION 'path history scope does not match document'
                        USING ERRCODE = '23514';
                END IF;
                IF NEW.valid_to IS NULL AND NEW.source_path <> source_document.source_path THEN
                    RAISE EXCEPTION 'current path history must match document source path'
                        USING ERRCODE = '23514';
                END IF;
                RETURN NEW;
            END IF;
            IF TG_OP = 'DELETE' OR OLD.valid_to IS NOT NULL OR NEW.valid_to IS NULL THEN
                RAISE EXCEPTION 'path history is immutable except interval close'
                    USING ERRCODE = '55000';
            END IF;
            IF ROW(
                NEW.id, NEW.campaign_id, NEW.corpus, NEW.document_id,
                NEW.source_path, NEW.event_kind, NEW.content_hash_at_event,
                NEW.valid_from
            ) IS DISTINCT FROM ROW(
                OLD.id, OLD.campaign_id, OLD.corpus, OLD.document_id,
                OLD.source_path, OLD.event_kind, OLD.content_hash_at_event,
                OLD.valid_from
            ) THEN
                RAISE EXCEPTION 'path history identity is immutable'
                    USING ERRCODE = '55000';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_document_path_history
        BEFORE INSERT OR UPDATE OR DELETE ON document_path_history
        FOR EACH ROW EXECUTE FUNCTION enforce_document_path_history()
    """)

    op.execute("""
        CREATE FUNCTION validate_document_current_path()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            target_document_id uuid;
            expected_path text;
            current_count bigint;
            current_path text;
        BEGIN
            IF TG_TABLE_NAME = 'document' THEN
                target_document_id := NEW.id;
            ELSE
                target_document_id := COALESCE(NEW.document_id, OLD.document_id);
            END IF;
            SELECT source_path INTO expected_path
            FROM document WHERE id = target_document_id;
            IF NOT FOUND THEN
                RETURN NULL;
            END IF;
            SELECT count(*), min(source_path)
            INTO current_count, current_path
            FROM document_path_history
            WHERE document_id = target_document_id AND valid_to IS NULL;
            IF current_count <> 1 OR current_path <> expected_path THEN
                RAISE EXCEPTION 'document current path and path history are inconsistent'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NULL;
        END;
        $$
    """)
    op.execute("""
        CREATE CONSTRAINT TRIGGER trg_document_current_path_consistent
        AFTER INSERT OR UPDATE ON document
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION validate_document_current_path()
    """)
    op.execute("""
        CREATE CONSTRAINT TRIGGER trg_document_path_current_consistent
        AFTER INSERT OR UPDATE OR DELETE ON document_path_history
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION validate_document_current_path()
    """)


def _drop_library_guards() -> None:
    op.execute(
        "DROP TRIGGER trg_document_path_current_consistent ON document_path_history"
    )
    op.execute("DROP TRIGGER trg_document_current_path_consistent ON document")
    op.execute("DROP FUNCTION validate_document_current_path()")
    op.execute("DROP TRIGGER trg_document_path_history ON document_path_history")
    op.execute("DROP FUNCTION enforce_document_path_history()")
    op.execute("DROP TRIGGER trg_document_identity ON document")
    op.execute("DROP FUNCTION enforce_document_identity()")
    op.execute("DROP TRIGGER trg_ingestion_run_lifecycle ON ingestion_run")
    op.execute("DROP FUNCTION enforce_ingestion_run_lifecycle()")
    op.execute("DROP TRIGGER trg_corpus_snapshot_lifecycle ON corpus_snapshot")
    op.execute("DROP FUNCTION enforce_corpus_snapshot_lifecycle()")
    op.execute(
        "DROP TRIGGER trg_corpus_snapshot_document_validate ON corpus_snapshot_document"
    )
    op.execute("DROP FUNCTION validate_snapshot_document()")
    op.execute("DROP TRIGGER trg_document_chunk_validate ON document_chunk")
    op.execute("DROP FUNCTION validate_document_chunk()")
    op.execute("DROP TRIGGER trg_document_revision_validate ON document_revision")
    op.execute("DROP FUNCTION validate_document_revision()")
    for table_name in (
        "document_revision",
        "document_chunk",
        "corpus_snapshot_document",
    ):
        op.execute(f"DROP TRIGGER trg_{table_name}_immutable ON {table_name}")
    op.execute("DROP FUNCTION reject_immutable_library_row()")


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "document",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("campaign_id", sa.UUID(), nullable=True),
        sa.Column("corpus", sa.String(length=20), nullable=False),
        sa.Column("logical_key", sa.String(length=200), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "corpus <> 'campaign' OR campaign_id IS NOT NULL",
            name=op.f("ck_document_campaign_corpus_has_owner"),
        ),
        sa.CheckConstraint(
            "corpus IN ('campaign','rules')", name=op.f("ck_document_corpus_allowed")
        ),
        sa.CheckConstraint(
            "length(source_path) > 0 AND source_path !~ '(^/|(^|/)\\.\\.(/|$)|\\\\)'",
            name=op.f("ck_document_source_path_safe_relative"),
        ),
        sa.CheckConstraint(
            "length(btrim(logical_key)) > 0",
            name=op.f("ck_document_logical_key_not_blank"),
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaign.id"],
            name=op.f("fk_document_campaign_id_campaign"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document")),
        sa.UniqueConstraint(
            "campaign_id",
            "corpus",
            "id",
            name="uq_document_owner_corpus_id",
            postgresql_nulls_not_distinct=True,
        ),
        sa.UniqueConstraint(
            "campaign_id",
            "corpus",
            "logical_key",
            name="uq_document_owner_corpus_logical_key",
            postgresql_nulls_not_distinct=True,
        ),
    )
    op.create_index(
        "uq_document_active_source_path",
        "document",
        ["campaign_id", "corpus", "source_path"],
        unique=True,
        postgresql_where=sa.text("retired_at IS NULL"),
        postgresql_nulls_not_distinct=True,
    )
    op.create_table(
        "ingestion_run",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("campaign_id", sa.UUID(), nullable=True),
        sa.Column("corpus", sa.String(length=20), nullable=False),
        sa.Column("source_root_label", sa.String(length=200), nullable=False),
        sa.Column(
            "configuration", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("parser_version", sa.String(length=80), nullable=False),
        sa.Column("chunker_version", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column(
            "summary",
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
            "(status = 'running' AND finished_at IS NULL) OR (status IN ('succeeded','failed','review_required') AND finished_at IS NOT NULL)",
            name=op.f("ck_ingestion_run_status_finished_consistent"),
        ),
        sa.CheckConstraint(
            "corpus <> 'campaign' OR campaign_id IS NOT NULL",
            name=op.f("ck_ingestion_run_campaign_corpus_has_owner"),
        ),
        sa.CheckConstraint(
            "corpus IN ('campaign','rules')",
            name=op.f("ck_ingestion_run_corpus_allowed"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(configuration) = 'object' AND jsonb_typeof(summary) = 'object'",
            name=op.f("ck_ingestion_run_json_objects"),
        ),
        sa.CheckConstraint(
            "status IN ('running','succeeded','failed','review_required')",
            name=op.f("ck_ingestion_run_status_allowed"),
        ),
        sa.CheckConstraint(
            "finished_at IS NULL OR finished_at >= started_at",
            name=op.f("ck_ingestion_run_finished_after_started"),
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaign.id"],
            name=op.f("fk_ingestion_run_campaign_id_campaign"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ingestion_run")),
        sa.UniqueConstraint(
            "campaign_id",
            "corpus",
            "id",
            name="uq_ingestion_run_owner_corpus_id",
            postgresql_nulls_not_distinct=True,
        ),
    )
    op.create_table(
        "corpus_snapshot",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("campaign_id", sa.UUID(), nullable=True),
        sa.Column("corpus", sa.String(length=20), nullable=False),
        sa.Column("parent_snapshot_id", sa.UUID(), nullable=True),
        sa.Column("ingestion_run_id", sa.UUID(), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(state = 'candidate' AND activated_at IS NULL) OR (state IN ('active','superseded') AND activated_at IS NOT NULL)",
            name=op.f("ck_corpus_snapshot_state_activation_consistent"),
        ),
        sa.CheckConstraint(
            "corpus <> 'campaign' OR campaign_id IS NOT NULL",
            name=op.f("ck_corpus_snapshot_campaign_corpus_has_owner"),
        ),
        sa.CheckConstraint(
            "corpus IN ('campaign','rules')",
            name=op.f("ck_corpus_snapshot_corpus_allowed"),
        ),
        sa.CheckConstraint(
            "state IN ('candidate','active','superseded')",
            name=op.f("ck_corpus_snapshot_state_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id", "corpus", "ingestion_run_id"],
            ["ingestion_run.campaign_id", "ingestion_run.corpus", "ingestion_run.id"],
            name="fk_corpus_snapshot_ingestion_same_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id", "corpus", "parent_snapshot_id"],
            [
                "corpus_snapshot.campaign_id",
                "corpus_snapshot.corpus",
                "corpus_snapshot.id",
            ],
            name="fk_corpus_snapshot_parent_same_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_run.id"],
            name=op.f("fk_corpus_snapshot_ingestion_run_id_ingestion_run"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["parent_snapshot_id"],
            ["corpus_snapshot.id"],
            name=op.f("fk_corpus_snapshot_parent_snapshot_id_corpus_snapshot"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_corpus_snapshot")),
        sa.UniqueConstraint(
            "campaign_id",
            "corpus",
            "id",
            name="uq_corpus_snapshot_owner_corpus_id",
            postgresql_nulls_not_distinct=True,
        ),
    )
    op.create_index(
        "uq_corpus_snapshot_active_scope",
        "corpus_snapshot",
        ["campaign_id", "corpus"],
        unique=True,
        postgresql_where=sa.text("state = 'active'"),
        postgresql_nulls_not_distinct=True,
    )
    op.create_table(
        "document_path_history",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("campaign_id", sa.UUID(), nullable=True),
        sa.Column("corpus", sa.String(length=20), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("event_kind", sa.String(length=24), nullable=False),
        sa.Column("content_hash_at_event", sa.String(length=64), nullable=False),
        sa.Column(
            "valid_from",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "content_hash_at_event ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_document_path_history_content_hash_valid"),
        ),
        sa.CheckConstraint(
            "corpus IN ('campaign','rules')",
            name=op.f("ck_document_path_history_corpus_allowed"),
        ),
        sa.CheckConstraint(
            "event_kind IN ('discovered','moved','content_changed','restored','retired')",
            name=op.f("ck_document_path_history_event_kind_allowed"),
        ),
        sa.CheckConstraint(
            "length(source_path) > 0 AND source_path !~ '(^/|(^|/)\\.\\.(/|$)|\\\\)'",
            name=op.f("ck_document_path_history_source_path_safe_relative"),
        ),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from",
            name=op.f("ck_document_path_history_valid_interval"),
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id", "corpus", "document_id"],
            ["document.campaign_id", "document.corpus", "document.id"],
            name="fk_document_path_owner_document",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["document.id"],
            name=op.f("fk_document_path_history_document_id_document"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_path_history")),
        sa.UniqueConstraint(
            "document_id", "source_path", "valid_from", name="uq_document_path_event"
        ),
    )
    op.create_index(
        "uq_document_path_current",
        "document_path_history",
        ["document_id"],
        unique=True,
        postgresql_where=sa.text("valid_to IS NULL"),
    )
    op.create_index(
        "ix_document_path_scope_content_hash",
        "document_path_history",
        ["campaign_id", "corpus", "content_hash_at_event"],
        unique=False,
    )
    op.create_table(
        "document_revision",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("campaign_id", sa.UUID(), nullable=True),
        sa.Column("corpus", sa.String(length=20), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("content_snapshot", sa.Text(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("document_type", sa.String(length=50), nullable=False),
        sa.Column("authority_class", sa.String(length=40), nullable=False),
        sa.Column("ruleset", sa.String(length=40), nullable=True),
        sa.Column("visibility_policy", sa.String(length=40), nullable=False),
        sa.Column(
            "visibility_audience",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column(
            "source_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("parser_version", sa.String(length=80), nullable=False),
        sa.Column("ingestion_run_id", sa.UUID(), nullable=False),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(visibility_policy = 'explicit_audience' AND jsonb_typeof(visibility_audience) = 'array' AND jsonb_array_length(visibility_audience) > 0) OR (visibility_policy <> 'explicit_audience' AND visibility_audience = '[]'::jsonb)",
            name=op.f("ck_document_revision_visibility_audience_consistent"),
        ),
        sa.CheckConstraint(
            "authority_class NOT IN ('canonical_claim','raw_record','preparation') OR corpus = 'campaign'",
            name=op.f("ck_document_revision_campaign_authority_scope"),
        ),
        sa.CheckConstraint(
            "authority_class <> 'official_rules' OR (corpus = 'rules' AND visibility_policy = 'dm_only')",
            name=op.f("ck_document_revision_official_rules_safe"),
        ),
        sa.CheckConstraint(
            "authority_class <> 'user_authored_rules' OR ruleset IS NOT NULL",
            name=op.f("ck_document_revision_user_rules_has_ruleset"),
        ),
        sa.CheckConstraint(
            "authority_class IN ('canonical_claim','raw_record','preparation','reference','official_rules','user_authored_rules')",
            name=op.f("ck_document_revision_authority_allowed"),
        ),
        sa.CheckConstraint(
            "content_hash ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_document_revision_content_hash_valid"),
        ),
        sa.CheckConstraint(
            "corpus <> 'rules' OR ruleset IS NOT NULL",
            name=op.f("ck_document_revision_rules_corpus_has_ruleset"),
        ),
        sa.CheckConstraint(
            "corpus IN ('campaign','rules')",
            name=op.f("ck_document_revision_corpus_allowed"),
        ),
        sa.CheckConstraint(
            "document_type <> 'canon_note' OR authority_class = 'canonical_claim'",
            name=op.f("ck_document_revision_canon_note_authority"),
        ),
        sa.CheckConstraint(
            "document_type <> 'raw_session_record' OR authority_class = 'raw_record'",
            name=op.f("ck_document_revision_raw_record_authority"),
        ),
        sa.CheckConstraint(
            "document_type IN ('canon_note','raw_session_record','plan_or_adventure','reference_lore','player_handout','character_sheet','important_item_record','creature_or_bestiary_record','dungeon_or_encounter_brief','house_rule_or_ruling','rules_reference')",
            name=op.f("ck_document_revision_document_type_allowed"),
        ),
        sa.CheckConstraint(
            "document_type <> 'rules_reference' OR corpus = 'rules'",
            name=op.f("ck_document_revision_rules_reference_corpus"),
        ),
        sa.CheckConstraint(
            "document_type NOT IN ('creature_or_bestiary_record','house_rule_or_ruling') OR ruleset IS NOT NULL",
            name=op.f("ck_document_revision_mechanics_record_has_ruleset"),
        ),
        sa.CheckConstraint(
            "document_type <> 'house_rule_or_ruling' OR authority_class = 'user_authored_rules'",
            name=op.f("ck_document_revision_house_rule_authority"),
        ),
        sa.CheckConstraint(
            "document_type NOT IN ('plan_or_adventure','dungeon_or_encounter_brief') OR (corpus = 'campaign' AND authority_class = 'preparation' AND visibility_policy = 'dm_only')",
            name=op.f("ck_document_revision_preparation_classification_safe"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(source_metadata) = 'object'",
            name=op.f("ck_document_revision_source_metadata_object"),
        ),
        sa.CheckConstraint(
            "length(source_path) > 0 AND source_path !~ '(^/|(^|/)\\.\\.(/|$)|\\\\)'",
            name=op.f("ck_document_revision_source_path_safe_relative"),
        ),
        sa.CheckConstraint(
            "octet_length(convert_to(content_snapshot, 'UTF8')) = byte_size",
            name=op.f("ck_document_revision_byte_size_matches_utf8_content"),
        ),
        sa.CheckConstraint(
            "ruleset IS NULL OR ruleset IN ('dnd_5e_2014','dnd_5e_2024','system_agnostic','other')",
            name=op.f("ck_document_revision_ruleset_allowed"),
        ),
        sa.CheckConstraint(
            "visibility_policy IN ('dm_only','all_campaign_players','explicit_audience','public')",
            name=op.f("ck_document_revision_visibility_allowed"),
        ),
        sa.CheckConstraint(
            "byte_size >= 0", name=op.f("ck_document_revision_byte_size_nonnegative")
        ),
        sa.CheckConstraint(
            "length(btrim(title)) > 0",
            name=op.f("ck_document_revision_title_not_blank"),
        ),
        sa.CheckConstraint(
            "revision_number > 0",
            name=op.f("ck_document_revision_revision_number_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id", "corpus", "document_id"],
            ["document.campaign_id", "document.corpus", "document.id"],
            name="fk_document_revision_owner_document",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["document.id"],
            name=op.f("fk_document_revision_document_id_document"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_run.id"],
            name=op.f("fk_document_revision_ingestion_run_id_ingestion_run"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_revision")),
        sa.UniqueConstraint(
            "campaign_id",
            "corpus",
            "id",
            name="uq_document_revision_owner_corpus_id",
            postgresql_nulls_not_distinct=True,
        ),
        sa.UniqueConstraint(
            "document_id", "content_hash", name="uq_document_revision_content_hash"
        ),
        sa.UniqueConstraint(
            "document_id", "revision_number", name="uq_document_revision_number"
        ),
    )
    op.create_index(
        "ix_document_revision_scope_content_hash",
        "document_revision",
        ["campaign_id", "corpus", "content_hash"],
        unique=False,
    )
    op.create_table(
        "corpus_snapshot_document",
        sa.Column("corpus_snapshot_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("document_revision_id", sa.UUID(), nullable=False),
        sa.Column("campaign_id", sa.UUID(), nullable=True),
        sa.Column("corpus", sa.String(length=20), nullable=False),
        sa.Column("ordinal", sa.SmallInteger(), nullable=False),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "ordinal >= 0", name=op.f("ck_corpus_snapshot_document_ordinal_nonnegative")
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id", "corpus", "corpus_snapshot_id"],
            [
                "corpus_snapshot.campaign_id",
                "corpus_snapshot.corpus",
                "corpus_snapshot.id",
            ],
            name="fk_snapshot_document_snapshot_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id", "corpus", "document_revision_id"],
            [
                "document_revision.campaign_id",
                "document_revision.corpus",
                "document_revision.id",
            ],
            name="fk_snapshot_document_revision_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["corpus_snapshot_id"],
            ["corpus_snapshot.id"],
            name=op.f("fk_corpus_snapshot_document_corpus_snapshot_id_corpus_snapshot"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["document.id"],
            name=op.f("fk_corpus_snapshot_document_document_id_document"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_revision_id"],
            ["document_revision.id"],
            name=op.f(
                "fk_corpus_snapshot_document_document_revision_id_document_revision"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "corpus_snapshot_id",
            "document_id",
            name=op.f("pk_corpus_snapshot_document"),
        ),
        sa.UniqueConstraint(
            "corpus_snapshot_id",
            "document_revision_id",
            name="uq_snapshot_document_revision",
        ),
        sa.UniqueConstraint(
            "corpus_snapshot_id", "ordinal", name="uq_snapshot_document_ordinal"
        ),
    )
    op.create_table(
        "document_chunk",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("campaign_id", sa.UUID(), nullable=True),
        sa.Column("corpus", sa.String(length=20), nullable=False),
        sa.Column("document_revision_id", sa.UUID(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column(
            "heading_path", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("page_end", sa.Integer(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("search_vector", postgresql.TSVECTOR(), nullable=False),
        sa.Column("fts_config", sa.String(length=50), nullable=False),
        sa.Column("chunker_version", sa.String(length=80), nullable=False),
        sa.Column("authority_class", sa.String(length=40), nullable=False),
        sa.Column("ruleset", sa.String(length=40), nullable=True),
        sa.Column("visibility_policy", sa.String(length=40), nullable=False),
        sa.Column(
            "visibility_audience",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(visibility_policy = 'explicit_audience' AND jsonb_typeof(visibility_audience) = 'array' AND jsonb_array_length(visibility_audience) > 0) OR (visibility_policy <> 'explicit_audience' AND visibility_audience = '[]'::jsonb)",
            name=op.f("ck_document_chunk_visibility_audience_consistent"),
        ),
        sa.CheckConstraint(
            "authority_class IN ('canonical_claim','raw_record','preparation','reference','official_rules','user_authored_rules')",
            name=op.f("ck_document_chunk_authority_allowed"),
        ),
        sa.CheckConstraint(
            "content_hash ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_document_chunk_content_hash_valid"),
        ),
        sa.CheckConstraint(
            "corpus IN ('campaign','rules')",
            name=op.f("ck_document_chunk_corpus_allowed"),
        ),
        sa.CheckConstraint(
            "fts_config IN ('english','simple')",
            name=op.f("ck_document_chunk_fts_config_allowed"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(heading_path) = 'array' AND jsonb_typeof(metadata) = 'object'",
            name=op.f("ck_document_chunk_chunk_json_shapes"),
        ),
        sa.CheckConstraint(
            "ruleset IS NULL OR ruleset IN ('dnd_5e_2014','dnd_5e_2024','system_agnostic','other')",
            name=op.f("ck_document_chunk_ruleset_allowed"),
        ),
        sa.CheckConstraint(
            "visibility_policy IN ('dm_only','all_campaign_players','explicit_audience','public')",
            name=op.f("ck_document_chunk_visibility_allowed"),
        ),
        sa.CheckConstraint(
            "(page_start IS NULL AND page_end IS NULL) OR (page_start >= 1 AND page_end >= page_start)",
            name=op.f("ck_document_chunk_page_range_valid"),
        ),
        sa.CheckConstraint(
            "ordinal >= 0", name=op.f("ck_document_chunk_ordinal_nonnegative")
        ),
        sa.CheckConstraint(
            "start_offset >= 0 AND end_offset > start_offset",
            name=op.f("ck_document_chunk_offsets_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["document_revision_id"],
            ["document_revision.id"],
            name=op.f("fk_document_chunk_document_revision_id_document_revision"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_chunk")),
        sa.UniqueConstraint(
            "document_revision_id", "ordinal", name="uq_document_chunk_ordinal"
        ),
    )
    op.create_index(
        "ix_document_chunk_search_vector",
        "document_chunk",
        ["search_vector"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        "ix_document_chunk_scope_visibility",
        "document_chunk",
        ["campaign_id", "corpus", "visibility_policy", "ruleset"],
        unique=False,
    )
    _create_library_guards()
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    _drop_library_guards()
    op.drop_index("ix_document_chunk_scope_visibility", table_name="document_chunk")
    op.drop_index(
        "ix_document_chunk_search_vector",
        table_name="document_chunk",
        postgresql_using="gin",
    )
    op.drop_table("document_chunk")
    op.drop_table("corpus_snapshot_document")
    op.drop_index(
        "ix_document_revision_scope_content_hash", table_name="document_revision"
    )
    op.drop_table("document_revision")
    op.drop_index(
        "ix_document_path_scope_content_hash",
        table_name="document_path_history",
    )
    op.drop_index(
        "uq_document_path_current",
        table_name="document_path_history",
        postgresql_where=sa.text("valid_to IS NULL"),
    )
    op.drop_table("document_path_history")
    op.drop_index(
        "uq_corpus_snapshot_active_scope",
        table_name="corpus_snapshot",
        postgresql_where=sa.text("state = 'active'"),
        postgresql_nulls_not_distinct=True,
    )
    op.drop_table("corpus_snapshot")
    op.drop_table("ingestion_run")
    op.drop_index(
        "uq_document_active_source_path",
        table_name="document",
        postgresql_where=sa.text("retired_at IS NULL"),
        postgresql_nulls_not_distinct=True,
    )
    op.drop_table("document")
    # ### end Alembic commands ###
