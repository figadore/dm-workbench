"""DM Assistant command-line entry point."""

import json
import secrets
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID, uuid4

import typer
from pydantic import BaseModel, JsonValue

from dm_assistant import __version__
from dm_assistant.adapters.assets import AssetCorruptionError, AssetStorageError
from dm_assistant.adapters.model_gateway import (
    GatewayCatalogModel,
    GatewayLoginEvent,
    GatewayProvider,
    ModelGatewayTransportError,
    PiGatewayClient,
)
from dm_assistant.campaigns import CampaignCatalog
from dm_assistant.config import RuntimeEnvironment
from dm_assistant.doctor import (
    collect_doctor_report,
    render_doctor_human,
    render_doctor_json,
)
from dm_assistant.errors import (
    AssetStorageUnavailableError,
    DomainError,
    DungeonExecutionFailedError,
    InvalidInputError,
    ModelRunRejectedError,
    format_cli_error,
)
from dm_assistant.modules.library import (
    AuthorityClass,
    CorpusKind,
    DocumentType,
    IngestSource,
    LexicalSearchQuery,
    RevisionClassification,
    Ruleset,
    SourceLocator,
    SourceScope,
    SourceVisibility,
    VisibilityLabel,
)
from dm_assistant.modules.modeling import (
    GatewayModelCatalogEntry,
    ModelEndpointProfile,
    PromptMessage,
    ReasoningEffort,
    ReasoningLevel,
    ResolvedModelRunProfile,
    TaskModelSelection,
    TaskProfile,
    resolve_run_profile,
    supported_from_reasoning,
)
from dm_assistant.modules.scope import TaskType, resolve_task_scope
from dm_assistant.orchestration.dungeons import (
    CreateDungeonWorkflow,
    ExportDungeonWorkflow,
    PromptDungeonWorkflow,
    RegenerateDungeonWorkflow,
    resolve_dungeon_v2_prompt_profile,
)
from dm_assistant.orchestration.modeling import ModelRunAbstained
from dm_assistant.paths import resolve_allowlisted_file
from dm_assistant.runtime import workbench_runtime
from dm_dungeon import read_layout_request

app = typer.Typer(
    name="dm",
    help="DM Assistant Workbench.",
    no_args_is_help=True,
    add_completion=False,
)
campaign_app = typer.Typer(
    name="campaign",
    help="Minimal campaign-root administration.",
    no_args_is_help=True,
)
dungeon_app = typer.Typer(
    name="dungeon",
    help="Provider-independent Dungeon Studio workflows.",
    no_args_is_help=True,
)
library_app = typer.Typer(
    name="library",
    help="Immutable source documents and scoped lexical search.",
    no_args_is_help=True,
)
run_app = typer.Typer(
    name="run",
    help="Safe durable dungeon prompt-attempt inspection.",
    no_args_is_help=True,
)
model_app = typer.Typer(
    name="model",
    help="Private model-gateway provider setup and inspection.",
    no_args_is_help=True,
)
app.add_typer(campaign_app, name="campaign")
app.add_typer(dungeon_app, name="dungeon")
app.add_typer(library_app, name="library")
dungeon_app.add_typer(run_app, name="run")
app.add_typer(model_app, name="model")


@app.callback()
def main() -> None:
    """Run DM Assistant commands."""


@app.command()
def version() -> None:
    """Show the installed DM Assistant version."""
    typer.echo(__version__)


@app.command()
def doctor(
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit deterministic JSON instead of text."),
    ] = False,
) -> None:
    """Check safe configuration, database, extension, and schema readiness."""
    report = collect_doctor_report()
    output = render_doctor_json(report) if json_output else render_doctor_human(report)
    typer.echo(output)
    if not report.ready:
        raise typer.Exit(code=1)


@campaign_app.command("create")
def campaign_create(name: str) -> None:
    """Create the initial campaign root; this does not commit campaign facts."""
    with _render_domain_errors():
        with workbench_runtime() as runtime:
            campaign = runtime.campaigns.create_campaign(name)
            typer.echo(
                json.dumps(
                    {
                        "id": str(campaign.id),
                        "name": campaign.name,
                        "active": campaign.active,
                    },
                    separators=(",", ":"),
                    sort_keys=True,
                )
            )


@campaign_app.command("list")
def campaign_list() -> None:
    """List safe campaign roots and the inspectable active default."""
    with _render_domain_errors():
        with workbench_runtime() as runtime:
            runtime.campaigns.ensure_active_campaign()
            typer.echo(
                json.dumps(
                    [
                        {
                            "id": str(campaign.id),
                            "name": campaign.name,
                            "active": campaign.active,
                        }
                        for campaign in runtime.campaigns.list_campaigns()
                    ],
                    separators=(",", ":"),
                    sort_keys=True,
                )
            )


@campaign_app.command("use")
def campaign_use(campaign: str) -> None:
    """Switch the inspectable active campaign by exact UUID or name."""
    with _render_domain_errors():
        with workbench_runtime() as runtime:
            selected = runtime.campaigns.use_campaign(campaign)
            typer.echo(
                json.dumps(
                    {
                        "id": str(selected.id),
                        "name": selected.name,
                        "active": selected.active,
                    },
                    separators=(",", ":"),
                    sort_keys=True,
                )
            )


@library_app.command("ingest")
def library_ingest(
    relative_path: str,
    campaign_id: Annotated[UUID | None, typer.Option("--campaign")] = None,
    corpus: Annotated[CorpusKind, typer.Option("--corpus")] = CorpusKind.CAMPAIGN,
    root: Annotated[str, typer.Option("--root")] = "root-0",
    title: Annotated[str, typer.Option("--title")] = "Source document",
    document_type: Annotated[DocumentType, typer.Option("--document-type")] = (
        DocumentType.REFERENCE_LORE
    ),
    authority: Annotated[AuthorityClass, typer.Option("--authority")] = (
        AuthorityClass.REFERENCE
    ),
    visibility: Annotated[SourceVisibility, typer.Option("--visibility")] = (
        SourceVisibility.DM_ONLY
    ),
    ruleset: Annotated[Ruleset | None, typer.Option("--ruleset")] = None,
) -> None:
    """Ingest one allowlisted Markdown/text source as an immutable revision."""
    with _render_domain_errors():
        with workbench_runtime() as runtime:
            resolved_campaign_id = campaign_id
            if corpus is CorpusKind.CAMPAIGN and resolved_campaign_id is None:
                resolved_campaign_id = runtime.campaigns.ensure_active_campaign().id
            _emit_model(
                runtime.library_sources.ingest(
                    IngestSource(
                        scope=SourceScope(
                            campaign_id=resolved_campaign_id,
                            corpus=corpus,
                        ),
                        locator=SourceLocator(
                            root_label=root,
                            relative_path=relative_path,
                        ),
                        classification=RevisionClassification(
                            corpus=corpus,
                            document_type=document_type,
                            authority_class=authority,
                            ruleset=ruleset,
                            visibility=VisibilityLabel(policy=visibility),
                        ),
                        title=title,
                    )
                )
            )


@library_app.command("documents")
def library_documents(
    campaign_id: Annotated[UUID | None, typer.Option("--campaign")] = None,
    corpus: Annotated[CorpusKind, typer.Option("--corpus")] = CorpusKind.CAMPAIGN,
) -> None:
    """List immutable Library documents in one campaign/rules scope."""
    with _render_domain_errors():
        with workbench_runtime() as runtime:
            scope = SourceScope(campaign_id=campaign_id, corpus=corpus)
            typer.echo(
                json.dumps(
                    [
                        {
                            "id": str(item.id),
                            "source_path": item.source_path,
                            "retired": item.retired,
                        }
                        for item in runtime.library_catalog.list_documents(scope)
                    ],
                    separators=(",", ":"),
                    sort_keys=True,
                )
            )


@library_app.command("show-document")
def library_show_document(
    document_id: UUID,
    campaign_id: Annotated[UUID | None, typer.Option("--campaign")] = None,
    corpus: Annotated[CorpusKind, typer.Option("--corpus")] = CorpusKind.CAMPAIGN,
    revision_id: Annotated[UUID | None, typer.Option("--revision")] = None,
) -> None:
    """Show one immutable document revision, latest by default."""
    with _render_domain_errors():
        with workbench_runtime() as runtime:
            detail = runtime.library_catalog.show_document(
                SourceScope(campaign_id=campaign_id, corpus=corpus),
                document_id,
                revision_id,
            )
            typer.echo(
                json.dumps(
                    {
                        "id": str(detail.id),
                        "source_path": detail.source_path,
                        "revision_id": str(detail.revision_id),
                        "revision_number": detail.revision_number,
                        "content_hash": detail.content_hash,
                        "content": detail.content_snapshot,
                        "title": detail.title,
                        "document_type": detail.document_type,
                        "authority_class": detail.authority_class,
                        "ruleset": detail.ruleset,
                        "visibility_policy": detail.visibility_policy,
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                )
            )


@library_app.command("search")
def library_search(
    query: str,
    campaign_id: Annotated[UUID | None, typer.Option("--campaign")] = None,
    corpus: Annotated[CorpusKind, typer.Option("--corpus")] = CorpusKind.CAMPAIGN,
    include_preparation: Annotated[bool, typer.Option("--include-preparation")] = False,
) -> None:
    """Search the active snapshot and return scoped immutable citations."""
    with _render_domain_errors():
        with workbench_runtime() as runtime:
            scope = SourceScope(campaign_id=campaign_id, corpus=corpus)
            results = runtime.library_search.search(
                LexicalSearchQuery(
                    scope=scope,
                    query=query,
                    include_preparation=include_preparation,
                    visible_policies=(SourceVisibility.DM_ONLY,),
                )
            )
            typer.echo(
                json.dumps(
                    {
                        "scope": {
                            "campaign_id": str(campaign_id)
                            if campaign_id is not None
                            else None,
                            "corpus": corpus.value,
                        },
                        "results": [item.model_dump(mode="json") for item in results],
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                )
            )


@model_app.command("providers")
def model_providers() -> None:
    """List gateway providers, models, capabilities, and auth state."""
    with _render_domain_errors():
        with workbench_runtime() as runtime:
            gateway = _require_model_gateway(runtime.model_gateway)
            _emit_models(gateway.providers())


@model_app.command("smoke")
def model_smoke(
    prompt: Annotated[
        str, typer.Argument(help="Short non-sensitive provider probe.")
    ] = "Reply with OK.",
    provider: Annotated[str, typer.Option("--provider")] = "openai-codex",
    model: Annotated[str, typer.Option("--model")] = "gpt-5.4",
    effort: Annotated[
        ReasoningEffort, typer.Option("--effort")
    ] = ReasoningEffort.STANDARD,
) -> None:
    """Send one minimal text-only request through the private pi-ai gateway."""
    with _render_domain_errors():
        with workbench_runtime() as runtime:
            gateway = _require_model_gateway(runtime.model_gateway)
            selected_provider = next(
                (item for item in gateway.providers() if item.id == provider), None
            )
            if selected_provider is None:
                raise InvalidInputError("The selected model provider is unavailable.")
            if not selected_provider.authenticated:
                raise InvalidInputError("The selected model provider requires login.")
            selected_model = next(
                (item for item in selected_provider.models if item.id == model), None
            )
            if selected_model is None or "text" not in selected_model.capabilities:
                raise InvalidInputError("The selected text model is unavailable.")
            completion = gateway.complete(
                profile=_provider_smoke_profile(
                    selected_provider, selected_model, effort
                ),
                messages=(PromptMessage(role="user", content=prompt),),
                allowed_tools=(),
                tool_schemas=(),
            )
            if completion.content is None:
                raise InvalidInputError("The selected model returned no text response.")
            _emit_document(
                {
                    "provider": selected_provider.id,
                    "model": selected_model.id,
                    "effort": effort.value,
                    "response": completion.content,
                    "usage": {
                        "input_tokens": completion.input_tokens,
                        "output_tokens": completion.output_tokens,
                    },
                }
            )


@model_app.command("login")
def model_login(
    provider: str,
    auth_type: Annotated[str, typer.Option("--type")] = "oauth",
) -> None:
    """Start provider login; use login-status/login-respond until complete."""
    with _render_domain_errors():
        with workbench_runtime() as runtime:
            gateway = _require_model_gateway(runtime.model_gateway)
            _emit_model(gateway.start_login(provider, auth_type))


@model_app.command("login-status")
def model_login_status(login_id: str) -> None:
    """Poll non-secret progress for a gateway-owned provider login."""
    with _render_domain_errors():
        with workbench_runtime() as runtime:
            gateway = _require_model_gateway(runtime.model_gateway)
            _emit_model(gateway.login_status(login_id))


@model_app.command("login-respond")
def model_login_respond(login_id: str, prompt_id: str) -> None:
    """Answer an OAuth coordination prompt without placing it in shell history."""
    value = typer.prompt("Response", hide_input=True)
    with _render_domain_errors():
        with workbench_runtime() as runtime:
            gateway = _require_model_gateway(runtime.model_gateway)
            gateway.respond_to_login(login_id, prompt_id, value)
            typer.echo('{"accepted":true}')


@model_app.command("logout")
def model_logout(provider: str) -> None:
    """Remove one provider credential from the private gateway store."""
    with _render_domain_errors():
        with workbench_runtime() as runtime:
            gateway = _require_model_gateway(runtime.model_gateway)
            gateway.logout(provider)
            typer.echo('{"logged_out":true}')


@dungeon_app.command("prompt")
def dungeon_prompt(
    prompt: Annotated[str, typer.Argument(help="Standalone dungeon request.")],
    campaign_id: Annotated[UUID | None, typer.Option("--campaign")] = None,
    provider: Annotated[str | None, typer.Option("--provider")] = None,
    model: Annotated[str | None, typer.Option("--model")] = None,
    seed: Annotated[int | None, typer.Option("--seed")] = None,
    title: Annotated[str | None, typer.Option("--title")] = None,
    effort: Annotated[ReasoningEffort | None, typer.Option("--effort")] = None,
    constraint: Annotated[list[str] | None, typer.Option("--constraint")] = None,
    debug: Annotated[
        bool,
        typer.Option(
            "--debug",
            help="Stream the model/harness exchange to stderr; it is not persisted.",
        ),
    ] = False,
    created_by: Annotated[str, typer.Option("--created-by")] = "dm",
) -> None:
    """Generate a standalone draft with active campaign and model defaults."""
    with _render_domain_errors():
        with workbench_runtime() as runtime:
            gateway = _require_model_gateway(runtime.model_gateway)
            prompted = runtime.dungeon_prompt_application
            if prompted is None:
                raise InvalidInputError("The model gateway is not enabled.")
            resolved_campaign_id = (
                campaign_id
                if campaign_id is not None
                else runtime.campaigns.ensure_active_campaign().id
            )
            selected_provider, selected_model, selected_effort = (
                _resolve_dungeon_model_selection(
                    gateway=gateway,
                    saved=runtime.model_selections.get("dungeon_generation_intent_v1"),
                    provider_override=provider,
                    model_override=model,
                    effort_override=effort,
                    allow_faux=(
                        runtime.settings.environment is RuntimeEnvironment.TEST
                    ),
                )
            )
            typer.echo(
                f"Using {selected_model.name} via {selected_provider.name} "
                f"at {selected_effort.value} effort.",
                err=True,
            )
            runtime.model_selections.save(
                task_name="dungeon_generation_intent_v1",
                provider_id=selected_provider.id,
                model_id=selected_model.id,
                effort=selected_effort,
                selection_policy="dungeon-task-baseline-v2",
            )
            resolved_seed = seed if seed is not None else secrets.randbits(63)
            try:
                profile = resolve_dungeon_v2_prompt_profile(
                    provider_id=selected_provider.id,
                    model_id=selected_model.id,
                    capabilities=selected_model.capabilities,
                    context_window_tokens=selected_model.context_window,
                    output_token_limit=selected_model.max_output_tokens,
                    requested_effort=selected_effort,
                )
                attempt = prompted.execute(
                    PromptDungeonWorkflow(
                        campaign_id=resolved_campaign_id,
                        title=title,
                        prompt=prompt,
                        seed=resolved_seed,
                        created_by=created_by,
                        scope=resolve_task_scope(
                            dm_principal_id=created_by,
                            campaign_owner_id=created_by,
                            task_type=TaskType.STANDALONE_DUNGEON,
                        ),
                        requested_constraints=tuple(constraint or ()),
                    ),
                    profile,
                    surface="cli",
                    debug=_emit_debug_event if debug else None,
                )
                if attempt.result is None:
                    raise ModelRunAbstained(attempt.public_code)
                result = attempt.result
            except ModelGatewayTransportError as error:
                raise InvalidInputError(str(error)) from None
            except ModelRunAbstained as error:
                raise _model_run_rejected_error(error) from None
            except AssetCorruptionError as error:
                raise _prompt_execution_error(error) from None
            except AssetStorageError as error:
                raise _prompt_execution_error(error) from None
            except ValueError as error:
                raise _prompt_execution_error(error) from None
            except Exception as error:
                raise _prompt_execution_error(error) from None
            resolved_title = title
            if result.success:
                assert result.artifact_id is not None
                resolved_title = runtime.dungeons.inspect(
                    campaign_id=resolved_campaign_id,
                    artifact_id=result.artifact_id,
                ).title
            _emit_document(
                {
                    **result.model_dump(mode="json"),
                    "resolved": {
                        "campaign_id": str(resolved_campaign_id),
                        "provider": selected_provider.id,
                        "model": selected_model.id,
                        "effort": selected_effort.value,
                        "seed": resolved_seed,
                        "title": resolved_title,
                    },
                }
            )
            if not result.success:
                _emit_dungeon_failure_summary(result.diagnostics)
                raise typer.Exit(code=1)


@run_app.command("inspect")
def dungeon_run_inspect(
    attempt_run_id: Annotated[
        UUID, typer.Argument(help="Durable prompt attempt UUID.")
    ],
    campaign_id: Annotated[UUID | None, typer.Option("--campaign")] = None,
) -> None:
    """Show safe attempt metadata without prompt, provider, or context bodies."""
    with _render_domain_errors():
        with workbench_runtime() as runtime:
            resolved_campaign_id = (
                campaign_id or runtime.campaigns.ensure_active_campaign().id
            )
            run = runtime.preparation.get_generation_run(
                resolved_campaign_id, attempt_run_id
            )
            _emit_document(
                {
                    "attempt_run_id": str(run.id),
                    "status": run.status.value,
                    "generation_kind": run.generation_kind,
                    "seed": run.seed,
                    "input_scope": run.input_scope,
                    "schema_versions": run.schema_versions,
                    "generator_versions": run.generator_versions,
                    "validation_report": run.validation_report,
                }
            )


@dungeon_app.command("generate")
def dungeon_generate(
    input_path: Annotated[Path, typer.Argument(help="Allowlisted LayoutRequest JSON.")],
    title: Annotated[str, typer.Option("--title")],
    campaign_id: Annotated[UUID | None, typer.Option("--campaign")] = None,
    created_by: Annotated[str, typer.Option("--created-by")] = "dm",
) -> None:
    """Generate, validate, preview, and persist a hand-authored layout request."""
    with _render_domain_errors():
        with workbench_runtime() as runtime:
            safe_path = resolve_allowlisted_file(
                input_path,
                runtime.settings.source_roots,
                maximum_bytes=2_000_000,
            )
            try:
                request = read_layout_request(safe_path)
            except (OSError, ValueError):
                raise InvalidInputError("The layout request is invalid.") from None
            result = runtime.dungeons.create(
                CreateDungeonWorkflow(
                    campaign_id=_active_campaign_id(runtime.campaigns, campaign_id),
                    title=title,
                    layout_request=request,
                    created_by=created_by,
                )
            )
            _emit_model(result)
            if not result.success:
                raise typer.Exit(code=1)


@dungeon_app.command("inspect")
def dungeon_inspect(
    artifact_id: UUID,
    campaign_id: Annotated[UUID | None, typer.Option("--campaign")] = None,
) -> None:
    """Inspect lifecycle and immutable version lineage."""
    with _render_domain_errors():
        with workbench_runtime() as runtime:
            _emit_model(
                runtime.dungeons.inspect(
                    campaign_id=_active_campaign_id(runtime.campaigns, campaign_id),
                    artifact_id=artifact_id,
                )
            )


@dungeon_app.command("compare")
def dungeon_compare(
    left_version_id: UUID,
    right_version_id: UUID,
    campaign_id: Annotated[UUID | None, typer.Option("--campaign")] = None,
) -> None:
    """Compare exact component IDs across two versions in one lineage."""
    with _render_domain_errors():
        with workbench_runtime() as runtime:
            _emit_model(
                runtime.dungeons.compare(
                    campaign_id=_active_campaign_id(runtime.campaigns, campaign_id),
                    left_version_id=left_version_id,
                    right_version_id=right_version_id,
                )
            )


@dungeon_app.command("regenerate")
def dungeon_regenerate(
    artifact_id: UUID,
    parent_version_id: UUID,
    seed: Annotated[int, typer.Option("--seed")],
    campaign_id: Annotated[UUID | None, typer.Option("--campaign")] = None,
    lock: Annotated[list[str] | None, typer.Option("--lock")] = None,
    summary: Annotated[str, typer.Option("--summary")] = "Regenerate dungeon.",
    created_by: Annotated[str, typer.Option("--created-by")] = "dm",
) -> None:
    """Regenerate from a parent while preserving selected exact components."""
    with _render_domain_errors():
        with workbench_runtime() as runtime:
            result = runtime.dungeons.regenerate(
                RegenerateDungeonWorkflow(
                    campaign_id=_active_campaign_id(runtime.campaigns, campaign_id),
                    artifact_id=artifact_id,
                    parent_version_id=parent_version_id,
                    seed=seed,
                    locked_component_ids=tuple(lock or ()),
                    change_summary=summary,
                    created_by=created_by,
                )
            )
            _emit_model(result)
            if not result.success:
                raise typer.Exit(code=1)


@dungeon_app.command("export")
def dungeon_export(
    artifact_version_id: UUID,
    export_format: Annotated[
        Literal["roll20", "pdf"],
        typer.Option("--format", help="Export family: roll20 or pdf."),
    ] = "roll20",
    campaign_id: Annotated[UUID | None, typer.Option("--campaign")] = None,
) -> None:
    """Create one selected export family for the current draft."""
    with _render_domain_errors():
        with workbench_runtime() as runtime:
            asset_ids = runtime.dungeons.export(
                ExportDungeonWorkflow(
                    campaign_id=_active_campaign_id(runtime.campaigns, campaign_id),
                    artifact_version_id=artifact_version_id,
                    export_format=export_format,
                )
            )
            typer.echo(
                json.dumps(
                    {"asset_ids": [str(item) for item in asset_ids]},
                    separators=(",", ":"),
                    sort_keys=True,
                )
            )


@dungeon_app.command("approve")
def dungeon_approve(
    artifact_id: UUID,
    artifact_version_id: UUID,
    reason: Annotated[str, typer.Option("--reason")],
    campaign_id: Annotated[UUID | None, typer.Option("--campaign")] = None,
    actor: Annotated[str, typer.Option("--actor")] = "dm",
) -> None:
    """Explicitly approve preparation for play; this never commits campaign canon."""
    with _render_domain_errors():
        with workbench_runtime() as runtime:
            _emit_model(
                runtime.dungeons.approve(
                    campaign_id=_active_campaign_id(runtime.campaigns, campaign_id),
                    artifact_id=artifact_id,
                    artifact_version_id=artifact_version_id,
                    actor=actor,
                    reason=reason,
                )
            )


def _active_campaign_id(
    campaigns: CampaignCatalog,
    override: UUID | None,
) -> UUID:
    return override if override is not None else campaigns.ensure_active_campaign().id


def _resolve_dungeon_model_selection(
    *,
    gateway: PiGatewayClient,
    saved: TaskModelSelection | None,
    provider_override: str | None,
    model_override: str | None,
    effort_override: ReasoningEffort | None,
    allow_faux: bool,
) -> tuple[GatewayProvider, GatewayCatalogModel, ReasoningEffort]:
    providers = gateway.providers()
    if saved is not None and saved.selection_policy != "dungeon-task-baseline-v2":
        saved = None
    requested_provider = provider_override or (
        saved.provider_id if saved is not None else None
    )
    selected_provider = next(
        (item for item in providers if item.id == requested_provider), None
    )
    if provider_override is not None and selected_provider is None:
        raise InvalidInputError("The selected model provider is unavailable.")

    if selected_provider is None:
        selected_provider = _default_provider(providers, allow_faux=allow_faux)
    if selected_provider is None:
        login_provider = _default_login_provider(providers)
        if login_provider is None:
            raise InvalidInputError("No compatible model provider is available.")
        _complete_provider_login(gateway, login_provider)
        providers = gateway.providers()
        selected_provider = next(
            (item for item in providers if item.id == login_provider.id), None
        )
        if selected_provider is None:
            raise InvalidInputError("The model provider became unavailable.")

    if not selected_provider.authenticated:
        if selected_provider.id == "faux" and allow_faux:
            pass
        elif "oauth" in selected_provider.auth_modes:
            _complete_provider_login(gateway, selected_provider)
            selected_provider = next(
                (
                    item
                    for item in gateway.providers()
                    if item.id == selected_provider.id
                ),
                None,
            )
            if selected_provider is None or not selected_provider.authenticated:
                raise InvalidInputError("Model provider login did not complete.")
        else:
            raise InvalidInputError("The selected model provider requires login.")

    requested_model = model_override or (
        saved.model_id
        if saved is not None and saved.provider_id == selected_provider.id
        else None
    )
    selected_model = next(
        (item for item in selected_provider.models if item.id == requested_model), None
    )
    if model_override is not None and selected_model is None:
        raise InvalidInputError("The selected model is unavailable.")
    if selected_model is None:
        selected_model = _default_model(
            selected_provider.models,
            selected_provider.id,
        )
    if selected_model is None:
        raise InvalidInputError("No compatible tool-capable model is available.")

    selected_effort = effort_override or (
        saved.effort
        if saved is not None
        and saved.provider_id == selected_provider.id
        and saved.model_id == selected_model.id
        else ReasoningEffort.STANDARD
    )
    return selected_provider, selected_model, selected_effort


def _provider_smoke_profile(
    provider: GatewayProvider,
    model: GatewayCatalogModel,
    effort: ReasoningEffort,
) -> ResolvedModelRunProfile:
    """Build an intentionally tool-free, short-lived profile for transport smoke tests."""
    reasoning_levels = (
        (ReasoningLevel.LOW, ReasoningLevel.MEDIUM, ReasoningLevel.HIGH)
        if "thinking" in model.capabilities
        else (ReasoningLevel.MEDIUM,)
    )
    supported_efforts = supported_from_reasoning(reasoning_levels)
    endpoint = ModelEndpointProfile(
        profile_id=uuid4(),
        profile_version="1.0.0",
        runtime_adapter="pi_ai",
        provider_id=provider.id,
        model_id=model.id,
        supported_efforts=supported_efforts,
        default_effort=ReasoningEffort.STANDARD,
        observed_capabilities=model.capabilities,
        context_window_tokens=model.context_window,
        output_token_limit=min(model.max_output_tokens, 256),
    )
    task = TaskProfile(
        profile_id=uuid4(),
        profile_version="1.0.0",
        task_name="provider_transport_smoke_v1",
        prompt_version="1.0.0",
        instruction_version="1.0.0",
        output_schema_name="plain_text",
        output_schema_version="1.0.0",
        allowed_tools=(),
        turn_budget=1,
        tool_budget=0,
        time_budget_seconds=30,
        token_budget=256,
        require_citation_ids=False,
        require_authorized_citations=False,
    )
    catalog = GatewayModelCatalogEntry(
        provider_id=provider.id,
        model_id=model.id,
        runtime_adapter="pi_ai",
        observed_capabilities=model.capabilities,
        supported_reasoning_levels=reasoning_levels,
        context_window_tokens=model.context_window,
        output_token_limit=min(model.max_output_tokens, 256),
    )
    return resolve_run_profile(
        endpoint_profile=endpoint,
        task_profile=task,
        catalog_entry=catalog,
        requested_effort=effort,
    )


def _default_provider(
    providers: tuple[GatewayProvider, ...], *, allow_faux: bool
) -> GatewayProvider | None:
    candidates = tuple(
        provider
        for provider in providers
        if provider.authenticated
        and (allow_faux or provider.id != "faux")
        and _default_model(provider.models, provider.id) is not None
    )
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: item.id)[0]


def _default_login_provider(
    providers: tuple[GatewayProvider, ...],
) -> GatewayProvider | None:
    candidates = tuple(
        sorted(
            (
                provider
                for provider in providers
                if provider.id != "faux"
                and "oauth" in provider.auth_modes
                and _default_model(provider.models, provider.id) is not None
            ),
            key=lambda item: item.id,
        )
    )
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    typer.echo("Available subscription model providers:", err=True)
    for candidate in candidates:
        typer.echo(f"  {candidate.id}: {candidate.name}", err=True)
    selected_id = typer.prompt(
        "Select model provider",
        default=candidates[0].id,
        show_default=True,
        err=True,
    )
    selected = next((item for item in candidates if item.id == selected_id), None)
    if selected is None:
        raise InvalidInputError("The selected model provider is unavailable.")
    return selected


def _default_model(
    models: tuple[GatewayCatalogModel, ...],
    provider_id: str,
) -> GatewayCatalogModel | None:
    compatible = tuple(
        model for model in models if {"text", "tool_calls"}.issubset(model.capabilities)
    )
    if not compatible:
        return None
    # Pinned task baselines avoid choosing a model merely because it advertises
    # the largest context/output limits. Revisit through the P7 eval gate.
    preferred_ids = {
        "github-copilot": ("gpt-4.1", "gpt-5-mini"),
        "openai-codex": ("gpt-5.4-mini", "gpt-5.4"),
    }.get(provider_id, ())
    by_id = {model.id: model for model in compatible}
    for preferred_id in preferred_ids:
        if preferred_id in by_id:
            return by_id[preferred_id]
    return sorted(compatible, key=lambda item: item.id)[0]


def _complete_provider_login(
    gateway: PiGatewayClient,
    provider: GatewayProvider,
) -> None:
    typer.echo(f"Starting login for {provider.name}...", err=True)
    session = gateway.start_login(provider.id, "oauth")
    seen_events = 0
    deadline = time.monotonic() + 600
    while True:
        for event in session.events[seen_events:]:
            _render_login_event(gateway, session.login_id, event)
        seen_events = len(session.events)
        if session.status == "completed":
            typer.echo("Model provider login completed.", err=True)
            return
        if session.status == "failed":
            raise InvalidInputError("Model provider login failed.")
        if time.monotonic() >= deadline:
            raise InvalidInputError("Model provider login timed out.")
        time.sleep(2)
        session = gateway.login_status(session.login_id)


def _render_login_event(
    gateway: PiGatewayClient,
    login_id: str,
    event: GatewayLoginEvent,
) -> None:
    if event.type == "device_code":
        typer.echo(
            f"Open {event.verification_uri} and enter code {event.user_code}.",
            err=True,
        )
    elif event.type == "auth_url":
        typer.echo(f"Open {event.url} to continue login.", err=True)
    elif event.type == "prompt" and event.prompt_id is not None:
        option_values: dict[str, str] = {}
        if event.options:
            typer.echo("Available login methods:", err=True)
            for option in event.options:
                option_id = option.get("id")
                option_label = option.get("label")
                if isinstance(option_id, str) and isinstance(option_label, str):
                    option_values[option_id] = option_label
                    typer.echo(f"  {option_id}: {option_label}", err=True)
        if "device_code" in option_values:
            value = "device_code"
            typer.echo(
                "Using device-code login for the containerized gateway.",
                err=True,
            )
        elif (
            event.prompt_type == "text"
            and event.message is not None
            and "blank for github.com" in event.message.lower()
        ):
            value = ""
            typer.echo("Using github.com for GitHub Copilot login.", err=True)
        elif event.prompt_type == "text":
            value = typer.prompt(
                event.message or "Login response",
                default="",
                show_default=False,
                err=True,
            )
        else:
            value = typer.prompt(
                event.message or "Login response",
                hide_input=event.prompt_type == "manual_code",
                err=True,
            )
        gateway.respond_to_login(login_id, event.prompt_id, value)
    elif event.message:
        typer.echo(event.message, err=True)


def _emit_debug_event(kind: str, data: dict[str, object]) -> None:
    """Print an explicit, transient transcript without contaminating ordinary logs."""
    typer.echo(
        json.dumps(
            {"debug": kind, "data": data},
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ),
        err=True,
    )


def _emit_dungeon_failure_summary(
    diagnostics: tuple[dict[str, JsonValue], ...],
) -> None:
    """Render persisted deterministic diagnostics for humans as well as JSON clients."""

    typer.echo(
        "Dungeon generation failed deterministic validation; no draft was created.",
        err=True,
    )
    for diagnostic in diagnostics:
        code = diagnostic.get("code")
        message = diagnostic.get("message")
        affected_ids = diagnostic.get("affected_ids")
        repair_hint = diagnostic.get("repair_hint")
        if isinstance(code, str) and isinstance(message, str):
            typer.echo(f"- [{code}] {message}", err=True)
        if isinstance(affected_ids, list):
            identifiers = [item for item in affected_ids if isinstance(item, str)]
            if identifiers and len(identifiers) == len(affected_ids):
                typer.echo(f"  Affected: {', '.join(identifiers)}", err=True)
        if isinstance(repair_hint, str):
            typer.echo(f"  Next step: {repair_hint}", err=True)


def _emit_model(model: BaseModel) -> None:
    _emit_document(model.model_dump(mode="json"))


def _emit_document(document: object) -> None:
    typer.echo(
        json.dumps(
            document,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )


def _emit_models(models: tuple[BaseModel, ...]) -> None:
    typer.echo(
        json.dumps(
            [model.model_dump(mode="json", by_alias=True) for model in models],
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )


def _prompt_execution_error(error: Exception) -> DomainError:
    """Contain non-model prompt failures behind stable, actionable public errors."""

    if isinstance(error, AssetCorruptionError):
        return AssetStorageUnavailableError(
            "Generated assets could not be verified in the asset store. The draft was "
            "not reported as created; inspect and repair the asset volume before retrying."
        )
    if isinstance(error, AssetStorageError):
        return AssetStorageUnavailableError(
            "Generated assets could not be persisted safely. The draft was not reported "
            "as created; verify the asset volume is writable and retry."
        )
    if isinstance(error, ValueError):
        return DungeonExecutionFailedError(
            "The deterministic dungeon workflow rejected an internal typed input. No "
            "draft was reported as created; retry or use the hand-authored Dungeon "
            "Studio workflow."
        )
    return DungeonExecutionFailedError(
        "The dungeon workflow stopped during deterministic generation or persistence. "
        "No draft was reported as created; inspect Workbench logs and retry."
    )


def _model_run_rejected_error(error: ModelRunAbstained) -> ModelRunRejectedError:
    """Convert bounded-run internals into an actionable, response-safe CLI error."""

    reasons = {
        "model output failed schema validation within the repair budget": (
            "The selected model returned dungeon JSON that did not match the required "
            "schema after a repair attempt. No draft was saved; try again or select "
            "another model."
        ),
        "time budget exhausted before a final answer": (
            "The selected model did not finish within the dungeon run time limit. "
            "No draft was saved; try again or select another model."
        ),
        "token budget exhausted before completion": (
            "The selected model exceeded the dungeon run token budget. No draft was "
            "saved; simplify the request or select another model."
        ),
        "turn budget exhausted before a final answer": (
            "The selected model used the available dungeon response turns without a "
            "usable result. No draft was saved; try again or select another model."
        ),
        "no budget remains for deterministic diagnostic repair": (
            "The generated dungeon did not pass deterministic validation within the "
            "repair budget. No draft was saved; try again or use the hand-authored "
            "Dungeon Studio workflow."
        ),
        "dungeon_prompt_repair_usage_unavailable": (
            "The generated dungeon did not pass deterministic validation, and the "
            "model gateway did not report token usage, so the safe automatic repair "
            "could not run. No draft was saved; retry after gateway usage reporting "
            "is available or use the hand-authored Dungeon Studio workflow."
        ),
        "dungeon intent did not include a brief and topology": (
            "The selected model did not return a complete dungeon brief and topology. "
            "No draft was saved; try again or select another model."
        ),
        "dungeon intent run did not succeed": (
            "The selected model did not produce a usable dungeon intent. No draft was "
            "saved; try again or select another model."
        ),
        "the model returned no answer content": (
            "The selected model returned no dungeon content. No draft was saved; try "
            "again or select another model."
        ),
        "tool budget exhausted before completion": (
            "The selected model requested more deterministic dungeon tool work than "
            "this run permits. No draft was saved; try again or select another model."
        ),
    }
    message = reasons.get(str(error))
    if message is None:
        # An intent may contain a model-authored abstain reason. Do not echo it:
        # it is untrusted response text, but the resulting category is actionable.
        message = (
            "The selected model explicitly abstained instead of providing a usable "
            "dungeon intent. No draft was saved; try again, simplify the request, or "
            "select another model."
        )
    return ModelRunRejectedError(message)


def _require_model_gateway(gateway: PiGatewayClient | None) -> PiGatewayClient:
    if gateway is None:
        raise InvalidInputError("The model gateway is not enabled.")
    return gateway


@contextmanager
def _render_domain_errors() -> Iterator[None]:
    try:
        yield
    except DomainError as error:
        typer.echo(format_cli_error(error), err=True)
        raise typer.Exit(code=1) from None
    except ModelGatewayTransportError:
        gateway_error = InvalidInputError("The model gateway is unavailable.")
        typer.echo(format_cli_error(gateway_error), err=True)
        raise typer.Exit(code=1) from None


if __name__ == "__main__":
    app()
