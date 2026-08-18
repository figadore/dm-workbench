"""Preparation lifecycle, lineage, pinning, ownership, and asset integration tests."""

import uuid
from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import JsonValue
from sqlalchemy import Engine, func, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from dm_assistant.adapters.assets import LocalAssetStore, StoredBlob
from dm_assistant.db import Campaign, build_session_factory, transactional_session
from dm_assistant.errors import ConflictError, ResourceNotFoundError
from dm_assistant.modules.preparation import (
    ArtifactAssetRole,
    ArtifactLifecycle,
    ArtifactType,
    AttachArtifactAsset,
    ContextSourceLink,
    CreateArtifact,
    CreateArtifactVersion,
    FinishGenerationRun,
    GenerationContextPin,
    GenerationStatus,
    InputPins,
    PendingArtifactAsset,
    PreparationService,
    PublishGeneratedPackage,
    RequiredArtifactAsset,
    StartGenerationRun,
    ToolRunPin,
    TransitionArtifact,
    VisibilityPolicy,
    canonical_json_sha256,
)
from dm_assistant.modules.preparation.models import (
    ArtifactAsset,
    ArtifactLifecycleEvent,
    GeneratedAsset,
    GenerationRun,
    PreparationArtifact,
    PreparationArtifactVersion,
)

pytestmark = pytest.mark.integration


def create_campaign(
    engine: Engine, name: str = "Synthetic Preparation Campaign"
) -> uuid.UUID:
    campaign_id = uuid.uuid4()
    factory = build_session_factory(engine)
    with transactional_session(factory) as session:
        session.add(Campaign(id=campaign_id, name=name))
    return campaign_id


def make_service(
    engine: Engine,
    tmp_path: Path,
    *,
    publication_fault_hook: Callable[[str], None] | None = None,
) -> PreparationService:
    return PreparationService(
        engine,
        LocalAssetStore(tmp_path / "assets", tmp_path / "scratch"),
        publication_fault_hook=publication_fault_hook,
    )


def start_run(service: PreparationService, campaign_id: uuid.UUID) -> uuid.UUID:
    payload: dict[str, JsonValue] = {
        "location": "synthetic_archive",
        "themes": ["flooded"],
    }
    context = GenerationContextPin(
        envelope_kind="dungeon_generation",
        payload_version="1.0.0",
        envelope={
            "schema_version": "1.0.0",
            "context_kind": "dungeon_generation",
            "payload": payload,
        },
        payload_sha256=canonical_json_sha256(payload),
        source_links=(
            ContextSourceLink(
                source_kind="document_revision",
                source_id="synthetic-source",
                revision_id="synthetic-revision",
                sha256="a" * 64,
            ),
        ),
    )
    run = service.start_generation_run(
        StartGenerationRun(
            campaign_id=campaign_id,
            generation_kind="dungeon_layout",
            seed=424242,
            input_scope={"floor_ids": ["floor_upper"]},
            input_pins=InputPins(
                campaign_revision_id=uuid.uuid4(),
                corpus_snapshot_id=uuid.uuid4(),
                rules_profile_id=uuid.uuid4(),
                party_snapshot_id=uuid.uuid4(),
            ),
            context=context,
            schema_versions={
                "dungeon_brief": "1.0.0",
                "dungeon_package": "1.0.0",
            },
            generator_versions={"layout": "orthogonal-v2"},
            renderer_versions={"svg": "svg-v1", "png": "png-v1"},
            model_task_profile_id=uuid.uuid4(),
            model_run_ids=(uuid.uuid4(),),
            tool_runs=(
                ToolRunPin(
                    tool_name="validate_geometry",
                    schema_version="1.0.0",
                    input_sha256="b" * 64,
                    output_sha256="c" * 64,
                    status="succeeded",
                ),
            ),
        )
    )
    return run.id


def finish_run(
    service: PreparationService,
    campaign_id: uuid.UUID,
    run_id: uuid.UUID,
) -> None:
    result = service.finish_generation_run(
        FinishGenerationRun(
            campaign_id=campaign_id,
            run_id=run_id,
            status=GenerationStatus.SUCCEEDED,
            validation_report={"valid": True, "diagnostics": []},
        )
    )
    assert result.status is GenerationStatus.SUCCEEDED


def create_artifact_and_version(
    service: PreparationService,
    campaign_id: uuid.UUID,
    *,
    run_id: uuid.UUID | None = None,
) -> tuple[uuid.UUID, uuid.UUID]:
    artifact = service.create_artifact(
        CreateArtifact(
            campaign_id=campaign_id,
            artifact_type=ArtifactType.DUNGEON,
            title="Synthetic Sunken Archive",
            visibility_policy=VisibilityPolicy.DM_ONLY,
            created_by="synthetic-dm",
        )
    )
    version = service.create_artifact_version(
        CreateArtifactVersion(
            campaign_id=campaign_id,
            artifact_id=artifact.id,
            schema_version="1.0.0",
            specification={"package_id": "pkg_synthetic", "seed": 424242},
            validation_report={"valid": True},
            change_summary="Create the first validated synthetic dungeon version.",
            generation_run_id=run_id,
            created_by="synthetic-dm",
        )
    )
    return artifact.id, version.id


def test_complete_generated_package_is_published_atomically_with_run_success(
    db_engine: Engine,
    tmp_path: Path,
) -> None:
    campaign_id = create_campaign(db_engine)
    service = make_service(db_engine, tmp_path)
    run_id = start_run(service, campaign_id)

    published = service.publish_generated_package(
        PublishGeneratedPackage(
            campaign_id=campaign_id,
            generation_run_id=run_id,
            title="Atomic Synthetic Archive",
            schema_version="1.0.0",
            specification={"package_id": "pkg_atomic", "seed": 424242},
            validation_report={"valid": True, "diagnostics": []},
            change_summary="Publish a complete synthetic generated package.",
            created_by="synthetic-dm",
            assets=(
                PendingArtifactAsset(
                    role=ArtifactAssetRole.SPECIFICATION,
                    media_type="application/json",
                    data=b'{"package_id":"pkg_atomic"}',
                ),
                PendingArtifactAsset(
                    role=ArtifactAssetRole.VALIDATION_REPORT,
                    media_type="application/json",
                    data=b'{"valid":true}',
                ),
            ),
            required_assets=(
                RequiredArtifactAsset(role=ArtifactAssetRole.SPECIFICATION),
                RequiredArtifactAsset(role=ArtifactAssetRole.VALIDATION_REPORT),
            ),
        )
    )

    assert published.generation_run.status is GenerationStatus.SUCCEEDED
    assert published.artifact.current_version_id == published.version.id
    with db_engine.connect() as connection:
        run = connection.execute(
            select(GenerationRun.status, GenerationRun.finished_at).where(
                GenerationRun.id == run_id
            )
        ).one()
        links = list(
            connection.scalars(
                select(ArtifactAsset.role).where(
                    ArtifactAsset.artifact_version_id == published.version.id
                )
            )
        )
    assert run[0] == GenerationStatus.SUCCEEDED.value
    assert run[1] is not None
    assert set(links) == {"specification", "validation_report"}


@pytest.mark.parametrize(
    ("checkpoint", "occurrence"),
    (
        ("asset_stage", 1),
        ("version_creation", 1),
        ("asset_link", 2),
        ("current_version", 1),
        ("run_finish", 1),
    ),
)
def test_generated_package_faults_leave_no_partial_publication(
    db_engine: Engine,
    tmp_path: Path,
    checkpoint: str,
    occurrence: int,
) -> None:
    campaign_id = create_campaign(db_engine)
    seen = 0

    def fail_at(stage: str) -> None:
        nonlocal seen
        if stage == checkpoint:
            seen += 1
        if seen == occurrence:
            raise RuntimeError(f"synthetic {stage} fault")

    service = make_service(db_engine, tmp_path, publication_fault_hook=fail_at)
    run_id = start_run(service, campaign_id)
    command = PublishGeneratedPackage(
        campaign_id=campaign_id,
        generation_run_id=run_id,
        title="Faulted Synthetic Archive",
        schema_version="1.0.0",
        specification={"package_id": "pkg_faulted"},
        validation_report={"valid": True, "diagnostics": []},
        change_summary="Attempt an atomically published synthetic package.",
        created_by="synthetic-dm",
        assets=(
            PendingArtifactAsset(
                role=ArtifactAssetRole.SPECIFICATION,
                media_type="application/json",
                data=b'{"package_id":"pkg_faulted"}',
            ),
            PendingArtifactAsset(
                role=ArtifactAssetRole.VALIDATION_REPORT,
                media_type="application/json",
                data=b'{"valid":true}',
            ),
        ),
        required_assets=(
            RequiredArtifactAsset(role=ArtifactAssetRole.SPECIFICATION),
            RequiredArtifactAsset(role=ArtifactAssetRole.VALIDATION_REPORT),
        ),
    )

    with pytest.raises(RuntimeError, match=checkpoint):
        service.publish_generated_package(command)

    run = service.get_generation_run(campaign_id, run_id)
    assert run.status is GenerationStatus.FAILED
    assert run.validation_report["stage"] == checkpoint
    with db_engine.connect() as connection:
        assert (
            connection.scalar(select(func.count()).select_from(PreparationArtifact))
            == 0
        )
        assert (
            connection.scalar(
                select(func.count()).select_from(PreparationArtifactVersion)
            )
            == 0
        )
        assert connection.scalar(select(func.count()).select_from(ArtifactAsset)) == 0
        assert connection.scalar(select(func.count()).select_from(GeneratedAsset)) == 0


def test_generation_run_pins_every_input_and_becomes_immutable(
    db_engine: Engine,
    tmp_path: Path,
) -> None:
    campaign_id = create_campaign(db_engine)
    service = make_service(db_engine, tmp_path)
    run_id = start_run(service, campaign_id)

    with db_engine.connect() as connection:
        row = (
            connection.execute(
                text(
                    "SELECT seed, input_scope, input_campaign_revision_id, "
                    "input_corpus_snapshot_id, input_rules_profile_id, "
                    "input_party_snapshot_id, context_envelope_kind, "
                    "context_payload_version, context_payload_sha256, "
                    "context_source_links, schema_versions, generator_versions, "
                    "renderer_versions, model_task_profile_id, model_run_ids, "
                    "tool_runs, status, finished_at FROM generation_run WHERE id = :id"
                ),
                {"id": run_id},
            )
            .mappings()
            .one()
        )
    assert row["seed"] == 424242
    assert row["input_scope"] == {"floor_ids": ["floor_upper"]}
    assert all(
        row[name] is not None
        for name in (
            "input_campaign_revision_id",
            "input_corpus_snapshot_id",
            "input_rules_profile_id",
            "input_party_snapshot_id",
            "model_task_profile_id",
        )
    )
    assert row["context_envelope_kind"] == "dungeon_generation"
    assert row["context_payload_version"] == "1.0.0"
    assert row["context_payload_sha256"]
    assert row["context_source_links"][0]["source_id"] == "synthetic-source"
    assert row["schema_versions"]["dungeon_package"] == "1.0.0"
    assert row["generator_versions"] == {"layout": "orthogonal-v2"}
    assert row["renderer_versions"]["png"] == "png-v1"
    assert len(row["model_run_ids"]) == 1
    assert row["tool_runs"][0]["tool_name"] == "validate_geometry"
    assert row["status"] == "running"
    assert row["finished_at"] is None

    finish_run(service, campaign_id, run_id)
    with pytest.raises(ConflictError, match="already terminal"):
        finish_run(service, campaign_id, run_id)
    with pytest.raises(DBAPIError, match="cannot be changed"):
        with db_engine.begin() as connection:
            connection.execute(
                text("UPDATE generation_run SET seed = 1 WHERE id = :id"),
                {"id": run_id},
            )


def test_versions_retain_parent_lineage_and_are_database_immutable(
    db_engine: Engine,
    tmp_path: Path,
) -> None:
    campaign_id = create_campaign(db_engine)
    service = make_service(db_engine, tmp_path)
    run_id = start_run(service, campaign_id)
    finish_run(service, campaign_id, run_id)
    artifact_id, first_id = create_artifact_and_version(
        service,
        campaign_id,
        run_id=run_id,
    )
    second = service.create_artifact_version(
        CreateArtifactVersion(
            campaign_id=campaign_id,
            artifact_id=artifact_id,
            parent_version_id=first_id,
            schema_version="1.0.0",
            specification={"package_id": "pkg_synthetic", "seed": 99},
            validation_report={"valid": True},
            change_summary="Regenerate the unlocked hall while retaining stable IDs.",
            created_by="synthetic-dm",
        )
    )

    assert second.version_number == 2
    assert second.parent_version_id == first_id
    with db_engine.connect() as connection:
        rows = connection.execute(
            select(PreparationArtifactVersion).where(
                PreparationArtifactVersion.artifact_id == artifact_id
            )
        ).scalars()
        assert len(list(rows)) == 2
        current = connection.scalar(
            select(PreparationArtifact.current_version_id).where(
                PreparationArtifact.id == artifact_id
            )
        )
    assert current == second.id

    with pytest.raises(DBAPIError, match="immutable preparation record"):
        with db_engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE prep_artifact_version SET change_summary = 'tampered' "
                    "WHERE id = :id"
                ),
                {"id": first_id},
            )


def test_lifecycle_is_audited_and_never_changes_campaign_canon(
    db_engine: Engine,
    tmp_path: Path,
) -> None:
    campaign_id = create_campaign(db_engine)
    service = make_service(db_engine, tmp_path)
    artifact_id, version_id = create_artifact_and_version(service, campaign_id)

    approved = service.transition_artifact(
        TransitionArtifact(
            campaign_id=campaign_id,
            artifact_id=artifact_id,
            artifact_version_id=version_id,
            target=ArtifactLifecycle.APPROVED_FOR_PLAY,
            actor="synthetic-dm",
            reason="Validated and reviewed for the next session.",
        )
    )
    assert approved.lifecycle is ArtifactLifecycle.APPROVED_FOR_PLAY
    with pytest.raises(ConflictError, match="current draft"):
        service.attach_asset(
            AttachArtifactAsset(
                campaign_id=campaign_id,
                artifact_version_id=version_id,
                role=ArtifactAssetRole.MANIFEST,
                media_type="application/json",
                data=b"{}",
            )
        )
    used = service.transition_artifact(
        TransitionArtifact(
            campaign_id=campaign_id,
            artifact_id=artifact_id,
            artifact_version_id=version_id,
            target=ArtifactLifecycle.USED,
            actor="synthetic-dm",
            reason="The map was used as preparation at the table.",
        )
    )
    assert used.lifecycle is ArtifactLifecycle.USED
    retired = service.transition_artifact(
        TransitionArtifact(
            campaign_id=campaign_id,
            artifact_id=artifact_id,
            target=ArtifactLifecycle.RETIRED,
            actor="synthetic-dm",
            reason="Retire the completed preparation package.",
        )
    )
    assert retired.lifecycle is ArtifactLifecycle.RETIRED

    with db_engine.connect() as connection:
        transitions = list(
            connection.scalars(
                select(ArtifactLifecycleEvent.to_lifecycle)
                .where(ArtifactLifecycleEvent.artifact_id == artifact_id)
                .order_by(ArtifactLifecycleEvent.created_at, ArtifactLifecycleEvent.id)
            )
        )
        campaign = connection.execute(
            select(Campaign.id, Campaign.name).where(Campaign.id == campaign_id)
        ).one()
        tables = set(connection.dialect.get_table_names(connection))
    assert transitions == ["draft", "approved_for_play", "used", "retired"]
    assert campaign == (campaign_id, "Synthetic Preparation Campaign")
    assert "campaign_revision" not in tables
    with pytest.raises(ConflictError, match="invalid"):
        service.transition_artifact(
            TransitionArtifact(
                campaign_id=campaign_id,
                artifact_id=artifact_id,
                target=ArtifactLifecycle.APPROVED_FOR_PLAY,
                actor="synthetic-dm",
                reason="A retired artifact cannot be re-approved.",
                artifact_version_id=version_id,
            )
        )


def test_new_version_resets_approved_artifact_to_draft_with_audit(
    db_engine: Engine,
    tmp_path: Path,
) -> None:
    campaign_id = create_campaign(db_engine)
    service = make_service(db_engine, tmp_path)
    artifact_id, first_id = create_artifact_and_version(service, campaign_id)
    service.transition_artifact(
        TransitionArtifact(
            campaign_id=campaign_id,
            artifact_id=artifact_id,
            artifact_version_id=first_id,
            target=ArtifactLifecycle.APPROVED_FOR_PLAY,
            actor="synthetic-dm",
            reason="Approve the first version.",
        )
    )

    second = service.create_artifact_version(
        CreateArtifactVersion(
            campaign_id=campaign_id,
            artifact_id=artifact_id,
            parent_version_id=first_id,
            schema_version="1.0.0",
            specification={"package_id": "pkg_synthetic", "seed": 7},
            validation_report={"valid": True},
            change_summary="Create a new draft from the approved version.",
            created_by="synthetic-dm",
        )
    )

    with db_engine.connect() as connection:
        artifact = connection.execute(
            select(
                PreparationArtifact.lifecycle,
                PreparationArtifact.current_version_id,
            ).where(PreparationArtifact.id == artifact_id)
        ).one()
        transitions = list(
            connection.scalars(
                select(ArtifactLifecycleEvent.to_lifecycle)
                .where(ArtifactLifecycleEvent.artifact_id == artifact_id)
                .order_by(ArtifactLifecycleEvent.created_at, ArtifactLifecycleEvent.id)
            )
        )
    assert artifact == ("draft", second.id)
    assert transitions == ["draft", "approved_for_play", "draft"]


def test_asset_metadata_and_roles_deduplicate_but_remain_immutable(
    db_engine: Engine,
    tmp_path: Path,
) -> None:
    campaign_id = create_campaign(db_engine)
    service = make_service(db_engine, tmp_path)
    _, version_id = create_artifact_and_version(service, campaign_id)
    command = AttachArtifactAsset(
        campaign_id=campaign_id,
        artifact_version_id=version_id,
        role=ArtifactAssetRole.PLAYER_PNG,
        media_type="image/png",
        data=b"synthetic png bytes",
    )

    first = service.attach_asset(command)
    repeated = service.attach_asset(command)
    manifest = service.attach_asset(
        command.model_copy(update={"role": ArtifactAssetRole.MANIFEST, "ordinal": 1})
    )

    assert repeated == first == manifest
    with db_engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(GeneratedAsset)) == 1
        assert connection.scalar(select(func.count()).select_from(ArtifactAsset)) == 2
    stored = StoredBlob(
        sha256=first.sha256,
        byte_size=first.byte_size,
        storage_locator=first.storage_locator,
        created=False,
    )
    assert (
        LocalAssetStore(tmp_path / "assets", tmp_path / "scratch").read_bytes(stored)
        == b"synthetic png bytes"
    )

    with pytest.raises(ConflictError, match="already assigned"):
        service.attach_asset(command.model_copy(update={"data": b"other bytes"}))
    with pytest.raises(DBAPIError, match="immutable preparation record"):
        with db_engine.begin() as connection:
            connection.execute(
                text("DELETE FROM generated_asset WHERE id = :id"),
                {"id": first.id},
            )


def test_cross_campaign_versions_runs_and_current_pointers_are_rejected(
    db_engine: Engine,
    tmp_path: Path,
) -> None:
    first_campaign = create_campaign(db_engine, "First Synthetic Campaign")
    second_campaign = create_campaign(db_engine, "Second Synthetic Campaign")
    service = make_service(db_engine, tmp_path)
    first_artifact, first_version = create_artifact_and_version(
        service,
        first_campaign,
    )
    second_artifact, second_version = create_artifact_and_version(
        service,
        second_campaign,
    )

    with pytest.raises(ResourceNotFoundError):
        service.create_artifact_version(
            CreateArtifactVersion(
                campaign_id=second_campaign,
                artifact_id=first_artifact,
                parent_version_id=first_version,
                schema_version="1.0.0",
                specification={"invalid": "cross-campaign"},
                validation_report={"valid": False},
                change_summary="This cross-campaign write must be rejected.",
                created_by="synthetic-dm",
            )
        )
    second_run = start_run(service, second_campaign)
    finish_run(service, second_campaign, second_run)
    with pytest.raises(ResourceNotFoundError, match="generation run"):
        service.create_artifact_version(
            CreateArtifactVersion(
                campaign_id=first_campaign,
                artifact_id=first_artifact,
                parent_version_id=first_version,
                schema_version="1.0.0",
                specification={"invalid": "cross-campaign-run"},
                validation_report={"valid": True},
                change_summary="A run from another campaign must be rejected.",
                generation_run_id=second_run,
                created_by="synthetic-dm",
            )
        )
    with pytest.raises(IntegrityError):
        with db_engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE prep_artifact SET current_version_id = :version_id "
                    "WHERE id = :artifact_id"
                ),
                {"version_id": second_version, "artifact_id": first_artifact},
            )
    assert second_artifact != first_artifact


def test_failed_or_unfinished_generation_runs_cannot_produce_versions(
    db_engine: Engine,
    tmp_path: Path,
) -> None:
    campaign_id = create_campaign(db_engine)
    service = make_service(db_engine, tmp_path)
    run_id = start_run(service, campaign_id)
    artifact = service.create_artifact(
        CreateArtifact(
            campaign_id=campaign_id,
            artifact_type=ArtifactType.DUNGEON,
            title="Synthetic Incomplete Run",
            created_by="synthetic-dm",
        )
    )
    command = CreateArtifactVersion(
        campaign_id=campaign_id,
        artifact_id=artifact.id,
        schema_version="1.0.0",
        specification={"package_id": "pkg_incomplete"},
        validation_report={"valid": False},
        change_summary="Do not persist output from an unfinished run.",
        generation_run_id=run_id,
        created_by="synthetic-dm",
    )

    with pytest.raises(ConflictError, match="succeeded"):
        service.create_artifact_version(command)
    service.finish_generation_run(
        FinishGenerationRun(
            campaign_id=campaign_id,
            run_id=run_id,
            status=GenerationStatus.FAILED,
            validation_report={"valid": False},
        )
    )
    with pytest.raises(ConflictError, match="succeeded"):
        service.create_artifact_version(command)
    with db_engine.connect() as connection:
        assert (
            connection.scalar(
                select(func.count())
                .select_from(PreparationArtifactVersion)
                .where(PreparationArtifactVersion.artifact_id == artifact.id)
            )
            == 0
        )

    invalid_version = service.create_artifact_version(
        command.model_copy(update={"generation_run_id": None})
    )
    with pytest.raises(ConflictError, match="valid artifact version"):
        service.transition_artifact(
            TransitionArtifact(
                campaign_id=campaign_id,
                artifact_id=artifact.id,
                artifact_version_id=invalid_version.id,
                target=ArtifactLifecycle.APPROVED_FOR_PLAY,
                actor="synthetic-dm",
                reason="Invalid output must not be approved.",
            )
        )
