"""Preparation repository port and synchronous SQLAlchemy implementation."""

import uuid
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from dm_assistant.modules.preparation.models import (
    ArtifactAsset,
    ArtifactLifecycleEvent,
    GeneratedAsset,
    GenerationRun,
    PreparationArtifact,
    PreparationArtifactVersion,
)


class PreparationRepository(Protocol):
    """Persistence operations required by preparation application services."""

    def add_artifact(self, artifact: PreparationArtifact) -> None: ...

    def list_artifacts(
        self, campaign_id: uuid.UUID
    ) -> tuple[PreparationArtifact, ...]: ...

    def get_artifact(
        self, campaign_id: uuid.UUID, artifact_id: uuid.UUID, *, for_update: bool
    ) -> PreparationArtifact | None: ...

    def add_lifecycle_event(self, event: ArtifactLifecycleEvent) -> None: ...

    def add_generation_run(self, run: GenerationRun) -> None: ...

    def get_generation_run(
        self, campaign_id: uuid.UUID, run_id: uuid.UUID, *, for_update: bool
    ) -> GenerationRun | None: ...

    def get_version(
        self, campaign_id: uuid.UUID, version_id: uuid.UUID
    ) -> PreparationArtifactVersion | None: ...

    def list_versions(
        self, campaign_id: uuid.UUID, artifact_id: uuid.UUID
    ) -> tuple[PreparationArtifactVersion, ...]: ...

    def list_artifact_assets(
        self, campaign_id: uuid.UUID, artifact_version_id: uuid.UUID
    ) -> tuple[tuple[ArtifactAsset, GeneratedAsset], ...]: ...

    def get_asset_for_campaign(
        self, campaign_id: uuid.UUID, asset_id: uuid.UUID
    ) -> GeneratedAsset | None: ...

    def next_version_number(self, artifact_id: uuid.UUID) -> int: ...

    def add_version(self, version: PreparationArtifactVersion) -> None: ...

    def flush_version(self, version: PreparationArtifactVersion) -> None: ...

    def get_or_add_asset(
        self,
        *,
        asset_id: uuid.UUID,
        sha256: str,
        byte_size: int,
        media_type: str,
        storage_locator: str,
    ) -> GeneratedAsset: ...

    def get_artifact_asset(
        self,
        artifact_version_id: uuid.UUID,
        role: str,
        ordinal: int,
    ) -> ArtifactAsset | None: ...

    def add_artifact_asset(self, artifact_asset: ArtifactAsset) -> None: ...


class SqlAlchemyPreparationRepository:
    """PostgreSQL repository; transaction ownership stays with the service."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add_artifact(self, artifact: PreparationArtifact) -> None:
        self._session.add(artifact)
        self._session.flush([artifact])

    def list_artifacts(self, campaign_id: uuid.UUID) -> tuple[PreparationArtifact, ...]:
        return tuple(
            self._session.scalars(
                select(PreparationArtifact)
                .where(PreparationArtifact.campaign_id == campaign_id)
                .order_by(PreparationArtifact.created_at, PreparationArtifact.id)
            )
        )

    def get_artifact(
        self,
        campaign_id: uuid.UUID,
        artifact_id: uuid.UUID,
        *,
        for_update: bool,
    ) -> PreparationArtifact | None:
        statement = select(PreparationArtifact).where(
            PreparationArtifact.campaign_id == campaign_id,
            PreparationArtifact.id == artifact_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def add_lifecycle_event(self, event: ArtifactLifecycleEvent) -> None:
        self._session.add(event)

    def add_generation_run(self, run: GenerationRun) -> None:
        self._session.add(run)
        self._session.flush([run])

    def get_generation_run(
        self,
        campaign_id: uuid.UUID,
        run_id: uuid.UUID,
        *,
        for_update: bool,
    ) -> GenerationRun | None:
        statement = select(GenerationRun).where(
            GenerationRun.campaign_id == campaign_id,
            GenerationRun.id == run_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def get_version(
        self,
        campaign_id: uuid.UUID,
        version_id: uuid.UUID,
    ) -> PreparationArtifactVersion | None:
        return self._session.scalar(
            select(PreparationArtifactVersion).where(
                PreparationArtifactVersion.campaign_id == campaign_id,
                PreparationArtifactVersion.id == version_id,
            )
        )

    def list_versions(
        self,
        campaign_id: uuid.UUID,
        artifact_id: uuid.UUID,
    ) -> tuple[PreparationArtifactVersion, ...]:
        return tuple(
            self._session.scalars(
                select(PreparationArtifactVersion)
                .where(
                    PreparationArtifactVersion.campaign_id == campaign_id,
                    PreparationArtifactVersion.artifact_id == artifact_id,
                )
                .order_by(PreparationArtifactVersion.version_number)
            )
        )

    def list_artifact_assets(
        self,
        campaign_id: uuid.UUID,
        artifact_version_id: uuid.UUID,
    ) -> tuple[tuple[ArtifactAsset, GeneratedAsset], ...]:
        rows = self._session.execute(
            select(ArtifactAsset, GeneratedAsset)
            .join(GeneratedAsset, GeneratedAsset.id == ArtifactAsset.asset_id)
            .join(
                PreparationArtifactVersion,
                PreparationArtifactVersion.id == ArtifactAsset.artifact_version_id,
            )
            .where(
                PreparationArtifactVersion.campaign_id == campaign_id,
                ArtifactAsset.artifact_version_id == artifact_version_id,
            )
            .order_by(ArtifactAsset.role, ArtifactAsset.ordinal)
        )
        return tuple((row[0], row[1]) for row in rows)

    def get_asset_for_campaign(
        self,
        campaign_id: uuid.UUID,
        asset_id: uuid.UUID,
    ) -> GeneratedAsset | None:
        return self._session.scalar(
            select(GeneratedAsset)
            .join(ArtifactAsset, ArtifactAsset.asset_id == GeneratedAsset.id)
            .join(
                PreparationArtifactVersion,
                PreparationArtifactVersion.id == ArtifactAsset.artifact_version_id,
            )
            .where(
                PreparationArtifactVersion.campaign_id == campaign_id,
                GeneratedAsset.id == asset_id,
            )
            .limit(1)
        )

    def next_version_number(self, artifact_id: uuid.UUID) -> int:
        current = self._session.scalar(
            select(func.max(PreparationArtifactVersion.version_number)).where(
                PreparationArtifactVersion.artifact_id == artifact_id
            )
        )
        return int(current or 0) + 1

    def add_version(self, version: PreparationArtifactVersion) -> None:
        self._session.add(version)

    def flush_version(self, version: PreparationArtifactVersion) -> None:
        self._session.flush([version])

    def get_or_add_asset(
        self,
        *,
        asset_id: uuid.UUID,
        sha256: str,
        byte_size: int,
        media_type: str,
        storage_locator: str,
    ) -> GeneratedAsset:
        statement = (
            insert(GeneratedAsset)
            .values(
                id=asset_id,
                sha256=sha256,
                byte_size=byte_size,
                media_type=media_type,
                storage_locator=storage_locator,
            )
            .on_conflict_do_nothing(index_elements=[GeneratedAsset.sha256])
        )
        self._session.execute(statement)
        asset = self._session.scalar(
            select(GeneratedAsset).where(GeneratedAsset.sha256 == sha256)
        )
        if asset is None:
            raise RuntimeError("asset upsert did not produce a row")
        return asset

    def get_artifact_asset(
        self,
        artifact_version_id: uuid.UUID,
        role: str,
        ordinal: int,
    ) -> ArtifactAsset | None:
        return self._session.get(
            ArtifactAsset,
            {
                "artifact_version_id": artifact_version_id,
                "role": role,
                "ordinal": ordinal,
            },
        )

    def add_artifact_asset(self, artifact_asset: ArtifactAsset) -> None:
        self._session.add(artifact_asset)
