"""Provider-independent Dungeon Studio orchestration over pure and prep boundaries."""

import json
import uuid
from dataclasses import dataclass
from typing import Literal

from pydantic import JsonValue, ValidationError

import dm_dungeon
from dm_assistant.errors import ConflictError, DungeonPrintExportDisabledError
from dm_assistant.modules.preparation import (
    ArtifactAssetRole,
    ArtifactLifecycle,
    ArtifactRecord,
    ArtifactType,
    AttachArtifactAsset,
    FinishGenerationRun,
    GenerationContextEnvelope,
    GenerationContextPin,
    GenerationStatus,
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
from dm_assistant.observability import bind_log_context, get_logger
from dm_assistant.orchestration.dungeons.contracts import (
    DUNGEON_EXPLORATION_ENRICHMENT_SCHEMA_VERSION,
    DUNGEON_FEATURE_INTERACTION_ENRICHMENT_SCHEMA_VERSION,
    DUNGEON_GENERATION_PROPOSAL_SCHEMA_VERSION,
    DUNGEON_OBJECTIVE_ENRICHMENT_SCHEMA_VERSION,
    DUNGEON_PUZZLE_ENRICHMENT_SCHEMA_VERSION,
    DUNGEON_ROOM_NARRATIVE_ENRICHMENT_SCHEMA_VERSION,
    DUNGEON_TRAP_ENRICHMENT_SCHEMA_VERSION,
    CreateDungeonWorkflow,
    CreatePromptedDungeonExplorationWorkflow,
    CreatePromptedDungeonFeatureInteractionWorkflow,
    CreatePromptedDungeonObjectiveWorkflow,
    CreatePromptedDungeonPuzzleWorkflow,
    CreatePromptedDungeonRoomNarrativeWorkflow,
    CreatePromptedDungeonTrapWorkflow,
    CreatePromptedDungeonWorkflow,
    DungeonDmGuide,
    DungeonDmNotes,
    DungeonExplorationAffordance,
    DungeonExplorationAffordanceApproval,
    DungeonExplorationContextSelection,
    DungeonExplorationEnrichmentInput,
    DungeonExplorationEnrichmentIssue,
    DungeonExplorationEnrichmentOutput,
    DungeonExplorationEnrichmentValidationResult,
    DungeonExplorationRoomContext,
    DungeonFeatureInteractionContextSelection,
    DungeonFeatureInteractionEnrichmentInput,
    DungeonFeatureInteractionEnrichmentOutput,
    DungeonFeatureInteractionFeature,
    DungeonFeatureInteractionIssue,
    DungeonFeatureInteractionRoomContext,
    DungeonFeatureInteractionValidationResult,
    DungeonGenerationRegressionCase,
    DungeonGuideConnection,
    DungeonGuideContentEntry,
    DungeonGuideContentIssue,
    DungeonGuideContentPlan,
    DungeonGuideContentValidationResult,
    DungeonGuideDependency,
    DungeonGuideEncounterContent,
    DungeonGuideFeature,
    DungeonGuideFeatureContent,
    DungeonGuideGateContent,
    DungeonGuideMapReference,
    DungeonGuideObjective,
    DungeonGuideObjectiveContent,
    DungeonGuidePlayerChoice,
    DungeonGuidePuzzle,
    DungeonGuidePuzzleContent,
    DungeonGuideRoom,
    DungeonGuideRoomNarrative,
    DungeonGuideRunnableContent,
    DungeonGuideTrap,
    DungeonObjectiveAcceptedMechanic,
    DungeonObjectiveContextSelection,
    DungeonObjectiveCurrentResolution,
    DungeonObjectiveEnrichmentInput,
    DungeonObjectiveEnrichmentOutput,
    DungeonObjectiveIssue,
    DungeonObjectiveRoomContext,
    DungeonObjectiveTarget,
    DungeonObjectiveValidationResult,
    DungeonPreparationReadiness,
    DungeonPreparationReadinessDiagnostic,
    DungeonPrintCapability,
    DungeonPuzzleClueApproval,
    DungeonPuzzleClueLocation,
    DungeonPuzzleContextSelection,
    DungeonPuzzleDependencyApproval,
    DungeonPuzzleDependencyRelationship,
    DungeonPuzzleEnrichmentInput,
    DungeonPuzzleEnrichmentIssue,
    DungeonPuzzleEnrichmentOutput,
    DungeonPuzzleEnrichmentValidationResult,
    DungeonPuzzleObjectiveApproval,
    DungeonPuzzleObjectiveRelationship,
    DungeonPuzzleRoomContext,
    DungeonRoomDmNote,
    DungeonRoomNarrativeAcceptedMechanic,
    DungeonRoomNarrativeContextSelection,
    DungeonRoomNarrativeEnrichmentInput,
    DungeonRoomNarrativeEnrichmentOutput,
    DungeonRoomNarrativeIssue,
    DungeonRoomNarrativeRoomContext,
    DungeonRoomNarrativeValidationResult,
    DungeonStudioDetail,
    DungeonStudioSpecification,
    DungeonTrapContextSelection,
    DungeonTrapEnrichmentInput,
    DungeonTrapEnrichmentOutput,
    DungeonTrapIssue,
    DungeonTrapMechanic,
    DungeonTrapRoomContext,
    DungeonTrapValidationResult,
    DungeonVersionComparison,
    DungeonWorkflowResult,
    ExportDungeonWorkflow,
    PromptDungeonExplorationWorkflow,
    PromptDungeonFeatureInteractionWorkflow,
    PromptDungeonObjectiveWorkflow,
    PromptDungeonPuzzleWorkflow,
    PromptDungeonRoomNarrativeWorkflow,
    PromptDungeonTrapWorkflow,
    PromptedDungeonModelLineage,
    RegenerateDungeonWorkflow,
)
from dm_dungeon import (
    DoorMechanics,
    DungeonPackage,
    DungeonPlan,
    LayoutRequest,
    LockedLayoutComponents,
    PngExportRequest,
    RenderAudience,
    RoomMechanicMarkerKind,
    SvgRenderRequest,
    SvgThemeName,
    build_map_key,
    compile_dungeon_plan,
    export_png,
    generate_layout,
    render_svg,
    to_canonical_json,
    validate_geometry,
    validate_topology,
)
from dm_dungeon.contracts import (
    DUNGEON_PACKAGE_SCHEMA_VERSION,
    EncounterSlotIntent,
    EndpointDoorKind,
    RoomRole,
    VerticalEndpointSide,
)
from dm_dungeon.export import (
    PDF_EXPORTER_VERSION,
    PNG_EXPORTER_VERSION,
    ROLL20_EXPORTER_VERSION,
    Roll20Artifact,
    Roll20ExportRequest,
    export_roll20_bundle,
)
from dm_dungeon.rendering import SVG_RENDERER_VERSION

_STUDIO_SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"
_VERSION_SCHEMA = "dungeon-studio-v1"
logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class _PendingAsset:
    role: ArtifactAssetRole
    ordinal: int
    media_type: str
    data: bytes


class DungeonStudioService:
    """Compose deterministic generation and preparation persistence without a model."""

    def __init__(self, preparation: PreparationService) -> None:
        self._preparation = preparation

    def list_artifacts(self, campaign_id: uuid.UUID) -> tuple[ArtifactRecord, ...]:
        return self._preparation.list_artifacts(campaign_id)

    def create(self, command: CreateDungeonWorkflow) -> DungeonWorkflowResult:
        return self._generate_version(
            campaign_id=command.campaign_id,
            artifact_id=None,
            artifact_title=command.title,
            parent_version_id=None,
            request=command.layout_request,
            change_summary="Create deterministic dungeon from hand-authored intent.",
            created_by=command.created_by,
        )

    def create_prompted(
        self,
        command: CreatePromptedDungeonWorkflow,
    ) -> DungeonWorkflowResult:
        """Persist a model-authored intent through the deterministic Studio path."""

        return self._generate_version(
            campaign_id=command.campaign_id,
            artifact_id=None,
            artifact_title=command.title,
            parent_version_id=None,
            request=command.layout_request,
            change_summary="Create deterministic dungeon from model-authored intent.",
            created_by=command.created_by,
            generation_kind="prompted_dungeon_layout",
            context=command.context,
            model_task_profile_id=command.model_task_profile_id,
            model_lineage=command.model_lineage,
            tool_runs=command.tool_runs,
            dm_notes=_build_dm_notes(command.layout_request, command.source_prompt),
        )

    def build_exploration_context(
        self,
        command: PromptDungeonExplorationWorkflow,
    ) -> DungeonExplorationEnrichmentInput:
        """Build one exact exploration context from an immutable structural version."""

        parent = self._preparation.get_version(
            command.campaign_id,
            command.parent_version_id,
        )
        if parent.artifact_id != command.artifact_id:
            raise ConflictError("Parent version does not belong to the artifact.")
        specification = _load_specification(parent.specification)
        return build_dungeon_exploration_enrichment_input(
            specification.package,
            command.selection,
        )

    def enrich_prompted_exploration(
        self,
        command: CreatePromptedDungeonExplorationWorkflow,
    ) -> DungeonWorkflowResult:
        """Publish accepted exploration content without regenerating package geometry."""

        parent = self._preparation.get_version(
            command.campaign_id,
            command.parent_version_id,
        )
        if parent.artifact_id != command.artifact_id:
            raise ConflictError("Parent version does not belong to the artifact.")
        specification = _load_specification(parent.specification)
        plan = _accepted_structural_plan(specification)
        if specification.dm_guide is None:
            raise ConflictError(
                "Exploration enrichment requires an exact structural guide."
            )

        context_document = command.context.model_dump(mode="json")
        context_hash = canonical_json_sha256(context_document)
        context_envelope = GenerationContextEnvelope(
            context_kind="dungeon_exploration_enrichment",
            payload_version=command.context.schema_version,
            visibility_policy=VisibilityPolicy.DM_ONLY,
            payload=context_document,
            payload_sha256=context_hash,
        )
        context_pin = GenerationContextPin(
            envelope_kind=context_envelope.context_kind,
            payload_version=context_envelope.payload_version,
            envelope=context_envelope.model_dump(mode="json"),
            payload_sha256=context_hash,
        )
        run = self._preparation.start_generation_run(
            StartGenerationRun(
                campaign_id=command.campaign_id,
                generation_kind="dungeon_exploration_enrichment",
                seed=specification.layout_request.seed,
                input_scope={
                    "artifact_id": str(command.artifact_id),
                    "parent_version_id": str(command.parent_version_id),
                    "package_id": specification.package.id,
                    "room_id": command.context.room.room_id,
                    "context_sha256": context_hash,
                },
                input_pins=parent.input_pins,
                context=context_pin,
                schema_versions={
                    "dungeon_package": specification.package.schema_version,
                    "dungeon_exploration_enrichment": (
                        DUNGEON_EXPLORATION_ENRICHMENT_SCHEMA_VERSION
                    ),
                    "dungeon_studio": _STUDIO_SCHEMA_VERSION,
                    "model_run": "1.0.0",
                },
                generator_versions={
                    "dungeon_kernel": dm_dungeon.__version__,
                    "layout": specification.layout_request.generator_version,
                    "exploration_guide_projection": "exploration-guide-projection-v1",
                },
                renderer_versions={
                    "svg": SVG_RENDERER_VERSION,
                    "png": PNG_EXPORTER_VERSION,
                    "pdf": PDF_EXPORTER_VERSION,
                    "roll20": ROLL20_EXPORTER_VERSION,
                },
                model_task_profile_id=command.model_task_profile_id,
                model_run_ids=(command.model_lineage.model_run_id,),
                tool_runs=command.tool_runs,
            )
        )

        try:
            guide = project_dungeon_exploration_enrichment(
                specification.dm_guide,
                plan=plan,
                package=specification.package,
                context=command.context,
                validation=command.validation,
            )
            readiness = _build_preparation_readiness(guide)
            topology_report = validate_topology(specification.package.topology)
            geometry_report = validate_geometry(specification.package)
            valid = topology_report.valid and geometry_report.valid
            validation_report: dict[str, JsonValue] = {
                "valid": valid,
                "stage": "completed" if valid else "validation",
                "topology": topology_report.model_dump(mode="json"),
                "geometry": geometry_report.model_dump(mode="json"),
                "exploration_enrichment": {
                    "accepted": True,
                    "package_id": command.context.package_id,
                    "room_id": command.context.room.room_id,
                    "context_sha256": context_hash,
                },
            }
            if readiness is not None:
                validation_report["preparation_readiness"] = readiness.model_dump(
                    mode="json"
                )
            if not valid:
                self._preparation.finish_generation_run(
                    FinishGenerationRun(
                        campaign_id=command.campaign_id,
                        run_id=run.id,
                        status=GenerationStatus.FAILED,
                        validation_report=validation_report,
                    )
                )
                diagnostics = tuple(
                    item.model_dump(mode="json")
                    for item in (
                        *topology_report.diagnostics,
                        *geometry_report.diagnostics,
                    )
                )
                return DungeonWorkflowResult(
                    success=False,
                    artifact_id=command.artifact_id,
                    artifact_version_id=None,
                    generation_run_id=run.id,
                    diagnostics=diagnostics,
                )

            enriched_specification = specification.model_copy(
                update={
                    "dm_guide": guide,
                    "preparation_readiness": readiness,
                    "exploration_model_lineage": (
                        *specification.exploration_model_lineage,
                        command.model_lineage,
                    ),
                }
            )
            resolved_notes = _resolved_dm_notes(enriched_specification)
            preview_assets = _preview_assets(
                enriched_specification.package,
                resolved_notes,
            )
            base_assets = (
                _PendingAsset(
                    ArtifactAssetRole.SPECIFICATION,
                    0,
                    "application/json",
                    _canonical_json_bytes(
                        enriched_specification.model_dump(mode="json")
                    ),
                ),
                _PendingAsset(
                    ArtifactAssetRole.VALIDATION_REPORT,
                    0,
                    "application/json",
                    _canonical_json_bytes(validation_report),
                ),
                _dm_notes_asset(
                    enriched_specification.layout_request,
                    resolved_notes,
                    guide,
                ),
            )
            artifact = self._preparation.get_artifact(
                command.campaign_id,
                command.artifact_id,
            )
            published = self._preparation.publish_generated_package(
                PublishGeneratedPackage(
                    campaign_id=command.campaign_id,
                    generation_run_id=run.id,
                    artifact_id=command.artifact_id,
                    artifact_type=ArtifactType.DUNGEON,
                    title=artifact.title,
                    visibility_policy=artifact.visibility_policy,
                    parent_version_id=command.parent_version_id,
                    schema_version=_VERSION_SCHEMA,
                    specification=enriched_specification.model_dump(mode="json"),
                    validation_report=validation_report,
                    change_summary="Add independently generated exact-room exploration content.",
                    input_pins=parent.input_pins,
                    created_by=command.created_by,
                    assets=tuple(
                        PendingArtifactAsset(
                            role=asset.role,
                            ordinal=asset.ordinal,
                            media_type=asset.media_type,
                            data=asset.data,
                        )
                        for asset in (*base_assets, *preview_assets)
                    ),
                    required_assets=tuple(
                        RequiredArtifactAsset(role=asset.role, ordinal=asset.ordinal)
                        for asset in (*base_assets, *preview_assets)
                    ),
                )
            )
        except Exception:
            if (
                self._preparation.get_generation_run(command.campaign_id, run.id).status
                is GenerationStatus.RUNNING
            ):
                self._preparation.finish_generation_run(
                    FinishGenerationRun(
                        campaign_id=command.campaign_id,
                        run_id=run.id,
                        status=GenerationStatus.FAILED,
                        validation_report={
                            "valid": False,
                            "stage": "projection",
                            "diagnostics": [
                                {
                                    "code": "exploration_enrichment.projection_failed",
                                    "message": "Exploration projection or publication failed.",
                                }
                            ],
                        },
                    )
                )
            raise
        return DungeonWorkflowResult(
            success=True,
            artifact_id=published.artifact.id,
            artifact_version_id=published.version.id,
            generation_run_id=run.id,
            diagnostics=(),
        )

    def build_feature_interaction_context(
        self,
        command: PromptDungeonFeatureInteractionWorkflow,
    ) -> DungeonFeatureInteractionEnrichmentInput:
        """Build one exact feature interaction context from an immutable structural version."""

        parent = self._preparation.get_version(
            command.campaign_id,
            command.parent_version_id,
        )
        if parent.artifact_id != command.artifact_id:
            raise ConflictError("Parent version does not belong to the artifact.")
        specification = _load_specification(parent.specification)
        if specification.dm_guide is None:
            raise ConflictError(
                "Feature interaction requires an exact structural guide."
            )
        return build_dungeon_feature_interaction_enrichment_input(
            specification.package,
            specification.dm_guide,
            command.selection,
        )

    def enrich_prompted_feature_interaction(
        self,
        command: CreatePromptedDungeonFeatureInteractionWorkflow,
    ) -> DungeonWorkflowResult:
        """Publish accepted feature interaction content without regenerating package geometry."""

        parent = self._preparation.get_version(
            command.campaign_id,
            command.parent_version_id,
        )
        if parent.artifact_id != command.artifact_id:
            raise ConflictError("Parent version does not belong to the artifact.")
        specification = _load_specification(parent.specification)
        plan = _accepted_structural_plan(specification)
        if specification.dm_guide is None:
            raise ConflictError(
                "Feature interaction enrichment requires an exact structural guide."
            )

        context_document = command.context.model_dump(mode="json")
        context_hash = canonical_json_sha256(context_document)
        context_envelope = GenerationContextEnvelope(
            context_kind="dungeon_feature_interaction_enrichment",
            payload_version=command.context.schema_version,
            visibility_policy=VisibilityPolicy.DM_ONLY,
            payload=context_document,
            payload_sha256=context_hash,
        )
        context_pin = GenerationContextPin(
            envelope_kind=context_envelope.context_kind,
            payload_version=context_envelope.payload_version,
            envelope=context_envelope.model_dump(mode="json"),
            payload_sha256=context_hash,
        )
        run = self._preparation.start_generation_run(
            StartGenerationRun(
                campaign_id=command.campaign_id,
                generation_kind="dungeon_feature_interaction_enrichment",
                seed=specification.layout_request.seed,
                input_scope={
                    "artifact_id": str(command.artifact_id),
                    "parent_version_id": str(command.parent_version_id),
                    "package_id": specification.package.id,
                    "room_id": command.context.room.room_id,
                    "feature_id": command.context.feature.feature_id,
                    "context_sha256": context_hash,
                },
                input_pins=parent.input_pins,
                context=context_pin,
                schema_versions={
                    "dungeon_package": specification.package.schema_version,
                    "dungeon_feature_interaction_enrichment": (
                        DUNGEON_FEATURE_INTERACTION_ENRICHMENT_SCHEMA_VERSION
                    ),
                    "dungeon_studio": _STUDIO_SCHEMA_VERSION,
                    "model_run": "1.0.0",
                },
                generator_versions={
                    "dungeon_kernel": dm_dungeon.__version__,
                    "layout": specification.layout_request.generator_version,
                    "feature_interaction_guide_projection": "feature-interaction-guide-projection-v1",
                },
                renderer_versions={
                    "svg": SVG_RENDERER_VERSION,
                    "png": PNG_EXPORTER_VERSION,
                    "pdf": PDF_EXPORTER_VERSION,
                    "roll20": ROLL20_EXPORTER_VERSION,
                },
                model_task_profile_id=command.model_task_profile_id,
                model_run_ids=(command.model_lineage.model_run_id,),
                tool_runs=command.tool_runs,
            )
        )

        try:
            guide = project_dungeon_feature_interaction_enrichment(
                specification.dm_guide,
                plan=plan,
                package=specification.package,
                context=command.context,
                validation=command.validation,
            )
            readiness = _build_preparation_readiness(guide)
            topology_report = validate_topology(specification.package.topology)
            geometry_report = validate_geometry(specification.package)
            valid = topology_report.valid and geometry_report.valid
            validation_report: dict[str, JsonValue] = {
                "valid": valid,
                "stage": "completed" if valid else "validation",
                "topology": topology_report.model_dump(mode="json"),
                "geometry": geometry_report.model_dump(mode="json"),
                "feature_interaction_enrichment": {
                    "accepted": True,
                    "package_id": command.context.package_id,
                    "room_id": command.context.room.room_id,
                    "feature_id": command.context.feature.feature_id,
                    "context_sha256": context_hash,
                },
            }
            if readiness is not None:
                validation_report["preparation_readiness"] = readiness.model_dump(
                    mode="json"
                )
            if not valid:
                self._preparation.finish_generation_run(
                    FinishGenerationRun(
                        campaign_id=command.campaign_id,
                        run_id=run.id,
                        status=GenerationStatus.FAILED,
                        validation_report=validation_report,
                    )
                )
                diagnostics = tuple(
                    item.model_dump(mode="json")
                    for item in (
                        *topology_report.diagnostics,
                        *geometry_report.diagnostics,
                    )
                )
                return DungeonWorkflowResult(
                    success=False,
                    artifact_id=command.artifact_id,
                    artifact_version_id=None,
                    generation_run_id=run.id,
                    diagnostics=diagnostics,
                )

            enriched_specification = specification.model_copy(
                update={
                    "dm_guide": guide,
                    "preparation_readiness": readiness,
                    "feature_interaction_model_lineage": (
                        *specification.feature_interaction_model_lineage,
                        command.model_lineage,
                    ),
                }
            )
            resolved_notes = _resolved_dm_notes(enriched_specification)
            preview_assets = _preview_assets(
                enriched_specification.package,
                resolved_notes,
            )
            base_assets = (
                _PendingAsset(
                    ArtifactAssetRole.SPECIFICATION,
                    0,
                    "application/json",
                    _canonical_json_bytes(
                        enriched_specification.model_dump(mode="json")
                    ),
                ),
                _PendingAsset(
                    ArtifactAssetRole.VALIDATION_REPORT,
                    0,
                    "application/json",
                    _canonical_json_bytes(validation_report),
                ),
                _dm_notes_asset(
                    enriched_specification.layout_request,
                    resolved_notes,
                    guide,
                ),
            )
            artifact = self._preparation.get_artifact(
                command.campaign_id,
                command.artifact_id,
            )
            published = self._preparation.publish_generated_package(
                PublishGeneratedPackage(
                    campaign_id=command.campaign_id,
                    generation_run_id=run.id,
                    artifact_id=command.artifact_id,
                    artifact_type=ArtifactType.DUNGEON,
                    title=artifact.title,
                    visibility_policy=artifact.visibility_policy,
                    parent_version_id=command.parent_version_id,
                    schema_version=_VERSION_SCHEMA,
                    specification=enriched_specification.model_dump(mode="json"),
                    validation_report=validation_report,
                    change_summary="Add independently generated exact-feature interaction content.",
                    input_pins=parent.input_pins,
                    created_by=command.created_by,
                    assets=tuple(
                        PendingArtifactAsset(
                            role=asset.role,
                            ordinal=asset.ordinal,
                            media_type=asset.media_type,
                            data=asset.data,
                        )
                        for asset in (*base_assets, *preview_assets)
                    ),
                    required_assets=tuple(
                        RequiredArtifactAsset(role=asset.role, ordinal=asset.ordinal)
                        for asset in (*base_assets, *preview_assets)
                    ),
                )
            )
        except Exception:
            if (
                self._preparation.get_generation_run(command.campaign_id, run.id).status
                is GenerationStatus.RUNNING
            ):
                self._preparation.finish_generation_run(
                    FinishGenerationRun(
                        campaign_id=command.campaign_id,
                        run_id=run.id,
                        status=GenerationStatus.FAILED,
                        validation_report={
                            "valid": False,
                            "stage": "projection",
                            "diagnostics": [
                                {
                                    "code": "feature_interaction_enrichment.projection_failed",
                                    "message": "Feature interaction projection or publication failed.",
                                }
                            ],
                        },
                    )
                )
            raise
        return DungeonWorkflowResult(
            success=True,
            artifact_id=published.artifact.id,
            artifact_version_id=published.version.id,
            generation_run_id=run.id,
            diagnostics=(),
        )

    def build_trap_context(
        self,
        command: PromptDungeonTrapWorkflow,
    ) -> DungeonTrapEnrichmentInput:
        """Build one exact trap context from an immutable structural version."""

        parent = self._preparation.get_version(
            command.campaign_id,
            command.parent_version_id,
        )
        if parent.artifact_id != command.artifact_id:
            raise ConflictError("Parent version does not belong to the artifact.")
        specification = _load_specification(parent.specification)
        if specification.dm_guide is None:
            raise ConflictError("Trap requires an exact structural guide.")
        return build_dungeon_trap_enrichment_input(
            specification.package,
            specification.dm_guide,
            command.selection,
        )

    def enrich_prompted_trap(
        self,
        command: CreatePromptedDungeonTrapWorkflow,
    ) -> DungeonWorkflowResult:
        """Publish accepted trap content without regenerating package geometry."""

        parent = self._preparation.get_version(
            command.campaign_id,
            command.parent_version_id,
        )
        if parent.artifact_id != command.artifact_id:
            raise ConflictError("Parent version does not belong to the artifact.")
        specification = _load_specification(parent.specification)
        plan = _accepted_structural_plan(specification)
        if specification.dm_guide is None:
            raise ConflictError("Trap enrichment requires an exact structural guide.")

        context_document = command.context.model_dump(mode="json")
        context_hash = canonical_json_sha256(context_document)
        context_envelope = GenerationContextEnvelope(
            context_kind="dungeon_trap_enrichment",
            payload_version=command.context.schema_version,
            visibility_policy=VisibilityPolicy.DM_ONLY,
            payload=context_document,
            payload_sha256=context_hash,
        )
        context_pin = GenerationContextPin(
            envelope_kind=context_envelope.context_kind,
            payload_version=context_envelope.payload_version,
            envelope=context_envelope.model_dump(mode="json"),
            payload_sha256=context_hash,
        )
        run = self._preparation.start_generation_run(
            StartGenerationRun(
                campaign_id=command.campaign_id,
                generation_kind="dungeon_trap_enrichment",
                seed=specification.layout_request.seed,
                input_scope={
                    "artifact_id": str(command.artifact_id),
                    "parent_version_id": str(command.parent_version_id),
                    "package_id": specification.package.id,
                    "room_id": command.context.room.room_id,
                    "trap_id": command.context.trap.trap_id,
                    "context_sha256": context_hash,
                },
                input_pins=parent.input_pins,
                context=context_pin,
                schema_versions={
                    "dungeon_package": specification.package.schema_version,
                    "dungeon_trap_enrichment": (DUNGEON_TRAP_ENRICHMENT_SCHEMA_VERSION),
                    "dungeon_studio": _STUDIO_SCHEMA_VERSION,
                    "model_run": "1.0.0",
                },
                generator_versions={
                    "dungeon_kernel": dm_dungeon.__version__,
                    "layout": specification.layout_request.generator_version,
                    "trap_guide_projection": "trap-guide-projection-v1",
                },
                renderer_versions={
                    "svg": SVG_RENDERER_VERSION,
                    "png": PNG_EXPORTER_VERSION,
                    "pdf": PDF_EXPORTER_VERSION,
                    "roll20": ROLL20_EXPORTER_VERSION,
                },
                model_task_profile_id=command.model_task_profile_id,
                model_run_ids=(command.model_lineage.model_run_id,),
                tool_runs=command.tool_runs,
            )
        )

        try:
            guide = project_dungeon_trap_enrichment(
                specification.dm_guide,
                plan=plan,
                package=specification.package,
                context=command.context,
                validation=command.validation,
            )
            readiness = _build_preparation_readiness(guide)
            topology_report = validate_topology(specification.package.topology)
            geometry_report = validate_geometry(specification.package)
            valid = topology_report.valid and geometry_report.valid
            validation_report: dict[str, JsonValue] = {
                "valid": valid,
                "stage": "completed" if valid else "validation",
                "topology": topology_report.model_dump(mode="json"),
                "geometry": geometry_report.model_dump(mode="json"),
                "trap_enrichment": {
                    "accepted": True,
                    "package_id": command.context.package_id,
                    "room_id": command.context.room.room_id,
                    "trap_id": command.context.trap.trap_id,
                    "context_sha256": context_hash,
                },
            }
            if readiness is not None:
                validation_report["preparation_readiness"] = readiness.model_dump(
                    mode="json"
                )
            if not valid:
                self._preparation.finish_generation_run(
                    FinishGenerationRun(
                        campaign_id=command.campaign_id,
                        run_id=run.id,
                        status=GenerationStatus.FAILED,
                        validation_report=validation_report,
                    )
                )
                diagnostics = tuple(
                    item.model_dump(mode="json")
                    for item in (
                        *topology_report.diagnostics,
                        *geometry_report.diagnostics,
                    )
                )
                return DungeonWorkflowResult(
                    success=False,
                    artifact_id=command.artifact_id,
                    artifact_version_id=None,
                    generation_run_id=run.id,
                    diagnostics=diagnostics,
                )

            enriched_specification = specification.model_copy(
                update={
                    "dm_guide": guide,
                    "preparation_readiness": readiness,
                    "trap_model_lineage": (
                        *specification.trap_model_lineage,
                        command.model_lineage,
                    ),
                }
            )
            resolved_notes = _resolved_dm_notes(enriched_specification)
            preview_assets = _preview_assets(
                enriched_specification.package,
                resolved_notes,
            )
            base_assets = (
                _PendingAsset(
                    ArtifactAssetRole.SPECIFICATION,
                    0,
                    "application/json",
                    _canonical_json_bytes(
                        enriched_specification.model_dump(mode="json")
                    ),
                ),
                _PendingAsset(
                    ArtifactAssetRole.VALIDATION_REPORT,
                    0,
                    "application/json",
                    _canonical_json_bytes(validation_report),
                ),
                _dm_notes_asset(
                    enriched_specification.layout_request,
                    resolved_notes,
                    guide,
                ),
            )
            artifact = self._preparation.get_artifact(
                command.campaign_id,
                command.artifact_id,
            )
            published = self._preparation.publish_generated_package(
                PublishGeneratedPackage(
                    campaign_id=command.campaign_id,
                    generation_run_id=run.id,
                    artifact_id=command.artifact_id,
                    artifact_type=ArtifactType.DUNGEON,
                    title=artifact.title,
                    visibility_policy=artifact.visibility_policy,
                    parent_version_id=command.parent_version_id,
                    schema_version=_VERSION_SCHEMA,
                    specification=enriched_specification.model_dump(mode="json"),
                    validation_report=validation_report,
                    change_summary="Add independently generated exact-trap content.",
                    input_pins=parent.input_pins,
                    created_by=command.created_by,
                    assets=tuple(
                        PendingArtifactAsset(
                            role=asset.role,
                            ordinal=asset.ordinal,
                            media_type=asset.media_type,
                            data=asset.data,
                        )
                        for asset in (*base_assets, *preview_assets)
                    ),
                    required_assets=tuple(
                        RequiredArtifactAsset(role=asset.role, ordinal=asset.ordinal)
                        for asset in (*base_assets, *preview_assets)
                    ),
                )
            )
        except Exception:
            if (
                self._preparation.get_generation_run(command.campaign_id, run.id).status
                is GenerationStatus.RUNNING
            ):
                self._preparation.finish_generation_run(
                    FinishGenerationRun(
                        campaign_id=command.campaign_id,
                        run_id=run.id,
                        status=GenerationStatus.FAILED,
                        validation_report={
                            "valid": False,
                            "stage": "projection",
                            "diagnostics": [
                                {
                                    "code": "trap_enrichment.projection_failed",
                                    "message": "Trap projection or publication failed.",
                                }
                            ],
                        },
                    )
                )
            raise
        return DungeonWorkflowResult(
            success=True,
            artifact_id=published.artifact.id,
            artifact_version_id=published.version.id,
            generation_run_id=run.id,
            diagnostics=(),
        )

    def build_objective_context(
        self,
        command: PromptDungeonObjectiveWorkflow,
    ) -> DungeonObjectiveEnrichmentInput:
        """Build one exact objective context from an immutable structural version."""

        parent = self._preparation.get_version(
            command.campaign_id,
            command.parent_version_id,
        )
        if parent.artifact_id != command.artifact_id:
            raise ConflictError("Parent version does not belong to the artifact.")
        specification = _load_specification(parent.specification)
        if specification.dm_guide is None:
            raise ConflictError("Objective requires an exact structural guide.")
        return build_dungeon_objective_enrichment_input(
            specification.package,
            specification.dm_guide,
            command.selection,
        )

    def enrich_prompted_objective(
        self,
        command: CreatePromptedDungeonObjectiveWorkflow,
    ) -> DungeonWorkflowResult:
        """Publish accepted objective content without regenerating package geometry."""

        parent = self._preparation.get_version(
            command.campaign_id,
            command.parent_version_id,
        )
        if parent.artifact_id != command.artifact_id:
            raise ConflictError("Parent version does not belong to the artifact.")
        specification = _load_specification(parent.specification)
        plan = _accepted_structural_plan(specification)
        if specification.dm_guide is None:
            raise ConflictError(
                "Objective enrichment requires an exact structural guide."
            )

        context_document = command.context.model_dump(mode="json")
        context_hash = canonical_json_sha256(context_document)
        context_envelope = GenerationContextEnvelope(
            context_kind="dungeon_objective_enrichment",
            payload_version=command.context.schema_version,
            visibility_policy=VisibilityPolicy.DM_ONLY,
            payload=context_document,
            payload_sha256=context_hash,
        )
        context_pin = GenerationContextPin(
            envelope_kind=context_envelope.context_kind,
            payload_version=context_envelope.payload_version,
            envelope=context_envelope.model_dump(mode="json"),
            payload_sha256=context_hash,
        )
        run = self._preparation.start_generation_run(
            StartGenerationRun(
                campaign_id=command.campaign_id,
                generation_kind="dungeon_objective_enrichment",
                seed=specification.layout_request.seed,
                input_scope={
                    "artifact_id": str(command.artifact_id),
                    "parent_version_id": str(command.parent_version_id),
                    "package_id": specification.package.id,
                    "room_id": command.context.room.room_id,
                    "objective_id": command.context.objective.objective_id,
                    "context_sha256": context_hash,
                },
                input_pins=parent.input_pins,
                context=context_pin,
                schema_versions={
                    "dungeon_package": specification.package.schema_version,
                    "dungeon_objective_enrichment": (
                        DUNGEON_OBJECTIVE_ENRICHMENT_SCHEMA_VERSION
                    ),
                    "dungeon_studio": _STUDIO_SCHEMA_VERSION,
                    "model_run": "1.0.0",
                },
                generator_versions={
                    "dungeon_kernel": dm_dungeon.__version__,
                    "layout": specification.layout_request.generator_version,
                    "objective_guide_projection": "objective-guide-projection-v1",
                },
                renderer_versions={
                    "svg": SVG_RENDERER_VERSION,
                    "png": PNG_EXPORTER_VERSION,
                    "pdf": PDF_EXPORTER_VERSION,
                    "roll20": ROLL20_EXPORTER_VERSION,
                },
                model_task_profile_id=command.model_task_profile_id,
                model_run_ids=(command.model_lineage.model_run_id,),
                tool_runs=command.tool_runs,
            )
        )

        try:
            guide = project_dungeon_objective_enrichment(
                specification.dm_guide,
                plan=plan,
                package=specification.package,
                context=command.context,
                validation=command.validation,
            )
            readiness = _build_preparation_readiness(guide)
            topology_report = validate_topology(specification.package.topology)
            geometry_report = validate_geometry(specification.package)
            valid = topology_report.valid and geometry_report.valid
            validation_report: dict[str, JsonValue] = {
                "valid": valid,
                "stage": "completed" if valid else "validation",
                "topology": topology_report.model_dump(mode="json"),
                "geometry": geometry_report.model_dump(mode="json"),
                "objective_enrichment": {
                    "accepted": True,
                    "package_id": command.context.package_id,
                    "room_id": command.context.room.room_id,
                    "objective_id": command.context.objective.objective_id,
                    "context_sha256": context_hash,
                },
            }
            if readiness is not None:
                validation_report["preparation_readiness"] = readiness.model_dump(
                    mode="json"
                )
            if not valid:
                self._preparation.finish_generation_run(
                    FinishGenerationRun(
                        campaign_id=command.campaign_id,
                        run_id=run.id,
                        status=GenerationStatus.FAILED,
                        validation_report=validation_report,
                    )
                )
                diagnostics = tuple(
                    item.model_dump(mode="json")
                    for item in (
                        *topology_report.diagnostics,
                        *geometry_report.diagnostics,
                    )
                )
                return DungeonWorkflowResult(
                    success=False,
                    artifact_id=command.artifact_id,
                    artifact_version_id=None,
                    generation_run_id=run.id,
                    diagnostics=diagnostics,
                )

            enriched_specification = specification.model_copy(
                update={
                    "dm_guide": guide,
                    "preparation_readiness": readiness,
                    "objective_model_lineage": (
                        *specification.objective_model_lineage,
                        command.model_lineage,
                    ),
                }
            )
            resolved_notes = _resolved_dm_notes(enriched_specification)
            preview_assets = _preview_assets(
                enriched_specification.package,
                resolved_notes,
            )
            base_assets = (
                _PendingAsset(
                    ArtifactAssetRole.SPECIFICATION,
                    0,
                    "application/json",
                    _canonical_json_bytes(
                        enriched_specification.model_dump(mode="json")
                    ),
                ),
                _PendingAsset(
                    ArtifactAssetRole.VALIDATION_REPORT,
                    0,
                    "application/json",
                    _canonical_json_bytes(validation_report),
                ),
                _dm_notes_asset(
                    enriched_specification.layout_request,
                    resolved_notes,
                    guide,
                ),
            )
            artifact = self._preparation.get_artifact(
                command.campaign_id,
                command.artifact_id,
            )
            published = self._preparation.publish_generated_package(
                PublishGeneratedPackage(
                    campaign_id=command.campaign_id,
                    generation_run_id=run.id,
                    artifact_id=command.artifact_id,
                    artifact_type=ArtifactType.DUNGEON,
                    title=artifact.title,
                    visibility_policy=artifact.visibility_policy,
                    parent_version_id=command.parent_version_id,
                    schema_version=_VERSION_SCHEMA,
                    specification=enriched_specification.model_dump(mode="json"),
                    validation_report=validation_report,
                    change_summary="Add independently generated exact-objective content.",
                    input_pins=parent.input_pins,
                    created_by=command.created_by,
                    assets=tuple(
                        PendingArtifactAsset(
                            role=asset.role,
                            ordinal=asset.ordinal,
                            media_type=asset.media_type,
                            data=asset.data,
                        )
                        for asset in (*base_assets, *preview_assets)
                    ),
                    required_assets=tuple(
                        RequiredArtifactAsset(role=asset.role, ordinal=asset.ordinal)
                        for asset in (*base_assets, *preview_assets)
                    ),
                )
            )
        except Exception:
            if (
                self._preparation.get_generation_run(command.campaign_id, run.id).status
                is GenerationStatus.RUNNING
            ):
                self._preparation.finish_generation_run(
                    FinishGenerationRun(
                        campaign_id=command.campaign_id,
                        run_id=run.id,
                        status=GenerationStatus.FAILED,
                        validation_report={
                            "valid": False,
                            "stage": "projection",
                            "diagnostics": [
                                {
                                    "code": "objective_enrichment.projection_failed",
                                    "message": "Objective projection or publication failed.",
                                }
                            ],
                        },
                    )
                )
            raise
        return DungeonWorkflowResult(
            success=True,
            artifact_id=published.artifact.id,
            artifact_version_id=published.version.id,
            generation_run_id=run.id,
            diagnostics=(),
        )

    def build_room_narrative_context(
        self,
        command: PromptDungeonRoomNarrativeWorkflow,
    ) -> DungeonRoomNarrativeEnrichmentInput:
        """Build a bounded exact-room context from one immutable guide version."""

        parent = self._preparation.get_version(
            command.campaign_id,
            command.parent_version_id,
        )
        if parent.artifact_id != command.artifact_id:
            raise ConflictError("Parent version does not belong to the artifact.")
        specification = _load_specification(parent.specification)
        if specification.dm_guide is None:
            raise ConflictError("Room narrative requires an exact structural guide.")
        return build_dungeon_room_narrative_enrichment_input(
            specification.package,
            specification.dm_guide,
            command.selection,
        )

    def enrich_prompted_room_narrative(
        self,
        command: CreatePromptedDungeonRoomNarrativeWorkflow,
    ) -> DungeonWorkflowResult:
        """Publish accepted room prose without regenerating package geometry."""

        parent = self._preparation.get_version(
            command.campaign_id,
            command.parent_version_id,
        )
        if parent.artifact_id != command.artifact_id:
            raise ConflictError("Parent version does not belong to the artifact.")
        specification = _load_specification(parent.specification)
        plan = _accepted_structural_plan(specification)
        if specification.dm_guide is None:
            raise ConflictError(
                "Room narrative enrichment requires an exact structural guide."
            )

        context_document = command.context.model_dump(mode="json")
        context_hash = canonical_json_sha256(context_document)
        context_envelope = GenerationContextEnvelope(
            context_kind="dungeon_room_narrative_enrichment",
            payload_version=command.context.schema_version,
            visibility_policy=VisibilityPolicy.DM_ONLY,
            payload=context_document,
            payload_sha256=context_hash,
        )
        context_pin = GenerationContextPin(
            envelope_kind=context_envelope.context_kind,
            payload_version=context_envelope.payload_version,
            envelope=context_envelope.model_dump(mode="json"),
            payload_sha256=context_hash,
        )
        run = self._preparation.start_generation_run(
            StartGenerationRun(
                campaign_id=command.campaign_id,
                generation_kind="dungeon_room_narrative_enrichment",
                seed=specification.layout_request.seed,
                input_scope={
                    "artifact_id": str(command.artifact_id),
                    "parent_version_id": str(command.parent_version_id),
                    "package_id": specification.package.id,
                    "room_ids": [room.room_id for room in command.context.rooms],
                    "room_count": len(command.context.rooms),
                    "context_sha256": context_hash,
                },
                input_pins=parent.input_pins,
                context=context_pin,
                schema_versions={
                    "dungeon_package": specification.package.schema_version,
                    "dungeon_room_narrative_enrichment": (
                        DUNGEON_ROOM_NARRATIVE_ENRICHMENT_SCHEMA_VERSION
                    ),
                    "dungeon_studio": _STUDIO_SCHEMA_VERSION,
                    "model_run": "1.0.0",
                },
                generator_versions={
                    "dungeon_kernel": dm_dungeon.__version__,
                    "layout": specification.layout_request.generator_version,
                    "room_narrative_guide_projection": "room-narrative-guide-projection-v1",
                },
                renderer_versions={
                    "svg": SVG_RENDERER_VERSION,
                    "png": PNG_EXPORTER_VERSION,
                    "pdf": PDF_EXPORTER_VERSION,
                    "roll20": ROLL20_EXPORTER_VERSION,
                },
                model_task_profile_id=command.model_task_profile_id,
                model_run_ids=(command.model_lineage.model_run_id,),
                tool_runs=command.tool_runs,
            )
        )

        try:
            guide = project_dungeon_room_narrative_enrichment(
                specification.dm_guide,
                plan=plan,
                package=specification.package,
                context=command.context,
                validation=command.validation,
            )
            readiness = _build_preparation_readiness(guide)
            topology_report = validate_topology(specification.package.topology)
            geometry_report = validate_geometry(specification.package)
            valid = topology_report.valid and geometry_report.valid
            validation_report: dict[str, JsonValue] = {
                "valid": valid,
                "stage": "completed" if valid else "validation",
                "topology": topology_report.model_dump(mode="json"),
                "geometry": geometry_report.model_dump(mode="json"),
                "room_narrative_enrichment": {
                    "accepted": True,
                    "package_id": command.context.package_id,
                    "room_ids": [room.room_id for room in command.context.rooms],
                    "room_count": len(command.context.rooms),
                    "context_sha256": context_hash,
                },
            }
            if readiness is not None:
                validation_report["preparation_readiness"] = readiness.model_dump(
                    mode="json"
                )
            if not valid:
                self._preparation.finish_generation_run(
                    FinishGenerationRun(
                        campaign_id=command.campaign_id,
                        run_id=run.id,
                        status=GenerationStatus.FAILED,
                        validation_report=validation_report,
                    )
                )
                diagnostics = tuple(
                    item.model_dump(mode="json")
                    for item in (
                        *topology_report.diagnostics,
                        *geometry_report.diagnostics,
                    )
                )
                return DungeonWorkflowResult(
                    success=False,
                    artifact_id=command.artifact_id,
                    artifact_version_id=None,
                    generation_run_id=run.id,
                    diagnostics=diagnostics,
                )

            enriched_specification = specification.model_copy(
                update={
                    "dm_guide": guide,
                    "preparation_readiness": readiness,
                    "room_narrative_model_lineage": (
                        *specification.room_narrative_model_lineage,
                        command.model_lineage,
                    ),
                }
            )
            resolved_notes = _resolved_dm_notes(enriched_specification)
            preview_assets = _preview_assets(
                enriched_specification.package,
                resolved_notes,
            )
            base_assets = (
                _PendingAsset(
                    ArtifactAssetRole.SPECIFICATION,
                    0,
                    "application/json",
                    _canonical_json_bytes(
                        enriched_specification.model_dump(mode="json")
                    ),
                ),
                _PendingAsset(
                    ArtifactAssetRole.VALIDATION_REPORT,
                    0,
                    "application/json",
                    _canonical_json_bytes(validation_report),
                ),
                _dm_notes_asset(
                    enriched_specification.layout_request,
                    resolved_notes,
                    guide,
                ),
            )
            artifact = self._preparation.get_artifact(
                command.campaign_id,
                command.artifact_id,
            )
            published = self._preparation.publish_generated_package(
                PublishGeneratedPackage(
                    campaign_id=command.campaign_id,
                    generation_run_id=run.id,
                    artifact_id=command.artifact_id,
                    artifact_type=ArtifactType.DUNGEON,
                    title=artifact.title,
                    visibility_policy=artifact.visibility_policy,
                    parent_version_id=command.parent_version_id,
                    schema_version=_VERSION_SCHEMA,
                    specification=enriched_specification.model_dump(mode="json"),
                    validation_report=validation_report,
                    change_summary="Add independently generated exact-room narratives.",
                    input_pins=parent.input_pins,
                    created_by=command.created_by,
                    assets=tuple(
                        PendingArtifactAsset(
                            role=asset.role,
                            ordinal=asset.ordinal,
                            media_type=asset.media_type,
                            data=asset.data,
                        )
                        for asset in (*base_assets, *preview_assets)
                    ),
                    required_assets=tuple(
                        RequiredArtifactAsset(role=asset.role, ordinal=asset.ordinal)
                        for asset in (*base_assets, *preview_assets)
                    ),
                )
            )
        except Exception:
            if (
                self._preparation.get_generation_run(command.campaign_id, run.id).status
                is GenerationStatus.RUNNING
            ):
                self._preparation.finish_generation_run(
                    FinishGenerationRun(
                        campaign_id=command.campaign_id,
                        run_id=run.id,
                        status=GenerationStatus.FAILED,
                        validation_report={
                            "valid": False,
                            "stage": "projection",
                            "diagnostics": [
                                {
                                    "code": "room_narrative_enrichment.projection_failed",
                                    "message": "Room narrative projection or publication failed.",
                                }
                            ],
                        },
                    )
                )
            raise
        return DungeonWorkflowResult(
            success=True,
            artifact_id=published.artifact.id,
            artifact_version_id=published.version.id,
            generation_run_id=run.id,
            diagnostics=(),
        )

    def build_puzzle_context(
        self,
        command: PromptDungeonPuzzleWorkflow,
    ) -> DungeonPuzzleEnrichmentInput:
        """Build one exact puzzle context from an immutable structural version."""

        parent = self._preparation.get_version(
            command.campaign_id,
            command.parent_version_id,
        )
        if parent.artifact_id != command.artifact_id:
            raise ConflictError("Parent version does not belong to the artifact.")
        specification = _load_specification(parent.specification)
        return build_dungeon_puzzle_enrichment_input(
            specification.package,
            command.selection,
        )

    def enrich_prompted_puzzle(
        self,
        command: CreatePromptedDungeonPuzzleWorkflow,
    ) -> DungeonWorkflowResult:
        """Publish accepted puzzle content without regenerating package geometry."""

        parent = self._preparation.get_version(
            command.campaign_id,
            command.parent_version_id,
        )
        if parent.artifact_id != command.artifact_id:
            raise ConflictError("Parent version does not belong to the artifact.")
        specification = _load_specification(parent.specification)
        plan = _accepted_structural_plan(specification)
        if specification.dm_guide is None:
            raise ConflictError("Puzzle enrichment requires an exact structural guide.")

        context_document = command.context.model_dump(mode="json")
        context_hash = canonical_json_sha256(context_document)
        context_envelope = GenerationContextEnvelope(
            context_kind="dungeon_puzzle_enrichment",
            payload_version=command.context.schema_version,
            visibility_policy=VisibilityPolicy.DM_ONLY,
            payload=context_document,
            payload_sha256=context_hash,
        )
        context_pin = GenerationContextPin(
            envelope_kind=context_envelope.context_kind,
            payload_version=context_envelope.payload_version,
            envelope=context_envelope.model_dump(mode="json"),
            payload_sha256=context_hash,
        )
        run = self._preparation.start_generation_run(
            StartGenerationRun(
                campaign_id=command.campaign_id,
                generation_kind="dungeon_puzzle_enrichment",
                seed=specification.layout_request.seed,
                input_scope={
                    "artifact_id": str(command.artifact_id),
                    "parent_version_id": str(command.parent_version_id),
                    "package_id": specification.package.id,
                    "room_id": command.context.room.room_id,
                    "context_sha256": context_hash,
                },
                input_pins=parent.input_pins,
                context=context_pin,
                schema_versions={
                    "dungeon_package": specification.package.schema_version,
                    "dungeon_puzzle_enrichment": (
                        DUNGEON_PUZZLE_ENRICHMENT_SCHEMA_VERSION
                    ),
                    "dungeon_studio": _STUDIO_SCHEMA_VERSION,
                    "model_run": "1.0.0",
                },
                generator_versions={
                    "dungeon_kernel": dm_dungeon.__version__,
                    "layout": specification.layout_request.generator_version,
                    "puzzle_guide_projection": "puzzle-guide-projection-v1",
                },
                renderer_versions={
                    "svg": SVG_RENDERER_VERSION,
                    "png": PNG_EXPORTER_VERSION,
                    "pdf": PDF_EXPORTER_VERSION,
                    "roll20": ROLL20_EXPORTER_VERSION,
                },
                model_task_profile_id=command.model_task_profile_id,
                model_run_ids=(command.model_lineage.model_run_id,),
                tool_runs=command.tool_runs,
            )
        )

        try:
            guide = project_dungeon_puzzle_enrichment(
                specification.dm_guide,
                plan=plan,
                package=specification.package,
                context=command.context,
                validation=command.validation,
            )
            readiness = _build_preparation_readiness(guide)
            topology_report = validate_topology(specification.package.topology)
            geometry_report = validate_geometry(specification.package)
            valid = topology_report.valid and geometry_report.valid
            validation_report: dict[str, JsonValue] = {
                "valid": valid,
                "stage": "completed" if valid else "validation",
                "topology": topology_report.model_dump(mode="json"),
                "geometry": geometry_report.model_dump(mode="json"),
                "puzzle_enrichment": {
                    "accepted": True,
                    "package_id": command.context.package_id,
                    "room_id": command.context.room.room_id,
                    "context_sha256": context_hash,
                },
            }
            if readiness is not None:
                validation_report["preparation_readiness"] = readiness.model_dump(
                    mode="json"
                )
            if not valid:
                self._preparation.finish_generation_run(
                    FinishGenerationRun(
                        campaign_id=command.campaign_id,
                        run_id=run.id,
                        status=GenerationStatus.FAILED,
                        validation_report=validation_report,
                    )
                )
                diagnostics = tuple(
                    item.model_dump(mode="json")
                    for item in (
                        *topology_report.diagnostics,
                        *geometry_report.diagnostics,
                    )
                )
                return DungeonWorkflowResult(
                    success=False,
                    artifact_id=command.artifact_id,
                    artifact_version_id=None,
                    generation_run_id=run.id,
                    diagnostics=diagnostics,
                )

            enriched_specification = specification.model_copy(
                update={
                    "dm_guide": guide,
                    "preparation_readiness": readiness,
                    "puzzle_model_lineage": (
                        *specification.puzzle_model_lineage,
                        command.model_lineage,
                    ),
                }
            )
            resolved_notes = _resolved_dm_notes(enriched_specification)
            preview_assets = _preview_assets(
                enriched_specification.package,
                resolved_notes,
            )
            base_assets = (
                _PendingAsset(
                    ArtifactAssetRole.SPECIFICATION,
                    0,
                    "application/json",
                    _canonical_json_bytes(
                        enriched_specification.model_dump(mode="json")
                    ),
                ),
                _PendingAsset(
                    ArtifactAssetRole.VALIDATION_REPORT,
                    0,
                    "application/json",
                    _canonical_json_bytes(validation_report),
                ),
                _dm_notes_asset(
                    enriched_specification.layout_request,
                    resolved_notes,
                    guide,
                ),
            )
            artifact = self._preparation.get_artifact(
                command.campaign_id,
                command.artifact_id,
            )
            published = self._preparation.publish_generated_package(
                PublishGeneratedPackage(
                    campaign_id=command.campaign_id,
                    generation_run_id=run.id,
                    artifact_id=command.artifact_id,
                    artifact_type=ArtifactType.DUNGEON,
                    title=artifact.title,
                    visibility_policy=artifact.visibility_policy,
                    parent_version_id=command.parent_version_id,
                    schema_version=_VERSION_SCHEMA,
                    specification=enriched_specification.model_dump(mode="json"),
                    validation_report=validation_report,
                    change_summary="Add independently generated exact-room puzzle content.",
                    input_pins=parent.input_pins,
                    created_by=command.created_by,
                    assets=tuple(
                        PendingArtifactAsset(
                            role=asset.role,
                            ordinal=asset.ordinal,
                            media_type=asset.media_type,
                            data=asset.data,
                        )
                        for asset in (*base_assets, *preview_assets)
                    ),
                    required_assets=tuple(
                        RequiredArtifactAsset(role=asset.role, ordinal=asset.ordinal)
                        for asset in (*base_assets, *preview_assets)
                    ),
                )
            )
        except Exception:
            if (
                self._preparation.get_generation_run(command.campaign_id, run.id).status
                is GenerationStatus.RUNNING
            ):
                self._preparation.finish_generation_run(
                    FinishGenerationRun(
                        campaign_id=command.campaign_id,
                        run_id=run.id,
                        status=GenerationStatus.FAILED,
                        validation_report={
                            "valid": False,
                            "stage": "projection",
                            "diagnostics": [
                                {
                                    "code": "puzzle_enrichment.projection_failed",
                                    "message": "Puzzle projection or publication failed.",
                                }
                            ],
                        },
                    )
                )
            raise
        return DungeonWorkflowResult(
            success=True,
            artifact_id=published.artifact.id,
            artifact_version_id=published.version.id,
            generation_run_id=run.id,
            diagnostics=(),
        )

    def regenerate(
        self,
        command: RegenerateDungeonWorkflow,
    ) -> DungeonWorkflowResult:
        parent = self._preparation.get_version(
            command.campaign_id,
            command.parent_version_id,
        )
        if parent.artifact_id != command.artifact_id:
            raise ConflictError("Parent version does not belong to the artifact.")
        specification = _load_specification(parent.specification)
        locks = _select_locks(
            specification.package,
            command.locked_component_ids,
        )
        request = specification.layout_request.model_copy(
            update={"seed": command.seed, "locked": locks}
        )
        return self._generate_version(
            campaign_id=command.campaign_id,
            artifact_id=command.artifact_id,
            artifact_title=None,
            parent_version_id=command.parent_version_id,
            request=request,
            change_summary=command.change_summary,
            created_by=command.created_by,
            dm_notes=_resolved_dm_notes(specification),
        )

    @property
    def print_capability(self) -> DungeonPrintCapability:
        """The sole application policy for new exact-scale print generation."""

        return DungeonPrintCapability()

    def export(self, command: ExportDungeonWorkflow) -> tuple[uuid.UUID, ...]:
        if command.export_format == "pdf":
            raise DungeonPrintExportDisabledError()
        snapshot = self._preparation.get_version(
            command.campaign_id,
            command.artifact_version_id,
        )
        specification = _load_specification(snapshot.specification)
        assets = _export_assets(
            specification.package,
            _resolved_dm_notes(specification),
            export_format=command.export_format,
        )
        records = tuple(
            self._preparation.attach_asset(
                AttachArtifactAsset(
                    campaign_id=command.campaign_id,
                    artifact_version_id=snapshot.id,
                    role=asset.role,
                    ordinal=asset.ordinal,
                    media_type=asset.media_type,
                    data=asset.data,
                )
            )
            for asset in assets
        )
        return tuple(item.id for item in records)

    def approve(
        self,
        *,
        campaign_id: uuid.UUID,
        artifact_id: uuid.UUID,
        artifact_version_id: uuid.UUID,
        actor: str,
        reason: str,
    ) -> DungeonStudioDetail:
        version = self._preparation.get_version(campaign_id, artifact_version_id)
        _require_preparation_ready(_load_specification(version.specification))
        self._preparation.transition_artifact(
            TransitionArtifact(
                campaign_id=campaign_id,
                artifact_id=artifact_id,
                artifact_version_id=artifact_version_id,
                target=ArtifactLifecycle.APPROVED_FOR_PLAY,
                actor=actor,
                reason=reason,
            )
        )
        return self.inspect(campaign_id=campaign_id, artifact_id=artifact_id)

    def notes_for_version(
        self, *, campaign_id: uuid.UUID, artifact_version_id: uuid.UUID
    ) -> DungeonDmNotes:
        """Return presentation notes, including a safe legacy-spec fallback."""

        version = self._preparation.get_version(campaign_id, artifact_version_id)
        return _resolved_dm_notes(_load_specification(version.specification))

    def guide_for_version(
        self, *, campaign_id: uuid.UUID, artifact_version_id: uuid.UUID
    ) -> DungeonDmGuide | None:
        """Return the immutable V1 DM-guide projection when the version has one."""

        version = self._preparation.get_version(campaign_id, artifact_version_id)
        return _load_specification(version.specification).dm_guide

    def inspect(
        self,
        *,
        campaign_id: uuid.UUID,
        artifact_id: uuid.UUID,
    ) -> DungeonStudioDetail:
        artifact = self._preparation.get_artifact(campaign_id, artifact_id)
        versions = self._preparation.list_versions(campaign_id, artifact_id)
        return DungeonStudioDetail(
            artifact_id=artifact.id,
            current_version_id=artifact.current_version_id,
            lifecycle=artifact.lifecycle.value,
            title=artifact.title,
            versions=tuple(item.id for item in versions),
        )

    def compare(
        self,
        *,
        campaign_id: uuid.UUID,
        left_version_id: uuid.UUID,
        right_version_id: uuid.UUID,
    ) -> DungeonVersionComparison:
        left = self._preparation.get_version(campaign_id, left_version_id)
        right = self._preparation.get_version(campaign_id, right_version_id)
        if left.artifact_id != right.artifact_id:
            raise ConflictError("Dungeon comparison requires one artifact lineage.")
        left_package = _load_specification(left.specification).package
        right_package = _load_specification(right.specification).package
        left_components = _component_documents(left_package)
        right_components = _component_documents(right_package)
        left_keys = set(left_components)
        right_keys = set(right_components)
        added_keys = right_keys - left_keys
        removed_keys = left_keys - right_keys
        shared_keys = left_keys & right_keys
        changed_keys = {
            key for key in shared_keys if left_components[key] != right_components[key]
        }
        unchanged_keys = shared_keys - changed_keys
        return DungeonVersionComparison(
            left_version_id=left.id,
            right_version_id=right.id,
            added_component_ids=_component_ids(added_keys),
            removed_component_ids=_component_ids(removed_keys),
            changed_component_ids=_component_ids(changed_keys),
            unchanged_component_ids=_component_ids(unchanged_keys),
        )

    def _generate_version(
        self,
        *,
        campaign_id: uuid.UUID,
        artifact_id: uuid.UUID | None,
        artifact_title: str | None,
        parent_version_id: uuid.UUID | None,
        request: LayoutRequest,
        change_summary: str,
        created_by: str,
        generation_kind: str = "dungeon_layout",
        context: GenerationContextPin | None = None,
        model_task_profile_id: uuid.UUID | None = None,
        model_lineage: tuple[PromptedDungeonModelLineage, ...] = (),
        tool_runs: tuple[ToolRunPin, ...] = (),
        dm_notes: DungeonDmNotes | None = None,
    ) -> DungeonWorkflowResult:
        request_document = json.loads(to_canonical_json(request))
        input_scope: dict[str, JsonValue] = {
            "layout_request_sha256": canonical_json_sha256(request_document),
            "package_id": request.package_id,
        }
        if artifact_id is not None:
            input_scope["artifact_id"] = str(artifact_id)
        schema_versions: dict[str, str] = {
            "dungeon_brief": request.brief.schema_version,
            "dungeon_topology": request.topology.schema_version,
            "layout_request": request.schema_version,
            "dungeon_package": DUNGEON_PACKAGE_SCHEMA_VERSION,
            "dungeon_studio": _STUDIO_SCHEMA_VERSION,
        }
        generator_versions = {
            "dungeon_kernel": dm_dungeon.__version__,
            "layout": request.generator_version,
        }
        generator_versions["dungeon_mechanics_policy"] = (
            request.mechanics_plan.policy_version
        )
        if model_lineage:
            input_scope["model_lineage_sha256"] = canonical_json_sha256(
                {
                    "model_lineage": [
                        item.model_dump(mode="json") for item in model_lineage
                    ]
                }
            )
            schema_versions["dungeon_generation_proposal"] = (
                DUNGEON_GENERATION_PROPOSAL_SCHEMA_VERSION
            )
            generator_versions["plan_compiler"] = (
                dm_dungeon.DUNGEON_PLAN_COMPILER_VERSION
            )
            schema_versions["model_run"] = "1.0.0"
        run = self._preparation.start_generation_run(
            StartGenerationRun(
                campaign_id=campaign_id,
                generation_kind=generation_kind,
                seed=request.seed,
                input_scope=input_scope,
                context=context,
                schema_versions=schema_versions,
                generator_versions=generator_versions,
                renderer_versions={
                    "svg": SVG_RENDERER_VERSION,
                    "png": PNG_EXPORTER_VERSION,
                    "pdf": PDF_EXPORTER_VERSION,
                    "roll20": ROLL20_EXPORTER_VERSION,
                },
                model_task_profile_id=model_task_profile_id,
                model_run_ids=tuple(item.model_run_id for item in model_lineage),
                tool_runs=tool_runs,
            )
        )
        layout = generate_layout(request)
        if not layout.success or layout.package is None:
            diagnostics = tuple(
                item.model_dump(mode="json") for item in layout.diagnostics
            )
            report: dict[str, JsonValue] = {
                "valid": False,
                "stage": "layout",
                "diagnostics": list(diagnostics),
            }
            self._preparation.finish_generation_run(
                FinishGenerationRun(
                    campaign_id=campaign_id,
                    run_id=run.id,
                    status=GenerationStatus.FAILED,
                    validation_report=report,
                )
            )
            _log_generation_result(
                run_id=run.id,
                stage="layout",
                diagnostics=diagnostics,
            )
            return DungeonWorkflowResult(
                success=False,
                artifact_id=artifact_id,
                artifact_version_id=None,
                generation_run_id=run.id,
                diagnostics=diagnostics,
                regression_case=_regression_case(
                    request=request,
                    stage="layout",
                    diagnostics=diagnostics,
                ),
            )

        package = layout.package
        topology_report = validate_topology(package.topology)
        geometry_report = validate_geometry(package)
        diagnostics = tuple(
            item.model_dump(mode="json")
            for item in (*topology_report.diagnostics, *geometry_report.diagnostics)
        )
        valid = topology_report.valid and geometry_report.valid
        validation_report: dict[str, JsonValue] = {
            "valid": valid,
            "topology": topology_report.model_dump(mode="json"),
            "geometry": geometry_report.model_dump(mode="json"),
            "layout_random_draw_count": layout.random_draw_count,
        }
        if not valid:
            self._preparation.finish_generation_run(
                FinishGenerationRun(
                    campaign_id=campaign_id,
                    run_id=run.id,
                    status=GenerationStatus.FAILED,
                    validation_report=validation_report,
                )
            )
            _log_generation_result(
                run_id=run.id,
                stage="validation",
                diagnostics=diagnostics,
            )
            return DungeonWorkflowResult(
                success=False,
                artifact_id=artifact_id,
                artifact_version_id=None,
                generation_run_id=run.id,
                diagnostics=diagnostics,
                regression_case=_regression_case(
                    request=request,
                    stage="validation",
                    diagnostics=diagnostics,
                ),
            )

        try:
            dm_guide = _build_dm_guide(request, package, model_lineage)
            preparation_readiness = _build_preparation_readiness(dm_guide)
            resolved_dm_notes = dm_notes or _build_dm_notes(request, None, package)
            preview_assets = _preview_assets(package, resolved_dm_notes)
        except ConflictError as error:
            logger.error(
                "dungeon preview generation failed",
                extra={
                    "event_data": {
                        "failure": str(error),
                        "package_id": package.id,
                    }
                },
            )
            render_diagnostic: dict[str, JsonValue] = {
                "code": "studio.preview_failed",
                "message": "Deterministic preview generation failed.",
                "severity": "error",
            }
            failed_report: dict[str, JsonValue] = {
                **validation_report,
                "valid": False,
                "stage": "preview",
                "diagnostics": [render_diagnostic],
            }
            self._preparation.finish_generation_run(
                FinishGenerationRun(
                    campaign_id=campaign_id,
                    run_id=run.id,
                    status=GenerationStatus.FAILED,
                    validation_report=failed_report,
                )
            )
            _log_generation_result(
                run_id=run.id,
                stage="preview",
                diagnostics=(render_diagnostic,),
            )
            return DungeonWorkflowResult(
                success=False,
                artifact_id=artifact_id,
                artifact_version_id=None,
                generation_run_id=run.id,
                diagnostics=(render_diagnostic,),
                regression_case=_regression_case(
                    request=request,
                    stage="preview",
                    diagnostics=(render_diagnostic,),
                ),
            )
        if preparation_readiness is not None:
            validation_report["preparation_readiness"] = (
                preparation_readiness.model_dump(mode="json")
            )
        specification = DungeonStudioSpecification(
            schema_version=_STUDIO_SCHEMA_VERSION,
            layout_request=request,
            package=package,
            dm_notes=resolved_dm_notes,
            dm_guide=dm_guide,
            preparation_readiness=preparation_readiness,
            model_lineage=model_lineage,
        )
        base_assets = (
            _PendingAsset(
                ArtifactAssetRole.SPECIFICATION,
                0,
                "application/json",
                _canonical_json_bytes(specification.model_dump(mode="json")),
            ),
            _PendingAsset(
                ArtifactAssetRole.VALIDATION_REPORT,
                0,
                "application/json",
                _canonical_json_bytes(validation_report),
            ),
            _dm_notes_asset(request, resolved_dm_notes, dm_guide),
        )
        try:
            published = self._preparation.publish_generated_package(
                PublishGeneratedPackage(
                    campaign_id=campaign_id,
                    generation_run_id=run.id,
                    artifact_id=artifact_id,
                    artifact_type=ArtifactType.DUNGEON,
                    title=artifact_title or request.brief.title,
                    visibility_policy=VisibilityPolicy.DM_ONLY,
                    parent_version_id=parent_version_id,
                    schema_version=_VERSION_SCHEMA,
                    specification=specification.model_dump(mode="json"),
                    validation_report=validation_report,
                    change_summary=change_summary,
                    created_by=created_by,
                    assets=tuple(
                        PendingArtifactAsset(
                            role=asset.role,
                            ordinal=asset.ordinal,
                            media_type=asset.media_type,
                            data=asset.data,
                        )
                        for asset in (*base_assets, *preview_assets)
                    ),
                    required_assets=tuple(
                        RequiredArtifactAsset(role=asset.role, ordinal=asset.ordinal)
                        for asset in (*base_assets, *preview_assets)
                    ),
                )
            )
        except Exception:  # publication must not leave a running/successful run
            persistence_diagnostic: dict[str, JsonValue] = {
                "code": "studio.persistence_failed",
                "message": "Generated package publication failed.",
                "severity": "error",
            }
            if (
                self._preparation.get_generation_run(campaign_id, run.id).status
                is GenerationStatus.RUNNING
            ):
                self._preparation.finish_generation_run(
                    FinishGenerationRun(
                        campaign_id=campaign_id,
                        run_id=run.id,
                        status=GenerationStatus.FAILED,
                        validation_report={
                            **validation_report,
                            "valid": False,
                            "stage": "persistence",
                            "diagnostics": [persistence_diagnostic],
                        },
                    )
                )
            _log_generation_result(
                run_id=run.id,
                stage="persistence",
                diagnostics=(persistence_diagnostic,),
            )
            return DungeonWorkflowResult(
                success=False,
                artifact_id=artifact_id,
                artifact_version_id=None,
                generation_run_id=run.id,
                diagnostics=(persistence_diagnostic,),
            )
        _log_generation_result(run_id=run.id, stage="completed", diagnostics=())
        return DungeonWorkflowResult(
            success=True,
            artifact_id=published.artifact.id,
            artifact_version_id=published.version.id,
            generation_run_id=run.id,
            diagnostics=diagnostics,
        )


def _require_preparation_ready(specification: DungeonStudioSpecification) -> None:
    """Keep incomplete generated preparation in draft without changing canon."""

    readiness = specification.preparation_readiness
    if readiness is not None and not readiness.ready:
        raise ConflictError(
            "Dungeon preparation is incomplete and cannot be approved for play."
        )


def _is_unknown_preparation_text(value: str | None) -> bool:
    """Reserve explicit, bounded unknown markers instead of guessing play details."""

    if value is None:
        return True
    return value.strip().casefold() in {
        "unknown",
        "unspecified",
        "not specified",
        "tbd",
    }


def build_dungeon_preparation_readiness(
    guide: DungeonDmGuide | None,
) -> DungeonPreparationReadiness | None:
    """Build provider-free readiness evidence for an exact DM guide."""

    return _build_preparation_readiness(guide)


def _build_preparation_readiness(
    guide: DungeonDmGuide | None,
) -> DungeonPreparationReadiness | None:
    """Derive stable DM-only approval diagnostics from the immutable guide.

    Geometry may be valid while preparation remains incomplete.  The guide preserves
    that explicit unknown for DM review, and this projection prevents approval rather
    than inventing a bypass, trap effect, or puzzle solution.
    """

    if guide is None:
        return None
    diagnostics: list[DungeonPreparationReadinessDiagnostic] = []
    dependency_gate_ids = {item.target_gate_id for item in guide.dependencies}
    for connection in guide.connections:
        if (
            connection.gate_id is not None
            and connection.gate_id not in dependency_gate_ids
        ):
            diagnostics.append(
                DungeonPreparationReadinessDiagnostic(
                    code="dungeon_preparation.lock_dependency_missing",
                    component_id=connection.component_id,
                    map_reference=connection.map_reference,
                    message="A locked or puzzle barrier needs a key or clue dependency.",
                )
            )
    for connection in guide.connections:
        if connection.trap_id is not None and (
            _is_unknown_preparation_text(connection.trap_trigger)
            or _is_unknown_preparation_text(connection.trap_effect)
        ):
            diagnostics.append(
                DungeonPreparationReadinessDiagnostic(
                    code="dungeon_preparation.trap_effect_unknown",
                    component_id=connection.component_id,
                    map_reference=connection.map_reference,
                    message="This trapped door or hatch has unknown trigger/effect details and needs DM completion.",
                )
            )
    for trap in guide.traps:
        if _is_unknown_preparation_text(trap.trigger) or _is_unknown_preparation_text(
            trap.effect
        ):
            diagnostics.append(
                DungeonPreparationReadinessDiagnostic(
                    code="dungeon_preparation.trap_effect_unknown",
                    component_id=trap.marker_id,
                    map_reference=trap.map_reference,
                    message="This trap's trigger/effect is unknown and needs DM completion.",
                )
            )
        if _is_unknown_preparation_text(trap.detection) or _is_unknown_preparation_text(
            trap.disable
        ):
            diagnostics.append(
                DungeonPreparationReadinessDiagnostic(
                    code="dungeon_preparation.trap_method_unknown",
                    component_id=trap.marker_id,
                    map_reference=trap.map_reference,
                    message="This trap needs concrete detection and disable methods.",
                )
            )
    for puzzle in guide.puzzles:
        if any(
            _is_unknown_preparation_text(value)
            for value in (
                puzzle.solution,
                puzzle.content.situation,
                puzzle.content.adjudication,
            )
        ):
            diagnostics.append(
                DungeonPreparationReadinessDiagnostic(
                    code="dungeon_preparation.puzzle_solution_unknown",
                    component_id=puzzle.room_id,
                    map_reference=puzzle.map_reference,
                    message="This puzzle has unknown play details and needs DM completion.",
                )
            )
    for issue in guide.content_issues:
        diagnostics.append(
            DungeonPreparationReadinessDiagnostic(
                code=(
                    "dungeon_preparation.guide_content_missing"
                    if issue.code == "guide_content.required_missing"
                    else "dungeon_preparation.guide_content_invalid"
                ),
                component_id=issue.entry_ref or issue.target_ref or issue.room_ref,
                message=issue.message,
            )
        )
    return DungeonPreparationReadiness(
        schema_version="1.0.0",
        ready=not diagnostics,
        diagnostics=tuple(diagnostics),
    )


def build_dungeon_exploration_enrichment_input(
    package: DungeonPackage,
    selection: DungeonExplorationContextSelection,
) -> DungeonExplorationEnrichmentInput:
    """Slice one trusted exact package into a local exploration-only context."""

    rooms_by_id = {room.id: room for room in package.rooms}
    room = rooms_by_id.get(selection.room_id)
    if room is None:
        raise ConflictError(
            "Exploration context selected an unknown exact exploration room."
        )
    if room.role is not RoomRole.EXPLORATION:
        raise ConflictError(
            "Exploration context selected a room without an exploration role."
        )

    encounter_slots = tuple(
        slot
        for slot in package.encounter_slots
        if slot.room_id == room.id
        and EncounterSlotIntent.EXPLORATION.value in slot.tags
    )
    if len(encounter_slots) != 1:
        raise ConflictError(
            "Exploration context requires one exact exploration encounter slot."
        )
    encounter_slot = encounter_slots[0]

    feature_markers = {
        marker.id: marker
        for marker in package.room_mechanic_markers
        if marker.kind is RoomMechanicMarkerKind.FEATURE
    }
    affordances: list[DungeonExplorationAffordance] = []
    for approval in selection.affordances:
        marker = feature_markers.get(approval.affordance_id)
        if marker is None:
            raise ConflictError(
                "Exploration context selected an unknown exact environmental affordance."
            )
        if marker.room_id != room.id or marker.floor_id != room.floor_id:
            raise ConflictError(
                "Exploration context selected an affordance outside the selected exploration room."
            )
        affordances.append(
            DungeonExplorationAffordance(
                affordance_id=marker.id,
                room_id=marker.room_id,
                floor_id=marker.floor_id,
                position=marker.position,
                use=approval.use,
            )
        )

    return DungeonExplorationEnrichmentInput(
        schema_version=DUNGEON_EXPLORATION_ENRICHMENT_SCHEMA_VERSION,
        package_id=package.id,
        room=DungeonExplorationRoomContext(
            room_id=room.id,
            floor_id=room.floor_id,
            boundary=room.boundary,
            capacity=room.capacity,
            encounter_slot_id=encounter_slot.id,
        ),
        affordances=tuple(affordances),
        pacing_role=selection.pacing_role,
        stakes=selection.stakes,
        constraints=selection.constraints,
    )


def validate_dungeon_exploration_enrichment(
    context: DungeonExplorationEnrichmentInput,
    output: DungeonExplorationEnrichmentOutput,
) -> DungeonExplorationEnrichmentValidationResult:
    """Check one exploration proposal against its exact server-authored context."""

    issues: list[DungeonExplorationEnrichmentIssue] = []
    if output.package_id != context.package_id:
        issues.append(
            DungeonExplorationEnrichmentIssue(
                code="exploration_enrichment.package_mismatch",
                component_id=output.package_id,
                message="Exploration enrichment targets a different dungeon package.",
            )
        )
    if output.room_id != context.room.room_id:
        issues.append(
            DungeonExplorationEnrichmentIssue(
                code="exploration_enrichment.room_mismatch",
                component_id=output.room_id,
                message="Exploration enrichment targets a different exact room.",
            )
        )
    if output.encounter_slot_id != context.room.encounter_slot_id:
        issues.append(
            DungeonExplorationEnrichmentIssue(
                code="exploration_enrichment.encounter_slot_mismatch",
                component_id=output.encounter_slot_id,
                message="Exploration enrichment targets a different exact encounter slot.",
            )
        )
    allowed_affordance_ids = {item.affordance_id for item in context.affordances}
    invalid_affordance_ids = sorted(
        {
            affordance_id
            for approach in output.approaches
            for affordance_id in approach.affordance_ids
            if affordance_id not in allowed_affordance_ids
        }
    )
    issues.extend(
        DungeonExplorationEnrichmentIssue(
            code="exploration_enrichment.affordance_invalid",
            component_id=affordance_id,
            message="Exploration approach uses an affordance outside the approved context.",
        )
        for affordance_id in invalid_affordance_ids
    )
    return DungeonExplorationEnrichmentValidationResult(
        schema_version=DUNGEON_EXPLORATION_ENRICHMENT_SCHEMA_VERSION,
        accepted_output=None if issues else output,
        issues=tuple(issues),
    )


def project_dungeon_exploration_enrichment(
    guide: DungeonDmGuide,
    *,
    plan: DungeonPlan,
    package: DungeonPackage,
    context: DungeonExplorationEnrichmentInput,
    validation: DungeonExplorationEnrichmentValidationResult,
) -> DungeonDmGuide:
    """Merge one accepted exact-ID exploration challenge without package mutation."""

    rebuilt_context = build_dungeon_exploration_enrichment_input(
        package,
        DungeonExplorationContextSelection(
            room_id=context.room.room_id,
            affordances=tuple(
                DungeonExplorationAffordanceApproval(
                    affordance_id=item.affordance_id,
                    use=item.use,
                )
                for item in context.affordances
            ),
            pacing_role=context.pacing_role,
            stakes=context.stakes,
            constraints=context.constraints,
        ),
    )
    if rebuilt_context != context:
        raise ConflictError(
            "Exploration enrichment context does not match the accepted exact package."
        )

    output = validation.accepted_output
    if output is None:
        raise ConflictError("Rejected exploration enrichment cannot be projected.")
    authoritative_validation = validate_dungeon_exploration_enrichment(context, output)
    if authoritative_validation.accepted_output is None:
        raise ConflictError(
            "Exploration enrichment failed exact-ID semantic validation."
        )

    compiled = compile_dungeon_plan(plan)
    if (
        not compiled.accepted
        or compiled.certificate is None
        or compiled.topology is None
        or package.topology != compiled.topology
    ):
        raise ConflictError(
            "Accepted exploration enrichment does not match the generated dungeon plan."
        )
    room_ref_by_id = {item.room_id: item.ref for item in compiled.certificate.rooms}
    room_ref = room_ref_by_id.get(output.room_id)
    if room_ref is None:
        raise ConflictError("Exploration enrichment targets an unknown planned room.")
    planned_room = next(room for room in plan.rooms if room.ref == room_ref)
    if (
        planned_room.role is not RoomRole.EXPLORATION
        or planned_room.encounter is not EncounterSlotIntent.EXPLORATION
    ):
        raise ConflictError(
            "Exploration enrichment targets a room without exploration intent."
        )

    guide_room = next(
        (room for room in guide.rooms if room.room_id == output.room_id), None
    )
    if guide_room is None:
        raise ConflictError(
            "Exploration enrichment targets a room outside the exact guide."
        )
    if guide_room.encounter_slot_id != output.encounter_slot_id:
        raise ConflictError(
            "Exploration enrichment targets a slot outside the exact guide."
        )
    if guide_room.encounter_content is not None:
        raise ConflictError(
            "Exploration enrichment cannot replace accepted exploration content."
        )

    pacing = context.pacing_role.replace("_", " ").capitalize()
    encounter_content = DungeonGuideRunnableContent(
        situation=" ".join((*output.observable_cues, f"Stakes: {context.stakes}")),
        adjudication=(
            f"Pacing: {pacing}. Escalation: {output.escalation} "
            f"Recovery: {output.recovery}"
        ),
        player_choices=tuple(
            DungeonGuidePlayerChoice(
                action=approach.action,
                outcome=(
                    f"{approach.adjudication} Consequence: {approach.consequence}"
                ),
            )
            for approach in output.approaches
        ),
    )
    rooms = tuple(
        room.model_copy(update={"encounter_content": encounter_content})
        if room.room_id == output.room_id
        else room
        for room in guide.rooms
    )
    content_issues = tuple(
        issue
        for issue in guide.content_issues
        if not (
            issue.code == "guide_content.required_missing"
            and issue.kind == "encounter"
            and issue.room_ref == room_ref
        )
    )
    document = guide.model_dump(mode="python")
    document["rooms"] = rooms
    document["content_issues"] = content_issues
    return DungeonDmGuide.model_validate(document)


def build_dungeon_feature_interaction_enrichment_input(
    package: DungeonPackage,
    guide: DungeonDmGuide,
    selection: DungeonFeatureInteractionContextSelection,
) -> DungeonFeatureInteractionEnrichmentInput:
    """Slice one exact package/guide feature into a local interaction context."""

    rooms_by_id = {room.id: room for room in package.rooms}
    room = rooms_by_id.get(selection.room_id)
    if room is None:
        raise ConflictError(
            "Feature interaction selected an unknown exact feature room."
        )

    marker = next(
        (
            item
            for item in package.room_mechanic_markers
            if item.id == selection.feature_id
            and item.kind is RoomMechanicMarkerKind.FEATURE
        ),
        None,
    )
    if marker is None:
        raise ConflictError(
            "Feature interaction selected an unknown exact room feature."
        )
    if marker.room_id != room.id or marker.floor_id != room.floor_id:
        raise ConflictError(
            "Feature interaction selected a feature outside the selected feature room."
        )

    guide_feature = next(
        (item for item in guide.features if item.marker_id == marker.id),
        None,
    )
    if guide_feature is None:
        raise ConflictError(
            "Feature interaction selected a feature outside the exact guide."
        )
    if guide_feature.room_id != room.id:
        raise ConflictError(
            "Feature interaction guide target does not match the exact feature room."
        )

    return DungeonFeatureInteractionEnrichmentInput(
        schema_version=DUNGEON_FEATURE_INTERACTION_ENRICHMENT_SCHEMA_VERSION,
        package_id=package.id,
        room=DungeonFeatureInteractionRoomContext(
            room_id=room.id,
            floor_id=room.floor_id,
            boundary=room.boundary,
            capacity=room.capacity,
        ),
        feature=DungeonFeatureInteractionFeature(
            feature_id=marker.id,
            room_id=marker.room_id,
            floor_id=marker.floor_id,
            position=marker.position,
            kind=guide_feature.kind,
            name=guide_feature.name,
            description=guide_feature.description,
        ),
        interaction_goal=selection.interaction_goal,
        stakes=selection.stakes,
        constraints=selection.constraints,
    )


def validate_dungeon_feature_interaction_enrichment(
    context: DungeonFeatureInteractionEnrichmentInput,
    output: DungeonFeatureInteractionEnrichmentOutput,
) -> DungeonFeatureInteractionValidationResult:
    """Check one feature-only proposal against its exact trusted context."""

    issues: list[DungeonFeatureInteractionIssue] = []
    if output.package_id != context.package_id:
        issues.append(
            DungeonFeatureInteractionIssue(
                code="feature_interaction.package_mismatch",
                component_id=output.package_id,
                message="Feature interaction targets a different dungeon package.",
            )
        )
    if output.room_id != context.room.room_id:
        issues.append(
            DungeonFeatureInteractionIssue(
                code="feature_interaction.room_mismatch",
                component_id=output.room_id,
                message="Feature interaction targets a different exact room.",
            )
        )
    if output.feature_id != context.feature.feature_id:
        issues.append(
            DungeonFeatureInteractionIssue(
                code="feature_interaction.feature_mismatch",
                component_id=output.feature_id,
                message="Feature interaction targets a different exact feature.",
            )
        )
    return DungeonFeatureInteractionValidationResult(
        schema_version=DUNGEON_FEATURE_INTERACTION_ENRICHMENT_SCHEMA_VERSION,
        accepted_output=None if issues else output,
        issues=tuple(issues),
    )


def project_dungeon_feature_interaction_enrichment(
    guide: DungeonDmGuide,
    *,
    plan: DungeonPlan,
    package: DungeonPackage,
    context: DungeonFeatureInteractionEnrichmentInput,
    validation: DungeonFeatureInteractionValidationResult,
) -> DungeonDmGuide:
    """Merge one accepted exact feature interaction without cross-task mutation."""

    guide_feature = next(
        (
            item
            for item in guide.features
            if item.marker_id == context.feature.feature_id
        ),
        None,
    )
    if guide_feature is not None and guide_feature.content is not None:
        raise ConflictError(
            "Feature interaction cannot replace accepted feature interaction content."
        )

    rebuilt_context = build_dungeon_feature_interaction_enrichment_input(
        package,
        guide,
        DungeonFeatureInteractionContextSelection(
            room_id=context.room.room_id,
            feature_id=context.feature.feature_id,
            interaction_goal=context.interaction_goal,
            stakes=context.stakes,
            constraints=context.constraints,
        ),
    )
    if rebuilt_context != context:
        raise ConflictError(
            "Feature interaction context does not match the accepted exact package and guide."
        )

    output = validation.accepted_output
    if output is None:
        raise ConflictError("Rejected feature interaction cannot be projected.")
    authoritative_validation = validate_dungeon_feature_interaction_enrichment(
        context, output
    )
    if authoritative_validation.accepted_output is None:
        raise ConflictError("Feature interaction failed exact-ID semantic validation.")

    compiled = compile_dungeon_plan(plan)
    if (
        not compiled.accepted
        or compiled.certificate is None
        or compiled.topology is None
        or compiled.mechanics_plan is None
        or package.topology != compiled.topology
    ):
        raise ConflictError(
            "Accepted feature interaction does not match the generated dungeon plan."
        )
    room_ref_by_id = {item.room_id: item.ref for item in compiled.certificate.rooms}
    room_ref = room_ref_by_id.get(output.room_id)
    if room_ref is None:
        raise ConflictError("Feature interaction targets an unknown planned room.")
    feature_plan = next(
        (
            item
            for item in compiled.mechanics_plan.room_features
            if item.id == output.feature_id and item.room_id == output.room_id
        ),
        None,
    )
    planned_content = next(
        (item for item in plan.room_contents if item.room_ref == room_ref),
        None,
    )
    if (
        feature_plan is None
        or planned_content is None
        or planned_content.feature is None
    ):
        raise ConflictError(
            "Feature interaction targets a feature outside the accepted plan."
        )
    if guide_feature is None or guide_feature.room_id != output.room_id:
        raise ConflictError(
            "Feature interaction targets a feature outside the exact guide."
        )

    adjudication_sections = [f"Interaction goal: {context.interaction_goal}"]
    if output.reset_or_retry is not None:
        adjudication_sections.append(f"Reset or retry: {output.reset_or_retry}")
    content = DungeonGuideRunnableContent(
        situation=" ".join((*output.observable_setup, f"Stakes: {context.stakes}")),
        adjudication=" ".join(adjudication_sections),
        player_choices=tuple(
            DungeonGuidePlayerChoice(
                action=affordance.action,
                outcome=(
                    f"{affordance.adjudication} Consequence: {affordance.consequence}"
                ),
            )
            for affordance in output.affordances
        ),
    )
    features = tuple(
        feature.model_copy(update={"content": content})
        if feature.marker_id == output.feature_id
        else feature
        for feature in guide.features
    )
    content_issues = tuple(
        issue
        for issue in guide.content_issues
        if not (
            issue.code == "guide_content.required_missing"
            and issue.kind == "feature"
            and issue.room_ref == room_ref
        )
    )
    document = guide.model_dump(mode="python")
    document["features"] = features
    document["content_issues"] = content_issues
    return DungeonDmGuide.model_validate(document)


def build_dungeon_trap_enrichment_input(
    package: DungeonPackage,
    guide: DungeonDmGuide,
    selection: DungeonTrapContextSelection,
) -> DungeonTrapEnrichmentInput:
    """Join one exact trap marker, guide entry, geometry, and code-owned DCs."""

    rooms_by_id = {room.id: room for room in package.rooms}
    room = rooms_by_id.get(selection.room_id)
    if room is None:
        raise ConflictError("Trap enrichment selected an unknown exact trap room.")

    marker = next(
        (
            item
            for item in package.room_mechanic_markers
            if item.id == selection.trap_id and item.kind is RoomMechanicMarkerKind.TRAP
        ),
        None,
    )
    if marker is None:
        raise ConflictError("Trap enrichment selected an unknown exact room trap.")
    if marker.room_id != room.id or marker.floor_id != room.floor_id:
        raise ConflictError(
            "Trap enrichment selected a trap outside the selected trap room."
        )

    guide_trap = next(
        (item for item in guide.traps if item.marker_id == marker.id),
        None,
    )
    if guide_trap is None:
        raise ConflictError("Trap enrichment selected a trap outside the exact guide.")
    if guide_trap.room_id != room.id:
        raise ConflictError(
            "Trap enrichment guide target does not match the exact trap room."
        )

    return DungeonTrapEnrichmentInput(
        schema_version=DUNGEON_TRAP_ENRICHMENT_SCHEMA_VERSION,
        package_id=package.id,
        room=DungeonTrapRoomContext(
            room_id=room.id,
            floor_id=room.floor_id,
            boundary=room.boundary,
            capacity=room.capacity,
        ),
        trap=DungeonTrapMechanic(
            trap_id=marker.id,
            room_id=marker.room_id,
            floor_id=marker.floor_id,
            position=marker.position,
            name=guide_trap.name,
            current_warning=guide_trap.warning,
            current_trigger=guide_trap.trigger,
            current_effect=guide_trap.effect,
            current_detection=guide_trap.detection,
            current_disable=guide_trap.disable,
            current_consequences=guide_trap.consequences,
            current_reset_or_recovery=guide_trap.reset_or_recovery,
            detection_difficulty=guide_trap.detection_difficulty,
            disable_difficulty=guide_trap.disable_difficulty,
        ),
        stakes=selection.stakes,
        constraints=selection.constraints,
    )


def validate_dungeon_trap_enrichment(
    context: DungeonTrapEnrichmentInput,
    output: DungeonTrapEnrichmentOutput,
) -> DungeonTrapValidationResult:
    """Check one trap-only proposal against its exact trusted context."""

    issues: list[DungeonTrapIssue] = []
    if output.package_id != context.package_id:
        issues.append(
            DungeonTrapIssue(
                code="trap_enrichment.package_mismatch",
                component_id=output.package_id,
                message="Trap enrichment targets a different dungeon package.",
            )
        )
    if output.room_id != context.room.room_id:
        issues.append(
            DungeonTrapIssue(
                code="trap_enrichment.room_mismatch",
                component_id=output.room_id,
                message="Trap enrichment targets a different exact room.",
            )
        )
    if output.trap_id != context.trap.trap_id:
        issues.append(
            DungeonTrapIssue(
                code="trap_enrichment.trap_mismatch",
                component_id=output.trap_id,
                message="Trap enrichment targets a different exact trap.",
            )
        )
    return DungeonTrapValidationResult(
        schema_version=DUNGEON_TRAP_ENRICHMENT_SCHEMA_VERSION,
        accepted_output=None if issues else output,
        issues=tuple(issues),
    )


def project_dungeon_trap_enrichment(
    guide: DungeonDmGuide,
    *,
    plan: DungeonPlan,
    package: DungeonPackage,
    context: DungeonTrapEnrichmentInput,
    validation: DungeonTrapValidationResult,
) -> DungeonDmGuide:
    """Merge accepted exact trap content without changing code-owned mechanics."""

    guide_trap = next(
        (item for item in guide.traps if item.marker_id == context.trap.trap_id),
        None,
    )
    if guide_trap is not None and all(
        value is not None
        for value in (
            guide_trap.warning,
            guide_trap.trigger,
            guide_trap.effect,
            guide_trap.detection,
            guide_trap.disable,
        )
    ):
        raise ConflictError("Trap enrichment cannot replace accepted trap content.")

    rebuilt_context = build_dungeon_trap_enrichment_input(
        package,
        guide,
        DungeonTrapContextSelection(
            room_id=context.room.room_id,
            trap_id=context.trap.trap_id,
            stakes=context.stakes,
            constraints=context.constraints,
        ),
    )
    if rebuilt_context != context:
        raise ConflictError(
            "Trap enrichment context does not match the accepted exact package and guide."
        )

    output = validation.accepted_output
    if output is None:
        raise ConflictError("Rejected trap enrichment cannot be projected.")
    authoritative_validation = validate_dungeon_trap_enrichment(context, output)
    if authoritative_validation.accepted_output is None:
        raise ConflictError("Trap enrichment failed exact-ID semantic validation.")

    compiled = compile_dungeon_plan(plan)
    if (
        not compiled.accepted
        or compiled.certificate is None
        or compiled.topology is None
        or compiled.mechanics_plan is None
        or package.topology != compiled.topology
    ):
        raise ConflictError(
            "Accepted trap enrichment does not match the generated dungeon plan."
        )
    room_ref_by_id = {item.room_id: item.ref for item in compiled.certificate.rooms}
    room_ref = room_ref_by_id.get(output.room_id)
    if room_ref is None:
        raise ConflictError("Trap enrichment targets an unknown planned room.")
    trap_plan = next(
        (
            item
            for item in compiled.mechanics_plan.room_traps
            if item.id == output.trap_id and item.room_id == output.room_id
        ),
        None,
    )
    planned_content = next(
        (item for item in plan.room_contents if item.room_ref == room_ref),
        None,
    )
    if trap_plan is None or planned_content is None or planned_content.trap is None:
        raise ConflictError("Trap enrichment targets a trap outside the accepted plan.")
    if guide_trap is None or guide_trap.room_id != output.room_id:
        raise ConflictError("Trap enrichment targets a trap outside the exact guide.")
    if (
        trap_plan.detection_difficulty != context.trap.detection_difficulty
        or trap_plan.disable_difficulty != context.trap.disable_difficulty
        or guide_trap.detection_difficulty != context.trap.detection_difficulty
        or guide_trap.disable_difficulty != context.trap.disable_difficulty
    ):
        raise ConflictError(
            "Trap enrichment cannot change deterministic trap mechanics."
        )

    traps = tuple(
        trap.model_copy(
            update={
                "warning": output.observable_warning,
                "trigger": output.trigger,
                "effect": output.effect_narration,
                "detection": output.detection_method,
                "disable": output.disable_operation,
                "consequences": output.consequences,
                "reset_or_recovery": output.reset_or_recovery,
            }
        )
        if trap.marker_id == output.trap_id
        else trap
        for trap in guide.traps
    )
    document = guide.model_dump(mode="python")
    document["traps"] = traps
    return DungeonDmGuide.model_validate(document)


def build_dungeon_objective_enrichment_input(
    package: DungeonPackage,
    guide: DungeonDmGuide,
    selection: DungeonObjectiveContextSelection,
) -> DungeonObjectiveEnrichmentInput:
    """Join one exact objective to local geometry and accepted mechanic summaries."""

    rooms_by_id = {room.id: room for room in package.rooms}
    room = rooms_by_id.get(selection.room_id)
    if room is None:
        raise ConflictError(
            "Objective enrichment selected an unknown exact objective room."
        )
    if room.role is not RoomRole.OBJECTIVE:
        raise ConflictError(
            "Objective enrichment selected a room without an objective role."
        )

    marker = next(
        (
            item
            for item in package.room_mechanic_markers
            if item.id == selection.objective_id
            and item.kind is RoomMechanicMarkerKind.OBJECTIVE
        ),
        None,
    )
    if marker is None:
        raise ConflictError(
            "Objective enrichment selected an unknown exact room objective."
        )
    if marker.room_id != room.id or marker.floor_id != room.floor_id:
        raise ConflictError(
            "Objective enrichment selected an objective outside the selected objective room."
        )

    guide_objective = next(
        (item for item in guide.objectives if item.marker_id == marker.id),
        None,
    )
    if guide_objective is None:
        raise ConflictError(
            "Objective enrichment selected an objective outside the exact guide."
        )
    if guide_objective.room_id != room.id:
        raise ConflictError(
            "Objective enrichment guide target does not match the exact objective room."
        )

    accepted_by_id = _accepted_objective_mechanics(package, guide)
    accepted_mechanics: list[DungeonObjectiveAcceptedMechanic] = []
    for mechanic_id in selection.mechanic_ids:
        mechanic = accepted_by_id.get(mechanic_id)
        if mechanic is None:
            raise ConflictError(
                "Objective enrichment selected an unknown or unaccepted exact mechanic."
            )
        accepted_mechanics.append(mechanic)

    current_content = guide_objective.content
    return DungeonObjectiveEnrichmentInput(
        schema_version=DUNGEON_OBJECTIVE_ENRICHMENT_SCHEMA_VERSION,
        package_id=package.id,
        room=DungeonObjectiveRoomContext(
            room_id=room.id,
            floor_id=room.floor_id,
            boundary=room.boundary,
            capacity=room.capacity,
        ),
        objective=DungeonObjectiveTarget(
            objective_id=marker.id,
            room_id=marker.room_id,
            floor_id=marker.floor_id,
            position=marker.position,
            kind=guide_objective.kind,
            name=guide_objective.name,
            current_situation=(
                current_content.situation if current_content is not None else None
            ),
            current_adjudication=(
                current_content.adjudication if current_content is not None else None
            ),
            current_resolutions=(
                tuple(
                    DungeonObjectiveCurrentResolution(
                        action=item.action,
                        outcome=item.outcome,
                    )
                    for item in current_content.player_choices
                )
                if current_content is not None
                else ()
            ),
        ),
        accepted_mechanics=tuple(accepted_mechanics),
        stakes=selection.stakes,
        constraints=selection.constraints,
    )


def _accepted_objective_mechanics(
    package: DungeonPackage,
    guide: DungeonDmGuide,
) -> dict[str, DungeonObjectiveAcceptedMechanic]:
    """Index only complete accepted mechanics using bounded guide-owned summaries."""

    accepted: dict[str, DungeonObjectiveAcceptedMechanic] = {}
    package_rooms_by_id = {room.id: room for room in package.rooms}
    guide_rooms_by_id = {room.room_id: room for room in guide.rooms}
    encounter_slots_by_id = {slot.id: slot for slot in package.encounter_slots}
    markers_by_id = {marker.id: marker for marker in package.room_mechanic_markers}

    for puzzle in guide.puzzles:
        package_room = package_rooms_by_id.get(puzzle.room_id)
        if package_room is None or package_room.role is not RoomRole.PUZZLE:
            continue
        accepted[puzzle.room_id] = DungeonObjectiveAcceptedMechanic(
            mechanic_id=puzzle.room_id,
            room_id=puzzle.room_id,
            kind="puzzle",
            name=puzzle.name,
            observable_summary=puzzle.content.situation,
            resolution_summary=puzzle.content.adjudication,
            outcome_summaries=tuple(
                item.outcome for item in puzzle.content.player_choices
            ),
        )

    for room in guide.rooms:
        if room.encounter_slot_id is None or room.encounter_content is None:
            continue
        encounter_slot = encounter_slots_by_id.get(room.encounter_slot_id)
        if (
            encounter_slot is None
            or encounter_slot.room_id != room.room_id
            or room.encounter_slot is not EncounterSlotIntent.EXPLORATION
            or EncounterSlotIntent.EXPLORATION.value not in encounter_slot.tags
        ):
            continue
        accepted[room.encounter_slot_id] = DungeonObjectiveAcceptedMechanic(
            mechanic_id=room.encounter_slot_id,
            room_id=room.room_id,
            kind="exploration",
            name=room.name,
            observable_summary=room.encounter_content.situation,
            resolution_summary=room.encounter_content.adjudication,
            outcome_summaries=tuple(
                item.outcome for item in room.encounter_content.player_choices
            ),
        )

    for feature in guide.features:
        if feature.content is None:
            continue
        marker = markers_by_id.get(feature.marker_id)
        if (
            marker is None
            or marker.kind is not RoomMechanicMarkerKind.FEATURE
            or marker.room_id != feature.room_id
        ):
            continue
        accepted[feature.marker_id] = DungeonObjectiveAcceptedMechanic(
            mechanic_id=feature.marker_id,
            room_id=feature.room_id,
            kind="feature",
            name=feature.name,
            observable_summary=feature.content.situation,
            resolution_summary=feature.content.adjudication,
            outcome_summaries=tuple(
                item.outcome for item in feature.content.player_choices
            ),
        )

    for trap in guide.traps:
        marker = markers_by_id.get(trap.marker_id)
        if (
            marker is None
            or marker.kind is not RoomMechanicMarkerKind.TRAP
            or marker.room_id != trap.room_id
            or not all(
                value is not None
                for value in (
                    trap.warning,
                    trap.trigger,
                    trap.effect,
                    trap.detection,
                    trap.disable,
                )
            )
        ):
            continue
        assert trap.warning is not None
        assert trap.effect is not None
        assert trap.disable is not None
        accepted[trap.marker_id] = DungeonObjectiveAcceptedMechanic(
            mechanic_id=trap.marker_id,
            room_id=trap.room_id,
            kind="trap",
            name=trap.name,
            observable_summary=trap.warning,
            resolution_summary=trap.disable,
            outcome_summaries=(trap.effect, *trap.consequences),
        )

    if any(item.room_id not in guide_rooms_by_id for item in accepted.values()):
        raise ConflictError(
            "Objective enrichment found accepted mechanics outside the exact guide."
        )
    return accepted


def validate_dungeon_objective_enrichment(
    context: DungeonObjectiveEnrichmentInput,
    output: DungeonObjectiveEnrichmentOutput,
) -> DungeonObjectiveValidationResult:
    """Check one objective-only proposal against exact IDs and accepted mechanics."""

    issues: list[DungeonObjectiveIssue] = []
    if output.package_id != context.package_id:
        issues.append(
            DungeonObjectiveIssue(
                code="objective_enrichment.package_mismatch",
                component_id=output.package_id,
                message="Objective enrichment targets a different dungeon package.",
            )
        )
    if output.room_id != context.room.room_id:
        issues.append(
            DungeonObjectiveIssue(
                code="objective_enrichment.room_mismatch",
                component_id=output.room_id,
                message="Objective enrichment targets a different exact room.",
            )
        )
    if output.objective_id != context.objective.objective_id:
        issues.append(
            DungeonObjectiveIssue(
                code="objective_enrichment.objective_mismatch",
                component_id=output.objective_id,
                message="Objective enrichment targets a different exact objective.",
            )
        )
    accepted_mechanic_ids = {item.mechanic_id for item in context.accepted_mechanics}
    invalid_mechanic_ids = sorted(
        {
            mechanic_id
            for resolution in output.resolutions
            for mechanic_id in resolution.mechanic_ids
            if mechanic_id not in accepted_mechanic_ids
        }
    )
    issues.extend(
        DungeonObjectiveIssue(
            code="objective_enrichment.mechanic_invalid",
            component_id=mechanic_id,
            message=(
                "Objective resolution uses a mechanic outside the accepted context."
            ),
        )
        for mechanic_id in invalid_mechanic_ids
    )
    return DungeonObjectiveValidationResult(
        schema_version=DUNGEON_OBJECTIVE_ENRICHMENT_SCHEMA_VERSION,
        accepted_output=None if issues else output,
        issues=tuple(issues),
    )


def project_dungeon_objective_enrichment(
    guide: DungeonDmGuide,
    *,
    plan: DungeonPlan,
    package: DungeonPackage,
    context: DungeonObjectiveEnrichmentInput,
    validation: DungeonObjectiveValidationResult,
) -> DungeonDmGuide:
    """Merge one accepted exact objective without changing structure or mechanics."""

    guide_objective = next(
        (
            item
            for item in guide.objectives
            if item.marker_id == context.objective.objective_id
        ),
        None,
    )
    if guide_objective is not None and guide_objective.content is not None:
        raise ConflictError(
            "Objective enrichment cannot replace accepted objective content."
        )

    rebuilt_context = build_dungeon_objective_enrichment_input(
        package,
        guide,
        DungeonObjectiveContextSelection(
            room_id=context.room.room_id,
            objective_id=context.objective.objective_id,
            mechanic_ids=tuple(item.mechanic_id for item in context.accepted_mechanics),
            stakes=context.stakes,
            constraints=context.constraints,
        ),
    )
    if rebuilt_context != context:
        raise ConflictError(
            "Objective enrichment context does not match the accepted exact package and guide."
        )

    output = validation.accepted_output
    if output is None:
        raise ConflictError("Rejected objective enrichment cannot be projected.")
    authoritative_validation = validate_dungeon_objective_enrichment(context, output)
    if authoritative_validation.accepted_output is None:
        raise ConflictError("Objective enrichment failed exact-ID semantic validation.")

    compiled = compile_dungeon_plan(plan)
    if (
        not compiled.accepted
        or compiled.certificate is None
        or compiled.topology is None
        or compiled.mechanics_plan is None
        or package.topology != compiled.topology
    ):
        raise ConflictError(
            "Accepted objective enrichment does not match the generated dungeon plan."
        )
    room_ref_by_id = {item.room_id: item.ref for item in compiled.certificate.rooms}
    room_ref = room_ref_by_id.get(output.room_id)
    if room_ref is None:
        raise ConflictError("Objective enrichment targets an unknown planned room.")
    planned_room = next(room for room in plan.rooms if room.ref == room_ref)
    objective_plan = next(
        (
            item
            for item in compiled.mechanics_plan.room_objectives
            if item.id == output.objective_id and item.room_id == output.room_id
        ),
        None,
    )
    planned_content = next(
        (item for item in plan.room_contents if item.room_ref == room_ref),
        None,
    )
    if (
        planned_room.role is not RoomRole.OBJECTIVE
        or objective_plan is None
        or planned_content is None
        or planned_content.objective != objective_plan.name
    ):
        raise ConflictError(
            "Objective enrichment targets an objective outside the accepted plan."
        )
    if (
        guide_objective is None
        or guide_objective.room_id != output.room_id
        or guide_objective.kind != objective_plan.kind
        or guide_objective.name != objective_plan.name
        or context.objective.kind != objective_plan.kind
        or context.objective.name != objective_plan.name
    ):
        raise ConflictError(
            "Objective enrichment cannot change the exact guide objective."
        )

    content = DungeonGuideRunnableContent(
        situation=output.observable_goal,
        adjudication=(
            f"{output.resolution_guidance} "
            f"Setback or aftermath: {output.setback_or_aftermath}"
        ),
        player_choices=tuple(
            DungeonGuidePlayerChoice(action=item.action, outcome=item.outcome)
            for item in output.resolutions
        ),
    )
    objectives = tuple(
        objective.model_copy(update={"content": content})
        if objective.marker_id == output.objective_id
        else objective
        for objective in guide.objectives
    )
    content_issues = tuple(
        issue
        for issue in guide.content_issues
        if not (
            issue.code == "guide_content.required_missing"
            and issue.kind == "objective"
            and issue.room_ref == room_ref
        )
    )
    document = guide.model_dump(mode="python")
    document["objectives"] = objectives
    document["content_issues"] = content_issues
    return DungeonDmGuide.model_validate(document)


def build_dungeon_room_narrative_enrichment_input(
    package: DungeonPackage,
    guide: DungeonDmGuide,
    selection: DungeonRoomNarrativeContextSelection,
) -> DungeonRoomNarrativeEnrichmentInput:
    """Build a homogeneous room-prose context from exact observable state."""

    package_rooms_by_id = {room.id: room for room in package.rooms}
    guide_rooms_by_id = {room.room_id: room for room in guide.rooms}
    accepted_mechanics = _accepted_room_narrative_mechanics(package, guide)
    rooms: list[DungeonRoomNarrativeRoomContext] = []
    for room_id in selection.room_ids:
        package_room = package_rooms_by_id.get(room_id)
        if package_room is None:
            raise ConflictError(
                "Room narrative context selected an unknown exact narrative room."
            )
        guide_room = guide_rooms_by_id.get(room_id)
        if guide_room is None:
            raise ConflictError(
                "Room narrative context selected a room outside the exact guide."
            )
        if (
            guide_room.floor_id != package_room.floor_id
            or guide_room.role is not package_room.role
        ):
            raise ConflictError(
                "Room narrative guide state does not match the exact package room."
            )
        local_mechanics = accepted_mechanics.get(room_id, ())
        required_kinds: set[str] = set()
        if package_room.role is RoomRole.PUZZLE:
            required_kinds.add("puzzle")
        if guide_room.encounter_slot is EncounterSlotIntent.EXPLORATION:
            required_kinds.add("exploration")
        if any(item.room_id == room_id for item in guide.features):
            required_kinds.add("feature")
        if any(item.room_id == room_id for item in guide.traps):
            required_kinds.add("trap")
        if any(item.room_id == room_id for item in guide.objectives):
            required_kinds.add("objective")
        accepted_kinds = {item.kind for item in local_mechanics}
        if not required_kinds.issubset(accepted_kinds):
            raise ConflictError(
                "Room narrative context requires accepted local mechanics before narrative authoring."
            )
        rooms.append(
            DungeonRoomNarrativeRoomContext(
                room_id=package_room.id,
                floor_id=package_room.floor_id,
                boundary=package_room.boundary,
                capacity=package_room.capacity,
                presentation_number=guide_room.presentation_number,
                name=guide_room.name,
                role=guide_room.role,
                tags=guide_room.tags,
                current_read_aloud=guide_room.read_aloud,
                current_observable_framing=guide_room.sensory_details,
                accepted_mechanics=local_mechanics,
            )
        )
    return DungeonRoomNarrativeEnrichmentInput(
        schema_version=DUNGEON_ROOM_NARRATIVE_ENRICHMENT_SCHEMA_VERSION,
        package_id=package.id,
        rooms=tuple(rooms),
        tone=selection.tone,
        constraints=selection.constraints,
    )


def _accepted_room_narrative_mechanics(
    package: DungeonPackage,
    guide: DungeonDmGuide,
) -> dict[str, tuple[DungeonRoomNarrativeAcceptedMechanic, ...]]:
    """Copy only player-observable summaries from complete exact mechanics."""

    mechanics: list[DungeonRoomNarrativeAcceptedMechanic] = [
        DungeonRoomNarrativeAcceptedMechanic(
            mechanic_id=item.mechanic_id,
            room_id=item.room_id,
            kind=item.kind,
            name=item.name,
            observable_summary=item.observable_summary,
        )
        for item in _accepted_objective_mechanics(package, guide).values()
    ]
    objective_markers = {
        marker.id: marker
        for marker in package.room_mechanic_markers
        if marker.kind is RoomMechanicMarkerKind.OBJECTIVE
    }
    for objective in guide.objectives:
        marker = objective_markers.get(objective.marker_id)
        if (
            objective.content is None
            or marker is None
            or marker.room_id != objective.room_id
        ):
            continue
        mechanics.append(
            DungeonRoomNarrativeAcceptedMechanic(
                mechanic_id=objective.marker_id,
                room_id=objective.room_id,
                kind="objective",
                name=objective.name,
                observable_summary=objective.content.situation,
            )
        )

    grouped: dict[str, list[DungeonRoomNarrativeAcceptedMechanic]] = {}
    for mechanic in mechanics:
        grouped.setdefault(mechanic.room_id, []).append(mechanic)
    return {
        room_id: tuple(sorted(items, key=lambda item: (item.kind, item.mechanic_id)))
        for room_id, items in grouped.items()
    }


def validate_dungeon_room_narrative_enrichment(
    context: DungeonRoomNarrativeEnrichmentInput,
    output: DungeonRoomNarrativeEnrichmentOutput,
) -> DungeonRoomNarrativeValidationResult:
    """Require the output to cover exactly the trusted selected room set."""

    issues: list[DungeonRoomNarrativeIssue] = []
    if output.package_id != context.package_id:
        issues.append(
            DungeonRoomNarrativeIssue(
                code="room_narrative_enrichment.package_mismatch",
                component_id=output.package_id,
                message=(
                    "Room narrative enrichment targets a different dungeon package."
                ),
            )
        )
    selected_room_ids = {room.room_id for room in context.rooms}
    output_room_ids = {room.room_id for room in output.rooms}
    issues.extend(
        DungeonRoomNarrativeIssue(
            code="room_narrative_enrichment.room_invalid",
            component_id=room.room_id,
            message=(
                "Room narrative enrichment targets a room outside the selected context."
            ),
        )
        for room in output.rooms
        if room.room_id not in selected_room_ids
    )
    issues.extend(
        DungeonRoomNarrativeIssue(
            code="room_narrative_enrichment.room_missing",
            component_id=room.room_id,
            message="Room narrative enrichment omits a selected exact room.",
        )
        for room in context.rooms
        if room.room_id not in output_room_ids
    )
    return DungeonRoomNarrativeValidationResult(
        schema_version=DUNGEON_ROOM_NARRATIVE_ENRICHMENT_SCHEMA_VERSION,
        accepted_output=None if issues else output,
        issues=tuple(issues),
    )


def project_dungeon_room_narrative_enrichment(
    guide: DungeonDmGuide,
    *,
    plan: DungeonPlan,
    package: DungeonPackage,
    context: DungeonRoomNarrativeEnrichmentInput,
    validation: DungeonRoomNarrativeValidationResult,
) -> DungeonDmGuide:
    """Merge accepted observable prose into only the selected exact rooms."""

    selected_room_ids = {room.room_id for room in context.rooms}
    if any(
        room.room_id in selected_room_ids and room.read_aloud is not None
        for room in guide.rooms
    ):
        raise ConflictError(
            "Room narrative enrichment cannot replace accepted room narrative content."
        )

    rebuilt_context = build_dungeon_room_narrative_enrichment_input(
        package,
        guide,
        DungeonRoomNarrativeContextSelection(
            room_ids=tuple(room.room_id for room in context.rooms),
            tone=context.tone,
            constraints=context.constraints,
        ),
    )
    if rebuilt_context != context:
        raise ConflictError(
            "Room narrative context does not match the accepted exact package and guide."
        )

    output = validation.accepted_output
    if output is None:
        raise ConflictError("Rejected room narrative enrichment cannot be projected.")
    authoritative_validation = validate_dungeon_room_narrative_enrichment(
        context, output
    )
    if authoritative_validation.accepted_output is None:
        raise ConflictError(
            "Room narrative enrichment failed exact-ID semantic validation."
        )

    compiled = compile_dungeon_plan(plan)
    if (
        not compiled.accepted
        or compiled.certificate is None
        or compiled.topology is None
        or package.topology != compiled.topology
    ):
        raise ConflictError(
            "Accepted room narratives do not match the generated dungeon plan."
        )
    room_ref_by_id = {item.room_id: item.ref for item in compiled.certificate.rooms}
    if not selected_room_ids.issubset(room_ref_by_id):
        raise ConflictError(
            "Room narrative enrichment targets a room outside the accepted plan."
        )

    output_by_room_id = {room.room_id: room for room in output.rooms}
    rooms = tuple(
        room.model_copy(
            update={
                "read_aloud": output_by_room_id[room.room_id].read_aloud,
                "sensory_details": output_by_room_id[room.room_id].observable_framing,
            }
        )
        if room.room_id in selected_room_ids
        else room
        for room in guide.rooms
    )
    selected_room_refs = {room_ref_by_id[room_id] for room_id in selected_room_ids}
    content_issues = tuple(
        issue
        for issue in guide.content_issues
        if not (
            issue.code == "guide_content.required_missing"
            and issue.kind == "room"
            and issue.room_ref in selected_room_refs
        )
    )
    document = guide.model_dump(mode="python")
    document["rooms"] = rooms
    document["content_issues"] = content_issues
    return DungeonDmGuide.model_validate(document)


def build_dungeon_puzzle_enrichment_input(
    package: DungeonPackage,
    selection: DungeonPuzzleContextSelection,
) -> DungeonPuzzleEnrichmentInput:
    """Slice one trusted exact package into a narrow puzzle-only context."""

    rooms_by_id = {room.id: room for room in package.rooms}
    room = rooms_by_id.get(selection.room_id)
    if room is None:
        raise ConflictError("Puzzle context selected an unknown exact puzzle room.")
    if room.role is not RoomRole.PUZZLE:
        raise ConflictError("Puzzle context selected a room without a puzzle role.")

    local_connections = tuple(
        connection
        for connection in package.topology.connections
        if room.id in (connection.from_room_id, connection.to_room_id)
    )
    connection_ids = tuple(sorted(connection.id for connection in local_connections))
    nearby_room_ids = {room.id}
    for connection in local_connections:
        nearby_room_ids.update((connection.from_room_id, connection.to_room_id))
    feature_ids = tuple(
        sorted(
            [feature.id for feature in package.features if feature.room_id == room.id]
            + [
                marker.id
                for marker in package.room_mechanic_markers
                if marker.room_id == room.id
                and marker.kind is RoomMechanicMarkerKind.FEATURE
            ]
        )
    )

    exact_locations: dict[str, tuple[str, str]] = {
        package_room.id: (package_room.id, package_room.floor_id)
        for package_room in package.rooms
    }
    for feature in package.features:
        if feature.room_id is not None:
            exact_locations[feature.id] = (feature.room_id, feature.floor_id)
    for mechanic_marker in package.room_mechanic_markers:
        exact_locations[mechanic_marker.id] = (
            mechanic_marker.room_id,
            mechanic_marker.floor_id,
        )
    for key in package.topology.keys:
        location_room = rooms_by_id[key.located_in_room_id]
        exact_locations[key.id] = (location_room.id, location_room.floor_id)
    for clue in package.topology.clues:
        location_room = rooms_by_id[clue.located_in_room_id]
        exact_locations[clue.id] = (location_room.id, location_room.floor_id)

    clue_locations: list[DungeonPuzzleClueLocation] = []
    for approval in selection.clue_locations:
        exact_location = exact_locations.get(approval.location_id)
        if exact_location is None:
            raise ConflictError(
                "Puzzle context selected an unknown exact clue location."
            )
        clue_room_id, clue_floor_id = exact_location
        if clue_room_id not in nearby_room_ids:
            raise ConflictError(
                "Puzzle context selected a clue location outside the local puzzle neighborhood."
            )
        clue_locations.append(
            DungeonPuzzleClueLocation(
                location_id=approval.location_id,
                room_id=clue_room_id,
                floor_id=clue_floor_id,
                purpose=approval.purpose,
            )
        )

    objective_relationship = None
    if selection.objective is not None:
        marker = next(
            (
                item
                for item in package.room_mechanic_markers
                if item.id == selection.objective.objective_id
                and item.kind is RoomMechanicMarkerKind.OBJECTIVE
            ),
            None,
        )
        if marker is None:
            raise ConflictError("Puzzle context selected an unknown exact objective.")
        objective_relationship = DungeonPuzzleObjectiveRelationship(
            objective_id=marker.id,
            objective_room_id=marker.room_id,
            relationship=selection.objective.relationship,
        )

    dependency_relationship = None
    if selection.dependency is not None:
        gate = next(
            (
                item
                for item in package.topology.gates
                if item.id == selection.dependency.gate_id
            ),
            None,
        )
        dependency_ids = {item.id for item in package.topology.keys} | {
            item.id for item in package.topology.clues
        }
        if gate is None or selection.dependency.dependency_id not in dependency_ids:
            raise ConflictError(
                "Puzzle context selected an unknown exact gate dependency."
            )
        if selection.dependency.dependency_id not in {
            item.target_id for item in gate.requires_all
        }:
            raise ConflictError(
                "Puzzle context selected a dependency not required by the exact gate."
            )
        dependency_relationship = DungeonPuzzleDependencyRelationship(
            gate_id=gate.id,
            dependency_id=selection.dependency.dependency_id,
            relationship=selection.dependency.relationship,
        )

    return DungeonPuzzleEnrichmentInput(
        schema_version="1.0.0",
        package_id=package.id,
        room=DungeonPuzzleRoomContext(
            room_id=room.id,
            floor_id=room.floor_id,
            boundary=room.boundary,
            capacity=room.capacity,
            connection_ids=connection_ids,
            feature_ids=feature_ids,
        ),
        objective_relationship=objective_relationship,
        dependency_relationship=dependency_relationship,
        clue_locations=tuple(clue_locations),
        tone=selection.tone,
        constraints=selection.constraints,
    )


def validate_dungeon_puzzle_enrichment(
    context: DungeonPuzzleEnrichmentInput,
    output: DungeonPuzzleEnrichmentOutput,
) -> DungeonPuzzleEnrichmentValidationResult:
    """Check one puzzle-only proposal against its exact server-authored context."""

    issues: list[DungeonPuzzleEnrichmentIssue] = []
    if output.package_id != context.package_id:
        issues.append(
            DungeonPuzzleEnrichmentIssue(
                code="puzzle_enrichment.package_mismatch",
                component_id=output.package_id,
                message="Puzzle enrichment targets a different dungeon package.",
            )
        )
    if output.room_id != context.room.room_id:
        issues.append(
            DungeonPuzzleEnrichmentIssue(
                code="puzzle_enrichment.room_mismatch",
                component_id=output.room_id,
                message="Puzzle enrichment targets a different exact room.",
            )
        )
    allowed_clue_ids = {item.location_id for item in context.clue_locations}
    for clue in output.clue_path:
        if clue.location_id not in allowed_clue_ids:
            issues.append(
                DungeonPuzzleEnrichmentIssue(
                    code="puzzle_enrichment.clue_location_invalid",
                    component_id=clue.location_id,
                    message="Puzzle clue uses a location outside the approved context.",
                )
            )
    return DungeonPuzzleEnrichmentValidationResult(
        schema_version="1.0.0",
        accepted_output=None if issues else output,
        issues=tuple(issues),
    )


def project_dungeon_puzzle_enrichment(
    guide: DungeonDmGuide,
    *,
    plan: DungeonPlan,
    package: DungeonPackage,
    context: DungeonPuzzleEnrichmentInput,
    validation: DungeonPuzzleEnrichmentValidationResult,
) -> DungeonDmGuide:
    """Merge one accepted exact-ID puzzle without changing package-owned state."""

    rebuilt_context = build_dungeon_puzzle_enrichment_input(
        package,
        DungeonPuzzleContextSelection(
            room_id=context.room.room_id,
            clue_locations=tuple(
                DungeonPuzzleClueApproval(
                    location_id=item.location_id,
                    purpose=item.purpose,
                )
                for item in context.clue_locations
            ),
            objective=(
                DungeonPuzzleObjectiveApproval(
                    objective_id=context.objective_relationship.objective_id,
                    relationship=context.objective_relationship.relationship,
                )
                if context.objective_relationship is not None
                else None
            ),
            dependency=(
                DungeonPuzzleDependencyApproval(
                    gate_id=context.dependency_relationship.gate_id,
                    dependency_id=context.dependency_relationship.dependency_id,
                    relationship=context.dependency_relationship.relationship,
                )
                if context.dependency_relationship is not None
                else None
            ),
            tone=context.tone,
            constraints=context.constraints,
        ),
    )
    if rebuilt_context != context:
        raise ConflictError(
            "Puzzle enrichment context does not match the accepted exact package."
        )

    output = validation.accepted_output
    if output is None:
        raise ConflictError("Rejected puzzle enrichment cannot be projected.")
    authoritative_validation = validate_dungeon_puzzle_enrichment(context, output)
    if authoritative_validation.accepted_output is None:
        raise ConflictError("Puzzle enrichment failed exact-ID semantic validation.")

    compiled = compile_dungeon_plan(plan)
    if (
        not compiled.accepted
        or compiled.certificate is None
        or compiled.topology is None
        or package.topology != compiled.topology
    ):
        raise ConflictError(
            "Accepted puzzle enrichment does not match the generated dungeon plan."
        )
    room_ref_by_id = {item.room_id: item.ref for item in compiled.certificate.rooms}
    room_ref = room_ref_by_id.get(output.room_id)
    if room_ref is None:
        raise ConflictError("Puzzle enrichment targets an unknown planned room.")
    planned_room = next(room for room in plan.rooms if room.ref == room_ref)
    if planned_room.role is not RoomRole.PUZZLE:
        raise ConflictError("Puzzle enrichment targets a room without a puzzle role.")

    guide_room = next(
        (room for room in guide.rooms if room.room_id == output.room_id), None
    )
    if guide_room is None:
        raise ConflictError("Puzzle enrichment targets a room outside the exact guide.")
    if any(puzzle.room_id == output.room_id for puzzle in guide.puzzles):
        raise ConflictError("Puzzle enrichment cannot replace accepted puzzle content.")

    player_choices = (
        DungeonGuidePlayerChoice(
            action=output.guide_solution(),
            outcome=output.success_outcome,
        ),
        *(
            DungeonGuidePlayerChoice(
                action=alternate.approach,
                outcome=alternate.adjudication,
            )
            for alternate in output.alternate_handling
        ),
    )
    puzzle = DungeonGuidePuzzle(
        content_ref=room_ref,
        room_id=output.room_id,
        map_reference=guide_room.map_reference,
        name=output.name,
        solution=output.guide_solution(),
        content=DungeonGuideRunnableContent(
            situation=output.guide_situation(),
            adjudication=output.guide_adjudication(),
            player_choices=player_choices,
        ),
    )
    presentation_by_room = {
        room.room_id: room.presentation_number for room in guide.rooms
    }
    puzzles = tuple(
        sorted(
            (*guide.puzzles, puzzle),
            key=lambda item: presentation_by_room[item.room_id],
        )
    )
    content_issues = tuple(
        issue
        for issue in guide.content_issues
        if not (
            issue.code == "guide_content.required_missing"
            and issue.kind == "puzzle"
            and issue.room_ref == room_ref
        )
    )
    document = guide.model_dump(mode="python")
    document["puzzles"] = puzzles
    document["content_issues"] = content_issues
    return DungeonDmGuide.model_validate(document)


def validate_dungeon_guide_content(
    plan: DungeonPlan,
    content_plan: DungeonGuideContentPlan | None,
) -> DungeonGuideContentValidationResult:
    """Validate optional runnable prose without invoking the pure compiler or layout."""

    rooms = {room.ref: room for room in plan.rooms}
    gates = {gate.ref: gate for gate in plan.gates}
    room_contents = {content.room_ref: content for content in plan.room_contents}
    accepted_room_narratives: list[DungeonGuideRoomNarrative] = []
    accepted: list[DungeonGuideContentEntry] = []
    issues: list[DungeonGuideContentIssue] = []
    supplied_targets: set[tuple[str, str]] = set()
    room_narratives = content_plan.room_narratives if content_plan is not None else ()
    content_entries = content_plan.entries if content_plan is not None else ()

    for narrative in room_narratives:
        if narrative.room_ref in rooms:
            accepted_room_narratives.append(narrative)
        else:
            issues.append(
                DungeonGuideContentIssue(
                    code="guide_content.target_invalid",
                    kind="room",
                    entry_ref=narrative.room_ref,
                    room_ref=narrative.room_ref,
                    target_ref=narrative.room_ref,
                    message="Room narrative does not match an accepted dungeon plan room.",
                )
            )
    accepted_narrative_refs = {
        narrative.room_ref for narrative in accepted_room_narratives
    }
    for room_ref in rooms:
        if room_ref in accepted_narrative_refs:
            continue
        issues.append(
            DungeonGuideContentIssue(
                code="guide_content.required_missing",
                kind="room",
                room_ref=room_ref,
                target_ref=room_ref,
                message="The accepted dungeon plan requires sensory read-aloud material for this room.",
            )
        )

    for entry in content_entries:
        target_ref = (
            entry.gate_ref
            if isinstance(entry, DungeonGuideGateContent)
            else entry.room_ref
        )
        supplied_targets.add((entry.kind, target_ref))
        room = rooms.get(entry.room_ref)
        valid = room is not None
        if isinstance(entry, DungeonGuideGateContent):
            gate = gates.get(entry.gate_ref)
            valid = valid and gate is not None
            if gate is not None:
                valid = valid and gate.dependency_room == entry.room_ref
                valid = valid and gate.dependency_name == entry.dependency_name
        elif isinstance(entry, DungeonGuideEncounterContent):
            valid = (
                valid and room is not None and room.encounter == entry.encounter_intent
            )
        elif isinstance(entry, DungeonGuidePuzzleContent):
            valid = valid and room is not None and room.role is RoomRole.PUZZLE
        elif isinstance(entry, DungeonGuideFeatureContent):
            planned = room_contents.get(entry.room_ref)
            valid = (
                valid
                and planned is not None
                and planned.feature is not None
                and planned.feature.name == entry.feature_name
            )
        elif isinstance(entry, DungeonGuideObjectiveContent):
            planned = room_contents.get(entry.room_ref)
            valid = (
                valid
                and room is not None
                and room.role is RoomRole.OBJECTIVE
                and planned is not None
                and planned.objective == entry.objective_name
            )
        if valid:
            accepted.append(entry)
        else:
            issues.append(
                DungeonGuideContentIssue(
                    code="guide_content.target_invalid",
                    kind=entry.kind,
                    entry_ref=entry.ref,
                    room_ref=entry.room_ref,
                    target_ref=target_ref,
                    message="Runnable guide content does not match the accepted dungeon plan target.",
                )
            )

    required_targets: list[
        tuple[
            Literal["gate_dependency", "encounter", "puzzle", "feature", "objective"],
            str,
            str,
        ]
    ] = []
    required_targets.extend(
        ("gate_dependency", gate.ref, gate.dependency_room) for gate in plan.gates
    )
    required_targets.extend(
        ("encounter", room.ref, room.ref)
        for room in plan.rooms
        if room.encounter is not None
    )
    required_targets.extend(
        ("puzzle", room.ref, room.ref)
        for room in plan.rooms
        if room.role is RoomRole.PUZZLE
    )
    required_targets.extend(
        ("feature", content.room_ref, content.room_ref)
        for content in plan.room_contents
        if content.feature is not None
    )
    required_targets.extend(
        ("objective", content.room_ref, content.room_ref)
        for content in plan.room_contents
        if content.objective is not None
    )
    for kind, target_ref, room_ref in required_targets:
        if (kind, target_ref) in supplied_targets:
            continue
        issues.append(
            DungeonGuideContentIssue(
                code="guide_content.required_missing",
                kind=kind,
                room_ref=room_ref,
                target_ref=target_ref,
                message="The accepted dungeon plan requires runnable guide content for this target.",
            )
        )
    return DungeonGuideContentValidationResult(
        schema_version="1.0.0",
        accepted_room_narratives=tuple(accepted_room_narratives),
        accepted_entries=tuple(accepted),
        issues=tuple(issues),
    )


def _runnable_content(entry: DungeonGuideContentEntry) -> DungeonGuideRunnableContent:
    return DungeonGuideRunnableContent(
        situation=entry.situation,
        adjudication=entry.adjudication,
        player_choices=entry.player_choices,
    )


def _accepted_structural_plan(specification: DungeonStudioSpecification) -> DungeonPlan:
    proposal = next(
        (
            lineage.proposal
            for lineage in reversed(specification.model_lineage)
            if lineage.proposal is not None and lineage.proposal.plan is not None
        ),
        None,
    )
    if proposal is None or proposal.plan is None:
        raise ConflictError(
            "Puzzle enrichment requires accepted structural plan lineage."
        )
    return proposal.plan


def _build_dm_guide(
    request: LayoutRequest,
    package: DungeonPackage,
    model_lineage: tuple[PromptedDungeonModelLineage, ...],
) -> DungeonDmGuide | None:
    """Project accepted Tier A plan prose onto exact certified package IDs."""
    proposal = next(
        (
            lineage.proposal
            for lineage in reversed(model_lineage)
            if lineage.proposal is not None and lineage.proposal.plan is not None
        ),
        None,
    )
    if proposal is None or proposal.plan is None:
        return None
    return build_dungeon_dm_guide(request, package, proposal.plan)


def build_dungeon_dm_guide(
    request: LayoutRequest,
    package: DungeonPackage,
    plan: DungeonPlan,
    content_plan: DungeonGuideContentPlan | None = None,
) -> DungeonDmGuide:
    """Project one accepted plan onto exact generated package IDs without persistence."""

    compiled = compile_dungeon_plan(plan)
    if (
        not compiled.accepted
        or compiled.topology is None
        or compiled.certificate is None
        or compiled.mechanics_plan is None
        or request.mechanics_plan != compiled.mechanics_plan
        or package.topology != compiled.topology
    ):
        raise ConflictError(
            "Accepted proposal does not match the generated dungeon plan."
        )

    content_validation = validate_dungeon_guide_content(plan, content_plan)
    room_narratives_by_ref = {
        item.room_ref: item for item in content_validation.accepted_room_narratives
    }
    content_by_kind_room = {
        (entry.kind, entry.room_ref): entry
        for entry in content_validation.accepted_entries
    }
    gate_content_by_ref = {
        entry.gate_ref: entry
        for entry in content_validation.accepted_entries
        if isinstance(entry, DungeonGuideGateContent)
    }

    map_callouts = tuple(
        entry
        for floor in package.floors
        for entry in build_map_key(
            package, floor.id, RenderAudience.DM, scale=64
        ).entries
    )

    def map_reference(
        component_id: str, floor_id: str
    ) -> DungeonGuideMapReference | None:
        entry = next(
            (
                item
                for item in map_callouts
                if item.component_id == component_id and item.floor_id == floor_id
            ),
            None,
        )
        if entry is None:
            return None
        return DungeonGuideMapReference(
            component_id=entry.component_id, floor_id=entry.floor_id, token=entry.token
        )

    room_ids_by_ref = {item.ref: item.room_id for item in compiled.certificate.rooms}
    rooms_by_id = {item.id: item for item in package.rooms}
    encounter_slots_by_room = {
        item.room_id: item for item in compiled.mechanics_plan.encounter_slots
    }
    guide_rooms: list[DungeonGuideRoom] = []
    plan_rooms_by_ref = {room.ref: room for room in plan.rooms}
    ordered_room_refs = []
    for critical_room_ref in plan.critical_path:
        ordered_room_refs.append(critical_room_ref)
        ordered_room_refs.extend(
            room_ref
            for branch in plan.branches
            if branch.from_room == critical_room_ref
            for room_ref in branch.rooms
        )
    ordered_room_refs.extend(
        room_ref
        for branch in plan.branches
        if branch.from_room not in plan.critical_path
        for room_ref in branch.rooms
    )
    ordered_room_refs.extend(sorted(set(plan_rooms_by_ref) - set(ordered_room_refs)))
    for presentation_number, room_ref in enumerate(ordered_room_refs, start=1):
        plan_room = plan_rooms_by_ref[room_ref]
        room_id = room_ids_by_ref[plan_room.ref]
        room = rooms_by_id[room_id]
        reference = map_reference(room_id, room.floor_id)
        if reference is None:
            raise ConflictError("A DM-visible room is missing its map callout.")
        encounter_content = content_by_kind_room.get(("encounter", plan_room.ref))
        narrative = room_narratives_by_ref.get(plan_room.ref)
        guide_rooms.append(
            DungeonGuideRoom(
                room_id=room_id,
                floor_id=room.floor_id,
                map_reference=reference,
                presentation_number=presentation_number,
                name=plan_room.name,
                role=room.role,
                tags=plan_room.tags,
                read_aloud=narrative.read_aloud if narrative is not None else None,
                sensory_details=(
                    narrative.sensory_details if narrative is not None else ()
                ),
                preparation_note=plan_room.purpose,
                encounter_slot=plan_room.encounter,
                encounter_slot_id=(
                    encounter_slots_by_room[room_id].id
                    if plan_room.encounter is not None
                    else None
                ),
                encounter_content=(
                    _runnable_content(encounter_content)
                    if isinstance(encounter_content, DungeonGuideEncounterContent)
                    else None
                ),
            )
        )

    mechanics_by_connection = {
        item.connection_id: item
        for item in compiled.mechanics_plan.door_mechanics
        if item.endpoint is None
    }
    doors_by_connection = {
        item.connection_id: item for item in package.composable_doors
    }
    guide_connections: list[DungeonGuideConnection] = []
    for connection in package.topology.connections:
        if connection.kind != "door":
            guide_connections.append(
                DungeonGuideConnection(
                    component_id=connection.id,
                    connection_id=connection.id,
                    passage=connection.kind,
                    from_room_id=connection.from_room_id,
                    to_room_id=connection.to_room_id,
                )
            )
            continue
        mechanics = mechanics_by_connection.get(connection.id)
        door = doors_by_connection.get(connection.id)
        if mechanics is None or door is None:
            raise ConflictError("A topology door is missing exact mechanics geometry.")
        guide_connections.append(
            _guide_connection(
                component_id=door.id,
                connection_id=connection.id,
                map_reference=map_reference(door.id, door.floor_id),
                passage=connection.kind,
                from_room_id=connection.from_room_id,
                to_room_id=connection.to_room_id,
                endpoint=None,
                endpoint_kind=None,
                mechanics=door.mechanics,
                trap_trigger=None,
                trap_effect=None,
            )
        )

    guide_dependencies: list[DungeonGuideDependency] = []
    if plan.gates:
        gate_intent = plan.gates[0]
        gate = package.topology.gates[0]
        dependency_id = (
            package.topology.keys[0].id
            if package.topology.keys
            else package.topology.clues[0].id
        )
        room_id = room_ids_by_ref[gate_intent.dependency_room]
        room = rooms_by_id[room_id]
        reference = map_reference(room_id, room.floor_id)
        if reference is None:
            raise ConflictError("A dependency room is missing its map callout.")
        gate_content = gate_content_by_ref.get(gate_intent.ref)
        guide_dependencies.append(
            DungeonGuideDependency(
                dependency_id=dependency_id,
                target_gate_id=gate.id,
                name=gate_intent.dependency_name,
                kind=gate_intent.dependency_kind.value,
                room_id=room_id,
                room_map_reference=reference,
                discovery=(
                    gate_content.discovery if gate_content is not None else None
                ),
                content=(
                    _runnable_content(gate_content)
                    if gate_content is not None
                    else None
                ),
            )
        )

    markers = {item.id: item for item in package.room_mechanic_markers}
    content_by_room = {item.room_ref: item for item in plan.room_contents}
    trap_plans = {item.room_id: item for item in compiled.mechanics_plan.room_traps}
    feature_plans = {
        item.room_id: item for item in compiled.mechanics_plan.room_features
    }
    objective_plans = {
        item.room_id: item for item in compiled.mechanics_plan.room_objectives
    }
    guide_traps: list[DungeonGuideTrap] = []
    guide_features: list[DungeonGuideFeature] = []
    guide_objectives: list[DungeonGuideObjective] = []
    for room_ref, content in sorted(content_by_room.items()):
        room_id = room_ids_by_ref[room_ref]
        if content.trap is not None:
            trap_plan = trap_plans[room_id]
            marker = markers[trap_plan.id]
            reference = map_reference(marker.id, marker.floor_id)
            if reference is None:
                raise ConflictError("A room trap is missing its DM map callout.")
            guide_traps.append(
                DungeonGuideTrap(
                    marker_id=marker.id,
                    room_id=room_id,
                    map_reference=reference,
                    name=content.trap.name,
                    trigger=content.trap.trigger,
                    effect=content.trap.effect,
                    detection=content.trap.detection,
                    disable=content.trap.disable,
                    detection_difficulty=trap_plan.detection_difficulty,
                    disable_difficulty=trap_plan.disable_difficulty,
                )
            )
        if content.feature is not None:
            feature_plan = feature_plans[room_id]
            marker = markers[feature_plan.id]
            reference = map_reference(marker.id, marker.floor_id)
            if reference is None:
                raise ConflictError("A feature is missing its DM map callout.")
            feature_content = content_by_kind_room.get(("feature", room_ref))
            guide_features.append(
                DungeonGuideFeature(
                    marker_id=marker.id,
                    room_id=room_id,
                    map_reference=reference,
                    kind=content.feature.kind,
                    name=content.feature.name,
                    description=content.feature.description,
                    content=(
                        _runnable_content(feature_content)
                        if isinstance(feature_content, DungeonGuideFeatureContent)
                        else None
                    ),
                )
            )
        if content.objective is not None:
            objective_plan = objective_plans[room_id]
            marker = markers[objective_plan.id]
            reference = map_reference(marker.id, marker.floor_id)
            if reference is None:
                raise ConflictError("An objective is missing its DM map callout.")
            objective_content = content_by_kind_room.get(("objective", room_ref))
            guide_objectives.append(
                DungeonGuideObjective(
                    marker_id=marker.id,
                    room_id=room_id,
                    map_reference=reference,
                    kind=objective_plan.kind,
                    name=objective_plan.name,
                    content=(
                        _runnable_content(objective_content)
                        if isinstance(objective_content, DungeonGuideObjectiveContent)
                        else None
                    ),
                )
            )

    guide_puzzles: list[DungeonGuidePuzzle] = []
    for entry in content_validation.accepted_entries:
        if not isinstance(entry, DungeonGuidePuzzleContent):
            continue
        room_id = room_ids_by_ref[entry.room_ref]
        room = rooms_by_id[room_id]
        reference = map_reference(room_id, room.floor_id)
        if reference is None:
            raise ConflictError("A puzzle room is missing its DM map callout.")
        guide_puzzles.append(
            DungeonGuidePuzzle(
                content_ref=entry.ref,
                room_id=room_id,
                map_reference=reference,
                name=entry.name,
                solution=entry.solution,
                content=_runnable_content(entry),
            )
        )

    return DungeonDmGuide(
        schema_version="1.0.0",
        title=plan.title,
        premise=plan.premise,
        map_callouts=map_callouts,
        rooms=tuple(guide_rooms),
        connections=tuple(guide_connections),
        dependencies=tuple(guide_dependencies),
        traps=tuple(guide_traps),
        puzzles=tuple(guide_puzzles),
        objectives=tuple(guide_objectives),
        features=tuple(guide_features),
        content_issues=content_validation.issues,
    )


def _guide_connection(
    *,
    component_id: str,
    connection_id: str,
    map_reference: DungeonGuideMapReference | None,
    passage: str,
    from_room_id: str,
    to_room_id: str,
    endpoint: VerticalEndpointSide | None,
    endpoint_kind: EndpointDoorKind | None,
    mechanics: DoorMechanics,
    trap_trigger: str | None,
    trap_effect: str | None,
) -> DungeonGuideConnection:
    return DungeonGuideConnection(
        component_id=component_id,
        connection_id=connection_id,
        map_reference=map_reference,
        passage=passage,
        from_room_id=from_room_id,
        to_room_id=to_room_id,
        endpoint=endpoint,
        endpoint_kind=endpoint_kind,
        concealed=mechanics.concealed,
        discovery_difficulty=mechanics.discovery_difficulty,
        gate_id=mechanics.gate_id,
        gate_kind=mechanics.gate_kind,
        unlock_difficulty=mechanics.unlock_difficulty,
        trap_id=mechanics.trap_id,
        trap_trigger=trap_trigger,
        trap_effect=trap_effect,
        disable_difficulty=mechanics.disable_difficulty,
    )


def _resolved_dm_notes(specification: DungeonStudioSpecification) -> DungeonDmNotes:
    if specification.dm_notes.room_notes:
        return specification.dm_notes
    source_prompt = specification.dm_notes.source_prompt
    if source_prompt is None:
        for lineage in specification.model_lineage:
            for message in lineage.model_run.run_input.messages:
                try:
                    document = json.loads(message.content)
                except json.JSONDecodeError:
                    continue
                prompt = document.get("prompt")
                if isinstance(prompt, str) and prompt:
                    source_prompt = prompt
                    break
            if source_prompt is not None:
                break
    return _build_dm_notes(
        specification.layout_request, source_prompt, specification.package
    )


def _build_dm_notes(
    request: LayoutRequest,
    source_prompt: str | None,
    package: DungeonPackage | None = None,
) -> DungeonDmNotes:
    """Build durable, human-readable room notes without changing kernel state."""

    floors = {floor.id: floor.name for floor in request.topology.floors}
    feature_names: dict[str, list[str]] = {}
    for feature in () if package is None else package.features:
        if feature.room_id is not None:
            detail = feature.name
            if feature.details:
                detail = f"{detail}: {feature.details}"
            feature_names.setdefault(feature.room_id, []).append(detail)
    notes: list[DungeonRoomDmNote] = []
    for room in request.topology.rooms:
        name = room.name or _humanize_id(room.id)
        fragments = [f"{name} is a {room.role.value.replace('_', ' ')} area"]
        floor_name = floors.get(room.floor_id)
        if floor_name:
            fragments.append(f"on {floor_name}")
        if room.tags:
            fragments.append(f"Tags: {', '.join(room.tags)}")
        if room.id in feature_names:
            fragments.append(f"Features: {'; '.join(feature_names[room.id])}")
        notes.append(
            DungeonRoomDmNote(
                room_id=room.id,
                name=name,
                text=". ".join(fragments) + ".",
            )
        )
    return DungeonDmNotes(source_prompt=source_prompt, room_notes=tuple(notes))


def _humanize_id(value: str) -> str:
    return value.removeprefix("room_").replace("_", " ").replace("-", " ").title()


def _dm_notes_asset(
    request: LayoutRequest,
    dm_notes: DungeonDmNotes,
    dm_guide: DungeonDmGuide | None = None,
) -> _PendingAsset:
    return _PendingAsset(
        ArtifactAssetRole.OTHER,
        0,
        "text/plain",
        (
            _dm_guide_text(dm_guide)
            if dm_guide is not None
            else _dm_notes_text(request, dm_notes)
        ).encode("utf-8"),
    )


def _dm_notes_text(request: LayoutRequest, dm_notes: DungeonDmNotes) -> str:
    """Create a portable DM-only notes download from the immutable specification."""

    brief = request.brief
    sections = [f"# {brief.title}", "", brief.summary]
    if dm_notes.source_prompt:
        sections.extend(("", "## Original request", dm_notes.source_prompt))
    for heading, items in (
        ("Inhabitants", brief.inhabitants),
        ("Constraints", brief.constraints),
        ("Hooks", brief.campaign_hooks),
    ):
        if items:
            sections.extend(
                ("", f"## {heading}", *[f"- {item.text}" for item in items])
            )
    if dm_notes.room_notes:
        sections.extend(("", "## Room notes"))
        sections.extend(
            f"{index}. {note.name}: {note.text}"
            for index, note in enumerate(dm_notes.room_notes, start=1)
        )
    return "\n".join(sections) + "\n"


def render_dungeon_dm_guide_text(guide: DungeonDmGuide) -> str:
    """Render an exact DM guide as a portable provider-free review document."""

    return _dm_guide_text(guide)


def _dm_guide_text(guide: DungeonDmGuide) -> str:
    """Render a concise, exploration-ordered Markdown DM document."""

    sections = [f"# {guide.title} — DM guide", "", guide.premise]
    gate_connections = {
        connection.gate_id: connection
        for connection in guide.connections
        if connection.gate_id is not None
    }
    if guide.rooms:
        sections.extend(("", "## Room-by-room guide"))
    for room in guide.rooms:
        sections.extend(
            (
                "",
                f"### {room.presentation_number}. {room.name} "
                f"(Map {room.map_reference.token})",
                "",
                "**Read aloud**",
                "",
                f"> {room.read_aloud or 'Unknown; complete before play.'}",
            )
        )

        for connection in guide.connections:
            if (
                connection.from_room_id == room.room_id
                and _connection_has_actionable_state(connection)
            ):
                _append_connection_state(sections, connection)
        if room.encounter_slot is not None:
            heading = (
                "Exploration challenge"
                if room.encounter_slot is EncounterSlotIntent.EXPLORATION
                else f"{room.encounter_slot.value.title()} scene pressure"
            )
            sections.extend(("", f"#### {heading}"))
            if room.encounter_content is None:
                sections.extend(
                    ("", "- **Preparation blocker:** Runnable details are missing.")
                )
            else:
                _append_runnable_content(sections, room.encounter_content)
        for dependency in guide.dependencies:
            if dependency.room_id != room.room_id:
                continue
            gate_connection = gate_connections.get(dependency.target_gate_id)
            gate_token = (
                gate_connection.map_reference.token
                if gate_connection is not None
                and gate_connection.map_reference is not None
                else dependency.target_gate_id
            )
            sections.extend(("", f"#### {dependency.name} — opens {gate_token}"))
            if dependency.discovery is not None:
                sections.extend(("", f"- **Find:** {dependency.discovery}"))
            if dependency.content is not None:
                _append_runnable_content(sections, dependency.content)
        for trap in guide.traps:
            if trap.room_id != room.room_id:
                continue
            sections.extend(("", f"#### {trap.map_reference.token} — {trap.name}", ""))
            if trap.warning is not None:
                sections.append(f"- **Warning:** {trap.warning}")
            sections.append(
                f"- **Trigger:** {trap.trigger or 'Unknown; complete before play.'}"
            )
            if trap.detection is not None and trap.disable is not None:
                sections.extend(
                    (
                        f"- **Detect:** DC {trap.detection_difficulty}; {trap.detection}",
                        f"- **Disable:** DC {trap.disable_difficulty}; {trap.disable}",
                    )
                )
            else:
                sections.append(
                    f"- **Detect / disable:** DC {trap.detection_difficulty} / "
                    f"DC {trap.disable_difficulty}; methods unknown; complete before play."
                )
            sections.append(
                f"- **Consequence:** {trap.effect or 'Unknown; complete before play.'}"
            )
            sections.extend(
                f"- **Further consequence:** {consequence}"
                for consequence in trap.consequences
            )
            if trap.reset_or_recovery is not None:
                sections.append(f"- **Reset / recovery:** {trap.reset_or_recovery}")
        for puzzle in guide.puzzles:
            if puzzle.room_id != room.room_id:
                continue
            sections.extend(
                ("", f"#### {puzzle.name}", "", f"- **Solution:** {puzzle.solution}")
            )
            _append_runnable_content(sections, puzzle.content)
        for feature in guide.features:
            if feature.room_id != room.room_id:
                continue
            sections.extend(
                ("", f"#### {feature.map_reference.token} — {feature.name}")
            )
            if feature.content is not None:
                _append_runnable_content(sections, feature.content)
        for objective in guide.objectives:
            if objective.room_id != room.room_id:
                continue
            sections.extend(
                ("", f"#### {objective.map_reference.token} — {objective.name}")
            )
            if objective.content is not None:
                _append_runnable_content(sections, objective.content)

    if guide.content_issues:
        sections.extend(("", "## Preparation blockers", ""))
        sections.extend(
            f"- {issue.code}: {issue.message}" for issue in guide.content_issues
        )
    return "\n".join(sections) + "\n"


def _connection_has_actionable_state(connection: DungeonGuideConnection) -> bool:
    return bool(
        connection.concealed
        or connection.gate_id
        or connection.trap_id
        or connection.endpoint is not None
    )


def _append_connection_state(
    sections: list[str], connection: DungeonGuideConnection
) -> None:
    token = (
        connection.map_reference.token
        if connection.map_reference is not None
        else "Transition"
    )
    if connection.concealed:
        heading = f"{token} — Secret {connection.passage}"
    elif connection.gate_id is not None:
        heading = f"{token} — {connection.gate_kind.value.title()} {connection.passage}"
    else:
        heading = f"{token} — {connection.passage.title()} state"
    sections.extend(("", f"#### {heading}", ""))
    if connection.concealed:
        sections.append(
            f"- **Find:** discovery DC {connection.discovery_difficulty}; "
            "check method is DM-adjudicated."
        )
    if connection.gate_id is not None:
        sections.append(f"- **Open:** unlock DC {connection.unlock_difficulty}.")
    if connection.trap_id is not None:
        sections.extend(
            (
                f"- **Trigger:** {connection.trap_trigger}",
                f"- **Disable:** DC {connection.disable_difficulty}.",
                f"- **Consequence:** {connection.trap_effect}",
            )
        )
    if connection.endpoint is not None and connection.endpoint_kind is not None:
        sections.append(
            f"- **Transition:** {connection.endpoint.value} "
            f"{connection.endpoint_kind.value}."
        )


def _append_runnable_content(
    sections: list[str], content: DungeonGuideRunnableContent
) -> None:
    sections.extend(
        (
            "",
            f"- **Situation:** {content.situation}",
            f"- **Run it:** {content.adjudication}",
            "",
            "##### Choices and consequences",
            "",
        )
    )
    sections.extend(
        f"{index}. **{choice.action}** — {choice.outcome}"
        for index, choice in enumerate(content.player_choices, start=1)
    )


def _dm_presentation_package(
    package: DungeonPackage, dm_notes: DungeonDmNotes
) -> DungeonPackage:
    """Return V1 package data; its DM annotations are already exact."""

    del dm_notes
    return package


def _log_generation_result(
    *,
    run_id: uuid.UUID,
    stage: str,
    diagnostics: tuple[dict[str, JsonValue], ...],
) -> None:
    """Write safe, correlatable dungeon-run breadcrumbs to the process log."""
    with bind_log_context(generation_run_id=str(run_id)):
        logger.info(
            "dungeon generation finished",
            extra={
                "event_data": {
                    "stage": stage,
                    "success": stage == "completed",
                    "diagnostic_codes": [
                        value["code"]
                        for value in diagnostics
                        if isinstance(value.get("code"), str)
                    ],
                }
            },
        )


def _preview_assets(
    package: DungeonPackage, dm_notes: DungeonDmNotes
) -> tuple[_PendingAsset, ...]:
    assets: list[_PendingAsset] = []
    for floor_index, floor in enumerate(package.floors):
        for audience_index, audience in enumerate(RenderAudience):
            ordinal = floor_index * 2 + audience_index
            rendered_package = (
                _dm_presentation_package(package, dm_notes)
                if audience is RenderAudience.DM
                else package
            )
            svg = render_svg(
                rendered_package,
                SvgRenderRequest(
                    schema_version="1.0.0",
                    package_id=package.id,
                    floor_id=floor.id,
                    audience=audience,
                    pixels_per_cell=64,
                    show_grid=True,
                    show_labels=True,
                    show_markers=True,
                    theme=SvgThemeName.LOW_INK,
                ),
            )
            if not svg.success or svg.svg is None:
                raise ConflictError(
                    "Dungeon preview SVG rendering failed: "
                    f"{_render_diagnostic_summary(svg.diagnostics)}"
                )
            svg_role = (
                ArtifactAssetRole.DM_SVG
                if audience is RenderAudience.DM
                else ArtifactAssetRole.PLAYER_SVG
            )
            assets.append(
                _PendingAsset(svg_role, floor_index, "image/svg+xml", svg.svg.encode())
            )
            png = export_png(
                rendered_package,
                PngExportRequest(
                    schema_version="1.0.0",
                    package_id=package.id,
                    floor_id=floor.id,
                    audience=audience,
                    pixels_per_cell=70,
                    dpi=140,
                    include_grid=True,
                    show_labels=True,
                    show_markers=True,
                    theme=SvgThemeName.LOW_INK,
                    maximum_ink_coverage_basis_points=5000,
                ),
            )
            if (
                not png.result.success
                or png.data is None
                or png.result.manifest is None
            ):
                raise ConflictError(
                    "Dungeon preview PNG rendering failed: "
                    f"{_render_diagnostic_summary(png.result.diagnostics)}"
                )
            png_role = (
                ArtifactAssetRole.DM_PNG
                if audience is RenderAudience.DM
                else ArtifactAssetRole.PLAYER_PNG
            )
            assets.extend(
                (
                    _PendingAsset(png_role, floor_index, "image/png", png.data),
                    _PendingAsset(
                        ArtifactAssetRole.MANIFEST,
                        ordinal,
                        "application/json",
                        to_canonical_json(png.result.manifest).encode(),
                    ),
                )
            )
    return tuple(assets)


def _export_assets(
    package: DungeonPackage,
    dm_notes: DungeonDmNotes,
    *,
    export_format: Literal["roll20"],
) -> tuple[_PendingAsset, ...]:
    assets: list[_PendingAsset] = []
    for floor_index, floor in enumerate(package.floors):
        for audience_index, audience in enumerate(RenderAudience):
            audience_ordinal = floor_index * 2 + audience_index
            rendered_package = (
                _dm_presentation_package(package, dm_notes)
                if audience is RenderAudience.DM
                else package
            )
            roll20 = export_roll20_bundle(
                rendered_package,
                Roll20ExportRequest(
                    schema_version="1.0.0",
                    package_id=package.id,
                    floor_id=floor.id,
                    audience=audience,
                    filename_prefix=f"dungeon-floor-{floor_index}",
                    maximum_ink_coverage_basis_points=5000,
                ),
            )
            _append_roll20_assets(
                assets,
                roll20,
                floor_index,
                audience,
                audience_ordinal,
            )
    return tuple(assets)


def _append_roll20_assets(
    assets: list[_PendingAsset],
    roll20: Roll20Artifact,
    floor_index: int,
    audience: RenderAudience,
    audience_ordinal: int,
) -> None:
    if (
        not roll20.result.success
        or roll20.zip_data is None
        or roll20.result.manifest is None
    ):
        raise ConflictError("Dungeon Roll20 bundle export failed.")
    role = (
        ArtifactAssetRole.DM_ROLL20_BUNDLE
        if audience is RenderAudience.DM
        else ArtifactAssetRole.PLAYER_ROLL20_BUNDLE
    )
    assets.extend(
        (
            _PendingAsset(role, floor_index, "application/zip", roll20.zip_data),
            _PendingAsset(
                ArtifactAssetRole.MANIFEST,
                2000 + audience_ordinal,
                "application/json",
                to_canonical_json(roll20.result.manifest).encode(),
            ),
        )
    )


def _render_diagnostic_summary(diagnostics: tuple[object, ...]) -> str:
    """Produce a bounded safe diagnostic summary for server logs only."""
    details: list[str] = []
    for diagnostic in diagnostics[:4]:
        code = getattr(diagnostic, "code", "unknown")
        message = getattr(diagnostic, "message", "no diagnostic message")
        details.append(f"{code}: {message}")
    return "; ".join(details) if details else "no renderer diagnostics"


def _regression_case(
    *,
    request: LayoutRequest,
    stage: str,
    diagnostics: tuple[dict[str, JsonValue], ...],
) -> DungeonGenerationRegressionCase:
    """Build fixture-ready input without persisting an invalid artifact version."""

    return DungeonGenerationRegressionCase(
        stage=stage,
        layout_request=request,
        expected_diagnostics=diagnostics,
    )


def _load_specification(document: dict[str, JsonValue]) -> DungeonStudioSpecification:
    try:
        return DungeonStudioSpecification.model_validate_json(
            json.dumps(document, separators=(",", ":"), sort_keys=True)
        )
    except ValidationError as error:
        raise ConflictError("Stored dungeon specification is invalid.") from error


def _select_locks(
    package: DungeonPackage,
    component_ids: tuple[str, ...],
) -> LockedLayoutComponents:
    selected = set(component_ids)
    known: set[str] = set()
    known.update(item.id for item in package.floors)
    known.update(item.id for item in package.rooms)
    known.update(item.id for item in package.corridors)
    known.update(item.id for item in package.composable_doors)
    known.update(item.id for item in package.stairs)
    known.update(item.id for item in package.vertical_links)
    known.update(item.id for item in package.vertical_endpoint_doors)
    known.update(item.id for item in package.room_mechanic_markers)
    if not selected <= known:
        raise ConflictError("A requested locked component does not exist.")

    selected_room_ids = {item.id for item in package.rooms if item.id in selected}
    selected_links = {item.id for item in package.vertical_links if item.id in selected}
    selected_doors = tuple(
        item for item in package.composable_doors if item.id in selected
    )
    for door in selected_doors:
        selected_room_ids.update(door.connects_room_ids)
    selected_endpoint_links = {
        item.vertical_link_id
        for item in package.vertical_endpoint_doors
        if item.id in selected
    }
    selected_links.update(selected_endpoint_links)
    selected_room_ids.update(
        room_id
        for connection in package.topology.connections
        if connection.id in selected_endpoint_links
        for room_id in (connection.from_room_id, connection.to_room_id)
    )
    selected_room_ids.update(
        item.room_id for item in package.room_mechanic_markers if item.id in selected
    )
    return LockedLayoutComponents(
        floors=tuple(item for item in package.floors if item.id in selected),
        rooms=tuple(item for item in package.rooms if item.id in selected_room_ids),
        corridors=tuple(item for item in package.corridors if item.id in selected),
        doors=selected_doors,
        stairs=tuple(item for item in package.stairs if item.id in selected),
        vertical_links=tuple(
            item for item in package.vertical_links if item.id in selected_links
        ),
    )


def _component_documents(package: DungeonPackage) -> dict[str, object]:
    documents: dict[str, object] = {}
    for category in (
        "floors",
        "rooms",
        "corridors",
        "composable_doors",
        "stairs",
        "vertical_links",
        "vertical_endpoint_doors",
        "room_mechanic_markers",
        "features",
        "terrain",
        "hazards",
        "zones",
        "labels",
        "encounter_slots",
        "position_anchors",
    ):
        for component in getattr(package, category, ()):
            documents[f"{category}:{component.id}"] = component.model_dump(mode="json")
    return documents


def _component_ids(keys: set[str]) -> tuple[str, ...]:
    return tuple(sorted({key.split(":", maxsplit=1)[1] for key in keys}))


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
