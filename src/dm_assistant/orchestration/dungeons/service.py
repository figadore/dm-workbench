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
    CreateDungeonWorkflow,
    CreatePromptedDungeonWorkflow,
    DungeonDmGuide,
    DungeonDmNotes,
    DungeonGenerationRegressionCase,
    DungeonGuideConnection,
    DungeonGuideDependency,
    DungeonGuideFeature,
    DungeonGuideMapReference,
    DungeonGuideObjective,
    DungeonGuideRoom,
    DungeonGuideTrap,
    DungeonPreparationReadiness,
    DungeonPreparationReadinessDiagnostic,
    DungeonPrintCapability,
    DungeonRoomDmNote,
    DungeonStudioDetail,
    DungeonStudioSpecification,
    DungeonVersionComparison,
    DungeonWorkflowResult,
    ExportDungeonWorkflow,
    PromptedDungeonModelLineage,
    RegenerateDungeonWorkflow,
)
from dm_dungeon import (
    DoorMechanics,
    DungeonPackage,
    LayoutRequest,
    LockedLayoutComponents,
    PngExportRequest,
    RenderAudience,
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
    EndpointDoorKind,
    VerticalEndpointSide,
)
from dm_dungeon.export import (
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
            schema_versions["dungeon_generation_proposal"] = "1.0.0"
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
                    "png": "png-v1",
                    "pdf": "pdf-v1",
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
    for puzzle in guide.puzzles:
        if any(
            _is_unknown_preparation_text(value)
            for value in (puzzle.mechanism, puzzle.solution, puzzle.consequence)
        ):
            diagnostics.append(
                DungeonPreparationReadinessDiagnostic(
                    code="dungeon_preparation.puzzle_solution_unknown",
                    component_id=puzzle.marker_id,
                    map_reference=puzzle.map_reference,
                    message="This puzzle has unknown play details and needs DM completion.",
                )
            )
    return DungeonPreparationReadiness(
        schema_version="1.0.0",
        ready=not diagnostics,
        diagnostics=tuple(diagnostics),
    )


def _build_dm_guide(
    request: LayoutRequest,
    package: DungeonPackage,
    model_lineage: tuple[PromptedDungeonModelLineage, ...],
) -> DungeonDmGuide | None:
    """Project accepted Tier A plan prose onto exact certified package IDs."""
    plan = next(
        (
            lineage.proposal.plan
            for lineage in reversed(model_lineage)
            if lineage.proposal is not None and lineage.proposal.plan is not None
        ),
        None,
    )
    if plan is None:
        return None
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
    for plan_room in sorted(plan.rooms, key=lambda item: item.ref):
        room_id = room_ids_by_ref[plan_room.ref]
        room = rooms_by_id[room_id]
        reference = map_reference(room_id, room.floor_id)
        if reference is None:
            raise ConflictError("A DM-visible room is missing its map callout.")
        guide_rooms.append(
            DungeonGuideRoom(
                room_id=room_id,
                floor_id=room.floor_id,
                map_reference=reference,
                name=plan_room.name,
                role=room.role,
                tags=plan_room.tags,
                preparation_note=plan_room.purpose,
                encounter_slot=plan_room.encounter,
                encounter_slot_id=(
                    encounter_slots_by_room[room_id].id
                    if plan_room.encounter is not None
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
        guide_dependencies.append(
            DungeonGuideDependency(
                dependency_id=dependency_id,
                target_gate_id=gate.id,
                name=gate_intent.dependency_name,
                kind=gate_intent.dependency_kind.value,
                room_id=room_id,
                room_map_reference=reference,
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
            guide_features.append(
                DungeonGuideFeature(
                    marker_id=marker.id,
                    room_id=room_id,
                    map_reference=reference,
                    kind=content.feature.kind,
                    name=content.feature.name,
                    description=content.feature.description,
                )
            )
        if content.objective is not None:
            objective_plan = objective_plans[room_id]
            marker = markers[objective_plan.id]
            reference = map_reference(marker.id, marker.floor_id)
            if reference is None:
                raise ConflictError("An objective is missing its DM map callout.")
            guide_objectives.append(
                DungeonGuideObjective(
                    marker_id=marker.id,
                    room_id=room_id,
                    map_reference=reference,
                    kind=objective_plan.kind,
                    name=objective_plan.name,
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
        puzzles=(),
        objectives=tuple(guide_objectives),
        features=tuple(guide_features),
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


def _dm_guide_text(guide: DungeonDmGuide) -> str:
    """Render the versioned guide as a portable readable UTF-8 DM document."""

    sections = [f"# {guide.title} — DM guide", "", guide.premise]
    if guide.rooms:
        sections.extend(("", "## Rooms"))
        for room in guide.rooms:
            details = [room.role.value.replace("_", " ")]
            if room.tags:
                details.append(f"tags: {', '.join(room.tags)}")
            if room.encounter_slot is not None:
                details.append(f"encounter: {room.encounter_slot.value}")
            sections.append(
                f"- {room.map_reference.token} — {room.name} ({'; '.join(details)})"
            )
            if room.preparation_note:
                sections.append(f"  {room.preparation_note}")
    if guide.connections:
        sections.extend(("", "## Doors and transitions"))
        for connection in guide.connections:
            token = (
                connection.map_reference.token
                if connection.map_reference
                else "Transition"
            )
            mechanics: list[str] = []
            if connection.concealed:
                mechanics.append(
                    f"secret (discovery {connection.discovery_difficulty})"
                )
            if connection.gate_id:
                mechanics.append(
                    f"{connection.gate_kind.value} gate (unlock {connection.unlock_difficulty})"
                )
            if connection.trap_id:
                mechanics.append(
                    f"trapped (trigger: {connection.trap_trigger}; "
                    f"disable {connection.disable_difficulty}; "
                    f"effect: {connection.trap_effect})"
                )
            endpoint = (
                f" {connection.endpoint.value} {connection.endpoint_kind.value}"
                if connection.endpoint is not None
                and connection.endpoint_kind is not None
                else ""
            )
            sections.append(
                f"- {token} — {connection.passage}{endpoint}"
                + (f": {', '.join(mechanics)}" if mechanics else ".")
            )
    if guide.dependencies:
        sections.extend(("", "## Keys and clues"))
        for dependency in guide.dependencies:
            sections.append(
                f"- {dependency.room_map_reference.token} — {dependency.kind}: {dependency.name}"
            )
    if guide.traps:
        sections.extend(("", "## Traps and hazards"))
        for trap in guide.traps:
            sections.append(
                f"- {trap.map_reference.token} — {trap.name}: trigger {trap.trigger or 'unknown'} "
                f"Detection {trap.detection_difficulty}; disable {trap.disable_difficulty}. "
                f"Effect: {trap.effect or 'unknown'}"
            )
    if guide.puzzles:
        sections.extend(("", "## Puzzles"))
        for puzzle in guide.puzzles:
            sections.append(
                f"- {puzzle.map_reference.token} — {puzzle.name}: {puzzle.mechanism or 'unknown'} "
                f"Difficulty {puzzle.difficulty}. Solution: {puzzle.solution or 'unknown'}. "
                f"Consequence: {puzzle.consequence or 'unknown'}"
            )
    if guide.objectives:
        sections.extend(("", "## Objectives"))
        for objective in guide.objectives:
            sections.append(f"- {objective.map_reference.token} — {objective.name}")
    if guide.features:
        sections.extend(("", "## Features"))
        for feature in guide.features:
            sections.append(
                f"- {feature.map_reference.token} — {feature.name}: {feature.description}"
            )
    return "\n".join(sections) + "\n"


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
