"""Transactional preparation services with no canonical campaign write path."""

import uuid
from collections.abc import Callable
from typing import Literal

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from dm_assistant.adapters.assets import AssetStore, StoredBlob
from dm_assistant.db import build_session_factory, transactional_session
from dm_assistant.errors import ConflictError, ResourceNotFoundError
from dm_assistant.modules.preparation.contracts import (
    ArtifactAssetRecord,
    ArtifactAssetRole,
    ArtifactLifecycle,
    ArtifactRecord,
    ArtifactType,
    ArtifactVersionRecord,
    ArtifactVersionSnapshot,
    AssetRecord,
    AttachArtifactAsset,
    CreateArtifact,
    CreateArtifactVersion,
    FinishGenerationRun,
    GenerationRunRecord,
    GenerationRunSnapshot,
    GenerationStatus,
    InputPins,
    PendingArtifactAsset,
    PublishedGeneratedPackage,
    PublishGeneratedPackage,
    StartGenerationRun,
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
from dm_assistant.modules.preparation.repository import (
    PreparationRepository,
    SqlAlchemyPreparationRepository,
)

RepositoryFactory = Callable[[Session], PreparationRepository]
IdFactory = Callable[[], uuid.UUID]
PublicationCheckpoint = Literal[
    "asset_stage",
    "version_creation",
    "asset_link",
    "current_version",
    "run_finish",
]
PublicationFaultHook = Callable[[PublicationCheckpoint], None]
_ALLOWED_TRANSITIONS = {
    ArtifactLifecycle.DRAFT: frozenset(
        {ArtifactLifecycle.APPROVED_FOR_PLAY, ArtifactLifecycle.RETIRED}
    ),
    ArtifactLifecycle.APPROVED_FOR_PLAY: frozenset(
        {ArtifactLifecycle.USED, ArtifactLifecycle.RETIRED}
    ),
    ArtifactLifecycle.USED: frozenset({ArtifactLifecycle.RETIRED}),
    ArtifactLifecycle.RETIRED: frozenset(),
}


class PreparationService:
    """Application boundary for preparation-only versions, runs, and assets."""

    def __init__(
        self,
        engine: Engine,
        asset_store: AssetStore,
        *,
        repository_factory: RepositoryFactory = SqlAlchemyPreparationRepository,
        id_factory: IdFactory = uuid.uuid4,
        publication_fault_hook: PublicationFaultHook | None = None,
    ) -> None:
        self._session_factory = build_session_factory(engine)
        self._asset_store = asset_store
        self._repository_factory = repository_factory
        self._id_factory = id_factory
        self._publication_fault_hook = publication_fault_hook

    def create_artifact(self, command: CreateArtifact) -> ArtifactRecord:
        artifact_id = self._id_factory()
        with transactional_session(self._session_factory) as session:
            repository = self._repository_factory(session)
            artifact = PreparationArtifact(
                id=artifact_id,
                campaign_id=command.campaign_id,
                artifact_type=command.artifact_type.value,
                title=command.title,
                lifecycle=ArtifactLifecycle.DRAFT.value,
                current_version_id=None,
                visibility_policy=command.visibility_policy.value,
                created_by=command.created_by,
            )
            repository.add_artifact(artifact)
            repository.add_lifecycle_event(
                ArtifactLifecycleEvent(
                    id=self._id_factory(),
                    artifact_id=artifact.id,
                    artifact_version_id=None,
                    from_lifecycle=None,
                    to_lifecycle=ArtifactLifecycle.DRAFT.value,
                    actor=command.created_by,
                    reason="Artifact created.",
                )
            )
        return _artifact_record(artifact)

    def list_artifacts(self, campaign_id: uuid.UUID) -> tuple[ArtifactRecord, ...]:
        with transactional_session(self._session_factory) as session:
            repository = self._repository_factory(session)
            artifacts = repository.list_artifacts(campaign_id)
            return tuple(_artifact_record(item) for item in artifacts)

    def get_artifact(
        self,
        campaign_id: uuid.UUID,
        artifact_id: uuid.UUID,
    ) -> ArtifactRecord:
        with transactional_session(self._session_factory) as session:
            repository = self._repository_factory(session)
            artifact = repository.get_artifact(
                campaign_id,
                artifact_id,
                for_update=False,
            )
            if artifact is None:
                raise ResourceNotFoundError("The preparation artifact was not found.")
            return _artifact_record(artifact)

    def list_versions(
        self,
        campaign_id: uuid.UUID,
        artifact_id: uuid.UUID,
    ) -> tuple[ArtifactVersionSnapshot, ...]:
        with transactional_session(self._session_factory) as session:
            repository = self._repository_factory(session)
            artifact = repository.get_artifact(
                campaign_id,
                artifact_id,
                for_update=False,
            )
            if artifact is None:
                raise ResourceNotFoundError("The preparation artifact was not found.")
            versions = repository.list_versions(campaign_id, artifact_id)
            return tuple(_version_snapshot(item) for item in versions)

    def get_version(
        self,
        campaign_id: uuid.UUID,
        version_id: uuid.UUID,
    ) -> ArtifactVersionSnapshot:
        with transactional_session(self._session_factory) as session:
            repository = self._repository_factory(session)
            version = repository.get_version(campaign_id, version_id)
            if version is None:
                raise ResourceNotFoundError("The artifact version was not found.")
            return _version_snapshot(version)

    def list_assets(
        self,
        campaign_id: uuid.UUID,
        artifact_version_id: uuid.UUID,
    ) -> tuple[ArtifactAssetRecord, ...]:
        with transactional_session(self._session_factory) as session:
            repository = self._repository_factory(session)
            if repository.get_version(campaign_id, artifact_version_id) is None:
                raise ResourceNotFoundError("The artifact version was not found.")
            pairs = repository.list_artifact_assets(campaign_id, artifact_version_id)
            return tuple(
                ArtifactAssetRecord(
                    artifact_version_id=link.artifact_version_id,
                    role=ArtifactAssetRole(link.role),
                    ordinal=link.ordinal,
                    asset_id=asset.id,
                    sha256=asset.sha256,
                    byte_size=asset.byte_size,
                    media_type=asset.media_type,
                    storage_locator=asset.storage_locator,
                )
                for link, asset in pairs
            )

    def read_asset(
        self,
        campaign_id: uuid.UUID,
        asset_id: uuid.UUID,
        *,
        maximum_bytes: int | None = None,
    ) -> tuple[AssetRecord, bytes]:
        with transactional_session(self._session_factory) as session:
            repository = self._repository_factory(session)
            asset = repository.get_asset_for_campaign(campaign_id, asset_id)
            if asset is None:
                raise ResourceNotFoundError("The generated asset was not found.")
            record = _asset_record(asset)
        data = self._asset_store.read_bytes(
            StoredBlob(
                sha256=record.sha256,
                byte_size=record.byte_size,
                storage_locator=record.storage_locator,
                created=False,
            ),
            maximum_bytes=maximum_bytes,
        )
        return record, data

    def start_generation_run(
        self,
        command: StartGenerationRun,
    ) -> GenerationRunRecord:
        run_id = self._id_factory()
        context = command.context
        pins = command.input_pins
        with transactional_session(self._session_factory) as session:
            repository = self._repository_factory(session)
            run = GenerationRun(
                id=run_id,
                campaign_id=command.campaign_id,
                generation_kind=command.generation_kind,
                seed=command.seed,
                input_scope=command.input_scope,
                input_campaign_revision_id=pins.campaign_revision_id,
                input_corpus_snapshot_id=pins.corpus_snapshot_id,
                input_rules_profile_id=pins.rules_profile_id,
                input_party_snapshot_id=pins.party_snapshot_id,
                generation_context_envelope=context.envelope if context else None,
                context_envelope_kind=context.envelope_kind if context else None,
                context_payload_version=context.payload_version if context else None,
                context_payload_sha256=context.payload_sha256 if context else None,
                context_source_links=(
                    [item.model_dump(mode="json") for item in context.source_links]
                    if context
                    else []
                ),
                schema_versions=dict(command.schema_versions),
                generator_versions=dict(command.generator_versions),
                renderer_versions=dict(command.renderer_versions),
                model_task_profile_id=command.model_task_profile_id,
                model_run_ids=[str(item) for item in command.model_run_ids],
                tool_runs=[item.model_dump(mode="json") for item in command.tool_runs],
                validation_report={},
                status=GenerationStatus.RUNNING.value,
                finished_at=None,
            )
            repository.add_generation_run(run)
        return _generation_run_record(run)

    def get_generation_run(
        self,
        campaign_id: uuid.UUID,
        run_id: uuid.UUID,
    ) -> GenerationRunSnapshot:
        with transactional_session(self._session_factory) as session:
            repository = self._repository_factory(session)
            run = repository.get_generation_run(
                campaign_id,
                run_id,
                for_update=False,
            )
            if run is None:
                raise ResourceNotFoundError("The generation run was not found.")
            return _generation_run_snapshot(run)

    def finish_generation_run(
        self,
        command: FinishGenerationRun,
    ) -> GenerationRunRecord:
        with transactional_session(self._session_factory) as session:
            repository = self._repository_factory(session)
            run = repository.get_generation_run(
                command.campaign_id,
                command.run_id,
                for_update=True,
            )
            if run is None:
                raise ResourceNotFoundError("The generation run was not found.")
            if run.status != GenerationStatus.RUNNING.value:
                raise ConflictError("The generation run is already terminal.")
            run.status = command.status.value
            run.validation_report = command.validation_report
            # Use the database clock so the persisted invariant remains valid
            # even when application and PostgreSQL clocks differ slightly.
            run.finished_at = session.scalar(select(func.now()))
        return _generation_run_record(run)

    def publish_generated_package(
        self,
        command: PublishGeneratedPackage,
    ) -> PublishedGeneratedPackage:
        """Stage blobs, then atomically expose a complete version and succeeded run.

        Content-addressed blobs intentionally outlive a rolled-back relational
        transaction. No artifact, version, asset link, current pointer, or run
        success is committed until every staged blob has validated metadata.
        """

        stage: list[PublicationCheckpoint] = ["asset_stage"]
        try:
            staged = tuple(
                (asset, self._stage_pending_asset(asset)) for asset in command.assets
            )
            artifact_id = command.artifact_id or self._id_factory()
            version_id = self._id_factory()
            return self._publish_staged_generated_package(
                command=command,
                staged=staged,
                artifact_id=artifact_id,
                version_id=version_id,
                stage=stage,
            )
        except Exception:
            self._finish_failed_publication_run(command, stage[0])
            raise

    def _publish_staged_generated_package(
        self,
        *,
        command: PublishGeneratedPackage,
        staged: tuple[tuple[PendingArtifactAsset, StoredBlob], ...],
        artifact_id: uuid.UUID,
        version_id: uuid.UUID,
        stage: list[PublicationCheckpoint],
    ) -> PublishedGeneratedPackage:
        with transactional_session(self._session_factory) as session:
            repository = self._repository_factory(session)
            run = repository.get_generation_run(
                command.campaign_id,
                command.generation_run_id,
                for_update=True,
            )
            if run is None:
                raise ResourceNotFoundError("The generation run was not found.")
            if run.status != GenerationStatus.RUNNING.value:
                raise ConflictError(
                    "Only a running generation run can publish a package."
                )

            artifact = repository.get_artifact(
                command.campaign_id, artifact_id, for_update=True
            )
            if artifact is None:
                if command.artifact_id is not None:
                    raise ResourceNotFoundError(
                        "The preparation artifact was not found."
                    )
                artifact = PreparationArtifact(
                    id=artifact_id,
                    campaign_id=command.campaign_id,
                    artifact_type=command.artifact_type.value,
                    title=command.title,
                    lifecycle=ArtifactLifecycle.DRAFT.value,
                    current_version_id=None,
                    visibility_policy=command.visibility_policy.value,
                    created_by=command.created_by,
                )
                repository.add_artifact(artifact)
                repository.add_lifecycle_event(
                    ArtifactLifecycleEvent(
                        id=self._id_factory(),
                        artifact_id=artifact.id,
                        artifact_version_id=None,
                        from_lifecycle=None,
                        to_lifecycle=ArtifactLifecycle.DRAFT.value,
                        actor=command.created_by,
                        reason="Artifact created with complete generated package.",
                    )
                )
            elif artifact.lifecycle == ArtifactLifecycle.RETIRED.value:
                raise ConflictError("A retired artifact cannot receive new versions.")

            stage[0] = "version_creation"
            self._publication_checkpoint(stage[0])
            version_number = repository.next_version_number(artifact.id)
            self._validate_parent(
                repository,
                CreateArtifactVersion(
                    campaign_id=command.campaign_id,
                    artifact_id=artifact.id,
                    parent_version_id=command.parent_version_id,
                    schema_version=command.schema_version,
                    specification=command.specification,
                    validation_report=command.validation_report,
                    change_summary=command.change_summary,
                    input_pins=command.input_pins,
                    generation_run_id=command.generation_run_id,
                    created_by=command.created_by,
                ),
                version_number,
            )
            version = PreparationArtifactVersion(
                id=version_id,
                campaign_id=command.campaign_id,
                artifact_id=artifact.id,
                version_number=version_number,
                parent_version_id=command.parent_version_id,
                schema_version=command.schema_version,
                specification=command.specification,
                specification_sha256=canonical_json_sha256(command.specification),
                validation_report=command.validation_report,
                change_summary=command.change_summary,
                input_campaign_revision_id=command.input_pins.campaign_revision_id,
                input_corpus_snapshot_id=command.input_pins.corpus_snapshot_id,
                input_rules_profile_id=command.input_pins.rules_profile_id,
                input_party_snapshot_id=command.input_pins.party_snapshot_id,
                generation_run_id=run.id,
                created_by=command.created_by,
            )
            repository.add_version(version)
            repository.flush_version(version)
            for pending, blob in staged:
                stage[0] = "asset_link"
                self._publication_checkpoint(stage[0])
                asset = repository.get_or_add_asset(
                    asset_id=self._id_factory(),
                    sha256=blob.sha256,
                    byte_size=blob.byte_size,
                    media_type=pending.media_type,
                    storage_locator=blob.storage_locator,
                )
                if (
                    asset.byte_size != blob.byte_size
                    or asset.storage_locator != blob.storage_locator
                    or asset.media_type != pending.media_type
                ):
                    raise ConflictError(
                        "Stored asset metadata conflicts with its hash."
                    )
                repository.add_artifact_asset(
                    ArtifactAsset(
                        artifact_version_id=version.id,
                        role=pending.role.value,
                        ordinal=pending.ordinal,
                        asset_id=asset.id,
                    )
                )
            stage[0] = "current_version"
            self._publication_checkpoint(stage[0])
            previous_lifecycle = ArtifactLifecycle(artifact.lifecycle)
            artifact.current_version_id = version.id
            if previous_lifecycle is not ArtifactLifecycle.DRAFT:
                artifact.lifecycle = ArtifactLifecycle.DRAFT.value
                repository.add_lifecycle_event(
                    ArtifactLifecycleEvent(
                        id=self._id_factory(),
                        artifact_id=artifact.id,
                        artifact_version_id=version.id,
                        from_lifecycle=previous_lifecycle.value,
                        to_lifecycle=ArtifactLifecycle.DRAFT.value,
                        actor=command.created_by,
                        reason="New immutable artifact version created.",
                    )
                )
            stage[0] = "run_finish"
            self._publication_checkpoint(stage[0])
            run.status = GenerationStatus.SUCCEEDED.value
            run.validation_report = command.validation_report
            run.finished_at = session.scalar(select(func.now()))
            result = PublishedGeneratedPackage(
                artifact=_artifact_record(artifact),
                version=_version_record(version),
                generation_run=_generation_run_record(run),
            )
        return result

    def _stage_pending_asset(self, asset: PendingArtifactAsset) -> StoredBlob:
        self._publication_checkpoint("asset_stage")
        blob = self._asset_store.put_bytes(asset.data)
        if blob.byte_size != len(asset.data):
            raise ConflictError("Staged asset size does not match its input bytes.")
        self._asset_store.verify(blob)
        return blob

    def _publication_checkpoint(self, stage: PublicationCheckpoint) -> None:
        if self._publication_fault_hook is not None:
            self._publication_fault_hook(stage)

    def _finish_failed_publication_run(
        self,
        command: PublishGeneratedPackage,
        stage: PublicationCheckpoint,
    ) -> None:
        try:
            self.finish_generation_run(
                FinishGenerationRun(
                    campaign_id=command.campaign_id,
                    run_id=command.generation_run_id,
                    status=GenerationStatus.FAILED,
                    validation_report={
                        "valid": False,
                        "stage": stage,
                        "diagnostics": [
                            {
                                "code": "preparation.package_publication_failed",
                                "severity": "error",
                            }
                        ],
                    },
                )
            )
        except (ConflictError, ResourceNotFoundError):
            # Preserve the primary storage/transaction error. A successful
            # publication is already terminal; a missing run has no durable
            # state to repair.
            pass

    def create_artifact_version(
        self,
        command: CreateArtifactVersion,
    ) -> ArtifactVersionRecord:
        version_id = self._id_factory()
        pins = command.input_pins
        with transactional_session(self._session_factory) as session:
            repository = self._repository_factory(session)
            artifact = repository.get_artifact(
                command.campaign_id,
                command.artifact_id,
                for_update=True,
            )
            if artifact is None:
                raise ResourceNotFoundError("The preparation artifact was not found.")
            if artifact.lifecycle == ArtifactLifecycle.RETIRED.value:
                raise ConflictError("A retired artifact cannot receive new versions.")
            version_number = repository.next_version_number(artifact.id)
            self._validate_parent(repository, command, version_number)
            if command.generation_run_id is not None:
                run = repository.get_generation_run(
                    command.campaign_id,
                    command.generation_run_id,
                    for_update=False,
                )
                if run is None:
                    raise ResourceNotFoundError("The generation run was not found.")
                if run.status != GenerationStatus.SUCCEEDED.value:
                    raise ConflictError(
                        "Only a succeeded generation run can produce a version."
                    )
            version = PreparationArtifactVersion(
                id=version_id,
                campaign_id=command.campaign_id,
                artifact_id=artifact.id,
                version_number=version_number,
                parent_version_id=command.parent_version_id,
                schema_version=command.schema_version,
                specification=command.specification,
                specification_sha256=canonical_json_sha256(command.specification),
                validation_report=command.validation_report,
                change_summary=command.change_summary,
                input_campaign_revision_id=pins.campaign_revision_id,
                input_corpus_snapshot_id=pins.corpus_snapshot_id,
                input_rules_profile_id=pins.rules_profile_id,
                input_party_snapshot_id=pins.party_snapshot_id,
                generation_run_id=command.generation_run_id,
                created_by=command.created_by,
            )
            repository.add_version(version)
            repository.flush_version(version)
            previous_lifecycle = ArtifactLifecycle(artifact.lifecycle)
            artifact.current_version_id = version.id
            if previous_lifecycle is not ArtifactLifecycle.DRAFT:
                artifact.lifecycle = ArtifactLifecycle.DRAFT.value
                repository.add_lifecycle_event(
                    ArtifactLifecycleEvent(
                        id=self._id_factory(),
                        artifact_id=artifact.id,
                        artifact_version_id=version.id,
                        from_lifecycle=previous_lifecycle.value,
                        to_lifecycle=ArtifactLifecycle.DRAFT.value,
                        actor=command.created_by,
                        reason="New immutable artifact version created.",
                    )
                )
        return _version_record(version)

    def attach_asset(self, command: AttachArtifactAsset) -> AssetRecord:
        with transactional_session(self._session_factory) as session:
            repository = self._repository_factory(session)
            version = repository.get_version(
                command.campaign_id,
                command.artifact_version_id,
            )
            if version is None:
                raise ResourceNotFoundError("The artifact version was not found.")
            artifact = repository.get_artifact(
                command.campaign_id,
                version.artifact_id,
                for_update=True,
            )
            if (
                artifact is None
                or artifact.lifecycle != ArtifactLifecycle.DRAFT.value
                or artifact.current_version_id != version.id
            ):
                raise ConflictError(
                    "Assets can be attached only to the current draft version."
                )
            blob = self._asset_store.put_bytes(command.data)
            asset = repository.get_or_add_asset(
                asset_id=self._id_factory(),
                sha256=blob.sha256,
                byte_size=blob.byte_size,
                media_type=command.media_type,
                storage_locator=blob.storage_locator,
            )
            if (
                asset.byte_size != blob.byte_size
                or asset.storage_locator != blob.storage_locator
                or asset.media_type != command.media_type
            ):
                raise ConflictError("Stored asset metadata conflicts with its hash.")
            existing = repository.get_artifact_asset(
                version.id,
                command.role.value,
                command.ordinal,
            )
            if existing is not None:
                if existing.asset_id != asset.id:
                    raise ConflictError("The artifact asset role is already assigned.")
                return _asset_record(asset)
            repository.add_artifact_asset(
                ArtifactAsset(
                    artifact_version_id=version.id,
                    role=command.role.value,
                    ordinal=command.ordinal,
                    asset_id=asset.id,
                )
            )
        return _asset_record(asset)

    def transition_artifact(self, command: TransitionArtifact) -> ArtifactRecord:
        with transactional_session(self._session_factory) as session:
            repository = self._repository_factory(session)
            artifact = repository.get_artifact(
                command.campaign_id,
                command.artifact_id,
                for_update=True,
            )
            if artifact is None:
                raise ResourceNotFoundError("The preparation artifact was not found.")
            current = ArtifactLifecycle(artifact.lifecycle)
            if current is command.target:
                if (
                    command.artifact_version_id is not None
                    and command.artifact_version_id != artifact.current_version_id
                ):
                    raise ConflictError(
                        "Lifecycle version must be the current version."
                    )
                if (
                    command.target is ArtifactLifecycle.APPROVED_FOR_PLAY
                    and command.artifact_version_id is None
                ):
                    raise ConflictError("Approval requires an artifact version.")
                return _artifact_record(artifact)
            if command.target not in _ALLOWED_TRANSITIONS[current]:
                raise ConflictError("The preparation lifecycle transition is invalid.")
            selected_version_id = artifact.current_version_id
            if command.target is ArtifactLifecycle.APPROVED_FOR_PLAY:
                if command.artifact_version_id is None:
                    raise ConflictError("Approval requires an artifact version.")
                version = repository.get_version(
                    command.campaign_id,
                    command.artifact_version_id,
                )
                if version is None or version.artifact_id != artifact.id:
                    raise ResourceNotFoundError("The artifact version was not found.")
                if version.validation_report.get("valid") is not True:
                    raise ConflictError(
                        "Only a valid artifact version can be approved."
                    )
                selected_version_id = version.id
                artifact.current_version_id = version.id
            elif command.artifact_version_id is not None:
                if command.artifact_version_id != artifact.current_version_id:
                    raise ConflictError(
                        "Lifecycle version must be the current version."
                    )
                selected_version_id = command.artifact_version_id
            if selected_version_id is None:
                raise ConflictError("Lifecycle transition requires a current version.")
            artifact.lifecycle = command.target.value
            repository.add_lifecycle_event(
                ArtifactLifecycleEvent(
                    id=self._id_factory(),
                    artifact_id=artifact.id,
                    artifact_version_id=selected_version_id,
                    from_lifecycle=current.value,
                    to_lifecycle=command.target.value,
                    actor=command.actor,
                    reason=command.reason,
                )
            )
        return _artifact_record(artifact)

    @staticmethod
    def _validate_parent(
        repository: PreparationRepository,
        command: CreateArtifactVersion,
        version_number: int,
    ) -> None:
        if version_number == 1:
            if command.parent_version_id is not None:
                raise ConflictError("The first artifact version cannot have a parent.")
            return
        if command.parent_version_id is None:
            raise ConflictError("Later artifact versions require parent lineage.")
        parent = repository.get_version(
            command.campaign_id,
            command.parent_version_id,
        )
        if parent is None or parent.artifact_id != command.artifact_id:
            raise ResourceNotFoundError("The parent artifact version was not found.")


def _artifact_record(artifact: PreparationArtifact) -> ArtifactRecord:
    return ArtifactRecord(
        id=artifact.id,
        campaign_id=artifact.campaign_id,
        artifact_type=ArtifactType(artifact.artifact_type),
        title=artifact.title,
        lifecycle=ArtifactLifecycle(artifact.lifecycle),
        current_version_id=artifact.current_version_id,
        visibility_policy=VisibilityPolicy(artifact.visibility_policy),
    )


def _version_record(version: PreparationArtifactVersion) -> ArtifactVersionRecord:
    return ArtifactVersionRecord(
        id=version.id,
        campaign_id=version.campaign_id,
        artifact_id=version.artifact_id,
        version_number=version.version_number,
        parent_version_id=version.parent_version_id,
        schema_version=version.schema_version,
        specification_sha256=version.specification_sha256,
        change_summary=version.change_summary,
        generation_run_id=version.generation_run_id,
    )


def _version_snapshot(version: PreparationArtifactVersion) -> ArtifactVersionSnapshot:
    return ArtifactVersionSnapshot(
        id=version.id,
        campaign_id=version.campaign_id,
        artifact_id=version.artifact_id,
        version_number=version.version_number,
        parent_version_id=version.parent_version_id,
        schema_version=version.schema_version,
        specification=version.specification,
        specification_sha256=version.specification_sha256,
        validation_report=version.validation_report,
        change_summary=version.change_summary,
        input_pins=InputPins(
            campaign_revision_id=version.input_campaign_revision_id,
            corpus_snapshot_id=version.input_corpus_snapshot_id,
            rules_profile_id=version.input_rules_profile_id,
            party_snapshot_id=version.input_party_snapshot_id,
        ),
        generation_run_id=version.generation_run_id,
        created_by=version.created_by,
    )


def _generation_run_snapshot(run: GenerationRun) -> GenerationRunSnapshot:
    return GenerationRunSnapshot(
        id=run.id,
        campaign_id=run.campaign_id,
        generation_kind=run.generation_kind,
        seed=run.seed,
        input_scope=run.input_scope,
        input_pins=InputPins(
            campaign_revision_id=run.input_campaign_revision_id,
            corpus_snapshot_id=run.input_corpus_snapshot_id,
            rules_profile_id=run.input_rules_profile_id,
            party_snapshot_id=run.input_party_snapshot_id,
        ),
        context_envelope_kind=run.context_envelope_kind,
        context_payload_version=run.context_payload_version,
        context_payload_sha256=run.context_payload_sha256,
        context_source_links=tuple(run.context_source_links),
        schema_versions=run.schema_versions,
        generator_versions=run.generator_versions,
        renderer_versions=run.renderer_versions,
        model_task_profile_id=run.model_task_profile_id,
        model_run_ids=tuple(uuid.UUID(item) for item in run.model_run_ids),
        tool_runs=tuple(run.tool_runs),
        validation_report=run.validation_report,
        status=GenerationStatus(run.status),
    )


def _generation_run_record(run: GenerationRun) -> GenerationRunRecord:
    return GenerationRunRecord(
        id=run.id,
        campaign_id=run.campaign_id,
        generation_kind=run.generation_kind,
        status=GenerationStatus(run.status),
    )


def _asset_record(asset: GeneratedAsset) -> AssetRecord:
    return AssetRecord(
        id=asset.id,
        sha256=asset.sha256,
        byte_size=asset.byte_size,
        media_type=asset.media_type,
        storage_locator=asset.storage_locator,
    )
