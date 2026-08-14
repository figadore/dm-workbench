"""Provider-independent Dungeon Studio orchestration over pure and prep boundaries."""

import json
import uuid
from dataclasses import dataclass
from typing import Literal

from pydantic import JsonValue, ValidationError

import dm_dungeon
from dm_assistant.errors import ConflictError
from dm_assistant.modules.preparation import (
    ArtifactAssetRole,
    ArtifactLifecycle,
    ArtifactRecord,
    ArtifactType,
    AttachArtifactAsset,
    CreateArtifact,
    CreateArtifactVersion,
    FinishGenerationRun,
    GenerationContextPin,
    GenerationStatus,
    PreparationService,
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
    DungeonGenerationRegressionCase,
    DungeonStudioDetail,
    DungeonStudioSpecification,
    DungeonVersionComparison,
    DungeonWorkflowResult,
    ExportDungeonWorkflow,
    PromptedDungeonModelLineage,
    RegenerateDungeonWorkflow,
)
from dm_dungeon import (
    DungeonPackage,
    LayoutRequest,
    LockedLayoutComponents,
    PdfExportRequest,
    PngExportRequest,
    RenderAudience,
    SvgRenderRequest,
    SvgThemeName,
    export_pdf,
    export_png,
    generate_layout,
    render_svg,
    to_canonical_json,
    validate_geometry,
    validate_topology,
)
from dm_dungeon.export import (
    PdfArtifact,
    Roll20Artifact,
    Roll20ExportRequest,
    export_roll20_bundle,
)

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
        artifact = self._preparation.create_artifact(
            CreateArtifact(
                campaign_id=command.campaign_id,
                artifact_type=ArtifactType.DUNGEON,
                title=command.title,
                visibility_policy=VisibilityPolicy.DM_ONLY,
                created_by=command.created_by,
            )
        )
        return self._generate_version(
            campaign_id=command.campaign_id,
            artifact_id=artifact.id,
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

        artifact = self._preparation.create_artifact(
            CreateArtifact(
                campaign_id=command.campaign_id,
                artifact_type=ArtifactType.DUNGEON,
                title=command.title,
                visibility_policy=VisibilityPolicy.DM_ONLY,
                created_by=command.created_by,
            )
        )
        return self._generate_version(
            campaign_id=command.campaign_id,
            artifact_id=artifact.id,
            parent_version_id=None,
            request=command.layout_request,
            change_summary="Create deterministic dungeon from model-authored intent.",
            created_by=command.created_by,
            generation_kind="prompted_dungeon_layout",
            context=command.context,
            model_task_profile_id=command.model_task_profile_id,
            model_lineage=command.model_lineage,
            tool_runs=command.tool_runs,
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
            parent_version_id=command.parent_version_id,
            request=request,
            change_summary=command.change_summary,
            created_by=command.created_by,
        )

    def export(self, command: ExportDungeonWorkflow) -> tuple[uuid.UUID, ...]:
        snapshot = self._preparation.get_version(
            command.campaign_id,
            command.artifact_version_id,
        )
        specification = _load_specification(snapshot.specification)
        assets = _export_assets(specification.package)
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
        artifact_id: uuid.UUID,
        parent_version_id: uuid.UUID | None,
        request: LayoutRequest,
        change_summary: str,
        created_by: str,
        generation_kind: str = "dungeon_layout",
        context: GenerationContextPin | None = None,
        model_task_profile_id: uuid.UUID | None = None,
        model_lineage: tuple[PromptedDungeonModelLineage, ...] = (),
        tool_runs: tuple[ToolRunPin, ...] = (),
    ) -> DungeonWorkflowResult:
        request_document = json.loads(to_canonical_json(request))
        input_scope: dict[str, JsonValue] = {
            "artifact_id": str(artifact_id),
            "layout_request_sha256": canonical_json_sha256(request_document),
            "package_id": request.package_id,
        }
        schema_versions: dict[str, str] = {
            "dungeon_brief": request.brief.schema_version,
            "dungeon_topology": request.topology.schema_version,
            "layout_request": request.schema_version,
            "dungeon_package": "1.0.0",
            "dungeon_studio": _STUDIO_SCHEMA_VERSION,
        }
        if model_lineage:
            input_scope["model_lineage_sha256"] = canonical_json_sha256(
                {
                    "model_lineage": [
                        item.model_dump(mode="json") for item in model_lineage
                    ]
                }
            )
            schema_versions["dungeon_generation_intent"] = model_lineage[
                -1
            ].intent.schema_version
            schema_versions["model_run"] = "1.0.0"
        run = self._preparation.start_generation_run(
            StartGenerationRun(
                campaign_id=campaign_id,
                generation_kind=generation_kind,
                seed=request.seed,
                input_scope=input_scope,
                context=context,
                schema_versions=schema_versions,
                generator_versions={
                    "dungeon_kernel": dm_dungeon.__version__,
                    "layout": request.generator_version,
                },
                renderer_versions={
                    "svg": "svg-v1",
                    "png": "png-v1",
                    "pdf": "pdf-v1",
                    "roll20": "roll20-v1",
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
            preview_assets = _preview_assets(package)
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
        specification = DungeonStudioSpecification(
            schema_version=_STUDIO_SCHEMA_VERSION,
            layout_request=request,
            package=package,
            model_lineage=model_lineage,
        )
        self._preparation.finish_generation_run(
            FinishGenerationRun(
                campaign_id=campaign_id,
                run_id=run.id,
                status=GenerationStatus.SUCCEEDED,
                validation_report=validation_report,
            )
        )
        version = self._preparation.create_artifact_version(
            CreateArtifactVersion(
                campaign_id=campaign_id,
                artifact_id=artifact_id,
                parent_version_id=parent_version_id,
                schema_version=_VERSION_SCHEMA,
                specification=specification.model_dump(mode="json"),
                validation_report=validation_report,
                change_summary=change_summary,
                generation_run_id=run.id,
                created_by=created_by,
            )
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
        )
        for asset in (*base_assets, *preview_assets):
            self._preparation.attach_asset(
                AttachArtifactAsset(
                    campaign_id=campaign_id,
                    artifact_version_id=version.id,
                    role=asset.role,
                    ordinal=asset.ordinal,
                    media_type=asset.media_type,
                    data=asset.data,
                )
            )
        _log_generation_result(run_id=run.id, stage="completed", diagnostics=())
        return DungeonWorkflowResult(
            success=True,
            artifact_id=artifact_id,
            artifact_version_id=version.id,
            generation_run_id=run.id,
            diagnostics=diagnostics,
        )


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


def _preview_assets(package: DungeonPackage) -> tuple[_PendingAsset, ...]:
    assets: list[_PendingAsset] = []
    for floor_index, floor in enumerate(package.floors):
        for audience_index, audience in enumerate(RenderAudience):
            ordinal = floor_index * 2 + audience_index
            svg = render_svg(
                package,
                SvgRenderRequest(
                    schema_version="1.0.0",
                    package_id=package.id,
                    floor_id=floor.id,
                    audience=audience,
                    pixels_per_cell=64,
                    show_grid=True,
                    show_labels=True,
                    show_room_ids=audience is RenderAudience.DM,
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
                package,
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


def _export_assets(package: DungeonPackage) -> tuple[_PendingAsset, ...]:
    assets: list[_PendingAsset] = []
    for floor_index, floor in enumerate(package.floors):
        for audience_index, audience in enumerate(RenderAudience):
            audience_ordinal = floor_index * 2 + audience_index
            pdf = export_pdf(
                package,
                PdfExportRequest(
                    schema_version="1.0.0",
                    package_id=package.id,
                    floor_id=floor.id,
                    audience=audience,
                    maximum_ink_coverage_basis_points=5000,
                ),
            )
            _append_pdf_assets(assets, pdf, floor_index, audience, audience_ordinal)
            roll20 = export_roll20_bundle(
                package,
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


def _append_pdf_assets(
    assets: list[_PendingAsset],
    pdf: PdfArtifact,
    floor_index: int,
    audience: RenderAudience,
    audience_ordinal: int,
) -> None:
    if not pdf.result.success or pdf.data is None or pdf.result.manifest is None:
        raise ConflictError("Dungeon PDF export failed.")
    role = (
        ArtifactAssetRole.DM_PRINT_PDF
        if audience is RenderAudience.DM
        else ArtifactAssetRole.PLAYER_PRINT_PDF
    )
    assets.extend(
        (
            _PendingAsset(role, floor_index, "application/pdf", pdf.data),
            _PendingAsset(
                ArtifactAssetRole.MANIFEST,
                1000 + audience_ordinal,
                "application/json",
                to_canonical_json(pdf.result.manifest).encode(),
            ),
        )
    )


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
    known.update(item.id for item in package.doors)
    known.update(item.id for item in package.stairs)
    known.update(item.id for item in package.vertical_links)
    if not selected <= known:
        raise ConflictError("A requested locked component does not exist.")
    return LockedLayoutComponents(
        floors=tuple(item for item in package.floors if item.id in selected),
        rooms=tuple(item for item in package.rooms if item.id in selected),
        corridors=tuple(item for item in package.corridors if item.id in selected),
        doors=tuple(item for item in package.doors if item.id in selected),
        stairs=tuple(item for item in package.stairs if item.id in selected),
        vertical_links=tuple(
            item for item in package.vertical_links if item.id in selected
        ),
    )


def _component_documents(package: DungeonPackage) -> dict[str, object]:
    documents: dict[str, object] = {}
    for category in (
        "floors",
        "rooms",
        "corridors",
        "doors",
        "stairs",
        "vertical_links",
        "features",
        "terrain",
        "hazards",
        "zones",
        "labels",
        "encounter_slots",
        "position_anchors",
    ):
        for component in getattr(package, category):
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
