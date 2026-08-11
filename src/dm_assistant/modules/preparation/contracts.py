"""Strict preparation lifecycle, version, run, and asset contracts."""

import hashlib
import json
from enum import StrEnum
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    model_validator,
)

Sha256Hex = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
Slug = Annotated[
    str,
    StringConstraints(min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9_]*$"),
]
VersionText = Annotated[
    str,
    StringConstraints(
        min_length=1, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9._+-]*$"
    ),
]
ShortText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]
SummaryText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
]
MediaType = Annotated[
    str,
    StringConstraints(
        min_length=3,
        max_length=127,
        pattern=r"^[a-z0-9][a-z0-9!#$&^_.+-]+/[a-z0-9][a-z0-9!#$&^_.+-]+$",
    ),
]


class ContractModel(BaseModel):
    """Strict immutable application contract baseline."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ArtifactType(StrEnum):
    DUNGEON = "dungeon"
    MAP_PACKAGE = "map_package"
    ENCOUNTER = "encounter"
    PUZZLE = "puzzle"
    GENERATED_CREATURE = "generated_creature"
    OTHER = "other"


class ArtifactLifecycle(StrEnum):
    DRAFT = "draft"
    APPROVED_FOR_PLAY = "approved_for_play"
    USED = "used"
    RETIRED = "retired"


class VisibilityPolicy(StrEnum):
    DM_ONLY = "dm_only"
    ALL_CAMPAIGN_PLAYERS = "all_campaign_players"
    EXPLICIT_AUDIENCE = "explicit_audience"
    PUBLIC = "public"


class GenerationStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ArtifactAssetRole(StrEnum):
    SPECIFICATION = "specification"
    VALIDATION_REPORT = "validation_report"
    DM_SVG = "dm_svg"
    PLAYER_SVG = "player_svg"
    DM_PNG = "dm_png"
    PLAYER_PNG = "player_png"
    PRINT_PDF = "print_pdf"
    DM_PRINT_PDF = "dm_print_pdf"
    PLAYER_PRINT_PDF = "player_print_pdf"
    ROLL20_BUNDLE = "roll20_bundle"
    DM_ROLL20_BUNDLE = "dm_roll20_bundle"
    PLAYER_ROLL20_BUNDLE = "player_roll20_bundle"
    MANIFEST = "manifest"
    OTHER = "other"


class InputPins(ContractModel):
    """Opaque snapshots that preparation consumed without claiming ownership."""

    campaign_revision_id: UUID | None = None
    corpus_snapshot_id: UUID | None = None
    rules_profile_id: UUID | None = None
    party_snapshot_id: UUID | None = None


class ContextSourceLink(ContractModel):
    """One source link captured by a generation-context envelope."""

    source_kind: Slug
    source_id: str = Field(min_length=1, max_length=200)
    revision_id: str | None = Field(default=None, min_length=1, max_length=200)
    sha256: Sha256Hex | None = None


class GenerationContextPin(ContractModel):
    """Pinned common envelope bytes plus named strict domain payload identity."""

    envelope_kind: Slug
    payload_version: VersionText
    envelope: dict[str, JsonValue]
    payload_sha256: Sha256Hex
    source_links: tuple[ContextSourceLink, ...] = ()

    @model_validator(mode="after")
    def verify_payload_hash(self) -> Self:
        if "payload" not in self.envelope:
            raise ValueError("generation context envelope requires a payload")
        actual = canonical_json_sha256(self.envelope["payload"])
        if actual != self.payload_sha256:
            raise ValueError("generation context payload hash does not match payload")
        return self


class ToolRunPin(ContractModel):
    """Immutable identity of one bounded deterministic/model tool invocation."""

    tool_name: Slug
    schema_version: VersionText
    input_sha256: Sha256Hex
    output_sha256: Sha256Hex | None = None
    status: Literal["succeeded", "failed"]


class CreateArtifact(ContractModel):
    campaign_id: UUID
    artifact_type: ArtifactType
    title: ShortText
    visibility_policy: VisibilityPolicy = VisibilityPolicy.DM_ONLY
    created_by: ShortText


class StartGenerationRun(ContractModel):
    campaign_id: UUID
    generation_kind: Slug
    seed: int | None = Field(default=None, ge=-(2**63), le=2**63 - 1)
    input_scope: dict[str, JsonValue]
    input_pins: InputPins = InputPins()
    context: GenerationContextPin | None = None
    schema_versions: dict[Slug, VersionText] = Field(min_length=1)
    generator_versions: dict[Slug, VersionText] = Field(default_factory=dict)
    renderer_versions: dict[Slug, VersionText] = Field(default_factory=dict)
    model_task_profile_id: UUID | None = None
    model_run_ids: tuple[UUID, ...] = ()
    tool_runs: tuple[ToolRunPin, ...] = ()


class FinishGenerationRun(ContractModel):
    campaign_id: UUID
    run_id: UUID
    status: Literal[
        GenerationStatus.SUCCEEDED,
        GenerationStatus.FAILED,
        GenerationStatus.CANCELLED,
    ]
    validation_report: dict[str, JsonValue]


class CreateArtifactVersion(ContractModel):
    campaign_id: UUID
    artifact_id: UUID
    parent_version_id: UUID | None = None
    schema_version: VersionText
    specification: dict[str, JsonValue]
    validation_report: dict[str, JsonValue]
    change_summary: SummaryText
    input_pins: InputPins = InputPins()
    generation_run_id: UUID | None = None
    created_by: ShortText


class AttachArtifactAsset(ContractModel):
    campaign_id: UUID
    artifact_version_id: UUID
    role: ArtifactAssetRole
    ordinal: int = Field(default=0, ge=0, le=32767)
    media_type: MediaType
    data: bytes


class TransitionArtifact(ContractModel):
    campaign_id: UUID
    artifact_id: UUID
    target: ArtifactLifecycle
    actor: ShortText
    reason: SummaryText
    artifact_version_id: UUID | None = None


class ArtifactRecord(ContractModel):
    id: UUID
    campaign_id: UUID
    artifact_type: ArtifactType
    title: str
    lifecycle: ArtifactLifecycle
    current_version_id: UUID | None
    visibility_policy: VisibilityPolicy


class ArtifactVersionRecord(ContractModel):
    id: UUID
    campaign_id: UUID
    artifact_id: UUID
    version_number: int
    parent_version_id: UUID | None
    schema_version: str
    specification_sha256: Sha256Hex
    change_summary: str
    generation_run_id: UUID | None


class ArtifactVersionSnapshot(ContractModel):
    id: UUID
    campaign_id: UUID
    artifact_id: UUID
    version_number: int
    parent_version_id: UUID | None
    schema_version: str
    specification: dict[str, JsonValue]
    specification_sha256: Sha256Hex
    validation_report: dict[str, JsonValue]
    change_summary: str
    input_pins: InputPins
    generation_run_id: UUID | None
    created_by: str


class ArtifactAssetRecord(ContractModel):
    artifact_version_id: UUID
    role: ArtifactAssetRole
    ordinal: int
    asset_id: UUID
    sha256: Sha256Hex
    byte_size: int
    media_type: str
    storage_locator: str


class GenerationRunRecord(ContractModel):
    id: UUID
    campaign_id: UUID
    generation_kind: str
    status: GenerationStatus


class GenerationRunSnapshot(ContractModel):
    id: UUID
    campaign_id: UUID
    generation_kind: str
    seed: int | None
    input_scope: dict[str, JsonValue]
    input_pins: InputPins
    context_envelope_kind: str | None
    context_payload_version: str | None
    context_payload_sha256: Sha256Hex | None
    context_source_links: tuple[dict[str, JsonValue], ...]
    schema_versions: dict[str, str]
    generator_versions: dict[str, str]
    renderer_versions: dict[str, str]
    model_task_profile_id: UUID | None
    model_run_ids: tuple[UUID, ...]
    tool_runs: tuple[dict[str, JsonValue], ...]
    validation_report: dict[str, JsonValue]
    status: GenerationStatus


class AssetRecord(ContractModel):
    id: UUID
    sha256: Sha256Hex
    byte_size: int
    media_type: str
    storage_locator: str


def canonical_json_sha256(value: JsonValue | dict[str, JsonValue]) -> str:
    """Hash the strict canonical JSON representation persisted as JSONB."""
    document = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(document.encode("utf-8")).hexdigest()
